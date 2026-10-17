"""Sicurezza: autenticazione, ruoli, protezione CSRF e registro attività.

- Ogni pagina richiede l'accesso; al primo avvio, senza utenti, si viene
  portati alla configurazione iniziale per creare l'amministratore.
- Tre ruoli: amministratore (tutto, compresi utenti, impostazioni, backup e
  registro), operatore (lavoro quotidiano) e sola consultazione (vede i dati
  ma non apre né invia i moduli di inserimento e modifica).
- Ogni richiesta che modifica dati (POST) deve portare il token CSRF della
  sessione, inserito nei form con ``{{ csrf_field() }}``.
- La sessione (cookie firmato) è legata all'utente da un'impronta e dal
  numero di versione ``User.sessione_versione``: uscita, cambio o reset della
  password, disattivazione, cambio di ruolo e ripristino di un backup la
  invalidano su tutti i dispositivi.
- Le operazioni rilevanti finiscono nel registro attività (``audit``).
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import timedelta
from functools import wraps
from urllib.parse import urlsplit

from flask import (
    Flask,
    abort,
    current_app,
    flash,
    g,
    has_request_context,
    redirect,
    request,
    session,
    url_for,
)
from markupsafe import Markup
from sqlalchemy import func, or_, select, update
from werkzeug.security import check_password_hash

from .models import AuditLog, User, db, now

# Pagine raggiungibili senza aver effettuato l'accesso.
PUBLIC_ENDPOINTS = {"static", "auth.login", "auth.setup"}
# Endpoint consentiti anche al profilo in sola consultazione, sia come modulo
# (GET) sia come invio (POST): non toccano i dati del gestionale.
READONLY_ALLOWED_POST = {
    "auth.logout",
    "auth.change_password",
    "notifications.mark_read",
    "notifications.mark_all_read",
}
# Nomi di endpoint che identificano un modulo di inserimento o modifica anche
# quando la route accetta solo GET (es. un modulo inviato a un'altra route).
PREFISSI_MODULI = ("new_", "edit_", "nuovo", "nuova", "modifica")
# Endpoint che accettano upload più grandi del limite generale (ripristino backup).
LARGE_UPLOAD_ENDPOINTS = {"settings.restore_backup"}
MAX_TENTATIVI_LOGIN = 5
MINUTI_BLOCCO_LOGIN = 15
LUNGHEZZA_MINIMA_PASSWORD = 8
LUNGHEZZA_MASSIMA_USERNAME = 60  # come la colonna users.username

MSG_SESSIONE_SCADUTA = "Sessione scaduta: accedi di nuovo."
MSG_SOLA_CONSULTAZIONE = "Il tuo profilo è in sola consultazione: non puoi modificare i dati."

# Esiti di verifica_password().
ESITO_OK = "ok"
ESITO_ERRATA = "errata"
ESITO_BLOCCATO_ORA = "bloccato_ora"  # questo errore ha fatto scattare il blocco
ESITO_BLOCCATO = "bloccato"  # account già bloccato: password non verificata

# Policy di sicurezza dei contenuti. Nessuno script inline: i comportamenti
# dell'interfaccia sono tutti in static/app.js (data-print, data-autosubmit…).
# Gli stili inline (attributi style, es. larghezza delle barre) restano ammessi.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data:; "
    "font-src 'self'; "
    "connect-src 'self'; "
    "object-src 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "frame-ancestors 'self'"
)

# Caratteri di controllo (C0, DEL, C1): i browser ne eliminano alcuni dagli URL
# («/\t/sito.example» diventa «//sito.example»), quindi non li accettiamo.
_CARATTERI_CONTROLLO = re.compile(r"[\x00-\x1f\x7f-\x9f]")


# ----------------------------------------------------------------------
# CSRF
# ----------------------------------------------------------------------
def csrf_token() -> str:
    token = session.get("_csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        session["_csrf"] = token
    return token


def csrf_field() -> Markup:
    return Markup('<input type="hidden" name="csrf_token" value="%s">') % csrf_token()


def _check_csrf():
    # Il limite alto (ripristino backup) vale solo per gli amministratori: gli
    # altri ricevono 413 subito, senza che il server legga centinaia di MB.
    if request.endpoint in LARGE_UPLOAD_ENDPOINTS and g.get("user") is not None and g.user.is_admin:
        request.max_content_length = current_app.config.get("MAX_RESTORE_SIZE")
    if not current_app.config.get("CSRF_ENABLED", True):
        return None
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return None
    inviato = request.form.get("csrf_token") or request.headers.get("X-CSRFToken") or ""
    atteso = session.get("_csrf") or ""
    if not atteso or not hmac.compare_digest(inviato, atteso):
        abort(400, description="Il modulo è scaduto o non è valido: ricarica la pagina e riprova.")
    return None


# ----------------------------------------------------------------------
# Redirect sicuri (niente open redirect verso siti esterni)
# ----------------------------------------------------------------------
def safe_next(target: str | None, default: str | None = None) -> str | None:
    """Restituisce ``target`` solo se è un percorso relativo di questa applicazione.

    Sono ammessi soltanto percorsi che iniziano con una sola «/» (es.
    ``/clienti/3?tab=polizze#titoli``). Vengono rifiutati, restituendo
    ``default``: URL assoluti (anche verso questo stesso host), «//host»,
    schemi come ``javascript:``, barre rovesciate e caratteri di controllo, che
    i browser interpretano o eliminano in modi che portano su altri siti.
    """
    if not target or not isinstance(target, str):
        return default
    if not target.startswith("/") or target.startswith("//"):
        return default
    if "\\" in target or _CARATTERI_CONTROLLO.search(target):
        return default
    parti = urlsplit(target)
    if parti.scheme or parti.netloc:
        return default
    return target


def pagina_precedente(default: str) -> str:
    """Percorso della pagina di provenienza (Referer) se appartiene a questa applicazione."""
    referrer = request.referrer if has_request_context() else None
    if not referrer:
        return default
    parti = urlsplit(referrer)
    if parti.scheme not in ("http", "https") or parti.netloc != request.host:
        return default
    percorso = parti.path + (f"?{parti.query}" if parti.query else "")
    return safe_next(percorso, default)


# ----------------------------------------------------------------------
# Registro attività
# ----------------------------------------------------------------------
def testo_per_registro(testo: str | None, lunghezza: int = LUNGHEZZA_MASSIMA_USERNAME) -> str:
    """Testo inviato dall'utente (es. lo username di un accesso fallito) reso
    sicuro per il registro: senza caratteri di controllo e di lunghezza limitata."""
    pulito = _CARATTERI_CONTROLLO.sub("", testo or "").strip()
    return pulito if len(pulito) <= lunghezza else pulito[: lunghezza - 1] + "…"


def audit(
    azione: str,
    entita: str | None = None,
    entita_id: int | None = None,
    descrizione: str = "",
    user: User | None = None,
    commit: bool = False,
    sistema: bool = False,
) -> None:
    """Aggiunge una voce al registro attività.

    Di norma la voce viene salvata insieme all'operazione che descrive (stessa
    transazione): chi chiama fa poi ``db.session.commit()``.
    """
    if sistema:
        utente = None
    else:
        utente = user if user is not None else (g.get("user") if has_request_context() else None)
    db.session.add(
        AuditLog(
            user_id=utente.id if utente else None,
            username=utente.username if utente else ("sistema" if sistema else None),
            azione=azione,
            entita=entita,
            entita_id=entita_id,
            descrizione=(descrizione or "")[:500],
            ip=request.remote_addr if has_request_context() and not sistema else None,
        )
    )
    if commit:
        db.session.commit()


# ----------------------------------------------------------------------
# Decoratori e controlli di accesso
# ----------------------------------------------------------------------
def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.get("user") is None or not g.user.is_admin:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


def require_admin():
    """Da usare come ``before_request`` di un blueprint riservato agli amministratori."""
    if g.get("user") is None or not g.user.is_admin:
        abort(403)


def password_problem(password: str, conferma: str | None = None) -> str | None:
    """Messaggio d'errore se la password non rispetta la policy, altrimenti None."""
    if len(password or "") < LUNGHEZZA_MINIMA_PASSWORD:
        return f"La password deve avere almeno {LUNGHEZZA_MINIMA_PASSWORD} caratteri."
    if password.isdigit() or password.isalpha():
        return "La password deve contenere sia lettere sia numeri o simboli."
    if conferma is not None and password != conferma:
        return "Le due password non coincidono."
    return None


# Nome con cui gli automatismi firmano il registro attività: non assegnabile.
USERNAME_RISERVATI = {"sistema"}


def username_problem(username: str) -> str | None:
    """Messaggio d'errore se il nome utente non è accettabile, altrimenti None."""
    if not username:
        return "Il nome utente è obbligatorio."
    if len(username) > LUNGHEZZA_MASSIMA_USERNAME:
        return f"Il nome utente può avere al massimo {LUNGHEZZA_MASSIMA_USERNAME} caratteri."
    if _CARATTERI_CONTROLLO.search(username):
        return "Il nome utente contiene caratteri non ammessi."
    if username.strip().casefold() in USERNAME_RISERVATI:
        return "Questo nome utente è riservato agli automatismi del gestionale: scegline un altro."
    return None


def trova_utente(username: str) -> User | None:
    """Utente per nome senza distinguere maiuscole e minuscole, anche accentate.

    Il confronto si fa in Python con casefold(): lower() di SQLite converte
    solo le lettere ASCII, quindi «Èrica» non troverebbe mai «èrica» (né sé
    stessa scritta in maiuscolo). La tabella utenti è piccola.
    """
    chiave = (username or "").strip().casefold()
    if not chiave:
        return None
    return next((u for u in User.query.all() if (u.username or "").casefold() == chiave), None)


# ----------------------------------------------------------------------
# Verifica della password con blocco dopo troppi tentativi
# ----------------------------------------------------------------------
_HASH_FITTIZI: dict[str, str] = {}


def verifica_password_fittizia(password: str) -> None:
    """Verifica la password contro un hash fittizio calcolato con lo stesso metodo.

    Per un utente inesistente, disattivato o bloccato la risposta impiega così
    lo stesso tempo di una verifica vera: dai tempi non si capisce se
    l'account esiste.
    """
    metodo = current_app.config.get("PASSWORD_HASH_METHOD", "scrypt")
    hash_fittizio = _HASH_FITTIZI.get(metodo)
    if hash_fittizio is None:
        fittizio = User()
        fittizio.set_password(secrets.token_urlsafe(16))
        hash_fittizio = _HASH_FITTIZI.setdefault(metodo, fittizio.password_hash)
    check_password_hash(hash_fittizio, password or "")


def _prenota_tentativo(user_id: int) -> int | None:
    """Conta in modo atomico un tentativo di verifica della password.

    Un solo UPDATE incrementa il contatore (nessuna lettura-modifica-scrittura
    in Python), quindi anche le richieste in parallelo ricevono numeri
    progressivi distinti. Restituisce il numero del tentativo, oppure None se
    l'account è bloccato (in quel caso il contatore non cambia).
    """
    esito = db.session.execute(
        update(User)
        .where(User.id == user_id, or_(User.bloccato_fino.is_(None), User.bloccato_fino <= now()))
        .values(tentativi_falliti=func.coalesce(User.tentativi_falliti, 0) + 1)
        .execution_options(synchronize_session=False)
    )
    numero = None
    if esito.rowcount:
        numero = db.session.execute(
            select(User.tentativi_falliti).where(User.id == user_id)
        ).scalar_one()
    # Commit subito: il lock di scrittura di SQLite non resta occupato
    # durante il calcolo dell'hash (lento per scelta).
    db.session.commit()
    return numero


def _blocca(user_id: int) -> None:
    """Blocca temporaneamente l'account e azzera il contatore (commit a carico di chi chiama)."""
    db.session.execute(
        update(User)
        .where(User.id == user_id)
        .values(bloccato_fino=now() + timedelta(minutes=MINUTI_BLOCCO_LOGIN), tentativi_falliti=0)
        .execution_options(synchronize_session=False)
    )


def verifica_password(user: User, password: str) -> str:
    """Verifica la password di ``user`` rispettando il limite di tentativi.

    Il tentativo viene contato *prima* del controllo: anche con molte richieste
    in parallelo si eseguono al massimo ``MAX_TENTATIVI_LOGIN`` verifiche, poi
    l'account resta bloccato per ``MINUTI_BLOCCO_LOGIN`` minuti. Con l'account
    bloccato la password non viene verificata (si esegue solo la verifica
    fittizia, per avere gli stessi tempi di risposta).

    Restituisce ``ESITO_OK``, ``ESITO_ERRATA``, ``ESITO_BLOCCATO_ORA`` (questo
    errore ha fatto scattare il blocco) o ``ESITO_BLOCCATO``. Con ESITO_OK il
    contatore va azzerato da chi chiama (insieme agli altri aggiornamenti).
    """
    user_id = user.id
    numero = _prenota_tentativo(user_id)
    if numero is None or numero > MAX_TENTATIVI_LOGIN:
        verifica_password_fittizia(password)
        if numero is not None:
            # Tentativi oltre il limite arrivati in parallelo: blocco (temporaneo).
            _blocca(user_id)
        return ESITO_BLOCCATO
    if user.check_password(password):
        return ESITO_OK
    if numero >= MAX_TENTATIVI_LOGIN:
        _blocca(user_id)
        return ESITO_BLOCCATO_ORA
    return ESITO_ERRATA


# ----------------------------------------------------------------------
# Sessione legata all'utente
# ----------------------------------------------------------------------
def _impronta(user: User) -> str:
    """Impronta HMAC di id, username e hash della password.

    Cambia se cambia la password o se, dopo un ripristino, allo stesso id
    corrisponde un altro utente: il cookie emesso prima non è più valido.
    """
    chiave = current_app.secret_key
    chiave = chiave.encode() if isinstance(chiave, str) else chiave
    dati = f"{user.id}:{user.username}:{user.password_hash}".encode()
    return hmac.new(chiave, dati, hashlib.sha256).hexdigest()[:32]


def login_user(user: User) -> None:
    """Apre la sessione per ``user`` (o la rinnova dopo un cambio di versione)."""
    session.clear()
    session["user_id"] = user.id
    session["ver"] = user.sessione_versione or 0
    session["impronta"] = _impronta(user)
    session.permanent = True  # durata: PERMANENT_SESSION_LIFETIME
    csrf_token()


def invalida_sessioni(user: User) -> None:
    """Rende non più valide tutte le sessioni aperte da ``user``, su ogni dispositivo.

    L'incremento avviene in SQL (``sessione_versione = sessione_versione + 1``)
    al prossimo flush; il commit è a carico di chi chiama.
    """
    user.sessione_versione = func.coalesce(User.sessione_versione, 0) + 1


def invalida_tutte_le_sessioni() -> None:
    """Invalida le sessioni di tutti gli utenti (es. dopo il ripristino di un backup).

    L'incremento è casuale, così un numero di versione salvato in un cookie non
    torna a coincidere per caso con quello del database ripristinato. Il
    commit è a carico di chi chiama.
    """
    db.session.execute(
        update(User)
        .values(sessione_versione=func.coalesce(User.sessione_versione, 0) + secrets.randbelow(1_000_000) + 1)
        .execution_options(synchronize_session=False)
    )


def _sessione_valida(user: User | None) -> bool:
    if user is None or not user.attivo:
        return False
    if session.get("ver") != (user.sessione_versione or 0):
        return False
    return hmac.compare_digest(str(session.get("impronta") or ""), _impronta(user))


def _load_user():
    g.user = None
    user_id = session.get("user_id")
    if user_id is None:
        return
    user = db.session.get(User, user_id) if isinstance(user_id, int) else None
    if not _sessione_valida(user):
        # Sessione revocata (uscita, password cambiata, utente disattivato o
        # modificato, backup ripristinato): si torna all'accesso.
        session.clear()
        g.sessione_scaduta = True
        if request.endpoint != "static":
            flash(MSG_SESSIONE_SCADUTA, "warning")
        return
    g.user = user


def _e_modulo_di_modifica(endpoint: str) -> bool:
    """True se l'endpoint è un modulo di inserimento/modifica (la sua route accetta POST)."""
    regola = request.url_rule
    if regola is not None and "POST" in (regola.methods or ()):
        return True
    nome = endpoint.rsplit(".", 1)[-1]
    return nome == "edit" or nome.startswith(PREFISSI_MODULI)


def _require_login():
    endpoint = request.endpoint
    if endpoint is None or endpoint in PUBLIC_ENDPOINTS:
        return None
    if g.user is None:
        if db.session.query(User.id).first() is None:
            return redirect(url_for("auth.setup"))
        if request.method == "GET":
            return redirect(url_for("auth.login", next=request.full_path))
        if not g.get("sessione_scaduta"):
            flash(MSG_SESSIONE_SCADUTA, "warning")
        return redirect(url_for("auth.login"))
    if not g.user.puo_modificare and endpoint not in READONLY_ALLOWED_POST:
        if request.method in ("GET", "HEAD"):
            if _e_modulo_di_modifica(endpoint):
                # Niente moduli aperti per niente: il salvataggio verrebbe rifiutato.
                abort(403, description=(
                    "Il tuo profilo è in sola consultazione: non puoi aprire i moduli "
                    "di inserimento o modifica."
                ))
        elif request.method != "OPTIONS":
            flash(MSG_SOLA_CONSULTAZIONE, "warning")
            return redirect(pagina_precedente(url_for("main.dashboard")))
    return None


def _security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    if response.mimetype == "text/html":
        response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
    if request.endpoint != "static" and g.get("user") is not None:
        # Dati riservati: niente copie nella cache del browser (tasto «indietro» dopo l'uscita).
        response.headers.setdefault("Cache-Control", "no-store")
    return response


def init_security(app: Flask) -> None:
    """Registra i controlli di sicurezza sull'applicazione (prima di tutto il resto)."""
    app.before_request(_load_user)
    app.before_request(_require_login)
    app.before_request(_check_csrf)
    app.after_request(_security_headers)
    app.jinja_env.globals["csrf_token"] = csrf_token
    app.jinja_env.globals["csrf_field"] = csrf_field

    @app.context_processor
    def inject_user():
        user = g.get("user")
        return {
            "utente": user,
            "puo_modificare": bool(user and user.puo_modificare),
            "is_admin": bool(user and user.is_admin),
        }

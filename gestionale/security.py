"""Sicurezza: autenticazione, ruoli, protezione CSRF e registro attività.

- Ogni pagina richiede l'accesso; al primo avvio, senza utenti, si viene
  portati alla configurazione iniziale per creare l'amministratore.
- Tre ruoli: amministratore (tutto, compresi utenti, impostazioni, backup e
  registro), operatore (lavoro quotidiano) e sola consultazione.
- Ogni richiesta che modifica dati (POST) deve portare il token CSRF della
  sessione, inserito nei form con ``{{ csrf_field() }}``.
- Le operazioni rilevanti finiscono nel registro attività (``audit``).
"""
from __future__ import annotations

import hmac
import secrets
from functools import wraps
from urllib.parse import urlparse

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

from .models import AuditLog, User, db

# Pagine raggiungibili senza aver effettuato l'accesso.
PUBLIC_ENDPOINTS = {"static", "auth.login", "auth.setup"}
# POST consentiti anche al profilo in sola consultazione (non toccano i dati).
READONLY_ALLOWED_POST = {
    "auth.logout",
    "auth.change_password",
    "notifications.mark_read",
    "notifications.mark_all_read",
}
# Endpoint che accettano upload più grandi del limite generale (ripristino backup).
LARGE_UPLOAD_ENDPOINTS = {"settings.restore_backup"}
MAX_TENTATIVI_LOGIN = 5
MINUTI_BLOCCO_LOGIN = 15
LUNGHEZZA_MINIMA_PASSWORD = 8


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
    if request.endpoint in LARGE_UPLOAD_ENDPOINTS:
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
    """Restituisce ``target`` solo se punta a una pagina di questa applicazione."""
    if not target:
        return default
    parsed = urlparse(target)
    if parsed.scheme or parsed.netloc:
        if has_request_context() and parsed.netloc == request.host:
            target = parsed.path + (f"?{parsed.query}" if parsed.query else "")
            target += f"#{parsed.fragment}" if parsed.fragment else ""
            return target or default
        return default
    if not target.startswith("/") or target.startswith("//") or target.startswith("/\\"):
        return default
    return target


# ----------------------------------------------------------------------
# Registro attività
# ----------------------------------------------------------------------
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


def login_user(user: User) -> None:
    session.clear()
    session["user_id"] = user.id
    session.permanent = True
    csrf_token()


def _load_user():
    g.user = None
    user_id = session.get("user_id")
    if user_id is None:
        return
    user = db.session.get(User, user_id)
    if user is None or not user.attivo:
        session.pop("user_id", None)
        return
    g.user = user


def _require_login():
    endpoint = request.endpoint
    if endpoint is None or endpoint in PUBLIC_ENDPOINTS:
        return None
    if g.user is None:
        if db.session.query(User.id).first() is None:
            return redirect(url_for("auth.setup"))
        if request.method == "GET":
            return redirect(url_for("auth.login", next=request.full_path))
        flash("Sessione scaduta: accedi di nuovo.", "warning")
        return redirect(url_for("auth.login"))
    if (
        request.method == "POST"
        and not g.user.puo_modificare
        and endpoint not in READONLY_ALLOWED_POST
    ):
        flash("Il tuo profilo è in sola consultazione: non puoi modificare i dati.", "warning")
        return redirect(safe_next(request.referrer, url_for("main.dashboard")))
    return None


def _security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "same-origin")
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

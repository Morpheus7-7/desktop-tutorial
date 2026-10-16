"""Accesso, uscita, configurazione iniziale e cambio password."""
from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from ..models import Settings, User, db, now
from ..security import (
    ESITO_BLOCCATO,
    ESITO_BLOCCATO_ORA,
    ESITO_ERRATA,
    ESITO_OK,
    LUNGHEZZA_MASSIMA_USERNAME,
    MAX_TENTATIVI_LOGIN,
    MINUTI_BLOCCO_LOGIN,
    audit,
    invalida_sessioni,
    login_user,
    password_problem,
    safe_next,
    testo_per_registro,
    username_problem,
    verifica_password,
    verifica_password_fittizia,
)

bp = Blueprint("auth", __name__)

# Unico messaggio per utente inesistente, password errata e account bloccato:
# chi prova ad accedere non scopre quali nomi utente esistono.
MSG_ACCESSO_NEGATO = (
    "Accesso non riuscito: nome utente o password non corretti. "
    f"Dopo {MAX_TENTATIVI_LOGIN} tentativi errati l'account resta bloccato "
    f"per {MINUTI_BLOCCO_LOGIN} minuti."
)


@bp.route("/accesso", methods=["GET", "POST"])
def login():
    if db.session.query(User.id).first() is None:
        return redirect(url_for("auth.setup"))
    if g.get("user") is not None:
        return redirect(url_for("main.dashboard"))

    username = ""
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = None
        if username and len(username) <= LUNGHEZZA_MASSIMA_USERNAME:
            user = User.query.filter(db.func.lower(User.username) == username.lower()).first()

        if user is not None and user.attivo:
            esito = verifica_password(user, password)
        else:
            # Stessi tempi di risposta di un utente esistente.
            verifica_password_fittizia(password)
            esito = None

        if esito == ESITO_OK:
            user.tentativi_falliti = 0
            user.bloccato_fino = None
            user.ultimo_accesso = now()
            audit("login", "utente", user.id, "Accesso effettuato", user=user)
            db.session.commit()
            login_user(user)
            return redirect(safe_next(request.args.get("next"), url_for("main.dashboard")))

        dettaglio = ""
        if esito in (ESITO_BLOCCATO, ESITO_BLOCCATO_ORA):
            dettaglio = " (account bloccato per troppi tentativi)"
        audit("login_fallito", "utente", user.id if user else None,
              f"Tentativo di accesso non riuscito per «{testo_per_registro(username)}»{dettaglio}",
              user=user)
        db.session.commit()
        flash(MSG_ACCESSO_NEGATO, "danger")

    return render_template("auth/login.html", username=username[:LUNGHEZZA_MASSIMA_USERNAME])


@bp.route("/esci", methods=["POST"])
def logout():
    user = g.get("user")
    if user is not None:
        # Uscita da tutti i dispositivi: anche una copia del cookie non vale più.
        invalida_sessioni(user)
        audit("logout", "utente", user.id, "Uscita dal gestionale", user=user, commit=True)
    session.clear()
    flash("Sei uscito dal gestionale.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/configurazione-iniziale", methods=["GET", "POST"])
def setup():
    """Primo avvio: crea l'account amministratore (solo se non esistono utenti)."""
    if db.session.query(User.id).first() is not None:
        return redirect(url_for("auth.login"))

    dati = {"nome": "", "username": "", "email": "", "studio_nome": ""}
    if request.method == "POST":
        dati = {k: (request.form.get(k) or "").strip() for k in dati}
        password = request.form.get("password") or ""
        errore = username_problem(dati["username"]) or password_problem(
            password, request.form.get("conferma") or ""
        )
        if errore:
            flash(errore, "danger")
        else:
            user = User(
                username=dati["username"],
                nome=dati["nome"] or None,
                email=dati["email"] or None,
                ruolo="admin",
                ultimo_accesso=now(),
            )
            user.set_password(password)
            db.session.add(user)
            if dati["studio_nome"]:
                Settings.get().studio_nome = dati["studio_nome"]
            db.session.flush()
            audit("crea", "utente", user.id, "Configurazione iniziale: creato l'amministratore", user=user)
            db.session.commit()
            login_user(user)
            flash("Benvenuto! Il gestionale è pronto: inizia inserendo i tuoi clienti.", "success")
            return redirect(url_for("main.dashboard"))

    return render_template("auth/setup.html", dati=dati)


@bp.route("/profilo/password", methods=["GET", "POST"])
def change_password():
    user = g.user
    if request.method == "POST":
        attuale = request.form.get("attuale") or ""
        nuova = request.form.get("nuova") or ""
        # La password attuale conta come un tentativo di accesso: chi ha solo
        # un cookie rubato non può provarle tutte.
        esito = verifica_password(user, attuale)
        if esito == ESITO_BLOCCATO_ORA:
            invalida_sessioni(user)
            audit("login_fallito", "utente", user.id,
                  "Password attuale errata troppe volte nel cambio password: account bloccato e sessioni chiuse")
            db.session.commit()
            session.clear()
            flash(
                "Troppi tentativi errati con la password attuale: per sicurezza sei stato disconnesso. "
                f"Potrai accedere di nuovo tra {MINUTI_BLOCCO_LOGIN} minuti.",
                "danger",
            )
            return redirect(url_for("auth.login"))
        if esito == ESITO_BLOCCATO:
            db.session.commit()
            flash(
                "Account temporaneamente bloccato per troppi tentativi errati: "
                f"riprova a cambiare la password tra {MINUTI_BLOCCO_LOGIN} minuti.",
                "danger",
            )
        elif esito == ESITO_ERRATA:
            audit("login_fallito", "utente", user.id, "Password attuale errata nel cambio password")
            db.session.commit()
            flash("La password attuale non è corretta.", "danger")
        else:
            user.tentativi_falliti = 0
            errore = password_problem(nuova, request.form.get("conferma") or "")
            if errore:
                db.session.commit()
                flash(errore, "danger")
            else:
                user.set_password(nuova)
                # Tutte le sessioni (anche questa) vanno riaperte con la nuova password.
                invalida_sessioni(user)
                audit("modifica", "utente", user.id, "Password personale cambiata")
                db.session.commit()
                session.clear()
                flash("Password aggiornata: accedi di nuovo con la nuova password.", "success")
                return redirect(url_for("auth.login"))
    return render_template("auth/password.html")

"""Accesso, uscita, configurazione iniziale e cambio password."""
from datetime import timedelta

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from ..models import Settings, User, db, now
from ..security import (
    MAX_TENTATIVI_LOGIN,
    MINUTI_BLOCCO_LOGIN,
    audit,
    login_user,
    password_problem,
    safe_next,
)

bp = Blueprint("auth", __name__)


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
        user = User.query.filter(db.func.lower(User.username) == username.lower()).first()

        if user is not None and user.bloccato:
            minuti = max(1, int((user.bloccato_fino - now()).total_seconds() // 60) + 1)
            flash(
                f"Account temporaneamente bloccato per troppi tentativi errati: riprova tra {minuti} minuti.",
                "danger",
            )
        elif user is None or not user.attivo or not user.check_password(password):
            if user is not None and user.attivo:
                user.tentativi_falliti = (user.tentativi_falliti or 0) + 1
                if user.tentativi_falliti >= MAX_TENTATIVI_LOGIN:
                    user.bloccato_fino = now() + timedelta(minutes=MINUTI_BLOCCO_LOGIN)
                    user.tentativi_falliti = 0
            audit("login_fallito", "utente", user.id if user else None,
                  f"Tentativo di accesso non riuscito per «{username}»", user=user)
            db.session.commit()
            flash("Nome utente o password non corretti.", "danger")
        else:
            user.tentativi_falliti = 0
            user.bloccato_fino = None
            user.ultimo_accesso = now()
            audit("login", "utente", user.id, "Accesso effettuato", user=user)
            db.session.commit()
            login_user(user)
            return redirect(safe_next(request.args.get("next"), url_for("main.dashboard")))

    return render_template("auth/login.html", username=username)


@bp.route("/esci", methods=["POST"])
def logout():
    user = g.get("user")
    if user is not None:
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
        errore = None
        if not dati["username"]:
            errore = "Il nome utente è obbligatorio."
        else:
            errore = password_problem(password, request.form.get("conferma") or "")
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
        if not user.check_password(attuale):
            flash("La password attuale non è corretta.", "danger")
        else:
            errore = password_problem(nuova, request.form.get("conferma") or "")
            if errore:
                flash(errore, "danger")
            else:
                user.set_password(nuova)
                audit("modifica", "utente", user.id, "Password personale cambiata")
                db.session.commit()
                flash("Password aggiornata.", "success")
                return redirect(url_for("main.dashboard"))
    return render_template("auth/password.html")

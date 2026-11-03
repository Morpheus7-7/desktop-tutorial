"""Gestione utenti (solo amministratori)."""
from types import SimpleNamespace

from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for

from ..models import USER_ROLES, User, db
from ..security import (
    audit,
    invalida_sessioni,
    login_user,
    password_problem,
    require_admin,
    username_problem,
    trova_utente,
)

bp = Blueprint("users", __name__, url_prefix="/utenti")
bp.before_request(require_admin)

MSG_ULTIMO_ADMIN = "Deve rimanere almeno un amministratore attivo."


def _altri_admin_attivi(user: User) -> int:
    return User.query.filter(
        User.ruolo == "admin", User.attivo.is_(True), User.id != user.id
    ).count()


def _admin_attivi() -> int:
    return User.query.filter(User.ruolo == "admin", User.attivo.is_(True)).count()


@bp.route("/")
def list_users():
    utenti = User.query.order_by(User.attivo.desc(), User.username.asc()).all()
    return render_template("users/list.html", utenti=utenti)


@bp.route("/nuovo", methods=["GET", "POST"])
def new_user():
    user = User(ruolo="operatore", attivo=True)
    if request.method == "POST":
        user.username = (request.form.get("username") or "").strip()
        user.nome = (request.form.get("nome") or "").strip() or None
        user.email = (request.form.get("email") or "").strip() or None
        ruolo = request.form.get("ruolo")
        user.ruolo = ruolo if ruolo in dict(USER_ROLES) else "operatore"
        password = request.form.get("password") or ""
        errore = username_problem(user.username)
        if errore is None and trova_utente(user.username) is not None:
            errore = f"Il nome utente «{user.username}» è già in uso."
        if errore is None:
            errore = password_problem(password, request.form.get("conferma") or "")
        if errore:
            flash(errore, "danger")
            return render_template("users/form.html", user=user, roles=USER_ROLES, nuovo=True), 400
        user.set_password(password)
        db.session.add(user)
        db.session.flush()
        audit("crea", "utente", user.id, f"Creato l'utente «{user.username}» ({user.ruolo_label})")
        db.session.commit()
        flash(f"Utente «{user.username}» creato.", "success")
        return redirect(url_for("users.list_users"))
    return render_template("users/form.html", user=user, roles=USER_ROLES, nuovo=True)


@bp.route("/<int:user_id>/modifica", methods=["GET", "POST"])
def edit_user(user_id):
    user = db.get_or_404(User, user_id)
    if request.method == "POST":
        ruolo = request.form.get("ruolo")
        ruolo = ruolo if ruolo in dict(USER_ROLES) else user.ruolo
        attivo = request.form.get("attivo") == "on"
        password = request.form.get("password") or ""
        nome = (request.form.get("nome") or "").strip() or None
        email = (request.form.get("email") or "").strip() or None

        errore = None
        resta_admin = ruolo == "admin" and attivo
        if user.is_admin and user.attivo and not resta_admin and _altri_admin_attivi(user) == 0:
            errore = MSG_ULTIMO_ADMIN
        elif password:
            errore = password_problem(password, request.form.get("conferma") or "")
        if errore:
            flash(errore, "danger")
            # Ripresenta i valori digitati senza salvarli.
            valori = SimpleNamespace(id=user.id, username=user.username, nome=nome, email=email,
                                     ruolo=ruolo, attivo=attivo)
            return render_template("users/form.html", user=valori, roles=USER_ROLES, nuovo=False), 400

        modifiche = []
        if ruolo != user.ruolo:
            modifiche.append(f"ruolo {user.ruolo} → {ruolo}")
        if attivo != user.attivo:
            modifiche.append("riattivato" if attivo else "disattivato")
        if password:
            modifiche.append("password reimpostata")
        # Ruolo, stato o password cambiati: le sessioni già aperte da quell'utente
        # non valgono più (un operatore declassato non resta admin fino all'uscita).
        revoca = ruolo != user.ruolo or attivo != user.attivo or bool(password)
        stesso_utente = user.id == g.user.id

        user.nome = nome
        user.email = email
        user.ruolo = ruolo
        user.attivo = attivo
        if password:
            user.set_password(password)
            user.tentativi_falliti = 0
            user.bloccato_fino = None
        if revoca:
            invalida_sessioni(user)
        db.session.flush()
        # Ricontrollo dentro la transazione: due amministratori che si declassano
        # a vicenda nello stesso momento non lasciano il gestionale senza admin.
        if _admin_attivi() == 0:
            db.session.rollback()
            flash(MSG_ULTIMO_ADMIN, "danger")
            return redirect(url_for("users.edit_user", user_id=user_id))
        audit("modifica", "utente", user.id,
              f"Modificato l'utente «{user.username}»" + (f": {', '.join(modifiche)}" if modifiche else ""))
        db.session.commit()

        if stesso_utente:
            if not user.attivo:
                session.clear()
                flash("Hai disattivato il tuo account: sei stato disconnesso.", "info")
                return redirect(url_for("auth.login"))
            if revoca:
                # Le altre sessioni sono chiuse; questa resta aperta con i nuovi dati.
                login_user(user)
            if not user.is_admin:
                flash(
                    f"Profilo aggiornato: ora il tuo ruolo è «{user.ruolo_label}» "
                    "e non hai più accesso alla gestione utenti.",
                    "info",
                )
                return redirect(url_for("main.dashboard"))
        flash(f"Utente «{user.username}» aggiornato.", "success")
        return redirect(url_for("users.list_users"))
    return render_template("users/form.html", user=user, roles=USER_ROLES, nuovo=False)


@bp.route("/<int:user_id>/sblocca", methods=["POST"])
def unlock_user(user_id):
    user = db.get_or_404(User, user_id)
    user.tentativi_falliti = 0
    user.bloccato_fino = None
    audit("modifica", "utente", user.id, f"Sbloccato l'utente «{user.username}»")
    db.session.commit()
    flash(f"Utente «{user.username}» sbloccato.", "success")
    return redirect(url_for("users.list_users"))

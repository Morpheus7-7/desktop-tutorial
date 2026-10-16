"""Gestione utenti (solo amministratori)."""
from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..models import USER_ROLES, User, db
from ..security import audit, password_problem, require_admin

bp = Blueprint("users", __name__, url_prefix="/utenti")
bp.before_request(require_admin)


def _altri_admin_attivi(user: User) -> int:
    return User.query.filter(
        User.ruolo == "admin", User.attivo.is_(True), User.id != user.id
    ).count()


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
        errore = None
        if not user.username:
            errore = "Il nome utente è obbligatorio."
        elif User.query.filter(db.func.lower(User.username) == user.username.lower()).first():
            errore = f"Il nome utente «{user.username}» è già in uso."
        else:
            errore = password_problem(password, request.form.get("conferma") or "")
        if errore:
            flash(errore, "danger")
        else:
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

        errore = None
        resta_admin = ruolo == "admin" and attivo
        if user.is_admin and user.attivo and not resta_admin and _altri_admin_attivi(user) == 0:
            errore = "Deve rimanere almeno un amministratore attivo."
        elif password:
            errore = password_problem(password, request.form.get("conferma") or "")
        if errore:
            flash(errore, "danger")
        else:
            modifiche = []
            if ruolo != user.ruolo:
                modifiche.append(f"ruolo {user.ruolo} → {ruolo}")
            if attivo != user.attivo:
                modifiche.append("riattivato" if attivo else "disattivato")
            user.nome = (request.form.get("nome") or "").strip() or None
            user.email = (request.form.get("email") or "").strip() or None
            user.ruolo = ruolo
            user.attivo = attivo
            if password:
                user.set_password(password)
                user.tentativi_falliti = 0
                user.bloccato_fino = None
                modifiche.append("password reimpostata")
            audit("modifica", "utente", user.id,
                  f"Modificato l'utente «{user.username}»" + (f": {', '.join(modifiche)}" if modifiche else ""))
            db.session.commit()
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


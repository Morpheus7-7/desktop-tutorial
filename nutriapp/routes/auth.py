"""Accesso, uscita, cambio password e gestione degli account."""
from __future__ import annotations

from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for

from .. import forms
from ..mailer import invia_credenziali
from ..models import Assistito, User, db
from ..security import (
    accedi,
    esci,
    login_required,
    nutrizionista_required,
    password_provvisoria,
    utente_corrente,
)

bp = Blueprint("auth", __name__)


@bp.route("/")
def indice():
    """Porta d'ingresso: ognuno finisce nella propria area."""
    utente = utente_corrente()
    if utente is None:
        return redirect(url_for("auth.login"))
    if utente.is_nutrizionista:
        return redirect(url_for("main.dashboard"))
    return redirect(url_for("portal.home"))


@bp.route("/accedi", methods=["GET", "POST"])
def login():
    if utente_corrente() is not None:
        return redirect(url_for("auth.indice"))

    if request.method == "POST":
        email = (forms.testo(request.form.get("email")) or "").lower()
        password = request.form.get("password") or ""
        utente = User.query.filter_by(email=email).first()

        if utente is None or not utente.check_password(password):
            # Stesso messaggio per email sbagliata e password sbagliata:
            # non diciamo a chi prova se l'indirizzo esiste.
            flash("Email o password non corretti.", "danger")
        elif not utente.attivo:
            flash("Questo accesso è stato sospeso. Contatta lo studio.", "warning")
        else:
            accedi(utente)
            utente.ultimo_accesso = datetime.utcnow()
            db.session.commit()
            if utente.deve_cambiare_password:
                return redirect(url_for("auth.cambia_password"))
            destinazione = request.args.get("next") or request.form.get("next")
            if destinazione and destinazione.startswith("/") and not destinazione.startswith("//"):
                return redirect(destinazione)
            return redirect(url_for("auth.indice"))

    return render_template("auth/login.html", next=request.args.get("next", ""))


@bp.route("/esci")
def logout():
    esci()
    flash("Sei uscito dall'applicazione.", "info")
    return redirect(url_for("auth.login"))


@bp.route("/cambia-password", methods=["GET", "POST"])
@login_required
def cambia_password():
    utente = utente_corrente()
    if request.method == "POST":
        attuale = request.form.get("attuale") or ""
        nuova = request.form.get("nuova") or ""
        conferma = request.form.get("conferma") or ""

        if not utente.deve_cambiare_password and not utente.check_password(attuale):
            flash("La password attuale non è corretta.", "danger")
        elif len(nuova) < 8:
            flash("La nuova password deve avere almeno 8 caratteri.", "warning")
        elif nuova != conferma:
            flash("Le due password non coincidono.", "warning")
        else:
            utente.set_password(nuova)
            utente.deve_cambiare_password = False
            db.session.commit()
            flash("Password aggiornata.", "success")
            return redirect(url_for("auth.indice"))

    return render_template("auth/cambia_password.html", primo_accesso=utente.deve_cambiare_password)


# ----------------------------------------------------------------------
# Gestione degli accessi (solo studio)
# ----------------------------------------------------------------------
@bp.route("/accessi")
@nutrizionista_required
def accessi():
    utenti = User.query.order_by(User.ruolo, User.nome).all()
    senza_accesso = (
        Assistito.query.filter(Assistito.attivo.is_(True), ~Assistito.utente.has())
        .order_by(Assistito.cognome)
        .all()
    )
    return render_template("auth/accessi.html", utenti=utenti, senza_accesso=senza_accesso)


@bp.route("/assistiti/<int:assistito_id>/accesso", methods=["POST"])
@nutrizionista_required
def crea_accesso(assistito_id: int):
    """Apre (o reimposta) l'area riservata di un assistito e gli manda le credenziali."""
    assistito = db.get_or_404(Assistito, assistito_id)
    email = forms.testo(request.form.get("email")) or assistito.email
    if not email:
        flash("Serve un indirizzo email per creare l'accesso.", "warning")
        return redirect(url_for("clients.dettaglio", assistito_id=assistito_id))

    email = email.lower()
    esistente = User.query.filter(User.email == email, User.assistito_id != assistito_id).first()
    if esistente:
        flash(f"L'indirizzo {email} è già usato da un altro accesso.", "danger")
        return redirect(url_for("clients.dettaglio", assistito_id=assistito_id))

    password = password_provvisoria()
    utente = assistito.utente
    if utente is None:
        utente = User(
            email=email,
            nome=assistito.nome_completo,
            ruolo="cliente",
            assistito_id=assistito.id,
        )
        db.session.add(utente)
        azione = "creato"
    else:
        utente.email = email
        utente.nome = assistito.nome_completo
        utente.attivo = True
        azione = "reimpostato"

    utente.set_password(password)
    utente.deve_cambiare_password = True
    if not assistito.email:
        assistito.email = email
    db.session.commit()

    inviata, dettaglio = invia_credenziali(utente, password)
    if inviata:
        flash(f"Accesso {azione}: credenziali inviate a {email}.", "success")
    else:
        # Senza SMTP configurato la password va comunque consegnata: la mostriamo
        # una volta sola, qui.
        flash(
            f"Accesso {azione}. {dettaglio} Password provvisoria da consegnare a mano: {password}",
            "warning",
        )
    return redirect(url_for("clients.dettaglio", assistito_id=assistito_id))


@bp.route("/accessi/<int:utente_id>/stato", methods=["POST"])
@nutrizionista_required
def cambia_stato(utente_id: int):
    utente = db.get_or_404(User, utente_id)
    if utente.id == utente_corrente().id:
        flash("Non puoi sospendere il tuo stesso accesso.", "warning")
    else:
        utente.attivo = not utente.attivo
        db.session.commit()
        flash(
            f"Accesso di {utente.nome} {'riattivato' if utente.attivo else 'sospeso'}.",
            "success",
        )
    return redirect(url_for("auth.accessi"))


@bp.route("/accessi/<int:utente_id>/elimina", methods=["POST"])
@nutrizionista_required
def elimina_accesso(utente_id: int):
    utente = db.get_or_404(User, utente_id)
    if utente.id == utente_corrente().id:
        flash("Non puoi eliminare il tuo stesso accesso.", "warning")
        return redirect(url_for("auth.accessi"))
    if utente.is_nutrizionista and User.query.filter_by(ruolo="nutrizionista").count() <= 1:
        flash("Deve restare almeno un accesso dello studio.", "warning")
        return redirect(url_for("auth.accessi"))
    nome = utente.nome
    db.session.delete(utente)
    db.session.commit()
    flash(f"Accesso di {nome} eliminato. La scheda dell'assistito resta.", "success")
    return redirect(url_for("auth.accessi"))


@bp.route("/accessi/nuovo", methods=["POST"])
@nutrizionista_required
def nuovo_collaboratore():
    """Un secondo accesso di studio (collega, segreteria)."""
    email = (forms.testo(request.form.get("email")) or "").lower()
    nome = forms.testo(request.form.get("nome"))
    if not email or not nome:
        flash("Servono nome ed email.", "warning")
    elif User.query.filter_by(email=email).first():
        flash("Esiste già un accesso con questa email.", "danger")
    else:
        password = password_provvisoria()
        utente = User(email=email, nome=nome, ruolo="nutrizionista", deve_cambiare_password=True)
        utente.set_password(password)
        db.session.add(utente)
        db.session.commit()
        inviata, dettaglio = invia_credenziali(utente, password)
        if inviata:
            flash(f"Accesso creato: credenziali inviate a {email}.", "success")
        else:
            flash(f"Accesso creato. {dettaglio} Password provvisoria: {password}", "warning")
    return redirect(url_for("auth.accessi"))

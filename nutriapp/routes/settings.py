"""Impostazioni: dati dello studio, email SMTP, servizi di spesa."""
from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from .. import forms
from ..mailer import contatore_pending, effective_config, invia_email_prova, invia_notifiche_pendenti
from ..models import FornitoreSpesa, Settings, db
from ..security import nutrizionista_required

bp = Blueprint("settings", __name__, url_prefix="/impostazioni")


@bp.route("/", methods=["GET", "POST"])
@nutrizionista_required
def modifica():
    settings = Settings.get()

    if request.method == "POST":
        f = request.form
        settings.nome_studio = forms.testo(f.get("nome_studio"), 150) or "NutriStudio"
        settings.professionista = forms.testo(f.get("professionista"), 150)
        settings.email_studio = forms.testo(f.get("email_studio"), 200)
        settings.telefono_studio = forms.testo(f.get("telefono_studio"), 50)
        settings.sito_web = forms.testo(f.get("sito_web"), 200)
        settings.disclaimer = forms.testo(f.get("disclaimer"))

        settings.email_attive = forms.flag(f.get("email_attive"))
        settings.smtp_host = forms.testo(f.get("smtp_host"), 200)
        settings.smtp_port = forms.intero(f.get("smtp_port")) or 587
        settings.smtp_security = forms.testo(f.get("smtp_security"), 10) or "tls"
        settings.smtp_user = forms.testo(f.get("smtp_user"), 200)
        nuova_password = f.get("smtp_password")
        if nuova_password:  # campo vuoto = «lascia quella che c'è»
            settings.smtp_password = nuova_password
        settings.mail_from = forms.testo(f.get("mail_from"), 200)
        settings.mail_to = forms.testo(f.get("mail_to"), 400)
        settings.intervallo_minuti = max(5, forms.intero(f.get("intervallo_minuti")) or 60)

        settings.avvisa_piano_in_scadenza = forms.flag(f.get("avvisa_piano_in_scadenza"))
        settings.giorni_preavviso_piano = max(0, forms.intero(f.get("giorni_preavviso_piano")) or 5)
        settings.avvisa_appuntamenti = forms.flag(f.get("avvisa_appuntamenti"))
        settings.avvisa_nuovo_piano_al_cliente = forms.flag(f.get("avvisa_nuovo_piano_al_cliente"))

        db.session.commit()
        flash("Impostazioni salvate.", "success")
        return redirect(url_for("settings.modifica"))

    return render_template(
        "settings/form.html",
        settings=settings,
        config=effective_config(settings),
        in_attesa=contatore_pending(),
        fornitori=FornitoreSpesa.query.order_by(FornitoreSpesa.ordine, FornitoreSpesa.nome).all(),
    )


@bp.route("/prova-email", methods=["POST"])
@nutrizionista_required
def prova_email():
    inviata, dettaglio = invia_email_prova()
    flash(dettaglio, "success" if inviata else "danger")
    return redirect(url_for("settings.modifica"))


@bp.route("/invia-notifiche", methods=["POST"])
@nutrizionista_required
def invia_notifiche():
    quante = invia_notifiche_pendenti()
    if quante:
        flash(f"Inviato il riepilogo con {quante} notifiche.", "success")
    else:
        flash("Nessuna notifica da inviare (o email non configurate).", "info")
    return redirect(url_for("settings.modifica"))


# ----------------------------------------------------------------------
# Servizi di spesa
# ----------------------------------------------------------------------
@bp.route("/spesa", methods=["POST"])
@nutrizionista_required
def salva_fornitore():
    fornitore_id = forms.intero(request.form.get("id"))
    nome = forms.testo(request.form.get("nome"), 80)
    template = forms.testo(request.form.get("url_template"), 400)

    if not nome or not template:
        flash("Servono nome e indirizzo di ricerca.", "warning")
    elif "{query}" not in template:
        flash("L'indirizzo deve contenere «{query}»: è lì che finisce il nome del prodotto.", "warning")
    else:
        fornitore = db.session.get(FornitoreSpesa, fornitore_id) if fornitore_id else None
        if fornitore is None:
            fornitore = FornitoreSpesa(nome=nome, url_template=template)
            db.session.add(fornitore)
        fornitore.nome = nome
        fornitore.url_template = template
        fornitore.icona = forms.testo(request.form.get("icona"), 60) or "bi-bag"
        fornitore.colore = forms.testo(request.form.get("colore"), 20) or "#198754"
        fornitore.ordine = forms.intero(request.form.get("ordine")) or 100
        fornitore.attivo = forms.flag(request.form.get("attivo"))
        db.session.commit()
        flash(f"Servizio «{nome}» salvato.", "success")
    return redirect(url_for("settings.modifica") + "#spesa")


@bp.route("/spesa/<int:fornitore_id>/elimina", methods=["POST"])
@nutrizionista_required
def elimina_fornitore(fornitore_id: int):
    fornitore = db.get_or_404(FornitoreSpesa, fornitore_id)
    nome = fornitore.nome
    db.session.delete(fornitore)
    db.session.commit()
    flash(f"Servizio «{nome}» rimosso.", "info")
    return redirect(url_for("settings.modifica") + "#spesa")

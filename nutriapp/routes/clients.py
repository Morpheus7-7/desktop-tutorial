"""Anagrafica assistiti: scheda, misurazioni, appuntamenti, messaggi."""
from __future__ import annotations

from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy import or_

from .. import forms
from ..models import (
    Appuntamento,
    Assistito,
    DIETE,
    Messaggio,
    Misurazione,
    OBIETTIVI,
    SESSI,
    STATI_APPUNTAMENTO,
    TIPI_APPUNTAMENTO,
    db,
)
from ..nutrition import LIVELLI_ATTIVITA, fabbisogno_stimato
from ..security import nutrizionista_required, utente_corrente

bp = Blueprint("clients", __name__, url_prefix="/assistiti")


def _leggi_form(assistito: Assistito) -> None:
    f = request.form
    assistito.nome = forms.testo(f.get("nome"), 100) or assistito.nome
    assistito.cognome = forms.testo(f.get("cognome"), 100) or assistito.cognome
    assistito.email = forms.testo(f.get("email"), 200)
    assistito.telefono = forms.testo(f.get("telefono"), 50)
    assistito.data_nascita = forms.data(f.get("data_nascita"))
    assistito.sesso = forms.testo(f.get("sesso"), 10)
    assistito.altezza_cm = forms.numero(f.get("altezza_cm"))
    assistito.peso_iniziale_kg = forms.numero(f.get("peso_iniziale_kg"))
    assistito.obiettivo = forms.testo(f.get("obiettivo"), 60)
    assistito.tipo_dieta = forms.testo(f.get("tipo_dieta"), 40) or "Standard"
    assistito.target_kcal = forms.intero(f.get("target_kcal")) or 1800
    assistito.allergie = forms.testo(f.get("allergie"))
    assistito.patologie = forms.testo(f.get("patologie"))
    assistito.preferenze = forms.testo(f.get("preferenze"))
    assistito.note = forms.testo(f.get("note"))
    assistito.attivo = forms.flag(f.get("attivo"))
    assistito.consenso_privacy = forms.flag(f.get("consenso_privacy"))


@bp.route("/")
@nutrizionista_required
def elenco():
    q = (request.args.get("q") or "").strip()
    stato = request.args.get("stato", "attivi")

    query = Assistito.query
    if stato == "attivi":
        query = query.filter_by(attivo=True)
    elif stato == "archiviati":
        query = query.filter_by(attivo=False)
    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(Assistito.nome.ilike(like), Assistito.cognome.ilike(like), Assistito.email.ilike(like))
        )

    assistiti = query.order_by(Assistito.cognome, Assistito.nome).all()
    return render_template("clients/list.html", assistiti=assistiti, q=q, stato=stato)


@bp.route("/nuovo", methods=["GET", "POST"])
@nutrizionista_required
def nuovo():
    if request.method == "POST":
        nome = forms.testo(request.form.get("nome"), 100)
        cognome = forms.testo(request.form.get("cognome"), 100)
        if not nome or not cognome:
            flash("Nome e cognome sono obbligatori.", "warning")
        else:
            assistito = Assistito(nome=nome, cognome=cognome)
            _leggi_form(assistito)
            db.session.add(assistito)
            db.session.commit()

            # La prima misurazione fissa il punto di partenza del percorso.
            if assistito.peso_iniziale_kg:
                db.session.add(
                    Misurazione(
                        assistito_id=assistito.id,
                        data=date.today(),
                        peso_kg=assistito.peso_iniziale_kg,
                        note="Misurazione iniziale",
                    )
                )
                db.session.commit()

            flash(f"{assistito.nome_completo} aggiunto.", "success")
            return redirect(url_for("clients.dettaglio", assistito_id=assistito.id))

    return render_template(
        "clients/form.html",
        assistito=None,
        diete=DIETE,
        obiettivi=OBIETTIVI,
        sessi=SESSI,
    )


@bp.route("/<int:assistito_id>")
@nutrizionista_required
def dettaglio(assistito_id: int):
    assistito = db.get_or_404(Assistito, assistito_id)
    livello = request.args.get("attivita", "leggero")
    misurazioni = assistito.misurazioni

    # Serie per il grafico: dalla più vecchia alla più recente.
    serie = [m for m in reversed(misurazioni) if m.peso_kg]

    return render_template(
        "clients/detail.html",
        assistito=assistito,
        misurazioni=misurazioni,
        serie_peso=serie,
        fabbisogno=fabbisogno_stimato(assistito, livello),
        livelli_attivita=LIVELLI_ATTIVITA,
        livello_scelto=livello,
        tipi_appuntamento=TIPI_APPUNTAMENTO,
        stati_appuntamento=STATI_APPUNTAMENTO,
        oggi=date.today(),
    )


@bp.route("/<int:assistito_id>/modifica", methods=["GET", "POST"])
@nutrizionista_required
def modifica(assistito_id: int):
    assistito = db.get_or_404(Assistito, assistito_id)
    if request.method == "POST":
        _leggi_form(assistito)
        if assistito.utente:
            assistito.utente.nome = assistito.nome_completo
        db.session.commit()
        flash("Scheda aggiornata.", "success")
        return redirect(url_for("clients.dettaglio", assistito_id=assistito.id))

    return render_template(
        "clients/form.html",
        assistito=assistito,
        diete=DIETE,
        obiettivi=OBIETTIVI,
        sessi=SESSI,
    )


@bp.route("/<int:assistito_id>/elimina", methods=["POST"])
@nutrizionista_required
def elimina(assistito_id: int):
    assistito = db.get_or_404(Assistito, assistito_id)
    nome = assistito.nome_completo
    db.session.delete(assistito)
    db.session.commit()
    flash(f"{nome} e tutti i suoi dati sono stati eliminati.", "success")
    return redirect(url_for("clients.elenco"))


# ----------------------------------------------------------------------
# Misurazioni
# ----------------------------------------------------------------------
@bp.route("/<int:assistito_id>/misurazioni", methods=["POST"])
@nutrizionista_required
def aggiungi_misurazione(assistito_id: int):
    assistito = db.get_or_404(Assistito, assistito_id)
    f = request.form
    misurazione = Misurazione(
        assistito_id=assistito.id,
        data=forms.data(f.get("data")) or date.today(),
        peso_kg=forms.numero(f.get("peso_kg")),
        massa_grassa_perc=forms.numero(f.get("massa_grassa_perc")),
        massa_magra_kg=forms.numero(f.get("massa_magra_kg")),
        vita_cm=forms.numero(f.get("vita_cm")),
        fianchi_cm=forms.numero(f.get("fianchi_cm")),
        torace_cm=forms.numero(f.get("torace_cm")),
        braccio_cm=forms.numero(f.get("braccio_cm")),
        coscia_cm=forms.numero(f.get("coscia_cm")),
        note=forms.testo(f.get("note")),
    )
    db.session.add(misurazione)
    if assistito.peso_iniziale_kg is None and misurazione.peso_kg:
        assistito.peso_iniziale_kg = misurazione.peso_kg
    db.session.commit()
    flash("Misurazione registrata.", "success")
    return redirect(url_for("clients.dettaglio", assistito_id=assistito.id) + "#misurazioni")


@bp.route("/<int:assistito_id>/misurazioni/<int:misurazione_id>/elimina", methods=["POST"])
@nutrizionista_required
def elimina_misurazione(assistito_id: int, misurazione_id: int):
    misurazione = db.get_or_404(Misurazione, misurazione_id)
    if misurazione.assistito_id != assistito_id:
        flash("Misurazione non trovata.", "warning")
    else:
        db.session.delete(misurazione)
        db.session.commit()
        flash("Misurazione eliminata.", "info")
    return redirect(url_for("clients.dettaglio", assistito_id=assistito_id) + "#misurazioni")


# ----------------------------------------------------------------------
# Appuntamenti
# ----------------------------------------------------------------------
@bp.route("/<int:assistito_id>/appuntamenti", methods=["POST"])
@nutrizionista_required
def aggiungi_appuntamento(assistito_id: int):
    assistito = db.get_or_404(Assistito, assistito_id)
    quando = forms.data_ora(request.form.get("data_ora"))
    if quando is None:
        flash("Indica data e ora dell'appuntamento.", "warning")
    else:
        db.session.add(
            Appuntamento(
                assistito_id=assistito.id,
                data_ora=quando,
                durata_minuti=forms.intero(request.form.get("durata_minuti")) or 45,
                tipo=forms.testo(request.form.get("tipo"), 40) or "Controllo",
                luogo=forms.testo(request.form.get("luogo"), 200),
                note=forms.testo(request.form.get("note")),
            )
        )
        db.session.commit()
        flash("Appuntamento fissato.", "success")
    return redirect(url_for("clients.dettaglio", assistito_id=assistito_id) + "#appuntamenti")


@bp.route("/appuntamenti/<int:appuntamento_id>/stato", methods=["POST"])
@nutrizionista_required
def stato_appuntamento(appuntamento_id: int):
    appuntamento = db.get_or_404(Appuntamento, appuntamento_id)
    nuovo_stato = forms.testo(request.form.get("stato"), 20)
    if nuovo_stato in STATI_APPUNTAMENTO:
        appuntamento.stato = nuovo_stato
        db.session.commit()
        flash(f"Appuntamento segnato come «{nuovo_stato}».", "success")
    return redirect(
        url_for("clients.dettaglio", assistito_id=appuntamento.assistito_id) + "#appuntamenti"
    )


@bp.route("/appuntamenti/<int:appuntamento_id>/elimina", methods=["POST"])
@nutrizionista_required
def elimina_appuntamento(appuntamento_id: int):
    appuntamento = db.get_or_404(Appuntamento, appuntamento_id)
    assistito_id = appuntamento.assistito_id
    db.session.delete(appuntamento)
    db.session.commit()
    flash("Appuntamento eliminato.", "info")
    return redirect(url_for("clients.dettaglio", assistito_id=assistito_id) + "#appuntamenti")


# ----------------------------------------------------------------------
# Messaggi
# ----------------------------------------------------------------------
@bp.route("/<int:assistito_id>/messaggi", methods=["POST"])
@nutrizionista_required
def invia_messaggio(assistito_id: int):
    assistito = db.get_or_404(Assistito, assistito_id)
    testo = forms.testo(request.form.get("testo"))
    if not testo:
        flash("Il messaggio è vuoto.", "warning")
    else:
        db.session.add(
            Messaggio(
                assistito_id=assistito.id,
                mittente_ruolo="nutrizionista",
                mittente_nome=utente_corrente().nome,
                testo=testo,
            )
        )
        # Leggendo la conversazione segniamo come letti quelli del cliente.
        for m in assistito.messaggi:
            if m.mittente_ruolo == "cliente" and not m.letto:
                m.letto = True
        db.session.commit()
        flash("Messaggio inviato.", "success")
    return redirect(url_for("clients.dettaglio", assistito_id=assistito_id) + "#messaggi")

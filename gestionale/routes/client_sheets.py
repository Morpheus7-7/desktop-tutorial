"""Schede dell'Accademia compilate dal gestionale e salvate nel cliente."""
from datetime import date, datetime

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .. import academy as ac
from ..models import Client, SchedaCompilata, db
from ..schede import SCHEDE_CLIENTE, leggi_form, precompila

bp = Blueprint("client_sheets", __name__, url_prefix="/clienti")


def _modello_or_404(scheda_id: str) -> dict:
    scheda = ac.get_scheda(scheda_id)
    if scheda is None or scheda_id not in SCHEDE_CLIENTE:
        abort(404)
    return scheda


def _compilata_or_404(client_id: int, compilata_id: int) -> SchedaCompilata:
    sc = db.get_or_404(SchedaCompilata, compilata_id)
    if sc.client_id != client_id:
        abort(404)
    return sc


def _data(valore: str) -> date:
    try:
        return datetime.strptime(valore, "%Y-%m-%d").date()
    except (TypeError, ValueError):
        return date.today()


def _salva(sc: SchedaCompilata, struttura: dict) -> None:
    sc.data_compilazione = _data(request.form.get("data_compilazione"))
    sc.consulente = (request.form.get("consulente") or "").strip()[:120] or None
    sc.contenuto = {"struttura": struttura, "valori": leggi_form(struttura, request.form)}


@bp.route("/<int:client_id>/schede/nuova/<scheda_id>", methods=["GET", "POST"])
def new_sheet(client_id, scheda_id):
    client = db.get_or_404(Client, client_id)
    struttura = _modello_or_404(scheda_id)
    if request.method == "POST":
        sc = SchedaCompilata(client_id=client.id, scheda_id=scheda_id, titolo=struttura["titolo"])
        _salva(sc, struttura)
        db.session.add(sc)
        db.session.commit()
        flash(f"Scheda «{sc.titolo}» salvata nella pratica del cliente.", "success")
        return redirect(url_for("client_sheets.view_sheet", client_id=client.id, compilata_id=sc.id))
    return render_template(
        "client_sheets/form.html", client=client, struttura=struttura, sc=None,
        valori=precompila(struttura, client), oggi=date.today(),
    )


@bp.route("/<int:client_id>/schede/<int:compilata_id>")
def view_sheet(client_id, compilata_id):
    client = db.get_or_404(Client, client_id)
    sc = _compilata_or_404(client_id, compilata_id)
    contenuto = sc.contenuto
    return render_template(
        "client_sheets/view.html", client=client, sc=sc,
        struttura=contenuto.get("struttura", {"sezioni": []}), valori=contenuto.get("valori", {}),
    )


@bp.route("/<int:client_id>/schede/<int:compilata_id>/modifica", methods=["GET", "POST"])
def edit_sheet(client_id, compilata_id):
    client = db.get_or_404(Client, client_id)
    sc = _compilata_or_404(client_id, compilata_id)
    struttura = sc.contenuto.get("struttura") or _modello_or_404(sc.scheda_id)
    if request.method == "POST":
        _salva(sc, struttura)
        db.session.commit()
        flash("Scheda aggiornata.", "success")
        return redirect(url_for("client_sheets.view_sheet", client_id=client.id, compilata_id=sc.id))
    return render_template(
        "client_sheets/form.html", client=client, struttura=struttura, sc=sc,
        valori=sc.contenuto.get("valori", {}), oggi=sc.data_compilazione,
    )


@bp.route("/<int:client_id>/schede/<int:compilata_id>/elimina", methods=["POST"])
def delete_sheet(client_id, compilata_id):
    sc = _compilata_or_404(client_id, compilata_id)
    db.session.delete(sc)
    db.session.commit()
    flash("Scheda eliminata.", "success")
    return redirect(url_for("clients.detail", client_id=client_id) + "#schede")

"""Schede dell'Accademia compilate dal gestionale e salvate nel cliente."""
import io
import uuid
from datetime import date, datetime
from pathlib import Path

from flask import (
    Blueprint, abort, current_app, flash, redirect, render_template, request, send_file, url_for,
)
from werkzeug.utils import secure_filename

from .. import academy as ac
from .. import desktop, google, mailer
from ..models import Client, Document, SchedaCompilata, db
from ..pdf import nome_file, scheda_pdf
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
        drive=cartella_drive(),
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


# ----------------------------------------------------------------------
# PDF, salvataggio nei documenti e in Google Drive, invio con Gmail
# ----------------------------------------------------------------------
def _pdf(client: Client, sc: SchedaCompilata) -> tuple[str, bytes]:
    contenuto = sc.contenuto
    dati = scheda_pdf(sc.titolo, client.ragione_sociale, sc.data_compilazione, sc.consulente,
                      contenuto.get("struttura", {"sezioni": []}), contenuto.get("valori", {}))
    return nome_file(sc.titolo, client.ragione_sociale, sc.data_compilazione), dati


def cartella_drive() -> str | None:
    """Cartella di Google Drive scelta su questo PC (impostazione locale)."""
    file_config = current_app.config.get("DC_CONFIG_FILE")
    config = desktop.leggi_configurazione(Path(file_config) if file_config else None)
    percorso = config.get("cartella_drive")
    return percorso if percorso and Path(percorso).is_dir() else None


@bp.route("/<int:client_id>/schede/<int:compilata_id>/pdf")
def sheet_pdf(client_id, compilata_id):
    client = db.get_or_404(Client, client_id)
    nome, dati = _pdf(client, _compilata_or_404(client_id, compilata_id))
    return send_file(io.BytesIO(dati), mimetype="application/pdf", as_attachment=True, download_name=nome)


@bp.route("/<int:client_id>/schede/<int:compilata_id>/salva-pdf", methods=["POST"])
def save_pdf(client_id, compilata_id):
    client = db.get_or_404(Client, client_id)
    sc = _compilata_or_404(client_id, compilata_id)
    nome, dati = _pdf(client, sc)
    dove = request.form.get("dove", "documenti")
    messaggi = []
    if dove in ("documenti", "entrambi"):
        cartella = Path(current_app.config["UPLOAD_FOLDER"])
        cartella.mkdir(parents=True, exist_ok=True)
        su_disco = f"{uuid.uuid4().hex}_{secure_filename(nome) or 'scheda.pdf'}"
        (cartella / su_disco).write_bytes(dati)
        db.session.add(Document(client_id=client.id, categoria="scheda", filename=su_disco,
                                original_name=nome, dimensione=len(dati),
                                note=f"Generato dalla scheda compilata il {sc.data_compilazione:%d/%m/%Y}"))
        db.session.commit()
        messaggi.append("nei documenti del cliente")
    if dove in ("drive", "entrambi"):
        drive = cartella_drive()
        if not drive:
            flash("Cartella di Google Drive non impostata o non trovata: sceglila in Impostazioni → Google.", "warning")
        else:
            try:
                google.salva_in_drive(drive, client.ragione_sociale, nome, dati)
                messaggi.append("in Google Drive")
            except OSError as exc:
                flash(f"Salvataggio in Google Drive non riuscito: {exc}", "danger")
    if messaggi:
        flash(f"PDF salvato {' e '.join(messaggi)}.", "success")
    return redirect(url_for("client_sheets.view_sheet", client_id=client.id, compilata_id=sc.id))


@bp.route("/<int:client_id>/schede/<int:compilata_id>/invia", methods=["GET", "POST"])
def email_sheet(client_id, compilata_id):
    client = db.get_or_404(Client, client_id)
    sc = _compilata_or_404(client_id, compilata_id)
    oggetto = request.form.get("oggetto") or f"{sc.titolo} — {client.ragione_sociale}"
    testo = request.form.get("testo") or (
        f"Gentile {client.referente or client.ragione_sociale},\n\n"
        f"in allegato trova la scheda «{sc.titolo}» compilata durante il nostro incontro "
        f"del {sc.data_compilazione:%d/%m/%Y}.\nSe qualcosa non corrisponde mi scriva pure.\n\n"
        f"Cordiali saluti\n{sc.consulente or ''}".rstrip()
    )
    destinatario = request.form.get("destinatario", client.email or "")
    if request.method == "POST":
        nome, dati = _pdf(client, sc)
        try:
            mailer.invia_al_cliente(destinatario, oggetto, testo, [(nome, dati, "application/pdf")])
        except ValueError as exc:
            flash(str(exc), "danger")
        except Exception as exc:  # noqa: BLE001 - errore del server di posta, da mostrare
            flash(f"Invio non riuscito: {exc}", "danger")
        else:
            flash(f"Email inviata a {destinatario} con il PDF allegato.", "success")
            return redirect(url_for("client_sheets.view_sheet", client_id=client.id, compilata_id=sc.id))
    return render_template("client_sheets/invia.html", client=client, sc=sc,
                           destinatario=destinatario, oggetto=oggetto, testo=testo)

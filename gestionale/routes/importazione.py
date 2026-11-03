"""Importazione di clienti e polizze da Excel: modello, anteprima, conferma."""
import io
import secrets
import tempfile
import time
from pathlib import Path

from flask import (
    Blueprint, current_app, flash, redirect, render_template, request, send_file, session, url_for,
)

from .. import desktop, import_excel
from ..archivio import ArchivioNonValido, percorso_db
from ..models import BRANCH_LABELS, RUOLI_PERSONA_LABELS

bp = Blueprint("importazione", __name__, url_prefix="/clienti/importa")

DURATA_FILE = 24 * 3600  # i file caricati e non confermati si cancellano dopo un giorno


def _cartella_temporanea() -> Path:
    cartella = Path(tempfile.gettempdir()) / "deal-combined-import"
    cartella.mkdir(exist_ok=True)
    adesso = time.time()
    for vecchio in cartella.glob("*.dat"):
        try:
            if adesso - vecchio.stat().st_mtime > DURATA_FILE:
                vecchio.unlink()
        except OSError:
            pass
    return cartella


def _file_in_attesa() -> tuple[Path, str] | None:
    attesa = session.get("dc_import") or {}
    token, nome = attesa.get("token"), attesa.get("nome")
    if not token or not nome or not token.isalnum():
        return None
    percorso = _cartella_temporanea() / f"{token}.dat"
    return (percorso, nome) if percorso.is_file() else None


@bp.route("/", methods=["GET"])
def start():
    return render_template("importazione/carica.html")


@bp.route("/modello.xlsx")
def template():
    return send_file(io.BytesIO(import_excel.modello_xlsx()), as_attachment=True,
                     download_name="Deal Combined - modello importazione.xlsx",
                     mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@bp.route("/", methods=["POST"])
def upload():
    file = request.files.get("file")
    if not file or not file.filename:
        flash("Scegli un file Excel (.xlsx) o CSV.", "warning")
        return redirect(url_for("importazione.start"))
    dati = file.read()
    try:
        anteprima = import_excel.analizza(dati, file.filename)
    except import_excel.FileNonValido as exc:
        flash(str(exc), "danger")
        return redirect(url_for("importazione.start"))
    token = secrets.token_hex(16)
    (_cartella_temporanea() / f"{token}.dat").write_bytes(dati)
    session["dc_import"] = {"token": token, "nome": file.filename[-200:]}
    return render_template("importazione/anteprima.html", a=anteprima, nome_file=file.filename, token=token,
                           rami=BRANCH_LABELS, ruoli=RUOLI_PERSONA_LABELS)


@bp.route("/conferma", methods=["POST"])
def confirm():
    attesa = _file_in_attesa()
    if not attesa or request.form.get("token") != session["dc_import"]["token"]:
        flash("Il file da importare non è più disponibile: caricalo di nuovo.", "warning")
        return redirect(url_for("importazione.start"))
    percorso, nome = attesa
    try:
        # Si rilegge il file: nel frattempo l'archivio potrebbe essere cambiato.
        anteprima = import_excel.analizza(percorso.read_bytes(), nome)
    except import_excel.FileNonValido as exc:
        flash(str(exc), "danger")
        return redirect(url_for("importazione.start"))
    try:
        desktop.esegui_backup(percorso_db(current_app.config["SQLALCHEMY_DATABASE_URI"]).parent, motivo="import-excel")
    except (ArchivioNonValido, OSError):
        pass  # database non SQLite (es. ambiente di prova): niente backup
    esito = import_excel.importa(anteprima)
    percorso.unlink(missing_ok=True)
    session.pop("dc_import", None)
    parti = [f"{esito['clienti']} clienti nuovi", f"{esito['polizze']} polizze"]
    if esito.get("persone"):
        parti.append(f"{esito['persone']} amministratori/persone collegate")
    if esito["completati"]:
        parti.append(f"{esito['completati']} clienti esistenti completati")
    flash("Importazione completata: " + ", ".join(parti) + ".", "success")
    return redirect(url_for("clients.list_clients"))


@bp.route("/annulla", methods=["POST"])
def cancel():
    attesa = _file_in_attesa()
    if attesa:
        attesa[0].unlink(missing_ok=True)
    session.pop("dc_import", None)
    return redirect(url_for("importazione.start"))

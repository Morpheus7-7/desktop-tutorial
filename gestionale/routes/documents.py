"""Archivio documenti: upload, download, eliminazione."""
import os
import uuid

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_from_directory,
    url_for,
)
from werkzeug.utils import secure_filename

from ..models import DOCUMENT_CATEGORIES, Client, Document, db

bp = Blueprint("documents", __name__, url_prefix="/documenti")

ALLOWED_EXTENSIONS = {
    "pdf", "doc", "docx", "xls", "xlsx", "odt", "ods",
    "png", "jpg", "jpeg", "gif", "txt", "csv", "p7m", "eml", "zip",
}


def _allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@bp.route("/")
def list_documents():
    categoria = request.args.get("categoria", "")
    query = Document.query
    if categoria:
        query = query.filter_by(categoria=categoria)
    documenti = query.order_by(Document.uploaded_at.desc()).all()
    return render_template(
        "documents/list.html",
        documenti=documenti,
        categoria=categoria,
        document_categories=DOCUMENT_CATEGORIES,
    )


def _resolve_policy_id(client, raw):
    if not raw:
        return None
    try:
        pid = int(raw)
    except (ValueError, TypeError):
        return None
    return pid if pid in [p.id for p in client.polizze] else None


@bp.route("/carica/<int:client_id>", methods=["POST"])
def upload(client_id):
    client = db.get_or_404(Client, client_id)
    # Accetta sia un singolo file sia una selezione multipla (drag & drop).
    files = [f for f in request.files.getlist("file") if f and f.filename]
    if not files:
        flash("Seleziona uno o più file da caricare.", "warning")
        return redirect(url_for("clients.detail", client_id=client.id) + "#documenti")

    policy_id = _resolve_policy_id(client, request.form.get("policy_id"))
    categoria = request.form.get("categoria", "altro")
    note = request.form.get("note", "").strip() or None
    upload_folder = current_app.config["UPLOAD_FOLDER"]

    caricati, scartati = 0, []
    for file in files:
        original = file.filename
        if not _allowed(original):
            scartati.append(original)
            continue
        safe = secure_filename(original) or "documento"
        stored_name = f"{uuid.uuid4().hex}_{safe}"
        path = os.path.join(upload_folder, stored_name)
        file.save(path)
        try:
            dimensione = os.path.getsize(path)
        except OSError:
            dimensione = None
        db.session.add(
            Document(
                client_id=client.id,
                policy_id=policy_id,
                categoria=categoria,
                filename=stored_name,
                original_name=original,
                dimensione=dimensione,
                note=note,
            )
        )
        caricati += 1

    if caricati:
        db.session.commit()
        flash(
            f"{caricati} documento{'i' if caricati > 1 else ''} caricat{'i' if caricati > 1 else 'o'}.",
            "success",
        )
    if scartati:
        flash("Tipo di file non consentito: " + ", ".join(scartati), "danger")
    return redirect(url_for("clients.detail", client_id=client.id) + "#documenti")


@bp.route("/<int:document_id>/scarica")
def download(document_id):
    doc = db.get_or_404(Document, document_id)
    return send_from_directory(
        current_app.config["UPLOAD_FOLDER"],
        doc.filename,
        as_attachment=True,
        download_name=doc.original_name,
    )


@bp.route("/<int:document_id>/elimina", methods=["POST"])
def delete(document_id):
    doc = db.get_or_404(Document, document_id)
    client_id = doc.client_id
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], doc.filename)
    if os.path.exists(path):
        os.remove(path)
    db.session.delete(doc)
    db.session.commit()
    flash("Documento eliminato.", "success")
    if request.form.get("da_archivio"):
        return redirect(url_for("documents.list_documents"))
    return redirect(url_for("clients.detail", client_id=client_id) + "#documenti")

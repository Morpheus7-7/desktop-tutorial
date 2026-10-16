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
from ..security import audit, safe_next
from ..utils import paginate, parse_int

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
    q = (request.args.get("q") or "").strip()
    query = Document.query.join(Client, Document.client_id == Client.id)
    if categoria:
        query = query.filter(Document.categoria == categoria)
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Document.original_name.ilike(like), Client.ragione_sociale.ilike(like)))
    pagination = paginate(query.order_by(Document.uploaded_at.desc()))
    return render_template(
        "documents/list.html",
        pagination=pagination,
        documenti=pagination.items,
        categoria=categoria,
        q=q,
        document_categories=DOCUMENT_CATEGORIES,
    )


def _resolve_policy_id(client, raw):
    pid = parse_int(raw)
    return pid if pid in [p.id for p in client.polizze] else None


def _resolve_claim_id(client, raw):
    cid = parse_int(raw)
    return cid if cid in [s.id for s in client.sinistri] else None


def _destinazione(client_id, claim_id=None):
    if claim_id:
        return url_for("claims.detail", claim_id=claim_id) + "#documenti"
    return safe_next(request.form.get("next")) or (
        url_for("clients.detail", client_id=client_id) + "#documenti"
    )


@bp.route("/carica/<int:client_id>", methods=["POST"])
def upload(client_id):
    client = db.get_or_404(Client, client_id)
    # Accetta sia un singolo file sia una selezione multipla (drag & drop).
    files = [f for f in request.files.getlist("file") if f and f.filename]
    claim_id = _resolve_claim_id(client, request.form.get("claim_id"))
    if not files:
        flash("Seleziona uno o più file da caricare.", "warning")
        return redirect(_destinazione(client.id, claim_id))

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
                claim_id=claim_id,
                categoria=categoria if categoria in dict(DOCUMENT_CATEGORIES) else "altro",
                filename=stored_name,
                original_name=original,
                dimensione=dimensione,
                note=note,
            )
        )
        caricati += 1

    if caricati:
        audit("crea", "documento", None,
              f"Caricati {caricati} documenti per «{client.ragione_sociale}»")
        db.session.commit()
        flash(
            f"{caricati} documento{'i' if caricati > 1 else ''} caricat{'i' if caricati > 1 else 'o'}.",
            "success",
        )
    if scartati:
        flash("Tipo di file non consentito: " + ", ".join(scartati), "danger")
    return redirect(_destinazione(client.id, claim_id))


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
    client_id, claim_id = doc.client_id, doc.claim_id
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], doc.filename)
    audit("elimina", "documento", doc.id,
          f"Eliminato il documento «{doc.original_name}» di «{doc.cliente.ragione_sociale}»")
    db.session.delete(doc)
    db.session.commit()
    if os.path.exists(path):
        os.remove(path)
    flash("Documento eliminato.", "success")
    if request.form.get("da_archivio"):
        return redirect(url_for("documents.list_documents"))
    return redirect(_destinazione(client_id, claim_id if request.form.get("da_sinistro") else None))

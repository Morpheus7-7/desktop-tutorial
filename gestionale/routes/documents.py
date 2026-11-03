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
from werkzeug.security import safe_join
from werkzeug.utils import secure_filename

from ..backup import cartella_documenti
from ..models import CARTELLE_DOCUMENTI, CARTELLA_DEL_TIPO, DOCUMENT_CATEGORIES, Client, Document, db
from ..security import audit, safe_next
from ..utils import paginate, parse_int

bp = Blueprint("documents", __name__, url_prefix="/documenti")

ALLOWED_EXTENSIONS = {
    "pdf", "doc", "docx", "xls", "xlsx", "odt", "ods",
    "png", "jpg", "jpeg", "gif", "txt", "csv", "p7m", "eml", "zip",
}

# Nome su disco «<uuid>_<nome sicuro>» al massimo di 100 caratteri: con la
# cartella dati in un percorso lungo (es. OneDrive aziendale) si resta sotto
# il limite di 260 caratteri dei percorsi di Windows.
LUNGHEZZA_MAX_NOME_FILE = 100
LUNGHEZZA_MAX_NOME_ORIGINALE = Document.__table__.c.original_name.type.length or 300


LUNGHEZZA_MAX_CARTELLA = 80


def nome_cartella(valore) -> str | None:
    """Nome di una cartella creata dall'utente, ripulito (None = cartella del tipo di documento)."""
    nome = " ".join((valore or "").replace("/", " ").replace("\\", " ").split())[:LUNGHEZZA_MAX_CARTELLA]
    return nome or None


def _allowed(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def tronca_nome(nome: str, massimo: int) -> str:
    """Accorcia un nome di file a ``massimo`` caratteri conservando l'estensione."""
    if len(nome) <= massimo:
        return nome
    base, estensione = os.path.splitext(nome)
    estensione = estensione[:16] if len(estensione) < massimo else ""
    return base[: massimo - len(estensione)] + estensione


def nome_su_disco(originale: str) -> str:
    """Nome univoco e sicuro con cui salvare il file (al massimo 100 caratteri)."""
    prefisso = f"{uuid.uuid4().hex}_"
    sicuro = secure_filename(originale) or "documento"
    return prefisso + tronca_nome(sicuro, LUNGHEZZA_MAX_NOME_FILE - len(prefisso))


@bp.route("/")
def list_documents():
    categoria = request.args.get("categoria", "")
    cartella = request.args.get("cartella", "")
    q = (request.args.get("q") or "").strip()
    query = Document.query.join(Client, Document.client_id == Client.id)
    if categoria:
        query = query.filter(Document.categoria == categoria)
    if cartella.startswith("personale:"):
        query = query.filter(Document.cartella == cartella.split(":", 1)[1])
    elif cartella:
        tipi = [t for t, c in CARTELLA_DEL_TIPO.items() if c == cartella]
        query = query.filter(Document.cartella.is_(None), Document.categoria.in_(tipi or [""]))
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Document.original_name.ilike(like), Client.ragione_sociale.ilike(like)))
    pagination = paginate(query.order_by(Document.uploaded_at.desc()))
    return render_template(
        "documents/list.html",
        pagination=pagination,
        documenti=pagination.items,
        categoria=categoria,
        cartella=cartella,
        q=q,
        cartelle_documenti=CARTELLE_DOCUMENTI,
        cartelle_personali=[r[0] for r in db.session.query(Document.cartella).filter(Document.cartella.isnot(None))
                            .distinct().order_by(Document.cartella)],
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
    cartella = nome_cartella(request.form.get("cartella"))
    note = request.form.get("note", "").strip() or None
    upload_folder = cartella_documenti()
    os.makedirs(upload_folder, exist_ok=True)

    caricati, scartati, non_salvati = 0, [], []
    for file in files:
        original = file.filename
        if not _allowed(original):
            scartati.append(original)
            continue
        stored_name = nome_su_disco(original)
        path = os.path.join(upload_folder, stored_name)
        try:
            file.save(path)
        except OSError:
            current_app.logger.exception("Salvataggio del documento %s non riuscito", path)
            try:
                os.remove(path)
            except OSError:
                pass
            non_salvati.append(original)
            continue
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
                original_name=tronca_nome(original, LUNGHEZZA_MAX_NOME_ORIGINALE),
                dimensione=dimensione,
                note=note,
                cartella=cartella,
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
    if non_salvati:
        flash("Impossibile salvare su disco: " + ", ".join(non_salvati)
              + ". Controlla lo spazio libero e i permessi della cartella dei documenti.", "danger")
    return redirect(_destinazione(client.id, claim_id))


@bp.route("/<int:document_id>/scarica")
def download(document_id):
    doc = db.get_or_404(Document, document_id)
    return send_from_directory(
        cartella_documenti(),
        doc.filename,
        as_attachment=True,
        download_name=doc.original_name,
    )


@bp.route("/<int:document_id>/sposta", methods=["POST"])
def move(document_id):
    """Cambia tipo di documento e/o cartella."""
    doc = db.get_or_404(Document, document_id)
    categoria = request.form.get("categoria")
    if categoria in dict(DOCUMENT_CATEGORIES):
        doc.categoria = categoria
    doc.cartella = nome_cartella(request.form.get("cartella"))
    audit("modifica", "documento", doc.id, f"Spostato il documento «{doc.original_name}» in «{doc.cartella_nome}»")
    db.session.commit()
    flash(f"Documento spostato in «{doc.cartella_nome}».", "success")
    if request.form.get("da_archivio"):
        return redirect(url_for("documents.list_documents"))
    return redirect(_destinazione(doc.client_id))


@bp.route("/<int:document_id>/elimina", methods=["POST"])
def delete(document_id):
    doc = db.get_or_404(Document, document_id)
    client_id, claim_id = doc.client_id, doc.claim_id
    # Il nome arriva dal database (anche da un backup ripristinato): mai fuori
    # dalla cartella dei documenti.
    path = safe_join(cartella_documenti(), doc.filename)
    if path is None:
        current_app.logger.warning("Documento #%s con nome file non valido: %r", doc.id, doc.filename)
    audit("elimina", "documento", doc.id,
          f"Eliminato il documento «{doc.original_name}» di «{doc.cliente.ragione_sociale}»")
    db.session.delete(doc)
    db.session.commit()
    file_rimasto = False
    if path:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass
        except OSError:  # es. Windows: file aperto in un altro programma
            current_app.logger.warning("File del documento non rimosso: %s", path, exc_info=True)
            file_rimasto = True
    if file_rimasto:
        flash("Documento eliminato dall'archivio, ma il file su disco è in uso (ad esempio aperto in un "
              "altro programma) e non è stato rimosso: resta nella cartella dei documenti, non più "
              "collegato al gestionale.", "warning")
    else:
        flash("Documento eliminato.", "success")
    if request.form.get("da_archivio"):
        return redirect(url_for("documents.list_documents"))
    return redirect(_destinazione(client_id, claim_id if request.form.get("da_sinistro") else None))

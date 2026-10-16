"""Registro attività (solo amministratori)."""
from datetime import timedelta

from flask import Blueprint, render_template, request

from ..export import csv_response
from ..models import AuditLog, User, db
from ..security import audit, require_admin
from ..utils import paginate, parse_date

bp = Blueprint("audit", __name__, url_prefix="/registro")
bp.before_request(require_admin)

AZIONI = [
    ("login", "Accesso"),
    ("login_fallito", "Accesso non riuscito"),
    ("logout", "Uscita"),
    ("crea", "Creazione"),
    ("modifica", "Modifica"),
    ("elimina", "Eliminazione"),
    ("incasso", "Incasso"),
    ("storno", "Storno"),
    ("rinnovo", "Rinnovo"),
    ("rimessa", "Rimessa"),
    ("export", "Esportazione"),
    ("backup", "Backup"),
    ("ripristino", "Ripristino"),
]
ENTITA = [
    ("cliente", "Cliente"),
    ("polizza", "Polizza"),
    ("titolo", "Titolo"),
    ("sinistro", "Sinistro"),
    ("documento", "Documento"),
    ("opportunita", "Opportunità"),
    ("utente", "Utente"),
    ("impostazioni", "Impostazioni"),
    ("sistema", "Sistema"),
]


def _query():
    query = AuditLog.query
    utente = request.args.get("utente", "")
    azione = request.args.get("azione", "")
    entita = request.args.get("entita", "")
    dal = parse_date(request.args.get("dal"))
    al = parse_date(request.args.get("al"))
    q = (request.args.get("q") or "").strip()
    if utente:
        query = query.filter(AuditLog.username == utente)
    if azione:
        query = query.filter(AuditLog.azione == azione)
    if entita:
        query = query.filter(AuditLog.entita == entita)
    if dal:
        query = query.filter(AuditLog.created_at >= dal)
    if al:
        query = query.filter(AuditLog.created_at < al + timedelta(days=1))
    if q:
        query = query.filter(AuditLog.descrizione.ilike(f"%{q}%"))
    return query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())


@bp.route("/")
def list_log():
    pagination = paginate(_query())
    utenti = [u for (u,) in db.session.query(User.username).order_by(User.username).all()]
    return render_template(
        "audit/list.html",
        pagination=pagination,
        voci=pagination.items,
        utenti=utenti,
        azioni=AZIONI,
        entita=ENTITA,
        azioni_label=dict(AZIONI),
        entita_label=dict(ENTITA),
        filtri=request.args,
    )


@bp.route("/esporta.csv")
def export_log():
    voci = _query().limit(50000).all()
    audit("export", "sistema", None, f"Esportato il registro attività ({len(voci)} voci)", commit=True)
    return csv_response(
        "registro_attivita",
        ["Data e ora", "Utente", "Azione", "Entità", "ID", "Descrizione", "IP"],
        [(v.created_at, v.username, v.azione, v.entita, v.entita_id, v.descrizione, v.ip) for v in voci],
    )

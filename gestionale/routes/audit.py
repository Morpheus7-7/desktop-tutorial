"""Registro attività (solo amministratori)."""
from datetime import datetime, time

from flask import Blueprint, render_template, request

from ..export import csv_response
from ..models import AuditLog, User, db
from ..security import audit, require_admin
from ..utils import fine_giornata, paginate, parse_date, parse_int

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


def _escape_like(testo: str) -> str:
    """Il testo cercato vale alla lettera: «%» e «_» non fanno da jolly."""
    return testo.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _query():
    query = AuditLog.query
    utente = request.args.get("utente") or ""
    azione = request.args.get("azione") or ""
    entita = request.args.get("entita") or ""
    # Date fuori dall'intervallo 1900–2100 o non valide vengono ignorate
    # (niente errori per valori come 9999-12-31).
    dal = parse_date(request.args.get("dal"))
    al = parse_date(request.args.get("al"))
    if dal and al and al < dal:
        dal, al = al, dal
    # Interi enormi o negativi vengono ignorati invece di arrivare a SQLite (OverflowError).
    entita_id = parse_int(request.args.get("entita_id"), minimo=1)
    q = (request.args.get("q") or "").strip()[:200]
    if utente:
        query = query.filter(AuditLog.username == utente)
    if azione:
        query = query.filter(AuditLog.azione == azione)
    if entita:
        query = query.filter(AuditLog.entita == entita)
    if entita_id:
        query = query.filter(AuditLog.entita_id == entita_id)
    if dal:
        query = query.filter(AuditLog.created_at >= datetime.combine(dal, time.min))
    if al:
        # «Al» incluso: fino all'ultimo istante del giorno.
        query = query.filter(AuditLog.created_at <= fine_giornata(al))
    if q:
        query = query.filter(AuditLog.descrizione.ilike(f"%{_escape_like(q)}%", escape="\\"))
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

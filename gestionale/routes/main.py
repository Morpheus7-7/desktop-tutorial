"""Dashboard e scadenzario."""
from datetime import date, timedelta

from flask import Blueprint, render_template, request

from ..models import Client, FollowUp, Notification, Policy, db

bp = Blueprint("main", __name__)


@bp.route("/")
def dashboard():
    today = date.today()
    limite_30 = today + timedelta(days=30)
    limite_60 = today + timedelta(days=60)

    attive = Policy.query.filter(Policy.stato.in_(["attiva", "in_rinnovo"]))
    stats = {
        "clienti": Client.query.count(),
        "aziende": Client.query.filter_by(tipo="azienda").count(),
        "professionisti": Client.query.filter_by(tipo="professionista").count(),
        "polizze_attive": attive.count(),
        "premi_totali": db.session.query(db.func.coalesce(db.func.sum(Policy.premio_annuo), 0.0))
        .filter(Policy.stato.in_(["attiva", "in_rinnovo"]))
        .scalar(),
        "scadenze_30gg": attive.filter(
            Policy.data_scadenza.isnot(None),
            Policy.data_scadenza >= today,
            Policy.data_scadenza <= limite_30,
        ).count(),
        "polizze_scadute": attive.filter(
            Policy.data_scadenza.isnot(None), Policy.data_scadenza < today
        ).count(),
        "followup_aperti": FollowUp.query.filter_by(stato="aperto").count(),
        "followup_in_ritardo": FollowUp.query.filter(
            FollowUp.stato == "aperto", FollowUp.data_scadenza < today
        ).count(),
    }

    prossime_scadenze = (
        Policy.query.filter(
            Policy.stato.in_(["attiva", "in_rinnovo"]),
            Policy.data_scadenza.isnot(None),
            Policy.data_scadenza <= limite_60,
        )
        .order_by(Policy.data_scadenza.asc())
        .limit(8)
        .all()
    )
    prossimi_followup = (
        FollowUp.query.filter(FollowUp.stato == "aperto")
        .order_by(FollowUp.data_scadenza.asc())
        .limit(8)
        .all()
    )
    ultime_notifiche = (
        Notification.query.filter_by(letta=False)
        .order_by(Notification.created_at.desc())
        .limit(6)
        .all()
    )
    ultimi_clienti = Client.query.order_by(Client.created_at.desc()).limit(5).all()

    return render_template(
        "dashboard.html",
        stats=stats,
        prossime_scadenze=prossime_scadenze,
        prossimi_followup=prossimi_followup,
        ultime_notifiche=ultime_notifiche,
        ultimi_clienti=ultimi_clienti,
    )


@bp.route("/scadenzario")
def scadenzario():
    today = date.today()
    try:
        giorni = int(request.args.get("giorni", 90))
    except ValueError:
        giorni = 90
    limite = today + timedelta(days=giorni)

    polizze = (
        Policy.query.filter(
            Policy.stato.in_(["attiva", "in_rinnovo"]),
            Policy.data_scadenza.isnot(None),
            Policy.data_scadenza <= limite,
        )
        .order_by(Policy.data_scadenza.asc())
        .all()
    )
    followups = (
        FollowUp.query.filter(
            FollowUp.stato == "aperto", FollowUp.data_scadenza <= limite
        )
        .order_by(FollowUp.data_scadenza.asc())
        .all()
    )
    return render_template(
        "scadenzario.html", polizze=polizze, followups=followups, giorni=giorni
    )

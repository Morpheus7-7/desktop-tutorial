"""Dashboard, scadenzario, ricerca globale e statistiche."""
from datetime import date, timedelta

from flask import Blueprint, render_template, request

from ..models import (
    BRANCH_LABELS,
    OPPORTUNITY_OPEN_STAGES,
    OPPORTUNITY_STAGES,
    Client,
    FollowUp,
    Notification,
    Opportunity,
    Policy,
    db,
)

bp = Blueprint("main", __name__)


def _premi_provvigioni_attive():
    """Somma premi e provvigioni delle polizze attive/in rinnovo."""
    premi = (
        db.session.query(db.func.coalesce(db.func.sum(Policy.premio_annuo), 0.0))
        .filter(Policy.stato.in_(["attiva", "in_rinnovo"]))
        .scalar()
    )
    provv = (
        db.session.query(
            db.func.coalesce(
                db.func.sum(Policy.premio_annuo * Policy.provvigione_perc / 100.0), 0.0
            )
        )
        .filter(
            Policy.stato.in_(["attiva", "in_rinnovo"]),
            Policy.premio_annuo.isnot(None),
            Policy.provvigione_perc.isnot(None),
        )
        .scalar()
    )
    return premi, provv


@bp.route("/")
def dashboard():
    today = date.today()
    limite_30 = today + timedelta(days=30)
    limite_60 = today + timedelta(days=60)

    attive = Policy.query.filter(Policy.stato.in_(["attiva", "in_rinnovo"]))
    premi_totali, provvigioni_totali = _premi_provvigioni_attive()
    stats = {
        "clienti": Client.query.count(),
        "aziende": Client.query.filter_by(tipo="azienda").count(),
        "professionisti": Client.query.filter_by(tipo="professionista").count(),
        "dipendenti": Client.query.filter_by(tipo="dipendente").count(),
        "polizze_attive": attive.count(),
        "premi_totali": premi_totali,
        "provvigioni_totali": provvigioni_totali,
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
        "opportunita_aperte": Opportunity.query.filter(
            Opportunity.fase.in_(OPPORTUNITY_OPEN_STAGES)
        ).count(),
        "pipeline_valore": (
            db.session.query(db.func.coalesce(db.func.sum(Opportunity.premio_stimato), 0.0))
            .filter(Opportunity.fase.in_(OPPORTUNITY_OPEN_STAGES))
            .scalar()
        ),
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
    opportunita_recenti = (
        Opportunity.query.filter(Opportunity.fase.in_(OPPORTUNITY_OPEN_STAGES))
        .order_by(Opportunity.updated_at.desc())
        .limit(6)
        .all()
    )

    return render_template(
        "dashboard.html",
        stats=stats,
        prossime_scadenze=prossime_scadenze,
        prossimi_followup=prossimi_followup,
        ultime_notifiche=ultime_notifiche,
        opportunita_recenti=opportunita_recenti,
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


@bp.route("/cerca")
def search():
    q = (request.args.get("q") or "").strip()
    clienti, polizze = [], []
    if q:
        like = f"%{q}%"
        clienti = (
            Client.query.filter(
                db.or_(
                    Client.ragione_sociale.ilike(like),
                    Client.partita_iva.ilike(like),
                    Client.codice_fiscale.ilike(like),
                    Client.citta.ilike(like),
                    Client.settore.ilike(like),
                    Client.professione.ilike(like),
                    Client.datore_lavoro.ilike(like),
                    Client.email.ilike(like),
                )
            )
            .order_by(Client.ragione_sociale.asc())
            .limit(50)
            .all()
        )
        polizze = (
            Policy.query.filter(
                db.or_(
                    Policy.numero_polizza.ilike(like),
                    Policy.compagnia.ilike(like),
                )
            )
            .order_by(Policy.data_scadenza.is_(None), Policy.data_scadenza.asc())
            .limit(50)
            .all()
        )
    return render_template("search.html", q=q, clienti=clienti, polizze=polizze)


@bp.route("/statistiche")
def analytics():
    """Cruscotto analitico: portafoglio per ramo, premi, provvigioni, pipeline."""
    today = date.today()
    attive_filter = Policy.query.filter(Policy.stato.in_(["attiva", "in_rinnovo"]))

    # Portafoglio per ramo: numero, premi e provvigioni.
    per_ramo = {}
    for p in attive_filter.all():
        r = per_ramo.setdefault(
            p.ramo, {"ramo": p.ramo, "nome": BRANCH_LABELS.get(p.ramo, p.ramo),
                     "numero": 0, "premi": 0.0, "provvigioni": 0.0}
        )
        r["numero"] += 1
        r["premi"] += p.premio_annuo or 0.0
        r["provvigioni"] += p.provvigione_annua or 0.0
    rami = sorted(per_ramo.values(), key=lambda x: -x["premi"])
    premi_max = max([r["premi"] for r in rami], default=0.0)

    premi_totali, provvigioni_totali = _premi_provvigioni_attive()

    # Clienti per tipo.
    clienti_per_tipo = [
        {"tipo": "Aziende", "n": Client.query.filter_by(tipo="azienda").count()},
        {"tipo": "Professionisti", "n": Client.query.filter_by(tipo="professionista").count()},
        {"tipo": "Dipendenti", "n": Client.query.filter_by(tipo="dipendente").count()},
    ]

    # Pipeline per fase (solo fasi utili) con valore stimato.
    pipeline = []
    for fase, label in OPPORTUNITY_STAGES:
        opp = Opportunity.query.filter_by(fase=fase).all()
        valore = sum(o.premio_stimato or 0.0 for o in opp)
        pipeline.append({"fase": fase, "label": label, "numero": len(opp), "valore": valore})
    pipeline_max = max([f["numero"] for f in pipeline], default=0)

    # Premi in scadenza nei prossimi 12 mesi, raggruppati per mese.
    mesi = []
    for i in range(12):
        anno = today.year + (today.month - 1 + i) // 12
        mese = (today.month - 1 + i) % 12 + 1
        inizio = date(anno, mese, 1)
        fine = date(anno + (mese // 12), (mese % 12) + 1, 1)
        tot = (
            db.session.query(db.func.coalesce(db.func.sum(Policy.premio_annuo), 0.0))
            .filter(
                Policy.stato.in_(["attiva", "in_rinnovo"]),
                Policy.data_scadenza >= inizio,
                Policy.data_scadenza < fine,
            )
            .scalar()
        )
        mesi.append({"label": inizio.strftime("%m/%y"), "premi": tot})
    mesi_max = max([m["premi"] for m in mesi], default=0.0)

    return render_template(
        "analytics.html",
        rami=rami, premi_max=premi_max,
        premi_totali=premi_totali, provvigioni_totali=provvigioni_totali,
        clienti_per_tipo=clienti_per_tipo,
        pipeline=pipeline, pipeline_max=pipeline_max,
        mesi=mesi, mesi_max=mesi_max,
        totale_polizze=attive_filter.count(),
    )

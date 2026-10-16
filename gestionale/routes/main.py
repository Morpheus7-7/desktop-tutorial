"""Dashboard, scadenzario, ricerca globale e statistiche."""
from datetime import date, timedelta

from flask import Blueprint, Response, render_template, request

from ..models import (
    BRANCH_LABELS,
    CLAIM_OPEN_STATUSES,
    CLAIM_STATUSES,
    CLAIM_TYPE_LABELS,
    OPPORTUNITY_OPEN_STAGES,
    OPPORTUNITY_STAGES,
    Claim,
    Client,
    FollowUp,
    Notification,
    Opportunity,
    Policy,
    Title,
    db,
)
from ..agenda import eventi_agenda, esporta_ics
from ..security import audit
from ..titoli import add_months
from ..utils import parse_int

bp = Blueprint("main", __name__)

STATI_ATTIVI = ["attiva", "in_rinnovo"]


def _premi_provvigioni_attive():
    """Somma premi e provvigioni delle polizze attive/in rinnovo."""
    premi = (
        db.session.query(db.func.coalesce(db.func.sum(Policy.premio_annuo), 0.0))
        .filter(Policy.stato.in_(STATI_ATTIVI))
        .scalar()
    )
    provv = (
        db.session.query(
            db.func.coalesce(
                db.func.sum(Policy.premio_annuo * Policy.provvigione_perc / 100.0), 0.0
            )
        )
        .filter(
            Policy.stato.in_(STATI_ATTIVI),
            Policy.premio_annuo.isnot(None),
            Policy.provvigione_perc.isnot(None),
        )
        .scalar()
    )
    return premi, provv


def _somma_titoli(*condizioni):
    return (
        db.session.query(
            db.func.count(Title.id), db.func.coalesce(db.func.sum(Title.premio_lordo), 0.0)
        )
        .filter(*condizioni)
        .one()
    )


def _termini_disdetta(dal: date, al: date) -> list[Policy]:
    """Polizze a tacito rinnovo, senza disdetta, con termine di preavviso in [dal, al]."""
    candidate = Policy.query.filter(
        Policy.stato.in_(STATI_ATTIVI),
        Policy.tacito_rinnovo.is_(True),
        Policy.data_disdetta.is_(None),
        Policy.data_scadenza.isnot(None),
        Policy.data_scadenza >= dal,
    ).all()
    return sorted(
        (p for p in candidate if p.termine_disdetta and dal <= p.termine_disdetta <= al),
        key=lambda p: p.termine_disdetta,
    )


@bp.route("/")
def dashboard():
    today = date.today()
    limite_30 = today + timedelta(days=30)
    limite_60 = today + timedelta(days=60)

    attive = Policy.query.filter(Policy.stato.in_(STATI_ATTIVI))
    premi_totali, provvigioni_totali = _premi_provvigioni_attive()
    arretrati = _somma_titoli(Title.stato == "da_incassare", Title.data_effetto < today)
    in_scadenza = _somma_titoli(
        Title.stato == "da_incassare", Title.data_effetto >= today, Title.data_effetto <= limite_30
    )
    incassato_mese = _somma_titoli(
        Title.stato == "incassato", Title.data_incasso >= today.replace(day=1)
    )
    sinistri_aperti = Claim.query.filter(Claim.stato.in_(CLAIM_OPEN_STATUSES))
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
        "polizze_non_in_vigore": attive.filter(
            Policy.data_decorrenza.isnot(None), Policy.data_decorrenza > today
        ).count(),
        "termini_disdetta_30gg": len(_termini_disdetta(today, limite_30)),
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
        "titoli_arretrati": arretrati[0],
        "importo_arretrati": arretrati[1],
        "titoli_in_scadenza": in_scadenza[0],
        "importo_in_scadenza": in_scadenza[1],
        "incassi_mese": incassato_mese[0],
        "incassato_mese": incassato_mese[1],
        "sinistri_aperti": sinistri_aperti.count(),
        "sinistri_da_denunciare": sinistri_aperti.filter(Claim.data_denuncia.is_(None)).count(),
        "clienti_senza_privacy": Client.query.filter(Client.data_consenso_privacy.is_(None)).count(),
    }

    # Solo le scadenze future: le polizze già scadute sono conteggiate a parte
    # (card «Scadute da rinnovare») e non devono nascondere quelle imminenti.
    prossime_scadenze = (
        Policy.query.filter(
            Policy.stato.in_(STATI_ATTIVI),
            Policy.data_scadenza.isnot(None),
            Policy.data_scadenza >= today,
            Policy.data_scadenza <= limite_60,
        )
        .order_by(Policy.data_scadenza.asc())
        .limit(8)
        .all()
    )
    prossimi_eventi = [
        e for e in eventi_agenda(today, limite_30, {"decorrenza", "disdetta", "denuncia", "sospensione"})
    ][:8]
    titoli_urgenti = (
        Title.query.filter(Title.stato == "da_incassare", Title.data_effetto <= limite_30)
        .order_by(Title.data_effetto.asc())
        .limit(8)
        .all()
    )
    prossimi_followup = (
        FollowUp.query.filter(FollowUp.stato == "aperto")
        .order_by(FollowUp.data_scadenza.asc())
        .limit(8)
        .all()
    )
    ultimi_sinistri = sinistri_aperti.order_by(Claim.data_evento.desc()).limit(6).all()
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
        prossimi_eventi=prossimi_eventi,
        titoli_urgenti=titoli_urgenti,
        prossimi_followup=prossimi_followup,
        ultimi_sinistri=ultimi_sinistri,
        ultime_notifiche=ultime_notifiche,
        opportunita_recenti=opportunita_recenti,
    )


PERIODI_SCADENZARIO = (7, 30, 60, 90, 180, 365)


def _orizzonte() -> tuple[date, int]:
    giorni = parse_int(request.args.get("giorni"), minimo=1, massimo=730) or 90
    return date.today() + timedelta(days=giorni), giorni


@bp.route("/scadenzario")
def scadenzario():
    today = date.today()
    limite, giorni = _orizzonte()

    polizze = (
        Policy.query.filter(
            Policy.stato.in_(STATI_ATTIVI),
            Policy.data_scadenza.isnot(None),
            Policy.data_scadenza <= limite,
        )
        .order_by(Policy.data_scadenza.asc())
        .all()
    )
    titoli = (
        Title.query.filter(Title.stato == "da_incassare", Title.data_effetto <= limite)
        .order_by(Title.data_effetto.asc())
        .all()
    )
    followups = (
        FollowUp.query.filter(
            FollowUp.stato == "aperto", FollowUp.data_scadenza <= limite
        )
        .order_by(FollowUp.data_scadenza.asc())
        .all()
    )
    # Agenda: le altre scadenze future (decorrenze, termini di disdetta e di
    # denuncia, sospensioni della copertura, compliance dei clienti).
    agenda = eventi_agenda(
        today, limite, {"decorrenza", "disdetta", "sospensione", "denuncia", "documento", "adeguatezza"}
    )
    return render_template(
        "scadenzario.html", polizze=polizze, titoli=titoli, followups=followups, giorni=giorni,
        agenda=agenda, periodi=PERIODI_SCADENZARIO, limite=limite,
    )


@bp.route("/scadenzario.ics")
def scadenzario_ics():
    """Esporta le scadenze del periodo in un file da importare in Outlook, Google Calendar…"""
    today = date.today()
    limite, giorni = _orizzonte()
    eventi = eventi_agenda(today, limite)
    audit("export", "scadenzario", None, f"Esportato lo scadenzario in calendario ({len(eventi)} eventi, {giorni} giorni)",
          commit=True)
    contenuto = esporta_ics(eventi, request.host_url, "Scadenze gestionale assicurativo")
    return Response(
        contenuto,
        mimetype="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="scadenzario_{today:%Y%m%d}.ics"'},
    )


@bp.route("/cerca")
def search():
    q = (request.args.get("q") or "").strip()
    clienti, polizze, sinistri = [], [], []
    if q:
        like = f"%{q}%"
        clienti = (
            Client.query.filter(
                db.or_(
                    Client.ragione_sociale.ilike(like),
                    Client.referente.ilike(like),
                    Client.partita_iva.ilike(like),
                    Client.codice_fiscale.ilike(like),
                    Client.citta.ilike(like),
                    Client.settore.ilike(like),
                    Client.professione.ilike(like),
                    Client.datore_lavoro.ilike(like),
                    Client.email.ilike(like),
                    Client.telefono.ilike(like),
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
        sinistri = (
            Claim.query.filter(
                db.or_(
                    Claim.numero.ilike(like),
                    Claim.numero_compagnia.ilike(like),
                    Claim.controparte.ilike(like),
                )
            )
            .order_by(Claim.data_evento.desc())
            .limit(50)
            .all()
        )
    return render_template("search.html", q=q, clienti=clienti, polizze=polizze, sinistri=sinistri)


@bp.route("/statistiche")
def analytics():
    """Cruscotto analitico: portafoglio, incassi, sinistri e pipeline."""
    today = date.today()
    attive_filter = Policy.query.filter(Policy.stato.in_(STATI_ATTIVI))
    polizze_attive = attive_filter.all()

    # Portafoglio per ramo: numero, premi, provvigioni e costo sinistri (S/P).
    per_ramo = {}
    for p in polizze_attive:
        r = per_ramo.setdefault(
            p.ramo, {"ramo": p.ramo, "nome": BRANCH_LABELS.get(p.ramo, p.ramo),
                     "numero": 0, "premi": 0.0, "provvigioni": 0.0, "sinistri": 0.0}
        )
        r["numero"] += 1
        r["premi"] += p.premio_annuo or 0.0
        r["provvigioni"] += p.provvigione_annua or 0.0
    # Rapporto sinistri/premi su un periodo omogeneo (ultimi 12 mesi): costo dei
    # sinistri accaduti nel periodo / premi dei titoli con effetto nel periodo
    # (anche di polizze poi cessate). Così non cresce con l'anzianità del portafoglio.
    inizio_sp = add_months(today, -12)
    premi_competenza = {}
    for t in Title.query.filter(
        Title.stato != "stornato", Title.data_effetto > inizio_sp, Title.data_effetto <= today
    ).all():
        ramo = t.polizza.ramo
        premi_competenza[ramo] = premi_competenza.get(ramo, 0.0) + (t.premio_lordo or 0.0)
    sinistri_periodo = Claim.query.filter(Claim.data_evento > inizio_sp, Claim.data_evento <= today).all()
    costo_per_ramo = {}
    for s in sinistri_periodo:
        if s.polizza:
            costo_per_ramo[s.polizza.ramo] = costo_per_ramo.get(s.polizza.ramo, 0.0) + s.costo
    for ramo, r in per_ramo.items():
        r["sinistri"] = costo_per_ramo.get(ramo, 0.0)
        r["premi_competenza"] = premi_competenza.get(ramo, 0.0)
        r["rapporto_sp"] = (100.0 * r["sinistri"] / r["premi_competenza"]) if r["premi_competenza"] else None
    rami = sorted(per_ramo.values(), key=lambda x: -x["premi"])
    premi_max = max([r["premi"] for r in rami], default=0.0)

    premi_totali, provvigioni_totali = _premi_provvigioni_attive()

    # Portafoglio per compagnia.
    per_compagnia = {}
    for p in polizze_attive:
        c = per_compagnia.setdefault(p.compagnia, {"nome": p.compagnia, "numero": 0, "premi": 0.0})
        c["numero"] += 1
        c["premi"] += p.premio_annuo or 0.0
    compagnie = sorted(per_compagnia.values(), key=lambda x: -x["premi"])
    compagnie_max = max([c["premi"] for c in compagnie], default=0.0)

    # Clienti per tipo e migliori clienti per premi.
    clienti_per_tipo = [
        {"tipo": "Aziende", "n": Client.query.filter_by(tipo="azienda").count()},
        {"tipo": "Professionisti", "n": Client.query.filter_by(tipo="professionista").count()},
        {"tipo": "Dipendenti", "n": Client.query.filter_by(tipo="dipendente").count()},
    ]
    premi_cliente = {}
    for p in polizze_attive:
        premi_cliente[p.cliente] = premi_cliente.get(p.cliente, 0.0) + (p.premio_annuo or 0.0)
    top_clienti = sorted(premi_cliente.items(), key=lambda kv: -kv[1])[:10]

    # Pipeline per fase con valore stimato.
    pipeline = []
    for fase, label in OPPORTUNITY_STAGES:
        opp = Opportunity.query.filter_by(fase=fase).all()
        valore = sum(o.premio_stimato or 0.0 for o in opp)
        pipeline.append({"fase": fase, "label": label, "numero": len(opp), "valore": valore})
    pipeline_max = max([f["numero"] for f in pipeline], default=0)
    chiuse = [f for f in pipeline if f["fase"] in ("vinta", "persa")]
    totale_chiuse = sum(f["numero"] for f in chiuse)
    tasso_conversione = (
        100.0 * next(f["numero"] for f in pipeline if f["fase"] == "vinta") / totale_chiuse
        if totale_chiuse else None
    )

    # Premi in scadenza nei prossimi 12 mesi e incassi degli ultimi 12 mesi.
    mesi = []
    for i in range(12):
        inizio = add_months(today.replace(day=1), i)
        fine = add_months(inizio, 1)
        tot = (
            db.session.query(db.func.coalesce(db.func.sum(Policy.premio_annuo), 0.0))
            .filter(
                Policy.stato.in_(STATI_ATTIVI),
                Policy.data_scadenza >= inizio,
                Policy.data_scadenza < fine,
            )
            .scalar()
        )
        mesi.append({"label": inizio.strftime("%m/%y"), "premi": tot})
    mesi_max = max([m["premi"] for m in mesi], default=0.0)

    incassi = []
    for i in range(11, -1, -1):
        inizio = add_months(today.replace(day=1), -i)
        fine = add_months(inizio, 1)
        tot = (
            db.session.query(db.func.coalesce(db.func.sum(Title.premio_lordo), 0.0))
            .filter(Title.stato == "incassato", Title.data_incasso >= inizio, Title.data_incasso < fine)
            .scalar()
        )
        incassi.append({"label": inizio.strftime("%m/%y"), "importo": tot})
    incassi_max = max([m["importo"] for m in incassi], default=0.0)

    # Sinistri.
    tutti_sinistri = Claim.query.all()
    costo_sinistri = sum(s.costo for s in tutti_sinistri)
    sinistri_per_stato = [
        {"stato": label, "n": sum(1 for s in tutti_sinistri if s.stato == stato)}
        for stato, label in CLAIM_STATUSES
    ]
    per_tipologia = {}
    for s in tutti_sinistri:
        voce = per_tipologia.setdefault(s.tipologia, {"nome": CLAIM_TYPE_LABELS.get(s.tipologia, s.tipologia), "n": 0, "costo": 0.0})
        voce["n"] += 1
        voce["costo"] += s.costo
    sinistri_tipologie = sorted(per_tipologia.values(), key=lambda v: -v["n"])

    return render_template(
        "analytics.html",
        rami=rami, premi_max=premi_max,
        compagnie=compagnie, compagnie_max=compagnie_max,
        premi_totali=premi_totali, provvigioni_totali=provvigioni_totali,
        clienti_per_tipo=clienti_per_tipo, top_clienti=top_clienti,
        pipeline=pipeline, pipeline_max=pipeline_max, tasso_conversione=tasso_conversione,
        mesi=mesi, mesi_max=mesi_max,
        incassi=incassi, incassi_max=incassi_max,
        totale_polizze=len(polizze_attive),
        numero_sinistri=len(tutti_sinistri),
        costo_sinistri=costo_sinistri,
        costo_sinistri_12m=sum(s.costo for s in sinistri_periodo),
        premi_competenza_12m=sum(premi_competenza.values()),
        rapporto_sp=(
            100.0 * sum(s.costo for s in sinistri_periodo) / sum(premi_competenza.values())
            if sum(premi_competenza.values()) else None
        ),
        sinistri_senza_polizza_12m=sum(s.costo for s in sinistri_periodo if not s.polizza),
        sinistri_per_stato=sinistri_per_stato,
        sinistri_tipologie=sinistri_tipologie,
    )

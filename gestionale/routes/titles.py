"""Titoli e incassi: portafoglio titoli, incasso, storno, foglio cassa ed
estratto conto per compagnia (rimesse)."""
from collections import OrderedDict
from datetime import date, timedelta

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from ..export import csv_response
from ..models import (
    PAYMENT_METHODS,
    TITLE_TYPES,
    Client,
    Policy,
    Title,
    db,
)
from ..notifications import segna_lette
from ..security import audit, safe_next
from ..utils import formatta_euro, paginate, parse_date, parse_float

bp = Blueprint("titles", __name__, url_prefix="/titoli")

VISTE = [
    ("da_incassare", "Da incassare"),
    ("arretrati", "Arretrati"),
    ("incassati", "Incassati"),
    ("stornati", "Stornati"),
    ("tutti", "Tutti"),
]


def _inizio_mese(giorno: date) -> date:
    return giorno.replace(day=1)


def _fine_mese(giorno: date) -> date:
    prossimo = (giorno.replace(day=28) + timedelta(days=4)).replace(day=1)
    return prossimo - timedelta(days=1)


def _periodo(default_dal: date, default_al: date) -> tuple[date, date]:
    dal = parse_date(request.args.get("dal")) or default_dal
    al = parse_date(request.args.get("al")) or default_al
    if al < dal:
        dal, al = al, dal
    return dal, al


def _query_portafoglio(vista: str):
    oggi = date.today()
    query = Title.query.join(Policy, Title.policy_id == Policy.id).join(
        Client, Title.client_id == Client.id
    )
    if vista == "da_incassare":
        query = query.filter(Title.stato == "da_incassare")
    elif vista == "arretrati":
        query = query.filter(Title.stato == "da_incassare", Title.data_effetto < oggi)
    elif vista == "incassati":
        query = query.filter(Title.stato == "incassato")
    elif vista == "stornati":
        query = query.filter(Title.stato == "stornato")

    compagnia = request.args.get("compagnia", "")
    if compagnia:
        query = query.filter(Policy.compagnia == compagnia)
    dal = parse_date(request.args.get("dal"))
    al = parse_date(request.args.get("al"))
    campo_data = Title.data_incasso if vista == "incassati" else Title.data_effetto
    if dal:
        query = query.filter(campo_data >= dal)
    if al:
        query = query.filter(campo_data <= al)
    q = (request.args.get("q") or "").strip()
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(Client.ragione_sociale.ilike(like), Policy.numero_polizza.ilike(like))
        )
    if vista == "incassati":
        return query.order_by(Title.data_incasso.desc(), Title.id.desc())
    return query.order_by(Title.data_effetto.asc(), Title.id.asc())


def _compagnie():
    return [c for (c,) in db.session.query(Policy.compagnia).distinct().order_by(Policy.compagnia)]


@bp.route("/")
def portfolio():
    vista = request.args.get("vista", "da_incassare")
    if vista not in dict(VISTE):
        vista = "da_incassare"
    query = _query_portafoglio(vista)
    totali = query.with_entities(
        db.func.count(Title.id),
        db.func.coalesce(db.func.sum(Title.premio_lordo), 0.0),
        db.func.coalesce(db.func.sum(Title.provvigione), 0.0),
    ).order_by(None).one()
    pagination = paginate(query)
    oggi = date.today()
    arretrati = (
        db.session.query(db.func.count(Title.id), db.func.coalesce(db.func.sum(Title.premio_lordo), 0.0))
        .filter(Title.stato == "da_incassare", Title.data_effetto < oggi)
        .one()
    )
    return render_template(
        "titles/list.html",
        vista=vista,
        viste=VISTE,
        pagination=pagination,
        titoli=pagination.items,
        totali={"numero": totali[0], "premi": totali[1], "provvigioni": totali[2]},
        arretrati={"numero": arretrati[0], "premi": arretrati[1]},
        compagnie=_compagnie(),
        filtri=request.args,
        payment_methods=PAYMENT_METHODS,
    )


@bp.route("/esporta.csv")
def export_portfolio():
    vista = request.args.get("vista", "da_incassare")
    if vista not in dict(VISTE):
        vista = "da_incassare"
    titoli = _query_portafoglio(vista).limit(50000).all()
    audit("export", "titolo", None, f"Esportati {len(titoli)} titoli (vista {vista})", commit=True)
    return csv_response(
        f"titoli_{vista}",
        ["Cliente", "Polizza", "Compagnia", "Ramo", "Tipo", "Rata", "Effetto", "Fine copertura",
         "Premio lordo", "Provvigione", "Netto compagnia", "Stato", "Data incasso",
         "Mezzo di pagamento", "Riferimento", "Data rimessa"],
        [
            (t.cliente.ragione_sociale, t.polizza.numero_polizza, t.polizza.compagnia,
             t.polizza.ramo_label, t.tipo_label, t.rata_label, t.data_effetto, t.data_fine_copertura,
             t.premio_lordo, t.provvigione, t.netto, t.stato_label, t.data_incasso,
             t.mezzo_label if t.mezzo_pagamento else None, t.riferimento_pagamento, t.data_rimessa)
            for t in titoli
        ],
    )


def _torna(titolo: Title):
    return redirect(
        safe_next(request.form.get("next"))
        or url_for("policies.detail", policy_id=titolo.policy_id) + "#titoli"
    )


@bp.route("/<int:title_id>/incassa", methods=["POST"])
def collect(title_id):
    titolo = db.get_or_404(Title, title_id)
    if titolo.stato != "da_incassare":
        flash("Il titolo non è da incassare.", "warning")
        return _torna(titolo)
    data_incasso = parse_date(request.form.get("data_incasso")) or date.today()
    if data_incasso > date.today():
        flash("La data di incasso non può essere futura.", "danger")
        return _torna(titolo)
    mezzo = request.form.get("mezzo_pagamento")
    importo = parse_float(request.form.get("importo"))
    if importo is not None and importo > 0 and abs(importo - (titolo.premio_lordo or 0)) > 0.005:
        # Incasso di un importo diverso (es. regolazione): ricalcola la provvigione in proporzione.
        if titolo.provvigione and titolo.premio_lordo:
            titolo.provvigione = round(titolo.provvigione * importo / titolo.premio_lordo, 2)
        titolo.premio_lordo = importo
    titolo.stato = "incassato"
    titolo.data_incasso = data_incasso
    titolo.mezzo_pagamento = mezzo if mezzo in dict(PAYMENT_METHODS) else "altro"
    titolo.riferimento_pagamento = (request.form.get("riferimento") or "").strip() or None
    titolo.incassato_da = g.user.username
    segna_lette(f"titolo:{titolo.id}:")
    audit("incasso", "titolo", titolo.id,
          f"Incassato titolo polizza {titolo.polizza.numero_polizza} ({titolo.cliente.ragione_sociale}): "
          f"€ {titolo.premio_lordo:.2f} con {titolo.mezzo_label}")
    db.session.commit()
    flash(f"Incasso registrato: {formatta_euro(titolo.premio_lordo)} ({titolo.mezzo_label}).", "success")
    return _torna(titolo)


@bp.route("/<int:title_id>/annulla-incasso", methods=["POST"])
def undo_collect(title_id):
    titolo = db.get_or_404(Title, title_id)
    if titolo.stato != "incassato":
        abort(400)
    if titolo.data_rimessa:
        flash("Il titolo è già stato rimesso alla compagnia: l'incasso non può essere annullato.", "danger")
        return _torna(titolo)
    audit("modifica", "titolo", titolo.id,
          f"Annullato incasso titolo polizza {titolo.polizza.numero_polizza} del {titolo.data_incasso:%d/%m/%Y}")
    titolo.stato = "da_incassare"
    titolo.data_incasso = None
    titolo.mezzo_pagamento = None
    titolo.riferimento_pagamento = None
    titolo.incassato_da = None
    db.session.commit()
    flash("Incasso annullato: il titolo è tornato da incassare.", "info")
    return _torna(titolo)


@bp.route("/<int:title_id>/storna", methods=["POST"])
def cancel(title_id):
    titolo = db.get_or_404(Title, title_id)
    if titolo.stato != "da_incassare":
        flash("Si possono stornare solo i titoli non ancora incassati.", "warning")
        return _torna(titolo)
    titolo.stato = "stornato"
    segna_lette(f"titolo:{titolo.id}:")
    motivo = (request.form.get("motivo") or "").strip()
    if motivo:
        titolo.note = ((titolo.note + "\n") if titolo.note else "") + f"Storno: {motivo}"
    audit("storno", "titolo", titolo.id,
          f"Stornato titolo polizza {titolo.polizza.numero_polizza} del {titolo.data_effetto:%d/%m/%Y}"
          + (f" — {motivo}" if motivo else ""))
    db.session.commit()
    flash("Titolo stornato.", "info")
    return _torna(titolo)


@bp.route("/<int:title_id>/modifica", methods=["GET", "POST"])
def edit(title_id):
    titolo = db.get_or_404(Title, title_id)
    if request.method == "POST":
        effetto = parse_date(request.form.get("data_effetto"))
        premio = parse_float(request.form.get("premio_lordo"))
        if not effetto or premio is None:
            flash("Data effetto e premio lordo sono obbligatori.", "danger")
        else:
            titolo.data_effetto = effetto
            titolo.data_fine_copertura = parse_date(request.form.get("data_fine_copertura"))
            titolo.premio_lordo = premio
            titolo.provvigione = parse_float(request.form.get("provvigione"))
            tipo = request.form.get("tipo")
            if tipo in dict(TITLE_TYPES):
                titolo.tipo = tipo
            titolo.note = (request.form.get("note") or "").strip() or None
            audit("modifica", "titolo", titolo.id,
                  f"Modificato titolo polizza {titolo.polizza.numero_polizza}: effetto {effetto:%d/%m/%Y}, € {premio:.2f}")
            db.session.commit()
            flash("Titolo aggiornato.", "success")
            return redirect(url_for("policies.detail", policy_id=titolo.policy_id) + "#titoli")
    return render_template("titles/form.html", titolo=titolo, title_types=TITLE_TYPES)


@bp.route("/nuovo/<int:policy_id>", methods=["POST"])
def new_title(policy_id):
    """Titolo manuale (es. appendice di regolazione premio)."""
    policy = db.get_or_404(Policy, policy_id)
    effetto = parse_date(request.form.get("data_effetto"))
    premio = parse_float(request.form.get("premio_lordo"))
    if not effetto or premio is None:
        flash("Data effetto e premio lordo sono obbligatori.", "danger")
        return redirect(url_for("policies.detail", policy_id=policy.id) + "#titoli")
    tipo = request.form.get("tipo")
    provvigione = parse_float(request.form.get("provvigione"))
    if provvigione is None and policy.provvigione_perc:
        provvigione = round(premio * policy.provvigione_perc / 100.0, 2)
    titolo = Title(
        policy_id=policy.id,
        client_id=policy.client_id,
        tipo=tipo if tipo in dict(TITLE_TYPES) else "appendice",
        data_effetto=effetto,
        data_fine_copertura=parse_date(request.form.get("data_fine_copertura")),
        premio_lordo=premio,
        provvigione=provvigione,
        note=(request.form.get("note") or "").strip() or None,
    )
    db.session.add(titolo)
    db.session.flush()
    audit("crea", "titolo", titolo.id,
          f"Nuovo titolo ({titolo.tipo_label}) polizza {policy.numero_polizza}: € {premio:.2f}")
    db.session.commit()
    flash("Titolo aggiunto.", "success")
    return redirect(url_for("policies.detail", policy_id=policy.id) + "#titoli")


@bp.route("/<int:title_id>/elimina", methods=["POST"])
def delete(title_id):
    titolo = db.get_or_404(Title, title_id)
    if titolo.stato == "incassato":
        flash("Un titolo incassato non può essere eliminato: annulla prima l'incasso.", "danger")
        return _torna(titolo)
    policy_id = titolo.policy_id
    audit("elimina", "titolo", titolo.id,
          f"Eliminato titolo polizza {titolo.polizza.numero_polizza} del {titolo.data_effetto:%d/%m/%Y}")
    db.session.delete(titolo)
    db.session.commit()
    flash("Titolo eliminato.", "success")
    return redirect(url_for("policies.detail", policy_id=policy_id) + "#titoli")


# ----------------------------------------------------------------------
# Foglio cassa (prima nota incassi)
# ----------------------------------------------------------------------
def _incassi_periodo(dal: date, al: date, compagnia: str = ""):
    query = (
        Title.query.join(Policy, Title.policy_id == Policy.id)
        .filter(Title.stato == "incassato", Title.data_incasso >= dal, Title.data_incasso <= al)
    )
    if compagnia:
        query = query.filter(Policy.compagnia == compagnia)
    return query.order_by(Title.data_incasso.asc(), Title.id.asc()).all()


@bp.route("/foglio-cassa")
def cash_sheet():
    oggi = date.today()
    dal, al = _periodo(_inizio_mese(oggi), oggi)
    compagnia = request.args.get("compagnia", "")
    incassi = _incassi_periodo(dal, al, compagnia)
    per_mezzo = OrderedDict((m, {"label": label, "numero": 0, "importo": 0.0}) for m, label in PAYMENT_METHODS)
    for t in incassi:
        voce = per_mezzo.setdefault(t.mezzo_pagamento or "altro", {"label": t.mezzo_label, "numero": 0, "importo": 0.0})
        voce["numero"] += 1
        voce["importo"] += t.premio_lordo or 0.0
    per_giorno = OrderedDict()
    for t in incassi:
        per_giorno.setdefault(t.data_incasso, []).append(t)
    return render_template(
        "titles/cash_sheet.html",
        dal=dal, al=al, compagnia=compagnia, compagnie=_compagnie(),
        incassi=incassi, per_giorno=per_giorno,
        per_mezzo=[v for v in per_mezzo.values() if v["numero"]],
        totale=sum(t.premio_lordo or 0.0 for t in incassi),
        provvigioni=sum(t.provvigione or 0.0 for t in incassi),
    )


@bp.route("/foglio-cassa.csv")
def cash_sheet_csv():
    oggi = date.today()
    dal, al = _periodo(_inizio_mese(oggi), oggi)
    incassi = _incassi_periodo(dal, al, request.args.get("compagnia", ""))
    audit("export", "titolo", None, f"Esportato foglio cassa {dal:%d/%m/%Y}–{al:%d/%m/%Y}", commit=True)
    return csv_response(
        f"foglio_cassa_{dal:%Y%m%d}_{al:%Y%m%d}",
        ["Data incasso", "Cliente", "Polizza", "Compagnia", "Tipo", "Effetto", "Premio lordo",
         "Provvigione", "Netto compagnia", "Mezzo di pagamento", "Riferimento", "Operatore"],
        [
            (t.data_incasso, t.cliente.ragione_sociale, t.polizza.numero_polizza, t.polizza.compagnia,
             t.tipo_label, t.data_effetto, t.premio_lordo, t.provvigione, t.netto, t.mezzo_label,
             t.riferimento_pagamento, t.incassato_da)
            for t in incassi
        ],
    )


# ----------------------------------------------------------------------
# Estratto conto per compagnia e rimesse
# ----------------------------------------------------------------------
@bp.route("/estratto-conto")
def statement():
    oggi = date.today()
    inizio_mese_scorso = _inizio_mese(_inizio_mese(oggi) - timedelta(days=1))
    dal, al = _periodo(inizio_mese_scorso, _fine_mese(inizio_mese_scorso))
    compagnie = OrderedDict()
    for t in _incassi_periodo(dal, al):
        nome = t.polizza.compagnia
        voce = compagnie.setdefault(
            nome,
            {"compagnia": nome, "numero": 0, "premi": 0.0, "provvigioni": 0.0, "netto": 0.0,
             "rimesso": 0.0, "da_rimettere": 0.0, "titoli_da_rimettere": 0},
        )
        voce["numero"] += 1
        voce["premi"] += t.premio_lordo or 0.0
        voce["provvigioni"] += t.provvigione or 0.0
        voce["netto"] += t.netto
        if t.data_rimessa:
            voce["rimesso"] += t.netto
        else:
            voce["da_rimettere"] += t.netto
            voce["titoli_da_rimettere"] += 1
    righe = sorted(compagnie.values(), key=lambda v: v["compagnia"].lower())
    dettaglio = request.args.get("compagnia", "")
    titoli_dettaglio = _incassi_periodo(dal, al, dettaglio) if dettaglio else []
    return render_template(
        "titles/statement.html",
        dal=dal, al=al, righe=righe, dettaglio=dettaglio, titoli_dettaglio=titoli_dettaglio,
        totali={k: sum(r[k] for r in righe) for k in ("numero", "premi", "provvigioni", "netto", "rimesso", "da_rimettere")},
    )


@bp.route("/estratto-conto/rimessa", methods=["POST"])
def register_remittance():
    dal = parse_date(request.form.get("dal"))
    al = parse_date(request.form.get("al"))
    compagnia = request.form.get("compagnia", "")
    data_rimessa = parse_date(request.form.get("data_rimessa")) or date.today()
    if not dal or not al or not compagnia:
        abort(400)
    titoli = [t for t in _incassi_periodo(dal, al, compagnia) if not t.data_rimessa]
    if not titoli:
        flash("Nessun titolo da rimettere per la compagnia e il periodo indicati.", "info")
    else:
        netto = sum(t.netto for t in titoli)
        for t in titoli:
            t.data_rimessa = data_rimessa
        audit("rimessa", "titolo", None,
              f"Rimessa a {compagnia} del {data_rimessa:%d/%m/%Y}: {len(titoli)} titoli, netto € {netto:.2f} "
              f"(incassi {dal:%d/%m/%Y}–{al:%d/%m/%Y})")
        db.session.commit()
        flash(f"Rimessa registrata per {compagnia}: {len(titoli)} titoli.", "success")
    return redirect(url_for("titles.statement", dal=dal.isoformat(), al=al.isoformat(), compagnia=compagnia))

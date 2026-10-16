"""Titoli e incassi: portafoglio titoli, incasso, storno, foglio cassa,
estratto conto per compagnia (rimesse) e previsione degli incassi futuri."""
from collections import OrderedDict
from datetime import date, timedelta

from flask import Blueprint, flash, g, redirect, render_template, request, url_for

from ..export import csv_response
from ..models import (
    PAYMENT_METHODS,
    TITLE_TYPES,
    Client,
    Policy,
    Title,
    db,
)
from ..notifications import elimina_notifiche, segna_lette
from ..security import admin_required, audit, safe_next
from ..titoli import add_months, annualita_piena, date_rate, periodi_polizza, premio_periodo, titoli_periodo
from ..utils import (
    arrotonda,
    fine_mese,
    formatta_euro,
    inizio_mese,
    leggi_data,
    leggi_importo,
    paginate,
    parse_date,
    parse_int,
    periodo_da_richiesta,
    ripartisci,
)

bp = Blueprint("titles", __name__, url_prefix="/titoli")

VISTE = [
    ("da_incassare", "Da incassare"),
    ("arretrati", "Arretrati"),
    ("incassati", "Incassati"),
    ("stornati", "Stornati"),
    ("tutti", "Tutti"),
]


def _query_portafoglio(vista: str):
    oggi = date.today()
    query = Title.query.join(Policy, Title.policy_id == Policy.id).join(
        Client, Title.client_id == Client.id
    )
    if vista == "da_incassare":
        query = query.filter(Title.stato == "da_incassare")
    elif vista == "arretrati":
        query = query.filter(
            Title.stato == "da_incassare", Title.data_effetto < oggi, Title.premio_lordo > 0
        )
    elif vista == "incassati":
        query = query.filter(Title.stato == "incassato")
    elif vista == "stornati":
        query = query.filter(Title.stato == "stornato")

    compagnia = request.args.get("compagnia", "")
    if compagnia:
        query = query.filter(Policy.compagnia == compagnia)
    dal = parse_date(request.args.get("dal"))
    al = parse_date(request.args.get("al"))
    if dal and al and al < dal:
        dal, al = al, dal
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


def _vista():
    vista = request.args.get("vista", "da_incassare")
    return vista if vista in dict(VISTE) else "da_incassare"


@bp.route("/")
def portfolio():
    vista = _vista()
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
        .filter(Title.stato == "da_incassare", Title.data_effetto < oggi, Title.premio_lordo > 0)
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
    vista = _vista()
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
        flash("Il titolo non è da incassare (forse è già stato incassato da un collega).", "warning")
        return _torna(titolo)
    errori: list[str] = []
    oggi = date.today()
    data_incasso = leggi_data(
        request.form, "data_incasso", "Data di incasso", errori, massimo=oggi,
        msg_massimo="La data di incasso non può essere futura.",
    ) or (oggi if not errori else None)
    importo = leggi_importo(request.form, "importo", "Importo", errori)
    if importo is not None and abs(importo - (titolo.premio_lordo or 0)) > 0.005:
        errori.append(
            f"L'importo incassato ({formatta_euro(importo)}) è diverso dal premio del titolo "
            f"({formatta_euro(titolo.premio_lordo)}): gli incassi parziali non sono ammessi. "
            "Correggi prima il titolo oppure registra un'appendice per la differenza."
        )
    mezzo = request.form.get("mezzo_pagamento")
    if mezzo not in dict(PAYMENT_METHODS):
        errori.append("Seleziona il mezzo di pagamento.")
    if errori:
        for e in errori:
            flash(e, "danger")
        return _torna(titolo)
    titolo.stato = "incassato"
    titolo.data_incasso = data_incasso
    titolo.mezzo_pagamento = mezzo
    titolo.riferimento_pagamento = (request.form.get("riferimento") or "").strip()[:120] or None
    titolo.incassato_da = g.user.username
    segna_lette(f"titolo:{titolo.id}:")
    segna_lette(f"decorrenza:{titolo.policy_id}:")
    audit("incasso", "titolo", titolo.id,
          f"Incassato titolo polizza {titolo.polizza.numero_polizza} ({titolo.cliente.ragione_sociale}) "
          f"del {titolo.data_effetto:%d/%m/%Y}: {formatta_euro(titolo.premio_lordo)} con {titolo.mezzo_label}"
          f" in data {data_incasso:%d/%m/%Y}")
    db.session.commit()
    flash(f"Incasso registrato: {formatta_euro(titolo.premio_lordo)} ({titolo.mezzo_label}).", "success")
    return _torna(titolo)


@bp.route("/<int:title_id>/annulla-incasso", methods=["POST"])
def undo_collect(title_id):
    """Annulla un incasso registrato per errore.

    Gli operatori possono annullare solo gli incassi del mese in corso (il foglio
    cassa dei mesi precedenti è già chiuso); gli amministratori anche quelli
    precedenti. Gli incassi già rimessi alla compagnia non si annullano.
    """
    titolo = db.get_or_404(Title, title_id)
    if titolo.stato != "incassato":
        flash("Il titolo non risulta incassato.", "warning")
        return _torna(titolo)
    if titolo.data_rimessa:
        flash("Il titolo è già stato rimesso alla compagnia: annulla prima la rimessa.", "danger")
        return _torna(titolo)
    if titolo.data_incasso and titolo.data_incasso < inizio_mese(date.today()) and not g.user.is_admin:
        flash(
            "L'incasso appartiene a un mese già chiuso nel foglio cassa: solo un amministratore può annullarlo.",
            "danger",
        )
        return _torna(titolo)
    audit("modifica", "titolo", titolo.id,
          f"Annullato incasso titolo polizza {titolo.polizza.numero_polizza} del "
          f"{titolo.data_incasso:%d/%m/%Y} ({formatta_euro(titolo.premio_lordo)}, {titolo.mezzo_label})")
    titolo.stato = "da_incassare"
    titolo.data_incasso = None
    titolo.mezzo_pagamento = None
    titolo.riferimento_pagamento = None
    titolo.incassato_da = None
    elimina_notifiche(f"titolo:{titolo.id}:")
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
    motivo = (request.form.get("motivo") or "").strip()[:200]
    if motivo:
        titolo.note = ((titolo.note + "\n") if titolo.note else "") + f"Storno: {motivo}"
    segna_lette(f"titolo:{titolo.id}:")
    audit("storno", "titolo", titolo.id,
          f"Stornato titolo polizza {titolo.polizza.numero_polizza} del {titolo.data_effetto:%d/%m/%Y}"
          + (f" — {motivo}" if motivo else ""))
    db.session.commit()
    flash("Titolo stornato.", "info")
    return _torna(titolo)


def _leggi_titolo(form, policy: Policy, errori: list[str]) -> dict:
    """Valida i campi di un titolo (nuovo o modificato) e restituisce i valori."""
    tipo = form.get("tipo") if form.get("tipo") in dict(TITLE_TYPES) else None
    effetto = leggi_data(form, "data_effetto", "Data effetto", errori, obbligatoria=True)
    fine = leggi_data(form, "data_fine_copertura", "Copertura fino al", errori)
    if effetto and fine and fine <= effetto:
        errori.append("La fine della copertura deve essere successiva alla data effetto.")
    premio = leggi_importo(form, "premio_lordo", "Premio lordo", errori, obbligatorio=True)
    if premio is not None and premio <= 0 and tipo != "appendice":
        errori.append("Il premio deve essere positivo (importi negativi solo per le appendici di rimborso).")
    provvigione = leggi_importo(form, "provvigione", "Provvigione", errori)
    if provvigione is not None and premio is not None and abs(provvigione) > abs(premio):
        errori.append("La provvigione non può superare il premio.")
    return {"tipo": tipo, "effetto": effetto, "fine": fine, "premio": premio, "provvigione": provvigione,
            "note": (form.get("note") or "").strip() or None}


@bp.route("/<int:title_id>/modifica", methods=["GET", "POST"])
def edit(title_id):
    titolo = db.get_or_404(Title, title_id)
    if not titolo.modificabile:
        flash(
            "Si possono modificare solo i titoli da incassare: per un titolo incassato annulla prima l'incasso.",
            "warning",
        )
        return redirect(url_for("policies.detail", policy_id=titolo.policy_id) + "#titoli")
    valori = None
    if request.method == "POST":
        errori: list[str] = []
        valori = _leggi_titolo(request.form, titolo.polizza, errori)
        if not errori:
            vecchia_data = titolo.data_effetto
            titolo.data_effetto = valori["effetto"]
            titolo.data_fine_copertura = valori["fine"]
            titolo.premio_lordo = valori["premio"]
            titolo.provvigione = valori["provvigione"]
            if valori["tipo"]:
                titolo.tipo = valori["tipo"]
            titolo.note = valori["note"]
            if vecchia_data != titolo.data_effetto:
                elimina_notifiche(f"titolo:{titolo.id}:")
            audit("modifica", "titolo", titolo.id,
                  f"Modificato titolo polizza {titolo.polizza.numero_polizza}: effetto "
                  f"{titolo.data_effetto:%d/%m/%Y}, {formatta_euro(titolo.premio_lordo)}")
            db.session.commit()
            flash("Titolo aggiornato.", "success")
            return redirect(url_for("policies.detail", policy_id=titolo.policy_id) + "#titoli")
        for e in errori:
            flash(e, "danger")
        return render_template("titles/form.html", titolo=titolo, valori=request.form,
                               title_types=TITLE_TYPES), 400
    return render_template("titles/form.html", titolo=titolo, valori=None, title_types=TITLE_TYPES)


@bp.route("/nuovo/<int:policy_id>", methods=["POST"])
def new_title(policy_id):
    """Titolo manuale (es. appendice di regolazione premio o di rimborso)."""
    policy = db.get_or_404(Policy, policy_id)
    errori: list[str] = []
    valori = _leggi_titolo(request.form, policy, errori)
    if errori:
        for e in errori:
            flash(e, "danger")
        return redirect(url_for("policies.detail", policy_id=policy.id) + "#titoli")
    provvigione = valori["provvigione"]
    if provvigione is None and policy.provvigione_perc:
        provvigione = arrotonda(valori["premio"] * policy.provvigione_perc / 100.0)
    titolo = Title(
        policy_id=policy.id,
        client_id=policy.client_id,
        tipo=valori["tipo"] or "appendice",
        data_effetto=valori["effetto"],
        data_fine_copertura=valori["fine"],
        premio_lordo=valori["premio"],
        provvigione=provvigione,
        note=valori["note"],
    )
    db.session.add(titolo)
    db.session.flush()
    audit("crea", "titolo", titolo.id,
          f"Nuovo titolo ({titolo.tipo_label}) polizza {policy.numero_polizza}: {formatta_euro(titolo.premio_lordo)}")
    db.session.commit()
    flash("Titolo aggiunto.", "success")
    if policy.data_decorrenza and titolo.data_effetto < policy.data_decorrenza:
        flash("Attenzione: la data effetto è precedente alla decorrenza della polizza.", "warning")
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
    elimina_notifiche(f"titolo:{titolo.id}:")
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
    dal, al = periodo_da_richiesta(inizio_mese(oggi), oggi)
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
    dal, al = periodo_da_richiesta(inizio_mese(oggi), oggi)
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
def _da_rimettere(compagnia: str, al: date):
    """Titoli incassati fino ad ``al`` e non ancora rimessi (anche dei periodi precedenti)."""
    return (
        Title.query.join(Policy, Title.policy_id == Policy.id)
        .filter(
            Policy.compagnia == compagnia,
            Title.stato == "incassato",
            Title.data_rimessa.is_(None),
            Title.data_incasso <= al,
        )
        .order_by(Title.data_incasso.asc(), Title.id.asc())
        .all()
    )


@bp.route("/estratto-conto")
def statement():
    oggi = date.today()
    inizio_mese_scorso = inizio_mese(inizio_mese(oggi) - timedelta(days=1))
    dal, al = periodo_da_richiesta(inizio_mese_scorso, fine_mese(inizio_mese_scorso))
    compagnie = OrderedDict()

    def voce(nome):
        return compagnie.setdefault(
            nome,
            {"compagnia": nome, "numero": 0, "premi": 0.0, "provvigioni": 0.0, "netto": 0.0,
             "rimesso": 0.0, "da_rimettere": 0.0, "arretrato_precedente": 0.0, "ids": []},
        )

    for t in _incassi_periodo(dal, al):
        v = voce(t.polizza.compagnia)
        v["numero"] += 1
        v["premi"] += t.premio_lordo or 0.0
        v["provvigioni"] += t.provvigione or 0.0
        v["netto"] += t.netto
        if t.data_rimessa:
            v["rimesso"] += t.netto
    # Saldo da rimettere: incassi del periodo e dei periodi precedenti non ancora rimessi.
    precedenti = (
        Title.query.join(Policy, Title.policy_id == Policy.id)
        .filter(Title.stato == "incassato", Title.data_rimessa.is_(None), Title.data_incasso <= al)
        .all()
    )
    for t in precedenti:
        v = voce(t.polizza.compagnia)
        v["da_rimettere"] += t.netto
        v["ids"].append(t.id)
        if t.data_incasso < dal:
            v["arretrato_precedente"] += t.netto
    righe = sorted(compagnie.values(), key=lambda v: v["compagnia"].lower())
    dettaglio = request.args.get("compagnia", "")
    titoli_dettaglio = _incassi_periodo(dal, al, dettaglio) if dettaglio else []
    return render_template(
        "titles/statement.html",
        dal=dal, al=al, righe=righe, dettaglio=dettaglio, titoli_dettaglio=titoli_dettaglio,
        totali={k: sum(r[k] for r in righe) for k in
                ("numero", "premi", "provvigioni", "netto", "rimesso", "da_rimettere", "arretrato_precedente")},
        rimesse_recenti=_rimesse_recenti(),
    )


def _rimesse_recenti(limite: int = 10):
    """Ultime rimesse registrate (compagnia + data), per poterle annullare."""
    righe = (
        db.session.query(
            Policy.compagnia, Title.data_rimessa,
            db.func.count(Title.id), db.func.coalesce(db.func.sum(Title.premio_lordo - db.func.coalesce(Title.provvigione, 0)), 0.0),
        )
        .join(Policy, Title.policy_id == Policy.id)
        .filter(Title.data_rimessa.isnot(None))
        .group_by(Policy.compagnia, Title.data_rimessa)
        .order_by(Title.data_rimessa.desc())
        .limit(limite)
        .all()
    )
    return [{"compagnia": c, "data": d, "numero": n, "netto": netto} for c, d, n, netto in righe]


@bp.route("/estratto-conto/rimessa", methods=["POST"])
def register_remittance():
    """Registra la rimessa dei soli titoli mostrati e confermati nell'estratto conto."""
    compagnia = request.form.get("compagnia", "")
    dal = parse_date(request.form.get("dal"))
    al = parse_date(request.form.get("al"))
    ids = [i for i in (parse_int(x, minimo=1) for x in request.form.getlist("ids")) if i]
    torna = redirect(url_for(
        "titles.statement",
        **({"dal": dal.isoformat(), "al": al.isoformat()} if dal and al else {}),
    ))
    if not compagnia or not ids:
        flash("Nessun titolo da rimettere per la compagnia indicata.", "info")
        return torna
    titoli = (
        Title.query.join(Policy, Title.policy_id == Policy.id)
        .filter(
            Title.id.in_(ids), Policy.compagnia == compagnia,
            Title.stato == "incassato", Title.data_rimessa.is_(None),
        )
        .all()
    )
    if len(titoli) != len(set(ids)):
        flash("L'estratto conto è cambiato nel frattempo (incassi annullati o già rimessi): ricarica la pagina e verifica l'importo.", "warning")
        return torna
    errori: list[str] = []
    ultimo_incasso = max(t.data_incasso for t in titoli)
    data_rimessa = leggi_data(
        request.form, "data_rimessa", "Data della rimessa", errori, obbligatoria=True,
        minimo=ultimo_incasso, massimo=date.today(),
        msg_minimo=f"La rimessa non può precedere l'ultimo incasso ({ultimo_incasso:%d/%m/%Y}).",
        msg_massimo="La data della rimessa non può essere futura.",
    )
    if errori:
        for e in errori:
            flash(e, "danger")
        return torna
    netto = sum(t.netto for t in titoli)
    for t in titoli:
        t.data_rimessa = data_rimessa
    audit("rimessa", "titolo", None,
          f"Rimessa a {compagnia} del {data_rimessa:%d/%m/%Y}: {len(titoli)} titoli, netto {formatta_euro(netto)}")
    db.session.commit()
    flash(f"Rimessa registrata per {compagnia}: {len(titoli)} titoli, netto {formatta_euro(netto)}.", "success")
    return torna


@bp.route("/estratto-conto/annulla-rimessa", methods=["POST"])
@admin_required
def undo_remittance():
    """Annulla una rimessa registrata per errore (solo amministratori)."""
    compagnia = request.form.get("compagnia", "")
    data_rimessa = parse_date(request.form.get("data_rimessa"))
    if not compagnia or not data_rimessa:
        flash("Rimessa non indicata.", "warning")
        return redirect(url_for("titles.statement"))
    titoli = (
        Title.query.join(Policy, Title.policy_id == Policy.id)
        .filter(Policy.compagnia == compagnia, Title.data_rimessa == data_rimessa)
        .all()
    )
    for t in titoli:
        t.data_rimessa = None
    if titoli:
        audit("rimessa", "titolo", None,
              f"Annullata la rimessa a {compagnia} del {data_rimessa:%d/%m/%Y} ({len(titoli)} titoli)")
        db.session.commit()
        flash(f"Rimessa a {compagnia} del {data_rimessa:%d/%m/%Y} annullata ({len(titoli)} titoli).", "info")
    else:
        flash("Nessuna rimessa trovata con questi dati.", "warning")
    return redirect(url_for("titles.statement"))


# ----------------------------------------------------------------------
# Previsione degli incassi futuri
# ----------------------------------------------------------------------
MESI_PREVISIONE = (6, 12, 18, 24)


def calcola_previsione(mesi: int = 12, compagnia: str = "", oggi: date | None = None) -> dict:
    """Incassi attesi per mese: rate già emesse da incassare e quietanze stimate.

    - «Emesse»: titoli da incassare con effetto nel mese (gli arretrati sono a parte).
    - «Stimate»: rate delle annualità future non ancora emesse, per le polizze
      attive non disdette (rinnovi e anniversari delle poliennali), calcolate dal
      premio annuo e dal frazionamento attuali.
    """
    oggi = oggi or date.today()
    primo = inizio_mese(oggi)
    mesi = mesi if mesi in MESI_PREVISIONE else 12
    fine_orizzonte = add_months(primo, mesi)
    colonne = []
    indice = {}
    for i in range(mesi):
        inizio = add_months(primo, i)
        voce = {"mese": inizio, "label": inizio.strftime("%m/%Y"),
                "emessi": 0.0, "stimati": 0.0, "provvigioni": 0.0, "numero_emessi": 0, "numero_stimati": 0}
        colonne.append(voce)
        indice[(inizio.year, inizio.month)] = voce

    query = Title.query.join(Policy, Title.policy_id == Policy.id).filter(
        Title.stato == "da_incassare", Title.premio_lordo > 0,
        Title.data_effetto >= oggi, Title.data_effetto < fine_orizzonte,
    )
    if compagnia:
        query = query.filter(Policy.compagnia == compagnia)
    for t in query.all():
        voce = indice.get((t.data_effetto.year, t.data_effetto.month))
        if voce:
            voce["emessi"] += t.premio_lordo
            voce["provvigioni"] += t.provvigione or 0.0
            voce["numero_emessi"] += 1

    polizze = Policy.query.filter(
        Policy.stato.in_(["attiva", "in_rinnovo"]), Policy.premio_annuo > 0,
        Policy.data_disdetta.is_(None),
    )
    if compagnia:
        polizze = polizze.filter(Policy.compagnia == compagnia)
    for policy in polizze.all():
        for inizio, fine in _periodi_futuri(policy, oggi, fine_orizzonte):
            if titoli_periodo(policy, inizio, fine):
                continue
            rate = date_rate(policy, inizio, fine)
            premi = ripartisci(premio_periodo(policy.premio_annuo, inizio, fine),
                               [1] * len(rate) if annualita_piena(inizio, fine) else [(f - e).days for e, f in rate])
            for (effetto, _fine), premio in zip(rate, premi):
                if not oggi <= effetto < fine_orizzonte:
                    continue
                voce = indice.get((effetto.year, effetto.month))
                if voce:
                    voce["stimati"] += premio
                    voce["provvigioni"] += arrotonda(premio * (policy.provvigione_perc or 0) / 100.0)
                    voce["numero_stimati"] += 1

    arretrati_q = Title.query.join(Policy, Title.policy_id == Policy.id).filter(
        Title.stato == "da_incassare", Title.premio_lordo > 0, Title.data_effetto < oggi,
    )
    if compagnia:
        arretrati_q = arretrati_q.filter(Policy.compagnia == compagnia)
    arretrati = sum(t.premio_lordo for t in arretrati_q.all())
    for voce in colonne:
        voce["totale"] = voce["emessi"] + voce["stimati"]
        voce["netto"] = voce["totale"] - voce["provvigioni"]
    return {
        "colonne": colonne,
        "arretrati": arretrati,
        "totale_emessi": sum(v["emessi"] for v in colonne),
        "totale_stimati": sum(v["stimati"] for v in colonne),
        "totale_provvigioni": sum(v["provvigioni"] for v in colonne),
        "massimo": max([v["totale"] for v in colonne], default=0.0),
        "mesi": mesi,
    }


def _periodi_futuri(policy: Policy, oggi: date, fine_orizzonte: date):
    """Annualità (anche oltre la scadenza attuale, ipotizzando il rinnovo) che
    si sovrappongono all'orizzonte di previsione."""
    periodi = [p for p in periodi_polizza(policy, fino_a=fine_orizzonte) if p[1] > oggi]
    if policy.data_scadenza:
        inizio = policy.data_scadenza
        while inizio < fine_orizzonte and len(periodi) < 40:
            try:
                fine = add_months(inizio, 12)
            except (ValueError, OverflowError):
                break
            periodi.append((inizio, fine))
            inizio = fine
    return [p for p in periodi if p[0] < fine_orizzonte]


@bp.route("/previsione")
def forecast():
    mesi = parse_int(request.args.get("mesi")) or 12
    compagnia = request.args.get("compagnia", "")
    dati = calcola_previsione(mesi, compagnia)
    return render_template("titles/forecast.html", dati=dati, compagnia=compagnia,
                           compagnie=_compagnie(), mesi_scelta=MESI_PREVISIONE)


@bp.route("/previsione.csv")
def forecast_csv():
    mesi = parse_int(request.args.get("mesi")) or 12
    compagnia = request.args.get("compagnia", "")
    dati = calcola_previsione(mesi, compagnia)
    audit("export", "titolo", None, f"Esportata la previsione incassi ({dati['mesi']} mesi)", commit=True)
    return csv_response(
        "previsione_incassi",
        ["Mese", "Rate emesse", "Rate stimate", "Totale atteso", "Provvigioni attese", "Netto compagnie"],
        [(v["label"], v["emessi"], v["stimati"], v["totale"], v["provvigioni"], v["netto"]) for v in dati["colonne"]],
    )

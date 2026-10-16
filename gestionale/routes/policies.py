"""Gestione polizze: portafoglio, scheda, rinnovo, disdetta e generazione dei titoli."""
from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError

from ..automatismi import storna_titoli_futuri
from ..export import csv_response
from ..models import (
    DOCUMENT_CATEGORIES,
    DURATA_MASSIMA_ANNI,
    PAYMENT_FREQUENCIES,
    PAYMENT_METHODS,
    POLICY_BRANCHES,
    POLICY_STATUSES,
    RAMI_SENZA_TACITO_RINNOVO,
    TITLE_TYPES,
    AuditLog,
    Client,
    FollowUp,
    Policy,
    db,
    now,
)
from ..notifications import elimina_notifiche, segna_lette
from ..security import audit
from ..titoli import (
    TitoliGiaPresenti,
    add_months,
    annualita_corrente,
    genera_titoli,
    periodi_polizza,
    prossima_scadenza_utile,
    titoli_periodo,
)
from ..utils import add_months_sicuro, clean, leggi_data, leggi_importo, paginate, parse_date, parse_int

bp = Blueprint("policies", __name__, url_prefix="/polizze")

STATI_CESSATI = {"disdetta", "scaduta"}


def _populate_from_form(policy: Policy, form) -> list[str]:
    """Copia i campi del form nella polizza e restituisce gli errori."""
    errori: list[str] = []
    policy.compagnia = (form.get("compagnia") or "").strip()
    policy.numero_polizza = (form.get("numero_polizza") or "").strip()
    policy.ramo = form.get("ramo") if form.get("ramo") in dict(POLICY_BRANCHES) else "altro"
    policy.massimale = leggi_importo(form, "massimale", "Massimale", errori, minimo=0)
    policy.premio_annuo = leggi_importo(form, "premio_annuo", "Premio annuo", errori, minimo=0)
    policy.provvigione_perc = leggi_importo(
        form, "provvigione_perc", "Provvigione %", errori, minimo=0, massimo=100
    )
    frazionamento = form.get("frazionamento")
    policy.frazionamento = frazionamento if frazionamento in dict(PAYMENT_FREQUENCIES) else "annuale"
    policy.data_decorrenza = leggi_data(form, "data_decorrenza", "Decorrenza", errori)
    policy.data_scadenza = leggi_data(
        form, "data_scadenza", "Scadenza", errori,
    )
    policy.tacito_rinnovo = bool(form.get("tacito_rinnovo"))
    preavviso = (form.get("preavviso_disdetta_giorni") or "").strip()
    if policy.tacito_rinnovo and preavviso:
        valore = parse_int(preavviso, minimo=0, massimo=365)
        if valore is None:
            errori.append("Preavviso di disdetta: indica un numero di giorni tra 0 e 365.")
        policy.preavviso_disdetta_giorni = valore
    elif not policy.tacito_rinnovo:
        policy.preavviso_disdetta_giorni = None
    stato = form.get("stato")
    policy.stato = stato if stato in dict(POLICY_STATUSES) else "attiva"
    policy.note = clean(form, "note")

    if not policy.compagnia or not policy.numero_polizza:
        errori.append("Compagnia e numero polizza sono obbligatori.")
    if policy.data_decorrenza and policy.data_scadenza:
        if policy.data_scadenza <= policy.data_decorrenza:
            errori.append("La scadenza deve essere successiva alla decorrenza.")
        else:
            limite = add_months_sicuro(policy.data_decorrenza, 12 * DURATA_MASSIMA_ANNI)
            if limite and policy.data_scadenza > limite:
                errori.append(
                    f"Durata oltre {DURATA_MASSIMA_ANNI} anni: controlla le date. "
                    "Per le polizze senza scadenza (es. vita) lascia vuoto il campo scadenza."
                )
    if policy.tacito_rinnovo and policy.ramo in RAMI_SENZA_TACITO_RINNOVO:
        errori.append("Il tacito rinnovo non è ammesso per l'RC auto (L. 221/2012).")
    return errori


def _query_portafoglio():
    query = Policy.query.join(Client, Policy.client_id == Client.id)
    ramo = request.args.get("ramo", "")
    stato = request.args.get("stato", "")
    compagnia = request.args.get("compagnia", "")
    q = (request.args.get("q") or "").strip()
    oggi = date.today()
    if ramo:
        query = query.filter(Policy.ramo == ramo)
    if stato == "vigenti":
        query = query.filter(Policy.stato.in_(["attiva", "in_rinnovo"]))
    elif stato == "non_in_vigore":
        query = query.filter(Policy.stato.in_(["attiva", "in_rinnovo"]), Policy.data_decorrenza > oggi)
    elif stato == "da_rinnovare":
        query = query.filter(Policy.stato.in_(["attiva", "in_rinnovo"]), Policy.data_scadenza < oggi)
    elif stato:
        query = query.filter(Policy.stato == stato)
    if compagnia:
        query = query.filter(Policy.compagnia == compagnia)
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(Policy.numero_polizza.ilike(like), Client.ragione_sociale.ilike(like))
        )
    return query.order_by(Policy.data_scadenza.is_(None), Policy.data_scadenza.asc(), Policy.id.asc())


def compagnie_note() -> list[str]:
    return [c for (c,) in db.session.query(Policy.compagnia).distinct().order_by(Policy.compagnia)]


@bp.route("/")
def list_policies():
    query = _query_portafoglio()
    totale_premi = query.with_entities(
        db.func.coalesce(db.func.sum(Policy.premio_annuo), 0.0)
    ).order_by(None).scalar()
    pagination = paginate(query)
    return render_template(
        "policies/list.html",
        pagination=pagination,
        polizze=pagination.items,
        totale_premi=totale_premi,
        filtri=request.args,
        ramo=request.args.get("ramo", ""),
        stato=request.args.get("stato", ""),
        compagnie=compagnie_note(),
        policy_branches=POLICY_BRANCHES,
        policy_statuses=POLICY_STATUSES,
    )


@bp.route("/esporta.csv")
def export_policies():
    polizze = _query_portafoglio().limit(50000).all()
    audit("export", "polizza", None, f"Esportate {len(polizze)} polizze", commit=True)
    return csv_response(
        "polizze",
        ["Cliente", "Numero polizza", "Compagnia", "Ramo", "Stato", "Situazione", "Premio annuo",
         "Provvigione %", "Provvigione annua", "Massimale", "Frazionamento", "Decorrenza", "Scadenza",
         "Tacito rinnovo", "Termine disdetta", "Data disdetta", "Titoli arretrati"],
        [
            (p.cliente.ragione_sociale, p.numero_polizza, p.compagnia, p.ramo_label, p.stato_label,
             p.stato_effettivo_label, p.premio_annuo, p.provvigione_perc, p.provvigione_annua, p.massimale,
             p.frazionamento_label, p.data_decorrenza, p.data_scadenza, p.tacito_rinnovo,
             p.termine_disdetta, p.data_disdetta, len(p.titoli_arretrati))
            for p in polizze
        ],
    )


@bp.route("/nuova/<int:client_id>", methods=["POST"])
def new_policy(client_id):
    client = db.get_or_404(Client, client_id)
    policy = Policy(client_id=client.id)
    with db.session.no_autoflush:
        errori = _populate_from_form(policy, request.form)
    if errori:
        for e in errori:
            flash(e, "danger")
        from .clients import render_detail

        return render_detail(client, form_polizza=request.form), 400

    db.session.add(policy)
    db.session.flush()
    messaggio = f"Polizza {policy.numero_polizza} registrata."
    livello = "success"
    if request.form.get("genera_titoli") and policy.premio_annuo:
        try:
            titoli = genera_titoli(policy)
            messaggio += f" Generati {len(titoli)} titoli da incassare."
        except (ValueError, TitoliGiaPresenti) as exc:
            messaggio += f" Titoli non generati: {exc}"
            livello = "warning"
    audit("crea", "polizza", policy.id,
          f"Nuova polizza {policy.numero_polizza} ({policy.compagnia}, {policy.ramo_label}) per {client.ragione_sociale}")
    db.session.commit()
    flash(messaggio, livello)
    if policy.non_ancora_in_vigore:
        flash(f"La polizza decorre il {policy.data_decorrenza:%d/%m/%Y}: fino ad allora risulta «non ancora in vigore».", "info")
    return redirect(url_for("policies.detail", policy_id=policy.id))


def _periodi_con_titoli(policy: Policy):
    """Annualità della polizza con i relativi titoli (per la scheda)."""
    elenco = []
    oggi = date.today()
    for inizio, fine in periodi_polizza(policy):
        titoli = titoli_periodo(policy, inizio, fine)
        elenco.append({
            "inizio": inizio,
            "fine": fine,
            "titoli": titoli,
            "corrente": inizio <= oggi < fine,
            "futura": inizio > oggi,
            "incassato": sum(t.premio_lordo or 0 for t in titoli if t.stato == "incassato"),
            "da_incassare": sum(t.premio_lordo or 0 for t in titoli if t.stato == "da_incassare"),
        })
    return elenco


@bp.route("/<int:policy_id>")
def detail(policy_id):
    policy = db.get_or_404(Policy, policy_id)
    annualita = annualita_corrente(policy)
    titoli_correnti = titoli_periodo(policy, *annualita) if annualita else []
    storico = (
        AuditLog.query.filter_by(entita="polizza", entita_id=policy.id)
        .order_by(AuditLog.created_at.desc())
        .limit(20)
        .all()
    )
    situazione = {
        "incassato": sum(t.premio_lordo or 0 for t in policy.titoli if t.stato == "incassato"),
        "da_incassare": sum(t.premio_lordo or 0 for t in policy.titoli if t.stato == "da_incassare"),
        "arretrato": sum(t.premio_lordo or 0 for t in policy.titoli_arretrati),
    }
    # Rinnovo: si propone l'annualità successiva; se la polizza è scaduta da
    # oltre un anno si indica anche la prima scadenza utile futura.
    proposta = add_months_sicuro(policy.data_scadenza, 12)
    prossima_utile = prossima_scadenza_utile(policy.data_scadenza) if policy.data_scadenza else None
    return render_template(
        "policies/detail.html",
        policy=policy,
        annualita=annualita,
        titoli_correnti=titoli_correnti,
        periodi=_periodi_con_titoli(policy),
        situazione=situazione,
        storico=storico,
        proposta_scadenza=proposta,
        prossima_utile=prossima_utile if prossima_utile != proposta else None,
        massimo_rinnovo=add_months_sicuro(policy.data_scadenza, 12 * DURATA_MASSIMA_ANNI),
        oggi_iso=date.today().isoformat(),
        payment_methods=PAYMENT_METHODS,
        title_types=TITLE_TYPES,
        document_categories=DOCUMENT_CATEGORIES,
    )


@bp.route("/<int:policy_id>/modifica", methods=["GET", "POST"])
def edit_policy(policy_id):
    policy = db.get_or_404(Policy, policy_id)
    if request.method == "POST":
        prima = (policy.premio_annuo, policy.data_scadenza, policy.stato, policy.data_decorrenza,
                 policy.frazionamento)
        with db.session.no_autoflush:
            errori = _populate_from_form(policy, request.form)
        if errori:
            for e in errori:
                flash(e, "danger")
            risposta = _form_polizza(policy, request.form)
            db.session.rollback()
            return risposta, 400
        dettagli = []
        if prima[0] != policy.premio_annuo:
            dettagli.append(f"premio {prima[0]} → {policy.premio_annuo}")
        if prima[1] != policy.data_scadenza:
            dettagli.append("scadenza " + (f"{prima[1]:%d/%m/%Y}" if prima[1] else "—") + " → "
                            + (f"{policy.data_scadenza:%d/%m/%Y}" if policy.data_scadenza else "—"))
            if prima[1]:
                segna_lette(f"polizza:{policy.id}:{prima[1].isoformat()}:")
        if prima[2] != policy.stato:
            dettagli.append(f"stato {prima[2]} → {policy.stato}")
        stornati = 0
        if prima[2] in ("attiva", "in_rinnovo") and policy.stato in STATI_CESSATI:
            stornati = storna_titoli_futuri(policy, date.today(), f"polizza {policy.stato}")
            if stornati:
                dettagli.append(f"stornate {stornati} rate future")
        audit("modifica", "polizza", policy.id,
              f"Modificata polizza {policy.numero_polizza}" + (f": {', '.join(dettagli)}" if dettagli else ""))
        db.session.commit()
        flash("Polizza aggiornata.", "success")
        if stornati:
            flash(f"Stornate {stornati} rate non ancora scadute: le rate arretrate restano dovute per il periodo coperto.", "info")
        date_cambiate = (prima[1], prima[3], prima[4]) != (policy.data_scadenza, policy.data_decorrenza, policy.frazionamento)
        if date_cambiate and policy.titoli_da_incassare:
            flash("Date o frazionamento sono cambiati: verifica che i titoli da incassare siano ancora corretti.", "warning")
        return redirect(url_for("policies.detail", policy_id=policy.id))
    return _form_polizza(policy)


def _form_polizza(policy: Policy, valori=None):
    return render_template(
        "policies/form.html",
        policy=policy,
        valori=valori,
        compagnie=compagnie_note(),
        policy_branches=POLICY_BRANCHES,
        policy_statuses=POLICY_STATUSES,
        payment_frequencies=PAYMENT_FREQUENCIES,
    )


@bp.route("/<int:policy_id>/genera-titoli", methods=["POST"])
def generate_titles(policy_id):
    """Genera i titoli dell'annualità indicata (``inizio``) o di quella corrente."""
    policy = db.get_or_404(Policy, policy_id)
    periodo = None
    inizio_richiesto = parse_date(request.form.get("inizio"))
    if inizio_richiesto:
        periodo = next((p for p in periodi_polizza(policy) if p[0] == inizio_richiesto), None)
        if periodo is None:
            flash("Annualità non valida per questa polizza.", "danger")
            return redirect(url_for("policies.detail", policy_id=policy.id) + "#titoli")
    try:
        titoli = genera_titoli(policy, *(periodo or (None, None)))
        audit("crea", "titolo", None,
              f"Generati {len(titoli)} titoli per la polizza {policy.numero_polizza} "
              f"(annualità dal {titoli[0].data_effetto:%d/%m/%Y})")
        db.session.commit()
    except (ValueError, TitoliGiaPresenti) as exc:
        db.session.rollback()
        flash(str(exc), "warning")
    except IntegrityError:
        db.session.rollback()
        flash("I titoli di questa annualità sono già presenti.", "warning")
    else:
        flash(f"Generati {len(titoli)} titoli.", "success")
    return redirect(url_for("policies.detail", policy_id=policy.id) + "#titoli")


@bp.route("/<int:policy_id>/rinnova", methods=["POST"])
def renew(policy_id):
    """Rinnova la polizza per una nuova annualità (o per più anni, con conferma).

    Sposta la scadenza, aggiorna il premio, chiude i follow-up di rinnovo
    ancora aperti, annulla un'eventuale disdetta registrata e (se richiesto)
    genera i titoli della prima annualità rinnovata; le annualità successive
    di un rinnovo pluriennale vengono emesse all'anniversario.
    """
    policy = db.get_or_404(Policy, policy_id)
    torna = redirect(url_for("policies.detail", policy_id=policy.id))
    vecchia = policy.data_scadenza
    if not vecchia:
        flash("Imposta prima la data di scadenza della polizza.", "danger")
        return torna
    errori: list[str] = []
    try:
        dodici_mesi = add_months(vecchia, 12)
    except (ValueError, OverflowError):
        flash("La scadenza attuale non è valida: correggila dalla modifica della polizza.", "danger")
        return torna
    if (request.form.get("nuova_scadenza") or "").strip():
        nuova = leggi_data(
            request.form, "nuova_scadenza", "Nuova scadenza", errori,
            massimo=add_months_sicuro(vecchia, 12 * DURATA_MASSIMA_ANNI),
            msg_massimo=f"Nuova scadenza: oltre {DURATA_MASSIMA_ANNI} anni dalla scadenza attuale.",
        )
    else:
        nuova = dodici_mesi
    nuovo_premio = leggi_importo(request.form, "nuovo_premio", "Premio annuo", errori, minimo=0)
    if nuova is not None and nuova <= vecchia:
        errori.append("La nuova scadenza deve essere successiva a quella attuale.")
    if nuova is not None and nuova > add_months(vecchia, 13) and not request.form.get("pluriennale"):
        errori.append(
            "La nuova scadenza è oltre 13 mesi: per un rinnovo pluriennale spunta la conferma "
            "«rinnovo pluriennale»."
        )
    if errori:
        for e in errori:
            flash(e, "danger")
        return torna

    premio_prec = policy.premio_annuo
    if nuovo_premio is not None:
        policy.premio_annuo = nuovo_premio
    policy.data_scadenza = nuova
    if nuova > date.today():
        policy.stato = "attiva"
    policy.data_disdetta = None

    chiusi = 0
    for fu in FollowUp.query.filter_by(policy_id=policy.id, tipo="rinnovo", stato="aperto").all():
        fu.stato = "completato"
        fu.completed_at = now()
        chiusi += 1
    segna_lette(f"polizza:{policy.id}:")
    segna_lette(f"disdetta:{policy.id}:")

    messaggio = f"Polizza {policy.numero_polizza} rinnovata fino al {nuova:%d/%m/%Y}."
    livello = "success"
    if request.form.get("genera_titoli") and policy.premio_annuo:
        fine_prima = min(nuova, dodici_mesi)
        try:
            titoli = genera_titoli(policy, inizio=vecchia, fine=fine_prima, tipo_primo="quietanza")
            messaggio += f" Generati {len(titoli)} titoli"
            messaggio += " della prima annualità (le successive verranno emesse all'anniversario)." if nuova > dodici_mesi else "."
        except TitoliGiaPresenti:
            messaggio += " I titoli della nuova annualità erano già presenti."
        except ValueError as exc:
            messaggio += f" Titoli non generati: {exc}"
            livello = "warning"
    if chiusi:
        messaggio += f" Chiusi {chiusi} follow-up di rinnovo."

    audit("rinnovo", "polizza", policy.id,
          f"Rinnovata polizza {policy.numero_polizza}: scadenza {vecchia:%d/%m/%Y} → {nuova:%d/%m/%Y}"
          + (f", premio {premio_prec} → {policy.premio_annuo}" if premio_prec != policy.premio_annuo else ""))
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("Rinnovo già registrato (doppio invio): ricarica la pagina.", "warning")
        return torna
    flash(messaggio, livello)
    if nuova <= date.today():
        flash(
            f"La nuova scadenza ({nuova:%d/%m/%Y}) è già passata: la polizza risulta ancora da rinnovare "
            "e i titoli generati sono arretrati. Registra anche le annualità successive.",
            "warning",
        )
    return torna


@bp.route("/<int:policy_id>/disdetta", methods=["POST"])
def register_cancellation(policy_id):
    """Registra la disdetta: alla scadenza (default) oppure con effetto immediato."""
    policy = db.get_or_404(Policy, policy_id)
    torna = redirect(url_for("policies.detail", policy_id=policy.id))
    if not policy.attiva:
        flash("La polizza non è attiva.", "warning")
        return torna
    errori: list[str] = []
    oggi = date.today()
    data_disdetta = leggi_data(
        request.form, "data_disdetta", "Data della disdetta", errori, obbligatoria=True,
        massimo=oggi, msg_massimo="La data della disdetta non può essere futura.",
    )
    immediata = request.form.get("effetto") == "immediato"
    data_cessazione = None
    if immediata:
        data_cessazione = leggi_data(
            request.form, "data_cessazione", "Data di cessazione", errori, obbligatoria=True,
            minimo=policy.data_decorrenza,
            msg_minimo="La cessazione non può precedere la decorrenza della polizza.",
        )
    elif not policy.data_scadenza:
        errori.append("La polizza non ha una scadenza: registra la disdetta con effetto immediato.")
    motivo = clean(request.form, "motivo") or "disdetta"
    if errori:
        for e in errori:
            flash(e, "danger")
        return torna

    policy.data_disdetta = data_disdetta
    if immediata:
        stornati = storna_titoli_futuri(policy, data_cessazione, f"disdetta: {motivo}")
        if data_cessazione <= oggi:
            policy.stato = "disdetta"
        descrizione = f"con effetto dal {data_cessazione:%d/%m/%Y}"
    else:
        stornati = storna_titoli_futuri(policy, policy.data_scadenza, f"disdetta: {motivo}")
        descrizione = f"alla scadenza del {policy.data_scadenza:%d/%m/%Y}"
    for fu in FollowUp.query.filter_by(policy_id=policy.id, tipo="rinnovo", stato="aperto").all():
        fu.stato = "completato"
        fu.completed_at = now()
    segna_lette(f"disdetta:{policy.id}:")
    audit("modifica", "polizza", policy.id,
          f"Registrata disdetta della polizza {policy.numero_polizza} del {data_disdetta:%d/%m/%Y} "
          f"{descrizione} ({motivo})" + (f", stornate {stornati} rate" if stornati else ""))
    db.session.commit()
    flash(f"Disdetta registrata {descrizione}." + (f" Stornate {stornati} rate." if stornati else ""), "success")
    if not immediata and policy.disdetta_tardiva:
        flash(
            f"Attenzione: la disdetta è successiva al termine di preavviso ({policy.termine_disdetta:%d/%m/%Y}): "
            "la compagnia potrebbe considerare il contratto rinnovato.",
            "warning",
        )
    return torna


@bp.route("/<int:policy_id>/annulla-disdetta", methods=["POST"])
def cancel_cancellation(policy_id):
    policy = db.get_or_404(Policy, policy_id)
    if policy.data_disdetta is None or not policy.attiva:
        flash("Non c'è una disdetta da annullare.", "warning")
    else:
        audit("modifica", "polizza", policy.id,
              f"Annullata la disdetta del {policy.data_disdetta:%d/%m/%Y} della polizza {policy.numero_polizza}")
        policy.data_disdetta = None
        db.session.commit()
        flash("Disdetta annullata. Se servono, rigenera i titoli stornati dalla scheda.", "info")
    return redirect(url_for("policies.detail", policy_id=policy.id))


@bp.route("/<int:policy_id>/elimina", methods=["POST"])
def delete_policy(policy_id):
    policy = db.get_or_404(Policy, policy_id)
    client_id = policy.client_id
    if policy.titoli_incassati:
        flash(
            "La polizza ha titoli incassati e non può essere eliminata: per toglierla dal "
            "portafoglio impostane lo stato a «Disdetta» o «Scaduta».",
            "danger",
        )
        return redirect(url_for("policies.detail", policy_id=policy.id))
    for doc in policy.documenti:
        doc.policy_id = None
    for claim in policy.sinistri:
        claim.policy_id = None
    for fu in FollowUp.query.filter_by(policy_id=policy.id).all():
        if fu.auto_generato and fu.tipo == "rinnovo" and fu.stato == "aperto":
            fu.stato = "annullato"
            elimina_notifiche(f"followup:{fu.id}:")
        fu.policy_id = None
    elimina_notifiche(
        f"polizza:{policy.id}:", f"disdetta:{policy.id}:", f"decorrenza:{policy.id}:",
        *(f"titolo:{t.id}:" for t in policy.titoli),
    )
    audit("elimina", "polizza", policy.id,
          f"Eliminata polizza {policy.numero_polizza} ({policy.compagnia}) di {policy.cliente.ragione_sociale}")
    db.session.delete(policy)
    db.session.commit()
    flash("Polizza eliminata.", "success")
    return redirect(url_for("clients.detail", client_id=client_id) + "#polizze")

"""Gestione polizze: portafoglio, scheda, rinnovo e generazione dei titoli."""
from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..export import csv_response
from ..models import (
    DOCUMENT_CATEGORIES,
    PAYMENT_FREQUENCIES,
    PAYMENT_METHODS,
    POLICY_BRANCHES,
    POLICY_STATUSES,
    TITLE_TYPES,
    AuditLog,
    Client,
    FollowUp,
    Policy,
    db,
    now,
)
from ..notifications import segna_lette
from ..security import audit
from ..titoli import TitoliGiaPresenti, add_months, annualita_corrente, genera_titoli, titoli_annualita
from ..utils import clean, paginate, parse_date, parse_float

bp = Blueprint("policies", __name__, url_prefix="/polizze")


def _populate_from_form(policy: Policy, form) -> list[str]:
    """Copia i campi del form nella polizza e restituisce gli errori."""
    policy.compagnia = (form.get("compagnia") or "").strip()
    policy.numero_polizza = (form.get("numero_polizza") or "").strip()
    policy.ramo = form.get("ramo") if form.get("ramo") in dict(POLICY_BRANCHES) else "altro"
    policy.massimale = parse_float(form.get("massimale"))
    policy.premio_annuo = parse_float(form.get("premio_annuo"))
    policy.provvigione_perc = parse_float(form.get("provvigione_perc"))
    frazionamento = form.get("frazionamento")
    policy.frazionamento = frazionamento if frazionamento in dict(PAYMENT_FREQUENCIES) else "annuale"
    policy.data_decorrenza = parse_date(form.get("data_decorrenza"))
    policy.data_scadenza = parse_date(form.get("data_scadenza"))
    policy.tacito_rinnovo = bool(form.get("tacito_rinnovo"))
    stato = form.get("stato")
    policy.stato = stato if stato in dict(POLICY_STATUSES) else "attiva"
    policy.note = clean(form, "note")

    errori = []
    if not policy.compagnia or not policy.numero_polizza:
        errori.append("Compagnia e numero polizza sono obbligatori.")
    if policy.data_decorrenza and policy.data_scadenza and policy.data_scadenza <= policy.data_decorrenza:
        errori.append("La scadenza deve essere successiva alla decorrenza.")
    if policy.premio_annuo is not None and policy.premio_annuo < 0:
        errori.append("Il premio non può essere negativo.")
    if policy.provvigione_perc is not None and not 0 <= policy.provvigione_perc <= 100:
        errori.append("La percentuale di provvigione deve essere tra 0 e 100.")
    return errori


def _query_portafoglio():
    query = Policy.query.join(Client, Policy.client_id == Client.id)
    ramo = request.args.get("ramo", "")
    stato = request.args.get("stato", "")
    compagnia = request.args.get("compagnia", "")
    q = (request.args.get("q") or "").strip()
    if ramo:
        query = query.filter(Policy.ramo == ramo)
    if stato:
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
        ["Cliente", "Numero polizza", "Compagnia", "Ramo", "Stato", "Premio annuo", "Provvigione %",
         "Provvigione annua", "Massimale", "Frazionamento", "Decorrenza", "Scadenza", "Tacito rinnovo",
         "Titoli arretrati"],
        [
            (p.cliente.ragione_sociale, p.numero_polizza, p.compagnia, p.ramo_label, p.stato_label,
             p.premio_annuo, p.provvigione_perc, p.provvigione_annua, p.massimale, p.frazionamento_label,
             p.data_decorrenza, p.data_scadenza, p.tacito_rinnovo, len(p.titoli_arretrati))
            for p in polizze
        ],
    )


@bp.route("/nuova/<int:client_id>", methods=["POST"])
def new_policy(client_id):
    client = db.get_or_404(Client, client_id)
    policy = Policy(client_id=client.id)
    errori = _populate_from_form(policy, request.form)
    if errori:
        for e in errori:
            flash(e, "danger")
        return redirect(url_for("clients.detail", client_id=client.id) + "#polizze")

    db.session.add(policy)
    db.session.flush()
    messaggio = f"Polizza {policy.numero_polizza} registrata."
    if request.form.get("genera_titoli") and policy.premio_annuo:
        titoli = genera_titoli(policy)
        messaggio += f" Generati {len(titoli)} titoli da incassare."
    audit("crea", "polizza", policy.id,
          f"Nuova polizza {policy.numero_polizza} ({policy.compagnia}, {policy.ramo_label}) per {client.ragione_sociale}")
    db.session.commit()
    flash(messaggio, "success")
    return redirect(url_for("policies.detail", policy_id=policy.id))


@bp.route("/<int:policy_id>")
def detail(policy_id):
    policy = db.get_or_404(Policy, policy_id)
    inizio, fine = annualita_corrente(policy)
    titoli_correnti = titoli_annualita(policy, inizio, fine)
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
    return render_template(
        "policies/detail.html",
        policy=policy,
        annualita=(inizio, fine),
        titoli_correnti=titoli_correnti,
        situazione=situazione,
        storico=storico,
        proposta_scadenza=add_months(policy.data_scadenza, 12) if policy.data_scadenza else None,
        payment_methods=PAYMENT_METHODS,
        title_types=TITLE_TYPES,
        document_categories=DOCUMENT_CATEGORIES,
    )


@bp.route("/<int:policy_id>/modifica", methods=["GET", "POST"])
def edit_policy(policy_id):
    policy = db.get_or_404(Policy, policy_id)
    if request.method == "POST":
        prima = (policy.premio_annuo, policy.data_scadenza, policy.stato)
        errori = _populate_from_form(policy, request.form)
        if errori:
            for e in errori:
                flash(e, "danger")
        else:
            dettagli = []
            if prima[0] != policy.premio_annuo:
                dettagli.append(f"premio {prima[0]} → {policy.premio_annuo}")
            if prima[1] != policy.data_scadenza:
                dettagli.append("scadenza " + (f"{prima[1]:%d/%m/%Y}" if prima[1] else "—") + " → "
                                + (f"{policy.data_scadenza:%d/%m/%Y}" if policy.data_scadenza else "—"))
            if prima[2] != policy.stato:
                dettagli.append(f"stato {prima[2]} → {policy.stato}")
            audit("modifica", "polizza", policy.id,
                  f"Modificata polizza {policy.numero_polizza}" + (f": {', '.join(dettagli)}" if dettagli else ""))
            db.session.commit()
            flash("Polizza aggiornata.", "success")
            return redirect(url_for("policies.detail", policy_id=policy.id))
    return render_template(
        "policies/form.html",
        policy=policy,
        compagnie=compagnie_note(),
        policy_branches=POLICY_BRANCHES,
        policy_statuses=POLICY_STATUSES,
        payment_frequencies=PAYMENT_FREQUENCIES,
    )


@bp.route("/<int:policy_id>/genera-titoli", methods=["POST"])
def generate_titles(policy_id):
    policy = db.get_or_404(Policy, policy_id)
    try:
        titoli = genera_titoli(policy)
    except (ValueError, TitoliGiaPresenti) as exc:
        flash(str(exc), "warning")
    else:
        audit("crea", "titolo", None,
              f"Generati {len(titoli)} titoli per la polizza {policy.numero_polizza} "
              f"(annualità {titoli[0].data_effetto:%d/%m/%Y})")
        db.session.commit()
        flash(f"Generati {len(titoli)} titoli per l'annualità in corso.", "success")
    return redirect(url_for("policies.detail", policy_id=policy.id) + "#titoli")


@bp.route("/<int:policy_id>/rinnova", methods=["POST"])
def renew(policy_id):
    """Rinnova la polizza per una nuova annualità.

    Sposta la scadenza, aggiorna il premio, chiude i follow-up di rinnovo
    ancora aperti e (se richiesto) genera i titoli della nuova annualità.
    """
    policy = db.get_or_404(Policy, policy_id)
    vecchia = policy.data_scadenza
    if not vecchia:
        flash("Imposta prima la data di scadenza della polizza.", "danger")
        return redirect(url_for("policies.detail", policy_id=policy.id))
    nuova = parse_date(request.form.get("nuova_scadenza")) or add_months(vecchia, 12)
    if nuova <= vecchia:
        flash("La nuova scadenza deve essere successiva a quella attuale.", "danger")
        return redirect(url_for("policies.detail", policy_id=policy.id))
    nuovo_premio = parse_float(request.form.get("nuovo_premio"))
    if nuovo_premio is not None and nuovo_premio < 0:
        flash("Il premio non può essere negativo.", "danger")
        return redirect(url_for("policies.detail", policy_id=policy.id))

    premio_prec = policy.premio_annuo
    if nuovo_premio is not None:
        policy.premio_annuo = nuovo_premio
    policy.data_scadenza = nuova
    policy.stato = "attiva"

    chiusi = 0
    for fu in FollowUp.query.filter_by(policy_id=policy.id, tipo="rinnovo", stato="aperto").all():
        fu.stato = "completato"
        fu.completed_at = now()
        chiusi += 1
    segna_lette(f"polizza:{policy.id}:")

    messaggio = f"Polizza {policy.numero_polizza} rinnovata fino al {nuova:%d/%m/%Y}."
    if request.form.get("genera_titoli") and policy.premio_annuo:
        try:
            titoli = genera_titoli(policy, inizio=vecchia, fine=nuova, tipo_primo="quietanza")
            messaggio += f" Generati {len(titoli)} titoli."
        except TitoliGiaPresenti:
            messaggio += " I titoli della nuova annualità erano già presenti."
    if chiusi:
        messaggio += f" Chiusi {chiusi} follow-up di rinnovo."

    audit("rinnovo", "polizza", policy.id,
          f"Rinnovata polizza {policy.numero_polizza}: scadenza {vecchia:%d/%m/%Y} → {nuova:%d/%m/%Y}"
          + (f", premio {premio_prec} → {policy.premio_annuo}" if premio_prec != policy.premio_annuo else ""))
    db.session.commit()
    flash(messaggio, "success")
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
    FollowUp.query.filter_by(policy_id=policy.id).update({"policy_id": None})
    audit("elimina", "polizza", policy.id,
          f"Eliminata polizza {policy.numero_polizza} ({policy.compagnia}) di {policy.cliente.ragione_sociale}")
    db.session.delete(policy)
    db.session.commit()
    flash("Polizza eliminata.", "success")
    return redirect(url_for("clients.detail", client_id=client_id) + "#polizze")


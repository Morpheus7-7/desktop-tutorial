"""Gestione sinistri: apertura, lavorazione, cronologia e chiusura."""
from datetime import date

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from ..export import csv_response
from ..models import (
    CLAIM_OPEN_STATUSES,
    CLAIM_STATUSES,
    CLAIM_TYPES,
    DOCUMENT_CATEGORIES,
    Claim,
    ClaimNote,
    Client,
    Policy,
    db,
    now,
)
from ..notifications import segna_lette
from ..security import audit
from ..utils import clean, formatta_euro, paginate, parse_date, parse_float, parse_int

bp = Blueprint("claims", __name__, url_prefix="/sinistri")

STATI_CHIUSI = {s for s, _ in CLAIM_STATUSES} - CLAIM_OPEN_STATUSES


def _query():
    query = Claim.query.join(Client, Claim.client_id == Client.id)
    filtro = request.args.get("filtro", "aperti")
    if filtro == "aperti":
        query = query.filter(Claim.stato.in_(CLAIM_OPEN_STATUSES))
    elif filtro == "chiusi":
        query = query.filter(Claim.stato.in_(STATI_CHIUSI))
    stato = request.args.get("stato", "")
    if stato:
        query = query.filter(Claim.stato == stato)
    tipologia = request.args.get("tipologia", "")
    if tipologia:
        query = query.filter(Claim.tipologia == tipologia)
    q = (request.args.get("q") or "").strip()
    if q:
        like = f"%{q}%"
        query = query.outerjoin(Policy, Claim.policy_id == Policy.id).filter(
            db.or_(
                Claim.numero.ilike(like),
                Claim.numero_compagnia.ilike(like),
                Claim.controparte.ilike(like),
                Client.ragione_sociale.ilike(like),
                Policy.numero_polizza.ilike(like),
            )
        )
    return query.order_by(Claim.data_evento.desc(), Claim.id.desc())


@bp.route("/")
def list_claims():
    pagination = paginate(_query())
    aperti = Claim.query.filter(Claim.stato.in_(CLAIM_OPEN_STATUSES))
    riepilogo = {
        "aperti": aperti.count(),
        "riservato": aperti.with_entities(db.func.coalesce(db.func.sum(Claim.importo_riservato), 0.0)).scalar(),
        "liquidato_anno": db.session.query(db.func.coalesce(db.func.sum(Claim.importo_liquidato), 0.0))
        .filter(Claim.data_liquidazione >= date(date.today().year, 1, 1))
        .scalar(),
        "da_denunciare": aperti.filter(Claim.data_denuncia.is_(None)).count(),
    }
    return render_template(
        "claims/list.html",
        pagination=pagination,
        sinistri=pagination.items,
        riepilogo=riepilogo,
        filtri=request.args,
        filtro=request.args.get("filtro", "aperti"),
        claim_statuses=CLAIM_STATUSES,
        claim_types=CLAIM_TYPES,
    )


@bp.route("/esporta.csv")
def export_claims():
    sinistri = _query().limit(50000).all()
    audit("export", "sinistro", None, f"Esportati {len(sinistri)} sinistri", commit=True)
    return csv_response(
        "sinistri",
        ["Numero", "N. compagnia", "Cliente", "Polizza", "Compagnia", "Tipologia", "Data evento",
         "Data denuncia", "Luogo", "Controparte", "Stato", "Importo richiesto", "Riserva",
         "Liquidato", "Franchigia", "Data liquidazione", "Data chiusura", "Giorni di apertura"],
        [
            (s.numero, s.numero_compagnia, s.cliente.ragione_sociale,
             s.polizza.numero_polizza if s.polizza else None,
             s.polizza.compagnia if s.polizza else None, s.tipologia_label, s.data_evento,
             s.data_denuncia, s.luogo, s.controparte, s.stato_label, s.importo_richiesto,
             s.importo_riservato, s.importo_liquidato, s.franchigia, s.data_liquidazione,
             s.data_chiusura, s.giorni_apertura)
            for s in sinistri
        ],
    )


def _populate(claim: Claim, form) -> list[str]:
    """Copia i campi del form nel sinistro; restituisce gli errori di validazione."""
    errori = []
    claim.tipologia = form.get("tipologia") if form.get("tipologia") in dict(CLAIM_TYPES) else "altro"
    claim.numero_compagnia = clean(form, "numero_compagnia")
    claim.data_evento = parse_date(form.get("data_evento"))
    claim.data_denuncia = parse_date(form.get("data_denuncia"))
    claim.luogo = clean(form, "luogo")
    claim.descrizione = clean(form, "descrizione")
    claim.controparte = clean(form, "controparte")
    claim.perito = clean(form, "perito")
    claim.liquidatore = clean(form, "liquidatore")
    claim.importo_richiesto = parse_float(form.get("importo_richiesto"))
    claim.importo_riservato = parse_float(form.get("importo_riservato"))
    claim.importo_liquidato = parse_float(form.get("importo_liquidato"))
    claim.franchigia = parse_float(form.get("franchigia"))
    claim.data_liquidazione = parse_date(form.get("data_liquidazione"))
    claim.note = clean(form, "note")

    if not claim.data_evento:
        errori.append("La data dell'evento è obbligatoria.")
    elif claim.data_evento > date.today():
        errori.append("La data dell'evento non può essere futura.")
    if claim.data_evento and claim.data_denuncia and claim.data_denuncia < claim.data_evento:
        errori.append("La data di denuncia non può precedere quella dell'evento.")
    for campo, etichetta in (
        ("importo_richiesto", "L'importo richiesto"),
        ("importo_riservato", "La riserva"),
        ("importo_liquidato", "L'importo liquidato"),
        ("franchigia", "La franchigia"),
    ):
        valore = getattr(claim, campo)
        if valore is not None and valore < 0:
            errori.append(f"{etichetta} non può essere negativo.")
    return errori


def _policy_for(client: Client, raw) -> Policy | None:
    pid = parse_int(raw)
    if pid is None:
        return None
    return next((p for p in client.polizze if p.id == pid), None)


def _form_context(claim, client=None):
    clienti = None if client else Client.query.order_by(Client.ragione_sociale).all()
    polizze = (
        client.polizze if client
        else Policy.query.join(Client).order_by(Client.ragione_sociale, Policy.numero_polizza).all()
    )
    return dict(
        claim=claim, client=client, clienti=clienti, polizze=polizze,
        claim_types=CLAIM_TYPES, claim_statuses=CLAIM_STATUSES,
    )


@bp.route("/nuovo", methods=["GET", "POST"])
def new_claim():
    client = None
    cid = parse_int(request.values.get("client_id"))
    if cid:
        client = db.get_or_404(Client, cid)
    claim = Claim(stato="aperto", data_denuncia=date.today())
    if request.method == "GET":
        policy = db.session.get(Policy, parse_int(request.args.get("policy_id")) or 0)
        if policy is not None:
            client = policy.cliente
            claim.policy_id = policy.id
        return render_template("claims/form.html", **_form_context(claim, client))

    if client is None:
        flash("Seleziona il cliente del sinistro.", "danger")
        return render_template("claims/form.html", **_form_context(claim, None)), 400
    errori = _populate(claim, request.form)
    policy = _policy_for(client, request.form.get("policy_id"))
    claim.policy_id = policy.id if policy else None
    if errori:
        for e in errori:
            flash(e, "danger")
        return render_template("claims/form.html", **_form_context(claim, client)), 400

    claim.client_id = client.id
    claim.numero = Claim.genera_numero(date.today().year)
    db.session.add(claim)
    db.session.flush()
    claim.eventi.append(ClaimNote(tipo="stato", testo="Sinistro aperto.", username=g.user.username))
    audit("crea", "sinistro", claim.id,
          f"Aperto sinistro {claim.numero} per {client.ragione_sociale}"
          + (f" (polizza {policy.numero_polizza})" if policy else ""))
    db.session.commit()
    flash(f"Sinistro {claim.numero} aperto.", "success")
    if claim.denuncia_tardiva:
        flash("Attenzione: denuncia oltre i 3 giorni dall'evento (art. 1913 c.c.).", "warning")
    return redirect(url_for("claims.detail", claim_id=claim.id))


@bp.route("/<int:claim_id>")
def detail(claim_id):
    claim = db.get_or_404(Claim, claim_id)
    return render_template(
        "claims/detail.html",
        claim=claim,
        claim_statuses=CLAIM_STATUSES,
        document_categories=DOCUMENT_CATEGORIES,
    )


@bp.route("/<int:claim_id>/modifica", methods=["GET", "POST"])
def edit_claim(claim_id):
    claim = db.get_or_404(Claim, claim_id)
    if request.method == "POST":
        errori = _populate(claim, request.form)
        policy = _policy_for(claim.cliente, request.form.get("policy_id"))
        claim.policy_id = policy.id if policy else None
        if errori:
            for e in errori:
                flash(e, "danger")
            return render_template("claims/form.html", **_form_context(claim, claim.cliente)), 400
        if claim.data_denuncia:
            segna_lette(f"sinistro:{claim.id}:denuncia")
        audit("modifica", "sinistro", claim.id, f"Modificato sinistro {claim.numero}")
        db.session.commit()
        flash("Sinistro aggiornato.", "success")
        return redirect(url_for("claims.detail", claim_id=claim.id))
    return render_template("claims/form.html", **_form_context(claim, claim.cliente))


@bp.route("/<int:claim_id>/stato", methods=["POST"])
def change_status(claim_id):
    claim = db.get_or_404(Claim, claim_id)
    nuovo = request.form.get("stato")
    if nuovo not in dict(CLAIM_STATUSES):
        abort(400)
    commento = (request.form.get("commento") or "").strip()
    if nuovo == "liquidato":
        importo = parse_float(request.form.get("importo_liquidato"))
        if importo is not None:
            claim.importo_liquidato = importo
        if not claim.importo_liquidato:
            flash("Per chiudere come liquidato indica l'importo liquidato.", "danger")
            return redirect(url_for("claims.detail", claim_id=claim.id))
        claim.data_liquidazione = claim.data_liquidazione or date.today()
    if nuovo == claim.stato:
        flash("Il sinistro è già in questo stato.", "info")
        return redirect(url_for("claims.detail", claim_id=claim.id))

    vecchio = claim.stato_label
    claim.stato = nuovo
    claim.data_chiusura = None if nuovo in CLAIM_OPEN_STATUSES else (claim.data_chiusura or date.today())
    testo = f"Stato: {vecchio} → {claim.stato_label}."
    if nuovo == "liquidato":
        testo += f" Liquidati {formatta_euro(claim.importo_liquidato)}."
    if commento:
        testo += f" {commento}"
    claim.eventi.append(ClaimNote(tipo="stato", testo=testo, username=g.user.username))
    if not claim.aperto:
        segna_lette(f"sinistro:{claim.id}:")
    audit("modifica", "sinistro", claim.id, f"Sinistro {claim.numero}: {testo}")
    db.session.commit()
    flash(f"Sinistro {claim.numero}: {claim.stato_label}.", "success")
    return redirect(url_for("claims.detail", claim_id=claim.id))


@bp.route("/<int:claim_id>/nota", methods=["POST"])
def add_note(claim_id):
    claim = db.get_or_404(Claim, claim_id)
    testo = (request.form.get("testo") or "").strip()
    if not testo:
        flash("Scrivi il testo della nota.", "warning")
    else:
        claim.eventi.append(ClaimNote(tipo="nota", testo=testo, username=g.user.username))
        claim.updated_at = now()
        db.session.commit()
        flash("Nota aggiunta alla cronologia.", "success")
    return redirect(url_for("claims.detail", claim_id=claim.id) + "#cronologia")


@bp.route("/<int:claim_id>/elimina", methods=["POST"])
def delete_claim(claim_id):
    claim = db.get_or_404(Claim, claim_id)
    client_id = claim.client_id
    for doc in claim.documenti:
        doc.claim_id = None
    audit("elimina", "sinistro", claim.id, f"Eliminato sinistro {claim.numero} ({claim.cliente.ragione_sociale})")
    db.session.delete(claim)
    db.session.commit()
    flash("Sinistro eliminato.", "success")
    return redirect(url_for("clients.detail", client_id=client_id) + "#sinistri")

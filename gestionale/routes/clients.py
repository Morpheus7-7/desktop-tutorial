"""Anagrafica clienti (aziende, professionisti, dipendenti) e analisi rischi."""
import json
import os

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from ..export import csv_response
from ..models import (
    CLAIM_STATUSES,
    CLIENT_TYPES,
    DOCUMENT_CATEGORIES,
    FOLLOWUP_PRIORITIES,
    FOLLOWUP_TYPES,
    ID_DOCUMENT_TYPES,
    PAYMENT_FREQUENCIES,
    PAYMENT_METHODS,
    POLICY_BRANCHES,
    POLICY_STATUSES,
    Client,
    RiskAnalysis,
    db,
)
from ..risk_engine import analyze_client
from ..security import audit
from ..utils import clean, paginate, parse_date, parse_float, parse_int
from ..validators import (
    data_nascita_da_cf,
    valida_cap,
    valida_codice_fiscale,
    valida_email,
    valida_partita_iva,
    valida_provincia,
)

bp = Blueprint("clients", __name__, url_prefix="/clienti")


def _populate_from_form(client: Client, form) -> None:
    tipo = form.get("tipo")
    client.tipo = tipo if tipo in dict(CLIENT_TYPES) else "azienda"
    client.ragione_sociale = (form.get("ragione_sociale") or "").strip()
    client.referente = clean(form, "referente")
    client.codice_fiscale = (clean(form, "codice_fiscale", upper=True) or "").replace(" ", "") or None
    client.partita_iva = (clean(form, "partita_iva") or "").replace(" ", "").upper().removeprefix("IT") or None
    client.codice_ateco = clean(form, "codice_ateco")
    client.professione = clean(form, "professione")
    client.datore_lavoro = clean(form, "datore_lavoro")
    client.settore = clean(form, "settore")
    client.indirizzo = clean(form, "indirizzo")
    client.citta = clean(form, "citta")
    client.cap = clean(form, "cap")
    client.provincia = clean(form, "provincia", upper=True)
    client.email = clean(form, "email")
    client.pec = clean(form, "pec")
    client.telefono = clean(form, "telefono")
    client.numero_dipendenti = parse_int(form.get("numero_dipendenti"))
    client.fatturato_annuo = parse_float(form.get("fatturato_annuo"))
    client.descrizione_attivita = clean(form, "descrizione_attivita")
    client.note = clean(form, "note")
    # Compliance
    client.data_nascita = parse_date(form.get("data_nascita"))
    client.data_consenso_privacy = parse_date(form.get("data_consenso_privacy"))
    client.consenso_marketing = bool(form.get("consenso_marketing"))
    client.data_adeguatezza = parse_date(form.get("data_adeguatezza"))
    documento_tipo = form.get("documento_tipo")
    client.documento_tipo = documento_tipo if documento_tipo in dict(ID_DOCUMENT_TYPES) else None
    client.documento_numero = clean(form, "documento_numero", upper=True)
    client.documento_scadenza = parse_date(form.get("documento_scadenza"))
    if client.persona_fisica and not client.data_nascita:
        client.data_nascita = data_nascita_da_cf(client.codice_fiscale)


def _valida(client: Client) -> list[str]:
    errori = []
    if not client.ragione_sociale:
        errori.append("La ragione sociale / il nominativo è obbligatorio.")
    for errore in (
        valida_partita_iva(client.partita_iva),
        valida_codice_fiscale(client.codice_fiscale),
        valida_cap(client.cap),
        valida_provincia(client.provincia),
        valida_email(client.email, "email"),
        valida_email(client.pec, "PEC"),
    ):
        if errore:
            errori.append(errore)
    if client.numero_dipendenti is not None and client.numero_dipendenti < 0:
        errori.append("Il numero di dipendenti non può essere negativo.")
    return errori


def _avvisa_duplicati(client: Client) -> None:
    condizioni = []
    if client.partita_iva:
        condizioni.append(Client.partita_iva == client.partita_iva)
    if client.codice_fiscale:
        condizioni.append(Client.codice_fiscale == client.codice_fiscale)
    if not condizioni:
        return
    query = Client.query.filter(db.or_(*condizioni))
    if client.id:
        query = query.filter(Client.id != client.id)
    doppione = query.first()
    if doppione:
        flash(
            f"Attenzione: esiste già un cliente con la stessa partita IVA / codice fiscale "
            f"(«{doppione.ragione_sociale}»).",
            "warning",
        )


def _form(client, nuovo):
    return render_template(
        "clients/form.html",
        client=client,
        nuovo=nuovo,
        client_types=CLIENT_TYPES,
        id_document_types=ID_DOCUMENT_TYPES,
    )


def _query_clienti():
    q = request.args.get("q", "").strip()
    tipo = request.args.get("tipo", "")
    query = Client.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                Client.ragione_sociale.ilike(like),
                Client.partita_iva.ilike(like),
                Client.codice_fiscale.ilike(like),
                Client.citta.ilike(like),
                Client.settore.ilike(like),
                Client.referente.ilike(like),
                Client.email.ilike(like),
            )
        )
    if tipo in dict(CLIENT_TYPES):
        query = query.filter_by(tipo=tipo)
    return query.order_by(Client.ragione_sociale.asc())


@bp.route("/")
def list_clients():
    pagination = paginate(_query_clienti())
    return render_template(
        "clients/list.html",
        pagination=pagination,
        clienti=pagination.items,
        q=request.args.get("q", "").strip(),
        tipo=request.args.get("tipo", ""),
        client_types=CLIENT_TYPES,
    )


@bp.route("/esporta.csv")
def export_clients():
    clienti = _query_clienti().limit(50000).all()
    audit("export", "cliente", None, f"Esportati {len(clienti)} clienti", commit=True)
    return csv_response(
        "clienti",
        ["Ragione sociale / Nominativo", "Tipo", "Referente", "Partita IVA", "Codice fiscale",
         "Codice ATECO", "Professione / Mansione", "Datore di lavoro", "Settore", "Indirizzo", "CAP",
         "Città", "Provincia", "Email", "PEC", "Telefono", "Dipendenti", "Fatturato", "Data di nascita",
         "Consenso privacy", "Consenso marketing", "Questionario adeguatezza", "Scadenza documento",
         "Polizze attive", "Premi attivi"],
        [
            (c.ragione_sociale, c.tipo_label, c.referente, c.partita_iva, c.codice_fiscale,
             c.codice_ateco, c.professione, c.datore_lavoro, c.settore, c.indirizzo, c.cap, c.citta,
             c.provincia, c.email, c.pec, c.telefono, c.numero_dipendenti, c.fatturato_annuo,
             c.data_nascita, c.data_consenso_privacy, c.consenso_marketing, c.data_adeguatezza,
             c.documento_scadenza, len(c.polizze_attive), c.premi_attivi)
            for c in clienti
        ],
    )


@bp.route("/nuovo", methods=["GET", "POST"])
def new_client():
    client = Client(tipo=request.args.get("tipo") if request.args.get("tipo") in dict(CLIENT_TYPES) else "azienda")
    if request.method == "POST":
        _populate_from_form(client, request.form)
        errori = _valida(client)
        if errori:
            for e in errori:
                flash(e, "danger")
            return _form(client, nuovo=True), 400
        _avvisa_duplicati(client)
        db.session.add(client)
        db.session.flush()
        audit("crea", "cliente", client.id, f"Nuovo cliente «{client.ragione_sociale}» ({client.tipo_label})")
        db.session.commit()
        flash(f"Cliente «{client.ragione_sociale}» creato.", "success")
        if request.form.get("analizza_subito") and client.descrizione_attivita:
            return redirect(url_for("clients.run_analysis", client_id=client.id), code=307)
        return redirect(url_for("clients.detail", client_id=client.id))
    return _form(client, nuovo=True)


@bp.route("/<int:client_id>")
def detail(client_id):
    client = db.get_or_404(Client, client_id)
    from .policies import compagnie_note

    return render_template(
        "clients/detail.html",
        client=client,
        compagnie=compagnie_note(),
        policy_branches=POLICY_BRANCHES,
        policy_statuses=POLICY_STATUSES,
        payment_frequencies=PAYMENT_FREQUENCIES,
        payment_methods=PAYMENT_METHODS,
        document_categories=DOCUMENT_CATEGORIES,
        followup_types=FOLLOWUP_TYPES,
        followup_priorities=FOLLOWUP_PRIORITIES,
        claim_statuses=CLAIM_STATUSES,
        id_document_types=dict(ID_DOCUMENT_TYPES),
    )


@bp.route("/<int:client_id>/modifica", methods=["GET", "POST"])
def edit_client(client_id):
    client = db.get_or_404(Client, client_id)
    if request.method == "POST":
        _populate_from_form(client, request.form)
        errori = _valida(client)
        if errori:
            for e in errori:
                flash(e, "danger")
            risposta = _form(client, nuovo=False)
            db.session.rollback()
            return risposta, 400
        _avvisa_duplicati(client)
        audit("modifica", "cliente", client.id, f"Modificata l'anagrafica di «{client.ragione_sociale}»")
        db.session.commit()
        flash("Anagrafica aggiornata.", "success")
        return redirect(url_for("clients.detail", client_id=client.id))
    return _form(client, nuovo=False)


@bp.route("/<int:client_id>/elimina", methods=["POST"])
def delete_client(client_id):
    client = db.get_or_404(Client, client_id)
    nome = client.ragione_sociale
    if any(t.stato == "incassato" for p in client.polizze for t in p.titoli):
        flash(
            "Il cliente ha titoli incassati registrati: per non alterare la contabilità non può essere "
            "eliminato. Puoi disdire le sue polizze.",
            "danger",
        )
        return redirect(url_for("clients.detail", client_id=client.id))
    cartella = current_app.config["UPLOAD_FOLDER"]
    file_da_rimuovere = [os.path.join(cartella, d.filename) for d in client.documenti]
    audit("elimina", "cliente", client.id,
          f"Eliminato il cliente «{nome}» con {len(client.polizze)} polizze e {len(client.documenti)} documenti")
    db.session.delete(client)
    db.session.commit()
    for percorso in file_da_rimuovere:
        try:
            os.remove(percorso)
        except OSError:
            pass
    flash(f"Cliente «{nome}» eliminato con tutti i dati collegati.", "success")
    return redirect(url_for("clients.list_clients"))


# ----------------------------------------------------------------------
# Analisi automatica dei rischi
# ----------------------------------------------------------------------
@bp.route("/<int:client_id>/analisi", methods=["POST"])
def run_analysis(client_id):
    client = db.get_or_404(Client, client_id)
    testo = request.form.get("descrizione") or client.descrizione_attivita
    if not testo or not testo.strip():
        flash(
            "Inserisci prima una descrizione dell'attività per eseguire l'analisi dei rischi.",
            "warning",
        )
        return redirect(url_for("clients.detail", client_id=client.id))

    # Se la descrizione arriva dal form, aggiorniamo anche l'anagrafica.
    if request.form.get("descrizione"):
        client.descrizione_attivita = testo.strip()

    results = analyze_client(client, description=testo)
    analysis = RiskAnalysis(
        client_id=client.id,
        input_text=testo.strip(),
        results_json=json.dumps(results, ensure_ascii=False),
    )
    db.session.add(analysis)
    db.session.commit()
    flash(
        f"Analisi completata: {results['sintesi']['rischi_rilevati']} rischi rilevati, "
        f"{results['sintesi']['rami_scoperti']} coperture consigliate ancora scoperte.",
        "success",
    )
    return redirect(
        url_for("clients.view_analysis", client_id=client.id, analysis_id=analysis.id)
    )


@bp.route("/<int:client_id>/analisi/<int:analysis_id>")
def view_analysis(client_id, analysis_id):
    client = db.get_or_404(Client, client_id)
    analysis = db.get_or_404(RiskAnalysis, analysis_id)
    if analysis.client_id != client.id:
        abort(404)
    return render_template(
        "clients/analysis.html", client=client, analysis=analysis
    )


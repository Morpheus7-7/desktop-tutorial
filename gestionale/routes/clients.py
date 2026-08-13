"""Anagrafica clienti (professionisti e aziende) e analisi rischi."""
import json

from flask import (
    Blueprint,
    abort,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)

from ..models import (
    CLIENT_TYPES,
    DOCUMENT_CATEGORIES,
    FOLLOWUP_PRIORITIES,
    FOLLOWUP_TYPES,
    PAYMENT_FREQUENCIES,
    POLICY_BRANCHES,
    POLICY_STATUSES,
    Client,
    RiskAnalysis,
    db,
)
from ..risk_engine import analyze_client

bp = Blueprint("clients", __name__, url_prefix="/clienti")


def _int_or_none(value):
    try:
        return int(value) if value not in (None, "") else None
    except ValueError:
        return None


def _float_or_none(value):
    try:
        return float(value.replace(",", ".")) if value not in (None, "") else None
    except (ValueError, AttributeError):
        return None


def _populate_from_form(client: Client, form) -> None:
    client.tipo = form.get("tipo", "azienda")
    client.ragione_sociale = form.get("ragione_sociale", "").strip()
    client.referente = form.get("referente", "").strip() or None
    client.codice_fiscale = form.get("codice_fiscale", "").strip().upper() or None
    client.partita_iva = form.get("partita_iva", "").strip() or None
    client.codice_ateco = form.get("codice_ateco", "").strip() or None
    client.professione = form.get("professione", "").strip() or None
    client.datore_lavoro = form.get("datore_lavoro", "").strip() or None
    client.settore = form.get("settore", "").strip() or None
    client.indirizzo = form.get("indirizzo", "").strip() or None
    client.citta = form.get("citta", "").strip() or None
    client.cap = form.get("cap", "").strip() or None
    client.provincia = form.get("provincia", "").strip().upper() or None
    client.email = form.get("email", "").strip() or None
    client.pec = form.get("pec", "").strip() or None
    client.telefono = form.get("telefono", "").strip() or None
    client.numero_dipendenti = _int_or_none(form.get("numero_dipendenti"))
    client.fatturato_annuo = _float_or_none(form.get("fatturato_annuo"))
    client.descrizione_attivita = form.get("descrizione_attivita", "").strip() or None
    client.note = form.get("note", "").strip() or None


@bp.route("/")
def list_clients():
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
            )
        )
    if tipo in {t for t, _ in CLIENT_TYPES}:
        query = query.filter_by(tipo=tipo)
    clienti = query.order_by(Client.ragione_sociale.asc()).all()
    return render_template(
        "clients/list.html", clienti=clienti, q=q, tipo=tipo, client_types=CLIENT_TYPES
    )


@bp.route("/nuovo", methods=["GET", "POST"])
def new_client():
    if request.method == "POST":
        client = Client()
        _populate_from_form(client, request.form)
        if not client.ragione_sociale:
            flash("La ragione sociale / il nominativo è obbligatorio.", "danger")
        else:
            db.session.add(client)
            db.session.commit()
            flash(f"Cliente “{client.ragione_sociale}” creato.", "success")
            if request.form.get("analizza_subito") and client.descrizione_attivita:
                return redirect(
                    url_for("clients.run_analysis", client_id=client.id), code=307
                )
            return redirect(url_for("clients.detail", client_id=client.id))
    return render_template(
        "clients/form.html", client=None, client_types=CLIENT_TYPES
    )


@bp.route("/<int:client_id>")
def detail(client_id):
    client = db.get_or_404(Client, client_id)
    return render_template(
        "clients/detail.html",
        client=client,
        policy_branches=POLICY_BRANCHES,
        policy_statuses=POLICY_STATUSES,
        payment_frequencies=PAYMENT_FREQUENCIES,
        document_categories=DOCUMENT_CATEGORIES,
        followup_types=FOLLOWUP_TYPES,
        followup_priorities=FOLLOWUP_PRIORITIES,
    )


@bp.route("/<int:client_id>/modifica", methods=["GET", "POST"])
def edit_client(client_id):
    client = db.get_or_404(Client, client_id)
    if request.method == "POST":
        _populate_from_form(client, request.form)
        if not client.ragione_sociale:
            flash("La ragione sociale / il nominativo è obbligatorio.", "danger")
        else:
            db.session.commit()
            flash("Anagrafica aggiornata.", "success")
            return redirect(url_for("clients.detail", client_id=client.id))
    return render_template(
        "clients/form.html", client=client, client_types=CLIENT_TYPES
    )


@bp.route("/<int:client_id>/elimina", methods=["POST"])
def delete_client(client_id):
    client = db.get_or_404(Client, client_id)
    nome = client.ragione_sociale
    db.session.delete(client)
    db.session.commit()
    flash(f"Cliente “{nome}” eliminato con tutti i dati collegati.", "success")
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


@bp.route("/<int:client_id>/analisi-ai", methods=["POST"])
def run_ai_analysis(client_id):
    from ..ai_analysis import analizza_cliente_ai

    client = db.get_or_404(Client, client_id)
    testo = request.form.get("descrizione") or client.descrizione_attivita
    if not testo or not testo.strip():
        flash("Inserisci prima una descrizione dell'attività per l'analisi AI.", "warning")
        return redirect(url_for("clients.detail", client_id=client.id) + "#analisi")

    if request.form.get("descrizione"):
        client.descrizione_attivita = testo.strip()
        db.session.commit()

    try:
        results = analizza_cliente_ai(client, testo)
    except RuntimeError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("clients.detail", client_id=client.id) + "#analisi")

    analysis = RiskAnalysis(
        client_id=client.id,
        input_text=testo.strip(),
        results_json=json.dumps(results, ensure_ascii=False),
        fonte="ai",
    )
    db.session.add(analysis)
    db.session.commit()
    flash(
        f"Analisi AI completata ({results['sintesi']['rischi_rilevati']} rischi individuati).",
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
    template = "clients/analysis_ai.html" if analysis.is_ai else "clients/analysis.html"
    return render_template(template, client=client, analysis=analysis)

"""Anagrafica clienti (professionisti e aziende) e analisi rischi."""
import json
from datetime import date

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
    RUOLI_PERSONA,
    RUOLI_PERSONA_LABELS,
    SEZIONI_NOTE,
    RUOLI_SOCIETARI,
    STATI_CIVILI,
    Client,
    PersonaCollegata,
    RiskAnalysis,
    db,
)
from .. import diario
from ..risk_engine import analyze_client
from ..academy import get_scheda
from ..schede import SCHEDE_CLIENTE

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


def _date_or_none(value):
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def _testo(form, campo, maiuscolo=False):
    valore = (form.get(campo) or "").strip()
    return (valore.upper() if maiuscolo else valore) or None


def _populate_from_form(client: Client, form) -> None:
    client.tipo = form.get("tipo", "azienda")
    client.ragione_sociale = form.get("ragione_sociale", "").strip()
    if client.tipo in ("professionista", "dipendente"):
        client.nome = _testo(form, "nome")
        client.cognome = _testo(form, "cognome")
        if client.nome or client.cognome:
            # Per le persone il nominativo è sempre «Nome Cognome».
            client.ragione_sociale = " ".join(x for x in (client.nome, client.cognome) if x)
        client.data_nascita = _date_or_none(form.get("data_nascita"))
        client.luogo_nascita = _testo(form, "luogo_nascita")
        client.stato_civile = _testo(form, "stato_civile")
        client.nucleo_familiare = _testo(form, "nucleo_familiare")
        client.interessi = _testo(form, "interessi")
        client.residenza_indirizzo = _testo(form, "residenza_indirizzo")
        client.residenza_citta = _testo(form, "residenza_citta")
        client.residenza_cap = _testo(form, "residenza_cap")
        client.residenza_provincia = _testo(form, "residenza_provincia", maiuscolo=True)
    if client.tipo == "professionista":
        client.albo = _testo(form, "albo")
        client.albo_provincia = _testo(form, "albo_provincia")
        client.albo_numero = _testo(form, "albo_numero")
        client.albo_data_iscrizione = _date_or_none(form.get("albo_data_iscrizione"))
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


def _persona_cercata(like):
    """Un'azienda si trova anche cercando il nome di un amministratore."""
    completo = db.func.coalesce(PersonaCollegata.nome, "") + " " + PersonaCollegata.cognome
    return db.or_(completo.ilike(like), PersonaCollegata.cognome.ilike(like),
                  PersonaCollegata.codice_fiscale.ilike(like))


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
                Client.persone.any(_persona_cercata(like)),
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
        "clients/form.html", client=None, client_types=CLIENT_TYPES, stati_civili=STATI_CIVILI
    )


@bp.route("/<int:client_id>")
def detail(client_id):
    client = db.get_or_404(Client, client_id)
    aperti = [f for f in client.followups if f.stato == "aperto"]
    prossimo_followup = min(aperti, key=lambda f: f.data_scadenza) if aperti else None
    return render_template(
        "clients/detail.html",
        client=client,
        prossimo_followup=prossimo_followup,
        schede_cliente=[get_scheda(i) for i in SCHEDE_CLIENTE],
        policy_branches=POLICY_BRANCHES,
        policy_statuses=POLICY_STATUSES,
        payment_frequencies=PAYMENT_FREQUENCIES,
        document_categories=DOCUMENT_CATEGORIES,
        followup_types=FOLLOWUP_TYPES,
        followup_priorities=FOLLOWUP_PRIORITIES,
        ruoli=RUOLI_PERSONA,
        ruoli_societari=RUOLI_SOCIETARI,
        sezioni_note=SEZIONI_NOTE,
        email_pronta=diario.destinatari_configurati(),
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
        "clients/form.html", client=client, client_types=CLIENT_TYPES, stati_civili=STATI_CIVILI
    )


# ----------------------------------------------------------------------
# Persone collegate: amministratori, consiglieri, soci, familiari…
# ----------------------------------------------------------------------
def _persona_or_404(client_id: int, persona_id: int) -> PersonaCollegata:
    persona = db.get_or_404(PersonaCollegata, persona_id)
    if persona.client_id != client_id:
        abort(404)
    return persona


def _compila_persona(p: PersonaCollegata, form) -> str | None:
    """Riempie la persona dal modulo; restituisce un errore o None."""
    ruolo = form.get("ruolo", "altro")
    p.ruolo = ruolo if ruolo in RUOLI_PERSONA_LABELS else "altro"
    p.ruolo_altro = _testo(form, "ruolo_altro") if p.ruolo == "altro" else None
    p.nome = _testo(form, "nome")
    p.cognome = _testo(form, "cognome")
    p.codice_fiscale = _testo(form, "codice_fiscale", maiuscolo=True)
    p.data_nascita = _date_or_none(form.get("data_nascita"))
    p.luogo_nascita = _testo(form, "luogo_nascita")
    p.indirizzo = _testo(form, "indirizzo")
    p.citta = _testo(form, "citta")
    p.cap = _testo(form, "cap")
    p.provincia = _testo(form, "provincia", maiuscolo=True)
    p.email = _testo(form, "email")
    p.telefono = _testo(form, "telefono")
    p.quota_perc = _float_or_none(form.get("quota_perc"))
    p.dal = _date_or_none(form.get("dal"))
    p.note = _testo(form, "note")
    if not p.cognome:
        return "Il cognome è obbligatorio."
    if p.quota_perc is not None and not 0 <= p.quota_perc <= 100:
        return "La quota deve essere una percentuale tra 0 e 100."
    return None


@bp.route("/<int:client_id>/persone/nuova", methods=["GET", "POST"])
def new_person(client_id):
    client = db.get_or_404(Client, client_id)
    persona = PersonaCollegata(client_id=client.id, ruolo=request.args.get("ruolo", "amministratore_unico"))
    if persona.ruolo not in RUOLI_PERSONA_LABELS:
        persona.ruolo = "altro"
    if request.method == "POST":
        errore = _compila_persona(persona, request.form)
        if errore:
            flash(errore, "danger")
        else:
            db.session.add(persona)
            db.session.commit()
            flash(f"{persona.ruolo_label} «{persona.nome_completo}» aggiunto.", "success")
            return redirect(url_for("clients.detail", client_id=client.id) + "#persone")
    return render_template("clients/persona_form.html", client=client, persona=persona, ruoli=RUOLI_PERSONA)


@bp.route("/<int:client_id>/persone/<int:persona_id>/modifica", methods=["GET", "POST"])
def edit_person(client_id, persona_id):
    client = db.get_or_404(Client, client_id)
    persona = _persona_or_404(client_id, persona_id)
    if request.method == "POST":
        errore = _compila_persona(persona, request.form)
        if errore:
            flash(errore, "danger")
        else:
            db.session.commit()
            flash("Dati aggiornati.", "success")
            return redirect(url_for("clients.detail", client_id=client.id) + "#persone")
    return render_template("clients/persona_form.html", client=client, persona=persona, ruoli=RUOLI_PERSONA)


@bp.route("/<int:client_id>/persone/<int:persona_id>/elimina", methods=["POST"])
def delete_person(client_id, persona_id):
    persona = _persona_or_404(client_id, persona_id)
    db.session.delete(persona)
    db.session.commit()
    flash(f"«{persona.nome_completo}» rimosso.", "success")
    return redirect(url_for("clients.detail", client_id=client_id) + "#persone")


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


@bp.route("/<int:client_id>/analisi/<int:analysis_id>")
def view_analysis(client_id, analysis_id):
    client = db.get_or_404(Client, client_id)
    analysis = db.get_or_404(RiskAnalysis, analysis_id)
    if analysis.client_id != client.id:
        abort(404)
    return render_template(
        "clients/analysis.html", client=client, analysis=analysis
    )

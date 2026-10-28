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


def _aziende(escludi: int | None = None):
    query = Client.query.filter(Client.tipo == "azienda")
    if escludi:
        query = query.filter(Client.id != escludi)
    return query.order_by(Client.ragione_sociale).all()


def _datore_collegato(client: Client | None) -> PersonaCollegata | None:
    if client is None or client.id is None:
        return None
    return next((r for r in client.ruoli_in_aziende if r.ruolo == "dipendente"), None)


def _copia_anagrafica(p: PersonaCollegata, c: Client) -> None:
    """Tiene nella persona una copia di nome e codice fiscale del cliente
    privato collegato: serve alla ricerca («trova l'azienda dal nome»)."""
    p.nome, p.cognome = c.nome, c.cognome or c.ragione_sociale
    p.codice_fiscale = c.codice_fiscale


def _aggiorna_datore(client: Client, form) -> None:
    """Dipendente: collega il cliente all'azienda scelta tra i clienti."""
    if "datore_lavoro_id" not in form:
        return
    azienda = None
    scelta = form.get("datore_lavoro_id", type=int)
    if client.tipo == "dipendente" and scelta:
        azienda = db.session.get(Client, scelta)
        if azienda is None or azienda.tipo != "azienda" or azienda.id == client.id:
            azienda = None
    attuale = _datore_collegato(client)
    if attuale is not None and (azienda is None or attuale.client_id != azienda.id):
        db.session.delete(attuale)
    if azienda is not None:
        if attuale is None or attuale.client_id != azienda.id:
            p = PersonaCollegata(client_id=azienda.id, persona_client_id=client.id, ruolo="dipendente")
            _copia_anagrafica(p, client)
            db.session.add(p)
        client.datore_lavoro = azienda.ragione_sociale


@bp.route("/nuovo", methods=["GET", "POST"])
def new_client():
    if request.method == "POST":
        client = Client()
        _populate_from_form(client, request.form)
        if not client.ragione_sociale:
            flash("La ragione sociale / il nominativo è obbligatorio.", "danger")
        else:
            db.session.add(client)
            db.session.flush()
            _aggiorna_datore(client, request.form)
            db.session.commit()
            flash(f"Cliente “{client.ragione_sociale}” creato.", "success")
            if request.form.get("analizza_subito") and client.descrizione_attivita:
                return redirect(
                    url_for("clients.run_analysis", client_id=client.id), code=307
                )
            return redirect(url_for("clients.detail", client_id=client.id))
    return render_template(
        "clients/form.html", client=None, client_types=CLIENT_TYPES, stati_civili=STATI_CIVILI,
        aziende=_aziende(), datore=None,
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
        suggerimenti={p.id: s for p in client.persone if (s := _cliente_privato_esistente(p, client.id))},
    )


@bp.route("/<int:client_id>/modifica", methods=["GET", "POST"])
def edit_client(client_id):
    client = db.get_or_404(Client, client_id)
    if request.method == "POST":
        _populate_from_form(client, request.form)
        if not client.ragione_sociale:
            flash("La ragione sociale / il nominativo è obbligatorio.", "danger")
        else:
            _aggiorna_datore(client, request.form)
            for ruolo in client.ruoli_in_aziende:
                _copia_anagrafica(ruolo, client)
            db.session.commit()
            flash("Anagrafica aggiornata.", "success")
            return redirect(url_for("clients.detail", client_id=client.id))
    return render_template(
        "clients/form.html", client=client, client_types=CLIENT_TYPES, stati_civili=STATI_CIVILI,
        aziende=_aziende(escludi=client.id), datore=_datore_collegato(client),
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
    p.quota_perc = _float_or_none(form.get("quota_perc"))
    p.dal = _date_or_none(form.get("dal"))
    p.note = _testo(form, "note")
    if p.quota_perc is not None and not 0 <= p.quota_perc <= 100:
        return "La quota deve essere una percentuale tra 0 e 100."
    if p.persona_client_id:
        return None  # l'anagrafica si modifica nella scheda privata
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
    if not p.cognome:
        return "Il cognome è obbligatorio."
    return None


def _cliente_privato_esistente(p: PersonaCollegata, escludi: int) -> Client | None:
    """Un cliente privato che sembra la stessa persona (stesso codice fiscale
    o, senza codice fiscale, stesso nome e cognome)."""
    if p.persona_client_id:
        return None
    persone = Client.query.filter(Client.tipo.in_(("dipendente", "professionista")), Client.id != escludi)
    if p.codice_fiscale:
        return persone.filter(db.func.upper(Client.codice_fiscale) == p.codice_fiscale.upper()).first()
    if p.cognome:
        nome = " ".join(x for x in (p.nome, p.cognome) if x).lower()
        return persone.filter(db.func.lower(Client.ragione_sociale) == nome).first()
    return None


@bp.route("/<int:client_id>/persone/<int:persona_id>/scheda-privata", methods=["POST"])
def person_to_client(client_id, persona_id):
    """Gestire l'amministratore (o il dipendente…) anche come cliente privato."""
    azienda = db.get_or_404(Client, client_id)
    p = _persona_or_404(client_id, persona_id)
    if p.persona_cliente is not None:
        return redirect(url_for("clients.detail", client_id=p.persona_client_id))
    privato = _cliente_privato_esistente(p, client_id)
    if privato is None:
        privato = Client(
            tipo="dipendente", nome=p.nome, cognome=p.cognome, ragione_sociale=p.nome_completo,
            codice_fiscale=p.codice_fiscale, data_nascita=p.data_nascita, luogo_nascita=p.luogo_nascita,
            indirizzo=p.indirizzo, citta=p.citta, cap=p.cap, provincia=p.provincia,
            email=p.email, telefono=p.telefono,
            datore_lavoro=azienda.ragione_sociale if p.ruolo == "dipendente" else None,
        )
        db.session.add(privato)
        db.session.flush()
        messaggio = f"Creata la scheda di cliente privato di {privato.ragione_sociale}"
    else:
        messaggio = f"Collegato alla scheda già esistente di {privato.ragione_sociale}"
    p.persona_client_id = privato.id
    db.session.commit()
    flash(f"{messaggio}: {p.ruolo_label.lower()} di {azienda.ragione_sociale}.", "success")
    return redirect(url_for("clients.detail", client_id=privato.id) + "#persone")


@bp.route("/<int:client_id>/persone/<int:persona_id>/collega", methods=["POST"])
def link_person(client_id, persona_id):
    p = _persona_or_404(client_id, persona_id)
    scelta = request.form.get("persona_client_id", type=int)
    if scelta:
        privato = db.session.get(Client, scelta)
        if privato is None or not privato.persona_fisica or privato.id == client_id:
            abort(400)
        p.persona_client_id = privato.id
        _copia_anagrafica(p, privato)
        flash(f"{p.nome_completo} collegato alla sua scheda di cliente privato.", "success")
    else:
        # Scollegando, la persona conserva i dati attuali della scheda privata.
        privato = p.persona_cliente
        if privato is not None:
            for campo in ("nome", "cognome", "codice_fiscale", "data_nascita", "luogo_nascita", "indirizzo",
                          "citta", "cap", "provincia", "email", "telefono"):
                setattr(p, campo, p.dato(campo))
        p.persona_client_id = None
        flash("Collegamento alla scheda privata rimosso.", "success")
    db.session.commit()
    return redirect(url_for("clients.detail", client_id=client_id) + "#persone")


@bp.route("/<int:client_id>/ruoli/nuovo", methods=["GET", "POST"])
def new_role(client_id):
    """Dalla scheda di un privato: «è amministratore / socio / dipendente di…»."""
    privato = db.get_or_404(Client, client_id)
    if not privato.persona_fisica:
        abort(404)
    ruolo = request.values.get("ruolo", "amministratore_unico")
    p = PersonaCollegata(persona_client_id=privato.id, ruolo=ruolo if ruolo in RUOLI_PERSONA_LABELS else "altro")
    if request.method == "POST":
        azienda = db.session.get(Client, request.form.get("azienda_id", type=int) or 0)
        errore = _compila_persona(p, request.form)
        if azienda is None or azienda.id == privato.id:
            errore = "Scegli l'azienda."
        if errore:
            flash(errore, "danger")
        else:
            p.client_id = azienda.id
            _copia_anagrafica(p, privato)
            db.session.add(p)
            if p.ruolo == "dipendente" and privato.tipo == "dipendente":
                privato.datore_lavoro = azienda.ragione_sociale
            db.session.commit()
            flash(f"{privato.nome_completo}: {p.ruolo_label.lower()} di {azienda.ragione_sociale}.", "success")
            return redirect(url_for("clients.detail", client_id=privato.id) + "#persone")
    return render_template("clients/ruolo_form.html", privato=privato, persona=p, ruoli=RUOLI_PERSONA,
                           aziende=_aziende(escludi=privato.id))


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
    # Se era amministratore o dipendente di aziende clienti, lì resta con i
    # suoi dati (copiati prima di eliminare la scheda privata).
    for ruolo in client.ruoli_in_aziende:
        for campo in ("nome", "cognome", "codice_fiscale", "data_nascita", "luogo_nascita", "indirizzo",
                      "citta", "cap", "provincia", "email", "telefono"):
            setattr(ruolo, campo, ruolo.dato(campo))
        ruolo.cognome = ruolo.cognome or nome
        ruolo.persona_client_id = None
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

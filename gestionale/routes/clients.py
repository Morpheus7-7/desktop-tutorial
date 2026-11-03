"""Anagrafica clienti (aziende, studi, professionisti, dipendenti, privati) e analisi rischi."""
import json
import os
from datetime import date, timedelta

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
from werkzeug.security import safe_join

from ..export import csv_response
from ..models import (
    CAMPI_PER_TIPO,
    CAMPI_PERSONA,
    CLAIM_STATUSES,
    CLIENT_TYPE_DESCRIZIONI,
    CLIENT_TYPES,
    DOCUMENT_CATEGORIES,
    FOLLOWUP_PRIORITIES,
    FOLLOWUP_TYPES,
    ID_DOCUMENT_TYPES,
    PAYMENT_FREQUENCIES,
    PAYMENT_METHODS,
    POLICY_BRANCHES,
    POLICY_STATUSES,
    RUOLI_PERSONA,
    RUOLI_PERSONA_LABELS,
    SEZIONI_NOTE,
    RUOLI_SOCIETARI,
    STATI_CIVILI,
    TIPI_PERSONA_FISICA,
    Client,
    PersonaCollegata,
    RiskAnalysis,
    db,
)
from ..backup import cartella_documenti
from ..notifications import elimina_notifiche
from ..professioni import (
    AREE,
    CONDIZIONI_PRIVATO,
    FORME_GIURIDICHE,
    INQUADRAMENTI,
    PROFESSIONI,
    PROFESSIONI_GENERICHE,
    info_professione,
    normalizza,
    separa_voci,
    trova_professione,
    unisci_voci,
)
from ..risk_engine import analyze_client
from ..security import audit
from ..utils import DATA_MIN, clean, leggi_data, leggi_importo, paginate, parse_int, plurale
from ..validators import (
    data_nascita_da_cf,
    valida_cap,
    valida_codice_fiscale,
    valida_email,
    valida_partita_iva,
    valida_provincia,
)
from .. import diario
from ..academy import get_scheda
from ..schede import SCHEDE_CLIENTE

bp = Blueprint("clients", __name__, url_prefix="/clienti")


def _testo(form, nome: str, lunghezza: int | None = None, upper: bool = False,
           maiuscolo: bool = False) -> str | None:
    """Testo ripulito e (se indicata) limitato alla lunghezza della colonna."""
    valore = clean(form, nome, upper=upper or maiuscolo)
    if not valore:
        return None
    return (valore[:lunghezza].strip() if lunghezza else valore) or None


def _date_or_none(value):
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def _float_or_none(value):
    """Importi anche all'italiana: «1.250,50», «€ 900», «12%»."""
    from ..import_excel import _numero

    try:
        return _numero(value.strip() if isinstance(value, str) else value)
    except (ValueError, TypeError):
        return None


def _populate_from_form(client: Client, form) -> list[str]:
    """Copia i campi del form nel cliente e restituisce gli errori su date e importi."""
    errori: list[str] = []
    oggi = date.today()
    tipo = form.get("tipo")
    client.tipo = tipo if tipo in dict(CLIENT_TYPES) else "azienda"
    client.ragione_sociale = (form.get("ragione_sociale") or "").strip()
    if client.tipo in TIPI_PERSONA_FISICA:
        client.nome = _testo(form, "nome", 80)
        client.cognome = _testo(form, "cognome", 80)
        if client.nome or client.cognome:
            # Per le persone il nominativo è sempre «Nome Cognome».
            client.ragione_sociale = " ".join(x for x in (client.nome, client.cognome) if x)
        client.luogo_nascita = _testo(form, "luogo_nascita", 100)
        stato_civile = form.get("stato_civile") or None
        client.stato_civile = stato_civile if stato_civile in STATI_CIVILI else None
        client.nucleo_familiare = clean(form, "nucleo_familiare")
        client.interessi = clean(form, "interessi")
        client.residenza_indirizzo = _testo(form, "residenza_indirizzo", 200)
        client.residenza_citta = _testo(form, "residenza_citta", 100)
        client.residenza_cap = _testo(form, "residenza_cap", 5)
        client.residenza_provincia = _testo(form, "residenza_provincia", 2, upper=True)
    else:
        for campo in CAMPI_PERSONA:
            setattr(client, campo, None)
    client.referente = _testo(form, "referente", 120)
    client.codice_fiscale = (clean(form, "codice_fiscale", upper=True) or "").replace(" ", "") or None
    client.partita_iva = (clean(form, "partita_iva") or "").replace(" ", "").upper().removeprefix("IT") or None
    client.codice_ateco = clean(form, "codice_ateco")
    # Campi con un nome per tipo (mansione del dipendente, condizione del
    # privato…): senza JavaScript il modulo li invia tutti e conta quello del tipo.
    forma = form.get("forma_giuridica_studio" if client.tipo == "studio" else "forma_giuridica")
    if forma is None:
        forma = form.get("forma_giuridica")
    client.forma_giuridica = forma if forma in FORME_GIURIDICHE.get(client.tipo, ()) else None
    nome_professione = {"dipendente": "mansione", "privato": "condizione"}.get(client.tipo, "professione")
    client.professione = _testo(form, nome_professione if nome_professione in form else "professione", 120)
    client.specializzazioni = unisci_voci(form.getlist("specializzazioni"), form.get("specializzazioni_altre"))
    client.attivita_svolte = unisci_voci(form.getlist("attivita_svolte"), form.get("attivita_altre"))
    client.albo = _testo(form, "albo", 150)
    client.albo_numero = _testo(form, "albo_numero", 40, upper=True)
    client.albo_provincia = _testo(form, "albo_provincia", 60)
    inquadramento = form.get("inquadramento")
    client.inquadramento = inquadramento if inquadramento in dict(INQUADRAMENTI) else None
    client.datore_lavoro = _testo(form, "datore_lavoro", 200)
    nome_settore = "settore_dipendente" if client.tipo == "dipendente" and "settore_dipendente" in form else "settore"
    client.settore = _testo(form, nome_settore, 120)
    client.indirizzo = clean(form, "indirizzo")
    client.citta = clean(form, "citta")
    client.cap = clean(form, "cap")
    client.provincia = clean(form, "provincia", upper=True)
    client.email = clean(form, "email")
    client.pec = clean(form, "pec")
    client.telefono = clean(form, "telefono")
    dipendenti = (form.get("numero_dipendenti") or "").strip()
    client.numero_dipendenti = parse_int(dipendenti, minimo=0, massimo=1_000_000)
    if dipendenti and client.numero_dipendenti is None:
        errori.append("Numero dipendenti: indica un numero intero non negativo.")
    professionisti = (form.get("numero_professionisti") or "").strip()
    client.numero_professionisti = parse_int(professionisti, minimo=1, massimo=100_000)
    if professionisti and client.numero_professionisti is None:
        errori.append("Professionisti dello studio: indica un numero intero di almeno 1.")
    etichetta_fatturato = "Volume d'affari" if client.tipo == "professionista" else "Fatturato annuo"
    client.fatturato_annuo = leggi_importo(form, "fatturato_annuo", etichetta_fatturato, errori, minimo=0)
    client.descrizione_attivita = clean(form, "descrizione_attivita")
    client.note = clean(form, "note")
    # Compliance: date nel passato (nascita, consenso, questionario) e una
    # scadenza del documento entro un orizzonte plausibile.
    futura = "non può essere una data futura."
    client.data_nascita = leggi_data(
        form, "data_nascita", "Data di nascita", errori, minimo=DATA_MIN, massimo=oggi,
        msg_massimo=f"Data di nascita: {futura}",
    )
    client.albo_data_iscrizione = leggi_data(
        form, "albo_data_iscrizione", "Data di iscrizione all'albo", errori, massimo=oggi,
        msg_massimo=f"Data di iscrizione all'albo: {futura}",
    )
    client.data_consenso_privacy = leggi_data(
        form, "data_consenso_privacy", "Consenso privacy", errori, massimo=oggi,
        msg_massimo=f"Consenso privacy: {futura}",
    )
    client.consenso_marketing = bool(form.get("consenso_marketing"))
    client.data_adeguatezza = leggi_data(
        form, "data_adeguatezza", "Questionario di adeguatezza", errori, massimo=oggi,
        msg_massimo=f"Questionario di adeguatezza: {futura}",
    )
    documento_tipo = form.get("documento_tipo")
    client.documento_tipo = documento_tipo if documento_tipo in dict(ID_DOCUMENT_TYPES) else None
    client.documento_numero = clean(form, "documento_numero", upper=True)
    client.documento_scadenza = leggi_data(
        form, "documento_scadenza", "Scadenza documento", errori,
        massimo=oggi + timedelta(days=365 * 20),
        msg_massimo="Scadenza documento: oltre 20 anni da oggi, controlla la data.",
    )
    studio_id = (form.get("studio_id") or "").strip()
    client.studio_id = parse_int(studio_id, minimo=1)
    if studio_id and client.studio_id is None:
        errori.append("Studio di appartenenza non valido.")
    # Campi non pertinenti al tipo di cliente (nascosti nel modulo): un libero
    # professionista non ha dipendenti né ragione sociale, un privato non ha
    # partita IVA, e così via.
    for campo, tipi in CAMPI_PER_TIPO.items():
        if client.tipo not in tipi:
            setattr(client, campo, None)
    if client.persona_fisica and not client.data_nascita:
        client.data_nascita = data_nascita_da_cf(client.codice_fiscale)
    return errori


def _valida(client: Client, errori: list[str] | None = None) -> list[str]:
    errori = list(errori or [])
    if not client.ragione_sociale:
        errori.append(
            "Il nome e cognome è obbligatorio." if client.persona_fisica
            else "La denominazione dello studio è obbligatoria." if client.tipo == "studio"
            else "La ragione sociale è obbligatoria."
        )
    if client.tipo in ("professionista", "studio") and not client.professione:
        errori.append(
            "Indica la professione del libero professionista (es. Avvocato, Pediatra)."
            if client.tipo == "professionista"
            else "Indica la professione esercitata dallo studio (es. Avvocato, Pediatra)."
        )
    if client.studio_id is not None:
        studio = db.session.get(Client, client.studio_id)
        if studio is None or studio.tipo != "studio" or (client.id and studio.id == client.id):
            errori.append("Studio di appartenenza non valido: scegli uno studio tra i clienti.")
    if (client.albo_data_iscrizione and client.data_nascita
            and client.albo_data_iscrizione <= client.data_nascita):
        errori.append("La data di iscrizione all'albo è precedente alla data di nascita: controlla le date.")
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
    professione = trova_professione(client.professione) if client.tipo in ("studio", "professionista") else None
    voci = {}
    for campo, testo in (("specializzazioni", client.specializzazioni), ("attivita", client.attivita_svolte)):
        catalogo = getattr(professione, "specializzazioni" if campo == "specializzazioni" else "attivita", ())
        voci[campo] = separa_voci(testo, catalogo)
    studi = (
        Client.query.filter(Client.tipo == "studio", Client.id != (client.id or 0))
        .order_by(Client.ragione_sociale).all()
    )
    # Catalogo per lo script del modulo: riconosce la professione mentre la si
    # scrive, con le stesse regole del server (alias già normalizzati).
    catalogo_js = [
        {
            "chiave": p.chiave,
            "area": p.area,
            "alias_generici": list(PROFESSIONI_GENERICHE.get(p.chiave, {}).get("alias", ())),
            "cede_a": list(PROFESSIONI_GENERICHE.get(p.chiave, {}).get("cede_a", ())),
            "alias": [normalizza(a) for a in (p.nome, *p.alias)],
            "albo": p.albo,
            "info": info_professione(p),
        }
        for p in PROFESSIONI
    ]
    return render_template(
        "clients/form.html",
        client=client,
        nuovo=nuovo,
        client_types=CLIENT_TYPES,
        descrizioni_tipo=CLIENT_TYPE_DESCRIZIONI,
        campi_tipo=CAMPI_PER_TIPO,
        id_document_types=ID_DOCUMENT_TYPES,
        professioni=PROFESSIONI,
        aree=AREE,
        professione_riconosciuta=professione,
        info_professione=info_professione(professione) if professione else "",
        catalogo_js=catalogo_js,
        voci=voci,
        forme_giuridiche=FORME_GIURIDICHE,
        inquadramenti=INQUADRAMENTI,
        condizioni_privato=CONDIZIONI_PRIVATO,
        studi=studi,
        stati_civili=STATI_CIVILI,
        aziende=_aziende(escludi=client.id),
        datore=_datore_collegato(client),
        ruoli=RUOLI_PERSONA,
    )


def _persona_cercata(like):
    """Un'azienda si trova anche cercando il nome di un amministratore."""
    completo = db.func.coalesce(PersonaCollegata.nome, "") + " " + PersonaCollegata.cognome
    return db.or_(completo.ilike(like), PersonaCollegata.cognome.ilike(like),
                  PersonaCollegata.codice_fiscale.ilike(like))


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
                Client.professione.ilike(like),
                Client.specializzazioni.ilike(like),
                Client.referente.ilike(like),
                Client.email.ilike(like),
                Client.nome.ilike(like),
                Client.cognome.ilike(like),
                Client.persone.any(_persona_cercata(like)),
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
        ["Ragione sociale / Nominativo", "Tipo", "Forma giuridica", "Referente", "Partita IVA",
         "Codice fiscale", "Codice ATECO", "Professione / Mansione / Condizione", "Specializzazioni",
         "Attività svolte", "Inquadramento", "Albo / Ordine", "N. iscrizione albo", "Iscritto dal",
         "Studio di appartenenza", "Professionisti dello studio", "Datore di lavoro", "Settore",
         "Indirizzo", "CAP", "Città", "Provincia", "Email", "PEC", "Telefono", "Dipendenti",
         "Fatturato / volume d'affari", "Data di nascita", "Consenso privacy", "Consenso marketing",
         "Questionario adeguatezza", "Scadenza documento", "Polizze attive", "Premi attivi"],
        [
            (c.ragione_sociale, c.tipo_label, c.forma_giuridica, c.referente, c.partita_iva,
             c.codice_fiscale, c.codice_ateco, c.professione, c.specializzazioni, c.attivita_svolte,
             c.inquadramento_label, c.albo, c.albo_numero, c.albo_data_iscrizione,
             c.studio.ragione_sociale if c.studio else None, c.numero_professionisti,
             c.datore_lavoro, c.settore, c.indirizzo, c.cap, c.citta, c.provincia, c.email, c.pec,
             c.telefono, c.numero_dipendenti, c.fatturato_annuo, c.data_nascita,
             c.data_consenso_privacy, c.consenso_marketing, c.data_adeguatezza,
             c.documento_scadenza, len(c.polizze_attive), c.premi_attivi)
            for c in clienti
        ],
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


def _aggiungi_persone(client: Client, form) -> int:
    """Righe «amministratore / familiare» compilate nel modulo del cliente.
    Le righe senza cognome si ignorano. Restituisce quante ne ha aggiunte."""
    colonne = [form.getlist(k) for k in ("persona_ruolo", "persona_nome", "persona_cognome", "persona_cf",
                                          "persona_telefono")]
    aggiunte = 0
    for ruolo, nome, cognome, cf, telefono in zip(*colonne):
        cognome = cognome.strip()[:80]
        if not cognome:
            continue
        db.session.add(PersonaCollegata(
            client_id=client.id, ruolo=ruolo if ruolo in RUOLI_PERSONA_LABELS else "altro",
            nome=nome.strip()[:80] or None, cognome=cognome, codice_fiscale=cf.strip().upper()[:16] or None,
            telefono=telefono.strip()[:30] or None,
        ))
        aggiunte += 1
    return aggiunte


@bp.route("/nuovo", methods=["GET", "POST"])
def new_client():
    client = Client(tipo=request.args.get("tipo") if request.args.get("tipo") in dict(CLIENT_TYPES) else "azienda")
    # «Aggiungi professionista» dalla scheda di uno studio.
    studio = db.session.get(Client, parse_int(request.args.get("studio"), minimo=1) or 0)
    if studio is not None and studio.tipo == "studio" and client.tipo == "professionista":
        client.studio_id = studio.id
        client.professione = studio.professione
    if request.method == "POST":
        errori = _valida(client, _populate_from_form(client, request.form))
        if errori:
            for e in errori:
                flash(e, "danger")
            return _form(client, nuovo=True), 400
        _avvisa_duplicati(client)
        db.session.add(client)
        db.session.flush()
        _aggiorna_datore(client, request.form)
        persone = _aggiungi_persone(client, request.form)
        audit("crea", "cliente", client.id, f"Nuovo cliente «{client.ragione_sociale}» ({client.tipo_label})")
        db.session.commit()
        flash(f"Cliente «{client.ragione_sociale}» creato"
              + (f" con {persone} {'persona collegata' if persone == 1 else 'persone collegate'}." if persone else "."),
              "success")
        if request.form.get("analizza_subito") and client.descrizione_attivita:
            return redirect(url_for("clients.run_analysis", client_id=client.id), code=307)
        return redirect(url_for("clients.detail", client_id=client.id) + ("#persone" if persone else ""))
    return _form(client, nuovo=True)


@bp.route("/<int:client_id>")
def detail(client_id):
    return render_detail(db.get_or_404(Client, client_id))


def render_detail(client: Client, form_polizza=None):
    """Scheda cliente; ``form_polizza`` ripresenta i dati di una polizza non salvata."""
    from .policies import compagnie_note

    aperti = [f for f in client.followups if f.stato == "aperto"]
    return render_template(
        "clients/detail.html",
        client=client,
        form_polizza=form_polizza,
        compagnie=compagnie_note(),
        prossimo_followup=min(aperti, key=lambda f: f.data_scadenza) if aperti else None,
        schede_cliente=[get_scheda(i) for i in SCHEDE_CLIENTE],
        policy_branches=POLICY_BRANCHES,
        policy_statuses=POLICY_STATUSES,
        payment_frequencies=PAYMENT_FREQUENCIES,
        payment_methods=PAYMENT_METHODS,
        document_categories=DOCUMENT_CATEGORIES,
        followup_types=FOLLOWUP_TYPES,
        followup_priorities=FOLLOWUP_PRIORITIES,
        claim_statuses=CLAIM_STATUSES,
        id_document_types=dict(ID_DOCUMENT_TYPES),
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
        era_studio = client.tipo == "studio"
        with db.session.no_autoflush:
            errori = _valida(client, _populate_from_form(client, request.form))
            if errori:
                for e in errori:
                    flash(e, "danger")
                risposta = _form(client, nuovo=False)
        if errori:
            db.session.rollback()
            return risposta, 400
        _avvisa_duplicati(client)
        if era_studio and client.tipo != "studio" and client.professionisti:
            scollegati = len(client.professionisti)
            for professionista in list(client.professionisti):
                professionista.studio_id = None
            flash(
                f"«{client.ragione_sociale}» non è più uno studio: "
                f"{plurale(scollegati, 'professionista scollegato', 'professionisti scollegati')}.",
                "info",
            )
        _aggiorna_datore(client, request.form)
        _aggiungi_persone(client, request.form)
        for ruolo in client.ruoli_in_aziende:
            _copia_anagrafica(ruolo, client)
        audit("modifica", "cliente", client.id, f"Modificata l'anagrafica di «{client.ragione_sociale}»")
        db.session.commit()
        flash("Anagrafica aggiornata.", "success")
        return redirect(url_for("clients.detail", client_id=client.id))
    return _form(client, nuovo=False)


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
    persone = Client.query.filter(Client.tipo.in_(TIPI_PERSONA_FISICA), Client.id != escludi)
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
            tipo="dipendente" if p.ruolo == "dipendente" else "privato", nome=p.nome, cognome=p.cognome, ragione_sociale=p.nome_completo,
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
    if any(t.stato == "incassato" for p in client.polizze for t in p.titoli):
        flash(
            "Il cliente ha titoli incassati registrati: per non alterare la contabilità non può essere "
            "eliminato. Puoi disdire le sue polizze.",
            "danger",
        )
        return redirect(url_for("clients.detail", client_id=client.id))
    cartella = cartella_documenti()
    file_da_rimuovere = [p for p in (safe_join(cartella, d.filename) for d in client.documenti) if p]
    prefissi = [f"cliente:{client.id}:"]
    for p in client.polizze:
        prefissi += [f"polizza:{p.id}:", f"disdetta:{p.id}:", f"decorrenza:{p.id}:"]
        prefissi += [f"automatismo:{tipo}:{p.id}:" for tipo in ("tacito", "quietanze", "chiusura")]
        prefissi += [f"titolo:{t.id}:" for t in p.titoli]
    prefissi += [f"sinistro:{s.id}:" for s in client.sinistri]
    prefissi += [f"followup:{f.id}:" for f in client.followups]
    elimina_notifiche(*prefissi)
    audit("elimina", "cliente", client.id,
          f"Eliminato il cliente «{nome}» con {len(client.polizze)} polizze e {len(client.documenti)} documenti")
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
    for percorso in file_da_rimuovere:
        try:
            if os.path.isfile(percorso):
                os.remove(percorso)
        except OSError:
            current_app.logger.warning("File %s non rimosso", percorso)
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


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
    Client,
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

bp = Blueprint("clients", __name__, url_prefix="/clienti")


def _populate_from_form(client: Client, form) -> list[str]:
    """Copia i campi del form nel cliente e restituisce gli errori su date e importi."""
    errori: list[str] = []
    oggi = date.today()
    tipo = form.get("tipo")
    client.tipo = tipo if tipo in dict(CLIENT_TYPES) else "azienda"
    client.ragione_sociale = (form.get("ragione_sociale") or "").strip()
    client.referente = clean(form, "referente")
    client.codice_fiscale = (clean(form, "codice_fiscale", upper=True) or "").replace(" ", "") or None
    client.partita_iva = (clean(form, "partita_iva") or "").replace(" ", "").upper().removeprefix("IT") or None
    client.codice_ateco = clean(form, "codice_ateco")
    forma = form.get("forma_giuridica")
    client.forma_giuridica = forma if forma in FORME_GIURIDICHE.get(client.tipo, ()) else None
    client.professione = clean(form, "professione")
    client.specializzazioni = unisci_voci(form.getlist("specializzazioni"), form.get("specializzazioni_altre"))
    client.attivita_svolte = unisci_voci(form.getlist("attivita_svolte"), form.get("attivita_altre"))
    client.albo_ordine = clean(form, "albo_ordine")
    client.albo_numero = clean(form, "albo_numero", upper=True)
    inquadramento = form.get("inquadramento")
    client.inquadramento = inquadramento if inquadramento in dict(INQUADRAMENTI) else None
    client.datore_lavoro = clean(form, "datore_lavoro")
    client.settore = clean(form, "settore")
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
            "generica": p.chiave in PROFESSIONI_GENERICHE,
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
                Client.professione.ilike(like),
                Client.specializzazioni.ilike(like),
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
             c.inquadramento_label, c.albo_ordine, c.albo_numero, c.albo_data_iscrizione,
             c.studio.ragione_sociale if c.studio else None, c.numero_professionisti,
             c.datore_lavoro, c.settore, c.indirizzo, c.cap, c.citta, c.provincia, c.email, c.pec,
             c.telefono, c.numero_dipendenti, c.fatturato_annuo, c.data_nascita,
             c.data_consenso_privacy, c.consenso_marketing, c.data_adeguatezza,
             c.documento_scadenza, len(c.polizze_attive), c.premi_attivi)
            for c in clienti
        ],
    )


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
        audit("crea", "cliente", client.id, f"Nuovo cliente «{client.ragione_sociale}» ({client.tipo_label})")
        db.session.commit()
        flash(f"Cliente «{client.ragione_sociale}» creato.", "success")
        if request.form.get("analizza_subito") and client.descrizione_attivita:
            return redirect(url_for("clients.run_analysis", client_id=client.id), code=307)
        return redirect(url_for("clients.detail", client_id=client.id))
    return _form(client, nuovo=True)


@bp.route("/<int:client_id>")
def detail(client_id):
    return render_detail(db.get_or_404(Client, client_id))


def render_detail(client: Client, form_polizza=None):
    """Scheda cliente; ``form_polizza`` ripresenta i dati di una polizza non salvata."""
    from .policies import compagnie_note

    return render_template(
        "clients/detail.html",
        client=client,
        form_polizza=form_polizza,
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


"""Modelli del database (SQLAlchemy)."""
import json
from datetime import date, datetime, timedelta

from flask import current_app
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

from .utils import add_months_sicuro

db = SQLAlchemy()


def now() -> datetime:
    """Data e ora locali.

    Il gestionale gira sul computer dello studio: gli orari (registro attività,
    notifiche, note dei sinistri) vanno salvati e mostrati nell'ora locale.
    """
    return datetime.now()

# ----------------------------------------------------------------------
# Vocabolari condivisi (usati da form, motore di analisi e report)
# ----------------------------------------------------------------------
CLIENT_TYPES = [
    ("azienda", "Azienda"),
    ("studio", "Studio professionale"),
    ("professionista", "Libero professionista"),
    ("dipendente", "Lavoratore dipendente"),
    ("privato", "Privato"),
]
CLIENT_TYPE_DESCRIZIONI = {
    "azienda": "Impresa commerciale, artigiana o industriale (ditta individuale, S.n.c., S.r.l., S.p.A.…).",
    "studio": "Più professionisti insieme: studio associato o società tra professionisti (STP). "
              "Es. studio legale associato, studio pediatrico S.r.l.",
    "professionista": "Una sola persona che esercita la professione: es. un avvocato civilista, "
                      "un pediatra, un ingegnere.",
    "dipendente": "Persona con un contratto di lavoro subordinato.",
    "privato": "Persona senza attività lavorativa in corso: pensionato, studente, casalinga…",
}
# Per riepiloghi e statistiche: (singolare breve, plurale breve, plurale esteso).
CLIENT_TYPE_PLURALI = {
    "azienda": ("azienda", "aziende", "Aziende"),
    "studio": ("studio", "studi", "Studi professionali"),
    "professionista": ("prof.", "prof.", "Liberi professionisti"),
    "dipendente": ("dip.", "dip.", "Lavoratori dipendenti"),
    "privato": ("privato", "privati", "Privati"),
}
CLIENT_TYPE_BADGES = {
    "azienda": "tipo-azienda",
    "studio": "tipo-studio",
    "professionista": "tipo-professionista",
    "dipendente": "tipo-dipendente",
    "privato": "tipo-privato",
}
TIPI_PERSONA_FISICA = ("professionista", "dipendente", "privato")

# Campi dell'anagrafica pertinenti a ciascun tipo di cliente: il modulo mostra
# solo questi e il salvataggio azzera gli altri (es. niente dipendenti e
# ragione sociale per il libero professionista, che è una persona sola).
CAMPI_PER_TIPO = {
    "referente": {"azienda", "studio"},
    "forma_giuridica": {"azienda", "studio"},
    "partita_iva": {"azienda", "studio", "professionista"},
    "codice_ateco": {"azienda", "studio"},
    "settore": {"azienda", "dipendente"},
    "professione": {"studio", "professionista", "dipendente", "privato"},
    "specializzazioni": {"studio", "professionista"},
    "attivita_svolte": {"studio", "professionista"},
    "albo_ordine": {"studio", "professionista"},
    "albo_numero": {"studio", "professionista"},
    "albo_data_iscrizione": {"studio", "professionista"},
    "inquadramento": {"professionista"},
    "studio_id": {"professionista"},
    "numero_professionisti": {"studio"},
    "numero_dipendenti": {"azienda", "studio"},
    "fatturato_annuo": {"azienda", "studio", "professionista"},
    "datore_lavoro": {"dipendente"},
    "data_nascita": set(TIPI_PERSONA_FISICA),
}

POLICY_BRANCHES = [
    ("rc_professionale", "RC Professionale"),
    ("rct_rco", "RC Terzi e Prestatori d'Opera (RCT/RCO)"),
    ("rc_prodotti", "RC Prodotti"),
    ("rc_ambientale", "RC Inquinamento Ambientale"),
    ("incendio", "Incendio / All Risks Beni"),
    ("furto", "Furto e Rapina"),
    ("catastrofali", "Eventi Catastrofali (CatNat)"),
    ("guasti_macchine", "Guasti Macchine / Elettronica"),
    ("cyber", "Cyber Risk"),
    ("infortuni", "Infortuni"),
    ("malattia", "Malattia / Rimborso Spese Mediche"),
    ("vita", "Vita / Temporanea Caso Morte"),
    ("previdenza", "Previdenza integrativa / PIP"),
    ("rc_capofamiglia", "RC Capofamiglia / Vita Privata"),
    ("do", "D&O — Responsabilità Amministratori"),
    ("tutela_legale", "Tutela Legale"),
    ("trasporti", "Trasporti / Merci"),
    ("auto", "Auto / Flotte (RCA)"),
    ("cauzioni", "Cauzioni e Fideiussioni"),
    ("credito", "Credito Commerciale"),
    ("key_man", "Key Man"),
    ("altro", "Altro"),
]
BRANCH_LABELS = dict(POLICY_BRANCHES)

POLICY_STATUSES = [
    ("attiva", "Attiva"),
    ("in_rinnovo", "In rinnovo"),
    ("sospesa", "Sospesa"),
    ("disdetta", "Disdetta"),
    ("scaduta", "Scaduta"),
]

PAYMENT_FREQUENCIES = [
    ("annuale", "Annuale"),
    ("semestrale", "Semestrale"),
    ("quadrimestrale", "Quadrimestrale"),
    ("trimestrale", "Trimestrale"),
    ("mensile", "Mensile"),
]

FOLLOWUP_TYPES = [
    ("chiamata", "Chiamata"),
    ("incontro", "Incontro"),
    ("email", "Email"),
    ("preventivo", "Preventivo"),
    ("rinnovo", "Rinnovo polizza"),
    ("sinistro", "Gestione sinistro"),
    ("documenti", "Raccolta documenti"),
    ("altro", "Altro"),
]
FOLLOWUP_TYPE_LABELS = dict(FOLLOWUP_TYPES)

FOLLOWUP_PRIORITIES = [
    ("alta", "Alta"),
    ("media", "Media"),
    ("bassa", "Bassa"),
]

DOCUMENT_CATEGORIES = [
    ("polizza", "Polizza / Contratto"),
    ("preventivo", "Preventivo"),
    ("identita", "Documento d'identità"),
    ("visura", "Visura camerale"),
    ("bilancio", "Bilancio / Dichiarazione"),
    ("sinistro", "Documentazione sinistro"),
    ("adeguatezza", "Questionario di adeguatezza"),
    ("privacy", "Privacy / GDPR"),
    ("altro", "Altro"),
]
DOCUMENT_CATEGORY_LABELS = dict(DOCUMENT_CATEGORIES)

# Fasi della pipeline commerciale (opportunità di vendita), stile CRM.
OPPORTUNITY_STAGES = [
    ("lead", "Lead"),
    ("contatto", "Contattato"),
    ("preventivo", "Preventivo inviato"),
    ("trattativa", "In trattativa"),
    ("vinta", "Vinta"),
    ("persa", "Persa"),
]
OPPORTUNITY_STAGE_LABELS = dict(OPPORTUNITY_STAGES)
OPPORTUNITY_OPEN_STAGES = {"lead", "contatto", "preventivo", "trattativa"}

# Stato «effettivo» di una polizza, calcolato dalle date (oltre allo stato manuale).
POLICY_EFFECTIVE_STATES = {
    "non_in_vigore": ("Non ancora in vigore", "bg-info text-dark"),
    "in_vigore": ("In vigore", "bg-success"),
    "disdetta_inviata": ("Disdetta inviata", "bg-warning text-dark"),
    "da_rinnovare": ("Scaduta da rinnovare", "bg-danger"),
    "tacito_da_registrare": ("Rinnovo tacito da registrare", "bg-warning text-dark"),
    "sospesa": ("Copertura sospesa", "bg-danger"),
}
# Preavviso di disdetta predefinito per le polizze a tacito rinnovo (giorni).
PREAVVISO_DISDETTA_DEFAULT = 30
# Rami per cui il tacito rinnovo non è ammesso (RC auto: L. 221/2012).
RAMI_SENZA_TACITO_RINNOVO = {"auto"}
# Assicurazioni sulla vita: l'art. 1901 c.c. (sospensione e risoluzione per
# mancato pagamento) non si applica; valgono l'art. 1924 c.c. e le condizioni.
RAMI_VITA = {"vita", "previdenza"}
# Durata massima di una polizza accettata nei form.
DURATA_MASSIMA_ANNI = 10

# Numero di rate annue per ciascun frazionamento del premio.
RATE_PER_FRAZIONAMENTO = {
    "annuale": 1,
    "semestrale": 2,
    "quadrimestrale": 3,
    "trimestrale": 4,
    "mensile": 12,
}

# Titoli di premio (quietanze) e incassi.
TITLE_TYPES = [
    ("perfezionamento", "Perfezionamento"),
    ("quietanza", "Quietanza di rinnovo"),
    ("rata", "Rata di frazionamento"),
    ("appendice", "Appendice / regolazione"),
]
TITLE_TYPE_LABELS = dict(TITLE_TYPES)
TITLE_STATUSES = [
    ("da_incassare", "Da incassare"),
    ("incassato", "Incassato"),
    ("stornato", "Stornato"),
]
TITLE_STATUS_LABELS = dict(TITLE_STATUSES)
PAYMENT_METHODS = [
    ("bonifico", "Bonifico"),
    ("pos", "POS / Carta"),
    ("contanti", "Contanti"),
    ("assegno", "Assegno"),
    ("sdd", "Addebito SDD / RID"),
    ("altro", "Altro"),
]
PAYMENT_METHOD_LABELS = dict(PAYMENT_METHODS)
# Art. 1901 c.c., comma 2: per i premi successivi al primo la copertura resta
# sospesa dalle ore 24 del quindicesimo giorno dopo la scadenza non pagata.
GIORNI_TOLLERANZA_PREMIO = 15
# Art. 1901 c.c., comma 3: il contratto si risolve di diritto se l'assicuratore
# non agisce per la riscossione entro sei mesi dalla scadenza della rata.
MESI_RISOLUZIONE_PREMIO = 6

# Sinistri.
CLAIM_TYPES = [
    ("danni_terzi", "Danni a terzi (RC)"),
    ("danni_propri", "Danni a beni propri"),
    ("incendio", "Incendio / esplosione"),
    ("acqua", "Danni da acqua"),
    ("eventi_atmosferici", "Eventi atmosferici / catastrofali"),
    ("furto", "Furto / rapina"),
    ("rca", "RC Auto / incidente stradale"),
    ("cristalli", "Cristalli"),
    ("infortunio", "Infortunio"),
    ("malattia", "Malattia / ricovero"),
    ("cyber", "Attacco informatico"),
    ("tutela_legale", "Vertenza legale"),
    ("altro", "Altro"),
]
CLAIM_TYPE_LABELS = dict(CLAIM_TYPES)
CLAIM_STATUSES = [
    ("aperto", "Aperto"),
    ("istruttoria", "In istruttoria"),
    ("perizia", "In perizia"),
    ("liquidato", "Liquidato"),
    ("respinto", "Respinto"),
    ("chiuso", "Chiuso senza seguito"),
]
CLAIM_STATUS_LABELS = dict(CLAIM_STATUSES)
CLAIM_OPEN_STATUSES = {"aperto", "istruttoria", "perizia"}
# Art. 1913 c.c.: la denuncia va fatta entro tre giorni dal sinistro.
GIORNI_DENUNCIA_SINISTRO = 3

# Documenti di identità (adeguata verifica antiriciclaggio).
ID_DOCUMENT_TYPES = [
    ("carta_identita", "Carta d'identità"),
    ("patente", "Patente di guida"),
    ("passaporto", "Passaporto"),
    ("permesso_soggiorno", "Permesso di soggiorno"),
    ("altro", "Altro"),
]

# Utenti e ruoli.
USER_ROLES = [
    ("admin", "Amministratore"),
    ("operatore", "Operatore"),
    ("consultazione", "Sola consultazione"),
]
USER_ROLE_LABELS = dict(USER_ROLES)


class Client(db.Model):
    __tablename__ = "clients"

    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(20), nullable=False, default="azienda")
    ragione_sociale = db.Column(db.String(200), nullable=False)
    referente = db.Column(db.String(120))
    codice_fiscale = db.Column(db.String(16))
    partita_iva = db.Column(db.String(11))
    codice_ateco = db.Column(db.String(10))
    professione = db.Column(db.String(120))
    datore_lavoro = db.Column(db.String(200))  # per i lavoratori dipendenti
    settore = db.Column(db.String(120))
    indirizzo = db.Column(db.String(200))
    citta = db.Column(db.String(100))
    cap = db.Column(db.String(5))
    provincia = db.Column(db.String(2))
    email = db.Column(db.String(120))
    pec = db.Column(db.String(120))
    telefono = db.Column(db.String(30))
    numero_dipendenti = db.Column(db.Integer)
    fatturato_annuo = db.Column(db.Float)  # volume d'affari per il professionista
    # Aziende e studi: forma giuridica. Professionisti e studi: specializzazioni
    # e attività svolte (voci separate da «; »), iscrizione all'albo.
    forma_giuridica = db.Column(db.String(40))
    specializzazioni = db.Column(db.Text)
    attivita_svolte = db.Column(db.Text)
    albo_ordine = db.Column(db.String(150))
    albo_numero = db.Column(db.String(40))
    albo_data_iscrizione = db.Column(db.Date)
    inquadramento = db.Column(db.String(30))  # vedi professioni.INQUADRAMENTI
    numero_professionisti = db.Column(db.Integer)  # soci / associati dello studio
    studio_id = db.Column(db.Integer, db.ForeignKey("clients.id", ondelete="SET NULL"), index=True)
    descrizione_attivita = db.Column(db.Text)
    note = db.Column(db.Text)
    # Persone fisiche e compliance (GDPR, IVASS Reg. 40/2018, antiriciclaggio).
    data_nascita = db.Column(db.Date)
    data_consenso_privacy = db.Column(db.Date)
    consenso_marketing = db.Column(db.Boolean, default=False, nullable=False)
    data_adeguatezza = db.Column(db.Date)  # ultimo questionario demands & needs
    documento_tipo = db.Column(db.String(30))
    documento_numero = db.Column(db.String(40))
    documento_scadenza = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=now)
    updated_at = db.Column(db.DateTime, default=now, onupdate=now)

    polizze = db.relationship(
        "Policy", backref="cliente", cascade="all, delete-orphan", lazy=True
    )
    documenti = db.relationship(
        "Document", backref="cliente", cascade="all, delete-orphan", lazy=True
    )
    followups = db.relationship(
        "FollowUp", backref="cliente", cascade="all, delete-orphan", lazy=True
    )
    analisi = db.relationship(
        "RiskAnalysis",
        backref="cliente",
        cascade="all, delete-orphan",
        lazy=True,
        order_by="RiskAnalysis.created_at.desc()",
    )
    opportunita = db.relationship(
        "Opportunity",
        backref="cliente",
        cascade="all, delete-orphan",
        lazy=True,
        order_by="Opportunity.created_at.desc()",
    )
    sinistri = db.relationship(
        "Claim",
        backref="cliente",
        cascade="all, delete-orphan",
        lazy=True,
        order_by="Claim.data_evento.desc()",
    )
    # I titoli appartengono alla polizza (e con essa vengono eliminati): dal
    # cliente li leggiamo soltanto.
    titoli = db.relationship(
        "Title", viewonly=True, lazy=True, order_by="Title.data_effetto.desc()"
    )
    # Il professionista può far parte di uno studio cliente; eliminato lo
    # studio, il collegamento si azzera.
    studio = db.relationship(
        "Client", remote_side=[id], lazy=True,
        backref=db.backref("professionisti", lazy=True, order_by="Client.ragione_sociale"),
    )

    @property
    def tipo_label(self):
        return dict(CLIENT_TYPES).get(self.tipo, self.tipo)

    @property
    def persona_fisica(self):
        return self.tipo in TIPI_PERSONA_FISICA

    # --- Professione ----------------------------------------------------
    @property
    def professione_catalogo(self):
        """Voce del catalogo delle professioni (solo studi e professionisti)."""
        from .professioni import trova_professione

        if self.tipo not in ("studio", "professionista"):
            return None
        return trova_professione(self.professione)

    @property
    def specializzazioni_elenco(self):
        from .professioni import dividi_voci

        return dividi_voci(self.specializzazioni)

    @property
    def attivita_elenco(self):
        from .professioni import dividi_voci

        return dividi_voci(self.attivita_svolte)

    @property
    def inquadramento_label(self):
        from .professioni import INQUADRAMENTI

        return dict(INQUADRAMENTI).get(self.inquadramento, self.inquadramento)

    @property
    def attivita_sintesi(self):
        """Breve descrizione dell'attività per elenchi e intestazioni."""
        if self.tipo == "professionista":
            parti = [self.professione, ", ".join(self.specializzazioni_elenco[:2])]
            if len(self.specializzazioni_elenco) > 2:
                parti[-1] += "…"
        elif self.tipo == "studio":
            parti = [self.professione, self.forma_giuridica]
        elif self.tipo == "dipendente":
            parti = [self.professione, f"presso {self.datore_lavoro}" if self.datore_lavoro else None]
            if self.settore and not self.professione:
                parti[0] = self.settore
        elif self.tipo == "privato":
            parti = [self.professione]
        else:
            parti = [self.settore]
        return " · ".join(p for p in parti if p) or None

    def _obblighi_di_legge(self):
        from .professioni import obblighi_di_legge

        return obblighi_di_legge(
            self.tipo, self.professione_catalogo, inquadramento=self.inquadramento,
            forma_giuridica=self.forma_giuridica, fatturato=self.fatturato_annuo,
            numero_professionisti=self.numero_professionisti,
            voci=self.specializzazioni_elenco + self.attivita_elenco,
        )

    @property
    def obblighi_assicurativi(self):
        """Coperture obbligatorie per legge, se sono in portafoglio e con quale massimale.

        Contano anche le polizze già emesse con decorrenza futura e, per il
        professionista, quelle dello studio di appartenenza. Per i sanitari
        l'RC dipende dall'inquadramento (L. 24/2017, art. 10).
        """
        obblighi, _ = self._obblighi_di_legge()
        proprie = [p for p in self.polizze if p.attiva]
        dello_studio = [p for p in self.studio.polizze if p.attiva] if self.tipo == "professionista" and self.studio else []
        for obbligo in obblighi:
            mie = [p for p in proprie if p.ramo == obbligo["ramo"]]
            studio = [p for p in dello_studio if p.ramo == obbligo["ramo"]]
            # "proprio" | "studio" (polizza dello studio di appartenenza) | None
            obbligo["in_portafoglio"] = "proprio" if mie else "studio" if studio else None
            massimali = [p.massimale for p in (mie or studio) if p.massimale]
            obbligo["massimale_polizza"] = max(massimali) if massimali else None
            obbligo["massimale_insufficiente"] = bool(
                obbligo["massimale_minimo"] and obbligo["massimale_polizza"]
                and obbligo["massimale_polizza"] < obbligo["massimale_minimo"]
            )
        return obblighi

    @property
    def avvertenze_assicurative(self):
        """Avvertenze per l'intermediario legate alla professione (es. polizza collettiva dei notai)."""
        return self._obblighi_di_legge()[1]

    @property
    def eta(self):
        if not self.data_nascita or self.data_nascita > date.today():
            return None
        oggi = date.today()
        return oggi.year - self.data_nascita.year - (
            (oggi.month, oggi.day) < (self.data_nascita.month, self.data_nascita.day)
        )

    # --- Compliance -----------------------------------------------------
    @property
    def adeguatezza_scadenza(self):
        """Data entro cui aggiornare il questionario di adeguatezza (12 mesi)."""
        return add_months_sicuro(self.data_adeguatezza, 12)

    @property
    def adeguatezza_stato(self):
        """mancante | da_aggiornare (oltre 12 mesi) | in_scadenza (entro 30 gg) | ok."""
        if not self.data_adeguatezza:
            return "mancante"
        scadenza = self.adeguatezza_scadenza
        if scadenza is None or scadenza < date.today():
            return "da_aggiornare"
        if (scadenza - date.today()).days <= 30:
            return "in_scadenza"
        return "ok"

    @property
    def documento_stato(self):
        """mancante | scaduto | in_scadenza (entro 30 giorni) | ok."""
        if not self.documento_scadenza:
            return "mancante"
        giorni = (self.documento_scadenza - date.today()).days
        if giorni < 0:
            return "scaduto"
        if giorni <= 30:
            return "in_scadenza"
        return "ok"

    @property
    def compliance_problemi(self):
        """Elenco leggibile delle carenze di compliance del cliente."""
        problemi = []
        if not self.data_consenso_privacy:
            problemi.append("Consenso privacy (GDPR) non registrato")
        if self.adeguatezza_stato == "mancante":
            problemi.append("Questionario di adeguatezza mancante")
        elif self.adeguatezza_stato == "da_aggiornare":
            problemi.append("Questionario di adeguatezza più vecchio di 12 mesi")
        if self.persona_fisica and self.documento_stato == "mancante":
            problemi.append("Documento d'identità non registrato")
        elif self.documento_stato == "scaduto":
            problemi.append("Documento d'identità scaduto")
        return problemi

    # --- Indicatori economici ------------------------------------------
    @property
    def premi_attivi(self):
        return sum(p.premio_annuo or 0.0 for p in self.polizze_attive)

    @property
    def provvigioni_attive(self):
        return sum(p.provvigione_annua or 0.0 for p in self.polizze_attive)

    @property
    def costo_sinistri(self):
        return sum(s.costo for s in self.sinistri)

    @property
    def costo_sinistri_12_mesi(self):
        limite = date.today() - timedelta(days=365)
        return sum(s.costo for s in self.sinistri if s.data_evento and s.data_evento > limite)

    @property
    def rapporto_sp(self):
        """Rapporto sinistri/premi degli ultimi 12 mesi, in percentuale.

        Sinistri accaduti negli ultimi 12 mesi rispetto ai premi annui delle
        polizze in vigore: un periodo omogeneo, che non cresce con l'anzianità
        del cliente.
        """
        premi = self.premi_attivi
        if not premi:
            return None
        return 100.0 * self.costo_sinistri_12_mesi / premi

    @property
    def titoli_da_incassare(self):
        return [t for t in self.titoli if t.stato == "da_incassare"]

    @property
    def tipo_badge(self):
        return CLIENT_TYPE_BADGES.get(self.tipo, "bg-secondary")

    @property
    def polizze_attive(self):
        """Polizze attive e già in vigore (escluse quelle con decorrenza futura)."""
        return [p for p in self.polizze if p.attiva and not p.non_ancora_in_vigore]

    @property
    def ultima_analisi(self):
        return self.analisi[0] if self.analisi else None

    def __repr__(self):  # pragma: no cover
        return f"<Client {self.ragione_sociale!r}>"


class Policy(db.Model):
    __tablename__ = "policies"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(
        db.Integer, db.ForeignKey("clients.id"), nullable=False, index=True
    )
    compagnia = db.Column(db.String(120), nullable=False)
    numero_polizza = db.Column(db.String(60), nullable=False)
    ramo = db.Column(db.String(40), nullable=False, default="altro")
    massimale = db.Column(db.Float)
    premio_annuo = db.Column(db.Float)
    provvigione_perc = db.Column(db.Float)  # percentuale di provvigione
    frazionamento = db.Column(db.String(20), default="annuale")
    data_decorrenza = db.Column(db.Date)
    data_scadenza = db.Column(db.Date, index=True)
    tacito_rinnovo = db.Column(db.Boolean, default=False)
    # Tacito rinnovo: preavviso di disdetta (giorni prima della scadenza) e
    # disdetta eventualmente già inviata (blocca il rinnovo automatico).
    preavviso_disdetta_giorni = db.Column(db.Integer)
    data_disdetta = db.Column(db.Date)
    # Scadenza prima di una cessazione anticipata con data futura (per l'annullo).
    scadenza_originale = db.Column(db.Date)
    stato = db.Column(db.String(20), nullable=False, default="attiva")
    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=now)

    documenti = db.relationship("Document", backref="polizza", lazy=True)
    titoli = db.relationship(
        "Title",
        backref="polizza",
        cascade="all, delete-orphan",
        lazy=True,
        order_by="Title.data_effetto.asc()",
    )
    sinistri = db.relationship(
        "Claim", backref="polizza", lazy=True, order_by="Claim.data_evento.desc()"
    )

    @property
    def ramo_label(self):
        return BRANCH_LABELS.get(self.ramo, self.ramo)

    @property
    def frazionamento_label(self):
        return dict(PAYMENT_FREQUENCIES).get(self.frazionamento, self.frazionamento or "—")

    @property
    def rate_annue(self):
        return RATE_PER_FRAZIONAMENTO.get(self.frazionamento or "annuale", 1)

    @property
    def attiva(self):
        return self.stato in ("attiva", "in_rinnovo")

    # --- Date future e stato effettivo ----------------------------------
    @property
    def non_ancora_in_vigore(self):
        return self.data_decorrenza is not None and self.data_decorrenza > date.today()

    @property
    def giorni_alla_decorrenza(self):
        if not self.data_decorrenza:
            return None
        return (self.data_decorrenza - date.today()).days

    @property
    def rinnovo_tacito(self):
        """Tacito rinnovo effettivo: mai per i rami che non lo ammettono (RC auto),
        anche se il flag è rimasto attivo da dati importati o da versioni precedenti."""
        return bool(self.tacito_rinnovo) and self.ramo not in RAMI_SENZA_TACITO_RINNOVO

    @property
    def preavviso_disdetta(self):
        """Giorni di preavviso per la disdetta (solo con tacito rinnovo)."""
        if not self.rinnovo_tacito:
            return None
        if self.preavviso_disdetta_giorni is None:
            return PREAVVISO_DISDETTA_DEFAULT
        return self.preavviso_disdetta_giorni

    @property
    def termine_disdetta(self):
        """Ultimo giorno utile per inviare la disdetta ed evitare il rinnovo tacito."""
        if not self.rinnovo_tacito or not self.data_scadenza:
            return None
        try:
            return self.data_scadenza - timedelta(days=self.preavviso_disdetta or 0)
        except OverflowError:
            return None

    @property
    def giorni_al_termine_disdetta(self):
        termine = self.termine_disdetta
        return None if termine is None else (termine - date.today()).days

    @property
    def disdetta_inviata(self):
        return self.data_disdetta is not None

    @property
    def disdetta_tardiva(self):
        termine = self.termine_disdetta
        return bool(self.data_disdetta and termine and self.data_disdetta > termine)

    @property
    def stato_effettivo(self):
        """Stato calcolato dalle date, per le polizze attive (None per gli altri stati).

        non_in_vigore | disdetta_inviata | da_rinnovare | tacito_da_registrare |
        sospesa | in_vigore
        """
        if not self.attiva:
            return None
        oggi = date.today()
        if self.non_ancora_in_vigore:
            return "non_in_vigore"
        if self.data_scadenza and self.data_scadenza < oggi:
            if self.rinnovo_tacito and not self.disdetta_inviata:
                return "tacito_da_registrare"
            return "da_rinnovare"
        if self.copertura_sospesa:
            return "sospesa"
        if self.disdetta_inviata:
            return "disdetta_inviata"
        return "in_vigore"

    @property
    def stato_effettivo_label(self):
        return POLICY_EFFECTIVE_STATES.get(self.stato_effettivo, ("", ""))[0]

    @property
    def stato_effettivo_badge(self):
        return POLICY_EFFECTIVE_STATES.get(self.stato_effettivo, ("", "bg-secondary"))[1]

    @property
    def titoli_arretrati(self):
        return [t for t in self.titoli if t.arretrato]

    @property
    def titoli_da_incassare(self):
        return [t for t in self.titoli if t.stato == "da_incassare"]

    @property
    def titoli_incassati(self):
        return [t for t in self.titoli if t.stato == "incassato"]

    @property
    def copertura_sospesa(self):
        """True se almeno un titolo non pagato sospende la copertura (art. 1901 c.c.)."""
        return any(t.copertura_sospesa for t in self.titoli)

    @property
    def stato_label(self):
        return dict(POLICY_STATUSES).get(self.stato, self.stato)

    @property
    def provvigione_annua(self):
        if self.premio_annuo and self.provvigione_perc:
            return self.premio_annuo * self.provvigione_perc / 100.0
        return None

    @property
    def giorni_alla_scadenza(self):
        if not self.data_scadenza:
            return None
        return (self.data_scadenza - date.today()).days

    @property
    def urgenza_scadenza(self):
        """Classe di urgenza per lo scadenzario: scaduta / critica / attenzione / ok."""
        giorni = self.giorni_alla_scadenza
        if giorni is None:
            return "ok"
        if giorni < 0:
            return "scaduta"
        if giorni <= 7:
            return "critica"
        if giorni <= 30:
            return "attenzione"
        return "ok"

    def __repr__(self):  # pragma: no cover
        return f"<Policy {self.numero_polizza!r} {self.ramo}>"


class Document(db.Model):
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(
        db.Integer, db.ForeignKey("clients.id"), nullable=False, index=True
    )
    policy_id = db.Column(db.Integer, db.ForeignKey("policies.id"), index=True)
    claim_id = db.Column(db.Integer, db.ForeignKey("claims.id"), index=True)
    categoria = db.Column(db.String(40), nullable=False, default="altro")
    filename = db.Column(db.String(300), nullable=False)  # nome su disco (sicuro)
    original_name = db.Column(db.String(300), nullable=False)
    dimensione = db.Column(db.Integer)  # dimensione in byte
    note = db.Column(db.Text)
    uploaded_at = db.Column(db.DateTime, default=now)

    @property
    def categoria_label(self):
        return DOCUMENT_CATEGORY_LABELS.get(self.categoria, self.categoria)

    @property
    def estensione(self):
        return self.original_name.rsplit(".", 1)[-1].lower() if "." in self.original_name else ""

    @property
    def dimensione_leggibile(self):
        n = float(self.dimensione or 0)
        for unit in ("B", "KB", "MB", "GB"):
            if n < 1024 or unit == "GB":
                return f"{int(n)} {unit}" if unit == "B" else f"{n:.1f} {unit}"
            n /= 1024
        return f"{n:.1f} GB"

    @property
    def icona(self):
        ext = self.estensione
        if ext == "pdf":
            return "bi-file-earmark-pdf"
        if ext in ("doc", "docx", "odt"):
            return "bi-file-earmark-word"
        if ext in ("xls", "xlsx", "ods", "csv"):
            return "bi-file-earmark-spreadsheet"
        if ext in ("png", "jpg", "jpeg", "gif"):
            return "bi-file-earmark-image"
        if ext in ("zip", "p7m"):
            return "bi-file-earmark-zip"
        return "bi-file-earmark-text"


class FollowUp(db.Model):
    __tablename__ = "followups"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(
        db.Integer, db.ForeignKey("clients.id"), nullable=False, index=True
    )
    policy_id = db.Column(db.Integer, db.ForeignKey("policies.id"), index=True)
    tipo = db.Column(db.String(30), nullable=False, default="chiamata")
    titolo = db.Column(db.String(200), nullable=False)
    descrizione = db.Column(db.Text)
    data_scadenza = db.Column(db.Date, nullable=False, index=True)
    priorita = db.Column(db.String(10), nullable=False, default="media")
    stato = db.Column(db.String(20), nullable=False, default="aperto")
    auto_generato = db.Column(db.Boolean, default=False, nullable=False)
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=now)

    @property
    def tipo_label(self):
        return FOLLOWUP_TYPE_LABELS.get(self.tipo, self.tipo)

    @property
    def in_ritardo(self):
        return self.stato == "aperto" and self.data_scadenza < date.today()


class Opportunity(db.Model):
    """Opportunità di vendita (pipeline commerciale, stile CRM assicurativo)."""

    __tablename__ = "opportunities"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(
        db.Integer, db.ForeignKey("clients.id"), nullable=False, index=True
    )
    titolo = db.Column(db.String(200), nullable=False)
    ramo = db.Column(db.String(40))  # ramo assicurativo di riferimento (opzionale)
    fase = db.Column(db.String(20), nullable=False, default="lead", index=True)
    premio_stimato = db.Column(db.Float)
    provvigione_perc = db.Column(db.Float)
    priorita = db.Column(db.String(10), nullable=False, default="media")
    origine = db.Column(db.String(40))  # es. manuale | analisi_rischi | rinnovo
    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=now)
    updated_at = db.Column(db.DateTime, default=now, onupdate=now)
    chiusa_at = db.Column(db.DateTime)

    @property
    def ramo_label(self):
        return BRANCH_LABELS.get(self.ramo, self.ramo or "—")

    @property
    def fase_label(self):
        return OPPORTUNITY_STAGE_LABELS.get(self.fase, self.fase)

    @property
    def aperta(self):
        return self.fase in OPPORTUNITY_OPEN_STAGES

    @property
    def provvigione_stimata(self):
        if self.premio_stimato and self.provvigione_perc:
            return self.premio_stimato * self.provvigione_perc / 100.0
        return None


class RiskAnalysis(db.Model):
    __tablename__ = "risk_analyses"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(
        db.Integer, db.ForeignKey("clients.id"), nullable=False, index=True
    )
    input_text = db.Column(db.Text, nullable=False)
    results_json = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=now)

    @property
    def results(self):
        return json.loads(self.results_json)


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(30), nullable=False)  # scadenza_polizza | followup | info
    livello = db.Column(db.String(10), nullable=False, default="info")  # danger|warning|info
    messaggio = db.Column(db.String(500), nullable=False)
    link = db.Column(db.String(300))
    dedup_key = db.Column(db.String(120), unique=True, nullable=False)
    letta = db.Column(db.Boolean, default=False, nullable=False)
    # Invio via email: la notifica viene inclusa nel prossimo digest e poi
    # marcata come inviata (una sola email per notifica).
    inviata_email = db.Column(db.Boolean, default=False, nullable=False)
    inviata_email_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=now)


# Livelli di preavviso per l'ordinamento del digest (dal più urgente).
LIVELLO_ORDINE = {"danger": 0, "warning": 1, "info": 2}


class Settings(db.Model):
    """Configurazione applicativa (riga singola, id=1).

    Contiene i parametri SMTP e i destinatari per le notifiche via email.
    Le impostazioni sono modificabili dalla pagina «Impostazioni»; le
    variabili d'ambiente omonime, se presenti, hanno la precedenza a runtime
    (utile per il deploy senza salvare la password nel database).
    """

    __tablename__ = "settings"

    id = db.Column(db.Integer, primary_key=True)
    email_attive = db.Column(db.Boolean, default=False, nullable=False)
    smtp_host = db.Column(db.String(200))
    smtp_port = db.Column(db.Integer, default=587)
    smtp_security = db.Column(db.String(10), default="tls")  # tls | ssl | none
    smtp_user = db.Column(db.String(200))
    smtp_password = db.Column(db.String(300))
    mail_from = db.Column(db.String(200))
    mail_to = db.Column(db.String(500))  # destinatari separati da virgola/;
    intervallo_minuti = db.Column(db.Integer, default=30)  # cadenza controllo automatico
    # Dati dell'intermediario: intestazione di stampe e report.
    studio_nome = db.Column(db.String(200))
    studio_rui = db.Column(db.String(40))  # iscrizione al Registro Unico Intermediari
    studio_piva = db.Column(db.String(16))
    studio_indirizzo = db.Column(db.String(250))
    studio_contatti = db.Column(db.String(250))
    # Backup automatico giornaliero del database e dei documenti.
    backup_automatico = db.Column(db.Boolean, default=True, nullable=False)
    backup_conservati = db.Column(db.Integer, default=14)
    # Automatismi sulle date (eseguiti dallo scheduler e all'accesso).
    rinnovo_tacito_automatico = db.Column(db.Boolean, default=True, nullable=False)
    emissione_quietanze_automatica = db.Column(db.Boolean, default=True, nullable=False)
    anticipo_quietanze_giorni = db.Column(db.Integer, default=30)
    scadenza_automatica = db.Column(db.Boolean, default=True, nullable=False)
    tolleranza_scadenza_giorni = db.Column(db.Integer, default=30)
    ultimo_backup_at = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime, default=now, onupdate=now)

    @staticmethod
    def get() -> "Settings":
        """Restituisce la riga di configurazione, creandola se assente."""
        row = db.session.get(Settings, 1)
        if row is None:
            row = Settings(id=1)
            db.session.add(row)
            db.session.commit()
        return row

    @property
    def destinatari(self) -> list[str]:
        if not self.mail_to:
            return []
        parti = self.mail_to.replace(";", ",").split(",")
        return [p.strip() for p in parti if p.strip()]

    @property
    def configurato(self) -> bool:
        """True se ci sono i dati minimi per inviare (host + almeno un destinatario)."""
        return bool(self.smtp_host and self.destinatari)


class Title(db.Model):
    """Titolo di premio (quietanza): una rata da incassare per una polizza.

    Il ciclo di vita è da_incassare → incassato (oppure stornato). Il premio
    incassato, al netto della provvigione, va rimesso alla compagnia: la data
    di rimessa viene registrata dall'estratto conto.
    """

    __tablename__ = "titles"

    id = db.Column(db.Integer, primary_key=True)
    policy_id = db.Column(
        db.Integer, db.ForeignKey("policies.id"), nullable=False, index=True
    )
    client_id = db.Column(
        db.Integer, db.ForeignKey("clients.id"), nullable=False, index=True
    )
    tipo = db.Column(db.String(20), nullable=False, default="rata")
    numero_rata = db.Column(db.Integer)
    rate_totali = db.Column(db.Integer)
    data_effetto = db.Column(db.Date, nullable=False, index=True)  # scadenza della rata
    data_fine_copertura = db.Column(db.Date)
    premio_lordo = db.Column(db.Float, nullable=False, default=0.0)
    provvigione = db.Column(db.Float)
    stato = db.Column(db.String(20), nullable=False, default="da_incassare", index=True)
    data_incasso = db.Column(db.Date, index=True)
    mezzo_pagamento = db.Column(db.String(20))
    riferimento_pagamento = db.Column(db.String(120))  # CRO, n. assegno…
    incassato_da = db.Column(db.String(60))
    data_rimessa = db.Column(db.Date)
    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=now)

    cliente = db.relationship("Client", viewonly=True)

    @property
    def tipo_label(self):
        return TITLE_TYPE_LABELS.get(self.tipo, self.tipo)

    @property
    def stato_label(self):
        return TITLE_STATUS_LABELS.get(self.stato, self.stato)

    @property
    def mezzo_label(self):
        return PAYMENT_METHOD_LABELS.get(self.mezzo_pagamento, self.mezzo_pagamento or "—")

    @property
    def rata_label(self):
        if self.numero_rata and self.rate_totali and self.rate_totali > 1:
            return f"{self.numero_rata}/{self.rate_totali}"
        return ""

    @property
    def netto(self):
        """Premio da rimettere alla compagnia (lordo meno provvigione)."""
        return (self.premio_lordo or 0.0) - (self.provvigione or 0.0)

    @property
    def da_rimborsare(self):
        """Titolo negativo (es. appendice di rimborso) ancora da pagare al cliente."""
        return self.stato == "da_incassare" and (self.premio_lordo or 0) < 0

    @property
    def arretrato(self):
        return (
            self.stato == "da_incassare"
            and (self.premio_lordo or 0) > 0
            and self.data_effetto < date.today()
        )

    @property
    def giorni_ritardo(self):
        if not self.arretrato:
            return 0
        return (date.today() - self.data_effetto).days

    @property
    def data_sospensione(self):
        """Giorno dal quale la copertura è sospesa se la rata resta impagata."""
        if self.tipo == "perfezionamento":
            return self.data_effetto
        try:
            return self.data_effetto + timedelta(days=GIORNI_TOLLERANZA_PREMIO)
        except OverflowError:
            return date.max

    @property
    def inizio_sospensione(self):
        """Primo giorno senza copertura se la rata resta impagata: la decorrenza
        per il primo premio, altrimenti il 16° giorno (sospesa dalle ore 24 del 15°)."""
        if self.tipo == "perfezionamento":
            return self.data_effetto
        try:
            return self.data_sospensione + timedelta(days=1)
        except OverflowError:
            return date.max

    @property
    def soggetto_art_1901(self):
        """L'art. 1901 c.c. non si applica alle assicurazioni sulla vita."""
        return self.polizza is None or self.polizza.ramo not in RAMI_VITA

    @property
    def data_risoluzione(self):
        """Art. 1901 c. 3: risoluzione di diritto se la rata resta impagata 6 mesi."""
        if not self.soggetto_art_1901:
            return None
        return add_months_sicuro(self.data_effetto, MESI_RISOLUZIONE_PREMIO)

    @property
    def copertura_sospesa(self):
        """Art. 1901 c.c.: primo premio non pagato → copertura non operante;
        premi successivi → sospesa dopo 15 giorni dalla scadenza."""
        if self.stato != "da_incassare" or (self.premio_lordo or 0) <= 0:
            return False
        if not self.soggetto_art_1901:
            return False
        oggi = date.today()
        if self.tipo == "perfezionamento":
            return self.data_effetto <= oggi
        return oggi > self.data_sospensione

    @property
    def modificabile(self):
        return self.stato == "da_incassare"

    def sospende_alla_data(self, giorno: date) -> bool:
        """True se, alla data indicata, questa rata impagata sospendeva la copertura."""
        if self.stato == "stornato" or (self.premio_lordo or 0) <= 0 or not self.soggetto_art_1901:
            return False
        if giorno < self.inizio_sospensione:
            return False
        # La copertura riprende dalle ore 24 del giorno del pagamento: un evento
        # accaduto proprio quel giorno è ancora scoperto.
        return self.data_incasso is None or self.data_incasso >= giorno


class Claim(db.Model):
    """Sinistro denunciato da un cliente, con importi e stato di lavorazione."""

    __tablename__ = "claims"

    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(30), unique=True, nullable=False)  # es. SIN-2026-0001
    client_id = db.Column(
        db.Integer, db.ForeignKey("clients.id"), nullable=False, index=True
    )
    policy_id = db.Column(db.Integer, db.ForeignKey("policies.id"), index=True)
    numero_compagnia = db.Column(db.String(60))
    tipologia = db.Column(db.String(30), nullable=False, default="altro")
    data_evento = db.Column(db.Date, nullable=False, index=True)
    data_denuncia = db.Column(db.Date)
    luogo = db.Column(db.String(200))
    descrizione = db.Column(db.Text)
    controparte = db.Column(db.String(200))
    perito = db.Column(db.String(200))
    liquidatore = db.Column(db.String(200))
    importo_richiesto = db.Column(db.Float)  # stima del danno
    importo_riservato = db.Column(db.Float)  # riserva della compagnia
    importo_liquidato = db.Column(db.Float)
    franchigia = db.Column(db.Float)
    data_liquidazione = db.Column(db.Date)
    stato = db.Column(db.String(20), nullable=False, default="aperto", index=True)
    data_chiusura = db.Column(db.Date)
    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=now)
    updated_at = db.Column(db.DateTime, default=now, onupdate=now)

    eventi = db.relationship(
        "ClaimNote",
        backref="sinistro",
        cascade="all, delete-orphan",
        lazy=True,
        order_by="ClaimNote.created_at.desc()",
    )
    documenti = db.relationship("Document", backref="sinistro", lazy=True)

    @staticmethod
    def genera_numero(anno: int | None = None) -> str:
        """Prossimo numero progressivo dell'anno: SIN-AAAA-NNNN.

        Usa un contatore persistente: i numeri dei sinistri eliminati non vengono
        riassegnati (sono già stati comunicati a cliente e compagnia).
        """
        anno = anno or date.today().year
        prefisso = f"SIN-{anno}-"
        massimo = 0
        for (numero,) in db.session.query(Claim.numero).filter(Claim.numero.like(prefisso + "%")):
            try:
                massimo = max(massimo, int(numero.rsplit("-", 1)[1]))
            except (ValueError, IndexError):
                continue
        return f"{prefisso}{Contatore.prossimo(f'sinistri-{anno}', almeno=massimo + 1):04d}"

    @property
    def avvisi_copertura(self):
        """Controlli di operatività della copertura alla data dell'evento."""
        avvisi = []
        polizza = self.polizza
        if polizza is None or self.data_evento is None:
            return avvisi
        if polizza.data_decorrenza and self.data_evento < polizza.data_decorrenza:
            avvisi.append(
                f"L'evento ({self.data_evento:%d/%m/%Y}) è precedente alla decorrenza della polizza "
                f"({polizza.data_decorrenza:%d/%m/%Y})."
            )
        if polizza.data_scadenza and self.data_evento >= polizza.data_scadenza:
            avvisi.append(
                f"L'evento ({self.data_evento:%d/%m/%Y}) è successivo alla scadenza della polizza "
                f"({polizza.data_scadenza:%d/%m/%Y})."
            )
        sospensive = [t for t in polizza.titoli if t.sospende_alla_data(self.data_evento)]
        if sospensive:
            t = sospensive[0]
            avvisi.append(
                f"Alla data dell'evento la copertura risultava sospesa per mancato pagamento "
                f"della rata del {t.data_effetto:%d/%m/%Y} (art. 1901 c.c.)."
            )
        return avvisi

    @property
    def stato_label(self):
        return CLAIM_STATUS_LABELS.get(self.stato, self.stato)

    @property
    def tipologia_label(self):
        return CLAIM_TYPE_LABELS.get(self.tipologia, self.tipologia)

    @property
    def aperto(self):
        return self.stato in CLAIM_OPEN_STATUSES

    @property
    def stato_badge(self):
        return {
            "aperto": "bg-warning text-dark",
            "istruttoria": "bg-info text-dark",
            "perizia": "bg-primary",
            "liquidato": "bg-success",
            "respinto": "bg-danger",
            "chiuso": "bg-secondary",
        }.get(self.stato, "bg-secondary")

    @property
    def giorni_apertura(self):
        inizio = self.data_denuncia or (self.created_at.date() if self.created_at else date.today())
        fine = self.data_chiusura or date.today()
        return max(0, (fine - inizio).days)

    @property
    def giorni_alla_denuncia(self):
        if not self.data_denuncia:
            return None
        return (self.data_denuncia - self.data_evento).days

    @property
    def denuncia_tardiva(self):
        giorni = self.giorni_alla_denuncia
        return giorni is not None and giorni > GIORNI_DENUNCIA_SINISTRO

    @property
    def costo(self):
        """Costo del sinistro per il rapporto S/P: liquidato più riserva se aperto."""
        costo = self.importo_liquidato or 0.0
        if self.aperto:
            costo += self.importo_riservato or 0.0
        return costo


class ClaimNote(db.Model):
    """Voce della cronologia di un sinistro (nota o cambio di stato)."""

    __tablename__ = "claim_notes"

    id = db.Column(db.Integer, primary_key=True)
    claim_id = db.Column(
        db.Integer, db.ForeignKey("claims.id"), nullable=False, index=True
    )
    tipo = db.Column(db.String(20), nullable=False, default="nota")  # nota | stato
    testo = db.Column(db.Text, nullable=False)
    username = db.Column(db.String(60))
    created_at = db.Column(db.DateTime, default=now)


class User(db.Model):
    """Utente del gestionale."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(60), unique=True, nullable=False)
    nome = db.Column(db.String(120))
    email = db.Column(db.String(120))
    password_hash = db.Column(db.String(255), nullable=False)
    ruolo = db.Column(db.String(20), nullable=False, default="operatore")
    attivo = db.Column(db.Boolean, default=True, nullable=False)
    tentativi_falliti = db.Column(db.Integer, default=0, nullable=False)
    # Incrementata a logout, cambio password, reset e disattivazione: invalida
    # i cookie di sessione già emessi.
    sessione_versione = db.Column(db.Integer, default=0, nullable=False)
    bloccato_fino = db.Column(db.DateTime)
    ultimo_accesso = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=now)

    def set_password(self, password: str) -> None:
        metodo = current_app.config.get("PASSWORD_HASH_METHOD", "scrypt")
        try:
            self.password_hash = generate_password_hash(password, method=metodo)
        except (ValueError, AttributeError):
            # Python compilato senza scrypt: ripiega su PBKDF2.
            self.password_hash = generate_password_hash(password, method="pbkdf2:sha256")

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def nome_visualizzato(self):
        return self.nome or self.username

    @property
    def ruolo_label(self):
        return USER_ROLE_LABELS.get(self.ruolo, self.ruolo)

    @property
    def is_admin(self):
        return self.ruolo == "admin"

    @property
    def puo_modificare(self):
        return self.ruolo in ("admin", "operatore")

    @property
    def bloccato(self):
        return self.bloccato_fino is not None and self.bloccato_fino > now()


class Contatore(db.Model):
    """Contatori progressivi persistenti (es. numerazione dei sinistri per anno)."""

    __tablename__ = "contatori"

    chiave = db.Column(db.String(60), primary_key=True)
    valore = db.Column(db.Integer, nullable=False, default=0)

    @staticmethod
    def prossimo(chiave: str, almeno: int = 1) -> int:
        """Incrementa e restituisce il contatore (mai inferiore ad ``almeno``).

        L'aggiornamento avviene nella transazione corrente: in caso di conflitto
        la chiamante ripete l'operazione.
        """
        riga = db.session.get(Contatore, chiave)
        if riga is None:
            riga = Contatore(chiave=chiave, valore=0)
            db.session.add(riga)
        riga.valore = max(riga.valore or 0, almeno - 1) + 1
        db.session.flush()
        return riga.valore


class AuditLog(db.Model):
    """Registro delle attività: chi ha fatto cosa e quando."""

    __tablename__ = "audit_log"

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=now, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), index=True)
    username = db.Column(db.String(60))
    azione = db.Column(db.String(30), nullable=False, index=True)
    entita = db.Column(db.String(30), index=True)
    entita_id = db.Column(db.Integer)
    descrizione = db.Column(db.String(500))
    ip = db.Column(db.String(45))

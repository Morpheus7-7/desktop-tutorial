"""Modelli del database (SQLAlchemy)."""
import json
from datetime import date, datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# ----------------------------------------------------------------------
# Vocabolari condivisi (usati da form, motore di analisi e report)
# ----------------------------------------------------------------------
CLIENT_TYPES = [
    ("azienda", "Azienda"),
    ("professionista", "Professionista"),
    ("dipendente", "Lavoratore dipendente"),
]
CLIENT_TYPE_BADGES = {
    "azienda": "tipo-azienda",
    "professionista": "tipo-professionista",
    "dipendente": "tipo-dipendente",
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
    ("scheda", "Scheda compilata"),
    ("altro", "Altro"),
]
DOCUMENT_CATEGORY_LABELS = dict(DOCUMENT_CATEGORIES)

# Ruoli delle persone collegate a un cliente (amministratori, soci, familiari…)
RUOLI_PERSONA = [
    ("amministratore_unico", "Amministratore unico"),
    ("amministratore_delegato", "Amministratore delegato"),
    ("presidente_cda", "Presidente del CdA"),
    ("consigliere", "Consigliere"),
    ("legale_rappresentante", "Legale rappresentante"),
    ("socio", "Socio"),
    ("procuratore", "Procuratore"),
    ("sindaco", "Sindaco / Revisore"),
    ("titolare_effettivo", "Titolare effettivo"),
    ("coniuge", "Coniuge / Convivente"),
    ("familiare", "Familiare"),
    ("altro", "Altro"),
]
RUOLI_PERSONA_LABELS = dict(RUOLI_PERSONA)
# I ruoli proposti per primi sul pulsante delle aziende
RUOLI_SOCIETARI = ("amministratore_unico", "amministratore_delegato", "presidente_cda", "consigliere",
                   "legale_rappresentante", "socio", "procuratore", "sindaco", "titolare_effettivo")

STATI_CIVILI = ["Celibe / Nubile", "Coniugato/a", "Unito/a civilmente", "Convivente",
                "Separato/a", "Divorziato/a", "Vedovo/a"]

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


class Client(db.Model):
    __tablename__ = "clients"

    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(20), nullable=False, default="azienda")
    ragione_sociale = db.Column(db.String(200), nullable=False)
    referente = db.Column(db.String(120))
    # Persone (professionisti e privati): il nominativo è «Nome Cognome»
    nome = db.Column(db.String(80))
    cognome = db.Column(db.String(80))
    data_nascita = db.Column(db.Date)
    luogo_nascita = db.Column(db.String(100))
    stato_civile = db.Column(db.String(30))
    nucleo_familiare = db.Column(db.Text)  # coniuge, figli ed età, persone a carico
    interessi = db.Column(db.Text)  # hobby, sport, abitudini: utili in trattativa
    # Residenza (se diversa dall'indirizzo principale)
    residenza_indirizzo = db.Column(db.String(200))
    residenza_citta = db.Column(db.String(100))
    residenza_cap = db.Column(db.String(5))
    residenza_provincia = db.Column(db.String(2))
    # Iscrizione all'albo (professionisti)
    albo = db.Column(db.String(150))  # es. Ordine degli Ingegneri
    albo_provincia = db.Column(db.String(60))
    albo_numero = db.Column(db.String(40))
    albo_data_iscrizione = db.Column(db.Date)
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
    fatturato_annuo = db.Column(db.Float)
    descrizione_attivita = db.Column(db.Text)
    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    persone = db.relationship(
        "PersonaCollegata",
        backref="cliente",
        cascade="all, delete-orphan",
        lazy=True,
        order_by="PersonaCollegata.id",
    )
    schede = db.relationship(
        "SchedaCompilata",
        backref="cliente",
        cascade="all, delete-orphan",
        lazy=True,
        order_by="SchedaCompilata.updated_at.desc()",
    )

    @property
    def tipo_label(self):
        return dict(CLIENT_TYPES).get(self.tipo, self.tipo)

    @property
    def tipo_badge(self):
        return CLIENT_TYPE_BADGES.get(self.tipo, "bg-secondary")

    @property
    def persona_fisica(self):
        return self.tipo in ("professionista", "dipendente")

    @property
    def nome_completo(self):
        """«Nome Cognome» per le persone, altrimenti la ragione sociale."""
        if self.persona_fisica and (self.nome or self.cognome):
            return " ".join(x for x in (self.nome, self.cognome) if x)
        return self.ragione_sociale

    @property
    def eta(self):
        return _eta(self.data_nascita)

    @property
    def polizze_attive(self):
        return [p for p in self.polizze if p.stato in ("attiva", "in_rinnovo")]

    @property
    def ultima_analisi(self):
        return self.analisi[0] if self.analisi else None

    def __repr__(self):  # pragma: no cover
        return f"<Client {self.ragione_sociale!r}>"


def _eta(nascita):
    if not nascita:
        return None
    oggi = date.today()
    return oggi.year - nascita.year - ((oggi.month, oggi.day) < (nascita.month, nascita.day))


class PersonaCollegata(db.Model):
    """Amministratori, consiglieri, soci, familiari… di un cliente."""

    __tablename__ = "client_persons"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False, index=True)
    ruolo = db.Column(db.String(40), nullable=False, default="amministratore_unico")
    ruolo_altro = db.Column(db.String(100))  # testo libero se ruolo = «altro»
    nome = db.Column(db.String(80))
    cognome = db.Column(db.String(80), nullable=False)
    codice_fiscale = db.Column(db.String(16))
    data_nascita = db.Column(db.Date)
    luogo_nascita = db.Column(db.String(100))
    indirizzo = db.Column(db.String(200))
    citta = db.Column(db.String(100))
    cap = db.Column(db.String(5))
    provincia = db.Column(db.String(2))
    email = db.Column(db.String(120))
    telefono = db.Column(db.String(30))
    quota_perc = db.Column(db.Float)  # quota di partecipazione dei soci
    dal = db.Column(db.Date)  # in carica dal
    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def nome_completo(self):
        return " ".join(x for x in (self.nome, self.cognome) if x)

    @property
    def ruolo_label(self):
        if self.ruolo == "altro" and self.ruolo_altro:
            return self.ruolo_altro
        return RUOLI_PERSONA_LABELS.get(self.ruolo, self.ruolo)

    @property
    def eta(self):
        return _eta(self.data_nascita)


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
    stato = db.Column(db.String(20), nullable=False, default="attiva")
    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    documenti = db.relationship("Document", backref="polizza", lazy=True)

    @property
    def ramo_label(self):
        return BRANCH_LABELS.get(self.ramo, self.ramo)

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
    categoria = db.Column(db.String(40), nullable=False, default="altro")
    filename = db.Column(db.String(300), nullable=False)  # nome su disco (sicuro)
    original_name = db.Column(db.String(300), nullable=False)
    dimensione = db.Column(db.Integer)  # dimensione in byte
    note = db.Column(db.Text)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


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
    # Privacy: PIN all'apertura (hash scrypt), codice di recupero, blocco per inattività
    pin_hash = db.Column(db.String(200))
    pin_recupero_hash = db.Column(db.String(200))
    blocco_minuti = db.Column(db.Integer, default=10)
    pin_tentativi = db.Column(db.Integer, default=0)
    pin_attesa_fino = db.Column(db.DateTime)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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


class AcademyProgress(db.Model):
    """Lezione dell'Accademia segnata come completata."""

    __tablename__ = "academy_progress"

    id = db.Column(db.Integer, primary_key=True)
    lezione_id = db.Column(db.String(80), unique=True, nullable=False)
    completata_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class QuizAttempt(db.Model):
    """Tentativo di quiz di un modulo dell'Accademia."""

    __tablename__ = "quiz_attempts"

    id = db.Column(db.Integer, primary_key=True)
    modulo_id = db.Column(db.String(80), nullable=False, index=True)
    punteggio = db.Column(db.Integer, nullable=False)
    totale = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    @property
    def percentuale(self) -> int:
        return round(100 * self.punteggio / self.totale) if self.totale else 0


class SchedaCompilata(db.Model):
    """Scheda dell'Accademia compilata dal gestionale e salvata nel cliente.

    `contenuto` conserva sia la struttura della scheda al momento del
    salvataggio (così una modifica futura ai modelli non altera le schede già
    compilate) sia i valori inseriti.
    """

    __tablename__ = "schede_compilate"

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False, index=True)
    scheda_id = db.Column(db.String(60), nullable=False)
    titolo = db.Column(db.String(200), nullable=False)
    data_compilazione = db.Column(db.Date, default=date.today, nullable=False)
    consulente = db.Column(db.String(120))
    contenuto_json = db.Column(db.Text, nullable=False, default="{}")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def contenuto(self) -> dict:
        try:
            return json.loads(self.contenuto_json or "{}")
        except ValueError:
            return {}

    @contenuto.setter
    def contenuto(self, value: dict) -> None:
        self.contenuto_json = json.dumps(value, ensure_ascii=False)

    @property
    def compilazione(self) -> tuple[int, int]:
        """(campi compilati, campi totali): misura quanto è completa la scheda."""
        valori = self.contenuto.get("valori", {})
        pieni = sum(1 for v in valori.values() if v not in ("", None, False))
        return pieni, len(valori)

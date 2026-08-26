"""Modelli di NutriStudio: utenti, assistiti, alimenti, piani, contenuti.

Un'unica app con due porte d'ingresso: la **nutrizionista** (che gestisce
assistiti, piani, ricette e articoli) e il **cliente** (che vede solo il
proprio piano, i propri progressi e i contenuti pubblicati).
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import date, datetime

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()

# «1 tazza (76 g)» → la coda con i grammi, e le porzioni che sono solo grammi.
_GRAMMI_FINALI = re.compile(r"\s*\(\s*[\d.,]+\s*g\s*\)\s*$")
_SOLO_GRAMMI = re.compile(r"^\s*[\d.,]+\s*g(\s+\w+)?\s*$")


# ----------------------------------------------------------------------
# Vocabolari
# ----------------------------------------------------------------------
RUOLI = ("nutrizionista", "cliente")

GIORNI = ["Lunedì", "Martedì", "Mercoledì", "Giovedì", "Venerdì", "Sabato", "Domenica"]

PASTI = ["Colazione", "Spuntino", "Pranzo", "Merenda", "Cena"]

DIETE = [
    "Standard",
    "Vegetariana",
    "Vegana",
    "Senza glutine",
    "Senza lattosio",
]

OBIETTIVI = [
    "Dimagrimento",
    "Mantenimento",
    "Aumento massa",
    "Nutrizione sportiva",
    "Gravidanza / allattamento",
    "Percorso clinico",
]

SESSI = ["F", "M", "Altro"]

STATI_PIANO = ["bozza", "pubblicato", "archiviato"]

TIPI_APPUNTAMENTO = ["Prima visita", "Controllo", "Misurazioni", "Videochiamata", "Altro"]

STATI_APPUNTAMENTO = ["programmato", "confermato", "svolto", "annullato"]

CATEGORIE_RICETTA = [
    "Colazione",
    "Primo piatto",
    "Secondo piatto",
    "Contorno",
    "Spuntino",
    "Dolce",
    "Bevanda",
]

CATEGORIE_ARTICOLO = [
    "Educazione alimentare",
    "Ricette e cucina",
    "Sport e movimento",
    "Benessere",
    "Domande frequenti",
    "Novità dello studio",
]

LIVELLO_ORDINE = {"danger": 0, "warning": 1, "info": 2}


def slugify(testo: str) -> str:
    """Slug ASCII minuscolo, usato per gli URL di ricette e articoli."""
    base = unicodedata.normalize("NFKD", testo or "").encode("ascii", "ignore").decode()
    base = re.sub(r"[^a-zA-Z0-9]+", "-", base).strip("-").lower()
    return base or "senza-titolo"


# ----------------------------------------------------------------------
# Utenti e accesso
# ----------------------------------------------------------------------
class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(200), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(300), nullable=False)
    nome = db.Column(db.String(150), nullable=False)
    ruolo = db.Column(db.String(20), nullable=False, default="cliente")
    attivo = db.Column(db.Boolean, nullable=False, default=True)
    deve_cambiare_password = db.Column(db.Boolean, nullable=False, default=False)
    ultimo_accesso = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    assistito_id = db.Column(db.Integer, db.ForeignKey("assistiti.id"), unique=True)
    assistito = db.relationship("Assistito", back_populates="utente")

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_nutrizionista(self) -> bool:
        return self.ruolo == "nutrizionista"

    @property
    def is_cliente(self) -> bool:
        return self.ruolo == "cliente"

    @property
    def iniziali(self) -> str:
        parti = [p for p in (self.nome or "").split() if p]
        return "".join(p[0].upper() for p in parti[:2]) or "?"

    def __repr__(self) -> str:  # pragma: no cover - debug
        return f"<User {self.email} ({self.ruolo})>"


# ----------------------------------------------------------------------
# Assistiti e misurazioni
# ----------------------------------------------------------------------
class Assistito(db.Model):
    __tablename__ = "assistiti"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    cognome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(200))
    telefono = db.Column(db.String(50))
    data_nascita = db.Column(db.Date)
    sesso = db.Column(db.String(10))
    altezza_cm = db.Column(db.Float)
    peso_iniziale_kg = db.Column(db.Float)
    obiettivo = db.Column(db.String(60))
    tipo_dieta = db.Column(db.String(40), default="Standard")
    target_kcal = db.Column(db.Integer, default=1800)
    allergie = db.Column(db.Text)
    patologie = db.Column(db.Text)
    preferenze = db.Column(db.Text)
    note = db.Column(db.Text)
    attivo = db.Column(db.Boolean, nullable=False, default=True)
    consenso_privacy = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    utente = db.relationship("User", back_populates="assistito", uselist=False)
    misurazioni = db.relationship(
        "Misurazione",
        back_populates="assistito",
        cascade="all, delete-orphan",
        order_by="Misurazione.data.desc()",
    )
    piani = db.relationship(
        "Piano",
        back_populates="assistito",
        cascade="all, delete-orphan",
        order_by="Piano.data_inizio.desc()",
    )
    messaggi = db.relationship(
        "Messaggio",
        back_populates="assistito",
        cascade="all, delete-orphan",
        order_by="Messaggio.created_at",
    )
    appuntamenti = db.relationship(
        "Appuntamento",
        back_populates="assistito",
        cascade="all, delete-orphan",
        order_by="Appuntamento.data_ora",
    )

    @property
    def nome_completo(self) -> str:
        return f"{self.nome} {self.cognome}".strip()

    @property
    def iniziali(self) -> str:
        return f"{(self.nome or '?')[0]}{(self.cognome or '')[:1]}".upper()

    @property
    def eta(self) -> int | None:
        if not self.data_nascita:
            return None
        oggi = date.today()
        return oggi.year - self.data_nascita.year - (
            (oggi.month, oggi.day) < (self.data_nascita.month, self.data_nascita.day)
        )

    @property
    def ultima_misurazione(self) -> "Misurazione | None":
        return self.misurazioni[0] if self.misurazioni else None

    @property
    def peso_attuale(self) -> float | None:
        ultima = self.ultima_misurazione
        if ultima and ultima.peso_kg:
            return ultima.peso_kg
        return self.peso_iniziale_kg

    @property
    def variazione_peso(self) -> float | None:
        """Differenza fra peso attuale e peso iniziale (negativa = calo)."""
        if self.peso_iniziale_kg and self.peso_attuale:
            return round(self.peso_attuale - self.peso_iniziale_kg, 1)
        return None

    @property
    def bmi(self) -> float | None:
        if self.altezza_cm and self.peso_attuale:
            m = self.altezza_cm / 100
            return round(self.peso_attuale / (m * m), 1)
        return None

    @property
    def bmi_categoria(self) -> str | None:
        bmi = self.bmi
        if bmi is None:
            return None
        if bmi < 18.5:
            return "Sottopeso"
        if bmi < 25:
            return "Normopeso"
        if bmi < 30:
            return "Sovrappeso"
        return "Obesità"

    @property
    def piano_attivo(self) -> "Piano | None":
        """Il piano pubblicato che copre oggi, altrimenti l'ultimo pubblicato."""
        oggi = date.today()
        pubblicati = [p for p in self.piani if p.stato == "pubblicato"]
        for p in pubblicati:
            if p.data_inizio <= oggi <= p.data_fine:
                return p
        return pubblicati[0] if pubblicati else None

    def __repr__(self) -> str:  # pragma: no cover - debug
        return f"<Assistito {self.nome_completo}>"


class Misurazione(db.Model):
    __tablename__ = "misurazioni"

    id = db.Column(db.Integer, primary_key=True)
    assistito_id = db.Column(db.Integer, db.ForeignKey("assistiti.id"), nullable=False)
    data = db.Column(db.Date, nullable=False, default=date.today)
    peso_kg = db.Column(db.Float)
    massa_grassa_perc = db.Column(db.Float)
    massa_magra_kg = db.Column(db.Float)
    vita_cm = db.Column(db.Float)
    fianchi_cm = db.Column(db.Float)
    torace_cm = db.Column(db.Float)
    braccio_cm = db.Column(db.Float)
    coscia_cm = db.Column(db.Float)
    note = db.Column(db.Text)
    inserita_dal_cliente = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    assistito = db.relationship("Assistito", back_populates="misurazioni")


# ----------------------------------------------------------------------
# Database alimenti
# ----------------------------------------------------------------------
class Alimento(db.Model):
    """Valori nutrizionali per 100 g di parte edibile (fonte: USDA FDC, CC0)."""

    __tablename__ = "alimenti"

    id = db.Column(db.Integer, primary_key=True)
    fdc_id = db.Column(db.Integer, index=True)
    nome = db.Column(db.String(250), nullable=False, index=True)
    nome_it = db.Column(db.String(250), index=True)
    categoria = db.Column(db.String(120))
    categoria_it = db.Column(db.String(120), index=True)
    spesa_query = db.Column(db.String(120))

    porzione_nome = db.Column(db.String(80))
    porzione_g = db.Column(db.Float, default=100)

    kcal = db.Column(db.Float)
    proteine = db.Column(db.Float)
    carboidrati = db.Column(db.Float)
    zuccheri = db.Column(db.Float)
    grassi = db.Column(db.Float)
    grassi_saturi = db.Column(db.Float)
    fibre = db.Column(db.Float)
    sodio = db.Column(db.Float)
    calcio = db.Column(db.Float)
    ferro = db.Column(db.Float)
    magnesio = db.Column(db.Float)
    potassio = db.Column(db.Float)
    zinco = db.Column(db.Float)
    vit_c = db.Column(db.Float)
    vit_d = db.Column(db.Float)
    vit_b12 = db.Column(db.Float)
    folati = db.Column(db.Float)

    # None = informazione non certa (nel foglio originale era «?»)
    vegan = db.Column(db.Boolean)
    vegetariano = db.Column(db.Boolean)
    senza_glutine = db.Column(db.Boolean)
    senza_lattosio = db.Column(db.Boolean)

    fonte_porzione = db.Column(db.String(40))
    da_verificare = db.Column(db.Boolean, nullable=False, default=False)
    personalizzato = db.Column(db.Boolean, nullable=False, default=False)

    @property
    def etichetta(self) -> str:
        return self.nome_it or self.nome

    @property
    def porzione_etichetta(self) -> str:
        return self.porzione_nome or f"{self.porzione_g or 100:.0f} g"

    @property
    def porzione_breve(self) -> str:
        """La porzione senza i grammi fra parentesi: «1 tazza (tritato)».

        I grammi li scrive già chi usa questa etichetta, e ripeterli due volte
        («1 × 1 porzione (120 g) (120 g)») rende la riga illeggibile.
        """
        testo = _GRAMMI_FINALI.sub("", (self.porzione_nome or "").strip()).strip()
        if not testo or _SOLO_GRAMMI.match(testo):
            return ""
        return testo

    @property
    def senza_valori(self) -> bool:
        """Alimento senza valori nutrizionali: entra nel piano e nella spesa,
        ma non nei totali finché non viene completato."""
        return self.kcal is None

    @property
    def termine_spesa(self) -> str:
        return self.spesa_query or (self.nome_it or self.nome).split(",")[0].strip()

    def __repr__(self) -> str:  # pragma: no cover - debug
        return f"<Alimento {self.etichetta}>"


# ----------------------------------------------------------------------
# Piani alimentari
# ----------------------------------------------------------------------
class Piano(db.Model):
    __tablename__ = "piani"

    id = db.Column(db.Integer, primary_key=True)
    assistito_id = db.Column(db.Integer, db.ForeignKey("assistiti.id"), nullable=False)
    titolo = db.Column(db.String(200), nullable=False)
    data_inizio = db.Column(db.Date, nullable=False, default=date.today)
    data_fine = db.Column(db.Date, nullable=False, default=date.today)
    target_kcal = db.Column(db.Integer, default=1800)
    tipo_dieta = db.Column(db.String(40), default="Standard")
    stato = db.Column(db.String(20), nullable=False, default="bozza")
    note_nutrizionista = db.Column(db.Text)
    note_cliente = db.Column(db.Text)
    riferimenti_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    pubblicato_at = db.Column(db.DateTime)

    assistito = db.relationship("Assistito", back_populates="piani")
    voci = db.relationship(
        "VocePiano",
        back_populates="piano",
        cascade="all, delete-orphan",
        order_by="VocePiano.giorno, VocePiano.ordine",
    )

    @property
    def pubblicato(self) -> bool:
        return self.stato == "pubblicato"

    @property
    def attivo_oggi(self) -> bool:
        return self.pubblicato and self.data_inizio <= date.today() <= self.data_fine

    @property
    def riferimenti(self) -> dict:
        """Riferimenti nutrizionali del piano (personalizzabili per assistito)."""
        from .nutrition import RIFERIMENTI_DEFAULT

        base = dict(RIFERIMENTI_DEFAULT)
        if self.riferimenti_json:
            try:
                base.update(json.loads(self.riferimenti_json))
            except (ValueError, TypeError):
                pass
        base["kcal"] = self.target_kcal or base.get("kcal", 1800)
        return base

    def imposta_riferimenti(self, valori: dict) -> None:
        self.riferimenti_json = json.dumps({k: v for k, v in valori.items() if v is not None})

    def voci_giorno(self, giorno: int) -> list["VocePiano"]:
        return [v for v in self.voci if v.giorno == giorno]

    def indice_giorno_oggi(self) -> int | None:
        """Indice 0-6 del giorno di oggi all'interno del piano, se in corso."""
        oggi = date.today()
        if not (self.data_inizio <= oggi <= self.data_fine):
            return None
        return (oggi - self.data_inizio).days % 7

    def __repr__(self) -> str:  # pragma: no cover - debug
        return f"<Piano {self.titolo} ({self.stato})>"


class VocePiano(db.Model):
    """Una riga del piano: un alimento (o una ricetta) dentro un pasto."""

    __tablename__ = "voci_piano"

    id = db.Column(db.Integer, primary_key=True)
    piano_id = db.Column(db.Integer, db.ForeignKey("piani.id"), nullable=False)
    giorno = db.Column(db.Integer, nullable=False, default=0)  # 0 = lunedì
    pasto = db.Column(db.String(30), nullable=False, default="Colazione")
    ordine = db.Column(db.Integer, nullable=False, default=0)

    alimento_id = db.Column(db.Integer, db.ForeignKey("alimenti.id"))
    ricetta_id = db.Column(db.Integer, db.ForeignKey("ricette.id"))
    testo_libero = db.Column(db.String(250))

    porzioni = db.Column(db.Float, nullable=False, default=1.0)
    nota = db.Column(db.String(250))

    piano = db.relationship("Piano", back_populates="voci")
    alimento = db.relationship("Alimento")
    ricetta = db.relationship("Ricetta")

    @property
    def etichetta(self) -> str:
        if self.alimento:
            return self.alimento.etichetta
        if self.ricetta:
            return self.ricetta.titolo
        return self.testo_libero or "—"

    @property
    def grammi(self) -> float | None:
        if self.alimento:
            return round((self.alimento.porzione_g or 100) * (self.porzioni or 1), 0)
        return None

    @property
    def quantita_etichetta(self) -> str:
        porzioni = self.porzioni or 1
        numero = f"{porzioni:g}".replace(".", ",")
        if self.alimento:
            porzione = self.alimento.porzione_breve
            grammi = f"{self.grammi:.0f} g"
            return f"{numero} × {porzione} · {grammi}" if porzione else grammi
        if self.ricetta:
            return f"{numero} × porzione"
        return numero if porzioni != 1 else ""


# ----------------------------------------------------------------------
# Ricettario
# ----------------------------------------------------------------------
class Ricetta(db.Model):
    __tablename__ = "ricette"

    id = db.Column(db.Integer, primary_key=True)
    titolo = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(220), unique=True, index=True)
    categoria = db.Column(db.String(60))
    descrizione = db.Column(db.Text)
    procedimento = db.Column(db.Text)
    tempo_minuti = db.Column(db.Integer)
    porzioni = db.Column(db.Integer, default=1)
    tags = db.Column(db.String(250))
    pubblicata = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    ingredienti = db.relationship(
        "IngredienteRicetta",
        back_populates="ricetta",
        cascade="all, delete-orphan",
        order_by="IngredienteRicetta.ordine",
    )

    @property
    def lista_tags(self) -> list[str]:
        return [t.strip() for t in (self.tags or "").split(",") if t.strip()]

    def assegna_slug(self) -> None:
        base = slugify(self.titolo)
        slug, n = base, 2
        while Ricetta.query.filter(Ricetta.slug == slug, Ricetta.id != self.id).first():
            slug = f"{base}-{n}"
            n += 1
        self.slug = slug


class IngredienteRicetta(db.Model):
    __tablename__ = "ingredienti_ricetta"

    id = db.Column(db.Integer, primary_key=True)
    ricetta_id = db.Column(db.Integer, db.ForeignKey("ricette.id"), nullable=False)
    alimento_id = db.Column(db.Integer, db.ForeignKey("alimenti.id"))
    testo = db.Column(db.String(200))
    grammi = db.Column(db.Float, default=0)
    ordine = db.Column(db.Integer, nullable=False, default=0)

    ricetta = db.relationship("Ricetta", back_populates="ingredienti")
    alimento = db.relationship("Alimento")

    @property
    def etichetta(self) -> str:
        if self.alimento:
            return self.alimento.etichetta
        return self.testo or "—"


# ----------------------------------------------------------------------
# Blog
# ----------------------------------------------------------------------
class Articolo(db.Model):
    __tablename__ = "articoli"

    id = db.Column(db.Integer, primary_key=True)
    titolo = db.Column(db.String(200), nullable=False)
    slug = db.Column(db.String(220), unique=True, index=True)
    sommario = db.Column(db.Text)
    corpo = db.Column(db.Text)
    categoria = db.Column(db.String(60))
    tags = db.Column(db.String(250))
    autore = db.Column(db.String(120))
    pubblicato = db.Column(db.Boolean, nullable=False, default=False)
    data_pubblicazione = db.Column(db.Date)
    tempo_lettura = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def lista_tags(self) -> list[str]:
        return [t.strip() for t in (self.tags or "").split(",") if t.strip()]

    def assegna_slug(self) -> None:
        base = slugify(self.titolo)
        slug, n = base, 2
        while Articolo.query.filter(Articolo.slug == slug, Articolo.id != self.id).first():
            slug = f"{base}-{n}"
            n += 1
        self.slug = slug

    def calcola_tempo_lettura(self) -> None:
        parole = len((self.corpo or "").split())
        self.tempo_lettura = max(1, round(parole / 200))


# ----------------------------------------------------------------------
# Messaggi e appuntamenti
# ----------------------------------------------------------------------
class Messaggio(db.Model):
    __tablename__ = "messaggi"

    id = db.Column(db.Integer, primary_key=True)
    assistito_id = db.Column(db.Integer, db.ForeignKey("assistiti.id"), nullable=False)
    mittente_ruolo = db.Column(db.String(20), nullable=False, default="nutrizionista")
    mittente_nome = db.Column(db.String(150))
    testo = db.Column(db.Text, nullable=False)
    letto = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    assistito = db.relationship("Assistito", back_populates="messaggi")


class Appuntamento(db.Model):
    __tablename__ = "appuntamenti"

    id = db.Column(db.Integer, primary_key=True)
    assistito_id = db.Column(db.Integer, db.ForeignKey("assistiti.id"), nullable=False)
    data_ora = db.Column(db.DateTime, nullable=False)
    durata_minuti = db.Column(db.Integer, default=45)
    tipo = db.Column(db.String(40), default="Controllo")
    luogo = db.Column(db.String(200))
    note = db.Column(db.Text)
    stato = db.Column(db.String(20), nullable=False, default="programmato")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    assistito = db.relationship("Assistito", back_populates="appuntamenti")


# ----------------------------------------------------------------------
# Notifiche
# ----------------------------------------------------------------------
class Notifica(db.Model):
    __tablename__ = "notifiche"

    id = db.Column(db.Integer, primary_key=True)
    chiave = db.Column(db.String(200), unique=True, index=True)
    messaggio = db.Column(db.String(400), nullable=False)
    livello = db.Column(db.String(20), nullable=False, default="info")
    categoria = db.Column(db.String(40))
    link = db.Column(db.String(300))
    destinatario = db.Column(db.String(20), nullable=False, default="nutrizionista")
    assistito_id = db.Column(db.Integer, db.ForeignKey("assistiti.id"))
    letta = db.Column(db.Boolean, nullable=False, default=False)
    inviata_email = db.Column(db.Boolean, nullable=False, default=False)
    inviata_email_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    assistito = db.relationship("Assistito")


# ----------------------------------------------------------------------
# Spesa online
# ----------------------------------------------------------------------
class FornitoreSpesa(db.Model):
    """Servizio di spesa online verso cui aprire il carrello (ricerca per prodotto)."""

    __tablename__ = "fornitori_spesa"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(80), nullable=False)
    url_template = db.Column(db.String(400), nullable=False)
    icona = db.Column(db.String(60), default="bi-bag")
    colore = db.Column(db.String(20), default="#198754")
    attivo = db.Column(db.Boolean, nullable=False, default=True)
    ordine = db.Column(db.Integer, nullable=False, default=0)

    def url_per(self, termine: str) -> str:
        from urllib.parse import quote_plus

        return self.url_template.replace("{query}", quote_plus(termine or ""))


FORNITORI_DEFAULT = [
    ("Glovo", "https://glovoapp.com/it/it/search/?q={query}", "bi-scooter", "#ffc244", 10),
    ("Everli", "https://it.everli.com/it/search?q={query}", "bi-cart4", "#00b16a", 20),
    ("Carrefour", "https://www.carrefour.it/ricerca?q={query}", "bi-shop", "#0050aa", 30),
    ("Esselunga", "https://www.esselunga.it/it-it/ricerca.html?q={query}", "bi-basket", "#e30613", 40),
    ("Deliveroo", "https://deliveroo.it/it/search?q={query}", "bi-bicycle", "#00ccbc", 50),
    ("Amazon", "https://www.amazon.it/s?k={query}", "bi-box-seam", "#ff9900", 60),
]


# ----------------------------------------------------------------------
# Impostazioni (riga unica)
# ----------------------------------------------------------------------
class Settings(db.Model):
    __tablename__ = "settings"

    id = db.Column(db.Integer, primary_key=True)

    # Studio
    nome_studio = db.Column(db.String(150), default="NutriStudio")
    professionista = db.Column(db.String(150), default="")
    email_studio = db.Column(db.String(200), default="")
    telefono_studio = db.Column(db.String(50), default="")
    sito_web = db.Column(db.String(200), default="")
    disclaimer = db.Column(
        db.Text,
        default=(
            "Strumento di supporto per professionisti della nutrizione. "
            "Non sostituisce il parere medico né una valutazione clinica."
        ),
    )

    # SMTP
    email_attive = db.Column(db.Boolean, default=False)
    smtp_host = db.Column(db.String(200), default="")
    smtp_port = db.Column(db.Integer, default=587)
    smtp_security = db.Column(db.String(10), default="tls")
    smtp_user = db.Column(db.String(200), default="")
    smtp_password = db.Column(db.String(200), default="")
    mail_from = db.Column(db.String(200), default="")
    mail_to = db.Column(db.String(400), default="")
    intervallo_minuti = db.Column(db.Integer, default=60)

    # Notifiche
    avvisa_piano_in_scadenza = db.Column(db.Boolean, default=True)
    giorni_preavviso_piano = db.Column(db.Integer, default=5)
    avvisa_appuntamenti = db.Column(db.Boolean, default=True)
    avvisa_nuovo_piano_al_cliente = db.Column(db.Boolean, default=True)

    @property
    def destinatari(self) -> list[str]:
        grezzo = (self.mail_to or "").replace(";", ",")
        return [d.strip() for d in grezzo.split(",") if d.strip()]

    @classmethod
    def get(cls) -> "Settings":
        riga = cls.query.first()
        if riga is None:
            riga = cls()
            db.session.add(riga)
            db.session.commit()
        return riga

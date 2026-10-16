"""Gestionale Assicurativo — applicazione Flask.

Gestionale per intermediari assicurativi: anagrafiche clienti
(professionisti, aziende e dipendenti), polizze, titoli e incassi, sinistri,
documenti, analisi automatica dei rischi, pipeline commerciale, follow-up,
scadenzario e notifiche. Accesso con utenti e ruoli, registro attività e
backup.
"""
import os
import re
import secrets
import time
from datetime import date, timedelta

from flask import Flask, g, render_template, request, url_for
from sqlalchemy import event, inspect, text
from sqlalchemy.engine import Engine

from .models import db
from .utils import formatta_euro

__version__ = "2.0.0"


@event.listens_for(Engine, "connect")
def _sqlite_pragmas(dbapi_connection, connection_record):  # pragma: no cover - dipende dal driver
    """Attesa sui lock: lo scheduler e le richieste web condividono il file SQLite."""
    if dbapi_connection.__class__.__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA busy_timeout = 10000")
        cursor.close()


def _ensure_schema() -> None:
    """Micro-migrazione per i database SQLite creati prima delle novità.

    `db.create_all()` crea le tabelle mancanti ma non aggiunge colonne alle
    tabelle già esistenti: qui aggiungiamo in modo idempotente le colonne
    introdotte dopo il primo rilascio, così chi ha già un database non deve
    ricrearlo.
    """
    inspector = inspect(db.engine)
    tabelle = set(inspector.get_table_names())

    # Mappa: tabella -> {colonna: DDL per aggiungerla}
    migrazioni = {
        "notifications": {
            "inviata_email": "ALTER TABLE notifications ADD COLUMN inviata_email BOOLEAN NOT NULL DEFAULT 0",
            "inviata_email_at": "ALTER TABLE notifications ADD COLUMN inviata_email_at DATETIME",
        },
        "clients": {
            "datore_lavoro": "ALTER TABLE clients ADD COLUMN datore_lavoro VARCHAR(200)",
            "data_nascita": "ALTER TABLE clients ADD COLUMN data_nascita DATE",
            "data_consenso_privacy": "ALTER TABLE clients ADD COLUMN data_consenso_privacy DATE",
            "consenso_marketing": "ALTER TABLE clients ADD COLUMN consenso_marketing BOOLEAN NOT NULL DEFAULT 0",
            "data_adeguatezza": "ALTER TABLE clients ADD COLUMN data_adeguatezza DATE",
            "documento_tipo": "ALTER TABLE clients ADD COLUMN documento_tipo VARCHAR(30)",
            "documento_numero": "ALTER TABLE clients ADD COLUMN documento_numero VARCHAR(40)",
            "documento_scadenza": "ALTER TABLE clients ADD COLUMN documento_scadenza DATE",
        },
        "policies": {
            "provvigione_perc": "ALTER TABLE policies ADD COLUMN provvigione_perc FLOAT",
            "preavviso_disdetta_giorni": "ALTER TABLE policies ADD COLUMN preavviso_disdetta_giorni INTEGER",
            "data_disdetta": "ALTER TABLE policies ADD COLUMN data_disdetta DATE",
        },
        "users": {
            "sessione_versione": "ALTER TABLE users ADD COLUMN sessione_versione INTEGER NOT NULL DEFAULT 0",
        },
        "documents": {
            "dimensione": "ALTER TABLE documents ADD COLUMN dimensione INTEGER",
            "claim_id": "ALTER TABLE documents ADD COLUMN claim_id INTEGER",
        },
        "followups": {
            "policy_id": "ALTER TABLE followups ADD COLUMN policy_id INTEGER",
            "auto_generato": "ALTER TABLE followups ADD COLUMN auto_generato BOOLEAN NOT NULL DEFAULT 0",
        },
        "settings": {
            "studio_nome": "ALTER TABLE settings ADD COLUMN studio_nome VARCHAR(200)",
            "studio_rui": "ALTER TABLE settings ADD COLUMN studio_rui VARCHAR(40)",
            "studio_piva": "ALTER TABLE settings ADD COLUMN studio_piva VARCHAR(16)",
            "studio_indirizzo": "ALTER TABLE settings ADD COLUMN studio_indirizzo VARCHAR(250)",
            "studio_contatti": "ALTER TABLE settings ADD COLUMN studio_contatti VARCHAR(250)",
            "backup_automatico": "ALTER TABLE settings ADD COLUMN backup_automatico BOOLEAN NOT NULL DEFAULT 1",
            "backup_conservati": "ALTER TABLE settings ADD COLUMN backup_conservati INTEGER DEFAULT 14",
            "ultimo_backup_at": "ALTER TABLE settings ADD COLUMN ultimo_backup_at DATETIME",
            "rinnovo_tacito_automatico": "ALTER TABLE settings ADD COLUMN rinnovo_tacito_automatico BOOLEAN NOT NULL DEFAULT 1",
            "emissione_quietanze_automatica": "ALTER TABLE settings ADD COLUMN emissione_quietanze_automatica BOOLEAN NOT NULL DEFAULT 1",
            "anticipo_quietanze_giorni": "ALTER TABLE settings ADD COLUMN anticipo_quietanze_giorni INTEGER DEFAULT 30",
            "scadenza_automatica": "ALTER TABLE settings ADD COLUMN scadenza_automatica BOOLEAN NOT NULL DEFAULT 1",
            "tolleranza_scadenza_giorni": "ALTER TABLE settings ADD COLUMN tolleranza_scadenza_giorni INTEGER DEFAULT 30",
        },
    }

    cambiato = False
    for tabella, colonne in migrazioni.items():
        if tabella not in tabelle:
            continue
        esistenti = {c["name"] for c in inspector.get_columns(tabella)}
        for colonna, ddl in colonne.items():
            if colonna not in esistenti:
                db.session.execute(text(ddl))
                cambiato = True
    if cambiato:
        db.session.commit()

    # Indici delle colonne aggiunte con ALTER TABLE e vincolo anti-duplicati
    # sulle rate (doppio clic su «Genera titoli» o «Rinnova»).
    indici = [
        "CREATE INDEX IF NOT EXISTS ix_documents_claim_id ON documents (claim_id)",
        "CREATE INDEX IF NOT EXISTS ix_followups_policy_id ON followups (policy_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ux_titles_rata ON titles (policy_id, data_effetto, numero_rata) "
        "WHERE stato != 'stornato' AND numero_rata IS NOT NULL AND tipo != 'appendice'",
    ]
    if db.engine.dialect.name == "sqlite":
        for ddl in indici:
            try:
                db.session.execute(text(ddl))
                db.session.commit()
            except Exception:  # noqa: BLE001 - es. duplicati già presenti: il vincolo resta solo applicativo
                db.session.rollback()

    _migra_chiavi_notifiche()


_CHIAVE_POLIZZA_VECCHIA = re.compile(r"^polizza:(\d+):(\d+|scaduta)$")
_CHIAVE_FOLLOWUP_VECCHIA = re.compile(r"^followup:(\d+):(ritardo|oggi|prossimo)$")


def _migra_chiavi_notifiche() -> None:
    """Converte le chiavi delle notifiche delle versioni precedenti nel formato con la data.

    Evita che, dopo l'aggiornamento, gli avvisi già ricevuti (anche via email)
    vengano generati e inviati una seconda volta.
    """
    from .models import FollowUp, Notification, Policy

    vecchie = Notification.query.filter(
        db.or_(Notification.dedup_key.like("polizza:%"), Notification.dedup_key.like("followup:%"))
    ).all()
    esistenti = {n.dedup_key for n in vecchie}
    cambiato = False
    for n in vecchie:
        nuova = None
        m = _CHIAVE_POLIZZA_VECCHIA.match(n.dedup_key)
        if m:
            policy = db.session.get(Policy, int(m.group(1)))
            if policy and policy.data_scadenza:
                nuova = f"polizza:{policy.id}:{policy.data_scadenza.isoformat()}:{m.group(2)}"
        m = _CHIAVE_FOLLOWUP_VECCHIA.match(n.dedup_key)
        if m:
            fu = db.session.get(FollowUp, int(m.group(1)))
            if fu:
                nuova = f"followup:{fu.id}:{fu.data_scadenza.isoformat()}:{m.group(2)}"
        if nuova and nuova not in esistenti:
            esistenti.discard(n.dedup_key)
            n.dedup_key = nuova
            esistenti.add(nuova)
            cambiato = True
    if cambiato:
        db.session.commit()


def init_db() -> None:
    """Crea le tabelle mancanti, applica le micro-migrazioni e la riga delle impostazioni."""
    from .models import Settings

    db.create_all()
    _ensure_schema()
    # Creata subito: così Settings.get() non deve mai fare commit durante una richiesta.
    Settings.get()


def _secret_key(app: Flask) -> str:
    """Chiave di sessione: da ambiente, altrimenti generata una volta e salvata.

    Una chiave fissa nel codice renderebbe falsificabili i cookie di sessione
    di chiunque usi l'eseguibile: la generiamo casualmente al primo avvio.
    """
    percorso = os.environ.get("SECRET_KEY_FILE") or os.path.join(app.instance_path, "secret_key")
    try:
        with open(percorso, encoding="utf-8") as fh:
            chiave = fh.read().strip()
            if chiave:
                return chiave
    except OSError:
        pass
    chiave = secrets.token_hex(32)
    try:
        os.makedirs(os.path.dirname(percorso) or ".", exist_ok=True)
        with open(percorso, "w", encoding="utf-8") as fh:
            fh.write(chiave)
        try:
            os.chmod(percorso, 0o600)
        except OSError:  # pragma: no cover - es. filesystem senza permessi POSIX
            pass
    except OSError:  # pragma: no cover - cartella non scrivibile: chiave valida fino al riavvio
        app.logger.warning("Impossibile salvare la chiave di sessione in %s", percorso)
    return chiave


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)

    os.makedirs(app.instance_path, exist_ok=True)

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY"),
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            "DATABASE_URL",
            "sqlite:///" + os.path.join(app.instance_path, "gestionale.db"),
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        UPLOAD_FOLDER=os.environ.get("UPLOAD_FOLDER", os.path.join(app.instance_path, "uploads")),
        BACKUP_FOLDER=os.environ.get("BACKUP_FOLDER", os.path.join(app.instance_path, "backups")),
        MAX_CONTENT_LENGTH=20 * 1024 * 1024,  # 20 MB per richiesta
        MAX_RESTORE_SIZE=512 * 1024 * 1024,  # ripristino backup: fino a 512 MB
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "").lower() in ("1", "true", "yes"),
        PERMANENT_SESSION_LIFETIME=timedelta(hours=10),
        CSRF_ENABLED=True,
        PASSWORD_HASH_METHOD="scrypt",
        # Rigenerazione notifiche/follow-up automatici: al massimo ogni N secondi.
        NOTIFICHE_REFRESH_SECONDI=60,
        ELEMENTI_PER_PAGINA=25,
    )
    if test_config:
        app.config.update(test_config)
    if not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = _secret_key(app)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    with app.app_context():
        init_db()

    # La sicurezza va registrata per prima: i suoi before_request girano
    # prima di quelli dei blueprint e della generazione notifiche.
    from .security import init_security

    init_security(app)

    from .cli import register_cli
    from .routes import register_blueprints

    register_blueprints(app)
    register_cli(app)

    # ------------------------------------------------------------------
    # Filtri Jinja e variabili globali dei template
    # ------------------------------------------------------------------
    @app.template_filter("data_it")
    def data_it(value):
        if value is None:
            return "—"
        return value.strftime("%d/%m/%Y")

    @app.template_filter("dataora_it")
    def dataora_it(value):
        if value is None:
            return "—"
        return value.strftime("%d/%m/%Y %H:%M")

    app.add_template_filter(formatta_euro, "euro")

    @app.template_filter("perc")
    def perc(value, decimali=1):
        if value is None:
            return "—"
        return f"{value:.{decimali}f}%".replace(".", ",")

    @app.template_filter("num_input")
    def num_input(value):
        """Importo per un campo di input (es. 1234,56): vuoto se assente."""
        if value is None or value == "":
            return ""
        if isinstance(value, str):
            return value
        return f"{value:.2f}".replace(".", ",")

    @app.template_filter("giorni")
    def giorni(value):
        """Distanza in giorni in parole: «oggi», «domani», «tra 5 giorni», «da 3 giorni»."""
        if value is None:
            return "—"
        if value == 0:
            return "oggi"
        if value == 1:
            return "domani"
        if value == -1:
            return "da ieri"
        return f"tra {value} giorni" if value > 0 else f"da {-value} giorni"

    def plurale(numero, singolare: str, plurale_: str) -> str:
        """«1 titolo», «3 titoli»."""
        return f"{numero} {singolare if numero == 1 else plurale_}"

    app.jinja_env.globals["plurale"] = plurale

    def url_pagina(numero: int) -> str:
        """URL della pagina corrente con un altro numero di pagina (paginazione)."""
        argomenti = dict(request.view_args or {})
        argomenti.update(request.args.to_dict())
        argomenti["page"] = numero
        return url_for(request.endpoint, **argomenti)

    from .models import PAYMENT_METHODS

    app.jinja_env.globals["url_pagina"] = url_pagina
    app.jinja_env.globals["versione"] = __version__
    app.jinja_env.globals["payment_methods"] = PAYMENT_METHODS

    @app.context_processor
    def inject_globals():
        from .models import Notification, Settings

        dati = {"oggi": date.today(), "notifiche_non_lette": 0, "studio": None}
        if g.get("user") is not None:
            dati["notifiche_non_lette"] = Notification.query.filter_by(letta=False).count()
            dati["studio"] = Settings.get()
        return dati

    # ------------------------------------------------------------------
    # Notifiche e follow-up automatici (al massimo ogni N secondi)
    # ------------------------------------------------------------------
    stato_refresh = {"ultimo": 0.0}

    @app.before_request
    def refresh_notifications():
        if request.endpoint in (None, "static") or g.get("user") is None:
            return
        intervallo = app.config.get("NOTIFICHE_REFRESH_SECONDI", 60)
        adesso = time.monotonic()
        if intervallo and adesso - stato_refresh["ultimo"] < intervallo:
            return

        from .notifications import LOCK, aggiorna_tutto

        # Se lo scheduler (o un'altra richiesta) sta già aggiornando, non aspettiamo.
        if not LOCK.acquire(blocking=False):
            return
        try:
            stato_refresh["ultimo"] = adesso
            aggiorna_tutto()
        except Exception:  # noqa: BLE001 - le notifiche non devono mai bloccare l'utente
            db.session.rollback()
            app.logger.exception("Aggiornamento automatico di notifiche e scadenze non riuscito.")
        finally:
            LOCK.release()

    # ------------------------------------------------------------------
    # Pagine di errore
    # ------------------------------------------------------------------
    messaggi_errore = {
        400: ("Richiesta non valida", "La richiesta non può essere elaborata."),
        403: ("Accesso negato", "Non hai i permessi per accedere a questa pagina."),
        404: ("Pagina non trovata", "La pagina o l'elemento richiesto non esiste (o è stato eliminato)."),
        405: ("Operazione non consentita", "Usa i pulsanti della pagina per eseguire questa operazione."),
        413: ("File troppo grande", "Il file supera la dimensione massima consentita."),
        500: ("Errore interno", "Si è verificato un errore imprevisto. Riprova; se il problema persiste contatta l'assistenza."),
    }

    def _pagina_errore(errore):
        codice = getattr(errore, "code", 500) or 500
        titolo, messaggio = messaggi_errore.get(codice, messaggi_errore[500])
        descrizione = getattr(errore, "description", None)
        if codice in (400, 403) and descrizione and not descrizione.startswith("The "):
            messaggio = descrizione
        if codice == 500:
            db.session.rollback()
        return render_template("errors/error.html", codice=codice, titolo=titolo, messaggio=messaggio), codice

    for codice in messaggi_errore:
        app.register_error_handler(codice, _pagina_errore)

    return app

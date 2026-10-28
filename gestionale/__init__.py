"""Deal Combined — applicazione Flask (gestionale assicurativo).

Gestionale per intermediari assicurativi: anagrafiche clienti
(professionisti e aziende), polizze, documenti, analisi automatica dei
rischi, follow-up, scadenzario e notifiche.
"""
__version__ = "2.3.0"

import os
from datetime import date

from urllib.parse import urlparse

from flask import Flask, abort, request
from sqlalchemy import inspect, text

from .models import db


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
            **{col: f"ALTER TABLE clients ADD COLUMN {col} {tipo}" for col, tipo in {
                "nome": "VARCHAR(80)", "cognome": "VARCHAR(80)", "data_nascita": "DATE",
                "luogo_nascita": "VARCHAR(100)", "stato_civile": "VARCHAR(30)", "nucleo_familiare": "TEXT",
                "interessi": "TEXT", "residenza_indirizzo": "VARCHAR(200)", "residenza_citta": "VARCHAR(100)",
                "residenza_cap": "VARCHAR(5)", "residenza_provincia": "VARCHAR(2)", "albo": "VARCHAR(150)",
                "albo_provincia": "VARCHAR(60)", "albo_numero": "VARCHAR(40)", "albo_data_iscrizione": "DATE",
            }.items()},
        },
        "policies": {
            "provvigione_perc": "ALTER TABLE policies ADD COLUMN provvigione_perc FLOAT",
        },
        "documents": {
            "dimensione": "ALTER TABLE documents ADD COLUMN dimensione INTEGER",
        },
        "settings": {
            "pin_hash": "ALTER TABLE settings ADD COLUMN pin_hash VARCHAR(200)",
            "pin_recupero_hash": "ALTER TABLE settings ADD COLUMN pin_recupero_hash VARCHAR(200)",
            "blocco_minuti": "ALTER TABLE settings ADD COLUMN blocco_minuti INTEGER DEFAULT 10",
            "pin_tentativi": "ALTER TABLE settings ADD COLUMN pin_tentativi INTEGER DEFAULT 0",
            "pin_attesa_fino": "ALTER TABLE settings ADD COLUMN pin_attesa_fino DATETIME",
        },
        "client_persons": {
            "persona_client_id": "ALTER TABLE client_persons ADD COLUMN persona_client_id INTEGER",
        },
        "followups": {
            "policy_id": "ALTER TABLE followups ADD COLUMN policy_id INTEGER",
            "auto_generato": "ALTER TABLE followups ADD COLUMN auto_generato BOOLEAN NOT NULL DEFAULT 0",
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


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)

    os.makedirs(app.instance_path, exist_ok=True)
    default_upload_folder = os.path.join(app.instance_path, "uploads")

    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY", "dev-cambiami-in-produzione"),
        SQLALCHEMY_DATABASE_URI=os.environ.get(
            "DATABASE_URL",
            "sqlite:///" + os.path.join(app.instance_path, "gestionale.db"),
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        UPLOAD_FOLDER=os.environ.get("UPLOAD_FOLDER", default_upload_folder),
        MAX_CONTENT_LENGTH=20 * 1024 * 1024,  # 20 MB per file
    )
    if test_config:
        app.config.update(test_config)

    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    with app.app_context():
        db.create_all()
        _ensure_schema()

    from .routes import register_blueprints

    register_blueprints(app)

    # ------------------------------------------------------------------
    # Filtri Jinja e variabili globali dei template
    # ------------------------------------------------------------------
    @app.template_filter("data_it")
    def data_it(value):
        if value is None:
            return "—"
        return value.strftime("%d/%m/%Y")

    @app.template_filter("euro")
    def euro(value):
        if value is None:
            return "—"
        return ("€ {:,.2f}".format(value)).replace(",", "X").replace(".", ",").replace("X", ".")

    @app.context_processor
    def inject_globals():
        from .models import Notification

        unread = Notification.query.filter_by(letta=False).count()
        return {"notifiche_non_lette": unread, "oggi": date.today()}

    @app.before_request
    def blocca_richieste_da_altri_siti():
        """Le modifiche arrivano solo dalle pagine dell'app: un sito esterno
        aperto nel browser non può inviare moduli verso il gestionale."""
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            provenienza = request.headers.get("Origin") or request.headers.get("Referer")
            if provenienza and urlparse(provenienza).netloc != request.host:
                abort(403)

    @app.before_request
    def refresh_notifications():
        from .notifications import auto_create_renewal_followups, generate_notifications

        if app.config.get("DC_IN_PAUSA"):
            return  # finestra nella barra o archivio aperto sull'altro PC: niente scritture
        auto_create_renewal_followups()
        generate_notifications()

    return app

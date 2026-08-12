"""Gestionale Assicurativo — applicazione Flask.

Gestionale per intermediari assicurativi: anagrafiche clienti
(professionisti e aziende), polizze, documenti, analisi automatica dei
rischi, follow-up, scadenzario e notifiche.
"""
import os
from datetime import date

from flask import Flask
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
    if "notifications" not in inspector.get_table_names():
        return
    esistenti = {c["name"] for c in inspector.get_columns("notifications")}
    nuove = {
        "inviata_email": "ALTER TABLE notifications ADD COLUMN inviata_email BOOLEAN NOT NULL DEFAULT 0",
        "inviata_email_at": "ALTER TABLE notifications ADD COLUMN inviata_email_at DATETIME",
    }
    for colonna, ddl in nuove.items():
        if colonna not in esistenti:
            db.session.execute(text(ddl))
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
    def refresh_notifications():
        from .notifications import generate_notifications

        generate_notifications()

    return app

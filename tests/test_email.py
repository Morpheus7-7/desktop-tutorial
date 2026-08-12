"""Test delle notifiche via email e della pagina Impostazioni.

L'invio SMTP reale è sostituito da un monkeypatch: non viene contattato alcun
server, ma verifichiamo che il messaggio venga costruito e che le notifiche
siano marcate come inviate.
"""
import os
import tempfile
from datetime import datetime

import pytest

from gestionale import create_app
from gestionale import mailer
from gestionale.models import Notification, Settings, db


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    upload_dir = tempfile.mkdtemp()
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
            "UPLOAD_FOLDER": upload_dir,
            "SECRET_KEY": "test",
        }
    )
    yield app
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    # Evita che variabili d'ambiente dell'host influenzino i test.
    for var in ("SMTP_HOST", "SMTP_PORT", "SMTP_SECURITY", "SMTP_USER",
                "SMTP_PASSWORD", "MAIL_FROM", "MAIL_TO", "EMAIL_ATTIVE"):
        monkeypatch.delenv(var, raising=False)


def _configura(app, **kwargs):
    with app.app_context():
        s = Settings.get()
        s.email_attive = kwargs.get("email_attive", True)
        s.smtp_host = kwargs.get("smtp_host", "smtp.example.com")
        s.smtp_port = kwargs.get("smtp_port", 587)
        s.smtp_security = kwargs.get("smtp_security", "tls")
        s.smtp_user = kwargs.get("smtp_user", "user@example.com")
        s.smtp_password = kwargs.get("smtp_password", "segreta")
        s.mail_from = kwargs.get("mail_from", "gestionale@example.com")
        s.mail_to = kwargs.get("mail_to", "titolare@example.com, socio@example.com")
        db.session.commit()


# ----------------------------------------------------------------------
# Configurazione effettiva
# ----------------------------------------------------------------------
def test_effective_config_env_override(app, monkeypatch):
    _configura(app)
    monkeypatch.setenv("SMTP_HOST", "smtp.override.it")
    monkeypatch.setenv("MAIL_TO", "solo@override.it")
    with app.app_context():
        cfg = mailer.effective_config()
        assert cfg.host == "smtp.override.it"
        assert cfg.destinatari == ["solo@override.it"]


def test_settings_destinatari_parsing(app):
    _configura(app, mail_to="a@x.it; b@x.it ,c@x.it")
    with app.app_context():
        assert Settings.get().destinatari == ["a@x.it", "b@x.it", "c@x.it"]


# ----------------------------------------------------------------------
# Digest
# ----------------------------------------------------------------------
def test_build_digest_orders_and_counts(app):
    with app.app_context():
        notifiche = [
            Notification(tipo="info", livello="info", messaggio="Info X",
                         dedup_key="k1", created_at=datetime(2026, 1, 1)),
            Notification(tipo="scadenza_polizza", livello="danger",
                         messaggio="Polizza SCADUTA", dedup_key="k2",
                         created_at=datetime(2026, 1, 2)),
        ]
        subject, text_body, html_body = mailer.build_digest(notifiche)
        assert "2" in subject and "urgent" in subject
        # La notifica urgente (danger) compare prima nel testo.
        assert text_body.index("Polizza SCADUTA") < text_body.index("Info X")
        assert "Polizza SCADUTA" in html_body


# ----------------------------------------------------------------------
# Invio (SMTP fittizio)
# ----------------------------------------------------------------------
def test_send_pending_marks_notifications(app, monkeypatch):
    inviati = []
    monkeypatch.setattr(mailer, "_send", lambda cfg, msg, **kw: inviati.append(msg))
    _configura(app)
    with app.app_context():
        db.session.add(Notification(tipo="followup", livello="warning",
                                    messaggio="Follow-up oggi", dedup_key="fu1"))
        db.session.commit()
        n = mailer.send_pending_notifications()
        assert n == 1
        assert len(inviati) == 1
        assert Notification.query.filter_by(inviata_email=True).count() == 1
        # Un secondo invio non re-invia nulla (già marcata).
        assert mailer.send_pending_notifications() == 0
        assert len(inviati) == 1


def test_send_pending_skips_when_disabled(app, monkeypatch):
    inviati = []
    monkeypatch.setattr(mailer, "_send", lambda cfg, msg, **kw: inviati.append(msg))
    _configura(app, email_attive=False)
    with app.app_context():
        db.session.add(Notification(tipo="info", livello="info",
                                    messaggio="X", dedup_key="x1"))
        db.session.commit()
        assert mailer.send_pending_notifications() == 0
        assert inviati == []


def test_send_test_email_success(app, monkeypatch):
    catturati = []
    monkeypatch.setattr(mailer, "_send", lambda cfg, msg, **kw: catturati.append((cfg, msg)))
    _configura(app)
    with app.app_context():
        ok, messaggio = mailer.send_test_email()
        assert ok is True
        assert "prova" in messaggio.lower()
        cfg, msg = catturati[0]
        assert msg["To"] == "titolare@example.com, socio@example.com"


def test_send_test_email_incomplete_config(app):
    _configura(app, smtp_host="", mail_to="")
    with app.app_context():
        ok, messaggio = mailer.send_test_email()
        assert ok is False
        assert "incompleta" in messaggio.lower()


# ----------------------------------------------------------------------
# Pagina Impostazioni
# ----------------------------------------------------------------------
def test_settings_page_loads(client):
    resp = client.get("/impostazioni/")
    assert resp.status_code == 200
    assert "Notifiche via email".encode() in resp.data


def test_settings_save_and_password_preserved(client, app):
    client.post("/impostazioni/", data={
        "email_attive": "on", "smtp_host": "smtp.test.it", "smtp_port": "465",
        "smtp_security": "ssl", "smtp_user": "u@test.it", "smtp_password": "pw1",
        "mail_from": "from@test.it", "mail_to": "to@test.it", "intervallo_minuti": "15",
    }, follow_redirects=True)
    with app.app_context():
        s = Settings.get()
        assert s.email_attive is True
        assert s.smtp_host == "smtp.test.it"
        assert s.smtp_password == "pw1"

    # Un secondo salvataggio con password vuota non deve cancellarla.
    client.post("/impostazioni/", data={
        "email_attive": "on", "smtp_host": "smtp.test.it", "smtp_port": "465",
        "smtp_security": "ssl", "smtp_user": "u@test.it", "smtp_password": "",
        "mail_from": "from@test.it", "mail_to": "to@test.it", "intervallo_minuti": "15",
    }, follow_redirects=True)
    with app.app_context():
        assert Settings.get().smtp_password == "pw1"


def test_settings_send_now_route(client, app, monkeypatch):
    monkeypatch.setattr(mailer, "_send", lambda cfg, msg, **kw: None)
    _configura(app)
    with app.app_context():
        db.session.add(Notification(tipo="info", livello="info",
                                    messaggio="Da inviare", dedup_key="dm1"))
        db.session.commit()
    resp = client.post("/impostazioni/invia-ora", follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        assert Notification.query.filter_by(inviata_email=True).count() == 1

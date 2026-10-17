"""Test delle notifiche via email e della pagina Impostazioni.

L'invio SMTP reale è sostituito da un monkeypatch: non viene contattato alcun
server, ma verifichiamo che il messaggio venga costruito e che le notifiche
siano marcate come inviate.
"""
from datetime import datetime

import pytest

from gestionale import mailer
from gestionale.models import Notification, Settings, db


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


# ----------------------------------------------------------------------
# Sicurezza e concorrenza del digest
# ----------------------------------------------------------------------
def test_build_digest_escape_dati_utente(app, monkeypatch):
    monkeypatch.setenv("APP_BASE_URL", "http://127.0.0.1:5000")
    with app.app_context():
        n = Notification(
            tipo="followup", livello="danger", dedup_key="h1",
            messaggio='Follow-up per <b>X</b> & Y <a href="https://phish.example">Rinnova qui</a>',
            link="/clienti/1?a=1&b='2'", created_at=datetime(2026, 1, 1),
        )
        _, text_body, html_body = mailer.build_digest([n])
    assert "&lt;b&gt;X&lt;/b&gt; &amp; Y" in html_body
    assert "<b>X</b>" not in html_body and 'href="https://phish.example"' not in html_body
    assert "href='http://127.0.0.1:5000/clienti/1?a=1&amp;b=&#39;2&#39;'" in html_body
    # Il testo semplice resta leggibile così com'è.
    assert '<b>X</b> & Y <a href="https://phish.example">' in text_body


def test_invii_contemporanei_un_solo_digest(app, monkeypatch):
    import threading
    import time

    inviati = []

    def _smtp_lento(cfg, msg, **kw):
        time.sleep(0.3)
        inviati.append(msg)

    monkeypatch.setattr(mailer, "_send", _smtp_lento)
    _configura(app)
    with app.app_context():
        db.session.add(Notification(tipo="info", livello="info", messaggio="Uno", dedup_key="c1"))
        db.session.commit()

    risultati = []

    def _invia():
        with app.app_context():
            risultati.append(mailer.send_pending_notifications())
            db.session.remove()

    fili = [threading.Thread(target=_invia) for _ in range(2)]  # scheduler e «Invia ora»
    for f in fili:
        f.start()
    for f in fili:
        f.join(10)
    assert len(inviati) == 1
    assert sorted(risultati) == [0, 1]
    with app.app_context():
        assert Notification.query.filter_by(inviata_email=True).count() == 1


def test_commit_fallito_dopo_invio_annulla_e_riprova(app, monkeypatch):
    from sqlalchemy.exc import OperationalError

    monkeypatch.setattr(mailer, "_send", lambda cfg, msg, **kw: None)
    _configura(app)
    with app.app_context():
        db.session.add(Notification(tipo="info", livello="info", messaggio="Uno", dedup_key="f1"))
        db.session.commit()
        commit_vero = db.session.commit
        fallimenti = {"restanti": 1}

        def _commit_instabile():
            if fallimenti["restanti"]:
                fallimenti["restanti"] -= 1
                raise OperationalError("COMMIT", {}, Exception("database is locked"))
            return commit_vero()

        monkeypatch.setattr(db.session, "commit", _commit_instabile)
        assert mailer.send_pending_notifications() == 1
        monkeypatch.setattr(db.session, "commit", commit_vero)
        db.session.expire_all()
        assert Notification.query.filter_by(inviata_email=True).count() == 1


def test_commit_sempre_fallito_dopo_invio_non_solleva(app, monkeypatch, caplog):
    from sqlalchemy.exc import OperationalError

    monkeypatch.setattr(mailer, "_send", lambda cfg, msg, **kw: None)
    _configura(app)
    with app.app_context():
        db.session.add(Notification(tipo="info", livello="info", messaggio="Uno", dedup_key="f2"))
        db.session.commit()
        commit_vero = db.session.commit

        def _commit_rotto():
            raise OperationalError("COMMIT", {}, Exception("disk I/O error"))

        monkeypatch.setattr(db.session, "commit", _commit_rotto)
        assert mailer.send_pending_notifications() == 1  # l'email è comunque partita
        monkeypatch.setattr(db.session, "commit", commit_vero)
        db.session.expire_all()
        assert Notification.query.filter_by(inviata_email=True).count() == 0
    assert "potrebbero essere spedite di nuovo" in caplog.text
    assert not mailer._invio_lock.locked()

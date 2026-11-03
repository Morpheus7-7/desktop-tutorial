"""Test di accesso, ruoli, protezione CSRF, redirect sicuri e registro attività."""
import re

import pytest
from conftest import ADMIN_PASSWORD, ADMIN_USER, add_user, login, make_app
from gestionale.models import AuditLog, Client, User, db
from gestionale.security import MAX_TENTATIVI_LOGIN


# ----------------------------------------------------------------------
# Primo avvio
# ----------------------------------------------------------------------
def test_first_run_redirects_to_setup(tmp_path):
    app = make_app(tmp_path)
    c = app.test_client()
    resp = c.get("/")
    assert resp.status_code == 302
    assert "/configurazione-iniziale" in resp.headers["Location"]
    assert c.get("/accesso").headers["Location"].endswith("/configurazione-iniziale")


def test_setup_creates_admin_and_logs_in(tmp_path):
    app = make_app(tmp_path)
    c = app.test_client()
    resp = c.post("/configurazione-iniziale", data={
        "username": "titolare", "nome": "Mario Rossi", "studio_nome": "Rossi Assicurazioni",
        "password": "segreta-123", "conferma": "segreta-123",
    })
    assert resp.status_code == 302
    assert c.get("/").status_code == 200
    with app.app_context():
        user = User.query.one()
        assert user.ruolo == "admin" and user.check_password("segreta-123")
    # Una volta creato l'amministratore la configurazione iniziale non è più disponibile.
    assert c.get("/configurazione-iniziale").headers["Location"].endswith("/accesso")


def test_setup_rejects_weak_password(tmp_path):
    app = make_app(tmp_path)
    c = app.test_client()
    resp = c.post("/configurazione-iniziale", data={
        "username": "titolare", "password": "corta", "conferma": "corta",
    })
    assert resp.status_code == 200
    assert "almeno 8 caratteri" in resp.get_data(as_text=True)
    with app.app_context():
        assert User.query.count() == 0


# ----------------------------------------------------------------------
# Accesso
# ----------------------------------------------------------------------
def test_protected_pages_require_login(anon_client):
    resp = anon_client.get("/clienti/")
    assert resp.status_code == 302
    assert "/accesso?next=" in resp.headers["Location"]
    assert anon_client.post("/clienti/nuovo", data={"ragione_sociale": "X"}).status_code == 302


def test_login_wrong_password_and_lockout(app, anon_client):
    for _ in range(MAX_TENTATIVI_LOGIN):
        resp = login(anon_client, ADMIN_USER, "sbagliata")
        assert resp.status_code == 200
    # Ora l'account è bloccato: anche la password giusta viene rifiutata.
    resp = login(anon_client)
    assert resp.status_code == 200
    assert "bloccato" in resp.get_data(as_text=True)
    with app.app_context():
        assert db.session.query(User).filter_by(username=ADMIN_USER).one().bloccato
        assert AuditLog.query.filter_by(azione="login_fallito").count() >= MAX_TENTATIVI_LOGIN


def test_login_is_case_insensitive_and_redirects_to_next(anon_client):
    resp = anon_client.post(
        "/accesso?next=/polizze/",
        data={"username": ADMIN_USER.upper(), "password": ADMIN_PASSWORD},
    )
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/polizze/")


def test_login_ignores_external_next(anon_client):
    resp = anon_client.post(
        "/accesso?next=https://sito-malevolo.example/",
        data={"username": ADMIN_USER, "password": ADMIN_PASSWORD},
    )
    assert resp.status_code == 302
    assert "sito-malevolo" not in resp.headers["Location"]


def test_logout_requires_post(client):
    assert client.get("/esci").status_code == 405
    assert client.post("/esci").status_code == 302
    assert client.get("/").status_code == 302


def test_inactive_user_cannot_login(app, anon_client):
    add_user(app, "ex", "password-ex-1", attivo=False)
    resp = login(anon_client, "ex", "password-ex-1")
    assert resp.status_code == 200


def test_change_password(client, app):
    resp = client.post("/profilo/password", data={
        "attuale": ADMIN_PASSWORD, "nuova": "nuova-password-9", "conferma": "nuova-password-9",
    })
    assert resp.status_code == 302
    with app.app_context():
        assert User.query.filter_by(username=ADMIN_USER).one().check_password("nuova-password-9")


# ----------------------------------------------------------------------
# Ruoli
# ----------------------------------------------------------------------
def test_readonly_user_can_read_but_not_write(app):
    add_user(app, "lettore", "password-let-1", ruolo="consultazione")
    c = app.test_client()
    assert login(c, "lettore", "password-let-1").status_code == 302
    assert c.get("/clienti/").status_code == 200
    resp = c.post("/clienti/nuovo", data={"tipo": "azienda", "ragione_sociale": "Non salvare"})
    assert resp.status_code == 302
    with app.app_context():
        assert Client.query.filter_by(ragione_sociale="Non salvare").count() == 0
    # Può comunque uscire e cambiare la propria password.
    assert c.post("/esci").status_code == 302


def test_operator_cannot_access_admin_pages(app):
    add_user(app, "operatore", "password-op-1", ruolo="operatore")
    c = app.test_client()
    login(c, "operatore", "password-op-1")
    for url in ("/utenti/", "/impostazioni/", "/registro/"):
        assert c.get(url).status_code == 403, url
    assert c.get("/clienti/").status_code == 200


def test_admin_creates_user(client, app):
    resp = client.post("/utenti/nuovo", data={
        "username": "giulia", "nome": "Giulia", "ruolo": "operatore",
        "password": "password-giu-1", "conferma": "password-giu-1",
    })
    assert resp.status_code == 302
    with app.app_context():
        assert User.query.filter_by(username="giulia").one().ruolo == "operatore"
    # Nome utente duplicato rifiutato.
    client.post("/utenti/nuovo", data={
        "username": "GIULIA", "ruolo": "operatore",
        "password": "password-giu-1", "conferma": "password-giu-1",
    })
    with app.app_context():
        assert User.query.count() == 2


def test_last_admin_cannot_be_demoted(client, app):
    with app.app_context():
        admin_id = User.query.filter_by(username=ADMIN_USER).one().id
    client.post(f"/utenti/{admin_id}/modifica", data={"ruolo": "operatore", "attivo": "on"})
    with app.app_context():
        assert db.session.get(User, admin_id).ruolo == "admin"


# ----------------------------------------------------------------------
# CSRF, header e chiave di sessione
# ----------------------------------------------------------------------
def test_csrf_blocks_post_without_token(tmp_path):
    app = make_app(tmp_path, CSRF_ENABLED=True)
    add_user(app, ADMIN_USER, ADMIN_PASSWORD, ruolo="admin")
    c = app.test_client()
    # Senza token anche l'accesso viene rifiutato.
    assert login(c).status_code == 400

    pagina = c.get("/accesso").get_data(as_text=True)
    token = re.search(r'name="csrf_token" value="([^"]+)"', pagina).group(1)
    resp = c.post("/accesso", data={"username": ADMIN_USER, "password": ADMIN_PASSWORD, "csrf_token": token})
    assert resp.status_code == 302

    assert c.post("/clienti/nuovo", data={"ragione_sociale": "Senza token"}).status_code == 400
    pagina = c.get("/clienti/nuovo").get_data(as_text=True)
    token = re.search(r'name="csrf_token" value="([^"]+)"', pagina).group(1)
    resp = c.post("/clienti/nuovo", data={"tipo": "azienda", "ragione_sociale": "Con token", "csrf_token": token})
    assert resp.status_code == 302
    with app.app_context():
        assert Client.query.filter_by(ragione_sociale="Con token").count() == 1
        assert Client.query.filter_by(ragione_sociale="Senza token").count() == 0


def test_security_headers(client):
    resp = client.get("/")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert resp.headers["Cache-Control"] == "no-store"


def test_secret_key_generated_and_persisted(tmp_path, monkeypatch):
    chiave = tmp_path / "secret_key"
    monkeypatch.setenv("SECRET_KEY_FILE", str(chiave))
    monkeypatch.delenv("SECRET_KEY", raising=False)
    app1 = make_app(tmp_path, SECRET_KEY=None)
    assert chiave.exists()
    app2 = make_app(tmp_path, SECRET_KEY=None)
    assert app1.config["SECRET_KEY"] == app2.config["SECRET_KEY"] == chiave.read_text().strip()
    assert len(app1.config["SECRET_KEY"]) >= 32


def test_open_redirect_blocked_on_next_param(client, app):
    with app.app_context():
        c = Client(tipo="azienda", ragione_sociale="ACME")
        db.session.add(c)
        db.session.commit()
        cid = c.id
    resp = client.post(f"/opportunita/da-gap/{cid}", data={"ramo": "cyber", "next": "https://evil.example/"})
    assert "evil.example" not in resp.headers["Location"]


# ----------------------------------------------------------------------
# Registro attività
# ----------------------------------------------------------------------
def test_audit_log_records_operations(client, app):
    client.post("/clienti/nuovo", data={"tipo": "azienda", "ragione_sociale": "Audit S.r.l."})
    with app.app_context():
        voce = AuditLog.query.filter_by(azione="crea", entita="cliente").one()
        assert voce.username == ADMIN_USER
        assert "Audit S.r.l." in voce.descrizione
        assert AuditLog.query.filter_by(azione="login").count() == 1
    assert client.get("/registro/").status_code == 200
    csv = client.get("/registro/esporta.csv")
    assert csv.status_code == 200
    assert "Audit S.r.l." in csv.get_data(as_text=True)


@pytest.mark.filterwarnings("ignore::getpass.GetPassWarning")
def test_reimposta_password_da_riga_di_comando(app, anon_client):
    from gestionale.cli import reimposta_password

    with app.app_context():
        user = User.query.filter_by(username=ADMIN_USER).one()
        user.attivo = False
        db.session.commit()
        esito = reimposta_password("ADMIN", "recupero-2026")
        assert "reimpostata" in esito
    assert login(anon_client, ADMIN_USER, "recupero-2026").status_code == 302

    runner = app.test_cli_runner()
    result = runner.invoke(args=["reimposta-password", "inesistente"], input="abc12345\nabc12345\n")
    assert "inesistente" in result.output

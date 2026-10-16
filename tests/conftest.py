"""Fixture condivise dai test.

Ogni test riceve un'applicazione con database e cartelle temporanee, un
amministratore già creato e un client HTTP che ha già effettuato l'accesso.
La protezione CSRF è disattivata qui e verificata a parte in test_security.py.
"""
import pytest

from gestionale import create_app
from gestionale.models import User, db

ADMIN_USER = "admin"
ADMIN_PASSWORD = "password-admin-1"


def make_app(tmp_path, **extra):
    config = {
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'test.db'}",
        "UPLOAD_FOLDER": str(tmp_path / "uploads"),
        "BACKUP_FOLDER": str(tmp_path / "backups"),
        "SECRET_KEY": "test",
        "CSRF_ENABLED": False,
        # Hash veloce nei test (in produzione: scrypt).
        "PASSWORD_HASH_METHOD": "pbkdf2:sha256:1000",
        "NOTIFICHE_REFRESH_SECONDI": 0,
    }
    config.update(extra)
    return create_app(config)


def add_user(app, username, password, ruolo="operatore", **kwargs):
    with app.app_context():
        user = User(username=username, ruolo=ruolo, **kwargs)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user.id


def login(client, username=ADMIN_USER, password=ADMIN_PASSWORD):
    return client.post(
        "/accesso", data={"username": username, "password": password}, follow_redirects=False
    )


@pytest.fixture
def app(tmp_path):
    app = make_app(tmp_path)
    add_user(app, ADMIN_USER, ADMIN_PASSWORD, ruolo="admin", nome="Amministratore")
    yield app
    with app.app_context():
        db.session.remove()
        db.engine.dispose()


@pytest.fixture
def client(app):
    c = app.test_client()
    resp = login(c)
    assert resp.status_code == 302, "login dell'amministratore di test non riuscito"
    return c


@pytest.fixture
def anon_client(app):
    return app.test_client()

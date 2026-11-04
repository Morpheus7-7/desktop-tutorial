"""Accademia: progressi di ciascun utente, vista del titolare e passaggio dai dati
della versione senza utenti."""
import sqlite3

from conftest import ADMIN_PASSWORD, ADMIN_USER, add_user, login, make_app
from gestionale import academy as ac
from gestionale.models import AcademyProgress, QuizAttempt, User, db

PRIMA = ac.tutte_le_lezioni()[0][1]["id"]
MODULO = ac.MODULI[0]["id"]


def test_ogni_consulente_ha_i_suoi_progressi(app, client):
    add_user(app, "mario", "password-mario-1", ruolo="operatore", nome="Mario Rossi")
    mario = app.test_client()
    assert login(mario, "mario", "password-mario-1").status_code == 302
    mario.post(f"/accademia/lezione/{PRIMA}/completa")
    mario.post(f"/accademia/modulo/{MODULO}/quiz", data={})
    with app.app_context():
        mario_id = User.query.filter_by(username="mario").one().id
        assert AcademyProgress.query.filter_by(user_id=mario_id).count() == 1
        assert QuizAttempt.query.filter_by(user_id=mario_id).count() == 1
        admin_id = User.query.filter_by(username=ADMIN_USER).one().id
        assert AcademyProgress.query.filter_by(user_id=admin_id).count() == 0
    client.post(f"/accademia/lezione/{PRIMA}/completa")  # la stessa lezione anche per l'amministratore
    with app.app_context():
        assert AcademyProgress.query.filter_by(lezione_id=PRIMA).count() == 2


def test_la_squadra_solo_per_il_titolare(app, client):
    add_user(app, "lucia", "password-lucia-1", ruolo="operatore", nome="Lucia Bianchi")
    lucia = app.test_client()
    login(lucia, "lucia", "password-lucia-1")
    lucia.post(f"/accademia/lezione/{PRIMA}/completa")
    pagina = client.get("/accademia/squadra").get_data(as_text=True)
    assert "Lucia Bianchi" in pagina and f"1/{len(ac.tutte_le_lezioni())}" in pagina
    with app.app_context():
        lid = User.query.filter_by(username="lucia").one().id
    assert client.get(f"/accademia/squadra/{lid}").status_code == 200
    assert lucia.get("/accademia/squadra").status_code == 403
    assert "La squadra" not in lucia.get("/accademia/").get_data(as_text=True)


def test_sola_consultazione_puo_studiare(app):
    add_user(app, "allievo", "password-allievo-1", ruolo="consultazione", nome="Allievo")
    c = app.test_client()
    login(c, "allievo", "password-allievo-1")
    assert c.post(f"/accademia/lezione/{PRIMA}/completa").status_code == 302
    assert c.get(f"/accademia/modulo/{MODULO}/quiz").status_code == 200
    with app.app_context():
        assert AcademyProgress.query.count() == 1


def test_progressi_della_versione_senza_utenti_vanno_al_titolare(tmp_path):
    # Archivio di Deal Combined 2.x: lezione unica per tutto il programma.
    percorso = tmp_path / "test.db"
    con = sqlite3.connect(percorso)
    con.executescript(f"""
        CREATE TABLE academy_progress (id INTEGER PRIMARY KEY, lezione_id VARCHAR(80) NOT NULL UNIQUE,
                                       completata_at DATETIME NOT NULL);
        INSERT INTO academy_progress (lezione_id, completata_at) VALUES ('{PRIMA}', '2026-10-01 10:00:00');
        CREATE TABLE quiz_attempts (id INTEGER PRIMARY KEY, modulo_id VARCHAR(80) NOT NULL, punteggio INTEGER NOT NULL,
                                    totale INTEGER NOT NULL, created_at DATETIME NOT NULL);
        INSERT INTO quiz_attempts (modulo_id, punteggio, totale, created_at) VALUES ('{MODULO}', 8, 10, '2026-10-01 11:00:00');
    """)
    con.commit()
    con.close()
    app = make_app(tmp_path)
    with app.app_context():
        assert AcademyProgress.query.filter(AcademyProgress.user_id.is_(None)).count() == 1  # nessun utente ancora
    # Primo avvio: si crea l'amministratore, che eredita lezioni e quiz.
    c = app.test_client()
    r = c.post("/configurazione-iniziale", data={"username": "luigi", "nome": "Luigi", "password": ADMIN_PASSWORD,
                                                  "conferma": ADMIN_PASSWORD, "password_conferma": ADMIN_PASSWORD})
    assert r.status_code == 302
    with app.app_context():
        luigi = User.query.filter_by(username="luigi").one()
        assert AcademyProgress.query.filter_by(user_id=luigi.id).count() == 1
        assert QuizAttempt.query.filter_by(user_id=luigi.id).count() == 1
    # E un altro utente può segnare la stessa lezione (il vecchio vincolo è sparito).
    add_user(app, "mario", "password-mario-1")
    m = app.test_client()
    login(m, "mario", "password-mario-1")
    m.post(f"/accademia/lezione/{PRIMA}/completa")
    with app.app_context():
        assert AcademyProgress.query.filter_by(lezione_id=PRIMA).count() == 2
        db.session.remove()
        db.engine.dispose()

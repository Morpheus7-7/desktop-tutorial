"""Test dell'Accademia commerciale: contenuti, progressi, quiz, obiezioni,
scenari e schede da stampare."""
import os
import tempfile
from datetime import date

import pytest

from gestionale import academy as ac
from gestionale import create_app
from gestionale.models import AcademyProgress, Client, QuizAttempt, db


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
            "UPLOAD_FOLDER": tempfile.mkdtemp(),
            "SECRET_KEY": "test",
        }
    )
    yield app
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    return app.test_client()


# ---------------------------------------------------------------- contenuti
def test_contenuti_coerenti():
    assert [m["id"] for m in ac.MODULI] == ac.ORDINE_MODULI
    assert [m["numero"] for m in ac.MODULI] == list(range(1, len(ac.MODULI) + 1))
    ids = [lez["id"] for _, lez in ac.tutte_le_lezioni()]
    assert len(ids) == len(set(ids))
    moduli = {m["id"] for m in ac.MODULI}
    for m in ac.MODULI:
        assert m["lezioni"] and m["quiz"] and m["fonti"] and m["evidenze"]
        for q in m["quiz"]:
            assert 0 <= q["corretta"] < len(q["opzioni"])
        for e in m["evidenze"]:
            assert e["livello"] in ac.LIVELLI_EVIDENZA
    assert all(t["modulo"] in moduli for t in ac.TECNICHE)
    assert all(s["modulo"] in moduli for s in ac.SCHEDE)
    assert all(o["categoria"] in ac.CATEGORIE_OBIEZIONI_LABELS for o in ac.OBIEZIONI)
    for s in ac.SCENARI:
        assert all(ac.get_obiezione(oid) for oid in s["obiezioni"])


def test_valuta_quiz():
    modulo = ac.get_modulo("domande")
    giuste = {f"q{i}": str(q["corretta"]) for i, q in enumerate(modulo["quiz"])}
    assert ac.valuta_quiz(modulo, giuste)["punteggio"] == len(modulo["quiz"])
    esito = ac.valuta_quiz(modulo, {"q0": "abc"})
    assert esito["punteggio"] == 0 and esito["dettaglio"][0]["scelta"] is None


def test_pillola_stabile_nel_giorno():
    d = date(2026, 10, 27)
    assert ac.pillola_del_giorno(d) is ac.pillola_del_giorno(d)


def test_cerca_obiezioni():
    assert {o["id"] for o in ac.cerca_obiezioni(categoria="prezzo")} >= {"caro", "sconto"}
    assert [o["id"] for o in ac.cerca_obiezioni("pensare")] == ["pensarci"]


# ---------------------------------------------------------------- pagine
def test_pagine_accademia(client):
    for url in ["/accademia/", "/accademia/obiezioni", "/accademia/obiezioni?categoria=fiducia&q=agente",
                "/accademia/allenamento", "/accademia/allenamento?id=caro", "/accademia/tecniche",
                "/accademia/scenari", "/accademia/schede"]:
        assert client.get(url).status_code == 200, url
    for m in ac.MODULI:
        r = client.get(f"/accademia/modulo/{m['id']}")
        assert r.status_code == 200
        assert "Base scientifica" in r.get_data(as_text=True)
        assert client.get(f"/accademia/modulo/{m['id']}/quiz").status_code == 200
    for s in ac.SCENARI:
        assert client.get(f"/accademia/scenari/{s['id']}").status_code == 200
    for s in ac.SCHEDE:
        assert client.get(f"/accademia/schede/{s['id']}").status_code == 200
    assert client.get("/accademia/modulo/inesistente").status_code == 404
    assert client.get("/accademia/schede/inesistente").status_code == 404


def test_pnl_con_evidenze_critiche(client):
    html = client.get("/accademia/modulo/pnl").get_data(as_text=True)
    assert "Non supportata" in html
    assert "Chartrand" in html


def test_completa_lezione_toggle(client, app):
    r = client.post("/accademia/lezione/domande-spin/completa")
    assert r.status_code == 302
    with app.app_context():
        assert AcademyProgress.query.filter_by(lezione_id="domande-spin").count() == 1
    assert "1<span" in client.get("/accademia/").get_data(as_text=True)
    client.post("/accademia/lezione/domande-spin/completa")
    with app.app_context():
        assert AcademyProgress.query.count() == 0
    assert client.post("/accademia/lezione/finta/completa").status_code == 404


def test_quiz_salva_tentativo(client, app):
    modulo = ac.get_modulo("chiusura")
    risposte = {f"q{i}": str(q["corretta"]) for i, q in enumerate(modulo["quiz"])}
    r = client.post("/accademia/modulo/chiusura/quiz", data=risposte)
    assert r.status_code == 200
    assert "Modulo superato" in r.get_data(as_text=True)
    with app.app_context():
        t = QuizAttempt.query.one()
        assert t.punteggio == t.totale and t.percentuale == 100
    assert "Quiz 100%" in client.get("/accademia/").get_data(as_text=True)


def test_scheda_intestata_al_cliente(client, app):
    with app.app_context():
        c = Client(tipo="azienda", ragione_sociale="Officine Rossi")
        db.session.add(c)
        db.session.commit()
        cid = c.id
    html = client.get(f"/accademia/schede/raccolta-azienda?cliente={cid}").get_data(as_text=True)
    assert "Officine Rossi" in html
    assert "raccolta-azienda" in client.get(f"/clienti/{cid}").get_data(as_text=True)

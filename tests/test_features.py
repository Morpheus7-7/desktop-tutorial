"""Test delle funzionalità aggiunte: dipendente, provvigioni, pipeline,
spunti di trattativa, ricerca, statistiche e upload multiplo."""
import io
import os
import tempfile
from datetime import date, timedelta

import pytest

from gestionale import create_app
from gestionale.models import Client, Document, Opportunity, Policy, db
from gestionale.risk_engine import analyze_risks


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


def _crea_cliente(client, **extra):
    data = {"tipo": "azienda", "ragione_sociale": "ACME", "analizza_subito": ""}
    data.update(extra)
    client.post("/clienti/nuovo", data=data, follow_redirects=True)


# ---------------------------------------------------------------- dipendente
def test_dipendente_creation_and_baseline():
    res = analyze_risks("Impiegato con famiglia e mutuo", client_type="dipendente")
    rami = {r for ri in res["rischi"] for r in ri["rami"]}
    assert {"infortuni", "malattia", "vita", "rc_capofamiglia", "tutela_legale"} <= rami


def test_dipendente_client_saved(client, app):
    client.post("/clienti/nuovo", data={
        "tipo": "dipendente", "ragione_sociale": "Marco Verdi",
        "datore_lavoro": "Acme S.p.A.", "professione": "Operaio",
    }, follow_redirects=True)
    with app.app_context():
        c = Client.query.filter_by(ragione_sociale="Marco Verdi").first()
        assert c.tipo == "dipendente"
        assert c.datore_lavoro == "Acme S.p.A."


# ---------------------------------------------------------------- trattativa
def test_analysis_includes_trattativa():
    res = analyze_risks("Azienda con e-commerce e dati in cloud", client_type="azienda")
    cyber = next(r for r in res["rischi"] if r["id"] == "cyber")
    assert cyber["trattativa"] is not None
    assert cyber["trattativa"]["esempio"]
    assert len(cyber["trattativa"]["pro"]) >= 2
    # anche le coperture scoperte portano lo spunto
    assert any(g.get("trattativa") for g in res["coperture_scoperte"])


# ---------------------------------------------------------------- provvigioni
def test_provvigione_annua_computed(app):
    with app.app_context():
        p = Policy(client_id=1, compagnia="X", numero_polizza="1",
                   premio_annuo=1000, provvigione_perc=15)
        assert p.provvigione_annua == 150.0
        p2 = Policy(client_id=1, compagnia="X", numero_polizza="2", premio_annuo=1000)
        assert p2.provvigione_annua is None


# ---------------------------------------------------------------- pipeline
def test_opportunity_flow(client, app):
    _crea_cliente(client)
    with app.app_context():
        cid = Client.query.filter_by(ragione_sociale="ACME").first().id

    # creazione
    client.post(f"/opportunita/nuova/{cid}", data={
        "titolo": "Proposta Cyber", "ramo": "cyber",
        "premio_stimato": "1200", "provvigione_perc": "20", "priorita": "alta",
    }, follow_redirects=True)
    with app.app_context():
        opp = Opportunity.query.filter_by(client_id=cid).first()
        assert opp is not None
        assert opp.fase == "lead"
        assert round(opp.provvigione_stimata, 2) == 240.0
        oid = opp.id

    # avanzamento di fase
    client.post(f"/opportunita/{oid}/fase", data={"fase": "vinta"}, follow_redirects=True)
    with app.app_context():
        opp = db.session.get(Opportunity, oid)
        assert opp.fase == "vinta"
        assert opp.aperta is False
        assert opp.chiusa_at is not None

    # board raggiungibile
    assert client.get("/opportunita/").status_code == 200


def test_opportunity_from_gap(client, app):
    _crea_cliente(client)
    with app.app_context():
        cid = Client.query.filter_by(ragione_sociale="ACME").first().id
    client.post(f"/opportunita/da-gap/{cid}", data={
        "ramo": "cyber", "titolo": "Proposta Cyber Risk",
    }, follow_redirects=True)
    with app.app_context():
        opp = Opportunity.query.filter_by(client_id=cid).first()
        assert opp.origine == "analisi_rischi"
        assert opp.ramo == "cyber"


# ---------------------------------------------------------------- pagine nuove
def test_analytics_and_search_pages(client):
    assert client.get("/statistiche").status_code == 200
    assert client.get("/cerca?q=test").status_code == 200
    assert client.get("/opportunita/").status_code == 200


def test_global_search_finds_client(client, app):
    _crea_cliente(client, ragione_sociale="Rossi Trasporti SpA")
    resp = client.get("/cerca?q=Rossi")
    assert resp.status_code == 200
    assert "Rossi Trasporti".encode() in resp.data


# ---------------------------------------------------------------- upload multiplo
def test_multi_document_upload(client, app):
    _crea_cliente(client)
    with app.app_context():
        cid = Client.query.filter_by(ragione_sociale="ACME").first().id
    data = {
        "categoria": "polizza",
        "file": [
            (io.BytesIO(b"primo file"), "uno.pdf"),
            (io.BytesIO(b"secondo file"), "due.pdf"),
        ],
    }
    resp = client.post(f"/documenti/carica/{cid}", data=data,
                       content_type="multipart/form-data", follow_redirects=True)
    assert resp.status_code == 200
    with app.app_context():
        docs = Document.query.filter_by(client_id=cid).all()
        assert len(docs) == 2
        assert all(d.dimensione and d.dimensione > 0 for d in docs)

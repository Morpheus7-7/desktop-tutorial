"""Test del gestionale assicurativo."""
import os
import tempfile
from datetime import date, timedelta

import pytest

from gestionale import create_app
from gestionale.models import (
    Client,
    FollowUp,
    Notification,
    Policy,
    RiskAnalysis,
    db,
)
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
            "WTF_CSRF_ENABLED": False,
            "SECRET_KEY": "test",
        }
    )
    yield app
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    return app.test_client()


# ----------------------------------------------------------------------
# Motore di analisi dei rischi
# ----------------------------------------------------------------------
def test_analyze_detects_fire_and_cyber():
    res = analyze_risks(
        "Falegnameria con magazzino legname e vernici, vendita online tramite e-commerce",
        client_type="azienda",
    )
    ids = {r["id"] for r in res["rischi"]}
    assert "incendio" in ids
    assert "cyber" in ids


def test_analyze_employees_boost_severity():
    res = analyze_risks(
        "Attività con personale operativo",
        client_type="azienda",
        employees=10,
    )
    infortuni = next(r for r in res["rischi"] if r["id"] == "infortuni_personale")
    assert infortuni["severita"] == "alta"


def test_analyze_gap_analysis_covered_vs_uncovered():
    res = analyze_risks(
        "Studio con consulenza e progettazione, dati trattati in cloud",
        client_type="professionista",
        active_branches={"rc_professionale"},
    )
    covered = {c["ramo"] for c in res["coperture_presenti"]}
    uncovered = {c["ramo"] for c in res["coperture_scoperte"]}
    assert "rc_professionale" in covered
    assert "cyber" in uncovered  # rilevato ma non coperto


def test_analyze_baseline_recommendations_for_company():
    res = analyze_risks("Piccola impresa senza dettagli", client_type="azienda")
    baseline_ids = {r["id"] for r in res["rischi"] if r["baseline"]}
    assert "catastrofali_base" in baseline_ids


def test_analyze_accent_insensitive():
    res = analyze_risks("Attività di riparazione con clientela", client_type="azienda")
    assert any(r["id"] == "rc_terzi" for r in res["rischi"])


# ----------------------------------------------------------------------
# Modelli
# ----------------------------------------------------------------------
def test_policy_urgency_classes(app):
    with app.app_context():
        oggi = date.today()
        scaduta = Policy(client_id=1, compagnia="X", numero_polizza="1",
                         data_scadenza=oggi - timedelta(days=1))
        critica = Policy(client_id=1, compagnia="X", numero_polizza="2",
                         data_scadenza=oggi + timedelta(days=3))
        attenzione = Policy(client_id=1, compagnia="X", numero_polizza="3",
                            data_scadenza=oggi + timedelta(days=20))
        ok = Policy(client_id=1, compagnia="X", numero_polizza="4",
                    data_scadenza=oggi + timedelta(days=200))
        assert scaduta.urgenza_scadenza == "scaduta"
        assert critica.urgenza_scadenza == "critica"
        assert attenzione.urgenza_scadenza == "attenzione"
        assert ok.urgenza_scadenza == "ok"


# ----------------------------------------------------------------------
# Percorsi HTTP end-to-end
# ----------------------------------------------------------------------
def test_dashboard_loads(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Dashboard".encode() in resp.data


def test_create_client_and_detail(client, app):
    resp = client.post(
        "/clienti/nuovo",
        data={
            "tipo": "azienda",
            "ragione_sociale": "Test S.r.l.",
            "descrizione_attivita": "magazzino con merci",
            "numero_dipendenti": "5",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        c = Client.query.filter_by(ragione_sociale="Test S.r.l.").first()
        assert c is not None
        assert c.numero_dipendenti == 5


def test_full_flow_policy_followup_analysis(client, app):
    client.post(
        "/clienti/nuovo",
        data={"tipo": "azienda", "ragione_sociale": "Flow S.p.A.",
              "descrizione_attivita": "officina con saldatura e magazzino vernici",
              "analizza_subito": ""},
        follow_redirects=True,
    )
    with app.app_context():
        c = Client.query.filter_by(ragione_sociale="Flow S.p.A.").first()
        cid = c.id

    # Polizza con scadenza vicina -> genera notifica
    client.post(
        f"/polizze/nuova/{cid}",
        data={"compagnia": "Generali", "numero_polizza": "P-1",
              "ramo": "incendio", "stato": "attiva",
              "data_scadenza": (date.today() + timedelta(days=5)).isoformat()},
        follow_redirects=True,
    )
    # Follow-up
    client.post(
        f"/follow-up/nuovo/{cid}",
        data={"titolo": "Chiamare cliente", "tipo": "chiamata",
              "data_scadenza": date.today().isoformat(), "priorita": "alta"},
        follow_redirects=True,
    )
    # Analisi
    resp = client.post(
        f"/clienti/{cid}/analisi",
        data={"descrizione": "officina con saldatura, magazzino vernici e solventi"},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        assert Policy.query.filter_by(client_id=cid).count() == 1
        # Un follow-up creato manualmente...
        assert FollowUp.query.filter_by(client_id=cid, auto_generato=False).count() == 1
        # ...più il follow-up di rinnovo generato in automatico (polizza in scadenza).
        assert FollowUp.query.filter_by(client_id=cid, tipo="rinnovo", auto_generato=True).count() == 1
        assert RiskAnalysis.query.filter_by(client_id=cid).count() == 1
        # Il before_request deve aver generato notifiche per scadenza/followup
        assert Notification.query.count() > 0


def test_scadenzario_and_notifications_pages(client):
    assert client.get("/scadenzario").status_code == 200
    assert client.get("/notifiche/").status_code == 200
    assert client.get("/polizze/").status_code == 200
    assert client.get("/documenti/").status_code == 200
    assert client.get("/follow-up/").status_code == 200


def test_document_upload_and_download(client, app):
    import io

    client.post(
        "/clienti/nuovo",
        data={"tipo": "professionista", "ragione_sociale": "Doc Test",
              "analizza_subito": ""},
        follow_redirects=True,
    )
    with app.app_context():
        cid = Client.query.filter_by(ragione_sociale="Doc Test").first().id

    resp = client.post(
        f"/documenti/carica/{cid}",
        data={"file": (io.BytesIO(b"contenuto pdf finto"), "polizza.pdf"),
              "categoria": "polizza"},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with app.app_context():
        from gestionale.models import Document

        doc = Document.query.filter_by(client_id=cid).first()
        assert doc is not None
        assert doc.original_name == "polizza.pdf"

    resp = client.get(f"/documenti/{doc.id}/scarica")
    assert resp.status_code == 200
    assert b"contenuto pdf finto" in resp.data

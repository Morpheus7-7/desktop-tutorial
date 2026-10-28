"""Preventivi salvati nelle proposte (opportunità) del cliente."""
import io
import os
import tempfile
from datetime import date, timedelta

import pytest

from gestionale import create_app
from gestionale.models import Client, Document, Opportunity, Preventivo, db


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
        "UPLOAD_FOLDER": tempfile.mkdtemp(),
        "SECRET_KEY": "test",
    })
    yield app
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def proposta(app):
    with app.app_context():
        c = Client(tipo="azienda", ragione_sociale="Panificio Rossi S.n.c.")
        db.session.add(c)
        db.session.flush()
        o = Opportunity(client_id=c.id, titolo="RC prodotti", fase="contatto")
        db.session.add(o)
        db.session.commit()
        return c.id, o.id


def _pdf(nome="preventivo.pdf", contenuto=b"%PDF-1.4 prova"):
    return (io.BytesIO(contenuto), nome)


def test_salva_preventivo_con_file(app, client, proposta):
    cid, oid = proposta
    assert client.get(f"/opportunita/{oid}/preventivi/nuovo").status_code == 200
    r = client.post(f"/opportunita/{oid}/preventivi/nuovo", data={
        "compagnia": "Generali", "descrizione": "Massimale 2 mln", "premio": "1.250,50",
        "valido_fino": (date.today() + timedelta(days=30)).isoformat(), "esito": "in_attesa",
        "file": _pdf(),
    }, content_type="multipart/form-data")
    assert r.status_code == 302 and r.headers["Location"].endswith(f"/clienti/{cid}#opportunita")
    with app.app_context():
        q = Preventivo.query.one()
        assert (q.compagnia, q.premio, q.esito) == ("Generali", 1250.5, "in_attesa")
        assert q.documento.categoria == "preventivo" and q.documento.client_id == cid
        assert os.path.exists(os.path.join(app.config["UPLOAD_FOLDER"], q.documento.filename))
        o = db.session.get(Opportunity, oid)
        assert o.fase == "preventivo" and o.premio_stimato == 1250.5  # «Preventivo inviato»
    pagina = client.get(f"/clienti/{cid}").get_data(as_text=True)
    assert "Preventivo Generali" in pagina and "preventivo.pdf" in pagina and "Massimale 2 mln" in pagina
    # Anche tra i documenti del cliente e nella pagina della proposta
    assert "preventivo.pdf" in client.get("/documenti/").get_data(as_text=True)
    assert "Generali" in client.get(f"/opportunita/{oid}/modifica").get_data(as_text=True)


def test_validazioni(app, client, proposta):
    _, oid = proposta
    client.post(f"/opportunita/{oid}/preventivi/nuovo", data={"note": "solo note"})
    client.post(f"/opportunita/{oid}/preventivi/nuovo", data={"compagnia": "X", "file": _pdf("virus.exe")},
                content_type="multipart/form-data")
    with app.app_context():
        assert Preventivo.query.count() == 0 and Document.query.count() == 0
    r = client.post(f"/opportunita/{oid}/preventivi/nuovo", data={"premio": "900", "next": "//evil.example"})
    assert "evil" not in r.headers["Location"]


def test_sostituisci_file_e_scaduto(app, client, proposta):
    cid, oid = proposta
    client.post(f"/opportunita/{oid}/preventivi/nuovo", data={
        "compagnia": "Allianz", "valido_fino": (date.today() - timedelta(days=1)).isoformat(), "file": _pdf("v1.pdf"),
    }, content_type="multipart/form-data")
    with app.app_context():
        q = Preventivo.query.one()
        vecchio = os.path.join(app.config["UPLOAD_FOLDER"], q.documento.filename)
        assert q.scaduto
        qid = q.id
    assert "Scaduto" in client.get(f"/clienti/{cid}").get_data(as_text=True)
    client.post(f"/opportunita/preventivi/{qid}/modifica", data={"compagnia": "Allianz", "esito": "accettato",
                                                               "file": _pdf("v2.pdf")}, content_type="multipart/form-data")
    with app.app_context():
        q = db.session.get(Preventivo, qid)
        assert q.esito == "accettato" and not q.scaduto and q.documento.original_name == "v2.pdf"
        assert not os.path.exists(vecchio) and Document.query.count() == 1


def test_eliminazioni(app, client, proposta):
    cid, oid = proposta
    for nome in ("a.pdf", "b.pdf"):
        client.post(f"/opportunita/{oid}/preventivi/nuovo", data={"compagnia": nome, "file": _pdf(nome)},
                    content_type="multipart/form-data")
    with app.app_context():
        qa, qb = [q.id for q in Preventivo.query.order_by(Preventivo.id)]
    # Senza spunta: il preventivo sparisce, il file resta tra i documenti
    client.post(f"/opportunita/preventivi/{qa}/elimina")
    with app.app_context():
        assert Preventivo.query.count() == 1 and Document.query.count() == 2
    # Eliminare il documento dall'archivio lascia il preventivo senza file
    with app.app_context():
        doc_b = db.session.get(Preventivo, qb).document_id
    client.post(f"/documenti/{doc_b}/elimina")
    with app.app_context():
        assert db.session.get(Preventivo, qb).document_id is None
    # Eliminare la proposta elimina i preventivi, non i documenti
    client.post(f"/opportunita/{oid}/elimina")
    with app.app_context():
        assert Preventivo.query.count() == 0 and Document.query.count() == 1


def test_elimina_anche_il_file(app, client, proposta):
    _, oid = proposta
    client.post(f"/opportunita/{oid}/preventivi/nuovo", data={"compagnia": "Unipol", "file": _pdf()},
                content_type="multipart/form-data")
    with app.app_context():
        q = Preventivo.query.one()
        percorso = os.path.join(app.config["UPLOAD_FOLDER"], q.documento.filename)
        qid = q.id
    client.post(f"/opportunita/preventivi/{qid}/elimina", data={"con_file": "1"})
    with app.app_context():
        assert Preventivo.query.count() == 0 and Document.query.count() == 0
    assert not os.path.exists(percorso)

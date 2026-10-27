"""Schede dell'Accademia compilate dal gestionale e salvate nel cliente."""
import os
import tempfile
from datetime import date

import pytest

from gestionale import academy as ac
from gestionale import create_app
from gestionale.models import Client, Policy, SchedaCompilata, db
from gestionale.schede import SCHEDE_CLIENTE, chiavi


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
def cliente_id(app):
    with app.app_context():
        c = Client(tipo="azienda", ragione_sociale="Falegnameria Test S.r.l.",
                   partita_iva="01234567890", codice_ateco="16.23", numero_dipendenti=8)
        db.session.add(c)
        db.session.flush()
        db.session.add(Policy(client_id=c.id, numero_polizza="POL-1", compagnia="Allianz",
                              ramo="incendio", massimale=500000, premio_annuo=1200,
                              data_scadenza=date(2027, 1, 31), stato="attiva"))
        db.session.commit()
        return c.id


def test_ogni_scheda_cliente_esiste_e_si_apre(client, cliente_id):
    for sid in SCHEDE_CLIENTE:
        assert ac.get_scheda(sid), sid
        assert client.get(f"/clienti/{cliente_id}/schede/nuova/{sid}").status_code == 200
    # le schede del consulente non si compilano nel cliente
    assert client.get(f"/clienti/{cliente_id}/schede/nuova/piano-settimanale").status_code == 404


def test_precompilazione_da_anagrafica_e_polizze(client, cliente_id):
    html = client.get(f"/clienti/{cliente_id}/schede/nuova/raccolta-azienda").get_data(as_text=True)
    assert 'value="Falegnameria Test S.r.l."' in html
    assert 'value="01234567890 / 16.23"' in html
    assert 'value="Allianz"' in html and 'value="31/01/2027"' in html


def test_salva_modifica_e_stampa(client, app, cliente_id):
    scheda = ac.get_scheda("informazioni-da-dare")
    dati = {"data_compilazione": "2026-10-20", "consulente": "Anna", "note": "Consegnato tutto"}
    prima_check = next(k for k, t in chiavi(scheda) if t == "check")
    dati[prima_check] = "1"
    r = client.post(f"/clienti/{cliente_id}/schede/nuova/informazioni-da-dare", data=dati)
    assert r.status_code == 302
    with app.app_context():
        sc = SchedaCompilata.query.one()
        assert sc.consulente == "Anna" and sc.data_compilazione == date(2026, 10, 20)
        assert sc.contenuto["valori"][prima_check] is True
        assert sc.contenuto["struttura"]["titolo"] == scheda["titolo"]
        sid = sc.id
    vista = client.get(f"/clienti/{cliente_id}/schede/{sid}").get_data(as_text=True)
    assert "Consegnato tutto" in vista and "spuntata" in vista
    # modifica: la casella tolta torna falsa
    client.post(f"/clienti/{cliente_id}/schede/{sid}/modifica",
                data={"data_compilazione": "2026-10-21", "consulente": "Anna", "note": "Rivisto"})
    with app.app_context():
        sc = db.session.get(SchedaCompilata, sid)
        assert sc.contenuto["valori"][prima_check] is False
        assert sc.contenuto["valori"]["note"] == "Rivisto"
    dettaglio = client.get(f"/clienti/{cliente_id}").get_data(as_text=True)
    assert scheda["titolo"] in dettaglio and "Anna" in dettaglio


def test_limiti_e_appartenenza(client, app, cliente_id):
    client.post(f"/clienti/{cliente_id}/schede/nuova/post-vendita",
                data={"data_compilazione": "non-una-data", "note": "x" * 10000})
    with app.app_context():
        sc = SchedaCompilata.query.one()
        assert sc.data_compilazione == date.today()
        assert len(sc.contenuto["valori"]["note"]) == 3000
        altro = Client(tipo="azienda", ragione_sociale="Altro")
        db.session.add(altro)
        db.session.commit()
        sid, altro_id = sc.id, altro.id
    assert client.get(f"/clienti/{altro_id}/schede/{sid}").status_code == 404
    assert client.post(f"/clienti/{altro_id}/schede/{sid}/elimina").status_code == 404


def test_elimina_e_cascata_col_cliente(client, app, cliente_id):
    client.post(f"/clienti/{cliente_id}/schede/nuova/diario-trattativa", data={"note": "a"})
    client.post(f"/clienti/{cliente_id}/schede/nuova/diario-trattativa", data={"note": "b"})
    with app.app_context():
        primo = SchedaCompilata.query.first().id
    client.post(f"/clienti/{cliente_id}/schede/{primo}/elimina")
    with app.app_context():
        assert SchedaCompilata.query.count() == 1
        db.session.delete(db.session.get(Client, cliente_id))
        db.session.commit()
        assert SchedaCompilata.query.count() == 0

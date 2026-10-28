"""Aziende e persone collegate: l'amministratore anche come cliente privato,
i dipendenti collegati all'azienda per cui lavorano."""
import io
import os
import sqlite3
import tempfile

import pytest
from openpyxl import Workbook

from gestionale import create_app
from gestionale import import_excel as ie
from gestionale.models import Client, PersonaCollegata, db


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


def _crea(app, **campi):
    with app.app_context():
        c = Client(**campi)
        db.session.add(c)
        db.session.commit()
        return c.id


def _panificio_con_amministratore(app, client):
    pid_az = _crea(app, tipo="azienda", ragione_sociale="Panificio Rossi S.n.c.")
    client.post(f"/clienti/{pid_az}/persone/nuova", data={
        "ruolo": "amministratore_unico", "nome": "Mario", "cognome": "Rossi", "codice_fiscale": "RSSMRA70A01B157X",
        "citta": "Brescia", "provincia": "BS", "telefono": "333 1111111", "dal": "2015-03-01",
    })
    with app.app_context():
        return pid_az, PersonaCollegata.query.one().id


def test_amministratore_gestito_anche_come_cliente_privato(app, client):
    az, pid = _panificio_con_amministratore(app, client)
    pagina = client.get(f"/clienti/{az}").get_data(as_text=True)
    assert "Amministratori" in pagina and "Gestisci come privato" in pagina

    r = client.post(f"/clienti/{az}/persone/{pid}/scheda-privata")
    with app.app_context():
        privato = Client.query.filter_by(cognome="Rossi").one()
        assert r.headers["Location"].endswith(f"/clienti/{privato.id}#persone")
        assert (privato.tipo, privato.ragione_sociale, privato.codice_fiscale, privato.telefono) == (
            "dipendente", "Mario Rossi", "RSSMRA70A01B157X", "333 1111111")
        assert db.session.get(PersonaCollegata, pid).persona_client_id == privato.id
        privato_id = privato.id

    # Dalla scheda privata: «Amministratore unico di Panificio Rossi»
    pagina = client.get(f"/clienti/{privato_id}").get_data(as_text=True)
    assert "Ruoli nelle aziende" in pagina and "Panificio Rossi S.n.c." in pagina
    # Un secondo clic non crea doppioni
    client.post(f"/clienti/{az}/persone/{pid}/scheda-privata")
    with app.app_context():
        assert Client.query.filter_by(cognome="Rossi").count() == 1

    # I dati si aggiornano in un posto solo: il telefono cambiato nella scheda
    # privata compare anche tra gli amministratori dell'azienda.
    client.post(f"/clienti/{privato_id}/modifica", data={
        "tipo": "dipendente", "nome": "Mario", "cognome": "Rossi", "telefono": "333 2222222",
        "residenza_citta": "Desenzano", "datore_lavoro_id": "",
    })
    pagina = client.get(f"/clienti/{az}").get_data(as_text=True)
    assert "333 2222222" in pagina and "Desenzano" in pagina and "Cliente privato" in pagina


def test_suggerisce_il_cliente_privato_gia_esistente(app, client):
    privato = _crea(app, tipo="dipendente", nome="Mario", cognome="Rossi", ragione_sociale="Mario Rossi",
                    codice_fiscale="RSSMRA70A01B157X")
    az, pid = _panificio_con_amministratore(app, client)
    assert "Collega a Mario Rossi" in client.get(f"/clienti/{az}").get_data(as_text=True)
    # «Gestisci come privato» non crea un doppione: collega quello che c'è
    client.post(f"/clienti/{az}/persone/{pid}/scheda-privata")
    with app.app_context():
        assert Client.query.filter_by(cognome="Rossi").count() == 1
        assert db.session.get(PersonaCollegata, pid).persona_client_id == privato


def test_collega_e_scollega_conservando_i_dati(app, client):
    privato = _crea(app, tipo="dipendente", nome="Anna", cognome="Verdi", ragione_sociale="Anna Verdi",
                    email="anna@example.it", citta="Bergamo")
    az, pid = _panificio_con_amministratore(app, client)
    client.post(f"/clienti/{az}/persone/{pid}/collega", data={"persona_client_id": privato})
    with app.app_context():
        p = db.session.get(PersonaCollegata, pid)
        assert p.nome_completo == "Anna Verdi" and p.dato("email") == "anna@example.it"
    # Modificare il ruolo non tocca l'anagrafica (i campi non sono nel modulo)
    client.post(f"/clienti/{az}/persone/{pid}/modifica", data={"ruolo": "presidente_cda", "note": "decide lei"})
    with app.app_context():
        p = db.session.get(PersonaCollegata, pid)
        assert p.ruolo == "presidente_cda" and p.persona_client_id == privato and p.cognome == "Verdi"
    client.post(f"/clienti/{az}/persone/{pid}/collega", data={"persona_client_id": ""})
    with app.app_context():
        p = db.session.get(PersonaCollegata, pid)
        assert p.persona_client_id is None and (p.cognome, p.email, p.citta) == ("Verdi", "anna@example.it", "Bergamo")
    # Non si collega a un'azienda o a sé stessa
    altra = _crea(app, tipo="azienda", ragione_sociale="Altra S.r.l.")
    assert client.post(f"/clienti/{az}/persone/{pid}/collega", data={"persona_client_id": altra}).status_code == 400


def test_dalla_scheda_privata_collega_a_un_azienda(app, client):
    az = _crea(app, tipo="azienda", ragione_sociale="Panificio Rossi S.n.c.")
    privato = _crea(app, tipo="professionista", nome="Luca", cognome="Bianchi", ragione_sociale="Luca Bianchi")
    assert client.get(f"/clienti/{privato}/ruoli/nuovo").status_code == 200
    assert client.get(f"/clienti/{az}/ruoli/nuovo").status_code == 404  # solo per le persone
    client.post(f"/clienti/{privato}/ruoli/nuovo", data={"ruolo": "socio", "quota_perc": "50"})  # manca l'azienda
    with app.app_context():
        assert PersonaCollegata.query.count() == 0
    r = client.post(f"/clienti/{privato}/ruoli/nuovo", data={"azienda_id": az, "ruolo": "socio", "quota_perc": "50"})
    assert r.status_code == 302
    with app.app_context():
        p = PersonaCollegata.query.one()
        assert (p.client_id, p.persona_client_id, p.quota_perc, p.cognome) == (az, privato, 50, "Bianchi")
    assert "Luca Bianchi" in client.get(f"/clienti/{az}").get_data(as_text=True)


def test_dipendente_collegato_all_azienda(app, client):
    az = _crea(app, tipo="azienda", ragione_sociale="Panificio Rossi S.n.c.")
    az2 = _crea(app, tipo="azienda", ragione_sociale="Forno Bianchi S.r.l.")
    client.post("/clienti/nuovo", data={"tipo": "dipendente", "nome": "Sara", "cognome": "Neri",
                                         "datore_lavoro_id": az, "datore_lavoro": ""})
    with app.app_context():
        sara = Client.query.filter_by(cognome="Neri").one()
        assert sara.datore_lavoro == "Panificio Rossi S.n.c."
        legame = PersonaCollegata.query.one()
        assert (legame.client_id, legame.persona_client_id, legame.ruolo) == (az, sara.id, "dipendente")
        sid = sara.id
    pagina = client.get(f"/clienti/{az}").get_data(as_text=True)
    assert "Dipendenti" in pagina and "Sara Neri" in pagina
    assert "Dipendente" in client.get(f"/clienti/{sid}").get_data(as_text=True)
    assert f'value="{az}" selected' in client.get(f"/clienti/{sid}/modifica").get_data(as_text=True)

    # Cambia lavoro: il legame passa alla nuova azienda
    client.post(f"/clienti/{sid}/modifica", data={"tipo": "dipendente", "nome": "Sara", "cognome": "Neri",
                                                   "datore_lavoro_id": az2})
    with app.app_context():
        assert [p.client_id for p in PersonaCollegata.query.all()] == [az2]
        assert db.session.get(Client, sid).datore_lavoro == "Forno Bianchi S.r.l."
    # Datore non cliente: il legame si toglie, resta il nome scritto
    client.post(f"/clienti/{sid}/modifica", data={"tipo": "dipendente", "nome": "Sara", "cognome": "Neri",
                                                   "datore_lavoro_id": "", "datore_lavoro": "Comune di Brescia"})
    with app.app_context():
        assert PersonaCollegata.query.count() == 0
        assert db.session.get(Client, sid).datore_lavoro == "Comune di Brescia"


def test_eliminazioni(app, client):
    az, pid = _panificio_con_amministratore(app, client)
    client.post(f"/clienti/{az}/persone/{pid}/scheda-privata")
    with app.app_context():
        privato = Client.query.filter_by(cognome="Rossi").one().id
    # Eliminare la scheda privata: nell'azienda l'amministratore resta, con i suoi dati
    client.post(f"/clienti/{privato}/modifica", data={"tipo": "dipendente", "nome": "Mario", "cognome": "Rossi",
                                                       "email": "mario@example.it", "datore_lavoro_id": ""})
    client.post(f"/clienti/{privato}/elimina")
    with app.app_context():
        p = db.session.get(PersonaCollegata, pid)
        assert p.persona_client_id is None and (p.cognome, p.email) == ("Rossi", "mario@example.it")
    # Eliminare l'azienda non elimina la scheda privata
    client.post(f"/clienti/{az}/persone/{pid}/scheda-privata")
    client.post(f"/clienti/{az}/elimina")
    with app.app_context():
        assert Client.query.filter_by(cognome="Rossi").count() == 1
        assert PersonaCollegata.query.count() == 0


def test_import_collega_al_cliente_privato_con_lo_stesso_cf(app):
    privato = _crea(app, tipo="dipendente", nome="Mario", cognome="Rossi", ragione_sociale="Mario Rossi",
                    codice_fiscale="RSSMRA70A01B157X")
    libro = Workbook()
    foglio = libro.active
    foglio.title = "Amministratori"
    foglio.append(["Cliente", "Ruolo", "Nome", "Cognome", "Codice fiscale"])
    foglio.append(["Panificio Rossi", "Amministratore unico", "Mario", "Rossi", "rssmra70a01b157x"])
    buf = io.BytesIO()
    libro.save(buf)
    with app.app_context():
        ie.importa(ie.analizza(buf.getvalue(), "cda.xlsx"))
        assert PersonaCollegata.query.one().persona_client_id == privato


def test_archivio_vecchio_riceve_il_collegamento():
    fd, percorso = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    config = {"TESTING": True, "SQLALCHEMY_DATABASE_URI": f"sqlite:///{percorso}",
              "UPLOAD_FOLDER": tempfile.mkdtemp(), "SECRET_KEY": "test"}
    try:
        app = create_app(config)
        with app.app_context():
            db.engine.dispose()
        # La tabella com'era nella versione 2.2.0, senza il collegamento.
        con = sqlite3.connect(percorso)
        con.execute("DROP TABLE client_persons")
        con.execute("CREATE TABLE client_persons (id INTEGER PRIMARY KEY, client_id INTEGER NOT NULL, "
                    "ruolo VARCHAR(40) NOT NULL, ruolo_altro VARCHAR(100), nome VARCHAR(80), "
                    "cognome VARCHAR(80) NOT NULL, codice_fiscale VARCHAR(16), data_nascita DATE, "
                    "luogo_nascita VARCHAR(100), indirizzo VARCHAR(200), citta VARCHAR(100), cap VARCHAR(5), "
                    "provincia VARCHAR(2), email VARCHAR(120), telefono VARCHAR(30), quota_perc FLOAT, "
                    "dal DATE, note TEXT, created_at DATETIME)")
        con.execute("INSERT INTO client_persons (client_id, ruolo, cognome) VALUES (1, 'socio', 'Vecchio')")
        con.commit()
        con.close()
        app = create_app(config)
        with app.app_context():
            colonne = [r[1] for r in db.session.execute(db.text("PRAGMA table_info(client_persons)"))]
            assert "persona_client_id" in colonne
            assert PersonaCollegata.query.one().cognome == "Vecchio"
            db.engine.dispose()
    finally:
        os.unlink(percorso)


def test_amministratori_dal_modulo_del_cliente(app, client):
    pagina = client.get("/clienti/nuovo").get_data(as_text=True)
    assert "Amministratori e figure societarie" in pagina and 'name="persona_cognome"' in pagina
    client.post("/clienti/nuovo", data={
        "tipo": "azienda", "ragione_sociale": "Panificio Rossi S.n.c.",
        "persona_ruolo": ["amministratore_unico", "socio", "consigliere"],
        "persona_nome": ["Mario", "", "Solo nome"],
        "persona_cognome": ["Rossi", "Bianchi", ""],
        "persona_cf": ["rssmra70a01b157x", "", ""],
        "persona_telefono": ["333 1", "", ""],
    })
    with app.app_context():
        az = Client.query.filter_by(ragione_sociale="Panificio Rossi S.n.c.").one()
        assert [(p.ruolo, p.nome_completo, p.codice_fiscale) for p in az.persone] == [
            ("amministratore_unico", "Mario Rossi", "RSSMRA70A01B157X"), ("socio", "Bianchi", None)]
        az_id = az.id
    pagina = client.get(f"/clienti/{az_id}/modifica").get_data(as_text=True)
    assert "Mario Rossi" in pagina  # elenco di chi c'è già
    client.post(f"/clienti/{az_id}/modifica", data={
        "tipo": "azienda", "ragione_sociale": "Panificio Rossi S.n.c.",
        "persona_ruolo": ["inventato"], "persona_nome": ["Ugo"], "persona_cognome": ["Verdi"],
        "persona_cf": [""], "persona_telefono": [""],
    })
    with app.app_context():
        assert [p.ruolo for p in db.session.get(Client, az_id).persone] == ["amministratore_unico", "socio", "altro"]

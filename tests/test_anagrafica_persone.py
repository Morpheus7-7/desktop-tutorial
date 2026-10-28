"""Anagrafica delle persone (nome e cognome, albo, residenza) e persone
collegate ai clienti (amministratori, consiglieri, soci, familiari)."""
import os
import sqlite3
import tempfile
from datetime import date

import pytest

from gestionale import create_app
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


def _azienda(app, nome="Rossi Impianti S.r.l."):
    with app.app_context():
        c = Client(tipo="azienda", ragione_sociale=nome)
        db.session.add(c)
        db.session.commit()
        return c.id


def test_professionista_con_nome_cognome_albo_e_residenza(app, client):
    r = client.post("/clienti/nuovo", data={
        "tipo": "professionista", "ragione_sociale": "", "nome": "Giulia", "cognome": "Bianchi",
        "professione": "Ingegnere civile", "data_nascita": "1980-04-12", "luogo_nascita": "Brescia",
        "albo": "Ordine degli Ingegneri", "albo_provincia": "Milano", "albo_numero": "A12345",
        "albo_data_iscrizione": "2006-09-01", "indirizzo": "Via Studio 1", "citta": "Milano",
        "residenza_indirizzo": "Via Casa 5", "residenza_citta": "Monza", "residenza_provincia": "mb",
        "stato_civile": "Coniugato/a", "nucleo_familiare": "2 figli", "interessi": "vela",
    })
    assert r.status_code == 302
    with app.app_context():
        c = Client.query.one()
        assert c.ragione_sociale == "Giulia Bianchi" and c.nome_completo == "Giulia Bianchi"
        assert (c.albo, c.albo_numero, c.albo_data_iscrizione) == ("Ordine degli Ingegneri", "A12345", date(2006, 9, 1))
        assert (c.residenza_citta, c.residenza_provincia) == ("Monza", "MB")
        assert c.data_nascita == date(1980, 4, 12) and c.eta >= 46
        cid = c.id
    pagina = client.get(f"/clienti/{cid}").get_data(as_text=True)
    assert "Iscrizione all&#39;albo" in pagina or "Iscrizione all'albo" in pagina
    assert "A12345" in pagina and "Via Casa 5" in pagina and "vela" in pagina


def test_azienda_non_salva_campi_da_persona(app, client):
    client.post("/clienti/nuovo", data={"tipo": "azienda", "ragione_sociale": "Acme S.p.A.",
                                         "nome": "residuo", "albo": "residuo"})
    with app.app_context():
        c = Client.query.one()
        assert c.ragione_sociale == "Acme S.p.A." and c.nome is None and c.albo is None


def test_cliente_esistente_senza_nome_propone_la_divisione(app, client):
    with app.app_context():
        c = Client(tipo="dipendente", ragione_sociale="Mario Rossi")
        db.session.add(c)
        db.session.commit()
        cid = c.id
    pagina = client.get(f"/clienti/{cid}/modifica").get_data(as_text=True)
    assert 'id="nome" name="nome" value="Mario"' in pagina
    assert 'id="cognome" name="cognome" value="Rossi"' in pagina and "Controlla" in pagina


def test_aggiungi_modifica_e_rimuovi_amministratore(app, client):
    cid = _azienda(app)
    pagina = client.get(f"/clienti/{cid}").get_data(as_text=True)
    assert "Aggiungi amministratore / consigliere / altro" in pagina
    assert client.get(f"/clienti/{cid}/persone/nuova?ruolo=consigliere").status_code == 200

    r = client.post(f"/clienti/{cid}/persone/nuova", data={
        "ruolo": "amministratore_unico", "nome": "Luca", "cognome": "D'Amico",
        "codice_fiscale": "dmclcu70a01f205x", "citta": "Brescia", "provincia": "bs", "dal": "2020-01-15",
    })
    assert r.status_code == 302 and r.headers["Location"].endswith("#persone")
    client.post(f"/clienti/{cid}/persone/nuova", data={"ruolo": "altro", "ruolo_altro": "Direttore tecnico",
                                                       "cognome": "Verdi"})
    client.post(f"/clienti/{cid}/persone/nuova", data={"ruolo": "socio", "cognome": "Neri", "quota_perc": "40,5"})
    with app.app_context():
        persone = PersonaCollegata.query.order_by(PersonaCollegata.id).all()
        assert [p.ruolo_label for p in persone] == ["Amministratore unico", "Direttore tecnico", "Socio"]
        assert persone[0].codice_fiscale == "DMCLCU70A01F205X" and persone[0].provincia == "BS"
        assert persone[2].quota_perc == 40.5
        pid = persone[0].id

    pagina = client.get(f"/clienti/{cid}").get_data(as_text=True)
    assert "Luca D&#39;Amico" in pagina and "Direttore tecnico" in pagina and "40.5%" in pagina

    client.post(f"/clienti/{cid}/persone/{pid}/modifica", data={"ruolo": "presidente_cda", "nome": "Luca",
                                                                "cognome": "D'Amico"})
    with app.app_context():
        assert db.session.get(PersonaCollegata, pid).ruolo == "presidente_cda"
    client.post(f"/clienti/{cid}/persone/{pid}/elimina")
    with app.app_context():
        assert PersonaCollegata.query.count() == 2


def test_validazioni_e_appartenenza(app, client):
    cid, altro = _azienda(app), _azienda(app, "Altra S.r.l.")
    client.post(f"/clienti/{cid}/persone/nuova", data={"ruolo": "socio", "nome": "Solo nome"})
    client.post(f"/clienti/{cid}/persone/nuova", data={"ruolo": "socio", "cognome": "X", "quota_perc": "150"})
    with app.app_context():
        assert PersonaCollegata.query.count() == 0
    client.post(f"/clienti/{cid}/persone/nuova", data={"ruolo": "inventato", "cognome": "Bianchi"})
    with app.app_context():
        p = PersonaCollegata.query.one()
        assert p.ruolo == "altro"
        pid = p.id
    assert client.get(f"/clienti/{altro}/persone/{pid}/modifica").status_code == 404
    assert client.post(f"/clienti/{altro}/persone/{pid}/elimina").status_code == 404


def test_ricerca_trova_l_azienda_dal_nome_dell_amministratore(app, client):
    cid = _azienda(app)
    client.post(f"/clienti/{cid}/persone/nuova", data={"ruolo": "amministratore_unico",
                                                       "nome": "Franca", "cognome": "Colombo"})
    assert "Rossi Impianti" in client.get("/clienti/?q=Franca Colombo").get_data(as_text=True)
    assert "Rossi Impianti" in client.get("/cerca?q=colombo").get_data(as_text=True)


def test_eliminare_il_cliente_elimina_le_persone(app, client):
    cid = _azienda(app)
    client.post(f"/clienti/{cid}/persone/nuova", data={"ruolo": "consigliere", "cognome": "Gialli"})
    client.post(f"/clienti/{cid}/elimina")
    with app.app_context():
        assert PersonaCollegata.query.count() == 0


def test_database_vecchio_riceve_le_nuove_colonne():
    """Chi ha già un archivio lo riapre senza perdere nulla."""
    nuove = ["nome", "cognome", "data_nascita", "luogo_nascita", "stato_civile", "nucleo_familiare",
             "interessi", "residenza_indirizzo", "residenza_citta", "residenza_cap", "residenza_provincia",
             "albo", "albo_provincia", "albo_numero", "albo_data_iscrizione"]
    fd, percorso = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    config = {"TESTING": True, "SQLALCHEMY_DATABASE_URI": f"sqlite:///{percorso}",
              "UPLOAD_FOLDER": tempfile.mkdtemp(), "SECRET_KEY": "test"}
    try:
        app = create_app(config)
        with app.app_context():
            db.session.add(Client(tipo="dipendente", ragione_sociale="Anna Neri"))
            db.session.commit()
            db.engine.dispose()
        # Riporta il database com'era prima di questa versione.
        con = sqlite3.connect(percorso)
        con.execute("DROP TABLE client_persons")
        for colonna in nuove:
            con.execute(f"ALTER TABLE clients DROP COLUMN {colonna}")
        con.commit()
        con.close()

        app = create_app(config)
        with app.app_context():
            c = Client.query.one()
            assert c.ragione_sociale == "Anna Neri" and c.albo is None and c.persone == []
            db.engine.dispose()
    finally:
        os.unlink(percorso)

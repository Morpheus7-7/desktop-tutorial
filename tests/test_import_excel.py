"""Importazione di clienti e polizze da Excel e CSV."""
import io
import os
import tempfile
from datetime import date

import pytest
from openpyxl import Workbook, load_workbook

from gestionale import create_app
from gestionale import import_excel as ie
from gestionale.models import Client, Policy, db


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


def _xlsx(fogli: dict) -> bytes:
    libro = Workbook()
    libro.remove(libro.active)
    for nome, righe in fogli.items():
        foglio = libro.create_sheet(nome)
        for riga in righe:
            foglio.append(riga)
    buf = io.BytesIO()
    libro.save(buf)
    return buf.getvalue()


def test_modello_ha_i_fogli_e_si_reimporta(app):
    dati = ie.modello_xlsx()
    libro = load_workbook(io.BytesIO(dati))
    assert {"Clienti", "Polizze", "Valori", "Istruzioni"} <= set(libro.sheetnames)
    with app.app_context():
        a = ie.analizza(dati, "modello.xlsx")
        # La riga di esempio: un cliente nuovo e una polizza collegata a lui.
        assert a["conteggi"]["clienti_nuovi"] == 1
        assert a["conteggi"]["polizze_nuove"] == 1
        assert a["polizze"][0]["dati"]["ramo"] == "rct_rco"
        assert a["polizze"][0]["dati"]["tacito_rinnovo"] is True
        assert a["polizze"][0]["nome_cliente"] == "Rossi Impianti S.r.l."


def test_intestazioni_libere_e_conversioni(app):
    dati = _xlsx({"Foglio1": [
        ["Elenco clienti 2026"],  # titolo sopra l'intestazione
        ["Nominativo", "P.IVA", "Comune", "CAP", "Tel", "Fatturato"],
        ["Bianchi Srl", 1234567890, "Milano", 2100, "02 123", "1.250.000,50"],
        ["", None, None, None, None, None],
        ["Verdi Mario", None, "Roma", "00184", None, None],
    ]})
    with app.app_context():
        a = ie.analizza(dati, "miei clienti.xlsx")
        assert a["conteggi"]["clienti_nuovi"] == 2
        b = a["clienti"][0]["dati"]
        assert b["partita_iva"] == "01234567890"  # zero iniziale ripristinato
        assert b["cap"] == "02100"
        assert b["fatturato_annuo"] == 1250000.50
        assert a["clienti"][0]["riga"] == 3


def test_polizze_creano_clienti_mancanti_e_saltano_doppioni(app):
    with app.app_context():
        c = Client(tipo="azienda", ragione_sociale="Esistente SpA", partita_iva="11111111111")
        db.session.add(c)
        db.session.flush()
        db.session.add(Policy(client_id=c.id, compagnia="Generali", numero_polizza="A-1"))
        db.session.commit()
        cid = c.id

    dati = _xlsx({"Polizze": [
        ["Cliente", "Compagnia", "N. polizza", "Ramo", "Premio", "Scadenza", "Provvigione"],
        ["11111111111", "Generali", "A-1", "RCT", 100, date(2026, 12, 31), 0.15],   # già presente
        ["esistente spa", "Allianz", "B-2", "Infortuni", "1.200,00", "31/12/2026", "12%"],
        ["Nuovo Cliente", "Unipol", "C-3", "ramo strano", None, "non è una data", None],
        ["Nuovo Cliente", "Unipol", "C-4", "TCM", None, None, None],
        ["", "Unipol", "", None, None, None, None],
    ]})
    with app.app_context():
        a = ie.analizza(dati, "portafoglio.xlsx")
        esiti = [p["esito"] for p in a["polizze"]]
        assert esiti == ["esistente", "nuova", "errore", "nuova", "errore"]
        assert a["polizze"][1]["dati"]["provvigione_perc"] == 12
        assert a["polizze"][1]["nome_cliente"] == "Esistente SpA"
        assert any("non riconosciuto" in w for w in a["polizze"][2]["avvisi"])
        assert a["polizze"][3]["dati"]["ramo"] == "vita"
        assert a["conteggi"]["clienti_nuovi"] == 1  # «Nuovo Cliente», una volta sola

        esito = ie.importa(a)
        assert esito == {"clienti": 1, "completati": 0, "polizze": 2}
        assert Policy.query.filter_by(client_id=cid).count() == 2
        nuovo = Client.query.filter_by(ragione_sociale="Nuovo Cliente").one()
        assert [p.numero_polizza for p in nuovo.polizze] == ["C-4"]


def test_clienti_esistenti_completati_non_sovrascritti(app):
    with app.app_context():
        db.session.add(Client(tipo="azienda", ragione_sociale="Rossi", partita_iva="22222222222", citta="Brescia"))
        db.session.commit()
        dati = _xlsx({"Clienti": [
            ["Ragione sociale", "Partita IVA", "Città", "Email"],
            ["Rossi Srl (nome diverso)", "22222222222", "Milano", "info@rossi.it"],
        ]})
        a = ie.analizza(dati, "x.xlsx")
        assert a["clienti"][0]["esito"] == "esistente"
        assert ie.importa(a)["completati"] == 1
        c = Client.query.one()
        assert (c.ragione_sociale, c.citta, c.email) == ("Rossi", "Brescia", "info@rossi.it")


def test_csv_con_punto_e_virgola(app):
    testo = "Ragione sociale;Codice fiscale;Provincia\nNeri Luca;nrilcu80a01h501x;rm\n".encode("cp1252")
    with app.app_context():
        a = ie.analizza(testo, "export.csv")
        d = a["clienti"][0]["dati"]
        assert d["codice_fiscale"] == "NRILCU80A01H501X" and d["provincia"] == "RM"


def test_file_non_validi(app):
    with app.app_context():
        with pytest.raises(ie.FileNonValido, match="xlsx"):
            ie.analizza(b"vecchio", "vecchio.xls")
        with pytest.raises(ie.FileNonValido):
            ie.analizza(b"non sono uno zip", "rotto.xlsx")
        with pytest.raises(ie.FileNonValido, match="colonne"):
            ie.analizza(_xlsx({"Foglio": [["Colore", "Peso"], ["rosso", 3]]}), "a.xlsx")


def test_flusso_web_anteprima_e_conferma(app, client):
    assert client.get("/clienti/importa/").status_code == 200
    r = client.get("/clienti/importa/modello.xlsx")
    assert r.status_code == 200 and r.data[:2] == b"PK"

    r = client.post("/clienti/importa/", data={"file": (io.BytesIO(r.data), "modello.xlsx")},
                    content_type="multipart/form-data")
    assert r.status_code == 200
    assert "Anteprima" in r.get_data(as_text=True)
    with app.app_context():
        assert Client.query.count() == 0  # l'anteprima non scrive nulla

    with client.session_transaction() as s:
        token = s["dc_import"]["token"]
    assert client.post("/clienti/importa/conferma", data={"token": "sbagliato"}).status_code == 302
    r = client.post("/clienti/importa/conferma", data={"token": token}, follow_redirects=True)
    assert "Importazione completata" in r.get_data(as_text=True)
    with app.app_context():
        assert Client.query.count() == 1 and Policy.query.count() == 1
    # Il file temporaneo è stato cancellato: una seconda conferma non reimporta.
    client.post("/clienti/importa/conferma", data={"token": token})
    with app.app_context():
        assert Policy.query.count() == 1

"""Programma installato: cartella dati, backup, blocco tra PC, archivio
esporta/importa, protezione dalle richieste di altri siti."""
import io
import json
import sqlite3
import time
import zipfile
from pathlib import Path

import pytest

from gestionale import archivio, create_app, desktop
from gestionale.models import Client, db


@pytest.fixture
def cartella(tmp_path):
    return tmp_path / "Deal Combined"


@pytest.fixture
def app(cartella):
    cartella.mkdir()
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{cartella / desktop.NOME_DB}",
        "UPLOAD_FOLDER": str(cartella / desktop.NOME_UPLOADS),
        "SECRET_KEY": "test",
    })
    yield app
    with app.app_context():
        db.engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()


def _aggiungi_cliente(app, nome):
    with app.app_context():
        db.session.add(Client(tipo="azienda", ragione_sociale=nome))
        db.session.commit()


def _nomi_clienti(app):
    with app.app_context():
        db.session.remove()
        return sorted(c.ragione_sociale for c in Client.query.all())


# ---------------------------------------------------------------- cartella e configurazione
def test_cartella_predefinita_e_configurazione(tmp_path):
    assert desktop.cartella_dati({}).name == "Deal Combined"
    cfg = tmp_path / "cfg" / "config.json"
    desktop.salva_configurazione({"cartella_dati": str(tmp_path / "OneDrive" / "DC")}, cfg)
    assert desktop.cartella_dati(desktop.leggi_configurazione(cfg)) == tmp_path / "OneDrive" / "DC"
    assert desktop.leggi_configurazione(tmp_path / "manca.json") == {}


def test_verifica_cartella(tmp_path):
    assert desktop.verifica_cartella("relativa/cartella")
    assert desktop.verifica_cartella(tmp_path / "nuova") is None
    assert (tmp_path / "nuova").is_dir()


def test_migrazione_dalla_vecchia_cartella(tmp_path):
    vecchia, nuova = tmp_path / "dati_gestionale", tmp_path / "Deal Combined"
    (vecchia / "uploads" / "1").mkdir(parents=True)
    sqlite3.connect(vecchia / desktop.NOME_DB).close()
    (vecchia / "uploads" / "1" / "polizza.pdf").write_bytes(b"%PDF")
    assert desktop.migra_vecchia_cartella(vecchia, nuova)
    assert (nuova / desktop.NOME_DB).exists() and (nuova / "uploads" / "1" / "polizza.pdf").exists()
    # non sovrascrive mai un archivio già presente
    assert not desktop.migra_vecchia_cartella(vecchia, nuova)


# ---------------------------------------------------------------- backup
def test_backup_e_rotazione(app, cartella):
    _aggiungi_cliente(app, "Rossi")
    backup_dir = cartella / desktop.NOME_BACKUP
    backup_dir.mkdir()
    for i in range(5):
        (backup_dir / f"gestionale-2020010{i}-000000-avvio.db").write_bytes(b"x")
    creato = desktop.esegui_backup(cartella, motivo="prova", da_tenere=3)
    rimasti = desktop.elenco_backup(cartella)
    assert len(rimasti) == 3 and rimasti[0] == creato
    con = sqlite3.connect(creato)
    assert con.execute("select ragione_sociale from clients").fetchone()[0] == "Rossi"
    con.close()


def test_backup_senza_database(tmp_path):
    assert desktop.esegui_backup(tmp_path) is None


# ---------------------------------------------------------------- blocco tra PC
def _scrivi_blocco(cartella, pc, aggiornato):
    cartella.mkdir(exist_ok=True)
    (cartella / desktop.NOME_BLOCCO).write_text(json.dumps({"pc": pc, "pid": 1, "aggiornato": aggiornato}))


def test_blocco_tra_pc(tmp_path):
    c = tmp_path / "dati"
    assert desktop.blocco_altrui(c) is None
    _scrivi_blocco(c, "PC-UFFICIO", time.time())
    assert desktop.blocco_altrui(c)["pc"] == "PC-UFFICIO"
    _scrivi_blocco(c, "PC-UFFICIO", time.time() - desktop.BLOCCO_SCADUTO_DOPO - 5)
    assert desktop.blocco_altrui(c) is None  # l'altro PC è stato chiuso male
    _scrivi_blocco(c, desktop.nome_pc(), time.time())
    assert desktop.blocco_altrui(c) is None  # questo stesso PC
    desktop.prendi_blocco(c)
    desktop.rilascia_blocco(c)
    assert not (c / desktop.NOME_BLOCCO).exists()
    _scrivi_blocco(c, "PC-UFFICIO", time.time())
    desktop.rilascia_blocco(c)
    assert (c / desktop.NOME_BLOCCO).exists()  # non tocca il blocco altrui


# ---------------------------------------------------------------- esporta / importa
def test_esporta_e_importa_ripristina_dati_e_documenti(app, client, cartella):
    _aggiungi_cliente(app, "Primo")
    (cartella / "uploads" / "1").mkdir(parents=True, exist_ok=True)
    (cartella / "uploads" / "1" / "visura.pdf").write_bytes(b"%PDF-1.4")
    r = client.get("/impostazioni/dati/esporta")
    assert r.status_code == 200 and r.mimetype == "application/zip"
    zip_bytes = r.data
    assert {"gestionale.db", "uploads/1/visura.pdf"} <= set(zipfile.ZipFile(io.BytesIO(zip_bytes)).namelist())

    _aggiungi_cliente(app, "Secondo")
    (cartella / "uploads" / "1" / "visura.pdf").unlink()
    # senza conferma non cambia nulla
    client.post("/impostazioni/dati/importa", data={"archivio": (io.BytesIO(zip_bytes), "a.zip")},
                content_type="multipart/form-data")
    assert _nomi_clienti(app) == ["Primo", "Secondo"]

    r = client.post("/impostazioni/dati/importa",
                    data={"archivio": (io.BytesIO(zip_bytes), "a.zip"), "conferma": "1"},
                    content_type="multipart/form-data")
    assert r.status_code == 302
    assert _nomi_clienti(app) == ["Primo"]
    assert (cartella / "uploads" / "1" / "visura.pdf").exists()
    # i dati sostituiti restano in un archivio di backup
    assert list((cartella / desktop.NOME_BACKUP).glob("archivio-prima-di-importare-*.zip"))


def _zip(voci):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for nome, dati in voci.items():
            z.writestr(nome, dati)
    return buf.getvalue()


@pytest.mark.parametrize("voci", [
    {"altro.txt": "x"},                                                     # niente database
    {"gestionale.db": "non sono un database"},                              # file non SQLite
    {"gestionale.db": b"SQLite format 3\x00", "../fuori.txt": "x"},         # zip slip
    {"gestionale.db": b"SQLite format 3\x00", "script.exe": "x"},           # file inatteso
])
def test_importa_rifiuta_archivi_non_validi(tmp_path, voci):
    db_file = tmp_path / "gestionale.db"
    db_file.write_bytes(b"originale")
    with pytest.raises(archivio.ArchivioNonValido):
        archivio.importa(_zip(voci), db_file, tmp_path / "uploads")
    assert db_file.read_bytes() == b"originale"
    assert not (tmp_path.parent / "fuori.txt").exists()


def test_importa_rifiuta_database_di_altro_programma(tmp_path):
    estraneo = tmp_path / "x.db"
    con = sqlite3.connect(estraneo)
    con.execute("create table altro (id int)")
    con.commit()
    con.close()
    with pytest.raises(archivio.ArchivioNonValido):
        archivio.importa(_zip({"gestionale.db": estraneo.read_bytes()}), tmp_path / "g.db", tmp_path / "u")


# ---------------------------------------------------------------- pagine e sicurezza
def test_pagina_dati_e_backup_manuale(client, cartella):
    assert client.get("/impostazioni/dati").status_code == 200
    client.post("/impostazioni/dati/backup")
    assert desktop.elenco_backup(cartella)


def test_richieste_da_altri_siti_bloccate(client):
    assert client.post("/impostazioni/dati/backup", headers={"Origin": "https://sito-malevolo.example"}).status_code == 403
    assert client.post("/impostazioni/dati/backup", headers={"Origin": "http://localhost"}).status_code == 302


def test_chiudi_solo_nel_programma_installato(app, client):
    assert client.post("/impostazioni/chiudi", headers={"X-DC-Azione": "chiudi"}).status_code == 404
    chiamato = []
    app.config.update(DC_DESKTOP=True, DC_SHUTDOWN=lambda: chiamato.append(True))
    assert client.post("/impostazioni/chiudi").status_code == 404  # senza intestazione
    assert client.post("/impostazioni/chiudi", headers={"X-DC-Azione": "chiudi"}).status_code == 204
    time.sleep(0.8)
    assert chiamato == [True]


def test_avviso_archivio_aperto_su_altro_pc(app, client, cartella):
    app.config["DC_BLOCCO_ALTRUI"] = {"pc": "PC-UFFICIO", "aggiornato": time.time()}
    r = client.get("/")
    assert r.status_code == 302 and "/impostazioni/in-uso" in r.headers["Location"]
    assert "PC-UFFICIO" in client.get("/impostazioni/in-uso").get_data(as_text=True)
    client.post("/impostazioni/in-uso/apri-comunque")
    assert app.config["DC_BLOCCO_ALTRUI"] is None
    assert desktop.leggi_blocco(cartella)["pc"] == desktop.nome_pc()
    assert client.get("/").status_code == 200


def test_cambio_cartella_con_copia(app, client, tmp_path):
    _aggiungi_cliente(app, "Da spostare")
    cfg = tmp_path / "config.json"
    nuova = tmp_path / "OneDrive" / "Deal Combined"
    app.config.update(DC_DESKTOP=True, DC_CONFIG_FILE=str(cfg))
    client.post("/impostazioni/dati/cartella", data={"cartella": str(nuova), "copia": "1"})
    assert desktop.leggi_configurazione(cfg)["cartella_dati"] == str(nuova)
    con = sqlite3.connect(nuova / desktop.NOME_DB)
    assert con.execute("select ragione_sociale from clients").fetchone()[0] == "Da spostare"
    con.close()

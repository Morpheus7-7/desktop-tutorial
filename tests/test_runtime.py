"""Test dell'avvio desktop (finestra di ripiego con Edge, schermata di avvio),
di app.py, dei tipi MIME e della gestione su disco dei documenti.

Cartella dati, backup all'avvio e archivio aperto su un altro PC sono
verificati in test_desktop.py.
"""
import importlib
import io
import mimetypes
import os
import sys

import pytest

import run_desktop as rd
from gestionale import _registra_tipi_mime
from gestionale.models import Client, Document, db


# ----------------------------------------------------------------------
# Tipi MIME dei file statici
# ----------------------------------------------------------------------
def test_tipi_mime_statici_corretti_anche_con_registro_errato(client):
    # Simula il registro di Windows con .js associato a text/plain.
    mimetypes.add_type("text/plain", ".js")
    mimetypes.add_type("text/plain", ".css")
    try:
        assert client.get("/static/app.js").mimetype == "text/plain"  # il problema
        _registra_tipi_mime()
        risposta = client.get("/static/app.js")
        assert risposta.mimetype == "text/javascript"
        assert risposta.headers["X-Content-Type-Options"] == "nosniff"
        assert client.get("/static/style.css").mimetype == "text/css"
    finally:
        _registra_tipi_mime()


# ----------------------------------------------------------------------
# app.py
# ----------------------------------------------------------------------
@pytest.fixture
def modulo_app(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///" + (tmp_path / "app.db").as_posix())
    monkeypatch.setenv("UPLOAD_FOLDER", str(tmp_path / "uploads"))
    monkeypatch.setenv("BACKUP_FOLDER", str(tmp_path / "backup"))
    monkeypatch.setenv("SECRET_KEY_FILE", str(tmp_path / "secret_key"))
    monkeypatch.delitem(sys.modules, "app", raising=False)
    modulo = importlib.import_module("app")
    yield modulo
    with modulo.app.app_context():
        db.session.remove()
        db.engine.dispose()
    sys.modules.pop("app", None)


def test_app_py_debug_solo_con_flask_debug(modulo_app, monkeypatch):
    assert modulo_app.debug_attivo({}) is False
    assert modulo_app.debug_attivo({"FLASK_DEBUG": "0"}) is False
    assert modulo_app.debug_attivo({"FLASK_DEBUG": "1"}) is True
    chiamate = []
    monkeypatch.setattr(modulo_app, "start_scheduler", lambda app: chiamate.append("scheduler"))
    monkeypatch.setattr(modulo_app.app, "run", lambda **kw: chiamate.append(kw))
    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    modulo_app.main()
    assert chiamate[0] == "scheduler"
    assert chiamate[1]["debug"] is False and chiamate[1]["host"] == "127.0.0.1"
    assert "flask --app app run" in modulo_app.__doc__ and "non parte" in modulo_app.__doc__.lower()


# ----------------------------------------------------------------------
# Documenti su disco
# ----------------------------------------------------------------------
def _cliente(app):
    with app.app_context():
        c = Client(tipo="azienda", ragione_sociale="Rossi Srl")
        db.session.add(c)
        db.session.commit()
        return c.id


def test_caricamento_nome_lungo_troncato(client, app):
    cid = _cliente(app)
    nome = "Set informativo " + "condizioni di assicurazione " * 15 + ".pdf"
    resp = client.post(f"/documenti/carica/{cid}", data={
        "file": (io.BytesIO(b"%PDF-1.4"), nome), "categoria": "polizza",
    }, content_type="multipart/form-data")
    assert resp.status_code == 302
    with app.app_context():
        doc = Document.query.one()
        assert len(doc.filename) <= 100 and doc.filename.endswith(".pdf")
        assert len(doc.original_name) <= 300 and doc.original_name.endswith(".pdf")
        assert os.path.isfile(os.path.join(app.config["UPLOAD_FOLDER"], doc.filename))
        doc_id = doc.id
    scaricato = client.get(f"/documenti/{doc_id}/scarica")
    assert scaricato.status_code == 200 and scaricato.data == b"%PDF-1.4"


def test_caricamento_errore_disco_senza_500(client, app, monkeypatch):
    from werkzeug.datastructures import FileStorage

    def _disco_pieno(self, dst, *a, **k):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(FileStorage, "save", _disco_pieno)
    cid = _cliente(app)
    resp = client.post(f"/documenti/carica/{cid}", data={
        "file": (io.BytesIO(b"x"), "contratto.pdf"),
    }, content_type="multipart/form-data", follow_redirects=True)
    assert resp.status_code == 200
    assert "Impossibile salvare su disco" in resp.get_data(as_text=True)
    with app.app_context():
        assert Document.query.count() == 0


def _documento(app, cid, filename):
    with app.app_context():
        d = Document(client_id=cid, categoria="altro", filename=filename, original_name="contratto.pdf")
        db.session.add(d)
        db.session.commit()
        return d.id


def test_eliminazione_file_bloccato_avviso_senza_500(client, app, monkeypatch):
    cid = _cliente(app)
    percorso = os.path.join(app.config["UPLOAD_FOLDER"], "abc_contratto.pdf")
    with open(percorso, "wb") as fh:
        fh.write(b"pdf")
    doc_id = _documento(app, cid, "abc_contratto.pdf")
    rimuovi = os.remove

    def _bloccato(p, *a, **k):
        if os.path.abspath(p) == os.path.abspath(percorso):
            raise PermissionError(13, "Il file è in uso da un altro processo")
        return rimuovi(p, *a, **k)

    monkeypatch.setattr(os, "remove", _bloccato)
    resp = client.post(f"/documenti/{doc_id}/elimina", data={"da_archivio": "1"}, follow_redirects=True)
    assert resp.status_code == 200
    assert "non è stato rimosso" in resp.get_data(as_text=True)
    with app.app_context():
        assert db.session.get(Document, doc_id) is None


def test_eliminazione_non_tocca_file_fuori_dalla_cartella(client, app, tmp_path):
    cid = _cliente(app)
    importante = tmp_path / "contabilita.xlsx"
    importante.write_bytes(b"dati")
    for nome in (str(importante), "../contabilita.xlsx"):
        doc_id = _documento(app, cid, nome)
        resp = client.post(f"/documenti/{doc_id}/elimina", data={"da_archivio": "1"})
        assert resp.status_code == 302
        with app.app_context():
            assert db.session.get(Document, doc_id) is None
    assert importante.read_bytes() == b"dati"


# ----------------------------------------------------------------------
# Finestra del programma
# ----------------------------------------------------------------------
def test_trova_edge_poi_chrome():
    env = {"PROGRAMFILES(X86)": r"C:\Program Files (x86)", "PROGRAMFILES": r"C:\Program Files"}
    edge = os.path.join(env["PROGRAMFILES(X86)"], "Microsoft", "Edge", "Application", "msedge.exe")
    chrome = os.path.join(env["PROGRAMFILES"], "Google", "Chrome", "Application", "chrome.exe")
    assert rd.trova_browser_app(env, esiste=lambda p: p in {edge, chrome}) == edge
    assert rd.trova_browser_app(env, esiste=lambda p: p == chrome) == chrome
    assert rd.trova_browser_app(env, esiste=lambda p: False) is None


def test_finestra_edge_in_modalita_applicazione(tmp_path):
    comando = rd.comando_finestra_app("msedge.exe", "http://127.0.0.1:5000", tmp_path)
    assert comando[0] == "msedge.exe" and "--app=http://127.0.0.1:5000" in comando
    assert f"--user-data-dir={tmp_path / 'finestra_edge'}" in comando


def test_senza_edge_si_ripiega_sul_browser(tmp_path, monkeypatch):
    monkeypatch.setattr(rd, "trova_browser_app", lambda: None)
    assert rd._apri_finestra_edge("http://127.0.0.1:5000", tmp_path) is False


def test_schermata_di_avvio_chiusa_senza_errori():
    rd._chiudi_splash()  # da sorgente non c'è la schermata: non fa nulla


def test_finestra_nativa_fallita_si_ricorda_per_versione(tmp_path):
    from gestionale import __version__

    prova = tmp_path / rd.FILE_PROVA_FINESTRA
    assert rd._leggi_testo(prova) is None
    prova.write_text(__version__, encoding="utf-8")
    assert rd._leggi_testo(prova) == __version__  # stessa versione: si usa Edge
    prova.write_text("0.0.1", encoding="utf-8")
    assert rd._leggi_testo(prova) != __version__  # programma aggiornato: si riprova la finestra nativa


def test_finestra_di_ripiego_riapribile_e_archivio_liberato_alla_chiusura(tmp_path, monkeypatch):
    """Con la finestra di Edge un nuovo doppio clic la riapre (DC_MOSTRA) e,
    chiusa la finestra, l'archivio si libera per l'altro PC."""
    import threading
    import time

    class _App:
        config = {}

    eventi, aperture = [], []
    profilo = tmp_path / "finestra_edge"
    profilo.mkdir()

    def apri(url, cartella):
        aperture.append(url)
        (profilo / "lockfile").write_text("")  # Edge ha aperto la finestra
        return True

    in_uso = {"n": 0}

    def edge_in_uso(p):
        in_uso["n"] += 1
        return in_uso["n"] < 3  # dopo un paio di controlli la finestra è chiusa

    chiusa = threading.Event()
    monkeypatch.setattr(rd, "_apri_finestra_edge", apri)
    monkeypatch.setattr(rd, "edge_in_uso", edge_in_uso)
    monkeypatch.setattr(rd.sys, "platform", "win32")
    app = _App()
    rd._finestra_ripiego(app, "http://127.0.0.1:5000", tmp_path,
                         entra=lambda: eventi.append("entra"),
                         esce=lambda: (eventi.append("esce"), chiusa.set()), pausa_s=0.01)
    assert chiusa.wait(5), "chiusa la finestra l'archivio deve liberarsi"
    assert eventi == ["entra", "esce"] and aperture == ["http://127.0.0.1:5000"]
    # Secondo doppio clic sull'icona: la finestra si riapre.
    app.config["DC_MOSTRA"]()
    time.sleep(0.05)
    assert aperture == ["http://127.0.0.1:5000"] * 2 and eventi[2] == "entra"


def test_finestra_di_ripiego_senza_edge_usa_il_browser(tmp_path, monkeypatch):
    class _App:
        config = {}

    aperti = []
    monkeypatch.setattr(rd, "_apri_finestra_edge", lambda url, cartella: False)
    monkeypatch.setattr(rd.webbrowser, "open", aperti.append)
    app = _App()
    rd._finestra_ripiego(app, "http://127.0.0.1:5000", tmp_path, entra=lambda: None, esce=lambda: None)
    assert aperti == ["http://127.0.0.1:5000"] and callable(app.config["DC_MOSTRA"])


def test_edge_in_uso_legge_il_blocco_del_profilo(tmp_path):
    assert rd.edge_in_uso(tmp_path) is False  # nessun lockfile: finestra chiusa
    (tmp_path / "lockfile").write_text("")
    assert rd.edge_in_uso(tmp_path) is False and not (tmp_path / "lockfile").exists()  # file libero

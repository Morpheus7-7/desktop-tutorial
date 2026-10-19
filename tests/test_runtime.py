"""Test dell'avvio desktop (cartella dati, istanza unica, porta, errori di
avvio, tipi MIME), di app.py e della gestione su disco dei documenti.

La logica di run_desktop è in funzioni pure con ambiente, sistema operativo e
cartelle iniettabili: così si verificano anche i casi Windows (cartella
temporanea dello ZIP, Programmi, OneDrive) senza un PC Windows.
"""
import importlib
import io
import mimetypes
import os
import socket
import sqlite3
import sys

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

import run_desktop as rd
from gestionale.models import Client, Document, db


# ----------------------------------------------------------------------
# Cartella dei dati
# ----------------------------------------------------------------------
def test_cartella_utente_per_sistema(tmp_path):
    home = tmp_path / "home"
    assert rd.cartella_utente("win32", {"LOCALAPPDATA": str(tmp_path / "Local")}, home) == \
        tmp_path / "Local" / "GestionaleAssicurativo"
    assert rd.cartella_utente("win32", {}, home) == home / "AppData" / "Local" / "GestionaleAssicurativo"
    assert rd.cartella_utente("darwin", {}, home) == \
        home / "Library" / "Application Support" / "GestionaleAssicurativo"
    assert rd.cartella_utente("linux", {}, home) == home / ".local" / "share" / "GestionaleAssicurativo"
    assert rd.cartella_utente("linux", {"XDG_DATA_HOME": str(tmp_path / "xdg")}, home) == \
        tmp_path / "xdg" / "GestionaleAssicurativo"


def test_posizione_instabile(tmp_path):
    temp = tmp_path / "Temp"
    env = {
        "PROGRAMFILES": str(tmp_path / "Program Files"),
        "ONEDRIVE": str(tmp_path / "OneDrive - Agenzia Rossi"),
    }
    assert rd.posizione_instabile(temp / "Temp1_GestionaleAssicurativo-windows.zip", env, temp) == "temporanea"
    assert rd.posizione_instabile(tmp_path / "Program Files" / "Gestionale", env, temp) == "programmi"
    assert rd.posizione_instabile(tmp_path / "OneDrive - Agenzia Rossi" / "Desktop", env, temp) == "onedrive"
    # Riconosciuti anche dal nome, se le variabili d'ambiente non bastano.
    assert rd.posizione_instabile(tmp_path / "x" / "Temp2_Gestionale.zip", {}, temp) == "temporanea"
    assert rd.posizione_instabile(tmp_path / "x" / "7zO1A2B3C4D", {}, temp) == "temporanea"
    assert rd.posizione_instabile(tmp_path / "OneDrive" / "Documenti", {}, temp) == "onedrive"
    assert rd.posizione_instabile(tmp_path / "Documenti" / "Gestionale", env, temp) is None


def _crea_db(percorso, tabella="clients"):
    percorso.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(percorso)
    conn.execute(f"CREATE TABLE {tabella} (id INTEGER PRIMARY KEY, nome TEXT)")
    conn.execute(f"INSERT INTO {tabella} (nome) VALUES ('Alfa')")
    conn.commit()
    conn.close()


def _scegli(base, tmp_path, **kwargs):
    kwargs.setdefault("env", {"LOCALAPPDATA": str(tmp_path / "Local")})
    return rd.scegli_cartella_dati(
        base, sistema="win32", home=tmp_path / "home", temp=tmp_path / "Temp", **kwargs
    )


def test_scelta_predefinita_cartella_utente(tmp_path):
    utente = tmp_path / "Local" / "GestionaleAssicurativo"
    # Programma estratto in una cartella normale: dati comunque nella cartella utente.
    scelta = _scegli(tmp_path / "Documenti" / "Gestionale", tmp_path)
    assert scelta.cartella == utente and scelta.migra_da is None and not scelta.avvisi
    # Programma avviato dall'interno dello ZIP (cartella temporanea): avviso, dati al sicuro.
    scelta = _scegli(tmp_path / "Temp" / "Temp1_Gestionale.zip", tmp_path)
    assert scelta.cartella == utente and "temporanea" in scelta.avvisi[0]
    # Programma copiato in Programmi: nessun tentativo di scrivere lì.
    env = {"LOCALAPPDATA": str(tmp_path / "Local"), "PROGRAMFILES": str(tmp_path / "Program Files")}
    assert _scegli(tmp_path / "Program Files" / "Gestionale", tmp_path, env=env).cartella == utente


def test_scelta_cartella_esistente_accanto_al_programma(tmp_path):
    base = tmp_path / "Documenti" / "Gestionale"
    _crea_db(base / "dati_gestionale" / "gestionale.db")
    scelta = _scegli(base, tmp_path)
    assert scelta.cartella == base / "dati_gestionale" and scelta.migra_da is None

    # Esistente ma su OneDrive: si continua a usarla, con un avviso.
    base = tmp_path / "OneDrive" / "Desktop" / "Gestionale"
    _crea_db(base / "dati_gestionale" / "gestionale.db")
    scelta = _scegli(base, tmp_path)
    assert scelta.cartella == base / "dati_gestionale" and "OneDrive" in scelta.avvisi[0]


def test_scelta_migra_dati_da_cartella_temporanea_o_non_scrivibile(tmp_path):
    utente = tmp_path / "Local" / "GestionaleAssicurativo"
    base = tmp_path / "Temp" / "Temp1_Gestionale.zip"
    _crea_db(base / "dati_gestionale" / "gestionale.db")
    scelta = _scegli(base, tmp_path)
    assert scelta.cartella == utente and scelta.migra_da == base / "dati_gestionale"

    altra = tmp_path / "Documenti" / "Sola lettura"
    _crea_db(altra / "dati_gestionale" / "gestionale.db")
    scelta = _scegli(altra, tmp_path, scrivibile=lambda p: False)
    assert scelta.cartella == utente and scelta.migra_da == altra / "dati_gestionale"
    assert "non è scrivibile" in scelta.avvisi[0]

    # Se la cartella utente ha già un database non si sovrascrive nulla.
    _crea_db(utente / "gestionale.db")
    scelta = _scegli(base, tmp_path)
    assert scelta.cartella == utente and scelta.migra_da is None


def test_scelta_portatile_e_variabile_esplicita(tmp_path):
    base = tmp_path / "Chiavetta" / "Gestionale"
    base.mkdir(parents=True)
    (base / "portatile.txt").write_text("")
    scelta = _scegli(base, tmp_path)
    assert scelta.cartella == base / "dati_gestionale" and scelta.motivo == "modalità portatile"

    # Portatile ma dentro lo ZIP: ignorata (i dati andrebbero persi).
    temp_base = tmp_path / "Temp" / "Temp1_Gestionale.zip"
    temp_base.mkdir(parents=True)
    (temp_base / "portatile.txt").write_text("")
    scelta = _scegli(temp_base, tmp_path)
    assert scelta.cartella == tmp_path / "Local" / "GestionaleAssicurativo"
    assert "portatile ignorata" in scelta.avvisi[0]

    env = {"GESTIONALE_DATI": str(tmp_path / "Dati espliciti")}
    scelta = _scegli(base, tmp_path, env=env)
    assert scelta.cartella == tmp_path / "Dati espliciti" and scelta.esplicita


def test_migra_dati_copia_database_e_documenti(tmp_path):
    sorgente, destinazione = tmp_path / "vecchia", tmp_path / "nuova"
    _crea_db(sorgente / "gestionale.db")
    (sorgente / "uploads").mkdir()
    (sorgente / "uploads" / "abc_doc.pdf").write_bytes(b"pdf")
    (sorgente / "secret_key").write_text("chiave")
    (sorgente / "gestionale.lock").write_text("")
    rd.migra_dati(sorgente, destinazione)
    conn = sqlite3.connect(destinazione / "gestionale.db")
    assert conn.execute("SELECT nome FROM clients").fetchone() == ("Alfa",)
    conn.close()
    assert (destinazione / "uploads" / "abc_doc.pdf").read_bytes() == b"pdf"
    assert (destinazione / "secret_key").read_text() == "chiave"
    assert not (destinazione / "gestionale.lock").exists()


def test_cartella_scrivibile(tmp_path):
    assert rd.cartella_scrivibile(tmp_path / "nuova" / "dati")
    file_al_posto_della_cartella = tmp_path / "file"
    file_al_posto_della_cartella.write_text("x")
    assert not rd.cartella_scrivibile(file_al_posto_della_cartella)


# ----------------------------------------------------------------------
# URL del database e variabili d'ambiente
# ----------------------------------------------------------------------
def test_url_sqlite_con_caratteri_speciali(tmp_path):
    percorso = tmp_path / "Gestionale%20v2 è #1?x=y" / "dati" / "gestionale.db"
    percorso.parent.mkdir(parents=True)
    url = rd.url_sqlite(percorso)
    assert make_url(url).database == str(percorso)
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE prova (id INTEGER)"))
    engine.dispose()
    assert percorso.is_file()  # proprio il file indicato, non un altro percorso decodificato


def test_configura_ambiente(tmp_path):
    env = {}
    rd.configura_ambiente(tmp_path / "dati 100%", env)
    assert make_url(env["DATABASE_URL"]).database == str(tmp_path / "dati 100%" / "gestionale.db")
    assert env["UPLOAD_FOLDER"] == str(tmp_path / "dati 100%" / "uploads")
    assert env["BACKUP_FOLDER"] == str(tmp_path / "dati 100%" / "backup")
    assert env["SECRET_KEY_FILE"] == str(tmp_path / "dati 100%" / "secret_key")
    # I valori già impostati dall'utente hanno la precedenza.
    env = {"DATABASE_URL": "sqlite:////altro.db"}
    rd.configura_ambiente(tmp_path, env)
    assert env["DATABASE_URL"] == "sqlite:////altro.db"


# ----------------------------------------------------------------------
# Istanza unica e porta
# ----------------------------------------------------------------------
def test_blocco_istanza_unica(tmp_path):
    primo, secondo = rd.BloccoIstanza(tmp_path / "gestionale.lock"), rd.BloccoIstanza(tmp_path / "gestionale.lock")
    assert primo.acquisisci()
    try:
        assert not secondo.acquisisci()
    finally:
        primo.rilascia()
    assert secondo.acquisisci()
    secondo.rilascia()


def test_socket_server_ripiega_su_porta_libera():
    primo = rd.crea_socket_server(0)
    try:
        occupata = primo.getsockname()[1]
        secondo = rd.crea_socket_server(occupata)
        try:
            assert secondo.getsockname()[1] != occupata
            assert rd.porta_in_ascolto(secondo.getsockname()[1])
        finally:
            secondo.close()
    finally:
        primo.close()


def test_porta_preferita():
    assert rd.porta_preferita({}) == 5000
    assert rd.porta_preferita({"PORT": "8080"}) == 8080
    assert rd.porta_preferita({"PORT": "abc"}) == 5000
    assert rd.porta_preferita({"PORT": "70000"}) == 5000


def test_seconda_istanza_apre_il_browser_sulla_prima(tmp_path):
    aperti = []
    # Nessuna istanza in ascolto: dopo l'attesa si rinuncia.
    assert rd.apri_istanza_esistente(tmp_path, attesa_s=0, apri=aperti.append) is None
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    try:
        porta = server.getsockname()[1]
        rd.scrivi_porta(tmp_path, porta)
        assert rd.leggi_porta(tmp_path) == porta
        url = rd.apri_istanza_esistente(tmp_path, attesa_s=0, apri=aperti.append)
    finally:
        server.close()
    assert url == f"http://127.0.0.1:{porta}" and aperti == [url]


# ----------------------------------------------------------------------
# Errori di avvio
# ----------------------------------------------------------------------
def test_errore_di_avvio_registrato_e_finestra_aperta(tmp_path, monkeypatch, capsys):
    attese = []
    monkeypatch.setattr(rd, "_cartella_log", tmp_path)
    monkeypatch.setattr(rd, "attendi_invio", lambda *a, **k: attese.append(True))

    def _guasto(argv):
        raise PermissionError("[Errno 13] Accesso negato: 'C:\\\\Program Files\\\\Gestionale'")

    monkeypatch.setattr(rd, "_main", _guasto)
    assert rd.main([]) == 1
    assert attese == [True]
    log = (tmp_path / "avvio.log").read_text(encoding="utf-8")
    assert "Traceback" in log and "PermissionError" in log
    uscita = capsys.readouterr().out
    assert "si è fermato per un errore" in uscita and str(tmp_path / "avvio.log") in uscita

    def _errore_chiaro(argv):
        raise rd.ErroreAvvio("Impossibile scrivere nella cartella dati X.")

    monkeypatch.setattr(rd, "_main", _errore_chiaro)
    assert rd.main([]) == 1
    assert "Impossibile scrivere nella cartella dati X." in capsys.readouterr().out


# ----------------------------------------------------------------------
# Tipi MIME dei file statici
# ----------------------------------------------------------------------
def test_tipi_mime_statici_corretti_anche_con_registro_errato(client):
    # Simula il registro di Windows con .js associato a text/plain.
    mimetypes.add_type("text/plain", ".js")
    mimetypes.add_type("text/plain", ".css")
    try:
        assert client.get("/static/app.js").mimetype == "text/plain"  # il problema
        rd.registra_tipi_mime()
        risposta = client.get("/static/app.js")
        assert risposta.mimetype == "text/javascript"
        assert risposta.headers["X-Content-Type-Options"] == "nosniff"
        assert client.get("/static/style.css").mimetype == "text/css"
    finally:
        rd.registra_tipi_mime()


# ----------------------------------------------------------------------
# app.py
# ----------------------------------------------------------------------
@pytest.fixture
def modulo_app(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", rd.url_sqlite(tmp_path / "app.db"))
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
# Finestra propria del programma
# ----------------------------------------------------------------------
class _WebviewFinto:
    def __init__(self, guasto=False):
        self.settings = {}
        self.finestre = []
        self.avviato = False
        self.guasto = guasto

    def create_window(self, titolo, url, **opzioni):
        self.finestre.append((titolo, url, opzioni))

    def start(self, **opzioni):
        if self.guasto:
            raise RuntimeError("WebView2 non installato")
        self.avviato = True


def test_finestra_propria_con_download_abilitati():
    finto = _WebviewFinto()
    assert rd.apri_finestra("http://127.0.0.1:5000", finto) is True
    assert finto.avviato and finto.finestre[0][:2] == ("Gestionale Assicurativo", "http://127.0.0.1:5000")
    assert finto.settings["ALLOW_DOWNLOADS"] is True


def test_senza_finestra_si_usa_il_browser(monkeypatch):
    assert rd.apri_finestra("http://127.0.0.1:5000", _WebviewFinto(guasto=True)) is False
    assert rd.modulo_finestra({"GESTIONALE_BROWSER": "1"}) is None
    monkeypatch.setitem(__import__("sys").modules, "webview", None)  # pywebview non installato
    assert rd.modulo_finestra({}) is None


def test_finestra_ricorda_dimensione_e_posizione(tmp_path):
    class _Finestra:
        width, height, x, y = 1500, 900, 40, 30

    rd.salva_geometria(tmp_path, _Finestra())
    assert rd.leggi_geometria(tmp_path) == {"width": 1500, "height": 900, "x": 40, "y": 30}
    (tmp_path / rd.FILE_FINESTRA).write_text('{"width": 10, "height": 99999, "x": -5000, "y": 1}')
    assert rd.leggi_geometria(tmp_path) == {}  # valori assurdi ignorati
    assert rd.leggi_geometria(None) == {}

"""Test di backup, backup automatico e ripristino."""
import io
import json
import os
import sqlite3
import stat
import time
import zipfile
from datetime import datetime, timedelta

import pytest

from gestionale import backup
from gestionale.models import Client, Document, Settings, User, db, now


def _crea_cliente(app, nome):
    with app.app_context():
        db.session.add(Client(tipo="azienda", ragione_sociale=nome))
        db.session.commit()


def test_crea_backup_contiene_database_documenti_e_manifest(app, tmp_path):
    _crea_cliente(app, "Alfa")
    with open(os.path.join(app.config["UPLOAD_FOLDER"], "abc_doc.pdf"), "wb") as fh:
        fh.write(b"pdf")
    with app.app_context():
        percorso = backup.crea_backup(str(tmp_path / "b.zip"))
    with zipfile.ZipFile(percorso) as zf:
        nomi = zf.namelist()
        assert "gestionale.db" in nomi and "uploads/abc_doc.pdf" in nomi
        manifest = json.loads(zf.read("manifest.json"))
        assert manifest["clienti"] == 1


def test_download_backup_admin(client):
    resp = client.post("/impostazioni/backup/scarica")
    assert resp.status_code == 200
    assert resp.mimetype == "application/zip"
    assert zipfile.is_zipfile(io.BytesIO(resp.data))


def test_backup_automatico_giornaliero_e_rotazione(app):
    with app.app_context():
        assert backup.backup_automatico() is not None
        assert backup.backup_automatico() is None  # già fatto oggi
        s = Settings.get()
        s.backup_conservati = 2
        db.session.commit()
        for _ in range(3):
            s.ultimo_backup_at = now() - timedelta(days=2)
            db.session.commit()
            assert backup.backup_automatico() is not None
        assert len(backup.elenco_backup()) == 2
        s.backup_automatico = False
        s.ultimo_backup_at = None
        db.session.commit()
        assert backup.backup_automatico() is None
        assert backup.backup_automatico(forza=True) is not None


def test_ripristino_backup(client, app):
    _crea_cliente(app, "Prima del backup")
    resp = client.post("/impostazioni/backup/scarica")
    archivio = resp.data
    _crea_cliente(app, "Dopo il backup")

    # Senza conferma esplicita non si ripristina nulla.
    client.post("/impostazioni/backup/ripristina", data={
        "archivio": (io.BytesIO(archivio), "backup.zip"), "conferma": "",
    }, content_type="multipart/form-data")
    with app.app_context():
        assert Client.query.count() == 2

    resp = client.post("/impostazioni/backup/ripristina", data={
        "archivio": (io.BytesIO(archivio), "backup.zip"), "conferma": "RIPRISTINA",
    }, content_type="multipart/form-data")
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/accesso")
    with app.app_context():
        assert [c.ragione_sociale for c in Client.query.all()] == ["Prima del backup"]
        sicurezza = [f for f in os.listdir(app.config["BACKUP_FOLDER"]) if f.startswith("pre_ripristino_")]
        assert len(sicurezza) == 1
        # La copia di sicurezza compare tra i backup elencati in Impostazioni.
        assert [b["nome"] for b in backup.elenco_backup() if b["pre_ripristino"]] == sicurezza
    # Dopo il ripristino la sessione è chiusa.
    assert client.get("/").status_code == 302


def test_ripristino_rifiuta_file_non_validi(client, app):
    _crea_cliente(app, "Intatto")
    for nome, contenuto in (("finto.zip", b"non sono uno zip"), ("vuoto.zip", None)):
        if contenuto is None:
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w") as zf:
                zf.writestr("altro.txt", "ciao")
            contenuto = buf.getvalue()
        resp = client.post("/impostazioni/backup/ripristina", data={
            "archivio": (io.BytesIO(contenuto), nome), "conferma": "RIPRISTINA",
        }, content_type="multipart/form-data", follow_redirects=True)
        assert "Ripristino annullato" in resp.get_data(as_text=True)
    with app.app_context():
        assert Client.query.one().ragione_sociale == "Intatto"


# ----------------------------------------------------------------------
# Percorsi relativi: stessa cartella per l'applicazione e per il backup
# ----------------------------------------------------------------------
def test_percorsi_relativi_risolti_rispetto_a_instance(tmp_path, monkeypatch):
    from flask import Flask

    from conftest import ADMIN_PASSWORD, ADMIN_USER, add_user, login, make_app

    istanza = tmp_path / "istanza"
    monkeypatch.setattr(Flask, "auto_find_instance_path", lambda self: str(istanza))
    corrente = tmp_path / "cartella_corrente"
    corrente.mkdir()
    monkeypatch.chdir(corrente)
    app = make_app(tmp_path, SQLALCHEMY_DATABASE_URI="sqlite:///rel.db",
                   UPLOAD_FOLDER="dati/uploads", BACKUP_FOLDER="dati/backup")
    backup.normalizza_cartelle(app)
    add_user(app, ADMIN_USER, ADMIN_PASSWORD, ruolo="admin")
    try:
        _crea_cliente(app, "Relativo")
        with app.app_context():
            assert backup.sqlite_path() == str(istanza / "rel.db")
            assert backup.cartella_documenti() == str(istanza / "dati" / "uploads")
            assert app.config["BACKUP_FOLDER"] == str(istanza / "dati" / "backup")
            percorso = backup.backup_automatico(forza=True)
            assert percorso.startswith(str(istanza / "dati" / "backup"))
        with zipfile.ZipFile(percorso) as zf:
            estratto = tmp_path / "estratto.db"
            estratto.write_bytes(zf.read("gestionale.db"))
        conn = sqlite3.connect(estratto)
        assert conn.execute("SELECT ragione_sociale FROM clients").fetchall() == [("Relativo",)]
        conn.close()

        # Caricamento e download dei documenti usano la stessa cartella.
        c = app.test_client()
        login(c)
        with app.app_context():
            cid = Client.query.one().id
        c.post(f"/documenti/carica/{cid}", data={"file": (io.BytesIO(b"pdf"), "polizza.pdf")},
               content_type="multipart/form-data")
        with app.app_context():
            doc = Document.query.one()
            assert (istanza / "dati" / "uploads" / doc.filename).is_file()
            doc_id = doc.id
        assert c.get(f"/documenti/{doc_id}/scarica").status_code == 200
    finally:
        with app.app_context():
            db.session.remove()
            db.engine.dispose()


# ----------------------------------------------------------------------
# Scrittura atomica e file abbandonati
# ----------------------------------------------------------------------
def test_backup_interrotto_non_lascia_archivi(app, monkeypatch):
    cartella = app.config["BACKUP_FOLDER"]

    def _interruzione():
        raise KeyboardInterrupt  # es. finestra chiusa a metà

    monkeypatch.setattr(backup, "_manifest", _interruzione)
    with app.app_context():
        with pytest.raises(KeyboardInterrupt):
            backup.backup_automatico(forza=True)
        assert backup.elenco_backup() == []
    assert os.listdir(cartella) == []


def test_file_parziali_ignorati_e_rimossi(app):
    cartella = app.config["BACKUP_FOLDER"]
    os.makedirs(cartella, exist_ok=True)
    vecchio = os.path.join(cartella, ".backup_gestionale_20260101_090000.zip.abc.part")
    recente = os.path.join(cartella, ".backup_gestionale_20261016_090000.zip.def.part")
    lavoro = os.path.join(cartella, ".lavoro_xyz")
    for percorso in (vecchio, recente):
        with open(percorso, "wb") as fh:
            fh.write(b"PK troncato")
    os.makedirs(lavoro)
    un_giorno_fa = time.time() - 86400
    os.utime(vecchio, (un_giorno_fa, un_giorno_fa))
    os.utime(lavoro, (un_giorno_fa, un_giorno_fa))
    with app.app_context():
        assert backup.elenco_backup() == []
        backup.backup_automatico(forza=True)
        assert len(backup.elenco_backup()) == 1
    assert not os.path.exists(vecchio) and not os.path.exists(lavoro)
    assert os.path.exists(recente)  # potrebbe essere un backup ancora in corso


# ----------------------------------------------------------------------
# Backup giornaliero per data di calendario
# ----------------------------------------------------------------------
def test_backup_dovuto_per_giorno_di_calendario():
    adesso = datetime(2026, 10, 16, 8, 58)
    assert backup.backup_dovuto(None, adesso)
    assert backup.backup_dovuto(datetime(2026, 10, 15, 9, 0, 5), adesso)  # ieri, anche se < 24 ore
    assert not backup.backup_dovuto(datetime(2026, 10, 16, 0, 1), adesso)
    assert backup.backup_dovuto(datetime(2027, 5, 4, 9, 0), adesso)  # nel futuro: orologio corretto


def test_backup_automatico_con_data_futura(app):
    with app.app_context():
        s = Settings.get()
        s.ultimo_backup_at = now() + timedelta(days=200)
        db.session.commit()
        assert backup.backup_automatico() is not None
        assert Settings.get().ultimo_backup_at <= now()


# ----------------------------------------------------------------------
# Copie di sicurezza pre-ripristino
# ----------------------------------------------------------------------
def test_copie_pre_ripristino_univoche_elencate_e_ruotate(app, monkeypatch):
    istante = datetime(2026, 10, 16, 9, 0, 0)
    monkeypatch.setattr(backup, "now", lambda: istante)
    prefisso = backup.PREFISSO_PRE_RIPRISTINO + backup.PREFISSO_FILE
    with app.app_context():
        nomi = {os.path.basename(backup._salva_in_cartella(prefisso)) for _ in range(3)}
        assert len(nomi) == 3  # stesso secondo, nomi diversi
        for _ in range(4):
            backup._salva_in_cartella(prefisso)
        normale = backup._salva_in_cartella(backup.PREFISSO_FILE)
        elenco = backup.elenco_backup()
        assert sum(b["pre_ripristino"] for b in elenco) == 7
        backup._ruota(backup.PRE_RIPRISTINO_CONSERVATI, pre_ripristino=True)
        backup._ruota(1)
        elenco = backup.elenco_backup()
        assert sum(b["pre_ripristino"] for b in elenco) == backup.PRE_RIPRISTINO_CONSERVATI
        assert [b["nome"] for b in elenco if not b["pre_ripristino"]] == [os.path.basename(normale)]


# ----------------------------------------------------------------------
# Validazione dell'archivio e del database da ripristinare
# ----------------------------------------------------------------------
def _ripristina(client, contenuto):
    return client.post("/impostazioni/backup/ripristina", data={
        "archivio": (io.BytesIO(contenuto), "backup.zip"), "conferma": "RIPRISTINA",
    }, content_type="multipart/form-data", follow_redirects=True)


def _archivio(db_bytes, extra=()):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("gestionale.db", db_bytes)
        for voce in extra:
            zf.writestr(voce, "x")
    return buf.getvalue()


def _db_valido(client):
    archivio = client.post("/impostazioni/backup/scarica").data
    with zipfile.ZipFile(io.BytesIO(archivio)) as zf:
        return zf.read("gestionale.db")


def test_ripristino_rifiuta_nomi_pericolosi_o_inattesi(client, app, tmp_path):
    _crea_cliente(app, "Intatto")
    db_bytes = _db_valido(client)
    collegamento = zipfile.ZipInfo("uploads/link.pdf")
    collegamento.external_attr = (stat.S_IFLNK | 0o777) << 16
    casi = [
        ("../fuori.txt", "percorso non ammesso"),
        ("/assoluto.txt", "percorso non ammesso"),
        ("uploads/..\\..\\fuori.txt", "percorso non ammesso"),
        ("C:/Windows/fuori.txt", "percorso non ammesso"),
        (collegamento, "collegamento simbolico"),
        ("uploads/sotto/doc.pdf", "file non previsto"),
        ("altro.txt", "file non previsto"),
    ]
    for voce, messaggio in casi:
        testo = _ripristina(client, _archivio(db_bytes, [voce])).get_data(as_text=True)
        assert "Ripristino annullato" in testo and messaggio in testo, voce
    assert not (tmp_path / "fuori.txt").exists()
    with app.app_context():
        assert Client.query.one().ragione_sociale == "Intatto"
        assert not any(b["pre_ripristino"] for b in backup.elenco_backup())


def _db_modificato(tmp_path, db_bytes, *sql):
    percorso = tmp_path / f"mod_{len(os.listdir(tmp_path))}.db"
    percorso.write_bytes(db_bytes)
    conn = sqlite3.connect(percorso)
    for istruzione in sql:
        conn.execute(istruzione)
    conn.commit()
    conn.close()
    return percorso.read_bytes()


def test_ripristino_rifiuta_database_non_validi(client, app, tmp_path):
    _crea_cliente(app, "Intatto")
    db_bytes = _db_valido(client)
    casi = [
        (_db_modificato(tmp_path, db_bytes, "DROP TABLE users"), "non contiene gli utenti"),
        (_db_modificato(tmp_path, db_bytes, "UPDATE users SET attivo = 0"), "amministratore attivo"),
        (_db_modificato(tmp_path, db_bytes, "UPDATE users SET ruolo = 'operatore'"), "amministratore attivo"),
        (_db_modificato(
            tmp_path, db_bytes,
            "INSERT INTO documents (client_id, categoria, filename, original_name) "
            "VALUES (1, 'altro', '../gestionale.db', 'x.pdf')"), "nomi di file non validi"),
        (b"SQLite format 3\x00" + b"\xff" * 4000, "danneggiato"),
        (b"non sono un database", "non è un database valido"),
    ]
    for contenuto, messaggio in casi:
        testo = _ripristina(client, _archivio(contenuto)).get_data(as_text=True)
        assert "Ripristino annullato" in testo and messaggio in testo, messaggio
    with app.app_context():
        assert Client.query.one().ragione_sociale == "Intatto"


def test_ripristino_invalida_tutte_le_sessioni(client, app):
    from conftest import add_user, login

    add_user(app, "operatore1", "password-op-1")
    with app.app_context():
        versioni = {u.username: u.sessione_versione for u in User.query.all()}
    archivio = client.post("/impostazioni/backup/scarica").data

    resp = client.post("/impostazioni/backup/ripristina", data={
        "archivio": (io.BytesIO(archivio), "backup.zip"), "conferma": "RIPRISTINA",
    }, content_type="multipart/form-data")
    assert resp.status_code == 302 and resp.headers["Location"].endswith("/accesso")
    with app.app_context():
        for user in User.query.all():
            assert user.sessione_versione > versioni[user.username]
    pagina = client.get("/accesso").get_data(as_text=True)
    assert "tutti gli utenti sono stati disconnessi" in pagina
    # L'amministratore può accedere di nuovo con le credenziali del backup.
    assert login(client).status_code == 302

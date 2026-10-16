"""Test di backup, backup automatico e ripristino."""
import io
import json
import os
import zipfile
from datetime import timedelta

from gestionale import backup
from gestionale.models import Client, Settings, db, now


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
        assert backup.backup_automatico() is None  # già fatto nelle ultime 24 ore
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

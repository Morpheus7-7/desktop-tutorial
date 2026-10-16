"""Backup e ripristino di database e documenti.

Il backup è un archivio ZIP con:
- ``gestionale.db``: copia coerente del database SQLite (API di backup di
  sqlite3, sicura anche mentre l'applicazione è in uso);
- ``uploads/``: i documenti caricati;
- ``manifest.json``: data, versione e conteggi principali.

Lo scheduler esegue un backup automatico al giorno nella cartella
``BACKUP_FOLDER`` e conserva gli ultimi N archivi.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import timedelta

from flask import current_app
from sqlalchemy.engine import make_url
from werkzeug.utils import secure_filename

from .models import Claim, Client, Policy, Settings, Title, User, db, now

NOME_DB = "gestionale.db"
PREFISSO_FILE = "backup_gestionale_"
TABELLE_OBBLIGATORIE = {"clients", "policies"}


class BackupError(Exception):
    """Errore comprensibile per l'utente durante backup o ripristino."""


def sqlite_path() -> str | None:
    """Percorso del file SQLite in uso, o None se il database non è SQLite."""
    url = make_url(current_app.config["SQLALCHEMY_DATABASE_URI"])
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        return None
    return os.path.abspath(url.database)


def supportato() -> bool:
    return sqlite_path() is not None


def nome_archivio() -> str:
    return f"{PREFISSO_FILE}{now().strftime('%Y%m%d_%H%M%S')}.zip"


def _manifest() -> dict:
    from . import __version__

    return {
        "applicazione": "Gestionale Assicurativo",
        "versione": __version__,
        "creato_il": now().isoformat(timespec="seconds"),
        "clienti": Client.query.count(),
        "polizze": Policy.query.count(),
        "titoli": Title.query.count(),
        "sinistri": Claim.query.count(),
    }


def crea_backup(destinazione: str) -> str:
    """Scrive l'archivio ZIP di backup in ``destinazione`` e ne restituisce il percorso."""
    origine = sqlite_path()
    if origine is None:
        raise BackupError("Il backup integrato è disponibile solo con database SQLite.")
    db.session.commit()  # niente transazioni a metà nella copia

    with tempfile.TemporaryDirectory() as tmp:
        copia = os.path.join(tmp, NOME_DB)
        sorgente = sqlite3.connect(origine)
        try:
            dest = sqlite3.connect(copia)
            try:
                sorgente.backup(dest)
            finally:
                dest.close()
        finally:
            sorgente.close()

        os.makedirs(os.path.dirname(os.path.abspath(destinazione)), exist_ok=True)
        with zipfile.ZipFile(destinazione, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(copia, NOME_DB)
            cartella = current_app.config["UPLOAD_FOLDER"]
            if os.path.isdir(cartella):
                for nome in sorted(os.listdir(cartella)):
                    percorso = os.path.join(cartella, nome)
                    if os.path.isfile(percorso):
                        zf.write(percorso, f"uploads/{nome}")
            zf.writestr("manifest.json", json.dumps(_manifest(), ensure_ascii=False, indent=2))
    return destinazione


def elenco_backup() -> list[dict]:
    """Backup automatici presenti nella cartella dei backup (dal più recente)."""
    cartella = current_app.config["BACKUP_FOLDER"]
    if not os.path.isdir(cartella):
        return []
    elenco = []
    for nome in os.listdir(cartella):
        if nome.startswith(PREFISSO_FILE) and nome.endswith(".zip"):
            percorso = os.path.join(cartella, nome)
            elenco.append(
                {"nome": nome, "dimensione": os.path.getsize(percorso), "mtime": os.path.getmtime(percorso)}
            )
    return sorted(elenco, key=lambda b: (b["mtime"], b["nome"]), reverse=True)


def _ruota(conservati: int) -> None:
    for vecchio in elenco_backup()[max(1, conservati):]:
        try:
            os.remove(os.path.join(current_app.config["BACKUP_FOLDER"], vecchio["nome"]))
        except OSError:  # pragma: no cover
            current_app.logger.warning("Impossibile eliminare il backup %s", vecchio["nome"])


def backup_automatico(forza: bool = False) -> str | None:
    """Esegue il backup giornaliero se dovuto. Restituisce il percorso creato."""
    if not supportato():
        return None
    settings = Settings.get()
    if not forza:
        if not settings.backup_automatico:
            return None
        if settings.ultimo_backup_at and now() - settings.ultimo_backup_at < timedelta(hours=24):
            return None
    cartella = current_app.config["BACKUP_FOLDER"]
    percorso = os.path.join(cartella, nome_archivio())
    progressivo = 1
    while os.path.exists(percorso):  # due backup nello stesso secondo
        progressivo += 1
        percorso = os.path.join(cartella, nome_archivio().replace(".zip", f"_{progressivo}.zip"))
    crea_backup(percorso)
    settings.ultimo_backup_at = now()
    db.session.commit()
    _ruota(settings.backup_conservati or 14)
    return percorso


def _verifica_database(percorso: str) -> None:
    with open(percorso, "rb") as fh:
        if fh.read(16) != b"SQLite format 3\x00":
            raise BackupError("Il file nell'archivio non è un database valido.")
    conn = sqlite3.connect(percorso)
    try:
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise BackupError("Il database nell'archivio risulta danneggiato.")
        tabelle = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()
    if not TABELLE_OBBLIGATORIE <= tabelle:
        raise BackupError("L'archivio non contiene un database del Gestionale Assicurativo.")
    if "users" in tabelle:
        conn = sqlite3.connect(percorso)
        try:
            admin = conn.execute(
                "SELECT COUNT(*) FROM users WHERE ruolo = 'admin' AND attivo = 1"
            ).fetchone()[0]
        finally:
            conn.close()
        if not admin:
            raise BackupError("Il backup non contiene alcun amministratore attivo: ripristino annullato.")


def ripristina_backup(file_zip) -> dict:
    """Ripristina database e documenti da un archivio di backup.

    Prima di sovrascrivere i dati crea comunque un backup di sicurezza dello
    stato attuale nella cartella dei backup. I documenti dell'archivio vengono
    aggiunti alla cartella dei documenti (quelli già presenti restano).
    """
    destinazione = sqlite_path()
    if destinazione is None:
        raise BackupError("Il ripristino integrato è disponibile solo con database SQLite.")

    with tempfile.TemporaryDirectory() as tmp:
        archivio = os.path.join(tmp, "backup.zip")
        file_zip.save(archivio)
        if not zipfile.is_zipfile(archivio):
            raise BackupError("Il file caricato non è un archivio ZIP di backup.")
        with zipfile.ZipFile(archivio) as zf:
            nomi = zf.namelist()
            if NOME_DB not in nomi:
                raise BackupError("L'archivio non contiene il database (gestionale.db).")
            db_estratto = os.path.join(tmp, NOME_DB)
            with zf.open(NOME_DB) as src, open(db_estratto, "wb") as dst:
                shutil.copyfileobj(src, dst)
            _verifica_database(db_estratto)

            sicurezza = crea_backup(
                os.path.join(current_app.config["BACKUP_FOLDER"], "pre_ripristino_" + nome_archivio())
            )

            # Sostituzione del database con l'API di backup di sqlite3.
            db.session.remove()
            db.engine.dispose()
            sorgente = sqlite3.connect(db_estratto)
            try:
                dest = sqlite3.connect(destinazione)
                try:
                    sorgente.backup(dest)
                finally:
                    dest.close()
            finally:
                sorgente.close()
            db.engine.dispose()

            # Documenti: solo file piatti con nome sicuro (niente percorsi «../»).
            cartella = current_app.config["UPLOAD_FOLDER"]
            os.makedirs(cartella, exist_ok=True)
            documenti = 0
            for nome in nomi:
                if not nome.startswith("uploads/") or nome.endswith("/"):
                    continue
                base = nome[len("uploads/"):]
                if not base or base != secure_filename(base):
                    continue
                with zf.open(nome) as src, open(os.path.join(cartella, base), "wb") as dst:
                    shutil.copyfileobj(src, dst)
                documenti += 1

    # Allinea lo schema se il backup proviene da una versione precedente.
    from . import init_db

    init_db()
    return {
        "documenti": documenti,
        "backup_sicurezza": os.path.basename(sicurezza),
        "utenti": User.query.count(),
    }

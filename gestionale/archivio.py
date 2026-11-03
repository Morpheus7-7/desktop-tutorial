"""Esporta e importa l'archivio completo (database + documenti caricati).

Serve a portare i dati da un PC all'altro (chiavetta, cloud) e come copia di
sicurezza manuale. Il file è un normale .zip con:
    gestionale.db       il database SQLite
    uploads/...         i documenti caricati
    deal-combined.json  informazioni sull'archivio (data, PC di origine)
"""
from __future__ import annotations

import io
import json
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path, PurePosixPath

from .desktop import NOME_DB, nome_pc

INTESTAZIONE_SQLITE = b"SQLite format 3\x00"
TABELLE_ATTESE = {"clients", "policies"}
LIMITE_ESTRATTO = 4 * 1024 ** 3  # 4 GB una volta estratto


class ArchivioNonValido(ValueError):
    pass


def percorso_db(uri: str) -> Path:
    """Percorso del file SQLite da un URI SQLAlchemy («sqlite:///...»)."""
    if not uri.startswith("sqlite:///"):
        raise ArchivioNonValido("Esporta e importa funzionano solo con il database SQLite locale.")
    return Path(uri[len("sqlite:///"):])


def esporta(db_file: Path, uploads: Path) -> io.BytesIO:
    """Crea lo zip in memoria. Il database è copiato con l'API di backup di
    SQLite, quindi la copia è coerente anche con il programma aperto."""
    buffer = io.BytesIO()
    with tempfile.TemporaryDirectory() as tmp:
        copia = Path(tmp) / NOME_DB
        src = sqlite3.connect(db_file)
        try:
            dst = sqlite3.connect(copia)
            try:
                src.backup(dst)
            finally:
                dst.close()
        finally:
            src.close()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(copia, NOME_DB)
            if uploads.is_dir():
                for f in sorted(uploads.rglob("*")):
                    if f.is_file():
                        z.write(f, str(PurePosixPath("uploads", *f.relative_to(uploads).parts)))
            z.writestr("deal-combined.json", json.dumps({
                "creato": datetime.now().isoformat(timespec="seconds"),
                "pc": nome_pc(),
            }, ensure_ascii=False))
    buffer.seek(0)
    return buffer


def _verifica(z: zipfile.ZipFile) -> None:
    nomi = z.namelist()
    if NOME_DB not in nomi:
        raise ArchivioNonValido("Il file non contiene un archivio di Deal Combined (manca gestionale.db).")
    for nome in nomi:
        p = PurePosixPath(nome)
        if p.is_absolute() or ".." in p.parts or "\\" in nome:
            raise ArchivioNonValido("L'archivio contiene percorsi non validi.")
        if nome not in (NOME_DB, "deal-combined.json") and p.parts[0] != "uploads":
            raise ArchivioNonValido(f"L'archivio contiene un file inatteso: {nome}")
    if sum(i.file_size for i in z.infolist()) > LIMITE_ESTRATTO:
        raise ArchivioNonValido("L'archivio è troppo grande per essere importato.")
    with z.open(NOME_DB) as f:
        if f.read(16) != INTESTAZIONE_SQLITE:
            raise ArchivioNonValido("Il database nell'archivio non è valido.")


def importa(dati: bytes, db_file: Path, uploads: Path) -> None:
    """Sostituisce database e documenti con quelli dell'archivio.

    Chi chiama deve aver già fatto un backup e chiuso le connessioni al
    database (db.engine.dispose()). In caso di errore i dati attuali non
    vengono toccati: tutto è prima estratto e verificato in una cartella
    temporanea.
    """
    try:
        z = zipfile.ZipFile(io.BytesIO(dati))
    except zipfile.BadZipFile as exc:
        raise ArchivioNonValido("Il file non è un archivio .zip valido.") from exc
    with z, tempfile.TemporaryDirectory() as tmp:
        _verifica(z)
        tmp = Path(tmp)
        z.extractall(tmp)
        con = sqlite3.connect(tmp / NOME_DB)
        try:
            tabelle = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        except sqlite3.DatabaseError as exc:
            raise ArchivioNonValido("Il database nell'archivio non è leggibile.") from exc
        finally:
            con.close()
        if not TABELLE_ATTESE <= tabelle:
            raise ArchivioNonValido("Il database nell'archivio non è di Deal Combined.")
        # Da qui in poi i dati sono verificati: sostituiamo.
        db_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(tmp / NOME_DB, db_file)
        if uploads.exists():
            shutil.rmtree(uploads)
        if (tmp / "uploads").is_dir():
            shutil.copytree(tmp / "uploads", uploads)
        else:
            uploads.mkdir(parents=True, exist_ok=True)

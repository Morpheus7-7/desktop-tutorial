"""Supporto per l'uso come programma installato sul PC.

- Cartella dati: di base «Documenti\\Deal Combined»; si può spostare (per
  esempio in una cartella di OneDrive o Google Drive per usarla da due PC).
  Il percorso scelto è salvato in un piccolo file di configurazione
  dell'utente, fuori dalla cartella dati.
- Blocco: un file nella cartella dati dice su quale PC il programma è aperto.
  Se la cartella è sincronizzata tra due PC, aprire l'archivio su entrambi
  insieme può corromperlo: il blocco lo segnala prima che succeda.
- Backup: a ogni avvio una copia del database, conservando le ultime copie.
"""
from __future__ import annotations

import json
import os
import socket
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

NOME_APP = "Deal Combined"
NOME_DB = "gestionale.db"
NOME_UPLOADS = "uploads"
NOME_BACKUP = "Backup"
NOME_BLOCCO = "deal-combined.lock"
BACKUP_DA_TENERE = 10
BLOCCO_SCADUTO_DOPO = 180  # secondi senza aggiornamenti: il PC che lo teneva è stato chiuso male
BATTITO_OGNI = 60


# ----------------------------------------------------------------------
# Cartelle
# ----------------------------------------------------------------------
def cartella_documenti() -> Path:
    """La cartella Documenti dell'utente, anche se Windows l'ha spostata
    (per esempio dentro OneDrive)."""
    if sys.platform == "win32":
        try:
            import ctypes
            import uuid

            # FOLDERID_Documents
            guid = uuid.UUID("{FDD39AD0-238F-46AF-ADB4-6C85480369C7}")

            class GUID(ctypes.Structure):
                _fields_ = [("data", ctypes.c_byte * 16)]

            gid = GUID()
            ctypes.memmove(ctypes.byref(gid), guid.bytes_le, 16)
            percorso = ctypes.c_wchar_p()
            shell32 = ctypes.windll.shell32
            if shell32.SHGetKnownFolderPath(ctypes.byref(gid), 0, None, ctypes.byref(percorso)) == 0:
                risultato = Path(percorso.value)
                ctypes.windll.ole32.CoTaskMemFree(percorso)
                return risultato
        except Exception:  # pragma: no cover - dipende da Windows
            pass
    casa = Path.home()
    for nome in ("Documents", "Documenti"):
        if (casa / nome).is_dir():
            return casa / nome
    return casa


def file_configurazione() -> Path:
    """Dove ricordiamo la cartella dati scelta (per utente, fuori dai dati)."""
    if sys.platform == "win32" and os.environ.get("APPDATA"):
        base = Path(os.environ["APPDATA"]) / NOME_APP
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "deal-combined"
    return base / "config.json"


def leggi_configurazione(percorso: Path | None = None) -> dict:
    percorso = percorso or file_configurazione()
    try:
        return json.loads(percorso.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def salva_configurazione(dati: dict, percorso: Path | None = None) -> None:
    percorso = percorso or file_configurazione()
    percorso.parent.mkdir(parents=True, exist_ok=True)
    percorso.write_text(json.dumps(dati, ensure_ascii=False, indent=2), encoding="utf-8")


def cartella_dati(config: dict | None = None) -> Path:
    config = leggi_configurazione() if config is None else config
    scelta = config.get("cartella_dati")
    return Path(scelta) if scelta else cartella_documenti() / NOME_APP


def verifica_cartella(percorso: str | Path) -> str | None:
    """Messaggio d'errore se la cartella non è utilizzabile, altrimenti None."""
    p = Path(percorso).expanduser()
    if not p.is_absolute():
        return "Indica un percorso completo (per esempio C:\\Users\\Mario\\OneDrive\\Deal Combined)."
    try:
        p.mkdir(parents=True, exist_ok=True)
        prova = p / ".prova-scrittura"
        prova.write_text("ok", encoding="utf-8")
        prova.unlink()
    except OSError:
        return "Non riesco a scrivere in questa cartella: controlla il percorso e i permessi."
    return None


def migra_vecchia_cartella(vecchia: Path, nuova: Path) -> bool:
    """Le versioni precedenti salvavano i dati accanto all'eseguibile, in
    «dati_gestionale». Se la nuova cartella è ancora vuota li copiamo."""
    import shutil

    if not (vecchia / NOME_DB).is_file() or (nuova / NOME_DB).exists():
        return False
    nuova.mkdir(parents=True, exist_ok=True)
    shutil.copy2(vecchia / NOME_DB, nuova / NOME_DB)
    if (vecchia / NOME_UPLOADS).is_dir():
        shutil.copytree(vecchia / NOME_UPLOADS, nuova / NOME_UPLOADS, dirs_exist_ok=True)
    return True


# ----------------------------------------------------------------------
# Backup
# ----------------------------------------------------------------------
def esegui_backup(cartella: Path, motivo: str = "avvio", da_tenere: int = BACKUP_DA_TENERE) -> Path | None:
    """Copia coerente del database (API di backup di SQLite) in Backup\\.
    Restituisce il file creato, o None se non c'è ancora un database."""
    db = cartella / NOME_DB
    if not db.is_file():
        return None
    destinazione = cartella / NOME_BACKUP
    destinazione.mkdir(parents=True, exist_ok=True)
    nome = f"gestionale-{datetime.now():%Y%m%d-%H%M%S}-{motivo}.db"
    file_backup = destinazione / nome
    sorgente = sqlite3.connect(db)
    try:
        copia = sqlite3.connect(file_backup)
        try:
            sorgente.backup(copia)
        finally:
            copia.close()
    finally:
        sorgente.close()
    for vecchio in elenco_backup(cartella)[da_tenere:]:
        try:
            vecchio.unlink()
        except OSError:
            pass
    return file_backup


def elenco_backup(cartella: Path) -> list[Path]:
    """Backup presenti, dal più recente."""
    d = cartella / NOME_BACKUP
    if not d.is_dir():
        return []
    return sorted(d.glob("gestionale-*.db"), key=lambda p: p.name, reverse=True)


# ----------------------------------------------------------------------
# Blocco tra PC
# ----------------------------------------------------------------------
def nome_pc() -> str:
    return socket.gethostname() or "questo PC"


def leggi_blocco(cartella: Path) -> dict | None:
    try:
        return json.loads((cartella / NOME_BLOCCO).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def blocco_altrui(cartella: Path, adesso: float | None = None) -> dict | None:
    """Il blocco di un ALTRO PC ancora attivo, oppure None se si può aprire."""
    blocco = leggi_blocco(cartella)
    if not blocco:
        return None
    adesso = time.time() if adesso is None else adesso
    if blocco.get("pc") == nome_pc():
        return None  # lo stesso PC: un'esecuzione precedente chiusa male
    if adesso - float(blocco.get("aggiornato", 0)) > BLOCCO_SCADUTO_DOPO:
        return None  # l'altro PC non aggiorna più il blocco
    return blocco


def prendi_blocco(cartella: Path) -> None:
    (cartella / NOME_BLOCCO).write_text(
        json.dumps({"pc": nome_pc(), "pid": os.getpid(), "aggiornato": time.time()}),
        encoding="utf-8",
    )


def rilascia_blocco(cartella: Path) -> None:
    blocco = leggi_blocco(cartella)
    if blocco and blocco.get("pc") == nome_pc() and blocco.get("pid") == os.getpid():
        try:
            (cartella / NOME_BLOCCO).unlink()
        except OSError:
            pass

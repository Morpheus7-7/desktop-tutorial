"""Backup e ripristino di database e documenti.

Il backup è un archivio ZIP con:
- ``gestionale.db``: copia coerente del database SQLite (API di backup di
  sqlite3, sicura anche mentre l'applicazione è in uso);
- ``uploads/``: i documenti caricati;
- ``manifest.json``: data, versione e conteggi principali.

Lo scheduler esegue un backup automatico al giorno (al primo controllo di ogni
giornata di calendario) nella cartella ``BACKUP_FOLDER`` e conserva gli
ultimi N archivi. Prima di ogni ripristino viene salvata una copia di
sicurezza dei dati attuali (``pre_ripristino_…zip``), ruotata a parte.

Gli archivi vengono scritti con un nome temporaneo e rinominati solo a
scrittura completata: se il programma viene chiuso a metà non resta mai un
archivio troncato tra i backup elencati o conteggiati nella rotazione.

I percorsi relativi di ``UPLOAD_FOLDER`` e ``BACKUP_FOLDER`` sono risolti
rispetto alla cartella ``instance`` dell'applicazione, come fa
Flask-SQLAlchemy per un ``DATABASE_URL`` SQLite relativo.
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import stat
import tempfile
import threading
import time
import zipfile
from datetime import datetime

from flask import Flask, current_app
from sqlalchemy import func
from werkzeug.utils import secure_filename

from .models import Claim, Client, Policy, Settings, Title, User, db, now

NOME_DB = "gestionale.db"
NOME_MANIFEST = "manifest.json"
CARTELLA_ZIP_DOCUMENTI = "uploads/"
PREFISSO_FILE = "backup_gestionale_"
PREFISSO_PRE_RIPRISTINO = "pre_ripristino_"
# File e cartelle di lavoro: mai elencati, rimossi se abbandonati.
SUFFISSO_PARZIALE = ".part"
PREFISSO_LAVORO = ".lavoro_"
ETA_MINIMA_ABBANDONATI_S = 3600
# Copie di sicurezza create prima dei ripristini: ruotate a parte.
PRE_RIPRISTINO_CONSERVATI = 5
TABELLE_OBBLIGATORIE = {"clients", "policies"}

# Serializza nomi, scrittura e rotazione tra lo scheduler e le richieste web
# (rientrante: il ripristino crea a sua volta la copia di sicurezza).
_lock_backup = threading.RLock()


class BackupError(Exception):
    """Errore comprensibile per l'utente durante backup o ripristino."""


# ----------------------------------------------------------------------
# Percorsi
# ----------------------------------------------------------------------
def percorso_assoluto(app: Flask, valore: str) -> str:
    """Percorso assoluto: quelli relativi partono dalla cartella ``instance``."""
    valore = os.path.expanduser(str(valore))
    if not os.path.isabs(valore):
        valore = os.path.join(app.instance_path, valore)
    return os.path.normpath(valore)


def normalizza_cartelle(app: Flask) -> None:
    """Rende assoluti ``UPLOAD_FOLDER`` e ``BACKUP_FOLDER`` nella configurazione.

    Va chiamata subito dopo ``create_app``: così tutte le parti dell'applicazione
    (caricamento, download ed eliminazione dei documenti, backup) usano la
    stessa cartella, qualunque sia la cartella corrente del processo.
    """
    for chiave in ("UPLOAD_FOLDER", "BACKUP_FOLDER"):
        if app.config.get(chiave):
            app.config[chiave] = percorso_assoluto(app, app.config[chiave])


def cartella_documenti() -> str:
    return percorso_assoluto(current_app, current_app.config["UPLOAD_FOLDER"])


def cartella_backup() -> str:
    return percorso_assoluto(current_app, current_app.config["BACKUP_FOLDER"])


def sqlite_path() -> str | None:
    """Percorso del file SQLite in uso, o None se il database non è SQLite.

    Usa l'URL dell'engine, che Flask-SQLAlchemy ha già reso assoluto: è lo
    stesso file che l'applicazione apre davvero, anche con un percorso relativo.
    """
    url = db.engine.url
    if url.get_backend_name() != "sqlite" or not url.database or url.database == ":memory:":
        return None
    if url.database.startswith("file:"):  # modalità URI di sqlite: non gestita
        return None
    return os.path.abspath(url.database)


def supportato() -> bool:
    return sqlite_path() is not None


def nome_archivio() -> str:
    return f"{PREFISSO_FILE}{now().strftime('%Y%m%d_%H%M%S')}.zip"


# ----------------------------------------------------------------------
# Creazione dell'archivio
# ----------------------------------------------------------------------
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


def _copia_sqlite(origine: str, destinazione: str) -> None:
    """Copia coerente di un database SQLite con l'API di backup."""
    sorgente = sqlite3.connect(origine)
    try:
        dest = sqlite3.connect(destinazione)
        try:
            sorgente.backup(dest)
        finally:
            dest.close()
    finally:
        sorgente.close()


def _cartella_lavoro() -> str | None:
    """Cartella per i file temporanei: quella dei backup (non %TEMP%), se disponibile."""
    cartella = cartella_backup()
    try:
        os.makedirs(cartella, exist_ok=True)
    except OSError:
        return None
    return cartella


def _scrivi_archivio(fileobj, cartella_lavoro: str | None) -> None:
    """Scrive l'archivio ZIP completo (database, documenti, manifest) in ``fileobj``."""
    origine = sqlite_path()
    if origine is None:
        raise BackupError("Il backup integrato è disponibile solo con database SQLite.")
    db.session.commit()  # niente transazioni a metà nella copia

    with tempfile.TemporaryDirectory(prefix=PREFISSO_LAVORO, dir=cartella_lavoro) as tmp:
        copia = os.path.join(tmp, NOME_DB)
        _copia_sqlite(origine, copia)
        with zipfile.ZipFile(fileobj, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(copia, NOME_DB)
            cartella = cartella_documenti()
            if os.path.isdir(cartella):
                for nome in sorted(os.listdir(cartella)):
                    percorso = os.path.join(cartella, nome)
                    if os.path.isfile(percorso) and not os.path.islink(percorso):
                        zf.write(percorso, CARTELLA_ZIP_DOCUMENTI + nome)
            zf.writestr(NOME_MANIFEST, json.dumps(_manifest(), ensure_ascii=False, indent=2))


def scrivi_backup(fileobj) -> None:
    """Scrive un backup completo in un file già aperto (es. un ``TemporaryFile`` da scaricare)."""
    _scrivi_archivio(fileobj, _cartella_lavoro())


def crea_backup(destinazione: str) -> str:
    """Scrive l'archivio ZIP di backup in ``destinazione`` e ne restituisce il percorso.

    L'archivio viene scritto con un nome temporaneo nella stessa cartella e
    rinominato (``os.replace``) solo quando è completo.
    """
    destinazione = os.path.abspath(destinazione)
    cartella = os.path.dirname(destinazione)
    os.makedirs(cartella, exist_ok=True)
    fd, parziale = tempfile.mkstemp(
        prefix="." + os.path.basename(destinazione) + ".", suffix=SUFFISSO_PARZIALE, dir=cartella
    )
    try:
        with os.fdopen(fd, "w+b") as fh:
            _scrivi_archivio(fh, cartella)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(parziale, destinazione)
    except BaseException:
        try:
            os.remove(parziale)
        except OSError:  # pragma: no cover - verrà rimosso da pulisci_abbandonati
            pass
        raise
    return destinazione


def pulisci_abbandonati(eta_minima_s: int = ETA_MINIMA_ABBANDONATI_S) -> int:
    """Rimuove archivi parziali e cartelle di lavoro lasciati da un'interruzione.

    Considera solo i file non modificati da almeno ``eta_minima_s`` secondi,
    per non toccare un backup in corso. Restituisce quanti elementi ha rimosso.
    """
    cartella = cartella_backup()
    if not os.path.isdir(cartella):
        return 0
    limite = time.time() - eta_minima_s
    rimossi = 0
    for nome in os.listdir(cartella):
        percorso = os.path.join(cartella, nome)
        try:
            if os.path.getmtime(percorso) > limite:
                continue
            if nome.endswith(SUFFISSO_PARZIALE) and os.path.isfile(percorso):
                os.remove(percorso)
            elif nome.startswith(PREFISSO_LAVORO) and os.path.isdir(percorso):
                shutil.rmtree(percorso)
            else:
                continue
            rimossi += 1
        except OSError:
            current_app.logger.warning("Impossibile rimuovere il file temporaneo di backup %s", percorso)
    return rimossi


def elenco_backup() -> list[dict]:
    """Archivi nella cartella dei backup, dal più recente.

    Comprende i backup (automatici e manuali) e le copie di sicurezza create
    prima di ogni ripristino (``pre_ripristino`` = True). I file temporanei di
    un backup in corso o interrotto non compaiono.
    """
    cartella = cartella_backup()
    if not os.path.isdir(cartella):
        return []
    elenco = []
    for nome in os.listdir(cartella):
        if not nome.endswith(".zip"):
            continue
        if nome.startswith(PREFISSO_PRE_RIPRISTINO):
            pre_ripristino = True
        elif nome.startswith(PREFISSO_FILE):
            pre_ripristino = False
        else:
            continue
        try:
            info = os.stat(os.path.join(cartella, nome))
        except OSError:  # pragma: no cover - eliminato nel frattempo
            continue
        elenco.append({
            "nome": nome,
            "dimensione": info.st_size,
            "mtime": info.st_mtime,
            "pre_ripristino": pre_ripristino,
        })
    return sorted(elenco, key=lambda b: (b["mtime"], b["nome"]), reverse=True)


def _ruota(conservati: int, pre_ripristino: bool = False) -> None:
    """Conserva gli ultimi ``conservati`` archivi del tipo indicato."""
    cartella = cartella_backup()
    candidati = [b for b in elenco_backup() if b["pre_ripristino"] == pre_ripristino]
    for vecchio in candidati[max(1, conservati):]:
        try:
            os.remove(os.path.join(cartella, vecchio["nome"]))
        except OSError:  # pragma: no cover
            current_app.logger.warning("Impossibile eliminare il backup %s", vecchio["nome"])


def _salva_in_cartella(prefisso: str) -> str:
    """Crea un archivio con nome univoco (progressivo se nello stesso secondo)."""
    with _lock_backup:
        cartella = cartella_backup()
        base = f"{prefisso}{now().strftime('%Y%m%d_%H%M%S')}"
        percorso = os.path.join(cartella, base + ".zip")
        progressivo = 1
        while os.path.exists(percorso):
            progressivo += 1
            percorso = os.path.join(cartella, f"{base}_{progressivo}.zip")
        return crea_backup(percorso)


def backup_dovuto(ultimo: datetime | None, adesso: datetime | None = None) -> bool:
    """True se il backup giornaliero va eseguito.

    Conta il giorno di calendario, non le 24 ore: chi apre il programma ogni
    mattina ottiene un backup al giorno anche se lo apre qualche minuto prima
    del giorno precedente. Un ultimo backup «nel futuro» (orologio del PC
    avanti e poi corretto) non blocca nulla: il backup viene rifatto e la data
    torna corretta.
    """
    adesso = adesso or now()
    return ultimo is None or ultimo > adesso or ultimo.date() < adesso.date()


def backup_automatico(forza: bool = False) -> str | None:
    """Esegue il backup giornaliero se dovuto. Restituisce il percorso creato."""
    if not supportato():
        return None
    settings = Settings.get()
    if not forza:
        if not settings.backup_automatico:
            return None
        if not backup_dovuto(settings.ultimo_backup_at):
            return None
    with _lock_backup:
        pulisci_abbandonati()
        percorso = _salva_in_cartella(PREFISSO_FILE)
        settings.ultimo_backup_at = now()
        db.session.commit()
        _ruota(settings.backup_conservati or 14)
    return percorso


# ----------------------------------------------------------------------
# Ripristino
# ----------------------------------------------------------------------
def _nome_documento_sicuro(nome) -> bool:
    """Nome di un file su disco: niente percorsi, unità o «..» (vedi documents.delete)."""
    return (
        isinstance(nome, str) and nome not in ("", ".", "..")
        and not any(c in nome for c in ("/", "\\", ":", "\x00"))
    )


def _verifica_membri(zf: zipfile.ZipFile) -> list[str]:
    """Controlla i nomi dei file dell'archivio prima di estrarre qualsiasi cosa.

    Sono ammessi solo ``gestionale.db``, ``manifest.json`` e i documenti nella
    cartella ``uploads/`` (senza sottocartelle). Percorsi assoluti, «..»,
    barre rovesciate, collegamenti simbolici o file inattesi indicano un
    archivio manomesso o non creato dal gestionale: il ripristino viene
    rifiutato. Restituisce i nomi dei documenti da estrarre.
    """
    documenti = []
    for info in zf.infolist():
        nome = info.filename
        parti = nome.split("/")
        if (
            not nome or nome.startswith("/") or "\\" in nome or ":" in nome
            or any(p in (".", "..") for p in parti)
        ):
            raise BackupError(f"L'archivio contiene un percorso non ammesso («{nome}»).")
        if stat.S_ISLNK(info.external_attr >> 16):
            raise BackupError(f"L'archivio contiene un collegamento simbolico («{nome}»).")
        if nome in (NOME_DB, NOME_MANIFEST, CARTELLA_ZIP_DOCUMENTI):
            continue
        if nome.startswith(CARTELLA_ZIP_DOCUMENTI) and len(parti) == 2 and parti[1]:
            documenti.append(nome)
            continue
        raise BackupError(
            f"L'archivio contiene un file non previsto («{nome}»): "
            "non sembra un backup del Gestionale Assicurativo."
        )
    return documenti


def _verifica_database(percorso: str) -> None:
    """Il database dell'archivio deve essere valido e avere un amministratore attivo."""
    with open(percorso, "rb") as fh:
        if fh.read(16) != b"SQLite format 3\x00":
            raise BackupError("Il file nell'archivio non è un database valido.")
    conn = sqlite3.connect(percorso)
    try:
        if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise BackupError("Il database nell'archivio risulta danneggiato.")
        tabelle = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not TABELLE_OBBLIGATORIE <= tabelle:
            raise BackupError("L'archivio non contiene un database del Gestionale Assicurativo.")
        if "users" not in tabelle:
            # Senza utenti la «configurazione iniziale» tornerebbe accessibile a chiunque.
            raise BackupError(
                "Il database dell'archivio non contiene gli utenti (versione precedente del "
                "gestionale): il ripristino lascerebbe il programma senza amministratore."
            )
        colonne = {r[1] for r in conn.execute("PRAGMA table_info(users)")}
        if not {"ruolo", "attivo", "password_hash"} <= colonne:
            raise BackupError("La tabella degli utenti del backup non è valida.")
        admin = conn.execute(
            "SELECT COUNT(*) FROM users WHERE ruolo = 'admin' AND attivo = 1 AND password_hash != ''"
        ).fetchone()[0]
        if not admin:
            raise BackupError("Il backup non contiene alcun amministratore attivo.")
        if "documents" in tabelle:
            for (nome,) in conn.execute("SELECT filename FROM documents"):
                if not _nome_documento_sicuro(nome):
                    raise BackupError("Il database dell'archivio contiene documenti con nomi di file non validi.")
    except sqlite3.DatabaseError as exc:
        raise BackupError("Il database nell'archivio risulta danneggiato o non leggibile.") from exc
    finally:
        conn.close()


def ripristina_backup(file_zip) -> dict:
    """Ripristina database e documenti da un archivio di backup.

    Prima di sovrascrivere i dati verifica l'intero archivio (nomi dei file,
    integrità, database con almeno un amministratore attivo) e crea una copia
    di sicurezza dello stato attuale nella cartella dei backup. I documenti
    dell'archivio vengono aggiunti alla cartella dei documenti (quelli già
    presenti restano). Al termine tutte le sessioni aperte vengono invalidate.
    """
    destinazione = sqlite_path()
    if destinazione is None:
        raise BackupError("Il ripristino integrato è disponibile solo con database SQLite.")

    with _lock_backup, tempfile.TemporaryDirectory(prefix=PREFISSO_LAVORO, dir=_cartella_lavoro()) as tmp:
        archivio = os.path.join(tmp, "backup.zip")
        file_zip.save(archivio)
        if not zipfile.is_zipfile(archivio):
            raise BackupError("Il file caricato non è un archivio ZIP di backup.")
        try:
            zf = zipfile.ZipFile(archivio)
        except zipfile.BadZipFile as exc:
            raise BackupError("Il file caricato non è un archivio ZIP di backup.") from exc
        with zf:
            documenti_zip = _verifica_membri(zf)
            if NOME_DB not in zf.namelist():
                raise BackupError("L'archivio non contiene il database (gestionale.db).")
            try:
                danneggiato = zf.testzip()
            except (zipfile.BadZipFile, OSError, EOFError) as exc:
                raise BackupError("L'archivio ZIP risulta danneggiato.") from exc
            if danneggiato is not None:
                raise BackupError(f"L'archivio ZIP risulta danneggiato («{danneggiato}»).")
            db_estratto = os.path.join(tmp, NOME_DB)
            with zf.open(NOME_DB) as src, open(db_estratto, "wb") as dst:
                shutil.copyfileobj(src, dst)
            _verifica_database(db_estratto)

            sicurezza = _salva_in_cartella(PREFISSO_PRE_RIPRISTINO + PREFISSO_FILE)
            _ruota(PRE_RIPRISTINO_CONSERVATI, pre_ripristino=True)

            # Sostituzione del database con l'API di backup di sqlite3.
            db.session.remove()
            db.engine.dispose()
            _copia_sqlite(db_estratto, destinazione)
            db.engine.dispose()

            # Documenti: solo file piatti con nome sicuro.
            cartella = cartella_documenti()
            os.makedirs(cartella, exist_ok=True)
            documenti = saltati = 0
            for nome in documenti_zip:
                base = nome[len(CARTELLA_ZIP_DOCUMENTI):]
                if base != secure_filename(base):
                    saltati += 1
                    continue
                with zf.open(nome) as src, open(os.path.join(cartella, base), "wb") as dst:
                    shutil.copyfileobj(src, dst)
                documenti += 1

    # Allinea lo schema se il backup proviene da una versione precedente.
    from . import init_db

    init_db()
    # Invalida i cookie di sessione emessi prima del ripristino (tutti gli utenti).
    User.query.update(
        {User.sessione_versione: func.coalesce(User.sessione_versione, 0) + 1},
        synchronize_session=False,
    )
    db.session.commit()
    return {
        "documenti": documenti,
        "documenti_saltati": saltati,
        "backup_sicurezza": os.path.basename(sicurezza),
        "utenti": User.query.count(),
    }

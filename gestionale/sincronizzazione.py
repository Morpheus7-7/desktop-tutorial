"""Sincronizzazione manuale tra due PC tramite una cartella condivisa.

Si lavora su un PC alla volta. A fine lavoro «Salva per l'altro PC» scrive
nella cartella scelta (una chiavetta USB, OneDrive, Dropbox…) un pacchetto
con tutti i dati; sull'altro PC «Carica dall'altro PC» lo ripristina.

Il pacchetto è un normale archivio di backup con in più, nel manifest, un
identificativo, il nome del PC e l'identificativo del pacchetto da cui il PC
era partito. Lo stato della sincronizzazione di ogni PC (cartella, ultimo
pacchetto inviato o ricevuto, quando) sta in un piccolo file accanto al
database, così non viene sovrascritto quando si caricano i dati dell'altro PC.

Protezioni contro la perdita di dati:
- prima di caricare, se su questo PC sono state fatte modifiche dopo l'ultima
  sincronizzazione, serve una conferma esplicita (verrebbero sostituite);
- prima di salvare, se nella cartella c'è un pacchetto dell'altro PC non
  ancora caricato qui, serve una conferma (verrebbe sovrascritto);
- il pacchetto precedente resta nella cartella come copia, e ogni caricamento
  crea prima la solita copia di sicurezza dei dati attuali.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import tempfile
import uuid
import zipfile
from datetime import datetime

from . import backup
from .models import AuditLog, Client, Policy, db, now

NOME_PACCHETTO = "gestionale_sincronizzazione.zip"
NOME_PRECEDENTE = "gestionale_sincronizzazione_precedente.zip"
NOME_STATO = "sincronizzazione.json"
# Voci del registro che non cambiano i dati.
AZIONI_SENZA_MODIFICHE = ("login", "login_fallito", "logout", "export", "backup", "sincronizzazione")


class SincronizzazioneError(Exception):
    """Errore comprensibile per l'utente."""


class ConfermaNecessaria(SincronizzazioneError):
    """L'operazione farebbe perdere dati: serve una conferma esplicita."""


# ----------------------------------------------------------------------
# Stato di questo PC
# ----------------------------------------------------------------------
def _percorso_stato() -> str:
    database = backup.sqlite_path()
    if database is None:
        raise SincronizzazioneError("La sincronizzazione è disponibile solo con database SQLite.")
    return os.path.join(os.path.dirname(database), NOME_STATO)


def stato() -> dict:
    """Cartella scelta e ultimo pacchetto inviato o ricevuto da questo PC."""
    try:
        with open(_percorso_stato(), encoding="utf-8") as fh:
            dati = json.load(fh)
        return dati if isinstance(dati, dict) else {}
    except (OSError, ValueError, SincronizzazioneError):
        return {}


def _salva_stato(**valori) -> dict:
    dati = {**stato(), **valori}
    percorso = _percorso_stato()
    parziale = percorso + ".part"
    with open(parziale, "w", encoding="utf-8") as fh:
        json.dump(dati, fh, ensure_ascii=False, indent=2)
    os.replace(parziale, percorso)
    return dati


def _ora(valore: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(valore) if valore else None
    except ValueError:
        return None


def nome_pc() -> str:
    return (socket.gethostname() or "PC").split(".")[0][:60]


# ----------------------------------------------------------------------
# Cartella e pacchetto
# ----------------------------------------------------------------------
def verifica_cartella(cartella: str) -> str | None:
    """Messaggio d'errore se la cartella non esiste o non è scrivibile, altrimenti None."""
    if not cartella:
        return "Indica la cartella di sincronizzazione."
    if not os.path.isabs(cartella):
        return "Indica il percorso completo della cartella (es. E:\\Gestionale o la cartella di OneDrive)."
    if not os.path.isdir(cartella):
        return f"La cartella «{cartella}» non esiste o non è collegata (la chiavetta è inserita?)."
    try:
        with tempfile.NamedTemporaryFile(dir=cartella, prefix=".prova_", delete=True):
            pass
    except OSError:
        return f"Nella cartella «{cartella}» non si può scrivere."
    return None


def cartella() -> str | None:
    return stato().get("cartella") or None


def imposta_cartella(percorso: str) -> None:
    percorso = os.path.abspath(os.path.expanduser(percorso.strip())) if percorso and percorso.strip() else ""
    errore = verifica_cartella(percorso)
    if errore:
        raise SincronizzazioneError(errore)
    _salva_stato(cartella=percorso)


def pacchetto(cartella_sync: str | None = None) -> dict | None:
    """Informazioni sul pacchetto presente nella cartella (None se manca o non è leggibile)."""
    cartella_sync = cartella_sync or cartella()
    if not cartella_sync:
        return None
    percorso = os.path.join(cartella_sync, NOME_PACCHETTO)
    try:
        with zipfile.ZipFile(percorso) as zf:
            manifest = json.loads(zf.read(backup.NOME_MANIFEST).decode("utf-8"))
    except (OSError, KeyError, ValueError, zipfile.BadZipFile):
        return None
    info = manifest.get("sincronizzazione") or {}
    if not info.get("id"):
        return None
    return {**manifest, **info, "percorso": percorso, "creato": _ora(info.get("creato_il"))}


def modifiche_locali() -> int:
    """Quante modifiche ai dati sono state fatte su questo PC dopo l'ultima sincronizzazione.

    Si contano le voci del registro attività degli utenti (non gli
    automatismi, che l'altro PC ripete da sé). Su un PC mai sincronizzato
    contano i clienti e le polizze già presenti.
    """
    ultima = _ora(stato().get("ultimo_at"))
    if ultima is None:
        return Client.query.count() + Policy.query.count()
    return AuditLog.query.filter(
        AuditLog.created_at > ultima,
        AuditLog.azione.notin_(AZIONI_SENZA_MODIFICHE),
        db.or_(AuditLog.username.is_(None), AuditLog.username != "sistema"),
    ).count()


def situazione() -> dict:
    """Riepilogo per la pagina e per l'avviso in dashboard."""
    dati = stato()
    cartella_sync = dati.get("cartella")
    errore = verifica_cartella(cartella_sync) if cartella_sync else None
    trovato = pacchetto(cartella_sync) if cartella_sync and not errore else None
    return {
        "cartella": cartella_sync,
        "errore_cartella": errore,
        "pacchetto": trovato,
        "ultimo_id": dati.get("ultimo_id"),
        "ultimo_at": _ora(dati.get("ultimo_at")),
        "ultima_operazione": dati.get("ultima_operazione"),
        # Un pacchetto diverso dall'ultimo inviato o ricevuto qui viene dall'altro PC.
        "da_caricare": bool(trovato and trovato["id"] != dati.get("ultimo_id")),
        "modifiche_locali": modifiche_locali(),
        "pc": nome_pc(),
    }


# ----------------------------------------------------------------------
# Operazioni
# ----------------------------------------------------------------------
def esporta(forza: bool = False) -> dict:
    """Scrive il pacchetto con tutti i dati nella cartella di sincronizzazione."""
    cartella_sync = cartella()
    errore = verifica_cartella(cartella_sync) if cartella_sync else "Scegli prima la cartella di sincronizzazione."
    if errore:
        raise SincronizzazioneError(errore)
    dati = stato()
    presente = pacchetto(cartella_sync)
    if presente and presente["id"] != dati.get("ultimo_id") and not forza:
        raise ConfermaNecessaria(
            f"Nella cartella c'è un pacchetto salvato da «{presente.get('pc', 'altro PC')}» il "
            f"{presente['creato']:%d/%m/%Y alle %H:%M} che non hai ancora caricato su questo PC: "
            "salvando lo sovrascrivi e le modifiche fatte sull'altro PC andranno perse."
            if presente.get("creato") else
            "Nella cartella c'è un pacchetto dell'altro PC che non hai ancora caricato: salvando lo sovrascrivi."
        )
    destinazione = os.path.join(cartella_sync, NOME_PACCHETTO)
    if os.path.isfile(destinazione):
        shutil.copyfile(destinazione, os.path.join(cartella_sync, NOME_PRECEDENTE))
    identificativo = uuid.uuid4().hex
    adesso = now()
    backup.crea_backup(destinazione, extra_manifest={"sincronizzazione": {
        "id": identificativo, "pc": nome_pc(), "creato_il": adesso.isoformat(timespec="seconds"),
        "base": dati.get("ultimo_id"),
    }})
    _salva_stato(ultimo_id=identificativo, ultimo_at=adesso.isoformat(),
                 ultima_operazione="inviato")
    return {"percorso": destinazione, "creato": adesso}


class _FileLocale:
    """Adatta un file su disco all'interfaccia di upload usata dal ripristino."""

    def __init__(self, percorso: str):
        self.percorso = percorso
        self.filename = os.path.basename(percorso)

    def save(self, destinazione: str) -> None:
        shutil.copyfile(self.percorso, destinazione)


def importa(forza: bool = False) -> dict:
    """Sostituisce i dati di questo PC con quelli del pacchetto dell'altro PC."""
    cartella_sync = cartella()
    errore = verifica_cartella(cartella_sync) if cartella_sync else "Scegli prima la cartella di sincronizzazione."
    if errore:
        raise SincronizzazioneError(errore)
    trovato = pacchetto(cartella_sync)
    if trovato is None:
        raise SincronizzazioneError("Nella cartella non c'è nessun pacchetto da caricare: salvalo prima sull'altro PC.")
    if trovato["id"] == stato().get("ultimo_id"):
        raise SincronizzazioneError("Questo PC ha già i dati del pacchetto presente nella cartella: niente da caricare.")
    modifiche = modifiche_locali()
    if modifiche and not forza:
        raise ConfermaNecessaria(
            f"Su questo PC ci sono {modifiche} modifiche successive all'ultima sincronizzazione: caricando il "
            "pacchetto dell'altro PC verranno sostituite (resta comunque una copia di sicurezza)."
        )
    esito = backup.ripristina_backup(_FileLocale(trovato["percorso"]))
    # Le voci del registro arrivano con l'orologio dell'altro PC: l'ultima
    # sincronizzazione non deve risultare precedente a nessuna di esse.
    ultima_voce = db.session.query(db.func.max(AuditLog.created_at)).scalar()
    momento = max(filter(None, [now(), ultima_voce]))
    _salva_stato(ultimo_id=trovato["id"], ultimo_at=momento.isoformat(),
                 ultima_operazione="ricevuto")
    return {**esito, "pacchetto": trovato}

"""Aggiornamenti del programma installato tramite le Release di GitHub.

Il repository è pubblico: l'elenco delle versioni si legge senza token.
Una versione si installa da sola solo se la Release contiene, oltre a
``Installa-DealCombined.exe``, il file ``Installa-DealCombined.exe.sha256``
con l'impronta SHA-256: l'installatore scaricato viene confrontato con
l'impronta e, se non coincide, non viene eseguito. Senza impronta il
programma mostra solo il link alla pagina della Release.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

REPOSITORY = "Morpheus7-7/desktop-tutorial"
API_ULTIMA = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
NOME_INSTALLATORE = "Installa-DealCombined.exe"
NOME_IMPRONTA = NOME_INSTALLATORE + ".sha256"
LIMITE_SCARICAMENTO = 300 * 1024 * 1024
PARAMETRI_SILENZIOSI = ["/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART"]


class AggiornamentoNonValido(Exception):
    pass


def versione_tupla(testo: str) -> tuple[int, ...]:
    """'v2.1.0' -> (2, 1, 0); le parti non numeriche si ignorano."""
    numeri = re.findall(r"\d+", (testo or "").split("-")[0])
    return tuple(int(n) for n in numeri[:4]) or (0,)


def piu_recente(nuova: str, attuale: str) -> bool:
    a, b = versione_tupla(nuova), versione_tupla(attuale)
    lunghezza = max(len(a), len(b))
    return a + (0,) * (lunghezza - len(a)) > b + (0,) * (lunghezza - len(b))


def _scarica(url: str, timeout: float, limite: int) -> bytes:
    richiesta = urllib.request.Request(url, headers={
        "User-Agent": "Deal-Combined-aggiornamenti",
        "Accept": "application/vnd.github+json, application/octet-stream;q=0.9, */*;q=0.5",
    })
    with urllib.request.urlopen(richiesta, timeout=timeout) as risposta:  # noqa: S310 - solo https fissi
        dati = risposta.read(limite + 1)
    if len(dati) > limite:
        raise AggiornamentoNonValido("Il file scaricato è troppo grande.")
    return dati


def leggi_release(dati: dict, versione_attuale: str) -> dict | None:
    """Dalla risposta dell'API ricava le informazioni utili, oppure None
    se non c'è una versione più recente."""
    tag = dati.get("tag_name") or ""
    if dati.get("draft") or dati.get("prerelease") or not piu_recente(tag, versione_attuale):
        return None
    asset = {a.get("name"): a.get("browser_download_url") for a in dati.get("assets", [])}
    installatore, impronta = asset.get(NOME_INSTALLATORE), asset.get(NOME_IMPRONTA)
    if not (installatore and impronta and installatore.startswith("https://") and impronta.startswith("https://")):
        installatore = impronta = None
    return {
        "versione": tag.lstrip("vV"),
        "pagina": dati.get("html_url") or f"https://github.com/{REPOSITORY}/releases",
        "note": (dati.get("body") or "").strip()[:4000],
        "installatore": installatore,
        "impronta": impronta,
    }


def controlla(versione_attuale: str, timeout: float = 8.0) -> dict | None:
    """Chiede a GitHub l'ultima versione. Errori di rete -> eccezione OSError."""
    try:
        dati = json.loads(_scarica(API_ULTIMA, timeout, 2 * 1024 * 1024))
    except ValueError as exc:
        raise OSError("Risposta di GitHub non leggibile.") from exc
    return leggi_release(dati, versione_attuale)


def impronta_dal_file(testo: str) -> str:
    """Accetta sia «abc123…» sia il formato di sha256sum «abc123…  nome.exe»."""
    trovata = re.search(r"\b[0-9a-fA-F]{64}\b", testo or "")
    if not trovata:
        raise AggiornamentoNonValido("Il file dell'impronta SHA-256 non è valido.")
    return trovata.group(0).lower()


def scarica_e_verifica(info: dict, cartella: Path | None = None, timeout: float = 60.0) -> Path:
    if not info.get("installatore") or not info.get("impronta"):
        raise AggiornamentoNonValido("Questa versione va scaricata a mano dalla pagina della Release.")
    attesa = impronta_dal_file(_scarica(info["impronta"], timeout, 4096).decode("utf-8", "replace"))
    dati = _scarica(info["installatore"], timeout, LIMITE_SCARICAMENTO)
    if hashlib.sha256(dati).hexdigest() != attesa:
        raise AggiornamentoNonValido("L'installatore scaricato non corrisponde all'impronta: non verrà eseguito.")
    cartella = Path(cartella or tempfile.mkdtemp(prefix="deal-combined-"))
    percorso = cartella / f"Installa-DealCombined-{re.sub(r'[^0-9.]', '', info['versione']) or 'nuova'}.exe"
    percorso.write_bytes(dati)
    return percorso


def avvia_installatore(percorso: Path) -> None:
    """Lancia l'installatore in modalità silenziosa, staccato dal programma
    (che subito dopo si chiude per lasciare sostituire l'eseguibile)."""
    if sys.platform != "win32":
        raise OSError("L'aggiornamento automatico è disponibile solo su Windows.")
    flag = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    subprocess.Popen([str(percorso), *PARAMETRI_SILENZIOSI], creationflags=flag, close_fds=True)  # noqa: S603

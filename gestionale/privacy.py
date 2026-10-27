"""Privacy: PIN all'apertura e stato della cifratura del disco.

Il PIN protegge lo schermo (chi trova il PC acceso o aperto non entra nel
gestionale), non i file: per proteggere i dati se il portatile viene perso
o rubato serve la cifratura del disco (BitLocker su Windows), di cui qui si
controlla lo stato.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path

TENTATIVI_MASSIMI = 5
_CIFRATURA_VALIDA_PER = 600  # secondi: PowerShell è lento, lo stato cambia di rado
_cifratura_letta: dict[str, tuple[float, str]] = {}
ATTESA_SECONDI = 60
_ALFABETO_RECUPERO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # niente I, O, 0, 1: si leggono male


def hash_segreto(segreto: str) -> str:
    sale = os.urandom(16)
    h = hashlib.scrypt(segreto.encode("utf-8"), salt=sale, n=2 ** 14, r=8, p=1, dklen=32)
    return f"scrypt${sale.hex()}${h.hex()}"


def verifica_segreto(segreto: str, salvato: str | None) -> bool:
    if not salvato:
        return False
    try:
        schema, sale, atteso = salvato.split("$")
    except ValueError:
        return False
    if schema != "scrypt":
        return False
    h = hashlib.scrypt(segreto.encode("utf-8"), salt=bytes.fromhex(sale), n=2 ** 14, r=8, p=1, dklen=32)
    return hmac.compare_digest(h.hex(), atteso)


def pin_valido(pin: str) -> str | None:
    """Messaggio d'errore se il PIN non va bene, altrimenti None."""
    if not pin.isdigit() or not 4 <= len(pin) <= 12:
        return "Il PIN deve essere fatto solo di cifre, da 4 a 12."
    if len(set(pin)) == 1 or pin in "0123456789012" or pin in "9876543210987":
        return "Il PIN è troppo facile da indovinare (cifre tutte uguali o in sequenza)."
    return None


def nuovo_codice_recupero() -> str:
    grezzo = "".join(secrets.choice(_ALFABETO_RECUPERO) for _ in range(12))
    return "-".join(grezzo[i:i + 4] for i in range(0, 12, 4))


def normalizza_codice(codice: str) -> str:
    pulito = "".join(c for c in codice.upper() if c.isalnum())
    return "-".join(pulito[i:i + 4] for i in range(0, len(pulito), 4))


# ----------------------------------------------------------------------
# Cifratura del disco (BitLocker)
# ----------------------------------------------------------------------
# Valori della proprietà di Windows System.Volume.BitLockerProtection.
_STATI_BITLOCKER = {
    1: "attiva", 6: "attiva", 3: "in_corso",
    2: "non_attiva", 4: "non_attiva", 5: "sospesa", 8: "non_attiva",
}


def stato_cifratura(percorso: str | Path) -> str:
    """'attiva', 'in_corso', 'sospesa', 'non_attiva' oppure 'sconosciuta'.

    Su Windows legge lo stato di BitLocker dell'unità dove stanno i dati con
    una proprietà della shell che non richiede permessi da amministratore.
    """
    if sys.platform != "win32":
        return "sconosciuta"
    unita = Path(percorso).resolve().drive or "C:"
    letta = _cifratura_letta.get(unita)
    if letta and time.monotonic() - letta[0] < _CIFRATURA_VALIDA_PER:
        return letta[1]
    stato = _leggi_bitlocker(unita)
    _cifratura_letta[unita] = (time.monotonic(), stato)
    return stato


def _leggi_bitlocker(unita: str) -> str:
    comando = (
        "(New-Object -ComObject Shell.Application).NameSpace('" + unita + "\\')"
        ".Self.ExtendedProperty('System.Volume.BitLockerProtection')"
    )
    try:
        risultato = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", comando],
            capture_output=True, text=True, timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return _STATI_BITLOCKER.get(int(risultato.stdout.strip()), "sconosciuta")
    except (OSError, ValueError, subprocess.SubprocessError):
        return "sconosciuta"

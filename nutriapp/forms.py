"""Piccoli aiuti per leggere i campi dei form senza ripetere try/except.

Tutti i convertitori accettano l'input «sporco» che arriva da un browser
(stringa vuota, virgola decimale all'italiana, spazi) e restituiscono ``None``
quando il campo è vuoto o illeggibile, invece di sollevare eccezioni.
"""
from __future__ import annotations

from datetime import date, datetime


def testo(valore: str | None, massimo: int | None = None) -> str | None:
    if valore is None:
        return None
    pulito = valore.strip()
    if not pulito:
        return None
    return pulito[:massimo] if massimo else pulito


def numero(valore: str | None) -> float | None:
    if valore is None:
        return None
    pulito = valore.strip().replace(",", ".")
    if not pulito:
        return None
    try:
        return float(pulito)
    except ValueError:
        return None


def intero(valore: str | None) -> int | None:
    n = numero(valore)
    return int(round(n)) if n is not None else None


def data(valore: str | None) -> date | None:
    pulito = testo(valore)
    if not pulito:
        return None
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(pulito, formato).date()
        except ValueError:
            continue
    return None


def data_ora(valore: str | None) -> datetime | None:
    pulito = testo(valore)
    if not pulito:
        return None
    for formato in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(pulito, formato)
        except ValueError:
            continue
    giorno = data(pulito)
    return datetime.combine(giorno, datetime.min.time()) if giorno else None


def flag(valore: str | None) -> bool:
    return (valore or "").strip().lower() in ("1", "true", "on", "si", "sì", "yes")


def tri_stato(valore: str | None) -> bool | None:
    """Sì / No / non verificato — i flag di dieta ammettono il «non so»."""
    pulito = (valore or "").strip().lower()
    if pulito in ("1", "si", "sì", "true", "y"):
        return True
    if pulito in ("0", "no", "false", "n"):
        return False
    return None

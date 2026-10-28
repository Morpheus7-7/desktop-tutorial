"""Collegamenti con Google senza registrare un'app su Google Cloud.

- Google Drive: i PDF si salvano nella cartella di «Google Drive per desktop»
  sul PC (es. G:\\Il mio Drive); è l'app di Google a caricarli online.
- Google Calendar: link che aprono Calendar con l'evento già compilato
  (basta premere Salva) ed esportazione .ics da importare in blocco.
- Gmail: si usa l'invio SMTP già presente, con una «password per le app».
"""
from __future__ import annotations

import os
import re
import string
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

SOTTOCARTELLA_DRIVE = "Deal Combined"
NOMI_DRIVE = ("Il mio Drive", "My Drive", "Mein Ablage", "Mi unidad", "Mon Drive")

GMAIL_SMTP = {"smtp_host": "smtp.gmail.com", "smtp_port": 587, "smtp_security": "tls"}


def candidati_drive() -> list[Path]:
    """Cartelle di Google Drive per desktop trovate su questo PC."""
    trovati = []
    if sys.platform == "win32":
        for lettera in string.ascii_uppercase[3:]:  # da D: in poi; di solito G:
            for nome in NOMI_DRIVE:
                p = Path(f"{lettera}:\\") / nome
                if p.is_dir():
                    trovati.append(p)
    casa = Path.home()
    for p in (casa / "Google Drive", casa / "Il mio Drive", casa / "My Drive",
              casa / "Google Drive" / "Il mio Drive", casa / "Google Drive" / "My Drive"):
        if p.is_dir() and p not in trovati:
            trovati.append(p)
    return trovati


def _nome_sicuro(testo: str) -> str:
    pulito = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", testo).strip().rstrip(".")
    return re.sub(r"\s+", " ", pulito)[:80] or "Cliente"


def cartella_cliente(cartella_drive: str | Path, ragione_sociale: str) -> Path:
    return Path(cartella_drive) / SOTTOCARTELLA_DRIVE / "Clienti" / _nome_sicuro(ragione_sociale)


def salva_in_drive(cartella_drive: str | Path, ragione_sociale: str, nome_file: str, dati: bytes) -> Path:
    """Scrive il file nella cartella del cliente dentro Google Drive.
    Se esiste già un file con lo stesso nome aggiunge (2), (3)…"""
    if not cartella_drive or not Path(cartella_drive).is_dir():
        raise FileNotFoundError("La cartella di Google Drive non è disponibile su questo PC.")
    destinazione = cartella_cliente(cartella_drive, ragione_sociale)
    destinazione.mkdir(parents=True, exist_ok=True)
    finale = destinazione / nome_file
    radice, est = os.path.splitext(nome_file)
    n = 2
    while finale.exists():
        finale = destinazione / f"{radice} ({n}){est}"
        n += 1
    finale.write_bytes(dati)
    return finale


# ----------------------------------------------------------------------
# Google Calendar
# ----------------------------------------------------------------------
def link_calendar(titolo: str, giorno: date, dettagli: str = "") -> str:
    """Link che apre Google Calendar con un evento di tutto il giorno."""
    fine = giorno + timedelta(days=1)
    parametri = {
        "action": "TEMPLATE",
        "text": titolo,
        "dates": f"{giorno:%Y%m%d}/{fine:%Y%m%d}",
        "details": dettagli,
    }
    return "https://calendar.google.com/calendar/render?" + urlencode(parametri)


def link_calendar_ora(titolo: str, inizio: datetime, dettagli: str = "", minuti: int = 30) -> str:
    """Link che apre Google Calendar con un evento a un'ora precisa (ora
    locale italiana): Calendar ricorda l'evento con le sue notifiche anche
    sul telefono, pure a PC spento."""
    fine = inizio + timedelta(minutes=minuti)
    parametri = {
        "action": "TEMPLATE",
        "text": titolo,
        "dates": f"{inizio:%Y%m%dT%H%M%S}/{fine:%Y%m%dT%H%M%S}",
        "ctz": "Europe/Rome",
        "details": dettagli,
    }
    return "https://calendar.google.com/calendar/render?" + urlencode(parametri)


def _ics_testo(testo: str) -> str:
    testo = (testo or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
    return testo.replace("\r\n", "\\n").replace("\n", "\\n")


def _piega(riga: str) -> str:
    """Le righe iCalendar non superano 75 byte: le più lunghe vanno a capo."""
    out, corrente = [], ""
    for ch in riga:
        if len((corrente + ch).encode("utf-8")) > 74:
            out.append(corrente)
            corrente = " " + ch
        else:
            corrente += ch
    out.append(corrente)
    return "\r\n".join(out)


def _utc(locale: datetime) -> str:
    """Ora locale del PC -> UTC nel formato iCalendar."""
    return locale.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def calendario_ics(eventi: list[dict], nome: str = "Deal Combined - Follow-up") -> bytes:
    """eventi: dict con uid, titolo, dettagli e giorno (date, tutto il giorno)
    oppure inizio (datetime locale: evento di 30 minuti con avviso)."""
    adesso = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    righe = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Deal Combined//Follow-up//IT",
             "CALSCALE:GREGORIAN", "METHOD:PUBLISH", f"X-WR-CALNAME:{_ics_testo(nome)}"]
    for e in eventi:
        righe += ["BEGIN:VEVENT", f"UID:{e['uid']}@deal-combined", f"DTSTAMP:{adesso}"]
        if e.get("inizio"):
            righe += [f"DTSTART:{_utc(e['inizio'])}", f"DTEND:{_utc(e['inizio'] + timedelta(minutes=30))}"]
        else:
            righe += [f"DTSTART;VALUE=DATE:{e['giorno']:%Y%m%d}",
                      f"DTEND;VALUE=DATE:{e['giorno'] + timedelta(days=1):%Y%m%d}"]
        righe += [f"SUMMARY:{_ics_testo(e['titolo'])}", f"DESCRIPTION:{_ics_testo(e.get('dettagli', ''))}"]
        if e.get("inizio"):
            righe += ["BEGIN:VALARM", "ACTION:DISPLAY", f"DESCRIPTION:{_ics_testo(e['titolo'])}",
                      "TRIGGER:PT0M", "END:VALARM"]
        righe.append("END:VEVENT")
    righe.append("END:VCALENDAR")
    return ("\r\n".join(_piega(r) for r in righe) + "\r\n").encode("utf-8")

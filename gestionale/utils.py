"""Funzioni di supporto condivise dalle route (parsing dei form, paginazione).

Date e importi arrivano dai form come testo: qui vengono interpretati in modo
rigoroso. Le varianti ``leggi_*`` distinguono il campo **vuoto** (ammesso,
restituisce None) dal valore **presente ma non valido** (aggiunge un messaggio
alla lista degli errori), così un refuso non diventa mai in silenzio «nessuna
data» o «nessun importo».
"""
from __future__ import annotations

import calendar
import math
import re
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal

from flask import current_app, request

# Intervallo plausibile per tutte le date del gestionale: protegge da anni
# digitati male (0026, 9999) che falserebbero i calcoli o li farebbero fallire.
DATA_MIN = date(1900, 1, 1)
DATA_MAX = date(2100, 12, 31)

_INT64_MAX = 2**63 - 1


# ----------------------------------------------------------------------
# Importi
# ----------------------------------------------------------------------
def formatta_euro(valore) -> str:
    """Importo in formato italiano: «€ 1.234,56»."""
    if valore is None:
        return "—"
    return ("€ {:,.2f}".format(valore)).replace(",", "X").replace(".", ",").replace("X", ".")


def arrotonda(valore) -> float:
    """Arrotondamento commerciale al centesimo (mezzo centesimo per eccesso)."""
    return float(Decimal(str(valore)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def ripartisci(totale: float, pesi: list[float]) -> list[float]:
    """Divide ``totale`` in parti proporzionali ai pesi, al centesimo.

    Il resto dell'arrotondamento finisce sull'ultima parte, così la somma
    coincide sempre esattamente con il totale.
    """
    if not pesi:
        return []
    somma_pesi = sum(pesi) or len(pesi)
    parti = [arrotonda(totale * p / somma_pesi) for p in pesi[:-1]]
    parti.append(arrotonda(totale - sum(parti)))
    return parti


_NUM_IT_CON_VIRGOLA = re.compile(r"^[+-]?(\d{1,3}(\.\d{3})+|\d+),\d+$")
_NUM_MIGLIAIA = re.compile(r"^[+-]?[1-9]\d{0,2}(\.\d{3})+$")
_NUM_SEMPLICE = re.compile(r"^[+-]?\d+(\.\d+)?$")


def parse_float(value) -> float | None:
    """Numero scritto all'italiana; None se vuoto o non interpretabile.

    Accetta «1.234,56», «1234,56», «1.234» (migliaia), «1.000.000»,
    «€ 1.200» e il formato con il punto decimale «1234.56» (usato dal
    browser e dai valori già salvati). Rifiuta formati ambigui o misti
    («1,234.56», «1.234,5.6»), notazioni esponenziali, NaN e infinito.
    """
    if value is None:
        return None
    testo = str(value).strip().replace("€", "").replace(" ", "").replace(" ", "")
    if not testo:
        return None
    if "," in testo:
        if not _NUM_IT_CON_VIRGOLA.match(testo):
            return None
        testo = testo.replace(".", "").replace(",", ".")
    elif _NUM_MIGLIAIA.match(testo):
        testo = testo.replace(".", "")
    elif not _NUM_SEMPLICE.match(testo):
        return None
    try:
        numero = float(testo)
    except ValueError:  # pragma: no cover - le regex escludono i casi non numerici
        return None
    return numero if math.isfinite(numero) else None


def leggi_importo(form, nome: str, etichetta: str, errori: list[str],
                  minimo: float | None = None, massimo: float | None = None,
                  obbligatorio: bool = False) -> float | None:
    """Importo da un campo del form con validazione (vedi docstring del modulo)."""
    grezzo = (form.get(nome) or "").strip()
    if not grezzo:
        if obbligatorio:
            errori.append(f"{etichetta}: campo obbligatorio.")
        return None
    valore = parse_float(grezzo)
    if valore is None:
        errori.append(f"{etichetta}: importo non valido (es. 1.234,56).")
        return None
    if minimo is not None and valore < minimo:
        errori.append(f"{etichetta}: non può essere inferiore a {formatta_numero(minimo)}.")
        return None
    if massimo is not None and valore > massimo:
        errori.append(f"{etichetta}: non può superare {formatta_numero(massimo)}.")
        return None
    return valore


def formatta_numero(valore) -> str:
    """Numero in formato italiano senza simbolo (per i messaggi)."""
    if float(valore).is_integer():
        return f"{int(valore):,}".replace(",", ".")
    return f"{valore:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ----------------------------------------------------------------------
# Date
# ----------------------------------------------------------------------
def _interpreta_data(value) -> date | None:
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value.strip(), formato).date()
        except (ValueError, AttributeError):
            continue
    return None


def parse_date(value) -> date | None:
    """Data aaaa-mm-gg o gg/mm/aaaa nell'intervallo 1900–2100; altrimenti None."""
    if not value:
        return None
    giorno = _interpreta_data(value)
    if giorno is None or not DATA_MIN <= giorno <= DATA_MAX:
        return None
    return giorno


def leggi_data(form, nome: str, etichetta: str, errori: list[str], *,
               obbligatoria: bool = False, minimo: date | None = None,
               massimo: date | None = None, msg_minimo: str | None = None,
               msg_massimo: str | None = None) -> date | None:
    """Data da un campo del form con validazione.

    Campo vuoto → None (o errore se ``obbligatoria``). Valore non interpretabile
    o fuori dall'intervallo 1900–2100 → errore. ``minimo``/``massimo`` aggiungono
    vincoli specifici (es. «non può essere futura»).
    """
    grezzo = (form.get(nome) or "").strip()
    if not grezzo:
        if obbligatoria:
            errori.append(f"{etichetta}: campo obbligatorio.")
        return None
    giorno = _interpreta_data(grezzo)
    if giorno is None:
        errori.append(f"{etichetta}: data non valida.")
        return None
    if not DATA_MIN <= giorno <= DATA_MAX:
        errori.append(f"{etichetta}: data fuori dall'intervallo ammesso (1900–2100).")
        return None
    if minimo is not None and giorno < minimo:
        errori.append(msg_minimo or f"{etichetta}: non può essere anteriore al {minimo:%d/%m/%Y}.")
        return None
    if massimo is not None and giorno > massimo:
        errori.append(msg_massimo or f"{etichetta}: non può essere successiva al {massimo:%d/%m/%Y}.")
        return None
    return giorno


def periodo_da_richiesta(default_dal: date, default_al: date,
                         nome_dal: str = "dal", nome_al: str = "al") -> tuple[date, date]:
    """Periodo dal/al dai parametri della richiesta: valori non validi → default,
    estremi invertiti → scambiati."""
    dal = parse_date(request.args.get(nome_dal)) or default_dal
    al = parse_date(request.args.get(nome_al)) or default_al
    if al < dal:
        dal, al = al, dal
    return dal, al


def fine_giornata(giorno: date) -> datetime:
    """Ultimo istante del giorno (per filtrare colonne datetime con un «al» incluso)."""
    return datetime.combine(giorno, datetime.max.time())


def add_months(giorno: date, mesi: int) -> date:
    """Somma (o sottrae) mesi a una data, rispettando la fine del mese.

    Solleva ``ValueError`` se il risultato esce dal calendario (anno < 1 o > 9999).
    """
    indice = giorno.month - 1 + mesi
    anno = giorno.year + indice // 12
    mese = indice % 12 + 1
    return date(anno, mese, min(giorno.day, calendar.monthrange(anno, mese)[1]))


def add_months_sicuro(giorno: date | None, mesi: int) -> date | None:
    """Come add_months ma restituisce None invece di sollevare eccezioni."""
    if giorno is None:
        return None
    try:
        return add_months(giorno, mesi)
    except (ValueError, OverflowError):
        return None


def inizio_mese(giorno: date) -> date:
    return giorno.replace(day=1)


def fine_mese(giorno: date) -> date:
    prossimo = (giorno.replace(day=28) + timedelta(days=4)).replace(day=1)
    return prossimo - timedelta(days=1)


# ----------------------------------------------------------------------
# Interi, testi e paginazione
# ----------------------------------------------------------------------
def parse_int(value, minimo: int | None = None, massimo: int | None = None) -> int | None:
    """Intero da testo; None se vuoto, non valido o fuori dai limiti (e da int64)."""
    try:
        numero = int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None
    if numero is None or abs(numero) > _INT64_MAX:
        return None
    if (minimo is not None and numero < minimo) or (massimo is not None and numero > massimo):
        return None
    return numero


def clean(form, nome: str, upper: bool = False) -> str | None:
    """Valore testuale ripulito di un campo del form (None se vuoto)."""
    valore = (form.get(nome) or "").strip()
    if upper:
        valore = valore.upper()
    return valore or None


def paginate(query):
    """Pagina la query secondo il parametro ``page`` della richiesta."""
    pagina = parse_int(request.args.get("page"), minimo=1, massimo=1_000_000) or 1
    return query.paginate(
        page=pagina,
        per_page=current_app.config.get("ELEMENTI_PER_PAGINA", 25),
        error_out=False,
    )


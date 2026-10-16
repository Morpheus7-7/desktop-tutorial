"""Funzioni di supporto condivise dalle route (parsing dei form, paginazione)."""
from __future__ import annotations

from datetime import date, datetime

from flask import current_app, request


def formatta_euro(valore) -> str:
    """Importo in formato italiano: «€ 1.234,56»."""
    if valore is None:
        return "—"
    return ("€ {:,.2f}".format(valore)).replace(",", "X").replace(".", ",").replace("X", ".")


def parse_date(value) -> date | None:
    """Data da un campo ``<input type="date">`` (aaaa-mm-gg) o in formato gg/mm/aaaa."""
    if not value:
        return None
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value.strip(), formato).date()
        except (ValueError, AttributeError):
            continue
    return None


def parse_float(value) -> float | None:
    """Numero da un campo di testo: accetta «1.234,56», «1234,56» e «1234.56»."""
    if value in (None, ""):
        return None
    testo = str(value).strip().replace("€", "").replace(" ", "")
    if "," in testo:
        testo = testo.replace(".", "").replace(",", ".")
    try:
        return float(testo)
    except ValueError:
        return None


def parse_int(value) -> int | None:
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def clean(form, nome: str, upper: bool = False) -> str | None:
    """Valore testuale ripulito di un campo del form (None se vuoto)."""
    valore = (form.get(nome) or "").strip()
    if upper:
        valore = valore.upper()
    return valore or None


def paginate(query):
    """Pagina la query secondo il parametro ``page`` della richiesta."""
    pagina = parse_int(request.args.get("page")) or 1
    return query.paginate(
        page=max(1, pagina),
        per_page=current_app.config.get("ELEMENTI_PER_PAGINA", 25),
        error_out=False,
    )

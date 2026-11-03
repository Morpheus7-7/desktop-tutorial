"""Esportazione CSV compatibile con Excel in italiano.

Separatore «;», decimali con la virgola, date gg/mm/aaaa e BOM UTF-8 così
Excel apre il file con accenti e colonne corretti. I testi che iniziano con
caratteri di formula vengono neutralizzati (CSV injection).
"""
from __future__ import annotations

import csv
import io
from datetime import date, datetime
from typing import Iterable, Sequence

from flask import Response

_PREFISSI_FORMULA = ("=", "+", "-", "@", "\t", "\r")


def _formatta(valore) -> str:
    if valore is None:
        return ""
    if isinstance(valore, bool):
        return "Sì" if valore else "No"
    if isinstance(valore, float):
        return f"{valore:.2f}".replace(".", ",")
    if isinstance(valore, int):
        return str(valore)
    if isinstance(valore, datetime):
        return valore.strftime("%d/%m/%Y %H:%M")
    if isinstance(valore, date):
        return valore.strftime("%d/%m/%Y")
    testo = str(valore)
    if testo.startswith(_PREFISSI_FORMULA):
        testo = "'" + testo
    return testo


def csv_text(intestazioni: Sequence[str], righe: Iterable[Sequence]) -> str:
    buffer = io.StringIO()
    buffer.write("﻿")
    writer = csv.writer(buffer, delimiter=";", quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    writer.writerow(intestazioni)
    for riga in righe:
        writer.writerow([_formatta(v) for v in riga])
    return buffer.getvalue()


def csv_response(nome_file: str, intestazioni: Sequence[str], righe: Iterable[Sequence]) -> Response:
    if not nome_file.endswith(".csv"):
        nome_file += ".csv"
    nome_file = f"{nome_file[:-4]}_{date.today().strftime('%Y%m%d')}.csv"
    return Response(
        csv_text(intestazioni, righe),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{nome_file}"'},
    )

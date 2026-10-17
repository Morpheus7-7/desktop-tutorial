"""Validazione dei dati anagrafici italiani (codice fiscale, partita IVA…)."""
from __future__ import annotations

import re
from datetime import date

_PATTERN_CF = re.compile(
    r"^[A-Z]{6}[0-9LMNPQRSTUV]{2}[ABCDEHLMPRST][0-9LMNPQRSTUV]{2}[A-Z][0-9LMNPQRSTUV]{3}[A-Z]$"
)
_DISPARI = {
    "0": 1, "1": 0, "2": 5, "3": 7, "4": 9, "5": 13, "6": 15, "7": 17, "8": 19, "9": 21,
    "A": 1, "B": 0, "C": 5, "D": 7, "E": 9, "F": 13, "G": 15, "H": 17, "I": 19, "J": 21,
    "K": 2, "L": 4, "M": 18, "N": 20, "O": 11, "P": 3, "Q": 6, "R": 8, "S": 12, "T": 14,
    "U": 16, "V": 10, "W": 22, "X": 25, "Y": 24, "Z": 23,
}
# Omocodia: le cifre possono essere sostituite da queste lettere.
_OMOCODIA = {c: str(i) for i, c in enumerate("LMNPQRSTUV")}
_MESI_CF = "ABCDEHLMPRST"
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def carattere_controllo_cf(primi15: str) -> str:
    totale = 0
    for i, c in enumerate(primi15):
        if i % 2 == 0:  # posizioni dispari (1ª, 3ª, …)
            totale += _DISPARI[c]
        else:
            totale += int(c) if c.isdigit() else ord(c) - ord("A")
    return chr(ord("A") + totale % 26)


def valida_partita_iva(piva: str | None) -> str | None:
    """Messaggio d'errore se la partita IVA non è valida, altrimenti None."""
    if not piva:
        return None
    if not re.fullmatch(r"\d{11}", piva):
        return "La partita IVA deve essere composta da 11 cifre."
    totale = 0
    for i, c in enumerate(piva[:10]):
        n = int(c)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        totale += n
    if (10 - totale % 10) % 10 != int(piva[10]):
        return "Partita IVA non valida: la cifra di controllo non corrisponde."
    return None


def valida_codice_fiscale(cf: str | None) -> str | None:
    """Messaggio d'errore se il codice fiscale non è valido, altrimenti None.

    Accetta sia il codice delle persone fisiche (16 caratteri, anche omocodico)
    sia quello numerico di società ed enti (11 cifre).
    """
    if not cf:
        return None
    if re.fullmatch(r"\d{11}", cf):
        errore = valida_partita_iva(cf)
        return errore.replace("Partita IVA", "Codice fiscale numerico") if errore else None
    if len(cf) != 16:
        return "Il codice fiscale deve avere 16 caratteri (o 11 cifre per società ed enti)."
    if not _PATTERN_CF.match(cf):
        return "Il formato del codice fiscale non è valido."
    if carattere_controllo_cf(cf[:15]) != cf[15]:
        return "Codice fiscale non valido: il carattere di controllo non corrisponde."
    return None


def data_nascita_da_cf(cf: str | None) -> date | None:
    """Ricava la data di nascita da un codice fiscale di persona fisica valido."""
    if not cf or len(cf) != 16 or valida_codice_fiscale(cf):
        return None
    cifre = lambda s: "".join(_OMOCODIA.get(c, c) for c in s)  # noqa: E731
    try:
        anno2 = int(cifre(cf[6:8]))
        mese = _MESI_CF.index(cf[8]) + 1
        giorno = int(cifre(cf[9:11]))
    except ValueError:
        return None
    if giorno > 40:
        giorno -= 40
    oggi = date.today()
    for secolo in (2000, 1900):
        try:
            candidata = date(secolo + anno2, mese, giorno)
        except ValueError:
            return None
        if candidata <= oggi:
            return candidata
    return None


def valida_cap(cap: str | None) -> str | None:
    if cap and not re.fullmatch(r"\d{5}", cap):
        return "Il CAP deve essere composto da 5 cifre."
    return None


def valida_provincia(provincia: str | None) -> str | None:
    if provincia and not re.fullmatch(r"[A-Z]{2}", provincia):
        return "La provincia va indicata con la sigla di 2 lettere (es. MI)."
    return None


def valida_email(email: str | None, campo: str = "email") -> str | None:
    if email and not _EMAIL.match(email):
        return f"L'indirizzo {campo} non è valido."
    return None

"""Comandi di amministrazione da riga di comando.

Servono soprattutto a recuperare l'accesso se l'unico amministratore ha
dimenticato la password:

    flask --app app reimposta-password NOMEUTENTE        (sviluppo)
    GestionaleAssicurativo.exe --reimposta-password NOMEUTENTE   (eseguibile)
"""
from __future__ import annotations

import getpass

import click
from flask import Flask

from .models import db
from .security import audit, invalida_sessioni, password_problem, trova_utente


def reimposta_password(username: str, password: str) -> str:
    """Reimposta la password (e sblocca/riattiva l'utente). Restituisce un esito leggibile.

    Va chiamata dentro un application context.
    """
    user = trova_utente(username)
    if user is None:
        raise ValueError(f"Utente «{username}» inesistente.")
    errore = password_problem(password)
    if errore:
        raise ValueError(errore)
    user.set_password(password)
    user.attivo = True
    user.tentativi_falliti = 0
    user.bloccato_fino = None
    invalida_sessioni(user)
    audit("modifica", "utente", user.id, "Password reimpostata da riga di comando", user=user)
    db.session.commit()
    return f"Password di «{user.username}» ({user.ruolo_label}) reimpostata."


def chiedi_e_reimposta(username: str) -> int:
    """Versione interattiva (chiede la password due volte). Restituisce il codice di uscita."""
    password = getpass.getpass("Nuova password: ")
    if password != getpass.getpass("Ripeti la password: "):
        print("Le due password non coincidono.")
        return 1
    try:
        print(reimposta_password(username, password))
    except ValueError as exc:
        print(exc)
        return 1
    return 0


def register_cli(app: Flask) -> None:
    @app.cli.command("reimposta-password")
    @click.argument("username")
    def _reimposta_password(username):
        """Reimposta la password di un utente (anche se bloccato o disattivato)."""
        raise SystemExit(chiedi_e_reimposta(username))

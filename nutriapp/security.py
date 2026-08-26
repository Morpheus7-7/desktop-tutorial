"""Sessione, ruoli e protezione delle viste.

Due ruoli soltanto: **nutrizionista** (vede tutto) e **cliente** (vede solo la
propria scheda). I decoratori qui sotto sono l'unico punto in cui si decide chi
può entrare dove, così nessuna vista può dimenticarsene per distrazione.
"""
from __future__ import annotations

import os
import secrets
import string
from functools import wraps

from flask import flash, g, redirect, request, session, url_for

from .models import User, db

CHIAVE_SESSIONE = "utente_id"
EMAIL_STUDIO_DEFAULT = "nutrizionista@nutristudio.it"
PASSWORD_STUDIO_DEFAULT = "nutristudio"
_ALFABETO_PASSWORD = string.ascii_letters.replace("l", "").replace("I", "") + "23456789"


def password_provvisoria(lunghezza: int = 10) -> str:
    """Password leggibile da dettare al telefono: niente caratteri ambigui."""
    return "".join(secrets.choice(_ALFABETO_PASSWORD) for _ in range(lunghezza))


def email_studio_iniziale() -> str:
    return os.environ.get("NUTRI_ADMIN_EMAIL", EMAIL_STUDIO_DEFAULT).strip().lower()


def password_studio_iniziale() -> str:
    return os.environ.get("NUTRI_ADMIN_PASSWORD", PASSWORD_STUDIO_DEFAULT)


def credenziali_di_fabbrica() -> tuple[str, str] | None:
    """Le credenziali dello studio da mostrare al primo avvio, se ancora valide.

    Nessuno si registra da solo in NutriStudio: l'accesso dello studio nasce
    con l'applicazione e quelli dei clienti li apre la nutrizionista. Al primo
    avvio, però, chi lancia il programma non ha modo di sapere che cosa
    scrivere — quindi glielo diciamo, ma **solo** finché la password è ancora
    quella di fabbrica, che è già pubblicata nel README. Appena viene cambiata
    l'indicazione sparisce da sola.
    """
    utenti = User.query.filter_by(ruolo="nutrizionista").all()
    if len(utenti) != 1:
        return None
    utente = utenti[0]
    if not utente.deve_cambiare_password:
        return None
    password = password_studio_iniziale()
    if not utente.check_password(password):
        return None
    return utente.email, password


def accedi(utente: User) -> None:
    session.clear()
    session[CHIAVE_SESSIONE] = utente.id
    session.permanent = True


def esci() -> None:
    session.clear()


def utente_corrente() -> User | None:
    if "utente" not in g:
        utente_id = session.get(CHIAVE_SESSIONE)
        g.utente = db.session.get(User, utente_id) if utente_id else None
        if g.utente is not None and not g.utente.attivo:
            g.utente = None
    return g.utente


def assistito_corrente():
    """L'assistito collegato all'utente loggato (solo per il ruolo cliente)."""
    utente = utente_corrente()
    return utente.assistito if utente and utente.is_cliente else None


def _vai_al_login():
    return redirect(url_for("auth.login", next=request.full_path))


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        utente = utente_corrente()
        if utente is None:
            return _vai_al_login()
        if utente.deve_cambiare_password and request.endpoint not in (
            "auth.cambia_password",
            "auth.logout",
        ):
            return redirect(url_for("auth.cambia_password"))
        return view(*args, **kwargs)

    return wrapper


def nutrizionista_required(view):
    @wraps(view)
    @login_required
    def wrapper(*args, **kwargs):
        if not utente_corrente().is_nutrizionista:
            flash("Quest'area è riservata allo studio.", "warning")
            return redirect(url_for("portal.home"))
        return view(*args, **kwargs)

    return wrapper


def cliente_required(view):
    """Area riservata del cliente. La nutrizionista non ci entra per sbaglio."""

    @wraps(view)
    @login_required
    def wrapper(*args, **kwargs):
        utente = utente_corrente()
        if not utente.is_cliente or utente.assistito is None:
            flash("Questa è l'area riservata degli assistiti.", "info")
            return redirect(url_for("main.dashboard"))
        return view(*args, **kwargs)

    return wrapper

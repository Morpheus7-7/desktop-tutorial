"""Thread in background che genera le notifiche e invia il digest via email.

Non parte durante i test: viene avviato esplicitamente dagli entry point
(`nutri_app.py`) con ``start_scheduler(app)``.
"""
from __future__ import annotations

import threading
import time

from flask import Flask

_thread: threading.Thread | None = None
_lock = threading.Lock()
_MIN_INTERVALLO_S = 60


def _tick(app: Flask) -> None:
    from .mailer import invia_notifiche_pendenti
    from .models import Settings
    from .notifications import genera_notifiche

    with app.app_context():
        try:
            genera_notifiche()
            inviate = invia_notifiche_pendenti(Settings.get())
            if inviate:
                app.logger.info("Scheduler: inviate %d notifiche via email.", inviate)
        except Exception:  # noqa: BLE001 — un errore transitorio non deve uccidere il thread
            app.logger.exception("Scheduler: errore durante il controllo periodico.")


def _intervallo_secondi(app: Flask) -> int:
    from .models import Settings

    with app.app_context():
        try:
            minuti = Settings.get().intervallo_minuti or 60
        except Exception:  # noqa: BLE001
            minuti = 60
    return max(_MIN_INTERVALLO_S, int(minuti) * 60)


def _run(app: Flask) -> None:
    time.sleep(5)  # lascia completare l'avvio del server
    while True:
        _tick(app)
        time.sleep(_intervallo_secondi(app))


def start_scheduler(app: Flask) -> bool:
    """Avvia lo scheduler una sola volta. True se è stato avviato adesso."""
    global _thread
    with _lock:
        if _thread is not None and _thread.is_alive():
            return False
        _thread = threading.Thread(target=_run, args=(app,), name="nutriapp-scheduler", daemon=True)
        _thread.start()
        app.logger.info("Scheduler notifiche avviato.")
        return True

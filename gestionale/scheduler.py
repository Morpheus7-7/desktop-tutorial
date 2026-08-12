"""Scheduler in background per l'invio automatico delle notifiche email.

Un singolo thread demone controlla periodicamente le scadenze: genera le
notifiche mancanti e, se le email sono attive, invia il digest delle notifiche
non ancora spedite. La cadenza è configurabile dalla pagina «Impostazioni»
(``Settings.intervallo_minuti``).

Lo scheduler NON parte in fase di test: viene avviato esplicitamente dagli
entry point (``app.py`` e ``run_desktop.py``) chiamando ``start_scheduler``.
"""
from __future__ import annotations

import threading
import time

from flask import Flask

_thread: threading.Thread | None = None
_lock = threading.Lock()
_MIN_INTERVALLO_S = 60  # limite di sicurezza: non più spesso di una volta al minuto


def _tick(app: Flask) -> None:
    """Un ciclo di controllo: genera notifiche e invia il digest se attivo."""
    from .mailer import send_pending_notifications
    from .notifications import generate_notifications
    from .models import Settings

    with app.app_context():
        try:
            generate_notifications()
            settings = Settings.get()
            inviate = send_pending_notifications(settings)
            if inviate:
                app.logger.info("Scheduler: inviate %d notifiche via email.", inviate)
        except Exception:  # noqa: BLE001 — non far morire il thread per un errore transitorio
            app.logger.exception("Scheduler: errore durante il controllo periodico.")


def _intervallo_secondi(app: Flask) -> int:
    from .models import Settings

    with app.app_context():
        try:
            minuti = Settings.get().intervallo_minuti or 30
        except Exception:  # noqa: BLE001
            minuti = 30
    return max(_MIN_INTERVALLO_S, int(minuti) * 60)


def _run(app: Flask) -> None:
    # Piccola attesa iniziale: lascia completare l'avvio del server.
    time.sleep(5)
    while True:
        _tick(app)
        time.sleep(_intervallo_secondi(app))


def start_scheduler(app: Flask) -> bool:
    """Avvia lo scheduler una sola volta. Ritorna True se è stato avviato ora."""
    global _thread
    with _lock:
        if _thread is not None and _thread.is_alive():
            return False
        _thread = threading.Thread(
            target=_run, args=(app,), name="gestionale-scheduler", daemon=True
        )
        _thread.start()
        app.logger.info("Scheduler notifiche avviato.")
        return True

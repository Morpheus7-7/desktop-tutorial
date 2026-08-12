"""Avvio «desktop» del Gestionale Assicurativo.

Fa partire il server web locale, avvia lo scheduler delle notifiche e apre
automaticamente il browser sull'applicazione. È l'entry point usato per
l'eseguibile impacchettato con PyInstaller (vedi ``gestionale.spec``), ma si
può lanciare anche direttamente con:

    python run_desktop.py

Il database e i file caricati vengono salvati accanto all'eseguibile, nella
cartella ``dati_gestionale``, così i dati restano tra un avvio e l'altro.
"""
from __future__ import annotations

import os
import socket
import sys
import threading
import webbrowser


def _base_dir() -> str:
    """Cartella dei dati: accanto all'eseguibile (o al sorgente in sviluppo)."""
    if getattr(sys, "frozen", False):  # eseguibile PyInstaller
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _find_free_port(preferred: int = 5000) -> int:
    for port in (preferred, 0):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", port))
                return s.getsockname()[1]
        except OSError:
            continue
    return preferred


def main() -> None:
    data_dir = os.path.join(_base_dir(), "dati_gestionale")
    os.makedirs(data_dir, exist_ok=True)
    # Persistiamo database e upload accanto all'eseguibile.
    os.environ.setdefault(
        "DATABASE_URL", "sqlite:///" + os.path.join(data_dir, "gestionale.db")
    )
    os.environ.setdefault("UPLOAD_FOLDER", os.path.join(data_dir, "uploads"))

    from gestionale import create_app
    from gestionale.scheduler import start_scheduler

    app = create_app()

    port = _find_free_port(int(os.environ.get("PORT", "5000")))
    url = f"http://127.0.0.1:{port}"
    # I link nelle email puntano all'app in esecuzione localmente.
    os.environ.setdefault("APP_BASE_URL", url)

    start_scheduler(app)

    print("=" * 60)
    print("  Gestionale Assicurativo è in esecuzione.")
    print(f"  Apri il browser su:  {url}")
    print(f"  Dati salvati in:     {data_dir}")
    print("  Chiudi questa finestra per fermare il programma.")
    print("=" * 60)

    # Apriamo il browser poco dopo l'avvio del server.
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    try:
        from waitress import serve  # server WSGI di produzione, puro Python

        serve(app, host="127.0.0.1", port=port, threads=8)
    except ImportError:
        # Fallback: server integrato di Flask (nessuna dipendenza extra).
        app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()

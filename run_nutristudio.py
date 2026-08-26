"""Avvio «desktop» di NutriStudio.

Fa partire il server locale, avvia lo scheduler delle notifiche e apre il
browser sull'applicazione. È l'entry point dell'eseguibile impacchettato con
PyInstaller (vedi ``nutristudio.spec``), ma si lancia anche direttamente:

    python run_nutristudio.py

Il database viene salvato accanto all'eseguibile, nella cartella
``dati_nutristudio``, così i dati restano tra un avvio e l'altro.

Da non confondere con ``run_desktop.py``, che avvia l'**altra** applicazione di
questo repository (il gestionale assicurativo).
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


def _find_free_port(preferred: int = 5001) -> int:
    for port in (preferred, 0):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("127.0.0.1", port))
                return s.getsockname()[1]
        except OSError:
            continue
    return preferred


def _credenziali_iniziali() -> tuple[str, str] | None:
    """Le credenziali dello studio, da mostrare finché sono quelle di default."""
    from nutriapp.models import User

    utente = User.query.filter_by(ruolo="nutrizionista").order_by(User.id).first()
    if utente is None or not utente.deve_cambiare_password:
        return None
    return utente.email, os.environ.get("NUTRI_ADMIN_PASSWORD", "nutristudio")


def main() -> None:
    data_dir = os.path.join(_base_dir(), "dati_nutristudio")
    os.makedirs(data_dir, exist_ok=True)
    os.environ.setdefault(
        "DATABASE_URL", "sqlite:///" + os.path.join(data_dir, "nutristudio.db")
    )

    from nutriapp import create_app
    from nutriapp.scheduler import start_scheduler

    app = create_app()

    port = _find_free_port(int(os.environ.get("PORT", "5001")))
    url = f"http://127.0.0.1:{port}"
    # I link dentro le email ai clienti puntano all'app in esecuzione.
    os.environ.setdefault("APP_BASE_URL", url)

    with app.app_context():
        credenziali = _credenziali_iniziali()

    start_scheduler(app)

    print("=" * 62)
    print("  NutriStudio è in esecuzione.")
    print(f"  Apri il browser su:  {url}")
    print(f"  Dati salvati in:     {data_dir}")
    if credenziali:
        email, password = credenziali
        print("-" * 62)
        print("  Primo accesso allo studio:")
        print(f"    email:    {email}")
        print(f"    password: {password}")
        print("  Ti verrà chiesto di cambiarla subito.")
    print("  Chiudi questa finestra per fermare il programma.")
    print("=" * 62)

    threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    try:
        from waitress import serve  # server WSGI di produzione, puro Python

        serve(app, host="127.0.0.1", port=port, threads=8)
    except ImportError:
        # Fallback: server integrato di Flask (nessuna dipendenza extra).
        app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()

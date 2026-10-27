"""Avvio «desktop» di Deal Combined.

È il punto di ingresso del programma installato (vedi ``gestionale.spec`` e
``installer/DealCombined.iss``), ma si può lanciare anche con:

    python run_desktop.py

Cosa fa:
- usa la cartella dati scelta dall'utente (di base Documenti\\Deal Combined) e
  vi sposta i dati delle versioni precedenti, che stavano accanto
  all'eseguibile in «dati_gestionale»;
- fa un backup del database e segna l'archivio come «aperto su questo PC»,
  così se la cartella è condivisa tra due PC l'altro viene avvisato;
- apre l'app in una finestra propria (Edge WebView2 tramite pywebview); se non
  è disponibile la apre nel browser, e il programma si chiude dal pulsante
  «Chiudi Deal Combined».
"""
from __future__ import annotations

import atexit
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path


def _base_dir() -> Path:
    """Cartella del programma: accanto all'eseguibile (o al sorgente)."""
    if getattr(sys, "frozen", False):  # eseguibile PyInstaller
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


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


def _attendi_server(port: int, secondi: float = 15.0) -> None:
    fine = time.time() + secondi
    while time.time() < fine:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return
        except OSError:
            time.sleep(0.1)


def main() -> None:
    from gestionale import desktop

    file_config = desktop.file_configurazione()
    data_dir = desktop.cartella_dati(desktop.leggi_configurazione(file_config))
    data_dir.mkdir(parents=True, exist_ok=True)

    # Senza console (programma installato) i messaggi vanno in un file di log.
    if sys.stdout is None or sys.stderr is None:
        log = open(data_dir / "deal-combined.log", "a", encoding="utf-8", buffering=1)  # noqa: SIM115
        sys.stdout = sys.stdout or log
        sys.stderr = sys.stderr or log

    migrati = desktop.migra_vecchia_cartella(_base_dir() / "dati_gestionale", data_dir)

    os.environ.setdefault("DATABASE_URL", "sqlite:///" + str(data_dir / desktop.NOME_DB))
    os.environ.setdefault("UPLOAD_FOLDER", str(data_dir / desktop.NOME_UPLOADS))

    # Se l'archivio è aperto su un altro PC non lo tocchiamo finché l'utente
    # non decide (pagina di avviso); altrimenti backup e blocco.
    blocco_altrui = desktop.blocco_altrui(data_dir)
    if not blocco_altrui:
        desktop.esegui_backup(data_dir, motivo="avvio")
        desktop.prendi_blocco(data_dir)

    from gestionale import create_app
    from gestionale.scheduler import start_scheduler

    def chiudi() -> None:
        desktop.rilascia_blocco(data_dir)
        os._exit(0)

    app = create_app()
    app.config.update(
        DC_DESKTOP=True,
        DC_CONFIG_FILE=str(file_config),
        DC_BLOCCO_ALTRUI=blocco_altrui,
        DC_SHUTDOWN=chiudi,
    )
    atexit.register(desktop.rilascia_blocco, data_dir)

    def battito() -> None:
        # Tiene «fresco» il blocco: se il programma si chiude male, dopo
        # qualche minuto l'altro PC potrà riaprire l'archivio.
        while True:
            time.sleep(desktop.BATTITO_OGNI)
            if not app.config.get("DC_BLOCCO_ALTRUI"):
                try:
                    desktop.prendi_blocco(data_dir)
                except OSError:
                    pass

    threading.Thread(target=battito, name="blocco", daemon=True).start()

    port = _find_free_port(int(os.environ.get("PORT", "5000")))
    url = f"http://127.0.0.1:{port}"
    os.environ.setdefault("APP_BASE_URL", url)  # link nelle email

    start_scheduler(app)

    if desktop.leggi_configurazione(file_config).get("aggiornamenti_automatici", True):
        from gestionale.routes.settings import controlla_aggiornamenti

        # Dopo qualche secondo, per non rallentare l'apertura.
        threading.Timer(8, controlla_aggiornamenti, args=(app,)).start()

    print("=" * 60)
    print("  Deal Combined è in esecuzione.")
    print(f"  Indirizzo:        {url}")
    print(f"  Dati salvati in:  {data_dir}")
    if migrati:
        print("  (dati della versione precedente copiati qui)")
    print("=" * 60)

    def servi() -> None:
        try:
            from waitress import serve  # server WSGI di produzione, puro Python

            serve(app, host="127.0.0.1", port=port, threads=8)
        except ImportError:
            app.run(host="127.0.0.1", port=port, debug=False, use_reloader=False)

    try:
        import webview  # pywebview: finestra nativa con Edge WebView2
    except ImportError:
        webview = None

    if webview is not None and not os.environ.get("DC_BROWSER"):
        threading.Thread(target=servi, name="server", daemon=True).start()
        _attendi_server(port)
        app.config["DC_FINESTRA"] = True
        try:
            webview.create_window(
                "Deal Combined", url, width=1320, height=860, min_size=(360, 560),
                text_select=True,
            )
            webview.start()
            chiudi()  # finestra chiusa: chiude il programma
            return
        except Exception as exc:  # noqa: BLE001 - nessun motore WebView disponibile
            print(f"Finestra non disponibile ({exc}): apro il browser.")
            app.config["DC_FINESTRA"] = False
            webbrowser.open(url)
            threading.Event().wait()  # il server resta attivo; si chiude dall'app
            return

    # Ripiego: browser predefinito; si chiude dal pulsante «Chiudi Deal Combined».
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    servi()


if __name__ == "__main__":
    main()

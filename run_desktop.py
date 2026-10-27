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
  «Chiudi Deal Combined»;
- su Windows mette un'icona vicino all'orologio: chiudendo la finestra il
  programma resta lì e mostra i promemoria (follow-up di oggi, polizze in
  scadenza) come notifiche di Windows. Con ``--avvio-silenzioso`` (avvio con
  Windows) parte direttamente nella barra, senza finestra.
"""
from __future__ import annotations

import atexit
import os
import socket
import sys
import threading
import time
import secrets
import urllib.request
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


def _altra_copia_attiva(file_istanza: Path) -> bool:
    """Se il programma è già aperto (magari solo nella barra), gli chiede di
    mostrare la finestra e restituisce True."""
    try:
        porta = int(file_istanza.read_text(encoding="utf-8").strip())
        richiesta = urllib.request.Request(
            f"http://127.0.0.1:{porta}/impostazioni/mostra", data=b"", method="POST",
            headers={"X-DC-Azione": "mostra"},
        )
        with urllib.request.urlopen(richiesta, timeout=3) as risposta:  # noqa: S310 - solo localhost
            return risposta.status == 204
    except (OSError, ValueError):
        return False


def main() -> None:
    from gestionale import desktop, promemoria

    silenzioso = promemoria.PARAMETRO_SILENZIOSO in sys.argv[1:]
    file_config = desktop.file_configurazione()
    config = desktop.leggi_configurazione(file_config)
    data_dir = desktop.cartella_dati(config)
    data_dir.mkdir(parents=True, exist_ok=True)

    file_istanza = file_config.parent / "istanza.txt"
    if _altra_copia_attiva(file_istanza):
        return

    # Senza console (programma installato) i messaggi vanno in un file di log.
    if sys.stdout is None or sys.stderr is None:
        log = open(data_dir / "deal-combined.log", "a", encoding="utf-8", buffering=1)  # noqa: SIM115
        sys.stdout = sys.stdout or log
        sys.stderr = sys.stderr or log

    # Chiave segreta propria di questa installazione: firma la sessione (e
    # quindi lo sblocco con il PIN), non deve essere quella pubblica di prova.
    if not config.get("secret_key"):
        config["secret_key"] = secrets.token_hex(32)
        desktop.salva_configurazione(config, file_config)
    os.environ.setdefault("SECRET_KEY", config["secret_key"])

    migrati = desktop.migra_vecchia_cartella(_base_dir() / "dati_gestionale", data_dir)

    os.environ.setdefault("DATABASE_URL", "sqlite:///" + str(data_dir / desktop.NOME_DB))
    os.environ.setdefault("UPLOAD_FOLDER", str(data_dir / desktop.NOME_UPLOADS))

    from gestionale import create_app
    from gestionale.scheduler import start_scheduler

    app = create_app()
    app.config.update(DC_DESKTOP=True, DC_CONFIG_FILE=str(file_config), DC_BLOCCO_ALTRUI=None,
                      DC_HO_BLOCCO=False, DC_IN_PAUSA=True)
    stato = {"backup_fatto": False}

    def entra() -> None:
        """La finestra si apre: l'archivio diventa «aperto su questo PC», a
        meno che non lo sia già su un altro (pagina di avviso)."""
        altrui = desktop.blocco_altrui(data_dir)
        app.config["DC_BLOCCO_ALTRUI"] = altrui
        if not altrui:
            if not stato["backup_fatto"]:
                desktop.esegui_backup(data_dir, motivo="avvio")
                stato["backup_fatto"] = True
            desktop.prendi_blocco(data_dir)
            app.config["DC_HO_BLOCCO"] = True
        app.config["DC_IN_PAUSA"] = False

    def esce() -> None:
        """La finestra va nella barra: l'archivio si libera per l'altro PC."""
        from datetime import datetime

        app.config["DC_IN_PAUSA"] = True
        app.config["DC_NASCOSTA_ALLE"] = datetime.utcnow().timestamp()  # stesso orologio del PIN
        if app.config.get("DC_HO_BLOCCO"):
            desktop.rilascia_blocco(data_dir)
            app.config["DC_HO_BLOCCO"] = False

    def chiudi() -> None:
        esce()
        try:
            file_istanza.unlink(missing_ok=True)
        except OSError:
            pass
        os._exit(0)

    app.config["DC_SHUTDOWN"] = chiudi
    atexit.register(esce)

    def battito() -> None:
        # Tiene «fresco» il blocco: se il programma si chiude male, dopo
        # qualche minuto l'altro PC potrà riaprire l'archivio.
        while True:
            time.sleep(desktop.BATTITO_OGNI)
            if app.config.get("DC_HO_BLOCCO") and not app.config.get("DC_BLOCCO_ALTRUI"):
                try:
                    desktop.prendi_blocco(data_dir)
                except OSError:
                    pass

    threading.Thread(target=battito, name="blocco", daemon=True).start()

    port = _find_free_port(int(os.environ.get("PORT", "5000")))
    url = f"http://127.0.0.1:{port}"
    os.environ.setdefault("APP_BASE_URL", url)  # link nelle email

    start_scheduler(app)

    if config.get("aggiornamenti_automatici", True):
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

    if webview is None or os.environ.get("DC_BROWSER"):
        # Ripiego: browser predefinito; si chiude dal pulsante «Chiudi Deal Combined».
        entra()
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()
        servi()
        return

    threading.Thread(target=servi, name="server", daemon=True).start()
    _attendi_server(port)
    try:
        file_istanza.write_text(str(port), encoding="utf-8")
    except OSError:
        pass
    app.config["DC_FINESTRA"] = True

    finestra = webview.create_window(
        "Deal Combined", url, width=1320, height=860, min_size=(360, 560),
        text_select=True, hidden=silenzioso,
    )
    icona = _avvia_barra(app, finestra, entra, esce, chiudi, url)
    if not silenzioso or icona is None:
        entra()

    try:
        webview.start()
    except Exception as exc:  # noqa: BLE001 - nessun motore WebView disponibile
        print(f"Finestra non disponibile ({exc}): apro il browser.")
        app.config["DC_FINESTRA"] = False
        entra()
        webbrowser.open(url)
        threading.Event().wait()  # il server resta attivo; si chiude dall'app
        return
    chiudi()  # finestra chiusa davvero (senza icona nella barra): fine


def _avvia_barra(app, finestra, entra, esce, chiudi, url):
    """Icona nella barra e promemoria (solo Windows). Restituisce l'icona,
    o None se non disponibile: allora chiudere la finestra chiude tutto."""
    if sys.platform != "win32":
        return None
    try:
        from gestionale import promemoria, tray
    except ImportError:
        return None

    stato = {"uscita": False}

    def mostra() -> None:
        entra()
        finestra.load_url(url)  # ricarica: dati aggiornati, eventuale avviso «in uso»
        finestra.show()
        finestra.restore()

    def esci() -> None:
        stato["uscita"] = True
        try:
            icona.stop()
        finally:
            chiudi()

    def alla_chiusura():
        if stato["uscita"]:
            return True
        esce()
        finestra.hide()
        if not stato.get("avvisato"):
            stato["avvisato"] = True
            icona.notify("Deal Combined resta attivo qui per i promemoria. Per chiuderlo: tasto destro → Esci.",
                         "Deal Combined è nella barra")
        return False  # niente chiusura: la finestra si nasconde

    try:
        icona = tray.crea(mostra, esci)
    except Exception as exc:  # noqa: BLE001 - pystray/Pillow mancanti o barra non disponibile
        print(f"Icona nella barra non disponibile ({exc}).")
        return None

    app.config["DC_MOSTRA"] = mostra
    finestra.events.closing += alla_chiusura

    def controlla_promemoria() -> None:
        annunciatore = promemoria.Annunciatore()
        time.sleep(30)
        while True:
            try:
                with app.app_context():
                    novita = annunciatore.novita(promemoria.elementi_di_oggi())
                if novita:
                    titolo, testo = novita
                    icona.notify(testo, titolo)
            except Exception as exc:  # noqa: BLE001 - archivio in sincronizzazione, ecc.
                print(f"Promemoria non disponibili ({exc}).")
            time.sleep(promemoria.CONTROLLO_OGNI)

    threading.Thread(target=controlla_promemoria, name="promemoria", daemon=True).start()
    return icona


if __name__ == "__main__":
    main()

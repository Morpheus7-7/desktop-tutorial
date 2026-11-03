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
  è disponibile, o se all'avvio precedente si era chiusa da sola, la apre in
  una finestra di Microsoft Edge in modalità applicazione (senza barra degli
  indirizzi) o, in mancanza, nel browser: il programma si chiude allora dal
  pulsante «Chiudi Deal Combined»;
- su Windows mette un'icona vicino all'orologio: chiudendo la finestra il
  programma resta lì e mostra i promemoria (follow-up di oggi, polizze in
  scadenza) come notifiche di Windows. Con ``--avvio-silenzioso`` (avvio con
  Windows) parte direttamente nella barra, senza finestra.

``DealCombined.exe --reimposta-password NOMEUTENTE`` imposta una nuova password
per un utente (es. l'unico amministratore che l'ha dimenticata).
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


def _chiudi_splash() -> None:
    """Toglie la schermata «Avvio in corso…» dell'eseguibile (se presente)."""
    if "_PYI_SPLASH_IPC" not in os.environ:
        return  # eseguibile senza schermata di avvio, o avvio da sorgente
    try:
        import pyi_splash  # disponibile solo nell'eseguibile con la schermata di avvio

        pyi_splash.close()
    except Exception:  # noqa: BLE001 - sorgente, oppure schermata già chiusa
        pass


NOME_MUTEX = "DealCombinedAppMutex"  # lo stesso in installer/DealCombined.iss
# Segno lasciato mentre la finestra nativa si apre: se il programma si chiude
# da solo entro questi secondi, al prossimo avvio si usa la finestra di Edge.
FILE_PROVA_FINESTRA = "finestra_nativa.prova"
SECONDI_PROVA_FINESTRA = 20


def _leggi_testo(percorso: Path) -> str | None:
    try:
        return percorso.read_text(encoding="utf-8").strip()
    except OSError:
        return None  # lo stesso in installer/DealCombined.iss


def _prendi_mutex():
    """Mutex di Windows con nome: dice all'installatore (e a una seconda
    copia) che il programma è aperto. Restituisce (handle, già_esistente)."""
    if sys.platform != "win32":
        return None, False
    import ctypes

    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateMutexW(None, False, NOME_MUTEX)
    return handle, kernel32.GetLastError() == 183  # ERROR_ALREADY_EXISTS


def chiudi_database(app) -> None:
    """Chiude ogni collegamento al file del database. Su Windows un file
    aperto non può essere sostituito da OneDrive/Google Drive: con la
    finestra nella barra la versione arrivata dall'altro PC deve poter
    entrare. Alla riapertura SQLAlchemy si ricollega da solo."""
    from gestionale.models import db

    with app.app_context():
        db.session.remove()
        db.engine.dispose()


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
    try:
        _avvia()
    finally:
        _chiudi_splash()


def apri_console() -> None:
    """Apre una console per i comandi interattivi quando l'eseguibile non ne ha una."""
    if sys.platform != "win32" or sys.stdin is not None:
        return
    try:
        import ctypes

        ctypes.windll.kernel32.AllocConsole()
        sys.stdin = open("CONIN$", encoding="utf-8")  # noqa: SIM115
        sys.stdout = sys.stderr = open("CONOUT$", "w", encoding="utf-8")  # noqa: SIM115
    except Exception:  # noqa: BLE001
        pass


def _reimposta_password(username: str, data_dir: Path, chiave: str | None) -> int:
    """``DealCombined.exe --reimposta-password NOMEUTENTE``: nuova password per
    un utente (es. l'unico amministratore che l'ha dimenticata)."""
    from gestionale import desktop

    apri_console()
    os.environ.setdefault("SECRET_KEY", chiave or secrets.token_hex(32))
    os.environ.setdefault("DATABASE_URL", "sqlite:///" + str(data_dir / desktop.NOME_DB))
    os.environ.setdefault("UPLOAD_FOLDER", str(data_dir / desktop.NOME_UPLOADS))
    os.environ.setdefault("BACKUP_FOLDER", str(data_dir / desktop.NOME_BACKUP))
    from gestionale import create_app
    from gestionale.cli import chiedi_e_reimposta

    app = create_app()
    with app.app_context():
        esito = chiedi_e_reimposta(username)
    if sys.platform == "win32":
        input("Premi Invio per chiudere…")
    return esito


def _avvia() -> None:
    from gestionale import desktop, promemoria

    silenzioso = promemoria.PARAMETRO_SILENZIOSO in sys.argv[1:]
    file_config = desktop.file_configurazione()
    config = desktop.leggi_configurazione(file_config)
    data_dir = desktop.cartella_dati(config)
    data_dir.mkdir(parents=True, exist_ok=True)

    argomenti = sys.argv[1:]
    if len(argomenti) >= 2 and argomenti[0] == "--reimposta-password":
        _chiudi_splash()
        raise SystemExit(_reimposta_password(argomenti[1], data_dir, config.get("secret_key")))

    file_istanza = file_config.parent / "istanza.txt"
    mutex_app, gia_aperto = _prendi_mutex()  # resta aperto finché il programma è attivo
    if gia_aperto:
        # L'altra copia potrebbe essere ancora in avvio: le si dà qualche secondo.
        for _ in range(20):
            if _altra_copia_attiva(file_istanza):
                return
            time.sleep(1)
        return
    if _altra_copia_attiva(file_istanza):  # fuori da Windows: solo il file
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
    # Backup del gestionale (giornalieri, prima di un ripristino o di una
    # sincronizzazione) nella stessa cartella dei backup di avvio.
    os.environ.setdefault("BACKUP_FOLDER", str(data_dir / desktop.NOME_BACKUP))

    from gestionale import create_app
    from gestionale.scheduler import start_scheduler

    app = create_app()
    app.config.update(DC_DESKTOP=True, DC_CONFIG_FILE=str(file_config), DC_BLOCCO_ALTRUI=None,
                      DC_HO_BLOCCO=False, DC_IN_PAUSA=True)
    stato = {"backup_fatto": False}
    mutex_blocco = threading.Lock()  # entra/esce e battito non si sovrappongono

    def entra() -> None:
        """La finestra si apre: l'archivio diventa «aperto su questo PC», a
        meno che non lo sia già su un altro (pagina di avviso)."""
        with mutex_blocco:
            altrui = desktop.blocco_altrui(data_dir)
            app.config["DC_BLOCCO_ALTRUI"] = altrui
            if not altrui:
                if not stato["backup_fatto"]:
                    desktop.esegui_backup(data_dir, motivo="avvio")
                    stato["backup_fatto"] = True
                desktop.prendi_blocco(data_dir)
                app.config["DC_HO_BLOCCO"] = True
            # Se l'archivio è aperto altrove resta in pausa finché l'utente
            # non sceglie «Apri comunque».
            app.config["DC_IN_PAUSA"] = bool(altrui)

    def esce() -> None:
        """La finestra va nella barra: l'archivio si libera per l'altro PC."""
        from datetime import datetime

        with mutex_blocco:
            app.config["DC_IN_PAUSA"] = True
            app.config["DC_NASCOSTA_ALLE"] = datetime.utcnow().timestamp()  # stesso orologio del PIN
            if app.config.get("DC_HO_BLOCCO"):
                desktop.rilascia_blocco(data_dir)
                app.config["DC_HO_BLOCCO"] = False
            chiudi_database(app)

    def chiudi() -> None:
        esce()
        if app.config.get("DC_FINESTRA"):
            # Chiusura normale della finestra nativa: funziona, si riusa la prossima volta.
            try:
                (data_dir / FILE_PROVA_FINESTRA).unlink(missing_ok=True)
            except OSError:
                pass
        ferma_icona = app.config.get("DC_FERMA_ICONA")
        if ferma_icona:
            try:
                ferma_icona()
            except Exception:  # noqa: BLE001 - l'icona potrebbe essere già ferma
                pass
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
            with mutex_blocco:
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

    # Se all'avvio precedente la finestra nativa si è chiusa da sola appena
    # aperta (componente grafico non compatibile), con questa stessa versione
    # si usa direttamente la finestra di Edge.
    from gestionale import __version__

    prova = data_dir / FILE_PROVA_FINESTRA
    nativa_fallita = _leggi_testo(prova) == __version__

    threading.Thread(target=servi, name="server", daemon=True).start()
    _attendi_server(port)
    try:
        file_istanza.write_text(str(port), encoding="utf-8")
    except OSError:
        pass

    if webview is None or os.environ.get("DC_BROWSER") or nativa_fallita:
        # Ripiego: finestra di Edge (o browser); si chiude dal pulsante «Chiudi Deal Combined».
        _chiudi_splash()
        _finestra_ripiego(app, url, data_dir, entra, esce)
        threading.Event().wait()  # il server resta attivo; si chiude dall'app
        return
    app.config["DC_FINESTRA"] = True

    finestra = webview.create_window(
        "Deal Combined", url, width=1320, height=860, min_size=(360, 560),
        text_select=True, hidden=silenzioso,
    )
    icona = _avvia_barra(app, finestra, entra, esce, chiudi, url)
    if not silenzioso or icona is None:
        entra()
    _chiudi_splash()

    try:
        prova.write_text(__version__, encoding="utf-8")
    except OSError:
        pass

    def finestra_ok() -> None:
        try:
            prova.unlink(missing_ok=True)
        except OSError:
            pass

    threading.Timer(SECONDI_PROVA_FINESTRA, finestra_ok).start()
    try:
        webview.start()
    except Exception as exc:  # noqa: BLE001 - nessun motore WebView disponibile
        print(f"Finestra non disponibile ({exc}): apro la finestra di Edge.")
        app.config["DC_FINESTRA"] = False
        _finestra_ripiego(app, url, data_dir, entra, esce)
        threading.Event().wait()  # il server resta attivo; si chiude dall'app
        return
    chiudi()  # finestra chiusa davvero (senza icona nella barra): fine


def trova_browser_app(env=None, esiste=os.path.isfile) -> str | None:
    """Microsoft Edge (o Chrome) per aprire il programma in una finestra
    propria, senza barra degli indirizzi né schede (solo Windows)."""
    env = os.environ if env is None else env
    candidati = []
    for base in (env.get("PROGRAMFILES(X86)"), env.get("PROGRAMFILES"), env.get("LOCALAPPDATA")):
        if base:
            candidati += [os.path.join(base, "Microsoft", "Edge", "Application", "msedge.exe"),
                          os.path.join(base, "Google", "Chrome", "Application", "chrome.exe")]
    return next((c for c in candidati if esiste(c)), None)


def comando_finestra_app(browser: str, url: str, cartella: Path) -> list[str]:
    """Edge/Chrome in modalità applicazione, con un profilo proprio (la
    finestra ricorda dimensione e posizione)."""
    return [
        browser, f"--app={url}", f"--user-data-dir={Path(cartella) / 'finestra_edge'}",
        "--no-first-run", "--no-default-browser-check", "--disable-sync",
        "--disable-features=Translate,msEdgeStartupBoost,msImplicitSignin",
        "--window-size=1366,860",
    ]


def _apri_finestra_edge(url: str, cartella: Path) -> bool:
    """Ripiego se la finestra nativa non parte: il programma si apre comunque
    in una finestra a sé (si chiude dal pulsante «Chiudi Deal Combined»)."""
    browser = trova_browser_app()
    if browser is None:
        return False
    import subprocess

    try:
        subprocess.Popen(comando_finestra_app(browser, url, cartella), close_fds=True)  # noqa: S603
    except OSError:
        return False
    return True


def edge_in_uso(profilo: Path) -> bool:
    """Edge tiene bloccato il file «lockfile» del profilo finché la finestra è
    aperta (Windows): finché non si riesce a cancellarlo, la finestra c'è."""
    blocco = Path(profilo) / "lockfile"
    if not blocco.exists():
        return False
    try:
        blocco.unlink()  # riesce solo quando Edge ha chiuso la finestra
    except PermissionError:
        return True
    except OSError:
        return False
    return False


def _finestra_ripiego(app, url: str, data_dir: Path, entra, esce, pausa_s: float = 2.0) -> None:
    """Apre il programma nella finestra di Edge (o nel browser) e la rende
    riapribile: un nuovo doppio clic sull'icona la riporta su (invece di non
    fare nulla). Chiusa la finestra di Edge, l'archivio si libera per l'altro
    PC come quando la finestra nativa va nella barra; il programma resta
    pronto e si chiude del tutto con «Chiudi Deal Combined»."""
    stato = {"sorveglia": False}
    profilo = data_dir / "finestra_edge"

    def sorveglia() -> None:
        # Aspetta che Edge apra la finestra (al massimo 30 s), poi che la chiuda.
        for _ in range(int(30 / pausa_s) + 1):
            if (profilo / "lockfile").exists():
                break
            time.sleep(pausa_s)
        while edge_in_uso(profilo):
            time.sleep(pausa_s)
        stato["sorveglia"] = False
        esce()

    def mostra() -> None:
        entra()
        if _apri_finestra_edge(url, data_dir):
            if sys.platform == "win32" and not stato["sorveglia"]:
                stato["sorveglia"] = True
                threading.Thread(target=sorveglia, name="finestra-edge", daemon=True).start()
        else:
            webbrowser.open(url)

    app.config["DC_MOSTRA"] = mostra
    mostra()


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
        chiudi()  # toglie anche l'icona

    def alla_chiusura():
        if stato["uscita"]:
            return True
        esce()
        finestra.hide()
        finestra.load_url("about:blank")  # ferma i timer della pagina (blocco PIN, ricarica)
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
    app.config["DC_FERMA_ICONA"] = icona.stop
    finestra.events.closing += alla_chiusura

    def controlla_promemoria() -> None:
        annunciatore = promemoria.Annunciatore()
        time.sleep(30)
        while True:
            try:
                with app.app_context():
                    novita = annunciatore.novita(promemoria.elementi_di_oggi())
                if app.config.get("DC_IN_PAUSA"):
                    chiudi_database(app)  # lettura lampo: il file non resta aperto
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

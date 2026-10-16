"""Avvio «desktop» del Gestionale Assicurativo.

Fa partire il server web locale, avvia lo scheduler delle notifiche e apre
automaticamente il browser sull'applicazione. È l'entry point usato per
l'eseguibile impacchettato con PyInstaller (vedi ``gestionale.spec``), ma si
può lanciare anche direttamente con:

    python run_desktop.py

Cartella dei dati (database, documenti, backup, chiave di sessione e log),
scelta in quest'ordine:

1. la cartella indicata dalla variabile d'ambiente ``GESTIONALE_DATI``;
2. la cartella ``dati_gestionale`` accanto al programma, se contiene già un
   database (installazioni precedenti): si continua a usarla;
3. in modalità portatile (file ``portatile.txt`` accanto al programma oppure
   ``GESTIONALE_PORTATILE=1``) la cartella ``dati_gestionale`` accanto al
   programma;
4. altrimenti la cartella dell'utente: ``%LOCALAPPDATA%\\GestionaleAssicurativo``
   su Windows, ``~/Library/Application Support/GestionaleAssicurativo`` su
   macOS, ``~/.local/share/GestionaleAssicurativo`` su Linux.

Se il programma gira da una cartella temporanea (ZIP aperto con doppio clic
senza estrarlo) i dati non vengono mai salvati lì: quelli eventualmente già
creati in una cartella temporanea vengono copiati nella cartella dell'utente.

Il programma si avvia una sola volta per cartella dati: un secondo avvio apre
il browser sull'istanza già in esecuzione. Gli errori di avvio vengono scritti
in ``avvio.log`` nella cartella dati e la finestra resta aperta finché non si
preme Invio.

Per recuperare l'accesso se si dimentica la password dell'amministratore:

    GestionaleAssicurativo.exe --reimposta-password NOMEUTENTE
"""
from __future__ import annotations

import logging
import logging.handlers
import mimetypes
import os
import re
import shutil
import socket
import sqlite3
import sys
import tempfile
import threading
import time
import traceback
import webbrowser
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

NOME_APP = "GestionaleAssicurativo"
NOME_CARTELLA_DATI = "dati_gestionale"
NOME_DB = "gestionale.db"
FILE_PORTATILE = "portatile.txt"
FILE_BLOCCO = "gestionale.lock"
FILE_PORTA = "porta.txt"
FILE_LOG = "gestionale.log"
FILE_LOG_AVVIO = "avvio.log"
ENV_CARTELLA_DATI = "GESTIONALE_DATI"
ENV_PORTATILE = "GESTIONALE_PORTATILE"
HOST = "127.0.0.1"
PORTA_PREDEFINITA = 5000
VALORI_VERI = {"1", "true", "yes", "si", "sì", "on"}

# Tipi MIME dei file statici, imposti all'avvio (vedi registra_tipi_mime).
TIPI_MIME = {
    ".js": "text/javascript",
    ".mjs": "text/javascript",
    ".css": "text/css",
    ".svg": "image/svg+xml",
    ".woff2": "font/woff2",
    ".woff": "font/woff",
    ".json": "application/json",
    ".map": "application/json",
}

DESCRIZIONE_POSIZIONE = {
    "temporanea": "una cartella temporanea (ad esempio lo ZIP aperto con doppio clic senza estrarlo)",
    "programmi": "la cartella Programmi",
    "onedrive": "una cartella sincronizzata con OneDrive",
}

# Cartelle in cui Esplora risorse, 7-Zip e WinRAR estraggono un file aperto
# direttamente dall'archivio (tutte sotto %TEMP%, controllate anche per nome).
_NOMI_TEMPORANEI = (
    re.compile(r"^temp\d+_.+\.zip$"),
    re.compile(r"^7zo[0-9a-f]+$"),
    re.compile(r"^rar\$ex"),
    re.compile(r"^_mei\d+$"),
)


class ErroreAvvio(Exception):
    """Errore di avvio con un messaggio comprensibile per l'utente."""


# ----------------------------------------------------------------------
# Tipi MIME
# ----------------------------------------------------------------------
def registra_tipi_mime() -> None:
    """Forza i tipi MIME di script, fogli di stile, icone e font.

    Su Windows ``mimetypes`` legge anche il registro, dove ``.js`` è spesso
    associato a ``text/plain`` da editor o installer: con l'header ``nosniff``
    il browser rifiuterebbe di eseguire Bootstrap e ``app.js``. ``add_type``
    inizializza prima il database dei tipi (registro compreso), quindi i
    valori impostati qui prevalgono.
    """
    for estensione, tipo in TIPI_MIME.items():
        mimetypes.add_type(tipo, estensione)


# ----------------------------------------------------------------------
# Cartella dei dati
# ----------------------------------------------------------------------
def base_dir() -> Path:
    """Cartella del programma: quella dell'eseguibile (o del sorgente in sviluppo)."""
    if getattr(sys, "frozen", False):  # eseguibile PyInstaller
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def cartella_utente(sistema: str | None = None, env: Mapping[str, str] | None = None,
                    home: Path | None = None) -> Path:
    """Cartella dati dell'utente, fuori dalla cartella del programma."""
    sistema = sistema or sys.platform
    env = os.environ if env is None else env
    home = Path.home() if home is None else Path(home)
    if sistema.startswith("win"):
        base = env.get("LOCALAPPDATA") or env.get("APPDATA")
        radice = Path(base) if base else home / "AppData" / "Local"
    elif sistema == "darwin":
        radice = home / "Library" / "Application Support"
    else:
        xdg = env.get("XDG_DATA_HOME")
        radice = Path(xdg) if xdg and os.path.isabs(xdg) else home / ".local" / "share"
    return radice / NOME_APP


def _normalizza(percorso) -> str:
    return os.path.normcase(os.path.realpath(os.path.abspath(os.path.expanduser(str(percorso)))))


def _sotto(percorso, radice) -> bool:
    """True se ``percorso`` coincide con ``radice`` o si trova al suo interno."""
    if not radice:
        return False
    r = _normalizza(radice)
    if len(Path(r).parts) < 2:  # mai considerare «sotto» la radice del disco
        return False
    p = _normalizza(percorso)
    return p == r or p.startswith(r.rstrip(os.sep) + os.sep)


def posizione_instabile(cartella, env: Mapping[str, str] | None = None,
                        temp: str | os.PathLike | None = None) -> str | None:
    """Dove non conviene tenere i dati: «temporanea», «programmi», «onedrive» o None."""
    env = os.environ if env is None else env
    temp = tempfile.gettempdir() if temp is None else temp
    if any(_sotto(cartella, r) for r in (temp, env.get("TEMP"), env.get("TMP"))):
        return "temporanea"
    if any(_sotto(cartella, env.get(v)) for v in ("PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMW6432")):
        return "programmi"
    if any(_sotto(cartella, env.get(v)) for v in ("ONEDRIVE", "ONEDRIVECOMMERCIAL", "ONEDRIVECONSUMER")):
        return "onedrive"
    for parte in Path(cartella).parts:
        nome = parte.lower()
        if any(regola.match(nome) for regola in _NOMI_TEMPORANEI):
            return "temporanea"
        if nome in ("program files", "program files (x86)"):
            return "programmi"
        if nome.startswith("onedrive"):
            return "onedrive"
    return None


def cartella_scrivibile(cartella: Path) -> bool:
    """Crea la cartella se serve e verifica che si possa scriverci (database compreso)."""
    cartella = Path(cartella)
    try:
        cartella.mkdir(parents=True, exist_ok=True)
        fd, prova = tempfile.mkstemp(prefix=".prova_scrittura_", dir=cartella)
        os.close(fd)
        os.remove(prova)
    except OSError:
        return False
    database = cartella / NOME_DB
    return not database.exists() or os.access(database, os.W_OK)


@dataclass
class SceltaDati:
    """Esito della scelta della cartella dati."""

    cartella: Path
    motivo: str
    avvisi: list[str] = field(default_factory=list)
    migra_da: Path | None = None  # cartella da cui copiare i dati esistenti
    esplicita: bool = False


def scegli_cartella_dati(
    base: Path,
    *,
    env: Mapping[str, str] | None = None,
    sistema: str | None = None,
    home: Path | None = None,
    temp: str | os.PathLike | None = None,
    scrivibile: Callable[[Path], bool] = cartella_scrivibile,
) -> SceltaDati:
    """Sceglie dove salvare i dati (vedi la docstring del modulo per l'ordine)."""
    env = os.environ if env is None else env
    base = Path(base)
    utente = cartella_utente(sistema, env, home)

    esplicita = (env.get(ENV_CARTELLA_DATI) or "").strip()
    if esplicita:
        return SceltaDati(Path(esplicita).expanduser(), f"indicata dalla variabile {ENV_CARTELLA_DATI}",
                          esplicita=True)

    accanto = base / NOME_CARTELLA_DATI
    instabile = posizione_instabile(base, env, temp)
    descrizione = DESCRIZIONE_POSIZIONE.get(instabile, "")

    def _verso_utente(problema: str) -> SceltaDati:
        if (utente / NOME_DB).exists():
            return SceltaDati(utente, "cartella dati dell'utente",
                              [f"{problema} Uso i dati già presenti in {utente}."])
        return SceltaDati(utente, "cartella dati dell'utente",
                          [f"{problema} I dati vengono copiati in {utente}."], migra_da=accanto)

    # Installazioni precedenti: dati già presenti accanto al programma.
    if (accanto / NOME_DB).is_file():
        if instabile == "temporanea":
            return _verso_utente(f"I dati trovati accanto al programma sono in {descrizione} e andrebbero persi.")
        if not scrivibile(accanto):
            return _verso_utente(f"La cartella dati {accanto} non è scrivibile.")
        avvisi = []
        if instabile:
            avvisi.append(
                f"La cartella dati {accanto} si trova in {descrizione}: per evitare perdite o conflitti "
                "sposta il programma con la sua cartella dati in una cartella locale non sincronizzata "
                "(es. C:\\Gestionale)."
            )
        return SceltaDati(accanto, "cartella dati esistente accanto al programma", avvisi)

    portatile = (base / FILE_PORTATILE).is_file() or (env.get(ENV_PORTATILE) or "").strip().lower() in VALORI_VERI
    if portatile:
        if instabile == "temporanea":
            avviso = (f"Modalità portatile ignorata: il programma gira da {descrizione}. "
                      "Estrai lo ZIP (tasto destro → Estrai tutto) in una cartella stabile.")
        elif not scrivibile(accanto):
            avviso = f"Modalità portatile ignorata: la cartella {accanto} non è scrivibile."
        else:
            avvisi = [f"La cartella dati si trova in {descrizione}."] if instabile else []
            return SceltaDati(accanto, "modalità portatile", avvisi)
        return SceltaDati(utente, "cartella dati dell'utente", [avviso])

    avvisi = []
    if instabile == "temporanea":
        avvisi.append(
            f"Il programma gira da {descrizione}: i dati vengono comunque salvati in modo permanente in "
            f"{utente}. Per comodità estrai lo ZIP (tasto destro → Estrai tutto) in una cartella stabile."
        )
    return SceltaDati(utente, "cartella dati dell'utente", avvisi)


def migra_dati(sorgente: Path, destinazione: Path) -> None:
    """Copia i dati in un'altra cartella; il database per ultimo, con l'API di backup.

    Se la copia si interrompe, al riavvio la destinazione non ha ancora il
    database e la copia viene ripetuta.
    """
    sorgente, destinazione = Path(sorgente), Path(destinazione)
    destinazione.mkdir(parents=True, exist_ok=True)
    esclusi = {NOME_DB, f"{NOME_DB}-journal", f"{NOME_DB}-wal", f"{NOME_DB}-shm", FILE_BLOCCO, FILE_PORTA}
    for voce in sorgente.iterdir():
        if voce.name in esclusi:
            continue
        dest = destinazione / voce.name
        if voce.is_dir():
            shutil.copytree(voce, dest, dirs_exist_ok=True)
        elif not dest.exists():
            shutil.copy2(voce, dest)
    parziale = destinazione / f".{NOME_DB}.copia"
    origine = sqlite3.connect(str(sorgente / NOME_DB))
    try:
        dest_conn = sqlite3.connect(str(parziale))
        try:
            origine.backup(dest_conn)
        finally:
            dest_conn.close()
    finally:
        origine.close()
    os.replace(parziale, destinazione / NOME_DB)


def url_sqlite(percorso: Path) -> str:
    """URL SQLAlchemy di un file SQLite, sicuro con spazi, accenti, «%», «#» e «?» nel percorso."""
    from sqlalchemy.engine import URL

    return URL.create("sqlite", database=str(percorso)).render_as_string(hide_password=False)


def configura_ambiente(cartella: Path, env: dict | None = None) -> None:
    """Variabili lette da ``create_app``: tutti i dati nella cartella scelta."""
    env = os.environ if env is None else env
    cartella = Path(cartella)
    env.setdefault("DATABASE_URL", url_sqlite(cartella / NOME_DB))
    env.setdefault("UPLOAD_FOLDER", str(cartella / "uploads"))
    env.setdefault("BACKUP_FOLDER", str(cartella / "backup"))
    # Chiave di sessione generata al primo avvio e conservata con i dati.
    env.setdefault("SECRET_KEY_FILE", str(cartella / "secret_key"))


# ----------------------------------------------------------------------
# Istanza unica e porta
# ----------------------------------------------------------------------
class BloccoIstanza:
    """Blocco esclusivo sulla cartella dati: una sola istanza del programma alla volta.

    Il blocco resta attivo finché il processo è in esecuzione e il sistema lo
    rilascia da solo alla chiusura (anche se la finestra viene chiusa).
    """

    def __init__(self, percorso: Path):
        self.percorso = Path(percorso)
        self._fd: int | None = None

    def acquisisci(self) -> bool:
        fd = os.open(self.percorso, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            if os.name == "nt":  # pragma: no cover - solo Windows
                import msvcrt

                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            return False
        self._fd = fd
        return True

    def rilascia(self) -> None:
        if self._fd is None:
            return
        try:
            if os.name == "nt":  # pragma: no cover - solo Windows
                import msvcrt

                os.lseek(self._fd, 0, os.SEEK_SET)
                msvcrt.locking(self._fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._fd, fcntl.LOCK_UN)
        except OSError:  # pragma: no cover
            pass
        finally:
            os.close(self._fd)
            self._fd = None


def porta_preferita(env: Mapping[str, str] | None = None) -> int:
    env = os.environ if env is None else env
    try:
        porta = int(env.get("PORT") or PORTA_PREDEFINITA)
    except ValueError:
        return PORTA_PREDEFINITA
    return porta if 1 <= porta <= 65535 else PORTA_PREDEFINITA


def crea_socket_server(preferita: int, host: str = HOST) -> socket.socket:
    """Socket in ascolto sulla porta preferita, o su una porta libera qualsiasi.

    Il socket viene passato così com'è a waitress: niente controllo «porta
    libera» seguito da un secondo bind, che lascerebbe spazio a un altro
    processo. Su Windows SO_EXCLUSIVEADDRUSE impedisce a chiunque altro di
    agganciarsi alla stessa porta (con SO_REUSEADDR due programmi potrebbero
    ascoltare insieme sulla 5000).
    """
    ultimo_errore: OSError | None = None
    for porta in dict.fromkeys((preferita, 0)):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):  # pragma: no cover - solo Windows
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            else:
                # POSIX: consente solo il riuso delle connessioni chiuse da poco (TIME_WAIT).
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, porta))
            sock.listen(128)
            return sock
        except OSError as exc:
            sock.close()
            ultimo_errore = exc
    raise ErroreAvvio(f"Impossibile aprire una porta di rete locale: {ultimo_errore}")


def scrivi_porta(cartella: Path, porta: int) -> None:
    (Path(cartella) / FILE_PORTA).write_text(str(porta), encoding="ascii")


def leggi_porta(cartella: Path) -> int | None:
    try:
        porta = int((Path(cartella) / FILE_PORTA).read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        return None
    return porta if 1 <= porta <= 65535 else None


def porta_in_ascolto(porta: int, host: str = HOST, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, porta), timeout=timeout):
            return True
    except OSError:
        return False


def apri_istanza_esistente(cartella: Path, attesa_s: float = 20.0,
                           apri: Callable[[str], object] = webbrowser.open,
                           pausa_s: float = 0.5) -> str | None:
    """Apre il browser sull'istanza già avviata. Restituisce l'indirizzo, o None.

    L'altra istanza potrebbe essere ancora in fase di avvio: si attende fino a
    ``attesa_s`` secondi che scriva la porta e inizi ad ascoltare.
    """
    scadenza = time.monotonic() + attesa_s
    while True:
        porta = leggi_porta(cartella)
        if porta and porta_in_ascolto(porta):
            url = f"http://{HOST}:{porta}"
            apri(url)
            return url
        if time.monotonic() >= scadenza:
            return None
        time.sleep(pausa_s)


# ----------------------------------------------------------------------
# Log ed errori di avvio
# ----------------------------------------------------------------------
_cartella_log: Path | None = None
_blocco: BloccoIstanza | None = None


def configura_log(cartella: Path) -> None:
    """Log dell'applicazione su console e su file (``gestionale.log``, a rotazione)."""
    radice = logging.getLogger()
    if any(getattr(h, "_gestionale", False) for h in radice.handlers):
        return
    formato = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    gestori: list[logging.Handler] = [
        logging.handlers.RotatingFileHandler(
            Path(cartella) / FILE_LOG, maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
    ]
    if sys.stderr is not None:
        gestori.append(logging.StreamHandler())
    for gestore in gestori:
        gestore.setFormatter(formato)
        gestore._gestionale = True  # type: ignore[attr-defined]
        radice.addHandler(gestore)
    radice.setLevel(logging.INFO)


def registra_errore_avvio(testo: str) -> Path | None:
    """Scrive il dettaglio dell'errore in ``avvio.log`` (cartella dati, o di ripiego)."""
    candidati = [_cartella_log, cartella_utente(), Path(tempfile.gettempdir())]
    for cartella in candidati:
        if cartella is None:
            continue
        try:
            Path(cartella).mkdir(parents=True, exist_ok=True)
            percorso = Path(cartella) / FILE_LOG_AVVIO
            with open(percorso, "a", encoding="utf-8") as fh:
                fh.write(f"\n=== {datetime.now():%d/%m/%Y %H:%M:%S} ===\n{testo}\n")
            return percorso
        except OSError:
            continue
    return None  # pragma: no cover


def attendi_invio(messaggio: str = "Premi Invio per chiudere…") -> None:
    """Tiene aperta la finestra della console finché l'utente non preme Invio."""
    try:
        if sys.stdin is not None and sys.stdin.isatty():
            input(messaggio)
    except (EOFError, OSError, KeyboardInterrupt):
        pass


# ----------------------------------------------------------------------
# Avvio
# ----------------------------------------------------------------------
def _main(argv: list[str]) -> int:
    global _cartella_log, _blocco

    registra_tipi_mime()
    scelta = scegli_cartella_dati(base_dir())
    cartella = scelta.cartella
    if not cartella_scrivibile(cartella):
        suggerimento = (f"Imposta {ENV_CARTELLA_DATI} su una cartella scrivibile."
                        if scelta.esplicita else "Controlla i permessi della cartella.")
        raise ErroreAvvio(f"Impossibile scrivere nella cartella dati {cartella}. {suggerimento}")
    _cartella_log = cartella

    # Istanza unica: il blocco viene preso prima di scrivere log o copiare dati.
    reimposta = len(argv) >= 2 and argv[0] == "--reimposta-password"
    if not reimposta:
        _blocco = BloccoIstanza(cartella / FILE_BLOCCO)
        if not _blocco.acquisisci():
            url = apri_istanza_esistente(cartella)
            if url:
                print(f"Il Gestionale Assicurativo è già in esecuzione: ho aperto il browser su {url}")
                time.sleep(2)  # il tempo di leggere il messaggio
                return 0
            raise ErroreAvvio(
                "Il Gestionale Assicurativo risulta già in esecuzione con la stessa cartella dati, ma non "
                "risponde. Chiudi l'altra finestra del programma (o riavvia il computer) e riprova."
            )
        try:  # porta dell'avvio precedente: non più valida
            (cartella / FILE_PORTA).unlink()
        except FileNotFoundError:
            pass

    configura_log(cartella)
    log = logging.getLogger("gestionale.avvio")
    log.info("Cartella dati: %s (%s)", cartella, scelta.motivo)
    if scelta.migra_da:
        migra_dati(scelta.migra_da, cartella)
        log.warning("Dati copiati da %s a %s", scelta.migra_da, cartella)
    for avviso in scelta.avvisi:
        log.warning(avviso)

    configura_ambiente(cartella)
    from gestionale import create_app
    from gestionale.backup import normalizza_cartelle

    app = create_app()
    normalizza_cartelle(app)

    if reimposta:
        from gestionale.cli import chiedi_e_reimposta

        with app.app_context():
            return chiedi_e_reimposta(argv[1])

    sock = crea_socket_server(porta_preferita())
    porta = sock.getsockname()[1]
    url = f"http://{HOST}:{porta}"
    # I link nelle email puntano all'app in esecuzione localmente.
    os.environ.setdefault("APP_BASE_URL", url)
    scrivi_porta(cartella, porta)

    from gestionale.scheduler import start_scheduler

    start_scheduler(app)

    print("=" * 60)
    print("  Gestionale Assicurativo è in esecuzione.")
    print(f"  Apri il browser su:  {url}")
    print(f"  Dati salvati in:     {cartella}")
    print("  Chiudi questa finestra per fermare il programma.")
    print("=" * 60)

    # Il socket è già in ascolto: il browser può aprirsi subito.
    apertura = threading.Timer(1.0, webbrowser.open, args=(url,))
    apertura.daemon = True
    apertura.start()

    try:
        from waitress import serve  # server WSGI di produzione, puro Python
    except ImportError:  # pragma: no cover
        # Fallback: server integrato di Flask (nessuna dipendenza extra).
        sock.close()
        app.run(host=HOST, port=porta, debug=False, use_reloader=False)
    else:
        serve(app, sockets=[sock], threads=8)
    return 0


def main(argv: list[str] | None = None) -> int:
    """Avvia il programma; qualsiasi errore viene registrato e mostrato senza chiudere la finestra."""
    argv = sys.argv[1:] if argv is None else argv
    try:
        return _main(argv)
    except KeyboardInterrupt:
        return 0
    except SystemExit:
        raise
    except BaseException as exc:  # noqa: BLE001 - l'utente deve sempre vedere cosa è successo
        percorso = registra_errore_avvio(traceback.format_exc())
        print("=" * 60)
        print("  Il Gestionale Assicurativo si è fermato per un errore.")
        if isinstance(exc, ErroreAvvio):
            print(f"  {exc}")
        else:
            print(f"  {exc.__class__.__name__}: {exc}")
        if percorso:
            print(f"  Dettagli tecnici nel file: {percorso}")
        print("=" * 60)
        attendi_invio()
        return 1


if __name__ == "__main__":
    sys.exit(main())

"""Impostazioni: notifiche via email (SMTP), dati e backup."""
import threading
from datetime import datetime
from pathlib import Path

from flask import (
    Blueprint, abort, current_app, flash, redirect, render_template, request, send_file, url_for,
)

from .. import archivio, desktop
from ..archivio import percorso_db
from ..desktop import NOME_DB
from ..mailer import contatore_pending, effective_config, send_pending_notifications, send_test_email
from ..models import Settings, db

LIMITE_IMPORTAZIONE = 1024 ** 3  # 1 GB: l'archivio comprende i documenti caricati


def aggiorna_schema() -> None:
    """Dopo un'importazione: crea tabelle e colonne mancanti (archivio di una
    versione precedente)."""
    from .. import _ensure_schema

    db.create_all()
    _ensure_schema()

bp = Blueprint("settings", __name__, url_prefix="/impostazioni")

SECURITY_CHOICES = [
    ("tls", "STARTTLS (porta 587)"),
    ("ssl", "SSL/TLS (porta 465)"),
    ("none", "Nessuna (sconsigliato)"),
]


def _parse_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _apply_form(s: Settings) -> None:
    """Aggiorna la configurazione dai campi del form e salva."""
    s.email_attive = request.form.get("email_attive") == "on"
    s.smtp_host = (request.form.get("smtp_host") or "").strip()
    s.smtp_port = _parse_int(request.form.get("smtp_port"), 587)
    s.smtp_security = request.form.get("smtp_security") or "tls"
    s.smtp_user = (request.form.get("smtp_user") or "").strip()
    # La password si aggiorna solo se il campo è stato compilato: così lasciare
    # il campo vuoto non cancella una password già salvata.
    nuova_pw = request.form.get("smtp_password")
    if nuova_pw:
        s.smtp_password = nuova_pw
    s.mail_from = (request.form.get("mail_from") or "").strip()
    s.mail_to = (request.form.get("mail_to") or "").strip()
    s.intervallo_minuti = max(1, _parse_int(request.form.get("intervallo_minuti"), 30))
    db.session.commit()


@bp.route("/", methods=["GET"])
def edit():
    s = Settings.get()
    cfg = effective_config(s)
    return render_template(
        "settings/form.html",
        s=s,
        cfg=cfg,
        security_choices=SECURITY_CHOICES,
        pending=contatore_pending(),
    )


@bp.route("/", methods=["POST"])
def save():
    _apply_form(Settings.get())
    flash("Impostazioni salvate.", "success")
    return redirect(url_for("settings.edit"))


@bp.route("/prova", methods=["POST"])
def test_email():
    # Salviamo i dati appena inseriti, poi proviamo l'invio con quei parametri.
    _apply_form(Settings.get())
    ok, messaggio = send_test_email()
    flash(messaggio, "success" if ok else "danger")
    return redirect(url_for("settings.edit"))


@bp.route("/invia-ora", methods=["POST"])
def send_now():
    s = Settings.get()
    if not s.email_attive:
        flash("Le notifiche via email sono disattivate: attivale per inviare.", "warning")
        return redirect(url_for("settings.edit"))
    try:
        inviate = send_pending_notifications(s)
    except Exception as exc:  # noqa: BLE001
        flash(f"Invio non riuscito: {exc}", "danger")
        return redirect(url_for("settings.edit"))
    if inviate:
        flash(f"Inviata 1 email con {inviate} notifiche.", "success")
    else:
        flash("Nessuna notifica da inviare al momento.", "info")
    return redirect(url_for("settings.edit"))


# ----------------------------------------------------------------------
# Dati e backup: cartella dati, backup, esporta/importa l'archivio
# ----------------------------------------------------------------------
def _cartella_corrente() -> Path:
    return percorso_db(current_app.config["SQLALCHEMY_DATABASE_URI"]).parent


@bp.route("/dati", methods=["GET"])
def data():
    cartella = _cartella_corrente()
    db_file = cartella / NOME_DB
    blocco = desktop.leggi_blocco(cartella)
    return render_template(
        "settings/dati.html",
        cartella=cartella,
        desktop_mode=current_app.config.get("DC_DESKTOP", False),
        dimensione_db=db_file.stat().st_size if db_file.exists() else 0,
        backup=desktop.elenco_backup(cartella),
        blocco=blocco,
        questo_pc=desktop.nome_pc(),
    )


@bp.route("/dati/backup", methods=["POST"])
def backup_now():
    creato = desktop.esegui_backup(_cartella_corrente(), motivo="manuale")
    flash(f"Backup creato: {creato.name}." if creato else "Non c'è ancora un database da salvare.",
          "success" if creato else "warning")
    return redirect(url_for("settings.data"))


@bp.route("/dati/esporta", methods=["GET"])
def export_archive():
    cartella = _cartella_corrente()
    zip_bytes = archivio.esporta(cartella / NOME_DB, Path(current_app.config["UPLOAD_FOLDER"]))
    nome = f"deal-combined-archivio-{datetime.now():%Y%m%d-%H%M}.zip"
    return send_file(zip_bytes, mimetype="application/zip", as_attachment=True, download_name=nome)


@bp.route("/dati/importa", methods=["POST"])
def import_archive():
    request.max_content_length = LIMITE_IMPORTAZIONE
    file = request.files.get("archivio")
    if not file or not file.filename:
        flash("Scegli il file .zip dell'archivio da importare.", "warning")
        return redirect(url_for("settings.data"))
    if request.form.get("conferma") != "1":
        flash("Conferma di voler sostituire i dati attuali.", "warning")
        return redirect(url_for("settings.data"))
    dati = file.read()
    cartella = _cartella_corrente()
    uploads = Path(current_app.config["UPLOAD_FOLDER"])
    # Copia di sicurezza completa (database e documenti) prima di sostituire.
    backup_dir = cartella / desktop.NOME_BACKUP
    backup_dir.mkdir(parents=True, exist_ok=True)
    copia = backup_dir / f"archivio-prima-di-importare-{datetime.now():%Y%m%d-%H%M%S}.zip"
    if (cartella / NOME_DB).exists():
        copia.write_bytes(archivio.esporta(cartella / NOME_DB, uploads).getvalue())
    db.session.remove()
    db.engine.dispose()
    try:
        archivio.importa(dati, cartella / NOME_DB, uploads)
    except archivio.ArchivioNonValido as exc:
        flash(str(exc), "danger")
        return redirect(url_for("settings.data"))
    aggiorna_schema()
    flash(f"Archivio importato. I dati precedenti sono salvati in Backup\\{copia.name}.", "success")
    return redirect(url_for("main.dashboard"))


@bp.route("/dati/cartella", methods=["POST"])
def change_folder():
    if not current_app.config.get("DC_DESKTOP"):
        flash("La cartella dati si cambia solo nel programma installato.", "warning")
        return redirect(url_for("settings.data"))
    nuova = Path((request.form.get("cartella") or "").strip()).expanduser()
    errore = desktop.verifica_cartella(nuova)
    if errore:
        flash(errore, "danger")
        return redirect(url_for("settings.data"))
    attuale = _cartella_corrente()
    if nuova.resolve() == attuale.resolve():
        flash("È già la cartella in uso.", "info")
        return redirect(url_for("settings.data"))
    if (nuova / NOME_DB).exists():
        messaggio = ("Nella nuova cartella c'è già un archivio di Deal Combined: al prossimo avvio "
                     "userai quello. I dati di questa cartella restano dove sono.")
    elif request.form.get("copia") == "1":
        db_corrente = attuale / NOME_DB
        if db_corrente.exists():
            desktop.esegui_backup(attuale, motivo="spostamento")
            archivio.importa(
                archivio.esporta(db_corrente, Path(current_app.config["UPLOAD_FOLDER"])).getvalue(),
                nuova / NOME_DB, nuova / desktop.NOME_UPLOADS,
            )
        messaggio = "Dati copiati nella nuova cartella."
    else:
        messaggio = "Al prossimo avvio partirai da un archivio vuoto in quella cartella."
    file_config = Path(current_app.config["DC_CONFIG_FILE"]) if current_app.config.get("DC_CONFIG_FILE") else None
    config = desktop.leggi_configurazione(file_config)
    config["cartella_dati"] = str(nuova)
    desktop.salva_configurazione(config, file_config)
    flash(f"{messaggio} Chiudi e riapri Deal Combined per usare la nuova cartella.", "success")
    return redirect(url_for("settings.data"))


@bp.route("/chiudi", methods=["POST"])
def shutdown():
    """Chiude il programma (solo nella versione installata). Richiede
    l'intestazione impostata dal nostro pulsante: un altro sito non può
    aggiungerla a una richiesta verso l'app."""
    if not current_app.config.get("DC_DESKTOP") or request.headers.get("X-DC-Azione") != "chiudi":
        abort(404)
    chiudi = current_app.config.get("DC_SHUTDOWN")
    if chiudi:
        threading.Timer(0.5, chiudi).start()
    return ("", 204)


@bp.route("/mostra", methods=["POST"])
def show_window():
    """Riporta in primo piano la finestra: la usa una seconda copia del
    programma, aperta mentre questa è già attiva nella barra."""
    mostra = current_app.config.get("DC_MOSTRA")
    if not mostra or request.headers.get("X-DC-Azione") != "mostra":
        abort(404)
    threading.Thread(target=mostra, daemon=True).start()
    return ("", 204)


# ----------------------------------------------------------------------
# Archivio aperto su un altro PC (cartella dati sincronizzata)
# ----------------------------------------------------------------------
@bp.before_app_request
def ferma_se_aperto_altrove():
    """Se all'avvio l'archivio risultava aperto su un altro PC, ogni pagina
    porta all'avviso finché l'utente non decide."""
    if not current_app.config.get("DC_BLOCCO_ALTRUI"):
        return None
    if request.endpoint in ("settings.in_use", "settings.open_anyway", "settings.shutdown",
                            "settings.show_window", "static"):
        return None
    return redirect(url_for("settings.in_use"))


@bp.route("/in-uso", methods=["GET"])
def in_use():
    blocco = current_app.config.get("DC_BLOCCO_ALTRUI")
    if not blocco:
        return redirect(url_for("main.dashboard"))
    return render_template("settings/in_uso.html", blocco=blocco,
                           desktop_mode=current_app.config.get("DC_DESKTOP", False))


@bp.route("/in-uso/apri-comunque", methods=["POST"])
def open_anyway():
    current_app.config["DC_BLOCCO_ALTRUI"] = None
    desktop.prendi_blocco(_cartella_corrente())
    current_app.config["DC_HO_BLOCCO"] = True
    flash("Archivio aperto su questo PC. Non usarlo nello stesso momento sull'altro PC.", "warning")
    return redirect(url_for("main.dashboard"))


# ----------------------------------------------------------------------
# Google: Gmail (SMTP), cartella di Google Drive per desktop, Calendar
# ----------------------------------------------------------------------
def _file_config_locale() -> Path | None:
    return Path(current_app.config["DC_CONFIG_FILE"]) if current_app.config.get("DC_CONFIG_FILE") else None


@bp.route("/google", methods=["GET", "POST"])
def google():
    from .. import google as g

    file_config = _file_config_locale()
    config = desktop.leggi_configurazione(file_config)
    s = Settings.get()
    if request.method == "POST":
        azione = request.form.get("azione")
        if azione == "drive":
            percorso = (request.form.get("cartella_drive") or "").strip()
            if percorso and not Path(percorso).is_dir():
                flash("Questa cartella non esiste su questo PC: controlla che Google Drive per desktop sia avviato.", "danger")
                return redirect(url_for("settings.google"))
            config["cartella_drive"] = percorso or None
            desktop.salva_configurazione(config, file_config)
            flash("Cartella di Google Drive salvata." if percorso else "Cartella di Google Drive rimossa.", "success")
        elif azione == "gmail":
            s.smtp_host = g.GMAIL_SMTP["smtp_host"]
            s.smtp_port = g.GMAIL_SMTP["smtp_port"]
            s.smtp_security = g.GMAIL_SMTP["smtp_security"]
            utente = (request.form.get("gmail") or "").strip()
            if utente:
                s.smtp_user = utente
                s.mail_from = s.mail_from or utente
            if request.form.get("password"):
                s.smtp_password = request.form["password"].replace(" ", "")
            db.session.commit()
            flash("Gmail impostato. Prova l'invio da «Notifiche email» → «Salva e invia email di prova».", "success")
        return redirect(url_for("settings.google"))
    return render_template(
        "settings/google.html",
        cartella_drive=config.get("cartella_drive"),
        drive_ok=bool(config.get("cartella_drive")) and Path(config["cartella_drive"]).is_dir(),
        candidati=g.candidati_drive(),
        s=s,
        gmail_attivo=(s.smtp_host or "").lower() == g.GMAIL_SMTP["smtp_host"],
    )


# ----------------------------------------------------------------------
# Aggiornamenti (Release di GitHub)
# ----------------------------------------------------------------------
def controlla_aggiornamenti(app) -> None:
    """Controlla se c'è una versione nuova e ne salva l'esito in app.config.
    Pensata per girare in un thread all'avvio: un errore di rete non deve
    disturbare l'utente, viene solo annotato."""
    from .. import __version__, aggiornamenti

    try:
        app.config["DC_AGGIORNAMENTO"] = aggiornamenti.controlla(__version__)
        app.config["DC_AGGIORNAMENTO_ERRORE"] = None
    except Exception as exc:  # noqa: BLE001 - rete assente, GitHub non raggiungibile…
        app.config["DC_AGGIORNAMENTO_ERRORE"] = str(exc) or exc.__class__.__name__
    app.config["DC_AGGIORNAMENTO_CONTROLLATO"] = datetime.now()


def _installabile() -> bool:
    import sys

    return bool(current_app.config.get("DC_DESKTOP")) and sys.platform == "win32"


@bp.route("/aggiornamenti", methods=["GET", "POST"])
def updates():
    from .. import __version__

    file_config = _file_config_locale()
    config = desktop.leggi_configurazione(file_config)
    if request.method == "POST":
        azione = request.form.get("azione")
        if azione == "controlla":
            controlla_aggiornamenti(current_app._get_current_object())
            errore = current_app.config.get("DC_AGGIORNAMENTO_ERRORE")
            if errore:
                flash(f"Controllo non riuscito: {errore}", "danger")
            elif not current_app.config.get("DC_AGGIORNAMENTO"):
                flash(f"Hai già l'ultima versione ({__version__}).", "success")
        elif azione == "avvio" and _installabile():
            from .. import promemoria

            try:
                promemoria.imposta_avvio_automatico(request.form.get("avvio") == "1")
                flash("Avvio con Windows aggiornato.", "success")
            except OSError as exc:
                flash(f"Non riesco a cambiare l'avvio con Windows: {exc}", "danger")
        elif azione == "automatico" and file_config:
            config["aggiornamenti_automatici"] = request.form.get("automatico") == "1"
            desktop.salva_configurazione(config, file_config)
            flash("Preferenza salvata.", "success")
        return redirect(url_for("settings.updates"))
    return render_template(
        "settings/aggiornamenti.html",
        versione=__version__,
        nuova=current_app.config.get("DC_AGGIORNAMENTO"),
        controllato=current_app.config.get("DC_AGGIORNAMENTO_CONTROLLATO"),
        errore=current_app.config.get("DC_AGGIORNAMENTO_ERRORE"),
        installabile=_installabile(),
        automatico=config.get("aggiornamenti_automatici", True),
        desktop_mode=bool(file_config),
        avvio=_avvio_con_windows() if _installabile() else None,
    )


def _avvio_con_windows():
    from .. import promemoria

    return promemoria.avvio_automatico()


@bp.route("/aggiornamenti/installa", methods=["POST"])
def install_update():
    from .. import aggiornamenti

    nuova = current_app.config.get("DC_AGGIORNAMENTO")
    if not nuova or not _installabile():
        abort(404)
    try:
        percorso = aggiornamenti.scarica_e_verifica(nuova)
    except (OSError, aggiornamenti.AggiornamentoNonValido) as exc:
        flash(f"Aggiornamento non riuscito: {exc}", "danger")
        return redirect(url_for("settings.updates"))
    desktop.esegui_backup(_cartella_corrente(), motivo="aggiornamento")
    try:
        aggiornamenti.avvia_installatore(percorso)
    except OSError as exc:
        flash(f"Non riesco ad avviare l'installatore: {exc}", "danger")
        return redirect(url_for("settings.updates"))
    chiudi = current_app.config.get("DC_SHUTDOWN")
    if chiudi:
        threading.Timer(1.5, chiudi).start()
    return render_template("settings/aggiornamento_in_corso.html", nuova=nuova)

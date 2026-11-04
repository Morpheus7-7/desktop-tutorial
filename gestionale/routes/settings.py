"""Impostazioni (solo amministratori): dati dello studio, notifiche via email
(SMTP), automatismi sulle date, backup/ripristino, cartella dati, Google e
aggiornamenti."""
import os
import tempfile
import threading
from datetime import datetime
from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    send_file,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.utils import secure_filename

from .. import archivio, backup, desktop, google_calendar
from ..archivio import percorso_db
from ..desktop import NOME_DB
from ..mailer import contatore_pending, effective_config, send_pending_notifications, send_test_email
from ..models import AuditLog, CalendarioEvento, Settings, db, leggi_preavvisi, now
from ..security import audit, require_admin
from ..utils import clean, parse_int

LIMITE_IMPORTAZIONE = 1024 ** 3  # 1 GB: l'archivio comprende i documenti caricati


def aggiorna_schema() -> None:
    """Dopo un'importazione: crea tabelle e colonne mancanti (archivio di una
    versione precedente)."""
    from .. import _ensure_schema

    db.create_all()
    _ensure_schema()

bp = Blueprint("settings", __name__, url_prefix="/impostazioni")
# Comandi della finestra del programma e avviso «archivio aperto sull'altro
# PC»: devono funzionare anche prima dell'accesso (vedi security.PUBLIC_ENDPOINTS).
ENDPOINT_SENZA_ADMIN = {"settings.shutdown", "settings.show_window", "settings.in_use", "settings.open_anyway",
                        "settings.calendar_return"}


@bp.before_request
def _solo_amministratori():
    if request.endpoint in ENDPOINT_SENZA_ADMIN:
        return None
    return require_admin()

SECURITY_CHOICES = [
    ("tls", "STARTTLS (porta 587)"),
    ("ssl", "SSL/TLS (porta 465)"),
    ("none", "Nessuna (sconsigliato)"),
]

# Campi numerici: (etichetta, minimo, massimo, valore se il campo è vuoto).
CAMPI_INTERI = {
    "smtp_port": ("Porta SMTP", 1, 65535, 587),
    "intervallo_minuti": ("Controllo automatico ogni (minuti)", 1, 1440, 30),
    "backup_conservati": ("Backup da conservare", 1, 365, 14),
    "anticipo_quietanze_giorni": ("Anticipo emissione quietanze (giorni)", 0, 120, 30),
    "tolleranza_scadenza_giorni": ("Tolleranza prima di segnare la polizza scaduta (giorni)", 0, 180, 30),
    "preavviso_rate_giorni": ("Preavviso delle rate da far pagare (giorni)", 1, 90, 15),
}

# Automatismi sulle date (vedi gestionale/automatismi.py).
CAMPI_AUTOMATISMI = {
    "rinnovo_tacito_automatico": "Rinnovo tacito automatico",
    "emissione_quietanze_automatica": "Emissione automatica delle quietanze",
    "anticipo_quietanze_giorni": "Anticipo emissione quietanze",
    "scadenza_automatica": "Scadenza automatica delle polizze non rinnovate",
    "tolleranza_scadenza_giorni": "Tolleranza dopo la scadenza",
    "preavvisi_scadenze": "Preavvisi delle scadenze annuali",
    "preavviso_rate_giorni": "Preavviso delle rate",
}


def _leggi_intero(nome: str, errori: list[str]) -> int | None:
    """Intero dal form entro i limiti di CAMPI_INTERI; campo vuoto → valore predefinito."""
    etichetta, minimo, massimo, predefinito = CAMPI_INTERI[nome]
    grezzo = (request.form.get(nome) or "").strip()
    if not grezzo:
        return predefinito
    valore = parse_int(grezzo, minimo=minimo, massimo=massimo)
    if valore is None:
        errori.append(f"{etichetta}: inserisci un numero intero tra {minimo} e {massimo}.")
    return valore


def _mostra_errori(errori: list[str]) -> None:
    for errore in errori:
        flash(errore, "danger")


def _apply_form(s: Settings) -> list[str]:
    """Aggiorna la configurazione email dai campi del form e salva.

    Restituisce gli errori di validazione: se ce ne sono non viene salvato nulla.
    """
    errori: list[str] = []
    porta = _leggi_intero("smtp_port", errori)
    intervallo = _leggi_intero("intervallo_minuti", errori)
    if errori:
        return errori
    s.email_attive = request.form.get("email_attive") == "on"
    s.smtp_host = (request.form.get("smtp_host") or "").strip()
    s.smtp_port = porta
    security = request.form.get("smtp_security")
    s.smtp_security = security if security in dict(SECURITY_CHOICES) else "tls"
    s.smtp_user = (request.form.get("smtp_user") or "").strip()
    # La password si aggiorna solo se il campo è stato compilato: così lasciare
    # il campo vuoto non cancella una password già salvata.
    nuova_pw = request.form.get("smtp_password")
    if nuova_pw:
        s.smtp_password = nuova_pw
    s.mail_from = (request.form.get("mail_from") or "").strip()
    s.mail_to = (request.form.get("mail_to") or "").strip()
    s.intervallo_minuti = intervallo
    audit("modifica", "impostazioni", None, "Aggiornate le impostazioni delle notifiche email")
    db.session.commit()
    return []


def _scheduler_attivo() -> bool:
    """Se il thread dei controlli automatici (email e backup) è in esecuzione."""
    from .. import scheduler

    thread = scheduler._thread
    return bool(thread is not None and thread.is_alive())


@bp.route("/", methods=["GET"])
def edit():
    s = Settings.get()
    cfg = effective_config(s)
    return render_template(
        "settings/form.html",
        s=s,
        cfg=cfg,
        security_choices=SECURITY_CHOICES,
        campi_interi=CAMPI_INTERI,
        pending=contatore_pending(),
        scheduler_attivo=_scheduler_attivo(),
        backup_supportato=backup.supportato(),
        backup_elenco=backup.elenco_backup()[:30],
        backup_cartella=backup.cartella_backup(),
        backup_futuro=bool(s.ultimo_backup_at and s.ultimo_backup_at > now()),
        pre_ripristino_conservati=backup.PRE_RIPRISTINO_CONSERVATI,
    )


@bp.route("/", methods=["POST"])
def save():
    errori = _apply_form(Settings.get())
    if errori:
        _mostra_errori(errori)
    else:
        flash("Impostazioni salvate.", "success")
    return redirect(url_for("settings.edit") + "#email")


@bp.route("/studio", methods=["POST"])
def save_studio():
    s = Settings.get()
    s.studio_nome = clean(request.form, "studio_nome")
    s.studio_rui = clean(request.form, "studio_rui", upper=True)
    s.studio_piva = clean(request.form, "studio_piva")
    s.studio_indirizzo = clean(request.form, "studio_indirizzo")
    s.studio_contatti = clean(request.form, "studio_contatti")
    audit("modifica", "impostazioni", None, "Aggiornati i dati dello studio")
    db.session.commit()
    flash("Dati dello studio salvati.", "success")
    return redirect(url_for("settings.edit"))


@bp.route("/prova", methods=["POST"])
def test_email():
    # Salviamo i dati appena inseriti, poi proviamo l'invio con quei parametri.
    errori = _apply_form(Settings.get())
    if errori:
        _mostra_errori(errori)
        return redirect(url_for("settings.edit") + "#email")
    ok, messaggio = send_test_email()
    flash(messaggio, "success" if ok else "danger")
    return redirect(url_for("settings.edit") + "#email")


@bp.route("/invia-ora", methods=["POST"])
def send_now():
    s = Settings.get()
    if not s.email_attive:
        flash("Le notifiche via email sono disattivate: attivale per inviare.", "warning")
        return redirect(url_for("settings.edit") + "#email")
    try:
        inviate = send_pending_notifications(s)
    except Exception as exc:  # noqa: BLE001
        db.session.rollback()
        flash(f"Invio non riuscito: {exc}", "danger")
        return redirect(url_for("settings.edit") + "#email")
    if inviate:
        flash(f"Inviata 1 email con {inviate} notific{'a' if inviate == 1 else 'he'}.", "success")
    else:
        flash("Nessuna notifica da inviare al momento.", "info")
    return redirect(url_for("settings.edit") + "#email")


# ----------------------------------------------------------------------
# Automatismi sulle date
# ----------------------------------------------------------------------
def _descrivi(valore) -> str:
    if isinstance(valore, bool):
        return "attivo" if valore else "disattivato"
    if valore is None:
        return "—"
    return f"{valore} giorni"


@bp.route("/automatismi", methods=["POST"])
def save_automatismi():
    s = Settings.get()
    errori: list[str] = []
    nuovi = {
        "rinnovo_tacito_automatico": request.form.get("rinnovo_tacito_automatico") == "on",
        "emissione_quietanze_automatica": request.form.get("emissione_quietanze_automatica") == "on",
        "anticipo_quietanze_giorni": _leggi_intero("anticipo_quietanze_giorni", errori),
        "scadenza_automatica": request.form.get("scadenza_automatica") == "on",
        "tolleranza_scadenza_giorni": _leggi_intero("tolleranza_scadenza_giorni", errori),
        "preavviso_rate_giorni": _leggi_intero("preavviso_rate_giorni", errori),
    }
    testo_preavvisi = (request.form.get("preavvisi_scadenze") or "").strip()
    preavvisi = leggi_preavvisi(testo_preavvisi)
    if testo_preavvisi and not preavvisi:
        errori.append("Preavvisi delle scadenze: indica da 1 a 5 numeri di giorni tra 1 e 365, separati da virgola (es. 60, 30, 7).")
    nuovi["preavvisi_scadenze"] = ", ".join(str(g) for g in preavvisi) if preavvisi else "60, 30, 7"
    if leggi_preavvisi(s.preavvisi_scadenze) == leggi_preavvisi(nuovi["preavvisi_scadenze"]):
        nuovi["preavvisi_scadenze"] = s.preavvisi_scadenze  # stessi giorni: nessuna modifica
    if errori:
        _mostra_errori(errori)
        return redirect(url_for("settings.edit") + "#automatismi")
    modifiche = []
    for campo, valore in nuovi.items():
        vecchio = getattr(s, campo)
        if vecchio != valore:
            modifiche.append(f"{CAMPI_AUTOMATISMI[campo]}: {_descrivi(vecchio)} → {_descrivi(valore)}")
            setattr(s, campo, valore)
    if modifiche:
        audit("modifica", "impostazioni", None, "Automatismi aggiornati. " + "; ".join(modifiche))
        db.session.commit()
        flash("Impostazioni degli automatismi salvate.", "success")
    else:
        flash("Nessuna modifica agli automatismi.", "info")
    return redirect(url_for("settings.edit") + "#automatismi")


# ----------------------------------------------------------------------
# Backup e ripristino
# ----------------------------------------------------------------------
@bp.route("/backup/opzioni", methods=["POST"])
def backup_options():
    s = Settings.get()
    errori: list[str] = []
    conservati = _leggi_intero("backup_conservati", errori)
    if errori:
        _mostra_errori(errori)
        return redirect(url_for("settings.edit") + "#backup")
    s.backup_automatico = request.form.get("backup_automatico") == "on"
    s.backup_conservati = conservati
    audit("modifica", "impostazioni", None,
          f"Backup automatico {'attivo' if s.backup_automatico else 'disattivato'}, conservati {s.backup_conservati}")
    db.session.commit()
    flash("Opzioni di backup salvate.", "success")
    return redirect(url_for("settings.edit") + "#backup")


@bp.route("/backup/scarica", methods=["POST"])
def download_backup():
    """Crea al momento un backup completo e lo scarica.

    L'archivio è scritto in un file temporaneo anonimo: il sistema lo elimina
    alla chiusura (anche su Windows, dove un file aperto non si può cancellare),
    così nessuna copia dei dati resta nella cartella temporanea.
    """
    if not backup.supportato():
        flash("Il backup integrato è disponibile solo con database SQLite.", "warning")
        return redirect(url_for("settings.edit") + "#backup")
    contenuto = tempfile.TemporaryFile(suffix=".zip")
    try:
        backup.scrivi_backup(contenuto)
    except backup.BackupError as exc:
        contenuto.close()
        flash(str(exc), "danger")
        return redirect(url_for("settings.edit") + "#backup")
    except BaseException:
        contenuto.close()
        raise
    contenuto.seek(0)
    audit("backup", "sistema", None, "Scaricato un backup completo", commit=True)
    return send_file(contenuto, as_attachment=True, download_name=backup.nome_archivio(),
                     mimetype="application/zip")


@bp.route("/backup/esegui", methods=["POST"])
def run_backup():
    try:
        percorso = backup.backup_automatico(forza=True)
    except backup.BackupError as exc:
        flash(str(exc), "danger")
    else:
        if percorso:
            audit("backup", "sistema", None, f"Backup salvato: {os.path.basename(percorso)}", commit=True)
            flash(f"Backup salvato in {percorso}.", "success")
        else:
            flash("Il backup integrato è disponibile solo con database SQLite.", "warning")
    return redirect(url_for("settings.edit") + "#backup")


@bp.route("/backup/file/<path:nome>")
def backup_file(nome):
    nome = secure_filename(nome)
    if not nome.endswith(".zip") or not nome.startswith((backup.PREFISSO_FILE, backup.PREFISSO_PRE_RIPRISTINO)):
        return redirect(url_for("settings.edit") + "#backup")
    audit("backup", "sistema", None, f"Scaricato il backup {nome}", commit=True)
    return send_from_directory(backup.cartella_backup(), nome, as_attachment=True)


@bp.route("/backup/ripristina", methods=["POST"])
def restore_backup():
    file = request.files.get("archivio")
    if not file or not file.filename:
        flash("Seleziona l'archivio di backup (.zip) da ripristinare.", "warning")
        return redirect(url_for("settings.edit") + "#backup")
    if request.form.get("conferma") != "RIPRISTINA":
        flash("Per confermare il ripristino scrivi RIPRISTINA nell'apposito campo.", "warning")
        return redirect(url_for("settings.edit") + "#backup")
    # Il database sta per essere sostituito: annotiamo prima chi esegue il ripristino.
    utente_id, username = g.user.id, g.user.username
    try:
        esito = backup.ripristina_backup(file)
    except backup.BackupError as exc:
        db.session.rollback()
        flash(f"Ripristino annullato: {exc}", "danger")
        return redirect(url_for("settings.edit") + "#backup")
    db.session.add(AuditLog(
        user_id=None, username=username, azione="ripristino", entita="sistema", ip=request.remote_addr,
        descrizione=f"Ripristinato il backup «{file.filename}» da utente #{utente_id} "
                    f"(backup di sicurezza: {esito['backup_sicurezza']})"[:500],
    ))
    db.session.commit()
    # Tutte le sessioni sono state invalidate dal ripristino, compresa questa.
    g.user = None
    session.clear()
    flash(
        f"Backup ripristinato ({esito['documenti']} documenti). Copia di sicurezza dei dati precedenti: "
        f"{esito['backup_sicurezza']}. Per sicurezza tutti gli utenti sono stati disconnessi: accedi di "
        "nuovo con le credenziali presenti nel backup.",
        "success",
    )
    if esito.get("documenti_saltati"):
        flash(f"{esito['documenti_saltati']} file dell'archivio con nome non valido non sono stati ripristinati.",
              "warning")
    return redirect(url_for("auth.login"))


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
    current_app.config["DC_IN_PAUSA"] = False
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
        gcal_configurato=google_calendar.configurato(s),
        gcal_collegato=google_calendar.collegato(s),
        gcal_ritorno=_ritorno_calendar(),
        gcal_eventi=CalendarioEvento.query.count(),
    )


# ----------------------------------------------------------------------
# Google Calendar collegato direttamente (vedi gestionale/google_calendar.py)
# ----------------------------------------------------------------------
def _ritorno_calendar() -> str:
    """Indirizzo a cui Google rimanda dopo il consenso (questo PC, porta attuale)."""
    return request.host_url.rstrip("/") + url_for("settings.calendar_return")


@bp.route("/google/calendar", methods=["POST"])
def calendar_settings():
    s = Settings.get()
    azione = request.form.get("azione")
    if azione == "credenziali":
        client_id = (request.form.get("client_id") or "").strip()
        segreto = (request.form.get("client_secret") or "").strip()
        if not client_id.endswith(".apps.googleusercontent.com"):
            flash("L'ID client non sembra giusto: finisce con «.apps.googleusercontent.com». "
                  "Copialo da Google Cloud → Credenziali.", "danger")
            return redirect(url_for("settings.google") + "#calendar")
        if client_id != s.gcal_client_id:
            s.gcal_refresh_token = None  # nuove credenziali: va rifatto il collegamento
        s.gcal_client_id = client_id[:200]
        if segreto:
            s.gcal_client_secret = segreto[:200]
        audit("modifica", "impostazioni", None, "Credenziali di Google Calendar aggiornate")
        db.session.commit()
        flash("Credenziali salvate. Ora premi «Collega Google Calendar».", "success")
    elif azione == "collega":
        try:
            indirizzo = google_calendar.url_autorizzazione(s, _ritorno_calendar())
        except google_calendar.CalendarError as exc:
            flash(str(exc), "danger")
            return redirect(url_for("settings.google") + "#calendar")
        if current_app.config.get("DC_FINESTRA"):
            # Google non accetta l'accesso dentro le finestre dei programmi:
            # si apre il browser e il ritorno arriva comunque qui.
            import webbrowser

            webbrowser.open(indirizzo)
            flash("Si è aperto il browser: accedi con il tuo account Google e consenti l'accesso. "
                  "Poi torna qui e aggiorna la pagina.", "info")
            return redirect(url_for("settings.google") + "#calendar")
        return redirect(indirizzo)
    elif azione == "sincronizza":
        try:
            esito = google_calendar.sincronizza(base_url=request.host_url)
        except google_calendar.CalendarError as exc:
            flash(f"Sincronizzazione non riuscita: {exc}", "danger")
        else:
            flash(f"Google Calendar aggiornato: {esito['creati']} eventi nuovi, {esito['aggiornati']} aggiornati, "
                  f"{esito['eliminati']} tolti.", "success")
    elif azione == "scollega":
        google_calendar.scollega(s)
        audit("modifica", "impostazioni", None, "Google Calendar scollegato")
        db.session.commit()
        flash("Google Calendar scollegato. Gli eventi già scritti restano nel calendario «Deal Combined»: "
              "se non ti servono, elimina quel calendario da Google Calendar.", "info")
    return redirect(url_for("settings.google") + "#calendar")


@bp.route("/google/calendar/ritorno")
def calendar_return():
    """Google rimanda qui dopo il consenso (anche nel browser esterno, senza
    sessione del programma): la richiesta è riconosciuta dal codice «state»."""
    s = Settings.get()
    errore = request.args.get("error")
    try:
        if errore:
            raise google_calendar.CalendarError("Accesso non concesso su Google." if errore == "access_denied"
                                                else f"Google ha risposto: {errore}.")
        google_calendar.completa_autorizzazione(s, request.args.get("state"), request.args.get("code"))
        esito = google_calendar.sincronizza(base_url=request.host_url)
        messaggio = (f"Google Calendar collegato. Nel calendario «{google_calendar.NOME_CALENDARIO}» ci sono ora "
                     f"{esito['creati'] + esito['aggiornati']} eventi: scadenze, rate, follow-up e promemoria.")
        ok = True
    except google_calendar.CalendarError as exc:
        messaggio, ok = str(exc), False
    return render_template("settings/calendar_ritorno.html", messaggio=messaggio, ok=ok)


# ----------------------------------------------------------------------
# Aggiornamenti (Release di GitHub)
# ----------------------------------------------------------------------
def controlla_aggiornamenti(app) -> None:
    """Controlla se c'è una versione nuova e ne salva l'esito in app.config.
    Pensata per girare in un thread all'avvio: un errore di rete non deve
    disturbare l'utente, viene solo annotato."""
    from .. import __version__, aggiornamenti

    app.config["DC_NESSUNA_RELEASE"] = False
    try:
        app.config["DC_AGGIORNAMENTO"] = aggiornamenti.controlla(__version__)
        app.config["DC_AGGIORNAMENTO_ERRORE"] = None
    except aggiornamenti.NessunaVersionePubblicata:
        app.config["DC_AGGIORNAMENTO"] = None
        app.config["DC_AGGIORNAMENTO_ERRORE"] = None
        app.config["DC_NESSUNA_RELEASE"] = True
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
            elif current_app.config.get("DC_NESSUNA_RELEASE"):
                flash("Su GitHub non è ancora stata pubblicata nessuna versione da installare: "
                      "per ora gli aggiornamenti si installano a mano.", "info")
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
        nessuna_release=current_app.config.get("DC_NESSUNA_RELEASE"),
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


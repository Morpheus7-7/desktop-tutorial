"""Impostazioni (solo amministratori): dati dello studio, notifiche via email
(SMTP), automatismi sulle date e backup/ripristino."""
import os
import tempfile

from flask import (
    Blueprint,
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

from .. import backup
from ..mailer import contatore_pending, effective_config, send_pending_notifications, send_test_email
from ..models import AuditLog, Settings, db, now
from ..security import audit, require_admin
from ..utils import clean, parse_int

bp = Blueprint("settings", __name__, url_prefix="/impostazioni")
bp.before_request(require_admin)

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
}

# Automatismi sulle date (vedi gestionale/automatismi.py).
CAMPI_AUTOMATISMI = {
    "rinnovo_tacito_automatico": "Rinnovo tacito automatico",
    "emissione_quietanze_automatica": "Emissione automatica delle quietanze",
    "anticipo_quietanze_giorni": "Anticipo emissione quietanze",
    "scadenza_automatica": "Scadenza automatica delle polizze non rinnovate",
    "tolleranza_scadenza_giorni": "Tolleranza dopo la scadenza",
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
    }
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

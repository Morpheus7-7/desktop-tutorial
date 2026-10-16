"""Impostazioni (solo amministratori): dati dello studio, notifiche via email
(SMTP) e backup/ripristino."""
import os
import tempfile

from flask import (
    Blueprint,
    after_this_request,
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

from .. import backup
from ..mailer import contatore_pending, effective_config, send_pending_notifications, send_test_email
from ..models import AuditLog, Settings, db
from ..security import audit, require_admin
from ..utils import clean

bp = Blueprint("settings", __name__, url_prefix="/impostazioni")
bp.before_request(require_admin)

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
    """Aggiorna la configurazione email dai campi del form e salva."""
    s.email_attive = request.form.get("email_attive") == "on"
    s.smtp_host = (request.form.get("smtp_host") or "").strip()
    s.smtp_port = _parse_int(request.form.get("smtp_port"), 587)
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
    s.intervallo_minuti = max(1, _parse_int(request.form.get("intervallo_minuti"), 30))
    audit("modifica", "impostazioni", None, "Aggiornate le impostazioni delle notifiche email")
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
        backup_supportato=backup.supportato(),
        backup_elenco=backup.elenco_backup()[:30],
        backup_cartella=current_app.config["BACKUP_FOLDER"],
    )


@bp.route("/", methods=["POST"])
def save():
    _apply_form(Settings.get())
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
    _apply_form(Settings.get())
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
        flash(f"Invio non riuscito: {exc}", "danger")
        return redirect(url_for("settings.edit") + "#email")
    if inviate:
        flash(f"Inviata 1 email con {inviate} notifiche.", "success")
    else:
        flash("Nessuna notifica da inviare al momento.", "info")
    return redirect(url_for("settings.edit") + "#email")


# ----------------------------------------------------------------------
# Backup e ripristino
# ----------------------------------------------------------------------
@bp.route("/backup/opzioni", methods=["POST"])
def backup_options():
    s = Settings.get()
    s.backup_automatico = request.form.get("backup_automatico") == "on"
    s.backup_conservati = min(365, max(1, _parse_int(request.form.get("backup_conservati"), 14)))
    audit("modifica", "impostazioni", None,
          f"Backup automatico {'attivo' if s.backup_automatico else 'disattivato'}, conservati {s.backup_conservati}")
    db.session.commit()
    flash("Opzioni di backup salvate.", "success")
    return redirect(url_for("settings.edit") + "#backup")


@bp.route("/backup/scarica", methods=["POST"])
def download_backup():
    """Crea al momento un backup completo e lo scarica."""
    if not backup.supportato():
        flash("Il backup integrato è disponibile solo con database SQLite.", "warning")
        return redirect(url_for("settings.edit") + "#backup")
    fd, percorso = tempfile.mkstemp(suffix=".zip")
    os.close(fd)
    backup.crea_backup(percorso)
    audit("backup", "sistema", None, "Scaricato un backup completo", commit=True)

    @after_this_request
    def _pulisci(response):
        try:
            os.remove(percorso)
        except OSError:  # pragma: no cover - su Windows il file può essere ancora aperto
            pass
        return response

    return send_file(percorso, as_attachment=True, download_name=backup.nome_archivio(),
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
    if not nome.endswith(".zip"):
        return redirect(url_for("settings.edit") + "#backup")
    audit("backup", "sistema", None, f"Scaricato il backup {nome}", commit=True)
    return send_from_directory(current_app.config["BACKUP_FOLDER"], nome, as_attachment=True)


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
        flash(f"Ripristino annullato: {exc}", "danger")
        return redirect(url_for("settings.edit") + "#backup")
    db.session.add(AuditLog(
        user_id=None, username=username, azione="ripristino", entita="sistema", ip=request.remote_addr,
        descrizione=f"Ripristinato il backup «{file.filename}» da utente #{utente_id} "
                    f"(backup di sicurezza: {esito['backup_sicurezza']})",
    ))
    db.session.commit()
    g.user = None
    session.clear()
    flash(
        f"Backup ripristinato ({esito['documenti']} documenti). Copia di sicurezza dei dati precedenti: "
        f"{esito['backup_sicurezza']}. Accedi di nuovo con le credenziali presenti nel backup.",
        "success",
    )
    return redirect(url_for("auth.login"))

"""Impostazioni applicative: configurazione notifiche via email (SMTP)."""
from flask import Blueprint, flash, redirect, render_template, request, url_for

from ..mailer import contatore_pending, effective_config, send_pending_notifications, send_test_email
from ..models import Settings, db

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
    # --- Analisi AI ---
    s.ai_attiva = request.form.get("ai_attiva") == "on"
    s.ai_modello = request.form.get("ai_modello") or "claude-opus-5"
    nuova_chiave = request.form.get("anthropic_api_key")
    if nuova_chiave:  # come per la password: si aggiorna solo se compilata
        s.anthropic_api_key = nuova_chiave.strip()
    db.session.commit()


AI_MODELS = [
    ("claude-opus-5", "Opus 5 — massima qualità"),
    ("claude-sonnet-5", "Sonnet 5 — equilibrato"),
    ("claude-haiku-4-5", "Haiku 4.5 — economico e veloce"),
]


@bp.route("/", methods=["GET"])
def edit():
    from ..ai_analysis import ai_disponibile, sdk_disponibile

    s = Settings.get()
    cfg = effective_config(s)
    return render_template(
        "settings/form.html",
        s=s,
        cfg=cfg,
        security_choices=SECURITY_CHOICES,
        pending=contatore_pending(),
        ai_models=AI_MODELS,
        ai_sdk=sdk_disponibile(),
        ai_pronta=ai_disponibile(s),
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

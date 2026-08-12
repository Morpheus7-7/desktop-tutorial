"""Invio delle notifiche via email (SMTP, solo libreria standard).

Il modulo non introduce dipendenze esterne: usa ``smtplib`` e
``email.message`` della libreria standard, così l'eseguibile impacchettato
resta leggero.

La configurazione SMTP arriva dalla tabella ``Settings`` (modificabile dalla
pagina «Impostazioni»); le variabili d'ambiente omonime, se presenti, hanno la
precedenza — utile per non salvare la password nel database in produzione.
"""
from __future__ import annotations

import os
import smtplib
import ssl
from dataclasses import dataclass, field
from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr

from flask import current_app

from .models import LIVELLO_ORDINE, Notification, Settings, db


@dataclass
class MailConfig:
    """Configurazione SMTP effettiva (Settings + override da ambiente)."""

    host: str = ""
    port: int = 587
    security: str = "tls"  # tls | ssl | none
    user: str = ""
    password: str = ""
    mittente: str = ""
    destinatari: list[str] = field(default_factory=list)

    @property
    def valida(self) -> bool:
        return bool(self.host and self.destinatari)


def _env(name: str, default: str | None = None) -> str | None:
    val = os.environ.get(name)
    return val if val not in (None, "") else default


def effective_config(settings: Settings | None = None) -> MailConfig:
    """Costruisce la configurazione effettiva unendo Settings e ambiente."""
    settings = settings or Settings.get()

    destinatari_env = _env("MAIL_TO")
    destinatari = (
        [d.strip() for d in destinatari_env.replace(";", ",").split(",") if d.strip()]
        if destinatari_env
        else settings.destinatari
    )

    mittente = _env("MAIL_FROM") or settings.mail_from or _env("SMTP_USER") or settings.smtp_user or ""

    try:
        porta = int(_env("SMTP_PORT") or settings.smtp_port or 587)
    except (TypeError, ValueError):
        porta = 587

    return MailConfig(
        host=_env("SMTP_HOST") or settings.smtp_host or "",
        port=porta,
        security=(_env("SMTP_SECURITY") or settings.smtp_security or "tls").lower(),
        user=_env("SMTP_USER") or settings.smtp_user or "",
        password=_env("SMTP_PASSWORD") or settings.smtp_password or "",
        mittente=mittente,
        destinatari=destinatari,
    )


def email_attive(settings: Settings | None = None) -> bool:
    """Se le notifiche email sono attive (Settings, con override da ambiente)."""
    settings = settings or Settings.get()
    env = _env("EMAIL_ATTIVE")
    if env is not None:
        return env.strip().lower() in ("1", "true", "yes", "si", "sì", "on")
    return bool(settings.email_attive)


# ----------------------------------------------------------------------
# Invio SMTP
# ----------------------------------------------------------------------
def _build_message(cfg: MailConfig, subject: str, text_body: str, html_body: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = formataddr(("Gestionale Assicurativo", cfg.mittente or cfg.user))
    msg["To"] = ", ".join(cfg.destinatari)
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")
    return msg


def _send(cfg: MailConfig, msg: EmailMessage, timeout: int = 20) -> None:
    """Consegna il messaggio via SMTP. Solleva eccezione in caso di errore."""
    if cfg.security == "ssl":
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(cfg.host, cfg.port, timeout=timeout, context=context) as server:
            if cfg.user:
                server.login(cfg.user, cfg.password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(cfg.host, cfg.port, timeout=timeout) as server:
            server.ehlo()
            if cfg.security == "tls":
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
            if cfg.user:
                server.login(cfg.user, cfg.password)
            server.send_message(msg)


def send_test_email(settings: Settings | None = None) -> tuple[bool, str]:
    """Invia un'email di prova. Ritorna (successo, messaggio per l'utente)."""
    cfg = effective_config(settings)
    if not cfg.valida:
        return False, "Configurazione incompleta: servono almeno server SMTP e un destinatario."
    ora = datetime.now().strftime("%d/%m/%Y %H:%M")
    text_body = (
        "Email di prova dal Gestionale Assicurativo.\n\n"
        f"Se leggi questo messaggio la configurazione SMTP funziona ({ora})."
    )
    html_body = _wrap_html(
        "Email di prova",
        f"<p>Se leggi questo messaggio la configurazione SMTP del "
        f"<strong>Gestionale Assicurativo</strong> funziona correttamente.</p>"
        f"<p class='muted'>Inviata il {ora}.</p>",
    )
    try:
        _send(cfg, _build_message(cfg, "Gestionale Assicurativo — email di prova", text_body, html_body))
        return True, f"Email di prova inviata a {', '.join(cfg.destinatari)}."
    except Exception as exc:  # noqa: BLE001 — mostriamo l'errore all'utente
        return False, f"Invio non riuscito: {exc}"


# ----------------------------------------------------------------------
# Digest delle notifiche
# ----------------------------------------------------------------------
def _base_url() -> str:
    return (os.environ.get("APP_BASE_URL") or "").rstrip("/")


def _pending_query():
    return (
        Notification.query.filter_by(inviata_email=False)
        .order_by(Notification.created_at.desc())
        .all()
    )


def _wrap_html(titolo: str, corpo: str) -> str:
    return f"""\
<!doctype html><html lang="it"><head><meta charset="utf-8"></head>
<body style="margin:0;background:#f4f6fb;font-family:Segoe UI,Arial,sans-serif;color:#1f2933;">
  <div style="max-width:640px;margin:0 auto;padding:24px;">
    <div style="background:#0d6efd;color:#fff;padding:16px 20px;border-radius:10px 10px 0 0;">
      <div style="font-size:18px;font-weight:700;">🛡️ Gestionale Assicurativo</div>
      <div style="opacity:.85;font-size:13px;">{titolo}</div>
    </div>
    <div style="background:#fff;padding:20px;border-radius:0 0 10px 10px;border:1px solid #e5e9f2;border-top:none;">
      {corpo}
    </div>
    <p style="color:#9aa5b1;font-size:12px;text-align:center;margin-top:16px;">
      Messaggio automatico del Gestionale Assicurativo.
    </p>
  </div>
</body></html>"""


def build_digest(notifiche: list[Notification]) -> tuple[str, str, str]:
    """Costruisce (oggetto, testo, html) per un elenco di notifiche."""
    base = _base_url()
    n = len(notifiche)
    urgenti = sum(1 for x in notifiche if x.livello == "danger")

    subject = f"Gestionale Assicurativo — {n} notific{'a' if n == 1 else 'he'}"
    if urgenti:
        subject += f" ({urgenti} urgent{'e' if urgenti == 1 else 'i'})"

    ordinate = sorted(
        notifiche,
        key=lambda x: (LIVELLO_ORDINE.get(x.livello, 9), x.created_at or datetime.min),
    )

    # --- testo semplice ---
    righe = ["Riepilogo notifiche dal Gestionale Assicurativo:", ""]
    etichetta = {"danger": "[URGENTE]", "warning": "[ATTENZIONE]", "info": "[INFO]"}
    for x in ordinate:
        righe.append(f"{etichetta.get(x.livello, '[INFO]')} {x.messaggio}")
    text_body = "\n".join(righe)

    # --- html ---
    colore = {"danger": "#dc3545", "warning": "#fd7e14", "info": "#0d6efd"}
    items = []
    for x in ordinate:
        col = colore.get(x.livello, "#0d6efd")
        link_html = ""
        if x.link and base:
            link_html = (
                f"<div style='margin-top:4px;'>"
                f"<a href='{base}{x.link}' style='color:#0d6efd;font-size:13px;'>Apri la scheda cliente →</a>"
                f"</div>"
            )
        items.append(
            f"<li style='list-style:none;margin:0 0 10px;padding:12px 14px;"
            f"border-left:4px solid {col};background:#f8f9fc;border-radius:6px;'>"
            f"<div style='font-size:14px;'>{x.messaggio}</div>{link_html}</li>"
        )
    corpo = (
        f"<p>Hai <strong>{n}</strong> notific{'a' if n == 1 else 'he'} da controllare"
        + (f", di cui <strong>{urgenti}</strong> urgent{'e' if urgenti == 1 else 'i'}" if urgenti else "")
        + ".</p><ul style='padding:0;margin:12px 0 0;'>"
        + "".join(items)
        + "</ul>"
    )
    html_body = _wrap_html("Riepilogo scadenze e follow-up", corpo)
    return subject, text_body, html_body


def send_pending_notifications(settings: Settings | None = None) -> int:
    """Invia un digest delle notifiche non ancora spedite e le marca.

    Va chiamata dentro un app context. Ritorna il numero di notifiche incluse
    nell'email inviata (0 se non c'è nulla da inviare o le email sono disattive).
    """
    settings = settings or Settings.get()
    if not email_attive(settings):
        return 0
    cfg = effective_config(settings)
    if not cfg.valida:
        return 0

    pending = _pending_query()
    if not pending:
        return 0

    subject, text_body, html_body = build_digest(pending)
    _send(cfg, _build_message(cfg, subject, text_body, html_body))

    ora = datetime.utcnow()
    for x in pending:
        x.inviata_email = True
        x.inviata_email_at = ora
    db.session.commit()
    current_app.logger.info("Inviato digest email con %d notifiche.", len(pending))
    return len(pending)


def contatore_pending() -> int:
    """Quante notifiche sono in attesa di essere inviate via email."""
    return Notification.query.filter_by(inviata_email=False).count()

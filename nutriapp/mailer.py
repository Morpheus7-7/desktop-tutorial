"""Invio email: solo libreria standard (smtplib), nessuna dipendenza esterna.

Due famiglie di messaggi:

* le **email transazionali** — credenziali di accesso, piano pubblicato, lista
  della spesa — che partono subito e vanno a un destinatario preciso;
* il **digest delle notifiche** per la nutrizionista, inviato dallo scheduler a
  intervalli regolari e mai due volte per la stessa notifica.

La configurazione SMTP arriva dalle Impostazioni; le variabili d'ambiente
omonime, se presenti, hanno la precedenza (utile per non tenere la password nel
database in produzione).
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

from .models import LIVELLO_ORDINE, Notifica, Settings, db


@dataclass
class MailConfig:
    host: str = ""
    port: int = 587
    security: str = "tls"  # tls | ssl | none
    user: str = ""
    password: str = ""
    mittente: str = ""
    destinatari: list[str] = field(default_factory=list)
    studio: str = "NutriStudio"

    @property
    def valida(self) -> bool:
        return bool(self.host and self.mittente)

    @property
    def valida_per_digest(self) -> bool:
        return self.valida and bool(self.destinatari)


def _env(nome: str, default: str | None = None) -> str | None:
    valore = os.environ.get(nome)
    return valore if valore not in (None, "") else default


def effective_config(settings: Settings | None = None) -> MailConfig:
    settings = settings or Settings.get()

    destinatari_env = _env("MAIL_TO")
    destinatari = (
        [d.strip() for d in destinatari_env.replace(";", ",").split(",") if d.strip()]
        if destinatari_env
        else settings.destinatari
    )
    mittente = (
        _env("MAIL_FROM")
        or settings.mail_from
        or _env("SMTP_USER")
        or settings.smtp_user
        or ""
    )
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
        studio=settings.nome_studio or "NutriStudio",
    )


def email_attive(settings: Settings | None = None) -> bool:
    settings = settings or Settings.get()
    env = _env("EMAIL_ATTIVE")
    if env is not None:
        return env.strip().lower() in ("1", "true", "yes", "si", "sì", "on")
    return bool(settings.email_attive)


# ----------------------------------------------------------------------
# Consegna
# ----------------------------------------------------------------------
def _messaggio(cfg: MailConfig, destinatari: list[str], oggetto: str, testo: str, html: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = oggetto
    msg["From"] = formataddr((cfg.studio, cfg.mittente or cfg.user))
    msg["To"] = ", ".join(destinatari)
    msg.set_content(testo)
    msg.add_alternative(html, subtype="html")
    return msg


def _consegna(cfg: MailConfig, msg: EmailMessage, timeout: int = 20) -> None:
    if cfg.security == "ssl":
        contesto = ssl.create_default_context()
        with smtplib.SMTP_SSL(cfg.host, cfg.port, timeout=timeout, context=contesto) as server:
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


def invia(destinatari: list[str], oggetto: str, testo: str, html: str,
          settings: Settings | None = None, forza: bool = False) -> tuple[bool, str]:
    """Invia un messaggio. Ritorna (successo, spiegazione per l'utente)."""
    settings = settings or Settings.get()
    destinatari = [d for d in destinatari if d]
    if not destinatari:
        return False, "Nessun destinatario: manca l'indirizzo email."
    if not forza and not email_attive(settings):
        return False, "Le notifiche via email non sono attive (Impostazioni)."
    cfg = effective_config(settings)
    if not cfg.valida:
        return False, "Configurazione SMTP incompleta: servono server e mittente."
    try:
        _consegna(cfg, _messaggio(cfg, destinatari, oggetto, testo, html))
        return True, f"Email inviata a {', '.join(destinatari)}."
    except Exception as exc:  # noqa: BLE001 — l'errore va mostrato a chi configura
        current_app.logger.warning("Invio email non riuscito: %s", exc)
        return False, f"Invio non riuscito: {exc}"


# ----------------------------------------------------------------------
# Impaginazione
# ----------------------------------------------------------------------
def _base_url() -> str:
    return (os.environ.get("APP_BASE_URL") or "").rstrip("/")


def _wrap_html(studio: str, titolo: str, corpo: str) -> str:
    return f"""\
<!doctype html><html lang="it"><head><meta charset="utf-8"></head>
<body style="margin:0;background:#f2f7f4;font-family:Segoe UI,Arial,sans-serif;color:#1f2933;">
  <div style="max-width:640px;margin:0 auto;padding:24px;">
    <div style="background:#2f8f5b;color:#fff;padding:18px 22px;border-radius:12px 12px 0 0;">
      <div style="font-size:19px;font-weight:700;">🥗 {studio}</div>
      <div style="opacity:.9;font-size:13px;">{titolo}</div>
    </div>
    <div style="background:#fff;padding:22px;border-radius:0 0 12px 12px;border:1px solid #dfe8e2;border-top:none;">
      {corpo}
    </div>
    <p style="color:#94a29a;font-size:12px;text-align:center;margin-top:16px;">
      Messaggio automatico di {studio}. Non rispondere a questo indirizzo.
    </p>
  </div>
</body></html>"""


def _bottone(url: str, testo: str) -> str:
    if not url:
        return ""
    return (
        f"<p style='margin:20px 0 4px;'><a href='{url}' style='background:#2f8f5b;color:#fff;"
        f"text-decoration:none;padding:11px 20px;border-radius:8px;font-weight:600;"
        f"display:inline-block;'>{testo}</a></p>"
    )


# ----------------------------------------------------------------------
# Email transazionali
# ----------------------------------------------------------------------
def invia_credenziali(utente, password_temporanea: str, settings: Settings | None = None) -> tuple[bool, str]:
    """Manda al cliente le credenziali della sua area riservata."""
    settings = settings or Settings.get()
    studio = settings.nome_studio or "NutriStudio"
    url = f"{_base_url()}/accedi" if _base_url() else "l'indirizzo dell'applicazione"

    testo = (
        f"Ciao {utente.nome},\n\n"
        f"{studio} ha aperto la tua area riservata: da lì trovi il piano alimentare, "
        f"le schede dei pasti, il ricettario e la lista della spesa.\n\n"
        f"Indirizzo: {url}\n"
        f"Email: {utente.email}\n"
        f"Password provvisoria: {password_temporanea}\n\n"
        "Ti verrà chiesto di sceglierne una nuova al primo accesso.\n"
    )
    corpo = (
        f"<p>Ciao <strong>{utente.nome}</strong>,</p>"
        f"<p>abbiamo aperto la tua area riservata: da lì trovi il piano alimentare giorno "
        f"per giorno, le schede dei pasti, il ricettario e la lista della spesa.</p>"
        f"<table style='margin:16px 0;font-size:14px;border-collapse:collapse;'>"
        f"<tr><td style='padding:4px 12px 4px 0;color:#6b7a72;'>Email</td>"
        f"<td style='padding:4px 0;'><strong>{utente.email}</strong></td></tr>"
        f"<tr><td style='padding:4px 12px 4px 0;color:#6b7a72;'>Password provvisoria</td>"
        f"<td style='padding:4px 0;'><code style='background:#eef4f0;padding:3px 8px;"
        f"border-radius:5px;'>{password_temporanea}</code></td></tr></table>"
        f"{_bottone(f'{_base_url()}/accedi' if _base_url() else '', 'Entra nella tua area')}"
        f"<p style='color:#6b7a72;font-size:13px;'>Al primo accesso ti verrà chiesto di "
        f"scegliere una password personale.</p>"
    )
    return invia(
        [utente.email],
        f"{studio} — le tue credenziali di accesso",
        testo,
        _wrap_html(studio, "Accesso all'area riservata", corpo),
        settings,
        forza=True,  # le credenziali partono anche se il digest è disattivo
    )


def invia_piano_pubblicato(piano, settings: Settings | None = None) -> tuple[bool, str]:
    """Avvisa il cliente che il suo nuovo piano è disponibile."""
    settings = settings or Settings.get()
    studio = settings.nome_studio or "NutriStudio"
    assistito = piano.assistito
    email = (assistito.utente.email if assistito.utente else None) or assistito.email
    if not email:
        return False, "L'assistito non ha un indirizzo email."

    periodo = f"dal {piano.data_inizio.strftime('%d/%m/%Y')} al {piano.data_fine.strftime('%d/%m/%Y')}"
    testo = (
        f"Ciao {assistito.nome},\n\n"
        f"il tuo nuovo piano «{piano.titolo}» è disponibile nella tua area riservata "
        f"({periodo}).\n\n"
        f"Target: circa {piano.target_kcal} kcal al giorno.\n"
        + (f"\nNota: {piano.note_cliente}\n" if piano.note_cliente else "")
    )
    corpo = (
        f"<p>Ciao <strong>{assistito.nome}</strong>,</p>"
        f"<p>il tuo nuovo piano <strong>«{piano.titolo}»</strong> è disponibile "
        f"nell'area riservata, {periodo}.</p>"
        f"<p style='background:#eef4f0;padding:12px 14px;border-radius:8px;font-size:14px;'>"
        f"Obiettivo indicativo: <strong>{piano.target_kcal} kcal al giorno</strong>"
        f"{' · ' + piano.tipo_dieta if piano.tipo_dieta else ''}</p>"
        + (
            f"<p style='border-left:3px solid #2f8f5b;padding-left:12px;color:#41524a;'>"
            f"{piano.note_cliente}</p>"
            if piano.note_cliente
            else ""
        )
        + _bottone(f"{_base_url()}/area/piano" if _base_url() else "", "Apri il piano")
    )
    return invia(
        [email],
        f"{studio} — il tuo nuovo piano alimentare",
        testo,
        _wrap_html(studio, "Nuovo piano pubblicato", corpo),
        settings,
    )


def invia_lista_spesa(piano, testo_lista: str, settings: Settings | None = None) -> tuple[bool, str]:
    """Manda al cliente la lista della spesa della settimana."""
    settings = settings or Settings.get()
    studio = settings.nome_studio or "NutriStudio"
    assistito = piano.assistito
    email = (assistito.utente.email if assistito.utente else None) or assistito.email
    if not email:
        return False, "L'assistito non ha un indirizzo email."

    html_lista = testo_lista.replace("\n", "<br>")
    corpo = (
        f"<p>Ciao <strong>{assistito.nome}</strong>, ecco la spesa per la settimana "
        f"del piano «{piano.titolo}».</p>"
        f"<div style='background:#f7faf8;border:1px solid #e2ebe6;border-radius:8px;"
        f"padding:14px;font-family:ui-monospace,Consolas,monospace;font-size:13px;"
        f"line-height:1.6;'>{html_lista}</div>"
        + _bottone(f"{_base_url()}/area/spesa" if _base_url() else "", "Apri la lista e i carrelli")
    )
    return invia(
        [email],
        f"{studio} — la tua lista della spesa",
        testo_lista,
        _wrap_html(studio, "Lista della spesa", corpo),
        settings,
    )


def invia_email_prova(settings: Settings | None = None) -> tuple[bool, str]:
    settings = settings or Settings.get()
    cfg = effective_config(settings)
    if not cfg.destinatari:
        return False, "Aggiungi almeno un destinatario nelle Impostazioni."
    ora = datetime.now().strftime("%d/%m/%Y %H:%M")
    corpo = (
        f"<p>Se leggi questo messaggio la configurazione SMTP di "
        f"<strong>{cfg.studio}</strong> funziona.</p>"
        f"<p style='color:#94a29a;font-size:13px;'>Inviata il {ora}.</p>"
    )
    return invia(
        cfg.destinatari,
        f"{cfg.studio} — email di prova",
        f"Email di prova da {cfg.studio}. Configurazione SMTP funzionante ({ora}).",
        _wrap_html(cfg.studio, "Email di prova", corpo),
        settings,
        forza=True,
    )


# ----------------------------------------------------------------------
# Digest delle notifiche per la nutrizionista
# ----------------------------------------------------------------------
def notifiche_da_inviare() -> list[Notifica]:
    return (
        Notifica.query.filter_by(inviata_email=False, destinatario="nutrizionista")
        .order_by(Notifica.created_at.desc())
        .all()
    )


def contatore_pending() -> int:
    return Notifica.query.filter_by(inviata_email=False, destinatario="nutrizionista").count()


def costruisci_digest(notifiche: list[Notifica], studio: str) -> tuple[str, str, str]:
    base = _base_url()
    n = len(notifiche)
    urgenti = sum(1 for x in notifiche if x.livello == "danger")

    oggetto = f"{studio} — {n} notific{'a' if n == 1 else 'he'}"
    if urgenti:
        oggetto += f" ({urgenti} urgent{'e' if urgenti == 1 else 'i'})"

    ordinate = sorted(
        notifiche, key=lambda x: (LIVELLO_ORDINE.get(x.livello, 9), x.created_at or datetime.min)
    )

    etichetta = {"danger": "[URGENTE]", "warning": "[ATTENZIONE]", "info": "[INFO]"}
    testo = "\n".join(
        [f"Riepilogo da {studio}:", ""]
        + [f"{etichetta.get(x.livello, '[INFO]')} {x.messaggio}" for x in ordinate]
    )

    colore = {"danger": "#c0392b", "warning": "#d98324", "info": "#2f8f5b"}
    voci = []
    for x in ordinate:
        col = colore.get(x.livello, "#2f8f5b")
        link = (
            f"<div style='margin-top:4px;'><a href='{base}{x.link}' "
            f"style='color:#2f8f5b;font-size:13px;'>Apri la scheda →</a></div>"
            if x.link and base
            else ""
        )
        voci.append(
            f"<li style='list-style:none;margin:0 0 10px;padding:12px 14px;"
            f"border-left:4px solid {col};background:#f7faf8;border-radius:6px;'>"
            f"<div style='font-size:14px;'>{x.messaggio}</div>{link}</li>"
        )
    corpo = (
        f"<p>Hai <strong>{n}</strong> notific{'a' if n == 1 else 'he'} da controllare"
        + (f", di cui <strong>{urgenti}</strong> urgent{'e' if urgenti == 1 else 'i'}" if urgenti else "")
        + ".</p><ul style='padding:0;margin:12px 0 0;'>"
        + "".join(voci)
        + "</ul>"
    )
    return oggetto, testo, _wrap_html(studio, "Riepilogo dello studio", corpo)


def invia_notifiche_pendenti(settings: Settings | None = None) -> int:
    """Invia un digest delle notifiche non ancora spedite. Ritorna quante ne ha incluse."""
    settings = settings or Settings.get()
    if not email_attive(settings):
        return 0
    cfg = effective_config(settings)
    if not cfg.valida_per_digest:
        return 0

    pendenti = notifiche_da_inviare()
    if not pendenti:
        return 0

    oggetto, testo, html = costruisci_digest(pendenti, cfg.studio)
    ok, _ = invia(cfg.destinatari, oggetto, testo, html, settings)
    if not ok:
        return 0

    ora = datetime.utcnow()
    for x in pendenti:
        x.inviata_email = True
        x.inviata_email_at = ora
    db.session.commit()
    current_app.logger.info("Inviato digest con %d notifiche.", len(pendenti))
    return len(pendenti)

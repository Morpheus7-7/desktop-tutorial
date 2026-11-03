"""Promemoria delle note: email all'ora scelta.

L'email parte dall'account configurato in Impostazioni (Gmail con la
«password per le app») e arriva agli indirizzi delle notifiche, oppure, se
non ce ne sono, al proprio indirizzo Gmail.

Il controllo gira anche con la finestra nella barra, quando il database non
va scritto (l'archivio potrebbe essere aperto sull'altro PC): per questo
«email già inviata» non si segna nel database ma con un piccolo file nella
cartella dati. Il file si crea in modo esclusivo prima dell'invio, così due
PC che condividono la cartella non mandano due volte la stessa email.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path

from . import mailer
from .models import Nota, Settings, db

CARTELLA_INVIATI = "Promemoria inviati"
# Un promemoria scaduto da più di così (PC spento, programma chiuso) non
# parte più per email: arriverebbe fuori tempo. Resta visibile nelle Note.
RITARDO_MASSIMO = timedelta(hours=6)


def cartella_inviati(app) -> Path:
    from .archivio import percorso_db

    return percorso_db(app.config["SQLALCHEMY_DATABASE_URI"]).parent / CARTELLA_INVIATI


def _segna(cartella: Path, nota: Nota) -> Path | None:
    """Crea il segnale «inviato»; None se c'era già (inviato altrove)."""
    cartella.mkdir(parents=True, exist_ok=True)
    segnale = cartella / f"nota-{nota.id}-{nota.promemoria_il:%Y%m%d%H%M}"
    try:
        os.close(os.open(segnale, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
    except FileExistsError:
        return None
    return segnale


def gia_inviato(app, nota: Nota) -> bool:
    if not nota.promemoria_il:
        return False
    return (cartella_inviati(app) / f"nota-{nota.id}-{nota.promemoria_il:%Y%m%d%H%M}").exists()


def destinatari(settings: Settings) -> list[str]:
    cfg = mailer.effective_config(settings)
    return cfg.destinatari or [x for x in (cfg.user, cfg.mittente) if x and "@" in x][:1]


def destinatari_configurati() -> bool:
    """Se l'invio email è impostato (server e almeno un destinatario)."""
    settings = Settings.get()
    return bool(mailer.effective_config(settings).host and destinatari(settings))


def testo_email(nota: Nota) -> tuple[str, str]:
    oggetto = f"Promemoria: {nota.titolo}"
    righe = [f"Promemoria di Deal Combined per le {nota.promemoria_il:%H:%M} del {nota.promemoria_il:%d/%m/%Y}.", ""]
    righe.append(f"{nota.sezione_label} · {nota.titolo}")
    if nota.cliente:
        righe.append(f"Cliente: {nota.cliente.ragione_sociale}")
    if nota.testo:
        righe += ["", nota.testo]
    return oggetto, "\n".join(righe)


def promemoria_da_inviare(adesso: datetime | None = None) -> list[Nota]:
    adesso = adesso or datetime.now()
    return (Nota.query.filter(Nota.promemoria_email.is_(True), Nota.promemoria_fatto.is_(False),
                              Nota.promemoria_il <= adesso, Nota.promemoria_il >= adesso - RITARDO_MASSIMO)
            .order_by(Nota.promemoria_il).all())


def invia_promemoria(app, adesso: datetime | None = None) -> int:
    """Invia le email dei promemoria arrivati all'ora. Solo letture dal
    database. Restituisce quante email sono partite."""
    inviate = 0
    with app.app_context():
        try:
            note = promemoria_da_inviare(adesso)
            if not note:
                return 0
            settings = Settings.get()
            a_chi = destinatari(settings)
            if not a_chi:
                return 0
            cartella = cartella_inviati(app)
            for nota in note:
                segnale = _segna(cartella, nota)
                if segnale is None:
                    continue
                oggetto, testo = testo_email(nota)
                try:
                    for indirizzo in a_chi:
                        mailer.invia_al_cliente(indirizzo, oggetto, testo, settings=settings)
                    inviate += 1
                except Exception:  # noqa: BLE001 - rete o server di posta: si riprova al giro dopo
                    segnale.unlink(missing_ok=True)
                    app.logger.exception("Promemoria: invio email non riuscito.")
                    break
        finally:
            if app.config.get("DC_IN_PAUSA"):
                # Finestra nella barra: niente collegamenti aperti al file.
                db.session.remove()
                db.engine.dispose()
    return inviate

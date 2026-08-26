"""Generazione automatica delle notifiche dello studio.

Le notifiche nascono dallo stato dei dati, non da un'azione dell'utente: un
piano che sta per finire, un controllo fissato per domani, un assistito che non
si pesa da un mese. Ogni notifica ha una **chiave** univoca, così ricontrollare
dieci volte al giorno non produce dieci avvisi uguali.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from .models import Appuntamento, Assistito, Messaggio, Notifica, Piano, Settings, db


def _crea(chiave: str, messaggio: str, livello: str = "info", categoria: str = "",
          link: str | None = None, destinatario: str = "nutrizionista",
          assistito_id: int | None = None) -> bool:
    """Crea la notifica se non esiste già. Ritorna True se è stata creata ora."""
    if Notifica.query.filter_by(chiave=chiave).first():
        return False
    db.session.add(
        Notifica(
            chiave=chiave,
            messaggio=messaggio,
            livello=livello,
            categoria=categoria,
            link=link,
            destinatario=destinatario,
            assistito_id=assistito_id,
        )
    )
    return True


def genera_notifiche() -> int:
    """Ricalcola le notifiche mancanti. Ritorna quante ne ha create."""
    settings = Settings.get()
    oggi = date.today()
    nuove = 0

    # --- piani in scadenza o già scaduti -------------------------------
    if settings.avvisa_piano_in_scadenza:
        preavviso = settings.giorni_preavviso_piano or 5
        piani = Piano.query.filter_by(stato="pubblicato").all()
        for piano in piani:
            giorni = (piano.data_fine - oggi).days
            nome = piano.assistito.nome_completo
            link = f"/piani/{piano.id}"
            if 0 <= giorni <= preavviso:
                quando = "oggi" if giorni == 0 else f"fra {giorni} giorn{'o' if giorni == 1 else 'i'}"
                nuove += _crea(
                    f"piano-scadenza-{piano.id}-{piano.data_fine.isoformat()}",
                    f"Il piano di {nome} finisce {quando}: prepara il rinnovo.",
                    "warning",
                    "piano",
                    link,
                    assistito_id=piano.assistito_id,
                )
            elif giorni < 0:
                nuove += _crea(
                    f"piano-scaduto-{piano.id}-{piano.data_fine.isoformat()}",
                    f"Il piano di {nome} è scaduto il {piano.data_fine.strftime('%d/%m/%Y')}.",
                    "danger",
                    "piano",
                    link,
                    assistito_id=piano.assistito_id,
                )

    # --- appuntamenti in arrivo ---------------------------------------
    if settings.avvisa_appuntamenti:
        limite = datetime.combine(oggi + timedelta(days=2), datetime.min.time())
        appuntamenti = (
            Appuntamento.query.filter(
                Appuntamento.stato.in_(["programmato", "confermato"]),
                Appuntamento.data_ora >= datetime.combine(oggi, datetime.min.time()),
                Appuntamento.data_ora < limite,
            )
            .order_by(Appuntamento.data_ora)
            .all()
        )
        for app in appuntamenti:
            giorno = app.data_ora.date()
            quando = "oggi" if giorno == oggi else "domani"
            nuove += _crea(
                f"appuntamento-{app.id}-{giorno.isoformat()}",
                f"{app.tipo} con {app.assistito.nome_completo} {quando} "
                f"alle {app.data_ora.strftime('%H:%M')}.",
                "info" if quando == "domani" else "warning",
                "appuntamento",
                f"/assistiti/{app.assistito_id}",
                assistito_id=app.assistito_id,
            )

    # --- assistiti senza piano attivo ---------------------------------
    for assistito in Assistito.query.filter_by(attivo=True).all():
        if assistito.piano_attivo is None and assistito.piani:
            nuove += _crea(
                f"senza-piano-{assistito.id}-{oggi.isoformat()}",
                f"{assistito.nome_completo} non ha un piano in corso.",
                "warning",
                "piano",
                f"/assistiti/{assistito.id}",
                assistito_id=assistito.id,
            )

        # --- silenzio sulle misurazioni --------------------------------
        ultima = assistito.ultima_misurazione
        if ultima and (oggi - ultima.data).days >= 30:
            settimana = ultima.data + timedelta(days=30)
            nuove += _crea(
                f"misurazioni-ferme-{assistito.id}-{settimana.isoformat()}",
                f"{assistito.nome_completo} non registra misurazioni dal "
                f"{ultima.data.strftime('%d/%m/%Y')}.",
                "info",
                "misurazioni",
                f"/assistiti/{assistito.id}",
                assistito_id=assistito.id,
            )

    # --- messaggi dei clienti non letti -------------------------------
    non_letti = (
        Messaggio.query.filter_by(mittente_ruolo="cliente", letto=False)
        .order_by(Messaggio.created_at)
        .all()
    )
    for messaggio in non_letti:
        nuove += _crea(
            f"messaggio-{messaggio.id}",
            f"Nuovo messaggio da {messaggio.assistito.nome_completo}.",
            "info",
            "messaggio",
            f"/assistiti/{messaggio.assistito_id}#messaggi",
            assistito_id=messaggio.assistito_id,
        )

    if nuove:
        db.session.commit()
    return nuove


def notifica_al_cliente(assistito, messaggio: str, link: str = "/area", chiave: str | None = None,
                        livello: str = "info") -> None:
    """Notifica visibile nell'area riservata del cliente."""
    chiave = chiave or f"cliente-{assistito.id}-{datetime.utcnow().timestamp()}"
    if _crea(chiave, messaggio, livello, "cliente", link, "cliente", assistito.id):
        db.session.commit()


def conta_non_lette(destinatario: str = "nutrizionista", assistito_id: int | None = None) -> int:
    query = Notifica.query.filter_by(letta=False, destinatario=destinatario)
    if assistito_id is not None:
        query = query.filter_by(assistito_id=assistito_id)
    return query.count()

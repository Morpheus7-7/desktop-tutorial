"""Generazione automatica delle notifiche.

Le notifiche vengono generate a partire dai dati (scadenze polizze e
follow-up) a ogni richiesta: la chiave di deduplicazione garantisce che
ogni evento produca una sola notifica per fascia di preavviso.
"""
from datetime import date, timedelta

from .models import (
    CLAIM_OPEN_STATUSES,
    GIORNI_DENUNCIA_SINISTRO,
    Claim,
    Client,
    FollowUp,
    Notification,
    Policy,
    Title,
    db,
)
from .utils import formatta_euro

# Fasce di preavviso per le scadenze polizza (giorni prima della scadenza).
POLICY_REMINDER_BUCKETS = [60, 30, 7]
# Preavviso per le rate (titoli) in scadenza e per i documenti d'identità.
TITLE_REMINDER_DAYS = 7
ID_DOCUMENT_REMINDER_DAYS = 30
# Sinistri aperti da troppo tempo: promemoria a queste soglie (giorni).
CLAIM_AGE_BUCKETS = [90, 180, 365]

# Automazione rinnovi: quanti giorni prima della scadenza creare il follow-up
# e con quale anticipo datarlo.
RENEWAL_LEAD_DAYS = 45
RENEWAL_FOLLOWUP_OFFSET = 15


def auto_create_renewal_followups() -> int:
    """Crea in automatico i follow-up di rinnovo per le polizze in scadenza.

    Genera un solo follow-up per ciascun ciclo di scadenza (deduplicato sulla
    data): quando la polizza viene rinnovata e la scadenza spostata in avanti,
    al ciclo successivo ne verrà creato uno nuovo.
    """
    today = date.today()
    limite = today + timedelta(days=RENEWAL_LEAD_DAYS)
    created = 0

    polizze = (
        Policy.query.filter(
            Policy.stato.in_(["attiva", "in_rinnovo"]),
            Policy.data_scadenza.isnot(None),
            Policy.data_scadenza >= today,
            Policy.data_scadenza <= limite,
        )
        .all()
    )
    for policy in polizze:
        target = policy.data_scadenza - timedelta(days=RENEWAL_FOLLOWUP_OFFSET)
        if target < today:
            target = today
        gia_presente = (
            FollowUp.query.filter_by(
                policy_id=policy.id, tipo="rinnovo", auto_generato=True, data_scadenza=target
            ).first()
        )
        if gia_presente:
            continue
        db.session.add(
            FollowUp(
                client_id=policy.client_id,
                policy_id=policy.id,
                tipo="rinnovo",
                titolo=f"Rinnovo polizza {policy.numero_polizza} ({policy.ramo_label})",
                descrizione=(
                    f"Follow-up generato automaticamente: la polizza scade il "
                    f"{policy.data_scadenza.strftime('%d/%m/%Y')}. Contattare il cliente per il rinnovo."
                ),
                data_scadenza=target,
                priorita="alta",
                auto_generato=True,
            )
        )
        created += 1

    if created:
        db.session.commit()
    return created


def segna_lette(prefisso: str) -> None:
    """Segna come lette le notifiche superate (es. rata incassata, sinistro denunciato).

    ``prefisso`` è l'inizio della chiave di deduplicazione, es. ``"titolo:12:"``.
    Le notifiche restano nello storico ma escono da quelle da leggere e dal
    prossimo digest email. Il commit è a carico del chiamante.
    """
    Notification.query.filter(
        Notification.dedup_key.like(f"{prefisso}%"),
        Notification.letta.is_(False),
    ).update({"letta": True, "inviata_email": True}, synchronize_session=False)


def _add(tipo: str, livello: str, messaggio: str, link: str, dedup_key: str) -> bool:
    if Notification.query.filter_by(dedup_key=dedup_key).first():
        return False
    db.session.add(
        Notification(
            tipo=tipo,
            livello=livello,
            messaggio=messaggio,
            link=link,
            dedup_key=dedup_key,
        )
    )
    return True


def generate_notifications() -> int:
    """Crea le notifiche mancanti; restituisce quante ne ha aggiunte."""
    today = date.today()
    created = 0

    # --- Scadenze polizze -------------------------------------------------
    policies = (
        Policy.query.filter(
            Policy.data_scadenza.isnot(None),
            Policy.stato.in_(["attiva", "in_rinnovo"]),
        )
        .filter(Policy.data_scadenza <= date.fromordinal(today.toordinal() + max(POLICY_REMINDER_BUCKETS)))
        .all()
    )
    for policy in policies:
        giorni = (policy.data_scadenza - today).days
        link = f"/polizze/{policy.id}"
        nome_cliente = policy.cliente.ragione_sociale
        ciclo = policy.data_scadenza.isoformat()
        if giorni < 0:
            created += _add(
                "scadenza_polizza",
                "danger",
                f"Polizza {policy.numero_polizza} ({policy.ramo_label}) di {nome_cliente} "
                f"SCADUTA il {policy.data_scadenza.strftime('%d/%m/%Y')}.",
                link,
                f"polizza:{policy.id}:{ciclo}:scaduta",
            )
            continue
        for bucket in sorted(POLICY_REMINDER_BUCKETS):
            if giorni <= bucket:
                livello = "danger" if bucket == 7 else "warning" if bucket == 30 else "info"
                created += _add(
                    "scadenza_polizza",
                    livello,
                    f"Polizza {policy.numero_polizza} ({policy.ramo_label}) di {nome_cliente} "
                    f"scade tra {giorni} giorni ({policy.data_scadenza.strftime('%d/%m/%Y')}).",
                    link,
                    f"polizza:{policy.id}:{ciclo}:{bucket}",
                )
                break

    # --- Follow-up --------------------------------------------------------
    followups = (
        FollowUp.query.filter(
            FollowUp.stato == "aperto",
            FollowUp.data_scadenza <= date.fromordinal(today.toordinal() + 3),
        )
        .all()
    )
    for fu in followups:
        link = f"/clienti/{fu.client_id}"
        nome_cliente = fu.cliente.ragione_sociale
        if fu.data_scadenza < today:
            created += _add(
                "followup",
                "danger",
                f"Follow-up IN RITARDO per {nome_cliente}: “{fu.titolo}” "
                f"(previsto il {fu.data_scadenza.strftime('%d/%m/%Y')}).",
                link,
                f"followup:{fu.id}:ritardo",
            )
        elif fu.data_scadenza == today:
            created += _add(
                "followup",
                "warning",
                f"Follow-up OGGI per {nome_cliente}: “{fu.titolo}”.",
                link,
                f"followup:{fu.id}:oggi",
            )
        else:
            created += _add(
                "followup",
                "info",
                f"Follow-up in arrivo per {nome_cliente}: “{fu.titolo}” "
                f"il {fu.data_scadenza.strftime('%d/%m/%Y')}.",
                link,
                f"followup:{fu.id}:prossimo",
            )

    created += _notifiche_titoli(today)
    created += _notifiche_sinistri(today)
    created += _notifiche_documenti(today)

    if created:
        db.session.commit()
    return created


def _notifiche_titoli(today: date) -> int:
    """Rate in scadenza, non pagate e con copertura sospesa (art. 1901 c.c.)."""
    created = 0
    titoli = Title.query.filter(
        Title.stato == "da_incassare",
        Title.data_effetto <= today + timedelta(days=TITLE_REMINDER_DAYS),
    ).all()
    for t in titoli:
        policy = t.polizza
        if policy is None or not policy.attiva:
            continue
        link = f"/polizze/{policy.id}"
        descr = f"polizza {policy.numero_polizza} di {policy.cliente.ragione_sociale}"
        if t.copertura_sospesa:
            created += _add(
                "titolo", "danger",
                f"Copertura SOSPESA per mancato pagamento: rata del {t.data_effetto:%d/%m/%Y} "
                f"({formatta_euro(t.premio_lordo)}) della {descr}.",
                link, f"titolo:{t.id}:sospesa",
            )
        elif t.data_effetto < today:
            created += _add(
                "titolo", "warning",
                f"Rata NON PAGATA scaduta il {t.data_effetto:%d/%m/%Y} ({formatta_euro(t.premio_lordo)}) della "
                f"{descr}: copertura sospesa dal {t.data_sospensione:%d/%m/%Y} se non incassata.",
                link, f"titolo:{t.id}:arretrato",
            )
        else:
            created += _add(
                "titolo", "info",
                f"Rata in scadenza il {t.data_effetto:%d/%m/%Y} ({formatta_euro(t.premio_lordo)}) della {descr}.",
                link, f"titolo:{t.id}:prossimo",
            )
    return created


def _notifiche_sinistri(today: date) -> int:
    """Sinistri ancora da denunciare e sinistri aperti da molto tempo."""
    created = 0
    for s in Claim.query.filter(Claim.stato.in_(CLAIM_OPEN_STATUSES)).all():
        link = f"/sinistri/{s.id}"
        nome = s.cliente.ragione_sociale
        if s.data_denuncia is None:
            giorni = (today - s.data_evento).days
            urgente = giorni >= GIORNI_DENUNCIA_SINISTRO
            created += _add(
                "sinistro", "danger" if urgente else "warning",
                f"Sinistro {s.numero} di {nome} non ancora denunciato alla compagnia "
                f"(evento del {s.data_evento:%d/%m/%Y}"
                + (", termine di 3 giorni superato — art. 1913 c.c.)." if urgente else ")."),
                link, f"sinistro:{s.id}:denuncia",
            )
        for soglia in reversed(CLAIM_AGE_BUCKETS):
            if s.giorni_apertura >= soglia:
                created += _add(
                    "sinistro", "info",
                    f"Sinistro {s.numero} di {nome} aperto da oltre {soglia} giorni: sollecitare la compagnia.",
                    link, f"sinistro:{s.id}:aperto:{soglia}",
                )
                break
    return created


def _notifiche_documenti(today: date) -> int:
    """Documenti d'identità dei clienti scaduti o in scadenza (adeguata verifica)."""
    created = 0
    clienti = Client.query.filter(
        Client.documento_scadenza.isnot(None),
        Client.documento_scadenza <= today + timedelta(days=ID_DOCUMENT_REMINDER_DAYS),
    ).all()
    for c in clienti:
        scaduto = c.documento_scadenza < today
        created += _add(
            "documento", "warning" if scaduto else "info",
            f"Documento d'identità di {c.ragione_sociale} "
            + (f"SCADUTO il {c.documento_scadenza:%d/%m/%Y}" if scaduto
               else f"in scadenza il {c.documento_scadenza:%d/%m/%Y}")
            + ": richiedere copia aggiornata.",
            f"/clienti/{c.id}",
            f"cliente:{c.id}:documento:{c.documento_scadenza.isoformat()}:{'scaduto' if scaduto else 'prossimo'}",
        )
    return created

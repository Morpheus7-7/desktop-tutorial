"""Generazione automatica delle notifiche.

Le notifiche vengono generate a partire dai dati (scadenze polizze e
follow-up) a ogni richiesta: la chiave di deduplicazione garantisce che
ogni evento produca una sola notifica per fascia di preavviso.
"""
from datetime import date, timedelta

from .models import FollowUp, Notification, Policy, db

# Fasce di preavviso per le scadenze polizza (giorni prima della scadenza).
POLICY_REMINDER_BUCKETS = [60, 30, 7]

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
        link = f"/clienti/{policy.client_id}"
        nome_cliente = policy.cliente.ragione_sociale
        if giorni < 0:
            created += _add(
                "scadenza_polizza",
                "danger",
                f"Polizza {policy.numero_polizza} ({policy.ramo_label}) di {nome_cliente} "
                f"SCADUTA il {policy.data_scadenza.strftime('%d/%m/%Y')}.",
                link,
                f"polizza:{policy.id}:scaduta",
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
                    f"polizza:{policy.id}:{bucket}",
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

    if created:
        db.session.commit()
    return created

"""Generazione automatica delle notifiche.

Le notifiche vengono generate a partire dai dati (scadenze polizze e
follow-up) a ogni richiesta: la chiave di deduplicazione garantisce che
ogni evento produca una sola notifica per fascia di preavviso.
"""
from datetime import date

from .models import FollowUp, Notification, Policy, db

# Fasce di preavviso per le scadenze polizza (giorni prima della scadenza).
POLICY_REMINDER_BUCKETS = [60, 30, 7]


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

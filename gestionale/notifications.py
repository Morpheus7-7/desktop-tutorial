"""Generazione automatica delle notifiche.

Le notifiche vengono generate a partire dai dati (scadenze, rate, sinistri,
follow-up, compliance). Ogni evento ha una chiave di deduplicazione che
contiene **la data di riferimento** (scadenza, effetto della rata, data del
follow-up…): così una proroga, un rinnovo o un annullamento producono un
nuovo avviso invece di restare silenziosi, e un id riutilizzato non eredita
le notifiche di un record eliminato (che vengono comunque cancellate).

Formato delle chiavi: ``entità:id:data:fascia``. I prefissi ``entità:id:``
servono a chiudere (``segna_lette``) o eliminare (``elimina_notifiche``) in
blocco gli avvisi di un record.
"""
from __future__ import annotations

import threading
from datetime import date, timedelta

from sqlalchemy.exc import IntegrityError

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
    now,
)
from .utils import formatta_euro

# Serializza automatismi e generazione delle notifiche tra scheduler e richieste web.
LOCK = threading.Lock()

# Fasce di preavviso (giorni prima dell'evento).
POLICY_REMINDER_BUCKETS = [60, 30, 7]
DISDETTA_REMINDER_BUCKETS = [30, 7, 0]
TITLE_REMINDER_DAYS = 7
ID_DOCUMENT_REMINDER_DAYS = 30
ADEGUATEZZA_REMINDER_DAYS = 30
DECORRENZA_REMINDER_DAYS = 7
RISOLUZIONE_REMINDER_DAYS = 30
# Sinistri aperti da troppo tempo: promemoria a queste soglie (giorni).
CLAIM_AGE_BUCKETS = [90, 180, 365]

# Automazione rinnovi: quanti giorni prima della scadenza creare il follow-up
# e con quale anticipo datarlo.
RENEWAL_LEAD_DAYS = 45
RENEWAL_FOLLOWUP_OFFSET = 15

STATI_ATTIVI = ("attiva", "in_rinnovo")


# ----------------------------------------------------------------------
# Ciclo di vita delle notifiche
# ----------------------------------------------------------------------
def segna_lette(prefisso: str) -> None:
    """Segna come lette (e già inviate) le notifiche superate di un record.

    Le notifiche restano nello storico. Il commit è a carico del chiamante.
    """
    Notification.query.filter(
        Notification.dedup_key.like(f"{prefisso}%"),
        Notification.letta.is_(False),
    ).update({"letta": True, "inviata_email": True}, synchronize_session=False)


def elimina_notifiche(*prefissi: str) -> None:
    """Elimina le notifiche di uno o più record (eliminazione, annullamento, riapertura).

    Così il record (o uno nuovo che ne riprende l'id) viene rinotificato con lo
    stato corrente. Il commit è a carico del chiamante.
    """
    for prefisso in prefissi:
        Notification.query.filter(Notification.dedup_key.like(f"{prefisso}%")).delete(
            synchronize_session=False
        )


def aggiungi_notifica(tipo: str, livello: str, messaggio: str, link: str, dedup_key: str) -> bool:
    """Inserisce la notifica se la chiave non esiste ancora (in modo idempotente)."""
    valori = dict(
        tipo=tipo, livello=livello, messaggio=messaggio[:500], link=link,
        dedup_key=dedup_key, letta=False, inviata_email=False, created_at=now(),
    )
    dialetto = db.engine.dialect.name
    if dialetto in ("sqlite", "postgresql"):
        if dialetto == "sqlite":
            from sqlalchemy.dialects.sqlite import insert
        else:  # pragma: no cover - usato solo con DATABASE_URL PostgreSQL
            from sqlalchemy.dialects.postgresql import insert
        risultato = db.session.execute(
            insert(Notification).values(**valori).on_conflict_do_nothing(index_elements=["dedup_key"])
        )
        return bool(risultato.rowcount)
    if Notification.query.filter_by(dedup_key=dedup_key).first():  # pragma: no cover
        return False
    try:  # pragma: no cover - altri database
        db.session.add(Notification(**valori))
        db.session.flush()
    except IntegrityError:  # pragma: no cover
        db.session.rollback()
        return False
    return True  # pragma: no cover


# Nome interno usato dalle funzioni di questo modulo.
_add = aggiungi_notifica


def _testo_giorni(giorni: int) -> str:
    if giorni == 0:
        return "OGGI"
    if giorni == 1:
        return "domani"
    return f"tra {giorni} giorni"


# ----------------------------------------------------------------------
# Follow-up automatici di rinnovo
# ----------------------------------------------------------------------
def auto_create_renewal_followups(oggi: date | None = None) -> int:
    """Crea i follow-up di rinnovo per le polizze in scadenza: uno per ciclo.

    La deduplica è sul ciclo di scadenza (qualunque stato e data del
    follow-up): completarlo non lo fa ricomparire il giorno dopo. Dopo il
    rinnovo la scadenza cambia e il ciclo successivo avrà il suo follow-up.
    """
    today = oggi or date.today()
    limite = today + timedelta(days=RENEWAL_LEAD_DAYS)
    created = 0
    polizze = Policy.query.filter(
        Policy.stato.in_(STATI_ATTIVI),
        Policy.data_scadenza.isnot(None),
        Policy.data_scadenza >= today,
        Policy.data_scadenza <= limite,
        Policy.data_disdetta.is_(None),
    ).all()
    for policy in polizze:
        scadenza = policy.data_scadenza
        gia_presente = FollowUp.query.filter(
            FollowUp.policy_id == policy.id,
            FollowUp.tipo == "rinnovo",
            FollowUp.auto_generato.is_(True),
            FollowUp.data_scadenza >= scadenza - timedelta(days=RENEWAL_LEAD_DAYS),
            FollowUp.data_scadenza <= scadenza,
        ).first()
        if gia_presente:
            continue
        target = max(scadenza - timedelta(days=RENEWAL_FOLLOWUP_OFFSET), today)
        if policy.tacito_rinnovo and policy.termine_disdetta:
            target = max(min(target, policy.termine_disdetta), today)
            descrizione = (
                f"Polizza a tacito rinnovo: scade il {scadenza:%d/%m/%Y}, termine per la disdetta "
                f"il {policy.termine_disdetta:%d/%m/%Y}. Verificare con il cliente se rinnovare o disdire."
            )
        else:
            descrizione = (
                f"Follow-up generato automaticamente: la polizza scade il {scadenza:%d/%m/%Y}. "
                "Contattare il cliente per il rinnovo."
            )
        db.session.add(FollowUp(
            client_id=policy.client_id,
            policy_id=policy.id,
            tipo="rinnovo",
            titolo=f"Rinnovo polizza {policy.numero_polizza} ({policy.ramo_label})",
            descrizione=descrizione,
            data_scadenza=target,
            priorita="alta",
            auto_generato=True,
        ))
        created += 1
    if created:
        db.session.commit()
    return created


# ----------------------------------------------------------------------
# Generazione delle notifiche
# ----------------------------------------------------------------------
def generate_notifications(oggi: date | None = None) -> int:
    """Crea le notifiche mancanti; restituisce quante ne ha aggiunte."""
    today = oggi or date.today()
    created = 0
    created += _notifiche_polizze(today)
    created += _notifiche_disdette(today)
    created += _notifiche_decorrenze(today)
    created += _notifiche_followup(today)
    created += _notifiche_titoli(today)
    created += _notifiche_sinistri(today)
    created += _notifiche_clienti(today)
    if created:
        db.session.commit()
    return created


def _notifiche_polizze(today: date) -> int:
    created = 0
    policies = Policy.query.filter(
        Policy.data_scadenza.isnot(None),
        Policy.stato.in_(STATI_ATTIVI),
        Policy.data_scadenza <= today + timedelta(days=max(POLICY_REMINDER_BUCKETS)),
    ).all()
    for policy in policies:
        giorni = (policy.data_scadenza - today).days
        link = f"/polizze/{policy.id}"
        nome_cliente = policy.cliente.ragione_sociale
        ciclo = policy.data_scadenza.isoformat()
        descr = f"Polizza {policy.numero_polizza} ({policy.ramo_label}) di {nome_cliente}"
        tacito = policy.tacito_rinnovo and not policy.disdetta_inviata
        if giorni < 0:
            if tacito:
                created += _add(
                    "scadenza_polizza", "warning",
                    f"{descr}: rinnovo tacito da registrare (scadenza {policy.data_scadenza:%d/%m/%Y}). "
                    "Registra il rinnovo e incassa la quietanza.",
                    link, f"polizza:{policy.id}:{ciclo}:tacito",
                )
            else:
                created += _add(
                    "scadenza_polizza", "danger",
                    f"{descr} SCADUTA il {policy.data_scadenza:%d/%m/%Y}.",
                    link, f"polizza:{policy.id}:{ciclo}:scaduta",
                )
            continue
        if tacito:
            continue  # per il tacito rinnovo conta il termine di disdetta (vedi sotto)
        for bucket in sorted(POLICY_REMINDER_BUCKETS):
            if giorni <= bucket:
                livello = "danger" if bucket == 7 else "warning" if bucket == 30 else "info"
                created += _add(
                    "scadenza_polizza", livello,
                    f"{descr} scade {_testo_giorni(giorni)} ({policy.data_scadenza:%d/%m/%Y}).",
                    link, f"polizza:{policy.id}:{ciclo}:{bucket}",
                )
                break
    return created


def _notifiche_disdette(today: date) -> int:
    """Termine per la disdetta delle polizze a tacito rinnovo (data futura chiave)."""
    created = 0
    policies = Policy.query.filter(
        Policy.stato.in_(STATI_ATTIVI),
        Policy.tacito_rinnovo.is_(True),
        Policy.data_disdetta.is_(None),
        Policy.data_scadenza.isnot(None),
        Policy.data_scadenza >= today,
    ).all()
    for policy in policies:
        termine = policy.termine_disdetta
        if termine is None or termine < today:
            continue
        giorni = (termine - today).days
        for bucket in sorted(DISDETTA_REMINDER_BUCKETS):
            if giorni <= bucket:
                livello = "danger" if bucket == 0 else "warning" if bucket == 7 else "info"
                created += _add(
                    "disdetta", livello,
                    f"Termine disdetta {_testo_giorni(giorni)} ({termine:%d/%m/%Y}) per la polizza "
                    f"{policy.numero_polizza} di {policy.cliente.ragione_sociale}: dopo, il contratto "
                    f"si rinnova tacitamente alla scadenza del {policy.data_scadenza:%d/%m/%Y}.",
                    f"/polizze/{policy.id}",
                    f"disdetta:{policy.id}:{policy.data_scadenza.isoformat()}:{bucket}",
                )
                break
    return created


def _notifiche_decorrenze(today: date) -> int:
    """Polizze in decorrenza con il perfezionamento ancora da incassare."""
    created = 0
    policies = Policy.query.filter(
        Policy.stato.in_(STATI_ATTIVI),
        Policy.data_decorrenza.isnot(None),
        Policy.data_decorrenza >= today,
        Policy.data_decorrenza <= today + timedelta(days=DECORRENZA_REMINDER_DAYS),
    ).all()
    for policy in policies:
        perfezionamento = next(
            (t for t in policy.titoli if t.tipo == "perfezionamento" and t.stato == "da_incassare"),
            None,
        )
        if perfezionamento is None:
            continue
        giorni = (policy.data_decorrenza - today).days
        created += _add(
            "decorrenza", "warning" if giorni <= 1 else "info",
            f"La polizza {policy.numero_polizza} di {policy.cliente.ragione_sociale} decorre "
            f"{_testo_giorni(giorni)} ({policy.data_decorrenza:%d/%m/%Y}): incassare il perfezionamento "
            f"({formatta_euro(perfezionamento.premio_lordo)}), senza il quale la copertura non è operante.",
            f"/polizze/{policy.id}",
            f"decorrenza:{policy.id}:{policy.data_decorrenza.isoformat()}",
        )
    return created


def _notifiche_followup(today: date) -> int:
    created = 0
    followups = FollowUp.query.filter(
        FollowUp.stato == "aperto",
        FollowUp.data_scadenza <= today + timedelta(days=3),
    ).all()
    for fu in followups:
        link = f"/clienti/{fu.client_id}#followup"
        nome_cliente = fu.cliente.ragione_sociale
        chiave = f"followup:{fu.id}:{fu.data_scadenza.isoformat()}"
        if fu.data_scadenza < today:
            created += _add(
                "followup", "danger",
                f"Follow-up IN RITARDO per {nome_cliente}: “{fu.titolo}” "
                f"(previsto il {fu.data_scadenza:%d/%m/%Y}).",
                link, f"{chiave}:ritardo",
            )
        elif fu.data_scadenza == today:
            created += _add(
                "followup", "warning", f"Follow-up OGGI per {nome_cliente}: “{fu.titolo}”.",
                link, f"{chiave}:oggi",
            )
        else:
            created += _add(
                "followup", "info",
                f"Follow-up in arrivo per {nome_cliente}: “{fu.titolo}” il {fu.data_scadenza:%d/%m/%Y}.",
                link, f"{chiave}:prossimo",
            )
    return created


def _notifiche_titoli(today: date) -> int:
    """Rate in scadenza, non pagate, con copertura sospesa o prossime alla risoluzione."""
    created = 0
    titoli = Title.query.filter(
        Title.stato == "da_incassare",
        Title.premio_lordo > 0,
        Title.data_effetto <= today + timedelta(days=TITLE_REMINDER_DAYS),
    ).all()
    for t in titoli:
        policy = t.polizza
        if policy is None or not policy.attiva:
            continue
        link = f"/polizze/{policy.id}"
        descr = f"polizza {policy.numero_polizza} di {policy.cliente.ragione_sociale}"
        chiave = f"titolo:{t.id}:{t.data_effetto.isoformat()}"
        importo = formatta_euro(t.premio_lordo)
        if t.copertura_sospesa:
            created += _add(
                "titolo", "danger",
                f"Copertura SOSPESA per mancato pagamento: rata del {t.data_effetto:%d/%m/%Y} ({importo}) "
                f"della {descr}.",
                link, f"{chiave}:sospesa",
            )
            risoluzione = t.data_risoluzione
            if risoluzione and (risoluzione - today).days <= RISOLUZIONE_REMINDER_DAYS:
                created += _add(
                    "titolo", "danger",
                    f"Rata del {t.data_effetto:%d/%m/%Y} ({importo}) della {descr} impagata da quasi sei mesi: "
                    f"il contratto si risolve di diritto il {risoluzione:%d/%m/%Y} se la compagnia non agisce "
                    "per la riscossione (art. 1901 c.c., comma 3).",
                    link, f"{chiave}:risoluzione",
                )
        elif t.data_effetto < today:
            created += _add(
                "titolo", "warning",
                f"Rata NON PAGATA scaduta il {t.data_effetto:%d/%m/%Y} ({importo}) della {descr}: "
                f"copertura sospesa dal {t.data_sospensione:%d/%m/%Y} se non incassata.",
                link, f"{chiave}:arretrato",
            )
        else:
            giorni = (t.data_effetto - today).days
            created += _add(
                "titolo", "info",
                f"Rata in scadenza {_testo_giorni(giorni)} ({t.data_effetto:%d/%m/%Y}, {importo}) della {descr}.",
                link, f"{chiave}:prossimo",
            )
    return created


def _notifiche_sinistri(today: date) -> int:
    """Sinistri ancora da denunciare e sinistri aperti da molto tempo."""
    created = 0
    for s in Claim.query.filter(Claim.stato.in_(CLAIM_OPEN_STATUSES)).all():
        link = f"/sinistri/{s.id}"
        nome = s.cliente.ragione_sociale
        chiave = f"sinistro:{s.id}:{s.data_evento.isoformat()}"
        if s.data_denuncia is None:
            giorni = (today - s.data_evento).days
            if giorni > GIORNI_DENUNCIA_SINISTRO:
                nuova = _add(
                    "sinistro", "danger",
                    f"Sinistro {s.numero} di {nome} NON ancora denunciato alla compagnia: evento del "
                    f"{s.data_evento:%d/%m/%Y}, termine di 3 giorni superato (art. 1913 c.c.).",
                    link, f"{chiave}:denuncia:scaduta",
                )
                if nuova:
                    segna_lette(f"{chiave}:denuncia:termine")
                created += nuova
            else:
                termine = s.data_evento + timedelta(days=GIORNI_DENUNCIA_SINISTRO)
                created += _add(
                    "sinistro", "warning",
                    f"Sinistro {s.numero} di {nome} da denunciare alla compagnia entro il "
                    f"{termine:%d/%m/%Y} (art. 1913 c.c.).",
                    link, f"{chiave}:denuncia:termine",
                )
        for soglia in reversed(CLAIM_AGE_BUCKETS):
            if s.giorni_apertura >= soglia:
                created += _add(
                    "sinistro", "info",
                    f"Sinistro {s.numero} di {nome} aperto da oltre {soglia} giorni: sollecitare la compagnia.",
                    link, f"{chiave}:aperto:{soglia}",
                )
                break
    return created


def _notifiche_clienti(today: date) -> int:
    """Documenti d'identità e questionari di adeguatezza scaduti o in scadenza."""
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
    limite_adeguatezza = today + timedelta(days=ADEGUATEZZA_REMINDER_DAYS)
    for c in Client.query.filter(Client.data_adeguatezza.isnot(None)).all():
        scadenza = c.adeguatezza_scadenza
        if scadenza is None or scadenza > limite_adeguatezza:
            continue
        scaduto = scadenza < today
        created += _add(
            "documento", "warning" if scaduto else "info",
            f"Questionario di adeguatezza di {c.ragione_sociale} "
            + ("da aggiornare: è più vecchio di 12 mesi" if scaduto
               else f"da aggiornare entro il {scadenza:%d/%m/%Y}")
            + " (IVASS Reg. 40/2018).",
            f"/clienti/{c.id}",
            f"cliente:{c.id}:adeguatezza:{scadenza.isoformat()}:{'scaduto' if scaduto else 'prossimo'}",
        )
    return created


def aggiorna_tutto(oggi: date | None = None) -> None:
    """Automatismi, follow-up di rinnovo e notifiche in un'unica passata."""
    from .automatismi import esegui_automatismi

    esegui_automatismi(oggi)
    auto_create_renewal_followups(oggi)
    generate_notifications(oggi)

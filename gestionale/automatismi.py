"""Automatismi legati alle date, eseguiti dallo scheduler e all'accesso.

- **Rinnovo tacito**: le polizze a tacito rinnovo senza disdetta, arrivate a
  scadenza, vengono prorogate di un'annualità e (se la polizza gestisce i
  titoli) ricevono la quietanza della nuova annualità.
- **Quietanze all'anniversario**: per le polizze che gestiscono i titoli nel
  gestionale (poliennali comprese), la quietanza di ogni nuova annualità viene
  emessa con un anticipo configurabile.
- **Scadenza automatica**: le polizze senza tacito rinnovo, non rinnovate entro
  i giorni di tolleranza dopo la scadenza, passano a «scaduta» (o «disdetta» se
  la disdetta era stata registrata); le rate future vengono stornate.

Ogni operazione finisce nel registro attività come utente «sistema» e genera
una notifica informativa. Ogni automatismo si disattiva dalle Impostazioni.
"""
from __future__ import annotations

from datetime import date, timedelta

from .models import RAMI_SENZA_TACITO_RINNOVO, FollowUp, Policy, Settings, db, now
from .titoli import TitoliGiaPresenti, add_months, genera_titoli, periodi_polizza, titoli_coprono

# Il rinnovo tacito automatico agisce solo su scadenze recenti: una polizza
# dimenticata da anni va verificata a mano, non rinnovata in blocco.
FINESTRA_RINNOVO_TACITO_GIORNI = 60
# Emissione automatica: un'annualità già iniziata si recupera solo se è
# iniziata da pochi giorni (gestionale non usato per qualche giorno).
FINESTRA_RECUPERO_QUIETANZE_GIORNI = 30
STATI_ATTIVI = ("attiva", "in_rinnovo")


def _audit_sistema(azione: str, policy: Policy, descrizione: str) -> None:
    from .security import audit

    audit(azione, "polizza", policy.id, descrizione, sistema=True)


def _notifica(dedup_key: str, messaggio: str, policy: Policy, livello: str = "info") -> None:
    from .notifications import aggiungi_notifica

    aggiungi_notifica("automatismo", livello, messaggio, f"/polizze/{policy.id}", dedup_key)


def _gestisce_titoli(policy: Policy) -> bool:
    """Le automazioni sui titoli valgono solo per le polizze che gestiscono già le
    rate nel gestionale: un'appendice (es. regolazione premio) non basta."""
    return bool(
        policy.premio_annuo and policy.premio_annuo > 0
        and any(t.tipo != "appendice" and t.stato != "stornato" for t in policy.titoli)
    )


def storna_titoli_futuri(policy: Policy, dal: date, motivo: str) -> int:
    """Storna le rate non incassate con effetto da ``dal`` in poi; restituisce quante."""
    from .notifications import elimina_notifiche

    stornati = 0
    for titolo in policy.titoli:
        if titolo.stato == "da_incassare" and titolo.data_effetto >= dal:
            titolo.stato = "stornato"
            titolo.note = ((titolo.note + "\n") if titolo.note else "") + f"Storno: {motivo}"
            elimina_notifiche(f"titolo:{titolo.id}:")
            stornati += 1
    return stornati


def ripristina_titoli_stornati(policy: Policy, motivo: str) -> int:
    """Rimette da incassare i titoli stornati con un motivo che inizia con
    ``motivo`` (es. l'annullo di una disdetta) e toglie la riga dello storno."""
    marcatore = f"Storno: {motivo}"
    ripristinati = 0
    for titolo in policy.titoli:
        if titolo.stato != "stornato" or not titolo.note:
            continue
        righe = titolo.note.split("\n")
        rimaste = [r for r in righe if not r.startswith(marcatore)]
        if len(rimaste) == len(righe):
            continue
        titolo.note = "\n".join(rimaste) or None
        titolo.stato = "da_incassare"
        ripristinati += 1
    return ripristinati


def _chiudi_followup_rinnovo(policy: Policy, stato: str) -> None:
    """Chiude i follow-up di rinnovo ancora aperti (rinnovo o chiusura automatici)."""
    from .notifications import segna_lette

    for fu in FollowUp.query.filter_by(policy_id=policy.id, tipo="rinnovo", stato="aperto").all():
        fu.stato = stato
        fu.completed_at = now()
        segna_lette(f"followup:{fu.id}:")


def _chiudi_notifiche_ciclo(policy: Policy, scadenza: date, tieni_scaduta: bool = False) -> None:
    """Segna lette le notifiche del ciclo di scadenza superato (rinnovo o chiusura)."""
    from .notifications import segna_lette

    if tieni_scaduta:
        for fascia in ("60", "30", "7"):
            segna_lette(f"polizza:{policy.id}:{scadenza.isoformat()}:{fascia}")
    else:
        segna_lette(f"polizza:{policy.id}:{scadenza.isoformat()}:")
    segna_lette(f"disdetta:{policy.id}:{scadenza.isoformat()}:")


def rinnova_taciti(oggi: date, settings: Settings) -> int:
    if not settings.rinnovo_tacito_automatico:
        return 0
    polizze = Policy.query.filter(
        Policy.stato.in_(STATI_ATTIVI),
        Policy.tacito_rinnovo.is_(True),
        Policy.ramo.notin_(RAMI_SENZA_TACITO_RINNOVO),  # RC auto: vietato (L. 221/2012)
        Policy.data_disdetta.is_(None),
        Policy.data_scadenza.isnot(None),
        Policy.data_scadenza <= oggi,
        Policy.data_scadenza >= oggi - timedelta(days=FINESTRA_RINNOVO_TACITO_GIORNI),
    ).all()
    rinnovate = 0
    for policy in polizze:
        vecchia = policy.data_scadenza
        try:
            nuova = add_months(vecchia, 12)
        except (ValueError, OverflowError):
            continue
        titoli_msg = ""
        if _gestisce_titoli(policy):
            try:
                titoli = genera_titoli(policy, inizio=vecchia, fine=nuova, tipo_primo="quietanza")
                titoli_msg = f", emesse {len(titoli)} rate"
            except (TitoliGiaPresenti, ValueError):
                pass
        policy.data_scadenza = nuova
        policy.stato = "attiva"
        _chiudi_notifiche_ciclo(policy, vecchia)
        _chiudi_followup_rinnovo(policy, "completato")
        _audit_sistema(
            "rinnovo", policy,
            f"Rinnovo tacito automatico della polizza {policy.numero_polizza}: "
            f"scadenza {vecchia:%d/%m/%Y} → {nuova:%d/%m/%Y}{titoli_msg}",
        )
        _notifica(
            f"automatismo:tacito:{policy.id}:{vecchia.isoformat()}",
            f"Polizza {policy.numero_polizza} di {policy.cliente.ragione_sociale} rinnovata tacitamente "
            f"fino al {nuova:%d/%m/%Y}{titoli_msg}.",
            policy,
        )
        rinnovate += 1
    return rinnovate


def emetti_quietanze(oggi: date, settings: Settings) -> int:
    if not settings.emissione_quietanze_automatica:
        return 0
    anticipo = max(0, min(settings.anticipo_quietanze_giorni or 0, 365))
    orizzonte = oggi + timedelta(days=anticipo)
    polizze = Policy.query.filter(
        Policy.stato.in_(STATI_ATTIVI),
        Policy.premio_annuo > 0,
    ).all()
    emesse = 0
    recupero = oggi - timedelta(days=FINESTRA_RECUPERO_QUIETANZE_GIORNI)
    for policy in polizze:
        # Anche con la disdetta registrata le annualità fino alla scadenza restano
        # dovute (es. poliennale disdetta alla scadenza): periodi_polizza non va
        # mai oltre la scadenza, quindi non si emette nulla dopo la cessazione.
        if not _gestisce_titoli(policy):
            continue
        periodi = list(periodi_polizza(policy, fino_a=orizzonte))
        # Tacito rinnovo ormai certo (termine di disdetta passato senza disdetta):
        # la quietanza dell'annualità successiva si emette in anticipo come le altre.
        termine = policy.termine_disdetta
        if (policy.rinnovo_tacito and policy.data_disdetta is None and termine and termine < oggi
                and policy.data_scadenza and policy.data_scadenza <= orizzonte):
            try:
                periodi.append((policy.data_scadenza, add_months(policy.data_scadenza, 12)))
            except (ValueError, OverflowError):
                pass
        for inizio, fine in periodi:
            if fine <= oggi or inizio > orizzonte:
                continue
            # Mai un primo premio automatico (lo emette chi registra la polizza)
            # né annualità iniziate da tempo: genererebbero arretrati e false
            # «coperture sospese». Si recuperano solo i ritardi di pochi giorni.
            if policy.data_decorrenza and inizio == policy.data_decorrenza:
                continue
            if inizio < recupero:
                continue
            # Periodo già emesso (anche se poi stornato o con date spostate): non
            # si riemette, così uno storno dell'operatore non viene annullato.
            if titoli_coprono(policy, inizio, fine, includi_stornati=True):
                continue
            try:
                titoli = genera_titoli(policy, inizio=inizio, fine=fine, tipo_primo="quietanza")
            except (TitoliGiaPresenti, ValueError):
                continue
            _audit_sistema(
                "crea", policy,
                f"Emesse automaticamente {len(titoli)} rate della polizza {policy.numero_polizza} "
                f"per l'annualità {inizio:%d/%m/%Y} – {fine:%d/%m/%Y}",
            )
            _notifica(
                f"automatismo:quietanze:{policy.id}:{inizio.isoformat()}",
                f"Emesse le rate dell'annualità {inizio:%d/%m/%Y} – {fine:%d/%m/%Y} della polizza "
                f"{policy.numero_polizza} di {policy.cliente.ragione_sociale}.",
                policy,
            )
            emesse += 1
    return emesse


def scadi_polizze(oggi: date, settings: Settings) -> int:
    if not settings.scadenza_automatica:
        return 0
    tolleranza = max(0, min(settings.tolleranza_scadenza_giorni or 0, 365))
    polizze = Policy.query.filter(
        Policy.stato.in_(STATI_ATTIVI),
        Policy.data_scadenza.isnot(None),
        Policy.data_scadenza < oggi,
    ).all()
    chiuse = 0
    for policy in polizze:
        disdetta = policy.data_disdetta is not None
        if policy.rinnovo_tacito and not disdetta:
            continue  # si rinnova per legge: la gestisce il rinnovo tacito
        limite = policy.data_scadenza + timedelta(days=0 if disdetta else tolleranza)
        if oggi <= limite:
            continue
        policy.stato = "disdetta" if disdetta else "scaduta"
        _chiudi_notifiche_ciclo(policy, policy.data_scadenza, tieni_scaduta=True)
        _chiudi_followup_rinnovo(policy, "annullato")
        stornati = storna_titoli_futuri(policy, policy.data_scadenza, f"polizza {policy.stato}")
        dettaglio = f", stornate {stornati} rate successive" if stornati else ""
        _audit_sistema(
            "modifica", policy,
            f"Polizza {policy.numero_polizza} passata automaticamente a «{policy.stato_label}» "
            f"(scadenza {policy.data_scadenza:%d/%m/%Y}){dettaglio}",
        )
        _notifica(
            f"automatismo:chiusura:{policy.id}:{policy.data_scadenza.isoformat()}",
            f"Polizza {policy.numero_polizza} di {policy.cliente.ragione_sociale} non rinnovata: "
            f"impostata come «{policy.stato_label}» (scaduta il {policy.data_scadenza:%d/%m/%Y}){dettaglio}.",
            policy,
        )
        chiuse += 1
    return chiuse


def esegui_automatismi(oggi: date | None = None) -> dict:
    """Esegue tutti gli automatismi e salva. Restituisce i conteggi."""
    oggi = oggi or date.today()
    settings = Settings.get()
    esito = {
        "rinnovi_taciti": rinnova_taciti(oggi, settings),
        "quietanze": emetti_quietanze(oggi, settings),
        "scadute": scadi_polizze(oggi, settings),
    }
    if any(esito.values()):
        db.session.commit()
    return esito


"""Titoli di premio: generazione delle rate di un'annualità e rinnovi.

Per ogni annualità di polizza si generano tanti titoli quante sono le rate
del frazionamento (annuale = 1, semestrale = 2, … mensile = 12). L'importo è
diviso in parti uguali e l'eventuale resto dell'arrotondamento finisce
sull'ultima rata, così la somma coincide sempre con il premio annuo.
"""
from __future__ import annotations

import calendar
from datetime import date

from .models import Policy, Title


class TitoliGiaPresenti(Exception):
    """L'annualità richiesta ha già dei titoli (non stornati)."""


def add_months(giorno: date, mesi: int) -> date:
    """Somma (o sottrae) mesi a una data, rispettando la fine del mese."""
    indice = giorno.month - 1 + mesi
    anno = giorno.year + indice // 12
    mese = indice % 12 + 1
    return date(anno, mese, min(giorno.day, calendar.monthrange(anno, mese)[1]))


def annualita_corrente(policy: Policy) -> tuple[date, date]:
    """Periodo dell'annualità in corso: i 12 mesi che terminano alla scadenza."""
    if policy.data_scadenza:
        return add_months(policy.data_scadenza, -12), policy.data_scadenza
    inizio = policy.data_decorrenza or date.today()
    return inizio, add_months(inizio, 12)


def titoli_annualita(policy: Policy, inizio: date, fine: date) -> list[Title]:
    """Titoli non stornati con effetto nell'annualità [inizio, fine)."""
    return [
        t for t in policy.titoli
        if t.stato != "stornato" and inizio <= t.data_effetto < fine
    ]


def genera_titoli(
    policy: Policy,
    inizio: date | None = None,
    fine: date | None = None,
    premio: float | None = None,
    tipo_primo: str | None = None,
) -> list[Title]:
    """Crea (senza salvarli) i titoli di un'annualità della polizza.

    Solleva ``ValueError`` se manca il premio e ``TitoliGiaPresenti`` se per
    quell'annualità esistono già titoli attivi.
    """
    if inizio is None or fine is None:
        inizio, fine = annualita_corrente(policy)
    premio = policy.premio_annuo if premio is None else premio
    if not premio or premio <= 0:
        raise ValueError("Per generare i titoli serve il premio annuo della polizza.")
    if titoli_annualita(policy, inizio, fine):
        raise TitoliGiaPresenti(
            f"L'annualità {inizio.strftime('%d/%m/%Y')} – {fine.strftime('%d/%m/%Y')} ha già dei titoli."
        )

    if tipo_primo is None:
        nuova = policy.data_decorrenza is not None and policy.data_decorrenza >= inizio
        tipo_primo = "perfezionamento" if nuova else "quietanza"

    rate = policy.rate_annue
    passo = 12 // rate
    importo_rata = round(premio / rate, 2)
    titoli = []
    for i in range(rate):
        ultima = i == rate - 1
        importo = round(premio - importo_rata * (rate - 1), 2) if ultima else importo_rata
        provvigione = (
            round(importo * policy.provvigione_perc / 100.0, 2)
            if policy.provvigione_perc
            else None
        )
        titoli.append(
            Title(
                policy_id=policy.id,
                client_id=policy.client_id,
                tipo=tipo_primo if i == 0 else "rata",
                numero_rata=i + 1,
                rate_totali=rate,
                data_effetto=add_months(inizio, i * passo),
                data_fine_copertura=fine if ultima else add_months(inizio, (i + 1) * passo),
                premio_lordo=importo,
                provvigione=provvigione,
                stato="da_incassare",
            )
        )
    policy.titoli.extend(titoli)
    return titoli

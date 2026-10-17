"""Titoli di premio: periodi di polizza, generazione delle rate e rinnovi.

**Periodi.** Le annualità di una polizza si calcolano a ritroso dalla
scadenza, a passi di 12 mesi, fino alla decorrenza: così una polizza
poliennale ha tutte le sue annualità, e un eventuale periodo iniziale più
corto (rateo, es. allineamento al 31/12) è il primo periodo.

**Rate.** Per ogni periodo si generano le rate del frazionamento (annuale = 1,
semestrale = 2, … mensile = 12) con effetto dentro il periodo. Se il periodo
non dura 12 mesi il premio è calcolato pro rata giorni. Premio e provvigione
sono ripartiti in parti uguali (annualità piena) o in proporzione alla durata
di ciascuna rata (periodo ridotto), con arrotondamento commerciale e il resto
sull'ultima rata: le somme coincidono sempre con i totali.
"""
from __future__ import annotations

from datetime import date, timedelta

from .models import Policy, Title
from .utils import add_months, arrotonda, ripartisci

# Limite di sicurezza sul numero di periodi calcolati per una polizza.
MAX_PERIODI = 60


class TitoliGiaPresenti(Exception):
    """Il periodo richiesto ha già dei titoli (non stornati)."""


def _passi_indietro(fine: date, passi: int) -> date | None:
    try:
        return add_months(fine, -12 * passi)
    except (ValueError, OverflowError):
        return None


def periodi_polizza(policy: Policy, fino_a: date | None = None) -> list[tuple[date, date]]:
    """Annualità della polizza come lista di (inizio, fine) in ordine cronologico.

    - Con scadenza: a ritroso dalla scadenza fino alla decorrenza (il primo
      periodo può essere più corto: rateo). Senza decorrenza: solo l'ultima
      annualità.
    - Senza scadenza (es. vita, PIP): annualità dalla decorrenza in avanti fino
      a quella che contiene ``fino_a`` (default oggi).
    """
    oggi = fino_a or date.today()
    decorrenza, scadenza = policy.data_decorrenza, policy.data_scadenza
    if scadenza:
        if decorrenza and decorrenza >= scadenza:
            return []
        periodi = []
        fine = scadenza
        for passo in range(1, MAX_PERIODI + 1):
            inizio = _passi_indietro(scadenza, passo)
            if inizio is None:
                break
            if decorrenza is None:
                periodi.append((inizio, fine))
                break
            if inizio <= decorrenza:
                periodi.append((decorrenza, fine))
                break
            periodi.append((inizio, fine))
            fine = inizio
        return list(reversed(periodi))
    if decorrenza:
        periodi = []
        # Polizze molto vecchie: si parte abbastanza avanti da arrivare sempre
        # all'annualità che contiene ``oggi`` entro MAX_PERIODI passi.
        primo_passo = max(0, (oggi.year - decorrenza.year) - MAX_PERIODI + 2)
        for passo in range(primo_passo, primo_passo + MAX_PERIODI):
            try:
                inizio = add_months(decorrenza, 12 * passo)
                fine = add_months(decorrenza, 12 * (passo + 1))
            except (ValueError, OverflowError):
                break
            periodi.append((inizio, fine))
            if fine > oggi:
                break
        return periodi
    return []


def annualita_corrente(policy: Policy, oggi: date | None = None) -> tuple[date, date] | None:
    """Annualità che contiene ``oggi``: la prima se la polizza non è ancora in
    vigore, l'ultima se è già scaduta. None se le date non lo consentono."""
    oggi = oggi or date.today()
    periodi = periodi_polizza(policy, fino_a=oggi)
    if not periodi:
        return None
    for inizio, fine in periodi:
        if inizio <= oggi < fine:
            return inizio, fine
    return periodi[0] if oggi < periodi[0][0] else periodi[-1]


def annualita_piena(inizio: date, fine: date) -> bool:
    """True se il periodo dura esattamente un anno, contato in avanti o (come
    fa periodi_polizza) a ritroso dalla fine: 28/02/2027 – 29/02/2028 è pieno."""
    try:
        return add_months(inizio, 12) == fine or add_months(fine, -12) == inizio
    except (ValueError, OverflowError):
        return False


def premio_periodo(premio_annuo: float, inizio: date, fine: date) -> float:
    """Premio di un periodo: pieno per 12 mesi, altrimenti pro rata giorni."""
    if annualita_piena(inizio, fine):
        return arrotonda(premio_annuo)
    try:
        giorni_anno = (add_months(inizio, 12) - inizio).days
    except (ValueError, OverflowError):
        giorni_anno = 365
    return arrotonda(premio_annuo * (fine - inizio).days / giorni_anno)


def titoli_periodo(policy: Policy, inizio: date, fine: date) -> list[Title]:
    """Titoli ordinari (perfezionamento, quietanza, rata) non stornati con
    effetto nel periodo (per l'elenco delle annualità nella scheda).

    Le appendici (regolazioni, variazioni, rimborsi) non contano: possono
    convivere con le rate ordinarie della stessa annualità.
    """
    return [
        t for t in policy.titoli
        if t.stato != "stornato" and t.tipo != "appendice" and inizio <= t.data_effetto < fine
    ]


def _fine_copertura(titolo: Title) -> date:
    """Fine (esclusa) della copertura di un titolo; in mancanza, il giorno dopo l'effetto."""
    if titolo.data_fine_copertura and titolo.data_fine_copertura > titolo.data_effetto:
        return titolo.data_fine_copertura
    return titolo.data_effetto + timedelta(days=1)


def titoli_coprono(policy: Policy, inizio: date, fine: date, includi_stornati: bool = False) -> list[Title]:
    """Titoli ordinari la cui copertura si sovrappone al periodo [inizio, fine).

    Serve a decidere se un periodo è già stato emesso: guardare solo la data
    effetto non basta, perché spostando decorrenza o scadenza (o rinnovando per
    una durata diversa da 12 mesi) la griglia delle annualità si sposta e un
    titolo già emesso finirebbe nel periodo accanto, che sembrerebbe scoperto.
    Con ``includi_stornati`` conta anche i titoli stornati (emissione
    automatica: un titolo stornato o eliminato dall'operatore non si riemette).
    """
    return [
        t for t in policy.titoli
        if t.tipo != "appendice"
        and (includi_stornati or t.stato != "stornato")
        and t.data_effetto < fine and _fine_copertura(t) > inizio
    ]


# Nome storico, usato dalle route.
titoli_annualita = titoli_periodo


def date_rate(policy: Policy, inizio: date, fine: date) -> list[tuple[date, date]]:
    """Periodi di copertura delle rate del frazionamento dentro [inizio, fine)."""
    passo = 12 // policy.rate_annue
    rate = []
    for i in range(policy.rate_annue):
        try:
            effetto = add_months(inizio, i * passo)
        except (ValueError, OverflowError):
            break
        if effetto >= fine:
            break
        if i == policy.rate_annue - 1:
            fine_rata = fine  # l'ultima rata arriva sempre a fine periodo (es. 29 febbraio)
        else:
            try:
                fine_rata = min(add_months(inizio, (i + 1) * passo), fine)
            except (ValueError, OverflowError):
                fine_rata = fine
        rate.append((effetto, fine_rata))
    return rate


def genera_titoli(
    policy: Policy,
    inizio: date | None = None,
    fine: date | None = None,
    premio: float | None = None,
    tipo_primo: str | None = None,
) -> list[Title]:
    """Crea (senza salvarli) i titoli di un periodo della polizza.

    Senza ``inizio``/``fine`` usa l'annualità corrente. ``premio`` è il premio
    ANNUO (default quello della polizza): per un periodo più corto viene
    ricalcolato pro rata. Solleva ``ValueError`` se mancano premio o date e
    ``TitoliGiaPresenti`` se il periodo ha già titoli ordinari.
    """
    if inizio is None or fine is None:
        periodo = annualita_corrente(policy)
        if periodo is None:
            raise ValueError("Per generare i titoli servono decorrenza o scadenza valide.")
        inizio, fine = periodo
    if fine <= inizio:
        raise ValueError("Il periodo dei titoli non è valido (fine non successiva all'inizio).")
    premio_annuo = policy.premio_annuo if premio is None else premio
    if not premio_annuo or premio_annuo <= 0:
        raise ValueError("Per generare i titoli serve il premio annuo della polizza.")
    if titoli_coprono(policy, inizio, fine):
        raise TitoliGiaPresenti(
            f"Il periodo {inizio:%d/%m/%Y} – {fine:%d/%m/%Y} ha già dei titoli."
        )

    if tipo_primo is None:
        tipo_primo = (
            "perfezionamento"
            if policy.data_decorrenza is not None and inizio == policy.data_decorrenza
            else "quietanza"
        )

    rate = date_rate(policy, inizio, fine)
    totale = premio_periodo(premio_annuo, inizio, fine)
    # Annualità piena: rate uguali (come le emettono le compagnie). Periodo
    # ridotto (rateo): ripartizione in proporzione alla durata di ogni rata.
    pesi = [1] * len(rate) if annualita_piena(inizio, fine) else [(f - e).days for e, f in rate]
    premi = ripartisci(totale, pesi)
    provvigioni = (
        ripartisci(arrotonda(totale * policy.provvigione_perc / 100.0), pesi)
        if policy.provvigione_perc
        else [None] * len(rate)
    )
    titoli = [
        Title(
            policy_id=policy.id,
            client_id=policy.client_id,
            tipo=tipo_primo if i == 0 else "rata",
            numero_rata=i + 1,
            rate_totali=len(rate),
            data_effetto=effetto,
            data_fine_copertura=fine_rata,
            premio_lordo=premi[i],
            provvigione=provvigioni[i],
            stato="da_incassare",
        )
        for i, (effetto, fine_rata) in enumerate(rate)
    ]
    policy.titoli.extend(titoli)
    return titoli


def prossima_scadenza_utile(scadenza: date, oggi: date | None = None) -> date | None:
    """Primo anniversario della scadenza successivo a oggi (per i rinnovi)."""
    oggi = oggi or date.today()
    for passi in range(1, MAX_PERIODI + 1):
        try:
            candidata = add_months(scadenza, 12 * passi)
        except (ValueError, OverflowError):
            return None
        if candidata > oggi:
            return candidata
    return None

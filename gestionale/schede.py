"""Compilazione delle schede dell'Accademia dentro il gestionale.

Ogni campo di una scheda ha una chiave stabile ricavata dalla sua posizione:
- campi:     s{sezione}c{campo}
- domande:   s{sezione}d{domanda}
- check:     s{sezione}v{voce}            (valore booleano)
- tabella:   s{sezione}r{riga}k{colonna}  (nelle righe fisse la colonna 0 è
                                           l'etichetta e non si compila)
più la chiave "note". La scheda compilata salva anche la struttura, quindi le
chiavi restano valide anche se i modelli in academy.py cambiano in futuro.
"""
from datetime import date

LIMITE_CAMPO = 300
LIMITE_TESTO = 3000
LIMITE_CELLA = 200


def righe_tabella(sezione: dict) -> int:
    return len(sezione["righe_fisse"]) if sezione.get("righe_fisse") else sezione.get("righe", 0)


def chiavi(scheda: dict) -> list[tuple[str, str]]:
    """Elenco (chiave, tipo) di tutti i campi compilabili della scheda."""
    out = []
    for si, sez in enumerate(scheda["sezioni"]):
        tipo = sez["tipo"]
        if tipo == "campi":
            out += [(f"s{si}c{ci}", "campo") for ci in range(len(sez["campi"]))]
        elif tipo == "domande":
            out += [(f"s{si}d{di}", "testo") for di in range(len(sez["domande"]))]
        elif tipo == "check":
            out += [(f"s{si}v{vi}", "check") for vi in range(len(sez["voci"]))]
        elif tipo == "tabella":
            prima = 1 if sez.get("righe_fisse") else 0
            for ri in range(righe_tabella(sez)):
                out += [(f"s{si}r{ri}k{ki}", "cella") for ki in range(prima, len(sez["colonne"]))]
    out.append(("note", "testo"))
    return out


def leggi_form(scheda: dict, form) -> dict:
    """Valori della scheda dal form inviato, puliti e limitati in lunghezza."""
    limiti = {"campo": LIMITE_CAMPO, "testo": LIMITE_TESTO, "cella": LIMITE_CELLA}
    valori = {}
    for chiave, tipo in chiavi(scheda):
        if tipo == "check":
            valori[chiave] = form.get(chiave) == "1"
        else:
            valori[chiave] = (form.get(chiave) or "").strip()[: limiti[tipo]]
    return valori


def _euro(valore) -> str:
    if valore is None:
        return ""
    return ("€\u00a0{:,.2f}".format(valore)).replace(",", "X").replace(".", ",").replace("X", ".")


def _indirizzo(c) -> str:
    parti = [c.indirizzo, " ".join(p for p in [c.cap, c.citta] if p)]
    testo = ", ".join(p for p in parti if p)
    return f"{testo} ({c.provincia})" if testo and c.provincia else testo


def precompila(scheda: dict, client) -> dict:
    """Valori iniziali presi da anagrafica e polizze attive del cliente.

    Il consulente li vede già scritti e li corregge se serve: la scheda
    raccoglie ciò che il cliente dice in aggiunta a quanto è già registrato.
    """
    c = client
    polizze = [p for p in c.polizze if p.stato in ("attiva", "in_rinnovo")]
    campi_da_anagrafica = {
        "Nome e cognome": c.ragione_sociale,
        "Ragione sociale e forma giuridica": c.ragione_sociale,
        "Cliente": c.ragione_sociale,
        "Cliente e data": c.ragione_sociale,
        "Cliente e interlocutore": " · ".join(p for p in [c.ragione_sociale, c.referente] if p),
        "Partita IVA / codice ATECO": " / ".join(p for p in [c.partita_iva, c.codice_ateco] if p),
        "Professione e tipo di contratto (dipendente, autonomo, pensionato)": c.professione or "",
        "Datore di lavoro / attività": c.datore_lavoro or c.settore or "",
        "Fatturato ultimo esercizio": _euro(c.fatturato_annuo),
        "Numero di dipendenti e collaboratori": str(c.numero_dipendenti) if c.numero_dipendenti else "",
        "Sedi e unità locali (indirizzi)": _indirizzo(c),
        "Coperture già note / gap dall'analisi": ", ".join(sorted({p.ramo_label for p in polizze})),
        "Data": date.today().strftime("%d/%m/%Y"),
    }
    valori = {}
    for si, sez in enumerate(scheda["sezioni"]):
        if sez["tipo"] == "campi":
            for ci, etichetta in enumerate(sez["campi"]):
                if campi_da_anagrafica.get(etichetta):
                    valori[f"s{si}c{ci}"] = campi_da_anagrafica[etichetta]
        elif sez["tipo"] == "tabella" and not sez.get("righe_fisse"):
            if "Coperture in essere" in sez["titolo"]:
                for ri, p in enumerate(polizze[: righe_tabella(sez)]):
                    cella = {
                        "Ramo": p.ramo_label,
                        "Compagnia": p.compagnia,
                        "Massimale": _euro(p.massimale),
                        "Massimale / capitale": _euro(p.massimale),
                        "Premio": _euro(p.premio_annuo),
                        "Premio annuo": _euro(p.premio_annuo),
                        "Scadenza": p.data_scadenza.strftime("%d/%m/%Y") if p.data_scadenza else "",
                        "Note": f"Polizza {p.numero_polizza}",
                    }
                    for ki, col in enumerate(sez["colonne"]):
                        if cella.get(col):
                            valori[f"s{si}r{ri}k{ki}"] = cella[col]
            elif sez["colonne"] and sez["colonne"][0] == "Polizza":
                for ri, p in enumerate(polizze[: righe_tabella(sez)]):
                    valori[f"s{si}r{ri}k0"] = f"{p.numero_polizza} · {p.ramo_label}"
    return valori


# Schede che riguardano un singolo cliente (le altre sono del consulente:
# piano settimanale, griglia di role-play, registro delle obiezioni).
SCHEDE_CLIENTE = [
    "raccolta-privato", "raccolta-azienda", "informazioni-da-dare",
    "preparazione-appuntamento", "diario-trattativa", "piano-negoziazione",
    "revisione-annuale", "mappa-referenze", "post-vendita",
]

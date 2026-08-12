"""Motore di analisi automatica dei rischi.

Analizza la descrizione dell'attività di un cliente (più i dati
strutturati dell'anagrafica: tipo, dipendenti, fatturato) e produce:

- l'elenco dei pericoli rilevati, con severità e parole chiave trovate;
- le coperture assicurative consigliate per ciascun pericolo;
- la gap analysis rispetto alle polizze attive del cliente
  (coperture consigliate ma scoperte vs. già presenti).

Il motore è basato su regole a parole chiave in italiano: non richiede
servizi esterni e i risultati sono sempre spiegabili (ogni rischio
riporta le parole che l'hanno attivato).
"""
from __future__ import annotations

import unicodedata
from datetime import datetime

from .models import BRANCH_LABELS

# ----------------------------------------------------------------------
# Regole: ogni regola descrive un pericolo, le parole chiave (radici,
# confrontate come sottostringhe del testo normalizzato), il peso di
# ciascun match e le coperture/rami consigliati.
# ----------------------------------------------------------------------
RISK_RULES = [
    {
        "id": "incendio",
        "nome": "Incendio ed esplosione",
        "descrizione": "Presenza di locali, merci, materiali o lavorazioni esposti al rischio di incendio o esplosione.",
        "keywords": [
            "magazzino", "deposito", "officina", "laboratorio", "capannone",
            "stoccaggio", "legno", "falegnam", "vernic", "solvent",
            "infiammabil", "cucina", "forno", "ristorant", "pizzeria",
            "plastica", "carta", "tessil", "saldatur", "carburant",
            "gpl", "gas", "stabiliment", "torrefazione", "panificio",
        ],
        "rami": ["incendio"],
        "coperture": ["Incendio / All Risks su fabbricato, contenuto e merci"],
    },
    {
        "id": "furto",
        "nome": "Furto, rapina e atti vandalici",
        "descrizione": "Beni, merci o valori esposti al rischio di furto o rapina.",
        "keywords": [
            "negozio", "gioiell", "orefic", "contant", "cassa", "merce",
            "magazzino", "elettronic", "boutique", "tabacch", "farmacia",
            "vendita al dettaglio", "showroom", "esposizione", "attrezzatur",
        ],
        "rami": ["furto"],
        "coperture": ["Furto e rapina su merci, attrezzature e valori"],
    },
    {
        "id": "rc_terzi",
        "nome": "Responsabilità civile verso terzi",
        "descrizione": "Danni a persone o cose di terzi causati nell'esercizio dell'attività o nei locali aperti al pubblico.",
        "keywords": [
            "clienti", "pubblico", "negozio", "cantiere", "installazion",
            "manutenzion", "montaggio", "eventi", "ristorant", "bar",
            "hotel", "alberg", "palestra", "scuola", "assistenza",
            "riparazion", "impiant", "pulizie", "b&b", "affitto",
        ],
        "rami": ["rct_rco"],
        "coperture": ["RC Terzi (RCT) con estensione RCO se sono presenti dipendenti"],
    },
    {
        "id": "infortuni_personale",
        "nome": "Infortuni del personale",
        "descrizione": "Presenza di dipendenti o collaboratori esposti a infortuni sul lavoro (rivalsa INAIL, danno differenziale).",
        "keywords": [
            "dipendent", "operai", "addett", "personale", "collaborator",
            "apprendist", "squadr", "tecnici", "installator", "magazzinier",
        ],
        "rami": ["rct_rco", "infortuni"],
        "coperture": [
            "RC Prestatori d'Opera (RCO)",
            "Infortuni cumulativa dipendenti",
        ],
    },
    {
        "id": "rc_professionale",
        "nome": "Responsabilità professionale",
        "descrizione": "Errori od omissioni nell'attività intellettuale o di consulenza che possono causare danni patrimoniali ai clienti.",
        "keywords": [
            "consulen", "progettazion", "ingegner", "architett", "avvocat",
            "commercialist", "revisor", "medic", "odontoiatr", "psicolog",
            "geometr", "perito", "broker", "immobiliar", "formazion",
            "contabil", "paghe", "fiscal", "tributar", "notai", "veterinar",
            "amministrator di condominio", "certificazion", "collaud",
        ],
        "rami": ["rc_professionale"],
        "coperture": ["RC Professionale (obbligatoria per molte professioni ordinistiche)"],
    },
    {
        "id": "cyber",
        "nome": "Rischio informatico (cyber)",
        "descrizione": "Trattamento di dati, dipendenza da sistemi informatici o vendite online: esposizione ad attacchi, ransomware e violazioni GDPR.",
        "keywords": [
            "dati", "e-commerce", "ecommerce", "online", "sito web",
            "software", "gestional", "cloud", "pagament", "informatic",
            "digital", "crm", "server", "privacy", "gdpr", "app",
            "piattaform", "sanitar", "fattur",
        ],
        "rami": ["cyber"],
        "coperture": ["Cyber Risk (danni propri, interruzione attività, RC verso terzi, GDPR)"],
    },
    {
        "id": "rc_prodotti",
        "nome": "Responsabilità da prodotto",
        "descrizione": "Produzione, lavorazione o commercializzazione di prodotti che possono causare danni dopo la consegna.",
        "keywords": [
            "produzion", "produce", "produciamo", "fabbric", "aliment",
            "bevande", "cosmetic", "dispositivi", "componenti", "export",
            "lavorazion", "assemblaggio", "conserv", "imbottigliament",
        ],
        "rami": ["rc_prodotti"],
        "coperture": ["RC Prodotti (con ritiro prodotti se settore alimentare/regolamentato)"],
    },
    {
        "id": "trasporto_merci",
        "nome": "Trasporto e giacenza merci",
        "descrizione": "Merci proprie o di terzi movimentate, trasportate o consegnate.",
        "keywords": [
            "trasport", "logistic", "spedizion", "corriere", "autocarr",
            "furgon", "consegn", "distribuzion", "vettor", "magazzino conto terzi",
        ],
        "rami": ["trasporti"],
        "coperture": ["Trasporti / Merci trasportate (vettoriale o danni propri)"],
    },
    {
        "id": "flotta_veicoli",
        "nome": "Veicoli e trasferte",
        "descrizione": "Uso di veicoli aziendali o trasferte frequenti del personale.",
        "keywords": [
            "flotta", "automezzi", "autocarr", "furgon", "veicol",
            "trasfert", "agenti", "rete commerciale", "cantieri esterni",
        ],
        "rami": ["auto"],
        "coperture": ["RCA flotte, Kasko dipendenti in missione, infortuni conducenti"],
    },
    {
        "id": "ambientale",
        "nome": "Inquinamento e danno ambientale",
        "descrizione": "Sostanze, lavorazioni o depositi che possono contaminare suolo, acqua o aria.",
        "keywords": [
            "chimic", "rifiut", "sostanze pericolose", "inquin",
            "verniciatur", "solvent", "depurazion", "smaltiment",
            "carburant", "serbatoi", "galvanic", "concia", "amianto",
        ],
        "rami": ["rc_ambientale"],
        "coperture": ["RC Inquinamento / danno ambientale (D.Lgs. 152/2006)"],
    },
    {
        "id": "guasti_macchine",
        "nome": "Guasti a macchinari e impianti",
        "descrizione": "Macchinari, impianti o apparecchiature la cui indisponibilità blocca l'attività.",
        "keywords": [
            "macchinar", "impiant", "cnc", "torni", "presse", "robot",
            "linea di produzione", "forni", "celle frigorifer", "server",
            "attrezzatur", "generator", "compressor",
        ],
        "rami": ["guasti_macchine"],
        "coperture": ["Guasti macchine / elettronica, con danni indiretti da fermo attività"],
    },
    {
        "id": "do",
        "nome": "Responsabilità degli amministratori (D&O)",
        "descrizione": "Responsabilità personale di amministratori e sindaci verso società, soci, creditori e terzi.",
        "keywords": [
            "srl", "s.r.l", "spa", "s.p.a", "consiglio di amministrazione",
            "cda", "holding", "gruppo", "soci",
        ],
        "rami": ["do"],
        "coperture": ["D&O — responsabilità civile di amministratori e sindaci"],
    },
    {
        "id": "cauzioni",
        "nome": "Appalti e obblighi contrattuali",
        "descrizione": "Partecipazione a gare o appalti che richiedono garanzie fideiussorie.",
        "keywords": [
            "appalt", "gare", "gara pubblica", "cantier", "edil",
            "costruzion", "subappalt", "pubblica amministrazione", "bandi",
        ],
        "rami": ["cauzioni"],
        "coperture": ["Cauzioni / fideiussioni per gare e appalti", "Postuma decennale se edilizia"],
    },
    {
        "id": "credito",
        "nome": "Credito commerciale",
        "descrizione": "Vendite B2B con pagamenti dilazionati: rischio di insoluti.",
        "keywords": [
            "dilazion", "pagamento a 30", "pagamento a 60", "pagamento a 90",
            "b2b", "export", "fornitur", "grossist", "rivendit",
        ],
        "rami": ["credito"],
        "coperture": ["Assicurazione del credito commerciale"],
    },
]

# Rami consigliati d'ufficio in base al tipo di cliente, anche senza
# riscontri nel testo (raccomandazioni di base).
BASELINE_BY_TYPE = {
    "azienda": [
        {
            "id": "catastrofali_base",
            "nome": "Eventi catastrofali (obbligo di legge)",
            "descrizione": "Le imprese con sede in Italia sono tenute a coprire i beni strumentali contro sismi, alluvioni e frane (L. 213/2023).",
            "rami": ["catastrofali"],
            "coperture": ["Polizza catastrofale su terreni, fabbricati, impianti e attrezzature"],
        },
        {
            "id": "tutela_legale_base",
            "nome": "Tutela legale",
            "descrizione": "Spese legali per vertenze con dipendenti, fornitori, clienti o pubblica amministrazione.",
            "rami": ["tutela_legale"],
            "coperture": ["Tutela legale aziendale"],
        },
    ],
    "professionista": [
        {
            "id": "rc_professionale_base",
            "nome": "RC Professionale",
            "descrizione": "Copertura obbligatoria o fortemente raccomandata per l'attività professionale.",
            "rami": ["rc_professionale"],
            "coperture": ["RC Professionale"],
        },
        {
            "id": "infortuni_base",
            "nome": "Infortuni e malattia del professionista",
            "descrizione": "La capacità di produrre reddito dipende dalla persona: coprire infortuni e inabilità.",
            "rami": ["infortuni", "malattia"],
            "coperture": ["Infortuni 24h", "Malattia / diaria da inabilità"],
        },
        {
            "id": "tutela_legale_base",
            "nome": "Tutela legale",
            "descrizione": "Spese legali per vertenze professionali, fiscali o con committenti.",
            "rami": ["tutela_legale"],
            "coperture": ["Tutela legale professionale"],
        },
    ],
}


def _normalize(text: str) -> str:
    """Minuscole e senza accenti, per un confronto robusto delle parole chiave."""
    text = (text or "").lower()
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


def _severity(score: int) -> str:
    if score >= 3:
        return "alta"
    if score == 2:
        return "media"
    return "bassa"


def analyze_risks(
    description: str,
    *,
    client_type: str = "azienda",
    employees: int | None = None,
    revenue: float | None = None,
    active_branches: set[str] | None = None,
) -> dict:
    """Esegue l'analisi dei rischi e la gap analysis.

    ``active_branches`` è l'insieme dei rami delle polizze attive del
    cliente: serve a calcolare le coperture già presenti vs. scoperte.
    """
    text = _normalize(description)
    active_branches = active_branches or set()

    detected = []
    for rule in RISK_RULES:
        matched = sorted({kw for kw in rule["keywords"] if _normalize(kw) in text})
        score = len(matched)

        # Potenziamenti dai dati strutturati dell'anagrafica.
        if rule["id"] == "infortuni_personale" and (employees or 0) > 0:
            score += 2
            matched.append(f"{employees} dipendenti in anagrafica")
        if rule["id"] == "do" and (revenue or 0) >= 1_000_000:
            score += 1
            matched.append("fatturato ≥ 1 mln € in anagrafica")
        if rule["id"] == "rc_professionale" and client_type == "professionista" and score:
            score += 1

        if score > 0:
            detected.append(
                {
                    "id": rule["id"],
                    "nome": rule["nome"],
                    "descrizione": rule["descrizione"],
                    "severita": _severity(score),
                    "punteggio": score,
                    "parole_chiave": matched,
                    "rami": rule["rami"],
                    "coperture_consigliate": rule["coperture"],
                    "baseline": False,
                }
            )

    detected.sort(key=lambda r: -r["punteggio"])

    # Raccomandazioni di base per il tipo di cliente (senza duplicare
    # pericoli già rilevati sugli stessi rami).
    detected_ids = {r["id"] for r in detected}
    for base in BASELINE_BY_TYPE.get(client_type, []):
        if base["id"].replace("_base", "") in detected_ids:
            continue
        detected.append(
            {
                "id": base["id"],
                "nome": base["nome"],
                "descrizione": base["descrizione"],
                "severita": "media",
                "punteggio": 0,
                "parole_chiave": [],
                "rami": base["rami"],
                "coperture_consigliate": base["coperture"],
                "baseline": True,
            }
        )

    # Gap analysis: rami consigliati vs. rami delle polizze attive.
    recommended_branches: dict[str, list[str]] = {}
    for risk in detected:
        for branch in risk["rami"]:
            recommended_branches.setdefault(branch, []).append(risk["nome"])

    covered, uncovered = [], []
    for branch, risk_names in sorted(recommended_branches.items()):
        entry = {
            "ramo": branch,
            "nome_ramo": BRANCH_LABELS.get(branch, branch),
            "rischi": risk_names,
        }
        (covered if branch in active_branches else uncovered).append(entry)

    return {
        "generata_il": datetime.utcnow().isoformat(timespec="seconds"),
        "rischi": detected,
        "coperture_presenti": covered,
        "coperture_scoperte": uncovered,
        "sintesi": {
            "rischi_rilevati": len([r for r in detected if not r["baseline"]]),
            "raccomandazioni_base": len([r for r in detected if r["baseline"]]),
            "rami_scoperti": len(uncovered),
            "rami_coperti": len(covered),
        },
    }


def analyze_client(client, description: str | None = None) -> dict:
    """Analizza un cliente del gestionale usando anagrafica + polizze attive."""
    text = description if description is not None else (client.descrizione_attivita or "")
    # Includiamo settore e professione: spesso la descrizione è breve.
    full_text = " ".join(filter(None, [text, client.settore, client.professione]))
    active = {p.ramo for p in client.polizze if p.stato in ("attiva", "in_rinnovo")}
    return analyze_risks(
        full_text,
        client_type=client.tipo,
        employees=client.numero_dipendenti,
        revenue=client.fatturato_annuo,
        active_branches=active,
    )

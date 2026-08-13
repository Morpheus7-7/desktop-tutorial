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
    "dipendente": [
        {
            "id": "infortuni_base",
            "nome": "Infortuni 24 ore (anche extra-lavoro)",
            "descrizione": "Il reddito della famiglia dipende dalla persona: un infortunio anche nel tempo libero può azzerarlo. L'INAIL copre solo l'ambito lavorativo.",
            "rami": ["infortuni"],
            "coperture": ["Infortuni 24h con diaria da ricovero e invalidità permanente"],
        },
        {
            "id": "malattia_base",
            "nome": "Salute e rimborso spese mediche",
            "descrizione": "Liste d'attesa lunghe nel pubblico: una polizza salute dà accesso rapido a visite e interventi.",
            "rami": ["malattia"],
            "coperture": ["Rimborso spese mediche / diaria da ricovero"],
        },
        {
            "id": "vita_base",
            "nome": "Tutela del reddito familiare (TCM)",
            "descrizione": "In caso di premorienza del percettore di reddito, una temporanea caso morte protegge mutuo e tenore di vita della famiglia.",
            "rami": ["vita"],
            "coperture": ["Temporanea caso morte a copertura del mutuo/famiglia"],
        },
        {
            "id": "rc_capofamiglia_base",
            "nome": "RC Capofamiglia",
            "descrizione": "Danni involontari causati a terzi nella vita privata dai membri della famiglia (anche figli e animali domestici).",
            "rami": ["rc_capofamiglia"],
            "coperture": ["RC della vita privata / capofamiglia"],
        },
        {
            "id": "tutela_legale_base",
            "nome": "Tutela legale privata",
            "descrizione": "Spese legali per controversie di lavoro, condominiali, di consumo o con la P.A.",
            "rami": ["tutela_legale"],
            "coperture": ["Tutela legale della famiglia"],
        },
    ],
}

# ----------------------------------------------------------------------
# Spunti di trattativa per ramo: pensiero laterale + esempio in terza
# persona + i vantaggi da portare in trattativa. Servono a supportare
# l'intermediario nella vendita consulenziale della copertura.
# ----------------------------------------------------------------------
TRATTATIVA = {
    "incendio": {
        "leva": "Non è «se» accade, ma «quanto costa» se accade: l'incendio è l'evento che più spesso chiude un'impresa che non era coperta.",
        "esempio": "Un imprenditore era convinto che «tanto ho gli estintori». Dopo un corto circuito di notte ha perso capannone e magazzino: senza polizza avrebbe chiuso, con la copertura ha riaperto in sei mesi.",
        "pro": [
            "Ricostruisce fabbricato, macchinari e merci a valore a nuovo",
            "Con la garanzia «danni indiretti» copre anche il fermo attività",
            "Premio spesso inferiore all'1% del valore assicurato",
        ],
    },
    "furto": {
        "leva": "Il danno del furto non è solo la merce rubata: è la vetrina sfondata, i giorni di chiusura e i clienti persi.",
        "esempio": "Una titolare di negozio pensava bastasse l'allarme. Dopo una spaccata notturna ha pagato di tasca propria vetrina e riparazioni: più del premio di tre anni di polizza.",
        "pro": [
            "Copre merci, attrezzature e valori, oltre ai guasti da effrazione",
            "Estendibile a rapina e portavalori",
            "Riduce l'esposizione proprio nei periodi di magazzino pieno",
        ],
    },
    "rct_rco": {
        "leva": "Basta un cliente che scivola o un dipendente che si infortuna per trasformare un'attività sana in una causa da centinaia di migliaia di euro.",
        "esempio": "Un ristoratore ha avuto un cliente caduto per un pavimento bagnato: risarcimento e spese legali sarebbero stati insostenibili, la RCT ha coperto tutto.",
        "pro": [
            "Protegge il patrimonio dell'impresa e del titolare",
            "L'estensione RCO copre la rivalsa INAIL e il danno differenziale sui dipendenti",
            "Richiesta di fatto da molti clienti e committenti",
        ],
    },
    "rc_professionale": {
        "leva": "La competenza non basta: un errore o una semplice contestazione può costare la parcella moltiplicata per dieci. Per molti ordini è anche un obbligo di legge.",
        "esempio": "Un progettista ha ricevuto una richiesta danni per un ritardo non dipeso da lui: la RC professionale ha pagato l'avvocato e la difesa, evitando un esborso enorme.",
        "pro": [
            "Copertura obbligatoria per le professioni ordinistiche",
            "Include la difesa legale, non solo il risarcimento",
            "Con la retroattività copre anche gli incarichi già svolti",
        ],
    },
    "cyber": {
        "leva": "«A me non capita» è la frase che precede un attacco. Oggi il rischio non è più solo delle grandi aziende: i ransomware colpiscono soprattutto le PMI, meno difese.",
        "esempio": "Uno studio si è ritrovato i file criptati e i dati dei clienti bloccati: senza cyber avrebbe pagato il riscatto e rischiato una sanzione GDPR; con la polizza ha avuto assistenza tecnica e legale immediata.",
        "pro": [
            "Copre ripristino dati, interruzione dell'attività e danni a terzi",
            "Include la gestione della violazione e gli obblighi GDPR",
            "Mette a disposizione tecnici e legali h24, non solo un rimborso",
        ],
    },
    "rc_prodotti": {
        "leva": "La responsabilità sul prodotto ti segue anche dopo la vendita: un difetto scoperto tra un anno è comunque un tuo problema.",
        "esempio": "Un produttore alimentare ha dovuto ritirare un lotto per un'etichetta errata: la RC prodotti ha coperto ritiro e richieste dei clienti, salvando il rapporto con la grande distribuzione.",
        "pro": [
            "Copre i danni causati dal prodotto dopo la consegna",
            "Estendibile alle spese di ritiro del prodotto (recall)",
            "Spesso richiesta da clienti esteri e dalla GDO",
        ],
    },
    "trasporti": {
        "leva": "Finché la merce viaggia, il rischio è tuo: un tamponamento o un furto sul furgone è una perdita secca se non è coperta.",
        "esempio": "Un corriere ha avuto un carico danneggiato in un incidente: la polizza trasporti ha rimborsato il valore, evitando la contestazione del committente.",
        "pro": [
            "Copre le merci proprie o di terzi durante il trasporto",
            "Adattabile a giacenza, carico/scarico e consegne",
            "Rassicura i committenti sulla continuità del servizio",
        ],
    },
    "auto": {
        "leva": "La RCA è obbligatoria, ma il vero buco è il conducente: se il dipendente si fa male alla guida, chi lo risarcisce?",
        "esempio": "Un'azienda con rete commerciale ha coperto i propri agenti con infortuni del conducente e kasko missione: dopo un incidente il collaboratore è stato tutelato e l'auto riparata subito.",
        "pro": [
            "Gestione unica della flotta con scadenze allineate",
            "Kasko e infortuni conducente per chi guida per lavoro",
            "Riduce i fermi e i contenziosi interni",
        ],
    },
    "rc_ambientale": {
        "leva": "Un danno ambientale non si «ripara» con due parole: la bonifica è obbligatoria per legge e i costi sono spesso a sei cifre.",
        "esempio": "Un'azienda ha avuto uno sversamento accidentale da un serbatoio: la RC inquinamento ha coperto la bonifica del suolo imposta dall'autorità.",
        "pro": [
            "Copre bonifica e danni ambientali (D.Lgs. 152/2006)",
            "Include le spese di prevenzione e ripristino",
            "Protegge da sanzioni e richieste di terzi",
        ],
    },
    "guasti_macchine": {
        "leva": "Se si ferma la macchina chiave, non perdi solo la riparazione: perdi la produzione di quei giorni e magari un ordine.",
        "esempio": "Un'officina ha avuto il guasto del centro di lavoro CNC: la polizza ha coperto riparazione e mancata produzione, evitando la penale sull'ordine in corso.",
        "pro": [
            "Copre guasti a macchinari, impianti ed elettronica",
            "Con i danni indiretti ristora il fermo attività",
            "Trasforma un fermo imprevisto in un costo pianificato",
        ],
    },
    "do": {
        "leva": "L'amministratore risponde con il patrimonio personale: casa e conti compresi. Non serve aver sbagliato, basta essere citati.",
        "esempio": "Un consigliere è stato chiamato in causa dai soci per una scelta gestionale: la D&O ha pagato la sua difesa, separando il rischio d'impresa da quello personale.",
        "pro": [
            "Protegge il patrimonio personale di amministratori e sindaci",
            "Copre le spese legali fin dalla prima contestazione",
            "Rende la carica più attrattiva per manager e consiglieri",
        ],
    },
    "cauzioni": {
        "leva": "Senza fideiussione non partecipi alla gara: la cauzione non è un costo, è la chiave d'ingresso al lavoro.",
        "esempio": "Un'impresa edile ha ottenuto la cauzione provvisoria in giornata e si è aggiudicata l'appalto: senza garanzia sarebbe rimasta fuori.",
        "pro": [
            "Sblocca la partecipazione a gare e appalti",
            "Non immobilizza liquidità come un deposito cauzionale",
            "Costruisce uno storico utile per garanzie future",
        ],
    },
    "credito": {
        "leva": "Vendere è facile, incassare no: basta un cliente importante che salta per mettere in crisi tutta la cassa.",
        "esempio": "Un fornitore B2B ha avuto un cliente insolvente per un ordine rilevante: l'assicurazione del credito ha rimborsato la fattura, evitando la crisi di liquidità.",
        "pro": [
            "Indennizza le fatture rimaste insolute",
            "Fornisce una valutazione preventiva dell'affidabilità dei clienti",
            "Protegge il margine e il rapporto con la banca",
        ],
    },
    "catastrofali": {
        "leva": "Ormai è un obbligo di legge per le imprese, ma è anche buon senso: alluvioni e frane non sono più eventi rari.",
        "esempio": "Un capannone allagato ha bloccato la produzione per settimane: chi aveva la copertura catastrofale ha ricostruito, gli altri hanno atteso ristori pubblici incerti.",
        "pro": [
            "Adempie all'obbligo di legge (L. 213/2023) per le imprese",
            "Copre sisma, alluvione e frana su beni strumentali",
            "Mette al riparo da eventi sempre più frequenti",
        ],
    },
    "infortuni": {
        "leva": "Il vero patrimonio è la capacità di produrre reddito: un infortunio la può azzerare in un istante, anche fuori dal lavoro.",
        "esempio": "Un professionista si è fratturato una mano sciando: fermo due mesi, senza incassi. La polizza infortuni gli ha garantito una diaria che ha coperto le spese fisse.",
        "pro": [
            "Opera 24 ore su 24, anche nel tempo libero",
            "Diaria da ricovero e capitale per invalidità permanente",
            "Tutela il reddito di chi non ha un datore di lavoro alle spalle",
        ],
    },
    "malattia": {
        "leva": "Le liste d'attesa del pubblico si allungano: pagare per curarsi in tempo è già una realtà per molte famiglie.",
        "esempio": "Una persona ha potuto anticipare un intervento importante rivolgendosi al privato: la polizza salute ha rimborsato la spesa che altrimenti avrebbe pagato per intero.",
        "pro": [
            "Accesso rapido a visite, esami e interventi",
            "Rimborso spese mediche e diaria da ricovero",
            "Estendibile a tutto il nucleo familiare",
        ],
    },
    "vita": {
        "leva": "È la copertura che nessuno vuole nominare, ma è quella che tiene in piedi la famiglia nel momento peggiore.",
        "esempio": "Alla scomparsa del principale percettore di reddito, la temporanea caso morte ha estinto il mutuo: la famiglia ha potuto restare nella propria casa.",
        "pro": [
            "Protegge mutuo e tenore di vita dei familiari",
            "Premi contenuti per capitali elevati (temporanea)",
            "Possibili benefici fiscali sui premi versati",
        ],
    },
    "rc_capofamiglia": {
        "leva": "Un danno involontario a un terzo nella vita di tutti i giorni — un figlio, il cane, una perdita d'acqua al vicino — lo paghi tu, spesso a caro prezzo.",
        "esempio": "Il figlio di un assicurato ha danneggiato l'auto di un passante giocando: la RC capofamiglia ha risarcito il terzo, evitando una spesa e un litigio.",
        "pro": [
            "Copre i danni a terzi di tutto il nucleo familiare",
            "Include figli minori e animali domestici",
            "Premio molto basso a fronte di risarcimenti potenzialmente alti",
        ],
    },
    "tutela_legale": {
        "leva": "Avere ragione non basta: senza qualcuno che paghi l'avvocato, spesso conviene rinunciare. La tutela legale ribalta questo calcolo.",
        "esempio": "Un cliente ha avuto una controversia con un fornitore: la tutela legale ha coperto avvocato e perizia, permettendogli di far valere le proprie ragioni fino in fondo.",
        "pro": [
            "Paga spese legali, peritali e di giudizio",
            "Mette a disposizione consulenza legale telefonica",
            "Consente di difendersi senza pensare ai costi",
        ],
    },
}


def trattativa_for(rami: list[str]) -> dict | None:
    """Restituisce lo spunto di trattativa per il primo ramo che ne ha uno."""
    for ramo in rami:
        if ramo in TRATTATIVA:
            return {"ramo": ramo, **TRATTATIVA[ramo]}
    return None


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
                    "trattativa": trattativa_for(rule["rami"]),
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
                "trattativa": trattativa_for(base["rami"]),
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
        if branch in active_branches:
            covered.append(entry)
        else:
            entry["trattativa"] = trattativa_for([branch])
            uncovered.append(entry)

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

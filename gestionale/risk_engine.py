"""Motore di analisi automatica dei rischi.

Analizza la descrizione dell'attività di un cliente (più i dati
strutturati dell'anagrafica: tipo, professione, specializzazioni, attività
svolte, inquadramento, dipendenti, fatturato) e produce:

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
from .professioni import Professione, normalizza, obblighi_di_legge

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
    "studio": [
        {
            "id": "rc_professionale_base",
            "nome": "RC professionale dello studio",
            "descrizione": "Copre gli errori di tutti i professionisti, praticanti e collaboratori dello studio: la polizza deve essere intestata allo studio o alla STP, non solo ai singoli.",
            "rami": ["rc_professionale"],
            "coperture": ["RC professionale dello studio / della STP"],
        },
        {
            "id": "multirischi_studio_base",
            "nome": "Multirischi dell'ufficio",
            "descrizione": "Incendio, furto ed elettronica per locali, arredi, computer e archivio dello studio.",
            "rami": ["incendio", "furto", "guasti_macchine"],
            "coperture": ["Multirischi ufficio: incendio, furto ed elettronica"],
        },
        {
            "id": "cyber_base",
            "nome": "Cyber e protezione dei dati",
            "descrizione": "Lo studio custodisce dati riservati dei clienti (spesso sanitari o giudiziari): un ransomware o una violazione GDPR blocca il lavoro e genera richieste di risarcimento.",
            "rami": ["cyber"],
            "coperture": ["Cyber Risk con RC per violazione dei dati"],
        },
        {
            "id": "tutela_legale_base",
            "nome": "Tutela legale",
            "descrizione": "Vertenze con clienti, dipendenti e fornitori; controlli fiscali.",
            "rami": ["tutela_legale"],
            "coperture": ["Tutela legale dello studio"],
        },
    ],
    "privato": [
        {
            "id": "rc_capofamiglia_base",
            "nome": "RC Capofamiglia",
            "descrizione": "Danni involontari causati a terzi nella vita privata (anche da familiari e animali domestici).",
            "rami": ["rc_capofamiglia"],
            "coperture": ["RC della vita privata / capofamiglia"],
        },
        {
            "id": "casa_base",
            "nome": "Casa: fabbricato e contenuto",
            "descrizione": "Incendio, acqua condotta ed eventi atmosferici sull'abitazione; con il mutuo la copertura incendio è di solito richiesta dalla banca.",
            "rami": ["incendio", "furto"],
            "coperture": ["Polizza casa: incendio, danni da acqua, furto del contenuto"],
        },
        {
            "id": "malattia_base",
            "nome": "Salute e rimborso spese mediche",
            "descrizione": "Accesso rapido a visite e interventi senza liste d'attesa; con l'età il bisogno cresce.",
            "rami": ["malattia"],
            "coperture": ["Rimborso spese mediche / diaria da ricovero"],
        },
        {
            "id": "infortuni_base",
            "nome": "Infortuni nel tempo libero",
            "descrizione": "Cadute in casa, sport e viaggi: senza tutela INAIL, un infortunio grave pesa interamente sulla famiglia.",
            "rami": ["infortuni"],
            "coperture": ["Infortuni con invalidità permanente e diaria"],
        },
        {
            "id": "tutela_legale_base",
            "nome": "Tutela legale privata",
            "descrizione": "Spese legali per controversie condominiali, di consumo o con la P.A.",
            "rami": ["tutela_legale"],
            "coperture": ["Tutela legale della famiglia"],
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
# Attività del professionista che richiedono estensioni o polizze dedicate
# (spesso escluse dalla RC professionale base). Le parole chiave sono
# confrontate con le attività svolte indicate in anagrafica.
# ----------------------------------------------------------------------
ATTIVITA_CONSIGLI = [
    {
        "id": "incarichi_giudiziari",
        "keywords": ["curator", "commissario", "gestore della crisi", "delegato alle vendite", "custode",
                     "amministratore giudiziario", "attestatore", "esperto della crisi", "liquidatore giudiziale"],
        "nome": "Incarichi giudiziari e procedure concorsuali",
        "descrizione": "Curatele, custodie, deleghe alle vendite e incarichi nella crisi d'impresa sono spesso esclusi dalla RC base: vanno estesi espressamente.",
        "rami": ["rc_professionale"],
        "coperture": ["Estensione della RC professionale agli incarichi giudiziari"],
    },
    {
        "id": "sindaco_revisore",
        "keywords": ["sindaco", "revisor", "organismo di vigilanza"],
        "nome": "Incarichi di sindaco, revisore e OdV 231",
        "descrizione": "La responsabilità verso la società e i terzi per gli incarichi di controllo richiede un'estensione o una polizza dedicata, con massimali adeguati alle società controllate.",
        "rami": ["rc_professionale"],
        "coperture": ["RC per incarichi di sindaco, revisore legale e componente dell'OdV"],
    },
    {
        "id": "amministratore_societa",
        "keywords": ["amministratore o liquidatore di societa"],
        "nome": "Incarichi di amministratore di società",
        "descrizione": "La RC professionale non copre la responsabilità di chi amministra una società: serve una D&O.",
        "rami": ["do"],
        "coperture": ["D&O per gli incarichi di amministratore o liquidatore"],
    },
    {
        "id": "amministratore_condominio",
        "keywords": ["amministratore di condominio"],
        "professioni": ["amministratore_condominio"],
        "nome": "Amministrazione di condomini",
        "descrizione": "L'assemblea può subordinare la nomina a una polizza RC per gli atti compiuti nell'incarico, da adeguare se delibera lavori straordinari (art. 1129 c. 3 c.c.). Per avvocati e commercialisti va estesa la RC professionale.",
        "rami": ["rc_professionale"],
        "coperture": ["RC professionale dell'amministratore di condominio"],
    },
    {
        "id": "attivita_invasiva",
        "keywords": ["interventi chirurgici", "procedure invasive", "implantolog", "sedazione", "anestesia",
                     "assistenza al parto", "parto a domicilio", "estrazioni e chirurgia", "rialzo del seno"],
        "nome": "Attività chirurgica o invasiva",
        "descrizione": "Chirurgia, anestesia e assistenza al parto portano ai massimali più alti (DM 232/2023, art. 4: 2 milioni per sinistro e 6 annui) e vanno dichiarate con esattezza, pena la riduzione dell'indennizzo.",
        "rami": ["rc_professionale"],
        "coperture": ["RC professionale per attività chirurgica / invasiva con massimali adeguati"],
    },
    {
        "id": "medicina_estetica",
        "keywords": ["medicina estetica", "chirurgia plastica", "estetica dentale", "trattamenti estetici"],
        "nome": "Medicina estetica",
        "descrizione": "Molte polizze escludono le prestazioni a fine estetico o le coprono solo con garanzia specifica.",
        "rami": ["rc_professionale"],
        "coperture": ["Garanzia specifica per la medicina estetica"],
    },
    {
        "id": "telemedicina",
        "keywords": ["telemedicina", "sedute online", "consulenze nutrizionali online", "vendita online",
                     "trattamento di dati per conto", "teleriabilitazione", "telemonitoraggio", "servizi cloud"],
        "nome": "Prestazioni a distanza e dati di terzi",
        "descrizione": "Prestazioni online e gestione di dati altrui espongono a violazioni della privacy e ad attacchi informatici.",
        "rami": ["cyber"],
        "coperture": ["Cyber Risk con RC per violazione dei dati", "Estensione della RC alle prestazioni a distanza"],
    },
    {
        "id": "cantiere",
        "keywords": ["direzione lavori", "collaud", "coordinamento sicurezza", "opere pubbliche", "rspp"],
        "nome": "Direzione lavori, collaudi e sicurezza",
        "descrizione": "Direzione lavori, collaudi e coordinamento della sicurezza (CSP / CSE) vanno dichiarati: in caso di infortunio in cantiere il coordinatore è spesso chiamato in causa. Per le opere pubbliche il bando può chiedere coperture specifiche.",
        "rami": ["rc_professionale"],
        "coperture": ["RC professionale estesa a direzione lavori, collaudi e CSP / CSE",
                      "Coperture richieste dai bandi di gara (D.Lgs. 36/2023)"],
    },
    {
        "id": "asseverazioni",
        "keywords": ["asseverazion"],
        "nome": "Asseverazioni per bonus edilizi",
        "descrizione": "La RC deve coprire le asseverazioni senza esclusioni, con un massimale specifico di almeno 500.000 € (e retroattività e ultrattività di almeno 5 anni se claims made), oppure serve una polizza dedicata (art. 119 c. 14 DL 34/2020).",
        "rami": ["rc_professionale"],
        "coperture": ["RC con garanzia asseverazioni da almeno 500.000 € o polizza dedicata"],
    },
    {
        "id": "visto_conformita",
        "keywords": ["visto di conformita"],
        "nome": "Visto di conformità",
        "descrizione": "Chi rilascia il visto di conformità deve avere una polizza dedicata con massimale di almeno 3.000.000 €, adeguato al numero di contribuenti assistiti (art. 22 DM 164/1999).",
        "rami": ["rc_professionale"],
        "coperture": ["Polizza dedicata al visto di conformità da almeno 3.000.000 €"],
    },
    {
        "id": "farmacia",
        "keywords": ["titolare o direttore di farmacia", "titolare di farmacia"],
        "nome": "Locali e merci della farmacia",
        "descrizione": "Farmaci e contanti in negozio: incendio, furto e rapina sono i rischi principali del titolare.",
        "rami": ["incendio", "furto"],
        "coperture": ["Multirischi della farmacia: incendio, furto e rapina"],
    },
    {
        "id": "merci_campionari",
        "keywords": ["deposito di merci", "campionari"],
        "nome": "Merci e campionari in custodia",
        "descrizione": "Merci della mandante in deposito e campionari in auto: furto e danneggiamento restano spesso a carico dell'agente.",
        "rami": ["furto", "trasporti"],
        "coperture": ["Furto e danni a merci e campionari, anche durante il trasporto"],
    },
]


def _voce_raccomandazione(base: dict, **extra) -> dict:
    voce = {
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
        "obbligatoria": False,
    }
    voce.update(extra)
    return voce


def raccomandazioni_professione(
    client_type: str,
    professione: Professione | None,
    inquadramento: str | None = None,
    attivita: list[str] | None = None,
    *,
    specializzazioni: list[str] | None = None,
    forma_giuridica: str | None = None,
    revenue: float | None = None,
    numero_professionisti: int | None = None,
) -> tuple[list[dict], list[str]]:
    """Obblighi di legge della professione, estensioni per le attività svolte e avvertenze."""
    if client_type not in ("professionista", "studio") or professione is None:
        return [], []
    obblighi, avvertenze = obblighi_di_legge(
        client_type, professione, inquadramento=inquadramento, forma_giuridica=forma_giuridica,
        fatturato=revenue, numero_professionisti=numero_professionisti,
        voci=list(specializzazioni or []) + list(attivita or []),
    )
    voci, usati = [], set()
    for obbligo in obblighi:
        coperture = [f"{obbligo['copertura']} ({obbligo['norma']})"]
        if obbligo["nota_massimale"]:
            coperture.append(obbligo["nota_massimale"][:1].upper() + obbligo["nota_massimale"][1:])
        # Due obblighi sullo stesso ramo (colpa grave e RC per l'attività privata).
        identificativo = f"obbligo_{obbligo['ramo']}"
        while identificativo in usati:
            identificativo += "_bis"
        usati.add(identificativo)
        voci.append(_voce_raccomandazione(
            {"id": identificativo,
             "nome": f"{obbligo['copertura']} — obbligatoria per legge",
             "descrizione": obbligo["descrizione"] or "Obbligatoria per legge per questa professione.",
             "rami": [obbligo["ramo"]], "coperture": coperture},
            severita="alta", obbligatoria=True,
        ))
    if professione.gelli_bianco and client_type == "professionista":
        voci.append(_voce_raccomandazione({
            "id": "tutela_legale_sanitaria",
            "nome": "Tutela legale con difesa penale",
            "descrizione": "Per i sanitari il procedimento penale per lesioni colpose è frequente anche senza colpa: "
                           "servono avvocato e perito di parte fin dalla prima contestazione.",
            "rami": ["tutela_legale"],
            "coperture": ["Tutela legale con difesa penale e perizie di parte"],
        }))
    testo_attivita = " | ".join(normalizza(a) for a in attivita or [])
    for consiglio in ATTIVITA_CONSIGLI:
        trovate = sorted({kw for kw in consiglio["keywords"] if normalizza(kw) in testo_attivita})
        if trovate or professione.chiave in consiglio.get("professioni", ()):
            voci.append(_voce_raccomandazione(
                {**consiglio, "id": f"attivita_{consiglio['id']}"}, parole_chiave=trovate,
            ))
    return voci, avvertenze


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
    professione: Professione | None = None,
    inquadramento: str | None = None,
    attivita: list[str] | None = None,
    specializzazioni: list[str] | None = None,
    forma_giuridica: str | None = None,
    numero_professionisti: int | None = None,
) -> dict:
    """Esegue l'analisi dei rischi e la gap analysis.

    ``active_branches`` è l'insieme dei rami delle polizze attive del
    cliente: serve a calcolare le coperture già presenti vs. scoperte.
    ``professione`` (voce del catalogo), ``inquadramento``, ``attivita`` e gli
    altri dati professionali aggiungono gli obblighi di legge (con i massimali
    minimi) e le estensioni per le attività svolte.
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
        if rule["id"] == "rc_professionale" and client_type in ("professionista", "studio") and score:
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
                    "obbligatoria": False,
                }
            )

    detected.sort(key=lambda r: -r["punteggio"])

    # Obblighi di legge della professione in testa: assorbono il pericolo
    # rilevato sullo stesso ramo (con le sue parole chiave) e le
    # raccomandazioni generiche corrispondenti.
    professionali, avvertenze = raccomandazioni_professione(
        client_type, professione, inquadramento, attivita, specializzazioni=specializzazioni,
        forma_giuridica=forma_giuridica, revenue=revenue, numero_professionisti=numero_professionisti,
    )
    rami_obbligatori = {r["rami"][0] for r in professionali if r["obbligatoria"]}
    for voce in professionali:
        if voce["obbligatoria"]:
            for rilevato in [r for r in detected if r["rami"] == voce["rami"]]:
                voce["parole_chiave"] = sorted(set(voce["parole_chiave"]) | set(rilevato["parole_chiave"]))
                detected.remove(rilevato)
    detected[:0] = [v for v in professionali if v["obbligatoria"]]

    # Raccomandazioni di base per il tipo di cliente (senza duplicare
    # pericoli già rilevati sugli stessi rami).
    detected_ids = {r["id"] for r in detected}
    specifiche = [v for v in professionali if not v["obbligatoria"]]
    rami_specifici = {ramo for v in specifiche for ramo in v["rami"]}
    for base in BASELINE_BY_TYPE.get(client_type, []):
        if base["id"].replace("_base", "") in detected_ids:
            continue
        # Già coperta da un obbligo di legge o da un consiglio più specifico.
        if set(base["rami"]) <= rami_obbligatori | (rami_specifici if base["id"] == "tutela_legale_base" else set()):
            continue
        detected.append(_voce_raccomandazione(base))
    detected.extend(specifiche)

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
        "generata_il": datetime.now().isoformat(timespec="seconds"),
        "rischi": detected,
        "coperture_presenti": covered,
        "coperture_scoperte": uncovered,
        "avvertenze": avvertenze,
        "sintesi": {
            "rischi_rilevati": len([r for r in detected if not r["baseline"]]),
            "raccomandazioni_base": len([r for r in detected if r["baseline"]]),
            "rami_scoperti": len(uncovered),
            "rami_coperti": len(covered),
            "obblighi_di_legge": len([r for r in detected if r.get("obbligatoria")]),
        },
    }


def analyze_client(client, description: str | None = None) -> dict:
    """Analizza un cliente del gestionale usando anagrafica + polizze attive."""
    text = description if description is not None else (client.descrizione_attivita or "")
    # Includiamo i dati dell'anagrafica: spesso la descrizione è breve.
    full_text = " ".join(filter(None, [
        text, client.settore, client.professione, client.specializzazioni, client.attivita_svolte,
    ]))
    active = {p.ramo for p in client.polizze if p.stato in ("attiva", "in_rinnovo")}
    # L'RC professionale dello studio copre anche i professionisti che vi lavorano.
    if client.tipo == "professionista" and client.studio is not None:
        if any(p.ramo == "rc_professionale" and p.stato in ("attiva", "in_rinnovo") for p in client.studio.polizze):
            active.add("rc_professionale")
    return analyze_risks(
        full_text,
        client_type=client.tipo,
        employees=client.numero_dipendenti,
        revenue=client.fatturato_annuo,
        active_branches=active,
        professione=client.professione_catalogo,
        inquadramento=client.inquadramento,
        attivita=client.attivita_elenco,
        specializzazioni=client.specializzazioni_elenco,
        forma_giuridica=client.forma_giuridica,
        numero_professionisti=client.numero_professionisti,
    )

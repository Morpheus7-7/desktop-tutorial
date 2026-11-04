"""«Come impostare la trattativa»: il ponte tra il cliente reale e l'Accademia.

Per ogni cliente mette insieme, in una pagina da leggere prima
dell'appuntamento:

- chi è (tipo, professione dal catalogo, attività);
- cosa deve avere per legge e cosa ha già (obblighi e polizze);
- le coperture scoperte trovate dall'ultima analisi dei rischi, con la leva
  di trattativa;
- le domande SPIN adatte al suo profilo;
- le obiezioni che è probabile sentire, con risposta e rilancio;
- il role-play da provare prima con un collega, le lezioni da ripassare e
  le schede da compilare con lui.

Nessun dato inventato: tutto viene dalla scheda del cliente, dal catalogo
delle professioni e dai contenuti dell'Accademia.
"""
from __future__ import annotations

from . import academy as ac

# Domande SPIN per profilo: situazione, problema, implicazione, bisogno.
DOMANDE = {
    "legale": {
        "situazione": ["Che tipo di incarichi segue di più (contenzioso, consulenza, procedure)?",
                       "Qual è il valore della pratica più importante che ha in corso?",
                       "Lavora da solo o con collaboratori e praticanti?"],
        "problema": ["Le è mai capitato un termine processuale a rischio o una contestazione di un cliente?",
                     "La sua polizza attuale copre anche gli errori dei collaboratori e gli incarichi di curatore o arbitro?"],
        "implicazione": ["Se un cliente le chiedesse i danni per un termine perso, il massimale attuale basterebbe?",
                         "E per le pratiche degli anni passati, la retroattività arriva abbastanza indietro?"],
        "bisogno": ["Quanto sarebbe tranquillo sapendo che ogni incarico, anche passato, è coperto?",
                    "Le sarebbe utile un confronto scritto voce per voce con la polizza che ha oggi?"],
    },
    "economica": {
        "situazione": ["Che servizi offre (contabilità, dichiarazioni, paghe, revisione, incarichi di sindaco)?",
                       "Quanti clienti segue e di che dimensione?"],
        "problema": ["Le è mai capitato un errore in una dichiarazione o una scadenza fiscale mancata per un cliente?",
                     "Gli incarichi di sindaco o revisore sono compresi nella sua polizza?"],
        "implicazione": ["Se una sanzione ricadesse su di lei per un errore, quanto potrebbe arrivare a pagare?",
                         "Cosa succederebbe alla relazione con il cliente in quel caso?"],
        "bisogno": ["Le interesserebbe avere sotto controllo massimale, retroattività e incarichi in un'unica verifica?",
                    "Se trovassimo un buco, preferirebbe chiuderlo subito o alla scadenza?"],
    },
    "tecnica": {
        "situazione": ["Che tipo di progetti o direzioni lavori segue? Ha cantieri in corso?",
                       "Firma anche collaudi, certificazioni o perizie?"],
        "problema": ["Un errore di progetto può emergere anni dopo: la sua polizza copre i lavori già consegnati?",
                     "Ha mai dovuto rispondere di un vizio dell'opera?"],
        "implicazione": ["Se smettesse di lavorare, chi coprirebbe un danno scoperto dopo? C'è la garanzia postuma?",
                         "Il massimale è adeguato al valore delle opere che firma?"],
        "bisogno": ["Quanto le varrebbe la certezza di essere coperto anche per i progetti di dieci anni fa?",
                    "Le va di verificare insieme retroattività, postuma e massimale?"],
    },
    "sanitaria": {
        "situazione": ["Lavora come dipendente di una struttura, in convenzione o in libera professione (anche intramoenia)?",
                       "Quali prestazioni esegue più spesso?"],
        "problema": ["Sa che, se è dipendente, la struttura può rivalersi su di lei in caso di colpa grave?",
                     "La sua polizza copre anche l'attività libero-professionale?"],
        "implicazione": ["Se arrivasse una richiesta di rivalsa, sarebbe pronto a sostenerla di tasca propria?",
                         "Gli anni già lavorati sono coperti dalla retroattività?"],
        "bisogno": ["Le sarebbe utile una verifica della sua posizione rispetto alla legge 24/2017?",
                    "Preferirebbe avere colpa grave, tutela legale e retroattività in un'unica soluzione chiara?"],
    },
    "professionista": {
        "situazione": ["Come è organizzata la sua attività e chi sono i suoi clienti tipici?",
                       "Ha collaboratori o dipendenti?"],
        "problema": ["Quale errore professionale la preoccupa di più?",
                     "Se si fermasse per un infortunio o una malattia, chi porterebbe avanti il lavoro?"],
        "implicazione": ["Quanto potrebbe costarle un mese di fermo, tra mancati incassi e spese fisse?",
                         "Un reclamo di un cliente quanto peserebbe sulla sua reputazione?"],
        "bisogno": ["Le interessa proteggere sia la responsabilità verso i clienti sia il suo reddito?",
                    "Da quale dei due rischi vorrebbe partire?"],
    },
    "studio": {
        "situazione": ["Quanti professionisti lavorano nello studio e con che forma (associazione, STP)?",
                       "Chi decide le coperture: i soci insieme o uno di voi?"],
        "problema": ["La polizza dello studio copre tutti i professionisti, i collaboratori e gli incarichi personali?",
                     "Cosa succede se un socio esce o ne entra uno nuovo?"],
        "implicazione": ["Un sinistro grave di un socio potrebbe ricadere sul patrimonio dello studio?",
                         "I massimali sono stati aggiornati con la crescita dello studio?"],
        "bisogno": ["Vi sarebbe utile una verifica unica per lo studio e per i singoli professionisti?",
                    "Possiamo organizzare un incontro con tutti i soci?"],
    },
    "azienda": {
        "situazione": ["Mi racconta come lavora l'azienda: sede, magazzino, dipendenti, clienti principali?",
                       "Quali beni sarebbero più difficili da sostituire?"],
        "problema": ["Le è mai capitato un fermo per un guasto, un furto o un danno?",
                     "I valori assicurati sono stati aggiornati negli ultimi anni?"],
        "implicazione": ["Se l'attività si fermasse per un mese, quanto costerebbe tra fatturato perso e spese fisse?",
                         "Se un dipendente si infortunasse gravemente, l'azienda sarebbe coperta per la sua responsabilità?"],
        "bisogno": ["Le interesserebbe una mappa dei rischi con le priorità, da affrontare per gradi?",
                    "Quale di questi rischi vorrebbe mettere al sicuro per primo?"],
    },
    "dipendente": {
        "situazione": ["Mi parla della sua famiglia e del suo lavoro? C'è un mutuo o un affitto?",
                       "Che coperture ha già, anche tramite l'azienda o la banca?"],
        "problema": ["Fuori dal lavoro, nel tempo libero, cosa la proteggerebbe in caso di infortunio?",
                     "Se lei non potesse lavorare per qualche mese, come andrebbero le spese di casa?"],
        "implicazione": ["Se le capitasse qualcosa di serio, la sua famiglia riuscirebbe a pagare il mutuo?",
                         "Quanto tempo potrebbe reggere il bilancio familiare con un solo stipendio?"],
        "bisogno": ["Le sarebbe utile capire con una cifra al mese come proteggere il reddito della famiglia?",
                    "Vuole che ne parliamo anche con il suo partner?"],
    },
    "privato": {
        "situazione": ["Come è composta la sua famiglia? La casa è di proprietà o in affitto?",
                       "Ha animali, seconde case, hobby o sport particolari?"],
        "problema": ["Se causasse un danno a qualcuno nella vita di tutti i giorni, chi pagherebbe?",
                     "Le sue polizze attuali sono state riviste di recente?"],
        "implicazione": ["Un danno all'appartamento di sotto o un incidente in bici potrebbero costare migliaia di euro: come li affronterebbe?",
                         "Se servissero cure o assistenza, la sua famiglia sarebbe pronta?"],
        "bisogno": ["Le interessa una protezione semplice per la famiglia, con un costo mensile chiaro?",
                    "Da cosa vorrebbe partire per stare più tranquillo?"],
    },
}

OBIEZIONI_PROFILO = {
    "legale": ["convenzione-ordine", "gia-assicurato", "caro", "mai-sinistri"],
    "economica": ["convenzione-ordine", "gia-assicurato", "altri-preventivi", "caro"],
    "tecnica": ["convenzione-ordine", "online", "mai-sinistri", "colleghi"],
    "sanitaria": ["gia-assicurato", "convenzione-ordine", "non-tempo", "colleghi"],
    "professionista": ["gia-assicurato", "non-tempo", "caro", "mai-sinistri"],
    "studio": ["gia-assicurato", "budget", "altri-preventivi", "pensarci"],
    "azienda": ["gia-assicurato", "budget", "commercialista", "non-momento", "mai-sinistri"],
    "dipendente": ["banca", "inail", "giovane", "moglie", "vita-fregatura"],
    "privato": ["affitto", "non-capita", "banca", "pensarci", "caro"],
}

SCENARI_PROFILO = {
    "legale": ["professionista", "commercialista"],
    "economica": ["commercialista"],
    "tecnica": ["professionista"],
    "sanitaria": ["medico-ospedaliero"],
    "professionista": ["professionista"],
    "studio": ["pmi", "commercialista"],
    "azienda": ["negozio", "pmi", "artigiano"],
    "dipendente": ["famiglia-mutuo"],
    "privato": ["famiglia-mutuo"],
}

# Lezioni da ripassare prima dell'appuntamento (id lezione).
LEZIONI_BASE = ["apertura-contratto", "domande-spin", "compliance-idd", "obiezioni-laer", "proposta-opzioni"]


def profilo(client) -> str:
    """Chiave del profilo: area della professione per i professionisti, tipo per gli altri."""
    if client.tipo == "professionista":
        prof = client.professione_catalogo
        if prof is not None and prof.area in DOMANDE:
            return prof.area
        return "professionista"
    return client.tipo if client.tipo in DOMANDE else "azienda"


def _lezioni(ids: list[str]) -> list[tuple[dict, dict]]:
    indice = {lez["id"]: (m, lez) for m, lez in ac.tutte_le_lezioni()}
    return [indice[i] for i in ids if i in indice]


def guida(client) -> dict:
    chiave = profilo(client)
    analisi = client.ultima_analisi
    scoperte = analisi.results.get("coperture_scoperte", []) if analisi else []
    obiezioni = [o for o in (ac.get_obiezione(i) for i in OBIEZIONI_PROFILO.get(chiave, [])) if o]
    scenari = [s for s in (ac.get_scenario(i) for i in SCENARI_PROFILO.get(chiave, [])) if s]
    persona = client.persona_fisica
    aperti = sorted((f for f in client.followups if f.stato == "aperto"), key=lambda f: f.data_scadenza)
    return {
        "profilo": chiave,
        "professione": client.professione_catalogo,
        "obblighi": client.obblighi_assicurativi,
        "avvertenze": client.avvertenze_assicurative,
        "analisi": analisi,
        "scoperte": scoperte[:6],
        "domande": DOMANDE[chiave],
        "obiezioni": obiezioni,
        "scenari": scenari,
        "lezioni": _lezioni(LEZIONI_BASE),
        "scheda_raccolta": "raccolta-privato" if persona else "raccolta-azienda",
        "prossimo_followup": aperti[0] if aperti else None,
        "trattative": [o for o in client.opportunita if o.aperta],
    }

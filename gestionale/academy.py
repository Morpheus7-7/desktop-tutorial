"""Accademia commerciale: programma di apprendimento per consulenti assicurativi.

Il programma non insegna i prodotti ma il *mestiere*: fare domande, ascoltare,
ragionare di lato, condurre e far proseguire una trattativa, gestire le
obiezioni, chiudere e far crescere il portafoglio. I contenuti sono dati
statici (moduli, lezioni, quiz, obiezioni, tecniche, scenari) organizzati in un
percorso di 12 settimane; lo stato di avanzamento è salvato nel database.

Le tecniche riportate provengono da metodi studiati e documentati; per ognuna
è indicata la fonte, così chi vuole approfondire sa dove andare.
"""
import random
from datetime import date

# ----------------------------------------------------------------------
# Moduli del percorso (uno a settimana)
# ----------------------------------------------------------------------
MODULI = [
    # ------------------------------------------------------------------ 1
    {
        "id": "mindset",
        "area": "Fondamenta",
        "icona": "bi-compass",
        "titolo": "Mentalità e metodo del consulente",
        "obiettivo": "Passare da «venditore di polizze» a consulente che risolve "
                     "problemi, e capire che il risultato commerciale è la "
                     "conseguenza misurabile di attività quotidiane.",
        "lezioni": [
            {
                "id": "mindset-consulente",
                "titolo": "Consulente, non venditore",
                "teoria": "Il cliente non compra una polizza: compra la "
                          "tranquillità che un problema preciso non gli rovinerà "
                          "la vita o l'azienda. Il venditore parla del prodotto, "
                          "il consulente parla del cliente. La fiducia nasce "
                          "quando il cliente percepisce che ti interessa più "
                          "capire la sua situazione che chiudere il contratto.",
                "punti": [
                    "Parla l'altro per il 70% del tempo: tu fai domande.",
                    "Il prodotto si nomina solo dopo aver fatto emergere il problema.",
                    "Una consulenza onesta che finisce con «oggi non ti serve nulla» crea più referenze di dieci vendite forzate.",
                    "La tua offerta è la diagnosi: la polizza è solo la terapia.",
                ],
                "esempio": "Invece di «Le propongo la nostra RC professionale», "
                           "prova: «Prima di parlare di coperture, mi racconta "
                           "qual è l'errore che nella sua professione le farebbe "
                           "più paura commettere?»",
                "esercizio": "Riascolta (o ricostruisci) le ultime tre telefonate "
                             "con un cliente: chi ha parlato di più? Quante "
                             "domande hai fatto prima di nominare un prodotto?",
            },
            {
                "id": "mindset-numeri",
                "titolo": "Il ciclo di vendita e la legge dei numeri",
                "teoria": "Ogni trattativa attraversa fasi riconoscibili: "
                          "contatto → appuntamento → analisi → proposta → "
                          "chiusura → post-vendita. Misurando i rapporti di "
                          "conversione tra una fase e l'altra scopri dove "
                          "perdi clienti e quante attività ti servono per "
                          "raggiungere l'obiettivo. Gli obiettivi di risultato "
                          "(premi, provvigioni) non si controllano: le attività "
                          "(telefonate, appuntamenti, analisi) sì.",
                "punti": [
                    "Lavora a ritroso: obiettivo annuo → contratti → proposte → appuntamenti → contatti.",
                    "Esempio: 1 chiusura ogni 3 proposte, 1 proposta ogni 2 appuntamenti, 1 appuntamento ogni 5 telefonate → servono 30 telefonate per 1 contratto.",
                    "Il collo di bottiglia si migliora con la formazione mirata, non lavorando di più a caso.",
                    "Usa la Pipeline del gestionale per vedere dove si fermano le opportunità.",
                ],
                "esempio": "Un consulente si accorge che fa molti appuntamenti "
                           "ma poche proposte: il problema non è la prospezione "
                           "ma l'analisi dei bisogni (modulo «L'arte delle domande»).",
                "esercizio": "Calcola i tuoi rapporti di conversione degli "
                             "ultimi 3 mesi e il numero di telefonate settimanali "
                             "necessario per il tuo obiettivo di provvigioni.",
            },
            {
                "id": "mindset-resilienza",
                "titolo": "Gestire il rifiuto e l'etica professionale",
                "teoria": "Il «no» riguarda la proposta in quel momento, non te. "
                          "Chi regge il rifiuto lo trasforma in informazione: "
                          "perché no? cosa avrei potuto chiedere prima? "
                          "L'etica non è un freno: nella distribuzione "
                          "assicurativa (Direttiva IDD, Regolamento IVASS n. 40/2018) "
                          "devi proporre contratti coerenti con le richieste e "
                          "le esigenze del cliente. Questo obbligo è anche il "
                          "miglior metodo commerciale: chi analizza bene, vende bene.",
                "punti": [
                    "Separa l'esito dalla prestazione: valuta come hai condotto il colloquio, non solo se hai chiuso.",
                    "Tieni un diario delle trattative: cosa ha funzionato, cosa no.",
                    "Mai vendere una copertura non necessaria: il costo reputazionale supera la provvigione.",
                    "La valutazione di coerenza (demands & needs) è il tuo questionario di analisi: usalo come strumento di vendita.",
                ],
                "esempio": "Dopo un rifiuto: «Grazie della franchezza. Per "
                           "migliorare il mio lavoro, posso chiederle cosa le è "
                           "mancato nella mia proposta?»",
                "esercizio": "Scrivi i 3 «no» più recenti e, per ciascuno, la "
                             "domanda che avresti potuto fare prima per prevenirlo.",
            },
        ],
        "quiz": [
            {
                "domanda": "In un colloquio consulenziale efficace, chi dovrebbe parlare di più?",
                "opzioni": ["Il consulente, per spiegare bene i prodotti",
                            "Il cliente, guidato dalle domande del consulente",
                            "Metà e metà, per equilibrio"],
                "corretta": 1,
                "spiegazione": "Sono le domande a far emergere bisogni e motivazioni: il cliente dovrebbe parlare per circa il 70% del tempo.",
            },
            {
                "domanda": "Quali obiettivi puoi controllare direttamente ogni giorno?",
                "opzioni": ["Le provvigioni del mese",
                            "Il numero di contratti firmati",
                            "Il numero di contatti, appuntamenti e analisi svolte"],
                "corretta": 2,
                "spiegazione": "I risultati sono conseguenza delle attività: pianifica e misura le attività.",
            },
            {
                "domanda": "La valutazione di coerenza richiesta dalla normativa IDD è…",
                "opzioni": ["Un adempimento burocratico da sbrigare a fine colloquio",
                            "Uno strumento di analisi dei bisogni che aiuta anche la vendita",
                            "Facoltativa per le polizze danni"],
                "corretta": 1,
                "spiegazione": "Raccogliere richieste ed esigenze del cliente è sia un obbligo sia la base di una proposta convincente.",
            },
        ],
        "fonti": [
            "Zig Ziglar, «Secrets of Closing the Sale»",
            "Direttiva (UE) 2016/97 (IDD) e Regolamento IVASS n. 40/2018",
            "Frank Bettger, «How I Raised Myself from Failure to Success in Selling»",
        ],
    },
    # ------------------------------------------------------------------ 2
    {
        "id": "prospezione",
        "area": "Accumulare clienti",
        "icona": "bi-binoculars",
        "titolo": "Prospezione e generazione di contatti",
        "obiettivo": "Costruire un flusso costante di nuovi contatti qualificati "
                     "attraverso referenze, nicchie di mercato e partner, invece "
                     "di dipendere dal caso.",
        "lezioni": [
            {
                "id": "prospezione-referenze",
                "titolo": "Il sistema delle referenze",
                "teoria": "La referenza è il contatto più caldo possibile: arriva "
                          "con la fiducia già trasferita. Non va «sperata» ma "
                          "chiesta con metodo, nei momenti in cui il cliente è più "
                          "soddisfatto: dopo la firma, dopo un sinistro gestito "
                          "bene, dopo una revisione annuale utile. La richiesta "
                          "deve essere specifica: chiedere «conosce qualcuno?» "
                          "produce un vuoto; chiedere di una categoria precisa "
                          "attiva la memoria.",
                "punti": [
                    "Chiedi per categoria: «Chi è il suo commercialista? Chi sono i due fornitori con cui lavora di più?»",
                    "Chiedi il permesso di usare il suo nome e, se possibile, una presentazione diretta (messaggio o telefonata a tre).",
                    "Ringrazia sempre e aggiorna chi ti ha dato la referenza sull'esito.",
                    "Legge dei 250 (Joe Girard): ogni cliente conosce in media 250 persone; ogni cliente scontento ne allontana altrettante.",
                ],
                "esempio": "«Sono contento che la soluzione la faccia sentire più "
                           "tranquillo. Il mio lavoro cresce solo col passaparola: "
                           "pensando ad altri titolari di officina che conosce, chi "
                           "potrebbe avere le sue stesse preoccupazioni?»",
                "esercizio": "Prepara la tua frase di richiesta referenze e usala "
                             "con i prossimi 5 clienti soddisfatti. Annota quante "
                             "referenze ottieni.",
            },
            {
                "id": "prospezione-nicchie",
                "titolo": "Nicchie, centri di influenza e social selling",
                "teoria": "Specializzarsi in una nicchia (es. studi medici, "
                          "autotrasportatori, ristorazione) moltiplica l'efficacia: "
                          "impari il linguaggio, i rischi tipici e diventi «quello "
                          "che conosce il settore». I centri di influenza — "
                          "commercialisti, consulenti del lavoro, associazioni di "
                          "categoria, banche locali — vedono ogni giorno i tuoi "
                          "potenziali clienti: costruisci con loro relazioni di "
                          "scambio reciproco. Online, il social selling (LinkedIn) "
                          "consiste nel pubblicare contenuti utili per la nicchia "
                          "e avviare conversazioni, non nell'inviare offerte.",
                "punti": [
                    "Scegli 1-2 nicchie dove hai già clienti soddisfatti.",
                    "Offri valore ai partner prima di chiederne: un seminario per i loro clienti, un controllo coperture gratuito.",
                    "Contenuti efficaci: casi reali anonimi, errori frequenti, novità normative (es. obbligo CatNat per le imprese).",
                    "Partecipa dove la nicchia si riunisce: fiere, associazioni, eventi di categoria.",
                ],
                "esempio": "Un consulente specializzato in studi dentistici "
                           "organizza con un commercialista un incontro serale su "
                           "«I 5 rischi che il dentista non sa di avere».",
                "esercizio": "Elenca 3 possibili nicchie e, per ognuna, 2 centri "
                             "di influenza da contattare entro un mese.",
            },
            {
                "id": "prospezione-portafoglio",
                "titolo": "Il portafoglio come miniera",
                "teoria": "La prospezione più economica è dentro il portafoglio "
                          "che hai già: clienti con una sola polizza, familiari e "
                          "dipendenti dei clienti aziendali, clienti «dormienti» "
                          "non sentiti da oltre un anno. L'analisi dei rischi e "
                          "la gap analysis del gestionale ti dicono già cosa "
                          "manca a ciascuno.",
                "punti": [
                    "Ogni cliente azienda ha titolare, soci e dipendenti: sono persone con bisogni personali (infortuni, salute, previdenza).",
                    "Pianifica una campagna di riattivazione dei clienti non contattati da 12 mesi.",
                    "Trasforma ogni copertura scoperta in un'opportunità nella Pipeline.",
                ],
                "esempio": "«Abbiamo messo al sicuro l'azienda. E lei, come "
                           "titolare, se domani si fermasse per tre mesi, chi "
                           "pagherebbe le sue spese di casa?»",
                "esercizio": "Estrai dal gestionale i 10 clienti con una sola "
                             "polizza e fissa per ognuno un follow-up di revisione.",
            },
        ],
        "quiz": [
            {
                "domanda": "Qual è il modo più efficace di chiedere una referenza?",
                "opzioni": ["«Conosce qualcuno a cui potrebbe interessare?»",
                            "Chiedere di una categoria precisa di persone, in un momento di soddisfazione",
                            "Lasciare dei biglietti da visita da distribuire"],
                "corretta": 1,
                "spiegazione": "Una richiesta specifica attiva la memoria; il momento giusto è quando il cliente ha appena percepito valore.",
            },
            {
                "domanda": "Cos'è un centro di influenza?",
                "opzioni": ["Un professionista o ente che vede regolarmente i tuoi potenziali clienti",
                            "Un influencer sui social",
                            "La sede della compagnia mandante"],
                "corretta": 0,
                "spiegazione": "Commercialisti, consulenti del lavoro, associazioni: relazioni di scambio reciproco che portano contatti qualificati.",
            },
            {
                "domanda": "Nel social selling la cosa più importante è…",
                "opzioni": ["Inviare molte offerte in messaggio privato",
                            "Pubblicare contenuti utili e avviare conversazioni",
                            "Avere molti follower"],
                "corretta": 1,
                "spiegazione": "Si costruisce autorevolezza e relazione; la vendita arriva dopo, offline.",
            },
        ],
        "fonti": [
            "Joe Girard, «How to Sell Anything to Anybody»",
            "Bill Cates, «Get More Referrals Now!»",
            "Jeb Blount, «Fanatical Prospecting»",
        ],
    },
    # ------------------------------------------------------------------ 3
    {
        "id": "apertura",
        "area": "Trattativa",
        "icona": "bi-telephone-outbound",
        "titolo": "Primo contatto, appuntamento e apertura del colloquio",
        "obiettivo": "Ottenere l'appuntamento con una telefonata breve e chiara, "
                     "e aprire il colloquio creando fiducia e un accordo esplicito "
                     "su come si svolgerà.",
        "lezioni": [
            {
                "id": "apertura-telefonata",
                "titolo": "La telefonata per fissare l'appuntamento",
                "teoria": "Lo scopo della telefonata è uno solo: ottenere "
                          "l'appuntamento, non vendere. Una struttura efficace: "
                          "presentazione → motivo della chiamata (referenza o "
                          "aggancio) → beneficio dell'incontro per lui → richiesta "
                          "con alternativa di date. Le obiezioni al telefono si "
                          "gestiscono brevemente e si torna alla richiesta.",
                "punti": [
                    "Prepara un aggancio: referenza, evento, novità normativa, settore.",
                    "Proponi un incontro breve e definito: «20 minuti», non «un caffè quando vuole».",
                    "Usa l'alternativa: «martedì mattina o giovedì pomeriggio?»",
                    "Non dare prezzi al telefono: «Dipende da come lavora, è proprio quello che vediamo insieme».",
                ],
                "esempio": "«Buongiorno, sono Luca Rossi, consulente assicurativo. "
                           "Mi ha dato il suo nome il dottor Bianchi, che seguo da "
                           "anni. Lavoro con molti studi tecnici e spesso trovo "
                           "buchi nella RC professionale che nessuno ha spiegato. "
                           "Le chiedo 20 minuti per un controllo: è più comodo "
                           "martedì mattina o giovedì pomeriggio?»",
                "esercizio": "Scrivi il tuo script di 30 secondi e provalo ad alta "
                             "voce 10 volte, registrandoti.",
            },
            {
                "id": "apertura-rapport",
                "titolo": "Rapport e primi minuti del colloquio",
                "teoria": "Nei primi minuti il cliente decide se fidarsi. Il "
                          "rapport nasce da attenzione autentica, dal rispecchiare "
                          "con naturalezza ritmo e tono dell'interlocutore e dal "
                          "trovare punti in comune reali. Non serve parlare di "
                          "calcio per mezz'ora: serve far sentire l'altro "
                          "ascoltato e rispettato nel suo tempo.",
                "punti": [
                    "Arriva preparato: settore, sito web, notizie sull'azienda.",
                    "Fai un complimento specifico e sincero, non generico.",
                    "Adegua velocità e registro: con un ingegnere dati e precisione, con un artigiano esempi concreti.",
                    "Rispetta l'orario concordato: è la prima promessa che mantieni.",
                ],
                "esempio": "«Ho visto che avete appena aperto il secondo "
                           "laboratorio: complimenti. Immagino sia stato un bel "
                           "salto, anche come organizzazione.»",
                "esercizio": "Prima di ogni appuntamento della settimana scrivi 3 "
                             "informazioni sul cliente e 1 domanda di apertura personalizzata.",
            },
            {
                "id": "apertura-contratto",
                "titolo": "L'accordo iniziale (up-front contract)",
                "teoria": "Metodo Sandler: all'inizio del colloquio si concorda "
                          "esplicitamente tempo, scopo, cosa farà ciascuno e "
                          "quali esiti sono possibili — incluso il «no». Questo "
                          "abbassa le difese del cliente (non si sente in "
                          "trappola) e ti protegge dai «ci devo pensare» "
                          "indefiniti, perché il cliente si è impegnato a dare "
                          "una risposta chiara.",
                "punti": [
                    "Tempo: «Avevamo detto 30 minuti, va ancora bene?»",
                    "Scopo: «Capire come lavora e se ci sono rischi scoperti.»",
                    "Ruoli: «Io le farò alcune domande, anche dirette; lei mi chiede tutto quello che vuole.»",
                    "Esito: «Alla fine, se non vediamo utilità, me lo dice tranquillamente; se la vediamo, decidiamo il prossimo passo.»",
                ],
                "esempio": "«Le propongo questo: per mezz'ora le faccio qualche "
                           "domanda su come lavora. Alla fine potrà dirmi "
                           "tranquillamente "
                           "che non le interessa, oppure decidiamo insieme se "
                           "preparare una proposta. Le sembra corretto?»",
                "esercizio": "Formula il tuo accordo iniziale in 4 frasi e "
                             "usalo nei prossimi 3 appuntamenti.",
            },
        ],
        "quiz": [
            {
                "domanda": "Qual è l'obiettivo della telefonata a freddo o su referenza?",
                "opzioni": ["Presentare la polizza", "Ottenere l'appuntamento", "Comunicare un prezzo indicativo"],
                "corretta": 1,
                "spiegazione": "Una cosa sola: l'appuntamento. Prezzi e prodotti si affrontano dopo l'analisi.",
            },
            {
                "domanda": "Nell'up-front contract di Sandler cosa si concorda all'inizio?",
                "opzioni": ["Il prezzo massimo che il cliente è disposto a pagare",
                            "Tempo, scopo, ruoli ed esiti possibili dell'incontro, compreso il «no»",
                            "La compagnia con cui verrà stipulata la polizza"],
                "corretta": 1,
                "spiegazione": "Rendere accettabile il «no» abbassa le difese e rende più netto anche il «sì».",
            },
            {
                "domanda": "Quale formula per fissare l'appuntamento è più efficace?",
                "opzioni": ["«Quando le farebbe comodo?»",
                            "«Martedì mattina o giovedì pomeriggio?»",
                            "«Mi richiami lei quando ha tempo»"],
                "corretta": 1,
                "spiegazione": "La domanda alternativa rende facile scegliere e sposta la decisione da «se» a «quando».",
            },
        ],
        "fonti": [
            "David Sandler, «You Can't Teach a Kid to Ride a Bike at a Seminar»",
            "Dale Carnegie, «Come trattare gli altri e farseli amici»",
            "Robert Cialdini, «Le armi della persuasione» (simpatia, impegno e coerenza)",
        ],
    },
    # ------------------------------------------------------------------ 4
    {
        "id": "domande",
        "area": "Trattativa",
        "icona": "bi-question-circle",
        "titolo": "L'arte delle domande e l'ascolto attivo",
        "obiettivo": "Condurre l'analisi dei bisogni con domande strutturate che "
                     "fanno emergere problemi, conseguenze e motivazioni, in modo "
                     "che sia il cliente stesso a riconoscere il bisogno.",
        "lezioni": [
            {
                "id": "domande-spin",
                "titolo": "Il metodo SPIN",
                "teoria": "Neil Rackham, studiando oltre 35.000 colloqui di "
                          "vendita, ha osservato che nelle vendite complesse i "
                          "migliori seguono una sequenza di domande: "
                          "Situazione (i fatti), Problema (difficoltà e "
                          "insoddisfazioni), Implicazione (conseguenze del "
                          "problema, che lo rendono grande e urgente), "
                          "Need-payoff (bisogno-beneficio: il cliente descrive "
                          "da sé il valore della soluzione). Le domande di "
                          "implicazione sono le più potenti e le meno usate.",
                "punti": [
                    "S — «Quanti dipendenti avete? Che macchinari usate?» (poche: le informazioni base le raccogli prima).",
                    "P — «Vi è mai capitato un fermo macchina? Cosa vi preoccupa di più?»",
                    "I — «Se la linea si fermasse un mese, cosa succederebbe agli ordini? E ai clienti? E agli stipendi?»",
                    "N — «Quanto sarebbe utile avere un indennizzo che copre i costi fissi durante il fermo?»",
                ],
                "esempio": "Con un ristoratore: S «Quante ore è aperto il "
                           "locale?» → P «Ha mai avuto problemi con la cucina o "
                           "l'impianto elettrico?» → I «Se un incendio la "
                           "tenesse chiuso tre mesi, l'affitto e il personale "
                           "come li pagherebbe?» → N «Le sarebbe utile sapere che "
                           "in quel caso arriva un'indennità per ogni giorno di chiusura?»",
                "esercizio": "Per la tua nicchia principale scrivi 3 domande per "
                             "ciascuna lettera S-P-I-N.",
            },
            {
                "id": "domande-tipi",
                "titolo": "Domande aperte, chiuse, a imbuto e i «5 perché»",
                "teoria": "Le domande aperte (cosa, come, quali, mi racconti) "
                          "fanno parlare; le chiuse (sì/no, quanto) confermano e "
                          "precisano. La tecnica dell'imbuto parte larga e si "
                          "stringe sul punto. I «5 perché» (Toyota) scavano "
                          "fino alla motivazione profonda: dietro «voglio "
                          "risparmiare» può esserci «ho paura di non arrivare a "
                          "fine mese», che cambia completamente la proposta.",
                "punti": [
                    "Apri: «Come è organizzata una sua giornata tipo?»",
                    "Stringi: «Tra queste attività, quale è la più rischiosa?»",
                    "Chiudi e conferma: «Quindi la priorità è proteggere il reddito se si ferma lei, giusto?»",
                    "Evita le domande che suonano come accuse («Perché non ha mai fatto…?»): preferisci «Cosa l'ha portata finora a…?»",
                ],
                "esempio": "«Vorrei spendere poco.» → «Cosa intende per poco?» → "
                           "«Meno di adesso.» → «Cosa la preoccupa dell'attuale "
                           "spesa?» → «L'anno scorso ho pagato tanto e non mi "
                           "hanno rimborsato un danno.» Il vero tema è la fiducia "
                           "nel rimborso, non il prezzo.",
                "esercizio": "In ogni colloquio della settimana applica almeno "
                             "una catena di 3 «perché» su una frase importante del cliente.",
            },
            {
                "id": "domande-ascolto",
                "titolo": "Ascolto attivo, riformulazione e silenzio",
                "teoria": "Ascoltare attivamente significa dimostrare all'altro "
                          "di aver capito: riformulare con parole proprie, "
                          "riassumere, chiedere conferma. Il silenzio dopo una "
                          "domanda importante è uno strumento: chi lo riempie per "
                          "primo spesso rivela l'informazione più preziosa. "
                          "Prendere appunti mostra rispetto e ti dà materiale "
                          "per la proposta, con le parole esatte del cliente.",
                "punti": [
                    "Riformulazione: «Se ho capito bene, la cosa che la preoccupa è…»",
                    "Riassunto a fine analisi: elenca i 3 problemi emersi e chiedi «Ho dimenticato qualcosa?»",
                    "Dopo una domanda di implicazione, conta mentalmente fino a 5 prima di parlare.",
                    "Annota le parole del cliente e riusale nella proposta.",
                ],
                "esempio": "«Mi ha detto tre cose: il furgone è il suo ufficio, "
                           "se si ferma lei si ferma tutto, e il mutuo lo paga "
                           "solo lei. È corretto?»",
                "esercizio": "Fai un role-play con un collega in cui puoi solo "
                             "fare domande e riformulare, mai proporre: 10 minuti.",
            },
        ],
        "quiz": [
            {
                "domanda": "Nel metodo SPIN, quali domande rendono il problema grande e urgente?",
                "opzioni": ["Situazione", "Implicazione", "Need-payoff"],
                "corretta": 1,
                "spiegazione": "Le domande di implicazione esplorano le conseguenze del problema e ne fanno percepire il peso.",
            },
            {
                "domanda": "Il cliente dice «voglio spendere poco». Cosa fai?",
                "opzioni": ["Proponi subito la soluzione più economica",
                            "Chiedi cosa intende e perché è importante per lui",
                            "Spieghi che la qualità costa"],
                "corretta": 1,
                "spiegazione": "Dietro un'affermazione di superficie c'è spesso una motivazione diversa (fiducia, liquidità, esperienze negative).",
            },
            {
                "domanda": "A cosa serve il silenzio dopo una domanda importante?",
                "opzioni": ["A mettere pressione al cliente",
                            "A dare spazio alla riflessione: spesso emerge l'informazione più preziosa",
                            "A nulla, è imbarazzante e va evitato"],
                "corretta": 1,
                "spiegazione": "Lasciare spazio permette al cliente di elaborare e approfondire.",
            },
        ],
        "fonti": [
            "Neil Rackham, «SPIN Selling»",
            "Carl Rogers, sull'ascolto attivo e la riformulazione",
            "Taiichi Ohno, i «5 perché» (Toyota Production System)",
        ],
    },
    # ------------------------------------------------------------------ 5
    {
        "id": "laterale",
        "area": "Trattativa",
        "icona": "bi-lightbulb",
        "titolo": "Pensiero laterale, riformulazione e storytelling",
        "obiettivo": "Uscire dagli schemi ovvi della trattativa: cambiare il punto "
                     "di vista del cliente sul rischio, usare analogie e storie che "
                     "rendono concreto un evento che «non capiterà mai».",
        "lezioni": [
            {
                "id": "laterale-debono",
                "titolo": "Gli strumenti di Edward de Bono",
                "teoria": "Il pensiero laterale cerca alternative invece di "
                          "approfondire la stessa strada. Strumenti utili in "
                          "trattativa: i Sei Cappelli per pensare (guardare la "
                          "decisione dal lato dei fatti, delle emozioni, dei "
                          "rischi, dei benefici, delle idee nuove e del "
                          "controllo), la provocazione («e se…?») e l'inversione "
                          "(«cosa dovrebbe succedere perché questa sia la scelta "
                          "peggiore?»). Aiutano il cliente bloccato a vedere la "
                          "situazione da un'altra angolatura.",
                "punti": [
                    "Cappello nero (rischi): «Cosa potrebbe andare storto nei prossimi 5 anni?»",
                    "Cappello giallo (benefici): «Cosa cambierebbe nel suo modo di lavorare sapendo di essere protetto?»",
                    "Cappello rosso (emozioni): «Come si sentirebbe a dover spiegare un danno non coperto ai suoi soci?»",
                    "Inversione: «Se volesse mettere in crisi la sua azienda, quale rischio lascerebbe scoperto?»",
                ],
                "esempio": "Un imprenditore sicuro di sé: «Facciamo un gioco: se "
                           "fosse il suo peggior concorrente e volesse vederla "
                           "chiudere, cosa le augurerebbe che succedesse?» Spesso "
                           "è il cliente stesso a nominare il rischio scoperto.",
                "esercizio": "Prendi una trattativa ferma e analizzala con i Sei "
                             "Cappelli: scrivi una frase per ognuno.",
            },
            {
                "id": "laterale-reframing",
                "titolo": "Reframing: cambiare la cornice",
                "teoria": "Lo stesso fatto cambia significato a seconda della "
                          "cornice. Il premio può essere visto come «costo» o "
                          "come «prezzo per trasferire un rischio che non "
                          "potresti sostenere»; il premio annuo come cifra "
                          "intera o come costo giornaliero. La cornice del «costo "
                          "del non fare» confronta il premio con la perdita "
                          "possibile, non con zero. Va usato con onestà: si "
                          "cambia prospettiva, non si distorcono i fatti.",
                "punti": [
                    "Dal costo all'investimento: «Non sta spendendo 600 €, sta evitando di rischiare 300.000 €.»",
                    "Spacchettamento: «Sono 1,60 € al giorno, meno di un caffè.»",
                    "Confronto di cornice: «Assicura il furgone da 30.000 €; la sua capacità di produrre reddito per 25 anni vale molto di più.»",
                    "Avversione alla perdita (Kahneman): le persone temono di perdere più di quanto desiderino guadagnare — parla di cosa proteggere.",
                ],
                "esempio": "«Lei assicura l'auto contro il furto, eppure la "
                           "macchina che le produce reddito ogni giorno è lei. "
                           "Ha mai pensato di assicurare quella?»",
                "esercizio": "Per i 3 prodotti che proponi più spesso, scrivi una "
                             "riformulazione del prezzo e un confronto «costo del non fare».",
            },
            {
                "id": "laterale-storie",
                "titolo": "Storytelling e casi in terza persona",
                "teoria": "Le persone ricordano storie, non percentuali. Un caso "
                          "reale (anonimo) raccontato in terza persona permette "
                          "al cliente di immedesimarsi senza sentirsi attaccato. "
                          "Struttura semplice: personaggio simile al cliente → "
                          "situazione normale → evento imprevisto → conseguenze → "
                          "come è finita (con o senza copertura). Il gestionale "
                          "propone già spunti di trattativa in terza persona per "
                          "ogni copertura consigliata: usali come base.",
                "punti": [
                    "Costruisci un archivio personale di 10 storie vere, divise per settore.",
                    "Il protagonista deve somigliare al cliente (età, mestiere, famiglia).",
                    "Racconta la storia, poi taci: lascia che sia il cliente a trarre la conclusione.",
                    "Mai inventare: le storie false si scoprono e distruggono la fiducia.",
                ],
                "esempio": "«Seguo un idraulico della sua età, con due figli. Lo "
                           "scorso inverno è caduto da una scala in cantiere: "
                           "quattro mesi fermo. La polizza infortuni gli ha "
                           "pagato una diaria che ha coperto il mutuo. Mi ha "
                           "detto che è stata la spesa più utile della sua vita.»",
                "esercizio": "Scrivi 3 storie della tua esperienza con la "
                             "struttura personaggio-evento-conseguenza-esito.",
            },
        ],
        "quiz": [
            {
                "domanda": "Il «costo del non fare» confronta il premio con…",
                "opzioni": ["Il premio dei concorrenti", "Zero", "La perdita possibile senza copertura"],
                "corretta": 2,
                "spiegazione": "Il confronto corretto non è premio contro zero, ma premio contro il danno che il cliente dovrebbe sostenere da solo.",
            },
            {
                "domanda": "Perché raccontare casi in terza persona?",
                "opzioni": ["Per far immedesimare il cliente senza che si senta giudicato",
                            "Per spaventarlo e chiudere più in fretta",
                            "Perché non si può parlare dei rischi del cliente"],
                "corretta": 0,
                "spiegazione": "La distanza della terza persona abbassa le difese e rende il rischio concreto.",
            },
            {
                "domanda": "Nei Sei Cappelli di de Bono, il cappello nero rappresenta…",
                "opzioni": ["Le emozioni", "I rischi e la prudenza", "Le idee creative"],
                "corretta": 1,
                "spiegazione": "Nero = giudizio critico e rischi; rosso = emozioni; verde = creatività; giallo = benefici; bianco = fatti; blu = controllo del processo.",
            },
        ],
        "fonti": [
            "Edward de Bono, «Il pensiero laterale» e «Sei cappelli per pensare»",
            "Daniel Kahneman, «Pensieri lenti e veloci» (avversione alla perdita, framing)",
            "Chip e Dan Heath, «Made to Stick»",
        ],
    },
    # ------------------------------------------------------------------ 6
    {
        "id": "proposta",
        "area": "Trattativa",
        "icona": "bi-easel",
        "titolo": "Presentare la proposta e il prezzo",
        "obiettivo": "Presentare soluzioni collegate ai problemi emersi, "
                     "traducendo le caratteristiche in benefici e comunicando il "
                     "prezzo con sicurezza.",
        "lezioni": [
            {
                "id": "proposta-fab",
                "titolo": "Caratteristiche, vantaggi, benefici (FAB)",
                "teoria": "Una caratteristica è cosa fa la polizza (massimale "
                          "2 milioni); il vantaggio è perché è utile in generale "
                          "(copre anche i danni gravi); il beneficio è cosa "
                          "significa per questo cliente, collegato a un problema "
                          "che lui stesso ha espresso (se il cantiere di via Roma "
                          "crolla, non perde la casa). Solo il beneficio vende. "
                          "Presenta solo le caratteristiche che rispondono ai "
                          "bisogni emersi: le altre sono rumore.",
                "punti": [
                    "Formula ponte: «… e questo per lei significa che…»",
                    "Riprendi le parole del cliente dall'analisi: «Mi aveva detto che…»",
                    "Dopo ogni beneficio chiedi conferma: «È importante per lei?» (chiusura di prova).",
                    "Meno è meglio: 3 benefici forti battono 15 caratteristiche.",
                ],
                "esempio": "«La polizza prevede la garanzia per la retroattività "
                           "illimitata (caratteristica): copre anche errori fatti "
                           "negli anni passati (vantaggio). Per lei significa che "
                           "i progetti firmati dal 2015 a oggi, di cui mi parlava, "
                           "sono protetti anche se il reclamo arriva domani (beneficio).»",
                "esercizio": "Per una tua polizza tipica, compila una tabella "
                             "caratteristica → vantaggio → beneficio per 3 tipi di cliente diversi.",
            },
            {
                "id": "proposta-opzioni",
                "titolo": "Le tre opzioni e l'ancoraggio",
                "teoria": "Presentare tre soluzioni (essenziale, consigliata, "
                          "completa) sposta la domanda del cliente da «compro o "
                          "no?» a «quale scelgo?». L'effetto ancoraggio fa sì che "
                          "la prima cifra presentata diventi il riferimento: "
                          "partire dalla soluzione completa rende più "
                          "accessibile quella consigliata. L'effetto "
                          "compromesso porta molte persone a scegliere l'opzione "
                          "centrale. Tutte e tre le opzioni devono essere "
                          "coerenti con i bisogni del cliente.",
                "punti": [
                    "Presenta prima la completa, poi la consigliata, infine l'essenziale.",
                    "Indica chiaramente cosa resta scoperto con l'essenziale: è una scelta informata.",
                    "Raccomanda in modo esplicito: «Io sceglierei questa, perché…»",
                    "Mai tre opzioni che il cliente non dovrebbe comprare: la coerenza IDD vale per tutte.",
                ],
                "esempio": "«Ho preparato tre livelli. La soluzione completa, "
                           "1.400 €, include anche la tutela legale. Quella che "
                           "le consiglio, 980 €, copre i tre rischi che mi ha "
                           "indicato. L'essenziale, 620 €, copre solo l'incendio: "
                           "resterebbe scoperto il fermo attività.»",
                "esercizio": "Riscrivi la tua ultima proposta in formato a tre "
                             "opzioni con una raccomandazione motivata.",
            },
            {
                "id": "proposta-prezzo",
                "titolo": "Comunicare il prezzo con sicurezza",
                "teoria": "Il prezzo va detto in modo chiaro, senza scuse e "
                          "senza fretta, dopo il valore e mai prima. La tecnica "
                          "«sandwich» mette il prezzo tra due blocchi di valore: "
                          "beneficio → prezzo → beneficio. Se esiti, il cliente "
                          "percepisce che anche tu lo ritieni caro. Dopo aver "
                          "detto il prezzo, taci.",
                "punti": [
                    "Sandwich: valore → prezzo → valore → silenzio.",
                    "Mostra il frazionamento disponibile e il costo giornaliero o mensile.",
                    "Non anticipare sconti non richiesti.",
                    "Se ti chiedono il prezzo troppo presto: «È una domanda giusta, glielo dico appena ho capito cosa le serve davvero, altrimenti rischio di darle una cifra sbagliata.»",
                ],
                "esempio": "«Con questa soluzione, se si ferma per infortunio "
                           "riceve 100 € al giorno. L'investimento è di 480 € "
                           "l'anno, anche in rate mensili da 40 €. E copre "
                           "anche il tempo libero, compresi i suoi weekend in "
                           "montagna.» (silenzio)",
                "esercizio": "Allenati davanti allo specchio a dire i tuoi 3 "
                             "prezzi più frequenti con la tecnica sandwich, senza esitazioni.",
            },
        ],
        "quiz": [
            {
                "domanda": "Quale elemento del modello FAB convince davvero il cliente?",
                "opzioni": ["La caratteristica tecnica", "Il vantaggio generale", "Il beneficio collegato al suo problema"],
                "corretta": 2,
                "spiegazione": "Il beneficio traduce la polizza nella vita del cliente, usando i problemi che lui stesso ha espresso.",
            },
            {
                "domanda": "Perché presentare tre opzioni?",
                "opzioni": ["Per confondere il cliente",
                            "Per spostare la domanda da «se comprare» a «quale scegliere»",
                            "Perché lo impone la compagnia"],
                "corretta": 1,
                "spiegazione": "La scelta tra alternative coerenti riduce il rischio percepito di decidere.",
            },
            {
                "domanda": "Subito dopo aver detto il prezzo, cosa fai?",
                "opzioni": ["Offri uno sconto per anticipare l'obiezione", "Taci e lasci reagire il cliente", "Ripeti il prezzo"],
                "corretta": 1,
                "spiegazione": "Il silenzio comunica sicurezza; uno sconto non richiesto comunica che il prezzo era gonfiato.",
            },
        ],
        "fonti": [
            "Neil Rackham, «SPIN Selling» (capitolo sulla dimostrazione delle capacità)",
            "Dan Ariely, «Prevedibilmente irrazionale» (ancoraggio, effetto esca)",
            "Robert Cialdini, «Le armi della persuasione» (contrasto percettivo)",
        ],
    },
    # ------------------------------------------------------------------ 7
    {
        "id": "obiezioni",
        "area": "Trattativa",
        "icona": "bi-shield-exclamation",
        "titolo": "Gestione delle obiezioni",
        "obiettivo": "Accogliere l'obiezione come richiesta di informazioni, "
                     "distinguere obiezioni vere da scuse e rispondere con metodo.",
        "lezioni": [
            {
                "id": "obiezioni-laer",
                "titolo": "Il metodo ACER: ascolta, conferma, esplora, rispondi",
                "teoria": "Il modello LAER (Listen, Acknowledge, Explore, "
                          "Respond), qui ACER, evita l'errore più comune: "
                          "rispondere subito difendendosi. Ascolta fino in "
                          "fondo; conferma di aver capito e riconosci la "
                          "legittimità del dubbio (non vuol dire dargli "
                          "ragione); esplora con domande per capire la vera "
                          "causa; rispondi solo a quella. Un'obiezione è un "
                          "segnale di interesse: chi non è interessato non "
                          "obietta, se ne va.",
                "punti": [
                    "Ascolta senza interrompere e senza preparare la replica mentre l'altro parla.",
                    "Conferma: «Capisco, è una considerazione sensata.»",
                    "Esplora: «Cosa intende esattamente?» «Rispetto a cosa?» «Oltre a questo, c'è altro?»",
                    "Rispondi e verifica: «Questo risponde al suo dubbio?»",
                ],
                "esempio": "«È troppo caro.» → «Capisco, è giusto valutarlo "
                           "bene. Caro rispetto a cosa? A un'altra offerta o a "
                           "quanto aveva previsto di spendere?» Solo dopo la "
                           "risposta sai se il tema è il budget, il confronto o "
                           "il valore percepito.",
                "esercizio": "Prendi le 5 obiezioni che senti più spesso e per "
                             "ognuna scrivi 2 domande di esplorazione.",
            },
            {
                "id": "obiezioni-tecniche",
                "titolo": "Tecniche di risposta",
                "teoria": "Una volta capita l'obiezione, puoi scegliere tra "
                          "tecniche collaudate: «Capisco – altri hanno pensato – "
                          "poi hanno scoperto» (Feel-Felt-Found) per normalizzare "
                          "il dubbio; l'isolamento («a parte questo, ci sono altri "
                          "motivi?») per capire se è l'unico ostacolo; il "
                          "boomerang, che trasforma l'obiezione nel motivo per "
                          "acquistare; la domanda di ritorno, che restituisce "
                          "l'obiezione come domanda; la compensazione, che "
                          "ammette un limite e lo bilancia con un vantaggio più grande.",
                "punti": [
                    "Feel-Felt-Found: «Capisco cosa prova; anche altri clienti lo pensavano; poi hanno scoperto che…»",
                    "Isolamento: «Se il premio fosse sistemato, procederemmo?»",
                    "Boomerang: «Proprio perché è giovane e sano, oggi paga il minimo e non ha esclusioni.»",
                    "Domanda di ritorno: «Ci devo pensare.» → «Certo. Su quale punto in particolare vuole riflettere?»",
                    "Compensazione: «È vero, la franchigia è più alta; in cambio il massimale è doppio.»",
                ],
                "esempio": "«Ho già l'assicurazione con la banca.» → «Ottimo, "
                           "vuol dire che il tema le sta a cuore. Molti miei "
                           "clienti pensavano di essere coperti, poi confrontando "
                           "le condizioni hanno scoperto che la polizza del mutuo "
                           "tutelava la banca, non la famiglia. Le va se le diamo "
                           "un'occhiata insieme?»",
                "esercizio": "Consulta la libreria delle obiezioni e, per 3 di "
                             "esse, prova ad alta voce due tecniche diverse.",
            },
            {
                "id": "obiezioni-prevenire",
                "titolo": "Scuse, obiezioni vere e prevenzione",
                "teoria": "Una scusa è un modo cortese di dire «non mi hai "
                          "convinto» o «non mi fido abbastanza»; un'obiezione "
                          "vera è un ostacolo concreto. Le scuse si "
                          "riconoscono perché cambiano quando le risolvi. Le "
                          "obiezioni ricorrenti si prevengono: se 7 clienti su 10 "
                          "dicono «costa troppo», affronta il tema del valore "
                          "prima del prezzo, nell'analisi. Anticipare "
                          "un'obiezione («Forse si starà chiedendo se…») ne "
                          "toglie la forza.",
                "punti": [
                    "Test della scusa: risolvi il punto e osserva se ne compare subito un altro.",
                    "Se compaiono scuse a catena, torna all'analisi: manca il bisogno o la fiducia.",
                    "Tieni un registro delle obiezioni e del momento in cui compaiono.",
                    "Prevenzione: inserisci la risposta alle obiezioni frequenti dentro la presentazione.",
                ],
                "esempio": "«Molti clienti a questo punto mi chiedono: ma se "
                           "poi non mi pagano? Gliela spiego subito, perché è la "
                           "domanda più giusta che si possa fare.»",
                "esercizio": "Analizza le ultime 10 trattative perse: quante "
                             "obiezioni erano in realtà scuse? Cosa mancava prima?",
            },
        ],
        "quiz": [
            {
                "domanda": "Qual è il primo errore da evitare quando arriva un'obiezione?",
                "opzioni": ["Fare domande", "Rispondere subito difendendosi", "Riconoscere il dubbio del cliente"],
                "corretta": 1,
                "spiegazione": "Prima si ascolta e si esplora: solo così si risponde alla vera causa.",
            },
            {
                "domanda": "«A parte il prezzo, c'è qualcos'altro che la frena?» è un esempio di…",
                "opzioni": ["Isolamento", "Boomerang", "Chiusura alternativa"],
                "corretta": 0,
                "spiegazione": "L'isolamento verifica se l'obiezione è l'unico ostacolo alla decisione.",
            },
            {
                "domanda": "Se risolvi un'obiezione e ne compare subito un'altra, probabilmente…",
                "opzioni": ["Il cliente è difficile, meglio lasciar perdere",
                            "Si tratta di scuse: mancano bisogno percepito o fiducia",
                            "Devi offrire uno sconto"],
                "corretta": 1,
                "spiegazione": "Le scuse a catena indicano che il problema è a monte: torna all'analisi dei bisogni.",
            },
        ],
        "fonti": [
            "Modello LAER (Listen, Acknowledge, Explore, Respond), diffuso nella formazione dei consulenti finanziari",
            "Tom Hopkins, «How to Master the Art of Selling»",
            "Brian Tracy, «The Psychology of Selling»",
        ],
    },
    # ------------------------------------------------------------------ 8
    {
        "id": "negoziazione",
        "area": "Trattativa",
        "icona": "bi-arrow-left-right",
        "titolo": "Negoziazione",
        "obiettivo": "Negoziare condizioni e prezzo senza svendere, cercando "
                     "accordi che soddisfino gli interessi reali di entrambe le parti.",
        "lezioni": [
            {
                "id": "negoziazione-harvard",
                "titolo": "Il metodo Harvard: interessi, non posizioni",
                "teoria": "Fisher e Ury (Harvard Negotiation Project) "
                          "distinguono la posizione («voglio pagare 500 €») "
                          "dall'interesse che la genera («devo restare nel "
                          "budget del trimestre», «voglio sentirmi trattato "
                          "bene»). Lavorando sugli interessi emergono soluzioni "
                          "che il braccio di ferro sulle posizioni non vede: "
                          "frazionamento, decorrenza diversa, franchigia "
                          "modulata, pacchetto multi-polizza. Il BATNA (la "
                          "migliore alternativa a un accordo) è la tua forza: "
                          "conosci il tuo e stima quello del cliente.",
                "punti": [
                    "Separa le persone dal problema: si può essere duri sul tema e cordiali con la persona.",
                    "Chiedi «perché è importante per lei?» per arrivare all'interesse.",
                    "Inventa opzioni prima di decidere: «Proviamo a vedere tre modi diversi per arrivarci.»",
                    "Usa criteri oggettivi: tariffe di mercato, statistiche di sinistrosità, costi di un danno reale.",
                ],
                "esempio": "Il cliente vuole uno sconto del 20%. Scopri che il "
                           "vero interesse è pagare meno subito perché a marzo ha "
                           "le tasse. Soluzione: frazionamento semestrale con "
                           "prima rata ad aprile, premio invariato.",
                "esercizio": "Per una trattativa in corso scrivi: posizione del "
                             "cliente, 2 possibili interessi, tuo BATNA, suo BATNA, 3 opzioni.",
            },
            {
                "id": "negoziazione-concessioni",
                "titolo": "Concessioni condizionate e ancoraggio",
                "teoria": "Ogni concessione deve avere un prezzo: «se… allora». "
                          "Una concessione gratuita insegna al cliente che "
                          "insistere funziona e svaluta la tua proposta. Le "
                          "concessioni vanno fatte decrescenti (sempre più "
                          "piccole), per segnalare che si sta arrivando al "
                          "limite. Evita di «dividere la differenza» per "
                          "abitudine: premia chi ha ancorato più lontano.",
                "punti": [
                    "Formula: «Se lei… (firma oggi / aggiunge la polizza casa / sceglie il pagamento annuale), allora io posso…»",
                    "Concedi variabili a basso costo per te e alto valore per lui (servizio, revisione semestrale, pratica sinistri seguita personalmente).",
                    "Preparati prima: obiettivo, limite e lista di concessioni possibili.",
                    "Riassumi ogni accordo parziale per fissarlo.",
                ],
                "esempio": "«Posso rivedere la franchigia, se in cambio "
                           "accorpiamo anche la polizza del furgone: così il "
                           "pacchetto ha un senso anche per la compagnia.»",
                "esercizio": "Prepara la tua lista di 6 concessioni possibili, "
                             "ordinate da quella che costa meno a te a quella che costa di più.",
            },
            {
                "id": "negoziazione-voss",
                "titolo": "Empatia tattica (Chris Voss)",
                "teoria": "Chris Voss, ex negoziatore FBI, propone strumenti per "
                          "far sentire l'altro compreso e guidarlo: il "
                          "rispecchiamento (ripetere le ultime 1-3 parole "
                          "dell'altro con tono interrogativo, per farlo "
                          "continuare), l'etichettatura delle emozioni («Sembra "
                          "che…»), le domande calibrate (iniziano con «come» o "
                          "«cosa» e fanno lavorare l'altro sulla soluzione) e le "
                          "domande orientate al «no», più facili da accettare.",
                "punti": [
                    "Rispecchiamento: «…non mi fido delle assicurazioni.» → «Non si fida?»",
                    "Etichettatura: «Sembra che abbia avuto una brutta esperienza con un sinistro.»",
                    "Domanda calibrata: «Come posso aiutarla a presentare la proposta ai suoi soci?»",
                    "Domanda orientata al no: «Sarebbe una cattiva idea fissare un incontro di 15 minuti la settimana prossima?»",
                ],
                "esempio": "«Sembra che il tema del prezzo la preoccupi meno "
                           "di quello che succede quando c'è un sinistro.» "
                           "(pausa) — «Esatto, l'ultima volta nessuno mi ha "
                           "seguito.» Ora sai su cosa negoziare: il servizio.",
                "esercizio": "In ogni conversazione della settimana (anche non "
                             "commerciale) usa almeno un rispecchiamento e un'etichettatura.",
            },
        ],
        "quiz": [
            {
                "domanda": "Nel metodo Harvard, cosa si cerca di far emergere?",
                "opzioni": ["Le posizioni", "Gli interessi che generano le posizioni", "Il prezzo minimo del cliente"],
                "corretta": 1,
                "spiegazione": "Lavorando sugli interessi si trovano soluzioni creative che soddisfano entrambi.",
            },
            {
                "domanda": "Cos'è il BATNA?",
                "opzioni": ["La migliore alternativa a un accordo negoziato",
                            "Lo sconto massimo concedibile",
                            "Un tipo di clausola contrattuale"],
                "corretta": 0,
                "spiegazione": "Best Alternative To a Negotiated Agreement: più è forte il tuo, più puoi negoziare con serenità.",
            },
            {
                "domanda": "Qual è una concessione fatta correttamente?",
                "opzioni": ["«Va bene, le faccio il 10% di sconto.»",
                            "«Se sceglie il pagamento annuale, allora posso ridurre la franchigia.»",
                            "«Dividiamo la differenza.»"],
                "corretta": 1,
                "spiegazione": "Ogni concessione è condizionata a una contropartita.",
            },
        ],
        "fonti": [
            "Roger Fisher, William Ury, «L'arte del negoziato» (Getting to Yes)",
            "Chris Voss, «Never Split the Difference»",
            "Deepak Malhotra, Max Bazerman, «Negotiation Genius»",
        ],
    },
    # ------------------------------------------------------------------ 9
    {
        "id": "chiusura",
        "area": "Trattativa",
        "icona": "bi-check2-circle",
        "titolo": "Chiusura",
        "obiettivo": "Riconoscere i segnali d'acquisto e chiedere la decisione in "
                     "modo naturale, senza pressioni scorrette.",
        "lezioni": [
            {
                "id": "chiusura-segnali",
                "titolo": "Segnali d'acquisto e chiusure di prova",
                "teoria": "Il cliente comunica la propria disponibilità prima "
                          "di dirla: domande sui dettagli operativi («da quando "
                          "parte?», «come si paga?»), coinvolgimento di altri "
                          "(«ne parlo con mia moglie stasera»), linguaggio al "
                          "possesso («la mia polizza»), segnali non verbali. "
                          "Le chiusure di prova («Come le sembra finora?») "
                          "misurano la temperatura senza chiedere la firma e ti "
                          "dicono se proseguire o tornare indietro.",
                "punti": [
                    "Rispondi a un segnale d'acquisto con una domanda: «Vuole che parta dal primo del mese?»",
                    "Chiusura di prova dopo ogni beneficio importante.",
                    "Se la temperatura è bassa, non chiudere: torna a esplorare.",
                    "Non parlare oltre il «sì»: chi continua a vendere rischia di ricomprare.",
                ],
                "esempio": "Cliente: «E se ho un sinistro chi chiamo?» → «Chiama "
                           "me, direttamente. Le lascio il mio numero sulla "
                           "polizza: la facciamo partire dal primo novembre?»",
                "esercizio": "Elenca 10 segnali d'acquisto che hai sentito nella "
                             "tua esperienza e la domanda con cui avresti potuto rispondere.",
            },
            {
                "id": "chiusura-tecniche",
                "titolo": "Le tecniche di chiusura",
                "teoria": "Chiedere la decisione è un atto di servizio: il "
                          "cliente ha bisogno di qualcuno che lo aiuti a "
                          "decidere. Le principali tecniche: alternativa "
                          "(scegliere tra due opzioni entrambe positive), "
                          "riepilogativa (riassumere i bisogni e i benefici e "
                          "chiedere conferma), assuntiva (procedere con i "
                          "dettagli dando per acquisita la decisione, solo se i "
                          "segnali sono chiari), del prossimo passo (nelle "
                          "vendite complesse chiudi un impegno, non per forza il "
                          "contratto). Dopo la domanda di chiusura: silenzio.",
                "punti": [
                    "Alternativa: «Preferisce il pagamento annuale o semestrale?»",
                    "Riepilogativa: «Abbiamo detto: proteggere il reddito, la casa e i figli. Questa soluzione li copre tutti e tre. Procediamo?»",
                    "Assuntiva: «Mi serve solo un documento d'identità per la proposta.»",
                    "Prossimo passo: «Fissiamo giovedì la presentazione ai suoi soci?»",
                ],
                "esempio": "«Riassumendo: le serviva una copertura che "
                           "rimborsasse il fermo del laboratorio e la tutelasse "
                           "per gli errori sui progetti. La soluzione consigliata "
                           "fa entrambe le cose, a 82 € al mese. Procediamo con "
                           "questa?» (silenzio)",
                "esercizio": "Scrivi la tua chiusura riepilogativa per la "
                             "prossima proposta in calendario.",
            },
            {
                "id": "chiusura-etica",
                "titolo": "Urgenza vera e pressione scorretta",
                "teoria": "L'urgenza è legittima quando è reale: un rischio "
                          "attivo da domani (nuovo cantiere, viaggio, apertura "
                          "di un locale), un adeguamento tariffario, l'età che "
                          "cambia il premio vita, un obbligo di legge (es. "
                          "copertura catastrofale per le imprese). Inventare "
                          "scadenze, offerte «solo oggi» o paure esagerate "
                          "produce disdette, reclami e perdita di reputazione. "
                          "Il cliente deve firmare convinto: sarà la base delle "
                          "vendite successive.",
                "punti": [
                    "Usa solo scadenze vere e verificabili.",
                    "Lascia sempre al cliente il diritto di dire no.",
                    "Se il cliente non è pronto, chiudi su un prossimo passo con data.",
                    "Un cliente convinto oggi è un cliente che rinnova e fa referenze domani.",
                ],
                "esempio": "«Non le metto fretta. L'unica cosa da sapere è che "
                           "il cantiere inizia lunedì e da quel giorno il rischio "
                           "è suo: per questo le suggerirei di decidere entro venerdì.»",
                "esercizio": "Per le tue trattative aperte individua l'eventuale "
                             "urgenza reale. Se non c'è, definisci un prossimo passo con data.",
            },
        ],
        "quiz": [
            {
                "domanda": "«Da quando partirebbe la copertura?» detto dal cliente è…",
                "opzioni": ["Un'obiezione", "Un segnale d'acquisto", "Una domanda tecnica irrilevante"],
                "corretta": 1,
                "spiegazione": "Le domande sui dettagli operativi indicano che il cliente si sta immaginando cliente.",
            },
            {
                "domanda": "«Preferisce partire dal 1° o dal 15 del mese?» è una chiusura…",
                "opzioni": ["Alternativa", "Riepilogativa", "Di prova"],
                "corretta": 0,
                "spiegazione": "Offre due opzioni entrambe positive, spostando la decisione sul «come».",
            },
            {
                "domanda": "Quale forma di urgenza è corretta?",
                "opzioni": ["«L'offerta vale solo oggi» (non vero)",
                            "«Il cantiere parte lunedì e da lì il rischio è attivo»",
                            "«Se non firma ora potrebbe succederle qualcosa stanotte»"],
                "corretta": 1,
                "spiegazione": "Solo urgenze reali e verificabili: le altre generano disdette e reclami.",
            },
        ],
        "fonti": [
            "Zig Ziglar, «Secrets of Closing the Sale»",
            "Neil Rackham, «SPIN Selling» (sul prossimo passo nelle vendite complesse)",
            "Codice delle Assicurazioni Private (D.Lgs. 209/2005), regole di comportamento",
        ],
    },
    # ------------------------------------------------------------------ 10
    {
        "id": "continuita",
        "area": "Continuità",
        "icona": "bi-arrow-repeat",
        "titolo": "Continuità della trattativa e follow-up",
        "obiettivo": "Non lasciare morire le trattative: ogni contatto termina "
                     "con un prossimo passo concordato e ogni follow-up aggiunge valore.",
        "lezioni": [
            {
                "id": "continuita-prossimo-passo",
                "titolo": "La regola del prossimo passo",
                "teoria": "Una trattativa senza prossimo passo è una trattativa "
                          "persa che non sa ancora di esserlo. Ogni incontro, "
                          "telefonata o email si chiude con un'azione concreta, "
                          "una data e un responsabile: «Le mando la proposta "
                          "domani, ci sentiamo giovedì alle 10 per i suoi "
                          "dubbi». Rackham distingue gli avanzamenti (il cliente "
                          "si impegna in un'azione) dalle continuazioni "
                          "(«ci risentiamo»), che non fanno avanzare nulla.",
                "punti": [
                    "Mai uscire senza data: «Quando ci risentiamo?» è già tardi, proponi tu la data.",
                    "Il prossimo passo deve impegnare anche il cliente (documenti, incontro con il socio, visita in azienda).",
                    "Registra subito il follow-up nel gestionale con data e priorità.",
                    "Conferma per iscritto quanto concordato entro 24 ore.",
                ],
                "esempio": "«Perfetto, allora lei recupera le condizioni della "
                           "polizza attuale, io preparo il confronto. Ci vediamo "
                           "mercoledì 12 alle 18 qui da lei: le mando conferma via email.»",
                "esercizio": "Controlla la Pipeline: ogni opportunità aperta ha "
                             "un follow-up con data? Se no, fissalo oggi.",
            },
            {
                "id": "continuita-ci-penso",
                "titolo": "«Ci devo pensare» e trattative ferme",
                "teoria": "«Ci devo pensare» è la frase che fa morire più "
                          "trattative. Va accolta, esplorata («su cosa vuole "
                          "riflettere?») e trasformata in un appuntamento "
                          "preciso. Se la trattativa si è fermata, riattivala "
                          "portando qualcosa di nuovo: un'informazione, un caso, "
                          "una novità normativa — mai «la chiamavo per sapere se "
                          "ha deciso». Dopo più tentativi senza risposta, il "
                          "messaggio di chiusura cortese («deduco che non sia una "
                          "priorità, chiudo la pratica») spesso ottiene risposta.",
                "punti": [
                    "Esplora: «Di solito quando un cliente mi dice così ha un dubbio sul prezzo, sulle condizioni o su di me. Qual è il suo?»",
                    "Fissa la data: «Le bastano tre giorni? La chiamo venerdì alle 11.»",
                    "Ogni follow-up porta valore: un articolo, una storia, una risposta a un dubbio.",
                    "Cadenza indicativa: 2 giorni, 1 settimana, 2 settimane, 1 mese, poi nurturing trimestrale.",
                ],
                "esempio": "Messaggio di riattivazione: «Buongiorno Marco, ho "
                           "letto che dal prossimo anno cambiano le regole sulla "
                           "copertura catastrofale per le imprese: riguarda anche "
                           "il suo capannone. Le spiego in 10 minuti cosa "
                           "cambia, martedì o mercoledì?»",
                "esercizio": "Scegli 3 trattative ferme e prepara per ognuna un "
                             "messaggio di riattivazione che porti un'informazione nuova.",
            },
            {
                "id": "continuita-dopo-no",
                "titolo": "Dopo un «no» e dopo la firma",
                "teoria": "Un «no» oggi non è un «no» per sempre: le situazioni "
                          "cambiano (nuova sede, figli, assunzioni, sinistro del "
                          "vicino). Chiudi bene la relazione, chiedi il permesso "
                          "di ricontattare e programma un follow-up a 6-12 mesi. "
                          "Dopo la firma inizia la seconda vendita: consegna "
                          "spiegata, contatto di benvenuto, verifica dopo 30 "
                          "giorni. Il momento più delicato per la fidelizzazione "
                          "è il primo sinistro.",
                "punti": [
                    "Dopo un no: «Posso risentirla tra sei mesi per vedere se è cambiato qualcosa?»",
                    "Consegna la polizza di persona e spiega cosa fare in caso di sinistro.",
                    "Follow-up a 30 giorni: «Ha domande sulla polizza?» e richiesta di referenze.",
                    "In caso di sinistro, sii presente prima che il cliente chiami.",
                ],
                "esempio": "«Capisco che oggi non sia il momento. Le lascio la "
                           "mia analisi, è sua. Mi permette di richiamarla a "
                           "marzo, quando chiude il bilancio?»",
                "esercizio": "Crea nel gestionale un follow-up a 6 mesi per ogni "
                             "trattativa persa negli ultimi 3 mesi.",
            },
        ],
        "quiz": [
            {
                "domanda": "Quale chiusura di un incontro fa avanzare la trattativa?",
                "opzioni": ["«Ci risentiamo.»",
                            "«Le mando del materiale.»",
                            "«Lei recupera la polizza attuale, ci vediamo mercoledì alle 18.»"],
                "corretta": 2,
                "spiegazione": "Un avanzamento ha azione concreta, data e impegno del cliente.",
            },
            {
                "domanda": "Come si riattiva correttamente una trattativa ferma?",
                "opzioni": ["Chiamando per chiedere se ha deciso",
                            "Portando un'informazione nuova e utile",
                            "Offrendo uno sconto"],
                "corretta": 1,
                "spiegazione": "Ogni contatto deve aggiungere valore, altrimenti è percepito come pressione.",
            },
            {
                "domanda": "Qual è il momento più delicato per la fidelizzazione del cliente?",
                "opzioni": ["La firma", "Il primo sinistro", "Il pagamento della prima rata"],
                "corretta": 1,
                "spiegazione": "È lì che il cliente verifica se la promessa è stata mantenuta.",
            },
        ],
        "fonti": [
            "Neil Rackham, «SPIN Selling» (avanzamenti e continuazioni)",
            "Jeb Blount, «Sales EQ»",
            "David Sandler, sistema Sandler (gestione del «ci penso»)",
        ],
    },
    # ------------------------------------------------------------------ 11
    {
        "id": "portafoglio",
        "area": "Portafoglio",
        "icona": "bi-graph-up-arrow",
        "titolo": "Sviluppo e fidelizzazione del portafoglio",
        "obiettivo": "Far crescere il valore di ogni cliente nel tempo con "
                     "revisioni periodiche, cross-selling, segmentazione e un "
                     "servizio che genera fedeltà e referenze.",
        "lezioni": [
            {
                "id": "portafoglio-segmentazione",
                "titolo": "Segmentazione ABC e principio di Pareto",
                "teoria": "In molti portafogli circa il 20% dei clienti genera "
                          "l'80% delle provvigioni. Segmentare (A: alto valore o "
                          "alto potenziale; B: medio; C: base) permette di "
                          "dedicare il tempo dove rende: i clienti A ricevono "
                          "revisioni frequenti e contatto personale, i B "
                          "revisione annuale, i C servizio efficiente e "
                          "comunicazioni periodiche. Il potenziale conta quanto "
                          "il valore attuale: un professionista giovane con una "
                          "sola polizza può diventare un cliente A.",
                "punti": [
                    "Classifica i clienti per provvigioni attuali e potenziale (dalla gap analysis).",
                    "A: almeno 2 contatti di valore all'anno + revisione completa.",
                    "B: revisione annuale prima del rinnovo principale.",
                    "C: comunicazioni periodiche e richiamo al rinnovo; promuovi a B chi mostra potenziale.",
                ],
                "esempio": "Dalle Statistiche il consulente scopre che 30 "
                           "aziende producono il 70% delle provvigioni: per "
                           "ognuna programma una revisione semestrale.",
                "esercizio": "Classifica i tuoi primi 50 clienti in A, B, C e "
                             "pianifica i contatti del prossimo trimestre.",
            },
            {
                "id": "portafoglio-cross",
                "titolo": "Cross-selling, up-selling e revisione annuale",
                "teoria": "Il cross-selling propone coperture su rischi "
                          "diversi (dall'auto all'infortuni), l'up-selling "
                          "migliora una copertura esistente (massimali, "
                          "garanzie). La revisione annuale è lo strumento "
                          "principe: cosa è cambiato nella vita o nell'azienda "
                          "del cliente? Ogni cambiamento (matrimonio, figlio, "
                          "casa, assunzioni, nuovo macchinario, export) è un "
                          "nuovo rischio. Più polizze ha un cliente, meno "
                          "probabilmente se ne va: la multi-polizza è anche "
                          "uno strumento di fidelizzazione.",
                "punti": [
                    "Domanda di revisione: «Cosa è cambiato quest'anno nella sua vita o nella sua attività?»",
                    "Momenti di vita come trigger: nascita, mutuo, pensione, successione, nuova sede.",
                    "Usa la gap analysis del gestionale prima di ogni revisione.",
                    "Proponi un solo tema per volta: meglio una polizza in più ogni anno che cinque rifiutate insieme.",
                ],
                "esempio": "«L'anno scorso mi aveva detto che stava pensando "
                           "di assumere: lo ha fatto? Allora dobbiamo parlare "
                           "della RCO, perché ora un infortunio di un "
                           "dipendente può ricadere su di lei.»",
                "esercizio": "Prepara un modulo di revisione annuale con 10 "
                             "domande sui cambiamenti di vita e di attività.",
            },
            {
                "id": "portafoglio-retention",
                "titolo": "Fidelizzazione e valore del cliente nel tempo",
                "teoria": "Acquisire un cliente nuovo costa molto più che "
                          "mantenerne uno; il valore di un cliente va misurato "
                          "sull'intera durata della relazione (lifetime value), "
                          "non sulla singola polizza. La fedeltà nasce da "
                          "contatti regolari non legati alla vendita "
                          "(auguri, aggiornamenti, check-up), dalla gestione "
                          "eccellente dei sinistri e dal sentirsi riconosciuti. "
                          "Misurare la soddisfazione (es. Net Promoter Score: "
                          "«Da 0 a 10, quanto mi consiglierebbe?») indica chi è "
                          "pronto a dare referenze e chi rischia di andarsene.",
                "punti": [
                    "Calendario di contatti di valore: almeno 4 all'anno per i clienti A.",
                    "Chiedi l'NPS dopo ogni sinistro chiuso: i promotori (9-10) sono i migliori per le referenze.",
                    "Monitora le disdette: chiama sempre per capirne il motivo.",
                    "Lifetime value = provvigione media annua × anni di permanenza × polizze per cliente.",
                ],
                "esempio": "Un cliente con 3 polizze da 150 € di provvigione "
                           "l'una che resta 15 anni vale 6.750 €: perderlo per "
                           "non aver risposto al telefono durante un sinistro "
                           "costa molto più di qualsiasi sconto.",
                "esercizio": "Calcola il lifetime value medio dei tuoi clienti A "
                             "e definisci 4 contatti di valore per il prossimo anno.",
            },
            {
                "id": "portafoglio-mappa",
                "titolo": "La mappa relazionale: ogni cliente è un ecosistema",
                "teoria": "Ogni cliente è al centro di cerchie di relazioni che "
                          "sono anche cerchie di rischio e di opportunità. Per "
                          "un privato: coniuge, figli, genitori anziani, "
                          "fratelli, colleghi, amici. Per un'azienda: soci, "
                          "familiari dei soci, dipendenti (welfare aziendale, "
                          "convenzioni), fornitori, clienti, commercialista, "
                          "banca. Disegnare la mappa con il cliente "
                          "(«chi dipende da lei? da chi dipende lei?») fa "
                          "emergere bisogni nuovi e nomi per le referenze "
                          "nello stesso momento. La ricerca sulle reti sociali "
                          "mostra che le informazioni nuove arrivano spesso dai "
                          "legami deboli (Granovetter, 1973): conoscenti, non "
                          "amici stretti.",
                "punti": [
                    "Privato: chi dipende economicamente da lui? Chi lo aiuterebbe se si fermasse?",
                    "Azienda: chi sono le 3 persone senza cui l'azienda si ferma? (key man, D&O, infortuni dei soci)",
                    "Dipendenti di un cliente azienda: proponi una convenzione o un piano di welfare, con il consenso del datore.",
                    "Fornitori e clienti del cliente: sono spesso della stessa filiera, quindi della tua nicchia.",
                ],
                "esempio": "Con un cliente titolare di un'impresa di pulizie "
                           "il consulente disegna la mappa: 2 soci, 40 "
                           "dipendenti, 3 clienti principali (condomini e "
                           "uffici), un commercialista. Ne nascono una "
                           "polizza key man, una convenzione infortuni per i "
                           "dipendenti e due presentazioni ad amministratori di condominio.",
                "esercizio": "Usa la scheda «Mappa delle relazioni e delle "
                             "referenze» con i tuoi 5 migliori clienti.",
            },
            {
                "id": "portafoglio-referenze-programma",
                "titolo": "Il programma referenze e gli eventi per i clienti",
                "teoria": "Le referenze arrivano con regolarità solo se sono "
                          "un processo, non un'occasione. Un programma "
                          "efficace ha: momenti fissi di richiesta (firma, "
                          "consegna, sinistro chiuso, revisione), una frase "
                          "preparata, un modo semplice per presentare "
                          "(messaggio pronto da inoltrare), un ringraziamento "
                          "sempre e un aggiornamento a chi ha segnalato. Gli "
                          "eventi per i clienti (una serata a tema, una visita, "
                          "un incontro informativo a cui ciascuno può portare "
                          "un amico) creano occasioni naturali di presentazione. "
                          "Attenzione: premi in denaro per le segnalazioni "
                          "vanno verificati con la normativa e con le regole "
                          "della compagnia; il ringraziamento personale è "
                          "sempre ammesso e spesso più efficace.",
                "punti": [
                    "4 momenti fissi di richiesta nel ciclo di vita del cliente.",
                    "Messaggio pronto: il cliente lo inoltra, tu ricevi il contatto con il permesso.",
                    "Ringrazia entro 24 ore e aggiorna sull'esito, anche se è un no.",
                    "Un evento clienti all'anno con formula «porta un amico».",
                ],
                "esempio": "Messaggio da far inoltrare: «Ciao Luca, ti presento "
                           "Anna, la consulente che mi ha sistemato le polizze "
                           "dell'officina. Mi ha trovato due buchi che non "
                           "sapevo di avere: ti consiglio un controllo, è gratuito.»",
                "esercizio": "Scrivi il tuo programma referenze: momenti, frase, "
                             "messaggio da inoltrare, ringraziamento. Misura le "
                             "referenze ricevute per 3 mesi.",
            },
            {
                "id": "portafoglio-campagne",
                "titolo": "Campagne sul portafoglio con il gestionale",
                "teoria": "Una campagna è un'azione mirata su un gruppo di "
                          "clienti con lo stesso bisogno, in un periodo "
                          "definito. Il gestionale ti dà i dati per "
                          "costruirla: tipo di cliente, rami posseduti, "
                          "coperture scoperte dalla gap analysis, scadenze. "
                          "Esempi: tutte le aziende senza catastrofali, tutti i "
                          "professionisti senza tutela legale, tutti i clienti "
                          "privati con figli e senza temporanea caso morte. "
                          "Una buona campagna ha un messaggio specifico, un "
                          "motivo per agire ora (vero), un'offerta di "
                          "consulenza e un indicatore di risultato.",
                "punti": [
                    "Seleziona il gruppo: gap analysis + tipo cliente + consenso marketing.",
                    "Messaggio: problema specifico + caso reale + invito a una verifica.",
                    "Canali in sequenza: email o lettera → telefonata dopo 3-5 giorni → appuntamento.",
                    "Misura: contattati, appuntamenti, proposte, contratti. Trasforma ogni interesse in un'opportunità in Pipeline.",
                ],
                "esempio": "Campagna d'autunno «Neve e ghiaccio»: ai clienti "
                           "con flotte o furgoni, controllo delle garanzie "
                           "eventi atmosferici e assistenza. 60 contattati, 18 "
                           "verifiche, 9 adeguamenti.",
                "esercizio": "Progetta la tua prossima campagna: gruppo, "
                             "messaggio, sequenza dei contatti, obiettivo numerico.",
            },
        ],
        "quiz": [
            {
                "domanda": "Il principio di Pareto applicato al portafoglio dice che…",
                "opzioni": ["Tutti i clienti vanno seguiti allo stesso modo",
                            "Una piccola parte dei clienti genera la maggior parte delle provvigioni",
                            "I clienti nuovi valgono più di quelli vecchi"],
                "corretta": 1,
                "spiegazione": "Segmentare permette di dedicare tempo dove rende di più, senza trascurare il potenziale.",
            },
            {
                "domanda": "Qual è la domanda chiave di una revisione annuale?",
                "opzioni": ["«Vuole aumentare i massimali?»",
                            "«Cosa è cambiato quest'anno nella sua vita o nella sua attività?»",
                            "«È soddisfatto del prezzo?»"],
                "corretta": 1,
                "spiegazione": "Ogni cambiamento genera nuovi rischi e quindi nuove esigenze di copertura.",
            },
            {
                "domanda": "Perché la multi-polizza aiuta la fidelizzazione?",
                "opzioni": ["Perché il cliente non può disdire",
                            "Perché aumenta i legami e il costo percepito del cambiamento",
                            "Perché costa meno"],
                "corretta": 1,
                "spiegazione": "Più coperture e più relazione rendono meno probabile l'abbandono.",
            },
        ],
        "fonti": [
            "Vilfredo Pareto e il principio 80/20 applicato alle vendite",
            "Frederick Reichheld, «The Ultimate Question» (Net Promoter Score)",
            "Philip Kotler, sul valore del cliente nel tempo (customer lifetime value)",
        ],
    },
    # ------------------------------------------------------------------ 12
    {
        "id": "crescita",
        "area": "Portafoglio",
        "icona": "bi-trophy",
        "titolo": "Organizzazione, KPI e allenamento continuo",
        "obiettivo": "Organizzare tempo e attività come un professionista, "
                     "misurare i progressi e allenare le tecniche con metodo.",
        "lezioni": [
            {
                "id": "crescita-tempo",
                "titolo": "Gestione del tempo e routine commerciale",
                "teoria": "Il consulente rischia di passare la giornata in "
                          "attività amministrative e urgenze. Il time blocking "
                          "riserva in agenda blocchi fissi per le attività che "
                          "generano ricavi: prospezione, appuntamenti, "
                          "revisioni. La «power hour» è un'ora al giorno, "
                          "senza interruzioni, dedicata solo a telefonate. La "
                          "matrice di Eisenhower aiuta a distinguere l'urgente "
                          "dall'importante.",
                "punti": [
                    "Blocca ogni mattina un'ora di telefonate: telefono in mano, email chiusa.",
                    "Raggruppa gli appuntamenti per zona geografica.",
                    "Delega o automatizza le attività amministrative (il gestionale genera da sé rinnovi e notifiche).",
                    "Ogni venerdì: rivedi la settimana e pianifica la successiva.",
                ],
                "esempio": "Settimana tipo: lunedì-giovedì 9-10 telefonate, "
                           "pomeriggi appuntamenti, venerdì mattina revisioni e "
                           "pianificazione, venerdì pomeriggio formazione.",
                "esercizio": "Disegna la tua settimana ideale con i blocchi fissi "
                             "e rispettala per 2 settimane.",
            },
            {
                "id": "crescita-kpi",
                "titolo": "KPI e rapporti di conversione",
                "teoria": "Misura poche cose ma con costanza: attività "
                          "(contatti, appuntamenti, analisi, proposte), "
                          "conversioni (appuntamenti/contatti, proposte/"
                          "appuntamenti, contratti/proposte), risultati "
                          "(premi, provvigioni, polizze per cliente, tasso di "
                          "rinnovo). L'andamento nel tempo conta più del dato "
                          "singolo: un calo nel rapporto proposte/contratti ti "
                          "dice che serve lavorare su presentazione e obiezioni.",
                "punti": [
                    "KPI settimanali: contatti, appuntamenti, proposte, contratti.",
                    "KPI mensili: provvigioni, polizze per cliente, valore della pipeline.",
                    "KPI annuali: tasso di rinnovo, crescita del portafoglio, referenze ricevute.",
                    "Collega ogni KPI debole al modulo dell'Accademia da ripassare.",
                ],
                "esempio": "Contratti/proposte sceso dal 40% al 25%: il "
                           "consulente ripassa i moduli sulla proposta e sulle obiezioni e riascolta le "
                           "ultime presentazioni.",
                "esercizio": "Crea una tabella settimanale dei tuoi KPI e "
                             "compilala per un mese.",
            },
            {
                "id": "crescita-allenamento",
                "titolo": "Pratica deliberata e role-play",
                "teoria": "Si migliora con la pratica deliberata: obiettivi "
                          "specifici, ripetizione, feedback immediato, uscita "
                          "dalla zona di comfort. Le tecniche di vendita sono "
                          "abilità, non nozioni: si imparano come uno sport. Il "
                          "role-play con colleghi (uno fa il cliente, uno il "
                          "consulente, uno osserva con una griglia) e la "
                          "registrazione delle proprie simulazioni accelerano "
                          "l'apprendimento più di qualsiasi lettura.",
                "punti": [
                    "Allenati su una abilità per volta: una settimana solo domande di implicazione.",
                    "Role-play a tre: consulente, cliente, osservatore con griglia di valutazione.",
                    "Usa gli scenari e l'allenamento sulle obiezioni dell'Accademia ogni giorno, 10 minuti.",
                    "Diario delle trattative: dopo ogni incontro, 3 righe su cosa ripetere e cosa cambiare.",
                ],
                "esempio": "Un gruppo di consulenti si incontra ogni lunedì per "
                           "30 minuti: ognuno porta un'obiezione ricevuta nella "
                           "settimana e la si prova a turno con tecniche diverse.",
                "esercizio": "Organizza un role-play settimanale con almeno un "
                             "collega usando gli scenari dell'Accademia.",
            },
        ],
        "quiz": [
            {
                "domanda": "Cos'è la «power hour»?",
                "opzioni": ["Un'ora di formazione online",
                            "Un'ora al giorno senza interruzioni dedicata solo alle telefonate",
                            "L'ora di punta per chiamare i clienti"],
                "corretta": 1,
                "spiegazione": "Un blocco protetto per l'attività che genera nuovi appuntamenti.",
            },
            {
                "domanda": "Il rapporto contratti/proposte è calato molto. Cosa ripassi?",
                "opzioni": ["La prospezione", "Presentazione della proposta e gestione delle obiezioni", "La telefonata per l'appuntamento"],
                "corretta": 1,
                "spiegazione": "Il calo avviene tra proposta e firma: lì vanno cercate le cause.",
            },
            {
                "domanda": "Quale caratteristica NON appartiene alla pratica deliberata?",
                "opzioni": ["Feedback immediato", "Obiettivi specifici", "Ripetere ciò che si sa già fare bene"],
                "corretta": 2,
                "spiegazione": "La pratica deliberata richiede di uscire dalla zona di comfort, lavorando sui punti deboli.",
            },
        ],
        "fonti": [
            "Anders Ericsson, «Peak» (pratica deliberata)",
            "Stephen Covey, «Le 7 regole per avere successo» (matrice urgente/importante)",
            "Jeb Blount, «Fanatical Prospecting» (power hour e time blocking)",
        ],
    },
]

# ----------------------------------------------------------------------
# Moduli aggiuntivi: psicologia della decisione, PNL, marketing e raccolta
# delle informazioni. Vengono inseriti nel percorso secondo ORDINE_MODULI.
# ----------------------------------------------------------------------
MODULI_EXTRA = [
    {
        "id": "psicologia",
        "area": "Fondamenta",
        "icona": "bi-cpu",
        "titolo": "Psicologia della decisione e della persuasione",
        "obiettivo": "Capire come le persone decidono davvero (non come dicono di "
                     "decidere) usando i risultati sperimentali della psicologia "
                     "sociale e dell'economia comportamentale, e applicarli in "
                     "modo etico alla consulenza assicurativa.",
        "lezioni": [
            {
                "id": "psicologia-due-sistemi",
                "titolo": "Pensieri veloci e lenti: perché il cliente non è un calcolatore",
                "teoria": "Daniel Kahneman (Nobel per l'economia 2002) descrive "
                          "due modalità di pensiero: il Sistema 1, rapido, "
                          "automatico ed emotivo, e il Sistema 2, lento, "
                          "faticoso e analitico. La maggior parte delle "
                          "decisioni quotidiane è guidata dal Sistema 1, che "
                          "usa scorciatoie (euristiche). Le assicurazioni sono "
                          "un prodotto difficile proprio per questo: chiedono "
                          "di pagare oggi una cifra certa per un evento futuro, "
                          "incerto e spiacevole da immaginare. Tre distorsioni "
                          "lavorano contro di te: il bias di ottimismo (Weinstein, "
                          "1980: la maggioranza delle persone si ritiene meno "
                          "esposta della media agli eventi negativi), la "
                          "preferenza per il presente (il futuro pesa meno del "
                          "dovuto, Laibson 1997) e l'euristica della "
                          "disponibilità (Tversky e Kahneman, 1973: giudichiamo "
                          "probabile ciò che ci viene in mente facilmente). Una "
                          "a favore: l'avversione alla perdita.",
                "punti": [
                    "Bias di ottimismo → non discuterlo con i numeri: rendi il rischio concreto con una storia vicina al cliente.",
                    "Euristica della disponibilità → un caso recente e locale pesa più di qualsiasi statistica nazionale.",
                    "Preferenza per il presente → riduci lo sforzo di oggi (rate mensili, partenza differita, pratica semplice).",
                    "Il Sistema 2 si attiva quando il cliente deve giustificare la scelta ad altri: prepara per lui le ragioni razionali da riportare.",
                ],
                "esempio": "Dopo un'alluvione nella zona, le richieste di "
                           "coperture catastrofali aumentano anche tra chi non "
                           "è stato colpito: è l'euristica della disponibilità. "
                           "Il consulente etico la usa per informare, non per "
                           "spaventare, e ricorda che il rischio esisteva anche prima.",
                "esercizio": "Per ciascuna delle tre distorsioni, scrivi una "
                             "frase che hai sentito da un cliente e come avresti "
                             "potuto rispondere tenendone conto.",
            },
            {
                "id": "psicologia-prospetto",
                "titolo": "Teoria del prospetto, avversione alla perdita e framing",
                "teoria": "Kahneman e Tversky (1979) hanno mostrato che le "
                          "persone valutano i risultati come guadagni o perdite "
                          "rispetto a un punto di riferimento, e che le perdite "
                          "pesano circa il doppio di guadagni equivalenti. Il "
                          "modo in cui un'informazione è presentata (framing) "
                          "cambia la scelta anche quando i numeri sono identici "
                          "(Tversky e Kahneman, 1981). Per il consulente: "
                          "presentare la copertura come protezione di ciò che "
                          "il cliente già possiede (casa, reddito, azienda, "
                          "tenore di vita della famiglia) è più efficace che "
                          "presentarla come un guadagno futuro. Attenzione però: "
                          "in ambito assicurativo la stessa teoria spiega perché "
                          "il premio, perdita certa, è percepito come doloroso; "
                          "per questo il premio va sempre confrontato con la "
                          "perdita evitata, non lasciato da solo.",
                "punti": [
                    "Cornice di perdita: «Cosa perderebbe la sua famiglia se…» è più forte di «Cosa guadagnerebbe se…».",
                    "Il punto di riferimento si può spostare: confronta il premio con il danno possibile, non con zero.",
                    "Effetto dotazione (Thaler): diamo più valore a ciò che già possediamo; ricorda al cliente cosa ha costruito.",
                    "Limite etico: la cornice di perdita va usata su rischi reali e con numeri veri.",
                ],
                "esempio": "«Ha costruito in vent'anni un'attività che oggi le "
                           "rende 60.000 € l'anno. La domanda non è se spendere "
                           "800 €, ma se è disposto a rischiare quello che ha "
                           "costruito per risparmiarli.»",
                "esercizio": "Riscrivi la presentazione di tre tue proposte "
                             "usando la cornice di protezione di ciò che il "
                             "cliente possiede già.",
            },
            {
                "id": "psicologia-cialdini",
                "titolo": "I principi dell'influenza di Cialdini",
                "teoria": "Robert Cialdini ha riassunto decenni di esperimenti "
                          "in sette principi che aumentano la probabilità di un "
                          "«sì». Reciprocità: ci sentiamo in debito con chi ci "
                          "ha dato qualcosa (un'analisi gratuita fatta bene). "
                          "Impegno e coerenza: dopo un piccolo impegno tendiamo "
                          "a restare coerenti (Freedman e Fraser, 1966, tecnica "
                          "del piede nella porta). Riprova sociale: seguiamo "
                          "ciò che fanno persone simili a noi (Goldstein, "
                          "Cialdini e Griskevicius, 2008). Autorità: ci fidiamo "
                          "di chi dimostra competenza. Simpatia: diciamo sì a "
                          "chi ci piace e ci somiglia. Scarsità: desideriamo di "
                          "più ciò che è limitato. Unità: ci fidiamo di chi "
                          "percepiamo come parte del nostro gruppo. Sono leve "
                          "potenti: usate su informazioni false diventano "
                          "manipolazione, e la normativa assicurativa vieta "
                          "pratiche commerciali scorrette.",
                "punti": [
                    "Reciprocità: dai valore vero prima di chiedere (check-up coperture, analisi rischi scritta).",
                    "Impegno: parti da un passo piccolo (ricevere la polizza attuale per un confronto).",
                    "Riprova sociale: «Molti studi tecnici che seguo hanno scelto…» — solo se è vero.",
                    "Autorità: mostra competenza con casi, certificazioni, contenuti; non con il titolo sul biglietto.",
                    "Scarsità: solo se reale (scadenza tariffaria, età che cambia il premio).",
                ],
                "esempio": "Il consulente consegna l'analisi dei rischi stampata "
                           "anche se il cliente non compra nulla (reciprocità); "
                           "chiede solo di poter rivedere insieme la polizza "
                           "attuale (piccolo impegno); cita, con il permesso, "
                           "due colleghi del cliente che si sono già protetti "
                           "(riprova sociale).",
                "esercizio": "Per ciascun principio scrivi un modo etico e "
                             "concreto di applicarlo nella tua prossima trattativa.",
            },
            {
                "id": "psicologia-scelta",
                "titolo": "Architettura della scelta: default, esche e opzioni",
                "teoria": "Il modo in cui le opzioni sono disposte influenza la "
                          "scelta (Thaler e Sunstein, «Nudge»). L'opzione di "
                          "default viene scelta molto più spesso: con l'adesione "
                          "automatica ai piani pensionistici aziendali la "
                          "partecipazione aumenta in modo drastico (Madrian e "
                          "Shea, 2001). L'effetto esca (Huber, Payne e Puto, "
                          "1982) e l'effetto compromesso (Simonson, 1989) "
                          "spiegano perché l'opzione centrale di tre viene "
                          "scelta spesso. Sul famoso «eccesso di scelta» "
                          "(esperimento delle marmellate, Iyengar e Lepper, "
                          "2000) le evidenze sono contrastanti: una meta-analisi "
                          "(Scheibehenne e colleghi, 2010) non trova un effetto "
                          "medio, ma per prodotti complessi come le polizze "
                          "poche opzioni chiare restano la scelta più prudente.",
                "punti": [
                    "Proponi la soluzione consigliata come punto di partenza (default) e lascia al cliente la libertà di togliere garanzie.",
                    "Tre opzioni bastano; dieci confondono.",
                    "«Risparmia di più domani» (Thaler e Benartzi, 2004): nella previdenza proponi aumenti futuri del versamento, legati agli aumenti di reddito.",
                    "Default e opzioni devono rispettare la coerenza con le esigenze del cliente: è un obbligo, non solo una buona pratica.",
                ],
                "esempio": "«La soluzione che le ho preparato comprende queste "
                           "quattro garanzie. Se vuole possiamo togliere la "
                           "tutela legale: il premio scende di 90 €, ma "
                           "resterebbe scoperto sulle vertenze con i dipendenti.»",
                "esercizio": "Riorganizza la tua proposta più frequente "
                             "partendo dalla soluzione consigliata come default "
                             "e prepara le varianti «in sottrazione».",
            },
        ],
        "quiz": [
            {
                "domanda": "Secondo la teoria del prospetto, le perdite pesano…",
                "opzioni": ["Quanto i guadagni equivalenti", "Circa il doppio dei guadagni equivalenti", "Meno dei guadagni equivalenti"],
                "corretta": 1,
                "spiegazione": "L'avversione alla perdita (Kahneman e Tversky, 1979) è stimata intorno a 2:1 in molti esperimenti.",
            },
            {
                "domanda": "Il cliente dice «a me non capiterà». Quale distorsione è all'opera?",
                "opzioni": ["Bias di ottimismo", "Effetto esca", "Reciprocità"],
                "corretta": 0,
                "spiegazione": "Il bias di ottimismo porta a sottostimare la propria esposizione agli eventi negativi.",
            },
            {
                "domanda": "Quale affermazione sull'«eccesso di scelta» è corretta?",
                "opzioni": ["È un effetto dimostrato e sempre presente",
                            "Le evidenze sono contrastanti, ma con prodotti complessi poche opzioni chiare sono prudenti",
                            "Più opzioni portano sempre a più vendite"],
                "corretta": 1,
                "spiegazione": "La meta-analisi di Scheibehenne e colleghi (2010) non trova un effetto medio; il contesto conta.",
            },
            {
                "domanda": "Usare la scarsità («solo oggi») quando non è vera è…",
                "opzioni": ["Una tecnica di chiusura efficace", "Una pratica scorretta, oltre che controproducente", "Obbligatorio per le polizze vita"],
                "corretta": 1,
                "spiegazione": "I principi di influenza vanno applicati solo su informazioni vere: altrimenti sono manipolazione.",
            },
        ],
        "fonti": [
            "Daniel Kahneman, «Pensieri lenti e veloci»",
            "Robert Cialdini, «Le armi della persuasione» e «Pre-suasione»",
            "Richard Thaler e Cass Sunstein, «Nudge. La spinta gentile»",
            "Kahneman e Tversky (1979), «Prospect Theory», Econometrica",
        ],
    },
    {
        "id": "pnl",
        "area": "Fondamenta",
        "icona": "bi-chat-square-heart",
        "titolo": "Comunicazione, PNL e linguaggio del corpo: cosa funziona davvero",
        "obiettivo": "Conoscere gli strumenti della Programmazione Neuro-Linguistica "
                     "più usati nella vendita e distinguere, sulla base della "
                     "ricerca, quelli utili da quelli smentiti.",
        "lezioni": [
            {
                "id": "pnl-cose",
                "titolo": "Che cos'è la PNL e cosa dice la ricerca",
                "teoria": "La PNL nasce negli anni '70 da Richard Bandler e John "
                          "Grinder, che studiarono il linguaggio di terapeuti "
                          "efficaci (Milton Erickson, Virginia Satir, Fritz "
                          "Perls) per ricavarne modelli replicabili. È molto "
                          "diffusa nella formazione commerciale, ma va studiata "
                          "con spirito critico: le revisioni della letteratura "
                          "scientifica (Sharpley, 1987; Witkowski, 2010) non "
                          "hanno trovato conferme per le sue tesi centrali, come "
                          "i «sistemi rappresentazionali preferiti» "
                          "(visivo-auditivo-cinestesico) o la lettura dei "
                          "movimenti oculari. Alcuni strumenti però funzionano, "
                          "perché coincidono con fenomeni studiati in modo "
                          "indipendente dalla psicologia: il rispecchiamento, le "
                          "domande di precisione, la riformulazione, la cornice "
                          "linguistica. In questo modulo impari a usare quelli e "
                          "a riconoscere i miti.",
                "punti": [
                    "Usa la PNL come cassetta di tecniche di comunicazione, non come scienza della mente.",
                    "Diffida di chi promette di «leggere» il cliente dagli occhi o di «programmarlo»: non c'è evidenza.",
                    "Ciò che funziona ha quasi sempre un nome anche in psicologia: verifica lì.",
                    "Il criterio finale è etico: le tecniche servono a capire e farsi capire, non a manipolare.",
                ],
                "esempio": "Un corso promette che, se il cliente guarda in alto "
                           "a destra, sta mentendo. Uno studio del 2012 "
                           "(Wiseman e colleghi) ha verificato l'ipotesi: i "
                           "movimenti oculari non distinguono chi mente da chi "
                           "dice il vero. Usa il tempo per ascoltare, non per "
                           "osservare le pupille.",
                "esercizio": "Elenca le tecniche di PNL che conosci e, per "
                             "ognuna, cerca nel modulo il suo livello di evidenza.",
            },
            {
                "id": "pnl-rapport",
                "titolo": "Rapport, ricalco e guida: la parte confermata",
                "teoria": "Nella PNL il «ricalco» consiste nell'adeguarsi a "
                          "postura, ritmo, tono e parole dell'interlocutore per "
                          "creare sintonia, e la «guida» nel condurlo poi verso "
                          "un nuovo stato. La psicologia sociale ha studiato lo "
                          "stesso fenomeno come imitazione spontanea: l'«effetto "
                          "camaleonte» (Chartrand e Bargh, 1999) mostra che chi "
                          "viene sottilmente imitato prova più simpatia e "
                          "l'interazione scorre meglio. Una cameriera che "
                          "ripeteva le ordinazioni con le stesse parole del "
                          "cliente riceveva mance più alte (van Baaren e "
                          "colleghi, 2003); nelle negoziazioni, chi imitava "
                          "sottilmente la controparte otteneva più spesso un "
                          "accordo (Maddux, Mullen e Galinsky, 2008). La chiave è "
                          "la sottigliezza: l'imitazione evidente viene percepita "
                          "e produce l'effetto contrario.",
                "punti": [
                    "Ripeti le parole chiave del cliente: se dice «il mio laboratorio», non chiamarlo «la sua azienda».",
                    "Adegua ritmo e volume della voce, non i gesti uno per uno.",
                    "Lascia qualche secondo di ritardo: mai imitare in tempo reale.",
                    "Guida: una volta in sintonia, rallenta tu il ritmo per portare il cliente alla riflessione.",
                ],
                "esempio": "Cliente: «Io lavoro con le mani, non con le carte.» "
                           "Consulente: «Allora le carte le guardo io, e a lei "
                           "dico solo cosa succede se si fanno male le mani.»",
                "esercizio": "Nei prossimi tre colloqui annota 5 parole tipiche "
                             "del cliente e riusale nella proposta scritta.",
            },
            {
                "id": "pnl-metamodello",
                "titolo": "Il metamodello: domande di precisione",
                "teoria": "Il metamodello della PNL classifica tre fenomeni del "
                          "linguaggio che fanno perdere informazioni: "
                          "generalizzazioni («le assicurazioni non pagano "
                          "mai»), cancellazioni («costa troppo» — rispetto a "
                          "cosa?) e deformazioni («se mi propone questo, vuol "
                          "dire che mi vuole spennare»). Per ciascuno esistono "
                          "domande di recupero. Il metamodello non è stato "
                          "validato come teoria, ma le domande che propone sono "
                          "di fatto domande di chiarimento, coerenti con quanto "
                          "la ricerca dice sull'ascolto: fare domande di "
                          "approfondimento aumenta la simpatia percepita "
                          "(Huang e colleghi, 2017) e un ascolto di qualità "
                          "riduce la difensività dell'interlocutore (Itzchakov e "
                          "Kluger).",
                "punti": [
                    "Generalizzazione («mai», «sempre», «tutti») → «Mai? Le è capitato personalmente?»",
                    "Cancellazione («è caro», «è meglio») → «Caro rispetto a cosa? Meglio per chi?»",
                    "Deformazione (lettura del pensiero, causa-effetto) → «Cosa glielo fa pensare?»",
                    "Usa il tono della curiosità, non dell'interrogatorio: una domanda alla volta.",
                ],
                "esempio": "«Tutti gli agenti vogliono solo vendere.» → «Tutti? "
                           "Le è successo con qualcuno in particolare?» → «Sì, "
                           "con quello di prima, che è sparito al primo "
                           "sinistro.» Ora sai che la vera esigenza è la "
                           "presenza durante i sinistri.",
                "esercizio": "Registra (con permesso) o ricostruisci un colloquio "
                             "e individua 3 generalizzazioni, cancellazioni o "
                             "deformazioni con la domanda che avresti potuto fare.",
            },
            {
                "id": "pnl-linguaggio",
                "titolo": "Linguaggio, presupposizioni e cornici",
                "teoria": "Il «modello Milton» della PNL raccoglie strutture "
                          "linguistiche vaghe e suggestive ispirate all'ipnosi "
                          "di Erickson. In vendita ne restano utili, con "
                          "moderazione, le presupposizioni (frasi che danno per "
                          "scontato un elemento: «Quando avrà la polizza, la "
                          "prima cosa da fare è…»), le domande di scelta e le "
                          "cornici positive. Ciò che la ricerca conferma "
                          "davvero è l'effetto della cornice (framing, "
                          "Tversky e Kahneman 1981) e il potere del «perché»: "
                          "nell'esperimento della fotocopiatrice (Langer, 1978) "
                          "dare una ragione, anche banale, aumentava molto "
                          "l'accettazione di una piccola richiesta. Le parole "
                          "che usi creano la cornice in cui il cliente decide.",
                "punti": [
                    "Motiva sempre le richieste: «Le chiedo la polizza attuale perché così confrontiamo le esclusioni, non solo il prezzo.»",
                    "Preferisci «investimento», «protezione», «tutela» a «costo» e «spesa», ma non mentire sui numeri.",
                    "Evita le negazioni che evocano l'immagine sbagliata: «non si preoccupi del prezzo» fa pensare al prezzo.",
                    "Presupposizioni con misura: usate di continuo diventano pressione e fanno scattare la diffidenza.",
                ],
                "esempio": "Invece di «Non è che le interesserebbe una polizza "
                           "infortuni?», prova: «Le mostro come funziona la "
                           "diaria in caso di infortunio, perché è la parte che "
                           "i miei clienti artigiani trovano più utile.»",
                "esercizio": "Rileggi le tue email commerciali: sostituisci le "
                             "negazioni e aggiungi un «perché» a ogni richiesta.",
            },
            {
                "id": "pnl-non-verbale",
                "titolo": "Comunicazione non verbale: miti e dati",
                "teoria": "Il dato più citato nei corsi di vendita — «il 7% "
                          "della comunicazione è verbale, il 38% è voce, il 55% "
                          "è corpo» — è un'interpretazione sbagliata degli "
                          "studi di Albert Mehrabian (1967), che riguardavano "
                          "singole parole pronunciate con tono incongruente per "
                          "esprimere simpatia o antipatia. Lo stesso Mehrabian ha "
                          "precisato che i numeri non valgono per la "
                          "comunicazione in generale. È vero invece che, quando "
                          "parole e segnali non verbali sono in contrasto, "
                          "tendiamo a credere ai secondi. Anche il «linguaggio "
                          "del corpo» come lettura del pensiero (braccia "
                          "incrociate = chiusura) è poco affidabile: un "
                          "singolo gesto può avere molte cause. Conta la "
                          "coerenza tra ciò che dici e come lo dici, e i "
                          "cambiamenti rispetto al comportamento abituale "
                          "dell'interlocutore.",
                "punti": [
                    "Cura la coerenza: dire il prezzo con sicurezza conta quanto il prezzo.",
                    "Osserva i cambiamenti (il cliente che si sporge, che prende la proposta in mano), non i singoli gesti.",
                    "Contatto visivo naturale, voce calma, pause: segnalano competenza.",
                    "Quando vedi un segnale incongruente, fai una domanda: «Mi sembra che questo punto la convinca poco, è così?»",
                ],
                "esempio": "Il cliente dice «interessante» ma si appoggia allo "
                           "schienale e guarda l'orologio. Invece di proseguire "
                           "con la presentazione, il consulente chiede: «Ho la "
                           "sensazione di averla annoiata con i dettagli. Cosa "
                           "le interessa capire davvero?»",
                "esercizio": "Registra un video di 2 minuti in cui presenti un "
                             "prezzo. Rivedilo senza audio: cosa comunica il tuo corpo?",
            },
        ],
        "quiz": [
            {
                "domanda": "Cosa dicono le revisioni scientifiche sui «sistemi rappresentazionali preferiti» (VAK) della PNL?",
                "opzioni": ["Sono stati confermati", "Non hanno trovato conferme", "Valgono solo nella vendita"],
                "corretta": 1,
                "spiegazione": "Sharpley (1987) e Witkowski (2010) non hanno trovato supporto empirico per queste tesi.",
            },
            {
                "domanda": "Quale strumento associato alla PNL è supportato da ricerche indipendenti?",
                "opzioni": ["La lettura dei movimenti oculari", "Il rispecchiamento sottile (effetto camaleonte)", "La regola 7-38-55"],
                "corretta": 1,
                "spiegazione": "Chartrand e Bargh (1999), van Baaren (2003) e Maddux (2008) mostrano effetti positivi dell'imitazione sottile.",
            },
            {
                "domanda": "«Le assicurazioni non pagano mai» è, secondo il metamodello, una…",
                "opzioni": ["Generalizzazione", "Presupposizione", "Chiusura alternativa"],
                "corretta": 0,
                "spiegazione": "Si recupera l'informazione con domande come «Mai? Le è capitato personalmente?»",
            },
            {
                "domanda": "La regola «7% parole, 38% voce, 55% corpo»…",
                "opzioni": ["Vale per ogni comunicazione",
                            "È un'estensione scorretta di esperimenti con messaggi incongruenti",
                            "È stata dimostrata nella vendita assicurativa"],
                "corretta": 1,
                "spiegazione": "Mehrabian stesso ha chiarito che i numeri non si applicano alla comunicazione in generale.",
            },
        ],
        "fonti": [
            "Richard Bandler e John Grinder, «La struttura della magia»",
            "Witkowski (2010), «Thirty-Five Years of Research on Neuro-Linguistic Programming», Polish Psychological Bulletin",
            "Chartrand e Bargh (1999), «The Chameleon Effect», Journal of Personality and Social Psychology",
            "Albert Mehrabian, «Silent Messages»",
        ],
    },
    {
        "id": "marketing",
        "area": "Accumulare clienti",
        "icona": "bi-megaphone",
        "titolo": "Marketing per il consulente assicurativo",
        "obiettivo": "Farsi trovare e riconoscere dai clienti giusti: "
                     "posizionamento, contenuti, eventi, presenza locale e "
                     "comunicazione al portafoglio, nel rispetto della privacy.",
        "lezioni": [
            {
                "id": "marketing-posizionamento",
                "titolo": "Posizionamento e proposta di valore",
                "teoria": "Il posizionamento è il posto che occupi nella mente "
                          "del cliente (Ries e Trout). «Consulente "
                          "assicurativo» non è un posizionamento: lo sono tutti. "
                          "«Il consulente che protegge gli studi medici dalla "
                          "responsabilità professionale e dal fermo dello "
                          "studio» lo è. Una proposta di valore chiara risponde "
                          "a tre domande: per chi lavori, quale problema "
                          "risolvi, perché tu e non un altro. La specializzazione "
                          "non riduce il mercato: rende più facile essere "
                          "ricordati e raccomandati.",
                "punti": [
                    "Formula: «Aiuto [chi] a [risultato] senza [problema tipico].»",
                    "Scegli la nicchia dove hai già clienti soddisfatti e storie vere.",
                    "Usa lo stesso messaggio ovunque: biglietto, sito, profilo LinkedIn, presentazione.",
                    "Verifica il posizionamento chiedendo ai clienti: «Perché ha scelto me?»",
                ],
                "esempio": "«Aiuto gli artigiani edili a lavorare tranquilli: "
                           "se si fanno male o rompono qualcosa in cantiere, "
                           "l'attività e la famiglia non si fermano.»",
                "esercizio": "Scrivi la tua proposta di valore in una frase e "
                             "provala su 5 clienti: la ricordano dopo una settimana?",
            },
            {
                "id": "marketing-contenuti",
                "titolo": "Content marketing, social e presenza locale",
                "teoria": "Il marketing dei contenuti consiste nel pubblicare "
                          "informazioni utili per il tuo pubblico, in modo che "
                          "ti riconosca come esperto prima ancora di incontrarti. "
                          "La psicologia sostiene due meccanismi: l'effetto "
                          "della semplice esposizione (Zajonc, 1968: ciò che "
                          "vediamo spesso ci diventa più familiare e gradito) e "
                          "la reciprocità. In un settore regolato come quello "
                          "assicurativo, i contenuti devono essere corretti e "
                          "non ingannevoli. La presenza locale conta: profilo "
                          "dell'attività su Google con recensioni reali, "
                          "partecipazione ad associazioni, articoli per la "
                          "stampa locale.",
                "punti": [
                    "Regola pratica: per ogni contenuto promozionale, almeno quattro utili (casi, guide, novità normative, errori da evitare).",
                    "Formati che funzionano: «3 errori che…», casi reali anonimi, domande dei clienti con risposta.",
                    "Costanza più che quantità: un post a settimana per un anno batte venti post in un mese.",
                    "Chiedi recensioni ai clienti soddisfatti, soprattutto dopo un sinistro gestito bene.",
                ],
                "esempio": "Serie di post per ristoratori: «Cosa succede se la "
                           "cappa prende fuoco di sabato sera?», «Il fermo "
                           "attività spiegato in 60 secondi», «Il caso di "
                           "Andrea: 40 giorni chiuso e nessun dipendente "
                           "licenziato».",
                "esercizio": "Prepara un calendario di 12 contenuti (uno a "
                             "settimana per tre mesi) per la tua nicchia.",
            },
            {
                "id": "marketing-eventi",
                "titolo": "Seminari, eventi e partnership",
                "teoria": "Un seminario di 45 minuti davanti a 20 imprenditori "
                          "dello stesso settore vale decine di telefonate: ti "
                          "presenta come esperto (autorità), crea riprova sociale "
                          "nel gruppo e genera appuntamenti con persone già "
                          "interessate. Funziona meglio se co-organizzato con un "
                          "partner che porta il pubblico (commercialista, "
                          "associazione di categoria, banca locale) e se il "
                          "tema è un problema concreto, non un prodotto.",
                "punti": [
                    "Tema: un problema e una novità («Nuovo obbligo CatNat: cosa rischia chi non si adegua»).",
                    "Struttura: problema → casi reali → cosa fare → domande. Niente listino.",
                    "Raccolta contatti con consenso e offerta di un check-up individuale gratuito.",
                    "Follow-up entro 48 ore a tutti i partecipanti.",
                ],
                "esempio": "Con il consulente del lavoro di zona: «Infortuni "
                           "dei dipendenti: cosa paga l'INAIL e cosa resta a "
                           "carico dell'azienda». 18 partecipanti, 7 check-up, "
                           "3 nuovi clienti.",
                "esercizio": "Progetta il tuo prossimo seminario: tema, partner, "
                             "data, scaletta, offerta finale e follow-up.",
            },
            {
                "id": "marketing-portafoglio-privacy",
                "titolo": "Comunicare al portafoglio nel rispetto della privacy",
                "teoria": "Il portafoglio è il pubblico più ricettivo che hai, "
                          "ma ogni comunicazione commerciale deve rispettare il "
                          "GDPR (Reg. UE 2016/679) e il Codice Privacy. Per il "
                          "marketing serve in generale un consenso specifico, "
                          "libero e documentato, distinto da quello per "
                          "l'esecuzione del contratto. Per le email ai clienti "
                          "già acquisiti il Codice Privacy (art. 130, comma 4) "
                          "consente il cosiddetto «soft spam» per prodotti "
                          "analoghi, a condizione di informare il cliente e "
                          "offrire sempre la possibilità di opporsi. Per le "
                          "telefonate commerciali va verificato il Registro "
                          "Pubblico delle Opposizioni, esteso dal 2022 anche ai "
                          "numeri mobili. Raccogli i consensi bene fin "
                          "dall'inizio: è un patrimonio dell'agenzia.",
                "punti": [
                    "Consenso marketing separato, facoltativo e registrato (data, modalità, testo dell'informativa).",
                    "Ogni email commerciale contiene un modo semplice per non riceverne più.",
                    "Newsletter utile: scadenze normative, consigli stagionali (grandine, viaggi, neve), casi reali.",
                    "Segmenta le comunicazioni con il gestionale (tipo cliente, rami posseduti, scoperti).",
                ],
                "esempio": "A maggio, newsletter ai clienti con casa assicurata: "
                           "«Grandine e temporali: cosa copre la sua polizza e "
                           "cosa no». Chi ha solo l'incendio riceve l'invito a "
                           "una verifica degli eventi atmosferici.",
                "esercizio": "Verifica quanti clienti del tuo portafoglio hanno "
                             "un consenso marketing registrato e prepara un "
                             "piano per raccoglierlo alla prossima occasione di contatto.",
            },
        ],
        "quiz": [
            {
                "domanda": "Quale frase è un posizionamento efficace?",
                "opzioni": ["«Consulente assicurativo con esperienza»",
                            "«Aiuto gli studi medici a proteggersi da richieste di risarcimento e fermo dello studio»",
                            "«Le migliori polizze al miglior prezzo»"],
                "corretta": 1,
                "spiegazione": "Dice per chi lavori, quale problema risolvi e ti rende facile da ricordare.",
            },
            {
                "domanda": "Per inviare email commerciali ai propri clienti su prodotti analoghi…",
                "opzioni": ["Non serve nulla", "È possibile informando il cliente e offrendo sempre l'opposizione (art. 130 c.4 Codice Privacy)", "Serve l'autorizzazione dell'IVASS"],
                "corretta": 1,
                "spiegazione": "È il cosiddetto soft spam; per altri canali e prodotti serve il consenso specifico.",
            },
            {
                "domanda": "Qual è il tema migliore per un seminario?",
                "opzioni": ["La presentazione del nuovo prodotto della compagnia",
                            "Un problema concreto del pubblico, con casi reali",
                            "La storia della propria agenzia"],
                "corretta": 1,
                "spiegazione": "Le persone partecipano per risolvere un problema, non per ascoltare un listino.",
            },
        ],
        "fonti": [
            "Al Ries e Jack Trout, «Positioning»",
            "Philip Kotler, «Marketing Management»",
            "Reg. UE 2016/679 (GDPR) e D.Lgs. 196/2003 (Codice Privacy), art. 130",
            "Zajonc (1968), «Attitudinal effects of mere exposure»",
        ],
    },
    {
        "id": "informazioni",
        "area": "Trattativa",
        "icona": "bi-clipboard-data",
        "titolo": "Informazioni da prendere e da dare",
        "obiettivo": "Sapere esattamente cosa chiedere al cliente per una "
                     "consulenza completa e cosa consegnargli per legge e per "
                     "fiducia, trasformando gli obblighi in strumenti commerciali.",
        "lezioni": [
            {
                "id": "informazioni-prendere-privati",
                "titolo": "Cosa chiedere a un cliente privato",
                "teoria": "Una consulenza completa su una persona copre cinque "
                          "aree: persona e famiglia (età, stato civile, figli, "
                          "persone a carico), lavoro e reddito (tipo di "
                          "contratto, reddito, stabilità, coperture del datore "
                          "di lavoro e degli enti pubblici), patrimonio e "
                          "impegni (casa, mutuo, prestiti, veicoli, animali), "
                          "coperture esistenti (cosa, con chi, scadenze, "
                          "esperienze di sinistro) e obiettivi (cosa vuole "
                          "proteggere, per chi, con quale budget). Le "
                          "informazioni economiche si chiedono dopo aver "
                          "creato fiducia, spiegando perché servono.",
                "punti": [
                    "Inizia dalle persone, non dai beni: «Mi parla della sua famiglia?»",
                    "Chiedi le cifre con una motivazione: «Mi serve per capire quanto le servirebbe se si fermasse.»",
                    "Chiedi sempre di vedere le polizze esistenti: le persone ricordano male cosa hanno.",
                    "Chiudi con la domanda più importante: «Cosa la preoccupa di più per il futuro?»",
                ],
                "esempio": "«Per darle un consiglio serio ho bisogno di farle "
                           "alcune domande anche personali, come farebbe un "
                           "medico prima di prescrivere qualcosa. Restano tra "
                           "noi e sono protette dalla privacy. Possiamo partire "
                           "dalla sua famiglia?»",
                "esercizio": "Usa la scheda stampabile «Raccolta informazioni — "
                             "privato» nel prossimo appuntamento e annota quali "
                             "domande sono state più difficili da porre.",
            },
            {
                "id": "informazioni-prendere-aziende",
                "titolo": "Cosa chiedere a un'azienda o a un professionista",
                "teoria": "Per un'impresa l'analisi parte dal modo in cui crea "
                          "valore: cosa fa, per chi, con quali persone, beni e "
                          "processi, e da cosa dipende. Le domande chiave: quali "
                          "sono i beni e le sedi; chi sono le persone "
                          "indispensabili; quanto dipende da pochi clienti o "
                          "fornitori; quali contratti impongono coperture "
                          "(appalti, capitolati, leasing); quali dati gestisce; "
                          "dove lavora (cantieri, export); quali sinistri ha "
                          "avuto; quali obblighi di legge ha (es. RC "
                          "professionale obbligatoria per molte professioni, "
                          "copertura catastrofale per le imprese). Infine: quali "
                          "rischi teme il titolare. L'analisi automatica dei "
                          "rischi del gestionale parte dalla descrizione "
                          "dell'attività: più è ricca, migliore è l'analisi.",
                "punti": [
                    "Fatti raccontare una giornata o un ordine tipico, dall'arrivo al pagamento.",
                    "Chiedi: «Se domani si fermasse per un mese, cosa succederebbe?»",
                    "Chiedi i contratti con i clienti principali: spesso contengono obblighi assicurativi.",
                    "Visita la sede: ciò che vedi (macchinari, magazzino, server) vale più di ciò che senti.",
                ],
                "esempio": "Visitando un'officina il consulente nota un "
                           "compressore vicino a materiale infiammabile e un "
                           "server sotto la scrivania: due spunti (incendio, "
                           "cyber) che il titolare non aveva menzionato.",
                "esercizio": "Compila la scheda «Raccolta informazioni — "
                             "azienda» per un cliente esistente e inserisci la "
                             "descrizione completa nel gestionale per rilanciare l'analisi.",
            },
            {
                "id": "informazioni-dare",
                "titolo": "Cosa dare al cliente: obblighi e opportunità",
                "teoria": "La normativa sulla distribuzione assicurativa "
                          "(Direttiva IDD, Codice delle Assicurazioni Private, "
                          "Regolamento IVASS n. 40/2018) prevede che prima della "
                          "sottoscrizione il cliente riceva informazioni sul "
                          "distributore (identità, iscrizione al Registro Unico "
                          "degli Intermediari, conflitti di interesse, natura "
                          "della remunerazione) e sul prodotto (Documento "
                          "Informativo Precontrattuale, DIP, e condizioni di "
                          "assicurazione), e che il contratto proposto sia "
                          "coerente con le sue richieste ed esigenze. Gli "
                          "allegati del Regolamento IVASS 40/2018 (in "
                          "particolare 3, 4 e 4-ter) definiscono i modelli. "
                          "Verifica sempre le versioni vigenti e le procedure "
                          "della tua compagnia o del tuo intermediario. Oltre "
                          "agli obblighi, dai valore: una sintesi chiara di "
                          "cosa è coperto e cosa no, cosa fare in caso di "
                          "sinistro, i tuoi contatti diretti.",
                "punti": [
                    "Prima della firma: informativa sul distributore, informativa sulla distribuzione del prodotto, DIP, condizioni, informativa privacy.",
                    "Valutazione di coerenza documentata con le richieste ed esigenze del cliente.",
                    "Spiega a voce le esclusioni principali: è la prova di trasparenza che il cliente ricorderà.",
                    "Dopo la firma: copia del contratto, istruzioni per il sinistro, scadenze, contatti diretti.",
                ],
                "esempio": "«Prima di firmare le consegno questi documenti, che "
                           "la legge prevede per tutelarla. Le evidenzio io le "
                           "tre esclusioni più importanti, così non avrà "
                           "sorprese. Questa è invece la mia scheda: cosa fare "
                           "in caso di sinistro e il mio numero diretto.»",
                "esercizio": "Prepara un kit di consegna standard (cartellina o "
                             "PDF) con documenti obbligatori, sintesi delle "
                             "coperture e istruzioni per il sinistro.",
            },
        ],
        "quiz": [
            {
                "domanda": "Quando conviene chiedere le informazioni economiche al cliente?",
                "opzioni": ["Subito, per qualificarlo",
                            "Dopo aver creato fiducia, spiegando perché servono",
                            "Mai, sono troppo personali"],
                "corretta": 1,
                "spiegazione": "Motivare la richiesta e farla dopo aver creato fiducia riduce le resistenze.",
            },
            {
                "domanda": "Perché chiedere i contratti dei clienti principali di un'azienda?",
                "opzioni": ["Per conoscere i prezzi dell'azienda", "Perché spesso contengono obblighi assicurativi", "Non serve"],
                "corretta": 1,
                "spiegazione": "Appalti e capitolati impongono spesso coperture e massimali minimi.",
            },
            {
                "domanda": "Cosa deve ricevere il cliente prima della sottoscrizione?",
                "opzioni": ["Solo il preventivo",
                            "Informazioni sul distributore e sul prodotto (es. DIP) e una proposta coerente con le sue esigenze",
                            "Un regalo promozionale"],
                "corretta": 1,
                "spiegazione": "Sono obblighi previsti da IDD, Codice delle Assicurazioni e regolamenti IVASS.",
            },
        ],
        "fonti": [
            "Direttiva (UE) 2016/97 (IDD)",
            "D.Lgs. 209/2005, Codice delle Assicurazioni Private",
            "Regolamento IVASS n. 40/2018 e Regolamento IVASS n. 41/2018 (DIP)",
        ],
    },
]

# Ordine del percorso: un modulo a settimana.
ORDINE_MODULI = [
    "mindset", "psicologia", "pnl", "prospezione", "marketing", "apertura",
    "informazioni", "domande", "laterale", "proposta", "obiezioni",
    "negoziazione", "chiusura", "continuita", "portafoglio", "crescita",
]

# ----------------------------------------------------------------------
# Base scientifica: per ogni modulo, cosa dice la ricerca e quanto è solida.
# Livelli: "solida" (molti studi convergenti), "moderata" (studi a favore con
# limiti), "limitata" (pratica professionale diffusa ma poco studiata),
# "non supportata" (le verifiche disponibili non la confermano).
# ----------------------------------------------------------------------
LIVELLI_EVIDENZA = {
    "solida": ("Evidenza solida", "success"),
    "moderata": ("Evidenza moderata", "primary"),
    "limitata": ("Pratica professionale", "secondary"),
    "non supportata": ("Non supportata", "danger"),
}

EVIDENZE = {
    "mindset": [
        {"tesi": "Le attività misurabili (contatti, appuntamenti) predicono i risultati meglio degli obiettivi di sola intenzione; fissare obiettivi specifici e impegnativi migliora la prestazione.",
         "livello": "solida", "fonte": "Locke e Latham, teoria del goal-setting (1990, 2002)"},
        {"tesi": "I venditori che vivono il rifiuto come informazione e non come giudizio personale (stile esplicativo ottimista) vendono di più e abbandonano meno.",
         "livello": "moderata", "fonte": "Seligman e Schulman (1986), studio sugli agenti assicurativi vita di MetLife"},
        {"tesi": "Il cliente deve parlare più del consulente: i dati di settore sulle trattative concluse indicano un rapporto parlato/ascoltato vicino a 45/55.",
         "livello": "limitata", "fonte": "Analisi di registrazioni di vendita (dati aziendali, non peer-reviewed)"},
    ],
    "psicologia": [
        {"tesi": "Avversione alla perdita, effetto cornice e ancoraggio influenzano le scelte economiche.",
         "livello": "solida", "fonte": "Kahneman e Tversky (1979, 1981); Tversky e Kahneman (1974)"},
        {"tesi": "Le opzioni di default aumentano fortemente l'adesione (es. piani pensionistici).",
         "livello": "solida", "fonte": "Madrian e Shea (2001); Johnson e Goldstein (2003)"},
        {"tesi": "I principi di Cialdini aumentano l'accettazione delle richieste.",
         "livello": "moderata", "fonte": "Cialdini, sintesi di esperimenti di psicologia sociale; alcuni effetti singoli hanno avuto repliche deboli"},
        {"tesi": "Troppe opzioni riducono sempre gli acquisti.",
         "livello": "non supportata", "fonte": "Meta-analisi Scheibehenne, Greifeneder e Todd (2010): effetto medio vicino a zero, dipende dal contesto"},
    ],
    "pnl": [
        {"tesi": "L'imitazione sottile di linguaggio e postura aumenta simpatia e accordi.",
         "livello": "solida", "fonte": "Chartrand e Bargh (1999); van Baaren e colleghi (2003); Maddux, Mullen e Galinsky (2008)"},
        {"tesi": "Domande di approfondimento e ascolto di qualità aumentano simpatia e apertura.",
         "livello": "moderata", "fonte": "Huang e colleghi (2017); Itzchakov e Kluger, ricerche sull'ascolto"},
        {"tesi": "Esistono sistemi rappresentazionali preferiti (visivo, auditivo, cinestesico) da individuare e ricalcare.",
         "livello": "non supportata", "fonte": "Sharpley (1987); Witkowski (2010); vedi anche il mito degli «stili di apprendimento», Pashler e colleghi (2008)"},
        {"tesi": "I movimenti oculari rivelano se una persona mente.",
         "livello": "non supportata", "fonte": "Wiseman e colleghi (2012), PLoS ONE"},
        {"tesi": "Il 93% della comunicazione è non verbale (regola 7-38-55).",
         "livello": "non supportata", "fonte": "Mehrabian (1967) e le sue precisazioni successive"},
    ],
    "prospezione": [
        {"tesi": "I clienti acquisiti tramite referenza sono più redditizi e più fedeli di quelli acquisiti con altri canali.",
         "livello": "moderata", "fonte": "Schmitt, Skiera e Van den Bulte (2011), Journal of Marketing (studio su una banca)"},
        {"tesi": "La fiducia si trasferisce attraverso le reti di relazione: la presentazione di una persona nota aumenta la risposta.",
         "livello": "moderata", "fonte": "Ricerche sul passaparola e sui legami sociali (Granovetter, 1973; Brown e Reingen, 1987)"},
        {"tesi": "Specializzarsi in una nicchia migliora l'efficacia commerciale.",
         "livello": "limitata", "fonte": "Pratica professionale diffusa; coerente con la letteratura sul posizionamento"},
    ],
    "marketing": [
        {"tesi": "L'esposizione ripetuta aumenta familiarità e gradimento.",
         "livello": "solida", "fonte": "Zajonc (1968); meta-analisi Bornstein (1989)"},
        {"tesi": "Le recensioni e la riprova sociale influenzano la scelta di servizi professionali.",
         "livello": "moderata", "fonte": "Studi sulle recensioni online (es. Chevalier e Mayzlin, 2006)"},
        {"tesi": "Il content marketing genera contatti a costo inferiore rispetto alla pubblicità tradizionale.",
         "livello": "limitata", "fonte": "Dati di settore e indagini di associazioni di marketing"},
    ],
    "apertura": [
        {"tesi": "Le prime impressioni di calore e competenza si formano in pochi secondi e influenzano il giudizio successivo.",
         "livello": "solida", "fonte": "Willis e Todorov (2006); Fiske, Cuddy e Glick (2007), modello calore-competenza"},
        {"tesi": "Dare una ragione aumenta l'accettazione di una richiesta.",
         "livello": "moderata", "fonte": "Langer, Blank e Chanowitz (1978)"},
        {"tesi": "L'accordo iniziale esplicito (up-front contract) riduce i rinvii indefiniti.",
         "livello": "limitata", "fonte": "Metodo Sandler, pratica professionale"},
    ],
    "informazioni": [
        {"tesi": "Gli obblighi informativi e la valutazione di coerenza sono richiesti dalla normativa.",
         "livello": "solida", "fonte": "Direttiva IDD, Codice delle Assicurazioni Private, Regolamenti IVASS 40 e 41/2018"},
        {"tesi": "La trasparenza su limiti ed esclusioni aumenta la fiducia nel consulente.",
         "livello": "moderata", "fonte": "Ricerche sulla fiducia nei servizi finanziari e sull'ammissione dei limiti (two-sided messages, Eisend 2006)"},
    ],
    "domande": [
        {"tesi": "Nelle vendite complesse, i venditori migliori fanno più domande di problema e implicazione.",
         "livello": "moderata", "fonte": "Rackham, ricerca Huthwaite su oltre 35.000 colloqui di vendita (pubblicata come libro, non peer-reviewed)"},
        {"tesi": "Fare domande di approfondimento aumenta la simpatia percepita.",
         "livello": "solida", "fonte": "Huang, Yeomans, Brooks, Minson e Gino (2017), Journal of Personality and Social Psychology"},
        {"tesi": "L'ascolto di qualità riduce la difensività e favorisce un pensiero più articolato.",
         "livello": "moderata", "fonte": "Itzchakov, Kluger e colleghi (2017-2020)"},
    ],
    "laterale": [
        {"tesi": "Una storia con una singola persona identificabile coinvolge più delle statistiche.",
         "livello": "solida", "fonte": "Effetto vittima identificabile: Small, Loewenstein e Slovic (2007)"},
        {"tesi": "Il «trasporto narrativo» modifica atteggiamenti e credenze.",
         "livello": "solida", "fonte": "Green e Brock (2000); meta-analisi van Laer e colleghi (2014)"},
        {"tesi": "Gli strumenti di de Bono (sei cappelli, provocazione) migliorano la generazione di idee.",
         "livello": "limitata", "fonte": "Diffusi nella formazione; pochi studi controllati"},
    ],
    "proposta": [
        {"tesi": "L'ancoraggio della prima cifra influenza le valutazioni successive.",
         "livello": "solida", "fonte": "Tversky e Kahneman (1974); Furnham e Boo (2011), revisione"},
        {"tesi": "L'opzione centrale e l'opzione esca orientano la scelta.",
         "livello": "moderata", "fonte": "Simonson (1989); Huber, Payne e Puto (1982); repliche non sempre forti per l'effetto esca"},
        {"tesi": "Parlare di benefici per il cliente convince più delle caratteristiche tecniche.",
         "livello": "limitata", "fonte": "Pratica professionale; coerente con le ricerche sulla rilevanza personale (Petty e Cacioppo, modello ELM)"},
    ],
    "obiezioni": [
        {"tesi": "Riconoscere il punto di vista dell'altro prima di rispondere riduce la reattività.",
         "livello": "moderata", "fonte": "Teoria della reattanza (Brehm, 1966); ricerche sull'ascolto"},
        {"tesi": "Un messaggio che ammette un limite e lo compensa (two-sided) è più credibile.",
         "livello": "moderata", "fonte": "Meta-analisi Eisend (2006)"},
        {"tesi": "Tecniche specifiche come Feel-Felt-Found o boomerang hanno efficacia dimostrata.",
         "livello": "limitata", "fonte": "Pratica professionale, poco studiata in modo controllato"},
    ],
    "negoziazione": [
        {"tesi": "Chi fa la prima offerta tende a ottenere risultati migliori grazie all'ancoraggio; offerte precise ancorano più di quelle tonde.",
         "livello": "solida", "fonte": "Galinsky e Mussweiler (2001); Mason e colleghi (2013)"},
        {"tesi": "Cercare gli interessi dietro le posizioni genera accordi integrativi di maggior valore.",
         "livello": "solida", "fonte": "Fisher e Ury; ricerche sulla negoziazione integrativa (Thompson, 1991)"},
        {"tesi": "Le tecniche di Voss (etichettatura, rispecchiamento) migliorano la negoziazione.",
         "livello": "moderata", "fonte": "Coerenti con studi su mimicry e affect labeling (Lieberman e colleghi, 2007); poco studiate nella forma proposta"},
    ],
    "chiusura": [
        {"tesi": "La tecnica del piede nella porta (piccolo impegno prima di uno più grande) aumenta l'adesione.",
         "livello": "moderata", "fonte": "Freedman e Fraser (1966); meta-analisi con effetti piccoli ma consistenti"},
        {"tesi": "La pressione percepita sulla libertà di scelta produce resistenza; ricordare «è libero di dire no» aumenta l'adesione.",
         "livello": "solida", "fonte": "Reattanza (Brehm); meta-analisi «But You Are Free», Carpenter (2013)"},
        {"tesi": "Le singole tecniche di chiusura classiche sono superiori alle altre.",
         "livello": "limitata", "fonte": "Rackham osserva che nelle vendite complesse l'uso eccessivo di tecniche di chiusura riduce il successo"},
    ],
    "continuita": [
        {"tesi": "Piani del tipo «quando/se… allora…» con data e luogo aumentano molto la probabilità di eseguire un'azione.",
         "livello": "solida", "fonte": "Intenzioni di implementazione, Gollwitzer (1999); meta-analisi Gollwitzer e Sheeran (2006)"},
        {"tesi": "Si ricordano soprattutto il momento più intenso e la fine di un'esperienza.",
         "livello": "moderata", "fonte": "Regola del picco e della fine, Kahneman e colleghi (1993)"},
        {"tesi": "Cadenze di follow-up specifiche (2 giorni, 1 settimana…) sono ottimali.",
         "livello": "limitata", "fonte": "Pratica professionale; adatta la cadenza al cliente"},
    ],
    "portafoglio": [
        {"tesi": "Piccoli aumenti nel tasso di fidelizzazione producono forti aumenti di redditività.",
         "livello": "moderata", "fonte": "Reichheld e Sasser (1990), Harvard Business Review"},
        {"tesi": "Il valore del cliente nel tempo (CLV) è una base migliore della singola vendita per allocare tempo e risorse.",
         "livello": "solida", "fonte": "Letteratura di marketing sul customer lifetime value (Gupta e colleghi, 2006)"},
        {"tesi": "Il Net Promoter Score predice la crescita meglio di altre misure di soddisfazione.",
         "livello": "non supportata", "fonte": "Keiningham e colleghi (2007): non superiore ad altre misure; resta utile come indicatore semplice"},
    ],
    "crescita": [
        {"tesi": "La pratica deliberata migliora le prestazioni, ma spiega solo una parte delle differenze tra professionisti.",
         "livello": "moderata", "fonte": "Ericsson e colleghi (1993); meta-analisi Macnamara, Hambrick e Oswald (2014)"},
        {"tesi": "Il feedback specifico e tempestivo migliora l'apprendimento delle abilità.",
         "livello": "solida", "fonte": "Hattie e Timperley (2007); Kluger e DeNisi (1996), con avvertenza: il feedback sulla persona e non sul compito può peggiorare la prestazione"},
        {"tesi": "Il time blocking aumenta la produttività commerciale.",
         "livello": "limitata", "fonte": "Pratica professionale; coerente con la ricerca sui costi del multitasking (Rubinstein, Meyer e Evans, 2001)"},
    ],
}

# ----------------------------------------------------------------------
# Libreria delle obiezioni più frequenti
# ----------------------------------------------------------------------
CATEGORIE_OBIEZIONI = [
    ("prezzo", "Prezzo"),
    ("tempo", "Tempo e rinvio"),
    ("fiducia", "Fiducia"),
    ("bisogno", "Bisogno"),
    ("concorrenza", "Concorrenza"),
]
CATEGORIE_OBIEZIONI_LABELS = dict(CATEGORIE_OBIEZIONI)

OBIEZIONI = [
    {
        "id": "caro",
        "categoria": "prezzo",
        "obiezione": "È troppo caro.",
        "cosa_nasconde": "Il valore percepito è inferiore al prezzo, oppure c'è un vincolo di budget reale, oppure un confronto con un'offerta più bassa.",
        "tecnica": "ACER + domanda di ritorno",
        "risposta": "«Capisco, è giusto valutarlo bene. Caro rispetto a cosa: a un'altra offerta, a quanto aveva previsto o a quello che le offre la polizza?»",
        "rilancio": "«Se trovassimo il modo di farlo rientrare nel suo budget, sarebbe la soluzione giusta per lei?»",
        "laterale": "Spacchetta il prezzo al giorno e confrontalo con il costo del danno, non con zero: «Sono 1,60 € al giorno per non rischiare 200.000 €.»",
    },
    {
        "id": "budget",
        "categoria": "prezzo",
        "obiezione": "Adesso non ho budget.",
        "cosa_nasconde": "Problema di liquidità reale oppure priorità non percepita.",
        "tecnica": "Interessi, non posizioni (metodo Harvard)",
        "risposta": "«La capisco, è un periodo in cui le uscite vanno controllate. È un problema di importo totale o di quando si paga?»",
        "rilancio": "«Se potessimo partire con un frazionamento mensile e la prima rata il mese prossimo, cambierebbe qualcosa?»",
        "laterale": "Proponi di partire dalla copertura essenziale sul rischio più grave e di integrarla al rinnovo: meglio protetto sul rischio principale che scoperto su tutto.",
    },
    {
        "id": "online",
        "categoria": "concorrenza",
        "obiezione": "Online la trovo a meno.",
        "cosa_nasconde": "Il cliente confronta il prezzo senza confrontare garanzie, esclusioni e servizio.",
        "tecnica": "Compensazione + confronto su criteri oggettivi",
        "risposta": "«È possibile, e fa bene a confrontare. Le propongo di metterle una accanto all'altra: massimali, franchigie, esclusioni. Se l'altra è uguale e costa meno, glielo dico io di prenderla.»",
        "rilancio": "«Quando avrà un sinistro, preferisce parlare con un call center o con me?»",
        "laterale": "Racconta il caso (vero) di un cliente che ha risparmiato 80 € e scoperto al sinistro una franchigia di 5.000 €.",
    },
    {
        "id": "pensarci",
        "categoria": "tempo",
        "obiezione": "Ci devo pensare.",
        "cosa_nasconde": "Un dubbio non espresso (prezzo, condizioni, fiducia) o la difficoltà a dire no.",
        "tecnica": "Domanda di ritorno + prossimo passo con data",
        "risposta": "«Certo, è una decisione importante. Di solito quando mi dicono così c'è un dubbio sul prezzo, sulle condizioni o su di me. Su cosa vuole riflettere?»",
        "rilancio": "«Le bastano tre giorni? La richiamo venerdì alle 11 così chiariamo eventuali dubbi.»",
        "laterale": "Domanda orientata al no (Voss): «Sarebbe sbagliato prendere una decisione, anche negativa, entro venerdì?»",
    },
    {
        "id": "moglie",
        "categoria": "tempo",
        "obiezione": "Devo parlarne con mia moglie / con il socio.",
        "cosa_nasconde": "Un decisore assente oppure il bisogno di condividere la responsabilità della scelta.",
        "tecnica": "Coinvolgimento del decisore",
        "risposta": "«Giustissimo, è una decisione che riguarda anche lei. Cosa pensa che le chiederà? Così la preparo a rispondere.»",
        "rilancio": "«Ha senso vederci insieme mezz'ora, così può fare le domande direttamente a me? Martedì sera o sabato mattina?»",
        "laterale": "Nelle polizze vita e infortuni il beneficiario è spesso proprio il coniuge: proponi l'incontro a due come la cosa più naturale.",
    },
    {
        "id": "non-momento",
        "categoria": "tempo",
        "obiezione": "Non è il momento, ci risentiamo più avanti.",
        "cosa_nasconde": "Priorità bassa percepita o desiderio di chiudere la conversazione.",
        "tecnica": "Esplorazione + permesso di ricontatto",
        "risposta": "«Va benissimo. Mi aiuta a capire cosa dovrebbe cambiare perché diventi il momento giusto?»",
        "rilancio": "«Mi segno di richiamarla a marzo: va bene la prima settimana?»",
        "laterale": "Il rischio non aspetta il momento giusto: chiedi «Se succedesse prima di marzo, come lo affronterebbe?»",
    },
    {
        "id": "gia-assicurato",
        "categoria": "concorrenza",
        "obiezione": "Sono già assicurato.",
        "cosa_nasconde": "Il cliente crede di essere coperto ma spesso non conosce le condizioni.",
        "tecnica": "Feel-Felt-Found + check-up gratuito",
        "risposta": "«Ottimo, vuol dire che il tema le sta a cuore. Molti miei clienti pensavano lo stesso; poi, rileggendo le condizioni insieme, hanno scoperto un paio di buchi che nessuno aveva spiegato.»",
        "rilancio": "«Le va se diamo un'occhiata alla polizza attuale? Se è perfetta, glielo dirò io.»",
        "laterale": "Proponi il check-up come un secondo parere medico: non sostituisce, verifica.",
    },
    {
        "id": "agente-amico",
        "categoria": "fiducia",
        "obiezione": "Ho un agente di fiducia, è un amico.",
        "cosa_nasconde": "Lealtà personale; la relazione conta più della polizza.",
        "tecnica": "Rispetto della relazione + compensazione",
        "risposta": "«La rispetto molto per questo: la fedeltà è una qualità rara. Non le chiedo di cambiare agente, le offro un secondo sguardo su un rischio specifico.»",
        "rilancio": "«C'è un'area, magari la sua attività o la previdenza, che il suo amico non segue direttamente?»",
        "laterale": "Lavora su un ramo non presidiato dall'amico (es. cyber, D&O, previdenza): la relazione si costruisce lì.",
    },
    {
        "id": "non-pagano",
        "categoria": "fiducia",
        "obiezione": "Tanto le assicurazioni non pagano mai.",
        "cosa_nasconde": "Un'esperienza negativa (propria o di conoscenti) o un pregiudizio diffuso.",
        "tecnica": "Etichettatura (Voss) + prova concreta",
        "risposta": "«Sembra che abbia avuto una brutta esperienza. Mi racconta cosa è successo?»",
        "rilancio": "«Se le facessi vedere esattamente cosa è escluso e come si gestisce un sinistro con me, le toglierebbe questo dubbio?»",
        "laterale": "Ribalta: le polizze che «non pagano» sono quelle non spiegate. Mostra le esclusioni prima del prezzo: la trasparenza crea fiducia.",
    },
    {
        "id": "non-capita",
        "categoria": "bisogno",
        "obiezione": "A me non capiterà.",
        "cosa_nasconde": "Ottimismo irrealistico: il rischio è percepito come astratto.",
        "tecnica": "Storytelling in terza persona + domande di implicazione",
        "risposta": "«Me lo auguro davvero. Anche il cliente di cui le racconto lo pensava: idraulico, 42 anni, mai un giorno di malattia…»",
        "rilancio": "«Se invece capitasse, chi pagherebbe le sue spese nei mesi di fermo?»",
        "laterale": "«Lei assicura l'auto anche se non pensa di fare un incidente: perché? Perché non potrebbe permettersi il danno. Qui è uguale.»",
    },
    {
        "id": "giovane",
        "categoria": "bisogno",
        "obiezione": "Sono giovane, ci penserò più avanti.",
        "cosa_nasconde": "Il bisogno è percepito come lontano nel tempo.",
        "tecnica": "Boomerang",
        "risposta": "«Proprio perché è giovane è il momento migliore: paga il premio più basso, non ha esclusioni per patologie e ha più tempo per far crescere la previdenza.»",
        "rilancio": "«Partire con 50 € al mese oggi o con 150 € tra dieci anni: quale preferisce?»",
        "laterale": "Mostra il costo dell'attesa: il premio di una temporanea caso morte o la rendita di un PIP cambiano molto con l'età di ingresso.",
    },
    {
        "id": "inps",
        "categoria": "bisogno",
        "obiezione": "C'è già l'INPS / l'INAIL / il Servizio Sanitario.",
        "cosa_nasconde": "Sopravvalutazione delle coperture pubbliche.",
        "tecnica": "Domande di implicazione + dati oggettivi",
        "risposta": "«È vero, e per fortuna esistono. Sa quanto le riconoscerebbero, e in quanto tempo, se si fermasse sei mesi?»",
        "rilancio": "«Se la differenza tra il suo reddito e l'indennità pubblica fosse scoperta, come la colmerebbe?»",
        "laterale": "Il pubblico è il pavimento, non il tetto: la polizza copre il divario tra ciò che arriva e ciò che serve.",
    },
    {
        "id": "mandi-email",
        "categoria": "tempo",
        "obiezione": "Mi mandi tutto via email.",
        "cosa_nasconde": "Un modo cortese per chiudere la conversazione o un reale bisogno di leggere con calma.",
        "tecnica": "Accordo + prossimo passo",
        "risposta": "«Volentieri. Perché le sia davvero utile, mi dice quali sono i due aspetti che vuole approfondire?»",
        "rilancio": "«Gliela invio oggi; ci sentiamo giovedì 10 minuti per le domande, alle 9 o alle 17?»",
        "laterale": "Un documento senza spiegazione è un preventivo da confrontare sul prezzo: proponi una videochiamata breve per presentarlo.",
    },
    {
        "id": "sconto",
        "categoria": "prezzo",
        "obiezione": "Mi fa uno sconto?",
        "cosa_nasconde": "Abitudine negoziale, desiderio di sentirsi trattato bene, a volte un test di serietà.",
        "tecnica": "Concessione condizionata",
        "risposta": "«Il prezzo è quello corretto per queste garanzie. Posso lavorare su qualcosa solo se cambiamo qualcosa anche noi: per esempio il pagamento annuale o l'accorpamento con la polizza del furgone.»",
        "rilancio": "«Se trovassimo questa soluzione, procediamo oggi?»",
        "laterale": "Offri valore invece di sconto: revisione semestrale, gestione personale dei sinistri, check-up coperture per la famiglia.",
    },
    {
        "id": "brutta-esperienza",
        "categoria": "fiducia",
        "obiezione": "Un vostro collega mi ha già fregato.",
        "cosa_nasconde": "Ferita di fiducia verso l'intera categoria.",
        "tecnica": "Ascolto attivo + accordo iniziale trasparente",
        "risposta": "«Mi dispiace, e la capisco se è diffidente. Mi racconta cosa è successo? Vorrei evitare di ripetere lo stesso errore.»",
        "rilancio": "«Le propongo questo: le mostro per iscritto cosa copre e cosa no, e decide lei con calma. Va bene?»",
        "laterale": "Trasforma la brutta esperienza nella tua specifica: «Quello che è successo a lei è il motivo per cui spiego sempre le esclusioni prima del prezzo.»",
    },
    {
        "id": "non-tempo",
        "categoria": "tempo",
        "obiezione": "Non ho tempo per queste cose.",
        "cosa_nasconde": "Priorità bassa percepita: il rischio non sembra urgente quanto il lavoro di oggi.",
        "tecnica": "Accordo iniziale breve + domanda di implicazione",
        "risposta": "«La capisco, il suo tempo vale. Le chiedo 10 minuti, cronometrati: se dopo non vede utilità, ci salutiamo.»",
        "rilancio": "«Se un infortunio la fermasse tre mesi, quanto tempo avrebbe allora per occuparsi del lavoro?»",
        "laterale": "Ribalta la cornice: proprio chi non ha tempo non può permettersi di gestire da solo un sinistro o un fermo.",
    },
]

# ----------------------------------------------------------------------
# Cassetta degli attrezzi: metodi e tecniche documentati
# ----------------------------------------------------------------------
TECNICHE = [
    {"nome": "SPIN Selling", "fonte": "Neil Rackham", "fase": "Analisi dei bisogni",
     "quando": "Vendite complesse, aziende e professionisti.",
     "come": "Domande di Situazione, Problema, Implicazione, Need-payoff in sequenza.", "modulo": "domande"},
    {"nome": "Up-front contract", "fonte": "David Sandler", "fase": "Apertura",
     "quando": "All'inizio di ogni incontro.",
     "come": "Concorda tempo, scopo, ruoli ed esiti possibili, incluso il «no».", "modulo": "apertura"},
    {"nome": "5 perché", "fonte": "Toyota Production System", "fase": "Analisi dei bisogni",
     "quando": "Quando il cliente esprime un'esigenza di superficie.",
     "come": "Chiedi «perché è importante?» più volte fino alla motivazione profonda.", "modulo": "domande"},
    {"nome": "Ascolto attivo e riformulazione", "fonte": "Carl Rogers", "fase": "Tutte",
     "quando": "Sempre, soprattutto dopo informazioni importanti.",
     "come": "Riformula con parole tue, riassumi, chiedi conferma.", "modulo": "domande"},
    {"nome": "Sei cappelli per pensare", "fonte": "Edward de Bono", "fase": "Pensiero laterale",
     "quando": "Trattative bloccate, decisioni con più decisori.",
     "come": "Esamina la decisione da sei prospettive: fatti, emozioni, rischi, benefici, idee, processo.", "modulo": "laterale"},
    {"nome": "Reframing", "fonte": "Programmazione neurolinguistica, Kahneman (framing)", "fase": "Proposta e obiezioni",
     "quando": "Quando il cliente guarda il premio come puro costo.",
     "come": "Cambia la cornice: costo del non fare, costo giornaliero, confronto con beni assicurati.", "modulo": "laterale"},
    {"nome": "Storytelling", "fonte": "Chip e Dan Heath, «Made to Stick»", "fase": "Proposta",
     "quando": "Rischi percepiti come astratti.",
     "come": "Caso reale in terza persona: personaggio simile → evento → conseguenze → esito.", "modulo": "laterale"},
    {"nome": "FAB (caratteristiche-vantaggi-benefici)", "fonte": "Formazione commerciale classica", "fase": "Proposta",
     "quando": "Presentazione della soluzione.",
     "come": "Traduci ogni caratteristica nel beneficio per questo cliente: «… e per lei significa che…»", "modulo": "proposta"},
    {"nome": "Tre opzioni e ancoraggio", "fonte": "Dan Ariely, Daniel Kahneman", "fase": "Proposta",
     "quando": "Presentazione di preventivi.",
     "come": "Presenta completa → consigliata → essenziale, raccomandando esplicitamente.", "modulo": "proposta"},
    {"nome": "Sandwich del prezzo", "fonte": "Formazione commerciale classica", "fase": "Proposta",
     "quando": "Comunicazione del premio.",
     "come": "Valore → prezzo → valore → silenzio.", "modulo": "proposta"},
    {"nome": "ACER / LAER", "fonte": "Modello LAER", "fase": "Obiezioni",
     "quando": "A ogni obiezione.",
     "come": "Ascolta, conferma, esplora con domande, rispondi alla vera causa.", "modulo": "obiezioni"},
    {"nome": "Feel-Felt-Found", "fonte": "Formazione commerciale anglosassone", "fase": "Obiezioni",
     "quando": "Dubbi emotivi o pregiudizi.",
     "come": "«Capisco cosa prova – anche altri lo pensavano – poi hanno scoperto che…»", "modulo": "obiezioni"},
    {"nome": "Isolamento dell'obiezione", "fonte": "Tom Hopkins", "fase": "Obiezioni",
     "quando": "Per verificare se l'obiezione è l'unico ostacolo.",
     "come": "«A parte questo, c'è altro che la frena?»", "modulo": "obiezioni"},
    {"nome": "Boomerang", "fonte": "Formazione commerciale classica", "fase": "Obiezioni",
     "quando": "Quando l'obiezione contiene il motivo per acquistare.",
     "come": "«Proprio perché… è il momento giusto per…»", "modulo": "obiezioni"},
    {"nome": "Interessi, non posizioni", "fonte": "Fisher e Ury, Harvard Negotiation Project", "fase": "Negoziazione",
     "quando": "Richieste di sconto o condizioni.",
     "come": "Chiedi perché la posizione è importante e cerca opzioni che soddisfino l'interesse.", "modulo": "negoziazione"},
    {"nome": "BATNA", "fonte": "Fisher e Ury", "fase": "Negoziazione",
     "quando": "Preparazione di ogni trattativa importante.",
     "come": "Definisci la tua migliore alternativa all'accordo e stima quella del cliente.", "modulo": "negoziazione"},
    {"nome": "Concessione condizionata", "fonte": "Negoziazione distributiva", "fase": "Negoziazione",
     "quando": "Ogni volta che concedi qualcosa.",
     "come": "«Se lei…, allora io posso…», con concessioni decrescenti.", "modulo": "negoziazione"},
    {"nome": "Rispecchiamento ed etichettatura", "fonte": "Chris Voss", "fase": "Negoziazione e obiezioni",
     "quando": "Per far parlare il cliente e far emergere emozioni.",
     "come": "Ripeti le ultime parole con tono interrogativo; «Sembra che…»", "modulo": "negoziazione"},
    {"nome": "Domande calibrate", "fonte": "Chris Voss", "fase": "Negoziazione",
     "quando": "Per coinvolgere il cliente nella soluzione.",
     "come": "Domande con «come» e «cosa»: «Come possiamo farlo funzionare per lei?»", "modulo": "negoziazione"},
    {"nome": "Chiusura alternativa", "fonte": "Zig Ziglar", "fase": "Chiusura",
     "quando": "Segnali d'acquisto evidenti.",
     "come": "Due opzioni entrambe positive: «Annuale o semestrale?»", "modulo": "chiusura"},
    {"nome": "Chiusura riepilogativa", "fonte": "Formazione commerciale classica", "fase": "Chiusura",
     "quando": "Dopo una presentazione completa.",
     "come": "Riassumi bisogni e benefici, poi chiedi «Procediamo?» e taci.", "modulo": "chiusura"},
    {"nome": "Avanzamento vs continuazione", "fonte": "Neil Rackham", "fase": "Continuità",
     "quando": "Alla fine di ogni contatto.",
     "come": "Chiudi sempre con un'azione concreta, una data e un impegno del cliente.", "modulo": "continuita"},
    {"nome": "Referral sistematico", "fonte": "Bill Cates", "fase": "Prospezione",
     "quando": "Dopo firma, sinistro ben gestito, revisione utile.",
     "come": "Chiedi per categorie precise e chiedi una presentazione diretta.", "modulo": "prospezione"},
    {"nome": "Segmentazione ABC (Pareto)", "fonte": "Vilfredo Pareto", "fase": "Portafoglio",
     "quando": "Pianificazione annuale e trimestrale.",
     "come": "Classifica i clienti per valore e potenziale e dosa i contatti.", "modulo": "portafoglio"},
    {"nome": "Net Promoter Score", "fonte": "Frederick Reichheld", "fase": "Portafoglio",
     "quando": "Dopo sinistri e revisioni.",
     "come": "«Da 0 a 10 quanto mi consiglierebbe?»: i 9-10 sono i candidati alle referenze.", "modulo": "portafoglio"},
    {"nome": "Pratica deliberata", "fonte": "Anders Ericsson", "fase": "Crescita",
     "quando": "Allenamento settimanale.",
     "come": "Una abilità per volta, ripetizione, feedback immediato, fuori dalla zona di comfort.", "modulo": "crescita"},
]

# ----------------------------------------------------------------------
# Scenari di role-play
# ----------------------------------------------------------------------
SCENARI = [
    {
        "id": "artigiano",
        "titolo": "L'artigiano che «non ha tempo»",
        "livello": "Base",
        "cliente": "Giorgio, 45 anni, elettricista con due dipendenti, sposato, due figli, mutuo sulla casa.",
        "contesto": "Referenza del suo commercialista. Ha solo la RC auto del furgone. Ti concede 20 minuti in officina, tra un lavoro e l'altro.",
        "obiettivo": "Fissare un secondo incontro con la moglie per parlare di infortuni e RCT/RCO.",
        "fasi": [
            "Apertura con accordo iniziale sui 20 minuti.",
            "Domande SPIN sul fermo attività e sui dipendenti.",
            "Storia in terza persona di un artigiano infortunato.",
            "Chiusura sul prossimo passo: incontro serale con la moglie.",
        ],
        "obiezioni": ["non-tempo", "non-capita", "moglie"],
        "trappole": ["Presentare subito il prodotto per sfruttare i 20 minuti.", "Dare un prezzo indicativo al volo.", "Uscire senza data del secondo incontro."],
        "debrief": ["Quante domande di implicazione hai fatto?", "Il cliente ha nominato da solo il rischio principale?", "Il prossimo passo ha data e partecipanti?"],
    },
    {
        "id": "professionista",
        "titolo": "L'architetto già assicurato",
        "livello": "Intermedio",
        "cliente": "Elena, 38 anni, architetta con studio proprio, molto preparata e diffidente.",
        "contesto": "Ha l'RC professionale obbligatoria sottoscritta online al prezzo più basso. È disposta a un controllo solo perché un collega ha avuto un sinistro.",
        "obiettivo": "Ottenere la polizza attuale per un confronto scritto e far emergere i limiti (retroattività, postuma, massimale).",
        "fasi": [
            "Etichettatura della diffidenza e accordo trasparente.",
            "Domande sui progetti passati e sui cantieri in corso.",
            "Confronto su criteri oggettivi (retroattività, massimale, franchigia).",
            "Tre opzioni con raccomandazione motivata.",
        ],
        "obiezioni": ["gia-assicurato", "online", "mandi-email"],
        "trappole": ["Criticare la sua scelta precedente.", "Entrare in una guerra di prezzo.", "Sommergerla di caratteristiche tecniche."],
        "debrief": ["Hai usato le sue parole nella proposta?", "Il confronto era oggettivo e verificabile?", "Hai fissato un appuntamento per il confronto?"],
    },
    {
        "id": "pmi",
        "titolo": "La PMI con due soci in disaccordo",
        "livello": "Avanzato",
        "cliente": "Metalmeccanica con 25 dipendenti: Paolo (commerciale, favorevole) e Franco (amministrativo, attento ai costi).",
        "contesto": "Hai completato l'analisi rischi: emergono fermo attività, cyber e D&O scoperti. Franco chiede uno sconto del 20% su tutto il pacchetto.",
        "obiettivo": "Chiudere almeno la copertura sul rischio principale senza svendere, con un piano per gli altri rami.",
        "fasi": [
            "Sei cappelli: fai esprimere a ciascun socio rischi e benefici.",
            "Interessi, non posizioni: scopri perché Franco chiede lo sconto.",
            "Concessioni condizionate (frazionamento, accorpamento, decorrenza).",
            "Chiusura riepilogativa e piano di sviluppo in due fasi.",
        ],
        "obiezioni": ["sconto", "budget", "moglie"],
        "trappole": ["Allearsi con il socio favorevole contro l'altro.", "Concedere lo sconto senza contropartita.", "Dividere la differenza."],
        "debrief": ["Hai individuato l'interesse dietro la richiesta di sconto?", "Ogni concessione aveva una contropartita?", "Entrambi i soci si sono sentiti ascoltati?"],
    },
    {
        "id": "trattativa-ferma",
        "titolo": "La trattativa ferma da due mesi",
        "livello": "Intermedio",
        "cliente": "Marco, titolare di un ristorante, ha ricevuto la proposta incendio + fermo attività e da allora non risponde.",
        "contesto": "Hai già mandato due messaggi «volevo sapere se ha deciso» senza risposta.",
        "obiettivo": "Riaprire il dialogo e ottenere una decisione, anche negativa.",
        "fasi": [
            "Messaggio di riattivazione con un'informazione nuova e utile.",
            "Se risponde: esplora il «ci devo pensare» residuo.",
            "Se non risponde: messaggio di chiusura cortese.",
            "In ogni caso: follow-up programmato nel gestionale.",
        ],
        "obiezioni": ["pensarci", "non-momento", "caro"],
        "trappole": ["Chiedere ancora «ha deciso?».", "Offrire uno sconto per sbloccare.", "Lasciar perdere senza un follow-up futuro."],
        "debrief": ["Il messaggio portava valore nuovo?", "Hai ottenuto una risposta chiara?", "C'è un follow-up con data nel gestionale?"],
    },
    {
        "id": "revisione",
        "titolo": "La revisione annuale che diventa cross-selling",
        "livello": "Base",
        "cliente": "Sara, 34 anni, impiegata, cliente da 3 anni con auto e casa. Si è appena sposata e aspetta un figlio.",
        "contesto": "Appuntamento di revisione prima del rinnovo dell'auto.",
        "obiettivo": "Far emergere i nuovi bisogni (vita, infortuni, previdenza) e chiedere referenze.",
        "fasi": [
            "Domanda di revisione: cosa è cambiato quest'anno?",
            "Domande di implicazione sul reddito familiare e sul futuro del figlio.",
            "Una sola proposta prioritaria, con le altre in agenda.",
            "Richiesta di referenze per categoria (colleghi, amici in attesa).",
        ],
        "obiezioni": ["giovane", "inps", "moglie"],
        "trappole": ["Proporre tutto insieme.", "Parlare solo del rinnovo auto.", "Dimenticare di chiedere referenze."],
        "debrief": ["Quali cambiamenti di vita sono emersi?", "Hai proposto una priorità chiara?", "Quante referenze hai chiesto e ottenuto?"],
    },
]


# ----------------------------------------------------------------------
# Schede da stampare
# Ogni sezione ha un tipo: "campi" (etichetta + riga da compilare),
# "check" (caselle da spuntare), "tabella" (colonne + righe vuote),
# "domande" (domande guida con spazio per la risposta).
# ----------------------------------------------------------------------
SCHEDE = [
    {
        "id": "raccolta-privato",
        "titolo": "Raccolta informazioni — cliente privato",
        "icona": "bi-person-vcard",
        "uso": "Primo appuntamento o revisione completa con una persona o una famiglia.",
        "modulo": "informazioni",
        "sezioni": [
            {"titolo": "Persona e famiglia", "tipo": "campi", "campi": [
                "Nome e cognome", "Data di nascita", "Stato civile", "Coniuge / convivente (età, lavoro)",
                "Figli (età)", "Altre persone a carico", "Stato di salute generale e attività sportive"]},
            {"titolo": "Lavoro e reddito", "tipo": "campi", "campi": [
                "Professione e tipo di contratto (dipendente, autonomo, pensionato)", "Datore di lavoro / attività",
                "Reddito netto mensile personale", "Reddito netto mensile familiare",
                "Coperture del datore di lavoro / cassa / ente (malattia, infortuni, vita)", "Stabilità del reddito nei prossimi 5 anni"]},
            {"titolo": "Casa, beni e impegni", "tipo": "campi", "campi": [
                "Abitazione (proprietà / affitto, zona, anno di costruzione)", "Mutuo o prestiti (importo residuo, durata, rata)",
                "Altri immobili", "Veicoli", "Animali domestici", "Spese fisse mensili della famiglia"]},
            {"titolo": "Coperture in essere", "tipo": "tabella",
             "colonne": ["Ramo", "Compagnia", "Massimale / capitale", "Premio annuo", "Scadenza", "Note"], "righe": 6},
            {"titolo": "Esperienze e obiettivi", "tipo": "domande", "domande": [
                "Ha mai avuto un sinistro? Come è andata la gestione?",
                "Se domani si fermasse per sei mesi, come pagherebbe le spese?",
                "Se le succedesse qualcosa di grave, cosa vorrebbe garantire alla sua famiglia?",
                "Cosa la preoccupa di più per il futuro (salute, pensione, figli, casa)?",
                "Quanto ritiene sostenibile destinare ogni mese alla protezione e al risparmio?"]},
            {"titolo": "Adempimenti", "tipo": "check", "voci": [
                "Informativa privacy consegnata", "Consenso al trattamento dati per finalità contrattuali",
                "Consenso marketing (facoltativo) raccolto e registrato",
                "Richieste ed esigenze del cliente documentate (valutazione di coerenza)",
                "Copia delle polizze in essere ricevuta"]},
        ],
    },
    {
        "id": "raccolta-azienda",
        "titolo": "Raccolta informazioni — azienda o professionista",
        "icona": "bi-building",
        "uso": "Analisi dei rischi di un'impresa o di uno studio professionale; da completare con una visita in sede.",
        "modulo": "informazioni",
        "sezioni": [
            {"titolo": "Dati dell'impresa", "tipo": "campi", "campi": [
                "Ragione sociale e forma giuridica", "Partita IVA / codice ATECO", "Anno di inizio attività",
                "Fatturato ultimo esercizio", "Numero di dipendenti e collaboratori", "Sedi e unità locali (indirizzi)"]},
            {"titolo": "Attività e processi", "tipo": "domande", "domande": [
                "Mi racconta un ordine tipico, dalla richiesta del cliente al pagamento?",
                "Quali macchinari, impianti o sistemi informatici sono indispensabili?",
                "Lavorate presso terzi (cantieri, clienti, all'estero)?",
                "Quali dati personali o riservati gestite (clienti, pazienti, dipendenti)?",
                "Ci sono lavorazioni pericolose, sostanze infiammabili o inquinanti?"]},
            {"titolo": "Persone chiave e dipendenze", "tipo": "campi", "campi": [
                "Soci e quote", "Persone indispensabili (key people)", "Peso dei primi 3 clienti sul fatturato",
                "Fornitori critici", "Contratti che impongono coperture (appalti, capitolati, leasing)", "Commercialista e banca di riferimento"]},
            {"titolo": "Coperture in essere", "tipo": "tabella",
             "colonne": ["Ramo", "Compagnia", "Massimale", "Franchigia", "Premio", "Scadenza"], "righe": 8},
            {"titolo": "Rischi e obblighi", "tipo": "check", "voci": [
                "RC professionale obbligatoria (se prevista per la professione)", "Copertura eventi catastrofali per le imprese (obbligo di legge)",
                "RCT/RCO", "Incendio e fermo attività", "Cyber", "D&O amministratori", "Tutela legale",
                "Infortuni titolare e soci", "Key man", "Welfare per i dipendenti"]},
            {"titolo": "La parola al titolare", "tipo": "domande", "domande": [
                "Se l'azienda si fermasse per un mese, cosa succederebbe?",
                "Qual è il rischio che le toglie il sonno?",
                "Quali sinistri o reclami avete avuto negli ultimi 5 anni?",
                "Quali cambiamenti prevedete nei prossimi 2 anni (assunzioni, nuove sedi, export, investimenti)?"]},
        ],
    },
    {
        "id": "informazioni-da-dare",
        "titolo": "Check-list informazioni e documenti da dare al cliente",
        "icona": "bi-file-earmark-check",
        "uso": "Prima e dopo la sottoscrizione. Verifica sempre la versione vigente dei modelli e le procedure della tua compagnia o intermediario.",
        "modulo": "informazioni",
        "sezioni": [
            {"titolo": "Prima della sottoscrizione", "tipo": "check", "voci": [
                "Presentazione: nome, ruolo, iscrizione al Registro Unico degli Intermediari (RUI)",
                "Informativa sul distributore (Reg. IVASS 40/2018, Allegato 3)",
                "Informazioni sulla distribuzione del prodotto, inclusa la natura della remunerazione (Allegato 4)",
                "Elenco delle regole di comportamento del distributore (Allegato 4-ter)",
                "Documento Informativo Precontrattuale (DIP) ed eventuale DIP aggiuntivo",
                "Condizioni di assicurazione",
                "Informativa privacy e raccolta dei consensi",
                "Raccolta delle richieste ed esigenze e valutazione di coerenza del contratto",
                "Spiegazione a voce di massimali, franchigie, scoperti ed esclusioni principali",
                "Modalità di pagamento ammesse e frazionamento"]},
            {"titolo": "Alla firma e dopo", "tipo": "check", "voci": [
                "Copia del contratto firmato",
                "Sintesi scritta: cosa è coperto, cosa no",
                "Istruzioni in caso di sinistro (cosa fare, entro quando, chi chiamare)",
                "Contatti diretti del consulente",
                "Scadenze, tacito rinnovo e modalità di disdetta",
                "Diritto di recesso o ripensamento, se previsto",
                "Procedura per i reclami (alla compagnia/intermediario e, in seconda istanza, all'IVASS)",
                "Follow-up a 30 giorni fissato in agenda"]},
            {"titolo": "Note", "tipo": "campi", "campi": ["Documenti consegnati il", "Firma del cliente per ricevuta"]},
        ],
    },
    {
        "id": "preparazione-appuntamento",
        "titolo": "Preparazione dell'appuntamento",
        "icona": "bi-journal-check",
        "uso": "Da compilare 15 minuti prima di ogni incontro commerciale.",
        "modulo": "apertura",
        "sezioni": [
            {"titolo": "Il cliente", "tipo": "campi", "campi": [
                "Cliente e interlocutore", "Come è nato il contatto (referenza, evento, campagna)",
                "Cosa so già (settore, famiglia, notizie)", "Coperture già note / gap dall'analisi"]},
            {"titolo": "Obiettivi", "tipo": "campi", "campi": [
                "Obiettivo principale dell'incontro", "Obiettivo minimo accettabile (prossimo passo)",
                "Accordo iniziale: tempo, scopo, ruoli, esiti"]},
            {"titolo": "Domande SPIN preparate", "tipo": "campi", "campi": [
                "Situazione", "Problema", "Implicazione", "Need-payoff (bisogno-beneficio)"]},
            {"titolo": "Obiezioni probabili e risposte", "tipo": "tabella",
             "colonne": ["Obiezione prevista", "Domanda di esplorazione", "Risposta / tecnica"], "righe": 3},
            {"titolo": "Materiali", "tipo": "check", "voci": [
                "Analisi dei rischi stampata", "Storia/caso pertinente pronto", "Documenti informativi obbligatori",
                "Scheda di raccolta informazioni", "Agenda per fissare il prossimo appuntamento"]},
        ],
    },
    {
        "id": "diario-trattativa",
        "titolo": "Diario della trattativa (debrief dopo l'incontro)",
        "icona": "bi-pencil-square",
        "uso": "Subito dopo ogni incontro, in 5 minuti. È la base della pratica deliberata.",
        "modulo": "crescita",
        "sezioni": [
            {"titolo": "Esito", "tipo": "campi", "campi": [
                "Cliente e data", "Obiettivo raggiunto? (sì / parziale / no)", "Prossimo passo concordato (azione, data, chi)"]},
            {"titolo": "Analisi", "tipo": "domande", "domande": [
                "Chi ha parlato di più?",
                "Quali bisogni sono emersi, con le parole del cliente?",
                "Quali obiezioni sono arrivate? Erano vere o scuse?",
                "Cosa ripeterei esattamente uguale?",
                "Cosa farei diversamente?"]},
            {"titolo": "Da fare", "tipo": "check", "voci": [
                "Follow-up registrato nel gestionale", "Opportunità aggiornata in Pipeline",
                "Email di riepilogo inviata entro 24 ore", "Descrizione dell'attività aggiornata per l'analisi rischi"]},
        ],
    },
    {
        "id": "piano-negoziazione",
        "titolo": "Piano di negoziazione",
        "icona": "bi-arrow-left-right",
        "uso": "Prima di una trattativa con richiesta di sconto o condizioni particolari.",
        "modulo": "negoziazione",
        "sezioni": [
            {"titolo": "Posizioni e interessi", "tipo": "campi", "campi": [
                "Posizione dichiarata del cliente", "Possibili interessi dietro la posizione",
                "I miei interessi (provvigione, relazione, portafoglio, tempo)"]},
            {"titolo": "Alternative e limiti", "tipo": "campi", "campi": [
                "Il mio BATNA (cosa faccio se non c'è accordo)", "Il BATNA stimato del cliente",
                "Il mio obiettivo", "Il mio limite oltre cui non vado", "Criteri oggettivi da usare (tariffe, dati, casi)"]},
            {"titolo": "Concessioni possibili", "tipo": "tabella",
             "colonne": ["Concessione", "Costo per me", "Valore per il cliente", "Contropartita richiesta («se… allora…»)"], "righe": 6},
            {"titolo": "Opzioni creative", "tipo": "check", "voci": [
                "Frazionamento o data della prima rata", "Decorrenza diversa", "Franchigia modulata",
                "Accorpamento multi-polizza", "Servizi aggiuntivi (revisione semestrale, gestione sinistri)", "Copertura in due fasi"]},
        ],
    },
    {
        "id": "registro-obiezioni",
        "titolo": "Registro delle obiezioni",
        "icona": "bi-list-check",
        "uso": "Tienilo per un mese: scoprirai quali obiezioni prevenire nella presentazione.",
        "modulo": "obiezioni",
        "sezioni": [
            {"titolo": "Registro", "tipo": "tabella",
             "colonne": ["Data", "Cliente", "Obiezione (parole esatte)", "Fase", "Vera / scusa", "Tecnica usata", "Esito"], "righe": 15},
        ],
    },
    {
        "id": "griglia-roleplay",
        "titolo": "Griglia di osservazione del role-play",
        "icona": "bi-people",
        "uso": "Per l'osservatore durante le simulazioni a tre (consulente, cliente, osservatore). Voto da 1 a 5.",
        "modulo": "crescita",
        "sezioni": [
            {"titolo": "Valutazione", "tipo": "tabella",
             "colonne": ["Abilità", "Voto 1-5", "Esempio osservato (frase)"],
             "righe_fisse": [
                 "Accordo iniziale (tempo, scopo, esiti)", "Rapporto parlare / ascoltare",
                 "Domande di situazione e problema", "Domande di implicazione", "Riformulazione e riassunto",
                 "Benefici collegati ai bisogni (FAB)", "Presentazione del prezzo", "Gestione delle obiezioni (ACER)",
                 "Chiusura o prossimo passo con data", "Coerenza del non verbale"]},
            {"titolo": "Feedback", "tipo": "domande", "domande": [
                "Il momento migliore della simulazione:",
                "Una sola cosa da migliorare nella prossima:"]},
        ],
    },
    {
        "id": "revisione-annuale",
        "titolo": "Revisione annuale del cliente",
        "icona": "bi-arrow-repeat",
        "uso": "Una volta l'anno, prima del rinnovo principale. Base del cross-selling e delle referenze.",
        "modulo": "portafoglio",
        "sezioni": [
            {"titolo": "Cosa è cambiato", "tipo": "check", "voci": [
                "Matrimonio / convivenza / separazione", "Nascita di un figlio", "Acquisto o ristrutturazione casa",
                "Nuovo lavoro / cambio di reddito", "Pensione in arrivo", "Nuovi veicoli",
                "Assunzioni o nuovi soci (aziende)", "Nuova sede, macchinari, export (aziende)", "Problemi di salute in famiglia", "Successione / passaggio generazionale"]},
            {"titolo": "Verifica delle polizze", "tipo": "tabella",
             "colonne": ["Polizza", "Ancora adeguata?", "Da aggiornare (massimali, garanzie)", "Azione"], "righe": 5},
            {"titolo": "Relazione", "tipo": "campi", "campi": [
                "Da 0 a 10, quanto mi consiglierebbe a un amico o collega?", "Cosa potrei fare meglio?",
                "Referenze richieste (nomi e categoria)", "Prossima revisione fissata il"]},
        ],
    },
    {
        "id": "mappa-referenze",
        "titolo": "Mappa delle relazioni e delle referenze",
        "icona": "bi-diagram-3",
        "uso": "Da compilare insieme al cliente soddisfatto: fa emergere nuovi bisogni e nuovi contatti.",
        "modulo": "portafoglio",
        "sezioni": [
            {"titolo": "Cliente al centro", "tipo": "campi", "campi": ["Cliente", "Data"]},
            {"titolo": "Le cerchie", "tipo": "tabella",
             "colonne": ["Cerchia", "Nome", "Relazione", "Bisogno potenziale", "Presentazione (sì/no)", "Stato"],
             "righe_fisse": [
                 "Famiglia", "Famiglia", "Soci / colleghi", "Dipendenti", "Fornitori", "Clienti del cliente",
                 "Commercialista / consulenti", "Associazioni / sport / scuola"]},
            {"titolo": "Dopo la segnalazione", "tipo": "check", "voci": [
                "Ringraziamento entro 24 ore", "Contatto fatto entro 7 giorni", "Aggiornamento a chi ha segnalato sull'esito"]},
        ],
    },
    {
        "id": "piano-settimanale",
        "titolo": "Piano settimanale e KPI",
        "icona": "bi-calendar-week",
        "uso": "Il venerdì: consuntivo della settimana e piano della successiva.",
        "modulo": "crescita",
        "sezioni": [
            {"titolo": "Attività", "tipo": "tabella",
             "colonne": ["Attività", "Obiettivo", "Lun", "Mar", "Mer", "Gio", "Ven", "Totale"],
             "righe_fisse": [
                 "Contatti / telefonate", "Appuntamenti fissati", "Appuntamenti svolti", "Analisi dei rischi",
                 "Proposte presentate", "Contratti chiusi", "Revisioni clienti", "Referenze richieste", "Referenze ottenute"]},
            {"titolo": "Rapporti di conversione", "tipo": "campi", "campi": [
                "Appuntamenti / contatti (%)", "Proposte / appuntamenti (%)", "Contratti / proposte (%)",
                "Collo di bottiglia della settimana e modulo dell'Accademia da ripassare"]},
        ],
    },
    {
        "id": "post-vendita",
        "titolo": "Percorso post-vendita",
        "icona": "bi-heart",
        "uso": "Dopo ogni nuovo contratto: la seconda vendita inizia qui.",
        "modulo": "continuita",
        "sezioni": [
            {"titolo": "Cliente", "tipo": "campi", "campi": ["Cliente", "Polizza", "Data firma"]},
            {"titolo": "Tappe", "tipo": "check", "voci": [
                "Consegna della polizza di persona con spiegazione (entro 7 giorni)",
                "Richiesta di referenze al momento della consegna",
                "Contatto a 30 giorni: domande sulla polizza?",
                "Inserimento consenso marketing e preferenze di contatto",
                "Contatto di valore a 3 mesi (informazione utile, non commerciale)",
                "Revisione a 12 mesi fissata",
                "In caso di sinistro: chiamata del consulente entro 24 ore dalla denuncia",
                "Dopo il sinistro chiuso: domanda di soddisfazione e richiesta di referenze"]},
        ],
    },
]


# ----------------------------------------------------------------------
# Assemblaggio del percorso
# ----------------------------------------------------------------------
_TUTTI = {m["id"]: m for m in MODULI + MODULI_EXTRA}
MODULI = [_TUTTI[mid] for mid in ORDINE_MODULI]
for _numero, _modulo in enumerate(MODULI, start=1):
    _modulo["numero"] = _numero
    _modulo["evidenze"] = EVIDENZE.get(_modulo["id"], [])

# ----------------------------------------------------------------------
# Funzioni di supporto
# ----------------------------------------------------------------------
_MODULI_BY_ID = {m["id"]: m for m in MODULI}
_SCHEDE_BY_ID = {s["id"]: s for s in SCHEDE}
_OBIEZIONI_BY_ID = {o["id"]: o for o in OBIEZIONI}
_SCENARI_BY_ID = {s["id"]: s for s in SCENARI}


def get_modulo(modulo_id: str) -> dict | None:
    return _MODULI_BY_ID.get(modulo_id)


def get_scenario(scenario_id: str) -> dict | None:
    return _SCENARI_BY_ID.get(scenario_id)


def get_scheda(scheda_id: str) -> dict | None:
    return _SCHEDE_BY_ID.get(scheda_id)


def tutte_le_lezioni() -> list[tuple[dict, dict]]:
    """Coppie (modulo, lezione) nell'ordine del percorso."""
    return [(m, lez) for m in MODULI for lez in m["lezioni"]]


def lezione_ids() -> set[str]:
    return {lez["id"] for _, lez in tutte_le_lezioni()}


def valuta_quiz(modulo: dict, risposte: dict) -> dict:
    """Corregge il quiz di un modulo.

    `risposte` mappa l'indice della domanda (stringa "q0", "q1", …) all'indice
    dell'opzione scelta. Restituisce punteggio, totale e dettaglio per domanda.
    """
    dettaglio = []
    punteggio = 0
    for i, q in enumerate(modulo["quiz"]):
        try:
            scelta = int(risposte.get(f"q{i}", ""))
        except (TypeError, ValueError):
            scelta = None
        giusta = scelta == q["corretta"]
        punteggio += int(giusta)
        dettaglio.append({"domanda": q, "scelta": scelta, "giusta": giusta})
    return {"punteggio": punteggio, "totale": len(modulo["quiz"]), "dettaglio": dettaglio}


def pillola_del_giorno(giorno: date | None = None) -> dict:
    """Obiezione del giorno: cambia ogni giorno ma è stabile nella giornata."""
    giorno = giorno or date.today()
    return OBIEZIONI[giorno.toordinal() % len(OBIEZIONI)]


def obiezione_casuale(esclusa: str | None = None) -> dict:
    candidate = [o for o in OBIEZIONI if o["id"] != esclusa] or OBIEZIONI
    return random.choice(candidate)


def get_obiezione(obiezione_id: str) -> dict | None:
    return _OBIEZIONI_BY_ID.get(obiezione_id)


def cerca_obiezioni(q: str = "", categoria: str = "") -> list[dict]:
    q = (q or "").strip().lower()
    risultati = []
    for o in OBIEZIONI:
        if categoria and o["categoria"] != categoria:
            continue
        if q and q not in " ".join(
            [o["obiezione"], o["cosa_nasconde"], o["tecnica"], o["risposta"], o["laterale"]]
        ).lower():
            continue
        risultati.append(o)
    return risultati

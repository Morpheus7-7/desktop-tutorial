"""Contenuti aggiuntivi dell'Accademia (versione 3.0).

- Modulo «Correttezza e normativa in pratica» (IDD, regolamenti IVASS,
  privacy, antiriciclaggio, reclami, aggiornamento professionale).
- Obiezioni frequenti nel lavoro con professionisti, artigiani e famiglie.
- Role-play per settore: commercialista, medico ospedaliero, famiglia con
  mutuo, negozio.

I riferimenti normativi sono indicazioni formative: verifica sempre il testo
vigente e le procedure della tua compagnia o del tuo intermediario.
"""

MODULO_COMPLIANCE = {
    "id": "compliance",
    "area": "Trattativa",
    "icona": "bi-shield-check",
    "titolo": "Correttezza e normativa in pratica",
    "obiettivo": "Vendere nel rispetto delle regole (IDD e regolamenti IVASS) trasformandole in un vantaggio: chiarezza, fiducia, meno reclami.",
    "lezioni": [
        {
            "id": "compliance-idd",
            "titolo": "Il migliore interesse del cliente: cosa chiede l'IDD",
            "teoria": "Con la direttiva IDD (UE 2016/97), recepita nel Codice delle assicurazioni private dal d.lgs. 68/2018, "
                      "il distributore deve agire in modo onesto, imparziale e professionale, nel migliore interesse del cliente. "
                      "Prima di proporre un contratto raccogli le richieste e le esigenze del cliente (demands and needs) e proponi "
                      "solo prodotti coerenti con esse. Se offri anche una consulenza, cioè una raccomandazione personalizzata, "
                      "devi spiegare perché quel prodotto è il più adatto. Non è burocrazia: è esattamente il metodo delle domande "
                      "che usi in trattativa, messo per iscritto.",
            "punti": [
                "Prima le esigenze, poi il prodotto: il questionario non è un modulo da far firmare alla fine.",
                "Ogni proposta deve essere coerente con ciò che il cliente ha detto: annota le sue parole.",
                "Se raccomandi una soluzione, scrivi il perché in una frase che il cliente possa rileggere.",
                "Il gestionale tiene traccia della data del questionario di adeguatezza: aggiornalo almeno ogni anno.",
            ],
            "esempio": "«Mi ha detto che la priorità è non fermare l'officina se lei si infortuna: per questo le propongo prima "
                       "la copertura infortuni con diaria e solo dopo la tutela legale, che oggi per lei è meno urgente.»",
            "esercizio": "Riprendi le ultime tre proposte: per ciascuna scrivi in una frase quale esigenza del cliente soddisfa. "
                         "Se non ci riesci, la proposta non era coerente.",
        },
        {
            "id": "compliance-documenti",
            "titolo": "Informativa precontrattuale e documenti da consegnare",
            "teoria": "Il Regolamento IVASS 40/2018 stabilisce cosa consegnare prima della firma: l'informativa sul distributore "
                      "(chi sei, iscrizione al RUI, conflitti di interesse, come si presenta un reclamo), le informazioni sulla "
                      "distribuzione del prodotto e l'elenco delle regole di comportamento. Per i rami danni il cliente riceve il "
                      "DIP (il documento informativo standard europeo) e il DIP aggiuntivo previsto dal Regolamento IVASS 41/2018. "
                      "Consegna i documenti prima della sottoscrizione, in tempo utile perché il cliente li legga, e conservane "
                      "la prova.",
            "punti": [
                "Consegna sempre prima di firmare, mai insieme alla firma «per velocizzare».",
                "Spiega a voce le esclusioni e le franchigie principali: sono la prima causa di reclamo.",
                "Archivia nel cliente (cartella «Privacy e adeguatezza») informativa, questionario e ricevuta di consegna.",
                "Se il cliente rifiuta di rispondere al questionario, annotalo e informalo per iscritto delle conseguenze.",
            ],
            "esempio": "Il consulente invia il DIP via email due giorni prima dell'appuntamento: «Le mando le schede ufficiali, "
                       "giovedì le guardiamo insieme e le spiego cosa resta escluso.» Al momento della firma il cliente ha già le domande pronte.",
            "esercizio": "Controlla in Deal Combined tre clienti: hanno informativa e questionario archiviati e aggiornati? "
                         "Completa quello che manca.",
        },
        {
            "id": "compliance-prodotti",
            "titolo": "Mercato di riferimento, conflitti di interesse e compensi",
            "teoria": "Ogni prodotto ha un mercato di riferimento definito dalla compagnia (POG, Regolamento IVASS 45/2020): "
                      "è il tipo di cliente per cui è pensato. Proporlo fuori da quel mercato richiede una valutazione attenta e "
                      "documentata. Devi poi gestire i conflitti di interesse e informare il cliente sulla natura del compenso "
                      "(commissione, onorario o entrambi). Per i prodotti di investimento assicurativo (IBIP) valgono regole più "
                      "stringenti: valutazione di adeguatezza o appropriatezza e informativa su costi e oneri.",
            "punti": [
                "Chiedi alla compagnia il mercato di riferimento dei prodotti che vendi più spesso.",
                "Non lasciare che la provvigione più alta scelga il prodotto: la raccomandazione deve reggere senza.",
                "Dichiara come sei pagato con naturalezza: la trasparenza costruisce fiducia.",
                "Per gli IBIP verifica conoscenze, esperienza, situazione finanziaria e obiettivi prima di proporre.",
            ],
            "esempio": "«Io sono pagato dalla compagnia con una commissione compresa nel premio: per lei il costo è lo stesso. "
                       "Le propongo questa soluzione perché è quella che copre il fermo attività, non perché mi conviene.»",
            "esercizio": "Prepara la tua frase di trenta secondi su come sei pagato e provala con un collega finché suona naturale.",
        },
        {
            "id": "compliance-tutele",
            "titolo": "Privacy, antiriciclaggio, reclami e aggiornamento",
            "teoria": "Privacy (GDPR): tratta i dati per le finalità dichiarate, chiedi un consenso separato per il marketing "
                      "e conserva i documenti in modo sicuro (il PIN e i backup del programma aiutano). Antiriciclaggio "
                      "(d.lgs. 231/2007): per i prodotti vita e di investimento serve l'adeguata verifica del cliente, con "
                      "documento di identità e titolare effettivo. Reclami (Regolamento IVASS 24/2008): vanno gestiti e riscontrati "
                      "entro 45 giorni; un reclamo ascoltato bene spesso salva il cliente. Aggiornamento professionale: il "
                      "Regolamento IVASS 40/2018 chiede ogni anno almeno 30 ore di formazione a chi distribuisce.",
            "punti": [
                "Consenso marketing separato e facoltativo: registrane la data nella scheda del cliente.",
                "Vita e investimento: documento valido e titolare effettivo prima della firma.",
                "Reclamo: rispondi per iscritto, nel merito, entro 45 giorni, e tieni traccia nel registro.",
                "Tieni il conto delle tue ore di aggiornamento: l'Accademia è allenamento, non sostituisce i corsi riconosciuti.",
            ],
            "esempio": "Un cliente contesta un sinistro liquidato poco. Il consulente lo richiama in giornata, ascolta, spiega la "
                       "franchigia che era stata illustrata alla firma (e lo dimostra con il DIP firmato) e lo aiuta a presentare "
                       "le osservazioni alla compagnia: il cliente rinnova l'anno dopo.",
            "esercizio": "Verifica nel programma i clienti con documento d'identità scaduto o consenso privacy mancante e pianifica "
                         "un follow-up per ciascuno.",
        },
    ],
    "quiz": [
        {
            "domanda": "Quando vanno raccolte le richieste e le esigenze del cliente (demands and needs)?",
            "opzioni": ["Dopo la firma, per completare la pratica",
                        "Prima di proporre il contratto, per offrire solo prodotti coerenti",
                        "Solo per le polizze vita"],
            "corretta": 1,
            "spiegazione": "L'IDD chiede di proporre solo contratti coerenti con richieste ed esigenze: vanno quindi raccolte prima.",
        },
        {
            "domanda": "Qual è il momento giusto per consegnare l'informativa precontrattuale e il DIP?",
            "opzioni": ["Prima della sottoscrizione, in tempo utile per leggerli",
                        "Insieme alla quietanza del primo premio",
                        "Solo se il cliente li chiede"],
            "corretta": 0,
            "spiegazione": "I documenti precontrattuali servono a decidere: vanno consegnati prima della firma.",
        },
        {
            "domanda": "Entro quanti giorni va dato riscontro a un reclamo (Regolamento IVASS 24/2008)?",
            "opzioni": ["15 giorni", "45 giorni", "90 giorni"],
            "corretta": 1,
            "spiegazione": "Il termine per il riscontro al reclamante è di 45 giorni.",
        },
        {
            "domanda": "Un cliente chiede come sei pagato. La risposta corretta è:",
            "opzioni": ["Evitare l'argomento: non lo riguarda",
                        "Spiegare con chiarezza la natura del compenso (commissione, onorario o entrambi)",
                        "Dire che il servizio è gratuito"],
            "corretta": 1,
            "spiegazione": "L'informativa sulla natura del compenso è un obbligo e, detta con naturalezza, rafforza la fiducia.",
        },
        {
            "domanda": "Per quali prodotti serve l'adeguata verifica antiriciclaggio del cliente?",
            "opzioni": ["Per l'RC auto", "Per i prodotti vita e di investimento", "Per tutte le polizze danni"],
            "corretta": 1,
            "spiegazione": "Il d.lgs. 231/2007 si applica ai rami vita e ai prodotti di investimento assicurativo.",
        },
    ],
    "fonti": [
        "Direttiva (UE) 2016/97 sulla distribuzione assicurativa (IDD)",
        "D.lgs. 209/2005, Codice delle assicurazioni private, come modificato dal d.lgs. 68/2018",
        "Regolamento IVASS 40/2018 (distribuzione assicurativa e riassicurativa)",
        "Regolamento IVASS 41/2018 (informativa, pubblicità e realizzazione dei prodotti)",
        "Regolamento IVASS 45/2020 (governo e controllo del prodotto, POG)",
        "Regolamento IVASS 24/2008 (gestione dei reclami)",
        "D.lgs. 231/2007 (antiriciclaggio) e Regolamento (UE) 2016/679 (GDPR)",
    ],
}

EVIDENZE_COMPLIANCE = [
    {"tesi": "Spiegare in modo chiaro esclusioni e limiti prima della firma riduce incomprensioni e reclami.",
     "livello": "limitata",
     "fonte": "Pratica professionale; le relazioni annuali IVASS sui reclami indicano tra le cause ricorrenti le contestazioni "
              "sulla liquidazione e sulle condizioni contrattuali"},
    {"tesi": "I documenti informativi standardizzati (come il DIP/IPID) migliorano la comparabilità tra prodotti, ma da soli "
             "vengono letti poco: servono spiegazioni a voce.",
     "livello": "moderata",
     "fonte": "EIOPA, consumer testing per l'IPID (2017); letteratura sull'effetto limitato dell'informativa obbligatoria "
              "(Ben-Shahar e Schneider, 2014)"},
    {"tesi": "La trasparenza sul compenso del consulente non riduce la fiducia quando è spiegata con chiarezza e insieme "
             "alla motivazione della raccomandazione.",
     "livello": "limitata",
     "fonte": "Studi sperimentali sulla disclosure dei conflitti di interesse con risultati misti (Cain, Loewenstein e Moore, 2005; "
              "Sah e Loewenstein, 2014): conta come viene comunicata"},
]

OBIEZIONI_EXTRA = [
    {
        "id": "banca",
        "categoria": "concorrenza",
        "obiezione": "Ce l'ho già con la banca, me l'hanno fatta con il mutuo.",
        "cosa_nasconde": "Comodità e l'idea che «la banca» sia una garanzia; spesso non sa cosa copre davvero la polizza abbinata.",
        "tecnica": "Domanda di verifica + confronto su criteri oggettivi",
        "risposta": "«Ottimo che ci abbia pensato. Sa dirmi cosa copre esattamente? Spesso quella polizza protegge la banca "
                    "(il mutuo), non lei e la sua famiglia.»",
        "rilancio": "«Le va se la guardiamo insieme? In dieci minuti le dico cosa è coperto e cosa no, poi decide lei.»",
        "laterale": "Chiedi chi è il beneficiario: se è la banca, la famiglia resta con le spese di tutti i giorni scoperte.",
    },
    {
        "id": "inail",
        "categoria": "bisogno",
        "obiezione": "Mi copre già l'INAIL.",
        "cosa_nasconde": "Crede che l'assicurazione pubblica copra tutto, anche fuori dal lavoro e per intero.",
        "tecnica": "Riformulazione + domanda di implicazione",
        "risposta": "«L'INAIL è importante e copre gli infortuni sul lavoro, con i suoi limiti e le sue franchigie. Fuori dal "
                    "lavoro, nel weekend o in vacanza, cosa succede?»",
        "rilancio": "«Se per tre mesi non potesse lavorare per un incidente in bici la domenica, chi coprirebbe le spese di casa?»",
        "laterale": "Sposta l'attenzione dal «se succede» al «quando non sono al lavoro»: è la maggior parte delle ore della settimana.",
    },
    {
        "id": "convenzione-ordine",
        "categoria": "concorrenza",
        "obiezione": "Ho la polizza convenzionata con il mio ordine, costa poco.",
        "cosa_nasconde": "Pensa che la convenzione sia automaticamente adeguata perché scelta dall'ordine.",
        "tecnica": "Confronto su criteri oggettivi (retroattività, postuma, massimale, franchigia)",
        "risposta": "«Le convenzioni sono un buon punto di partenza. Verifichiamo tre cose: massimale rispetto ai suoi incarichi, "
                    "retroattività per i lavori passati e garanzia postuma se smette.»",
        "rilancio": "«Se trovassimo un buco su uno di questi punti, vorrebbe saperlo prima o dopo un sinistro?»",
        "laterale": "Fai calcolare a lui il valore del suo incarico più grande e confrontalo con il massimale: la cifra parla da sola.",
    },
    {
        "id": "mai-sinistri",
        "categoria": "bisogno",
        "obiezione": "In vent'anni non mi è mai successo niente.",
        "cosa_nasconde": "Bias dell'ottimismo: l'assenza di sinistri passati viene letta come assenza di rischio futuro.",
        "tecnica": "Storia in terza persona + reframing",
        "risposta": "«È un'ottima notizia e vuol dire che lavora bene. Anche i miei clienti che hanno avuto un sinistro non ne "
                    "avevano mai avuti prima: il primo arriva sempre senza preavviso.»",
        "rilancio": "«Se il primo fosse grosso, quanto potrebbe sostenere di tasca sua senza mettere in difficoltà l'attività?»",
        "laterale": "Vent'anni senza sinistri significano anche vent'anni di patrimonio accumulato: oggi c'è di più da proteggere.",
    },
    {
        "id": "dopo-estate",
        "categoria": "tempo",
        "obiezione": "Ne riparliamo dopo l'estate.",
        "cosa_nasconde": "Rinvio comodo: il tema non è prioritario o non è stato chiarito il costo del rinvio.",
        "tecnica": "Accordo sul prossimo passo con data",
        "risposta": "«Va benissimo. Fissiamo già adesso il giorno, così non ci pensa più: la prima settimana di settembre le va bene il martedì?»",
        "rilancio": "«Nel frattempo, c'è qualcosa che le serve sapere per decidere con calma?»",
        "laterale": "Proponi di attivare subito solo la copertura più urgente e rinviare il resto: il rinvio non lascia scoperto il rischio principale.",
    },
    {
        "id": "affitto",
        "categoria": "bisogno",
        "obiezione": "Sono in affitto, la casa non è mia.",
        "cosa_nasconde": "Confonde l'assicurazione della casa con quella delle proprie responsabilità e dei propri beni.",
        "tecnica": "Domanda di situazione + esempio concreto",
        "risposta": "«Giusto, i muri sono del proprietario. Ma se una perdita d'acqua dal suo bagno rovina l'appartamento di sotto, "
                    "chi paga? E i suoi mobili, i computer, gli elettrodomestici?»",
        "rilancio": "«Le faccio vedere quanto costa al mese coprire la responsabilità verso i vicini e i suoi beni?»",
        "laterale": "Ribalta la cornice: chi è in affitto rischia di dover pagare danni su una casa che non è nemmeno sua.",
    },
    {
        "id": "commercialista",
        "categoria": "fiducia",
        "obiezione": "Queste cose le segue il mio commercialista.",
        "cosa_nasconde": "Delega per fiducia; spesso il commercialista non si occupa di coperture e rischi.",
        "tecnica": "Alleanza invece di competizione",
        "risposta": "«Benissimo, un buon commercialista è prezioso. Le propongo di coinvolgerlo: io porto l'analisi dei rischi, "
                    "lui la parte fiscale, e decidete insieme.»",
        "rilancio": "«Le va se preparo una sintesi da girargli, così ne parlate alla prossima occasione?»",
        "laterale": "Fai del commercialista un centro di influenza: una sintesi chiara per lui può diventare una fonte di referenze.",
    },
    {
        "id": "vita-fregatura",
        "categoria": "fiducia",
        "obiezione": "Le polizze vita sono una fregatura, preferisco investire.",
        "cosa_nasconde": "Confonde la protezione (caso morte) con il risparmio; magari ha avuto una brutta esperienza con un prodotto di investimento.",
        "tecnica": "Distinguere i bisogni + domanda di implicazione",
        "risposta": "«Ha ragione a voler far rendere i suoi soldi: per investire ci sono strumenti appositi. Qui parliamo di "
                    "un'altra cosa: se lei mancasse domani, la sua famiglia come pagherebbe il mutuo?»",
        "rilancio": "«Una temporanea caso morte non è un investimento: costa poco proprio perché protegge e basta. Le mostro una cifra?»",
        "laterale": "Separa i due cassetti: investimento per far crescere, protezione per non dover vendere gli investimenti nel momento peggiore.",
    },
    {
        "id": "altri-preventivi",
        "categoria": "concorrenza",
        "obiezione": "Sto raccogliendo altri preventivi.",
        "cosa_nasconde": "Vuole confrontare, spesso solo sul prezzo, senza criteri per farlo bene.",
        "tecnica": "Dare i criteri del confronto",
        "risposta": "«Fa benissimo a confrontare. Le lascio una griglia: massimali, franchigie, esclusioni e servizio in caso di "
                    "sinistro. Così confronta mele con mele, non solo il prezzo.»",
        "rilancio": "«Quando li ha tutti, ci vediamo dieci minuti e li guardiamo insieme sulla griglia?»",
        "laterale": "Diventa il consulente del confronto invece che uno dei concorrenti: chi detta i criteri spesso vince la scelta.",
    },
    {
        "id": "colleghi",
        "categoria": "prezzo",
        "obiezione": "Un mio collega paga la metà.",
        "cosa_nasconde": "Ancoraggio a un prezzo sentito, senza sapere cosa copre la polizza del collega.",
        "tecnica": "Domanda di chiarimento + confronto oggettivo",
        "risposta": "«Può darsi, i prezzi cambiano molto. Sa che massimale ha e cosa esclude? Spesso la differenza di prezzo è "
                    "tutta lì.»",
        "rilancio": "«Se mi porta la sua polizza, le preparo un confronto voce per voce.»",
        "laterale": "Chiedi se il collega ha mai avuto un sinistro con quella polizza: il prezzo si vede alla firma, il valore al sinistro.",
    },
]

SCENARI_EXTRA = [
    {
        "id": "commercialista",
        "titolo": "Il commercialista con la convenzione dell'ordine",
        "livello": "Intermedio",
        "cliente": "Marco, 52 anni, commercialista con studio individuale, due collaboratrici, molti clienti PMI.",
        "contesto": "Ha l'RC professionale obbligatoria tramite la convenzione dell'ordine, massimale minimo. Segue anche "
                    "incarichi di revisione e sindaco in due società.",
        "obiettivo": "Verificare massimale, retroattività e copertura degli incarichi di sindaco; fissare un confronto scritto.",
        "fasi": [
            "Accordo iniziale: 20 minuti per un controllo, non una vendita.",
            "Domande SPIN su incarichi, clienti più grandi e sanzioni che potrebbero ricadere su di lui.",
            "Confronto su criteri oggettivi (massimale per sinistro e annuo, retroattività, postuma, incarichi di sindaco).",
            "Proposta in due opzioni e prossimo passo con data.",
        ],
        "obiezioni": ["convenzione-ordine", "gia-assicurato", "caro"],
        "trappole": ["Criticare la convenzione davanti a lui.", "Parlare di prezzo prima di aver trovato un buco reale.",
                     "Dimenticare gli incarichi di sindaco e revisore, spesso esclusi."],
        "debrief": ["Ha calcolato lui il valore del suo incarico più grande?", "Hai verificato retroattività e postuma?",
                    "Il confronto è stato messo per iscritto?"],
    },
    {
        "id": "medico-ospedaliero",
        "titolo": "Il medico ospedaliero e la colpa grave",
        "livello": "Intermedio",
        "cliente": "Sara, 41 anni, anestesista dipendente di un ospedale pubblico, poco tempo e molti turni.",
        "contesto": "Pensa di essere coperta dall'ospedale. Non sa che, per la legge 24/2017, il medico dipendente deve avere una "
                    "propria polizza per la colpa grave (l'azione di rivalsa della struttura).",
        "obiettivo": "Far capire la differenza tra copertura della struttura e colpa grave e proporre la polizza con retroattività adeguata.",
        "fasi": [
            "Apertura rispettosa del poco tempo: 15 minuti tra due turni.",
            "Domande: cosa sa della rivalsa? Ha mai avuto contestazioni?",
            "Spiegazione semplice dell'obbligo (L. 24/2017) e del rischio di rivalsa.",
            "Proposta con retroattività e postuma, e consegna dei documenti precontrattuali.",
        ],
        "obiezioni": ["gia-assicurato", "non-tempo", "convenzione-ordine"],
        "trappole": ["Fare paura con casi estremi.", "Usare termini tecnici senza spiegarli.",
                     "Non verificare la retroattività per gli anni già lavorati."],
        "debrief": ["La cliente sa spiegare con parole sue cos'è la colpa grave?", "Hai consegnato l'informativa prima della firma?",
                    "Hai verificato le eventuali coperture già esistenti?"],
    },
    {
        "id": "famiglia-mutuo",
        "titolo": "La giovane famiglia con il mutuo",
        "livello": "Base",
        "cliente": "Luca e Giulia, 34 e 32 anni, un figlio di due anni, mutuo di 25 anni appena acceso.",
        "contesto": "Hanno la polizza incendio obbligatoria del mutuo, fatta in banca. Luca è dipendente, Giulia libera professionista.",
        "obiettivo": "Far emergere il bisogno di protezione del reddito (temporanea caso morte, infortuni) e fissare un secondo incontro.",
        "fasi": [
            "Accordo iniziale con entrambi presenti.",
            "Domande sul bilancio familiare: cosa succede se uno dei due non può lavorare?",
            "Storia in terza persona di una famiglia simile.",
            "Due opzioni di budget e prossimo passo concordato.",
        ],
        "obiezioni": ["banca", "giovane", "vita-fregatura", "moglie"],
        "trappole": ["Parlare solo con uno dei due.", "Proporre subito un prodotto di investimento.",
                     "Dimenticare che Giulia, libera professionista, non ha le tutele di un dipendente."],
        "debrief": ["Entrambi hanno espresso un bisogno con parole loro?", "Hai distinto protezione e risparmio?",
                    "Il budget proposto è sostenibile ogni mese?"],
    },
    {
        "id": "negozio",
        "titolo": "Il negozio di quartiere",
        "livello": "Base",
        "cliente": "Anna, 47 anni, titolare di un negozio di ottica con una commessa, affitto del locale e molti strumenti costosi.",
        "contesto": "Ha una vecchia polizza incendio di dieci anni fa, mai aggiornata. Accetta pagamenti elettronici e gestisce "
                    "online le prenotazioni.",
        "obiettivo": "Aggiornare valori e garanzie (incendio, furto, RC verso terzi, fermo attività) e far emergere il rischio cyber.",
        "fasi": [
            "Domande di situazione su valori, magazzino e strumenti.",
            "Implicazione: cosa succede se il negozio resta chiuso un mese?",
            "Verifica dei valori assicurati rispetto a quelli di oggi (sottoassicurazione).",
            "Proposta con priorità e calendario per il resto.",
        ],
        "obiezioni": ["gia-assicurato", "budget", "non-momento"],
        "trappole": ["Lasciare valori assicurati vecchi di dieci anni.", "Proporre tutto insieme a un budget limitato.",
                     "Non chiedere dei dati dei clienti gestiti online."],
        "debrief": ["Hai verificato la regola proporzionale con valori aggiornati?", "La cliente ha scelto le priorità?",
                    "Hai fissato quando rivedere le altre coperture?"],
    },
]

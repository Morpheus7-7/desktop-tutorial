# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
Una rete commerciale di consulenti assicurativi (titolare e consulenti, anche in formazione) che seguono professionisti, aziende e lavoratori dipendenti. Lo usano ogni giorno per gestire clienti, polizze, scadenze e trattative, e per formarsi con l'Accademia commerciale. Per questa rete l'Accademia è centrale quanto il gestionale.

## Product Purpose
Tenere in un unico posto il lavoro del consulente: anagrafiche, polizze, documenti, scadenze, follow-up, pipeline delle trattative. Fa anche l'analisi automatica dei rischi dalla descrizione dell'attività del cliente, con spunti di trattativa e gap di copertura. In più offre un percorso di formazione commerciale di 16 settimane, che insegna il mestiere più che i prodotti. Funziona se nessuna scadenza viene persa, se ogni trattativa ha un prossimo passo e se i consulenti migliorano in modo misurabile.

## Positioning
Unisce il gestionale operativo e la palestra commerciale nello stesso strumento: l'analisi dei rischi di un cliente reale diventa materiale di trattativa, e la formazione rimanda subito a pipeline, follow-up e schede stampabili. Ogni tecnica insegnata riporta il suo livello di evidenza scientifica.

## Operating Context
- Uso interno, al computer (ufficio e portatile). I clienti non vedono lo schermo.
- Ai clienti arrivano solo documenti stampati: report di analisi dei rischi, schede di raccolta informazioni e altre schede intestate. Le stampe devono reggere da sole davanti al cliente.
- Contesto normativo italiano: IDD, Regolamenti IVASS 40 e 41/2018, GDPR.
- Applicazione Flask + Bootstrap 5 servita in locale o impacchettata come eseguibile desktop (PyInstaller). Deve funzionare offline: asset vendorizzati, nessuna CDN.

## Capabilities and Constraints
- Dati di esempio caricabili con `seed_demo.py`.
- Lingua dell'interfaccia: italiano.
- Asset statici solo locali (cartella `gestionale/static/vendor`).

## Brand Commitments
- Nome: **Deal Combined** (sostituisce il nome di lavoro "Gestionale Assicurativo").
- Nessun logo né colori aziendali esistenti.

## Evidence on Hand
- Contenuti reali dell'Accademia in `gestionale/academy.py`: moduli, evidenze con fonti, obiezioni, scenari e schede.
- Dati demo sintetici (`seed_demo.py`), da non presentare come clienti reali.
- Non esistono testimonianze, clienti o numeri di mercato da citare: non inventarli.

## Product Principles
- Il prossimo passo prima di tutto: ogni schermata deve rendere evidente cosa fare dopo (scadenza, follow-up, fase della trattativa).
- Spiegabile e onesto: le analisi mostrano perché, le tecniche mostrano il loro livello di evidenza.
- La stampa è il volto verso il cliente: ciò che si stampa deve essere impeccabile anche senza lo schermo.
- Uno strumento per una rete: deve funzionare per chi è esperto e insegnare a chi è in formazione.

## Accessibility & Inclusion
Contrasto WCAG AA in entrambi i temi (chiaro e scuro); interfaccia utilizzabile da tastiera.

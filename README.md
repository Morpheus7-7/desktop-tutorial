# Deal Combined

Gestionale per intermediari assicurativi (agenti e broker) che seguono
**aziende, studi professionali, liberi professionisti, lavoratori dipendenti e
privati**, con un'**Accademia commerciale** per la formazione del consulente.
Raccoglie in un unico posto anagrafiche, persone collegate, polizze, **titoli e
incassi**, **sinistri**, preventivi, note e documenti; **analizza
automaticamente i pericoli** a partire dalla descrizione dell'attività e non fa
perdere **scadenze, rate e follow-up** grazie a notifiche generate in
automatico. Si usa come un normale **programma Windows**, con accesso tramite
**utenti e password**, **PIN** con blocco per inattività, **registro attività**
e **backup** integrati.

> **Versione 3.0** — unisce il *Gestionale Assicurativo* (titoli e incassi,
> sinistri, utenti e ruoli, tipi di cliente con professioni e obblighi di
> legge, documenti in cartelle, rate da far pagare, sincronizzazione tra due
> PC, temi di colore) e *Deal Combined* (Accademia, note e promemoria, persone
> collegate, preventivi, schede compilate, import da Excel, PIN, Google,
> icona vicino all'orologio, aggiornamenti). Aprendo la nuova versione i dati
> già presenti in `Documenti\Deal Combined` vengono aggiornati da soli, dopo un
> backup automatico: al primo avvio si crea l'utente amministratore.

## Funzionalità

### Portafoglio
- **Anagrafica clienti** per tipo, ciascuno con i propri campi (il form mostra
  solo quelli pertinenti e il salvataggio azzera gli altri):
  - **Azienda** — forma giuridica, referente, ATECO, settore, dipendenti, fatturato.
  - **Studio professionale** (studio associato o STP: es. studio legale
    associato, studio pediatrico S.r.l.) — forma giuridica, professione
    esercitata, aree di attività, professionisti/soci, dipendenti e
    collaboratori, fatturato, iscrizione all'albo; elenco dei professionisti
    collegati e pulsante «Aggiungi professionista».
  - **Libero professionista** (una persona sola: es. l'avvocato civilista, il
    pediatra) — professione, **specializzazioni** e **attività svolte**
    suggerite da un catalogo di 25 professioni (scrivendo «Medico pediatra»
    compaiono i settori della pediatria), albo e numero di iscrizione,
    inquadramento (libero professionista, convenzionato SSN, dipendente),
    studio di appartenenza e volume d'affari. Niente dipendenti né ragione
    sociale.
  - **Lavoratore dipendente** (mansione, datore di lavoro, settore) e
    **privato** (pensionato, studente…).
  - **Assicurazioni obbligatorie per legge** in scheda per professionisti e
    studi (es. RC e infortuni per gli avvocati, L. 247/2012; RC professionale o
    per colpa grave per i sanitari secondo l'inquadramento, L. 24/2017), con
    l'indicazione se sono in portafoglio, anche tramite la polizza dello studio.
  - **Validazione** di codice fiscale (anche omocodico e numerico di società),
    partita IVA, CAP, provincia ed email, con avviso sui **duplicati**; la data
    di nascita viene ricavata dal codice fiscale.
  - **Compliance**: consenso privacy (GDPR) e marketing, questionario di
    adeguatezza *demands & needs* (IVASS Reg. 40/2018), documento d'identità
    con scadenza (adeguata verifica). La scheda cliente segnala cosa manca.
  - Indicatori per cliente: premi e provvigioni, titoli da incassare,
    sinistri e **rapporto sinistri/premi**.
- **Polizze** con scheda dedicata: compagnia (con suggerimenti), ramo,
  massimale, premio, **percentuale di provvigione**, frazionamento, decorrenza,
  scadenza, tacito rinnovo con **preavviso di disdetta** e stato; oltre 20 rami
  precompilati. Storico delle modifiche dal registro attività.
  - **Stato effettivo** calcolato dalle date: *non ancora in vigore* (decorrenza
    futura), *in vigore*, *copertura sospesa*, *disdetta inviata*, *scaduta da
    rinnovare*, *rinnovo tacito da registrare*.
  - **Annualità** della polizza calcolate a ritroso dalla scadenza: poliennali
    con tutte le annualità, eventuale **rateo** iniziale (es. allineamento al
    31/12) con premio pro rata giorni; i titoli si generano per ogni annualità.
  - **Disdetta**: termine di preavviso (default 30 giorni, il tacito rinnovo non
    è ammesso per l'RC auto), registrazione alla scadenza o con cessazione
    anticipata, storno delle rate successive, avviso se inviata oltre il termine.
- **Rinnovo in un clic**: nuova scadenza (proposta a 12 mesi, con la prima
  scadenza utile se la polizza è scaduta da tempo), nuovo premio, rinnovo
  **pluriennale** con conferma esplicita (massimo 10 anni), quietanza della
  prima annualità e chiusura automatica dei follow-up di rinnovo.
- **Titoli e incassi**:
  - generazione automatica delle **rate dell'annualità** in base al
    frazionamento (annuale → mensile), con arrotondamenti che quadrano sempre
    con il premio annuo; perfezionamento, quietanze, rate e appendici manuali;
  - **incasso** con data (mai futura), mezzo di pagamento e riferimento (CRO,
    assegno…) per l'importo del titolo, annullamento (gli incassi dei mesi già
    chiusi solo dall'amministratore) e **storno**;
  - **arretrati** evidenziati con lo stato della copertura secondo
    l'**art. 1901 c.c.** (primo premio non pagato → copertura non operante;
    rate successive → sospesa dal 15° giorno);
  - **foglio cassa** (prima nota incassi) per periodo, con riepilogo per mezzo
    di pagamento, provvigioni maturate e netto da rimettere;
  - **estratto conto per compagnia** che include gli incassi dei periodi
    precedenti non ancora rimessi; la **rimessa** registra esattamente i titoli
    mostrati e confermati, con data validata, ed è annullabile dall'amministratore;
  - **previsione incassi** a 6-24 mesi: rate già emesse, quietanze stimate dei
    rinnovi e delle annualità future, provvigioni e netto per mese (esportabile).
- **Sinistri**: apertura con numerazione progressiva (SIN-anno-numero, mai
  riassegnata dopo un'eliminazione),
  polizza coinvolta, tipologia, controparte, perito e liquidatore; importi
  richiesti, riservati, franchigia e liquidati; **cronologia** con note e
  cambi di stato; documenti collegati (denuncia, foto, perizia…); promemoria
  e avviso di **denuncia oltre i 3 giorni** (art. 1913 c.c.); controllo della
  **copertura alla data dell'evento** (prima della decorrenza, dopo la scadenza,
  rata impagata). Le date di evento, denuncia e liquidazione non possono essere future.
- **Archivio documenti**: caricamento **multiplo con drag & drop**, download ed
  eliminazione, collegabili a una polizza o a un sinistro, con ricerca.

### Consulenza e commerciale
- **Analisi automatica dei rischi**: un motore a regole in italiano legge la
  descrizione dell'attività (più i dati di anagrafica) e produce:
  - i **pericoli rilevati** con severità e parole chiave che li hanno attivati;
  - le **coperture consigliate** per ciascun pericolo;
  - per ogni copertura uno **spunto di trattativa** con pensiero laterale,
    esempio in terza persona e vantaggi da portare in trattativa;
  - la **gap analysis** tra coperture consigliate e polizze già attive, con la
    possibilità di trasformare una copertura scoperta in un'**opportunità** con
    un clic. Ogni analisi è salvata nello storico ed è stampabile.
- **Pipeline commerciale (opportunità)** a fasi in stile CRM (lead → contatto →
  preventivo → trattativa → vinta/persa), con premio e provvigione stimati.
- **Statistiche**: premi, provvigioni e **rapporto S/P per ramo sugli ultimi
  12 mesi** (sinistri accaduti nel periodo su premi di competenza), premi per
  compagnia, incassi degli ultimi 12 mesi, premi in scadenza, primi 10 clienti,
  sinistri per tipologia e conversione della pipeline.

### Operatività quotidiana
- **Dashboard** con indicatori chiave e avvisi: scadenze future, polizze non
  ancora in vigore, termini di disdetta in arrivo, titoli arretrati, sinistri da
  denunciare, follow-up in ritardo, clienti senza consenso privacy.
- **Scadenzario** unificato di polizze, rate da incassare e follow-up, con
  un'**agenda** delle altre date da rispettare (decorrenze, termini di disdetta
  e di denuncia, sospensioni della copertura, documenti d'identità e
  questionari di adeguatezza in scadenza) ed **esportazione in calendario
  (.ics)** per Outlook, Google Calendar o il telefono.
- **Automatismi sulle date** (attivabili dalle *Impostazioni*, registrati come
  utente «sistema»): **rinnovo tacito** delle polizze arrivate a scadenza senza
  disdetta, **emissione delle quietanze** dell'annualità successiva con anticipo
  configurabile, **scadenza automatica** delle polizze non rinnovate dopo i
  giorni di tolleranza (con storno delle rate future).
- **Follow-up** con scadenza, tipo e priorità; i **follow-up di rinnovo**
  vengono generati automaticamente prima della scadenza delle polizze.
- **Notifiche automatiche** per polizze in scadenza (60/30/7 giorni e
  scadute), termini di disdetta, decorrenze imminenti con il primo premio da
  incassare, rate in scadenza o non pagate, coperture sospese e risoluzione
  dopo 6 mesi (art. 1901 c. 3), sinistri da denunciare o aperti da troppo
  tempo, documenti d'identità e questionari di adeguatezza in scadenza e
  follow-up. Le notifiche superate (rata incassata, sinistro denunciato…) si
  chiudono da sole.
- **Notifiche via email**: riepilogo automatico via SMTP configurabile dalla
  pagina *Impostazioni*. Vedi [Notifiche via email](#notifiche-via-email).
- **Ricerca globale** di clienti, polizze e sinistri ed **esportazione CSV**
  (compatibile con Excel) di clienti, polizze, titoli, foglio cassa, sinistri e
  registro attività. Tutte le liste sono paginate e filtrabili.

### Sicurezza e amministrazione
- **Accesso con utente e password**. Al primo avvio il gestionale chiede di
  creare l'**amministratore** (nessuna password predefinita).
- **Ruoli**: *Amministratore* (tutto, compresi utenti, impostazioni, backup e
  registro), *Operatore* (lavoro quotidiano), *Sola consultazione*.
- Password con hash (scrypt), **blocco dopo 5 tentativi errati** (15 minuti,
  contatore atomico, stesso messaggio per utente inesistente o password errata),
  protezione **CSRF** su tutti i form, cookie di sessione `HttpOnly` e
  `SameSite`, **sessioni revocabili** (uscita, cambio o reimpostazione della
  password, disattivazione, cambio di ruolo, ripristino di un backup),
  **Content-Security-Policy** senza script inline, header di sicurezza, chiave
  di sessione generata casualmente al primo avvio, protezione da redirect
  esterni e da *CSV injection*.
- **Date e importi validati**: date nell'intervallo 1900-2100 con regole su
  passato e futuro (es. incasso, denuncia e rimessa non future), importi in
  formato italiano (1.234,56) senza ambiguità; i moduli con errori conservano
  i dati inseriti.
- **Registro attività**: accessi (anche falliti), creazioni, modifiche,
  eliminazioni, incassi, storni, rinnovi, rimesse, esportazioni, backup e
  ripristini, con utente, data e IP; filtrabile ed esportabile.
- **Backup**: archivio ZIP con database e documenti scaricabile in un clic,
  **backup automatico giornaliero** con rotazione degli archivi e
  **ripristino** guidato (con copia di sicurezza dei dati attuali).
- Stampe con l'intestazione dello studio (ragione sociale, RUI, P.IVA),
  ottimizzate per A4 (tabelle intere, badge e righe di urgenza a colori).
- Interfaccia **responsive e accessibile**: etichette associate ai campi,
  pulsanti con nome leggibile dagli screen reader, contrasto WCAG AA, focus
  visibile da tastiera, nessun doppio invio dei moduli.

### Novità della 3.0

- **Rate da far pagare** (semestrali, trimestrali, mensili e quietanze
  annuali) nella lista «Da fare» di «Oggi», nelle notifiche e nel riepilogo
  email, anche quando il titolo non è ancora stato emesso. Giorni di
  preavviso di scadenze e rate scelti in *Impostazioni → Automatismi*.
- **Google Calendar collegato**: scadenze, disdette, rate, follow-up e
  promemoria scritti e aggiornati da soli in un calendario «Deal Combined»
  (vedi [PACKAGING.md](PACKAGING.md#google-gmail-drive-e-calendar)).
- **Avviso di pagamento** al cliente: lettera da stampare o email pronta, con
  importo, periodo, come pagare e art. 1901 c.c.; per le rate scadute diventa
  un sollecito che indica da quando la copertura è sospesa.
- **«Come impostare la trattativa»** dalla scheda del cliente: domande SPIN
  per il suo profilo, obblighi di legge, coperture scoperte con la leva di
  trattativa, obiezioni probabili, role-play e lezioni da ripassare.
- **Accademia per utente**: ognuno ha i suoi progressi; il titolare vede in
  «La squadra» a che punto è ogni consulente. Nuovo modulo «Correttezza e
  normativa in pratica», 10 obiezioni e 4 role-play per settore in più.

### Dalla versione Deal Combined

- **Persone fisiche con nome e cognome**: nascita, **residenza**, stato civile,
  nucleo familiare e interessi; per i professionisti anche la **sede
  dell'ordine** accanto ad albo, numero e data di iscrizione.
- **Note (diario delle attività)** divise per sezione e collegabili a un
  cliente, con **promemoria** (email dal proprio Gmail, evento in Google
  Calendar, notifica di Windows, voce nell'agenda di «Oggi»).
- **Amministratori e persone collegate**: amministratori, consiglieri, soci
  (con quota), legali rappresentanti, titolari effettivi, familiari… La
  ricerca trova un'azienda anche dal nome di un suo amministratore e ogni
  persona si può **gestire anche come cliente privato**. Il lavoratore
  dipendente si collega all'azienda cliente per cui lavora.
- **Preventivi nelle proposte**: compagnia, cosa prevedono, premio, validità,
  esito e file allegato (salvato anche tra i documenti del cliente).
- **Schede compilate nel cliente** («Compila scheda»), salvate con data e
  consulente, modificabili e stampabili.
- **Import da Excel** di clienti, polizze e amministratori, con anteprima.
- Pagina **«Oggi»** in stile agenda: cose da fare in ordine di urgenza, il
  **nastro rosso** sul prossimo passo, trattative aperte e allenamento del
  giorno, sopra gli indicatori del portafoglio.

## Accademia commerciale

Dal menu **Accademia** si accede a un percorso di **17 settimane** (un modulo a
settimana) che copre psicologia della decisione, comunicazione e PNL,
prospezione, marketing, primo contatto, raccolta delle informazioni,
correttezza e normativa in pratica (IDD, regolamenti IVASS, privacy,
antiriciclaggio, reclami), arte delle domande (SPIN, ascolto attivo), pensiero laterale e storytelling,
proposta e prezzo, obiezioni, negoziazione (metodo Harvard, Voss), chiusura,
continuità della trattativa, sviluppo del portafoglio dai clienti acquisiti e
organizzazione personale.

- **Lezioni** con teoria, punti chiave, esempio di dialogo ed esercizio sul
  campo; si segnano come completate e l'avanzamento è salvato.
- **Base scientifica** per ogni modulo: cosa conferma la ricerca, cosa è solo
  pratica professionale e quali miti evitare (es. movimenti oculari o regola
  7-38-55), con le fonti.
- **Quiz** con correzione spiegata e storico dei tentativi (soglia 70%).
- **Libreria delle obiezioni** (26, tra cui «ce l'ho con la banca», «mi copre
  l'INAIL», «ho la convenzione dell'ordine», «sono in affitto») con cosa nascondono, tecnica, risposta, rilancio
  e spunto di pensiero laterale; **allenamento quotidiano** a flashcard.
- **Role-play** (9, anche per settore: commercialista, medico ospedaliero,
  famiglia con mutuo, negozio): scenari a tre (consulente, cliente, osservatore) con trappole
  e domande di debrief.
- **Cassetta degli attrezzi**: le tecniche documentate con fonte e modulo.
- **Schede da stampare**: raccolta informazioni (privato e azienda), documenti
  da dare al cliente, preparazione dell'appuntamento, diario della trattativa,
  piano di negoziazione, registro obiezioni, griglia di role-play, revisione
  annuale, mappa delle referenze, piano settimanale e KPI, post-vendita.
- **Schede compilate nel cliente**: dalla scheda del cliente («Compila scheda»)
  le schede che riguardano il cliente si compilano direttamente nel gestionale,
  con anagrafica e polizze in essere già scritte. Restano salvate nella scheda
  **Schede** del cliente con data e consulente, si possono modificare e
  stampare compilate. Resta disponibile anche la versione vuota da stampare.

I contenuti sono in `gestionale/academy.py`. I riferimenti normativi (IDD,
Regolamenti IVASS, privacy) sono indicazioni formative: verifica sempre le
versioni vigenti e le procedure della tua compagnia o intermediario.

## Grafica, temi e dispositivi

La grafica predefinita segue il mondo dell'**agenda del consulente**, descritto
in [DESIGN.md](DESIGN.md): barra laterale verde come copertina, pagina «Oggi»
con la data in grande e un unico **nastro rosso** che segna il prossimo passo.

- **Aspetto** (menu dell'utente in alto a destra): ognuno sceglie il colore
  (*Agenda verde* predefinito, oppure blu, ottanio, smeraldo, viola, bordeaux,
  grafite) e la modalità **chiara, scura o come Windows**. Le stampe escono
  sempre chiare.
- **Dispositivi**: computer, tablet, telefono e pieghevoli.
- **Carattere**: Archivo (SIL Open Font License, `gestionale/static/vendor/fonts/Archivo-OFL.txt`),
  servito in locale per funzionare anche offline.
- Il contesto di prodotto per chi lavora alla grafica è in [PRODUCT.md](PRODUCT.md);
  la skill di design [Impeccable](https://github.com/pbakaus/impeccable) è inclusa
  in `.claude/skills/impeccable/`.

## Programma installato sul PC (Windows)

Deal Combined si installa come un normale programma con
`Installa-DealCombined.exe`: icona sul desktop e nel menu Start, **finestra
propria** (non il browser), funziona senza internet. I dati stanno in
`Documenti\Deal Combined`, con un backup automatico a ogni avvio. Il modo più
semplice per creare programma e installatore è un **doppio clic su
`CREA_EXE.bat`** su un PC Windows con Python 3.11–3.14 (per l'installatore
serve anche Inno Setup 6). In più: **icona vicino all'orologio** con le
notifiche di Windows, avvio con Windows, **PIN** con blocco per inattività,
**PDF** delle schede, **Gmail**, **Google Calendar** e **Google Drive**,
**aggiornamenti automatici** verificati e due modi per lavorare da **due PC**
(cartella dati condivisa oppure «Sincronizza PC»).
Tutti i dettagli in **[PACKAGING.md](PACKAGING.md)**.

## Requisiti

- Python 3.11+
- Flask e Flask-SQLAlchemy (vedi `requirements.txt`)

## Avvio rapido

```bash
pip install -r requirements.txt

python run_desktop.py
# si apre la finestra del programma
```

Per provare il gestionale con dati di esempio (clienti, polizze, titoli,
sinistri…) nella cartella `instance/`, con il server di sviluppo:

```bash
python seed_demo.py
python app.py
```

`run_desktop.py` è il modo consigliato per l'uso quotidiano (è lo stesso avvio
dell'eseguibile): usa il server [waitress](https://github.com/Pylons/waitress),
avvia lo **scheduler** (email automatiche e backup giornaliero), apre la
finestra del programma (o, se non è disponibile, una finestra di Edge) e salva
i dati in `Documenti\Deal Combined` (la cartella si cambia da *Impostazioni →
Dati e backup*; vedi [PACKAGING.md](PACKAGING.md#dove-sono-i-dati)).

Per lo sviluppo c'è anche `python app.py`, che usa il server di sviluppo di
Flask e salva i dati nella cartella `instance/` (esclusa dal versionamento).
Non usarlo in produzione né in rete; il debugger interattivo si attiva solo con
`FLASK_DEBUG=1 python app.py`. Con `flask --app app run` lo scheduler **non
parte**: niente email automatiche né backup giornaliero.

Al primo accesso il gestionale chiede di creare l'account **amministratore**;
gli altri utenti si aggiungono poi dalla pagina **Utenti**. Se l'unico
amministratore dimentica la password: `flask --app app reimposta-password NOMEUTENTE`
(con l'eseguibile: `DealCombined.exe --reimposta-password NOMEUTENTE`).

## Configurazione

Variabili d'ambiente supportate:

| Variabile               | Default                              | Descrizione                                         |
|-------------------------|--------------------------------------|-----------------------------------------------------|
| `SECRET_KEY`            | generata e salvata al primo avvio    | Chiave di sessione Flask                            |
| `SECRET_KEY_FILE`       | `<instance>/secret_key`              | Dove salvare la chiave generata                     |
| `DATABASE_URL`          | `sqlite:///<instance>/gestionale.db` | URI del database SQLAlchemy                         |
| `UPLOAD_FOLDER`         | `<instance>/uploads`                 | Cartella dei documenti caricati                     |
| `BACKUP_FOLDER`         | `<instance>/backups`                 | Cartella dei backup automatici                      |
| `SESSION_COOKIE_SECURE` | `false`                              | `true` se il gestionale è servito in HTTPS          |
| `PORT`                  | `5000`                               | Solo `run_desktop.py`/eseguibile: porta preferita   |

`<instance>` è la cartella `instance/` del progetto (con `python app.py`); con
`run_desktop.py` e con l'eseguibile i quattro percorsi stanno nella cartella
dati. Un percorso SQLite relativo in `DATABASE_URL` (es. `sqlite:///gestionale.db`)
e i percorsi relativi di `UPLOAD_FOLDER` e `BACKUP_FOLDER` sono risolti
rispetto a `instance/`.

> **In rete**: il server integrato ascolta solo su `127.0.0.1`. Per usarlo da
> più postazioni pubblicalo dietro un reverse proxy **HTTPS** (es. Caddy o
> nginx) e imposta `SESSION_COOKIE_SECURE=true`.

### Notifiche via email

Le email si configurano dalla pagina **Impostazioni** (icona ingranaggio in alto
a destra): server SMTP, porta, sicurezza (STARTTLS/SSL), utente, password,
mittente e destinatari. Da lì puoi **attivare l'invio automatico**, mandare
un'**email di prova** e **inviare subito** il riepilogo delle notifiche in
attesa. Lo scheduler in background genera le notifiche e invia un unico *digest*
delle novità con la cadenza scelta (campo «Controllo automatico ogni N minuti»,
da 1 a 1440). Un solo invio alla volta: se premi «Invia ora» mentre lo
scheduler sta spedendo, le stesse notifiche non partono due volte. I dati
inseriti dagli utenti (nomi dei clienti, titoli dei follow-up…) compaiono
nell'email HTML sempre come testo, mai come codice.

In alternativa (o in produzione) i parametri SMTP possono arrivare da variabili
d'ambiente, che **hanno la precedenza** su quanto salvato nel database:

| Variabile        | Esempio                     | Descrizione                                   |
|------------------|-----------------------------|-----------------------------------------------|
| `EMAIL_ATTIVE`   | `true`                      | Attiva l'invio automatico                     |
| `SMTP_HOST`      | `smtp.gmail.com`            | Server SMTP                                    |
| `SMTP_PORT`      | `587`                       | Porta                                          |
| `SMTP_SECURITY`  | `tls`                       | `tls` (STARTTLS), `ssl` oppure `none`         |
| `SMTP_USER`      | `mario@gmail.com`           | Utente SMTP                                    |
| `SMTP_PASSWORD`  | `app-password`              | Password (per Gmail: *App Password*)          |
| `MAIL_FROM`      | `gestionale@studio.it`      | Indirizzo mittente                            |
| `MAIL_TO`        | `titolare@studio.it, ...`   | Destinatari (separati da virgola)             |
| `APP_BASE_URL`   | `http://127.0.0.1:5000`     | Base per i link «Apri scheda» nelle email     |

### Backup e ripristino

Da **Impostazioni → Backup** l'amministratore può scaricare un backup completo
(database + documenti in un unico ZIP), salvarne uno nella cartella dei backup,
configurare il **backup automatico giornaliero** (attivo di default, ultimi 14
archivi conservati) e **ripristinare** un archivio.

- Il backup automatico parte al primo controllo di ogni giornata di calendario
  (anche se il programma viene aperto ogni giorno a orari diversi); una data
  dell'ultimo backup nel futuro, dovuta a un orologio corretto, non lo blocca.
- Gli archivi vengono scritti con un nome temporaneo e rinominati solo quando
  sono completi: un'interruzione non lascia archivi troncati nell'elenco.
- Il download dal browser non lascia copie dei dati nella cartella temporanea
  del sistema.
- Prima di ogni ripristino viene salvata una copia di sicurezza dei dati attuali
  (`pre_ripristino_…zip`), elencata tra i backup salvati; se ne conservano le
  ultime 5, a parte rispetto ai backup giornalieri.
- Il ripristino accetta solo archivi creati dal gestionale (database,
  `manifest.json` e documenti in `uploads/`: niente percorsi assoluti, `..` o
  collegamenti) con un database valido che contenga almeno un amministratore
  attivo. Al termine **tutti gli utenti vengono disconnessi** e si accede con le
  credenziali presenti nel backup.

Conserva periodicamente una copia dei backup su un disco esterno o in cloud.


### Documenti in cartelle

Nella scheda del cliente i documenti sono divisi in **cartelle**: documenti
personali (carta d'identità, codice fiscale, patente…), documenti azienda
(visura camerale, statuto, bilancio, DURC…), documenti professionali, polizze e
contratti, sinistri, veicoli, privacy e adeguatezza. Il tipo di documento
scelto al caricamento decide la cartella; si possono anche creare **cartelle
proprie** (es. «Pratica mutuo 2025») e **spostare** i file. L'archivio generale
filtra per cartella e per tipo.

### Aspetto

Dal menu utente → **Aspetto** ognuno sceglie il proprio **tema di colore** (blu,
ottanio, verde smeraldo, viola, bordeaux, grafite) e la **modalità chiara,
scura o «come Windows»**. Il programma ha una sua icona e, nella versione
desktop, la finestra riapre con la dimensione e la posizione dell'ultima volta.

### Due PC: «Sincronizza PC»

Per chi lavora su più computer (es. un fisso a casa e un portatile), uno alla
volta. Dal menu **Sincronizza PC** (amministratori):

1. su ogni PC scegli una **cartella di sincronizzazione**: una chiavetta USB
   o una cartella di OneDrive, Dropbox o Google Drive;
2. a fine lavoro premi **«Salva per l'altro PC»**: tutti i dati (documenti
   compresi) finiscono in `gestionale_sincronizzazione.zip` nella cartella;
3. sull'altro PC premi **«Carica dall'altro PC»** (la dashboard lo ricorda
   quando c'è un pacchetto nuovo), poi accedi di nuovo.

Protezioni: se su questo PC ci sono modifiche successive all'ultima
sincronizzazione, il caricamento chiede conferma; se nella cartella c'è un
pacchetto dell'altro PC non ancora caricato, il salvataggio chiede conferma.
Il pacchetto precedente resta come `gestionale_sincronizzazione_precedente.zip`
e ogni caricamento crea prima una copia di sicurezza dei dati attuali. Non è
una fusione: vince sempre l'ultimo pacchetto caricato.

## Struttura

```
app.py                     # avvio per lo sviluppo (server di Flask, senza scheduler con `flask run`)
run_desktop.py             # avvio «desktop» consigliato: cartella dati, istanza unica, finestra propria o browser (usato dall'exe)
seed_demo.py               # dati di esempio
gestionale.spec            # ricetta PyInstaller per l'eseguibile
gestionale/
  __init__.py              # application factory, filtri, errori e micro-migrazioni
  models.py                # modelli e vocabolari (clienti, polizze, titoli, sinistri, utenti…)
  security.py              # accesso, ruoli, CSRF, redirect sicuri, registro attività
  titoli.py                # annualità (poliennali, rateo), generazione delle rate, rinnovi
  automatismi.py           # rinnovo tacito, emissione quietanze, scadenza automatica
  agenda.py                # agenda delle scadenze future ed esportazione iCalendar
  validators.py            # codice fiscale, partita IVA, CAP, provincia, email
  backup.py                # backup ZIP, backup automatico e ripristino
  export.py                # esportazione CSV per Excel
  risk_engine.py           # motore di analisi automatica dei rischi
  notifications.py         # notifiche da scadenze, rate, sinistri e follow-up
  mailer.py                # invio email (SMTP stdlib) e digest notifiche
  scheduler.py             # thread in background: automatismi, notifiche, email e backup
  routes/                  # blueprint: auth, main (dashboard, ricerca, statistiche),
                           #   clients, policies, titles, claims, documents, followups,
                           #   opportunities, notifications, settings, users, audit
  templates/               # interfaccia (Bootstrap 5)
  static/style.css, app.js # tema grafico e comportamenti dell'interfaccia
  static/vendor/           # Bootstrap e icone in locale (funziona offline)
tests/                     # test automatici (pytest): conftest con le fixture comuni
.github/workflows/build.yml # CI: test + build eseguibile Windows
```

## Test

```bash
pip install -r requirements-dev.txt
python -m pytest
```

## Come funziona l'analisi dei rischi

Il motore (`gestionale/risk_engine.py`) confronta la descrizione dell'attività
con un insieme di **regole a parole chiave** (radici, confronto senza accenti e
maiuscole). Ogni regola rappresenta un pericolo, con severità calcolata dal
numero di riscontri e potenziata dai dati strutturati (es. numero di dipendenti
→ rischio infortuni, fatturato elevato → D&O). A queste si aggiungono
raccomandazioni di base per tipo di cliente (es. catastrofali e tutela legale
per le aziende, multirischi e cyber per gli studi, RC capofamiglia e casa per i
privati), gli **obblighi di legge della professione** (in testa, con la norma) e
le estensioni richieste dalle attività svolte (incarichi giudiziari, sindaco e
revisore, attività chirurgiche, direzione lavori, asseverazioni…). Infine i
rami consigliati vengono confrontati con quelli delle polizze attive per la gap
analysis. Il risultato è **sempre spiegabile** e non richiede servizi esterni.

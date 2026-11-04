# Deal Combined come programma installato sul PC

Deal Combined si installa come un normale programma Windows: icona sul desktop
e nel menu Start, finestra propria (non il browser), disinstallazione da
*Impostazioni di Windows → App*. Funziona senza internet e salva tutto sul PC.

## Aggiornare dalla versione 2.x (dati già presenti)

Installando la versione 3.0 sopra quella già presente, **i dati restano in
`Documenti\Deal Combined`**: all'avvio il programma fa il solito backup in
`Backup\` e poi aggiunge da solo le colonne e le tabelle nuove (titoli,
sinistri, utenti…), senza toccare clienti, polizze, note, preventivi, schede e
progressi dell'Accademia. Alla prima apertura chiede di **creare l'utente
amministratore** (nome utente e password): da lì in poi si entra con utente e
password, e il **PIN**, se impostato, resta per il blocco dopo i minuti di
inattività. Altri utenti (operatori, sola consultazione) si aggiungono dal menu
**Utenti**.

Password dimenticata dell'unico amministratore: chiudi il programma e da
*Prompt dei comandi* lancia
`"%LOCALAPPDATA%\Programs\Deal Combined\DealCombined.exe" --reimposta-password NOMEUTENTE`
(il percorso è quello dell'installazione; con il solo `.exe` usa il suo percorso).

## Dove sono i dati

- **Cartella:** `Documenti\Deal Combined`. Se Windows ha spostato Documenti
  dentro OneDrive, la cartella è lì.
  - `gestionale.db`: clienti, polizze, schede, trattative, progressi dell'Accademia;
  - `uploads\`: i documenti caricati;
  - `Backup\`: copie automatiche del database, una a ogni avvio, conservate le ultime 10,
    più i backup completi (database e documenti) giornalieri e prima di ogni ripristino;
  - `deal-combined.log`: messaggi tecnici del programma, utili in caso di problemi.
- **Disinstallare il programma non cancella i dati.**
- **Versioni precedenti:** se i dati stavano accanto all'eseguibile, nella
  cartella `dati_gestionale`, al primo avvio vengono copiati nella nuova
  cartella automaticamente.
- **Gestione:** da *Impostazioni → Dati e backup* vedi dove sono i dati, fai
  un backup al volo, esporti o importi l'archivio e sposti la cartella.

## Usarlo da due PC

Ogni PC ha il suo archivio. Per lavorare con gli stessi dati su due PC ci
sono due modi.

1. **Cartella sincronizzata (automatico).** Su entrambi i PC, in
   *Impostazioni → Dati e backup → Sposta la cartella dati*, indica la stessa
   cartella di OneDrive, Google Drive o Dropbox, poi chiudi e riapri il
   programma. Sul primo PC lascia spuntato «Copia lì i dati attuali»; sul
   secondo il programma troverà l'archivio già presente e userà quello.
   - **Un PC alla volta:** il database non va aperto su due PC nello stesso
     momento. Deal Combined scrive nella cartella su quale PC è aperto: se
     provi ad aprirlo sull'altro, ti avvisa e ti chiede di chiuderlo prima.
     Prima di passare all'altro PC aspetta che la sincronizzazione sia finita.
   - **Chiusura anomala:** se il programma si è chiuso male, ad esempio per
     un PC spento di colpo, dopo 3 minuti l'avviso non compare più.
   - **Finestra chiusa = archivio libero:** chiudendo la finestra il
     programma resta solo come icona vicino all'orologio (per i promemoria)
     e l'archivio risulta libero, quindi puoi aprirlo sull'altro PC.
2. **Archivio da portare (manuale).** *Esporta archivio* crea un unico `.zip`
   con database e documenti. Sull'altro PC usa *Importa*. Prima di sostituire
   i dati viene salvata una copia completa di quelli attuali in `Backup\`.
3. **«Sincronizza PC» (a fine lavoro).** Dal menu *Amministrazione →
   Sincronizza PC* scegli una cartella comune (chiavetta USB, OneDrive,
   Dropbox, Google Drive). A fine lavoro clicca **«Salva per l'altro PC»**;
   sull'altro PC clicca **«Carica dall'altro PC»**. Il programma avvisa se
   rischi di sovrascrivere modifiche non ancora portate dall'altra parte e fa
   sempre prima una copia di sicurezza.

## Icona vicino all'orologio e promemoria

- Chiudendo la finestra (la X), Deal Combined **resta attivo come icona**
  vicino all'orologio di Windows. Doppio clic o *Apri Deal Combined* la
  riapre; tasto destro → **Esci** chiude davvero il programma.
- Ogni 15 minuti controlla i **follow-up di oggi o in ritardo** e le
  **polizze che scadono entro 7 giorni** e, se c'è qualcosa di nuovo, mostra
  una notifica di Windows (una sola volta al giorno per ogni voce).
- Con la finestra chiusa il gestionale non scrive nulla nell'archivio (le
  email automatiche ripartono alla riapertura) e, se è attivo il PIN, alla
  riapertura lo richiede.
- **Avvio con Windows:** si sceglie durante l'installazione o in
  *Impostazioni → Programma*. All'accensione del PC parte solo l'icona, senza
  aprire la finestra.
- Se apri il programma mentre è già nella barra, si riapre la finestra
  esistente invece di avviarne un secondo.

## PIN e privacy

*Impostazioni → Privacy*: un PIN (4–12 cifre) chiesto all'apertura e dopo i
minuti di inattività scelti, con un pulsante **Blocca ora** in alto. Al
momento di impostarlo il programma mostra **una sola volta** un codice di
recupero: conservalo, serve se dimentichi il PIN. Dopo 5 tentativi sbagliati
bisogna attendere un minuto. Il PIN protegge lo schermo, non i file: per
proteggere i dati se il portatile viene perso serve **BitLocker**, di cui la
stessa pagina mostra lo stato.

## Google: Gmail, Drive e Calendar

Da *Impostazioni → Google*. Gmail e Drive non richiedono di registrare app su
Google Cloud; il collegamento diretto a Calendar sì (una volta sola, guida
passo passo nella pagina).

- **Gmail:** le schede compilate si inviano al cliente come PDF allegato
  (pulsante *Invia per email* nella scheda), con una *password per le app*
  di Google. Le email compaiono in «Posta inviata».
- **Google Drive:** con *Google Drive per desktop* installato, i PDF si
  salvano in `Il mio Drive\Deal Combined\Clienti\<cliente>` e Drive li carica.
  La cartella si imposta per ogni PC.
- **Google Calendar collegato:** Deal Combined scrive da solo, in un
  calendario «Deal Combined» del tuo account, scadenze delle polizze, ultimi
  giorni per la disdetta, rate da far pagare (annuali e frazionate), follow-up
  e promemoria delle note. Li aggiorna quando cambiano e li toglie quando sono
  fatti o incassati, a ogni controllo automatico (ogni 30 minuti di base) o
  con *Aggiorna adesso*. I promemoria di Calendar arrivano ai giorni di
  preavviso scelti in *Impostazioni → Automatismi* (Google ne accetta fino a 4
  settimane prima). Configurazione, una volta sola:
  1. su **console.cloud.google.com** crea un progetto e abilita la
     **Google Calendar API**;
  2. nella **schermata di consenso OAuth** scegli *Esterno*, poi
     **pubblica l'app** («In produzione»): se resta «In prova» Google
     interrompe il collegamento ogni 7 giorni;
  3. in **Credenziali** crea un **ID client OAuth** di tipo **App desktop** e
     copia ID e secret in Deal Combined;
  4. premi **Collega Google Calendar**: si apre il browser, accedi e consenti
     (Google avvisa che l'app non è verificata: è la tua, *Avanzate → Vai a
     Deal Combined*).
  Il programma chiede solo il permesso sui **calendari che crea lui**: gli
  altri tuoi calendari restano invisibili. Due PC con lo stesso archivio non
  creano doppioni.
- **Senza collegamento:** ogni follow-up aperto ha un pulsante che apre
  Calendar con l'evento già compilato; *Scarica il calendario (.ics)* li
  importa tutti.

## Note e promemoria

Il menu **Note** è il diario delle attività: ogni cosa fatta (o da fare) è una
nota singola con giorno, ora, sezione e, se serve, il cliente. Le note si
vedono giorno per giorno, si filtrano per sezione, cliente e periodo e si
cercano; ogni cliente ha anche la sua scheda *Note*.

Ogni nota può avere un **promemoria**:

- **Email:** all'ora scelta Deal Combined manda un'email dal tuo Gmail
  (impostato in *Impostazioni → Google*), anche con la finestra chiusa vicino
  all'orologio. Se usi due PC con la cartella condivisa, l'email parte una
  volta sola. Se il PC è spento all'ora del promemoria, l'email non parte
  (dopo 6 ore non viene più mandata).
- **Google Calendar:** il pulsante della nota apre Calendar con l'evento già
  compilato all'ora del promemoria: premi *Salva* e Google ti avvisa anche sul
  telefono, pure a PC spento. *Promemoria in Calendar (.ics)* li esporta
  tutti in una volta.
- **Windows e «Oggi»:** all'ora del promemoria arriva anche una notifica di
  Windows e la voce compare nell'agenda di *Oggi* finché non premi *Fatto*.

## Importare clienti e polizze da Excel

*Clienti → Importa da Excel*: scarica il modello (fogli *Clienti*, *Polizze*
e *Amministratori*; le persone con nome, cognome, nascita, residenza e albo;
menu a tendina per ramo, stato, ruolo e frazionamento) oppure carica il tuo
Excel/CSV: le intestazioni comuni (Ragione sociale, P.IVA, Compagnia,
N. polizza, Scadenza…) sono riconosciute. Prima vedi un'**anteprima** con
nuovi, già presenti ed errori riga per riga; niente viene salvato finché non
confermi. I clienti esistenti non vengono sovrascritti (si completano solo i
campi vuoti), le polizze già presenti si saltano e prima dell'importazione si
fa un backup.

## Aggiornamenti

*Impostazioni → Programma* mostra la versione installata e, all'avvio,
controlla se su GitHub c'è una versione nuova (si può disattivare): in quel
caso compare un'icona verde in alto. *Scarica e installa* fa un backup,
scarica l'installatore, **ne verifica l'impronta SHA-256**, chiude il
programma, lo aggiorna e lo riapre. I dati non vengono toccati.

**Per pubblicare una versione:**
1. aggiorna `__version__` in `gestionale/__init__.py` (es. `2.2.0`);
2. esegui `build_windows.bat`: crea `dist\Installa-DealCombined.exe` e
   `dist\Installa-DealCombined.exe.sha256`;
3. su GitHub crea una *Release* con tag `v2.2.0` e allega **entrambi** i file.
   Senza il file `.sha256` il programma mostra solo il link alla pagina della
   versione, senza installare nulla.

In alternativa, se GitHub Actions è attivo, basta creare e spingere il tag
`v2.2.0`: il workflow compila e pubblica la Release con i due file.

## Ottenere l'installatore

Serve un PC Windows. PyInstaller non sa creare un `.exe` Windows partendo da
Linux o macOS.

### Opzione A: sul tuo PC con un doppio clic

1. Installa **Python da 3.11 a 3.14** da python.org e, durante
   l'installazione, spunta *Add Python to PATH*.
2. Installa **Inno Setup 6**, gratuito: https://jrsoftware.org/isinfo.php
   (serve solo per l'installatore).
3. Nella cartella del progetto fai doppio clic su **`CREA_EXE.bat`**: prepara
   un ambiente separato (`.venv-build`), installa i componenti, crea il
   programma e, se trova Inno Setup, l'installatore. Alla fine apre la
   cartella `dist\`. (`build_windows.bat` fa lo stesso con il Python nel PATH.)

Alla fine trovi in `dist\`:

- **`Installa-DealCombined.exe`**: l'installatore da usare e da dare agli
  altri consulenti;
- **`DealCombined.exe`**: il programma da solo, utile per provarlo senza
  installarlo.

### Opzione B: su GitHub

Il workflow [`.github/workflows/build.yml`](.github/workflows/build.yml) fa le
stesse cose su un computer Windows di GitHub: esegue i test, crea `.exe` e
installatore e li pubblica nell'artifact **`DealCombined-windows`**.

- **Come lanciarlo:** *Actions → «Test e build» → Run workflow*, oppure
  pubblicando un tag (es. `v3.0.0`).
- **Requisito:** GitHub Actions deve essere attivo sul repository
  (*Settings → Actions*) e l'account deve avere minuti o fatturazione
  disponibili (*Settings → Billing*). Altrimenti il job si chiude in pochi
  secondi senza fare nulla.

## Provare senza compilare

```bash
pip install -r requirements.txt
python run_desktop.py
```

Senza `pywebview` installato, l'app si apre nel browser. In quel caso si chiude
con **Chiudi Deal Combined** in fondo alla barra laterale.

## Come è fatto

- **`run_desktop.py`** è il punto di ingresso:
  - sceglie la cartella dati, copia lì quelli delle versioni precedenti;
  - fa il backup, scrive e aggiorna il blocco tra PC;
  - avvia il server locale ([waitress](https://github.com/Pylons/waitress)) e
    apre la finestra con [pywebview](https://pywebview.flowrl.com/), che usa
    Edge WebView2, già presente in Windows 10 e 11;
  - se la finestra non è disponibile, o se all'avvio precedente si era chiusa
    da sola appena aperta, usa una finestra di Microsoft Edge in modalità
    applicazione (senza barra degli indirizzi né schede); in mancanza, il browser.
- **`gestionale/desktop.py`**: cartella dati, file di configurazione dell'utente
  (`%APPDATA%\Deal Combined\config.json`), backup, blocco tra PC.
- **`gestionale/archivio.py`**: esporta e importa l'archivio `.zip`, con
  controlli su contenuto, percorsi e dimensione.
- **`gestionale.spec`**: ricetta di PyInstaller. Produce `DealCombined.exe`
  senza finestra di console, con l'icona `installer/deal-combined.ico`.
- **`installer/DealCombined.iss`**: installatore Inno Setup. L'installazione è
  per il solo utente, quindi non chiede permessi da amministratore. Crea le
  icone su desktop e menu Start e non tocca mai la cartella dati.
- **Sicurezza:** il server ascolta solo su `127.0.0.1`, quindi non è
  raggiungibile da altri dispositivi. Si entra con utente e password (ruoli
  amministratore, operatore, sola consultazione), ogni modulo porta un codice
  anti-CSRF, le richieste di modifica che arrivano da altri siti vengono
  rifiutate e le pagine accettano solo i propri script (Content Security Policy).

## Risoluzione problemi

- **Avviso di Windows SmartScreen o dell'antivirus.** Eseguibile e
  installatore non sono firmati digitalmente. Scegli *Ulteriori informazioni →
  Esegui comunque*. Per farlo sparire serve un certificato di firma del
  codice.
- **Si apre una finestra di Edge invece di quella del programma.** La finestra
  nativa non è partita (manca Edge WebView2, raro su Windows 10 e 11, oppure
  si è chiusa da sola all'avvio precedente). Funziona allo stesso modo.
  Chiudendo la finestra l'archivio si libera per l'altro PC e il programma
  resta pronto: un nuovo doppio clic sull'icona riapre la finestra. Per
  chiuderlo del tutto usa **Chiudi Deal Combined** in fondo alla barra
  laterale. Con la versione successiva del programma si riprova la finestra
  nativa.
- **Il programma non parte.** Guarda `Documenti\Deal Combined\deal-combined.log`.
- **Email:** si configurano da *Impostazioni → Generali ed email*. Le variabili
  d'ambiente equivalenti sono elencate nel README.

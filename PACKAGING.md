# Deal Combined come programma installato sul PC

Deal Combined si installa come un normale programma Windows: icona sul desktop
e nel menu Start, finestra propria, disinstallazione da *Impostazioni di
Windows → App*. Funziona senza internet e salva tutto sul PC.

## Dove sono i dati

- **Cartella:** `Documenti\Deal Combined`. Se Windows ha spostato Documenti
  dentro OneDrive, la cartella è lì.
  - `gestionale.db`: clienti, polizze, schede, trattative, progressi dell'Accademia;
  - `uploads\`: i documenti caricati;
  - `Backup\`: copie automatiche del database, una a ogni avvio, conservate le ultime 10;
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
2. **Archivio da portare (manuale).** *Esporta archivio* crea un unico `.zip`
   con database e documenti. Sull'altro PC usa *Importa*. Prima di sostituire
   i dati viene salvata una copia completa di quelli attuali in `Backup\`.

## Ottenere l'installatore

Serve un PC Windows. PyInstaller non sa creare un `.exe` Windows partendo da
Linux o macOS.

### Opzione A: sul tuo PC con un doppio clic

1. Installa **Python 3.11 o più recente** da python.org e, durante
   l'installazione, spunta *Add Python to PATH*.
2. Installa **Inno Setup 6**, gratuito: https://jrsoftware.org/isinfo.php
3. Nella cartella del progetto fai doppio clic su **`build_windows.bat`**.

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
  pubblicando un tag (es. `v2.0.0`).
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
  - se la finestra non è disponibile, apre il browser.
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
  raggiungibile da altri dispositivi. Le richieste di modifica che arrivano da
  altri siti aperti nel browser vengono rifiutate.

## Risoluzione problemi

- **Avviso di Windows SmartScreen o dell'antivirus.** Eseguibile e
  installatore non sono firmati digitalmente. Scegli *Ulteriori informazioni →
  Esegui comunque*. Per farlo sparire serve un certificato di firma del
  codice.
- **Si apre il browser invece della finestra.** Manca Edge WebView2, raro su
  Windows 10 e 11. Installalo da Microsoft (*WebView2 Runtime*) oppure usa
  Deal Combined nel browser: funziona allo stesso modo.
- **Il programma non parte.** Guarda `Documenti\Deal Combined\deal-combined.log`.
- **Email:** si configurano da *Impostazioni → Notifiche email*. Le variabili
  d'ambiente equivalenti sono elencate nel README.

# Deal Combined

Gestionale web per intermediari assicurativi che seguono **professionisti e
aziende**. Permette di raccogliere in un unico posto anagrafiche, polizze e
documenti, di **analizzare automaticamente i pericoli** a partire dalla
descrizione dell'attività, e di non perdere **scadenze e follow-up** grazie a
notifiche generate in automatico.

## Funzionalità

- **Anagrafica clienti** — aziende, professionisti **e lavoratori dipendenti**
  (con datore di lavoro e mansione): dati fiscali, contatti, sede, settore,
  dipendenti, fatturato e descrizione dettagliata dell'attività. Il form adatta
  i campi al tipo di cliente selezionato.
- **Polizze**: compagnia, ramo, massimale, premio, **percentuale di provvigione**,
  frazionamento, decorrenza, scadenza, tacito rinnovo e stato; oltre 20 rami
  precompilati.
- **Archivio documenti**: caricamento **multiplo con drag & drop**, download ed
  eliminazione di file (polizze, preventivi, visure, sinistri, GDPR…), con
  dimensione e icona per tipo, collegabili a una polizza.
- **Analisi automatica dei rischi**: un motore a regole in italiano legge la
  descrizione dell'attività (più i dati di anagrafica) e produce:
  - i **pericoli rilevati** con severità e parole chiave che li hanno attivati;
  - le **coperture consigliate** per ciascun pericolo;
  - per ogni copertura uno **spunto di trattativa** con pensiero laterale,
    esempio in terza persona e vantaggi da portare in trattativa;
  - la **gap analysis** tra coperture consigliate e polizze già attive, con la
    possibilità di trasformare una copertura scoperta in un'**opportunità** con
    un clic. Ogni analisi è salvata nello storico ed è stampabile.
- **Pipeline commerciale (opportunità)**: gestione delle opportunità di vendita
  a fasi in stile CRM (lead → contatto → preventivo → trattativa → vinta/persa),
  con premio e provvigione stimati, alimentabile direttamente dai gap di copertura.
- **Statistiche di portafoglio**: cruscotto con premi e provvigioni per ramo,
  clienti per tipo, valore della pipeline e premi in scadenza nei 12 mesi.
- **Ricerca globale** di clienti e polizze dalla barra in alto.
- **Follow-up**: attività con scadenza, tipo e priorità; i **follow-up di
  rinnovo** vengono generati automaticamente prima della scadenza delle polizze.
- **Scadenzario** unificato di polizze e follow-up, con evidenza delle urgenze.
- **Notifiche automatiche**: generate a ogni accesso per polizze in scadenza
  (preavviso a 60/30/7 giorni e polizze scadute) e per follow-up in arrivo,
  odierni o in ritardo. Deduplicate per non ripetersi.
- **Notifiche via email**: oltre a quelle in-app, l'applicazione può inviare in
  automatico un **riepilogo via email** (SMTP configurabile dalla pagina
  *Impostazioni*, con email di prova e invio manuale). Uno scheduler in
  background controlla le scadenze a intervalli regolabili. Vedi
  [Notifiche via email](#notifiche-via-email).
- **Dashboard** con indicatori chiave, prossime scadenze e follow-up.
- **Accademia commerciale**: programma di apprendimento per consulenti
  assicurativi centrato sul *mestiere* più che sui prodotti. Vedi
  [Accademia commerciale](#accademia-commerciale).

## Accademia commerciale

Dal menu **Accademia** si accede a un percorso di **16 settimane** (un modulo a
settimana) che copre psicologia della decisione, comunicazione e PNL,
prospezione, marketing, primo contatto, raccolta delle informazioni, arte
delle domande (SPIN, ascolto attivo), pensiero laterale e storytelling,
proposta e prezzo, obiezioni, negoziazione (metodo Harvard, Voss), chiusura,
continuità della trattativa, sviluppo del portafoglio dai clienti acquisiti e
organizzazione personale.

- **Lezioni** con teoria, punti chiave, esempio di dialogo ed esercizio sul
  campo; si segnano come completate e l'avanzamento è salvato.
- **Base scientifica** per ogni modulo: cosa conferma la ricerca, cosa è solo
  pratica professionale e quali miti evitare (es. movimenti oculari o regola
  7-38-55), con le fonti.
- **Quiz** con correzione spiegata e storico dei tentativi (soglia 70%).
- **Libreria delle obiezioni** con cosa nascondono, tecnica, risposta, rilancio
  e spunto di pensiero laterale; **allenamento quotidiano** a flashcard.
- **Role-play**: scenari a tre (consulente, cliente, osservatore) con trappole
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

La grafica segue il mondo dell'**agenda del consulente**, descritto in
[DESIGN.md](DESIGN.md): barra laterale verde come copertina, pagina «Oggi» con
la data in grande e un unico **nastro rosso** che segna il prossimo passo (la
prossima attività, la trattativa da muovere, il prossimo follow-up del cliente,
la prossima lezione dell'Accademia).

- **Tema chiaro e scuro**: all'apertura segue il sistema; il pulsante nella
  barra superiore alterna automatico → chiaro → scuro e la scelta resta nel
  browser. Le stampe escono sempre chiare.
- **Dispositivi**: computer, tablet, telefono e pieghevoli. Sui pieghevoli con
  cerniera (due pannelli affiancati) la pagina «Oggi» mette la lista su un
  pannello e trattative/portafoglio sull'altro, lasciando libera la piega
  (CSS *viewport segments*).
- **Carattere**: Archivo (SIL Open Font License, `gestionale/static/vendor/fonts/Archivo-OFL.txt`),
  servito in locale per funzionare anche offline.
- Il contesto di prodotto per chi lavora alla grafica è in [PRODUCT.md](PRODUCT.md);
  la skill di design [Impeccable](https://github.com/pbakaus/impeccable) è inclusa
  in `.claude/skills/impeccable/`.

## Programma installato sul PC (Windows)

Deal Combined si installa come un normale programma, con
`Installa-DealCombined.exe`: icona sul desktop e nel menu Start, finestra
propria, funziona senza internet. I dati stanno in `Documenti\Deal Combined`,
con un backup automatico a ogni avvio. Da *Impostazioni → Dati e backup* si
esporta o importa l'archivio e si può spostare la cartella dati in OneDrive o
Google Drive per usarlo da **due PC**: un avviso impedisce di aprirlo su
entrambi nello stesso momento. L'installatore si crea con `build_windows.bat`.
Tutti i dettagli in **[PACKAGING.md](PACKAGING.md)**.

## Requisiti

- Python 3.11+
- Flask e Flask-SQLAlchemy (vedi `requirements.txt`)

## Avvio rapido

```bash
pip install -r requirements.txt

# (opzionale) carica dati di esempio: 3 clienti, polizze, follow-up e analisi
python seed_demo.py

python app.py
# apri http://127.0.0.1:5000
```

Il database SQLite e i documenti caricati vengono salvati nella cartella
`instance/` (esclusa dal versionamento).

## Configurazione

Variabili d'ambiente supportate:

| Variabile        | Default                              | Descrizione                          |
|------------------|--------------------------------------|--------------------------------------|
| `SECRET_KEY`     | `dev-cambiami-in-produzione`         | Chiave di sessione Flask             |
| `DATABASE_URL`   | `sqlite:///instance/gestionale.db`   | URI del database SQLAlchemy          |
| `UPLOAD_FOLDER`  | `instance/uploads`                   | Cartella dei documenti caricati      |

### Notifiche via email

Le email si configurano dalla pagina **Impostazioni** (icona ingranaggio in alto
a destra): server SMTP, porta, sicurezza (STARTTLS/SSL), utente, password,
mittente e destinatari. Da lì puoi **attivare l'invio automatico**, mandare
un'**email di prova** e **inviare subito** il riepilogo delle notifiche in
attesa. Lo scheduler in background genera le notifiche e invia un unico *digest*
delle novità con la cadenza scelta (campo «Controllo automatico ogni N minuti»).

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

## Struttura

```
app.py                     # entry point (server di sviluppo)
run_desktop.py             # avvio del programma installato: finestra propria, dati in Documenti
seed_demo.py               # dati di esempio
gestionale.spec            # ricetta PyInstaller per l'eseguibile
build_windows.bat          # crea DealCombined.exe e l'installatore
installer/                 # installatore Inno Setup e icona
gestionale/
  __init__.py              # application factory, filtri e micro-migrazioni
  models.py                # modelli e vocabolari (rami, categorie, Settings…)
  risk_engine.py           # motore di analisi automatica dei rischi
  academy.py               # contenuti dell'Accademia commerciale
  schede.py                # schede compilabili: campi, precompilazione
  desktop.py               # programma installato: cartella dati, backup, blocco tra PC
  archivio.py              # esporta/importa l'archivio .zip
  notifications.py         # generazione notifiche da scadenze e follow-up
  mailer.py                # invio email (SMTP stdlib) e digest notifiche
  scheduler.py             # thread in background per l'invio automatico
  routes/                  # blueprint: main (dashboard, ricerca, statistiche),
                           #            clients, policies, documents, followups,
                           #            opportunities, notifications, settings,
                           #            academy
  templates/               # interfaccia (Bootstrap 5)
  static/style.css         # tema grafico
  static/vendor/           # Bootstrap e icone in locale (funziona offline)
tests/test_app.py          # test funzionali (pytest)
tests/test_email.py        # test notifiche email e pagina impostazioni
tests/test_academy.py      # test dell'Accademia commerciale
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
per le aziende, RC professionale e infortuni per i professionisti). Infine i
rami consigliati vengono confrontati con quelli delle polizze attive per la gap
analysis. Il risultato è **sempre spiegabile** e non richiede servizi esterni.

# Gestionale Assicurativo

Gestionale web per intermediari assicurativi (agenti e broker) che seguono
**aziende, professionisti e lavoratori dipendenti**. Raccoglie in un unico
posto anagrafiche, polizze, **titoli e incassi**, **sinistri** e documenti;
**analizza automaticamente i pericoli** a partire dalla descrizione
dell'attività e non fa perdere **scadenze, rate e follow-up** grazie a
notifiche generate in automatico. Accesso con **utenti e ruoli**, **registro
attività** e **backup** integrati.

## Funzionalità

### Portafoglio
- **Anagrafica clienti** — aziende, professionisti **e lavoratori dipendenti**
  (con datore di lavoro e mansione): dati fiscali, contatti, sede, settore,
  dipendenti, fatturato e descrizione dettagliata dell'attività. Il form adatta
  i campi al tipo di cliente selezionato.
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
  scadenza, tacito rinnovo e stato; oltre 20 rami precompilati. Storico delle
  modifiche dal registro attività.
- **Rinnovo in un clic**: nuova scadenza, nuovo premio, generazione dei titoli
  della nuova annualità e chiusura automatica dei follow-up di rinnovo.
- **Titoli e incassi**:
  - generazione automatica delle **rate dell'annualità** in base al
    frazionamento (annuale → mensile), con arrotondamenti che quadrano sempre
    con il premio annuo; perfezionamento, quietanze, rate e appendici manuali;
  - **incasso** con data, importo, mezzo di pagamento e riferimento (CRO,
    assegno…), annullamento e **storno**;
  - **arretrati** evidenziati con lo stato della copertura secondo
    l'**art. 1901 c.c.** (primo premio non pagato → copertura non operante;
    rate successive → sospesa dal 15° giorno);
  - **foglio cassa** (prima nota incassi) per periodo, con riepilogo per mezzo
    di pagamento, provvigioni maturate e netto da rimettere;
  - **estratto conto per compagnia** con registrazione delle **rimesse**.
- **Sinistri**: apertura con numerazione progressiva (SIN-anno-numero),
  polizza coinvolta, tipologia, controparte, perito e liquidatore; importi
  richiesti, riservati, franchigia e liquidati; **cronologia** con note e
  cambi di stato; documenti collegati (denuncia, foto, perizia…); avviso di
  **denuncia oltre i 3 giorni** (art. 1913 c.c.).
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
- **Statistiche**: premi, provvigioni e **rapporto S/P per ramo**, premi per
  compagnia, incassi degli ultimi 12 mesi, premi in scadenza, primi 10 clienti,
  sinistri per tipologia e conversione della pipeline.

### Operatività quotidiana
- **Dashboard** con indicatori chiave e avvisi: scadenze, titoli arretrati,
  sinistri da denunciare, follow-up in ritardo, clienti senza consenso privacy.
- **Scadenzario** unificato di polizze, rate da incassare e follow-up.
- **Follow-up** con scadenza, tipo e priorità; i **follow-up di rinnovo**
  vengono generati automaticamente prima della scadenza delle polizze.
- **Notifiche automatiche** per polizze in scadenza (60/30/7 giorni e
  scadute), rate in scadenza o non pagate, coperture sospese, sinistri da
  denunciare o aperti da troppo tempo, documenti d'identità in scadenza e
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
- Password con hash (scrypt), **blocco dopo 5 tentativi errati** (15 minuti),
  protezione **CSRF** su tutti i form, cookie di sessione `HttpOnly` e
  `SameSite`, header di sicurezza, chiave di sessione generata casualmente al
  primo avvio, protezione da redirect esterni e da *CSV injection*.
- **Registro attività**: accessi (anche falliti), creazioni, modifiche,
  eliminazioni, incassi, storni, rinnovi, rimesse, esportazioni, backup e
  ripristini, con utente, data e IP; filtrabile ed esportabile.
- **Backup**: archivio ZIP con database e documenti scaricabile in un clic,
  **backup automatico giornaliero** con rotazione degli archivi e
  **ripristino** guidato (con copia di sicurezza dei dati attuali).
- Stampe con l'intestazione dello studio (ragione sociale, RUI, P.IVA).

## Applicazione desktop (.exe)

Vuoi provarla senza installare Python? È possibile impacchettare il gestionale
in un **eseguibile unico** (`GestionaleAssicurativo.exe` su Windows) che avvia il
server locale e apre il browser da solo. Il modo più semplice per ottenere il
`.exe` è la build automatica su GitHub Actions. Tutti i dettagli in
**[PACKAGING.md](PACKAGING.md)**.

## Requisiti

- Python 3.11+
- Flask e Flask-SQLAlchemy (vedi `requirements.txt`)

## Avvio rapido

```bash
pip install -r requirements.txt

# (opzionale) carica dati di esempio: clienti, polizze, titoli, sinistri…
python seed_demo.py

python app.py
# apri http://127.0.0.1:5000
```

Al primo accesso il gestionale chiede di creare l'account **amministratore**;
gli altri utenti si aggiungono poi dalla pagina **Utenti**. Se l'unico
amministratore dimentica la password: `flask --app app reimposta-password NOMEUTENTE`
(con l'eseguibile: `GestionaleAssicurativo.exe --reimposta-password NOMEUTENTE`).

Il database SQLite, i documenti caricati, i backup automatici e la chiave di
sessione vengono salvati nella cartella `instance/` (esclusa dal
versionamento).

## Configurazione

Variabili d'ambiente supportate:

| Variabile               | Default                              | Descrizione                                         |
|-------------------------|--------------------------------------|-----------------------------------------------------|
| `SECRET_KEY`            | generata e salvata al primo avvio    | Chiave di sessione Flask                            |
| `SECRET_KEY_FILE`       | `instance/secret_key`                | Dove salvare la chiave generata                     |
| `DATABASE_URL`          | `sqlite:///instance/gestionale.db`   | URI del database SQLAlchemy                         |
| `UPLOAD_FOLDER`         | `instance/uploads`                   | Cartella dei documenti caricati                     |
| `BACKUP_FOLDER`         | `instance/backups`                   | Cartella dei backup automatici                      |
| `SESSION_COOKIE_SECURE` | `false`                              | `true` se il gestionale è servito in HTTPS          |

> **In rete**: il server integrato ascolta solo su `127.0.0.1`. Per usarlo da
> più postazioni pubblicalo dietro un reverse proxy **HTTPS** (es. Caddy o
> nginx) e imposta `SESSION_COOKIE_SECURE=true`.

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

### Backup e ripristino

Da **Impostazioni → Backup** l'amministratore può scaricare un backup completo
(database + documenti in un unico ZIP), salvarne uno nella cartella dei backup,
configurare il **backup automatico giornaliero** (attivo di default, ultimi 14
archivi conservati) e **ripristinare** un archivio. Prima di ogni ripristino
viene salvata una copia di sicurezza dei dati attuali (`pre_ripristino_…zip`).
Conserva periodicamente una copia dei backup su un disco esterno o in cloud.

## Struttura

```
app.py                     # entry point (server di sviluppo)
run_desktop.py             # avvio «desktop»: server + browser (usato dall'exe)
seed_demo.py               # dati di esempio
gestionale.spec            # ricetta PyInstaller per l'eseguibile
gestionale/
  __init__.py              # application factory, filtri, errori e micro-migrazioni
  models.py                # modelli e vocabolari (clienti, polizze, titoli, sinistri, utenti…)
  security.py              # accesso, ruoli, CSRF, redirect sicuri, registro attività
  titoli.py                # generazione delle rate di premio e calcolo delle annualità
  validators.py            # codice fiscale, partita IVA, CAP, provincia, email
  backup.py                # backup ZIP, backup automatico e ripristino
  export.py                # esportazione CSV per Excel
  risk_engine.py           # motore di analisi automatica dei rischi
  notifications.py         # notifiche da scadenze, rate, sinistri e follow-up
  mailer.py                # invio email (SMTP stdlib) e digest notifiche
  scheduler.py             # thread in background: email e backup automatico
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
per le aziende, RC professionale e infortuni per i professionisti). Infine i
rami consigliati vengono confrontati con quelli delle polizze attive per la gap
analysis. Il risultato è **sempre spiegabile** e non richiede servizi esterni.

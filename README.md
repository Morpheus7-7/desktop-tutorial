# Gestionale Assicurativo

Gestionale web per intermediari assicurativi che seguono **professionisti e
aziende**. Permette di raccogliere in un unico posto anagrafiche, polizze e
documenti, di **analizzare automaticamente i pericoli** a partire dalla
descrizione dell'attività, e di non perdere **scadenze e follow-up** grazie a
notifiche generate in automatico.

## Funzionalità

- **Anagrafica clienti** (aziende e professionisti): dati fiscali, contatti,
  sede, settore, dipendenti, fatturato e descrizione dettagliata dell'attività.
- **Polizze**: compagnia, ramo, massimale, premio, frazionamento, decorrenza,
  scadenza, tacito rinnovo e stato; oltre 20 rami precompilati.
- **Archivio documenti**: caricamento e download di file (polizze, preventivi,
  visure, documenti d'identità, sinistri, GDPR…), collegabili a una polizza.
- **Analisi automatica dei rischi**: un motore a regole in italiano legge la
  descrizione dell'attività (più i dati di anagrafica) e produce:
  - i **pericoli rilevati** con severità e parole chiave che li hanno attivati;
  - le **coperture consigliate** per ciascun pericolo;
  - la **gap analysis** tra coperture consigliate e polizze già attive
    (scoperte vs. presenti). Ogni analisi è salvata nello storico ed è stampabile.
- **Follow-up**: attività con scadenza, tipo e priorità (chiamate, rinnovi,
  preventivi, raccolta documenti, gestione sinistri…).
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
run_desktop.py             # avvio «desktop»: server + browser (usato dall'exe)
seed_demo.py               # dati di esempio
gestionale.spec            # ricetta PyInstaller per l'eseguibile
gestionale/
  __init__.py              # application factory, filtri e micro-migrazioni
  models.py                # modelli e vocabolari (rami, categorie, Settings…)
  risk_engine.py           # motore di analisi automatica dei rischi
  notifications.py         # generazione notifiche da scadenze e follow-up
  mailer.py                # invio email (SMTP stdlib) e digest notifiche
  scheduler.py             # thread in background per l'invio automatico
  routes/                  # blueprint: main, clients, policies, documents,
                           #            followups, notifications, settings
  templates/               # interfaccia (Bootstrap 5)
  static/style.css
tests/test_app.py          # test funzionali (pytest)
tests/test_email.py        # test notifiche email e pagina impostazioni
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

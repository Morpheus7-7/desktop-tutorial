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
- **Dashboard** con indicatori chiave, prossime scadenze e follow-up.

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

## Struttura

```
app.py                     # entry point
seed_demo.py               # dati di esempio
gestionale/
  __init__.py              # application factory, filtri e notifiche
  models.py                # modelli e vocabolari (rami, categorie…)
  risk_engine.py           # motore di analisi automatica dei rischi
  notifications.py         # generazione notifiche da scadenze e follow-up
  routes/                  # blueprint: main, clients, policies, documents,
                           #            followups, notifications
  templates/               # interfaccia (Bootstrap 5)
  static/style.css
tests/test_app.py          # test (pytest)
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

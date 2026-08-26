# NutriStudio — l'app dello studio di nutrizione

Nasce dal planner Excel **Nutrition Planner v3** e ne conserva la sostanza —
gli alimenti USDA, il piano settimanale, l'analisi dei nutrienti, il foglio da
consegnare — portandola dove un foglio di calcolo non arriva: **due porte
d'accesso**, una per la nutrizionista e una per ogni cliente, con notifiche via
email, ricettario, articoli e lista della spesa collegata ai carrelli online.

```bash
pip install -r requirements.txt
python seed_nutri.py       # (opzionale) studio già avviato con dati di esempio
python nutri_app.py        # poi apri http://127.0.0.1:5001
```

Oppure, senza riga di comando, l'avvio «desktop» che apre da solo il browser
(è anche l'entry point dell'eseguibile `NutriStudio.exe`, vedi
[PACKAGING.md](PACKAGING.md)):

```bash
python run_nutristudio.py
```

> **In questo repository ci sono due applicazioni.** `app.py`,
> `run_desktop.py` e `GestionaleAssicurativo.exe` avviano il **gestionale
> assicurativo** sulla porta 5000. NutriStudio è `nutri_app.py`,
> `run_nutristudio.py` e `NutriStudio.exe`, sulla porta 5001.

## Come si entra la prima volta

**In NutriStudio non ci si registra.** È un'applicazione di studio privato: c'è
un accesso per lo studio, creato insieme al database al primo avvio, e gli
accessi dei clienti li apre la nutrizionista dalla scheda di ogni assistito
(«Crea accesso»: genera una password provvisoria e la manda via email).

Al primo avvio, quindi, entra con le credenziali di fabbrica — te le mostra la
pagina di accesso e le stampa la console — e ti verrà chiesto subito di
sceglierne una tua, dopodiché l'indicazione sparisce:

| Ruolo | Email | Password |
|-------|-------|----------|
| Studio | `nutrizionista@nutristudio.it` | `nutristudio` (da cambiare al primo accesso) |
| Cliente di esempio (solo dopo `seed_nutri.py`) | `giulia.bianchi@example.it` | `giulia2026` |

Per partire con credenziali tue invece di quelle di fabbrica, imposta
`NUTRI_ADMIN_EMAIL` e `NUTRI_ADMIN_PASSWORD` prima del primo avvio: in quel caso
la pagina non suggerisce niente e non c'è nessun cambio password forzato.

---

## Che cosa è diventato il foglio di calcolo

| Nel workbook | Nell'applicazione |
|---|---|
| Foglio **Foods** (322 alimenti USDA) | Database alimenti consultabile, filtrabile, correggibile, con nomi in italiano ed estendibile con alimenti propri |
| Foglio **Meal Plan** (una settimana, un cliente) | Piani illimitati, uno per assistito, componibili a pasti con alimenti *o ricette* |
| Foglio **Weekly Analysis** | Analisi giorno per giorno + medie settimanali + copertura dei micronutrienti, con riferimenti personalizzabili per assistito |
| Foglio **Client Handout** | Scheda stampabile **e** area riservata del cliente, consultabile dal telefono |
| Colonne Vegan/Vegetarian/GF/DF | Controllo automatico: le voci incompatibili con la dieta scelta diventano rosse e bloccano l'attenzione prima della pubblicazione |
| — | Anagrafica, misurazioni con grafico, appuntamenti, messaggi, ricettario, blog, lista della spesa, notifiche email |

---

## Funzionalità

### Area studio

- **Assistiti** — anagrafica, allergie e patologie in evidenza, obiettivo, tipo di
  dieta, target calorico; **misurazioni** (peso, massa grassa, circonferenze) con
  grafico dell'andamento; **stima del fabbisogno** con Mifflin-St Jeor e livelli di
  attività; appuntamenti; conversazione con il cliente.
- **Piani alimentari** — costruttore a settimana: sette giornate × cinque pasti,
  si aggiunge un alimento (o una ricetta, o una voce libera) e grammi e nutrienti
  si calcolano da soli. Una giornata si **copia sugli altri giorni** con un clic.
  Ogni giornata mostra kcal, percentuale sul target e ripartizione dei macro.
- **Analisi nutrizionale** — totali per giorno, medie settimanali, copertura dei
  micronutrienti contro riferimenti modificabili per ogni assistito, elenco delle
  voci in conflitto con la dieta.
- **Scheda da consegnare** — la pagina da stampare o salvare in PDF, con
  intestazione dello studio e disclaimer.
- **Ricettario** — ricette con ingredienti collegati agli alimenti: i valori per
  porzione si calcolano, non si scrivono. Le ricette entrano nei piani e i loro
  ingredienti entrano nella lista della spesa.
- **Articoli** — area editoriale con bozze e pubblicazione; i clienti li leggono
  nella loro area.
- **Alimenti** — 322 voci USDA più la dispensa italiana; ricerca, filtri
  (da verificare, senza valori, vegano, senza glutine…), correzione e aggiunta.
- **Notifiche** — piani in scadenza, appuntamenti di oggi e domani, assistiti senza
  piano attivo, misurazioni ferme da un mese, messaggi non letti. Deduplicate: lo
  stesso avviso non ricompare.

### Area cliente

- **Oggi** — la giornata in corso, pasto per pasto, con la barra delle calorie.
- **Il mio piano** — tutta la settimana, con la scheda di ogni giorno.
- **Spesa** — la lista aggregata, spuntabile, con i link ai carrelli.
- **Ricette** e **Blog** — solo i contenuti pubblicati.
- **Progressi** — grafico del peso e inserimento delle proprie misurazioni, che la
  nutrizionista vede subito con l'indicazione «inserita dal cliente».
- **Messaggi** — la conversazione con lo studio.

Nessuna vista dell'area cliente accetta un id: l'assistito viene sempre ricavato
dalla sessione, quindi non esiste un URL che mostri i dati di un altro.

---

## Lista della spesa e carrelli online

I grammi di ogni alimento vengono sommati su tutta la settimana (le ricette
espanse nei loro ingredienti, riproporzionati sulle porzioni previste),
raggruppati per reparto e trasformati in quantità leggibili. La lista si può
limitare ad alcuni giorni, stampare, scaricare in testo o **inviare al cliente
via email**.

Ogni riga apre la ricerca del prodotto sui servizi di spesa. Preconfigurati:
**Glovo, Everli, Carrefour, Esselunga, Deliveroo, Amazon**; se ne aggiungono
altri dalle Impostazioni indicando l'indirizzo di ricerca con `{query}` al posto
del nome del prodotto:

```
https://negozio.it/cerca?q={query}
```

Sono **link di ricerca**, non integrazioni: nessuna API da autorizzare, nessun
dato del cliente che esce dall'applicazione. Il carrello lo compone la persona,
sul sito del negozio.

---

## Email

Si configurano dalle **Impostazioni** (server SMTP, porta, sicurezza, utente,
password, mittente, destinatari), con email di prova e invio manuale del
riepilogo. Le variabili d'ambiente omonime hanno la precedenza sul database:

| Variabile | Esempio |
|---|---|
| `EMAIL_ATTIVE` | `true` |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_SECURITY` | `smtp.gmail.com` / `587` / `tls` |
| `SMTP_USER` / `SMTP_PASSWORD` | con Gmail serve una *password per le app* |
| `MAIL_FROM` / `MAIL_TO` | mittente / destinatari del riepilogo |
| `APP_BASE_URL` | `https://studio.esempio.it` — per i link dentro le email |

Partono quattro tipi di messaggio: **credenziali** di accesso al cliente (che
partono anche a invio automatico spento), **avviso di piano pubblicato**,
**lista della spesa**, e il **riepilogo periodico** delle notifiche allo studio,
mandato da uno scheduler in background con la cadenza scelta.

---

## I dati, e i loro limiti

I 322 alimenti vengono da **USDA FoodData Central, Foundation Foods** (rilascio
30 aprile 2026, pubblico dominio CC0). I valori nutrizionali sono riprodotti
**senza modifiche**. Quello che è stato aggiunto è la traduzione italiana del
nome e del reparto e il termine con cui cercare il prodotto sui servizi di
spesa; i nomi che il dizionario non copre restano in inglese e l'alimento è
marcato «da verificare».

Tre limiti da conoscere, ereditati dalla fonte e mostrati esplicitamente
dall'interfaccia invece di essere nascosti:

1. **Una cella vuota significa «non analizzato», non «zero».** Foundation Foods
   non misura ogni nutriente in ogni alimento (fibre nel 55% dei casi, vitamina
   B12 nel 20%). Ogni totale porta con sé quante voci non avevano il dato: dove
   manca qualcosa compare un asterisco e il valore va letto come sottostimato.
2. **Foundation Foods copre materie prime crude e secche.** Niente pane, niente
   pasta, niente olio d'oliva, nessun piatto pronto. L'applicazione aggiunge
   **20 alimenti della dispensa italiana** (olio extravergine, pasta, pane,
   parmigiano, salumi, passata…) con nome, porzione e compatibilità con le
   diete, ma **senza valori nutrizionali**: qui non si inventano numeri. Sono già
   utilizzabili nel piano e nella lista della spesa; i valori si inseriscono una
   volta sola, dalla propria fonte di riferimento (tabelle CREA / BDA), e l'elenco
   alimenti ha il filtro «senza valori nutrizionali» per trovarli.
3. **Le porzioni non sono tutte ufficiali.** Solo 78 vengono da FDC; le altre sono
   default di categoria, segnalati nella scheda alimento.

Non è un dispositivo medico né un supporto diagnostico: è uno strumento di
calcolo per professionisti della nutrizione. Ogni output va riletto prima di
darlo a un cliente.

---

## Struttura

```
nutri_app.py                # entry point per lo sviluppo (http://127.0.0.1:5001)
run_nutristudio.py          # avvio «desktop»: apre il browser, dati accanto all'eseguibile
nutristudio.spec            # ricetta PyInstaller → NutriStudio.exe
seed_nutri.py               # dati di esempio (--reset per ricominciare)
nutriapp/
  __init__.py               # application factory, filtri Jinja, primo avvio
  models.py                 # utenti, assistiti, alimenti, piani, ricette, articoli…
  nutrition.py              # motore di calcolo, semafori, fabbisogno
  shopping.py               # aggregazione della spesa e link ai carrelli
  security.py               # sessione, ruoli, decoratori di accesso
  mailer.py                 # SMTP: credenziali, avvisi, digest
  notifications.py          # generazione automatica delle notifiche
  scheduler.py              # thread in background per l'invio periodico
  charts.py                 # grafico del peso in SVG, senza librerie
  forms.py                  # lettura tollerante dei campi dei form
  foodimport.py             # importazione alimenti + traduzione
  data/                     # foods.json, traduzioni.json, alimenti_italia.json,
                            # sample_week.json (la settimana del workbook)
  routes/                   # auth, main, clients, plans, shopping, foods,
                            # recipes, blog, portal, settings
  templates/                # interfaccia (Bootstrap 5, vendorizzato)
tests/test_nutriapp.py      # 39 test funzionali
```

Il database SQLite sta in `instance/nutristudio.db` (escluso dal versionamento).

## Configurazione

| Variabile | Default | Descrizione |
|---|---|---|
| `SECRET_KEY` | `dev-cambiami-in-produzione` | chiave di sessione Flask |
| `DATABASE_URL` | `sqlite:///instance/nutristudio.db` | URI del database |
| `NUTRI_ADMIN_EMAIL` | `nutrizionista@nutristudio.it` | utente studio creato al primo avvio |
| `NUTRI_ADMIN_PASSWORD` | `nutristudio` | se lasciata al default va cambiata al primo accesso |

## Test

```bash
pip install -r requirements-dev.txt
python -m pytest tests/test_nutriapp.py -q
```

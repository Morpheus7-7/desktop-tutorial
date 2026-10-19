# Impacchettare il Gestionale in un eseguibile

Il gestionale può essere distribuito come **eseguibile unico** che avvia il
gestionale in una **finestra propria**, come un normale programma Windows:
chi lo usa non deve installare Python né conoscere la riga di comando. Basta
fare doppio clic. Tutti i dati restano sul PC: il motore interno risponde solo
a questo computer e non serve internet.

La finestra usa **Microsoft Edge WebView2**, già presente in Windows 10 e 11
aggiornati (se mancasse, si scarica gratis da Microsoft cercando «WebView2
Runtime»). Se la finestra non si può aprire, il programma ripiega sul browser
predefinito; per usare sempre il browser imposta `GESTIONALE_BROWSER=1`.

- Su **Windows** si ottiene `GestionaleAssicurativo.exe`
- Su **macOS/Linux** si ottiene un binario `GestionaleAssicurativo`

L'eseguibile salva i dati (database SQLite, documenti caricati, backup
automatici, chiave di sessione e log) nella **cartella dati dell'utente**, così
restano al sicuro anche se l'eseguibile viene spostato, avviato dall'interno
dello ZIP o copiato in *Programmi*:

| Sistema | Cartella dati predefinita |
|---------|---------------------------|
| Windows | `%LOCALAPPDATA%\GestionaleAssicurativo` (es. `C:\Users\Mario\AppData\Local\GestionaleAssicurativo`) |
| macOS   | `~/Library/Application Support/GestionaleAssicurativo` |
| Linux   | `~/.local/share/GestionaleAssicurativo` |

Il percorso esatto è stampato nella console a ogni avvio. Al primo avvio il
gestionale chiede di creare l'account amministratore. Vedi
[Cartella dei dati](#cartella-dei-dati) per la modalità portatile e per chi ha
già i dati accanto all'eseguibile.

---

## Opzione A — Build su GitHub (senza Windows né Python)

Il workflow [`.github/workflows/build.yml`](.github/workflows/build.yml) è già
incluso e, quando viene eseguito, compila l'eseguibile Windows su un runner
GitHub e lo pubblica come *artifact* scaricabile.

> **Serve avere GitHub Actions abilitato sull'account/repository.** Se Actions è
> disattivato o l'account ha esaurito i minuti/fatturazione, i job vengono
> interrotti all'avvio (senza runner) e non producono l'eseguibile: in quel caso
> usa l'**Opzione B** qui sotto. Abilita/verifica Actions da
> *Settings → Actions* del repository e *Settings → Billing* dell'account.

Per lanciarlo:

1. Vai su **Actions → «Test e build» → Run workflow** e scegli il branch
   (in alternativa, il workflow parte da solo quando pubblichi un **tag** di
   release, es. `v1.0.0`). GitHub allora:
   - esegue i test su Linux;
   - compila l'eseguibile su un runner **Windows**;
   - pubblica il risultato come *artifact*.
2. Apri l'esecuzione riuscita e scarica l'artifact **`GestionaleAssicurativo-windows`**.
3. **Estrai lo zip** (tasto destro → *Estrai tutto*) in una cartella stabile,
   ad esempio `C:\Gestionale` o `Documenti\Gestionale` (non in *Programmi*),
   poi fai doppio clic su `GestionaleAssicurativo.exe` estratto: si apre la
   finestra del gestionale. Se lo avvii direttamente dall'interno dello zip
   i dati vengono comunque salvati nella cartella dati dell'utente.

> Nota: il workflow **non** parte a ogni push, per non generare esiti rossi
> quando Actions non è disponibile. L'artifact resta scaricabile per il periodo
> di retention di GitHub (di norma 90 giorni); per una distribuzione stabile
> puoi allegarlo a una *Release*.

---

## Opzione B — Build in locale

Serve avere **Python 3.11+** installato sul sistema con cui vuoi produrre
l'eseguibile (PyInstaller **non** fa cross-compilazione: per ottenere un `.exe`
Windows bisogna compilare su Windows).

```bash
# 1. Installa le dipendenze di build (app + PyInstaller)
pip install -r requirements-build.txt

# 2. Compila usando la ricetta inclusa
pyinstaller gestionale.spec --noconfirm

# 3. L'eseguibile è nella cartella dist/
#    Windows:      dist\GestionaleAssicurativo.exe
#    macOS/Linux:  dist/GestionaleAssicurativo
```

Doppio clic sull'eseguibile: si apre la finestra del gestionale. Per fermarlo
chiudi la finestra (i backup vengono scritti con un nome temporaneo e
rinominati solo a fine scrittura: chiudere a metà non lascia archivi corrotti).

### Provare l'avvio «desktop» senza compilare

Puoi verificare il comportamento dell'eseguibile lanciando direttamente lo
stesso entry point:

```bash
pip install -r requirements.txt
python run_desktop.py
```

---

## Come è fatto il pacchetto

- **Entry point:** `run_desktop.py` — sceglie la cartella dati, impedisce un
  secondo avvio sulla stessa cartella, apre la porta (5000 o, se occupata, una
  libera), avvia lo scheduler delle notifiche, apre la finestra (pywebview, con ripiego sul browser) e serve l'app con
  [waitress](https://github.com/Pylons/waitress) (server WSGI puro Python; se
  non disponibile, usa il server integrato di Flask come fallback). All'avvio
  forza i tipi MIME di `.js`, `.css`, `.svg` e dei font, che su alcuni PC
  Windows il registro associa a `text/plain` (il browser bloccherebbe gli
  script).
- **Ricetta PyInstaller:** `gestionale.spec` — include i template Jinja e i file
  statici, dichiara i blueprint importati dinamicamente ed esclude il pacchetto
  `cryptography` (non necessario: l'invio email usa `ssl`/`smtplib` della
  libreria standard).
- **Dati persistenti:** cartella dati (vedi sotto) con `gestionale.db`,
  `uploads/`, `backup/`, `secret_key`, `gestionale.log` (log del programma, a
  rotazione) e `avvio.log` (eventuali errori di avvio).

## Cartella dei dati

Il launcher sceglie la cartella dati in quest'ordine:

1. la cartella indicata dalla variabile d'ambiente `GESTIONALE_DATI`;
2. la cartella `dati_gestionale` **accanto all'eseguibile, se contiene già un
   database**: chi usava le versioni precedenti continua a ritrovare i suoi
   dati senza fare nulla (se la cartella si trova in *Programmi* o su OneDrive
   compare un avviso con il consiglio di spostarla);
3. **modalità portatile** (es. chiavetta USB): se accanto all'eseguibile c'è un
   file `portatile.txt` (anche vuoto), oppure con `GESTIONALE_PORTATILE=1`, i
   dati vanno in `dati_gestionale` accanto all'eseguibile;
4. altrimenti la cartella dati dell'utente indicata all'inizio di questa pagina.

I dati non vengono mai salvati in una cartella temporanea: se trova dati creati
da un avvio precedente dall'interno dello zip (es.
`%TEMP%\Temp1_GestionaleAssicurativo-windows.zip\dati_gestionale`), il launcher
li copia nella cartella dati dell'utente. Lo stesso accade se la cartella
`dati_gestionale` accanto all'eseguibile non è scrivibile.

Per spostare i dati su un altro PC copia l'intera cartella dati (a programma
chiuso) oppure usa **Impostazioni → Backup**.

## Risoluzione problemi

- **Windows SmartScreen / antivirus**: gli eseguibili PyInstaller non sono
  firmati e possono generare un avviso. Scegli «Ulteriori informazioni →
  Esegui comunque», oppure firma l'eseguibile con un certificato tuo.
- **La porta 5000 è occupata**: il launcher passa automaticamente a una porta
  libera (scritta in `porta.txt` nella cartella dati).
- **Ho fatto doppio clic due volte**: il programma gira una sola volta per
  cartella dati. Il secondo avvio apre un'altra finestra sul gestionale già in
  esecuzione (niente doppio server né email doppie).
- **Compare un errore all'avvio**: un messaggio lo descrive e il dettaglio
  tecnico viene salvato in `avvio.log` nella
  cartella dati (il percorso è indicato nel messaggio): invialo all'assistenza.
- **Dove sono i miei dati?** Il percorso è stampato nella console a ogni avvio
  («Dati salvati in: …»); in **Impostazioni → Backup** trovi la cartella dei
  backup, che sta dentro la cartella dati.
- **Voglio configurare le email**: accedi come amministratore, vai su
  **Impostazioni → Notifiche via email** e inserisci i parametri SMTP. Vedi il
  README per l'elenco delle variabili d'ambiente equivalenti.
- **Ho dimenticato la password**: un altro amministratore può reimpostarla
  dalla pagina **Utenti**. Se l'unico amministratore ha perso l'accesso, apri
  un prompt dei comandi nella cartella dell'eseguibile e lancia
  `GestionaleAssicurativo.exe --reimposta-password NOMEUTENTE` (in sviluppo:
  `flask --app app reimposta-password NOMEUTENTE`): verrà chiesta la nuova
  password e l'utente sarà anche sbloccato e riattivato.

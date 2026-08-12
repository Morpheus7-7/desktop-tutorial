# Impacchettare il Gestionale in un eseguibile

Il gestionale può essere distribuito come **eseguibile unico** che avvia il
server web locale e apre automaticamente il browser: chi lo usa non deve
installare Python né conoscere la riga di comando. Basta fare doppio clic.

- Su **Windows** si ottiene `GestionaleAssicurativo.exe`
- Su **macOS/Linux** si ottiene un binario `GestionaleAssicurativo`

L'eseguibile salva i dati (database SQLite e documenti caricati) nella cartella
`dati_gestionale/` creata **accanto all'eseguibile stesso**, così i dati
restano tra un avvio e l'altro e sono facili da spostare o salvare.

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
3. Dentro lo zip trovi `GestionaleAssicurativo.exe`: doppio clic e si apre il
   browser sull'applicazione.

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

Doppio clic sull'eseguibile (oppure lancialo da terminale): partirà il server e
si aprirà il browser su `http://127.0.0.1:5000`. Per fermarlo, chiudi la
finestra della console.

### Provare l'avvio «desktop» senza compilare

Puoi verificare il comportamento dell'eseguibile lanciando direttamente lo
stesso entry point:

```bash
pip install -r requirements.txt
python run_desktop.py
```

---

## Come è fatto il pacchetto

- **Entry point:** `run_desktop.py` — sceglie una porta libera, avvia lo
  scheduler delle notifiche, apre il browser e serve l'app con
  [waitress](https://github.com/Pylons/waitress) (server WSGI puro Python; se
  non disponibile, usa il server integrato di Flask come fallback).
- **Ricetta PyInstaller:** `gestionale.spec` — include i template Jinja e i file
  statici, dichiara i blueprint importati dinamicamente ed esclude il pacchetto
  `cryptography` (non necessario: l'invio email usa `ssl`/`smtplib` della
  libreria standard).
- **Dati persistenti:** cartella `dati_gestionale/` accanto all'eseguibile.

## Risoluzione problemi

- **Windows SmartScreen / antivirus**: gli eseguibili PyInstaller non sono
  firmati e possono generare un avviso. Scegli «Ulteriori informazioni →
  Esegui comunque», oppure firma l'eseguibile con un certificato tuo.
- **La porta 5000 è occupata**: il launcher passa automaticamente a una porta
  libera; l'indirizzo esatto è stampato nella console all'avvio.
- **Voglio configurare le email**: apri l'app, vai su **Impostazioni** (icona
  ingranaggio) e inserisci i parametri SMTP. Vedi il README per l'elenco delle
  variabili d'ambiente equivalenti.

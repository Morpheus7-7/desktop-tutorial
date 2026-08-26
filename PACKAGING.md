# Impacchettare le applicazioni in un eseguibile

In questo repository ci sono **due applicazioni**, e ognuna ha il suo
eseguibile: avviano un server web locale e aprono da sole il browser, quindi
chi le usa non deve installare Python né conoscere la riga di comando. Basta
fare doppio clic.

| Applicazione | Eseguibile | Ricetta | Entry point | Dati |
|---|---|---|---|---|
| Gestionale Assicurativo | `GestionaleAssicurativo.exe` | `gestionale.spec` | `run_desktop.py` | `dati_gestionale/` |
| NutriStudio (nutrizione) | `NutriStudio.exe` | `nutristudio.spec` | `run_nutristudio.py` | `dati_nutristudio/` |

> **Attenzione a non confonderli.** `run_desktop.py` e
> `GestionaleAssicurativo.exe` avviano il gestionale assicurativo; per l'app di
> nutrizione servono `run_nutristudio.py` e `NutriStudio.exe`.

Su **macOS/Linux** si ottengono i binari senza estensione
(`GestionaleAssicurativo`, `NutriStudio`).

Ogni eseguibile salva i suoi dati (database SQLite e, per il gestionale, i
documenti caricati) nella propria cartella creata **accanto all'eseguibile
stesso**, così i dati restano tra un avvio e l'altro e sono facili da spostare
o salvare. Le due applicazioni non condividono nulla: database separati, porte
separate (5000 e 5001), accessi separati.

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
2. Apri l'esecuzione riuscita e scarica l'artifact che ti serve:
   **`GestionaleAssicurativo-windows`** oppure **`NutriStudio-windows`**.
3. Dentro lo zip trovi l'eseguibile: doppio clic e si apre il browser
   sull'applicazione. Al primo avvio di NutriStudio la console mostra le
   credenziali dello studio da usare per entrare.

> **Il branch conta.** NutriStudio esiste solo sul branch in cui è stato
> sviluppato finché la sua pull request non viene unita a `main`: se lanci il
> workflow su `main` prima del merge otterrai soltanto l'eseguibile del
> gestionale.

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

# 2. Compila usando la ricetta dell'applicazione che ti serve
pyinstaller gestionale.spec --noconfirm     # gestionale assicurativo
pyinstaller nutristudio.spec --noconfirm    # NutriStudio

# 3. Gli eseguibili sono nella cartella dist/
#    Windows:      dist\GestionaleAssicurativo.exe  ·  dist\NutriStudio.exe
#    macOS/Linux:  dist/GestionaleAssicurativo      ·  dist/NutriStudio
```

Doppio clic sull'eseguibile (oppure lancialo da terminale): partirà il server e
si aprirà il browser — su `http://127.0.0.1:5000` il gestionale, su
`http://127.0.0.1:5001` NutriStudio. Per fermarlo, chiudi la finestra della
console.

### Provare l'avvio «desktop» senza compilare

Puoi verificare il comportamento dell'eseguibile lanciando direttamente lo
stesso entry point:

```bash
pip install -r requirements.txt
python run_desktop.py        # gestionale assicurativo  → porta 5000
python run_nutristudio.py    # NutriStudio              → porta 5001
```

---

## Come è fatto il pacchetto

I due pacchetti sono costruiti allo stesso modo:

- **Entry point:** `run_desktop.py` / `run_nutristudio.py` — sceglie una porta
  libera, avvia lo scheduler delle notifiche, apre il browser e serve l'app con
  [waitress](https://github.com/Pylons/waitress) (server WSGI puro Python; se
  non disponibile, usa il server integrato di Flask come fallback).
- **Ricetta PyInstaller:** `gestionale.spec` / `nutristudio.spec` — include i
  template Jinja e i file statici, dichiara i blueprint importati dinamicamente
  ed esclude il pacchetto `cryptography` (non necessario: l'invio email usa
  `ssl`/`smtplib` della libreria standard). La ricetta di NutriStudio include
  anche `nutriapp/data`, senza cui l'eseguibile partirebbe con il database
  alimenti vuoto.
- **Dati persistenti:** `dati_gestionale/` e `dati_nutristudio/`, accanto
  all'eseguibile.

## Risoluzione problemi

- **Windows SmartScreen / antivirus**: gli eseguibili PyInstaller non sono
  firmati e possono generare un avviso. Scegli «Ulteriori informazioni →
  Esegui comunque», oppure firma l'eseguibile con un certificato tuo.
- **Mi parte l'applicazione sbagliata**: stai lanciando l'entry point
  dell'altra. Il gestionale è `run_desktop.py` / `GestionaleAssicurativo.exe`
  (porta 5000), NutriStudio è `run_nutristudio.py` / `NutriStudio.exe`
  (porta 5001). Il titolo in cima alla console lo dice all'avvio.
- **La porta è occupata**: il launcher passa automaticamente a una porta
  libera; l'indirizzo esatto è stampato nella console all'avvio.
- **Non ricordo le credenziali di NutriStudio**: al primo avvio la console le
  stampa. Dopo il cambio password, se le perdi, cancella
  `dati_nutristudio/nutristudio.db` (perdendo i dati) oppure reimposta
  l'accesso dalla pagina «Gestione accessi» con un altro utente dello studio.
- **Voglio configurare le email**: apri l'app, vai su **Impostazioni** (icona
  ingranaggio) e inserisci i parametri SMTP. Vedi il README per l'elenco delle
  variabili d'ambiente equivalenti.

# Guida — TradingAgents in locale sul tuo PC

[TradingAgents](https://github.com/TauricResearch/TradingAgents) è un framework di
**ricerca multi-agente**: diversi agenti IA (analista fondamentale, tecnico, del
sentiment, ricercatori "toro/orso", trader, risk manager) **discutono tra loro** e
producono una **decisione finale BUY / SELL / HOLD** con report motivati su un titolo.

Questo kit lo fa girare **100% in locale e gratis**: l'IA su **Ollama** (sul tuo PC) e i
dati di mercato da **yfinance** (gratuito, nessuna chiave a pagamento).

> ⚠️ **Cosa NON è.** TradingAgents *non esegue ordini* su MetaTrader 5 e *non* lavora
> tick-by-tick: analizza dati **giornalieri** (azioni USA, crypto, ecc.) e dà un parere.
> È **complementare** al bot MT5 di questo repo, non un sostituto. È materiale di ricerca,
> non consulenza finanziaria.

---

## 1. Requisiti

- **Windows** (va bene anche Mac/Linux) con **Python 3.10+** ([python.org](https://www.python.org/downloads/) — spunta *"Add Python to PATH"*).
- **Git** installato.
- **[Ollama](https://ollama.com)** per l'IA locale.
- **Hardware:** l'IA locale è esigente. Indicativamente servono **≥16 GB di RAM** per modelli ~14B; con una **GPU** va molto più veloce. Con un PC modesto usa modelli più piccoli (vedi §6).

---

## 2. Setup automatico (un comando)

Apri il terminale nella cartella di questo repo, poi:

**Windows (PowerShell):**
```powershell
cd tradingagents-setup
powershell -ExecutionPolicy Bypass -File .\setup.ps1
```

**Mac / Linux:**
```bash
cd tradingagents-setup
bash setup.sh
```

Lo script: clona TradingAgents, crea un ambiente virtuale Python, installa tutto e prepara
il file `.env`. (Cosa fa "a mano" è spiegato in fondo, §10.)

---

## 3. Installa Ollama e scarica i modelli

1. Installa **Ollama** da <https://ollama.com> e avvialo (resta in background).
2. Scarica i due modelli usati di default:
   ```bash
   ollama pull qwen2.5:14b
   ollama pull llama3.1
   ```
   La prima volta scarica alcuni GB. Verifica con `ollama list`.

> 💡 PC poco potente? Vedi §6 per modelli più leggeri.

---

## 4. La tua prima analisi

Dalla cartella `tradingagents-setup`, con la venv attiva (lo script l'ha già attivata):

```bash
python run_analysis.py AAPL
```

Altri esempi:
```bash
python run_analysis.py NVDA --date 2026-06-25
python run_analysis.py BTC-USD
python run_analysis.py AAPL --deep qwen2.5:14b --quick llama3.1 --rounds 2
```

⏳ Con i modelli locali un'analisi può richiedere **diversi minuti** (gli agenti si scambiano
molti messaggi). È normale: la prima esecuzione scarica anche i dati.

In alternativa puoi usare la **CLI interattiva guidata** (ti chiede ticker, data, modelli…):
```bash
cd TradingAgents
python -m cli.main
```

---

## 5. Come leggere il risultato

Alla fine vedrai una **decisione** (`BUY` / `SELL` / `HOLD`) preceduta dai report degli
agenti. La logica è:

```
Analista tecnico ─┐
Analista fondam. ─┤
Analista news    ─┼─► Ricercatori (dibattito Toro vs Orso) ─► Trader ─► Risk Manager ─► DECISIONE
Analista sentiment┘
```

I report completi vengono salvati anche in `~/.tradingagents/logs`. Leggi le **motivazioni**,
non solo il verdetto: il valore è nel ragionamento, che puoi usare come *secondo parere*.

---

## 6. Configurazione (file `.env`)

Modifica `tradingagents-setup/.env` per cambiare comportamento senza toccare il codice:

| Variabile | A cosa serve |
|---|---|
| `TRADINGAGENTS_DEEP_THINK_LLM` | modello per il ragionamento profondo |
| `TRADINGAGENTS_QUICK_THINK_LLM` | modello veloce di supporto |
| `TRADINGAGENTS_MAX_DEBATE_ROUNDS` | round di dibattito (1 = veloce, di più = più accurato/lento) |
| `TRADINGAGENTS_OUTPUT_LANGUAGE` | lingua dei report (impostata su `Italian`) |

**Modelli più leggeri** per PC modesti (più veloci, meno accurati):
```bash
ollama pull llama3.2:3b
ollama pull qwen2.5:7b
```
poi nel `.env`: `TRADINGAGENTS_DEEP_THINK_LLM=qwen2.5:7b` e `TRADINGAGENTS_QUICK_THINK_LLM=llama3.2:3b`.

---

## 7. Locale vs Cloud — il compromesso onesto

| | **Locale (Ollama)** | **Cloud (OpenAI/Anthropic…)** |
|---|---|---|
| Costo | Gratis | A pagamento (per token) |
| Privacy | Tutto sul tuo PC | Dati inviati al provider |
| Qualità | Buona con modelli grandi | Tipicamente superiore |
| Velocità | Dipende dal tuo hardware | Veloce |

Hai scelto il **locale** ed è perfetto per imparare e sperimentare senza spese. Se un giorno
vorrai più qualità/velocità, nel `.env` ci sono già (commentate) le righe per passare a OpenAI
o Anthropic: basta scommentarle e inserire la tua API key.

---

## 8. Dati e costi

- I dati di prezzo/fondamentali/news arrivano da **yfinance**: gratis, nessuna chiave.
- I dati **macroeconomici (FRED)** sono opzionali; se li vuoi, la chiave è **gratuita**
  (link nel `.env`).
- In modalità locale **non paghi nulla** per l'IA.

---

## 9. Come si collega al bot MT5 di questo repo

I due sistemi sono complementari e si possono **unire**:

```
TradingAgents (parere IA: BUY/SELL/HOLD su un titolo)
        │
        ▼
Bot MT5 di questo repo  ──►  esecuzione reale dell'ordine su MetaTrader 5 (demo)
```

Se ti interessa, come passo successivo posso scrivere un **ponte**: una funzione che prende la
decisione di TradingAgents e la passa come segnale aggiuntivo al motore decisionale del bot
MT5 (`src/engine/decision.py`). Chiedimelo pure.

---

## 10. Setup manuale (se preferisci capire ogni passo)

```bash
cd tradingagents-setup
git clone https://github.com/TauricResearch/TradingAgents.git
python -m venv .venv
# Windows:  .\.venv\Scripts\Activate.ps1
# Mac/Linux: source .venv/bin/activate
python -m pip install --upgrade pip
pip install ./TradingAgents
cp .env.example .env        # Windows: Copy-Item .env.example .env
python run_analysis.py AAPL
```

---

## 11. Problemi frequenti

| Sintomo | Soluzione |
|---|---|
| `tradingagents non installato` | Attiva la venv e rilancia `setup`. |
| Errore di connessione a `localhost:11434` | Ollama non è avviato → apri l'app o `ollama serve`. |
| `model not found` | Scarica il modello: `ollama pull <nome>`. |
| Molto lento / il PC arranca | Usa modelli più piccoli (§6) e `--rounds 1`. |
| Nessun dato per il ticker/data | Usa un **giorno feriale** recente e un ticker valido (es. `AAPL`, `MSFT`, `BTC-USD`). |
| `python` non riconosciuto | Reinstalla Python spuntando *"Add to PATH"*. |

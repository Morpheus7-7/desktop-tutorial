# Trading AI Bot — MetaTrader 5 + IA locale

Algoritmo di trading in **Python** che:

- legge dati di mercato in tempo reale da **MetaTrader 5** (Forex e Indici/CFD);
- analizza il mercato con un **motore di strategie classiche** (RSI, MACD, incrocio medie, Bollinger) + un **modello ML** (XGBoost) addestrato sui dati storici;
- usa un **LLM locale (Ollama)** come *supervisore di rischio* che approva o pone il veto sulle operazioni;
- esegue gli ordini su MT5, **in modalità DEMO/paper di default** (il passaggio al conto reale richiede un'attivazione esplicita).

> ⚠️ **Avvertenza.** Il trading comporta il rischio di perdere capitale. Questo
> progetto è materiale didattico/di base: **usalo solo su conto DEMO** finché non
> hai validato a fondo strategia, dati e gestione del rischio. Nessuna garanzia
> di profitto. Le performance passate non predicono quelle future.

---

## Architettura

```
            ┌──────────────────────────────────────────────────────────┐
            │                      Orchestrator (loop)                  │
            └──────────────────────────────────────────────────────────┘
                 │              │                 │              │
        ┌────────▼──┐   ┌───────▼──────┐   ┌──────▼──────┐  ┌───▼─────────┐
        │  Broker   │   │  Strategie   │   │  Modello ML │  │ Supervisore │
        │ MT5/Paper │   │ RSI/MACD/... │   │  (XGBoost)  │  │ LLM (Ollama)│
        └────────┬──┘   └───────┬──────┘   └──────┬──────┘  └───┬─────────┘
                 │              └───────┬─────────┘             │
              dati OHLCV          Decision Engine ──── veto ─────┘
                 │              (punteggio combinato)
                 │                      │
                 │               Risk Manager (sizing, SL/TP, limiti)
                 │                      │
                 └──────────► esecuzione ordine (DEMO/PAPER)
```

Struttura del codice:

| Percorso | Ruolo |
|---|---|
| `src/brokers/` | Astrazione broker: `mt5_broker.py` (reale), `paper_broker.py` (simulato) |
| `src/strategies/` | Strategie classiche, una per file + `registry.py` |
| `src/ml/` | Feature engineering (`features.py`) e modello (`model.py`) |
| `src/llm/` | Supervisore LLM via Ollama (`supervisor.py`) |
| `src/engine/` | `decision.py` (aggregazione) e `risk.py` (gestione rischio) |
| `src/orchestrator.py` | Ciclo principale in tempo reale |
| `scripts/` | `run_live.py`, `train_model.py`, `backtest.py` |
| `config/config.yaml` | Tutta la configurazione (simboli, pesi, rischio…) |

---

## Requisiti

- **Python 3.10+**
- Per il trading reale/demo: **Windows** con il terminale **MetaTrader 5** installato e il pacchetto `MetaTrader5` (`pip install MetaTrader5`). Su Linux/Mac è possibile via **Wine**.
- Per l'IA locale: **[Ollama](https://ollama.com)** in esecuzione, con un modello scaricato (es. `ollama pull llama3.1`).
- Lo sviluppo, i test e il backtest funzionano **ovunque** (anche senza MT5) grazie al `PaperBroker`.

## Installazione

```bash
python -m venv .venv
# Windows:  .venv\Scripts\activate
# Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env   # poi compila login/password DEMO MT5 e impostazioni Ollama
```

## Configurazione

- I **segreti** (login MT5, password, host Ollama) stanno nel file `.env`.
- Tutto il resto (simboli, timeframe, pesi delle strategie, parametri di rischio) è in `config/config.yaml`.
- La voce `mode` decide il comportamento:
  - `paper` → simulazione locale, nessun MT5 (ideale per sviluppo/backtest);
  - `demo` → MT5 su **conto demo** (consigliato per i primi test reali);
  - `live` → conto reale, **bloccato** se nel `.env` non imposti `ALLOW_LIVE_TRADING=true`.

## Uso

**1. Backtest / prova della pipeline (nessun MT5 richiesto):**
```bash
python -m scripts.backtest --steps 1500
```

**2. Allenare il modello ML:**
```bash
python -m scripts.train_model --symbols EURUSD GBPUSD --bars 5000
```
Il modello viene salvato in `models/xgb_direction.joblib` e caricato in automatico.
Per dati reali, esporta da MT5 un CSV `data/<symbol>.csv` con colonne
`time,open,high,low,close,volume`, oppure lascia che lo script li scarichi da MT5
(in modalità `demo`/`live`).

**3. Avviare il bot in tempo reale:**
```bash
python -m scripts.run_live
```

**4. Test:**
```bash
pytest -q
```

---

## Come funziona la decisione

1. Ogni strategia produce un `Signal` con **direzione** (−1/0/+1) e **confidenza** (0–1).
2. Il modello ML stima la **probabilità di rialzo** della prossima candela.
3. Il `DecisionEngine` combina tutto in un **punteggio in [−1, 1]**, pesando strategie e ML (pesi in `config.yaml`).
4. Se supera la soglia d'ingresso, il **supervisore LLM** valuta il contesto e può **approvare o porre il veto**.
5. Il `RiskManager` calcola il **lotto** (rischio % sull'equity), lo **stop loss** e il **take profit** (basati su ATR) e applica i limiti (max posizioni, stop giornaliero).
6. L'ordine viene inviato al broker.

## Sicurezza e prossimi passi

Protezioni già incluse: default su demo/paper, blocco del live non autorizzato,
stop loss giornaliero, dimensionamento del rischio per operazione, limite di
posizioni, gestione errori isolata per simbolo.

Possibili estensioni: trailing stop, gestione attiva delle posizioni aperte,
walk-forward validation del modello, notifiche (Telegram), dashboard, più
strategie e feature, persistenza dello stato.

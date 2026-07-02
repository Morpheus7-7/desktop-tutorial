# SMC-MT5 — Python pensa, TradingView conferma, MetaTrader esegue

Sistema di trading a tre componenti che porta la strategia a confluenza
(SMC + Liquidity Delta + divergenze RSI) fuori da MQL5:

```
┌──────────────────┐   alert webhook JSON    ┌─────────────────────────┐
│   TradingView    │ ──────────────────────► │   PYTHON (il cervello)  │
│  Pine script:    │                         │  • struttura SMC        │
│  BOS/CHoCH,      │                         │  • order blocks         │
│  sweep, div RSI  │                         │  • liquidity zones LDP  │
└──────────────────┘                         │  • divergenze RSI       │
                                             │  • confluenza + risk    │
┌──────────────────┐   barre OHLCV           │  • backtest             │
│  MetaTrader 5    │ ──────────────────────► │                         │
│  (il braccio)    │ ◄────────────────────── │                         │
└──────────────────┘   ordini (SL/TP/BE)     └─────────────────────────┘
```

- **Python studia, elabora e pensa**: riceve le barre da MT5, ricostruisce
  struttura/zone/divergenze, calcola la confluenza, applica il risk
  management e decide.
- **TradingView** fornisce conferme o trigger tramite gli alert del Pine
  script (`pine/SMC_Confluence_Alerts.pine`) inviati al webhook Python.
- **MetaTrader 5 esegue soltanto**: ordini a mercato con SL/TP,
  breakeven, chiusure di fine giornata.

## Struttura del progetto

```
python/
├── requirements.txt
├── config.example.yaml        # copia in config.yaml e personalizza
├── pine/
│   └── SMC_Confluence_Alerts.pine   # indicatore TradingView con alert JSON
└── smc_mt5/
    ├── config.py              # caricamento configurazione
    ├── mt5_client.py          # connessione, dati, ordini (pacchetto MetaTrader5)
    ├── risk.py                # sizing, limiti giornalieri, sessione, breakeven
    ├── webhook.py             # server FastAPI per gli alert TradingView
    ├── backtest.py            # backtest su storico MT5 o CSV
    ├── main.py                # loop live: pensa → filtra → esegue
    └── strategy/
        ├── indicators.py      # RSI/ATR Wilder, pivot
        ├── structure.py       # BOS/CHoCH, trend, premium/discount
        ├── order_blocks.py    # OB su break interni, mitigazione, retest
        ├── liquidity.py       # zone BSL/SSL, delta, ABS/EXH/DIV/REJ
        └── confluence.py      # motore che unisce tutto e genera i segnali
```

## Requisiti

- **Windows** con MetaTrader 5 installato e loggato (il pacchetto Python
  `MetaTrader5` funziona solo su Windows; su Linux serve Wine).
- Python 3.10+.
- Per i webhook TradingView: piano TradingView che li supporta e un
  endpoint raggiungibile da internet (VPS con porta aperta, oppure un
  tunnel tipo ngrok / cloudflared).

## Setup

```bash
cd python
python -m venv .venv
.venv\Scripts\activate            # Windows
pip install -r requirements.txt
copy config.example.yaml config.yaml
# modifica config.yaml (simbolo, timeframe, rischio, secret webhook...)
```

## 1. Studiare: il backtest

Prima di tutto si studia. Il backtest usa lo stesso identico motore del live:

```bash
# dallo storico MT5 (terminale aperto)
python -m smc_mt5.backtest --config config.yaml --bars 20000

# oppure da CSV (colonne: time,open,high,low,close,tick_volume)
python -m smc_mt5.backtest --config config.yaml --csv eurusd_m15.csv
```

Output: trade totali, win rate, profit factor, attesa in R, max drawdown e
la scomposizione per tipo di segnale (`LDP-ABS`, `LDP-REJ`, `OB retest`...).
Regole d'oro: **minimo 200 trade**, test su piu' simboli e periodi,
walk-forward prima di andare live.

## 2. TradingView: gli occhi

1. Apri l'editor Pine su TradingView e incolla `pine/SMC_Confluence_Alerts.pine`.
2. Imposta il **secret** identico a quello di `config.yaml`.
3. Crea un alert sull'indicatore → condizione *"Any alert() function call"* →
   Webhook URL: `https://TUO-HOST:8642/webhook`.

Tre modalita' in `config.yaml` → `tradingview.mode`:

| Modalita' | Comportamento |
|---|---|
| `off` | TradingView ignorato: decide solo Python |
| `confirm` | il segnale Python parte **solo** se TV ha mandato un alert concorde nelle ultime N barre |
| `trigger` | un alert TV e' un trigger in piu', ma passa comunque da confluenza e risk management Python |

Il webhook **non esegue mai ordini direttamente**: qualunque cosa arrivi da
TradingView passa dal cervello Python.

## 3. Live: MetaTrader esegue

```bash
python -m smc_mt5.main --config config.yaml
```

Il loop: warm-up dallo storico → a ogni barra chiusa il motore elabora →
se c'e' un segnale con confluenza sufficiente e il risk management
approva (finestra oraria, spread, max trade, limite perdita giornaliero,
eventuale conferma TV) → ordine a mercato su MT5 con SL/TP → breakeven a
1R → flat forzato a fine giornata.

## Sicurezza e note

- Il webhook accetta solo richieste con il `secret` corretto: usa HTTPS
  (reverse proxy o tunnel) e un secret robusto.
- `MetaTrader5` dialoga con il terminale locale: l'account resta nel
  terminale, Python non ha bisogno delle credenziali (login `0` in config).
- Testato: i moduli strategia hanno superato uno smoke test end-to-end
  (determinismo incrementale vs batch, coerenza degli SL, backtest) su
  dati sintetici. La connessione MT5 va provata su **conto demo**.

> ⚠️ Nessuna strategia garantisce profitti. Valida sempre su demo prima
> di usare capitale reale. Il trading comporta il rischio di perdita del
> capitale.

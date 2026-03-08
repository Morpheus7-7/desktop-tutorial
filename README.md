# GoldScalper Pro v3.0 — Advanced MT5 Gold Trading System

Expert Advisor (EA) per MetaTrader 5 specializzato su **XAUUSD (Gold)**.
Strategia multi-timeframe con gestione del rischio avanzata e trade management automatico.

---

## Caratteristiche principali

### Analisi Multi-Timeframe
| Timeframe | Ruolo |
|-----------|-------|
| H4        | Filtro trend (EMA 21/89/200) |
| H1        | Segnali di entrata |

### Indicatori Combinati
- **EMA 21/89/200** (H4) — direzione del trend principale
- **EMA 8/21** (H1) — crossover per entry
- **RSI 14** — filtro overbought/oversold
- **MACD 12/26/9** — conferma momentum e crossover
- **Bollinger Bands 20/2** — volatilità e mean-reversion
- **ATR 14** — SL/TP dinamici e sizing del rischio
- **Volume** — filtro spike per conferma breakout

### Strategie di Entrata (3 per direzione)
1. **Trend Continuation** — EMA cross + MACD in trend forte H4
2. **Pullback/Reversal** — prezzo near BB con RSI estremo + MACD cross
3. **Momentum Breakout** — trend forte H4 + tutti i segnali allineati + volume spike

### Risk Management
- **Position sizing dinamico** basato su % rischio equity
- **ATR-based Stop Loss** — adattivo alla volatilità corrente
- **3 livelli di Take Profit** con chiusura parziale automatica
  - TP1: 30% della posizione (ATR x 1.5)
  - TP2: 40% della posizione (ATR x 3.0)
  - TP3: 30% rimante con trailing stop (ATR x 5.0)
- **Break-even automatico** quando il prezzo si muove ATR x 0.8
- **Trailing stop ATR-based** (attivo dopo TP1)
- **Max daily loss %** — stop automatico del trading
- **Max drawdown %** — protezione account globale

### Filtri
- **Session filter** — London (8-16) e NY (13-21) server time
- **Spread filter** — skip se spread > soglia configurabile
- **News filter** — evita N minuti prima/dopo orari news configurati
- **Max open trades** — limite posizioni contemporanee

---

## Installazione

1. Copia `GoldScalper_Pro.mq5` in `MQL5/Experts/` della cartella dati MT5
2. Apri MetaEditor e compila il file
3. Trascina l'EA sul grafico XAUUSD (H1 consigliato come chart principale)
4. Abilita **Algo Trading** nella toolbar di MT5
5. Abilita **"Allow automated trading"** nelle proprieta EA

---

## Parametri principali

| Parametro | Default | Descrizione |
|-----------|---------|-------------|
| `RiskPercent` | 1.0 | % equity rischiata per trade |
| `MaxLotSize` | 5.0 | Lotto massimo |
| `MaxOpenTrades` | 3 | Trade simultanei max |
| `MaxDailyLossPerc` | 5.0 | Stop giornaliero % |
| `MaxDrawdownPerc` | 15.0 | Stop globale drawdown % |
| `ATR_SL_Multiplier` | 1.5 | SL = ATR x questo valore |
| `ATR_TP1_Multi` | 1.5 | TP1 = ATR x 1.5 |
| `ATR_TP2_Multi` | 3.0 | TP2 = ATR x 3.0 |
| `ATR_TP3_Multi` | 5.0 | TP3 = ATR x 5.0 |
| `EnableBreakEven` | true | Break-even automatico |
| `EnableTrailing` | true | Trailing stop attivo |
| `MaxSpread_Points` | 30 | Spread max ammesso (in points) |
| `UseSessions` | true | Filtro sessioni London/NY |
| `UseNewsFilter` | true | Filtro orari news |

---

## Raccomandazioni operative

- **Broker**: ECN/STP con spread tipico XAUUSD < 20 pts
- **Conto**: Minimo $3,000-$5,000 per lotti 0.01-0.1 con RiskPercent 1%
- **VPS**: Consigliato per continuita 24/5
- **Backtest**: Usa dati tick reali (99% quality) in Strategy Tester MT5
- **Ottimizzazione**: Ottimizza ATR multipliers e RSI levels su dati storici recenti

---

## Avvertenze

> **DISCLAIMER**: Il trading su forex e metalli preziosi comporta rischi significativi di perdita del capitale.
> Testa sempre su **conto demo** prima di operare in live.
> Le performance passate non garantiscono risultati futuri.

---

## Struttura file

```
GoldScalper_Pro.mq5   — Expert Advisor principale (MQL5)
README.md             — Documentazione
```

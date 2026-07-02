# StatisticalDayTrader — Expert Advisor per MetaTrader 5

Expert Advisor multi-strategia per il **day trading**, costruito sulla base di una ricerca
sulle strategie intraday con la migliore evidenza statistica documentata in backtest pubblici.

> ⚠️ **Disclaimer**: nessuna strategia garantisce profitti. I risultati dei backtest citati
> provengono da fonti terze, su strumenti e periodi specifici, e spesso **non includono
> integralmente spread, slippage e commissioni**. Testare sempre in demo e nello Strategy
> Tester prima di qualunque uso reale. Il trading comporta il rischio di perdita del capitale.

---

## 1. La ricerca: cosa dice la statistica sul day trading

Dalla ricerca sul web emergono alcuni punti fermi:

### Strategie con evidenza documentata

| Strategia | Evidenza statistica riportata | Note |
|---|---|---|
| **Opening Range Breakout (ORB)** | Win rate realistico 40–60%; un backtest pubblico su 114 trade riporta 74,5% di trade profittevoli e profit factor 2,51; su Nifty una variante ha raggiunto il 71,4% di win rate | Punta ai "trend day": non serve un win rate alto perché i vincenti corrono per multipli del rischio. L'edge sulle azioni USA si è eroso nel tempo; su forex il profit factor dipende molto dallo stop loss |
| **RSI(2) Mean Reversion (Larry Connors)** | Win rate tipicamente >50%; documentata in dettaglio con tre varianti e backtest su US500 M30 (gen 2024–mar 2025) in un articolo tecnico su MQL5.com | Regole precise: RSI(2) < 5 in uptrend (prezzo > MA200) per il long, RSI(2) > 95 in downtrend per lo short; uscita sulla MA a 5 periodi |
| **Trend-following / momentum intraday** | Uno studio VT Markets 2025 riporta ~62% di win rate nei periodi di trend, ma i costi di transazione erodono gran parte del profitto lordo (profit factor comunitari 1,07–1,24) | Il momentum azionario è documentato da oltre un secolo su lookback 1–12 mesi; intraday l'edge è più fragile |

### Requisiti di significatività statistica

- Minimo **100 trade** in backtest per una significatività di base; **200–500 trade** per confidenza elevata.
- Parametri e criteri di rifiuto vanno dichiarati **prima** del test (no data mining / ottimizzazione a posteriori).
- Un'analisi FX Replay 2025 attribuisce al backtesting disciplinato un incremento medio di profittabilità del ~30%.
- Diffidare di win rate dichiarati >80%: quasi sempre ignorano slippage, falsi breakout e giornate laterali.

### Fonti

- [QuantifiedStrategies — 21 Best Day Trading Strategies](https://www.quantifiedstrategies.com/day-trading-strategies/)
- [QuantifiedStrategies — Opening Range Breakout Strategy: Backtest](https://www.quantifiedstrategies.com/opening-range-breakout-strategy/)
- [MQL5.com — Day Trading Larry Connors RSI2 Mean-Reversion Strategies](https://www.mql5.com/en/articles/17636)
- [DailyBulls — ORB backtest: 71.4% win rate su Nifty](https://dailybulls.in/orb-intraday-trading-strategy-backtest/)
- [Trade That Swing — Opening Range Breakout Strategy](https://tradethatswing.com/opening-range-breakout-strategy-up-400-this-year/)
- [LuxAlgo — ORB Trading Strategy: How it Works](https://www.luxalgo.com/blog/opening-range-breakout-orb-trading-strategy-how-it-works/)
- [HyroTrader — The Most Profitable Trading Strategy: Data-Backed Guide](https://www.hyrotrader.com/blog/most-profitable-trading-strategy/)
- [GoatFundedTrader — 7 Key Metrics When Backtesting Day Trading Strategies](https://www.goatfundedtrader.com/blog/backtesting-day-trading-strategies)
- [QuantifiedStrategies — Mean Reversion Strategies: Backtested](https://www.quantifiedstrategies.com/mean-reversion-strategies/)

---

## 2. Le strategie implementate nell'EA

### Strategia A — Opening Range Breakout (ORB)

1. All'inizio della sessione (default 09:00 ora server) l'EA misura il **range di apertura**
   dei primi `N` minuti (default 30).
2. Il range è valido solo se la sua ampiezza è compresa tra 0,3× e 3× l'ATR(14)
   (filtro anti-giornate anomale o troppo compresse).
3. **Long**: una barra chiude sopra il massimo del range + buffer (0,1× ATR).
   **Short**: chiusura sotto il minimo del range − buffer.
4. Stop loss sul lato opposto del range; take profit a 2R (rapporto rendimento/rischio 2:1).
5. Dopo un movimento favorevole di 1R lo stop viene portato a **breakeven**.
6. Massimo un tentativo long e uno short al giorno.

### Strategia B — RSI(2) Mean Reversion (Larry Connors)

1. **Long**: RSI(2) della barra chiusa < 5 **e** prezzo sopra la SMA(200) (si compra il
   panico dentro un uptrend).
2. **Short**: RSI(2) > 95 **e** prezzo sotto la SMA(200).
3. **Uscita**: chiusura oltre la SMA(5) (ritorno alla media compiuto) oppure rottura
   della SMA(200) (trend invalidato).
4. Stop loss di emergenza a 2× ATR(14).

### Risk management comune (il vero "edge" statistico)

- **Position sizing a rischio fisso**: ogni trade rischia una % del saldo (default 1%),
  con lotti calcolati dalla distanza dello stop.
- **Limite di perdita giornaliero** (default 3% del saldo): raggiunto il limite, l'EA chiude
  tutto e si ferma fino al giorno successivo.
- **Massimo numero di trade al giorno** (default 4) per evitare l'overtrading.
- **Filtro spread**: niente ingressi se lo spread supera la soglia.
- **Finestra oraria**: ingressi solo tra inizio sessione e ora di cutoff.
- **Nessuna posizione overnight**: chiusura forzata a fine giornata (default 21:30) —
  requisito che definisce il day trading e azzera il rischio di gap.

---

## 3. Installazione

1. Apri MetaTrader 5 → `File` → `Apri cartella dati`.
2. Copia `Experts/StatisticalDayTrader.mq5` in `MQL5/Experts/`.
3. In MetaEditor (F4) apri il file e premi **Compila** (F7): deve compilare senza errori.
4. Trascina l'EA sul grafico dello strumento desiderato (timeframe consigliato: **M15 o M30**).
5. Abilita "Algo Trading".

## 4. Parametri principali

| Parametro | Default | Descrizione |
|---|---|---|
| `InpStrategy` | `STRAT_BOTH` | ORB, RSI2 o entrambe |
| `InpRiskPercent` | 1.0 | % del saldo rischiata per trade |
| `InpDailyLossLimit` | 3.0 | Stop di perdita giornaliero (% saldo) |
| `InpMaxTradesPerDay` | 4 | Trade massimi al giorno |
| `InpSessionStartHour/Min` | 09:00 | Inizio sessione (ora **del broker**) |
| `InpORBRangeMinutes` | 30 | Durata dell'opening range |
| `InpORBRewardRisk` | 2.0 | Take profit in multipli del rischio |
| `InpCloseAllHour/Min` | 21:30 | Chiusura forzata di tutte le posizioni |

> Gli orari sono in **ora del server del broker**: verifica il fuso del tuo broker e adatta
> `InpSessionStartHour` all'apertura della sessione che vuoi tradare (es. apertura di
> Londra o di New York).

## 5. Come validare l'EA (obbligatorio prima dell'uso reale)

1. **Strategy Tester** (Ctrl+R) → modalità "Every tick based on real ticks", su almeno
   2–3 anni di dati e più simboli (es. EURUSD, GBPUSD, US500).
2. Pretendi **almeno 200 trade** nel campione prima di trarre conclusioni.
3. Valuta: profit factor (>1,3 al netto dei costi), max drawdown, win rate coerente con
   le attese (40–60% ORB, >50% RSI2).
4. Esegui una **walk-forward**: ottimizza su una finestra, verifica su quella successiva.
5. Passa a un **conto demo per 1–3 mesi** prima di qualunque capitale reale.

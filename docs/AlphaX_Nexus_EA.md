# AlphaX Nexus EA v3 — Multi-Timeframe SMC Trading Engine

Evoluzione dell'indicatore **AlphaX_Nexus** in un **Expert Advisor** che opera
realmente sul mercato. Il motore di confluenza (struttura BOS/CHoCH, Order
Block, Fair Value Gap, liquidity sweep, volume / absorption / delta, EMA) viene
eseguito **in modo indipendente su ogni timeframe abilitato**, e ogni timeframe
fa trading con **il proprio magic number**.

> Nota tecnica: un *indicatore* MQL5 non può aprire ordini. Per "aprire ed
> essere realmente produttivo" serve un EA. Questo file è l'EA; l'indicatore
> originale resta in `Indicators/` per la sola visualizzazione.

## File

| File | Tipo | Scopo |
|------|------|-------|
| `Indicators/AlphaX_Nexus.mq5` | Indicatore | Visualizzazione SMC sul grafico |
| `Experts/AlphaX_Nexus_EA.mq5` | Expert Advisor | Trading multi-timeframe |

## Installazione

1. Copia `Experts/AlphaX_Nexus_EA.mq5` in
   `MQL5/Experts/` del tuo terminale MetaTrader 5.
2. (Opzionale) copia `Indicators/AlphaX_Nexus.mq5` in `MQL5/Indicators/`.
3. In MetaEditor premi **Compile** (F7).
4. Trascina l'EA sul grafico del simbolo desiderato e abilita
   **AutoTrading**.

L'EA si attacca a **un solo grafico** ma gestisce tutti i timeframe abilitati
dagli input: non serve aprire più grafici.

## Magic number per timeframe

Il magic è derivato in modo deterministico:

```
magic(TF) = InpMagicBase + (minuti del timeframe)
```

Con `InpMagicBase = 990000`:

| TF  | Minuti | Magic   |
|-----|--------|---------|
| M5  | 5      | 990005  |
| M15 | 15     | 990015  |
| M30 | 30     | 990030  |
| H1  | 60     | 990060  |
| H4  | 240    | 990240  |
| D1  | 1440   | 991440  |

Così ogni timeframe ha posizioni **isolate e tracciabili**: SL/TP, breakeven e
trailing vengono applicati solo alle posizioni del rispettivo magic, e puoi
filtrare/chiudere per TF anche manualmente.

## Logica operativa

- **Valutazione su barra chiusa** (niente repaint): a ogni nuova barra del TF
  l'engine ricalcola l'intero stato su una finestra di `InpLookbackBars` barre
  chiuse e decide sull'ultima barra chiusa.
- **Direzione**: serve `score >= InpMinConfluence` (su 8 fattori) + candela
  coerente + vincitore netto bull vs bear.
- **Filtro HTF**: l'entry deve essere allineato al trend del timeframe
  superiore (prezzo sopra/sotto EMA del TF più alto).
- **Una posizione per TF** + cooldown in barre dopo ogni trade.
- **Filtro spread** e **filtro sessione** opzionali.

## Gestione del rischio (esecuzione reale)

- **Sizing a rischio %**: il lotto è calcolato da `InpRiskPercent` dell'equity
  e dalla distanza dello stop (tick value/size del simbolo). Imposta
  `InpFixedLots > 0` per lotto fisso.
- **Stop loss**: dal bordo dell'Order Block pertinente + padding ATR; fallback
  su swing/ATR se non c'è zona.
- **Take profit**: da `InpRiskReward`.
- **Breakeven** a `+InpBE_TriggerR` R, **trailing ATR** da `+InpTrailStartR` R.
- **Cap globale** posizioni simultanee con `InpMaxOpenTotal`.
- Stop normalizzati al `SYMBOL_TRADE_STOPS_LEVEL` del broker.

## Parametri principali

| Gruppo | Input | Default | Note |
|--------|-------|---------|------|
| Rischio | `InpRiskPercent` | 0.5 | % equity a rischio per trade |
| Rischio | `InpFixedLots` | 0.0 | >0 = lotto fisso, ignora il rischio % |
| Rischio | `InpMaxOpenTotal` | 6 | max posizioni totali |
| TF | `InpTradeM15/H1/H4/...` | — | quali timeframe operare |
| Confluenza | `InpMinConfluence` | 4 | soglia minima (0–8) |
| Confluenza | `InpCooldownBars` | 5 | attesa dopo un trade (barre del TF) |
| HTF | `InpUseHTFFilter` | true | allinea al TF superiore |
| Exit | `InpRiskReward` | 2.0 | rapporto rischio/rendimento |
| Exit | `InpUseBreakeven` / `InpUseTrailing` | true | gestione attiva |

## Workflow consigliato (da algo trader)

1. **Backtest per singolo TF**: abilita un solo timeframe alla volta nello
   Strategy Tester per capire il comportamento di ciascun magic.
2. **Ottimizza** `InpMinConfluence`, `InpRiskReward`, `InpSLPaddingATR` sul tuo
   simbolo/sessione.
3. **Combina** i TF migliori; ogni magic resta indipendente, quindi puoi
   pesare il rischio per TF agendo su `InpRiskPercent`.
4. **Forward test** in demo prima del live.

> Disclaimer: strumento per ricerca/educazione sul trading algoritmico.
> Nessuna garanzia di profitto. Testa sempre in demo prima del reale.

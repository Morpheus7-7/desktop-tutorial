# PHANTOM EA v4.01 — Descrizione della strategia

Expert Advisor per MetaTrader 5, progettato per **XAU/USD (oro) su timeframe M1**.
Strategia: **mean-reversion con recupero a grid martingala**, filtrata da indicatori
di trend, momentum e volumi.

> ⚠️ **Avvertenza importante**: la martingala aumenta l'esposizione quando il mercato
> va contro la posizione. In un trend forte e prolungato il basket può accumulare
> perdite molto superiori al profitto medio per ciclo, fino ad azzerare il conto se
> le protezioni sono disattivate. Usare **solo su conto demo o con capitale che ci si
> può permettere di perdere**, con le protezioni (Daily Loss, Basket Stop, Max DD)
> sempre attive. Richiede un **conto HEDGING** (su conto netting le posizioni si
> fondono e la logica grid non funziona: l'EA lo segnala all'avvio).

---

## 1. Idea di fondo

L'EA cerca **esaurimenti di breve termine** sull'oro in M1: quando il prezzo è in
ipervenduto/ipercomprato con volumi sufficienti e un trend non troppo violento,
apre una posizione contraria al movimento appena esaurito, puntando a un rimbalzo
verso la media (VWAP intraday come riferimento).

Se il prezzo continua contro la posizione, l'EA **media il prezzo di carico** con
ordini aggiuntivi a distanza fissa e volume crescente (grid martingala), spostando
il breakeven sempre più vicino al prezzo corrente. Il ciclo si chiude in profitto
quando il prezzo ritraccia di una frazione del movimento subito.

## 2. Segnale di ingresso (primo ordine)

L'ingresso avviene **solo a barra M1 nuova, solo se non ci sono posizioni aperte**
e se tutti i blocchi (orario, giornaliero, circuit breaker, DD) sono inattivi.

Filtri "hard" (tutti obbligatori):

| Filtro | Condizione | Scopo |
|---|---|---|
| **ADX (M1)** | `ADX_Min ≤ ADX ≤ ADX_Max` (default 18–50) | Esclude mercati piatti e trend esplosivi |
| **Stocastico (5,3,3)** | BUY: %K < 25 e %K > %D · SELL: %K > 75 e %K < %D | Ipervenduto/ipercomprato con inizio di inversione |
| **Volume spike** | Volume tick barra chiusa ≥ 0.5 × media 20 barre | Evita ingressi in mercato illiquido |
| **ATR (M1, 14)** | ATR ≤ 25 pips (configurabile) | Evita ingressi con volatilità anomala (news) |

Filtri "soft" direzionali (basta che UNO confermi la direzione):

- **OBV su M15** in crescita → conferma BUY; in calo → conferma SELL.
- **VWAP intraday**: prezzo sopra VWAP → conferma BUY; sotto → conferma SELL.

Modalità **"Filtri disabilitati"** (`InpDisableAllFilters`): ignora tutti gli
indicatori e apre a ogni barra nuova (se flat), scegliendo la direzione da
prezzo vs VWAP. Il filtro ATR resta comunque attivo se abilitato. Modalità
pensata per test, non per operatività reale.

## 3. Grid martingala (recupero)

- Se il prezzo va contro di **`InpGridStep` punti** (default 500 = 5.00 $ sull'oro)
  dall'ultimo ordine, viene aperto un nuovo ordine **nella stessa direzione**.
- Volume del nuovo ordine = volume precedente × **`InpLotMultiplier`** (default 1.5),
  arrotondato allo step di volume del simbolo.
- Massimo **`InpMaxGridOrders`** ordini totali (default 5).

Progressione lotti con base 0.01 e moltiplicatore 1.5 (step volume 0.01):

| Livello | 1 | 2 | 3 | 4 | 5 | Totale |
|---|---|---|---|---|---|---|
| Lotti | 0.01 | 0.02 | 0.03 | 0.05 | 0.08 | **0.19** |

A ogni nuovo livello il TP di **tutte** le posizioni viene riallineato a
`breakeven ± InpTP_Basket` punti (default 1000 = 10 $): il ciclo chiude in
profitto se il prezzo ritraccia di ~10 $ dal prezzo medio di carico.

## 4. Uscite

1. **TP primo ordine** (`InpTP_First`, default 1000 punti) — se il primo ordine va
   subito a favore. Con `InpTP_Dynamic` il TP è agganciato al VWAP (mai più vicino
   del TP minimo).
2. **Basket TP** — con 2+ ordini, chiusura totale a `breakeven ± InpTP_Basket`
   (sia via TP server sulle posizioni, sia via controllo software a ogni tick).
3. **Trailing stop classico** (opzionale) — SL reale sul server; con 2+ ordini
   lavora sul breakeven del basket.
4. **Trailing stop di basket** (opzionale) — trailing "virtuale" sul profitto in
   punti dal breakeven: aggancia il picco e chiude tutto il basket se il prezzo
   ritraccia di `InpBasketTrailingDistance` punti dal picco.

## 5. Protezioni del capitale

| Protezione | Default | Comportamento |
|---|---|---|
| **Filtro orario** | 09:00–11:00 | Orari in **ORA DEL SERVER del broker** (riga "Ora server" sulla board come riferimento). Supporta finestre a cavallo della mezzanotte (es. 22:00–02:00). Fuori finestra: nessun nuovo ingresso; con basket aperto entra in *closing mode* (gestisce solo l'uscita; nuovi livelli grid solo se `InpCloseModeGrid=true`) |
| **Circuit breaker** | 4 livelli → pausa 4h | Raggiunti N livelli grid, blocca i **nuovi ingressi base** per N ore. Il basket aperto continua a essere gestito normalmente |
| **Basket Stop** | 50% | Chiude tutto il basket se il suo floating loss supera la % del balance |
| **Daily Loss Limit** | 50% | Chiude tutto e blocca l'EA fino a domani se l'equity perde la % dal balance di inizio giorno |
| **Max Drawdown** | 20% | Come sopra ma pensato come "paracadute" finale: chiude TUTTO e blocca fino al giorno dopo |
| **Filtro ATR** | 25 pips | Nessun ingresso con volatilità anomala |
| **Pulsanti BUY/SELL** | ON | Dalla board si può disabilitare una direzione al volo |

> Nota: i default 50% di Daily Loss e Basket Stop sono **molto permissivi**. Per un
> uso prudente si consigliano valori nell'ordine di 3–10%.

## 6. Interfaccia grafica

- **Board "Glass Dark"**: indicatori in tempo reale, semafori segnali BUY/SELL,
  stato del basket (ordini, lotti, breakeven, profit), statistiche giornaliere
  (trade chiusi, profitto/perdita lorda, DD massimo), stato protezioni e pulsanti
  BUY/SELL cliccabili.
- **Linee sul grafico**: entry, livelli grid aperti e previsti, breakeven, target,
  trailing stop, VWAP — tutte con etichette e colori configurabili.
- **Etichette P&L**: a ogni chiusura (anche manuale) un punto + testo colorato con
  il profitto del deal, ancorati a prezzo/orario esatti; frecce sugli ingressi.

## 7. Requisiti e impostazioni consigliate

- **Simbolo**: XAUUSD (2 decimali; le distanze in "punti" presumono point = 0.01).
- **Timeframe grafico**: M1 (gli indicatori sono comunque calcolati su M1/M15 fissi).
- **Conto**: HEDGING obbligatorio; leva adeguata al volume massimo del basket.
- **Esecuzione**: VPS consigliato (logica per tick).
- **Backtest**: "Ogni tick basato su tick reali", periodi con trend forti inclusi
  (es. rally o crolli dell'oro) per stress-testare la martingala.

## 8. Come verificare che le impostazioni siano applicate (v4.01)

Dopo ogni cambio di parametri l'EA scrive nel tab **Esperti** un riepilogo dei
valori realmente attivi (finestra oraria con l'ora server attuale, grid, TP,
protezioni). Se dopo un cambio input il log non compare, o la board non mostra
`v4.01` nel titolo, **sul grafico sta girando ancora la versione vecchia**:

1. Rimuovere l'EA dal grafico (tasto destro → *Lista Expert* → rimuovi).
2. Ricompilare `PHANTOM.mq5` in MetaEditor (F7) senza errori.
3. Riagganciare l'EA al grafico e impostare i valori nella **finestra Input**.

Attenzione a due trappole comuni di MT5:

- **Cambiare i default nel codice non basta**: l'istanza già attaccata al
  grafico (e lo Strategy Tester) conservano gli input impostati in precedenza
  nella finestra proprietà. I valori vanno cambiati lì (F7 sul grafico).
- **Il filtro orario usa l'ora del server del broker**, non quella del PC:
  se il broker è ad esempio GMT+3 e l'Italia è GMT+2, una finestra 9–11
  server corrisponde alle 8–10 italiane. La riga "Ora server" sulla board
  mostra il riferimento corretto.

## 9. Novità della v4.00/v4.01 (riscrittura)

Correzioni di bug rispetto alla v3.80:

1. **Circuit breaker**: bloccava l'intera gestione del basket (niente basket TP
   software, trailing, grid) lasciandolo orfano; ora blocca solo i nuovi ingressi.
2. **Closing mode**: fuori orario l'EA continuava ad aprire nuovi livelli grid;
   ora di default gestisce solo l'uscita (`InpCloseModeGrid` per il vecchio
   comportamento).
3. **DD giornaliero** aggiornato sempre, anche a EA bloccato (la v3.52 lo
   prometteva ma i `return` anticipati lo impedivano).
4. **Board** aggiornata anche dopo Basket Stop e durante i blocchi.
5. **Basket Stop** calcolato sul P&L del solo basket (prima usava balance−equity
   dell'intero conto, falsato da posizioni su altri simboli).
6. **Lotti** normalizzati a `VOLUME_STEP/MIN/MAX` e **controllo margine** prima di
   ogni ordine; esiti di apertura/chiusura verificati e loggati.
7. **Prestazioni**: una sola scansione posizioni per tick (prima decine), VWAP
   incrementale (prima ~1440 barre ricalcolate a ogni tick), linee grafiche
   aggiornate in-place (prima cancella+ricrea tutto a ogni tick).
8. **Warning conto netting** all'avvio.
9. **Versione unificata** (prima: 3.80 nell'header, 3.73 su board e log) e pulizia
   di input inutilizzati e dead code.

E nella v4.01:

10. **Log dei parametri applicati** a ogni OnInit (verifica immediata dei valori
    attivi dopo un cambio impostazioni).
11. **Riga "Ora server" sulla board** e timer 1s: filtro orario e board aggiornati
    anche senza tick.
12. **Finestre orarie a cavallo della mezzanotte** supportate; ore/minuti fuori
    range vengono limitati automaticamente.
13. **Linee ridisegnate da zero dopo un cambio parametri**: nuovi colori ed
    etichette si applicano subito.

## 10. Parametri principali

| Gruppo | Parametro | Default | Note |
|---|---|---|---|
| Strategia | `InpLotSize` | 0.01 | Lotto base |
| Strategia | `InpLotMultiplier` | 1.5 | Moltiplicatore grid |
| Strategia | `InpGridStep` | 500 | Distanza livelli (punti) |
| Strategia | `InpMaxGridOrders` | 5 | Livelli massimi |
| Take Profit | `InpTP_First` / `InpTP_Basket` | 1000 / 1000 | Punti |
| Protezioni | `InpDailyLossLimit` | 50 | % (consigliato 3–10) |
| Protezioni | `InpBasketStopLoss` | 50 | % (consigliato 3–10) |
| Protezioni | `InpMaxDrawdownPct` | 20 | % |
| Orario | `InpStartHour–InpEndHour` | 9–11 | Ora del broker |
| Indicatori | `InpADX_Min/Max` | 18 / 50 | Range ADX |
| Indicatori | `InpStoch_OB/OS` | 75 / 25 | Soglie stocastico |

---

*Questo software è fornito a scopo didattico. Il trading su margine comporta un
rischio elevato di perdita del capitale. Nessuna parte di questo documento
costituisce consulenza finanziaria.*

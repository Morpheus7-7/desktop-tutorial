//+------------------------------------------------------------------+
//|                                                      PHANTOM.mq5 |
//|                                  Grid Martingale EA v4.00        |
//|                         Gold XAU/USD M1 - Volumetric Analysis    |
//|                                                                  |
//| v4.00: Riscrittura completa partendo dalla v3.80.               |
//|   FIX / MIGLIORIE PRINCIPALI:                                   |
//|   1) Circuit breaker: ora blocca SOLO i nuovi ingressi base;    |
//|      il basket aperto continua a essere gestito (TP basket,     |
//|      grid, trailing). Nella v3.80 il blocco fermava TUTTA la    |
//|      gestione lasciando il basket orfano.                        |
//|   2) Closing mode (fuori orario): di default NON apre piu'      |
//|      nuovi livelli grid (input InpCloseModeGrid per il vecchio  |
//|      comportamento). Prima l'EA aumentava l'esposizione proprio |
//|      mentre doveva chiudere.                                     |
//|   3) dayMaxDrawdown aggiornato SEMPRE, anche con EA bloccato.   |
//|   4) Board aggiornata anche dopo Basket Stop / blocchi (prima   |
//|      restava congelata).                                         |
//|   5) Cache del basket (ScanBasket): una sola scansione delle    |
//|      posizioni per tick invece di decine.                        |
//|   6) VWAP incrementale: ricalcolo completo solo a barra nuova   |
//|      (prima: fino a 1440 barre AD OGNI TICK).                    |
//|   7) Linee grafiche aggiornate in-place con nomi deterministici |
//|      (prima: delete+recreate di tutti gli oggetti a ogni tick). |
//|   8) Lotti normalizzati a VOLUME_STEP/MIN/MAX e controllo       |
//|      margine libero prima di ogni invio ordine.                  |
//|   9) Controllo esito di Buy/Sell/PositionClose con log errori.  |
//|  10) Warning all'avvio se il conto e' NETTING (la logica grid   |
//|      richiede un conto HEDGING).                                 |
//|  11) Basket Stop calcolato sul P&L del SOLO basket (prima:      |
//|      balance-equity dell'intero conto, falsato da altri simboli)|
//|  12) Freccia entry nominata con il ticket dell'ordine (prima:   |
//|      TimeCurrent() -> collisioni nello stesso secondo).          |
//|  13) Profit "ultimo basket" accumulato su tutti i deal di       |
//|      chiusura, non solo sull'ultimo deal.                        |
//|  14) Versione unica via #define (prima: 3.80 nell'header ma     |
//|      3.73 su board e log).                                       |
//|  15) Rimossi: #property strict (MQL4), input sfondo P&L         |
//|      inutilizzati, DeletePnLLabels (dead code), logica di reset |
//|      giornaliero duplicata in CheckMaxDrawdown.                  |
//|                                                                  |
//| v4.01: Impostazioni verificabili e applicate subito.            |
//|   - Log dei parametri applicati a ogni OnInit: dopo un cambio   |
//|     input il tab Esperti mostra i valori realmente attivi.      |
//|   - Nuova riga "Ora server" sulla board: il filtro orario usa   |
//|     l'ORA DEL BROKER (TimeCurrent), non quella locale del PC.   |
//|   - Filtro orario: supporto finestre a cavallo della mezzanotte |
//|     (es. 22:00-02:00); ore/minuti fuori range vengono limitati. |
//|   - OnTimer 1s: filtro orario e board aggiornati anche senza    |
//|     tick (prima, a mercato fermo, la board restava congelata    |
//|     sui vecchi valori dopo un cambio parametri).                 |
//|   - Linee di trading ridisegnate da zero dopo cambio parametri  |
//|     cosi' nuovi colori/etichette si applicano immediatamente.   |
//+------------------------------------------------------------------+
#property copyright "PHANTOM EA"
#property version   "4.01"
#property description "Grid Martingale EA per XAU/USD M1 con filtri ADX/Stocastico/Volumi/OBV/VWAP"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>

#define EA_VERSION "4.01"

CTrade        trade;
CPositionInfo posInfo;

//+------------------------------------------------------------------+
//| INPUT PARAMETERS                                                 |
//+------------------------------------------------------------------+

// --- STRATEGY ---
input group "=== STRATEGIA ==="
input double   InpLotSize          = 0.01;   // Lotto minimo / fallback
input bool     InpDynamicLot       = false;  // Abilita lot sizing dinamico
input double   InpLotPerBalance    = 1000.0; // Balance per 0.01 lotti (es. 1000 = 0.01 ogni 1000)
input double   InpLotMultiplier    = 1.5;    // Moltiplicatore lotto grid
input int      InpGridStep         = 500;    // Distanza grid (punti)
input int      InpMaxGridOrders    = 5;      // Max ordini grid
input double   InpDailyLossLimit   = 50;     // Limite perdita giornaliera (% sul balance di inizio giorno) - 0 = disabilitato
input double   InpBasketStopLoss   = 50;     // Hard stop basket: chiude grid se floating loss >= % del balance (0 = disabilitato)
input double   InpMaxDrawdownPct   = 20.0;   // STOP LOSS DD MASSIMO: chiude TUTTO se equity scende di questa % dal balance di inizio giorno (0 = disabilitato)

// --- CIRCUIT BREAKER ---
input group "=== CIRCUIT BREAKER ==="
input bool     InpCB_Enabled       = true;   // Abilita circuit breaker
input int      InpCB_TriggerLevels = 4;      // Livelli grid per attivare blocco (es. 4)
input int      InpCB_PauseHours    = 4;      // Ore di pausa dopo il blocco

// --- ATR FILTER ---
input group "=== FILTRO ATR (VOLATILITA') ==="
input bool     InpATR_Enabled      = true;   // Abilita filtro ATR
input int      InpATR_Period       = 14;     // ATR periodo (su M1)
input double   InpATR_MaxPips      = 25.0;   // ATR massimo in pips (0 = disabilitato)

// --- TIME FILTER ---
input group "=== FILTRO ORARIO ==="
input bool     InpTimeFilter       = true;   // Abilita filtro orario
input int      InpStartHour        = 9;      // Ora inizio (es. 8)
input int      InpStartMin         = 0;      // Minuti inizio
input int      InpEndHour          = 11;     // Ora fine (es. 12)
input int      InpEndMin           = 0;      // Minuti fine
input bool     InpCloseModeGrid    = false;  // Consenti nuovi livelli grid in closing mode (fuori orario)

// --- TAKE PROFIT ---
input group "=== TAKE PROFIT ==="
input int      InpTP_First         = 1000;   // TP primo ordine (punti)
input bool     InpTP_Dynamic       = false;  // Usa VWAP come TP dinamico
input int      InpTP_Basket        = 1000;   // TP basket sul breakeven (punti)

// --- TRAILING STOP ---
input group "=== TRAILING STOP ==="
input bool     InpTrailingEnabled  = false;  // Abilita Trailing Stop (singolo ordine)
input int      InpTrailingStart    = 150;    // Attiva trailing dopo (punti)
input int      InpTrailingStep     = 50;     // Step trailing (punti)
input int      InpTrailingDistance = 50;     // Distanza trailing (punti)

input group "=== TRAILING STOP BASKET ==="
input bool     InpBasketTrailingEnabled  = false;  // Abilita Trailing Stop sul basket (chiude tutto insieme)
input int      InpBasketTrailingStart    = 200;    // Attiva quando il basket e' in profitto di X punti dal breakeven
input int      InpBasketTrailingStep     = 50;     // Step minimo per aggiornare il picco (punti)
input int      InpBasketTrailingDistance = 100;    // Distanza dal picco: sotto questa, chiude tutto il basket (punti)

input group "=== ORDINI MANUALI ==="
input bool     InpManageManualOrders = false; // Gestisci anche ordini aperti manualmente (magic=0) sullo stesso simbolo

// --- INDICATORS ---
input group "=== INDICATORI ==="
input bool     InpDisableAllFilters= false;  // *** DISABILITA TUTTI GLI INDICATORI *** (apre ordini liberi)
input int      InpADX_Period       = 14;     // ADX periodo
input double   InpADX_Min          = 18.0;   // ADX minimo per entrare
input double   InpADX_Max          = 50.0;   // ADX massimo
input int      InpStoch_K          = 5;      // Stocastico %K
input int      InpStoch_D          = 3;      // Stocastico %D
input int      InpStoch_Slowing    = 3;      // Stocastico Slowing
input int      InpStoch_OB         = 75;     // Stocastico ipercomprato
input int      InpStoch_OS         = 25;     // Stocastico ipervenduto
input int      InpVolSpike_Period  = 20;     // Volume spike periodo MA
input double   InpVolSpike_Min     = 0.5;    // Volume minimo (x media)
input bool     InpOBV_Filter       = true;   // Usa OBV come filtro soft
input bool     InpVWAP_Filter      = true;   // Usa VWAP come filtro direzionale

// --- COLORS LINES ---
input group "=== COLORI LINEE ==="
input color    InpColor_Entry      = clrDodgerBlue;  // Colore linea primo ordine
input color    InpColor_Grid       = clrDimGray;     // Colore linee grid previste
input color    InpColor_GridOpen   = clrOrange;      // Colore linea grid aperta
input color    InpColor_TP         = clrLime;        // Colore linea Take Profit
input color    InpColor_BE         = clrYellow;      // Colore linea Break Even
input color    InpColor_TS         = clrMagenta;     // Colore linea Trailing Stop
input color    InpColor_VWAP       = clrCyan;        // Colore linea VWAP
input int      InpLine_Width       = 1;              // Spessore linee
input int      InpLine_Width_TP    = 2;              // Spessore linea TP

// --- ETICHETTE P&L SUL GRAFICO ---
input group "=== ETICHETTE P&L GRAFICO ==="
input bool     InpPnL_Labels       = true;           // Mostra etichette P&L
input color    InpPnL_Color_Profit = clrLime;        // Colore testo profitto
input color    InpPnL_Color_Loss   = clrTomato;      // Colore testo perdita
input color    InpPnL_Color_BE     = clrYellow;      // Colore testo breakeven
input int      InpPnL_FontSize     = 8;              // Dimensione font etichetta
input int      InpPnL_Arrow_Size   = 2;              // Dimensione freccia entry (1-5)
input color    InpPnL_Arrow_Buy    = clrDodgerBlue;  // Colore freccia BUY
input color    InpPnL_Arrow_Sell   = clrOrangeRed;   // Colore freccia SELL

// --- BOARD ---
input group "=== BOARD POSIZIONE ==="
input int      InpBoard_X          = 14;     // Board posizione X
input int      InpBoard_Y          = 30;     // Board posizione Y
input int      InpBoard_Width      = 210;    // Board larghezza
input int      InpBoard_FontSize   = 9;      // Board font size

// --- LINE LABELS ---
input group "=== ETICHETTE LINEE ==="
input string   InpLabel_Entry      = "ENTRY";        // Label primo ordine
input string   InpLabel_Grid       = "GRID";         // Label linee grid
input string   InpLabel_TP         = "TARGET";       // Label Take Profit
input string   InpLabel_BE         = "BREAKEVEN";    // Label Break Even
input string   InpLabel_TS         = "TRAIL STOP";   // Label Trailing Stop
input string   InpLabel_VWAP       = "VWAP";         // Label VWAP
input int      InpLabel_FontSize   = 8;              // Font size etichette linee
input color    InpLabelCol_Entry   = clrDodgerBlue;  // Colore label ENTRY
input color    InpLabelCol_Grid    = clrDimGray;     // Colore label GRID futuro
input color    InpLabelCol_GridOpen= clrOrange;      // Colore label GRID aperto
input color    InpLabelCol_TP      = clrLime;        // Colore label TARGET
input color    InpLabelCol_BE      = clrYellow;      // Colore label BREAKEVEN
input color    InpLabelCol_TS      = clrMagenta;     // Colore label TRAIL STOP
input color    InpLabelCol_VWAP    = clrCyan;        // Colore label VWAP

//+------------------------------------------------------------------+
//| COLORS (Glass Dark palette)                                      |
//+------------------------------------------------------------------+
#define CLR_BG          C'26,31,46'
#define CLR_BG2         C'20,24,36'
#define CLR_BORDER      C'60,80,120'
#define CLR_ACCENT      C'99,179,237'
#define CLR_GREEN       C'104,211,145'
#define CLR_GREEN_BG    C'26,52,42'
#define CLR_GREEN_BD    C'52,105,84'
#define CLR_RED         C'252,129,129'
#define CLR_RED_BG      C'61,21,21'
#define CLR_RED_BD      C'126,52,52'
#define CLR_YELLOW      C'251,211,141'
#define CLR_MUTED       C'113,128,150'
#define CLR_TEXT        C'226,232,240'
#define CLR_DIM         C'74,85,104'
#define CLR_SECTION_L   C'45,55,72'

//+------------------------------------------------------------------+
//| GLOBAL VARIABLES                                                 |
//+------------------------------------------------------------------+
int      adxHandle   = INVALID_HANDLE;
int      stochHandle = INVALID_HANDLE;
int      obvHandle   = INVALID_HANDLE;
int      atrHandle   = INVALID_HANDLE;

double   adxMain[], adxPlus[], adxMinus[];
double   stochMain[], stochSignal[];
double   obvBuffer[];

// Fotografia del basket, calcolata UNA volta per tick da ScanBasket()
struct SBasket
{
   int                count;      // numero posizioni gestite
   double             lots;       // volume totale
   double             breakEven;  // prezzo medio ponderato
   double             profit;     // P&L flottante (profit+swap+commission)
   double             lastPrice;  // prezzo apertura ultimo livello grid
   double             lastLot;    // volume ultimo livello grid
   double             tp;         // primo TP > 0 trovato sulle posizioni
   ENUM_POSITION_TYPE type;       // direzione del basket (dalla posizione piu' vecchia)
};
SBasket  basket;

bool     buyEnabled        = true;
bool     sellEnabled       = true;
bool     dailyBlocked      = false;
bool     basketStopHit     = false;
bool     timeBlocked       = false;
bool     closingMode       = false;
bool     circuitBlocked    = false;
bool     ddBlocked         = false;
datetime circuitBlockUntil = 0;

double   dayStartBalance   = 0;
double   dayMaxDrawdown    = 0;
double   vwapValue         = 0;
double   trailingStopLevel = 0;
bool     basketTrailActive = false;
double   basketTrailPeak   = 0;

int      lastKnownPos       = 0;
double   lastKnownLots      = 0.0;
double   lastKnownBE        = 0.0;
double   lastKnownProfit    = 0.0;
double   basketClosedProfit = 0.0;  // accumulo P&L dei deal di chiusura del basket corrente
bool     tradeWasOpen       = false;
int      dayTrades          = 0;
double   dayGrossProfit     = 0.0;
double   dayGrossLoss       = 0.0;

// Cache VWAP: somme delle sole barre CHIUSE del giorno
datetime vwapBarTime  = 0;
double   vwapClosedPV = 0;
double   vwapClosedV  = 0;

datetime lastBarTime  = 0;
datetime lastDayReset = 0;
int      Magic        = 20250101;
string   objPrefix    = "PHT_";
string   pnlPrefix    = "PHTPNL_";
int      _prevPosCount = 0;
bool     _boardReady   = false;

// Stato linee grafiche disegnate (per cancellare solo gli oggetti stale)
int      _linesPosDrawn  = 0;
int      _linesGridDrawn = 0;
bool     _linesActive    = false;

//+------------------------------------------------------------------+
//| EXPERT INIT                                                      |
//+------------------------------------------------------------------+
int OnInit()
{
   trade.SetExpertMagicNumber(Magic);
   trade.SetDeviationInPoints(10);
   trade.SetTypeFillingBySymbol(_Symbol);

   // La logica grid conta le posizioni per simbolo: su conto NETTING le
   // posizioni si fondono in una sola e i livelli grid non sono tracciabili
   if((ENUM_ACCOUNT_MARGIN_MODE)AccountInfoInteger(ACCOUNT_MARGIN_MODE) !=
      ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
      Print("PHANTOM: ATTENZIONE - conto in modalita' NETTING: le posizioni si fondono ",
            "e la logica grid non funziona correttamente. Usare un conto HEDGING.");

   adxHandle   = iADX(_Symbol, PERIOD_M1, InpADX_Period);
   stochHandle = iStochastic(_Symbol, PERIOD_M1, InpStoch_K, InpStoch_D,
                             InpStoch_Slowing, MODE_SMA, STO_LOWHIGH);
   obvHandle   = iOBV(_Symbol, PERIOD_M15, VOLUME_TICK);
   atrHandle   = iATR(_Symbol, PERIOD_M1, InpATR_Period);

   if(adxHandle==INVALID_HANDLE || stochHandle==INVALID_HANDLE ||
      obvHandle==INVALID_HANDLE  || atrHandle==INVALID_HANDLE)
   {
      Print("PHANTOM: Errore inizializzazione indicatori");
      return INIT_FAILED;
   }

   ArraySetAsSeries(adxMain,     true);
   ArraySetAsSeries(adxPlus,     true);
   ArraySetAsSeries(adxMinus,    true);
   ArraySetAsSeries(stochMain,   true);
   ArraySetAsSeries(stochSignal, true);
   ArraySetAsSeries(obvBuffer,   true);

   dayStartBalance = AccountInfoDouble(ACCOUNT_BALANCE);
   lastDayReset    = GetDayStart(TimeCurrent());
   dayMaxDrawdown  = 0;
   lastBarTime     = 0;
   vwapBarTime     = 0;

   if(InpDailyLossLimit <= 0)
      Print("PHANTOM: Daily Loss Limit DISABILITATO (impostato a 0)");

   // Board sempre ricreata da zero: Delete+Create evita la board vuota
   // dopo un cambio parametri (OnDeinit con REASON_PARAMETERS non cancella)
   _boardReady = false;
   DeleteBoardObjects();
   DeleteTradeLines();     // le linee vengono ridisegnate col prossimo tick
                           // usando i NUOVI colori/etichette degli input
   DrawBoard();
   _boardReady = true;

   ScanBasket();
   UpdateVWAP();
   if(RefreshIndicators()) UpdateBoard();

   // Timer 1s: filtro orario e board restano aggiornati anche senza tick
   EventSetTimer(1);

   // Log dei parametri realmente attivi: dopo ogni cambio input questo
   // blocco compare nel tab Esperti e permette di verificare che le
   // nuove impostazioni siano state applicate
   MqlDateTime dtNow;
   TimeToStruct(TimeCurrent(), dtNow);
   Print("PHANTOM EA v", EA_VERSION, " avviato su ", _Symbol);
   PrintFormat("PHANTOM: filtro orario %s - finestra %s (ORA SERVER, adesso %02d:%02d)",
               InpTimeFilter ? "ON" : "OFF", GetTimeString(), dtNow.hour, dtNow.min);
   PrintFormat("PHANTOM: grid %d pt x %d livelli, mult %.2f | TP first %d / basket %d pt | lotto base %.2f",
               InpGridStep, InpMaxGridOrders, InpLotMultiplier,
               InpTP_First, InpTP_Basket, CalcBaseLot());
   PrintFormat("PHANTOM: protezioni - DailyLoss %.1f%% | BasketSL %.1f%% | MaxDD %.1f%% | CB %s (%d liv/%dh) | ATR max %.1f pips",
               InpDailyLossLimit, InpBasketStopLoss, InpMaxDrawdownPct,
               InpCB_Enabled ? "ON" : "OFF", InpCB_TriggerLevels, InpCB_PauseHours,
               InpATR_MaxPips);
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| EXPERT DEINIT                                                    |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   // Su cambio parametri gli oggetti restano: OnInit li ricrea comunque
   // e cosi' la board non "sparisce" durante la riconfigurazione
   if(reason != REASON_PARAMETERS)
   {
      _boardReady = false;
      DeleteAllObjects();
   }
   IndicatorRelease(adxHandle);
   IndicatorRelease(stochHandle);
   IndicatorRelease(obvHandle);
   IndicatorRelease(atrHandle);
}

//+------------------------------------------------------------------+
//| ON TRADE TRANSACTION                                             |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest     &request,
                        const MqlTradeResult      &result)
{
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD) return;

   ulong dealTicket = trans.deal;
   if(!HistoryDealSelect(dealTicket)) return;

   // Accetta deal dell'EA (Magic) oppure chiusure manuali (Magic=0) sullo stesso simbolo
   long dealMagic = HistoryDealGetInteger(dealTicket, DEAL_MAGIC);
   if(dealMagic != Magic && dealMagic != 0) return;
   if(HistoryDealGetString(dealTicket, DEAL_SYMBOL) != _Symbol) return;

   ENUM_DEAL_ENTRY entry = (ENUM_DEAL_ENTRY)HistoryDealGetInteger(dealTicket, DEAL_ENTRY);
   if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_INOUT) return;

   double dealProfit = HistoryDealGetDouble(dealTicket, DEAL_PROFIT)
                     + HistoryDealGetDouble(dealTicket, DEAL_SWAP)
                     + HistoryDealGetDouble(dealTicket, DEAL_COMMISSION);

   // Statistiche: deal dell'EA sempre; deal manuali solo se gestiti dall'EA
   if(dealMagic == Magic || (InpManageManualOrders && dealMagic == 0))
   {
      dayTrades++;
      if(dealProfit >= 0) dayGrossProfit += dealProfit;
      else                dayGrossLoss   += dealProfit;
      basketClosedProfit += dealProfit;
      lastKnownProfit     = basketClosedProfit;
   }

   if(InpPnL_Labels)
   {
      datetime dealTime  = (datetime)HistoryDealGetInteger(dealTicket, DEAL_TIME);
      double   dealPrice = HistoryDealGetDouble(dealTicket, DEAL_PRICE);
      DrawPnLLabel(dealTicket, dealTime, dealPrice, dealProfit);
   }
}

//+------------------------------------------------------------------+
//| EXPERT TICK                                                      |
//+------------------------------------------------------------------+
void OnTick()
{
   CheckDayReset();
   ScanBasket();
   UpdateVWAP();
   UpdateDrawdownStats();               // DD giornaliero aggiornato SEMPRE

   if(!RefreshIndicators()) return;
   CheckTimeFilter();
   CheckCircuitBreaker();
   SnapshotBasket();

   //--- Protezioni capitale: chiudono tutto e bloccano i nuovi ingressi
   if(CheckMaxDrawdown() || CheckDailyLoss() || CheckBasketStop())
   {
      ScanBasket();                     // riflette le chiusure appena eseguite
      UpdateLines();
      UpdateBoard();
      return;
   }

   //--- Gestione basket: SEMPRE attiva finche' ci sono posizioni,
   //    anche con circuit breaker o closing mode (solo i NUOVI ingressi
   //    base vengono bloccati, mai la gestione dell'esposizione esistente)
   if(basket.count > 0)
   {
      ManageOpenPositions();
      if(!closingMode || InpCloseModeGrid) ManageGrid();
      if(InpTrailingEnabled) ManageTrailingStop();
      CheckBasketTrailing();
   }

   //--- Nuovo ingresso base: solo a barra nuova, flat e senza blocchi
   datetime currentBar = iTime(_Symbol, PERIOD_M1, 0);
   bool newBar = (currentBar != lastBarTime);
   if(newBar) lastBarTime = currentBar;

   bool entryAllowed = !dailyBlocked && !timeBlocked && !closingMode &&
                       !circuitBlocked && !ddBlocked && !basketStopHit;
   if(newBar && basket.count == 0 && entryAllowed)
   {
      int signal = GetEntrySignal();
      if(signal != 0 && CheckATRFilter())
      {
         if(signal > 0 && buyEnabled)       TryOpenBase(ORDER_TYPE_BUY);
         else if(signal < 0 && sellEnabled) TryOpenBase(ORDER_TYPE_SELL);
      }
   }

   UpdateLines();
   UpdateBoard();
}

//+------------------------------------------------------------------+
//| EXPERT TIMER (1s)                                                |
//| Mantiene filtro orario, stato e board aggiornati anche in        |
//| assenza di tick (mercato fermo, spread congelato, weekend):      |
//| senza questo, dopo un cambio parametri la board mostrava i       |
//| vecchi valori finche' non arrivava un tick.                      |
//+------------------------------------------------------------------+
void OnTimer()
{
   CheckDayReset();
   ScanBasket();
   CheckTimeFilter();
   CheckCircuitBreaker();
   SnapshotBasket();
   UpdateBoard();
}

//+------------------------------------------------------------------+
//| SCAN BASKET - unica scansione posizioni per tick                 |
//+------------------------------------------------------------------+
void ScanBasket()
{
   basket.count     = 0;
   basket.lots      = 0;
   basket.breakEven = 0;
   basket.profit    = 0;
   basket.lastPrice = 0;
   basket.lastLot   = 0;
   basket.tp        = 0;
   basket.type      = POSITION_TYPE_BUY;

   double   sumPV     = 0;
   datetime firstTime = 0;
   datetime lastTime  = 0;

   for(int i = PositionsTotal()-1; i >= 0; i--)
   {
      if(!posInfo.SelectByIndex(i) || !IsManagedPosition()) continue;

      basket.count++;
      basket.lots   += posInfo.Volume();
      basket.profit += posInfo.Profit() + posInfo.Swap() + posInfo.Commission();
      sumPV         += posInfo.PriceOpen() * posInfo.Volume();

      if(firstTime == 0 || posInfo.Time() < firstTime)
      {
         firstTime   = posInfo.Time();
         basket.type = posInfo.PositionType();
      }
      if(posInfo.Time() >= lastTime)
      {
         lastTime         = posInfo.Time();
         basket.lastPrice = posInfo.PriceOpen();
         basket.lastLot   = posInfo.Volume();
      }
      if(basket.tp == 0 && posInfo.TakeProfit() > 0)
         basket.tp = posInfo.TakeProfit();
   }

   if(basket.lots > 0)
      basket.breakEven = NormalizeDouble(sumPV / basket.lots, _Digits);
}

// Memorizza gli ultimi valori noti per il display a basket chiuso
void SnapshotBasket()
{
   if(basket.count > 0)
   {
      if(!tradeWasOpen) basketClosedProfit = 0;   // nuovo basket: azzera l'accumulo
      tradeWasOpen  = true;
      lastKnownPos  = basket.count;
      lastKnownLots = basket.lots;
      lastKnownBE   = basket.breakEven;
   }
   else if(tradeWasOpen)
   {
      tradeWasOpen  = false;
      lastKnownPos  = 0;
      lastKnownLots = 0.0;
      lastKnownBE   = 0.0;
   }
}

//+------------------------------------------------------------------+
//| RESET GIORNALIERO                                                |
//+------------------------------------------------------------------+
void CheckDayReset()
{
   datetime todayStart = GetDayStart(TimeCurrent());
   if(todayStart <= lastDayReset) return;

   lastDayReset      = todayStart;
   dayStartBalance   = AccountInfoDouble(ACCOUNT_BALANCE);
   dayMaxDrawdown    = 0;
   dailyBlocked      = false;
   timeBlocked       = false;
   closingMode       = false;
   circuitBlocked    = false;
   basketStopHit     = false;
   ddBlocked         = false;
   circuitBlockUntil = 0;
   lastBarTime       = 0;
   lastKnownPos      = 0;
   lastKnownLots     = 0.0;
   lastKnownBE       = 0.0;
   lastKnownProfit   = 0.0;
   basketClosedProfit= 0.0;
   tradeWasOpen      = false;
   basketTrailActive = false;
   basketTrailPeak   = 0;
   dayTrades         = 0;
   dayGrossProfit    = 0.0;
   dayGrossLoss      = 0.0;
   Print("PHANTOM: Nuovo giorno - reset. Balance=", DoubleToString(dayStartBalance,2));
}

datetime GetDayStart(datetime t)
{
   MqlDateTime dt;
   TimeToStruct(t, dt);
   dt.hour = 0; dt.min = 0; dt.sec = 0;
   return StructToTime(dt);
}

//+------------------------------------------------------------------+
//| FILTRO ORARIO                                                    |
//| Gli orari sono in ORA DEL SERVER del broker (TimeCurrent), NON   |
//| nell'ora locale del PC: la riga "Ora server" sulla board mostra  |
//| il riferimento usato. Supporta finestre a cavallo della          |
//| mezzanotte (es. 22:00-02:00).                                    |
//+------------------------------------------------------------------+
int ClampInt(int v, int lo, int hi)
{
   return (v < lo) ? lo : ((v > hi) ? hi : v);
}

bool IsInTradeWindow()
{
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   int nowMins   = dt.hour * 60 + dt.min;
   int startMins = ClampInt(InpStartHour,0,23)*60 + ClampInt(InpStartMin,0,59);
   int endMins   = ClampInt(InpEndHour,  0,23)*60 + ClampInt(InpEndMin,  0,59);

   if(startMins == endMins) return true;                          // finestra nulla = filtro di fatto off
   if(startMins < endMins)  return (nowMins >= startMins && nowMins < endMins);
   return (nowMins >= startMins || nowMins < endMins);            // a cavallo della mezzanotte
}

void CheckTimeFilter()
{
   if(!InpTimeFilter)
   {
      timeBlocked = false;
      closingMode = false;
      return;
   }

   bool inWindow = IsInTradeWindow();

   if(inWindow)
   {
      timeBlocked = false;
      closingMode = false;
      return;
   }

   if(basket.count > 0)
   {
      closingMode = true;
      timeBlocked = false;
      if(basket.count != _prevPosCount)
      {
         Print("PHANTOM: Fuori orario - closing mode attivo (", basket.count, " posizioni)");
         _prevPosCount = basket.count;
      }
   }
   else
   {
      closingMode = false;
      timeBlocked = true;
   }
}

//+------------------------------------------------------------------+
//| REFRESH INDICATORS                                               |
//+------------------------------------------------------------------+
bool RefreshIndicators()
{
   if(CopyBuffer(adxHandle,   0, 0, 4, adxMain)     < 3) return false;
   if(CopyBuffer(adxHandle,   1, 0, 4, adxPlus)     < 3) return false;
   if(CopyBuffer(adxHandle,   2, 0, 4, adxMinus)    < 3) return false;
   if(CopyBuffer(stochHandle, 0, 0, 4, stochMain)   < 3) return false;
   if(CopyBuffer(stochHandle, 1, 0, 4, stochSignal) < 3) return false;
   if(CopyBuffer(obvHandle,   0, 0, 4, obvBuffer)   < 3) return false;
   return true;
}

//+------------------------------------------------------------------+
//| CIRCUIT BREAKER - blocca solo i NUOVI ingressi base              |
//+------------------------------------------------------------------+
void CheckCircuitBreaker()
{
   if(!InpCB_Enabled) { circuitBlocked = false; return; }

   if(circuitBlocked && TimeCurrent() >= circuitBlockUntil)
   {
      circuitBlocked = false;
      Print("PHANTOM: Circuit breaker scaduto - ingressi riabilitati");
   }

   if(!circuitBlocked && basket.count >= InpCB_TriggerLevels)
   {
      circuitBlocked    = true;
      circuitBlockUntil = TimeCurrent() + InpCB_PauseHours * 3600;
      Print("PHANTOM: Circuit breaker ATTIVATO (", basket.count, " livelli grid) - pausa ",
            InpCB_PauseHours, "h fino a ", TimeToString(circuitBlockUntil, TIME_DATE|TIME_MINUTES));
   }
}

//+------------------------------------------------------------------+
//| ATR FILTER CHECK                                                 |
//+------------------------------------------------------------------+
bool CheckATRFilter()
{
   if(!InpATR_Enabled || InpATR_MaxPips <= 0) return true;

   double atrBuf[];
   ArraySetAsSeries(atrBuf, true);
   if(CopyBuffer(atrHandle, 0, 0, 3, atrBuf) < 2) return true;

   // Convenzione: 1 pip = 10 punti (valida per XAUUSD a 2 decimali e FX a 5/3)
   double atrPips = atrBuf[1] / (_Point * 10);
   if(atrPips > InpATR_MaxPips)
   {
      static datetime lastATRLog = 0;
      datetime curBar = iTime(_Symbol, PERIOD_M1, 0);
      if(curBar != lastATRLog)
      {
         lastATRLog = curBar;
         Print("PHANTOM: ATR filter - volatilita' troppo alta (", DoubleToString(atrPips,1),
               " pips > max ", DoubleToString(InpATR_MaxPips,1), ") - ingresso bloccato");
      }
      return false;
   }
   return true;
}

//+------------------------------------------------------------------+
//| ENTRY SIGNAL                                                     |
//+------------------------------------------------------------------+
int GetEntrySignal()
{
   // --- MODALITA' FILTRI DISABILITATI ---
   // Tutti gli indicatori vengono ignorati; la direzione e' determinata
   // da prezzo vs VWAP (buy sopra, sell sotto). Se VWAP non e' disponibile,
   // si forza BUY di default. Il filtro ATR resta comunque attivo se abilitato.
   if(InpDisableAllFilters)
   {
      if(vwapValue > 0)
      {
         double price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         return (price >= vwapValue) ? 1 : -1;
      }
      return 1;
   }

   double adx      = adxMain[1];
   double stoch    = stochMain[1];
   double stochSig = stochSignal[1];
   double price    = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   if(adx < InpADX_Min || adx > InpADX_Max) return 0;
   if(!CheckVolumeSpike()) return 0;

   int scoreBuy = 0, scoreSell = 0;
   if(InpOBV_Filter && ArraySize(obvBuffer) >= 3)
   {
      if(obvBuffer[1] > obvBuffer[2]) scoreBuy++;
      else                            scoreSell++;
   }
   if(InpVWAP_Filter && vwapValue > 0)
   {
      if(price > vwapValue) scoreBuy++;
      else                  scoreSell++;
   }
   bool softDisabled = (!InpOBV_Filter && !InpVWAP_Filter);

   if(stoch < InpStoch_OS && stoch > stochSig)
      if(softDisabled || scoreBuy >= 1) return 1;
   if(stoch > InpStoch_OB && stoch < stochSig)
      if(softDisabled || scoreSell >= 1) return -1;

   return 0;
}

//+------------------------------------------------------------------+
//| VOLUME SPIKE CHECK                                               |
//+------------------------------------------------------------------+
bool CheckVolumeSpike()
{
   long volBuf[];
   ArraySetAsSeries(volBuf, true);
   if(CopyTickVolume(_Symbol, PERIOD_M1, 0, InpVolSpike_Period+2, volBuf) < InpVolSpike_Period+2)
      return true;
   double avg = 0;
   for(int i = 1; i <= InpVolSpike_Period; i++) avg += (double)volBuf[i];
   avg /= InpVolSpike_Period;
   return ((double)volBuf[1] >= avg * InpVolSpike_Min);
}

//+------------------------------------------------------------------+
//| VWAP INTRADAY - incrementale                                     |
//| Le somme delle barre CHIUSE del giorno vengono ricalcolate solo  |
//| a barra nuova; a ogni tick si aggiunge solo la barra corrente.   |
//+------------------------------------------------------------------+
void UpdateVWAP()
{
   datetime curBar = iTime(_Symbol, PERIOD_M1, 0);
   if(curBar == 0) return;

   if(curBar != vwapBarTime)
   {
      vwapBarTime  = curBar;
      vwapClosedPV = 0;
      vwapClosedV  = 0;
      datetime dayStart = GetDayStart(TimeCurrent());
      int bars = Bars(_Symbol, PERIOD_M1, dayStart, curBar);
      for(int i = 1; i < bars; i++)
      {
         double tp = (iHigh(_Symbol,PERIOD_M1,i) +
                      iLow(_Symbol, PERIOD_M1,i) +
                      iClose(_Symbol,PERIOD_M1,i)) / 3.0;
         double v  = (double)iVolume(_Symbol, PERIOD_M1, i);
         vwapClosedPV += tp * v;
         vwapClosedV  += v;
      }
   }

   double tp0 = (iHigh(_Symbol,PERIOD_M1,0) +
                 iLow(_Symbol, PERIOD_M1,0) +
                 iClose(_Symbol,PERIOD_M1,0)) / 3.0;
   double v0  = (double)iVolume(_Symbol, PERIOD_M1, 0);
   double sPV = vwapClosedPV + tp0 * v0;
   double sV  = vwapClosedV  + v0;
   if(sV > 0) vwapValue = NormalizeDouble(sPV / sV, _Digits);
}

//+------------------------------------------------------------------+
//| APERTURA ORDINI                                                  |
//+------------------------------------------------------------------+
void TryOpenBase(ENUM_ORDER_TYPE type)
{
   if(OpenOrder(type, CalcBaseLot(), 0))
   {
      ScanBasket();
      DrawEntryArrow(type, trade.ResultOrder());
   }
}

bool OpenOrder(ENUM_ORDER_TYPE type, double lots, int gridLevel)
{
   lots = NormalizeLot(lots);
   double price = (type==ORDER_TYPE_BUY) ?
                  SymbolInfoDouble(_Symbol,SYMBOL_ASK) :
                  SymbolInfoDouble(_Symbol,SYMBOL_BID);

   if(!CheckMargin(type, lots, price))
   {
      Print("PHANTOM: margine libero insufficiente per ", DoubleToString(lots,2),
            " lotti - ordine livello ", gridLevel, " annullato");
      return false;
   }

   double tp = 0;
   if(gridLevel == 0)
   {
      if(InpTP_Dynamic && vwapValue > 0)
         tp = (type==ORDER_TYPE_BUY) ?
              MathMax(vwapValue, price + InpTP_First*_Point) :
              MathMin(vwapValue, price - InpTP_First*_Point);
      else
         tp = (type==ORDER_TYPE_BUY) ?
              price + InpTP_First*_Point :
              price - InpTP_First*_Point;
      tp = NormalizeDouble(tp, _Digits);
   }

   string comment = "PHANTOM_G" + IntegerToString(gridLevel);
   bool ok = (type==ORDER_TYPE_BUY) ?
             trade.Buy(lots,  _Symbol, price, 0, tp, comment) :
             trade.Sell(lots, _Symbol, price, 0, tp, comment);

   uint rc = trade.ResultRetcode();
   if(!ok || (rc != TRADE_RETCODE_DONE && rc != TRADE_RETCODE_DONE_PARTIAL))
   {
      Print("PHANTOM: apertura ordine fallita - retcode ", rc,
            " (", trade.ResultRetcodeDescription(), ")");
      return false;
   }
   return true;
}

// Allinea il lotto a VOLUME_STEP e lo vincola tra VOLUME_MIN e VOLUME_MAX
double NormalizeLot(double lot)
{
   double volMin  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double volMax  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double volStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(volStep > 0) lot = MathRound(lot / volStep) * volStep;
   if(lot < volMin) lot = volMin;
   if(volMax > 0 && lot > volMax) lot = volMax;
   return NormalizeDouble(lot, 8);
}

bool CheckMargin(ENUM_ORDER_TYPE type, double lots, double price)
{
   double need = 0;
   if(!OrderCalcMargin(type, _Symbol, lots, price, need))
      return true;   // in caso di errore di calcolo non blocca: decide il server
   return (AccountInfoDouble(ACCOUNT_MARGIN_FREE) >= need);
}

//+------------------------------------------------------------------+
//| MANAGE GRID                                                      |
//+------------------------------------------------------------------+
void ManageGrid()
{
   if(basket.count == 0 || basket.count >= InpMaxGridOrders) return;
   if(basket.lastPrice <= 0) return;

   double gridDist     = InpGridStep * _Point;
   double currentPrice = (basket.type==POSITION_TYPE_BUY) ?
                          SymbolInfoDouble(_Symbol,SYMBOL_BID) :
                          SymbolInfoDouble(_Symbol,SYMBOL_ASK);

   bool need = false;
   if(basket.type==POSITION_TYPE_BUY  && currentPrice <= basket.lastPrice - gridDist) need = true;
   if(basket.type==POSITION_TYPE_SELL && currentPrice >= basket.lastPrice + gridDist) need = true;
   if(!need) return;

   ENUM_ORDER_TYPE otype = (basket.type==POSITION_TYPE_BUY) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   if(OpenOrder(otype, GetNextLot(), basket.count))
   {
      ScanBasket();       // include il livello appena aperto
      UpdateBasketTP();
   }
}

//+------------------------------------------------------------------+
//| MANAGE OPEN POSITIONS - Basket TP                                |
//+------------------------------------------------------------------+
void ManageOpenPositions()
{
   if(basket.count < 2 || basket.breakEven <= 0) return;

   double dist = InpTP_Basket * _Point;
   double currentPrice = (basket.type==POSITION_TYPE_BUY) ?
                          SymbolInfoDouble(_Symbol,SYMBOL_BID) :
                          SymbolInfoDouble(_Symbol,SYMBOL_ASK);

   bool hit = (basket.type==POSITION_TYPE_BUY  && currentPrice >= basket.breakEven + dist) ||
              (basket.type==POSITION_TYPE_SELL && currentPrice <= basket.breakEven - dist);
   if(hit)
   {
      Print("PHANTOM: Basket TP raggiunto - chiudo tutto");
      CloseAllPositions();
      ScanBasket();
   }
}

//+------------------------------------------------------------------+
//| TRAILING STOP (SL reale sul server)                              |
//| Con 2+ ordini lavora sul breakeven del basket, altrimenti sul    |
//| singolo ordine.                                                  |
//+------------------------------------------------------------------+
void ManageTrailingStop()
{
   if(basket.count == 0) return;

   double dist  = InpTrailingDistance * _Point;
   double start = InpTrailingStart    * _Point;
   double step  = InpTrailingStep     * _Point;
   double bid   = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask   = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

   if(basket.count >= 2)
   {
      if(basket.type == POSITION_TYPE_BUY)
      {
         if(bid - basket.breakEven >= start)
            ApplyBasketSL(NormalizeDouble(bid - dist, _Digits), step, true);
      }
      else
      {
         if(basket.breakEven - ask >= start)
            ApplyBasketSL(NormalizeDouble(ask + dist, _Digits), step, false);
      }
      return;
   }

   for(int i = PositionsTotal()-1; i >= 0; i--)
   {
      if(!posInfo.SelectByIndex(i) || !IsManagedPosition()) continue;
      double open = posInfo.PriceOpen();
      double sl   = posInfo.StopLoss();
      if(posInfo.PositionType()==POSITION_TYPE_BUY)
      {
         if(bid - open >= start)
         {
            double nsl = NormalizeDouble(bid - dist, _Digits);
            if(sl == 0 || nsl > sl + step)
            { trade.PositionModify(posInfo.Ticket(), nsl, posInfo.TakeProfit()); trailingStopLevel = nsl; }
         }
      }
      else
      {
         if(open - ask >= start)
         {
            double nsl = NormalizeDouble(ask + dist, _Digits);
            if(sl == 0 || nsl < sl - step)
            { trade.PositionModify(posInfo.Ticket(), nsl, posInfo.TakeProfit()); trailingStopLevel = nsl; }
         }
      }
   }
}

void ApplyBasketSL(double nsl, double step, bool isBuy)
{
   for(int i = PositionsTotal()-1; i >= 0; i--)
   {
      if(!posInfo.SelectByIndex(i) || !IsManagedPosition()) continue;
      double curSL = posInfo.StopLoss();
      bool better = (curSL == 0) || (isBuy ? (nsl > curSL + step) : (nsl < curSL - step));
      if(better)
      {
         trade.PositionModify(posInfo.Ticket(), nsl, posInfo.TakeProfit());
         trailingStopLevel = nsl;
      }
   }
}

//+------------------------------------------------------------------+
//| BASKET TRAILING STOP                                             |
//| Trailing "virtuale" (non SL sul server) calcolato sul profitto   |
//| dell'intero basket rispetto al breakeven. Una volta attivato,    |
//| segue il picco di profitto e, se il prezzo retrocede di          |
//| InpBasketTrailingDistance dal picco, chiude TUTTO il basket.     |
//+------------------------------------------------------------------+
void CheckBasketTrailing()
{
   if(!InpBasketTrailingEnabled) return;

   if(basket.count == 0)
   {
      basketTrailActive = false;
      basketTrailPeak   = 0;
      return;
   }
   if(basket.breakEven <= 0) return;

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

   double startDist = InpBasketTrailingStart    * _Point;
   double stepDist  = InpBasketTrailingStep     * _Point;
   double trailDist = InpBasketTrailingDistance * _Point;

   double profitDist = (basket.type == POSITION_TYPE_BUY) ?
                       (bid - basket.breakEven) : (basket.breakEven - ask);

   if(!basketTrailActive)
   {
      if(profitDist >= startDist)
      {
         basketTrailActive = true;
         basketTrailPeak   = profitDist;
      }
      return;
   }

   if(profitDist > basketTrailPeak + stepDist)
      basketTrailPeak = profitDist;

   if(basketTrailPeak - profitDist >= trailDist)
   {
      Print("PHANTOM: Basket Trailing Stop - chiudo tutto il basket. Picco ",
            DoubleToString(basketTrailPeak/_Point,1), " punti, ritracciamento a ",
            DoubleToString(profitDist/_Point,1), " punti.");
      CloseAllPositions();
      ScanBasket();
   }
}

//+------------------------------------------------------------------+
//| UPDATE BASKET TP                                                 |
//+------------------------------------------------------------------+
void UpdateBasketTP()
{
   if(basket.count == 0 || basket.breakEven <= 0) return;

   double ntp = (basket.type==POSITION_TYPE_BUY) ?
                NormalizeDouble(basket.breakEven + InpTP_Basket*_Point, _Digits) :
                NormalizeDouble(basket.breakEven - InpTP_Basket*_Point, _Digits);

   for(int i = PositionsTotal()-1; i >= 0; i--)
   {
      if(!posInfo.SelectByIndex(i) || !IsManagedPosition()) continue;
      if(MathAbs(posInfo.TakeProfit() - ntp) > 0.5*_Point)
         trade.PositionModify(posInfo.Ticket(), posInfo.StopLoss(), ntp);
   }
}

//+------------------------------------------------------------------+
//| PROTEZIONI CAPITALE                                              |
//+------------------------------------------------------------------+

// DD massimo giornaliero: aggiornato ogni tick, indipendente dai blocchi
void UpdateDrawdownStats()
{
   if(dayStartBalance <= 0) return;
   double drawdown = (dayStartBalance - AccountInfoDouble(ACCOUNT_EQUITY)) /
                     dayStartBalance * 100.0;
   if(drawdown > dayMaxDrawdown) dayMaxDrawdown = drawdown;
}

// Chiude TUTTO se l'equity scende di InpMaxDrawdownPct% dal balance di
// inizio giorno. Il blocco dura fino al reset giornaliero (CheckDayReset).
bool CheckMaxDrawdown()
{
   if(InpMaxDrawdownPct <= 0) return false;
   if(ddBlocked) return true;

   double refBalance = (dayStartBalance > 0) ? dayStartBalance
                                             : AccountInfoDouble(ACCOUNT_BALANCE);
   if(refBalance <= 0) return false;

   double ddPct = (refBalance - AccountInfoDouble(ACCOUNT_EQUITY)) / refBalance * 100.0;
   if(ddPct >= InpMaxDrawdownPct)
   {
      ddBlocked = true;
      Print("PHANTOM: MAX DRAWDOWN - DD=", DoubleToString(ddPct,2),
            "% >= ", DoubleToString(InpMaxDrawdownPct,2),
            "% - chiudo tutto, riparto domani");
      CloseAllPositions();
      return true;
   }
   return false;
}

bool CheckDailyLoss()
{
   if(InpDailyLossLimit <= 0) return false;
   if(dailyBlocked) return true;
   if(dayStartBalance <= 0) return false;

   double drawdown = (dayStartBalance - AccountInfoDouble(ACCOUNT_EQUITY)) /
                     dayStartBalance * 100.0;
   if(drawdown >= InpDailyLossLimit)
   {
      if(basket.count > 0) CloseAllPositions();
      dailyBlocked = true;
      Print("PHANTOM: Daily loss ", DoubleToString(drawdown,2),
            "% - EA bloccato fino a domani");
      return true;
   }
   return false;
}

// Hard stop sul floating loss del SOLO basket (non dell'intero conto)
bool CheckBasketStop()
{
   if(InpBasketStopLoss <= 0) return false;
   if(basketStopHit)          return true;
   if(basket.count == 0)      return false;

   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   if(balance <= 0) return false;

   double floatingLoss = -basket.profit;
   if(floatingLoss <= 0) return false;

   double lossPct = floatingLoss / balance * 100.0;
   if(lossPct >= InpBasketStopLoss)
   {
      CloseAllPositions();
      basketStopHit = true;
      Print("PHANTOM: Basket Stop attivato - floating loss ",
            DoubleToString(lossPct,2),"% >= soglia ",
            DoubleToString(InpBasketStopLoss,2),"%");
      return true;
   }
   return false;
}

//+------------------------------------------------------------------+
//| CLOSE ALL                                                        |
//+------------------------------------------------------------------+
void CloseAllPositions()
{
   for(int i = PositionsTotal()-1; i >= 0; i--)
   {
      if(!posInfo.SelectByIndex(i) || !IsManagedPosition()) continue;
      if(!trade.PositionClose(posInfo.Ticket()))
         Print("PHANTOM: chiusura ticket ", posInfo.Ticket(),
               " fallita - retcode ", trade.ResultRetcode(),
               " (", trade.ResultRetcodeDescription(), ")");
   }
   trailingStopLevel = 0;
   basketTrailActive = false;
   basketTrailPeak   = 0;
   DeleteTradeLines();
}

//+------------------------------------------------------------------+
//| UTILITIES                                                        |
//+------------------------------------------------------------------+
// Vera per le posizioni dell'EA (Magic) e, se InpManageManualOrders e'
// attivo, anche per le posizioni manuali (magic=0) sullo stesso simbolo.
// Non tocca mai posizioni di ALTRI EA (magic diverso da 0 e da Magic).
bool IsManagedPosition()
{
   if(posInfo.Symbol() != _Symbol) return false;
   if(posInfo.Magic() == Magic) return true;
   if(InpManageManualOrders && posInfo.Magic() == 0) return true;
   return false;
}

double CalcBaseLot()
{
   double lot = InpLotSize;
   if(InpDynamicLot && InpLotPerBalance > 0)
   {
      double balance = AccountInfoDouble(ACCOUNT_BALANCE);
      double dynLot  = (balance / InpLotPerBalance) * 0.01;
      lot = MathMax(dynLot, InpLotSize);
   }
   return NormalizeLot(lot);
}

double GetNextLot()
{
   if(basket.lastLot <= 0) return CalcBaseLot();
   return NormalizeLot(basket.lastLot * InpLotMultiplier);
}

string GetTimeString()
{
   return StringFormat("%02d:%02d - %02d:%02d",
          InpStartHour, InpStartMin, InpEndHour, InpEndMin);
}

//+------------------------------------------------------------------+
//| ETICHETTE P&L SUL GRAFICO                                        |
//+------------------------------------------------------------------+
// Nomi oggetto con ticket a 64 bit (%I64u): IntegerToString((int)ticket)
// troncava il valore generando nomi duplicati/negativi
void DrawEntryArrow(ENUM_ORDER_TYPE type, ulong ticket)
{
   if(!InpPnL_Labels) return;
   if(ticket == 0) ticket = (ulong)GetTickCount64();   // fallback anti-collisione

   datetime t   = TimeCurrent();
   double   bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   string   name = pnlPrefix + "ARW_" + StringFormat("%I64u", ticket);

   int   arrowCode = (type==ORDER_TYPE_BUY) ? 233 : 234;
   color arrowCol  = (type==ORDER_TYPE_BUY) ? InpPnL_Arrow_Buy : InpPnL_Arrow_Sell;

   if(ObjectFind(0, name) < 0)
      ObjectCreate(0, name, OBJ_ARROW, 0, t, bid);
   ObjectSetInteger(0, name, OBJPROP_TIME,      (long)t);
   ObjectSetDouble(0,  name, OBJPROP_PRICE,     bid);
   ObjectSetInteger(0, name, OBJPROP_ARROWCODE, arrowCode);
   ObjectSetInteger(0, name, OBJPROP_COLOR,     arrowCol);
   ObjectSetInteger(0, name, OBJPROP_WIDTH,     InpPnL_Arrow_Size);
   ObjectSetInteger(0, name, OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0, name, OBJPROP_BACK,      false);
   ChartRedraw();
}

// OBJPROP_BGCOLOR non e' supportato su OBJ_TEXT con coordinate grafico in
// MT5 (ignorato/resettato silenziosamente): testo colorato senza sfondo
void DrawPnLLabel(ulong ticket, datetime closeTime, double closePrice, double profit)
{
   if(!InpPnL_Labels) return;

   string tickStr  = StringFormat("%I64u", ticket);
   string nameDot  = pnlPrefix + "DOT_" + tickStr;
   string nameTxt  = pnlPrefix + "PNL_" + tickStr;

   string sign = (profit >= 0) ? "+" : "";
   string txt  = sign + DoubleToString(profit, 2) + " $";

   color col = (profit > 0.01)  ? InpPnL_Color_Profit :
               (profit < -0.01) ? InpPnL_Color_Loss    :
                                   InpPnL_Color_BE;

   // --- Bullet punto sul prezzo esatto del deal ---
   if(ObjectFind(0, nameDot) < 0)
      ObjectCreate(0, nameDot, OBJ_ARROW, 0, closeTime, closePrice);
   ObjectSetInteger(0, nameDot, OBJPROP_TIME,      (long)closeTime);
   ObjectSetDouble(0,  nameDot, OBJPROP_PRICE,     closePrice);
   ObjectSetInteger(0, nameDot, OBJPROP_ARROWCODE, 159);
   ObjectSetInteger(0, nameDot, OBJPROP_WIDTH,      2);
   ObjectSetInteger(0, nameDot, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, nameDot, OBJPROP_BACK,       false);
   ObjectSetInteger(0, nameDot, OBJPROP_COLOR,      col);

   // --- Testo P&L sopra il punto di chiusura (ANCHOR_LEFT_LOWER) ---
   if(ObjectFind(0, nameTxt) < 0)
      ObjectCreate(0, nameTxt, OBJ_TEXT, 0, closeTime, closePrice);
   ObjectSetInteger(0, nameTxt, OBJPROP_TIME,      (long)closeTime);
   ObjectSetDouble(0,  nameTxt, OBJPROP_PRICE,     closePrice);
   ObjectSetString(0,  nameTxt, OBJPROP_TEXT,      " " + txt + " ");
   ObjectSetInteger(0, nameTxt, OBJPROP_FONTSIZE,  InpPnL_FontSize);
   ObjectSetString(0,  nameTxt, OBJPROP_FONT,      "Arial Bold");
   ObjectSetDouble(0,  nameTxt, OBJPROP_ANGLE,     0);
   ObjectSetInteger(0, nameTxt, OBJPROP_ANCHOR,    ANCHOR_LEFT_LOWER);
   ObjectSetInteger(0, nameTxt, OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0, nameTxt, OBJPROP_BACK,      false);
   ObjectSetInteger(0, nameTxt, OBJPROP_COLOR,     col);

   ChartRedraw();
}

//+------------------------------------------------------------------+
//| CHART LINES                                                      |
//| Aggiornate in-place (niente delete+recreate per tick); vengono   |
//| cancellati solo gli oggetti diventati stale.                     |
//+------------------------------------------------------------------+
void UpdateLines()
{
   if(basket.count == 0)
   {
      if(_linesActive) DeleteTradeLines();
      return;
   }
   _linesActive = true;

   double gridDist = InpGridStep * _Point;

   // --- Linee posizioni aperte ---
   int idx = 0;
   for(int i = 0; i < PositionsTotal(); i++)
   {
      if(!posInfo.SelectByIndex(i) || !IsManagedPosition()) continue;
      string lname = objPrefix + "POS_" + IntegerToString(idx);
      color  col, lblCol;
      string label;
      if(idx == 0)
      {
         label  = InpLabel_Entry;
         col    = InpColor_Entry;
         lblCol = InpLabelCol_Entry;
      }
      else
      {
         label  = InpLabel_Grid + IntegerToString(idx);
         col    = InpColor_GridOpen;
         lblCol = InpLabelCol_GridOpen;
      }
      DrawHLine(lname, posInfo.PriceOpen(), col, InpLine_Width, STYLE_SOLID, label);
      DrawLineLabel(lname, posInfo.PriceOpen(), label, lblCol);
      idx++;
   }
   for(int i = idx; i < _linesPosDrawn; i++)
      RemoveLine(objPrefix + "POS_" + IntegerToString(i));
   _linesPosDrawn = idx;

   // --- Linee grid previste ---
   int gcount = InpMaxGridOrders - basket.count;
   if(gcount < 0) gcount = 0;
   for(int g = 1; g <= gcount; g++)
   {
      double gp = (basket.type==POSITION_TYPE_BUY) ?
                   basket.lastPrice - g*gridDist : basket.lastPrice + g*gridDist;
      string gname  = objPrefix + "GRID_" + IntegerToString(g);
      string glabel = InpLabel_Grid + " " + IntegerToString(basket.count + g);
      DrawHLine(gname, gp, InpColor_Grid, InpLine_Width, STYLE_DASH, glabel);
      DrawLineLabel(gname, gp, glabel, InpLabelCol_Grid);
   }
   for(int g = gcount+1; g <= _linesGridDrawn; g++)
      RemoveLine(objPrefix + "GRID_" + IntegerToString(g));
   _linesGridDrawn = gcount;

   // --- Breakeven ---
   if(basket.count > 1 && basket.breakEven > 0)
   {
      DrawHLine(objPrefix+"BE", basket.breakEven, InpColor_BE, InpLine_Width+1, STYLE_SOLID, InpLabel_BE);
      DrawLineLabel(objPrefix+"BE", basket.breakEven, InpLabel_BE, InpLabelCol_BE);
   }
   else
      RemoveLine(objPrefix+"BE");

   // --- Take Profit (basket o singolo: basket.tp copre entrambi) ---
   if(basket.tp > 0)
   {
      DrawHLine(objPrefix+"TP", basket.tp, InpColor_TP, InpLine_Width_TP, STYLE_SOLID, InpLabel_TP);
      DrawLineLabel(objPrefix+"TP", basket.tp, InpLabel_TP, InpLabelCol_TP);
   }
   else
      RemoveLine(objPrefix+"TP");

   // --- Trailing Stop ---
   if(InpTrailingEnabled && trailingStopLevel > 0)
   {
      DrawHLine(objPrefix+"TS", trailingStopLevel, InpColor_TS, InpLine_Width, STYLE_DOT, InpLabel_TS);
      DrawLineLabel(objPrefix+"TS", trailingStopLevel, InpLabel_TS, InpLabelCol_TS);
   }
   else
      RemoveLine(objPrefix+"TS");

   // --- VWAP ---
   if(vwapValue > 0)
   {
      DrawHLine(objPrefix+"VWAP", vwapValue, InpColor_VWAP, 1, STYLE_DOT, InpLabel_VWAP);
      DrawLineLabel(objPrefix+"VWAP", vwapValue, InpLabel_VWAP, InpLabelCol_VWAP);
   }
   else
      RemoveLine(objPrefix+"VWAP");

   ChartRedraw();
}

void DrawHLine(string name, double price, color col, int width,
               ENUM_LINE_STYLE style, string label)
{
   if(ObjectFind(0,name)<0) ObjectCreate(0,name,OBJ_HLINE,0,0,price);
   ObjectSetDouble(0, name,OBJPROP_PRICE,     price);
   ObjectSetInteger(0,name,OBJPROP_COLOR,     col);
   ObjectSetInteger(0,name,OBJPROP_WIDTH,     width);
   ObjectSetInteger(0,name,OBJPROP_STYLE,     style);
   ObjectSetString(0, name,OBJPROP_TEXT,      label);
   ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,name,OBJPROP_BACK,      true);
}

void DrawLineLabel(string baseName, double price, string txt, color col)
{
   string lname = baseName + "_LBL";
   datetime t   = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(ObjectFind(0, lname) < 0)
      ObjectCreate(0, lname, OBJ_TEXT, 0, t, price);
   ObjectSetInteger(0, lname, OBJPROP_TIME,       (long)t);
   ObjectSetDouble(0,  lname, OBJPROP_PRICE,      price);
   ObjectSetString(0,  lname, OBJPROP_TEXT,       txt + " ");
   ObjectSetInteger(0, lname, OBJPROP_FONTSIZE,   InpLabel_FontSize);
   ObjectSetString(0,  lname, OBJPROP_FONT,       "Arial Bold");
   ObjectSetDouble(0,  lname, OBJPROP_ANGLE,      0);
   ObjectSetInteger(0, lname, OBJPROP_ANCHOR,     ANCHOR_RIGHT);
   ObjectSetInteger(0, lname, OBJPROP_SELECTABLE, false);
   ObjectSetInteger(0, lname, OBJPROP_BACK,       false);
   ObjectSetInteger(0, lname, OBJPROP_COLOR,      col);
}

void RemoveLine(string name)
{
   ObjectDelete(0, name);
   ObjectDelete(0, name + "_LBL");
}

// Cancella tutte le linee di trading (nomi deterministici, board esclusa)
void DeleteTradeLines()
{
   int maxN = MathMax(50, InpMaxGridOrders + 1);
   for(int i = 0; i <= maxN; i++)
   {
      RemoveLine(objPrefix + "POS_"  + IntegerToString(i));
      RemoveLine(objPrefix + "GRID_" + IntegerToString(i));
   }
   RemoveLine(objPrefix + "BE");
   RemoveLine(objPrefix + "TP");
   RemoveLine(objPrefix + "TS");
   RemoveLine(objPrefix + "VWAP");
   _linesPosDrawn  = 0;
   _linesGridDrawn = 0;
   _linesActive    = false;
   ChartRedraw();
}

// Cancella la board (linee di trading ed etichette P&L escluse)
void DeleteBoardObjects()
{
   for(int i = ObjectsTotal(0)-1; i >= 0; i--)
   {
      string n = ObjectName(0,i);
      if(StringFind(n, pnlPrefix) == 0) continue;
      if(StringFind(n, objPrefix) != 0) continue;
      bool isLine = (StringFind(n, objPrefix+"POS_")  == 0 ||
                     StringFind(n, objPrefix+"GRID_") == 0 ||
                     StringFind(n, objPrefix+"BE")    == 0 ||
                     StringFind(n, objPrefix+"TP")    == 0 ||
                     StringFind(n, objPrefix+"TS")    == 0 ||
                     StringFind(n, objPrefix+"VWAP")  == 0);
      if(!isLine) ObjectDelete(0,n);
   }
   ChartRedraw();
}

void DeleteAllObjects()
{
   for(int i = ObjectsTotal(0)-1; i >= 0; i--)
   {
      string n = ObjectName(0,i);
      if(StringFind(n,objPrefix)==0 || StringFind(n,pnlPrefix)==0) ObjectDelete(0,n);
   }
   ChartRedraw();
}

//+------------------------------------------------------------------+
//| BOARD GLASS DARK - DRAW                                          |
//+------------------------------------------------------------------+
void DrawBoard()
{
   int x  = InpBoard_X;
   int y  = InpBoard_Y;
   int w  = InpBoard_Width;
   int fs = InpBoard_FontSize;
   int lh = 14;
   int cy = y+10;

   CreateRect(objPrefix+"BOARD_BG",       x, y, w, 444, CLR_BG,  CLR_BORDER);
   CreateRect(objPrefix+"BOARD_TITLE_BG", x, y, w,  26, CLR_BG2, CLR_BORDER);
   CreateLabel(objPrefix+"BOARD_DIAMOND", x+10, cy, "◈",                          CLR_ACCENT, fs+2, "Arial Bold");
   CreateLabel(objPrefix+"BOARD_TITLE",   x+24, cy, "PHANTOM  EA  v"+EA_VERSION,  CLR_ACCENT, fs+1, "Arial Bold");
   cy += 28;

   CreateSectionBar(objPrefix+"S_IND_BG", x, cy-2, w);
   CreateLabel(objPrefix+"S_IND", x+8, cy, "INDICATORI", CLR_DIM, fs-1, "Arial Bold");
   cy += lh+2;
   CreateRowLabel(objPrefix+"LBL_ADX",   x+8, cy, "ADX",     fs); CreateLabelRight(objPrefix+"VAL_ADX",   x+w-6, cy, "--", CLR_GREEN, fs); cy+=lh;
   CreateRowLabel(objPrefix+"LBL_STOCH", x+8, cy, "STOCH",   fs); CreateLabelRight(objPrefix+"VAL_STOCH", x+w-6, cy, "--", CLR_GREEN, fs); cy+=lh;
   CreateRowLabel(objPrefix+"LBL_VOL",   x+8, cy, "VOLUME",  fs); CreateLabelRight(objPrefix+"VAL_VOL",   x+w-6, cy, "--", CLR_GREEN, fs); cy+=lh;
   CreateRowLabel(objPrefix+"LBL_OBV",   x+8, cy, "OBV M15", fs); CreateLabelRight(objPrefix+"VAL_OBV",   x+w-6, cy, "--", CLR_GREEN, fs); cy+=lh;
   CreateRowLabel(objPrefix+"LBL_VWAP",  x+8, cy, "VWAP",    fs); CreateLabelRight(objPrefix+"VAL_VWAP",  x+w-6, cy, "--", CLR_GREEN, fs); cy+=lh+4;

   CreateSectionBar(objPrefix+"S_SIG_BG", x, cy-2, w);
   CreateLabel(objPrefix+"S_SIG", x+8, cy, "SEGNALI", CLR_DIM, fs-1, "Arial Bold");
   cy += lh+2;
   CreateRowLabel(objPrefix+"LBL_SBUY",  x+8,    cy, "BUY",  fs);
   CreateLabel(objPrefix+"DOT_BUY",      x+w-60, cy, "●",    CLR_RED, fs+1);
   CreateLabelRight(objPrefix+"VAL_SBUY",  x+w-6, cy, "NO",  CLR_RED, fs); cy+=lh;
   CreateRowLabel(objPrefix+"LBL_SSELL", x+8,    cy, "SELL", fs);
   CreateLabel(objPrefix+"DOT_SELL",     x+w-60, cy, "●",    CLR_RED, fs+1);
   CreateLabelRight(objPrefix+"VAL_SSELL", x+w-6, cy, "NO",  CLR_RED, fs); cy+=lh+4;

   CreateSectionBar(objPrefix+"S_TRD_BG", x, cy-2, w);
   CreateLabel(objPrefix+"S_TRD", x+8, cy, "TRADE", CLR_DIM, fs-1, "Arial Bold");
   cy += lh+2;
   CreateRowLabel(objPrefix+"LBL_POS",  x+8, cy, "Ordini",    fs); CreateLabelRight(objPrefix+"VAL_POS",  x+w-6, cy, "0",    CLR_TEXT,   fs); cy+=lh;
   CreateRowLabel(objPrefix+"LBL_LOTS", x+8, cy, "Lotto tot", fs); CreateLabelRight(objPrefix+"VAL_LOTS", x+w-6, cy, "0.00", CLR_TEXT,   fs); cy+=lh;
   CreateRowLabel(objPrefix+"LBL_BLOT", x+8, cy, "Lotto base",fs); CreateLabelRight(objPrefix+"VAL_BLOT", x+w-6, cy, "0.01", CLR_MUTED,  fs); cy+=lh;
   CreateRowLabel(objPrefix+"LBL_BE",   x+8, cy, "Breakeven", fs); CreateLabelRight(objPrefix+"VAL_BE",   x+w-6, cy, "--",   CLR_YELLOW, fs); cy+=lh;
   CreateRowLabel(objPrefix+"LBL_PROF", x+8, cy, "Profit",    fs); CreateLabelRight(objPrefix+"VAL_PROF", x+w-6, cy, "0.00", CLR_GREEN,  fs); cy+=lh+4;

   CreateSectionBar(objPrefix+"S_STAT_BG", x, cy-2, w);
   CreateLabel(objPrefix+"S_STAT", x+8, cy, "STATISTICHE OGGI", CLR_DIM, fs-1, "Arial Bold");
   cy += lh+2;
   CreateRowLabel(objPrefix+"LBL_DTRADES", x+8, cy, "Trade chiusi",   fs); CreateLabelRight(objPrefix+"VAL_DTRADES", x+w-6, cy, "0",     CLR_TEXT,  fs); cy+=lh;
   CreateRowLabel(objPrefix+"LBL_DWIN",    x+8, cy, "Profitto lordo", fs); CreateLabelRight(objPrefix+"VAL_DWIN",    x+w-6, cy, "+0.00", CLR_GREEN, fs); cy+=lh;
   CreateRowLabel(objPrefix+"LBL_DLOSS",   x+8, cy, "Perdita lorda",  fs); CreateLabelRight(objPrefix+"VAL_DLOSS",   x+w-6, cy, "0.00",  CLR_RED,   fs); cy+=lh+4;

   CreateSectionBar(objPrefix+"S_INF_BG", x, cy-2, w);
   CreateLabel(objPrefix+"S_INF", x+8, cy, "INFO", CLR_DIM, fs-1, "Arial Bold");
   cy += lh+2;
   CreateRowLabel(objPrefix+"LBL_DD",   x+8, cy, "DD oggi",    fs); CreateLabelRight(objPrefix+"VAL_DD",   x+w-6, cy, "0.00%",  CLR_GREEN, fs); cy+=lh;
   CreateRowLabel(objPrefix+"LBL_BSL",  x+8, cy, "Basket SL",  fs); CreateLabelRight(objPrefix+"VAL_BSL",  x+w-6, cy, "--",     CLR_MUTED, fs); cy+=lh;
   CreateRowLabel(objPrefix+"LBL_ATR",    x+8, cy, "ATR (pips)",  fs); CreateLabelRight(objPrefix+"VAL_ATR",    x+w-6, cy, "--",            CLR_GREEN, fs); cy+=lh;
   CreateRowLabel(objPrefix+"LBL_CB",     x+8, cy, "Cir.Breaker", fs); CreateLabelRight(objPrefix+"VAL_CB",     x+w-6, cy, "OFF",           CLR_MUTED, fs); cy+=lh;
   CreateRowLabel(objPrefix+"LBL_SRVTIME",x+8, cy, "Ora server",  fs); CreateLabelRight(objPrefix+"VAL_SRVTIME",x+w-6, cy, "--:--",         CLR_TEXT,  fs); cy+=lh;
   CreateRowLabel(objPrefix+"LBL_TIME",   x+8, cy, "Orario",      fs); CreateLabelRight(objPrefix+"VAL_TIME",   x+w-6, cy, GetTimeString(), CLR_TEXT,  fs); cy+=lh;
   CreateRowLabel(objPrefix+"LBL_STATUS", x+8, cy, "Stato",       fs); CreateLabelRight(objPrefix+"VAL_STATUS", x+w-6, cy, "ATTIVO",        CLR_GREEN, fs, "Arial Bold"); cy+=lh+8;

   CreateButton(objPrefix+"BTN_BUY",  x+8,       cy, (w/2)-12, 18, "● BUY  ON", CLR_GREEN_BG, CLR_GREEN_BD, CLR_GREEN, fs);
   CreateButton(objPrefix+"BTN_SELL", x+(w/2)+4, cy, (w/2)-12, 18, "● SELL ON", CLR_RED_BG,   CLR_RED_BD,   CLR_RED,   fs);

   ChartRedraw();
}

//+------------------------------------------------------------------+
//| BOARD UPDATE                                                     |
//+------------------------------------------------------------------+
void UpdateBoard()
{
   if(!_boardReady) return;

   // Ora server e stato orario: aggiornati SEMPRE, anche se gli
   // indicatori non sono ancora pronti (es. subito dopo l'avvio)
   bool inWin = (!InpTimeFilter || IsInTradeWindow());
   SetLabelText(objPrefix+"VAL_SRVTIME", TimeToString(TimeCurrent(), TIME_MINUTES));
   SetLabelColor(objPrefix+"VAL_SRVTIME", inWin ? CLR_GREEN : CLR_YELLOW);
   SetLabelText(objPrefix+"VAL_TIME", GetTimeString());
   SetLabelColor(objPrefix+"VAL_TIME", (!InpTimeFilter || (!timeBlocked && !closingMode)) ?
                                        CLR_GREEN : CLR_YELLOW);

   if(ArraySize(adxMain)<2 || ArraySize(stochMain)<2)
   {
      ChartRedraw();
      return;
   }

   double adx      = adxMain[1];
   double stoch    = stochMain[1];
   double price    = SymbolInfoDouble(_Symbol,SYMBOL_BID);
   bool   volOK    = CheckVolumeSpike();
   bool   obvUp    = (ArraySize(obvBuffer)>=3 && obvBuffer[1]>obvBuffer[2]);

   bool adxOK = (adx>=InpADX_Min && adx<=InpADX_Max);
   SetLabelText(objPrefix+"VAL_ADX",  DoubleToString(adx,1));
   SetLabelColor(objPrefix+"VAL_ADX", adxOK ? CLR_GREEN : CLR_RED);

   bool stochZone = (stoch<InpStoch_OS || stoch>InpStoch_OB);
   SetLabelText(objPrefix+"VAL_STOCH",  DoubleToString(stoch,1));
   SetLabelColor(objPrefix+"VAL_STOCH", stochZone ? CLR_GREEN : CLR_YELLOW);

   SetLabelText(objPrefix+"VAL_VOL",  volOK ? "OK" : "BASSO");
   SetLabelColor(objPrefix+"VAL_VOL", volOK ? CLR_GREEN : CLR_RED);

   SetLabelText(objPrefix+"VAL_OBV",  obvUp ? "RIALZO" : "RIBASSO");
   SetLabelColor(objPrefix+"VAL_OBV", obvUp ? CLR_GREEN : CLR_RED);

   bool aboveVWAP = (vwapValue>0 && price>vwapValue);
   SetLabelText(objPrefix+"VAL_VWAP",  vwapValue>0 ? DoubleToString(vwapValue,_Digits) : "--");
   SetLabelColor(objPrefix+"VAL_VWAP", aboveVWAP ? CLR_GREEN : CLR_RED);

   bool blocksOK = (!dailyBlocked && !timeBlocked && !circuitBlocked &&
                    !ddBlocked && !basketStopHit);
   bool canBuy, canSell;
   if(InpDisableAllFilters)
   {
      canBuy  = blocksOK && buyEnabled;
      canSell = blocksOK && sellEnabled;
   }
   else
   {
      bool gateOK = adxOK && volOK && blocksOK;
      canBuy  = gateOK && stoch<InpStoch_OS && buyEnabled;
      canSell = gateOK && stoch>InpStoch_OB && sellEnabled;
   }
   SetLabelColor(objPrefix+"DOT_BUY",  canBuy  ? CLR_GREEN : CLR_RED);
   SetLabelText(objPrefix+"VAL_SBUY",  canBuy  ? "PRONTO" : "NO");
   SetLabelColor(objPrefix+"VAL_SBUY", canBuy  ? CLR_GREEN : CLR_RED);
   SetLabelColor(objPrefix+"DOT_SELL", canSell ? CLR_GREEN : CLR_RED);
   SetLabelText(objPrefix+"VAL_SSELL",  canSell ? "PRONTO" : "NO");
   SetLabelColor(objPrefix+"VAL_SSELL",canSell ? CLR_GREEN : CLR_RED);

   bool posOpen = (basket.count > 0);

   SetLabelText(objPrefix+"VAL_POS", IntegerToString(posOpen ? basket.count : lastKnownPos));
   SetLabelColor(objPrefix+"VAL_POS", posOpen ? CLR_TEXT : CLR_MUTED);

   double dispLots = posOpen ? basket.lots : lastKnownLots;
   SetLabelText(objPrefix+"VAL_LOTS", DoubleToString(dispLots,2));
   SetLabelColor(objPrefix+"VAL_LOTS", posOpen ? CLR_TEXT : CLR_MUTED);
   SetLabelText(objPrefix+"VAL_BLOT", DoubleToString(CalcBaseLot(),2));
   SetLabelColor(objPrefix+"VAL_BLOT", InpDynamicLot ? CLR_GREEN : CLR_MUTED);

   double dispBE = posOpen ? basket.breakEven : lastKnownBE;
   SetLabelText(objPrefix+"VAL_BE", dispBE>0 ? DoubleToString(dispBE,_Digits) : "--");
   SetLabelColor(objPrefix+"VAL_BE", posOpen ? CLR_YELLOW : CLR_MUTED);

   double dispProfit = posOpen ? basket.profit : lastKnownProfit;
   SetLabelText(objPrefix+"VAL_PROF", (posOpen ? "" : "✓ ") + DoubleToString(dispProfit,2));
   SetLabelColor(objPrefix+"VAL_PROF", dispProfit>=0 ? CLR_GREEN : CLR_RED);

   SetLabelText(objPrefix+"VAL_DTRADES", IntegerToString(dayTrades));
   SetLabelColor(objPrefix+"VAL_DTRADES", dayTrades>0 ? CLR_TEXT : CLR_MUTED);

   SetLabelText(objPrefix+"VAL_DWIN",  "+" + DoubleToString(dayGrossProfit,2));
   SetLabelColor(objPrefix+"VAL_DWIN", dayGrossProfit>0 ? CLR_GREEN : CLR_MUTED);

   SetLabelText(objPrefix+"VAL_DLOSS", DoubleToString(dayGrossLoss,2));
   SetLabelColor(objPrefix+"VAL_DLOSS", dayGrossLoss<0 ? CLR_RED : CLR_MUTED);

   if(InpDailyLossLimit <= 0)
   {
      color ddCol = (dayMaxDrawdown < 1.0) ? CLR_GREEN :
                    (dayMaxDrawdown < 3.0) ? CLR_YELLOW : CLR_RED;
      SetLabelText(objPrefix+"VAL_DD",  DoubleToString(dayMaxDrawdown,2)+"%");
      SetLabelColor(objPrefix+"VAL_DD", ddCol);
   }
   else
   {
      color ddCol = (dayMaxDrawdown < InpDailyLossLimit*0.5) ? CLR_GREEN :
                    (dayMaxDrawdown < InpDailyLossLimit*0.8) ? CLR_YELLOW : CLR_RED;
      SetLabelText(objPrefix+"VAL_DD",  DoubleToString(dayMaxDrawdown,2)+"%");
      SetLabelColor(objPrefix+"VAL_DD", ddCol);
   }

   if(InpBasketStopLoss > 0 && basket.count > 0)
   {
      double bal  = AccountInfoDouble(ACCOUNT_BALANCE);
      double fPct = (bal > 0 && basket.profit < 0) ? (-basket.profit / bal * 100.0) : 0.0;
      color bsCol = (fPct < InpBasketStopLoss * 0.5) ? CLR_GREEN :
                    (fPct < InpBasketStopLoss * 0.8) ? CLR_YELLOW : CLR_RED;
      SetLabelText(objPrefix+"VAL_BSL",
                   DoubleToString(fPct,1)+"% / "+DoubleToString(InpBasketStopLoss,1)+"%");
      SetLabelColor(objPrefix+"VAL_BSL", bsCol);
   }
   else
      SetLabelText(objPrefix+"VAL_BSL", basketStopHit ? "STOP ATTIVO" : "--");

   double atrBuf[];
   ArraySetAsSeries(atrBuf, true);
   if(InpATR_Enabled && CopyBuffer(atrHandle, 0, 0, 3, atrBuf) >= 2)
   {
      double atrPips = atrBuf[1] / (_Point * 10);
      bool   atrHigh = (InpATR_MaxPips > 0 && atrPips > InpATR_MaxPips);
      SetLabelText(objPrefix+"VAL_ATR",  DoubleToString(atrPips,1) +
                   (InpATR_MaxPips>0 ? " / "+DoubleToString(InpATR_MaxPips,1) : ""));
      SetLabelColor(objPrefix+"VAL_ATR", atrHigh ? CLR_RED : CLR_GREEN);
   }
   else
   {
      SetLabelText(objPrefix+"VAL_ATR",  "OFF");
      SetLabelColor(objPrefix+"VAL_ATR", CLR_MUTED);
   }

   if(!InpCB_Enabled)
   {
      SetLabelText(objPrefix+"VAL_CB",  "OFF");
      SetLabelColor(objPrefix+"VAL_CB", CLR_MUTED);
   }
   else if(circuitBlocked)
   {
      int minsLeft = (int)((circuitBlockUntil - TimeCurrent()) / 60);
      SetLabelText(objPrefix+"VAL_CB",  "BLOCCO " + IntegerToString(minsLeft) + "m");
      SetLabelColor(objPrefix+"VAL_CB", CLR_RED);
   }
   else
   {
      SetLabelText(objPrefix+"VAL_CB",  IntegerToString(basket.count) + "/" +
                                        IntegerToString(InpCB_TriggerLevels));
      SetLabelColor(objPrefix+"VAL_CB", basket.count >= InpCB_TriggerLevels-1 ? CLR_YELLOW : CLR_GREEN);
   }

   string statusTxt = "ATTIVO";
   color  statusCol = CLR_GREEN;
   if(ddBlocked)                { statusTxt = "DD MAX";      statusCol = CLR_RED;    }
   else if(dailyBlocked)        { statusTxt = "MAX LOSS";    statusCol = CLR_RED;    }
   else if(basketStopHit)       { statusTxt = "BASKET STOP"; statusCol = CLR_RED;    }
   else if(circuitBlocked)      { statusTxt = "CIRCUIT BR";  statusCol = CLR_RED;    }
   else if(closingMode)         { statusTxt = "CLOSING";     statusCol = CLR_YELLOW; }
   else if(timeBlocked)         { statusTxt = "FUORI ORA";   statusCol = CLR_MUTED;  }
   else if(InpDisableAllFilters){ statusTxt = "FILTRI OFF";  statusCol = CLR_YELLOW; }
   SetLabelText(objPrefix+"VAL_STATUS",  statusTxt);
   SetLabelColor(objPrefix+"VAL_STATUS", statusCol);

   UpdateButtonStyle(objPrefix+"BTN_BUY",
      buyEnabled ? "● BUY  ON" : "● BUY  OFF",
      buyEnabled ? CLR_GREEN_BG : CLR_BG2,
      buyEnabled ? CLR_GREEN_BD : CLR_DIM,
      buyEnabled ? CLR_GREEN    : CLR_MUTED);
   UpdateButtonStyle(objPrefix+"BTN_SELL",
      sellEnabled ? "● SELL ON" : "● SELL OFF",
      sellEnabled ? CLR_RED_BG  : CLR_BG2,
      sellEnabled ? CLR_RED_BD  : CLR_DIM,
      sellEnabled ? CLR_RED     : CLR_MUTED);

   ChartRedraw();
}

//+------------------------------------------------------------------+
//| CHART EVENT                                                      |
//+------------------------------------------------------------------+
void OnChartEvent(const int id,const long &lparam,const double &dparam,const string &sparam)
{
   if(id==CHARTEVENT_OBJECT_CLICK)
   {
      if(sparam==objPrefix+"BTN_BUY")
      { buyEnabled=!buyEnabled;
        Print("PHANTOM: BUY ",buyEnabled?"ON":"OFF"); UpdateBoard(); }
      if(sparam==objPrefix+"BTN_SELL")
      { sellEnabled=!sellEnabled;
        Print("PHANTOM: SELL ",sellEnabled?"ON":"OFF"); UpdateBoard(); }
   }
}

//+------------------------------------------------------------------+
//| UI HELPERS                                                       |
//+------------------------------------------------------------------+
void CreateRect(string name,int x,int y,int w,int h,color bg,color border)
{
   if(ObjectFind(0,name)>=0) ObjectDelete(0,name);
   ObjectCreate(0,name,OBJ_RECTANGLE_LABEL,0,0,0);
   ObjectSetInteger(0,name,OBJPROP_XDISTANCE,   x);
   ObjectSetInteger(0,name,OBJPROP_YDISTANCE,   y);
   ObjectSetInteger(0,name,OBJPROP_XSIZE,       w);
   ObjectSetInteger(0,name,OBJPROP_YSIZE,       h);
   ObjectSetInteger(0,name,OBJPROP_BGCOLOR,     bg);
   ObjectSetInteger(0,name,OBJPROP_BORDER_COLOR,border);
   ObjectSetInteger(0,name,OBJPROP_BORDER_TYPE, BORDER_FLAT);
   ObjectSetInteger(0,name,OBJPROP_CORNER,      CORNER_LEFT_UPPER);
   ObjectSetInteger(0,name,OBJPROP_SELECTABLE,  false);
   ObjectSetInteger(0,name,OBJPROP_BACK,        false);
}

void CreateSectionBar(string name,int x,int y,int w)
{
   CreateRect(name, x, y, w, 14, CLR_SECTION_L, CLR_SECTION_L);
}

void CreateLabel(string name,int x,int y,string text,color col,int fs,string font="Arial")
{
   if(ObjectFind(0,name)>=0) ObjectDelete(0,name);
   ObjectCreate(0,name,OBJ_LABEL,0,0,0);
   ObjectSetInteger(0,name,OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0,name,OBJPROP_YDISTANCE, y);
   ObjectSetString(0, name,OBJPROP_TEXT,      text);
   ObjectSetInteger(0,name,OBJPROP_COLOR,     col);
   ObjectSetInteger(0,name,OBJPROP_FONTSIZE,  fs);
   ObjectSetString(0, name,OBJPROP_FONT,      font);
   ObjectSetInteger(0,name,OBJPROP_CORNER,    CORNER_LEFT_UPPER);
   ObjectSetInteger(0,name,OBJPROP_ANCHOR,    ANCHOR_LEFT_UPPER);
   ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,name,OBJPROP_BACK,      false);
}

void CreateLabelRight(string name,int x,int y,string text,color col,int fs,string font="Arial")
{
   if(ObjectFind(0,name)>=0) ObjectDelete(0,name);
   ObjectCreate(0,name,OBJ_LABEL,0,0,0);
   ObjectSetInteger(0,name,OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0,name,OBJPROP_YDISTANCE, y);
   ObjectSetString(0, name,OBJPROP_TEXT,      text);
   ObjectSetInteger(0,name,OBJPROP_COLOR,     col);
   ObjectSetInteger(0,name,OBJPROP_FONTSIZE,  fs);
   ObjectSetString(0, name,OBJPROP_FONT,      font);
   ObjectSetInteger(0,name,OBJPROP_CORNER,    CORNER_LEFT_UPPER);
   ObjectSetInteger(0,name,OBJPROP_ANCHOR,    ANCHOR_RIGHT_UPPER);
   ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,name,OBJPROP_BACK,      false);
}

void CreateRowLabel(string name,int x,int y,string text,int fs)
{
   CreateLabel(name, x, y, text, CLR_MUTED, fs);
}

void CreateButton(string name,int x,int y,int w,int h,
                  string text,color bg,color border,color tc,int fs)
{
   if(ObjectFind(0,name)>=0) ObjectDelete(0,name);
   ObjectCreate(0,name,OBJ_BUTTON,0,0,0);
   ObjectSetInteger(0,name,OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0,name,OBJPROP_YDISTANCE, y);
   ObjectSetInteger(0,name,OBJPROP_XSIZE,     w);
   ObjectSetInteger(0,name,OBJPROP_YSIZE,     h);
   ObjectSetString(0, name,OBJPROP_TEXT,      text);
   ObjectSetInteger(0,name,OBJPROP_BGCOLOR,   bg);
   ObjectSetInteger(0,name,OBJPROP_BORDER_COLOR, border);
   ObjectSetInteger(0,name,OBJPROP_COLOR,     tc);
   ObjectSetInteger(0,name,OBJPROP_FONTSIZE,  fs);
   ObjectSetInteger(0,name,OBJPROP_CORNER,    CORNER_LEFT_UPPER);
   ObjectSetInteger(0,name,OBJPROP_SELECTABLE,false);
   ObjectSetInteger(0,name,OBJPROP_BACK,      false);
}

void UpdateButtonStyle(string name,string text,color bg,color border,color tc)
{
   ObjectSetString(0, name,OBJPROP_TEXT,        text);
   ObjectSetInteger(0,name,OBJPROP_BGCOLOR,     bg);
   ObjectSetInteger(0,name,OBJPROP_BORDER_COLOR,border);
   ObjectSetInteger(0,name,OBJPROP_COLOR,       tc);
   ObjectSetInteger(0,name,OBJPROP_STATE,       false);
}

void SetLabelText(string name,string text)
{
   ObjectSetString(0,name,OBJPROP_TEXT,text);
}

void SetLabelColor(string name,color col)
{
   ObjectSetInteger(0,name,OBJPROP_COLOR,col);
}
//+------------------------------------------------------------------+

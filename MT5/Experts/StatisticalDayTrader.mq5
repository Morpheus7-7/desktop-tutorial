//+------------------------------------------------------------------+
//|                                        StatisticalDayTrader.mq5 |
//|  Expert Advisor multi-strategia per il day trading basato su     |
//|  strategie con evidenza statistica documentata:                  |
//|                                                                  |
//|  1) ORB  - Opening Range Breakout (breakout del range di         |
//|     apertura sessione, punta ai "trend day")                     |
//|  2) RSI2 - Mean Reversion di Larry Connors (RSI a 2 periodi      |
//|     con filtro di trend a 200 periodi)                           |
//|                                                                  |
//|  Risk management integrato:                                      |
//|   - Position sizing a rischio percentuale fisso                  |
//|   - Stop loss basati su ATR / range                              |
//|   - Limite di perdita giornaliero                                |
//|   - Numero massimo di trade al giorno                            |
//|   - Filtro spread e filtro orario di sessione                    |
//|   - Chiusura totale a fine giornata (nessuna posizione overnight)|
//+------------------------------------------------------------------+
#property copyright "Open source - uso a proprio rischio"
#property version   "1.00"

#include <Trade/Trade.mqh>

//--- Selettore di strategia
enum ENUM_STRATEGY_MODE
  {
   STRAT_ORB  = 0,   // Solo Opening Range Breakout
   STRAT_RSI2 = 1,   // Solo RSI(2) Mean Reversion
   STRAT_BOTH = 2    // Entrambe le strategie
  };

//=================== INPUT GENERALI ===================
input group "=== Generale ==="
input ENUM_STRATEGY_MODE InpStrategy        = STRAT_BOTH; // Strategia attiva
input long               InpMagicBase       = 260702;     // Magic number base
input double             InpRiskPercent     = 1.0;        // Rischio per trade (% del saldo)
input int                InpMaxSpreadPoints = 30;         // Spread massimo (points, 0=disattivo)
input int                InpMaxTradesPerDay = 4;          // Max trade al giorno (totale)
input double             InpDailyLossLimit  = 3.0;        // Stop perdita giornaliera (% saldo, 0=off)

input group "=== Orari (ora del server/broker) ==="
input int                InpSessionStartHour = 9;         // Inizio sessione - ora
input int                InpSessionStartMin  = 0;         // Inizio sessione - minuti
input int                InpEntryCutoffHour  = 17;        // Ultima ora utile per nuovi ingressi
input int                InpCloseAllHour     = 21;        // Chiusura forzata posizioni - ora
input int                InpCloseAllMin      = 30;        // Chiusura forzata posizioni - minuti

input group "=== Opening Range Breakout ==="
input int                InpORBRangeMinutes  = 30;        // Durata opening range (minuti)
input double             InpORBBufferATR     = 0.10;      // Buffer breakout (x ATR)
input double             InpORBRewardRisk    = 2.0;       // Rapporto rendimento/rischio target
input bool               InpORBBreakEven     = true;      // Sposta SL a breakeven dopo 1R
input double             InpORBMinRangeATR   = 0.30;      // Range minimo valido (x ATR)
input double             InpORBMaxRangeATR   = 3.00;      // Range massimo valido (x ATR)

input group "=== RSI(2) Mean Reversion (Connors) ==="
input int                InpRSIPeriod        = 2;         // Periodo RSI
input double             InpRSIBuyLevel      = 5.0;       // Livello ipervenduto (buy)
input double             InpRSISellLevel     = 95.0;      // Livello ipercomprato (sell)
input int                InpTrendMAPeriod    = 200;       // MA filtro di trend
input int                InpExitMAPeriod     = 5;         // MA di uscita
input double             InpRSISLAtrMult     = 2.0;       // Stop loss (x ATR)

input group "=== Volatilita' ==="
input int                InpATRPeriod        = 14;        // Periodo ATR

//=================== VARIABILI GLOBALI ===================
CTrade   g_trade;
int      g_hATR      = INVALID_HANDLE;
int      g_hRSI      = INVALID_HANDLE;
int      g_hMATrend  = INVALID_HANDLE;
int      g_hMAExit   = INVALID_HANDLE;

datetime g_lastBarTime   = 0;
datetime g_currentDay    = 0;
bool     g_orbLongDone   = false;   // breakout long gia' tentato oggi
bool     g_orbShortDone  = false;   // breakout short gia' tentato oggi
bool     g_dayHalted     = false;   // trading fermato per limite di perdita

const long MAGIC_ORB_OFFSET  = 0;
const long MAGIC_RSI2_OFFSET = 1;

//+------------------------------------------------------------------+
//| Inizializzazione                                                 |
//+------------------------------------------------------------------+
int OnInit()
  {
   g_hATR     = iATR(_Symbol, PERIOD_CURRENT, InpATRPeriod);
   g_hRSI     = iRSI(_Symbol, PERIOD_CURRENT, InpRSIPeriod, PRICE_CLOSE);
   g_hMATrend = iMA(_Symbol, PERIOD_CURRENT, InpTrendMAPeriod, 0, MODE_SMA, PRICE_CLOSE);
   g_hMAExit  = iMA(_Symbol, PERIOD_CURRENT, InpExitMAPeriod, 0, MODE_SMA, PRICE_CLOSE);

   if(g_hATR == INVALID_HANDLE || g_hRSI == INVALID_HANDLE ||
      g_hMATrend == INVALID_HANDLE || g_hMAExit == INVALID_HANDLE)
     {
      Print("Errore nella creazione degli indicatori");
      return(INIT_FAILED);
     }

   g_trade.SetDeviationInPoints(20);
   g_trade.SetTypeFillingBySymbol(_Symbol);

   if(InpRiskPercent <= 0.0 || InpRiskPercent > 5.0)
      Print("ATTENZIONE: rischio per trade fuori dal range prudente (0-5%)");

   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| Deinizializzazione                                               |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   if(g_hATR     != INVALID_HANDLE) IndicatorRelease(g_hATR);
   if(g_hRSI     != INVALID_HANDLE) IndicatorRelease(g_hRSI);
   if(g_hMATrend != INVALID_HANDLE) IndicatorRelease(g_hMATrend);
   if(g_hMAExit  != INVALID_HANDLE) IndicatorRelease(g_hMAExit);
  }

//+------------------------------------------------------------------+
//| Tick principale: logica eseguita a chiusura barra                |
//+------------------------------------------------------------------+
void OnTick()
  {
   datetime barTime = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(barTime == g_lastBarTime)
      return;                      // lavora solo a barra nuova
   g_lastBarTime = barTime;

   ResetDailyStateIfNewDay();

   //--- chiusura forzata di fine giornata: nessuna posizione overnight
   if(IsPastCloseAllTime())
     {
      CloseAllOurPositions("Chiusura di fine giornata");
      return;
     }

   //--- gestione uscite delle posizioni aperte (sempre attiva)
   ManageORBPositions();
   ManageRSI2Positions();

   //--- filtri di ingresso
   if(g_dayHalted)
      return;
   if(CheckDailyLossLimitHit())
     {
      g_dayHalted = true;
      CloseAllOurPositions("Limite di perdita giornaliero raggiunto");
      Print("Trading sospeso fino a domani: limite di perdita giornaliero raggiunto");
      return;
     }
   if(!IsWithinEntryWindow())
      return;
   if(!SpreadOK())
      return;
   if(CountTradesToday() >= InpMaxTradesPerDay)
      return;

   //--- segnali di ingresso
   if(InpStrategy == STRAT_ORB || InpStrategy == STRAT_BOTH)
      CheckORBEntry();
   if(InpStrategy == STRAT_RSI2 || InpStrategy == STRAT_BOTH)
      CheckRSI2Entry();
  }

//+------------------------------------------------------------------+
//| Reset dello stato giornaliero                                    |
//+------------------------------------------------------------------+
void ResetDailyStateIfNewDay()
  {
   datetime today = DayStart(TimeCurrent());
   if(today != g_currentDay)
     {
      g_currentDay   = today;
      g_orbLongDone  = false;
      g_orbShortDone = false;
      g_dayHalted    = false;
     }
  }

//+------------------------------------------------------------------+
//| Inizio giornata (00:00 ora server)                               |
//+------------------------------------------------------------------+
datetime DayStart(datetime t)
  {
   MqlDateTime dt;
   TimeToStruct(t, dt);
   dt.hour = 0; dt.min = 0; dt.sec = 0;
   return StructToTime(dt);
  }

//+------------------------------------------------------------------+
//| Orario di inizio sessione di oggi                                |
//+------------------------------------------------------------------+
datetime SessionStartToday()
  {
   return DayStart(TimeCurrent()) + InpSessionStartHour*3600 + InpSessionStartMin*60;
  }

//+------------------------------------------------------------------+
//| Finestra utile per nuovi ingressi                                |
//+------------------------------------------------------------------+
bool IsWithinEntryWindow()
  {
   datetime now    = TimeCurrent();
   datetime start  = SessionStartToday();
   datetime cutoff = DayStart(now) + InpEntryCutoffHour*3600;
   return (now >= start && now < cutoff);
  }

//+------------------------------------------------------------------+
//| Siamo oltre l'orario di chiusura forzata?                        |
//+------------------------------------------------------------------+
bool IsPastCloseAllTime()
  {
   datetime closeAt = DayStart(TimeCurrent()) + InpCloseAllHour*3600 + InpCloseAllMin*60;
   return (TimeCurrent() >= closeAt);
  }

//+------------------------------------------------------------------+
//| Filtro spread                                                    |
//+------------------------------------------------------------------+
bool SpreadOK()
  {
   if(InpMaxSpreadPoints <= 0)
      return true;
   long spread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   return (spread <= InpMaxSpreadPoints);
  }

//+------------------------------------------------------------------+
//| Valore ATR della barra chiusa piu' recente                       |
//+------------------------------------------------------------------+
double GetATR()
  {
   double buf[1];
   if(CopyBuffer(g_hATR, 0, 1, 1, buf) != 1)
      return 0.0;
   return buf[0];
  }

//+------------------------------------------------------------------+
//| Valore indicatore su barra chiusa (shift 1)                      |
//+------------------------------------------------------------------+
double GetIndicator(int handle, int shift = 1)
  {
   double buf[1];
   if(CopyBuffer(handle, 0, shift, 1, buf) != 1)
      return EMPTY_VALUE;
   return buf[0];
  }

//+------------------------------------------------------------------+
//| Calcolo lotti a rischio percentuale fisso                        |
//+------------------------------------------------------------------+
double CalcLots(double slDistance)
  {
   if(slDistance <= 0.0)
      return 0.0;

   double balance   = AccountInfoDouble(ACCOUNT_BALANCE);
   double riskMoney = balance * InpRiskPercent / 100.0;

   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickValue <= 0.0 || tickSize <= 0.0)
      return 0.0;

   double lossPerLot = slDistance / tickSize * tickValue;
   if(lossPerLot <= 0.0)
      return 0.0;

   double lots = riskMoney / lossPerLot;

   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(lotStep > 0.0)
      lots = MathFloor(lots / lotStep) * lotStep;
   lots = MathMax(minLot, MathMin(maxLot, lots));

   // se anche il lotto minimo supera il rischio consentito, non entrare
   if(minLot * lossPerLot > riskMoney * 1.5)
      return 0.0;

   return lots;
  }

//+------------------------------------------------------------------+
//| Conta i trade aperti oggi (deals IN con i nostri magic)          |
//+------------------------------------------------------------------+
int CountTradesToday()
  {
   int count = 0;
   if(!HistorySelect(g_currentDay, TimeCurrent()))
      return 0;
   int total = HistoryDealsTotal();
   for(int i = 0; i < total; i++)
     {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0) continue;
      long magic = HistoryDealGetInteger(ticket, DEAL_MAGIC);
      if(!IsOurMagic(magic)) continue;
      if(HistoryDealGetString(ticket, DEAL_SYMBOL) != _Symbol) continue;
      if((ENUM_DEAL_ENTRY)HistoryDealGetInteger(ticket, DEAL_ENTRY) == DEAL_ENTRY_IN)
         count++;
     }
   // includi anche le posizioni ancora aperte gia' contate come deal IN?
   // I deal IN delle posizioni aperte sono gia' in history: nessun doppio conteggio.
   return count;
  }

//+------------------------------------------------------------------+
//| Perdita realizzata oggi >= limite giornaliero?                   |
//+------------------------------------------------------------------+
bool CheckDailyLossLimitHit()
  {
   if(InpDailyLossLimit <= 0.0)
      return false;
   if(!HistorySelect(g_currentDay, TimeCurrent()))
      return false;

   double pnl = 0.0;
   int total = HistoryDealsTotal();
   for(int i = 0; i < total; i++)
     {
      ulong ticket = HistoryDealGetTicket(i);
      if(ticket == 0) continue;
      if(!IsOurMagic(HistoryDealGetInteger(ticket, DEAL_MAGIC))) continue;
      if(HistoryDealGetString(ticket, DEAL_SYMBOL) != _Symbol) continue;
      pnl += HistoryDealGetDouble(ticket, DEAL_PROFIT)
           + HistoryDealGetDouble(ticket, DEAL_COMMISSION)
           + HistoryDealGetDouble(ticket, DEAL_SWAP);
     }

   double limit = AccountInfoDouble(ACCOUNT_BALANCE) * InpDailyLossLimit / 100.0;
   return (pnl <= -limit);
  }

//+------------------------------------------------------------------+
//| Il magic appartiene a questo EA?                                 |
//+------------------------------------------------------------------+
bool IsOurMagic(long magic)
  {
   return (magic == InpMagicBase + MAGIC_ORB_OFFSET ||
           magic == InpMagicBase + MAGIC_RSI2_OFFSET);
  }

//+------------------------------------------------------------------+
//| C'e' una posizione aperta con questo magic?                      |
//+------------------------------------------------------------------+
bool HasPosition(long magic)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(PositionGetSymbol(i) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) == magic)
         return true;
     }
   return false;
  }

//+------------------------------------------------------------------+
//| Chiudi tutte le posizioni di questo EA                           |
//+------------------------------------------------------------------+
void CloseAllOurPositions(string reason)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(PositionGetSymbol(i) != _Symbol) continue;
      long magic = PositionGetInteger(POSITION_MAGIC);
      if(!IsOurMagic(magic)) continue;
      ulong ticket = PositionGetInteger(POSITION_TICKET);
      if(g_trade.PositionClose(ticket))
         PrintFormat("Posizione #%I64u chiusa: %s", ticket, reason);
     }
  }

//==================================================================
//  STRATEGIA 1: OPENING RANGE BREAKOUT
//==================================================================

//+------------------------------------------------------------------+
//| Calcola high/low dell'opening range di oggi                      |
//| Ritorna false se il range non e' ancora completo o non valido    |
//+------------------------------------------------------------------+
bool GetOpeningRange(double &rangeHigh, double &rangeLow)
  {
   datetime rangeStart = SessionStartToday();
   datetime rangeEnd   = rangeStart + InpORBRangeMinutes * 60;

   if(TimeCurrent() < rangeEnd)
      return false;               // range non ancora formato

   MqlRates rates[];
   int copied = CopyRates(_Symbol, PERIOD_CURRENT, rangeStart, rangeEnd - 1, rates);
   if(copied <= 0)
      return false;

   rangeHigh = rates[0].high;
   rangeLow  = rates[0].low;
   for(int i = 1; i < copied; i++)
     {
      if(rates[i].high > rangeHigh) rangeHigh = rates[i].high;
      if(rates[i].low  < rangeLow)  rangeLow  = rates[i].low;
     }
   return (rangeHigh > rangeLow);
  }

//+------------------------------------------------------------------+
//| Ingresso Opening Range Breakout                                  |
//+------------------------------------------------------------------+
void CheckORBEntry()
  {
   long magic = InpMagicBase + MAGIC_ORB_OFFSET;
   if(HasPosition(magic))
      return;
   if(g_orbLongDone && g_orbShortDone)
      return;

   double rangeHigh, rangeLow;
   if(!GetOpeningRange(rangeHigh, rangeLow))
      return;

   double atr = GetATR();
   if(atr <= 0.0)
      return;

   //--- filtro qualita' del range: scarta giornate anomale
   double range = rangeHigh - rangeLow;
   if(range < InpORBMinRangeATR * atr || range > InpORBMaxRangeATR * atr)
      return;

   double buffer    = InpORBBufferATR * atr;
   double lastClose = iClose(_Symbol, PERIOD_CURRENT, 1);
   double point     = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   int    digits    = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);

   g_trade.SetExpertMagicNumber(magic);

   //--- breakout rialzista: chiusura sopra il range + buffer
   if(!g_orbLongDone && lastClose > rangeHigh + buffer)
     {
      double entry = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl    = NormalizeDouble(rangeLow, digits);
      double slDist = entry - sl;
      if(slDist > point)
        {
         double tp   = NormalizeDouble(entry + InpORBRewardRisk * slDist, digits);
         double lots = CalcLots(slDist);
         if(lots > 0.0 && g_trade.Buy(lots, _Symbol, 0.0, sl, tp, "ORB long"))
            g_orbLongDone = true;
        }
     }
   //--- breakout ribassista: chiusura sotto il range - buffer
   else if(!g_orbShortDone && lastClose < rangeLow - buffer)
     {
      double entry = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double sl    = NormalizeDouble(rangeHigh, digits);
      double slDist = sl - entry;
      if(slDist > point)
        {
         double tp   = NormalizeDouble(entry - InpORBRewardRisk * slDist, digits);
         double lots = CalcLots(slDist);
         if(lots > 0.0 && g_trade.Sell(lots, _Symbol, 0.0, sl, tp, "ORB short"))
            g_orbShortDone = true;
        }
     }
  }

//+------------------------------------------------------------------+
//| Gestione posizioni ORB: breakeven dopo 1R                        |
//+------------------------------------------------------------------+
void ManageORBPositions()
  {
   if(!InpORBBreakEven)
      return;

   long magic = InpMagicBase + MAGIC_ORB_OFFSET;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(PositionGetSymbol(i) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != magic) continue;

      ulong  ticket = PositionGetInteger(POSITION_TICKET);
      double open   = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl     = PositionGetDouble(POSITION_SL);
      double tp     = PositionGetDouble(POSITION_TP);
      long   type   = PositionGetInteger(POSITION_TYPE);
      int    digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
      double point  = SymbolInfoDouble(_Symbol, SYMBOL_POINT);

      if(type == POSITION_TYPE_BUY)
        {
         double risk = open - sl;
         double bid  = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         if(risk > 0.0 && sl < open && bid >= open + risk)
            g_trade.PositionModify(ticket, NormalizeDouble(open + point, digits), tp);
        }
      else if(type == POSITION_TYPE_SELL)
        {
         double risk = sl - open;
         double ask  = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         if(risk > 0.0 && sl > open && ask <= open - risk)
            g_trade.PositionModify(ticket, NormalizeDouble(open - point, digits), tp);
        }
     }
  }

//==================================================================
//  STRATEGIA 2: RSI(2) MEAN REVERSION (Larry Connors)
//==================================================================

//+------------------------------------------------------------------+
//| Ingresso RSI(2) mean reversion con filtro di trend               |
//+------------------------------------------------------------------+
void CheckRSI2Entry()
  {
   long magic = InpMagicBase + MAGIC_RSI2_OFFSET;
   if(HasPosition(magic))
      return;

   double rsi     = GetIndicator(g_hRSI);
   double maTrend = GetIndicator(g_hMATrend);
   if(rsi == EMPTY_VALUE || maTrend == EMPTY_VALUE)
      return;

   double atr = GetATR();
   if(atr <= 0.0)
      return;

   double lastClose = iClose(_Symbol, PERIOD_CURRENT, 1);
   int    digits    = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double slDist    = InpRSISLAtrMult * atr;

   g_trade.SetExpertMagicNumber(magic);

   //--- long: ipervenduto in un uptrend (prezzo sopra MA200)
   if(rsi < InpRSIBuyLevel && lastClose > maTrend)
     {
      double entry = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double sl    = NormalizeDouble(entry - slDist, digits);
      double lots  = CalcLots(slDist);
      if(lots > 0.0)
         g_trade.Buy(lots, _Symbol, 0.0, sl, 0.0, "RSI2 long");
     }
   //--- short: ipercomprato in un downtrend (prezzo sotto MA200)
   else if(rsi > InpRSISellLevel && lastClose < maTrend)
     {
      double entry = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double sl    = NormalizeDouble(entry + slDist, digits);
      double lots  = CalcLots(slDist);
      if(lots > 0.0)
         g_trade.Sell(lots, _Symbol, 0.0, sl, 0.0, "RSI2 short");
     }
  }

//+------------------------------------------------------------------+
//| Uscita RSI(2): chiusura oltre la MA veloce o rottura del trend   |
//+------------------------------------------------------------------+
void ManageRSI2Positions()
  {
   long magic = InpMagicBase + MAGIC_RSI2_OFFSET;

   double maExit  = GetIndicator(g_hMAExit);
   double maTrend = GetIndicator(g_hMATrend);
   if(maExit == EMPTY_VALUE || maTrend == EMPTY_VALUE)
      return;

   double lastClose = iClose(_Symbol, PERIOD_CURRENT, 1);

   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(PositionGetSymbol(i) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != magic) continue;

      ulong ticket = PositionGetInteger(POSITION_TICKET);
      long  type   = PositionGetInteger(POSITION_TYPE);

      bool exitLong  = (type == POSITION_TYPE_BUY)  &&
                       (lastClose > maExit || lastClose < maTrend);
      bool exitShort = (type == POSITION_TYPE_SELL) &&
                       (lastClose < maExit || lastClose > maTrend);

      if(exitLong || exitShort)
         g_trade.PositionClose(ticket);
     }
  }
//+------------------------------------------------------------------+

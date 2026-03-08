//+------------------------------------------------------------------+
//|                                              GoldScalper_Pro.mq5 |
//|                        Advanced Gold Trading System for MT5       |
//|                    Multi-TF | Smart MM | Full Trade Management    |
//+------------------------------------------------------------------+
#property copyright "GoldScalper Pro"
#property link      ""
#property version   "3.00"
#property strict

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\OrderInfo.mqh>
#include <Indicators\Trend.mqh>

//+------------------------------------------------------------------+
//| INPUT PARAMETERS                                                  |
//+------------------------------------------------------------------+

// --- General Settings ---
input group "=== GENERAL SETTINGS ==="
input string   EA_Name           = "GoldScalper Pro";
input int      MagicNumber       = 202400;
input string   TradeComment      = "GSP_v3";
input bool     EnableLongTrades  = true;
input bool     EnableShortTrades = true;

// --- Risk Management ---
input group "=== RISK MANAGEMENT ==="
input double   RiskPercent       = 1.0;    // Risk % per trade
input double   MaxLotSize        = 5.0;    // Max lot size
input double   MinLotSize        = 0.01;   // Min lot size
input int      MaxOpenTrades     = 3;      // Max concurrent trades
input double   MaxDailyLossPerc  = 5.0;    // Max daily loss % before stop trading
input double   MaxDrawdownPerc   = 15.0;   // Max drawdown % (equity-based)

// --- ATR-Based Stop Loss / Take Profit ---
input group "=== STOP LOSS & TAKE PROFIT (ATR-based) ==="
input int      ATR_Period        = 14;
input double   ATR_SL_Multiplier = 1.5;   // SL = ATR * multiplier
input double   ATR_TP1_Multi     = 1.5;   // TP1 = ATR * multiplier
input double   ATR_TP2_Multi     = 3.0;   // TP2 = ATR * multiplier
input double   ATR_TP3_Multi     = 5.0;   // TP3 = ATR * multiplier
input double   TP1_ClosePercent  = 30.0;  // % of position to close at TP1
input double   TP2_ClosePercent  = 40.0;  // % of position to close at TP2
// Remaining 30% rides to TP3 with trailing stop

// --- Trailing Stop ---
input group "=== TRAILING STOP ==="
input bool     EnableTrailing    = true;
input double   TrailATR_Multi    = 1.2;   // Trail distance = ATR * multiplier
input double   TrailStep_Points  = 10;    // Min move before updating trail
input bool     EnableBreakEven   = true;
input double   BreakEven_ATR     = 0.8;   // Move SL to BE when price moves ATR * this

// --- Trend Filter (Higher Timeframe) ---
input group "=== TREND FILTER (H4) ==="
input ENUM_TIMEFRAMES  TrendTF   = PERIOD_H4;
input int      EMA_Fast_TF       = 21;
input int      EMA_Slow_TF       = 89;
input int      EMA_200_TF        = 200;   // Only trade in direction of EMA200

// --- Entry Indicators (Entry Timeframe) ---
input group "=== ENTRY INDICATORS ==="
input ENUM_TIMEFRAMES  EntryTF   = PERIOD_H1;
input int      EMA_Fast_Entry    = 8;
input int      EMA_Slow_Entry    = 21;
input int      RSI_Period        = 14;
input double   RSI_OB            = 70.0;  // Overbought
input double   RSI_OS            = 30.0;  // Oversold
input int      MACD_Fast         = 12;
input int      MACD_Slow         = 26;
input int      MACD_Signal       = 9;
input int      BB_Period         = 20;
input double   BB_Deviation      = 2.0;
input bool     UseVolumeFilter   = true;  // Volume spike confirmation

// --- Session Filter ---
input group "=== SESSION FILTER ==="
input bool     UseSessions       = true;
input int      LondonOpen_H      = 8;     // London open hour (server time)
input int      LondonClose_H     = 16;
input int      NYOpen_H          = 13;    // NY open hour (server time)
input int      NYClose_H         = 21;
input bool     TradeAsianSession = false;

// --- Spread & Slippage ---
input group "=== EXECUTION ==="
input int      MaxSpread_Points  = 30;    // Max allowed spread in points
input int      MaxSlippage       = 10;
input bool     UseStopOrders     = false; // Use stop orders instead of market

// --- News Filter (Time-based) ---
input group "=== NEWS FILTER ==="
input bool     UseNewsFilter     = true;
input int      MinsBefore_News   = 30;    // Minutes to avoid before news
input int      MinsAfter_News    = 30;    // Minutes to avoid after news
// High-impact news times (server time HH:MM) - adjust to your broker
input string   NewsTime1         = "14:30"; // US sessions
input string   NewsTime2         = "15:30";
input string   NewsTime3         = "08:30";
input string   NewsTime4         = "10:00";
input string   NewsTime5         = "13:30";

//+------------------------------------------------------------------+
//| GLOBAL VARIABLES                                                  |
//+------------------------------------------------------------------+
CTrade         trade;
CPositionInfo  posInfo;
COrderInfo     orderInfo;

// Indicator handles - Trend TF
int h_ema_fast_tf, h_ema_slow_tf, h_ema200_tf, h_atr_tf;

// Indicator handles - Entry TF
int h_ema_fast_entry, h_ema_slow_entry;
int h_rsi, h_macd, h_bb, h_atr_entry;
int h_volume;

// State tracking
double   StartingEquity;
double   DayStartEquity;
datetime LastDayChecked;
bool     TradingAllowed = true;
int      TP1_Ticket[100], TP2_Ticket[100], TP3_Ticket[100]; // Partial close tracking
bool     TP1_Hit[100], TP2_Hit[100];
ulong    OpenTickets[100];
int      OpenCount = 0;

// Price data buffers
double ema_fast_tf[], ema_slow_tf[], ema200_tf[], atr_tf[];
double ema_fast_en[], ema_slow_en[];
double rsi[], macd_main[], macd_signal[], macd_hist[];
double bb_upper[], bb_middle[], bb_lower[];
double atr_entry[], volume_buf[];

//+------------------------------------------------------------------+
//| Expert initialization                                             |
//+------------------------------------------------------------------+
int OnInit()
{
   // Configure trade object
   trade.SetExpertMagicNumber(MagicNumber);
   trade.SetDeviationInPoints(MaxSlippage);
   trade.SetTypeFilling(ORDER_FILLING_IOC);
   trade.LogLevel(LOG_LEVEL_ERRORS);

   // Store starting equity
   StartingEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   DayStartEquity = StartingEquity;
   LastDayChecked = TimeCurrent();

   // --- Create indicator handles ---
   // Trend TF indicators
   h_ema_fast_tf  = iMA(_Symbol, TrendTF, EMA_Fast_TF, 0, MODE_EMA, PRICE_CLOSE);
   h_ema_slow_tf  = iMA(_Symbol, TrendTF, EMA_Slow_TF, 0, MODE_EMA, PRICE_CLOSE);
   h_ema200_tf    = iMA(_Symbol, TrendTF, EMA_200_TF,  0, MODE_EMA, PRICE_CLOSE);
   h_atr_tf       = iATR(_Symbol, TrendTF, ATR_Period);

   // Entry TF indicators
   h_ema_fast_entry = iMA(_Symbol, EntryTF, EMA_Fast_Entry, 0, MODE_EMA, PRICE_CLOSE);
   h_ema_slow_entry = iMA(_Symbol, EntryTF, EMA_Slow_Entry, 0, MODE_EMA, PRICE_CLOSE);
   h_rsi            = iRSI(_Symbol, EntryTF, RSI_Period, PRICE_CLOSE);
   h_macd           = iMACD(_Symbol, EntryTF, MACD_Fast, MACD_Slow, MACD_Signal, PRICE_CLOSE);
   h_bb             = iBands(_Symbol, EntryTF, BB_Period, 0, BB_Deviation, PRICE_CLOSE);
   h_atr_entry      = iATR(_Symbol, EntryTF, ATR_Period);
   h_volume         = iVolumes(_Symbol, EntryTF, VOLUME_TICK);

   // Validate handles
   if(h_ema_fast_tf == INVALID_HANDLE || h_ema_slow_tf == INVALID_HANDLE ||
      h_ema200_tf   == INVALID_HANDLE || h_atr_tf      == INVALID_HANDLE ||
      h_ema_fast_entry == INVALID_HANDLE || h_ema_slow_entry == INVALID_HANDLE ||
      h_rsi == INVALID_HANDLE || h_macd == INVALID_HANDLE ||
      h_bb  == INVALID_HANDLE || h_atr_entry == INVALID_HANDLE)
   {
      Print("ERROR: Failed to create indicator handles!");
      return INIT_FAILED;
   }

   ArraySetAsSeries(ema_fast_tf,  true);
   ArraySetAsSeries(ema_slow_tf,  true);
   ArraySetAsSeries(ema200_tf,    true);
   ArraySetAsSeries(atr_tf,       true);
   ArraySetAsSeries(ema_fast_en,  true);
   ArraySetAsSeries(ema_slow_en,  true);
   ArraySetAsSeries(rsi,          true);
   ArraySetAsSeries(macd_main,    true);
   ArraySetAsSeries(macd_signal,  true);
   ArraySetAsSeries(macd_hist,    true);
   ArraySetAsSeries(bb_upper,     true);
   ArraySetAsSeries(bb_middle,    true);
   ArraySetAsSeries(bb_lower,     true);
   ArraySetAsSeries(atr_entry,    true);
   ArraySetAsSeries(volume_buf,   true);

   Print(EA_Name, " initialized successfully on ", _Symbol);
   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization                                           |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   IndicatorRelease(h_ema_fast_tf);
   IndicatorRelease(h_ema_slow_tf);
   IndicatorRelease(h_ema200_tf);
   IndicatorRelease(h_atr_tf);
   IndicatorRelease(h_ema_fast_entry);
   IndicatorRelease(h_ema_slow_entry);
   IndicatorRelease(h_rsi);
   IndicatorRelease(h_macd);
   IndicatorRelease(h_bb);
   IndicatorRelease(h_atr_entry);
   IndicatorRelease(h_volume);
}

//+------------------------------------------------------------------+
//| Main tick function                                                |
//+------------------------------------------------------------------+
void OnTick()
{
   // Reset daily equity tracking
   CheckDailyReset();

   // Check global risk limits
   if(!CheckRiskLimits()) return;

   // Update all indicator buffers
   if(!RefreshIndicators()) return;

   // Manage existing open trades
   ManageOpenTrades();

   // Check if we can open new trades
   if(!CanOpenNewTrade()) return;

   // Check session filter
   if(UseSessions && !IsValidSession()) return;

   // Check news filter
   if(UseNewsFilter && IsNewsTime()) return;

   // Check spread
   if(!IsSpreadOK()) return;

   // Analyze market and signal
   int signal = GetTradeSignal();

   // Execute trade if signal
   if(signal == 1 && EnableLongTrades)
      OpenTrade(ORDER_TYPE_BUY);
   else if(signal == -1 && EnableShortTrades)
      OpenTrade(ORDER_TYPE_SELL);
}

//+------------------------------------------------------------------+
//| Refresh all indicator data                                        |
//+------------------------------------------------------------------+
bool RefreshIndicators()
{
   if(CopyBuffer(h_ema_fast_tf,  0, 0, 3, ema_fast_tf)  < 3) return false;
   if(CopyBuffer(h_ema_slow_tf,  0, 0, 3, ema_slow_tf)  < 3) return false;
   if(CopyBuffer(h_ema200_tf,    0, 0, 3, ema200_tf)    < 3) return false;
   if(CopyBuffer(h_atr_tf,       0, 0, 3, atr_tf)       < 3) return false;
   if(CopyBuffer(h_ema_fast_entry, 0, 0, 3, ema_fast_en) < 3) return false;
   if(CopyBuffer(h_ema_slow_entry, 0, 0, 3, ema_slow_en) < 3) return false;
   if(CopyBuffer(h_rsi,          0, 0, 3, rsi)          < 3) return false;
   if(CopyBuffer(h_macd,         0, 0, 3, macd_main)    < 3) return false;
   if(CopyBuffer(h_macd,         1, 0, 3, macd_signal)  < 3) return false;
   if(CopyBuffer(h_macd,         2, 0, 3, macd_hist)    < 3) return false;
   if(CopyBuffer(h_bb,           0, 0, 3, bb_upper)     < 3) return false;
   if(CopyBuffer(h_bb,           1, 0, 3, bb_middle)    < 3) return false;
   if(CopyBuffer(h_bb,           2, 0, 3, bb_lower)     < 3) return false;
   if(CopyBuffer(h_atr_entry,    0, 0, 3, atr_entry)    < 3) return false;
   if(UseVolumeFilter)
   {
      if(CopyBuffer(h_volume, 0, 0, 3, volume_buf) < 3) return false;
   }
   return true;
}

//+------------------------------------------------------------------+
//| Core signal generation                                            |
//+------------------------------------------------------------------+
int GetTradeSignal()
{
   // ---- TREND FILTER (H4) ----
   bool trendBull = (ema_fast_tf[1] > ema_slow_tf[1]) &&
                    (ema_slow_tf[1] > ema200_tf[1]);   // Strong uptrend
   bool trendBear = (ema_fast_tf[1] < ema_slow_tf[1]) &&
                    (ema_slow_tf[1] < ema200_tf[1]);   // Strong downtrend

   // Moderate trend (EMA cross only)
   bool modBull = (ema_fast_tf[1] > ema_slow_tf[1]);
   bool modBear = (ema_fast_tf[1] < ema_slow_tf[1]);

   // Price must be above/below EMA200 for directional bias
   double closeH4[];
   ArraySetAsSeries(closeH4, true);
   if(CopyClose(_Symbol, TrendTF, 0, 2, closeH4) < 2) return 0;
   bool aboveEMA200 = (closeH4[1] > ema200_tf[1]);
   bool belowEMA200 = (closeH4[1] < ema200_tf[1]);

   // ---- ENTRY SIGNALS (H1) ----
   double closeH1[];
   ArraySetAsSeries(closeH1, true);
   if(CopyClose(_Symbol, EntryTF, 0, 3, closeH1) < 3) return 0;

   // EMA crossover on entry TF
   bool ema_cross_up   = (ema_fast_en[2] < ema_slow_en[2]) && (ema_fast_en[1] > ema_slow_en[1]);
   bool ema_cross_down = (ema_fast_en[2] > ema_slow_en[2]) && (ema_fast_en[1] < ema_slow_en[1]);

   // RSI conditions
   bool rsi_bull = (rsi[1] > 40.0 && rsi[1] < RSI_OB);   // Not overbought, trending up
   bool rsi_bear = (rsi[1] < 60.0 && rsi[1] > RSI_OS);   // Not oversold, trending down
   bool rsi_ob   = (rsi[1] >= RSI_OB);
   bool rsi_os   = (rsi[1] <= RSI_OS);

   // MACD crossover
   bool macd_cross_up   = (macd_hist[2] < 0 && macd_hist[1] > 0);
   bool macd_cross_down = (macd_hist[2] > 0 && macd_hist[1] < 0);
   bool macd_bull       = (macd_main[1] > macd_signal[1] && macd_hist[1] > 0);
   bool macd_bear       = (macd_main[1] < macd_signal[1] && macd_hist[1] < 0);

   // Bollinger Bands
   double priceNow = closeH1[1];
   bool price_near_lower = (priceNow <= bb_lower[1] * 1.001);   // Near/below lower band
   bool price_near_upper = (priceNow >= bb_upper[1] * 0.999);   // Near/above upper band
   bool price_mid_bull   = (priceNow > bb_middle[1]);
   bool price_mid_bear   = (priceNow < bb_middle[1]);

   // Volume filter
   bool volume_spike = true;
   if(UseVolumeFilter && volume_buf[1] > 0 && volume_buf[2] > 0)
      volume_spike = (volume_buf[1] > volume_buf[2] * 1.2); // 20% above previous bar

   // ---- BUY SIGNAL ----
   // Strategy 1: Trend continuation (strong trend + EMA cross + MACD)
   bool buy_s1 = (trendBull || (modBull && aboveEMA200)) &&
                 ema_cross_up && macd_bull && rsi_bull && price_mid_bull;

   // Strategy 2: Reversal from oversold (pullback entry)
   bool buy_s2 = (modBull || aboveEMA200) && price_near_lower &&
                 rsi_os && macd_cross_up && volume_spike;

   // Strategy 3: Momentum breakout
   bool buy_s3 = trendBull && macd_cross_up && (rsi[1] > 50 && rsi[1] < RSI_OB) &&
                 ema_cross_up && volume_spike;

   // ---- SELL SIGNAL ----
   // Strategy 1: Trend continuation
   bool sell_s1 = (trendBear || (modBear && belowEMA200)) &&
                  ema_cross_down && macd_bear && rsi_bear && price_mid_bear;

   // Strategy 2: Reversal from overbought
   bool sell_s2 = (modBear || belowEMA200) && price_near_upper &&
                  rsi_ob && macd_cross_down && volume_spike;

   // Strategy 3: Momentum breakdown
   bool sell_s3 = trendBear && macd_cross_down && (rsi[1] < 50 && rsi[1] > RSI_OS) &&
                  ema_cross_down && volume_spike;

   // Avoid trading if H4 trend is not clear (range market)
   bool clearTrend = trendBull || trendBear || aboveEMA200 || belowEMA200;
   if(!clearTrend) return 0;

   // --- Final signal ---
   if(buy_s1 || buy_s2 || buy_s3)   return 1;
   if(sell_s1 || sell_s2 || sell_s3) return -1;

   return 0;
}

//+------------------------------------------------------------------+
//| Open a new trade with SL/TP                                       |
//+------------------------------------------------------------------+
void OpenTrade(ENUM_ORDER_TYPE orderType)
{
   double atr    = atr_entry[1];
   double spread = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double point  = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   int    digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);

   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);

   double slDist  = atr * ATR_SL_Multiplier;
   double tp1Dist = atr * ATR_TP1_Multi;
   double tp2Dist = atr * ATR_TP2_Multi;
   double tp3Dist = atr * ATR_TP3_Multi;

   double entryPrice, sl, tp1, tp2, tp3;

   if(orderType == ORDER_TYPE_BUY)
   {
      entryPrice = ask;
      sl  = NormalizeDouble(entryPrice - slDist,  digits);
      tp1 = NormalizeDouble(entryPrice + tp1Dist, digits);
      tp2 = NormalizeDouble(entryPrice + tp2Dist, digits);
      tp3 = NormalizeDouble(entryPrice + tp3Dist, digits);
   }
   else
   {
      entryPrice = bid;
      sl  = NormalizeDouble(entryPrice + slDist,  digits);
      tp1 = NormalizeDouble(entryPrice - tp1Dist, digits);
      tp2 = NormalizeDouble(entryPrice - tp2Dist, digits);
      tp3 = NormalizeDouble(entryPrice - tp3Dist, digits);
   }

   // Calculate position size based on risk
   double lotSize = CalcLotSize(slDist);
   if(lotSize <= 0) return;

   // Minimum SL distance check
   long   stopsLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double minSLDist  = stopsLevel * point;
   if(slDist < minSLDist + spread)
   {
      Print("SL too close to entry (broker restriction). Skipping.");
      return;
   }

   string comment = TradeComment + "_" + (orderType == ORDER_TYPE_BUY ? "B" : "S");

   // Open trade with TP3 as main TP (partial closes handled manually)
   bool result = trade.PositionOpen(_Symbol, orderType, lotSize, entryPrice, sl, tp3, comment);

   if(result && trade.ResultRetcode() == TRADE_RETCODE_DONE)
   {
      ulong ticket = trade.ResultOrder();
      Print("Trade opened: ticket=", ticket, " type=", EnumToString(orderType),
            " lot=", lotSize, " SL=", sl, " TP1=", tp1, " TP2=", tp2, " TP3=", tp3);
      // Store TP levels as custom properties via comment (simple approach)
      // In production, use a database or global variables
      StoreTPLevels(ticket, tp1, tp2, orderType);
   }
   else
   {
      Print("Trade failed: ", trade.ResultRetcodeDescription());
   }
}

//+------------------------------------------------------------------+
//| Store TP levels for partial close tracking                        |
//+------------------------------------------------------------------+
void StoreTPLevels(ulong ticket, double tp1, double tp2, ENUM_ORDER_TYPE dir)
{
   // Use GlobalVariables to store TP levels
   string prefix = "GSP_" + IntegerToString(ticket) + "_";
   GlobalVariableSet(prefix + "TP1", tp1);
   GlobalVariableSet(prefix + "TP2", tp2);
   GlobalVariableSet(prefix + "TP1Hit", 0);
   GlobalVariableSet(prefix + "TP2Hit", 0);
   GlobalVariableSet(prefix + "Dir", (dir == ORDER_TYPE_BUY) ? 1 : -1);
}

//+------------------------------------------------------------------+
//| Manage all open positions (partial close, trailing, BE)           |
//+------------------------------------------------------------------+
void ManageOpenTrades()
{
   double point  = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   int    digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(!posInfo.SelectByIndex(i)) continue;
      if(posInfo.Magic() != MagicNumber) continue;
      if(posInfo.Symbol() != _Symbol) continue;

      ulong ticket    = posInfo.Ticket();
      string prefix   = "GSP_" + IntegerToString(ticket) + "_";
      double tp1      = GlobalVariableGet(prefix + "TP1");
      double tp2      = GlobalVariableGet(prefix + "TP2");
      bool   tp1Hit   = (GlobalVariableGet(prefix + "TP1Hit") == 1);
      bool   tp2Hit   = (GlobalVariableGet(prefix + "TP2Hit") == 1);
      int    dir      = (int)GlobalVariableGet(prefix + "Dir");

      double curPrice = (dir == 1) ? SymbolInfoDouble(_Symbol, SYMBOL_BID)
                                   : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      double openPrice = posInfo.PriceOpen();
      double curSL     = posInfo.StopLoss();
      double curLots   = posInfo.Volume();
      double atr       = atr_entry[1];

      // --- PARTIAL CLOSE at TP1 ---
      if(!tp1Hit && tp1 > 0)
      {
         bool tp1Reached = (dir == 1) ? (curPrice >= tp1) : (curPrice <= tp1);
         if(tp1Reached)
         {
            double closeVol = NormalizeDouble(curLots * (TP1_ClosePercent / 100.0), 2);
            closeVol = MathMax(closeVol, SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN));
            if(closeVol < curLots)
            {
               if(trade.PositionClosePartial(ticket, closeVol))
               {
                  GlobalVariableSet(prefix + "TP1Hit", 1);
                  Print("TP1 hit - partial close ", closeVol, " lots on ticket ", ticket);
               }
            }
         }
      }

      // --- PARTIAL CLOSE at TP2 ---
      if(tp1Hit && !tp2Hit && tp2 > 0)
      {
         bool tp2Reached = (dir == 1) ? (curPrice >= tp2) : (curPrice <= tp2);
         if(tp2Reached)
         {
            double tp2ClosePct = TP2_ClosePercent / (100.0 - TP1_ClosePercent) * 100.0;
            double closeVol = NormalizeDouble(curLots * (tp2ClosePct / 100.0), 2);
            closeVol = MathMax(closeVol, SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN));
            if(closeVol < curLots)
            {
               if(trade.PositionClosePartial(ticket, closeVol))
               {
                  GlobalVariableSet(prefix + "TP2Hit", 1);
                  Print("TP2 hit - partial close ", closeVol, " lots on ticket ", ticket);
               }
            }
         }
      }

      // --- BREAK-EVEN ---
      if(EnableBreakEven && curSL != openPrice)
      {
         double beDistance = atr * BreakEven_ATR;
         bool beCondition = (dir == 1) ? (curPrice >= openPrice + beDistance)
                                       : (curPrice <= openPrice - beDistance);
         if(beCondition)
         {
            double newSL = (dir == 1)
                           ? NormalizeDouble(openPrice + 2 * point, digits)  // 2 pts above open
                           : NormalizeDouble(openPrice - 2 * point, digits);
            bool shouldMove = (dir == 1) ? (newSL > curSL) : (newSL < curSL || curSL == 0);
            if(shouldMove)
            {
               trade.PositionModify(ticket, newSL, posInfo.TakeProfit());
               Print("Break-even set for ticket ", ticket, " SL=", newSL);
            }
         }
      }

      // --- TRAILING STOP (only after TP1 hit) ---
      if(EnableTrailing && tp1Hit)
      {
         double trailDist = atr * TrailATR_Multi;
         double newSL     = 0;
         if(dir == 1)
         {
            newSL = NormalizeDouble(curPrice - trailDist, digits);
            if(newSL > curSL + TrailStep_Points * point)
               trade.PositionModify(ticket, newSL, posInfo.TakeProfit());
         }
         else
         {
            newSL = NormalizeDouble(curPrice + trailDist, digits);
            if(newSL < curSL - TrailStep_Points * point || curSL == 0)
               trade.PositionModify(ticket, newSL, posInfo.TakeProfit());
         }
      }

      // --- Clean up GlobalVars if position closed ---
      // (handled automatically when position disappears from loop)
   }
}

//+------------------------------------------------------------------+
//| Calculate lot size based on risk %                                |
//+------------------------------------------------------------------+
double CalcLotSize(double slDistancePrice)
{
   if(slDistancePrice <= 0) return 0;

   double equity       = AccountInfoDouble(ACCOUNT_EQUITY);
   double riskAmount   = equity * (RiskPercent / 100.0);
   double tickValue    = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize     = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double lotStep      = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double minLot       = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot       = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);

   if(tickValue <= 0 || tickSize <= 0) return 0;

   // Value per lot per price distance
   double valuePerLot = (slDistancePrice / tickSize) * tickValue;
   if(valuePerLot <= 0) return 0;

   double lots = riskAmount / valuePerLot;

   // Round to lot step
   lots = MathFloor(lots / lotStep) * lotStep;

   // Clamp
   lots = MathMax(lots, MathMax(minLot, MinLotSize));
   lots = MathMin(lots, MathMin(maxLot, MaxLotSize));

   return NormalizeDouble(lots, 2);
}

//+------------------------------------------------------------------+
//| Check daily reset and equity limits                               |
//+------------------------------------------------------------------+
void CheckDailyReset()
{
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   MqlDateTime dtLast;
   TimeToStruct(LastDayChecked, dtLast);

   if(dt.day != dtLast.day)
   {
      DayStartEquity  = AccountInfoDouble(ACCOUNT_EQUITY);
      LastDayChecked  = TimeCurrent();
      TradingAllowed  = true;
      Print("Daily reset: new equity baseline = ", DayStartEquity);
   }
}

//+------------------------------------------------------------------+
//| Check global risk limits                                          |
//+------------------------------------------------------------------+
bool CheckRiskLimits()
{
   double equity    = AccountInfoDouble(ACCOUNT_EQUITY);
   double balance   = AccountInfoDouble(ACCOUNT_BALANCE);

   // Max daily loss
   if(DayStartEquity > 0)
   {
      double dailyLoss = (DayStartEquity - equity) / DayStartEquity * 100.0;
      if(dailyLoss >= MaxDailyLossPerc)
      {
         if(TradingAllowed)
         {
            Print("MAX DAILY LOSS reached (", dailyLoss, "%). Trading halted for today.");
            TradingAllowed = false;
         }
         return false;
      }
   }

   // Max drawdown from starting equity
   if(StartingEquity > 0)
   {
      double drawdown = (StartingEquity - equity) / StartingEquity * 100.0;
      if(drawdown >= MaxDrawdownPerc)
      {
         if(TradingAllowed)
         {
            Print("MAX DRAWDOWN reached (", drawdown, "%). Trading halted.");
            TradingAllowed = false;
         }
         return false;
      }
   }

   return true;
}

//+------------------------------------------------------------------+
//| Check if we can open a new trade                                  |
//+------------------------------------------------------------------+
bool CanOpenNewTrade()
{
   if(!TradingAllowed) return false;

   int count = 0;
   for(int i = 0; i < PositionsTotal(); i++)
   {
      if(posInfo.SelectByIndex(i))
         if(posInfo.Magic() == MagicNumber && posInfo.Symbol() == _Symbol)
            count++;
   }
   return (count < MaxOpenTrades);
}

//+------------------------------------------------------------------+
//| Session filter                                                    |
//+------------------------------------------------------------------+
bool IsValidSession()
{
   MqlDateTime dt;
   TimeToStruct(TimeCurrent(), dt);
   int hour = dt.hour;

   bool london = (hour >= LondonOpen_H && hour < LondonClose_H);
   bool ny     = (hour >= NYOpen_H && hour < NYClose_H);
   bool asian  = (!london && !ny);

   if(london || ny) return true;
   if(TradeAsianSession && asian) return true;
   return false;
}

//+------------------------------------------------------------------+
//| Spread filter                                                     |
//+------------------------------------------------------------------+
bool IsSpreadOK()
{
   double spread = SymbolInfoDouble(_Symbol, SYMBOL_ASK) - SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double point  = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   return (spread / point <= MaxSpread_Points);
}

//+------------------------------------------------------------------+
//| News time filter                                                  |
//+------------------------------------------------------------------+
bool IsNewsTime()
{
   string newsTimes[] = {NewsTime1, NewsTime2, NewsTime3, NewsTime4, NewsTime5};
   datetime now = TimeCurrent();
   MqlDateTime dtNow;
   TimeToStruct(now, dtNow);

   for(int i = 0; i < ArraySize(newsTimes); i++)
   {
      if(newsTimes[i] == "") continue;
      string parts[];
      if(StringSplit(newsTimes[i], ':', parts) < 2) continue;

      int newsH = (int)StringToInteger(parts[0]);
      int newsM = (int)StringToInteger(parts[1]);

      // Build datetime for today's news
      MqlDateTime dtNews = dtNow;
      dtNews.hour = newsH;
      dtNews.min  = newsM;
      dtNews.sec  = 0;
      datetime newsTime = StructToTime(dtNews);

      long diffSeconds = (long)(now - newsTime);
      if(diffSeconds >= -(long)MinsBefore_News * 60 &&
         diffSeconds <= (long)MinsAfter_News * 60)
         return true; // in news window
   }
   return false;
}

//+------------------------------------------------------------------+
//| OnTradeTransaction - cleanup GlobalVars on position close         |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction& trans,
                        const MqlTradeRequest& request,
                        const MqlTradeResult& result)
{
   if(trans.type == TRADE_TRANSACTION_DEAL_ADD)
   {
      if(trans.deal_type == DEAL_TYPE_BUY || trans.deal_type == DEAL_TYPE_SELL)
      {
         // If position fully closed, clean up GlobalVars
         ulong posTicket = trans.position;
         if(!PositionSelectByTicket(posTicket))
         {
            string prefix = "GSP_" + IntegerToString(posTicket) + "_";
            GlobalVariableDel(prefix + "TP1");
            GlobalVariableDel(prefix + "TP2");
            GlobalVariableDel(prefix + "TP1Hit");
            GlobalVariableDel(prefix + "TP2Hit");
            GlobalVariableDel(prefix + "Dir");
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Dashboard on chart                                                |
//+------------------------------------------------------------------+
void OnChartEvent(const int id, const long& lparam,
                  const double& dparam, const string& sparam)
{
   // Reserved for interactive controls if needed
}

//+------------------------------------------------------------------+
//| Draw info panel                                                   |
//+------------------------------------------------------------------+
void DrawPanel()
{
   double equity   = AccountInfoDouble(ACCOUNT_EQUITY);
   double balance  = AccountInfoDouble(ACCOUNT_BALANCE);
   double dailyPnL = equity - DayStartEquity;
   string spread   = DoubleToString((SymbolInfoDouble(_Symbol, SYMBOL_ASK) -
                                     SymbolInfoDouble(_Symbol, SYMBOL_BID)) /
                                     SymbolInfoDouble(_Symbol, SYMBOL_POINT), 1);

   string info = "\n  GoldScalper Pro v3.0\n" +
                 "  Balance:  " + DoubleToString(balance,  2) + "\n" +
                 "  Equity:   " + DoubleToString(equity,   2) + "\n" +
                 "  Day PnL:  " + DoubleToString(dailyPnL, 2) + "\n" +
                 "  Spread:   " + spread + " pts\n" +
                 "  Trading:  " + (TradingAllowed ? "YES" : "HALTED") + "\n" +
                 "  Session:  " + (IsValidSession() ? "ACTIVE" : "CLOSED");

   Comment(info);
}
//+------------------------------------------------------------------+

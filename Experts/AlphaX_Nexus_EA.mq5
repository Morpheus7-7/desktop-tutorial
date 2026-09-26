//+------------------------------------------------------------------+
//| AlphaX_Nexus_EA.mq5                                               |
//| AlphaX Nexus - Multi-Timeframe SMC x Order Flow Trading Engine   |
//| Expert Advisor evolution of the AlphaX_Nexus indicator           |
//|                                                                  |
//| Each traded timeframe runs an INDEPENDENT instance of the        |
//| confluence engine and trades with ITS OWN magic number, so       |
//| positions are isolated, manageable and trackable per TF.         |
//| (c) AlphaX                                                        |
//+------------------------------------------------------------------+
#property copyright   "AlphaX"
#property link        ""
#property version     "3.00"
#property description "Multi-Timeframe SMC x Order Flow Trading Engine"
#property description "Each timeframe trades with its own magic number"

#include <Trade/Trade.mqh>
#include <Trade/PositionInfo.mqh>

// ═══════════════════════════════════════════════════════════════════
// ══════════════════════ INPUT PARAMETERS ══════════════════════════
// ═══════════════════════════════════════════════════════════════════

// ── General / Risk ────────────────────────────────────────────────
input group "══════ General & Risk ══════"
input long   InpMagicBase        = 990000;   // Magic Base (per-TF magic = base + TF minutes)
input double InpRiskPercent      = 0.5;      // Risk % of equity per trade
input double InpFixedLots         = 0.0;     // Fixed lots (0 = use risk %)
input int    InpMaxSpreadPts     = 35;       // Max spread (points, 0 = ignore)
input int    InpSlippagePts      = 15;       // Max slippage / deviation (points)
input int    InpLookbackBars     = 320;      // Bars analyzed per timeframe
input int    InpMaxOpenTotal     = 6;        // Max simultaneous positions (all TFs)
input string InpTradeComment     = "AlphaX_Nexus";

// ── Timeframes to trade (each gets its own magic) ─────────────────
input group "══════ Timeframes (each = own magic) ══════"
input bool   InpTradeM5          = false;    // Trade M5
input bool   InpTradeM15         = true;     // Trade M15
input bool   InpTradeM30         = false;    // Trade M30
input bool   InpTradeH1          = true;     // Trade H1
input bool   InpTradeH4          = true;     // Trade H4
input bool   InpTradeD1          = false;    // Trade D1

// ── Confluence Engine ─────────────────────────────────────────────
input group "══════ Confluence Engine ══════"
input int    InpSwingLen         = 7;        // Swing detection length
input int    InpMinConfluence    = 4;        // Min confluence score (out of 8)
input int    InpCooldownBars     = 5;        // Cooldown bars after a trade (per TF)
input int    InpEmaFastLen       = 21;       // Fast EMA
input int    InpEmaMediumLen     = 50;       // Medium EMA
input int    InpEmaSlowLen       = 200;      // Slow EMA
input int    InpAtrLen           = 14;       // ATR length

// ── Order Blocks / FVG / Liquidity ────────────────────────────────
input group "══════ SMC Zones ══════"
input int    InpOBMaxAge         = 80;       // OB max age (bars)
input bool   InpOBVolumeFilter   = true;     // Require volume confirmation on OB
input double InpOBVolMultiplier  = 1.4;      // OB volume multiplier
input int    InpFVGMaxAge        = 60;       // FVG max age (bars)
input double InpFVGMinSize       = 15.0;     // Min FVG size (% of ATR)
input int    InpLiqLookback      = 25;       // Liquidity lookback

// ── Order Flow ────────────────────────────────────────────────────
input group "══════ Order Flow ══════"
input int    InpVolSmaLen        = 20;       // Volume SMA length
input double InpVolSpikeMulti    = 1.8;      // Volume spike multiplier
input double InpAbsorbRatio      = 2.0;      // Absorption wick/body ratio
input int    InpDeltaLen         = 4;        // Delta smooth length

// ── Multi-Timeframe Trend Filter ──────────────────────────────────
input group "══════ HTF Trend Filter ══════"
input bool   InpUseHTFFilter     = true;     // Align entries with next-higher TF
input int    InpHTFEmaLen        = 50;       // HTF EMA length

// ── Exit / Trade Management ───────────────────────────────────────
input group "══════ Exits & Management ══════"
input double InpRiskReward       = 2.0;      // Risk : Reward ratio
input double InpSLPaddingATR     = 0.5;      // SL padding (x ATR)
input bool   InpUseBreakeven     = true;     // Enable breakeven
input double InpBE_TriggerR      = 1.0;      // Move to BE at +R
input double InpBE_LockPts       = 10;       // Lock-in points at BE
input bool   InpUseTrailing      = true;     // Enable ATR trailing stop
input double InpTrailATRmult     = 2.0;      // Trailing distance (x ATR)
input double InpTrailStartR      = 1.0;      // Start trailing at +R

// ── Session Filter ────────────────────────────────────────────────
input group "══════ Session Filter ══════"
input bool   InpUseSession       = false;    // Restrict trading hours (server time)
input int    InpStartHour        = 7;        // Start hour
input int    InpEndHour          = 21;       // End hour
input bool   InpCloseOutsideSess = false;    // Close positions outside session

// ── Display ───────────────────────────────────────────────────────
input group "══════ Display ══════"
input bool   InpShowDashboard    = true;     // Show on-chart dashboard
input bool   InpAlertPush        = false;    // Push notifications on entry
input bool   InpAlertPopup       = false;    // Popup alerts on entry


// ═══════════════════════════════════════════════════════════════════
// ══════════════════════ DATA STRUCTURES ═══════════════════════════
// ═══════════════════════════════════════════════════════════════════

// Result of one confluence evaluation on the last closed bar of a TF
struct SSignal
{
   bool   valid;
   int    dir;            // +1 long, -1 short, 0 none
   int    bullScore;
   int    bearScore;
   double bullConf;
   double bearConf;
   int    structTrend;    // 1 bull, -1 bear, 0 range
   double atr;
   double slLong;         // proposed SL for a long (zone-aware)
   double slShort;        // proposed SL for a short
   double refClose;       // close of the decision bar
};

// Lightweight zone records used inside the per-TF evaluation
struct SZone
{
   double top;
   double bottom;
   int    startIdx;
   bool   isBull;
};

// Per-timeframe trading unit
struct STFUnit
{
   ENUM_TIMEFRAMES tf;
   long            magic;
   int             hEmaF, hEmaM, hEmaS, hATR;
   int             hHTFEma;          // higher-TF trend EMA
   ENUM_TIMEFRAMES htf;              // the higher timeframe used for filter
   datetime        lastBarTime;      // last processed bar open time
   datetime        lastTradeTime;    // open time of bar that produced last trade
   // cached state for dashboard
   int             dashTrend;
   int             dashBull;
   int             dashBear;
   string          dashState;
};


// ═══════════════════════════════════════════════════════════════════
// ══════════════════════ GLOBALS ═══════════════════════════════════
// ═══════════════════════════════════════════════════════════════════

STFUnit        g_units[];
CTrade         g_trade;
CPositionInfo  g_pos;
string         g_dashName = "AlphaX_EA_Dash";


// ═══════════════════════════════════════════════════════════════════
// ══════════════════════ INITIALIZATION ════════════════════════════
// ═══════════════════════════════════════════════════════════════════

int OnInit()
{
   ArrayResize(g_units, 0);

   ENUM_TIMEFRAMES wanted[6];
   bool            enabled[6];
   wanted[0]=PERIOD_M5;  enabled[0]=InpTradeM5;
   wanted[1]=PERIOD_M15; enabled[1]=InpTradeM15;
   wanted[2]=PERIOD_M30; enabled[2]=InpTradeM30;
   wanted[3]=PERIOD_H1;  enabled[3]=InpTradeH1;
   wanted[4]=PERIOD_H4;  enabled[4]=InpTradeH4;
   wanted[5]=PERIOD_D1;  enabled[5]=InpTradeD1;

   for(int k=0; k<6; k++)
   {
      if(!enabled[k]) continue;
      if(!AddUnit(wanted[k]))
      {
         Print("Failed to initialise unit for ", EnumToString(wanted[k]));
         return INIT_FAILED;
      }
   }

   if(ArraySize(g_units) == 0)
   {
      Print("No timeframe enabled - enable at least one TF to trade.");
      return INIT_FAILED;
   }

   g_trade.SetDeviationInPoints(InpSlippagePts);
   g_trade.SetTypeFillingBySymbol(_Symbol);
   g_trade.SetAsyncMode(false);

   PrintFormat("AlphaX Nexus EA started on %s with %d timeframe unit(s).",
               _Symbol, ArraySize(g_units));
   for(int u=0; u<ArraySize(g_units); u++)
      PrintFormat("  %-5s -> magic %I64d",
                  EnumToString(g_units[u].tf), g_units[u].magic);

   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Create indicator handles for one timeframe unit                  |
//+------------------------------------------------------------------+
bool AddUnit(ENUM_TIMEFRAMES tf)
{
   STFUnit u;
   u.tf            = tf;
   u.magic         = TFMagic(tf);
   u.htf           = HigherTF(tf);
   u.lastBarTime   = 0;
   u.lastTradeTime = 0;
   u.dashTrend     = 0;
   u.dashBull      = 0;
   u.dashBear      = 0;
   u.dashState     = "init";

   u.hEmaF = iMA(_Symbol, tf, InpEmaFastLen,   0, MODE_EMA, PRICE_CLOSE);
   u.hEmaM = iMA(_Symbol, tf, InpEmaMediumLen, 0, MODE_EMA, PRICE_CLOSE);
   u.hEmaS = iMA(_Symbol, tf, InpEmaSlowLen,   0, MODE_EMA, PRICE_CLOSE);
   u.hATR  = iATR(_Symbol, tf, InpAtrLen);
   u.hHTFEma = InpUseHTFFilter ? iMA(_Symbol, u.htf, InpHTFEmaLen, 0, MODE_EMA, PRICE_CLOSE)
                               : INVALID_HANDLE;

   if(u.hEmaF==INVALID_HANDLE || u.hEmaM==INVALID_HANDLE ||
      u.hEmaS==INVALID_HANDLE || u.hATR==INVALID_HANDLE)
      return false;

   int sz = ArraySize(g_units);
   ArrayResize(g_units, sz+1);
   g_units[sz] = u;
   return true;
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   for(int u=0; u<ArraySize(g_units); u++)
   {
      if(g_units[u].hEmaF   != INVALID_HANDLE) IndicatorRelease(g_units[u].hEmaF);
      if(g_units[u].hEmaM   != INVALID_HANDLE) IndicatorRelease(g_units[u].hEmaM);
      if(g_units[u].hEmaS   != INVALID_HANDLE) IndicatorRelease(g_units[u].hEmaS);
      if(g_units[u].hATR    != INVALID_HANDLE) IndicatorRelease(g_units[u].hATR);
      if(g_units[u].hHTFEma != INVALID_HANDLE) IndicatorRelease(g_units[u].hHTFEma);
   }
   ObjectDelete(0, g_dashName);
   Comment("");
}


// ═══════════════════════════════════════════════════════════════════
// ══════════════════════ MAIN TICK LOOP ════════════════════════════
// ═══════════════════════════════════════════════════════════════════

void OnTick()
{
   // Manage open trades every tick (trailing / breakeven / session close)
   ManageOpenPositions();

   // Entry evaluation happens once per closed bar of each timeframe
   for(int u=0; u<ArraySize(g_units); u++)
   {
      datetime barTime = iTime(_Symbol, g_units[u].tf, 0);
      if(barTime == 0) continue;                 // data not ready
      if(barTime == g_units[u].lastBarTime) continue; // same bar, skip
      g_units[u].lastBarTime = barTime;          // new bar on this TF

      ProcessUnitNewBar(u);
   }

   if(InpShowDashboard)
      UpdateDashboard();
}

//+------------------------------------------------------------------+
//| New-bar entry logic for a single timeframe unit                  |
//+------------------------------------------------------------------+
void ProcessUnitNewBar(int u)
{
   SSignal sig;
   if(!EvaluateTF(g_units[u], sig))
      return;

   // cache for dashboard
   g_units[u].dashTrend = sig.structTrend;
   g_units[u].dashBull  = sig.bullScore;
   g_units[u].dashBear  = sig.bearScore;

   // Already have a position for this TF magic? -> no new entry
   if(CountPositions(g_units[u].magic) > 0)
   {
      g_units[u].dashState = "in trade";
      return;
   }

   // Global cap
   if(CountPositions(0) >= InpMaxOpenTotal)
   {
      g_units[u].dashState = "max open";
      return;
   }

   // Cooldown (measured in bars of this TF)
   if(g_units[u].lastTradeTime > 0)
   {
      int barsSince = iBarShift(_Symbol, g_units[u].tf, g_units[u].lastTradeTime, false);
      if(barsSince < InpCooldownBars)
      {
         g_units[u].dashState = "cooldown";
         return;
      }
   }

   // Session filter
   if(!SessionOK())
   {
      g_units[u].dashState = "off-session";
      return;
   }

   // Spread filter
   if(InpMaxSpreadPts > 0)
   {
      long spread = (long)SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
      if(spread > InpMaxSpreadPts)
      {
         g_units[u].dashState = "wide spread";
         return;
      }
   }

   if(sig.dir == 0)
   {
      g_units[u].dashState = "no edge";
      return;
   }

   // HTF trend filter
   if(InpUseHTFFilter && !HTFAligned(g_units[u], sig.dir))
   {
      g_units[u].dashState = "htf block";
      return;
   }

   // ── Build & send the order ──────────────────────────────────────
   if(OpenTrade(u, sig))
   {
      g_units[u].lastTradeTime = g_units[u].lastBarTime;
      g_units[u].dashState     = (sig.dir>0 ? "LONG opened" : "SHORT opened");
   }
}


// ═══════════════════════════════════════════════════════════════════
// ══════════════════════ ORDER EXECUTION ═══════════════════════════
// ═══════════════════════════════════════════════════════════════════

bool OpenTrade(int u, const SSignal &sig)
{
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(ask<=0 || bid<=0) return false;

   double entry, sl, tp;
   if(sig.dir > 0)
   {
      entry = ask;
      sl    = sig.slLong;
      if(sl >= entry) sl = entry - sig.atr * (InpSLPaddingATR + 0.5);
      double risk = entry - sl;
      if(risk <= 0) return false;
      tp = entry + risk * InpRiskReward;
   }
   else
   {
      entry = bid;
      sl    = sig.slShort;
      if(sl <= entry) sl = entry + sig.atr * (InpSLPaddingATR + 0.5);
      double risk = sl - entry;
      if(risk <= 0) return false;
      tp = entry - risk * InpRiskReward;
   }

   // Respect broker stops level
   if(!NormalizeStops(sig.dir, entry, sl, tp)) return false;

   double riskDist = MathAbs(entry - sl);
   double lots = CalcLots(riskDist);
   if(lots <= 0) return false;

   g_trade.SetExpertMagicNumber(g_units[u].magic);
   string cmt = StringFormat("%s_%s", InpTradeComment, TFToStr(g_units[u].tf));

   bool ok;
   if(sig.dir > 0)
      ok = g_trade.Buy(lots, _Symbol, 0.0, sl, tp, cmt);
   else
      ok = g_trade.Sell(lots, _Symbol, 0.0, sl, tp, cmt);

   if(!ok)
   {
      PrintFormat("[%s] order failed: retcode=%d %s",
                  TFToStr(g_units[u].tf), g_trade.ResultRetcode(),
                  g_trade.ResultRetcodeDescription());
      return false;
   }

   PrintFormat("[%s] %s %.2f lots @ %.5f  SL %.5f  TP %.5f  (score %d/%d  conf %.0f%%)",
               TFToStr(g_units[u].tf), (sig.dir>0?"BUY":"SELL"), lots, entry, sl, tp,
               (sig.dir>0?sig.bullScore:sig.bearScore), 8,
               (sig.dir>0?sig.bullConf:sig.bearConf));

   if(InpAlertPopup || InpAlertPush)
   {
      string msg = StringFormat("AlphaX %s %s %s  SL %s TP %s",
                     (sig.dir>0?"LONG":"SHORT"), _Symbol, TFToStr(g_units[u].tf),
                     DoubleToString(sl,_Digits), DoubleToString(tp,_Digits));
      if(InpAlertPopup) Alert(msg);
      if(InpAlertPush)  SendNotification(msg);
   }

   return true;
}

//+------------------------------------------------------------------+
//| Position sizing from SL distance and risk %                      |
//+------------------------------------------------------------------+
double CalcLots(double riskDistPrice)
{
   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(lotStep<=0) lotStep = 0.01;

   if(InpFixedLots > 0.0)
      return ClampLot(InpFixedLots, minLot, maxLot, lotStep);

   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickValue<=0 || tickSize<=0 || riskDistPrice<=0)
      return ClampLot(minLot, minLot, maxLot, lotStep);

   double valuePerUnit = tickValue / tickSize;          // money per 1.0 lot per 1 price unit
   double riskMoney    = AccountInfoDouble(ACCOUNT_EQUITY) * InpRiskPercent / 100.0;
   double lots         = riskMoney / (riskDistPrice * valuePerUnit);

   return ClampLot(lots, minLot, maxLot, lotStep);
}

double ClampLot(double lots, double minLot, double maxLot, double lotStep)
{
   lots = MathFloor(lots / lotStep) * lotStep;
   if(lots < minLot) lots = minLot;
   if(lots > maxLot) lots = maxLot;
   return NormalizeDouble(lots, 2);
}

//+------------------------------------------------------------------+
//| Clamp SL/TP to broker stops level & freeze distance              |
//+------------------------------------------------------------------+
bool NormalizeStops(int dir, double entry, double &sl, double &tp)
{
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   long   stopsLevel = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL);
   double minDist = stopsLevel * point;
   if(minDist <= 0) minDist = point * 5;   // safety floor

   if(dir > 0)
   {
      if(entry - sl < minDist) sl = entry - minDist;
      if(tp - entry < minDist) tp = entry + minDist;
   }
   else
   {
      if(sl - entry < minDist) sl = entry + minDist;
      if(entry - tp < minDist) tp = entry - minDist;
   }
   sl = NormalizeDouble(sl, _Digits);
   tp = NormalizeDouble(tp, _Digits);
   return true;
}


// ═══════════════════════════════════════════════════════════════════
// ══════════════════════ POSITION MANAGEMENT ═══════════════════════
// ═══════════════════════════════════════════════════════════════════

void ManageOpenPositions()
{
   for(int i = PositionsTotal()-1; i>=0; i--)
   {
      ulong ticket = PositionGetTicket(i);
      if(ticket==0) continue;
      if(!g_pos.SelectByTicket(ticket)) continue;
      if(g_pos.Symbol() != _Symbol) continue;

      long magic = g_pos.Magic();
      int  uidx  = UnitIndexByMagic(magic);
      if(uidx < 0) continue;     // not ours

      // Close outside session if requested
      if(InpUseSession && InpCloseOutsideSess && !SessionOK())
      {
         g_trade.SetExpertMagicNumber(magic);
         g_trade.PositionClose(ticket);
         continue;
      }

      double atr = GetATR(g_units[uidx]);
      if(atr <= 0) continue;

      ApplyBreakevenAndTrail(ticket, atr);
   }
}

//+------------------------------------------------------------------+
void ApplyBreakevenAndTrail(ulong ticket, double atr)
{
   if(!g_pos.SelectByTicket(ticket)) return;

   long   type   = g_pos.PositionType();
   double open   = g_pos.PriceOpen();
   double curSL  = g_pos.StopLoss();
   double curTP  = g_pos.TakeProfit();
   double point  = SymbolInfoDouble(_Symbol, SYMBOL_POINT);
   double bid    = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask    = SymbolInfoDouble(_Symbol, SYMBOL_ASK);

   // Risk distance = |open - original SL|. If SL already moved we approximate
   // with ATR-based distance, which is fine for R-multiple gating.
   double riskDist = (curSL>0) ? MathAbs(open - curSL) : atr * (InpSLPaddingATR + 0.5);
   if(riskDist <= 0) riskDist = atr;

   double newSL = curSL;
   bool   changed = false;

   if(type == POSITION_TYPE_BUY)
   {
      double profit = bid - open;

      // Breakeven
      if(InpUseBreakeven && profit >= riskDist * InpBE_TriggerR)
      {
         double beSL = open + InpBE_LockPts * point;
         if(beSL > newSL) { newSL = beSL; changed = true; }
      }
      // Trailing
      if(InpUseTrailing && profit >= riskDist * InpTrailStartR)
      {
         double trail = bid - atr * InpTrailATRmult;
         if(trail > newSL) { newSL = trail; changed = true; }
      }
      // never move SL above current price
      if(newSL >= bid) changed = false;
   }
   else if(type == POSITION_TYPE_SELL)
   {
      double profit = open - ask;

      if(InpUseBreakeven && profit >= riskDist * InpBE_TriggerR)
      {
         double beSL = open - InpBE_LockPts * point;
         if(curSL<=0 || beSL < newSL) { newSL = beSL; changed = true; }
      }
      if(InpUseTrailing && profit >= riskDist * InpTrailStartR)
      {
         double trail = ask + atr * InpTrailATRmult;
         if(curSL<=0 || trail < newSL) { newSL = trail; changed = true; }
      }
      if(newSL <= ask) changed = false;
   }

   if(changed)
   {
      newSL = NormalizeDouble(newSL, _Digits);
      if(MathAbs(newSL - curSL) >= point)
      {
         g_trade.SetExpertMagicNumber(g_pos.Magic());
         g_trade.PositionModify(ticket, newSL, curTP);
      }
   }
}


// ═══════════════════════════════════════════════════════════════════
// ══════════════════════ CONFLUENCE EVALUATION ═════════════════════
// ═══════════════════════════════════════════════════════════════════
//
// Recomputes the full SMC/order-flow state machine over a fixed window
// of CLOSED bars for the given timeframe and returns the scores for the
// most recently closed bar. Stateless per call => no repaint / no drift.
//+------------------------------------------------------------------+
bool EvaluateTF(STFUnit &u, SSignal &sig)
{
   ZeroSignal(sig);

   int need = InpLookbackBars;
   int minBars = MathMax(InpEmaSlowLen, InpLiqLookback) + InpSwingLen + 10;
   if(need < minBars) need = minBars;

   MqlRates rates[];
   ArraySetAsSeries(rates, false);
   // start at shift 1 => exclude the still-forming bar
   int copied = CopyRates(_Symbol, u.tf, 1, need, rates);
   if(copied < minBars) return false;
   int n = copied;

   double emaF[], emaM[], emaS[], atr[];
   ArraySetAsSeries(emaF,false); ArraySetAsSeries(emaM,false);
   ArraySetAsSeries(emaS,false); ArraySetAsSeries(atr,false);
   if(CopyBuffer(u.hEmaF,0,1,need,emaF) < n) return false;
   if(CopyBuffer(u.hEmaM,0,1,need,emaM) < n) return false;
   if(CopyBuffer(u.hEmaS,0,1,need,emaS) < n) return false;
   if(CopyBuffer(u.hATR ,0,1,need,atr)  < n) return false;

   // local price arrays
   double open[], high[], low[], close[];
   long   vol[];
   ArrayResize(open,n); ArrayResize(high,n); ArrayResize(low,n);
   ArrayResize(close,n); ArrayResize(vol,n);
   bool useRealVol = (rates[n-1].real_volume > 0);
   for(int i=0;i<n;i++)
   {
      open[i]=rates[i].open; high[i]=rates[i].high;
      low[i]=rates[i].low;   close[i]=rates[i].close;
      vol[i] = useRealVol ? (long)rates[i].real_volume : (long)rates[i].tick_volume;
   }

   // ── State machine ───────────────────────────────────────────────
   int    structTrend = 0;
   double lastSH=0,lastSL=0,prevSH=0,prevSL=0;
   double smoothDeltaPrev = 0; bool haveDelta=false;
   double smoothDeltaArr[]; ArrayResize(smoothDeltaArr,n);

   SZone obArr[];   ArrayResize(obArr,0);
   SZone fvgArr[];  ArrayResize(fvgArr,0);

   // outputs at the last bar
   int last = n-1;
   bool priceInBullOB=false, priceInBearOB=false;
   bool priceInBullFVG=false, priceInBearFVG=false;
   bool bullLiqSweep=false, bearLiqSweep=false;
   bool bullAbsorption=false, bearAbsorption=false;
   bool deltaBullDiv=false, deltaBearDiv=false;
   bool volAboveAvg=false;
   double bestBullOBbottom=0, bestBearOBtop=0;

   for(int i=0;i<n;i++)
   {
      double atrVal = atr[i];
      if(atrVal<=0){ smoothDeltaArr[i]=(i>0?smoothDeltaArr[i-1]:0); continue; }

      // volume sma
      double volSma=0;
      if(i>=InpVolSmaLen)
      {
         double s=0;
         for(int v=i-InpVolSmaLen+1; v<=i; v++) s += (double)vol[v];
         volSma = s/InpVolSmaLen;
      }
      bool volSpikeNow  = volSma>0 && (double)vol[i] > volSma*InpVolSpikeMulti;
      bool volAboveNow  = volSma>0 && (double)vol[i] > volSma;

      // delta estimation
      double rng = high[i]-low[i];
      double body= MathAbs(close[i]-open[i]);
      double upWick = high[i]-MathMax(close[i],open[i]);
      double dnWick = MathMin(close[i],open[i])-low[i];
      double buyEst = rng>0 ? (double)vol[i]*((close[i]-low[i])/rng) : (double)vol[i]*0.5;
      double rawDelta = buyEst - ((double)vol[i]-buyEst);
      double sd;
      if(haveDelta) sd = EmaStep(rawDelta, smoothDeltaPrev, InpDeltaLen);
      else          { sd = rawDelta; haveDelta=true; }
      smoothDeltaArr[i]=sd; smoothDeltaPrev=sd;

      bool deltaRising  = (i>=2)&& sd>smoothDeltaArr[i-1] && smoothDeltaArr[i-1]>smoothDeltaArr[i-2];
      bool deltaFalling = (i>=2)&& sd<smoothDeltaArr[i-1] && smoothDeltaArr[i-1]<smoothDeltaArr[i-2];
      bool priceNewHigh = (i>=10)&& high[i]==HighestRange(high,i-9,10,n);
      bool priceNewLow  = (i>=10)&& low[i] ==LowestRange(low, i-9,10,n);
      bool dBearDiv = priceNewHigh && deltaFalling;
      bool dBullDiv = priceNewLow  && deltaRising;

      // absorption
      bool bAbs = dnWick>body*InpAbsorbRatio && volAboveNow && close[i]>open[i] && dnWick>upWick*1.5;
      bool sAbs = upWick>body*InpAbsorbRatio && volAboveNow && close[i]<open[i] && upWick>dnWick*1.5;

      // swings (pivot confirmed InpSwingLen bars later)
      int pivot = i - InpSwingLen;
      if(pivot >= InpSwingLen)
      {
         double sh = PivotHigh(high, pivot, InpSwingLen, n);
         if(sh>0){ prevSH=lastSH; lastSH=sh; }
         double slp = PivotLow(low, pivot, InpSwingLen, n);
         if(slp>0){ prevSL=lastSL; lastSL=slp; }
      }

      // structure
      bool bosUp=false,bosDn=false,chUp=false,chDn=false;
      if(lastSH>0 && close[i]>lastSH && i>0 && close[i-1]<=lastSH)
      {
         if(structTrend>=0){bosUp=true;structTrend=1;} else {chUp=true;structTrend=1;}
      }
      if(lastSL>0 && close[i]<lastSL && i>0 && close[i-1]>=lastSL)
      {
         if(structTrend<=0){bosDn=true;structTrend=-1;} else {chDn=true;structTrend=-1;}
      }

      // order blocks
      if(bosUp||chUp)
      {
         for(int kk=1; kk<=15 && (i-kk)>=0; kk++)
            if(close[i-kk]<open[i-kk])
            {
               bool volOK = !InpOBVolumeFilter || VolOK(vol,i-kk,InpVolSmaLen,n,InpOBVolMultiplier);
               if(volOK) AddZone(obArr, high[i-kk], low[i-kk], i-kk, true);
               break;
            }
      }
      if(bosDn||chDn)
      {
         for(int kk=1; kk<=15 && (i-kk)>=0; kk++)
            if(close[i-kk]>open[i-kk])
            {
               bool volOK = !InpOBVolumeFilter || VolOK(vol,i-kk,InpVolSmaLen,n,InpOBVolMultiplier);
               if(volOK) AddZone(obArr, high[i-kk], low[i-kk], i-kk, false);
               break;
            }
      }

      // OB mitigation / age / containment at last bar
      bool inBullOB=false, inBearOB=false;
      for(int j=ArraySize(obArr)-1;j>=0;j--)
      {
         if(i - obArr[j].startIdx > InpOBMaxAge){ RemoveZone(obArr,j); continue; }
         bool mit;
         if(obArr[j].isBull)
         {
            mit = low[i] < obArr[j].bottom;
            if(!mit && low[i]<=obArr[j].top && high[i]>=obArr[j].bottom) inBullOB=true;
         }
         else
         {
            mit = high[i] > obArr[j].top;
            if(!mit && high[i]>=obArr[j].bottom && low[i]<=obArr[j].top) inBearOB=true;
         }
         if(mit) RemoveZone(obArr,j);
      }

      // FVG
      if(i>=2)
      {
         double minSize = atrVal*InpFVGMinSize/100.0;
         double buT=low[i], buB=high[i-2];
         if(buB<buT && close[i-1]>open[i-1] && (buT-buB)>minSize)
            AddZone(fvgArr, buT, buB, i-1, true);
         double beT=low[i-2], beB=high[i];
         if(beT>beB && close[i-1]<open[i-1] && (beT-beB)>minSize)
            AddZone(fvgArr, beT, beB, i-1, false);
      }
      bool inBullFVG=false, inBearFVG=false;
      for(int j=ArraySize(fvgArr)-1;j>=0;j--)
      {
         if(i - fvgArr[j].startIdx > InpFVGMaxAge){ RemoveZone(fvgArr,j); continue; }
         bool fill;
         if(fvgArr[j].isBull)
         {
            fill = low[i] <= fvgArr[j].bottom;
            if(!fill && low[i]<=fvgArr[j].top && high[i]>=fvgArr[j].bottom) inBullFVG=true;
         }
         else
         {
            fill = high[i] >= fvgArr[j].top;
            if(!fill && high[i]>=fvgArr[j].bottom && low[i]<=fvgArr[j].top) inBearFVG=true;
         }
         if(fill) RemoveZone(fvgArr,j);
      }

      // liquidity sweep
      bool bLiq=false,sLiq=false;
      if(i>=InpLiqLookback+1)
      {
         double prevLow  = LowestRange(low,  i-InpLiqLookback-1, InpLiqLookback, n);
         double prevHigh = HighestRange(high,i-InpLiqLookback-1, InpLiqLookback, n);
         bLiq = low[i]<prevLow  && close[i]>prevLow  && close[i]>open[i];
         sLiq = high[i]>prevHigh&& close[i]<prevHigh && close[i]<open[i];
      }

      // capture last-bar values
      if(i==last)
      {
         priceInBullOB=inBullOB; priceInBearOB=inBearOB;
         priceInBullFVG=inBullFVG; priceInBearFVG=inBearFVG;
         bullLiqSweep=bLiq; bearLiqSweep=sLiq;
         bullAbsorption=bAbs; bearAbsorption=sAbs;
         deltaBullDiv=dBullDiv; deltaBearDiv=dBearDiv;
         volAboveAvg=volAboveNow;

         // zone-based SL references
         for(int j=ArraySize(obArr)-1;j>=0;j--)
            if(obArr[j].isBull){ bestBullOBbottom=obArr[j].bottom; break; }
         for(int j=ArraySize(obArr)-1;j>=0;j--)
            if(!obArr[j].isBull){ bestBearOBtop=obArr[j].top; break; }
      }
   }

   // ── Scoring on last bar (mirrors indicator) ─────────────────────
   double cF=emaF[last], cM=emaM[last], cS=emaS[last], cC=close[last], cO=open[last];
   bool emaBull = cF>cM && cM>cS;
   bool emaBear = cF<cM && cM<cS;
   bool aboveEma = cC>cS, belowEma = cC<cS;

   int bull=0;
   bull += (structTrend==1);
   bull += priceInBullOB;
   bull += priceInBullFVG;
   bull += bullLiqSweep;
   bull += (volAboveAvg && cC>cO);
   bull += bullAbsorption;
   bull += deltaBullDiv;
   bull += (emaBull || (aboveEma && cF>cM));

   int bear=0;
   bear += (structTrend==-1);
   bear += priceInBearOB;
   bear += priceInBearFVG;
   bear += bearLiqSweep;
   bear += (volAboveAvg && cC<cO);
   bear += bearAbsorption;
   bear += deltaBearDiv;
   bear += (emaBear || (belowEma && cF<cM));

   double bullConf=0, bearConf=0;
   bullConf += structTrend==1?25:(structTrend==0?10:0);
   bullConf += priceInBullOB?15:0;  bullConf += priceInBullFVG?10:0;
   bullConf += bullLiqSweep?15:0;   bullConf += bullAbsorption?10:0;
   bullConf += deltaBullDiv?8:0;    bullConf += (volAboveAvg&&cC>cO)?7:0;
   bullConf += emaBull?10:(aboveEma?5:0); if(bullConf>100)bullConf=100;

   bearConf += structTrend==-1?25:(structTrend==0?10:0);
   bearConf += priceInBearOB?15:0;  bearConf += priceInBearFVG?10:0;
   bearConf += bearLiqSweep?15:0;   bearConf += bearAbsorption?10:0;
   bearConf += deltaBearDiv?8:0;    bearConf += (volAboveAvg&&cC<cO)?7:0;
   bearConf += emaBear?10:(belowEma?5:0); if(bearConf>100)bearConf=100;

   double atrLast = atr[last];

   // direction: require min confluence + bullish/bearish close + clear winner
   int dir = 0;
   bool bullOK = bull>=InpMinConfluence && cC>cO;
   bool bearOK = bear>=InpMinConfluence && cC<cO;
   if(bullOK && !bearOK) dir=1;
   else if(bearOK && !bullOK) dir=-1;
   else if(bullOK && bearOK)  dir = (bull>bear)?1:(bear>bull?-1:0);

   // SL references (zone-aware, fallback to ATR swing)
   double slLong  = bestBullOBbottom>0 ? bestBullOBbottom - atrLast*InpSLPaddingATR
                                       : low[last] - atrLast*InpSLPaddingATR;
   double slShort = bestBearOBtop>0    ? bestBearOBtop + atrLast*InpSLPaddingATR
                                       : high[last] + atrLast*InpSLPaddingATR;

   sig.valid       = true;
   sig.dir         = dir;
   sig.bullScore   = bull;
   sig.bearScore   = bear;
   sig.bullConf    = bullConf;
   sig.bearConf    = bearConf;
   sig.structTrend = structTrend;
   sig.atr         = atrLast;
   sig.slLong      = slLong;
   sig.slShort     = slShort;
   sig.refClose    = cC;
   return true;
}


// ═══════════════════════════════════════════════════════════════════
// ══════════════════════ HELPER FUNCTIONS ══════════════════════════
// ═══════════════════════════════════════════════════════════════════

void ZeroSignal(SSignal &s)
{
   s.valid=false; s.dir=0; s.bullScore=0; s.bearScore=0;
   s.bullConf=0; s.bearConf=0; s.structTrend=0; s.atr=0;
   s.slLong=0; s.slShort=0; s.refClose=0;
}

long TFMagic(ENUM_TIMEFRAMES tf)
{
   return InpMagicBase + (long)(PeriodSeconds(tf)/60);
}

int UnitIndexByMagic(long magic)
{
   for(int u=0;u<ArraySize(g_units);u++)
      if(g_units[u].magic==magic) return u;
   return -1;
}

ENUM_TIMEFRAMES HigherTF(ENUM_TIMEFRAMES tf)
{
   switch(tf)
   {
      case PERIOD_M1:  return PERIOD_M15;
      case PERIOD_M5:  return PERIOD_H1;
      case PERIOD_M15: return PERIOD_H1;
      case PERIOD_M30: return PERIOD_H4;
      case PERIOD_H1:  return PERIOD_H4;
      case PERIOD_H4:  return PERIOD_D1;
      case PERIOD_D1:  return PERIOD_W1;
      default:         return PERIOD_D1;
   }
}

bool HTFAligned(STFUnit &u, int dir)
{
   if(u.hHTFEma==INVALID_HANDLE) return true;
   double ema[1];
   if(CopyBuffer(u.hHTFEma,0,0,1,ema)<=0) return true; // don't block on data hiccup
   double price = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   if(dir>0) return price > ema[0];
   if(dir<0) return price < ema[0];
   return true;
}

double GetATR(STFUnit &u)
{
   double a[1];
   if(CopyBuffer(u.hATR,0,1,1,a)<=0) return 0;
   return a[0];
}

int CountPositions(long magic)   // magic==0 -> count all our magics
{
   int c=0;
   for(int i=PositionsTotal()-1;i>=0;i--)
   {
      ulong t=PositionGetTicket(i);
      if(t==0) continue;
      if(!g_pos.SelectByTicket(t)) continue;
      if(g_pos.Symbol()!=_Symbol) continue;
      long m=g_pos.Magic();
      if(magic==0)
      {
         if(UnitIndexByMagic(m)>=0) c++;
      }
      else if(m==magic) c++;
   }
   return c;
}

bool SessionOK()
{
   if(!InpUseSession) return true;
   MqlDateTime t; TimeToStruct(TimeCurrent(), t);
   int h=t.hour;
   if(InpStartHour<=InpEndHour)
      return h>=InpStartHour && h<InpEndHour;
   // wraps midnight
   return h>=InpStartHour || h<InpEndHour;
}

string TFToStr(ENUM_TIMEFRAMES tf)
{
   string s = EnumToString(tf);
   StringReplace(s, "PERIOD_", "");
   return s;
}

// ── math helpers (mirror indicator) ───────────────────────────────
double EmaStep(double value, double prevEma, int period)
{
   double k = 2.0/(period+1.0);
   return value*k + prevEma*(1.0-k);
}

double PivotHigh(const double &h[], int bar, int len, int total)
{
   if(bar-len<0 || bar+len>=total) return 0;
   double p=h[bar];
   for(int i=bar-len;i<=bar+len;i++){ if(i==bar)continue; if(h[i]>=p) return 0; }
   return p;
}
double PivotLow(const double &l[], int bar, int len, int total)
{
   if(bar-len<0 || bar+len>=total) return 0;
   double p=l[bar];
   for(int i=bar-len;i<=bar+len;i++){ if(i==bar)continue; if(l[i]<=p) return 0; }
   return p;
}
double HighestRange(const double &a[], int start, int count, int total)
{
   double m=-DBL_MAX;
   for(int i=start;i<start+count && i<total;i++){ if(i<0)continue; if(a[i]>m)m=a[i]; }
   return m;
}
double LowestRange(const double &a[], int start, int count, int total)
{
   double m=DBL_MAX;
   for(int i=start;i<start+count && i<total;i++){ if(i<0)continue; if(a[i]<m)m=a[i]; }
   return m;
}
bool VolOK(const long &vol[], int bar, int period, int total, double mult)
{
   if(bar-period+1<0) return false;
   double s=0;
   for(int i=bar-period+1;i<=bar;i++) s+=(double)vol[i];
   double sma=s/period;
   return sma>0 && (double)vol[bar] > sma*mult;
}

void AddZone(SZone &arr[], double top, double bottom, int idx, bool isBull)
{
   int sz=ArraySize(arr);
   ArrayResize(arr, sz+1);
   arr[sz].top=top; arr[sz].bottom=bottom; arr[sz].startIdx=idx; arr[sz].isBull=isBull;
}
void RemoveZone(SZone &arr[], int idx)
{
   int sz=ArraySize(arr);
   for(int i=idx;i<sz-1;i++) arr[i]=arr[i+1];
   ArrayResize(arr, sz-1);
}


// ═══════════════════════════════════════════════════════════════════
// ══════════════════════ DASHBOARD ═════════════════════════════════
// ═══════════════════════════════════════════════════════════════════

void UpdateDashboard()
{
   string d="";
   d += "═══════════════════════════════════════\n";
   d += "   A L P H A X   N E X U S   E A  v3\n";
   d += "   Multi-Timeframe SMC Trading Engine\n";
   d += "═══════════════════════════════════════\n";
   d += StringFormat("Symbol: %s   Spread: %d pts\n",
            _Symbol, (int)SymbolInfoInteger(_Symbol,SYMBOL_SPREAD));
   d += StringFormat("Equity: %.2f %s   Risk/trade: %.2f%%\n",
            AccountInfoDouble(ACCOUNT_EQUITY), AccountInfoString(ACCOUNT_CURRENCY),
            InpRiskPercent);
   d += "───────────────────────────────────────\n";
   d += " TF    MAGIC     TREND   B/S    STATE\n";
   d += "───────────────────────────────────────\n";

   for(int u=0;u<ArraySize(g_units);u++)
   {
      string tr = g_units[u].dashTrend==1?"▲BULL":g_units[u].dashTrend==-1?"▼BEAR":"—RANG";
      int    np = CountPositions(g_units[u].magic);
      string st = np>0 ? StringFormat("POS x%d",np) : g_units[u].dashState;
      d += StringFormat(" %-5s %I64d  %-6s  %d/%d   %s\n",
               TFToStr(g_units[u].tf), g_units[u].magic, tr,
               g_units[u].dashBull, g_units[u].dashBear, st);
   }
   d += "───────────────────────────────────────\n";
   d += StringFormat("Open positions (EA): %d / %d\n",
            CountPositions(0), InpMaxOpenTotal);
   d += "═══════════════════════════════════════";

   Comment(d);
}
//+------------------------------------------------------------------+

//+------------------------------------------------------------------+
//| AlphaX_Nexus.mq5                                                  |
//| AlphaX Nexus - SMC × Order Flow Confluence Engine                 |
//| Converted from Pine Script v6 to MQL5 with improvements           |
//| © AlphaX                                                          |
//+------------------------------------------------------------------+
#property copyright   "AlphaX"
#property link        ""
#property version     "2.00"
#property description "Smart Money Concepts × Order Flow Confluence Engine"
#property description "Converted & improved for MetaTrader 5"
#property indicator_chart_window
#property indicator_buffers 14
#property indicator_plots   10

// ── Plot definitions ────────────────────────────────────────────────
#property indicator_label1  "Fast EMA"
#property indicator_type1   DRAW_LINE
#property indicator_color1  clrYellowGreen
#property indicator_style1  STYLE_DOT
#property indicator_width1  1

#property indicator_label2  "Medium EMA"
#property indicator_type2   DRAW_LINE
#property indicator_color2  clrGray
#property indicator_style2  STYLE_SOLID
#property indicator_width2  1

#property indicator_label3  "Slow EMA"
#property indicator_type3   DRAW_LINE
#property indicator_color3  clrDimGray
#property indicator_style3  STYLE_SOLID
#property indicator_width3  2

#property indicator_label4  "Cloud Fast"
#property indicator_type4   DRAW_LINE
#property indicator_color4  clrYellowGreen
#property indicator_style4  STYLE_SOLID
#property indicator_width4  1

#property indicator_label5  "Cloud Slow"
#property indicator_type5   DRAW_LINE
#property indicator_color5  clrYellowGreen
#property indicator_style5  STYLE_SOLID
#property indicator_width5  1

#property indicator_label6  "Bull Absorption"
#property indicator_type6   DRAW_ARROW
#property indicator_color6  clrLime
#property indicator_width6  1

#property indicator_label7  "Bear Absorption"
#property indicator_type7   DRAW_ARROW
#property indicator_color7  clrRed
#property indicator_width7  1

#property indicator_label8  "Volume Spike"
#property indicator_type8   DRAW_ARROW
#property indicator_color8  clrDodgerBlue
#property indicator_width8  1

#property indicator_label9  "Delta Accum"
#property indicator_type9   DRAW_ARROW
#property indicator_color9  clrLime
#property indicator_width9  1

#property indicator_label10 "Delta Distr"
#property indicator_type10  DRAW_ARROW
#property indicator_color10 clrRed
#property indicator_width10 1

// ═══════════════════════════════════════════════════════════════════
// ══════════════════════ INPUT PARAMETERS ══════════════════════════
// ═══════════════════════════════════════════════════════════════════

// ── Market Structure ──────────────────────────────────────────────
input group "══════ Market Structure ══════"
input int    InpSwingLen        = 7;     // Swing Detection Length
input bool   InpShowBOS         = true;  // Show Break of Structure
input bool   InpShowCHoCH       = true;  // Show Change of Character
input bool   InpShowStructLabel = true;  // Show Structure Labels

// ── Order Blocks ──────────────────────────────────────────────────
input group "══════ Order Blocks ══════"
input bool   InpShowOB          = true;  // Show Order Blocks
input int    InpOBMaxBoxes      = 4;     // Max Active Order Blocks
input bool   InpOBWickMitigate  = true;  // Wick Mitigation (false=Close)
input bool   InpOBVolumeFilter  = true;  // Require Volume Confirmation
input double InpOBVolMultiplier = 1.4;   // OB Volume Multiplier
input int    InpOBMaxAge        = 80;    // OB Max Age (bars)

// ── Fair Value Gaps ───────────────────────────────────────────────
input group "══════ Fair Value Gaps ══════"
input bool   InpShowFVG         = true;  // Show Fair Value Gaps
input int    InpFVGMaxBoxes     = 4;     // Max Active FVGs
input double InpFVGMinSize      = 15.0;  // Min FVG Size (% of ATR)
input int    InpFVGMaxAge       = 60;    // FVG Max Age (bars)

// ── Liquidity ─────────────────────────────────────────────────────
input group "══════ Liquidity ══════"
input bool   InpShowLiqSweep    = true;  // Show Liquidity Sweeps
input int    InpLiqLookback     = 25;    // Liquidity Lookback
input bool   InpShowEqHL        = true;  // Show Equal Highs/Lows
input double InpEqThreshold     = 0.08;  // Equal Level Threshold (%)

// ── Order Flow ────────────────────────────────────────────────────
input group "══════ Order Flow ══════"
input bool   InpShowVolProfile  = true;  // Show Volume Analysis
input int    InpVolSmaLen       = 20;    // Volume SMA Length
input double InpVolSpikeMulti   = 1.8;   // Volume Spike Multiplier
input bool   InpShowAbsorption  = true;  // Show Absorption Detection
input double InpAbsorbRatio     = 2.0;   // Absorption Wick/Body Ratio
input bool   InpShowDelta       = true;  // Show Delta Divergence
input int    InpDeltaLen        = 4;     // Delta Smooth Length

// ── Confluence Engine ─────────────────────────────────────────────
input group "══════ Confluence Engine ══════"
input int    InpMinConfluence   = 3;     // Min Confluence Score
input bool   InpShowSignals     = true;  // Show Entry Signals
input int    InpSignalCooldown  = 12;    // Signal Cooldown (bars)
input double InpSignalOffset    = 3.4;   // Signal Label Offset (x ATR)

// ── EMA Settings ──────────────────────────────────────────────────
input group "══════ EMA Settings ══════"
input bool   InpShowEmaFast     = true;  // Show Fast EMA
input bool   InpShowEmaMedium   = true;  // Show Medium EMA
input bool   InpShowEmaSlow     = true;  // Show Slow EMA
input int    InpEmaFastLen      = 21;    // Fast EMA Length
input int    InpEmaMediumLen    = 50;    // Medium EMA Length
input int    InpEmaSlowLen      = 200;   // Slow EMA Length

// ── Trend Cloud ───────────────────────────────────────────────────
input group "══════ Trend Cloud ══════"
input bool   InpShowCloud       = true;  // Show Trend Cloud
input int    InpCloudFastLen    = 9;     // Cloud Fast Length
input int    InpCloudSlowLen    = 26;    // Cloud Slow Length

// ── Display ───────────────────────────────────────────────────────
input group "══════ Display ══════"
input bool   InpShowDash        = true;  // Show Dashboard
input ENUM_BASE_CORNER InpDashCorner = CORNER_RIGHT_UPPER; // Dashboard Corner
input bool   InpAlertPush       = true;  // Push Notifications
input bool   InpAlertPopup      = true;  // Popup Alerts

// ── Colors ────────────────────────────────────────────────────────
input group "══════ Theme Colors ══════"
input color  InpBullPrimary     = C'200,230,36';   // Bull Primary
input color  InpBullBright      = C'212,240,58';   // Bull Bright
input color  InpBullDim         = C'154,184,28';   // Bull Dim
input color  InpBearPrimary     = C'255,23,68';    // Bear Primary
input color  InpBearBright      = C'255,82,82';    // Bear Bright
input color  InpBearDim         = C'213,0,50';     // Bear Dim
input color  InpOBBullColor     = C'200,230,36';   // Bullish OB
input color  InpOBBearColor     = C'255,23,68';    // Bearish OB
input color  InpFVGBullColor    = C'200,230,36';   // Bullish FVG
input color  InpFVGBearColor    = C'255,23,68';    // Bearish FVG
input color  InpLiqColor        = clrGray;         // Liquidity Lines

// ── MQL5 Improvement: Multi-Timeframe Confirmation ────────────────
input group "══════ MTF Confirmation (MQL5 Enhancement) ══════"
input bool            InpUseMTF       = false;               // Enable MTF Filter
input ENUM_TIMEFRAMES InpHTFPeriod    = PERIOD_H4;           // Higher Timeframe
input int             InpHTFEmaLen    = 50;                  // HTF EMA Length

// ── MQL5 Improvement: Auto SL/TP from Zones ──────────────────────
input group "══════ SL/TP Levels (MQL5 Enhancement) ══════"
input bool   InpShowSLTP        = true;  // Show SL/TP Levels on Signals
input double InpRiskReward      = 2.0;   // Risk:Reward Ratio
input double InpSLPaddingATR    = 0.3;   // SL Padding (x ATR)


// ═══════════════════════════════════════════════════════════════════
// ══════════════════════ DATA STRUCTURES ═══════════════════════════
// ═══════════════════════════════════════════════════════════════════

struct SOrderBlock
{
   double   top;
   double   bottom;
   int      startBar;    // bar index when OB was created
   datetime startTime;
   bool     isBull;
   bool     active;
   string   objName;     // rectangle object name
};

struct SFairValueGap
{
   double   top;
   double   bottom;
   int      startBar;
   datetime startTime;
   bool     isBull;
   bool     active;
   string   objName;
};

// ═══════════════════════════════════════════════════════════════════
// ══════════════════════ GLOBAL VARIABLES ══════════════════════════
// ═══════════════════════════════════════════════════════════════════

// ── Indicator Buffers ─────────────────────────────────────────────
double g_bufEmaFast[];
double g_bufEmaMedium[];
double g_bufEmaSlow[];
double g_bufCloudFast[];
double g_bufCloudSlow[];
double g_bufBullAbsorb[];
double g_bufBearAbsorb[];
double g_bufVolSpike[];
double g_bufDeltaAccum[];
double g_bufDeltaDistr[];
// Internal calculation buffers (no plot)
double g_bufATR[];
double g_bufVolSma[];
double g_bufSmoothDelta[];
double g_bufRawDelta[];

// ── EMA handles ───────────────────────────────────────────────────
int g_hEmaFast, g_hEmaMedium, g_hEmaSlow, g_hATR;
int g_hHTFEma;  // for MTF

// ── Swing tracking ────────────────────────────────────────────────
double g_lastSwingHigh, g_lastSwingLow;
int    g_lastSwingHighBar, g_lastSwingLowBar;
double g_prevSwingHigh, g_prevSwingLow;
int    g_prevSwingHighBar, g_prevSwingLowBar;

// ── Structure ─────────────────────────────────────────────────────
int g_structureTrend;  // 1=bull, -1=bear, 0=ranging

// ── Order Blocks & FVGs ───────────────────────────────────────────
SOrderBlock   g_obArray[];
SFairValueGap g_fvgArray[];

// ── Signal cooldown ───────────────────────────────────────────────
int g_lastSignalBar;

// ── Equal H/L lines ──────────────────────────────────────────────
string g_eqHighLineName, g_eqLowLineName;

// ── Dashboard label names ─────────────────────────────────────────
string g_dashName;

// ── Object counter for unique names ──────────────────────────────
int g_objCounter;

// ── Prev bars for incremental calc ───────────────────────────────
int g_prevCalculated;


// ═══════════════════════════════════════════════════════════════════
// ══════════════════════ HELPER FUNCTIONS ══════════════════════════
// ═══════════════════════════════════════════════════════════════════

string UniqueObjName(string prefix)
{
   g_objCounter++;
   return prefix + "_" + IntegerToString(g_objCounter) + "_" + IntegerToString(GetTickCount());
}

color ColorWithAlpha(color clr, uchar alpha)
{
   return (color)((uint)clr | ((uint)alpha << 24));
}

//+------------------------------------------------------------------+
//| Pivot High Detection (confirmed swingLen bars later)              |
//+------------------------------------------------------------------+
double PivotHigh(const double &high[], int bar, int len, int totalBars)
{
   if(bar - len < 0 || bar + len >= totalBars)
      return 0;
   
   double pivot = high[bar];
   for(int i = bar - len; i <= bar + len; i++)
   {
      if(i == bar) continue;
      if(high[i] >= pivot)
         return 0;
   }
   return pivot;
}

//+------------------------------------------------------------------+
//| Pivot Low Detection                                               |
//+------------------------------------------------------------------+
double PivotLow(const double &low[], int bar, int len, int totalBars)
{
   if(bar - len < 0 || bar + len >= totalBars)
      return 0;
   
   double pivot = low[bar];
   for(int i = bar - len; i <= bar + len; i++)
   {
      if(i == bar) continue;
      if(low[i] <= pivot)
         return 0;
   }
   return pivot;
}

//+------------------------------------------------------------------+
//| Highest value in range                                            |
//+------------------------------------------------------------------+
double HighestInRange(const double &arr[], int startBar, int count, int totalBars)
{
   double maxVal = -DBL_MAX;
   for(int i = startBar; i < startBar + count && i < totalBars; i++)
   {
      if(i < 0) continue;
      if(arr[i] > maxVal) maxVal = arr[i];
   }
   return maxVal;
}

//+------------------------------------------------------------------+
//| Lowest value in range                                             |
//+------------------------------------------------------------------+
double LowestInRange(const double &arr[], int startBar, int count, int totalBars)
{
   double minVal = DBL_MAX;
   for(int i = startBar; i < startBar + count && i < totalBars; i++)
   {
      if(i < 0) continue;
      if(arr[i] < minVal) minVal = arr[i];
   }
   return minVal;
}

//+------------------------------------------------------------------+
//| Simple Moving Average of volume                                   |
//+------------------------------------------------------------------+
double VolumeSMA(const long &vol[], int bar, int period, int totalBars)
{
   if(bar - period + 1 < 0) return 0;
   double sum = 0;
   for(int i = bar - period + 1; i <= bar; i++)
      sum += (double)vol[i];
   return sum / period;
}

//+------------------------------------------------------------------+
//| EMA calculation inline (for delta smoothing)                      |
//+------------------------------------------------------------------+
double EmaStep(double value, double prevEma, int period)
{
   double k = 2.0 / (period + 1.0);
   return value * k + prevEma * (1.0 - k);
}

//+------------------------------------------------------------------+
//| Grade from confidence                                             |
//+------------------------------------------------------------------+
string GetGrade(double conf)
{
   if(conf >= 75) return "A+";
   if(conf >= 60) return "A";
   if(conf >= 45) return "B";
   if(conf >= 30) return "C";
   return "D";
}

color GetGradeColor(double conf, bool isBull)
{
   if(conf >= 60)
      return isBull ? InpBullBright : InpBearBright;
   if(conf >= 45)
      return isBull ? InpBullPrimary : InpBearPrimary;
   if(conf >= 30)
      return isBull ? InpBullDim : InpBearDim;
   return clrGray;
}

//+------------------------------------------------------------------+
//| Delete OB rectangle                                               |
//+------------------------------------------------------------------+
void DeleteOBObject(int idx)
{
   if(idx >= 0 && idx < ArraySize(g_obArray))
   {
      ObjectDelete(0, g_obArray[idx].objName);
   }
}

void DeleteFVGObject(int idx)
{
   if(idx >= 0 && idx < ArraySize(g_fvgArray))
   {
      ObjectDelete(0, g_fvgArray[idx].objName);
   }
}

//+------------------------------------------------------------------+
//| Remove OB from array                                              |
//+------------------------------------------------------------------+
void RemoveOB(int idx)
{
   DeleteOBObject(idx);
   int size = ArraySize(g_obArray);
   for(int i = idx; i < size - 1; i++)
      g_obArray[i] = g_obArray[i + 1];
   ArrayResize(g_obArray, size - 1);
}

void RemoveFVG(int idx)
{
   DeleteFVGObject(idx);
   int size = ArraySize(g_fvgArray);
   for(int i = idx; i < size - 1; i++)
      g_fvgArray[i] = g_fvgArray[i + 1];
   ArrayResize(g_fvgArray, size - 1);
}


// ═══════════════════════════════════════════════════════════════════
// ══════════════════════ INITIALIZATION ════════════════════════════
// ═══════════════════════════════════════════════════════════════════

int OnInit()
{
   // ── Set buffers ────────────────────────────────────────────────
   SetIndexBuffer(0,  g_bufEmaFast,     INDICATOR_DATA);
   SetIndexBuffer(1,  g_bufEmaMedium,   INDICATOR_DATA);
   SetIndexBuffer(2,  g_bufEmaSlow,     INDICATOR_DATA);
   SetIndexBuffer(3,  g_bufCloudFast,   INDICATOR_DATA);
   SetIndexBuffer(4,  g_bufCloudSlow,   INDICATOR_DATA);
   SetIndexBuffer(5,  g_bufBullAbsorb,  INDICATOR_DATA);
   SetIndexBuffer(6,  g_bufBearAbsorb,  INDICATOR_DATA);
   SetIndexBuffer(7,  g_bufVolSpike,    INDICATOR_DATA);
   SetIndexBuffer(8,  g_bufDeltaAccum,  INDICATOR_DATA);
   SetIndexBuffer(9,  g_bufDeltaDistr,  INDICATOR_DATA);
   SetIndexBuffer(10, g_bufATR,         INDICATOR_CALCULATIONS);
   SetIndexBuffer(11, g_bufVolSma,      INDICATOR_CALCULATIONS);
   SetIndexBuffer(12, g_bufSmoothDelta, INDICATOR_CALCULATIONS);
   SetIndexBuffer(13, g_bufRawDelta,    INDICATOR_CALCULATIONS);

   // Arrow codes
   PlotIndexSetInteger(5, PLOT_ARROW, 119);  // diamond - bull absorb
   PlotIndexSetInteger(6, PLOT_ARROW, 119);  // diamond - bear absorb
   PlotIndexSetInteger(7, PLOT_ARROW, 159);  // circle  - vol spike
   PlotIndexSetInteger(8, PLOT_ARROW, 233);  // up arrow - delta accum
   PlotIndexSetInteger(9, PLOT_ARROW, 234);  // dn arrow - delta distr

   // Colors for arrows
   PlotIndexSetInteger(5, PLOT_LINE_COLOR, InpBullDim);
   PlotIndexSetInteger(6, PLOT_LINE_COLOR, InpBearDim);
   PlotIndexSetInteger(7, PLOT_LINE_COLOR, clrDodgerBlue);
   PlotIndexSetInteger(8, PLOT_LINE_COLOR, InpBullBright);
   PlotIndexSetInteger(9, PLOT_LINE_COLOR, InpBearBright);

   // ── EMA visibility ────────────────────────────────────────────
   PlotIndexSetInteger(0, PLOT_DRAW_TYPE, InpShowEmaFast   ? DRAW_LINE : DRAW_NONE);
   PlotIndexSetInteger(1, PLOT_DRAW_TYPE, InpShowEmaMedium ? DRAW_LINE : DRAW_NONE);
   PlotIndexSetInteger(2, PLOT_DRAW_TYPE, InpShowEmaSlow   ? DRAW_LINE : DRAW_NONE);
   PlotIndexSetInteger(3, PLOT_DRAW_TYPE, InpShowCloud     ? DRAW_LINE : DRAW_NONE);
   PlotIndexSetInteger(4, PLOT_DRAW_TYPE, InpShowCloud     ? DRAW_LINE : DRAW_NONE);

   // ── Create EMA handles ────────────────────────────────────────
   g_hEmaFast   = iMA(_Symbol, PERIOD_CURRENT, InpEmaFastLen,   0, MODE_EMA, PRICE_CLOSE);
   g_hEmaMedium = iMA(_Symbol, PERIOD_CURRENT, InpEmaMediumLen, 0, MODE_EMA, PRICE_CLOSE);
   g_hEmaSlow   = iMA(_Symbol, PERIOD_CURRENT, InpEmaSlowLen,   0, MODE_EMA, PRICE_CLOSE);
   g_hATR       = iATR(_Symbol, PERIOD_CURRENT, 14);

   if(g_hEmaFast == INVALID_HANDLE || g_hEmaMedium == INVALID_HANDLE ||
      g_hEmaSlow == INVALID_HANDLE || g_hATR == INVALID_HANDLE)
   {
      Print("Error creating indicator handles");
      return INIT_FAILED;
   }

   // MTF EMA handle
   if(InpUseMTF)
   {
      g_hHTFEma = iMA(_Symbol, InpHTFPeriod, InpHTFEmaLen, 0, MODE_EMA, PRICE_CLOSE);
      if(g_hHTFEma == INVALID_HANDLE)
         Print("Warning: HTF EMA handle failed");
   }

   // ── Initialize state ──────────────────────────────────────────
   g_structureTrend  = 0;
   g_lastSwingHigh   = 0;
   g_lastSwingLow    = 0;
   g_lastSwingHighBar = 0;
   g_lastSwingLowBar  = 0;
   g_prevSwingHigh   = 0;
   g_prevSwingLow    = 0;
   g_prevSwingHighBar = 0;
   g_prevSwingLowBar  = 0;
   g_lastSignalBar   = 0;
   g_objCounter      = 0;
   g_prevCalculated  = 0;

   ArrayResize(g_obArray, 0);
   ArrayResize(g_fvgArray, 0);

   g_eqHighLineName = "AlphaX_EqHigh";
   g_eqLowLineName  = "AlphaX_EqLow";
   g_dashName       = "AlphaX_Dashboard";

   IndicatorSetString(INDICATOR_SHORTNAME, "AlphaX Nexus v2");
   IndicatorSetInteger(INDICATOR_DIGITS, _Digits);

   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   // Clean up all objects
   ObjectsDeleteAll(0, "AlphaX_");
   Comment("");
}


// ═══════════════════════════════════════════════════════════════════
// ══════════════════════ MAIN CALCULATION ══════════════════════════
// ═══════════════════════════════════════════════════════════════════

int OnCalculate(const int rates_total,
                const int prev_calculated,
                const datetime &time[],
                const double &open[],
                const double &high[],
                const double &low[],
                const double &close[],
                const long &tick_volume[],
                const long &volume[],
                const int &spread[])
{
   if(rates_total < InpEmaSlowLen + 50) return 0;

   // ── Copy EMA & ATR data ───────────────────────────────────────
   if(CopyBuffer(g_hEmaFast,   0, 0, rates_total, g_bufEmaFast)   <= 0) return 0;
   if(CopyBuffer(g_hEmaMedium, 0, 0, rates_total, g_bufEmaMedium) <= 0) return 0;
   if(CopyBuffer(g_hEmaSlow,   0, 0, rates_total, g_bufEmaSlow)   <= 0) return 0;
   if(CopyBuffer(g_hATR,       0, 0, rates_total, g_bufATR)       <= 0) return 0;

   // ── Determine start bar ───────────────────────────────────────
   int startBar = prev_calculated > 0 ? prev_calculated - 1 : InpEmaSlowLen + 50;
   
   // If recalculating from scratch, reset state
   if(prev_calculated == 0)
   {
      g_structureTrend = 0;
      g_lastSwingHigh = 0; g_lastSwingLow = 0;
      g_prevSwingHigh = 0; g_prevSwingLow = 0;
      g_lastSignalBar = 0;
      
      // Clear old objects
      ObjectsDeleteAll(0, "AlphaX_");
      ArrayResize(g_obArray, 0);
      ArrayResize(g_fvgArray, 0);
   }

   // ── Use tick_volume if real volume unavailable ─────────────────
   // MQL5 improvement: prefer real volume, fallback to tick volume
   bool useRealVol = false;
   if(volume[rates_total - 1] > 0)
      useRealVol = true;

   // ═══════════════════════════════════════════════════════════════
   // ══════════════════ BAR-BY-BAR PROCESSING ═════════════════════
   // ═══════════════════════════════════════════════════════════════

   for(int i = startBar; i < rates_total; i++)
   {
      // Init arrow buffers to EMPTY
      g_bufBullAbsorb[i] = EMPTY_VALUE;
      g_bufBearAbsorb[i] = EMPTY_VALUE;
      g_bufVolSpike[i]   = EMPTY_VALUE;
      g_bufDeltaAccum[i] = EMPTY_VALUE;
      g_bufDeltaDistr[i] = EMPTY_VALUE;

      double atrVal = g_bufATR[i];
      if(atrVal <= 0) continue;

      // ── Volume SMA ─────────────────────────────────────────────
      long vol = useRealVol ? volume[i] : tick_volume[i];
      double volSma = 0;
      if(i >= InpVolSmaLen)
      {
         double volSum = 0;
         for(int v = i - InpVolSmaLen + 1; v <= i; v++)
            volSum += (double)(useRealVol ? volume[v] : tick_volume[v]);
         volSma = volSum / InpVolSmaLen;
      }
      g_bufVolSma[i] = volSma;

      double relVol = volSma > 0 ? (double)vol / volSma : 1.0;
      bool volSpike    = (double)vol > volSma * InpVolSpikeMulti;
      bool volAboveAvg = (double)vol > volSma;

      // ── Cloud ──────────────────────────────────────────────────
      if(InpShowCloud && i >= InpCloudSlowLen)
      {
         g_bufCloudFast[i] = (HighestInRange(high, i - InpCloudFastLen + 1, InpCloudFastLen, rates_total) +
                              LowestInRange(low,   i - InpCloudFastLen + 1, InpCloudFastLen, rates_total)) / 2.0;
         g_bufCloudSlow[i] = (HighestInRange(high, i - InpCloudSlowLen + 1, InpCloudSlowLen, rates_total) +
                              LowestInRange(low,   i - InpCloudSlowLen + 1, InpCloudSlowLen, rates_total)) / 2.0;
      }
      else
      {
         g_bufCloudFast[i] = EMPTY_VALUE;
         g_bufCloudSlow[i] = EMPTY_VALUE;
      }

      // ── Delta Estimation ───────────────────────────────────────
      double candleRange = high[i] - low[i];
      double bodySize    = MathAbs(close[i] - open[i]);
      double upperWick   = high[i] - MathMax(close[i], open[i]);
      double lowerWick   = MathMin(close[i], open[i]) - low[i];

      double buyVolEst  = candleRange > 0 ? (double)vol * ((close[i] - low[i]) / candleRange) : (double)vol * 0.5;
      double rawDelta   = buyVolEst - ((double)vol - buyVolEst);
      g_bufRawDelta[i] = rawDelta;

      if(i > 0 && g_bufSmoothDelta[i - 1] != EMPTY_VALUE)
         g_bufSmoothDelta[i] = EmaStep(rawDelta, g_bufSmoothDelta[i - 1], InpDeltaLen);
      else
         g_bufSmoothDelta[i] = rawDelta;

      double smoothDelta = g_bufSmoothDelta[i];

      // ── Delta Divergence ───────────────────────────────────────
      bool deltaRising  = (i >= 2) && smoothDelta > g_bufSmoothDelta[i - 1] && g_bufSmoothDelta[i - 1] > g_bufSmoothDelta[i - 2];
      bool deltaFalling = (i >= 2) && smoothDelta < g_bufSmoothDelta[i - 1] && g_bufSmoothDelta[i - 1] < g_bufSmoothDelta[i - 2];

      bool priceNewHigh = (i >= 10) && high[i] == HighestInRange(high, i - 9, 10, rates_total);
      bool priceNewLow  = (i >= 10) && low[i]  == LowestInRange(low,  i - 9, 10, rates_total);

      bool deltaBearDiv = priceNewHigh && deltaFalling && InpShowDelta;
      bool deltaBullDiv = priceNewLow  && deltaRising  && InpShowDelta;

      if(deltaBullDiv) g_bufDeltaAccum[i] = low[i];
      if(deltaBearDiv) g_bufDeltaDistr[i] = high[i];

      // ── Absorption Detection ───────────────────────────────────
      bool bullAbsorption = InpShowAbsorption &&
         lowerWick > bodySize * InpAbsorbRatio &&
         volAboveAvg && close[i] > open[i] &&
         lowerWick > upperWick * 1.5;

      bool bearAbsorption = InpShowAbsorption &&
         upperWick > bodySize * InpAbsorbRatio &&
         volAboveAvg && close[i] < open[i] &&
         upperWick > lowerWick * 1.5;

      if(bullAbsorption && InpShowAbsorption) g_bufBullAbsorb[i] = low[i];
      if(bearAbsorption && InpShowAbsorption) g_bufBearAbsorb[i] = high[i];

      // ── Volume Spike ───────────────────────────────────────────
      if(volSpike && InpShowVolProfile) g_bufVolSpike[i] = low[i] - atrVal * 0.5;

      // ── Swing Detection ────────────────────────────────────────
      int pivotBar = i - InpSwingLen;
      if(pivotBar >= InpSwingLen)
      {
         double sh = PivotHigh(high, pivotBar, InpSwingLen, rates_total);
         if(sh > 0)
         {
            g_prevSwingHigh    = g_lastSwingHigh;
            g_prevSwingHighBar = g_lastSwingHighBar;
            g_lastSwingHigh    = sh;
            g_lastSwingHighBar = pivotBar;
         }

         double sl = PivotLow(low, pivotBar, InpSwingLen, rates_total);
         if(sl > 0)
         {
            g_prevSwingLow    = g_lastSwingLow;
            g_prevSwingLowBar = g_lastSwingLowBar;
            g_lastSwingLow    = sl;
            g_lastSwingLowBar = pivotBar;
         }
      }

      // ═══════════════════════════════════════════════════════════
      // ══════════════ MARKET STRUCTURE (BOS / CHoCH) ═════════════
      // ═══════════════════════════════════════════════════════════

      bool bosUp = false, bosDown = false;
      bool chochUp = false, chochDown = false;

      if(g_lastSwingHigh > 0 && close[i] > g_lastSwingHigh && (i > 0 && close[i - 1] <= g_lastSwingHigh))
      {
         if(g_structureTrend >= 0)
         { bosUp = true; g_structureTrend = 1; }
         else
         { chochUp = true; g_structureTrend = 1; }
      }

      if(g_lastSwingLow > 0 && close[i] < g_lastSwingLow && (i > 0 && close[i - 1] >= g_lastSwingLow))
      {
         if(g_structureTrend <= 0)
         { bosDown = true; g_structureTrend = -1; }
         else
         { chochDown = true; g_structureTrend = -1; }
      }

      // ── Structure Labels ───────────────────────────────────────
      if(InpShowStructLabel)
      {
         if(InpShowBOS && bosUp)
            CreateLabel("AlphaX_BOS_" + IntegerToString(i), time[i], low[i],
                        "BOS ▲", InpBullPrimary, ANCHOR_UPPER, atrVal);

         if(InpShowBOS && bosDown)
            CreateLabel("AlphaX_BOS_" + IntegerToString(i), time[i], high[i],
                        "BOS ▼", InpBearPrimary, ANCHOR_LOWER, -atrVal);

         if(InpShowCHoCH && chochUp)
            CreateLabel("AlphaX_CHoCH_" + IntegerToString(i), time[i], low[i],
                        "CHoCH ▲", InpBullBright, ANCHOR_UPPER, atrVal);

         if(InpShowCHoCH && chochDown)
            CreateLabel("AlphaX_CHoCH_" + IntegerToString(i), time[i], high[i],
                        "CHoCH ▼", InpBearBright, ANCHOR_LOWER, -atrVal);
      }

      // ═══════════════════════════════════════════════════════════
      // ══════════════════ ORDER BLOCKS ═══════════════════════════
      // ═══════════════════════════════════════════════════════════

      if(InpShowOB && (bosUp || chochUp))
      {
         // Find last bearish candle (bullish OB)
         for(int k = 1; k <= 15 && (i - k) >= 0; k++)
         {
            if(close[i - k] < open[i - k])
            {
               bool volOK = !InpOBVolumeFilter ||
                  (double)(useRealVol ? volume[i - k] : tick_volume[i - k]) >
                  g_bufVolSma[i - k] * InpOBVolMultiplier;

               if(volOK)
               {
                  // Limit OBs
                  while(ArraySize(g_obArray) >= InpOBMaxBoxes)
                     RemoveOB(0);

                  int sz = ArraySize(g_obArray);
                  ArrayResize(g_obArray, sz + 1);

                  g_obArray[sz].top       = high[i - k];
                  g_obArray[sz].bottom    = low[i - k];
                  g_obArray[sz].startBar  = i - k;
                  g_obArray[sz].startTime = time[i - k];
                  g_obArray[sz].isBull    = true;
                  g_obArray[sz].active    = true;
                  g_obArray[sz].objName   = UniqueObjName("AlphaX_OB");

                  CreateRectangle(g_obArray[sz].objName, time[i - k],
                     g_obArray[sz].top, g_obArray[sz].bottom,
                     InpOBBullColor, true);
               }
               break;
            }
         }
      }

      if(InpShowOB && (bosDown || chochDown))
      {
         for(int k = 1; k <= 15 && (i - k) >= 0; k++)
         {
            if(close[i - k] > open[i - k])
            {
               bool volOK = !InpOBVolumeFilter ||
                  (double)(useRealVol ? volume[i - k] : tick_volume[i - k]) >
                  g_bufVolSma[i - k] * InpOBVolMultiplier;

               if(volOK)
               {
                  while(ArraySize(g_obArray) >= InpOBMaxBoxes)
                     RemoveOB(0);

                  int sz = ArraySize(g_obArray);
                  ArrayResize(g_obArray, sz + 1);

                  g_obArray[sz].top       = high[i - k];
                  g_obArray[sz].bottom    = low[i - k];
                  g_obArray[sz].startBar  = i - k;
                  g_obArray[sz].startTime = time[i - k];
                  g_obArray[sz].isBull    = false;
                  g_obArray[sz].active    = true;
                  g_obArray[sz].objName   = UniqueObjName("AlphaX_OB");

                  CreateRectangle(g_obArray[sz].objName, time[i - k],
                     g_obArray[sz].top, g_obArray[sz].bottom,
                     InpOBBearColor, false);
               }
               break;
            }
         }
      }

      // ── OB Mitigation & Age ────────────────────────────────────
      bool priceInBullOB = false, priceInBearOB = false;

      for(int j = ArraySize(g_obArray) - 1; j >= 0; j--)
      {
         if(!g_obArray[j].active) continue;

         // Age check
         if(i - g_obArray[j].startBar > InpOBMaxAge)
         { RemoveOB(j); continue; }

         bool mitigated = false;
         if(g_obArray[j].isBull)
         {
            mitigated = InpOBWickMitigate ? (low[i] < g_obArray[j].bottom) : (close[i] < g_obArray[j].bottom);
            if(!mitigated && low[i] <= g_obArray[j].top && high[i] >= g_obArray[j].bottom)
               priceInBullOB = true;
         }
         else
         {
            mitigated = InpOBWickMitigate ? (high[i] > g_obArray[j].top) : (close[i] > g_obArray[j].top);
            if(!mitigated && high[i] >= g_obArray[j].bottom && low[i] <= g_obArray[j].top)
               priceInBearOB = true;
         }

         if(mitigated)
         { RemoveOB(j); continue; }

         // Extend rectangle to current bar
         ObjectSetInteger(0, g_obArray[j].objName, OBJPROP_TIME, 1, time[i]);
      }

      // ═══════════════════════════════════════════════════════════
      // ══════════════════ FAIR VALUE GAPS ═════════════════════════
      // ═══════════════════════════════════════════════════════════

      if(InpShowFVG && i >= 2)
      {
         double fvgMinATR = atrVal * InpFVGMinSize / 100.0;

         // Bullish FVG: low[i] > high[i-2]
         double bullFvgTop    = low[i];
         double bullFvgBottom = high[i - 2];
         bool bullFvgExists   = bullFvgBottom < bullFvgTop &&
            close[i - 1] > open[i - 1] &&
            (bullFvgTop - bullFvgBottom) > fvgMinATR;

         // Bearish FVG: low[i-2] > high[i]
         double bearFvgTop    = low[i - 2];
         double bearFvgBottom = high[i];
         bool bearFvgExists   = bearFvgTop > bearFvgBottom &&
            close[i - 1] < open[i - 1] &&
            (bearFvgTop - bearFvgBottom) > fvgMinATR;

         if(bullFvgExists)
         {
            while(ArraySize(g_fvgArray) >= InpFVGMaxBoxes)
               RemoveFVG(0);

            int sz = ArraySize(g_fvgArray);
            ArrayResize(g_fvgArray, sz + 1);

            g_fvgArray[sz].top       = bullFvgTop;
            g_fvgArray[sz].bottom    = bullFvgBottom;
            g_fvgArray[sz].startBar  = i - 1;
            g_fvgArray[sz].startTime = time[i - 1];
            g_fvgArray[sz].isBull    = true;
            g_fvgArray[sz].active    = true;
            g_fvgArray[sz].objName   = UniqueObjName("AlphaX_FVG");

            CreateRectangle(g_fvgArray[sz].objName, time[i - 1],
               bullFvgTop, bullFvgBottom, InpFVGBullColor, true, true);
         }

         if(bearFvgExists)
         {
            while(ArraySize(g_fvgArray) >= InpFVGMaxBoxes)
               RemoveFVG(0);

            int sz = ArraySize(g_fvgArray);
            ArrayResize(g_fvgArray, sz + 1);

            g_fvgArray[sz].top       = bearFvgTop;
            g_fvgArray[sz].bottom    = bearFvgBottom;
            g_fvgArray[sz].startBar  = i - 1;
            g_fvgArray[sz].startTime = time[i - 1];
            g_fvgArray[sz].isBull    = false;
            g_fvgArray[sz].active    = true;
            g_fvgArray[sz].objName   = UniqueObjName("AlphaX_FVG");

            CreateRectangle(g_fvgArray[sz].objName, time[i - 1],
               bearFvgTop, bearFvgBottom, InpFVGBearColor, false, true);
         }
      }

      // ── FVG Fill & Age ─────────────────────────────────────────
      bool priceInBullFVG = false, priceInBearFVG = false;

      for(int j = ArraySize(g_fvgArray) - 1; j >= 0; j--)
      {
         if(!g_fvgArray[j].active) continue;

         if(i - g_fvgArray[j].startBar > InpFVGMaxAge)
         { RemoveFVG(j); continue; }

         bool filled = false;
         if(g_fvgArray[j].isBull)
         {
            filled = low[i] <= g_fvgArray[j].bottom;
            if(!filled && low[i] <= g_fvgArray[j].top && high[i] >= g_fvgArray[j].bottom)
               priceInBullFVG = true;
         }
         else
         {
            filled = high[i] >= g_fvgArray[j].top;
            if(!filled && high[i] >= g_fvgArray[j].bottom && low[i] <= g_fvgArray[j].top)
               priceInBearFVG = true;
         }

         if(filled)
         { RemoveFVG(j); continue; }

         ObjectSetInteger(0, g_fvgArray[j].objName, OBJPROP_TIME, 1, time[i]);
      }

      // ═══════════════════════════════════════════════════════════
      // ══════════════ LIQUIDITY SWEEP DETECTION ══════════════════
      // ═══════════════════════════════════════════════════════════

      bool bullLiqSweep = false, bearLiqSweep = false;

      if(InpShowLiqSweep && i >= InpLiqLookback + 1)
      {
         double recentHighVal = HighestInRange(high, i - InpLiqLookback, InpLiqLookback, rates_total);
         double recentLowVal  = LowestInRange(low,   i - InpLiqLookback, InpLiqLookback, rates_total);
         double prevRecentHigh = HighestInRange(high, i - InpLiqLookback - 1, InpLiqLookback, rates_total);
         double prevRecentLow  = LowestInRange(low,   i - InpLiqLookback - 1, InpLiqLookback, rates_total);

         bullLiqSweep = low[i] < prevRecentLow && close[i] > prevRecentLow && close[i] > open[i];
         bearLiqSweep = high[i] > prevRecentHigh && close[i] < prevRecentHigh && close[i] < open[i];

         if(bullLiqSweep)
            CreateLabel("AlphaX_LIQ_" + IntegerToString(i), time[i], low[i],
                        "$ SWEEP", InpBullPrimary, ANCHOR_UPPER, atrVal * 0.8);

         if(bearLiqSweep)
            CreateLabel("AlphaX_LIQ_" + IntegerToString(i), time[i], high[i],
                        "$ SWEEP", InpBearPrimary, ANCHOR_LOWER, -atrVal * 0.8);
      }

      // ── Equal Highs / Lows ─────────────────────────────────────
      if(InpShowEqHL && g_lastSwingHigh > 0 && g_prevSwingHigh > 0)
      {
         double pctDiff = MathAbs(g_lastSwingHigh - g_prevSwingHigh) / g_prevSwingHigh * 100;
         if(pctDiff < InpEqThreshold && g_lastSwingHighBar != g_prevSwingHighBar)
         {
            double eqLevel = (g_lastSwingHigh + g_prevSwingHigh) / 2.0;
            ObjectDelete(0, g_eqHighLineName);
            ObjectCreate(0, g_eqHighLineName, OBJ_TREND, 0,
               time[g_prevSwingHighBar], eqLevel, time[i], eqLevel);
            ObjectSetInteger(0, g_eqHighLineName, OBJPROP_COLOR, InpLiqColor);
            ObjectSetInteger(0, g_eqHighLineName, OBJPROP_STYLE, STYLE_DASH);
            ObjectSetInteger(0, g_eqHighLineName, OBJPROP_WIDTH, 1);
            ObjectSetInteger(0, g_eqHighLineName, OBJPROP_RAY_RIGHT, true);
         }
      }

      if(InpShowEqHL && g_lastSwingLow > 0 && g_prevSwingLow > 0)
      {
         double pctDiff = MathAbs(g_lastSwingLow - g_prevSwingLow) / g_prevSwingLow * 100;
         if(pctDiff < InpEqThreshold && g_lastSwingLowBar != g_prevSwingLowBar)
         {
            double eqLevel = (g_lastSwingLow + g_prevSwingLow) / 2.0;
            ObjectDelete(0, g_eqLowLineName);
            ObjectCreate(0, g_eqLowLineName, OBJ_TREND, 0,
               time[g_prevSwingLowBar], eqLevel, time[i], eqLevel);
            ObjectSetInteger(0, g_eqLowLineName, OBJPROP_COLOR, InpLiqColor);
            ObjectSetInteger(0, g_eqLowLineName, OBJPROP_STYLE, STYLE_DASH);
            ObjectSetInteger(0, g_eqLowLineName, OBJPROP_WIDTH, 1);
            ObjectSetInteger(0, g_eqLowLineName, OBJPROP_RAY_RIGHT, true);
         }
      }

      // ═══════════════════════════════════════════════════════════
      // ══════════════════ CONFLUENCE ENGINE ═══════════════════════
      // ═══════════════════════════════════════════════════════════

      bool emaTrendBull = g_bufEmaFast[i] > g_bufEmaMedium[i] && g_bufEmaMedium[i] > g_bufEmaSlow[i];
      bool emaTrendBear = g_bufEmaFast[i] < g_bufEmaMedium[i] && g_bufEmaMedium[i] < g_bufEmaSlow[i];
      bool priceAboveEma = close[i] > g_bufEmaSlow[i];
      bool priceBelowEma = close[i] < g_bufEmaSlow[i];

      // ── MTF Filter (MQL5 Enhancement) ──────────────────────────
      bool mtfBullOK = true, mtfBearOK = true;
      if(InpUseMTF && g_hHTFEma != INVALID_HANDLE)
      {
         double htfEma[1];
         if(CopyBuffer(g_hHTFEma, 0, rates_total - 1 - i, 1, htfEma) > 0)
         {
            mtfBullOK = close[i] > htfEma[0];
            mtfBearOK = close[i] < htfEma[0];
         }
      }

      // ── Bull Score ─────────────────────────────────────────────
      int bullScore = 0;
      bullScore += g_structureTrend == 1 ? 1 : 0;
      bullScore += priceInBullOB ? 1 : 0;
      bullScore += priceInBullFVG ? 1 : 0;
      bullScore += bullLiqSweep ? 1 : 0;
      bullScore += (volAboveAvg && close[i] > open[i]) ? 1 : 0;
      bullScore += bullAbsorption ? 1 : 0;
      bullScore += deltaBullDiv ? 1 : 0;
      bullScore += (emaTrendBull || (priceAboveEma && g_bufEmaFast[i] > g_bufEmaMedium[i])) ? 1 : 0;

      // ── Bear Score ─────────────────────────────────────────────
      int bearScore = 0;
      bearScore += g_structureTrend == -1 ? 1 : 0;
      bearScore += priceInBearOB ? 1 : 0;
      bearScore += priceInBearFVG ? 1 : 0;
      bearScore += bearLiqSweep ? 1 : 0;
      bearScore += (volAboveAvg && close[i] < open[i]) ? 1 : 0;
      bearScore += bearAbsorption ? 1 : 0;
      bearScore += deltaBearDiv ? 1 : 0;
      bearScore += (emaTrendBear || (priceBelowEma && g_bufEmaFast[i] < g_bufEmaMedium[i])) ? 1 : 0;

      // ── Confidence ─────────────────────────────────────────────
      double bullConf = 0, bearConf = 0;

      // Bull confidence
      bullConf += g_structureTrend == 1 ? 25 : (g_structureTrend == 0 ? 10 : 0);
      bullConf += priceInBullOB ? 15 : 0;
      bullConf += priceInBullFVG ? 10 : 0;
      bullConf += bullLiqSweep ? 15 : 0;
      bullConf += bullAbsorption ? 10 : 0;
      bullConf += deltaBullDiv ? 8 : 0;
      bullConf += (volAboveAvg && close[i] > open[i]) ? 7 : 0;
      bullConf += emaTrendBull ? 10 : (priceAboveEma ? 5 : 0);
      if(bullConf > 100) bullConf = 100;

      // Bear confidence
      bearConf += g_structureTrend == -1 ? 25 : (g_structureTrend == 0 ? 10 : 0);
      bearConf += priceInBearOB ? 15 : 0;
      bearConf += priceInBearFVG ? 10 : 0;
      bearConf += bearLiqSweep ? 15 : 0;
      bearConf += bearAbsorption ? 10 : 0;
      bearConf += deltaBearDiv ? 8 : 0;
      bearConf += (volAboveAvg && close[i] < open[i]) ? 7 : 0;
      bearConf += emaTrendBear ? 10 : (priceBelowEma ? 5 : 0);
      if(bearConf > 100) bearConf = 100;

      // ═══════════════════════════════════════════════════════════
      // ══════════════════ SIGNAL GENERATION ═══════════════════════
      // ═══════════════════════════════════════════════════════════

      bool cooldownOK = (i - g_lastSignalBar) >= InpSignalCooldown;

      bool bullSignal = InpShowSignals && bullScore >= InpMinConfluence && cooldownOK &&
                        close[i] > open[i] && mtfBullOK;
      bool bearSignal = InpShowSignals && bearScore >= InpMinConfluence && cooldownOK &&
                        close[i] < open[i] && mtfBearOK;

      // Prevent simultaneous
      if(bullSignal && bearSignal)
      {
         if(bullScore > bearScore)      bearSignal = false;
         else if(bearScore > bullScore) bullSignal = false;
         else { bullSignal = false; bearSignal = false; }
      }

      if(bullSignal || bearSignal)
         g_lastSignalBar = i;

      // ── Draw Signal Labels ─────────────────────────────────────
      if(bullSignal)
      {
         string grade = GetGrade(bullConf);
         color  clr   = GetGradeColor(bullConf, true);

         string details = "";
         if(g_structureTrend == 1)                                          details += "STR ";
         if(priceInBullOB)                                                  details += "OB ";
         if(priceInBullFVG)                                                 details += "FVG ";
         if(bullLiqSweep)                                                   details += "LIQ ";
         if(volAboveAvg && close[i] > open[i])                              details += "VOL ";
         if(bullAbsorption)                                                 details += "ABS ";
         if(deltaBullDiv)                                                   details += "DLT ";
         if(emaTrendBull || (priceAboveEma && g_bufEmaFast[i] > g_bufEmaMedium[i])) details += "EMA ";

         string txt = "▲ LONG  " + grade + " | " +
            IntegerToString((int)MathRound(bullConf)) + "% | " +
            IntegerToString(bullScore) + "/8\n" + details;

         double labelY = low[i] - atrVal * InpSignalOffset;

         // Connector line
         string lineName = UniqueObjName("AlphaX_SIG_LINE");
         ObjectCreate(0, lineName, OBJ_TREND, 0, time[i], low[i], time[i], labelY);
         ObjectSetInteger(0, lineName, OBJPROP_COLOR, clr);
         ObjectSetInteger(0, lineName, OBJPROP_STYLE, STYLE_DOT);
         ObjectSetInteger(0, lineName, OBJPROP_WIDTH, 1);
         ObjectSetInteger(0, lineName, OBJPROP_RAY, false);

         // Signal label
         string lblName = UniqueObjName("AlphaX_SIG");
         ObjectCreate(0, lblName, OBJ_TEXT, 0, time[i], labelY);
         ObjectSetString(0, lblName, OBJPROP_TEXT, txt);
         ObjectSetInteger(0, lblName, OBJPROP_COLOR, clr);
         ObjectSetInteger(0, lblName, OBJPROP_FONTSIZE, 8);
         ObjectSetInteger(0, lblName, OBJPROP_ANCHOR, ANCHOR_UPPER);

         // ── SL/TP Lines (MQL5 Enhancement) ──────────────────────
         if(InpShowSLTP)
         {
            double slLevel = low[i] - atrVal * InpSLPaddingATR;
            // Use OB bottom if price is in OB
            if(priceInBullOB)
            {
               for(int j = ArraySize(g_obArray) - 1; j >= 0; j--)
                  if(g_obArray[j].active && g_obArray[j].isBull)
                  { slLevel = g_obArray[j].bottom - atrVal * InpSLPaddingATR; break; }
            }
            double risk   = close[i] - slLevel;
            double tpLevel = close[i] + risk * InpRiskReward;

            DrawSLTPLine("AlphaX_SL_" + IntegerToString(i), time[i], slLevel, clrOrangeRed, "SL");
            DrawSLTPLine("AlphaX_TP_" + IntegerToString(i), time[i], tpLevel, InpBullBright, "TP");
         }

         // Alerts
         if(i == rates_total - 1)
            SendSignalAlert("LONG", grade, bullConf, bullScore);
      }

      if(bearSignal)
      {
         string grade = GetGrade(bearConf);
         color  clr   = GetGradeColor(bearConf, false);

         string details = "";
         if(g_structureTrend == -1)                                         details += "STR ";
         if(priceInBearOB)                                                  details += "OB ";
         if(priceInBearFVG)                                                 details += "FVG ";
         if(bearLiqSweep)                                                   details += "LIQ ";
         if(volAboveAvg && close[i] < open[i])                              details += "VOL ";
         if(bearAbsorption)                                                 details += "ABS ";
         if(deltaBearDiv)                                                   details += "DLT ";
         if(emaTrendBear || (priceBelowEma && g_bufEmaFast[i] < g_bufEmaMedium[i])) details += "EMA ";

         string txt = "▼ SHORT  " + grade + " | " +
            IntegerToString((int)MathRound(bearConf)) + "% | " +
            IntegerToString(bearScore) + "/8\n" + details;

         double labelY = high[i] + atrVal * InpSignalOffset;

         string lineName = UniqueObjName("AlphaX_SIG_LINE");
         ObjectCreate(0, lineName, OBJ_TREND, 0, time[i], high[i], time[i], labelY);
         ObjectSetInteger(0, lineName, OBJPROP_COLOR, clr);
         ObjectSetInteger(0, lineName, OBJPROP_STYLE, STYLE_DOT);
         ObjectSetInteger(0, lineName, OBJPROP_WIDTH, 1);
         ObjectSetInteger(0, lineName, OBJPROP_RAY, false);

         string lblName = UniqueObjName("AlphaX_SIG");
         ObjectCreate(0, lblName, OBJ_TEXT, 0, time[i], labelY);
         ObjectSetString(0, lblName, OBJPROP_TEXT, txt);
         ObjectSetInteger(0, lblName, OBJPROP_COLOR, clr);
         ObjectSetInteger(0, lblName, OBJPROP_FONTSIZE, 8);
         ObjectSetInteger(0, lblName, OBJPROP_ANCHOR, ANCHOR_LOWER);

         if(InpShowSLTP)
         {
            double slLevel = high[i] + atrVal * InpSLPaddingATR;
            if(priceInBearOB)
            {
               for(int j = ArraySize(g_obArray) - 1; j >= 0; j--)
                  if(g_obArray[j].active && !g_obArray[j].isBull)
                  { slLevel = g_obArray[j].top + atrVal * InpSLPaddingATR; break; }
            }
            double risk   = slLevel - close[i];
            double tpLevel = close[i] - risk * InpRiskReward;

            DrawSLTPLine("AlphaX_SL_" + IntegerToString(i), time[i], slLevel, clrOrangeRed, "SL");
            DrawSLTPLine("AlphaX_TP_" + IntegerToString(i), time[i], tpLevel, InpBearBright, "TP");
         }

         if(i == rates_total - 1)
            SendSignalAlert("SHORT", grade, bearConf, bearScore);
      }

      // ═══════════════════════════════════════════════════════════
      // ══════════════════ DASHBOARD (last bar only) ══════════════
      // ═══════════════════════════════════════════════════════════

      if(InpShowDash && i == rates_total - 1)
      {
         bool cloudBull = g_bufCloudFast[i] != EMPTY_VALUE &&
                          g_bufCloudFast[i] > g_bufCloudSlow[i];
         bool cloudBear = g_bufCloudFast[i] != EMPTY_VALUE &&
                          g_bufCloudFast[i] < g_bufCloudSlow[i];

         // Count active zones
         int obCount = 0, fvgCount = 0;
         for(int j = 0; j < ArraySize(g_obArray); j++)
            if(g_obArray[j].active) obCount++;
         for(int j = 0; j < ArraySize(g_fvgArray); j++)
            if(g_fvgArray[j].active) fvgCount++;

         // Verdict
         string verdictTxt = "✕  NO CLEAR EDGE";
         if(bullScore >= 5 && g_structureTrend == 1 && emaTrendBull)
            verdictTxt = "✓  HIGH CONFIDENCE LONG";
         else if(bearScore >= 5 && g_structureTrend == -1 && emaTrendBear)
            verdictTxt = "✓  HIGH CONFIDENCE SHORT";
         else if(bullScore >= InpMinConfluence && g_structureTrend == 1)
            verdictTxt = "△  LEAN LONG — CAUTION";
         else if(bearScore >= InpMinConfluence && g_structureTrend == -1)
            verdictTxt = "▽  LEAN SHORT — CAUTION";
         else if(bullScore >= InpMinConfluence && bearScore >= InpMinConfluence)
            verdictTxt = "✕  MIXED — STAND ASIDE";

         string volState = relVol > InpVolSpikeMulti * 1.5 ? "SPIKE" :
                           relVol > InpVolSpikeMulti ? "HIGH" :
                           relVol > 1.0 ? "NORMAL" : "DRY";

         string dashText = "";
         dashText += "═══════════════════════════════\n";
         dashText += "   A L P H A X   N E X U S  v2\n";
         dashText += "   SMC × Order Flow Engine\n";
         dashText += "═══════════════════════════════\n";
         dashText += "STRUCTURE:  " + (g_structureTrend == 1 ? "▲ BULLISH" : g_structureTrend == -1 ? "▼ BEARISH" : "— RANGING") + "\n";
         dashText += "EMA TREND:  " + (emaTrendBull ? "▲ BULL ALIGNED" : emaTrendBear ? "▼ BEAR ALIGNED" : "— MIXED") + "\n";
         dashText += "CLOUD:      " + (cloudBull ? "▲ BULLISH" : cloudBear ? "▼ BEARISH" : "— FLAT") + "\n";
         dashText += "───────────────────────────────\n";
         dashText += "REL VOLUME: " + volState + " (" + DoubleToString(relVol, 2) + "x)\n";
         dashText += "DELTA FLOW: " + (smoothDelta > 0 ? "▲ BUYING" : smoothDelta < 0 ? "▼ SELLING" : "— FLAT") + "\n";
         dashText += "ACTIVE:     OB:" + IntegerToString(obCount) + "  FVG:" + IntegerToString(fvgCount) + "\n";
         dashText += "───────────────────────────────\n";
         dashText += "BULL SCORE: " + IntegerToString(bullScore) + "/8  " + IntegerToString((int)MathRound(bullConf)) + "% [" + GetGrade(bullConf) + "]\n";
         dashText += "BEAR SCORE: " + IntegerToString(bearScore) + "/8  " + IntegerToString((int)MathRound(bearConf)) + "% [" + GetGrade(bearConf) + "]\n";
         dashText += "───────────────────────────────\n";
         dashText += "VERDICT: " + verdictTxt + "\n";
         if(InpUseMTF)
            dashText += "MTF(" + EnumToString(InpHTFPeriod) + "): " +
               (mtfBullOK && !mtfBearOK ? "▲ ABOVE" : !mtfBullOK && mtfBearOK ? "▼ BELOW" : "— NEUTRAL") + "\n";
         dashText += "═══════════════════════════════";

         Comment(dashText);
      }

   } // end main loop

   return rates_total;
}


// ═══════════════════════════════════════════════════════════════════
// ══════════════════════ DRAWING FUNCTIONS ═════════════════════════
// ═══════════════════════════════════════════════════════════════════

void CreateLabel(string name, datetime dt, double price, string text,
                 color clr, ENUM_ANCHOR_POINT anchor, double offset)
{
   ObjectDelete(0, name);
   ObjectCreate(0, name, OBJ_TEXT, 0, dt, price + offset * 0.5);
   ObjectSetString(0, name, OBJPROP_TEXT, text);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, 7);
   ObjectSetInteger(0, name, OBJPROP_ANCHOR, anchor);
   ObjectSetString(0, name, OBJPROP_FONT, "Consolas");
}

void CreateRectangle(string name, datetime startTime,
                     double top, double bottom, color clr,
                     bool isBull, bool isDotted = false)
{
   ObjectCreate(0, name, OBJ_RECTANGLE, 0, startTime, top, startTime, bottom);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_STYLE, isDotted ? STYLE_DOT : STYLE_SOLID);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
   ObjectSetInteger(0, name, OBJPROP_FILL, false);
   ObjectSetInteger(0, name, OBJPROP_BACK, true);

   // Semi-transparent fill using back property
   color fillClr = clr;
   ObjectSetInteger(0, name, OBJPROP_COLOR, fillClr);
}

void DrawSLTPLine(string name, datetime dt, double price, color clr, string label)
{
   ObjectDelete(0, name);
   ObjectCreate(0, name, OBJ_TREND, 0, dt, price,
      dt + PeriodSeconds() * 20, price);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, name, OBJPROP_STYLE, STYLE_DASHDOTDOT);
   ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
   ObjectSetInteger(0, name, OBJPROP_RAY, false);

   string txtName = name + "_txt";
   ObjectDelete(0, txtName);
   ObjectCreate(0, txtName, OBJ_TEXT, 0, dt + PeriodSeconds() * 21, price);
   ObjectSetString(0, txtName, OBJPROP_TEXT,
      label + " " + DoubleToString(price, _Digits));
   ObjectSetInteger(0, txtName, OBJPROP_COLOR, clr);
   ObjectSetInteger(0, txtName, OBJPROP_FONTSIZE, 7);
   ObjectSetString(0, txtName, OBJPROP_FONT, "Consolas");
}


// ═══════════════════════════════════════════════════════════════════
// ══════════════════════ ALERT SYSTEM ═════════════════════════════
// ═══════════════════════════════════════════════════════════════════

void SendSignalAlert(string direction, string grade, double conf, int score)
{
   string msg = "AlphaX Nexus: " + direction + " signal on " +
      _Symbol + " " + EnumToString(_Period) +
      " | Grade: " + grade +
      " | Conf: " + IntegerToString((int)MathRound(conf)) + "%" +
      " | Score: " + IntegerToString(score) + "/8";

   if(InpAlertPopup)
      Alert(msg);

   if(InpAlertPush)
      SendNotification(msg);
}

//+------------------------------------------------------------------+

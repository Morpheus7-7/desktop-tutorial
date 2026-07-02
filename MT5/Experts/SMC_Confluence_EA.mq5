//+------------------------------------------------------------------+
//|                                            SMC_Confluence_EA.mq5 |
//|  Expert Advisor a confluenza basato sui concetti dell'indicatore |
//|  "SMC + OscDiv + TickProfile + LDP" (Luigi Damaso):              |
//|                                                                  |
//|  MODULI DI SEGNALE (ricalcolati internamente su barre chiuse):   |
//|   1. Struttura SMC     - pivot swing/internal, BOS e CHoCH,      |
//|                          trend strutturale, premium/discount     |
//|   2. Order Blocks      - OB interni creati sui break di          |
//|                          struttura, mitigazione high/low,        |
//|                          ingresso sul retest della zona          |
//|   3. Liquidity Zones   - zone BSL/SSL sui pivot (stile LDP),     |
//|                          accumulo delta per quadrante, sweep     |
//|                          e reversal ABS / EXH / DIV / REJ        |
//|   4. Divergenze RSI    - divergenza regolare rialzista/ribassista|
//|                          su pivot dell'oscillatore               |
//|                                                                  |
//|  LOGICA DI INGRESSO (confluenza):                                |
//|   Trigger  = reversal su sweep di liquidita' OPPURE retest OB    |
//|   Filtri   = trend strutturale + premium/discount + divergenza   |
//|   Serve un punteggio minimo di confluenza per aprire il trade.   |
//|                                                                  |
//|  RISK MANAGEMENT: rischio % fisso, SL oltre la zona, TP a R:R,   |
//|  breakeven a 1R, limite perdita giornaliero, max trade/giorno,   |
//|  filtro spread, finestra oraria, chiusura totale a fine giornata.|
//+------------------------------------------------------------------+
#property copyright "Open source - uso a proprio rischio"
#property version   "1.00"

#include <Trade/Trade.mqh>

//=================== ENUM ===================
enum ENUM_ENTRY_MODEL
  {
   ENTRY_SWEEP = 0,   // Solo reversal su sweep di liquidita'
   ENTRY_OB    = 1,   // Solo retest degli Order Block
   ENTRY_BOTH  = 2    // Entrambi i trigger
  };

//=================== INPUT ===================
input group "=== Generale ==="
input long   InpMagic            = 260703;   // Magic number
input double InpRiskPercent      = 1.0;      // Rischio per trade (% saldo)
input int    InpMaxSpreadPoints  = 30;       // Spread massimo (points, 0=off)
input int    InpMaxTradesPerDay  = 3;        // Max trade al giorno
input double InpDailyLossLimit   = 3.0;      // Stop perdita giornaliera (% saldo, 0=off)

input group "=== Orari (ora del server) ==="
input int    InpSessionStartHour = 8;        // Inizio finestra ingressi - ora
input int    InpEntryCutoffHour  = 19;       // Fine finestra ingressi - ora
input int    InpCloseAllHour     = 21;       // Chiusura forzata - ora
input int    InpCloseAllMin      = 30;       // Chiusura forzata - minuti
input bool   InpCloseEndOfDay    = true;     // Chiudi tutto a fine giornata

input group "=== Ingressi e confluenza ==="
input ENUM_ENTRY_MODEL InpEntryModel   = ENTRY_BOTH; // Modello di ingresso
input int    InpMinConfluence    = 2;        // Punteggio confluenza minimo (0-3)
input bool   InpRequireDivergence= false;    // Divergenza RSI obbligatoria
input double InpRewardRisk       = 2.0;      // Take profit (x rischio)
input bool   InpBreakEven        = true;     // SL a breakeven dopo 1R
input double InpSLBufferATR      = 0.20;     // Buffer stop loss (x ATR)

input group "=== Struttura SMC ==="
input int    InpSwingLen         = 50;       // Lunghezza pivot swing (min 10)
input int    InpInternalLen      = 5;        // Lunghezza pivot interni
input bool   InpUsePremDisc      = true;     // Filtro Premium/Discount

input group "=== Order Blocks ==="
input int    InpMaxOB            = 10;       // Max OB attivi per lato
input int    InpOBMaxAgeBars     = 300;      // Eta' massima OB (barre)

input group "=== Liquidity Zones (LDP) ==="
input int    InpLdpLen           = 15;       // Lunghezza pivot liquidita'
input int    InpLdpMaxZones      = 10;       // Max zone attive per tipo
input bool   InpSigABS           = true;     // Segnale ABS (absorption)
input bool   InpSigEXH           = true;     // Segnale EXH (exhaustion)
input bool   InpSigDIV           = true;     // Segnale DIV (delta divergence)
input bool   InpSigREJ           = true;     // Segnale REJ (snapback rejection)

input group "=== Divergenza RSI ==="
input int    InpRsiPeriod        = 14;       // Periodo RSI
input int    InpDivLookback      = 5;        // Pivot lookback (sx e dx)
input int    InpDivValidBars     = 12;       // Validita' divergenza (barre)

input group "=== Varie ==="
input int    InpAtrPeriod        = 14;       // Periodo ATR
input int    InpWarmupBars       = 1000;     // Barre di storico per warm-up

//=================== STRUTTURE ===================
struct SOrderBlock
  {
   double   top, bottom;
   int      bias;          // +1 bull, -1 bear
   datetime created;
   bool     active;
  };

struct SLiqZone
  {
   double   top, bottom;
   double   deltas[4];     // quadranti dal basso (0) all'alto (3)
   double   volTraded;
   bool     isBsl;         // true = Buy Side Liquidity (sopra pivot high)
   bool     swept;
   bool     signaled;
   bool     active;
   datetime created;
  };

//=================== GLOBALI ===================
CTrade   g_trade;
int      g_hATR = INVALID_HANDLE;
int      g_hRSI = INVALID_HANDLE;

datetime g_lastBarTime = 0;
datetime g_currentDay  = 0;
bool     g_dayHalted   = false;
bool     g_warmed      = false;

//--- struttura SMC (swing e internal)
double   g_swHighLvl = 0, g_swLowLvl = 0;
bool     g_swHighCrossed = true, g_swLowCrossed = true;
datetime g_swHighTime = 0, g_swLowTime = 0;
int      g_swTrend = 0;

double   g_inHighLvl = 0, g_inLowLvl = 0;
bool     g_inHighCrossed = true, g_inLowCrossed = true;
datetime g_inHighTime = 0, g_inLowTime = 0;
int      g_inTrend = 0;

//--- range per premium/discount (trailing swing)
double   g_rangeTop = 0, g_rangeBot = 0;

//--- order blocks
SOrderBlock g_obs[];
int         g_obCount = 0;

//--- zone di liquidita'
SLiqZone g_zones[];
int      g_zoneCount = 0;

//--- divergenze RSI
double   g_lastRsiPLVal = 0, g_lastRsiPLPrice = 0;   // pivot low precedente
double   g_lastRsiPHVal = 0, g_lastRsiPHPrice = 0;   // pivot high precedente
bool     g_hasPrevPL = false, g_hasPrevPH = false;
datetime g_bullDivUntil = 0, g_bearDivUntil = 0;

//--- segnali della barra corrente (riempiti da UpdateState)
bool     g_sigLong = false,  g_sigShort = false;
double   g_sigLongSL = 0,    g_sigShortSL = 0;
string   g_sigLongTag = "",  g_sigShortTag = "";

//+------------------------------------------------------------------+
int OnInit()
  {
   g_hATR = iATR(_Symbol, PERIOD_CURRENT, InpAtrPeriod);
   g_hRSI = iRSI(_Symbol, PERIOD_CURRENT, InpRsiPeriod, PRICE_CLOSE);
   if(g_hATR == INVALID_HANDLE || g_hRSI == INVALID_HANDLE)
     {
      Print("Errore creazione indicatori");
      return(INIT_FAILED);
     }

   g_trade.SetExpertMagicNumber(InpMagic);
   g_trade.SetDeviationInPoints(20);
   g_trade.SetTypeFillingBySymbol(_Symbol);

   ArrayResize(g_obs, InpMaxOB * 2 + 4);
   ArrayResize(g_zones, InpLdpMaxZones * 2 + 4);
   g_obCount = 0;
   g_zoneCount = 0;

   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   if(g_hATR != INVALID_HANDLE) IndicatorRelease(g_hATR);
   if(g_hRSI != INVALID_HANDLE) IndicatorRelease(g_hRSI);
  }

//+------------------------------------------------------------------+
//| Helpers dati barra (shift-based, serie)                          |
//+------------------------------------------------------------------+
double H(int s) { return iHigh(_Symbol, PERIOD_CURRENT, s);  }
double L(int s) { return iLow(_Symbol, PERIOD_CURRENT, s);   }
double C(int s) { return iClose(_Symbol, PERIOD_CURRENT, s); }
double O(int s) { return iOpen(_Symbol, PERIOD_CURRENT, s);  }
datetime T(int s) { return iTime(_Symbol, PERIOD_CURRENT, s); }
double V(int s) { return (double)iVolume(_Symbol, PERIOD_CURRENT, s); }

double GetATR(int shift)
  {
   double buf[1];
   if(CopyBuffer(g_hATR, 0, shift, 1, buf) != 1) return 0.0;
   return buf[0];
  }

double GetRSI(int shift)
  {
   double buf[1];
   if(CopyBuffer(g_hRSI, 0, shift, 1, buf) != 1) return EMPTY_VALUE;
   return buf[0];
  }

//+------------------------------------------------------------------+
//| Pivot classici (strettamente maggiore/minore dei vicini)         |
//+------------------------------------------------------------------+
bool IsPivotHigh(int shift, int len)
  {
   double cand = H(shift);
   if(cand <= 0) return false;
   for(int i = 1; i <= len; i++)
      if(H(shift + i) >= cand || H(shift - i) >= cand) return false;
   return true;
  }

bool IsPivotLow(int shift, int len)
  {
   double cand = L(shift);
   if(cand <= 0) return false;
   for(int i = 1; i <= len; i++)
      if(L(shift + i) <= cand || L(shift - i) <= cand) return false;
   return true;
  }

//==================================================================
//  MODULO 1: STRUTTURA SMC (BOS / CHoCH, trend, premium/discount)
//==================================================================

//+------------------------------------------------------------------+
//| Aggiorna pivot e break di struttura per un set swing o internal  |
//| Ritorna: +1 break rialzista, -1 ribassista, 0 nessuno            |
//+------------------------------------------------------------------+
int UpdateStructureSet(int s, int len,
                       double &highLvl, bool &highCrossed, datetime &highTime,
                       double &lowLvl,  bool &lowCrossed,  datetime &lowTime,
                       int &trend, bool &wasChoch)
  {
   wasChoch = false;
   int p = s + len;

   //--- nuovo pivot confermato alla chiusura della barra s
   if(IsPivotHigh(p, len))
     { highLvl = H(p); highCrossed = false; highTime = T(p); }
   if(IsPivotLow(p, len))
     { lowLvl = L(p); lowCrossed = false; lowTime = T(p); }

   int brk = 0;
   //--- break rialzista: chiusura sopra l'ultimo pivot high non ancora rotto
   if(highLvl > 0 && !highCrossed && C(s) > highLvl && C(s + 1) <= highLvl)
     {
      wasChoch = (trend == -1);
      highCrossed = true;
      trend = +1;
      brk = +1;
     }
   //--- break ribassista
   else if(lowLvl > 0 && !lowCrossed && C(s) < lowLvl && C(s + 1) >= lowLvl)
     {
      wasChoch = (trend == +1);
      lowCrossed = true;
      trend = -1;
      brk = -1;
     }
   return brk;
  }

//==================================================================
//  MODULO 2: ORDER BLOCKS (creazione su break, mitigazione, retest)
//==================================================================
void AddOrderBlock(double top, double bottom, int bias, datetime created)
  {
   //--- limita il numero di OB attivi per lato (rimuove il piu' vecchio)
   int sameSide = 0, oldestIdx = -1;
   datetime oldestT = 0;
   for(int i = 0; i < g_obCount; i++)
      if(g_obs[i].active && g_obs[i].bias == bias)
        {
         sameSide++;
         if(oldestIdx < 0 || g_obs[i].created < oldestT)
           { oldestT = g_obs[i].created; oldestIdx = i; }
        }
   if(sameSide >= InpMaxOB && oldestIdx >= 0)
      g_obs[oldestIdx].active = false;

   //--- riusa uno slot inattivo o accoda
   int slot = -1;
   for(int i = 0; i < g_obCount; i++)
      if(!g_obs[i].active) { slot = i; break; }
   if(slot < 0)
     {
      if(g_obCount >= ArraySize(g_obs)) ArrayResize(g_obs, g_obCount + 8);
      slot = g_obCount++;
     }
   g_obs[slot].top = top;
   g_obs[slot].bottom = bottom;
   g_obs[slot].bias = bias;
   g_obs[slot].created = created;
   g_obs[slot].active = true;
  }

//+------------------------------------------------------------------+
//| Crea l'OB dal leg che ha causato il break (stile SMC)            |
//| bias +1: cerca la barra col minimo piu' basso tra pivot e break  |
//+------------------------------------------------------------------+
void CreateOBFromBreak(int s, datetime pivotTime, int bias)
  {
   int pShift = iBarShift(_Symbol, PERIOD_CURRENT, pivotTime, false);
   if(pShift < 0 || pShift <= s) return;

   int best = -1;
   if(bias == +1)
     {
      double mn = DBL_MAX;
      for(int i = s; i <= pShift; i++)
         if(L(i) < mn) { mn = L(i); best = i; }
     }
   else
     {
      double mx = -DBL_MAX;
      for(int i = s; i <= pShift; i++)
         if(H(i) > mx) { mx = H(i); best = i; }
     }
   if(best < 0) return;
   AddOrderBlock(H(best), L(best), bias, T(best));
  }

//+------------------------------------------------------------------+
//| Mitigazione OB sulla barra s (modalita' high/low)                |
//+------------------------------------------------------------------+
void MitigateOBs(int s)
  {
   datetime maxAge = T(s) - (datetime)InpOBMaxAgeBars * PeriodSeconds();
   for(int i = 0; i < g_obCount; i++)
     {
      if(!g_obs[i].active) continue;
      if(g_obs[i].created < maxAge) { g_obs[i].active = false; continue; }
      if(g_obs[i].bias == +1 && L(s) < g_obs[i].bottom) g_obs[i].active = false;
      if(g_obs[i].bias == -1 && H(s) > g_obs[i].top)    g_obs[i].active = false;
     }
  }

//+------------------------------------------------------------------+
//| Retest OB sulla barra s: wick dentro la zona, chiusura fuori     |
//| Ritorna l'indice dell'OB oppure -1                               |
//+------------------------------------------------------------------+
int CheckOBRetest(int s, int bias)
  {
   for(int i = 0; i < g_obCount; i++)
     {
      if(!g_obs[i].active || g_obs[i].bias != bias) continue;
      if(g_obs[i].created >= T(s)) continue;          // non sulla barra di creazione
      if(bias == +1)
        {
         if(L(s) <= g_obs[i].top && C(s) > g_obs[i].top && L(s) >= g_obs[i].bottom)
            return i;
        }
      else
        {
         if(H(s) >= g_obs[i].bottom && C(s) < g_obs[i].bottom && H(s) <= g_obs[i].top)
            return i;
        }
     }
   return -1;
  }

//==================================================================
//  MODULO 3: LIQUIDITY ZONES (stile LDP: delta, sweep, reversal)
//==================================================================
void AddLiqZone(double top, double bottom, bool isBsl, datetime created)
  {
   int sameType = 0, oldestIdx = -1;
   datetime oldestT = 0;
   for(int i = 0; i < g_zoneCount; i++)
     {
      if(!g_zones[i].active) continue;
      if(g_zones[i].isBsl != isBsl) continue;
      //--- filtro sovrapposizioni: scarta se overlappa una zona attiva
      if(MathMax(bottom, g_zones[i].bottom) <= MathMin(top, g_zones[i].top))
         return;
      sameType++;
      if(oldestIdx < 0 || g_zones[i].created < oldestT)
        { oldestT = g_zones[i].created; oldestIdx = i; }
     }
   if(sameType >= InpLdpMaxZones && oldestIdx >= 0)
      g_zones[oldestIdx].active = false;

   int slot = -1;
   for(int i = 0; i < g_zoneCount; i++)
      if(!g_zones[i].active) { slot = i; break; }
   if(slot < 0)
     {
      if(g_zoneCount >= ArraySize(g_zones)) ArrayResize(g_zones, g_zoneCount + 8);
      slot = g_zoneCount++;
     }
   g_zones[slot].top = top;
   g_zones[slot].bottom = bottom;
   g_zones[slot].isBsl = isBsl;
   g_zones[slot].swept = false;
   g_zones[slot].signaled = false;
   g_zones[slot].active = true;
   g_zones[slot].created = created;
   g_zones[slot].volTraded = 0;
   for(int q = 0; q < 4; q++) g_zones[slot].deltas[q] = 0;
  }

//+------------------------------------------------------------------+
//| Crea zone di liquidita' sui pivot confermati alla barra s        |
//+------------------------------------------------------------------+
void CreateLiqZones(int s)
  {
   int p = s + InpLdpLen;
   double atr = GetATR(p);
   if(atr <= 0) return;

   if(IsPivotHigh(p, InpLdpLen))
     {
      double top = H(p);
      double bot = MathMax(O(p), C(p));
      if(top - bot < atr * 0.1) bot = top - atr * 0.1;
      AddLiqZone(top, bot, true, T(p));
     }
   if(IsPivotLow(p, InpLdpLen))
     {
      double bot = L(p);
      double top = MathMin(O(p), C(p));
      if(top - bot < atr * 0.1) top = bot + atr * 0.1;
      AddLiqZone(top, bot, false, T(p));
     }
  }

//+------------------------------------------------------------------+
//| Classifica il reversal di zona (regole LDP: ABS/EXH/DIV/REJ)     |
//| Ritorna il tag del segnale o "" se nessuno                       |
//+------------------------------------------------------------------+
string ClassifyReversal(int zi, int s, double barDelta, double barVol)
  {
   double absTotal = 0;
   for(int q = 0; q < 4; q++) absTotal += MathAbs(g_zones[zi].deltas[q]);
   if(absTotal <= 0) return "";

   bool isBsl = g_zones[zi].isBsl;
   int outerIdx = isBsl ? 3 : 0;
   double outerD = g_zones[zi].deltas[outerIdx];
   double ratio = MathAbs(outerD) / (absTotal + 0.0001);

   bool sweeping = isBsl ? (H(s) > g_zones[zi].top) : (L(s) < g_zones[zi].bottom);
   bool closesInside = (C(s) <= g_zones[zi].top && C(s) >= g_zones[zi].bottom);
   double mid = (g_zones[zi].top + g_zones[zi].bottom) / 2.0;
   bool closesRejecting = isBsl ? (C(s) < mid) : (C(s) > mid);

   // 1) ABS - absorption all'estremo: sweep con delta contrario forte
   if(InpSigABS && sweeping && ((isBsl && outerD < 0) || (!isBsl && outerD > 0)) && ratio > 0.2)
      return "ABS";
   // 2) EXH - exhaustion: sweep "secco" senza partecipazione
   if(InpSigEXH && sweeping && ratio < 0.1)
      return "EXH";
   // 3) DIV - delta divergence: chiude dentro, delta esterno FOMO intrappolato
   if(InpSigDIV && closesInside && ratio > 0.6 &&
      ((isBsl && outerD > 0) || (!isBsl && outerD < 0)))
      return "DIV";
   // 4) REJ - snapback rejection: sweep + chiusura di rifiuto + delta barra contrario
   if(InpSigREJ && sweeping && closesRejecting)
     {
      double barRatio = MathAbs(barDelta) / (barVol + 0.0001);
      if(((isBsl && barDelta < 0) || (!isBsl && barDelta > 0)) && barRatio > 0.2)
         return "REJ";
     }
   return "";
  }

//+------------------------------------------------------------------+
//| Elabora la barra s su tutte le zone attive: delta, sweep, segnali|
//+------------------------------------------------------------------+
void ProcessLiqZones(int s)
  {
   double barH = H(s), barL = L(s), barC = C(s), barV = V(s);
   double range = barH - barL;
   double barDelta = (range <= 0) ? 0 : barV * (barC - O(s)) / range;

   for(int i = 0; i < g_zoneCount; i++)
     {
      if(!g_zones[i].active || g_zones[i].swept) continue;
      if(g_zones[i].created >= T(s)) continue;

      //--- accumula delta nei 4 quadranti in proporzione all'overlap
      double step = (g_zones[i].top - g_zones[i].bottom) / 4.0;
      bool hit = false;
      for(int q = 0; q < 4; q++)
        {
         double qBot = g_zones[i].bottom + q * step;
         double qTop = qBot + step;
         double ovl = MathMin(barH, qTop) - MathMax(barL, qBot);
         if(ovl > 0 && range > 0)
           {
            hit = true;
            double r = ovl / range;
            g_zones[i].deltas[q] += barDelta * r;
            g_zones[i].volTraded += barV * r;
           }
        }

      //--- sweep?
      bool sweep = g_zones[i].isBsl ? (barH > g_zones[i].top)
                                    : (barL < g_zones[i].bottom);

      //--- valutazione reversal (solo al primo evento utile)
      if((hit || sweep) && !g_zones[i].signaled)
        {
         string tag = ClassifyReversal(i, s, barDelta, barV);
         if(tag != "")
           {
            g_zones[i].signaled = true;
            double atr = GetATR(s);
            double buf = InpSLBufferATR * atr;
            if(g_zones[i].isBsl)
              {
               //--- sweep della liquidita' buy-side => segnale SHORT
               g_sigShort = true;
               g_sigShortSL = MathMax(barH, g_zones[i].top) + buf;
               g_sigShortTag = "LDP-" + tag;
              }
            else
              {
               //--- sweep della liquidita' sell-side => segnale LONG
               g_sigLong = true;
               g_sigLongSL = MathMin(barL, g_zones[i].bottom) - buf;
               g_sigLongTag = "LDP-" + tag;
              }
           }
        }

      if(sweep) g_zones[i].swept = true;
     }
  }

//==================================================================
//  MODULO 4: DIVERGENZE RSI (regolari, su pivot dell'oscillatore)
//==================================================================
void UpdateDivergences(int s)
  {
   int p = s + InpDivLookback;
   double rsiP = GetRSI(p);
   if(rsiP == EMPTY_VALUE) return;

   //--- pivot low dell'RSI
   bool isPL = true, isPH = true;
   for(int i = 1; i <= InpDivLookback && (isPL || isPH); i++)
     {
      double rl = GetRSI(p + i), rr = GetRSI(p - i);
      if(rl == EMPTY_VALUE || rr == EMPTY_VALUE) { isPL = false; isPH = false; break; }
      if(rl <= rsiP || rr <= rsiP) isPL = false;
      if(rl >= rsiP || rr >= rsiP) isPH = false;
     }

   datetime valid = T(s) + (datetime)(InpDivValidBars * PeriodSeconds());

   if(isPL)
     {
      double priceLow = L(p);
      //--- divergenza rialzista: prezzo LL, RSI HL (sotto la mediana 50)
      if(g_hasPrevPL && priceLow < g_lastRsiPLPrice && rsiP > g_lastRsiPLVal && rsiP < 50)
         g_bullDivUntil = valid;
      g_lastRsiPLVal = rsiP;
      g_lastRsiPLPrice = priceLow;
      g_hasPrevPL = true;
     }
   if(isPH)
     {
      double priceHigh = H(p);
      //--- divergenza ribassista: prezzo HH, RSI LH (sopra la mediana 50)
      if(g_hasPrevPH && priceHigh > g_lastRsiPHPrice && rsiP < g_lastRsiPHVal && rsiP > 50)
         g_bearDivUntil = valid;
      g_lastRsiPHVal = rsiP;
      g_lastRsiPHPrice = priceHigh;
      g_hasPrevPH = true;
     }
  }

//==================================================================
//  AGGIORNAMENTO STATO PER BARRA CHIUSA
//==================================================================
void UpdateState(int s)
  {
   //--- 1. struttura swing
   bool choch;
   int brkSw = UpdateStructureSet(s, InpSwingLen,
                                  g_swHighLvl, g_swHighCrossed, g_swHighTime,
                                  g_swLowLvl,  g_swLowCrossed,  g_swLowTime,
                                  g_swTrend, choch);
   if(brkSw != 0)
     {
      //--- aggiorna il range premium/discount sui break di swing
      if(g_swHighLvl > 0) g_rangeTop = g_swHighLvl;
      if(g_swLowLvl > 0)  g_rangeBot = g_swLowLvl;
     }
   //--- trailing del range come nell'indicatore
   if(g_rangeTop > 0 && H(s) > g_rangeTop) g_rangeTop = H(s);
   if(g_rangeBot > 0 && L(s) < g_rangeBot) g_rangeBot = L(s);
   if(g_rangeTop <= 0 && g_swHighLvl > 0) g_rangeTop = g_swHighLvl;
   if(g_rangeBot <= 0 && g_swLowLvl > 0)  g_rangeBot = g_swLowLvl;

   //--- 2. struttura interna + order blocks sui break interni
   datetime prevHighTime = g_inHighTime, prevLowTime = g_inLowTime;
   int brkIn = UpdateStructureSet(s, InpInternalLen,
                                  g_inHighLvl, g_inHighCrossed, g_inHighTime,
                                  g_inLowLvl,  g_inLowCrossed,  g_inLowTime,
                                  g_inTrend, choch);
   if(brkIn == +1) CreateOBFromBreak(s, prevHighTime, +1);
   if(brkIn == -1) CreateOBFromBreak(s, prevLowTime, -1);
   MitigateOBs(s);

   //--- 3. zone di liquidita'
   CreateLiqZones(s);
   ProcessLiqZones(s);

   //--- 4. divergenze
   UpdateDivergences(s);
  }

//==================================================================
//  CONFLUENZA E INGRESSI
//==================================================================
int ConfluenceScore(int dir, int s)
  {
   int score = 0;
   //--- 1. trend strutturale swing concorde
   if(g_swTrend == dir) score++;
   //--- 2. premium/discount: long in discount, short in premium
   if(InpUsePremDisc && g_rangeTop > g_rangeBot && g_rangeBot > 0)
     {
      double eq = (g_rangeTop + g_rangeBot) / 2.0;
      if(dir == +1 && C(s) < eq) score++;
      if(dir == -1 && C(s) > eq) score++;
     }
   else if(!InpUsePremDisc)
      score++;   // filtro disattivato: non penalizzare
   //--- 3. divergenza RSI attiva
   bool div = (dir == +1) ? (T(s) <= g_bullDivUntil) : (T(s) <= g_bearDivUntil);
   if(div) score++;
   return score;
  }

double CalcLots(double slDistance)
  {
   if(slDistance <= 0) return 0;
   double riskMoney = AccountInfoDouble(ACCOUNT_BALANCE) * InpRiskPercent / 100.0;
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize  = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickValue <= 0 || tickSize <= 0) return 0;
   double lossPerLot = slDistance / tickSize * tickValue;
   if(lossPerLot <= 0) return 0;
   double lots = riskMoney / lossPerLot;
   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(lotStep > 0) lots = MathFloor(lots / lotStep) * lotStep;
   lots = MathMax(minLot, MathMin(maxLot, lots));
   if(minLot * lossPerLot > riskMoney * 1.5) return 0;   // rischio minimo eccessivo
   return lots;
  }

void TryEnter()
  {
   if(HasPosition()) return;

   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double atr = GetATR(1);
   if(atr <= 0) return;
   double buf = InpSLBufferATR * atr;

   //--- trigger OB retest (se abilitato)
   bool obLong = false, obShort = false;
   double obLongSL = 0, obShortSL = 0;
   if(InpEntryModel == ENTRY_OB || InpEntryModel == ENTRY_BOTH)
     {
      int ib = CheckOBRetest(1, +1);
      if(ib >= 0) { obLong = true; obLongSL = g_obs[ib].bottom - buf; }
      int is = CheckOBRetest(1, -1);
      if(is >= 0) { obShort = true; obShortSL = g_obs[is].top + buf; }
     }

   bool sweepLong  = g_sigLong  && (InpEntryModel == ENTRY_SWEEP || InpEntryModel == ENTRY_BOTH);
   bool sweepShort = g_sigShort && (InpEntryModel == ENTRY_SWEEP || InpEntryModel == ENTRY_BOTH);

   //--- LONG
   if(sweepLong || obLong)
     {
      bool divOk = !InpRequireDivergence || (T(1) <= g_bullDivUntil);
      if(divOk && ConfluenceScore(+1, 1) >= InpMinConfluence)
        {
         double sl = sweepLong ? g_sigLongSL : obLongSL;
         if(sweepLong && obLong) sl = MathMin(g_sigLongSL, obLongSL);
         double entry = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         double slDist = entry - sl;
         if(slDist > 0)
           {
            double tp = NormalizeDouble(entry + InpRewardRisk * slDist, digits);
            double lots = CalcLots(slDist);
            string tag = sweepLong ? g_sigLongTag : "OB retest";
            if(lots > 0)
               g_trade.Buy(lots, _Symbol, 0.0, NormalizeDouble(sl, digits), tp, tag);
           }
        }
     }
   //--- SHORT
   else if(sweepShort || obShort)
     {
      bool divOk = !InpRequireDivergence || (T(1) <= g_bearDivUntil);
      if(divOk && ConfluenceScore(-1, 1) >= InpMinConfluence)
        {
         double sl = sweepShort ? g_sigShortSL : obShortSL;
         if(sweepShort && obShort) sl = MathMax(g_sigShortSL, obShortSL);
         double entry = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         double slDist = sl - entry;
         if(slDist > 0)
           {
            double tp = NormalizeDouble(entry - InpRewardRisk * slDist, digits);
            double lots = CalcLots(slDist);
            string tag = sweepShort ? g_sigShortTag : "OB retest";
            if(lots > 0)
               g_trade.Sell(lots, _Symbol, 0.0, NormalizeDouble(sl, digits), tp, tag);
           }
        }
     }
  }

//==================================================================
//  GESTIONE POSIZIONI E RISK MANAGEMENT
//==================================================================
bool HasPosition()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(PositionGetSymbol(i) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) == InpMagic) return true;
     }
   return false;
  }

void ManagePositions()
  {
   if(!InpBreakEven) return;
   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);
   double point = SymbolInfoDouble(_Symbol, SYMBOL_POINT);

   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(PositionGetSymbol(i) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;

      ulong  ticket = PositionGetInteger(POSITION_TICKET);
      double open = PositionGetDouble(POSITION_PRICE_OPEN);
      double sl   = PositionGetDouble(POSITION_SL);
      double tp   = PositionGetDouble(POSITION_TP);
      long   type = PositionGetInteger(POSITION_TYPE);

      if(type == POSITION_TYPE_BUY)
        {
         double risk = open - sl;
         double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
         if(risk > 0 && sl < open && bid >= open + risk)
            g_trade.PositionModify(ticket, NormalizeDouble(open + point, digits), tp);
        }
      else
        {
         double risk = sl - open;
         double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
         if(risk > 0 && sl > open && ask <= open - risk)
            g_trade.PositionModify(ticket, NormalizeDouble(open - point, digits), tp);
        }
     }
  }

void CloseAllOurPositions(string reason)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      if(PositionGetSymbol(i) != _Symbol) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      ulong ticket = PositionGetInteger(POSITION_TICKET);
      if(g_trade.PositionClose(ticket))
         PrintFormat("Posizione #%I64u chiusa: %s", ticket, reason);
     }
  }

datetime DayStart(datetime t)
  {
   MqlDateTime dt;
   TimeToStruct(t, dt);
   dt.hour = 0; dt.min = 0; dt.sec = 0;
   return StructToTime(dt);
  }

bool IsWithinEntryWindow()
  {
   datetime now = TimeCurrent();
   datetime start = DayStart(now) + InpSessionStartHour * 3600;
   datetime cutoff = DayStart(now) + InpEntryCutoffHour * 3600;
   return (now >= start && now < cutoff);
  }

bool IsPastCloseAllTime()
  {
   if(!InpCloseEndOfDay) return false;
   datetime closeAt = DayStart(TimeCurrent()) + InpCloseAllHour * 3600 + InpCloseAllMin * 60;
   return (TimeCurrent() >= closeAt);
  }

bool SpreadOK()
  {
   if(InpMaxSpreadPoints <= 0) return true;
   return (SymbolInfoInteger(_Symbol, SYMBOL_SPREAD) <= InpMaxSpreadPoints);
  }

int CountTradesToday()
  {
   int count = 0;
   if(!HistorySelect(g_currentDay, TimeCurrent())) return 0;
   int total = HistoryDealsTotal();
   for(int i = 0; i < total; i++)
     {
      ulong t = HistoryDealGetTicket(i);
      if(t == 0) continue;
      if(HistoryDealGetInteger(t, DEAL_MAGIC) != InpMagic) continue;
      if(HistoryDealGetString(t, DEAL_SYMBOL) != _Symbol) continue;
      if((ENUM_DEAL_ENTRY)HistoryDealGetInteger(t, DEAL_ENTRY) == DEAL_ENTRY_IN) count++;
     }
   return count;
  }

bool DailyLossLimitHit()
  {
   if(InpDailyLossLimit <= 0) return false;
   if(!HistorySelect(g_currentDay, TimeCurrent())) return false;
   double pnl = 0;
   int total = HistoryDealsTotal();
   for(int i = 0; i < total; i++)
     {
      ulong t = HistoryDealGetTicket(i);
      if(t == 0) continue;
      if(HistoryDealGetInteger(t, DEAL_MAGIC) != InpMagic) continue;
      if(HistoryDealGetString(t, DEAL_SYMBOL) != _Symbol) continue;
      pnl += HistoryDealGetDouble(t, DEAL_PROFIT)
           + HistoryDealGetDouble(t, DEAL_COMMISSION)
           + HistoryDealGetDouble(t, DEAL_SWAP);
     }
   double limit = AccountInfoDouble(ACCOUNT_BALANCE) * InpDailyLossLimit / 100.0;
   return (pnl <= -limit);
  }

//==================================================================
//  ONTICK
//==================================================================
void OnTick()
  {
   datetime barTime = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(barTime == g_lastBarTime) return;
   g_lastBarTime = barTime;

   //--- warm-up: ricostruisce lo stato (struttura, zone, OB) dallo storico
   if(!g_warmed)
     {
      int maxLb = MathMax(MathMax(InpSwingLen, InpLdpLen), InpDivLookback) * 2 + 5;
      int bars = Bars(_Symbol, PERIOD_CURRENT);
      if(bars < maxLb + 10) return;
      int startShift = MathMin(InpWarmupBars, bars - maxLb - 2);
      for(int s = startShift; s >= 2; s--)
        {
         g_sigLong = false; g_sigShort = false;   // niente trade in warm-up
         UpdateState(s);
        }
      g_warmed = true;
     }

   //--- reset giornaliero
   datetime today = DayStart(TimeCurrent());
   if(today != g_currentDay) { g_currentDay = today; g_dayHalted = false; }

   //--- chiusura di fine giornata
   if(IsPastCloseAllTime())
     {
      CloseAllOurPositions("Chiusura di fine giornata");
      return;
     }

   //--- aggiorna lo stato con la barra appena chiusa
   g_sigLong = false; g_sigShort = false;
   g_sigLongTag = ""; g_sigShortTag = "";
   UpdateState(1);

   //--- gestione posizioni (breakeven)
   ManagePositions();

   //--- filtri di ingresso
   if(g_dayHalted) return;
   if(DailyLossLimitHit())
     {
      g_dayHalted = true;
      CloseAllOurPositions("Limite di perdita giornaliero");
      Print("Trading sospeso fino a domani: limite di perdita raggiunto");
      return;
     }
   if(!IsWithinEntryWindow()) return;
   if(!SpreadOK()) return;
   if(CountTradesToday() >= InpMaxTradesPerDay) return;

   TryEnter();
  }
//+------------------------------------------------------------------+

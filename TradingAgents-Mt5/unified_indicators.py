# -*- coding: utf-8 -*-
"""
===============================================================================
 unified_indicators.py  -  Motore di confluenza unificato per TradingAgents-Mt5
===============================================================================

Porting in Python (numpy/pandas) di 20 indicatori LuxAlgo per TradingView,
riuniti in un unico motore decisionale ("confluence engine") che produce:

  * un REGIME di mercato      (TREND / RANGE / TRANSIZIONE)
  * uno stato di VOLATILITA'  (QUIET / NORMAL / HIGH VOL)
  * un PUNTEGGIO DIREZIONALE  (-1 ... +1) e una decisione BUY / SELL / HOLD
  * una MAPPA DEI LIVELLI     (supporti/resistenze/liquidita' in confluenza)
  * dei SETUP nominati        (pattern operativi riconosciuti)
  * un PIANO DI TRADE         (entry, stop, 3 target, rischio/rendimento)
  * un REPORT Markdown pronto per gli agenti LLM di TradingAgents

Il file e' autosufficiente: dipende solo da numpy e pandas.  Il pacchetto
MetaTrader5 serve solo se si usa il loader MT5 incluso; langchain_core solo
se si vuole il tool per gli agenti.

-------------------------------------------------------------------------------
 INDICATORI INCLUSI (20)                       key            famiglia
-------------------------------------------------------------------------------
 Batch 1
  1  Volumetric Regression Heatmap             vrh            hybrid
  2  Retest & Break Setup                      rb             breakout
  3  Multi-Strategy Portfolio Optimizer        mspo           ensemble
  4  RSI Divergence: Out-of-Sample Optimizer   rsid           reversion
  5  Supertrend Parameter Sensitivity 3D       st3d           trend
 Batch 2  (il Supertrend 3D era un duplicato)
  6  Session Volume Moving Average             svma           volume
  7  Peak Activity Range                       par            breakout
  8  Signal Forge                              sf             ensemble
  9  ATR Exceedance Probability Model          atrp           volatility
 Batch 3
 10  Historical Liquidity Proximity Heatmap    hlph           structure
 11  Order Flow VWAP Deviation                 ofvd           hybrid
 12  Liquidity Delta Profiler                  ldp            reversion
 13  Structural Leg Profiler                   slp            structure
 14  Temporal Volume Profile 3D                tvp            volume
 Batch 4 / 5
 15  EQH/EQL Liquidity Zones                   eqhl           structure
 16  Ultimate Opening Range Breakout           orb            breakout
 17  Omni-Flow Consensus                       ofc            momentum
 18  Market Structure & Scatter Dashboard      mss            trend
 19  Universal Signal Backtester               usb            trend
 20  Order Flow 3D Delta Profile               of3d           volume

La spiegazione dettagliata di OGNI indicatore (come funziona in Pine, cosa
restituisce qui, come contribuisce alla decisione e quali limiti ha) e'
nella docstring della rispettiva classe (cerca "class <Nome>(IndicatorModule)").

-------------------------------------------------------------------------------
 LOGICA UNIFICATA (in sintesi)
-------------------------------------------------------------------------------
Ogni indicatore e' un "modulo" che restituisce un ModuleResult standard:

    bias        [-1..+1]  direzione suggerita (positivo = rialzista)
    confidence  [0..1]    affidabilita' della lettura in questo momento
    regime      [-1..+1]  voto sul regime (-1 range/mean-reversion, +1 trend)
    volatility  [-1..+1]  solo moduli di volatilita' (-1 quiet, +1 espansione)
    signals     eventi discreti (BOS, CHoCH, divergenze, sweep, breakout ...)
    levels      livelli di prezzo (POC, VWAP, zone di liquidita', bande ...)
    metrics     numeri grezzi (win-rate, profit factor, parametri ottimali...)

Il motore (UnifiedEngine) li combina in 6 passaggi:

 1. REGIME      media pesata dei voti di regime (VRH piattezza del canale,
                MSPO trend-vs-reversion, ST3D consenso dei 100 supertrend,
                OFC intensita' del flusso, SF ADX, MSS BOS vs CHoCH,
                TVP migrazione del POC, OF3D prezzo dentro/fuori value area).
                >= +0.20 TREND, <= -0.20 RANGE, altrimenti TRANSIZIONE.
 2. VOLATILITA' dal modello ATRP (z-score ATR, frequenza di sforamento,
                clustering). Serve per dimensionare lo stop e per dare piu'
                credito ai breakout quando la volatilita' si sta espandendo.
 3. DIREZIONE   score = somma( bias * confidence * peso * moltiplicatore_regime )
                / somma( confidence * peso ).  Il moltiplicatore dipende dallo
                "stile" del modulo: in TREND pesano di piu' trend/momentum/
                breakout, in RANGE pesano di piu' i moduli di mean-reversion.
 4. LIVELLI     tutti i livelli di tutti i moduli vengono raggruppati in
                cluster entro 0.25*ATR; ogni cluster ha un punteggio pari
                alla somma dei pesi dei moduli distinti che lo confermano.
                Si ottengono i supporti/resistenze "di confluenza" piu' forti.
 5. SETUP       regole nominate che richiedono l'accordo di piu' famiglie
                (es. LIQUIDITY_SWEEP_REVERSAL = sweep di liquidita' + segnale
                di inversione + estremo statistico).  Ogni setup concorde
                aggiunge un bonus al punteggio.
 6. DECISIONE   soglie su score e accordo, veto contro-trend, controllo del
                rischio/rendimento sui livelli di confluenza -> BUY/SELL/HOLD
                + piano di trade (entry, SL, TP1-3, R:R).

-------------------------------------------------------------------------------
 USO RAPIDO
-------------------------------------------------------------------------------
    import pandas as pd
    from unified_indicators import UnifiedEngine, load_mt5_ohlcv

    df = load_mt5_ohlcv("EURUSD", "H1", bars=3000)        # oppure un DataFrame
    analysis = UnifiedEngine().analyze(df, symbol="EURUSD", timeframe="H1")
    print(analysis.decision, analysis.score)
    print(analysis.to_markdown())                          # report per LLM
    data = analysis.to_dict()                              # JSON-serializzabile

 Da riga di comando:
    python unified_indicators.py --demo                    # dati sintetici
    python unified_indicators.py --symbol EURUSD --timeframe H1 --bars 3000
    python unified_indicators.py --csv dati.csv --json

 DataFrame accettato: colonne open, high, low, close e volume (oppure
 tick_volume / real_volume come in MT5), indice DatetimeIndex oppure colonna
 "time" (datetime o secondi unix).  Si consigliano 1500-3000 barre.

 FUSO ORARIO: i tempi di MT5 sono nell'ora del server del broker.  Gli
 indicatori a sessione (SVMA, ORB, OFVD) hanno bisogno del fuso corretto:
 passare data_tz (es. "Europe/Athens" o "UTC+2") a UnifiedEngine.analyze()
 o a load_mt5_ohlcv(server_tz=...), oppure impostare una volta sola la
 variabile d'ambiente UNIFIED_INDICATORS_SERVER_TZ.  Default: UTC.

 REQUISITI: Python >= 3.9, numpy >= 1.20, pandas >= 1.3 (testato con
 numpy 1.26 / 2.4 e pandas 2.2 / 3.0).  Facoltativi: MetaTrader5,
 langchain-core.

-------------------------------------------------------------------------------
 INTEGRAZIONE CON TRADINGAGENTS
-------------------------------------------------------------------------------
 Il file espone:
   * get_unified_indicators_report(symbol, timeframe, bars) -> str (Markdown)
   * get_unified_indicators  (tool LangChain, se langchain_core e' installato)

 Nel TradingAgents originale basta importare il tool e aggiungerlo alla
 lista dei tool del Market Analyst (tradingagents/agents/analysts/
 market_analyst.py) e al ToolNode "market" in tradingagents/graph/
 trading_graph.py.  Nei fork per MT5 l'aggancio e' analogo: il tool
 restituisce una stringa Markdown che l'LLM legge come qualsiasi altro report.

-------------------------------------------------------------------------------
 AGGIUNGERE I PROSSIMI BATCH DI INDICATORI
-------------------------------------------------------------------------------
 1. Scrivere una classe che eredita da IndicatorModule, con key/title/style,
    una dataclass Params e il metodo compute(md) -> ModuleResult.
 2. Decorarla con @register_module.
 3. (facoltativo) aggiungerne il peso in ConfluenceConfig.module_weights e,
    se serve, nuove regole in UnifiedEngine._detect_setups().
 Il motore la includera' automaticamente.

-------------------------------------------------------------------------------
 LIMITI NOTI (validi per tutti i moduli)
-------------------------------------------------------------------------------
 * I pivot di Pine vengono confermati dopo "right" barre: tutti i segnali basati
   su pivot hanno quel ritardo (qui replicato, nessun look-ahead).
 * Alcuni indicatori originali ricalcolano la storia all'ultima barra
   (VRH, TVP, OF3D, parte di MSPO/ST3D): i loro segnali "storici" sono
   in-sample.  Il motore usa solo lo stato ATTUALE e i segnali recenti.
 * Il volume in MT5 per forex/CFD e' tick_volume: i moduli order-flow usano
   proxy (posizione della chiusura nella candela) come nell'originale.
 * Structural Leg Profiler usa dati a 1 minuto in Pine; qui usa le barre del
   timeframe corrente (lo stesso fallback previsto dall'originale).
 * Nessun indicatore garantisce risultati: l'output e' un supporto
   decisionale, da validare con backtest e gestione del rischio propri.

-------------------------------------------------------------------------------
 LICENZE
-------------------------------------------------------------------------------
 Gli script originali sono (c) LuxAlgo.  18 su 20 sono rilasciati con licenza
 Creative Commons BY-NC-SA 4.0 (https://creativecommons.org/licenses/by-nc-sa/4.0/):
 attribuzione obbligatoria, solo uso NON commerciale, opere derivate con la
 stessa licenza.  "Session Volume Moving Average" e "Structural Leg Profiler"
 sono rilasciati con Mozilla Public License 2.0 (https://mozilla.org/MPL/2.0/).
 Questo porting e' un'opera derivata: ogni classe riporta la licenza del
 proprio script di origine.  Usare il file nel rispetto di tali licenze
 (in particolare: niente uso commerciale delle parti CC BY-NC-SA).
===============================================================================
"""

import argparse
import json
import logging
import math
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import timedelta, timezone
from typing import Annotated, Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

try:  # numpy >= 1.20
    from numpy.lib.stride_tricks import sliding_window_view as _swv
except ImportError:  # pragma: no cover
    _swv = None

log = logging.getLogger("unified_indicators")

__version__ = "1.0.0"

NAN = float("nan")


# =============================================================================
# SEZIONE 0 - Utility generiche
# =============================================================================

def _isnan(x: Any) -> bool:
    """True se x e' None o NaN (funziona con float Python e numpy)."""
    if x is None:
        return True
    try:
        return math.isnan(x)
    except TypeError:
        return False


def _nz(x: Any, repl: float = 0.0) -> float:
    """Equivalente di nz() di Pine."""
    return repl if _isnan(x) else x


def _clip(x: float, lo: float = -1.0, hi: float = 1.0) -> float:
    if _isnan(x):
        return 0.0
    return max(lo, min(hi, x))


def _sign(x: float) -> int:
    if _isnan(x):
        return 0
    return 1 if x > 0 else (-1 if x < 0 else 0)


def _pine_round(x: float) -> int:
    """math.round di Pine: arrotonda .5 lontano da zero (Python usa il banker's rounding)."""
    if x >= 0:
        return int(math.floor(x + 0.5))
    return -int(math.floor(-x + 0.5))


def _decay(bars_ago: Optional[int], window: int) -> float:
    """Peso lineare 1 -> 0 per un evento avvenuto bars_ago barre fa."""
    if bars_ago is None or bars_ago < 0 or window <= 0:
        return 0.0
    return max(0.0, 1.0 - bars_ago / float(window))


def _safe_div(a: float, b: float, default: float = 0.0) -> float:
    if b == 0 or _isnan(b) or _isnan(a):
        return default
    return a / b


def _to_py(obj: Any) -> Any:
    """Converte ricorsivamente numpy/pandas in tipi Python JSON-friendly (NaN -> None)."""
    if isinstance(obj, dict):
        return {str(k): _to_py(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_py(v) for v in obj]
    if isinstance(obj, np.ndarray):
        return [_to_py(v) for v in obj.tolist()]
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating, float)):
        f = float(obj)
        return None if (math.isnan(f) or math.isinf(f)) else f
    if isinstance(obj, (pd.Timestamp,)):
        return obj.isoformat()
    if hasattr(obj, "to_dict") and callable(obj.to_dict):
        return _to_py(obj.to_dict())
    return obj


def _fmt(x: Any, nd: Optional[int] = None) -> str:
    """Formattazione compatta per il report (decimali adattivi al livello di prezzo)."""
    if x is None or _isnan(x):
        return "n/d"
    if isinstance(x, (bool, np.bool_)):
        return str(bool(x))
    if isinstance(x, (int, np.integer)):
        return str(int(x))
    x = float(x)
    ax = abs(x)
    if nd is None:
        nd = 2 if ax >= 1000 else 3 if ax >= 100 else 4 if ax >= 10 else 5 if ax >= 0.1 else 6
    return f"{x:,.{nd}f}"


# =============================================================================
# SEZIONE 1 - Primitive tecniche che replicano le funzioni ta.* di Pine
# =============================================================================
# Convenzioni: tutti gli array sono numpy float64 lunghi quanto la serie,
# con NaN dove Pine restituirebbe "na".  Indice 0 = barra piu' vecchia.

def _arr(x: Any) -> np.ndarray:
    return np.asarray(x, dtype=float)


def shift(x: np.ndarray, k: int = 1) -> np.ndarray:
    """x[k] di Pine (valore di k barre fa)."""
    x = _arr(x)
    out = np.full_like(x, np.nan)
    if k <= 0:
        return x.copy()
    if k < len(x):
        out[k:] = x[:-k]
    return out


def change(x: np.ndarray, k: int = 1) -> np.ndarray:
    return _arr(x) - shift(x, k)


def sma(x: np.ndarray, n: int) -> np.ndarray:
    return pd.Series(_arr(x)).rolling(int(n), min_periods=int(n)).mean().to_numpy()


def stdev(x: np.ndarray, n: int) -> np.ndarray:
    """ta.stdev (popolazione, biased=true)."""
    return pd.Series(_arr(x)).rolling(int(n), min_periods=int(n)).std(ddof=0).to_numpy()


def highest(x: np.ndarray, n: int) -> np.ndarray:
    return pd.Series(_arr(x)).rolling(int(n), min_periods=int(n)).max().to_numpy()


def lowest(x: np.ndarray, n: int) -> np.ndarray:
    return pd.Series(_arr(x)).rolling(int(n), min_periods=int(n)).min().to_numpy()


def rolling_median(x: np.ndarray, n: int) -> np.ndarray:
    return pd.Series(_arr(x)).rolling(int(n), min_periods=int(n)).median().to_numpy()


def percentile_linear(x: np.ndarray, n: int, pct: float) -> np.ndarray:
    return pd.Series(_arr(x)).rolling(int(n), min_periods=int(n)).quantile(pct / 100.0).to_numpy()


def _recursive_ma(x: np.ndarray, n: int, alpha: float) -> np.ndarray:
    """Media esponenziale inizializzata con la SMA delle prime n barre valide (come ta.rma)."""
    xs = _arr(x).tolist()
    out = [NAN] * len(xs)
    prev = NAN
    run: List[float] = []
    for i, v in enumerate(xs):
        if math.isnan(prev):
            if math.isnan(v):
                run = []
                continue
            run.append(v)
            if len(run) >= n:
                prev = sum(run[-n:]) / n
                out[i] = prev
        else:
            if not math.isnan(v):
                prev = alpha * v + (1.0 - alpha) * prev
            out[i] = prev
    return np.asarray(out, dtype=float)


def rma(x: np.ndarray, n: int) -> np.ndarray:
    """ta.rma (Wilder)."""
    n = max(1, int(n))
    return _recursive_ma(x, n, 1.0 / n)


def ema(x: np.ndarray, n: int) -> np.ndarray:
    """ta.ema (inizializzata con SMA, differenze trascurabili dopo il warm-up)."""
    n = max(1, int(n))
    return _recursive_ma(x, n, 2.0 / (n + 1.0))


def wma(x: np.ndarray, n: int) -> np.ndarray:
    x = _arr(x)
    n = int(n)
    out = np.full_like(x, np.nan)
    if n < 1 or len(x) < n:
        return out
    w = np.arange(1, n + 1, dtype=float)
    win = _swv(x, n)
    out[n - 1:] = win @ w / w.sum()
    return out


def hma(x: np.ndarray, n: int) -> np.ndarray:
    n = int(n)
    half = max(1, n // 2)
    return wma(2.0 * wma(x, half) - wma(x, n), max(1, _pine_round(math.sqrt(n))))


def vwma(x: np.ndarray, v: np.ndarray, n: int) -> np.ndarray:
    return sma(_arr(x) * _arr(v), n) / sma(v, n)


def linreg(x: np.ndarray, n: int, offset: int = 0) -> np.ndarray:
    """ta.linreg(src, length, offset)."""
    x = _arr(x)
    n = int(n)
    out = np.full_like(x, np.nan)
    if n < 2 or len(x) < n:
        return out
    t = np.arange(n, dtype=float)
    win = _swv(x, n)
    tm = t.mean()
    ym = win.mean(axis=1)
    slope = ((win - ym[:, None]) * (t - tm)).sum(axis=1) / ((t - tm) ** 2).sum()
    intercept = ym - slope * tm
    out[n - 1:] = intercept + slope * (n - 1 - offset)
    return out


def true_range(h: np.ndarray, l: np.ndarray, c: np.ndarray, handle_na: bool = True) -> np.ndarray:
    h, l, c = _arr(h), _arr(l), _arr(c)
    pc = shift(c, 1)
    tr = np.fmax(h - l, np.fmax(np.abs(h - pc), np.abs(l - pc)))
    if len(tr):
        tr[0] = (h[0] - l[0]) if handle_na else np.nan
    return tr


def atr(h: np.ndarray, l: np.ndarray, c: np.ndarray, n: int) -> np.ndarray:
    return rma(true_range(h, l, c, True), n)


def rsi(x: np.ndarray, n: int) -> np.ndarray:
    ch = change(x)
    up = rma(np.where(np.isnan(ch), np.nan, np.maximum(ch, 0.0)), n)
    dn = rma(np.where(np.isnan(ch), np.nan, np.maximum(-ch, 0.0)), n)
    with np.errstate(divide="ignore", invalid="ignore"):
        r = 100.0 - 100.0 / (1.0 + up / dn)
    r = np.where(dn == 0, 100.0, r)
    r = np.where((up == 0) & (dn != 0), 0.0, r)
    r[np.isnan(up) | np.isnan(dn)] = np.nan
    return r


def macd(x: np.ndarray, fast: int, slow: int, sig: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    m = ema(x, fast) - ema(x, slow)
    s = ema(m, sig)
    return m, s, m - s


def bollinger(x: np.ndarray, n: int, mult: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    basis = sma(x, n)
    dev = mult * stdev(x, n)
    return basis, basis + dev, basis - dev


def stoch(c: np.ndarray, h: np.ndarray, l: np.ndarray, n: int) -> np.ndarray:
    ll, hh = lowest(l, n), highest(h, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        k = 100.0 * (_arr(c) - ll) / (hh - ll)
    k[~np.isfinite(k)] = np.nan
    return k


def cci(x: np.ndarray, n: int) -> np.ndarray:
    x = _arr(x)
    n = int(n)
    out = np.full_like(x, np.nan)
    if len(x) < n:
        return out
    win = _swv(x, n)
    m = win.mean(axis=1)
    dev = np.abs(win - m[:, None]).mean(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        out[n - 1:] = (x[n - 1:] - m) / (0.015 * dev)
    out[~np.isfinite(out)] = np.nan
    return out


def supertrend(h: np.ndarray, l: np.ndarray, c: np.ndarray, factor: float, n: int) -> Tuple[np.ndarray, np.ndarray]:
    """ta.supertrend: restituisce (linea, direzione) con direzione -1 = rialzo, +1 = ribasso."""
    a = atr(h, l, c, n).tolist()
    hs, ls, cs = _arr(h).tolist(), _arr(l).tolist(), _arr(c).tolist()
    size = len(cs)
    st_out = [NAN] * size
    dir_out = [NAN] * size
    prev_lower = prev_upper = prev_st = NAN
    for i in range(size):
        src = (hs[i] + ls[i]) / 2.0
        up = src + factor * a[i]
        lo = src - factor * a[i]
        pl = 0.0 if math.isnan(prev_lower) else prev_lower
        pu = 0.0 if math.isnan(prev_upper) else prev_upper
        c1 = cs[i - 1] if i > 0 else NAN
        lo = lo if (lo > pl or c1 < pl) else pl
        up = up if (up < pu or c1 > pu) else pu
        if i == 0 or math.isnan(a[i - 1]):
            d = 1
        elif prev_st == pu:
            d = -1 if cs[i] > up else 1
        else:
            d = 1 if cs[i] < lo else -1
        st = lo if d == -1 else up
        st_out[i], dir_out[i] = st, d
        prev_lower, prev_upper, prev_st = lo, up, st
    return np.asarray(st_out), np.asarray(dir_out)


def parabolic_sar(h: np.ndarray, l: np.ndarray, c: np.ndarray, start: float, inc: float, maxv: float) -> np.ndarray:
    """ta.sar (porting della reference implementation di Pine)."""
    hs, ls, cs = _arr(h).tolist(), _arr(l).tolist(), _arr(c).tolist()
    size = len(cs)
    out = [NAN] * size
    result = max_min = acc = NAN
    is_below = False
    for i in range(1, size):
        first = False
        if i == 1:
            if cs[1] > cs[0]:
                is_below, max_min, result = True, hs[1], ls[0]
            else:
                is_below, max_min, result = False, ls[1], hs[0]
            first = True
            acc = start
        result = result + acc * (max_min - result)
        if is_below:
            if result > ls[i]:
                first, is_below = True, False
                result = max(hs[i], max_min)
                max_min, acc = ls[i], start
        else:
            if result < hs[i]:
                first, is_below = True, True
                result = min(ls[i], max_min)
                max_min, acc = hs[i], start
        if not first:
            if is_below:
                if hs[i] > max_min:
                    max_min = hs[i]
                    acc = min(acc + inc, maxv)
            else:
                if ls[i] < max_min:
                    max_min = ls[i]
                    acc = min(acc + inc, maxv)
        if is_below:
            result = min(result, ls[i - 1])
            if i > 1:
                result = min(result, ls[i - 2])
        else:
            result = max(result, hs[i - 1])
            if i > 1:
                result = max(result, hs[i - 2])
        out[i] = result
    return np.asarray(out)


def dmi(h: np.ndarray, l: np.ndarray, c: np.ndarray, di_len: int, adx_len: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """ta.dmi -> (+DI, -DI, ADX)."""
    up = change(h)
    down = -change(l)
    plus_dm = np.where(np.isnan(up), np.nan, np.where((up > down) & (up > 0), up, 0.0))
    minus_dm = np.where(np.isnan(down), np.nan, np.where((down > up) & (down > 0), down, 0.0))
    trur = rma(true_range(h, l, c, False), di_len)
    with np.errstate(divide="ignore", invalid="ignore"):
        plus = pd.Series(100.0 * rma(plus_dm, di_len) / trur).ffill().to_numpy()
        minus = pd.Series(100.0 * rma(minus_dm, di_len) / trur).ffill().to_numpy()
        s = plus + minus
        adx = 100.0 * rma(np.abs(plus - minus) / np.where(s == 0, 1.0, s), adx_len)
    return plus, minus, adx


def pivothigh(src: np.ndarray, left: int, right: int) -> np.ndarray:
    """ta.pivothigh: valore del pivot sulla barra di CONFERMA (right barre dopo il pivot).
    Pari merito: il pivot deve essere >= delle barre a sinistra e > di quelle a destra."""
    x = _arr(src)
    out = np.full_like(x, np.nan)
    k = left + right + 1
    if len(x) < k:
        return out
    win = _swv(x, k)
    center = win[:, left]
    with np.errstate(invalid="ignore"):
        lmax = win[:, :left].max(axis=1) if left > 0 else np.full(len(win), -np.inf)
        rmax = win[:, left + 1:].max(axis=1) if right > 0 else np.full(len(win), -np.inf)
        ok = (center >= lmax) & (center > rmax) & ~np.isnan(center)
    out[k - 1:] = np.where(ok, center, np.nan)
    return out


def pivotlow(src: np.ndarray, left: int, right: int) -> np.ndarray:
    x = _arr(src)
    out = np.full_like(x, np.nan)
    k = left + right + 1
    if len(x) < k:
        return out
    win = _swv(x, k)
    center = win[:, left]
    with np.errstate(invalid="ignore"):
        lmin = win[:, :left].min(axis=1) if left > 0 else np.full(len(win), np.inf)
        rmin = win[:, left + 1:].min(axis=1) if right > 0 else np.full(len(win), np.inf)
        ok = (center <= lmin) & (center < rmin) & ~np.isnan(center)
    out[k - 1:] = np.where(ok, center, np.nan)
    return out


def crossover(a: np.ndarray, b: Any) -> np.ndarray:
    a = _arr(a)
    b = _arr(b) if np.ndim(b) else np.full_like(a, float(b))
    with np.errstate(invalid="ignore"):
        return (a > b) & (shift(a) <= shift(b))


def crossunder(a: np.ndarray, b: Any) -> np.ndarray:
    a = _arr(a)
    b = _arr(b) if np.ndim(b) else np.full_like(a, float(b))
    with np.errstate(invalid="ignore"):
        return (a < b) & (shift(a) >= shift(b))


def barssince(cond: np.ndarray) -> np.ndarray:
    """ta.barssince: barre dall'ultima volta che cond era vera (NaN se mai)."""
    out = np.full(len(cond), np.nan)
    last = -1
    for i, v in enumerate(cond):
        if v:
            last = i
        if last >= 0:
            out[i] = i - last
    return out


def anchored_vwap(src: np.ndarray, vol: np.ndarray, reset: np.ndarray, mult: float) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """ta.vwap(src, anchor, stdev_mult) -> (vwap, upper, lower, stdev)."""
    s, v = _arr(src).tolist(), _arr(vol).tolist()
    size = len(s)
    vw, sd = [NAN] * size, [NAN] * size
    sv = spv = sp2v = 0.0
    for i in range(size):
        if reset[i] or i == 0:
            sv = spv = sp2v = 0.0
        vi = 0.0 if math.isnan(v[i]) else v[i]
        sv += vi
        spv += s[i] * vi
        sp2v += s[i] * s[i] * vi
        if sv > 0:
            m = spv / sv
            vw[i] = m
            sd[i] = math.sqrt(max(sp2v / sv - m * m, 0.0))
    vw_a, sd_a = np.asarray(vw), np.asarray(sd)
    return vw_a, vw_a + mult * sd_a, vw_a - mult * sd_a, sd_a


def moving_average(kind: str, x: np.ndarray, n: int, vol: Optional[np.ndarray] = None) -> np.ndarray:
    kind = kind.upper()
    if kind == "EMA":
        return ema(x, n)
    if kind == "RMA":
        return rma(x, n)
    if kind == "WMA":
        return wma(x, n)
    if kind == "HMA":
        return hma(x, n)
    if kind == "VWMA" and vol is not None:
        return vwma(x, vol, n)
    if kind == "LSMA":
        return linreg(x, n, 0)
    return sma(x, n)


def value_area(bins: np.ndarray, pct: float = 70.0) -> Tuple[int, int, int]:
    """POC e Value Area (espansione dal POC verso il lato con piu' volume). -> (poc, lo_idx, hi_idx)."""
    bins = _arr(bins)
    if len(bins) == 0 or np.nansum(bins) <= 0:
        return 0, 0, max(0, len(bins) - 1)
    poc = int(np.nanargmax(bins))
    target = np.nansum(bins) * pct / 100.0
    acc = bins[poc]
    lo = hi = poc
    while acc < target:
        up_v = bins[hi + 1] if hi + 1 < len(bins) else -1.0
        dn_v = bins[lo - 1] if lo - 1 >= 0 else -1.0
        if up_v < 0 and dn_v < 0:
            break
        if up_v >= dn_v:
            hi += 1
            acc += up_v
        else:
            lo -= 1
            acc += dn_v
    return poc, lo, hi


# =============================================================================
# SEZIONE 2 - Tempo, fusi orari e sessioni
# =============================================================================

_TZ_RE = re.compile(r"^(UTC|GMT)\s*([+-])\s*(\d{1,2})(?::?(\d{2}))?$")


def resolve_tz(name: Any) -> Any:
    """Converte "UTC-5", "GMT+2", "UTC", "America/New_York" in un oggetto tz usabile da pandas.
    Nota: come in Pine, "GMT-4" significa UTC-4 (non la convenzione invertita Etc/GMT)."""
    if name is None:
        return timezone.utc
    if not isinstance(name, str):
        return name
    s = name.strip()
    up = s.upper()
    if up in ("UTC", "GMT", "Z"):
        return timezone.utc
    m = _TZ_RE.match(up)
    if m:
        sign = 1 if m.group(2) == "+" else -1
        hours = int(m.group(3))
        minutes = int(m.group(4) or 0)
        return timezone(sign * timedelta(hours=hours, minutes=minutes))
    return s  # nome IANA, gestito da pandas/zoneinfo


def localize_index(idx: pd.DatetimeIndex, tz: Any) -> pd.DatetimeIndex:
    """tz_localize tollerante ai cambi di ora legale (orari inesistenti/ambigui)."""
    tzv = resolve_tz(tz)
    try:
        return idx.tz_localize(tzv)
    except Exception:
        return idx.tz_localize(tzv, ambiguous=np.zeros(len(idx), dtype=bool), nonexistent="shift_forward")


def _parse_session(sess: str) -> Tuple[int, int]:
    """"0930-1600" -> (570, 960) minuti dalla mezzanotte."""
    core = sess.split(":")[0].strip()
    a, b = core.split("-")
    return int(a[:2]) * 60 + int(a[2:4]), int(b[:2]) * 60 + int(b[2:4])


def session_mask(local_idx: pd.DatetimeIndex, bar_minutes: float, sess: str, days: Optional[str] = None) -> np.ndarray:
    """True se la barra [inizio, inizio+durata) si sovrappone alla sessione (ora locale).
    days: stringa stile Pine "1234567" (1 = domenica)."""
    start, end = _parse_session(sess)
    tod = (local_idx.hour * 60 + local_idx.minute).to_numpy().astype(float)
    bar_end = tod + max(bar_minutes, 1.0)
    if start < end:
        mask = (tod < end) & (bar_end > start)
    else:  # sessione a cavallo della mezzanotte
        mask = (bar_end > start) | (tod < end)
    if days:
        pine_dow = ((local_idx.dayofweek.to_numpy() + 1) % 7) + 1  # lun=2 ... dom=1
        allowed = np.array([int(ch) for ch in days if ch.isdigit()])
        mask &= np.isin(pine_dow, allowed)
    return mask


# =============================================================================
# SEZIONE 3 - Normalizzazione dei dati e contenitore MarketData
# =============================================================================

def normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    """Rende standard un DataFrame OHLCV (MT5, CSV, yfinance ...).
    Output: colonne open/high/low/close/volume float, DatetimeIndex ordinato."""
    if df is None or len(df) == 0:
        raise ValueError("DataFrame vuoto")
    d = df.copy()
    d.columns = [str(c).strip().lower().replace(" ", "_") for c in d.columns]
    rename = {"o": "open", "h": "high", "l": "low", "c": "close", "adj_close": "adj_close",
              "datetime": "time", "date": "time", "timestamp": "time"}
    d = d.rename(columns={k: v for k, v in rename.items() if k in d.columns and v not in d.columns})
    for col in ("open", "high", "low", "close"):
        if col not in d.columns:
            raise ValueError(f"Colonna mancante: {col}")
    if "volume" not in d.columns:
        rv = d["real_volume"] if "real_volume" in d.columns else None
        tv = d["tick_volume"] if "tick_volume" in d.columns else None
        if rv is not None and float(pd.to_numeric(rv, errors="coerce").fillna(0).sum()) > 0:
            d["volume"] = rv
        elif tv is not None:
            d["volume"] = tv
        elif "vol" in d.columns:
            d["volume"] = d["vol"]
        else:
            d["volume"] = 1.0
            log.warning("Nessuna colonna di volume: uso volume=1 (i moduli di volume perdono significato)")
    if not isinstance(d.index, pd.DatetimeIndex):
        if "time" in d.columns:
            t = d["time"]
            if np.issubdtype(t.dtype, np.number):
                idx = pd.to_datetime(t.astype("int64"), unit="s")
            else:
                idx = pd.to_datetime(t)
            d.index = pd.DatetimeIndex(idx)
        else:
            log.warning("Nessun timestamp: genero un indice orario sintetico (sessioni non affidabili)")
            d.index = pd.date_range("2000-01-03", periods=len(d), freq="h")
    d = d[~d.index.duplicated(keep="last")].sort_index()
    for col in ("open", "high", "low", "close", "volume"):
        d[col] = pd.to_numeric(d[col], errors="coerce").astype(float)
    d = d.dropna(subset=["open", "high", "low", "close"])
    d["volume"] = d["volume"].fillna(0.0).clip(lower=0.0)
    return d[["open", "high", "low", "close", "volume"]]


def _infer_mintick(close: np.ndarray) -> float:
    """Stima del tick minimo dal numero di decimali dei prezzi (fallback se MT5 non lo fornisce)."""
    sample = close[-500:] if len(close) > 500 else close
    digits = 0
    for v in sample:
        if math.isnan(v):
            continue
        s = f"{v:.8f}".rstrip("0")
        if "." in s:
            digits = max(digits, len(s.split(".")[1]))
    return 10.0 ** (-min(digits, 8)) if digits > 0 else 1.0


class MarketData:
    """Contenitore dei dati con cache delle serie condivise (ATR, orari locali ...)."""

    def __init__(self, df: pd.DataFrame, data_tz: Any = "UTC", mintick: Optional[float] = None,
                 symbol: Optional[str] = None, timeframe: Optional[str] = None):
        raw_attrs = dict(getattr(df, "attrs", {}) or {})
        d = normalize_ohlcv(df)
        self.df = d
        self.data_tz = data_tz
        self.symbol = symbol or raw_attrs.get("symbol")
        self.timeframe = timeframe or raw_attrs.get("timeframe")
        self.open = d["open"].to_numpy(dtype=float)
        self.high = d["high"].to_numpy(dtype=float)
        self.low = d["low"].to_numpy(dtype=float)
        self.close = d["close"].to_numpy(dtype=float)
        self.volume = d["volume"].to_numpy(dtype=float)
        self.n = len(d)
        idx = pd.DatetimeIndex(d.index)
        if idx.tz is None:
            idx = localize_index(idx, data_tz)
        elif data_tz in (None, "UTC"):
            self.data_tz = idx.tz          # indice gia' con fuso: e' quello "nativo" dei dati
        self.time_utc = idx.tz_convert("UTC")
        diffs = pd.Series(self.time_utc).diff().dt.total_seconds().to_numpy()[1:]
        diffs = diffs[diffs > 0]
        self.bar_seconds = float(np.median(diffs)) if len(diffs) else 3600.0
        self.mintick = float(mintick or raw_attrs.get("mintick") or raw_attrs.get("point") or _infer_mintick(self.close))
        self._cache: Dict[Any, Any] = {}

    # --- serie derivate con cache ------------------------------------------
    @property
    def hl2(self) -> np.ndarray:
        return self._cached("hl2", lambda: (self.high + self.low) / 2.0)

    @property
    def hlc3(self) -> np.ndarray:
        return self._cached("hlc3", lambda: (self.high + self.low + self.close) / 3.0)

    def _cached(self, key: Any, fn):
        if key not in self._cache:
            self._cache[key] = fn()
        return self._cache[key]

    def atr(self, n: int) -> np.ndarray:
        return self._cached(("atr", n), lambda: atr(self.high, self.low, self.close, n))

    def tr(self, handle_na: bool = True) -> np.ndarray:
        return self._cached(("tr", handle_na), lambda: true_range(self.high, self.low, self.close, handle_na))

    def local_index(self, tz: Any) -> pd.DatetimeIndex:
        return self._cached(("tz", str(tz)), lambda: self.time_utc.tz_convert(resolve_tz(tz)))

    @property
    def bar_minutes(self) -> float:
        return self.bar_seconds / 60.0

    @property
    def is_intraday(self) -> bool:
        return self.bar_seconds < 86400

    def last_atr(self, n: int = 14) -> float:
        a = self.atr(n)
        v = a[-1] if len(a) else NAN
        if _isnan(v):
            v = float(np.nanmean(self.high - self.low)) if self.n else NAN
        return float(v)

    def ts(self, i: int) -> Optional[str]:
        if 0 <= i < self.n:
            return self.time_utc[i].isoformat()
        return None


# =============================================================================
# SEZIONE 4 - Tipi standard dei risultati e classe base dei moduli
# =============================================================================

@dataclass
class Signal:
    """Evento discreto emesso da un modulo."""
    module: str
    name: str
    direction: int          # +1 rialzista, -1 ribassista, 0 neutro/informativo
    bar_index: int
    bars_ago: int
    price: float = NAN
    strength: float = 1.0   # 0..1
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return _to_py(self.__dict__)


@dataclass
class Level:
    """Livello (o zona se top/bottom sono valorizzati) di prezzo."""
    module: str
    name: str
    price: float
    kind: str = "level"     # support | resistance | magnet | target | pivot | band | level
    weight: float = 1.0
    top: float = NAN
    bottom: float = NAN
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return _to_py(self.__dict__)


@dataclass
class ModuleResult:
    key: str
    title: str
    style: str
    bias: float = 0.0
    confidence: float = 0.0
    regime: Optional[float] = None
    regime_confidence: float = 0.0
    volatility: Optional[float] = None
    signals: List[Signal] = field(default_factory=list)
    levels: List[Level] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)
    applicable: bool = True
    error: Optional[str] = None

    def add_signal(self, md: "MarketData", name: str, direction: int, idx: int, price: float = NAN,
                   strength: float = 1.0, note: str = "") -> None:
        self.signals.append(Signal(self.key, name, int(direction), int(idx), int(md.n - 1 - idx),
                                   float(price), float(strength), note))

    def add_level(self, name: str, price: float, kind: str = "level", weight: float = 1.0,
                  top: float = NAN, bottom: float = NAN, note: str = "") -> None:
        if price is None or _isnan(price):
            return
        self.levels.append(Level(self.key, name, float(price), kind, float(weight), float(top), float(bottom), note))

    def recent_signals(self, max_bars: int) -> List[Signal]:
        return [s for s in self.signals if s.bars_ago <= max_bars]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key, "title": self.title, "style": self.style,
            "bias": _to_py(round(self.bias, 4)), "confidence": _to_py(round(self.confidence, 4)),
            "regime": _to_py(self.regime), "regime_confidence": _to_py(self.regime_confidence),
            "volatility": _to_py(self.volatility), "applicable": self.applicable, "error": self.error,
            "signals": [s.to_dict() for s in self.signals[-15:]],
            "levels": [lv.to_dict() for lv in self.levels],
            "metrics": _to_py(self.metrics), "notes": list(self.notes),
        }


MODULE_REGISTRY: Dict[str, type] = {}


def register_module(cls: type) -> type:
    """Decoratore: registra un modulo nel motore unificato."""
    MODULE_REGISTRY[cls.key] = cls
    return cls


class IndicatorModule:
    """Classe base.  Ogni modulo definisce key, title, style, source e una dataclass Params."""
    key: str = ""
    title: str = ""
    style: str = "structure"   # trend | momentum | breakout | reversion | hybrid | structure | volume | ensemble | volatility
    source: str = "LuxAlgo"
    license: str = "CC BY-NC-SA 4.0"
    batch: int = 0
    min_bars: int = 50

    @dataclass
    class Params:
        pass

    def __init__(self, **params: Any):
        self.params = self.Params(**params)

    def new_result(self) -> ModuleResult:
        return ModuleResult(key=self.key, title=self.title, style=self.style)

    def compute(self, md: MarketData) -> ModuleResult:  # pragma: no cover - astratto
        raise NotImplementedError

    def run(self, md: MarketData) -> ModuleResult:
        """compute() protetto: un errore in un modulo non blocca gli altri."""
        if md.n < self.min_bars:
            r = self.new_result()
            r.applicable = False
            r.error = f"dati insufficienti ({md.n} barre < {self.min_bars})"
            return r
        try:
            r = self.compute(md)
            r.bias = _clip(r.bias)
            r.confidence = _clip(r.confidence, 0.0, 1.0)
            if r.regime is not None:
                r.regime = _clip(r.regime)
            if r.volatility is not None:
                r.volatility = _clip(r.volatility)
            return r
        except Exception as exc:  # pragma: no cover - robustezza in produzione
            log.exception("Errore nel modulo %s", self.key)
            r = self.new_result()
            r.applicable = False
            r.error = f"{type(exc).__name__}: {exc}"
            return r


def _trade_stats(profits: Sequence[float]) -> Dict[str, float]:
    """Statistiche standard da una lista di rendimenti per trade (frazioni o %)."""
    p = [float(x) for x in profits]
    n = len(p)
    wins = sum(1 for x in p if x > 0)
    gp = sum(x for x in p if x > 0)
    gl = sum(-x for x in p if x <= 0)
    net = sum(p)
    eq, peak, dd = 0.0, 0.0, 0.0
    for x in p:
        eq += x
        peak = max(peak, eq)
        dd = max(dd, peak - eq)
    mean = net / n if n else 0.0
    sd = math.sqrt(sum((x - mean) ** 2 for x in p) / n) if n else 0.0
    return {
        "trades": n, "wins": wins, "win_rate": (wins * 100.0 / n) if n else 0.0,
        "net": net, "gross_profit": gp, "gross_loss": gl,
        "profit_factor": (gp / gl) if gl > 0 else (999.0 if gp > 0 else 0.0),
        "avg_trade": mean, "sharpe": (mean / sd) if sd > 0 else 0.0, "max_dd": dd,
    }


# =============================================================================
# SEZIONE 5 - BATCH 1
# =============================================================================

@register_module
class VolumetricRegressionHeatmap(IndicatorModule):
    """
    Volumetric Regression Heatmap [LuxAlgo]  -  (c) LuxAlgo, CC BY-NC-SA 4.0

    COME FUNZIONA (Pine)
      * Periodo dinamico: L = round(400 * ATR(200)/ATR(20)) limitato a [50, 1000]:
        con volatilita' corrente alta il canale si accorcia, con volatilita'
        bassa si allunga.
      * Regressione lineare di hl2 sulle ultime L barre -> linea centrale;
        deviazione standard (di popolazione) di hl2 sulla finestra.
      * Canale = centro +/- 3 sd diviso in 2*40 "bin"; il volume di ogni barra
        viene assegnato al bin della sua distanza dalla retta, poi smussato con
        un kernel binomiale [1,4,6,4,1]/16 ripetuto 4 volte -> heatmap.
      * Stato: |salita totale della retta| < 2.5 * sd  =>  CONTRACTION (canale
        piatto, laterale) altrimenti EXPANSION (trend).
      * Segnali di mean-reversion SOLO in contraction: chiusura che rompe sotto
        la banda -2 sd (verde, comprare) o sopra +2 sd (rosso, vendere).
      * Istogrammi buy/sell volume con il proxy della posizione della chiusura.

    COSA RESTITUISCE QUI
      regime (piattezza del canale), bias misto trend/mean-reversion, z-score
      del prezzo nel canale, POC/VAH/VAL del profilo "rispetto alla retta"
      proiettati sulla barra attuale, delta volumetrico recente, livelli del
      canale (centro, +/-2 sd, +/-3 sd).

    LIMITI
      Il canale viene ricalcolato ad ogni barra: i segnali storici sono
      disegnati rispetto alla retta ATTUALE (repaint).  Qui si usano solo i
      segnali delle ultime barre.
    """
    key = "vrh"
    title = "Volumetric Regression Heatmap"
    style = "hybrid"
    batch = 1
    min_bars = 120

    @dataclass
    class Params:
        base_length: int = 400
        dynamic_length: bool = True
        num_bins: int = 40
        smooth_bins: int = 4
        signal_band: float = 2.0
        slope_threshold: float = 2.5
        recent_signal_bars: int = 3
        delta_lookback: int = 20
        value_area_pct: float = 70.0

    def compute(self, md: MarketData) -> ModuleResult:
        p, r = self.params, self.new_result()
        n, t = md.n, md.n - 1
        src, c, v = md.hl2, md.close, md.volume
        af, aslow = _nz(md.atr(20)[t]), _nz(md.atr(200)[t])
        length = p.base_length
        if p.dynamic_length and af > 0 and aslow > 0:
            length = max(50, min(_pine_round(p.base_length * aslow / af), 1000))
        length_req = length
        length = min(length, n)
        w = src[n - length:]
        x = np.arange(length, dtype=float)
        sx, sy, sxy, sx2 = x.sum(), w.sum(), (x * w).sum(), (x * x).sum()
        den = length * sx2 - sx * sx
        m = (length * sxy - sx * sy) / den if length > 1 and den != 0 else 0.0
        b = (sy - m * sx) / length
        start, end = b, b + m * (length - 1)
        sd = float(np.std(w))
        pred = start + m * x
        total_rise = abs(end - start)
        contraction = total_rise < sd * p.slope_threshold
        ratio = total_rise / (sd * p.slope_threshold) if sd > 0 else 0.0
        z = (c[t] - end) / sd if sd > 0 else 0.0

        # --- segnali di mean reversion (solo in contraction, ultime 100 barre) ---
        last_bull = last_bear = None
        if contraction and length > 1:
            cw = c[n - length:]
            up_b = pred + sd * p.signal_band
            lo_b = pred - sd * p.signal_band
            cu = (cw[:-1] >= lo_b[:-1]) & (cw[1:] < lo_b[1:])
            co = (cw[:-1] <= up_b[:-1]) & (cw[1:] > up_b[1:])
            for k in np.nonzero(cu)[0]:
                idx = n - length + int(k) + 1
                if t - idx <= 100:
                    r.add_signal(md, "MR_BUY", 1, idx, md.low[idx], note="chiusura sotto -2sd in canale piatto")
                    last_bull = t - idx
            for k in np.nonzero(co)[0]:
                idx = n - length + int(k) + 1
                if t - idx <= 100:
                    r.add_signal(md, "MR_SELL", -1, idx, md.high[idx], note="chiusura sopra +2sd in canale piatto")
                    last_bear = t - idx

        # --- profilo volumetrico rispetto alla retta ---
        nb = p.num_bins
        bins = np.zeros(2 * nb)
        dev = 3.0 * sd / nb
        vw = np.nan_to_num(v[n - length:])
        if dev > 0:
            bi = np.floor((w - pred) / dev).astype(int) + nb
            ok = (bi >= 0) & (bi < 2 * nb)
            np.add.at(bins, bi[ok], vw[ok])
        sm = bins.copy()
        for _ in range(p.smooth_bins):
            tmp = sm.copy()
            size = len(tmp)
            for i in range(size):
                val = tmp[i]
                l1 = tmp[i - 1] if i > 0 else val
                r1 = tmp[i + 1] if i < size - 1 else val
                l2 = tmp[i - 2] if i > 1 else l1
                r2 = tmp[i + 2] if i < size - 2 else r1
                sm[i] = (l2 + l1 * 4.0 + val * 6.0 + r1 * 4.0 + r2) / 16.0
        poc = vah = val_ = NAN
        if sm.max() > 0 and dev > 0:
            pb, lo_i, hi_i = value_area(sm, p.value_area_pct)
            poc = end + (pb - nb) * dev + dev / 2.0
            vah = end + (hi_i - nb) * dev + dev
            val_ = end + (lo_i - nb) * dev

        # --- delta buy/sell (proxy close location) ---
        hw, lw, cw2 = md.high[n - length:], md.low[n - length:], c[n - length:]
        rng = hw - lw
        with np.errstate(divide="ignore", invalid="ignore"):
            buy = np.where(rng == 0, vw / 2.0, vw * (cw2 - lw) / rng)
            sell = np.where(rng == 0, vw / 2.0, vw * (hw - cw2) / rng)
        tot = buy.sum() + sell.sum()
        delta_window = _safe_div(buy.sum() - sell.sum(), tot)
        k = min(p.delta_lookback, length)
        tot_r = buy[-k:].sum() + sell[-k:].sum()
        delta_recent = _safe_div(buy[-k:].sum() - sell[-k:].sum(), tot_r)

        # --- bias / regime ---
        trend_bias = _sign(m) * _clip(ratio - 0.5, 0.0, 1.0)
        mr_bias = -_clip(z / 2.0)
        if contraction:
            bias = 0.65 * mr_bias + 0.35 * trend_bias
            if last_bull is not None and last_bull <= p.recent_signal_bars:
                bias = max(bias, 0.8)
            if last_bear is not None and last_bear <= p.recent_signal_bars:
                bias = min(bias, -0.8)
        else:
            bias = 0.75 * trend_bias + 0.25 * mr_bias
        r.bias = bias + 0.15 * delta_recent
        r.regime = _clip(ratio - 1.0)
        r.regime_confidence = 0.7
        r.confidence = 0.6 if length == length_req else 0.4
        if np.nansum(v) <= 0:
            r.confidence = min(r.confidence, 0.4)

        band = p.signal_band
        r.add_level("Regressione (centro)", end, "magnet", 1.0)
        r.add_level("Banda +2sd", end + band * sd, "resistance", 0.7)
        r.add_level("Banda -2sd", end - band * sd, "support", 0.7)
        r.add_level("Canale +3sd", end + 3 * sd, "resistance", 0.5)
        r.add_level("Canale -3sd", end - 3 * sd, "support", 0.5)
        r.add_level("POC regressione", poc, "magnet", 1.2)
        r.add_level("VAH regressione", vah, "resistance", 0.6)
        r.add_level("VAL regressione", val_, "support", 0.6)

        r.metrics.update({
            "length": length, "length_required": length_req, "slope_per_bar": m, "stdev": sd,
            "total_rise": total_rise, "flatness_ratio": ratio, "market_state": "Contraction" if contraction else "Expansion",
            "trend_bias": "Bullish" if m > 0 else "Bearish", "z_score": z, "channel_width": 6 * sd,
            "center": end, "poc": poc, "vah": vah, "val": val_,
            "delta_window": delta_window, "delta_recent": delta_recent,
        })
        r.notes.append(f"Canale {length} barre, stato {'CONTRACTION (laterale)' if contraction else 'EXPANSION (trend)'}, "
                       f"pendenza {'rialzista' if m > 0 else 'ribassista'}, prezzo a {z:+.2f} sd dal centro.")
        r.notes.append(f"POC del profilo volumetrico: {_fmt(poc)} | delta recente {delta_recent:+.2f}.")
        if last_bull is not None and last_bull <= 10:
            r.notes.append(f"Segnale mean-reversion BUY {last_bull} barre fa.")
        if last_bear is not None and last_bear <= 10:
            r.notes.append(f"Segnale mean-reversion SELL {last_bear} barre fa.")
        return r


@register_module
class RetestBreakSetup(IndicatorModule):
    """
    Retest & Break Setup [LuxAlgo]  -  (c) LuxAlgo, CC BY-NC-SA 4.0

    COME FUNZIONA (Pine) - macchina a stati per lato (qui il lato rialzista,
    il ribassista e' speculare):
      0) si attende la chiusura sopra l'ultimo swing high (pivot 5/5)
      1) il livello rotto diventa supporto: servono K=2 retest (minimo <= livello
         e corpo interamente sopra) ognuno entro P=20 barre dal precedente
         evento; nel frattempo si registra il massimo raggiunto (recent high)
      2) dopo il K-esimo retest il setup e' "armato": se entro N=20 barre la
         chiusura supera il recent high -> BREAK (segnale di acquisto),
         altrimenti il setup e' invalidato.
      Il win-rate valuta se N barre dopo il break il prezzo e' oltre il livello.

    COSA RESTITUISCE QUI
      stato corrente dei due lati (livello rotto, numero di retest, livello di
      trigger, barre residue), break completati recenti con verifica del
      follow-through, win-rate storico per direzione.  Il livello di trigger di
      un setup armato e' un ottimo livello per ordini stop.

    LIMITI
      Ritardo di 5 barre dei pivot; nessun repaint dopo la conferma.
    """
    key = "rb"
    title = "Retest & Break Setup"
    style = "breakout"
    batch = 1
    min_bars = 40

    @dataclass
    class Params:
        length: int = 5
        n_bars: int = 20
        p_bars: int = 20
        k_retests: int = 2
        recent_bars: int = 10

    def compute(self, md: MarketData) -> ModuleResult:
        p, r = self.params, self.new_result()
        h, l, o, c = md.high.tolist(), md.low.tolist(), md.open.tolist(), md.close.tolist()
        ph = pivothigh(md.high, p.length, p.length).tolist()
        pl = pivotlow(md.low, p.length, p.length).tolist()
        n = md.n
        st = {1: dict(state=0, cur=NAN, cur_bar=-1, broken=NAN, broken_bar=-1, recent=NAN, last=-1, cnt=0),
              -1: dict(state=0, cur=NAN, cur_bar=-1, broken=NAN, broken_bar=-1, recent=NAN, last=-1, cnt=0)}
        stats = {1: dict(total=0, completed=0, evals=0, wins=0), -1: dict(total=0, completed=0, evals=0, wins=0)}
        pending: List[Tuple[int, float, int]] = []
        breaks: List[Dict[str, Any]] = []
        for i in range(n):
            if pending:
                keep = []
                for eb, price, d in pending:
                    if i >= eb:
                        stats[d]["evals"] += 1
                        if (d == 1 and c[i] > price) or (d == -1 and c[i] < price):
                            stats[d]["wins"] += 1
                    else:
                        keep.append((eb, price, d))
                pending = keep
            if not math.isnan(ph[i]):
                st[1]["cur"], st[1]["cur_bar"] = ph[i], i - p.length
            if not math.isnan(pl[i]):
                st[-1]["cur"], st[-1]["cur_bar"] = pl[i], i - p.length
            for d in (1, -1):
                s = st[d]
                if s["state"] == 0:
                    if not math.isnan(s["cur"]) and ((d == 1 and c[i] > s["cur"]) or (d == -1 and c[i] < s["cur"])):
                        s.update(broken=s["cur"], broken_bar=s["cur_bar"], recent=h[i] if d == 1 else l[i],
                                 state=1, last=s["cur_bar"], cnt=0, cur=NAN)
                elif s["state"] == 1:
                    since = i - s["last"]
                    s["recent"] = max(s["recent"], h[i]) if d == 1 else min(s["recent"], l[i])
                    if since <= p.p_bars:
                        retest = (l[i] <= s["broken"] and min(o[i], c[i]) > s["broken"]) if d == 1 else \
                                 (h[i] >= s["broken"] and max(o[i], c[i]) < s["broken"])
                        if retest:
                            s["cnt"] += 1
                            s["last"] = i
                            r.add_signal(md, f"RETEST{s['cnt']}", d, i, l[i] if d == 1 else h[i],
                                         0.3, "retest del livello rotto")
                            if s["cnt"] == p.k_retests:
                                s["state"] = 2
                                stats[d]["total"] += 1
                    else:
                        s.update(state=0, broken=NAN, recent=NAN)
                elif s["state"] == 2:
                    since = i - s["last"]
                    brk = (c[i] > s["recent"]) if d == 1 else (c[i] < s["recent"])
                    if brk:
                        if since <= p.n_bars:
                            stats[d]["completed"] += 1
                            pending.append((i + p.n_bars, s["recent"], d))
                            breaks.append(dict(idx=i, dir=d, trigger=s["recent"], broken=s["broken"]))
                            r.add_signal(md, "BREAK", d, i, c[i], 1.0, "setup Retest & Break completato")
                        s.update(state=0, broken=NAN, recent=NAN)
                    elif since > p.n_bars:
                        s.update(state=0, broken=NAN, recent=NAN)

        t = n - 1
        close = c[t]
        comp = {1: 0.0, -1: 0.0}
        for d in (1, -1):
            s = st[d]
            if s["state"] == 2:
                comp[d] = max(comp[d], 0.35)
                r.add_level(f"Trigger break {'long' if d == 1 else 'short'}", s["recent"],
                            "resistance" if d == 1 else "support", 1.0, note="setup armato")
                r.add_level(f"Livello rotto ({'swing high' if d == 1 else 'swing low'})", s["broken"],
                            "support" if d == 1 else "resistance", 1.0)
            elif s["state"] == 1:
                comp[d] = max(comp[d], 0.05 + 0.15 * s["cnt"] / max(1, p.k_retests))
                r.add_level(f"Livello in retest ({'long' if d == 1 else 'short'})", s["broken"],
                            "support" if d == 1 else "resistance", 0.8)
        last_break = {1: None, -1: None}
        for bk in breaks:
            last_break[bk["dir"]] = bk
        for d in (1, -1):
            bk = last_break[d]
            if bk is None:
                continue
            ago = t - bk["idx"]
            dec = _decay(ago, p.recent_bars)
            if dec <= 0:
                continue
            ft = 1.0
            if (d == 1 and close < bk["broken"]) or (d == -1 and close > bk["broken"]):
                ft = 0.2
            elif (d == 1 and close < bk["trigger"]) or (d == -1 and close > bk["trigger"]):
                ft = 0.6
            comp[d] = max(comp[d], dec * ft)
            r.add_level("Supporto post-break" if d == 1 else "Resistenza post-break", bk["broken"],
                        "support" if d == 1 else "resistance", 0.9)
        r.bias = comp[1] - comp[-1]
        dom = 1 if r.bias >= 0 else -1
        ev, wi = stats[dom]["evals"], stats[dom]["wins"]
        wr = wi * 100.0 / ev if ev else NAN
        r.confidence = (0.3 + 0.7 * _clip((wr - 40.0) / 30.0, 0.0, 1.0)) if ev >= 5 else 0.5
        state_names = {0: "inattivo", 1: "in retest", 2: "ARMATO"}
        for d, lab in ((1, "rialzista"), (-1, "ribassista")):
            s = st[d]
            ev_d = stats[d]["evals"]
            wr_d = stats[d]["wins"] * 100.0 / ev_d if ev_d else NAN
            r.metrics[f"{'bull' if d == 1 else 'bear'}"] = {
                "state": state_names[s["state"]], "retests": s["cnt"], "broken_level": s["broken"],
                "trigger": s["recent"], "setups_total": stats[d]["total"], "setups_completed": stats[d]["completed"],
                "win_rate": wr_d, "evaluated": ev_d,
            }
            txt = f"Lato {lab}: {state_names[s['state']]}"
            if s["state"] >= 1:
                txt += f" (livello {_fmt(s['broken'])}, retest {s['cnt']}/{p.k_retests}, trigger {_fmt(s['recent'])})"
            txt += f"; win-rate storico {('%.0f%%' % wr_d) if ev_d else 'n/d'} su {ev_d} break."
            r.notes.append(txt)
        for d in (1, -1):
            bk = last_break[d]
            if bk is not None and t - bk["idx"] <= 3 * p.recent_bars:
                r.notes.append(f"Ultimo BREAK {'long' if d == 1 else 'short'} {t - bk['idx']} barre fa a {_fmt(bk['trigger'])}.")
        return r


def _mspo_simulate(signal: Sequence[int], c: List[float], h: List[float], l: List[float], atr_v: List[float],
                   sl_mult: float, tp_mult: float, use_sltp: bool) -> Tuple[np.ndarray, int, List[float], Dict[str, float]]:
    """Replica di f_sim(): posizione sempre allineata al segnale, uscita su cambio segnale o SL/TP ATR.
    Restituisce (curva cumulativa %, posizione finale, rendimenti per trade, trade aperto)."""
    n = len(c)
    cum = np.zeros(n)
    cur, entry, sl, tp = 0, NAN, NAN, NAN
    last_sig: Optional[int] = None
    trades: List[float] = []
    total = 0.0
    for i in range(n):
        pc = c[i - 1] if i > 0 else c[i]
        ret = cur * (c[i] - pc) / pc if pc else 0.0
        s = int(signal[i])
        if last_sig is None or s != last_sig:
            if cur != 0:
                trades.append(cur * (c[i] - entry) / entry)
            cur, entry = s, c[i]
            a = atr_v[i]
            sl = c[i] - a * sl_mult if s == 1 else c[i] + a * sl_mult
            tp = c[i] + a * tp_mult if s == 1 else c[i] - a * tp_mult
            last_sig = s
        elif cur != 0 and use_sltp:
            hit_sl = (l[i] <= sl) if cur == 1 else (h[i] >= sl)
            hit_tp = (h[i] >= tp) if cur == 1 else (l[i] <= tp)
            if hit_sl or hit_tp:
                ex = tp if hit_tp else sl
                ret = cur * (ex - pc) / pc if pc else 0.0
                trades.append(cur * (ex - entry) / entry)
                cur, entry, sl, tp = 0, NAN, NAN, NAN
        total += ret
        cum[i] = total * 100.0
    return cum, cur, trades, {"dir": cur, "entry": entry, "sl": sl, "tp": tp}


def _hold_signal(long_cond: np.ndarray, short_cond: np.ndarray) -> np.ndarray:
    """pos := long ? 1 : short ? -1 : pos[1]  (inizializzato a 0)."""
    out = np.zeros(len(long_cond), dtype=int)
    pos = 0
    for i in range(len(long_cond)):
        if long_cond[i]:
            pos = 1
        elif short_cond[i]:
            pos = -1
        out[i] = pos
    return out


@register_module
class MultiStrategyPortfolioOptimizer(IndicatorModule):
    """
    Multi-Strategy Portfolio Optimizer [LuxAlgo]  -  (c) LuxAlgo, CC BY-NC-SA 4.0

    COME FUNZIONA (Pine)
      9 famiglie di strategie x 3 set di parametri = 27 simulazioni sempre-a-mercato
      (long se il segnale e' +1, short se -1), con uscita su cambio segnale o
      SL = 2 ATR / TP = 4 ATR (poi flat fino al segnale successivo):
        Supertrend (trend)       ST (10,3) (20,5) (14,2)
        MACD (trend/momentum)    (12,26,9) (5,34,5) (24,52,9)
        Donchian (breakout)      20 / 50 / 100
        RSI trend (>50)          14 / 21 / 7
        Bollinger reversion      (20,2) (50,2.5) (14,2)
        RSI reversion (30/70)    14 / 7 / 4
        Stocastico reversion     14 / 21 / 7 (20/80)
        CCI momentum (+/-100)    20 / 50 / 14
        EMA crossover            (9,21) (20,50) (50,200)
      Per ogni famiglia sceglie la variante con rendimento cumulato maggiore;
      il portafoglio e' la media equipesata; la diversificazione e' la
      correlazione media dei rendimenti (ultime 100 barre).
      Attive di default (come in Pine): ST, Donchian, BB, Stocastico, CCI.

    COSA RESTITUISCE QUI
      * voto d'insieme: posizione corrente della variante migliore di ogni
        famiglia, pesata per rendimento storico e performance recente;
      * voto di REGIME: rendimento recente (200 barre) delle famiglie trend/
        momentum contro quelle di reversion -> quale "stile" sta funzionando;
      * classe di diversificazione e correlazione media.

    LIMITI
      La scelta della variante migliore usa tutta la storia (in-sample): il
      rendimento del portafoglio e' ottimistico.  Esecuzione a TP prioritario
      se SL e TP sono toccati nella stessa barra (come l'originale).
    """
    key = "mspo"
    title = "Multi-Strategy Portfolio Optimizer"
    style = "ensemble"
    batch = 1
    min_bars = 250

    @dataclass
    class Params:
        use_st: bool = True
        use_macd: bool = False
        use_donch: bool = True
        use_rsit: bool = False
        use_bb: bool = True
        use_rsir: bool = False
        use_stoch: bool = True
        use_cci: bool = True
        use_ema: bool = False
        use_sltp: bool = True
        atr_len: int = 14
        sl_mult: float = 2.0
        tp_mult: float = 4.0
        corr_len: int = 100
        regime_lookback: int = 200
        flip_recent_bars: int = 10

    def _families(self, md: MarketData) -> List[Dict[str, Any]]:
        p = self.params
        c, h, l = md.close, md.high, md.low
        fam: List[Dict[str, Any]] = []

        def add(name: str, short: str, style: str, enabled: bool, variants: List[Tuple[str, Any]]):
            fam.append(dict(name=name, short=short, style=style, enabled=enabled, variants=variants))

        st_v = []
        for f, a, lab in ((3, 10, "ST (10,3)"), (5, 20, "ST (20,5)"), (2, 14, "ST (14,2)")):
            st_v.append((lab, lambda f=f, a=a: np.where(supertrend(h, l, c, f, a)[1] < 0, 1, -1)))
        add("Supertrend", "ST", "trend", p.use_st, st_v)
        mc = []
        for f, s, g, lab in ((12, 26, 9, "MACD (12,26)"), (5, 34, 5, "MACD (5,34)"), (24, 52, 9, "MACD (24,52)")):
            mc.append((lab, lambda f=f, s=s, g=g: (lambda mm: np.where(mm[0] > mm[1], 1, -1))(macd(c, f, s, g))))
        add("MACD", "MACD", "trend", p.use_macd, mc)
        dv = []
        for nlen in (20, 50, 100):
            dv.append((f"Donchian ({nlen})", lambda nlen=nlen: _hold_signal(
                c > shift(highest(h, nlen)), c < shift(lowest(l, nlen)))))
        add("Donchian", "DON", "trend", p.use_donch, dv)
        rt = []
        for nlen in (14, 21, 7):
            rt.append((f"RSI Tr ({nlen})", lambda nlen=nlen: np.where(rsi(c, nlen) > 50, 1, -1)))
        add("RSI Trend", "RSI-T", "trend", p.use_rsit, rt)
        bbv = []
        for nlen, mult in ((20, 2.0), (50, 2.5), (14, 2.0)):
            bbv.append((f"BB ({nlen},{mult:g})", lambda nlen=nlen, mult=mult: (lambda bb: _hold_signal(
                c < bb[2], c > bb[1]))(bollinger(c, nlen, mult))))
        add("BB Rev", "BB", "reversion", p.use_bb, bbv)
        rr = []
        for nlen in (14, 7, 4):
            rr.append((f"RSI Rev ({nlen})", lambda nlen=nlen: (lambda rs: _hold_signal(rs < 30, rs > 70))(rsi(c, nlen))))
        add("RSI Rev", "RSI-R", "reversion", p.use_rsir, rr)
        sv = []
        for nlen, lab in ((14, "Stoch (14,3)"), (21, "Stoch (21,5)"), (7, "Stoch (7,3)")):
            sv.append((lab, lambda nlen=nlen: (lambda k: _hold_signal(k < 20, k > 80))(stoch(c, h, l, nlen))))
        add("Stochastic", "STOCH", "reversion", p.use_stoch, sv)
        cv = []
        for nlen in (20, 50, 14):
            cv.append((f"CCI ({nlen})", lambda nlen=nlen: (lambda cc: _hold_signal(cc > 100, cc < -100))(cci(c, nlen))))
        add("CCI Break", "CCI", "momentum", p.use_cci, cv)
        ev = []
        for f, s in ((9, 21), (20, 50), (50, 200)):
            ev.append((f"EMA ({f},{s})", lambda f=f, s=s: np.where(ema(c, f) > ema(c, s), 1, -1)))
        add("EMA Cross", "EMA", "trend", p.use_ema, ev)
        return fam

    def compute(self, md: MarketData) -> ModuleResult:
        p, r = self.params, self.new_result()
        c, h, l = md.close.tolist(), md.high.tolist(), md.low.tolist()
        atr_v = md.atr(p.atr_len).tolist()
        n = md.n
        bar_ret = np.nan_to_num(change(md.close) / shift(md.close))
        lr = max(10, min(p.regime_lookback, n - 1))
        scale = float(np.std(bar_ret[-lr:])) * math.sqrt(lr) * 100.0 or 1.0
        rows: List[Dict[str, Any]] = []
        for fam in self._families(md):
            if not fam["enabled"]:
                continue
            best = None
            recent_perf = []
            for lab, fn in fam["variants"]:
                sig = np.asarray(fn(), dtype=int)
                cum, pos, trades, open_tr = _mspo_simulate(sig, c, h, l, atr_v, p.sl_mult, p.tp_mult, p.use_sltp)
                recent_perf.append(cum[-1] - cum[-1 - lr])
                cand = dict(setting=lab, cum=cum, pos=pos, trades=trades, open=open_tr, sig=sig)
                if best is None or cum[-1] > best["cum"][-1]:
                    best = cand
            stats = _trade_stats(best["trades"])
            rows.append(dict(name=fam["name"], short=fam["short"], style=fam["style"], best=best,
                             ret=float(best["cum"][-1]), recent=float(np.mean(recent_perf)), stats=stats))
        if not rows:
            r.applicable = False
            r.error = "nessuna famiglia attiva"
            return r
        # --- voto d'insieme ---
        num = den = 0.0
        for row in rows:
            base = 1.0 if row["ret"] > 0 else 0.25
            wgt = base * (1.0 + _clip(row["recent"] / scale, -0.5, 1.0))
            row["weight"] = wgt
            num += wgt * int(row["best"]["sig"][-1])   # opinione attuale della strategia
            den += wgt
        r.bias = _safe_div(num, den)
        # --- regime: trend/momentum vs reversion ---
        tr_perf = [row["recent"] for row in rows if row["style"] in ("trend", "momentum")]
        rv_perf = [row["recent"] for row in rows if row["style"] == "reversion"]
        if tr_perf and rv_perf:
            r.regime = _clip((np.mean(tr_perf) - np.mean(rv_perf)) / scale)
            r.regime_confidence = 0.6
        # --- correlazione / diversificazione ---
        corr_vals = []
        L = p.corr_len
        for i in range(len(rows)):
            for j in range(i + 1, len(rows)):
                a = np.diff(rows[i]["best"]["cum"][-(L + 1):])
                b = np.diff(rows[j]["best"]["cum"][-(L + 1):])
                if len(a) >= L and np.std(a) > 0 and np.std(b) > 0:
                    corr_vals.append(float(np.corrcoef(a, b)[0, 1]))
                else:
                    corr_vals.append(0.0)
        avg_corr = float(np.mean(corr_vals)) if corr_vals else NAN
        if len(rows) < 2:
            div = "N/A"
        elif avg_corr > 0.7:
            div = "Very Poor"
        elif avg_corr > 0.4:
            div = "Poor"
        elif avg_corr > 0.1:
            div = "Moderate"
        elif avg_corr > -0.2:
            div = "Good"
        else:
            div = "Excellent"
        frac_pos = sum(1 for row in rows if row["ret"] > 0) / len(rows)
        r.confidence = 0.35 + 0.35 * (1.0 - _clip(_nz(avg_corr), 0.0, 1.0)) + 0.2 * frac_pos
        # --- segnali: flip recenti delle varianti migliori ---
        for row in rows:
            sig = row["best"]["sig"]
            for i in range(max(1, n - p.flip_recent_bars), n):
                if sig[i] != sig[i - 1] and sig[i] != 0:
                    r.add_signal(md, f"FLIP {row['short']}", int(sig[i]), i, c[i], 0.5, row["best"]["setting"])
            ot = row["best"]["open"]
            if ot["dir"] != 0 and p.use_sltp:
                r.add_level(f"SL {row['short']}", ot["sl"], "support" if ot["dir"] == 1 else "resistance", 0.3)
                r.add_level(f"TP {row['short']}", ot["tp"], "level", 0.3)
        port = float(np.mean([row["ret"] for row in rows]))
        r.metrics.update({
            "families": [{"name": row["name"], "best_setting": row["best"]["setting"], "return_pct": row["ret"],
                          "recent_return_pct": row["recent"], "signal": int(row["best"]["sig"][-1]),
                          "position": row["best"]["pos"], "style": row["style"],
                          "weight": row["weight"], "win_rate": row["stats"]["win_rate"],
                          "trades": row["stats"]["trades"]} for row in rows],
            "portfolio_return_pct": port, "avg_correlation": avg_corr, "diversification": div,
            "trend_minus_reversion_recent": (float(np.mean(tr_perf) - np.mean(rv_perf)) if tr_perf and rv_perf else None),
        })
        longs = sum(1 for row in rows if row["best"]["sig"][-1] == 1)
        shorts = sum(1 for row in rows if row["best"]["sig"][-1] == -1)
        r.notes.append(f"{len(rows)} famiglie attive, segnale attuale: {longs} long, {shorts} short, "
                       f"{len(rows) - longs - shorts} neutrali. "
                       f"Portafoglio equipesato {port:+.2f}% (in-sample), diversificazione {div} (corr {_nz(avg_corr):+.2f}).")
        best_row = max(rows, key=lambda x: x["recent"])
        r.notes.append(f"Famiglia migliore nelle ultime {lr} barre: {best_row['name']} ({best_row['best']['setting']}), "
                       f"stile {best_row['style']}.")
        return r


def _lux_rsi(close: List[float], length: int) -> List[float]:
    """RSI dell'optimizer (Wilder con seed sul primo valore, come nello script)."""
    alpha = 1.0 / length
    pu = pd_ = NAN
    prev_rsi = NAN
    out: List[float] = []
    for i, cv in enumerate(close):
        ch = cv - (close[i - 1] if i > 0 else cv)
        up, dn = max(0.0, ch), max(0.0, -ch)
        pu = up if math.isnan(pu) else alpha * up + (1 - alpha) * pu
        pd_ = dn if math.isnan(pd_) else alpha * dn + (1 - alpha) * pd_
        if pd_ == 0:
            val = (50.0 if math.isnan(prev_rsi) else prev_rsi) if pu == 0 else 100.0
        else:
            val = 100.0 - 100.0 / (1.0 + pu / pd_)
        out.append(val)
        prev_rsi = val
    return out


def _rsid_stats(profits: Sequence[float]) -> Dict[str, float]:
    """Statistiche per periodo come in record_trade() (equity = 1 + somma profitti)."""
    s = dict(profit=0.0, gp=0.0, gl=0.0, trades=0, wins=0, dd=0.0, profit_sq=0.0, runs=0)
    peak, last_sign = 1.0, 0
    for pr in profits:
        sign = 1 if pr > 0 else -1
        if s["trades"] > 0 and last_sign != 0 and last_sign != sign:
            s["runs"] += 1
        if s["trades"] == 0:
            s["runs"] = 1
        last_sign = sign
        s["profit_sq"] += pr * pr
        s["trades"] += 1
        if pr > 0:
            s["wins"] += 1
            s["gp"] += pr
        else:
            s["gl"] += abs(pr)
        s["profit"] += pr
        eq = 1.0 + s["profit"]
        peak = max(peak, eq)
        s["dd"] = max(s["dd"], (peak - eq) / max(peak, 1e-6))
    return s


def _rsid_metric(s: Dict[str, float], metric: str, dashboard: bool = False) -> float:
    """Valore della metrica di ottimizzazione (come il loop 'Walk-forward transition')."""
    tr, pr = s["trades"], s["profit"]
    if metric == "Net Profit":
        return pr if (tr > 0 or not dashboard) else -999.0
    if metric == "Win Rate":
        return s["wins"] * 100.0 / tr if tr > 0 else -1.0
    if metric == "Profit Factor":
        return -1.0 if tr == 0 else ((999.0 if s["gp"] > 0 else 0.0) if s["gl"] == 0 else s["gp"] / s["gl"])
    if metric == "Drawdown":
        return -s["dd"] if tr > 0 else -999.0
    if metric == "Return / Drawdown":
        return (pr / s["dd"] if s["dd"] > 0 else (999.0 if pr > 0 else 0.0)) if tr > 0 else -999.0
    if metric == "Average Trade":
        return pr / tr if tr > 0 else -999.0
    if metric == "Gross Profit":
        return s["gp"] if tr > 0 else -999.0
    if metric == "Total Trades":
        return float(tr) if tr > 0 else -1.0
    if metric == "Sharpe Ratio":
        if tr == 0:
            return -999.0
        var = (s["profit_sq"] - pr * pr / tr) / tr
        sd = math.sqrt(max(0.0, var))
        return 0.0 if sd == 0 else (pr / tr) / sd
    if metric == "Z-Score (Dependency)":
        w, n_ = float(s["wins"]), float(tr)
        lo = n_ - w
        if n_ > 1:
            e = 1.0 + (2.0 * w * lo) / n_
            var = (2.0 * w * lo * (2.0 * w * lo - n_)) / (n_ * n_ * (n_ - 1.0))
            sdr = math.sqrt(max(0.0, var))
            return 0.0 if sdr == 0 else (s["runs"] - e) / sdr
        return 0.0
    return pr


@register_module
class RSIDivergenceOOS(IndicatorModule):
    """
    RSI Divergence: Out-of-Sample Optimizer [LuxAlgo]  -  (c) LuxAlgo, CC BY-NC-SA 4.0

    COME FUNZIONA (Pine)
      * Simula in parallelo un RSI per ogni periodo tra 2 e 50.
      * Pivot sull'RSI (5 barre a sinistra, 2 a destra, stretti).  Divergenza
        rialzista: pivot low dell'RSI piu' alto del precedente mentre il minimo
        del prezzo e' piu' basso (entro 60 barre); ribassista speculare.
      * Trade: entrata alla chiusura sulla divergenza, SL 1.5 ATR(14), TP 2 ATR,
        uscita anche su divergenza opposta.  I trade sono attribuiti al periodo
        di entrata: In-Sample (IS), Out-of-Sample (OOS) o Forward.
      * Walk-forward: il periodo RSI migliore (metrica scelta, default Net
        Profit) viene fissato alla fine dell'IS e usato in OOS/Forward.

    COSA RESTITUISCE QUI
      periodo RSI ottimale, metriche IS/OOS/Forward (validazione fuori
      campione), divergenze recenti del periodo scelto, trade simulato aperto
      (con SL/TP come livelli), valore dell'RSI.
      Per dati MT5 le date di default del Pine (2024 IS / 2025 OOS) spesso non
      sono coperte: di default qui si usa uno split percentuale 50% IS /
      30% OOS / 20% Forward (split_mode="dates" per le date di Pine).

    LIMITI
      Divergenze confermate 2 barre dopo il pivot.  Split unico (non rolling).
    """
    key = "rsid"
    title = "RSI Divergence OOS Optimizer"
    style = "reversion"
    batch = 1
    min_bars = 150

    @dataclass
    class Params:
        split_mode: str = "fraction"          # "fraction" | "dates"
        is_fraction: float = 0.5
        oos_fraction: float = 0.3
        is_start: str = "2024-01-03"
        is_end: str = "2024-12-31"
        oos_start: str = "2025-01-01"
        oos_end: str = "2025-12-31"
        min_len: int = 2
        max_len: int = 50
        step_len: int = 1
        opt_metric: str = "Net Profit"
        use_auto_oos: bool = True
        manual_oos: int = 14
        pivot_left: int = 5
        pivot_right: int = 2
        max_div_bars: int = 60
        sl_mult: float = 1.5
        tp_mult: float = 2.0
        opp_exit: bool = True
        default_len: int = 14
        recent_bars: int = 10

    def _periods(self, md: MarketData) -> Tuple[np.ndarray, np.ndarray, np.ndarray, int, int]:
        p, n = self.params, md.n
        idx = np.arange(n)
        if p.split_mode == "dates":
            tt = md.time_utc
            ts = lambda s: pd.Timestamp(s, tz="UTC")
            in_is = np.asarray((tt >= ts(p.is_start)) & (tt <= ts(p.is_end)))
            in_oos = np.asarray((tt >= ts(p.oos_start)) & (tt <= ts(p.oos_end)))
            in_fwd = np.asarray(tt > ts(p.oos_end))
            le = np.nonzero(np.asarray(tt <= ts(p.is_end)))[0]
            is_end_idx = int(le[-1]) if len(le) else 0
            os_ = np.nonzero(np.asarray(tt >= ts(p.oos_start)))[0]
            oos_start_idx = int(os_[0]) if len(os_) else n
        else:
            i1 = max(1, int(n * p.is_fraction)) - 1
            i2 = max(i1 + 1, int(n * (p.is_fraction + p.oos_fraction))) - 1
            in_is, in_oos, in_fwd = idx <= i1, (idx > i1) & (idx <= i2), idx > i2
            is_end_idx, oos_start_idx = i1, i1 + 1
        return in_is, in_oos, in_fwd, is_end_idx, oos_start_idx

    def _simulate(self, md: MarketData, length: int, in_is, in_oos, in_fwd, atr_v: List[float]) -> Dict[str, Any]:
        p = self.params
        c, h, l = md.close.tolist(), md.high.tolist(), md.low.tolist()
        n = md.n
        rs = _lux_rsi(c, length)
        rsa = np.asarray(rs)
        k = p.pivot_left + p.pivot_right + 1
        div_bull = [False] * n
        div_bear = [False] * n
        bull_start: Dict[int, Tuple[int, float, float]] = {}
        bear_start: Dict[int, Tuple[int, float, float]] = {}
        if n >= k:
            win = _swv(rsa, k)
            center = win[:, p.pivot_left]
            others = np.delete(win, p.pivot_left, axis=1)
            is_pl = center < others.min(axis=1)
            is_ph = center > others.max(axis=1)
            last_pl = last_ph = None
            for row in np.nonzero(is_pl | is_ph)[0]:
                t = int(row) + k - 1
                pb = t - p.pivot_right
                if is_pl[row]:
                    rv, pv = rs[pb], l[pb]
                    if last_pl is not None and rv > last_pl[2] and pv < last_pl[1] and pb - last_pl[0] <= p.max_div_bars:
                        div_bull[t] = True
                        bull_start[t] = last_pl
                    last_pl = (pb, pv, rv)
                if is_ph[row]:
                    rv, pv = rs[pb], h[pb]
                    if last_ph is not None and rv < last_ph[2] and pv > last_ph[1] and pb - last_ph[0] <= p.max_div_bars:
                        div_bear[t] = True
                        bear_start[t] = last_ph
                    last_ph = (pb, pv, rv)
        pos, entry, sl, tp, period, entry_idx = 0, NAN, NAN, NAN, 0, -1
        trades: List[Tuple[int, int, int, float, int]] = []  # (entry_idx, exit_idx, period, profit, dir)
        for i in range(n):
            exited = False
            if pos == 1:
                pr = None
                if l[i] <= sl:
                    pr = (sl - entry) / entry
                elif h[i] >= tp:
                    pr = (tp - entry) / entry
                elif p.opp_exit and div_bear[i]:
                    pr = (c[i] - entry) / entry
                if pr is not None:
                    trades.append((entry_idx, i, period, pr, 1))
                    pos, exited = 0, True
            elif pos == -1:
                pr = None
                if h[i] >= sl:
                    pr = (entry - sl) / entry
                elif l[i] <= tp:
                    pr = (entry - tp) / entry
                elif p.opp_exit and div_bull[i]:
                    pr = (entry - c[i]) / entry
                if pr is not None:
                    trades.append((entry_idx, i, period, pr, -1))
                    pos, exited = 0, True
            if pos == 0 and not exited and (in_is[i] or in_oos[i] or in_fwd[i]) and not math.isnan(atr_v[i]):
                if div_bull[i]:
                    pos, entry, entry_idx = 1, c[i], i
                    sl, tp = c[i] - atr_v[i] * p.sl_mult, c[i] + atr_v[i] * p.tp_mult
                    period = 1 if in_is[i] else (2 if in_oos[i] else 3)
                elif div_bear[i]:
                    pos, entry, entry_idx = -1, c[i], i
                    sl, tp = c[i] + atr_v[i] * p.sl_mult, c[i] - atr_v[i] * p.tp_mult
                    period = 1 if in_is[i] else (2 if in_oos[i] else 3)
        return dict(length=length, rsi=rs, div_bull=div_bull, div_bear=div_bear, bull_start=bull_start,
                    bear_start=bear_start, trades=trades, pos=pos, entry=entry, sl=sl, tp=tp)

    def compute(self, md: MarketData) -> ModuleResult:
        p, r = self.params, self.new_result()
        n, t = md.n, md.n - 1
        in_is, in_oos, in_fwd, is_end_idx, oos_start_idx = self._periods(md)
        atr_v = md.atr(14).tolist()
        sims = [self._simulate(md, L, in_is, in_oos, in_fwd, atr_v)
                for L in range(p.min_len, p.max_len + 1, max(1, p.step_len))]
        best_len, best_val, best_np, best_tr = None, -999999.0, -999999.0, -1
        heat = []
        for s in sims:
            st_is = _rsid_stats([tr[3] for tr in s["trades"] if tr[2] == 1 and tr[1] <= is_end_idx])
            val = _rsid_metric(st_is, p.opt_metric)
            heat.append((s["length"], val))
            upd = best_len is None or val > best_val or (
                val == best_val and (st_is["profit"] > best_np or (st_is["profit"] == best_np and st_is["trades"] > best_tr)))
            if upd:
                best_len, best_val, best_np, best_tr = s["length"], val, st_is["profit"], st_is["trades"]
        lengths = [s["length"] for s in sims]
        if p.use_auto_oos:
            chosen = best_len
        else:
            chosen = min(lengths, key=lambda L: abs(L - p.manual_oos))
        visual = chosen if t >= oos_start_idx else min(lengths, key=lambda L: abs(L - p.default_len))
        by_len = {s["length"]: s for s in sims}
        bs_is, bs_oos, vis = by_len[best_len], by_len[chosen], by_len[visual]
        per = lambda s, k: _rsid_stats([tr[3] for tr in s["trades"] if tr[2] == k])
        s_is, s_oos, s_fwd = per(bs_is, 1), per(bs_oos, 2), per(bs_oos, 3)

        def summary(s: Dict[str, float]) -> Dict[str, Any]:
            return {"trades": s["trades"], "net_profit_pct": s["profit"] * 100, "win_rate": _rsid_metric(s, "Win Rate"),
                    "profit_factor": _rsid_metric(s, "Profit Factor"), "max_dd_pct": s["dd"] * 100,
                    "sharpe": _rsid_metric(s, "Sharpe Ratio"), "z_score": _rsid_metric(s, "Z-Score (Dependency)")}

        # --- segnali recenti del periodo "visuale" ---
        last_bull = last_bear = None
        for i in range(max(0, n - 100), n):
            if vis["div_bull"][i]:
                pb = vis["bull_start"].get(i, (i, NAN, NAN))
                r.add_signal(md, "BULL_DIV", 1, i, md.low[i - p.pivot_right], 1.0,
                             f"RSI{visual}: minimo piu' basso sul prezzo, piu' alto sull'RSI (inizio barra {pb[0]})")
                last_bull = t - i
            if vis["div_bear"][i]:
                r.add_signal(md, "BEAR_DIV", -1, i, md.high[i - p.pivot_right], 1.0,
                             f"RSI{visual}: massimo piu' alto sul prezzo, piu' basso sull'RSI")
                last_bear = t - i
        comp = 0.0
        if last_bull is not None:
            comp += _decay(last_bull, p.recent_bars)
        if last_bear is not None:
            comp -= _decay(last_bear, p.recent_bars)
        if comp == 0 and vis["pos"] != 0:
            comp = 0.5 * vis["pos"]
        rsi_now = vis["rsi"][t]
        if rsi_now > 70:
            comp -= 0.15
        elif rsi_now < 30:
            comp += 0.15
        r.bias = comp
        if vis["pos"] != 0:
            r.add_level("SL trade divergenza", vis["sl"], "support" if vis["pos"] == 1 else "resistance", 0.5)
            r.add_level("TP trade divergenza", vis["tp"], "level", 0.5)
        # --- confidenza = validazione walk-forward ---
        if s_oos["trades"] >= 3 and s_oos["profit"] > 0 and _rsid_metric(s_oos, "Profit Factor") > 1:
            conf, verdict = 0.75, "VALIDATO fuori campione"
        elif s_oos["trades"] >= 3:
            conf, verdict = 0.3, "NON validato (OOS negativo: possibile overfitting)"
        else:
            conf, verdict = 0.45, "OOS con pochi trade"
        if s_fwd["trades"] >= 3:
            conf += 0.1 if s_fwd["profit"] > 0 else -0.1
        r.confidence = conf
        r.metrics.update({
            "best_is_length": best_len, "chosen_oos_length": chosen, "visual_length": visual,
            "opt_metric": p.opt_metric, "rsi": rsi_now, "in_sample": summary(s_is), "out_of_sample": summary(s_oos),
            "forward": summary(s_fwd), "validation": verdict,
            "open_trade": {"dir": vis["pos"], "entry": vis["entry"], "sl": vis["sl"], "tp": vis["tp"]} if vis["pos"] else None,
            "is_heatmap": heat,
        })
        r.notes.append(f"RSI ottimale (IS, metrica {p.opt_metric}): {best_len}; periodo usato ora: {visual}; RSI = {rsi_now:.1f}.")
        r.notes.append(f"IS {s_is['profit'] * 100:+.2f}% su {s_is['trades']} trade | OOS {s_oos['profit'] * 100:+.2f}% su "
                       f"{s_oos['trades']} | Forward {s_fwd['profit'] * 100:+.2f}% su {s_fwd['trades']} -> {verdict}.")
        if last_bull is not None and last_bull <= p.recent_bars:
            r.notes.append(f"Divergenza RIALZISTA confermata {last_bull} barre fa.")
        if last_bear is not None and last_bear <= p.recent_bars:
            r.notes.append(f"Divergenza RIBASSISTA confermata {last_bear} barre fa.")
        if vis["pos"]:
            r.notes.append(f"Trade simulato aperto {'LONG' if vis['pos'] == 1 else 'SHORT'} da {_fmt(vis['entry'])}, "
                           f"SL {_fmt(vis['sl'])}, TP {_fmt(vis['tp'])}.")
        return r


@register_module
class SupertrendSensitivity3D(IndicatorModule):
    """
    Supertrend Parameter Sensitivity 3D [LuxAlgo]  -  (c) LuxAlgo, CC BY-NC-SA 4.0

    COME FUNZIONA (Pine)
      * Griglia 10x10 di Supertrend: ATR length 5..14 (passo 1) x moltiplicatore
        1.0..1.9 (passo 0.1) = 100 combinazioni simulate barra per barra
        (trade ad ogni inversione, PnL % dalla chiusura).
      * Superficie 3D della metrica scelta (default Win Rate); cella migliore,
        peggiore e "area piu' stabile": finestra 3x3 con punteggio
        media - 1.5 * deviazione standard (robustezza ai parametri).
      * "Auto Apply" usa ad ogni barra la combinazione stabile.
      * Supertrend principale (10, 3).

    COSA RESTITUISCE QUI
      * CONSENSO: percentuale delle 100 combinazioni attualmente in uptrend
        (misura robusta della direzione, indipendente dal singolo parametro);
      * trend e trailing stop della combinazione STABILE e del ST(10,3);
      * voto di regime: consenso netto (tutte d'accordo = trend, divise = range);
      * robustezza: quota di combinazioni con profitto netto positivo.

    LIMITI
      La superficie e' calcolata su tutta la storia (in-sample).
    """
    key = "st3d"
    title = "Supertrend Sensitivity 3D"
    style = "trend"
    batch = 1
    min_bars = 60

    @dataclass
    class Params:
        main_len: int = 10
        main_mult: float = 3.0
        len_start: int = 5
        len_step: int = 1
        mult_start: float = 1.0
        mult_step: float = 0.1
        metric: str = "Win Rate"
        consensus_smooth: int = 10

    @staticmethod
    def _metric(tr, wins, gp, gl, metric: str) -> np.ndarray:
        with np.errstate(divide="ignore", invalid="ignore"):
            losses = tr - wins
            if metric == "Net Profit":
                return gp - gl
            if metric == "Win Rate":
                return np.where(tr > 0, wins / np.maximum(tr, 1) * 100.0, 0.0)
            if metric == "Profit Factor":
                return np.where(gl > 0, gp / np.where(gl > 0, gl, 1), np.where(gp > 0, 10.0, 0.0))
            if metric == "Total Trades":
                return tr.astype(float)
            if metric == "Average Trade":
                return np.where(tr > 0, (gp - gl) / np.maximum(tr, 1), 0.0)
            if metric == "Reward/Risk Ratio":
                aw = np.where(wins > 0, gp / np.maximum(wins, 1), 0.0)
                al = np.where(losses > 0, gl / np.maximum(losses, 1), 0.0)
                return np.where(al > 0, aw / np.where(al > 0, al, 1), np.where(aw > 0, 10.0, 0.0))
            if metric == "Gross Profit":
                return gp
            if metric == "Total Wins":
                return wins.astype(float)
            if metric == "Win/Loss Ratio":
                return np.where(losses > 0, wins / np.maximum(losses, 1), np.where(wins > 0, 10.0, 0.0))
        return gp - gl

    def compute(self, md: MarketData) -> ModuleResult:
        p, r = self.params, self.new_result()
        n = md.n
        c, hl2 = md.close, md.hl2
        tr_ = md.tr(True)
        lens = [p.len_start + i * p.len_step for i in range(10)]
        mults = np.array([p.mult_start + j * p.mult_step for j in range(10)])
        atr_mat = np.vstack([rma(tr_, L) for L in lens])            # (10, n)
        mult_vec = np.tile(mults, 10)                                 # idx = i*10 + j
        prev_up = np.full(100, np.nan)
        prev_dn = np.full(100, np.nan)
        trend = np.ones(100, dtype=int)
        position = np.zeros(100, dtype=int)
        entry = np.full(100, np.nan)
        trades = np.zeros(100, dtype=int)
        wins = np.zeros(100, dtype=int)
        gp = np.zeros(100)
        gl = np.zeros(100)
        up_frac = np.zeros(n)
        with np.errstate(invalid="ignore", divide="ignore"):
            for t in range(n):
                a = np.repeat(atr_mat[:, t], 10)
                bl = hl2[t] - mult_vec * a
                bu = hl2[t] + mult_vec * a
                pl_ = np.where(np.isnan(prev_up), bl, prev_up)
                pu_ = np.where(np.isnan(prev_dn), bu, prev_dn)
                c1 = c[t - 1] if t > 0 else np.nan
                lower = np.where(c1 > pl_, np.maximum(bl, pl_), bl)
                upper = np.where(c1 < pu_, np.minimum(bu, pu_), bu)
                new_tr = trend.copy()
                new_tr[(trend == -1) & (c[t] > pu_)] = 1
                new_tr[(trend == 1) & (c[t] < pl_)] = -1
                changed = new_tr != trend
                has_pos = changed & (position != 0)
                if has_pos.any():
                    pnl = (c[t] - entry) / entry * position * 100.0
                    win = has_pos & (pnl > 0)
                    wins += win
                    gp += np.where(win, pnl, 0.0)
                    gl += np.where(has_pos & ~(pnl > 0), np.abs(pnl), 0.0)
                    trades += has_pos
                position = np.where(changed, new_tr, position)
                entry = np.where(changed, c[t], entry)
                prev_up, prev_dn, trend = lower, upper, new_tr
                up_frac[t] = float(np.mean(trend == 1))
        z = self._metric(trades, wins, gp, gl, p.metric).reshape(10, 10)
        net = (gp - gl).reshape(10, 10)
        flat = z.ravel()
        best_idx = int(len(flat) - 1 - np.argmax(flat[::-1]))     # ">=": ultima occorrenza del massimo
        worst_idx = int(len(flat) - 1 - np.argmin(flat[::-1]))
        bi, bj = divmod(best_idx, 10)
        wi, wj = divmod(worst_idx, 10)
        si, sj, best_score = 1, 1, None
        for i in range(1, 9):
            for j in range(1, 9):
                blk = z[i - 1:i + 2, j - 1:j + 2]
                sc = blk.mean() - blk.std() * 1.5
                if best_score is None or sc > best_score:
                    best_score, si, sj = sc, i, j
        s_idx = si * 10 + sj
        st_tr = int(trend[s_idx])
        st_stop = float(prev_up[s_idx] if st_tr == 1 else prev_dn[s_idx])
        _, main_dir_arr = supertrend(md.high, md.low, c, p.main_mult, p.main_len)
        main_line, _ = supertrend(md.high, md.low, c, p.main_mult, p.main_len)
        main_dir = 1 if main_dir_arr[-1] < 0 else -1
        consensus = 2.0 * up_frac[-1] - 1.0
        k = max(1, min(p.consensus_smooth, n))
        agreement = float(np.mean(np.abs(2.0 * up_frac[-k:] - 1.0)))
        frac_profit = float(np.mean(net > 0))
        r.bias = 0.4 * consensus + 0.4 * st_tr + 0.2 * main_dir
        r.regime = 2.0 * agreement - 1.0
        r.regime_confidence = 0.5
        r.confidence = 0.3 + 0.6 * frac_profit
        r.add_level(f"Trailing ST stabile ({lens[si]},{mults[sj]:.1f})", st_stop,
                    "support" if st_tr == 1 else "resistance", 1.0)
        r.add_level(f"ST({p.main_len},{p.main_mult:g})", float(main_line[-1]),
                    "support" if main_dir == 1 else "resistance", 0.8)
        # flip recenti della combinazione stabile / del consenso
        for i in range(max(1, n - 10), n):
            if (up_frac[i] >= 0.5) != (up_frac[i - 1] >= 0.5):
                r.add_signal(md, "CONSENSUS_FLIP", 1 if up_frac[i] >= 0.5 else -1, i, c[i], 0.6,
                             f"consenso passa a {up_frac[i] * 100:.0f}% rialzista")
        r.metrics.update({
            "metric": p.metric, "consensus_up_pct": up_frac[-1] * 100.0, "consensus_up_pct_prev5": up_frac[max(0, n - 6)] * 100.0,
            "agreement": agreement, "best": {"len": lens[bi], "mult": round(float(mults[bj]), 2), "value": float(z[bi, bj])},
            "worst": {"len": lens[wi], "mult": round(float(mults[wj]), 2), "value": float(z[wi, wj])},
            "stable": {"len": lens[si], "mult": round(float(mults[sj]), 2), "value": float(z[si, sj]),
                       "trend": st_tr, "stop": st_stop},
            "main_supertrend": {"len": p.main_len, "mult": p.main_mult, "dir": main_dir, "line": float(main_line[-1])},
            "pct_profitable_combos": frac_profit * 100.0, "avg_trades_per_combo": float(trades.mean()),
        })
        r.notes.append(f"Consenso: {up_frac[-1] * 100:.0f}% delle 100 combinazioni Supertrend in uptrend "
                       f"(5 barre fa {up_frac[max(0, n - 6)] * 100:.0f}%).")
        r.notes.append(f"Combinazione stabile ({lens[si]}, {mults[sj]:.1f}): trend {'UP' if st_tr == 1 else 'DOWN'}, "
                       f"trailing stop {_fmt(st_stop)}; ST({p.main_len},{p.main_mult:g}) {'UP' if main_dir == 1 else 'DOWN'}.")
        r.notes.append(f"Robustezza: {frac_profit * 100:.0f}% delle combinazioni in profitto netto; "
                       f"migliore {p.metric} = {z[bi, bj]:.2f} a ({lens[bi]}, {mults[bj]:.1f}).")
        return r


# =============================================================================
# SEZIONE 6 - BATCH 2
# =============================================================================

def _volume_rows(vols: np.ndarray, hi: float, lo: float, v: float, top: float, bot: float) -> None:
    """Distribuisce il volume di una barra sulle righe [bot, top] in proporzione alla sovrapposizione."""
    rows = len(vols)
    if v <= 0 or top <= bot or rows == 0:
        return
    rh = (top - bot) / rows
    if hi == lo:
        k = int(math.floor((hi - bot) / rh))
        vols[max(0, min(rows - 1, k))] += v
        return
    rb = bot + np.arange(rows) * rh
    ov = np.maximum(0.0, np.minimum(hi, rb + rh) - np.maximum(lo, rb))
    vols += v * ov / (hi - lo)


@register_module
class SessionVolumeMA(IndicatorModule):
    """
    Session Volume Moving Average [LuxAlgo]  -  (c) LuxAlgo, Mozilla Public License 2.0

    COME FUNZIONA (Pine)
      * Media mobile (SMA 50 di default, anche EMA/RMA/WMA/HMA/VWMA) con il
        volume disegnato come barre sopra/sotto la media.
      * Filtro sessioni (default: New York 09:30-16:00 America/New_York; anche
        Londra, Tokyo, Sydney): fuori sessione il volume e' ignorato.
      * DELTA DI SESSIONE: % di volume delle candele rialziste sul totale della
        sessione (gradiente rosso<50<verde tra 35% e 65%).
      * Streak di volume: >= 4 barre consecutive di volume crescente (o
        decrescente) con volume > 2x la media di 50 barre.
      * Volume profile della sessione (24 righe, prezzo di chiusura).

    COSA RESTITUISCE QUI
      posizione del prezzo rispetto alla media, delta % della sessione attiva
      (o dell'ultima), streak di volume in corso, POC/massimo/minimo di
      sessione.  Su timeframe >= D1 (sessioni non applicabili) il delta e il
      profilo vengono calcolati sulle ultime 20 barre.

    LIMITI
      Il delta usa il colore della candela (non l'order flow reale).
    """
    key = "svma"
    title = "Session Volume Moving Average"
    style = "volume"
    license = "MPL-2.0"
    batch = 2
    min_bars = 60

    @dataclass
    class Params:
        length: int = 50
        ma_type: str = "SMA"
        sessions: Tuple[Tuple[str, bool, str], ...] = (
            ("New York", True, "0930-1600"), ("London", False, "0300-1130"),
            ("Tokyo", False, "1800-0300"), ("Sydney", False, "1700-0200"))
        session_tz: str = "America/New_York"
        consec_bars: int = 4
        sig_vol_mult: float = 2.0
        vp_bins: int = 24
        fallback_bars: int = 20

    def compute(self, md: MarketData) -> ModuleResult:
        p, r = self.params, self.new_result()
        n, t = md.n, md.n - 1
        c, o, v = md.close, md.open, md.volume
        ma = moving_average(p.ma_type, c, p.length, v)
        a14 = md.last_atr(14)
        enabled = [s for s in p.sessions if s[1]]
        fallback = not md.is_intraday or not enabled
        if not fallback:
            local = md.local_index(p.session_tz)
            masks = [session_mask(local, md.bar_minutes, s[2]) for s in enabled]
            in_sess = np.logical_or.reduce(masks)
            new_sess = np.logical_or.reduce([m & ~np.r_[False, m[:-1]] for m in masks])
            vol = np.where(in_sess, v, 0.0)
        else:
            in_sess = np.ones(n, dtype=bool)
            new_sess = np.zeros(n, dtype=bool)
            vol = v.copy()
        # --- delta di sessione (loop come in Pine) ---
        bull_v = tot_v = 0.0
        sess_start = -1
        delta = np.full(n, 50.0)
        for i in range(n):
            if new_sess[i]:
                bull_v = vol[i] if c[i] > o[i] else 0.0
                tot_v = vol[i]
                sess_start = i
            elif in_sess[i] and not fallback:
                bull_v += vol[i] if c[i] > o[i] else 0.0
                tot_v += vol[i]
            delta[i] = bull_v / tot_v * 100.0 if tot_v > 0 else 50.0
        if fallback:
            k = min(p.fallback_bars, n)
            vv = v[-k:]
            tot = vv.sum()
            d_now = float(vv[c[-k:] > o[-k:]].sum() / tot * 100.0) if tot > 0 else 50.0
            s0, s1 = n - k, t
            active = True
        else:
            d_now = float(delta[t])
            active = bool(in_sess[t])
            s0 = sess_start if sess_start >= 0 else max(0, n - p.fallback_bars)
            s1 = t
            if not active:  # fine della sessione piu' recente
                idx = np.nonzero(in_sess[: t + 1])[0]
                s1 = int(idx[-1]) if len(idx) else t
        # --- streak di volume ---
        streak = 0
        streaks = np.zeros(n, dtype=int)
        for i in range(n):
            if in_sess[i]:
                pv = vol[i - 1] if i > 0 else 0.0
                if new_sess[i]:
                    streak = 0
                elif vol[i] > pv:
                    streak = streak + 1 if streak > 0 else 2
                elif vol[i] < pv:
                    streak = streak - 1 if streak < 0 else -2
                else:
                    streak = 0
            else:
                streak = 0
            streaks[i] = streak
        avg50 = sma(v, 50)
        for i in range(max(1, n - 30), n):
            s = streaks[i]
            if abs(s) == p.consec_bars and (p.sig_vol_mult == 0 or v[i] > _nz(avg50[i], np.inf) * p.sig_vol_mult):
                k0 = max(0, i - abs(s) + 1)
                d = _sign(c[i] - c[k0]) if s > 0 else 0
                r.add_signal(md, "VOL_STREAK_INC" if s > 0 else "VOL_STREAK_DEC", d, i, c[i], 0.5,
                             f"{abs(s)} barre di volume {'crescente' if s > 0 else 'decrescente'}")
        # --- volume profile della sessione ---
        poc = s_hi = s_lo = NAN
        if s1 >= s0:
            s_hi = float(np.max(md.high[s0:s1 + 1]))
            s_lo = float(np.min(md.low[s0:s1 + 1]))
            if s_hi > s_lo:
                bs = (s_hi - s_lo) / p.vp_bins
                bins = np.zeros(p.vp_bins)
                idx = np.clip(np.floor((c[s0:s1 + 1] - s_lo) / bs).astype(int), 0, p.vp_bins - 1)
                np.add.at(bins, idx, vol[s0:s1 + 1])
                if bins.max() > 0:
                    poc = s_lo + (int(np.argmax(bins)) + 0.5) * bs
        # --- bias ---
        ma_t = ma[t]
        pos_comp = _sign(c[t] - ma_t) * min(1.0, abs(c[t] - ma_t) / a14) if not _isnan(ma_t) and a14 > 0 else 0.0
        delta_comp = _clip((d_now - 50.0) / 15.0)
        bias = 0.5 * pos_comp + 0.5 * delta_comp
        rec = [s for s in r.signals if s.bars_ago <= 3 and s.direction != 0]
        if rec:
            bias += 0.2 * rec[-1].direction
        r.bias = bias
        r.confidence = 0.35 if fallback else 0.45
        above = not _isnan(ma_t) and c[t] > ma_t
        r.add_level(f"{p.ma_type} {p.length}", ma_t, "support" if above else "resistance", 0.8)
        r.add_level("POC sessione", poc, "magnet", 0.9)
        r.add_level("Massimo sessione", s_hi, "resistance", 0.5)
        r.add_level("Minimo sessione", s_lo, "support", 0.5)
        r.metrics.update({"ma": ma_t, "ma_type": p.ma_type, "delta_pct": d_now, "session_active": active,
                          "fallback_mode": fallback, "volume_streak": int(streaks[t]), "session_poc": poc,
                          "session_high": s_hi, "session_low": s_lo})
        mode = "ultime %d barre" % p.fallback_bars if fallback else ("sessione in corso" if active else "ultima sessione")
        r.notes.append(f"Prezzo {'sopra' if above else 'sotto'} la {p.ma_type}{p.length} ({_fmt(ma_t)}); "
                       f"delta volume rialzista {d_now:.0f}% ({mode}); POC sessione {_fmt(poc)}.")
        if abs(streaks[t]) >= p.consec_bars:
            r.notes.append(f"Streak di volume {'crescente' if streaks[t] > 0 else 'decrescente'} di {abs(streaks[t])} barre in corso.")
        return r


@register_module
class PeakActivityRange(IndicatorModule):
    """
    Peak Activity Range [LuxAlgo]  -  (c) LuxAlgo, CC BY-NC-SA 4.0

    COME FUNZIONA (Pine)
      * Ogni pivot high del VOLUME (10 barre per lato) definisce un nuovo range:
        massimo e minimo della candela a volume di picco (+ linea mediana).
      * Volume profile dentro il range (10 righe) con POC.
      * Segnali (una volta per direzione finche' il prezzo non riattraversa la
        mediana):
          - modalita' "Retest" (default): apertura sopra il top e chiusura sotto
            (retest dall'alto) = ▲; apertura sotto il bottom e chiusura sopra = ▼
          - modalita' "Breakout": chiusura che attraversa top (▲) o bottom (▼).
      * Al nuovo pivot i segnali successivi al pivot vengono rivalutati.

    COSA RESTITUISCE QUI
      range attivo (top, bottom, mediana, POC, colore della candela di picco,
      eta'), posizione del prezzo rispetto al range, segnali recenti.

    LIMITI
      Il pivot di volume e' confermato dopo 10 barre: il range nasce in ritardo
      e i segnali di quelle 10 barre sono calcolati retroattivamente.
    """
    key = "par"
    title = "Peak Activity Range"
    style = "breakout"
    batch = 2
    min_bars = 40

    @dataclass
    class Params:
        length: int = 10
        signal_mode: str = "Retest"
        vp_rows: int = 10
        recent_bars: int = 10

    def compute(self, md: MarketData) -> ModuleResult:
        p, r = self.params, self.new_result()
        n, t = md.n, md.n - 1
        h, l, o, c, v = md.high, md.low, md.open, md.close, md.volume
        vph = pivothigh(v, p.length, p.length)
        sigs: List[Tuple[int, int]] = []
        cur = None
        state = 0
        vols = np.zeros(p.vp_rows)
        n_ranges = 0

        def evaluate(j: int, rng: Dict[str, float], st: int) -> int:
            cp = c[j - 1] if j > 0 else NAN
            if (c[j] > rng["avg"] and cp <= rng["avg"]) or (c[j] < rng["avg"] and cp >= rng["avg"]):
                st = 0
            if p.signal_mode == "Breakout":
                up = c[j] > rng["top"] and cp <= rng["top"]
                dn = c[j] < rng["bot"] and cp >= rng["bot"]
            else:
                up = o[j] > rng["top"] and c[j] < rng["top"]
                dn = o[j] < rng["bot"] and c[j] > rng["bot"]
            if up and st != 1:
                st = 1
                sigs.append((j, 1))
            if dn and st != -1:
                st = -1
                sigs.append((j, -1))
            return st

        for i in range(n):
            if not math.isnan(vph[i]):
                piv = i - p.length
                sigs = [s for s in sigs if s[0] < piv]
                cur = dict(top=h[piv], bot=l[piv], avg=(h[piv] + l[piv]) / 2.0, bull=bool(c[piv] >= o[piv]), start=piv)
                n_ranges += 1
                state = 0
                vols = np.zeros(p.vp_rows)
                for j in range(piv, i + 1):
                    state = evaluate(j, cur, state)
                    if cur["top"] > cur["bot"]:
                        _volume_rows(vols, h[j], l[j], v[j], cur["top"], cur["bot"])
            elif cur is not None:
                state = evaluate(i, cur, state)
                if cur["top"] > cur["bot"]:
                    _volume_rows(vols, h[i], l[i], v[i], cur["top"], cur["bot"])
        if cur is None:
            r.applicable = False
            r.error = "nessun pivot di volume"
            return r
        for j, d in sigs:
            if t - j <= 100:
                r.add_signal(md, "RANGE_UP" if d == 1 else "RANGE_DOWN", d, j, c[j], 0.8,
                             f"{p.signal_mode.lower()} del range di picco")
        poc = cur["avg"]
        if vols.max() > 0 and cur["top"] > cur["bot"]:
            rh = (cur["top"] - cur["bot"]) / p.vp_rows
            poc = cur["bot"] + (int(np.argmax(vols)) + 0.5) * rh
        price = c[t]
        pos = "sopra" if price > cur["top"] else ("sotto" if price < cur["bot"] else "dentro")
        last = [s for s in r.signals if s.bars_ago <= p.recent_bars]
        if last:
            bias = last[-1].direction * _decay(last[-1].bars_ago, p.recent_bars)
        else:
            bias = 0.3 if pos == "sopra" else (-0.3 if pos == "sotto" else 0.0)
        r.bias = bias
        r.confidence = 0.45
        r.add_level("Top range di picco", cur["top"], "support" if price > cur["top"] else "resistance", 0.9)
        r.add_level("Bottom range di picco", cur["bot"], "support" if price > cur["bot"] else "resistance", 0.9)
        r.add_level("POC range di picco", poc, "magnet", 1.0)
        r.add_level("Mediana range di picco", cur["avg"], "magnet", 0.4)
        r.metrics.update({"range_top": cur["top"], "range_bottom": cur["bot"], "range_mid": cur["avg"], "range_poc": poc,
                          "peak_candle": "rialzista" if cur["bull"] else "ribassista", "range_age_bars": t - cur["start"],
                          "price_position": pos, "state": state, "ranges_found": n_ranges, "signal_mode": p.signal_mode})
        r.notes.append(f"Range di picco volume ({'candela rialzista' if cur['bull'] else 'candela ribassista'}, "
                       f"{t - cur['start']} barre fa): {_fmt(cur['bot'])} - {_fmt(cur['top'])}, POC {_fmt(poc)}; prezzo {pos}.")
        if last:
            r.notes.append(f"Ultimo segnale {'▲' if last[-1].direction == 1 else '▼'} {last[-1].bars_ago} barre fa.")
        return r


@register_module
class SignalForge(IndicatorModule):
    """
    Signal Forge [LuxAlgo]  -  (c) LuxAlgo, CC BY-NC-SA 4.0

    COME FUNZIONA (Pine)
      11 indicatori classici trasformati in stati Bullish/Bearish:
        SMA 10/20 cross, RSI 14 vs 50, MACD vs segnale, Supertrend (3,10),
        Stocastico %K (14,3,3) vs 50, prezzo vs media Bollinger (20,2),
        EMA 10/20 cross, Awesome Oscillator vs 0, Parabolic SAR, CCI 20 vs 0,
        ADX(14) > 20 con +DI/-DI.
      * Ogni indicatore ha un backtest "standalone" (entra alla transizione verso
        lo stato, esce sullo stato opposto) -> win-rate individuale.
      * Segnale combinato: tutti gli indicatori ABILITATI devono concordare
        (require all) oppure ne basta uno; backtest interno con SL/TP/trailing
        ATR opzionali.  Default Pine: solo SMA cross abilitato.

    COSA RESTITUISCE QUI
      pannello di voto di tutti e 11 gli indicatori pesato per il loro win-rate
      standalone, segnale combinato secondo la configurazione, statistiche del
      backtest, voto di regime da ADX.
    """
    key = "sf"
    title = "Signal Forge"
    style = "ensemble"
    batch = 2
    min_bars = 60

    NAMES = ("SMA Cross", "RSI", "MACD", "Supertrend", "Stochastic", "Bollinger", "EMA Cross", "AO", "SAR", "CCI", "ADX")

    @dataclass
    class Params:
        require_all: bool = True
        enabled: Tuple[str, ...] = ("SMA Cross",)
        atr_len: int = 14
        enable_tp: bool = False
        tp_mult: float = 2.0
        enable_sl: bool = False
        sl_mult: float = 1.5
        enable_ts: bool = False
        ts_mult: float = 1.0
        sma_fast: int = 10
        sma_slow: int = 20
        rsi_len: int = 14
        rsi_long: float = 50.0
        rsi_short: float = 50.0
        macd_fast: int = 12
        macd_slow: int = 26
        macd_signal: int = 9
        st_factor: float = 3.0
        st_len: int = 10
        stoch_k: int = 14
        stoch_smooth: int = 3
        bb_len: int = 20
        bb_mult: float = 2.0
        ema_fast: int = 10
        ema_slow: int = 20
        sar_start: float = 0.02
        sar_inc: float = 0.02
        sar_max: float = 0.2
        cci_len: int = 20
        cci_long: float = 0.0
        cci_short: float = 0.0
        di_len: int = 14
        adx_len: int = 14
        adx_threshold: float = 20.0

    def _states(self, md: MarketData) -> Tuple[List[np.ndarray], List[np.ndarray], Dict[str, np.ndarray]]:
        p = self.params
        c, h, l = md.close, md.high, md.low
        with np.errstate(invalid="ignore"):
            sf_, ss_ = sma(c, p.sma_fast), sma(c, p.sma_slow)
            rs = rsi(c, p.rsi_len)
            m, s, _ = macd(c, p.macd_fast, p.macd_slow, p.macd_signal)
            st_line, st_dir = supertrend(h, l, c, p.st_factor, p.st_len)
            k = sma(stoch(c, h, l, p.stoch_k), p.stoch_smooth)
            bb_mid, _, _ = bollinger(c, p.bb_len, p.bb_mult)
            ef, es = ema(c, p.ema_fast), ema(c, p.ema_slow)
            ao = sma(md.hl2, 5) - sma(md.hl2, 34)
            sar = parabolic_sar(h, l, c, p.sar_start, p.sar_inc, p.sar_max)
            cc = cci(c, p.cci_len)
            dip, dim, adx = dmi(h, l, c, p.di_len, p.adx_len)
            bull = [sf_ > ss_, rs > p.rsi_long, m > s, st_dir == -1, k > 50, c > bb_mid, ef > es, ao > 0, c > sar,
                    cc > p.cci_long, (adx > p.adx_threshold) & (dip > dim)]
            bear = [sf_ < ss_, rs < p.rsi_short, m < s, st_dir == 1, k < 50, c < bb_mid, ef < es, ao < 0, c < sar,
                    cc < p.cci_short, (adx > p.adx_threshold) & (dim > dip)]
        extra = dict(sar=sar, st_line=st_line, bb_mid=bb_mid, adx=adx, dip=dip, dim=dim)
        return bull, bear, extra

    def _backtest(self, md: MarketData, bull: np.ndarray, bear: np.ndarray) -> Dict[str, Any]:
        """Backtest stile Signal Forge: entra sulla transizione verso lo stato, esce su stato opposto o SL/TP/TS."""
        p = self.params
        c, h, l = md.close.tolist(), md.high.tolist(), md.low.tolist()
        a = md.atr(p.atr_len).tolist()
        state, entry, sl, tp, ts = 0, NAN, NAN, NAN, NAN
        prev_b = prev_s = False
        rets: List[float] = []
        entries: List[Tuple[int, int]] = []
        for i in range(len(c)):
            b, s = bool(bull[i]), bool(bear[i])
            px = None
            if state == 1:
                if p.enable_sl and l[i] <= sl:
                    px = sl
                elif p.enable_tp and h[i] >= tp:
                    px = tp
                elif p.enable_ts and l[i] <= ts:
                    px = ts
                elif s:
                    px = c[i]
                if px is not None:
                    rets.append((px - entry) / entry * 100.0)
                    state, sl, tp, ts = 0, NAN, NAN, NAN
            elif state == -1:
                if p.enable_sl and h[i] >= sl:
                    px = sl
                elif p.enable_tp and l[i] <= tp:
                    px = tp
                elif p.enable_ts and h[i] >= ts:
                    px = ts
                elif b:
                    px = c[i]
                if px is not None:
                    rets.append((entry - px) / entry * 100.0)
                    state, sl, tp, ts = 0, NAN, NAN, NAN
            enter_l = b and not prev_b and state != 1
            enter_s = s and not prev_s and state != -1
            if enter_l:
                state, entry = 1, c[i]
                sl, tp, ts = c[i] - a[i] * p.sl_mult, c[i] + a[i] * p.tp_mult, c[i] - a[i] * p.ts_mult
                entries.append((i, 1))
            if enter_s:
                state, entry = -1, c[i]
                sl, tp, ts = c[i] + a[i] * p.sl_mult, c[i] - a[i] * p.tp_mult, c[i] + a[i] * p.ts_mult
                entries.append((i, -1))
            if state == 1 and not enter_l and p.enable_ts:
                ts = max(ts, c[i] - a[i] * p.ts_mult)
            if state == -1 and not enter_s and p.enable_ts:
                ts = min(ts, c[i] + a[i] * p.ts_mult)
            prev_b, prev_s = b, s
        out = _trade_stats(rets)
        out.update(state=state, entry=entry, entries=entries)
        return out

    def compute(self, md: MarketData) -> ModuleResult:
        p, r = self.params, self.new_result()
        n, t = md.n, md.n - 1
        bull, bear, ex = self._states(md)
        panel = []
        num = den = 0.0
        for i, name in enumerate(self.NAMES):
            bt = self._backtest(md, bull[i], bear[i])
            s = 1 if bull[i][t] else (-1 if bear[i][t] else 0)
            wr = bt["win_rate"]
            wgt = max(0.25, wr / 50.0) if bt["trades"] >= 5 else 1.0
            num += wgt * s
            den += wgt
            panel.append({"indicator": name, "status": {1: "Bullish", -1: "Bearish", 0: "Neutral"}[s],
                          "standalone_win_rate": wr, "trades": bt["trades"], "weight": wgt,
                          "enabled": name in p.enabled})
        # --- segnale combinato (configurazione Pine) ---
        en = [i for i, nm in enumerate(self.NAMES) if nm in p.enabled]
        if en:
            if p.require_all:
                lc = np.logical_and.reduce([bull[i] for i in en])
                sc = np.logical_and.reduce([bear[i] for i in en])
            else:
                lc = np.logical_or.reduce([bull[i] for i in en])
                sc = np.logical_or.reduce([bear[i] for i in en])
        else:
            lc = sc = np.zeros(n, dtype=bool)
        comb = self._backtest(md, lc, sc)
        for (i, d) in comb["entries"]:
            if t - i <= 10:
                r.add_signal(md, "FORGE_LONG" if d == 1 else "FORGE_SHORT", d, i, md.close[i], 0.7,
                             "ingresso del segnale combinato")
        bulls = sum(1 for x in panel if x["status"] == "Bullish")
        bears = sum(1 for x in panel if x["status"] == "Bearish")
        r.bias = _safe_div(num, den)
        adx_t = ex["adx"][t]
        if not _isnan(adx_t):
            r.regime = _clip((adx_t - 20.0) / 15.0)
            r.regime_confidence = 0.5
        good_bt = comb["trades"] >= 10 and comb["profit_factor"] > 1.0
        r.confidence = 0.35 + 0.35 * abs(bulls - bears) / len(self.NAMES) + (0.15 if good_bt else 0.0)
        sar_t = ex["sar"][t]
        r.add_level("Parabolic SAR", sar_t, "support" if md.close[t] > sar_t else "resistance", 0.6)
        r.add_level(f"Supertrend ({p.st_factor:g},{p.st_len})", ex["st_line"][t],
                    "support" if md.close[t] > ex["st_line"][t] else "resistance", 0.6)
        r.add_level(f"Media Bollinger {p.bb_len}", ex["bb_mid"][t], "magnet", 0.4)
        cur_sig = "LONG" if lc[t] else ("SHORT" if sc[t] else "NEUTRAL")
        r.metrics.update({"panel": panel, "bullish": bulls, "bearish": bears, "adx": adx_t,
                          "combined_signal": cur_sig, "enabled": list(p.enabled), "require_all": p.require_all,
                          "combined_backtest": {k: comb[k] for k in ("trades", "win_rate", "profit_factor", "net", "max_dd")},
                          "combined_state": comb["state"]})
        best = sorted([x for x in panel if x["trades"] >= 5], key=lambda x: -x["standalone_win_rate"])[:3]
        r.notes.append(f"Pannello 11 indicatori: {bulls} rialzisti, {bears} ribassisti, {11 - bulls - bears} neutri; "
                       f"ADX {_fmt(adx_t, 1)}.")
        r.notes.append(f"Segnale combinato ({'tutti' if p.require_all else 'almeno uno'} di {', '.join(p.enabled)}): {cur_sig}; "
                       f"backtest {comb['trades']} trade, WR {comb['win_rate']:.0f}%, PF {comb['profit_factor']:.2f}.")
        if best:
            r.notes.append("Indicatori con win-rate standalone migliore: " +
                           ", ".join(f"{x['indicator']} {x['standalone_win_rate']:.0f}% ({x['status']})" for x in best) + ".")
        return r


@register_module
class ATRExceedanceModel(IndicatorModule):
    """
    ATR Exceedance Probability Model [LuxAlgo]  -  (c) LuxAlgo, CC BY-NC-SA 4.0

    COME FUNZIONA (Pine)
      * Sforamento: il massimo supera high[1] + 1.5*ATR[1] o il minimo scende
        sotto low[1] - 1.5*ATR[1] (default "Price vs Previous ATR Level"),
        oppure True Range > 1.5*ATR.
      * Frequenza di sforamento a breve (20 barre) e di base (200), z-score della
        frequenza a breve rispetto alla sua storia (significativo oltre 1.96).
      * Probabilita' di continuazione: P(sforamento | sforamento alla barra
        precedente) sulle ultime 20 barre; "Clustering Edge" = continuazione -
        frequenza (volatilita' che si auto-alimenta).
      * Regime di volatilita' dallo z-score dell'ATR su 200 barre:
        > +1 High Vol, < -1 Quiet, altrimenti Normal.

    COSA RESTITUISCE QUI
      asse di VOLATILITA' per il motore (non direzionale), probabilita' di
      espansione, clustering, direzione prevalente degli sforamenti recenti
      (usata solo come lieve indizio di momentum) e le soglie ATR della
      prossima barra.
    """
    key = "atrp"
    title = "ATR Exceedance Probability Model"
    style = "volatility"
    batch = 2
    min_bars = 220

    @dataclass
    class Params:
        atr_len: int = 14
        threshold: float = 1.5
        detect_method: str = "Price vs Previous ATR Level"   # oppure "True Range vs ATR"
        band_mode: str = "High/Low Offset"                   # oppure "Central Basis"
        band_method: str = "SMA"
        basis_len: int = 20
        short_window: int = 20
        long_window: int = 200
        z_conf: float = 1.96

    def compute(self, md: MarketData) -> ModuleResult:
        p, r = self.params, self.new_result()
        n, t = md.n, md.n - 1
        h, l, c, o = md.high, md.low, md.close, md.open
        tr_ = md.tr(True)
        a = md.atr(p.atr_len)
        basis = c.copy() if p.band_method == "Price" else moving_average(p.band_method, c, p.basis_len, md.volume)
        if p.band_mode == "Central Basis":
            upper, lower = basis + a * p.threshold, basis - a * p.threshold
        else:
            upper, lower = h + a * p.threshold, l - a * p.threshold
        with np.errstate(invalid="ignore"):
            if p.detect_method == "True Range vs ATR":
                exceed = tr_ > a * p.threshold
                up_b = exceed & (c >= o)
                dn_b = exceed & (c < o)
            else:
                up_b = h > shift(upper)
                dn_b = l < shift(lower)
                exceed = up_b | dn_b
        ex = exceed.astype(float)
        cur = sma(ex, p.short_window) * 100.0
        base = sma(ex, p.long_window) * 100.0
        bm, bsd = sma(cur, p.long_window), stdev(cur, p.long_window)
        with np.errstate(invalid="ignore", divide="ignore"):
            z = np.where(bsd > 0, (cur - bm) / bsd, np.nan)
        prev_cnt = cont = 0
        for i in range(p.short_window):
            j = t - i
            if j - 1 >= 0 and ex[j - 1] == 1.0:
                prev_cnt += 1
                if ex[j] == 1.0:
                    cont += 1
        prob = cont / prev_cnt * 100.0 if prev_cnt > 0 else 0.0
        edge = prob - _nz(cur[t])
        atr_z = (a[t] - sma(a, p.long_window)[t]) / max(_nz(stdev(a, p.long_window)[t]), 1e-6)
        regime = "High Vol" if atr_z > 1.0 else ("Quiet" if atr_z < -1.0 else "Normal")
        w = slice(max(0, n - p.short_window), n)
        ups, dns = int(up_b[w].sum()), int(dn_b[w].sum())
        r.bias = 0.5 * _safe_div(ups - dns, ups + dns)
        r.confidence = 0.3
        r.volatility = _clip(atr_z / 2.0)
        for i in range(max(0, n - 5), n):
            if exceed[i]:
                sig = not _isnan(z[i]) and z[i] > p.z_conf
                r.add_signal(md, "SIGNIFICANT_BREACH" if sig else "ATR_BREACH", 1 if up_b[i] else -1, i, c[i],
                             0.6 if sig else 0.3, "sforamento della soglia ATR")
        expansion = prob if exceed[t] else _nz(cur[t])
        r.metrics.update({"next_bar_upper": upper[t], "next_bar_lower": lower[t], "atr": a[t], "atr_z": atr_z, "vol_regime": regime, "exceed_freq_pct": cur[t],
                          "baseline_freq_pct": base[t], "freq_z": z[t], "continuation_prob_pct": prob,
                          "cluster_edge_pct": edge, "expansion_prob_pct": expansion, "breaches_up": ups,
                          "breaches_down": dns, "last_bar_exceeded": bool(exceed[t])})
        r.notes.append(f"Regime di volatilita' {regime} (z ATR {atr_z:+.2f}); frequenza sforamenti {_nz(cur[t]):.0f}% "
                       f"vs base {_nz(base[t]):.0f}% (z {_nz(z[t]):+.2f}).")
        r.notes.append(f"Probabilita' di sforamento consecutivo {prob:.0f}% (clustering edge {edge:+.0f}%); "
                       f"sforamenti recenti: {ups} al rialzo, {dns} al ribasso.")
        return r


# =============================================================================
# SEZIONE 7 - BATCH 3
# =============================================================================

@register_module
class HistoricalLiquidityProximity(IndicatorModule):
    """
    Historical Liquidity Proximity Heatmap [LuxAlgo]  -  (c) LuxAlgo, CC BY-NC-SA 4.0

    COME FUNZIONA (Pine)
      * Memorizza gli ultimi 200 pivot high e 200 pivot low (20/20 barre) con il
        volume della barra di pivot: sono i punti dove si accumulano stop/ordini.
      * Ad ogni barra mostra i 10 pivot high PIU' VICINI sopra il massimo attuale
        e i 10 pivot low piu' vicini sotto il minimo, colorati per volume.
      * "VWAP Highs/Lows": media dei prezzi di quei pivot pesata per volume ->
        baricentro della liquidita' sopra e sotto il prezzo.

    COSA RESTITUISCE QUI
      liquidita' storica piu' vicina sopra/sotto (livelli e volumi), i due
      baricentri VWAP, sbilanciamento di liquidita' entro 5 ATR (il prezzo tende
      ad essere attratto verso il bacino di liquidita' maggiore: indizio debole).
    """
    key = "hlph"
    title = "Historical Liquidity Proximity"
    style = "structure"
    batch = 3
    min_bars = 60

    @dataclass
    class Params:
        left: int = 20
        right: int = 20
        buffer_size: int = 200
        num_points: int = 10
        proximity_atr: float = 5.0

    def compute(self, md: MarketData) -> ModuleResult:
        p, r = self.params, self.new_result()
        t = md.n - 1
        v = md.volume
        ph = pivothigh(md.high, p.left, p.right)
        pl = pivotlow(md.low, p.left, p.right)
        hi_idx = np.nonzero(~np.isnan(ph))[0][-p.buffer_size:]
        lo_idx = np.nonzero(~np.isnan(pl))[0][-p.buffer_size:]
        highs = [(float(ph[i]), float(v[i - p.right])) for i in hi_idx]
        lows = [(float(pl[i]), float(v[i - p.right])) for i in lo_idx]
        allv = [x[1] for x in highs + lows]
        vmin, vmax = (min(allv), max(allv)) if allv else (0.0, 1.0)
        above = sorted([x for x in highs if x[0] > md.high[t]], key=lambda x: x[0] - md.high[t])[:p.num_points]
        below = sorted([x for x in lows if x[0] < md.low[t]], key=lambda x: md.low[t] - x[0])[:p.num_points]
        vw = lambda pts: _safe_div(sum(a * b for a, b in pts), sum(b for _, b in pts), NAN)
        vwap_h, vwap_l = vw(above), vw(below)
        a14 = md.last_atr(14)
        c = md.close[t]
        near_up = sum(b for a, b in above if a - c <= p.proximity_atr * a14)
        near_dn = sum(b for a, b in below if c - a <= p.proximity_atr * a14)
        r.bias = 0.3 * _safe_div(near_up - near_dn, near_up + near_dn)
        r.confidence = 0.25
        norm = lambda x: _safe_div(x - vmin, vmax - vmin, 0.5)
        for k, (pr, vol) in enumerate(above[:3]):
            r.add_level(f"Liquidita' sopra #{k + 1}", pr, "liquidity", 0.4 + 0.5 * norm(vol))
        for k, (pr, vol) in enumerate(below[:3]):
            r.add_level(f"Liquidita' sotto #{k + 1}", pr, "liquidity", 0.4 + 0.5 * norm(vol))
        r.add_level("VWAP pivot high (liquidita' sopra)", vwap_h, "resistance", 0.8)
        r.add_level("VWAP pivot low (liquidita' sotto)", vwap_l, "support", 0.8)
        r.metrics.update({"vwap_highs": vwap_h, "vwap_lows": vwap_l, "levels_above": [a for a, _ in above],
                          "levels_below": [a for a, _ in below], "near_liquidity_above": near_up,
                          "near_liquidity_below": near_dn})
        r.notes.append(f"Liquidita' storica: {len(above)} pivot sopra (baricentro {_fmt(vwap_h)}), "
                       f"{len(below)} sotto (baricentro {_fmt(vwap_l)}).")
        if above:
            r.notes.append(f"Resistenza di liquidita' piu' vicina {_fmt(above[0][0])}; supporto piu' vicino "
                           f"{_fmt(below[0][0]) if below else 'n/d'}.")
        return r


@register_module
class OrderFlowVWAPDeviation(IndicatorModule):
    """
    Order Flow VWAP Deviation [LuxAlgo]  -  (c) LuxAlgo, CC BY-NC-SA 4.0

    COME FUNZIONA (Pine)
      * VWAP ancorato (sessione/settimana/mese/anno) su hlc3 con bande +/- 2 dev.
      * "Stop Zones": pivot 50/50 (livelli dove stanno gli stop).  Quando il
        prezzo li attraversa con volume > 1.2x la media a 20 -> "stops triggered"
        (caccia agli stop / presa di liquidita').
      * IFVG (disattivati di default in Pine, qui attivi): Fair Value Gap creato
        da una candela di corpo > 1.2x la media; se il prezzo chiude oltre il gap
        nel verso opposto il gap si "inverte" e diventa supporto/resistenza
        finche' non viene mitigato.
      * Profilo di volume dall'ancora giornaliera 18:00 (GMT-4) con POC e "stop
        zones" (righe con volume > 1.5x la media) marcate B/S secondo il lato
        dominante (proxy close-location).

    COSA RESTITUISCE QUI
      deviazione del prezzo dal VWAP in sigma (sopra VWAP = controllo dei
      compratori; oltre +/-2 sigma = estensione da mean-reversion), eventi di
      stop-run, IFVG attivi, POC e stop zones del profilo di sessione.
    """
    key = "ofvd"
    title = "Order Flow VWAP Deviation"
    style = "hybrid"
    batch = 3
    min_bars = 120

    @dataclass
    class Params:
        vwap_anchor: str = "Session"        # Session | Week | Month | Year
        vwap_tz: Optional[str] = None       # None = fuso dei dati (ora server MT5)
        std_mult: float = 2.0
        pivot_lookback: int = 50
        max_active_lines: int = 10
        vp_rows: int = 50
        anchor_time: str = "1800"
        anchor_tz: str = "GMT-4"
        stop_threshold: float = 1.5
        use_ifvg: bool = True
        ifvg_vol_filter: float = 1.2
        ifvg_history: int = 5
        max_open_fvg: int = 200
        recent_bars: int = 5

    def compute(self, md: MarketData) -> ModuleResult:
        p, r = self.params, self.new_result()
        n, t = md.n, md.n - 1
        h, l, o, c, v = md.high, md.low, md.open, md.close, md.volume
        # --- VWAP ancorato ---
        loc = md.local_index(p.vwap_tz or md.data_tz)
        if p.vwap_anchor == "Week":
            key = (loc.isocalendar().year.to_numpy() * 100 + loc.isocalendar().week.to_numpy())
        elif p.vwap_anchor == "Month":
            key = loc.year.to_numpy() * 100 + loc.month.to_numpy()
        elif p.vwap_anchor == "Year":
            key = loc.year.to_numpy()
        else:
            key = loc.year.to_numpy() * 10000 + loc.month.to_numpy() * 100 + loc.day.to_numpy()
        key = np.asarray(key)
        reset = np.r_[True, key[1:] != key[:-1]]
        vw, up_b, lo_b, sd = anchored_vwap(md.hlc3, v, reset, p.std_mult)
        z = (c[t] - vw[t]) / sd[t] if sd[t] > 0 else 0.0
        # --- stop lines su pivot 50/50 ---
        ph = pivothigh(h, p.pivot_lookback, p.pivot_lookback)
        pl = pivotlow(l, p.pivot_lookback, p.pivot_lookback)
        avg20 = sma(v, 20)
        up_lines: List[float] = []
        lo_lines: List[float] = []
        for i in range(n):
            if not math.isnan(ph[i]):
                up_lines.insert(0, float(ph[i]))
                if len(up_lines) > p.max_active_lines:
                    up_lines.pop()
            if not math.isnan(pl[i]):
                lo_lines.insert(0, float(pl[i]))
                if len(lo_lines) > p.max_active_lines:
                    lo_lines.pop()
            hit_u = [x for x in up_lines if h[i] >= x]
            if hit_u:
                up_lines = [x for x in up_lines if h[i] < x]
                if v[i] > _nz(avg20[i], np.inf) * 1.2 and t - i <= 50:
                    r.add_signal(md, "BUY_STOPS_RUN", -1, i, max(hit_u), 0.4, "stop sopra pivot high presi con volume")
            hit_l = [x for x in lo_lines if l[i] <= x]
            if hit_l:
                lo_lines = [x for x in lo_lines if l[i] > x]
                if v[i] > _nz(avg20[i], np.inf) * 1.2 and t - i <= 50:
                    r.add_signal(md, "SELL_STOPS_RUN", 1, i, min(hit_l), 0.4, "stop sotto pivot low presi con volume")
        # --- IFVG ---
        ifvgs: List[Dict[str, Any]] = []
        if p.use_ifvg:
            body = np.abs(c - o)
            avg_body = sma(body, 50)
            bear_fvg: List[Tuple[float, float, int]] = []
            bull_fvg: List[Tuple[float, float, int]] = []
            for i in range(2, n):
                valid = body[i - 1] > _nz(avg_body[i], np.inf) * p.ifvg_vol_filter
                if valid and h[i] < l[i - 2]:
                    bear_fvg.insert(0, (l[i - 2], h[i], i - 1))
                if valid and l[i] > h[i - 2]:
                    bull_fvg.insert(0, (l[i], h[i - 2], i - 1))
                del bear_fvg[p.max_open_fvg:]
                del bull_fvg[p.max_open_fvg:]
                for fv in [f for f in bear_fvg if c[i] > f[0]]:
                    bear_fvg.remove(fv)
                    ifvgs.insert(0, dict(top=fv[0], btm=fv[1], bull=True, idx=i))
                for fv in [f for f in bull_fvg if c[i] < f[1]]:
                    bull_fvg.remove(fv)
                    ifvgs.insert(0, dict(top=fv[0], btm=fv[1], bull=False, idx=i))
                del ifvgs[p.ifvg_history:]
                ifvgs = [z_ for z_ in ifvgs if not ((z_["bull"] and c[i] < z_["btm"]) or (not z_["bull"] and c[i] > z_["top"]))]
        # --- profilo dall'ancora di sessione ---
        aloc = md.local_index(p.anchor_tz)
        amin = int(p.anchor_time[:2]) * 60 + int(p.anchor_time[2:4])
        tday = (aloc - pd.Timedelta(minutes=amin)).normalize()
        tkey = tday.asi8
        anchor_idx = np.nonzero(np.r_[True, tkey[1:] != tkey[:-1]])[0]
        s0 = int(anchor_idx[-1])
        prices, vols = c[s0:], v[s0:]
        rng = np.maximum(h[s0:] - l[s0:], md.mintick)
        bvol, svol = vols * (prices - l[s0:]) / rng, vols * (h[s0:] - prices) / rng
        poc = NAN
        stop_zones = []
        s_hi, s_lo = float(prices.max()), float(prices.min())
        if s_hi > s_lo:
            bs = (s_hi - s_lo) / p.vp_rows
            bidx = np.clip(np.floor((prices - s_lo) / bs).astype(int), 0, p.vp_rows - 1)
            bins, bb, sb = np.zeros(p.vp_rows), np.zeros(p.vp_rows), np.zeros(p.vp_rows)
            np.add.at(bins, bidx, vols)
            np.add.at(bb, bidx, bvol)
            np.add.at(sb, bidx, svol)
            if bins.max() > 0:
                pi = int(np.argmax(bins))
                poc = s_lo + (pi + 0.5) * bs
                avg_v = bins.sum() / p.vp_rows
                for i in range(p.vp_rows):
                    if bins[i] > avg_v * p.stop_threshold and i != pi:
                        stop_zones.append(dict(price=s_lo + (i + 0.5) * bs, mult=bins[i] / avg_v,
                                               side="B" if bb[i] > sb[i] else "S"))
        # --- bias ---
        if abs(z) <= p.std_mult:
            bias = 0.5 * _clip(z)
        else:
            bias = -0.6 * _sign(z)
        for zf in ifvgs:
            ago = t - zf["idx"]
            d = 1 if zf["bull"] else -1
            if ago <= p.recent_bars:
                bias += 0.4 * d * _decay(ago, p.recent_bars + 1)
                r.add_signal(md, "IFVG_BULL" if zf["bull"] else "IFVG_BEAR", d, zf["idx"], c[zf["idx"]], 0.6,
                             "fair value gap invertito")
            elif zf["btm"] <= c[t] <= zf["top"]:
                bias += 0.3 * d
        r.bias = bias
        r.confidence = 0.5
        r.add_level("VWAP", vw[t], "magnet", 1.2)
        r.add_level(f"VWAP +{p.std_mult:g}sd", up_b[t], "resistance", 0.8)
        r.add_level(f"VWAP -{p.std_mult:g}sd", lo_b[t], "support", 0.8)
        for k, x in enumerate(sorted(up_lines)[:3]):
            r.add_level(f"Stop pool sopra #{k + 1}", x, "liquidity", 0.6)
        for k, x in enumerate(sorted(lo_lines, reverse=True)[:3]):
            r.add_level(f"Stop pool sotto #{k + 1}", x, "liquidity", 0.6)
        for zf in ifvgs:
            mid = (zf["top"] + zf["btm"]) / 2.0
            r.add_level("IFVG rialzista" if zf["bull"] else "IFVG ribassista", mid,
                        "support" if zf["bull"] else "resistance", 0.8, zf["top"], zf["btm"])
        r.add_level("POC profilo sessione", poc, "magnet", 1.0)
        for sz in stop_zones[:4]:
            r.add_level(f"Stop zone {sz['side']} ({sz['mult']:.1f}x)", sz["price"], "level", 0.5)
        r.metrics.update({"vwap": vw[t], "vwap_upper": up_b[t], "vwap_lower": lo_b[t], "vwap_z": z,
                          "active_stop_lines_above": sorted(up_lines), "active_stop_lines_below": sorted(lo_lines),
                          "active_ifvg": ifvgs, "session_poc": poc, "session_anchor_bar": s0, "stop_zones": stop_zones})
        r.notes.append(f"Prezzo a {z:+.2f} sigma dal VWAP {p.vwap_anchor.lower()} ({_fmt(vw[t])}); "
                       f"bande {_fmt(lo_b[t])} / {_fmt(up_b[t])}.")
        r.notes.append(f"Stop pool attivi: {len(up_lines)} sopra, {len(lo_lines)} sotto; IFVG attivi: {len(ifvgs)}; "
                       f"POC dall'ancora {p.anchor_time} {p.anchor_tz}: {_fmt(poc)}.")
        runs = [s for s in r.signals if s.name.endswith("STOPS_RUN") and s.bars_ago <= 10]
        if runs:
            r.notes.append(f"Caccia agli stop recente: {runs[-1].name} {runs[-1].bars_ago} barre fa a {_fmt(runs[-1].price)}.")
        return r


@register_module
class LiquidityDeltaProfiler(IndicatorModule):
    """
    Liquidity Delta Profiler [LuxAlgo]  -  (c) LuxAlgo, CC BY-NC-SA 4.0

    COME FUNZIONA (Pine)
      * Zone di liquidita' dai pivot 15/15: BSL (buy-side, sopra) = dal corpo al
        massimo della candela di pivot high; SSL (sell-side, sotto) = dal minimo
        al corpo della candela di pivot low.  Filtro sovrapposizioni, max 10.
      * Ogni zona e' divisa in 4 quadranti: il delta di ogni barra
        (volume*(close-open)/range) viene ripartito sui quadranti toccati.
      * "Salute" della zona: 100% - volume assorbito / (5 x volume medio).
      * Sweep = massimo oltre la BSL (o minimo sotto la SSL).  Al tocco/sweep si
        cercano 4 pattern di inversione:
          ABS  assorbimento: il quadrante esterno ha delta contrario allo sweep
          EXH  esaurimento: sweep con volume quasi nullo sul bordo esterno
          DIV  divergenza/FOMO: forte delta nel verso dello sweep ma chiusura
               dentro la zona (breakout fallito)
          REJ  snapback: sweep e chiusura oltre la meta' con delta di barra opposto
      * Statistiche: vittoria se entro 10 barre il prezzo resta in profitto per
        3 chiusure consecutive.

    COSA RESTITUISCE QUI
      zone BSL/SSL attive con salute (resistenze/supporti), segnali di
      inversione recenti con significativita' e win-rate storico per tipo.
    """
    key = "ldp"
    title = "Liquidity Delta Profiler"
    style = "reversion"
    batch = 3
    min_bars = 60

    @dataclass
    class Params:
        length: int = 15
        max_zones: int = 10
        filter_overlaps: bool = True
        zone_capacity: float = 5.0
        enable_reversals: bool = True
        eval_window: int = 10
        hold_bars: int = 3
        recent_bars: int = 10

    def compute(self, md: MarketData) -> ModuleResult:
        p, r = self.params, self.new_result()
        n, t = md.n, md.n - 1
        h, l, o, c, v = md.high, md.low, md.open, md.close, np.nan_to_num(md.volume)
        a = md.atr(14)
        L = p.length
        ph, pl = pivothigh(h, L, L), pivotlow(l, L, L)
        avgv = np.nan_to_num(sma(v, L))
        zones = {True: [], False: []}   # True = BSL
        trades: List[Dict[str, Any]] = []
        stats = {k: [0, 0] for k in ("ABS", "EXH", "DIV", "REJ")}
        sigs: List[Dict[str, Any]] = []

        def new_zone(is_bsl: bool, top: float, bot: float, i: int) -> None:
            lst = zones[is_bsl]
            if p.filter_overlaps:
                for k in range(len(lst) - 1, -1, -1):
                    ex = lst[k]
                    if not ex["swept"] and max(bot, ex["bottom"]) <= min(top, ex["top"]):
                        if (is_bsl and top > ex["top"]) or (not is_bsl and bot < ex["bottom"]):
                            lst.pop(k)
                        else:
                            return
            cap = (avgv[i] if avgv[i] > 0 else 1.0) * p.zone_capacity
            lst.insert(0, dict(top=top, bottom=bot, left=i - L, swept=False, signaled=False, deltas=[0.0] * 4,
                               vol=0.0, cap=cap, sweep_idx=-1))
            del lst[p.max_zones:]

        for i in range(n):
            if not math.isnan(ph[i]):
                pi = i - L
                top, bot = h[pi], max(c[pi], o[pi])
                if top - bot < _nz(a[pi], 0.0) * 0.1:
                    bot = top - a[pi] * 0.1
                new_zone(True, top, bot, i)
            if not math.isnan(pl[i]):
                pi = i - L
                bot, top = l[pi], min(c[pi], o[pi])
                if top - bot < _nz(a[pi], 0.0) * 0.1:
                    top = bot + a[pi] * 0.1
                new_zone(False, top, bot, i)
            rng = h[i] - l[i]
            bdelta = 0.0 if rng == 0 else v[i] * (c[i] - o[i]) / rng
            for is_bsl in (True, False):
                for z in reversed(zones[is_bsl]):
                    if z["swept"]:
                        continue
                    step = (z["top"] - z["bottom"]) / 4.0
                    hit = False
                    for j in range(4):
                        qb, qt = z["bottom"] + j * step, z["bottom"] + (j + 1) * step
                        ov = min(h[i], qt) - max(l[i], qb)
                        if ov > 0:
                            hit = True
                            ratio = 0.0 if rng == 0 else ov / rng
                            z["deltas"][j] += bdelta * ratio
                            z["vol"] += v[i] * ratio
                    if (is_bsl and h[i] > z["top"]) or (not is_bsl and l[i] < z["bottom"]):
                        z["swept"], z["sweep_idx"] = True, i
                    if (hit or z["swept"]) and p.enable_reversals and not z["signaled"]:
                        tot_abs = sum(abs(d) for d in z["deltas"])
                        if tot_abs > 0:
                            outer = z["deltas"][3 if is_bsl else 0]
                            ratio = abs(outer) / (tot_abs + 0.0001)
                            sweeping = h[i] > z["top"] if is_bsl else l[i] < z["bottom"]
                            inside = z["bottom"] <= c[i] <= z["top"]
                            mid = (z["top"] + z["bottom"]) / 2.0
                            rejecting = c[i] < mid if is_bsl else c[i] > mid
                            typ, sig = "", 0.0
                            if sweeping and ((is_bsl and outer < 0) or (not is_bsl and outer > 0)) and ratio > 0.2:
                                typ, sig = "ABS", ratio * 2
                            if not typ and sweeping and ratio < 0.1:
                                typ, sig = "EXH", 1.0 - ratio * 5
                            if not typ and inside and ratio > 0.6 and ((is_bsl and outer > 0) or (not is_bsl and outer < 0)):
                                typ, sig = "DIV", ratio
                            if not typ and sweeping and rejecting:
                                br = abs(bdelta) / (v[i] + 0.0001)
                                if ((is_bsl and bdelta < 0) or (not is_bsl and bdelta > 0)) and br > 0.2:
                                    typ, sig = "REJ", br * 2
                            if typ:
                                z["signaled"] = True
                                d = -1 if is_bsl else 1
                                sigs.append(dict(type=typ, dir=d, idx=i, sig=min(max(sig, 0.0), 1.0), price=c[i]))
                                trades.append(dict(type=typ, dir=d, entry=c[i], bar=i, consec=0))
            keep = []
            for tr in trades:
                if i > tr["bar"]:
                    inprof = (tr["dir"] == 1 and c[i] > tr["entry"]) or (tr["dir"] == -1 and c[i] < tr["entry"])
                    tr["consec"] = tr["consec"] + 1 if inprof else 0
                    if tr["consec"] >= p.hold_bars:
                        stats[tr["type"]][0] += 1
                        stats[tr["type"]][1] += 1
                        continue
                    if i - tr["bar"] >= p.eval_window:
                        stats[tr["type"]][0] += 1
                        continue
                keep.append(tr)
            trades = keep

        wr = {k: (s[1] * 100.0 / s[0] if s[0] else NAN) for k, s in stats.items()}
        for s in sigs:
            if t - s["idx"] <= 100:
                r.add_signal(md, s["type"], s["dir"], s["idx"], s["price"], s["sig"],
                             f"inversione su {'BSL' if s['dir'] == -1 else 'SSL'} (win-rate {_fmt(wr[s['type']], 0)}%)")
        bias = 0.0
        last = [s for s in sigs if t - s["idx"] <= p.recent_bars]
        conf = 0.45
        if last:
            s = last[-1]
            tot = stats[s["type"]][0]
            f = _clip((wr[s["type"]] - 40.0) / 30.0, 0.0, 1.0) if tot >= 5 else 0.5
            bias = s["dir"] * _decay(t - s["idx"], p.recent_bars) * (0.5 + 0.5 * f) * (0.6 + 0.4 * s["sig"])
            if tot >= 10 and wr[s["type"]] > 55:
                conf = 0.6
        r.bias = bias
        r.confidence = conf
        price = c[t]
        act_b = [z for z in zones[True] if not z["swept"]]
        act_s = [z for z in zones[False] if not z["swept"]]
        for z in sorted(act_b, key=lambda z: z["bottom"])[:4]:
            health = max(0.0, 100.0 - z["vol"] / z["cap"] * 100.0)
            r.add_level(f"BSL zona (salute {health:.0f}%)", (z["top"] + z["bottom"]) / 2.0, "liquidity",
                        0.5 + 0.5 * health / 100.0, z["top"], z["bottom"])
        for z in sorted(act_s, key=lambda z: -z["top"])[:4]:
            health = max(0.0, 100.0 - z["vol"] / z["cap"] * 100.0)
            r.add_level(f"SSL zona (salute {health:.0f}%)", (z["top"] + z["bottom"]) / 2.0, "liquidity",
                        0.5 + 0.5 * health / 100.0, z["top"], z["bottom"])
        r.metrics.update({"active_bsl": len(act_b), "active_ssl": len(act_s),
                          "reversal_stats": {k: {"total": s[0], "wins": s[1], "win_rate": wr[k]} for k, s in stats.items()},
                          "last_signal": ({k: last[-1][k] for k in ("type", "dir", "sig")} | {"bars_ago": t - last[-1]["idx"]}) if last else None})
        nb = min((z["bottom"] for z in act_b if z["bottom"] > price), default=NAN)
        ns = max((z["top"] for z in act_s if z["top"] < price), default=NAN)
        r.notes.append(f"Zone attive: {len(act_b)} BSL (piu' vicina {_fmt(nb)}), {len(act_s)} SSL (piu' vicina {_fmt(ns)}).")
        r.notes.append("Win-rate inversioni: " + ", ".join(f"{k} {_fmt(wr[k], 0)}% ({stats[k][0]})" for k in stats) + ".")
        if last:
            s = last[-1]
            r.notes.append(f"Segnale {s['type']} {'rialzista' if s['dir'] == 1 else 'ribassista'} {t - s['idx']} barre fa "
                           f"(significativita' {s['sig']:.2f}).")
        return r


@register_module
class StructuralLegProfiler(IndicatorModule):
    """
    Structural Leg Profiler [LuxAlgo]  -  (c) LuxAlgo, Mozilla Public License 2.0

    COME FUNZIONA (Pine)
      * Zigzag a soglia di volatilita': inversione quando il prezzo ritraccia
        2.5 x ATR(5) dall'estremo del movimento in corso.
      * Per ogni gamba strutturale completata: volume profile (righe alte
        ATR(14)/10, max 50), POC, volume totale e delta buy-sell (proxy
        close-location; in Pine con dati a 1 minuto se disponibili).
      * POC "non testati" estesi in avanti finche' il prezzo non li tocca
        (max 2 per direzione).  Bolle sulle candele con volume >= 2x SMA20.

    COSA RESTITUISCE QUI
      direzione della gamba in corso e suo delta live, ultime gambe completate
      (volume, delta, POC, divergenze prezzo/delta), POC non testati come
      calamite, anomalie di volume recenti.
    """
    key = "slp"
    title = "Structural Leg Profiler"
    style = "structure"
    license = "MPL-2.0"
    batch = 3
    min_bars = 40

    @dataclass
    class Params:
        atr_period: int = 5
        swing_mult: float = 2.5
        max_boxes: int = 50
        bubble_mult: float = 2.0
        recent_bars: int = 5

    def _leg(self, md: MarketData, s: int, e: int, box_h: float, buy: np.ndarray, sell: np.ndarray) -> Dict[str, float]:
        p = self.params
        hh, ll, vv = md.high[s:e + 1], md.low[s:e + 1], md.volume[s:e + 1]
        mx, mn = float(hh.max()), float(ll.min())
        rng_ = mx - mn
        poc = (mx + mn) / 2.0
        if rng_ > 0 and box_h > 0:
            target = rng_ / p.max_boxes if rng_ / box_h > p.max_boxes else box_h
            nb = max(1, _pine_round(rng_ / target))
            bh = rng_ / nb
            vols = np.zeros(nb)
            br = np.maximum(hh - ll, md.mintick)
            bots = mn + np.arange(nb) * bh
            for k in range(len(hh)):
                ov = np.maximum(0.0, np.minimum(bots + bh, hh[k]) - np.maximum(bots, ll[k]))
                vols += vv[k] * ov / br[k]
            poc = mn + int(np.argmax(vols)) * bh + bh / 2.0
        return dict(high=mx, low=mn, poc=poc, volume=float(vv.sum()),
                    delta=float(buy[s:e + 1].sum() - sell[s:e + 1].sum()))

    def compute(self, md: MarketData) -> ModuleResult:
        p, r = self.params, self.new_result()
        n, t = md.n, md.n - 1
        h, l, c, o, v = md.high, md.low, md.close, md.open, md.volume
        ga, a14 = md.atr(p.atr_period), md.atr(14)
        rngv = np.maximum(h - l, md.mintick)
        buy, sell = v * (c - l) / rngv, v * (h - c) / rngv
        zz_dir, zz_hi, zz_hi_b, zz_lo, zz_lo_b = 1, h[0], 0, l[0], 0
        last_b, last_p = 0, c[0]
        legs: List[Dict[str, Any]] = []
        untested: List[Dict[str, Any]] = []
        for i in range(n):
            rev = ga[i] * p.swing_mult
            sw_hi = sw_lo = False
            if zz_dir == 1:
                if h[i] > zz_hi:
                    zz_hi, zz_hi_b = h[i], i
                if l[i] < zz_hi - rev:
                    zz_dir, zz_lo, zz_lo_b, sw_hi = -1, l[i], i, True
            else:
                if l[i] < zz_lo:
                    zz_lo, zz_lo_b = l[i], i
                if h[i] > zz_lo + rev:
                    zz_dir, zz_hi, zz_hi_b, sw_lo = 1, h[i], i, True
            for is_up, fire in ((True, sw_hi), (False, sw_lo)):
                if not fire:
                    continue
                end = zz_hi_b if is_up else zz_lo_b
                end_p = zz_hi if is_up else zz_lo
                leg = self._leg(md, last_b, end, _nz(a14[i], 0.0) / 10.0, buy, sell)
                leg.update(start=last_b, end=end, dir=1 if is_up else -1, start_price=last_p, end_price=end_p, confirm=i)
                legs.append(leg)
                untested.append(dict(price=leg["poc"], bull=is_up, end=end))
                last_b, last_p = end, end_p
            untested = [u for u in untested if not (h[i] >= u["price"] and l[i] <= u["price"])]
            keep, nb_, ns_ = [], 0, 0
            for u in reversed(untested):
                if u["bull"]:
                    nb_ += 1
                    if nb_ > 2:
                        continue
                else:
                    ns_ += 1
                    if ns_ > 2:
                        continue
                keep.append(u)
            untested = list(reversed(keep))
        live_delta = float(buy[last_b:].sum() - sell[last_b:].sum())
        live_vol = float(v[last_b:].sum())
        vs = sma(v, 20)
        for i in range(max(0, n - 20), n):
            if vs[i] > 0 and v[i] / vs[i] >= p.bubble_mult:
                r.add_signal(md, "VOLUME_SPIKE", 1 if c[i] >= o[i] else -1, i, md.hl2[i], min(1.0, v[i] / vs[i] / 4.0),
                             f"volume {v[i] / vs[i]:.1f}x la media")
        bias = 0.5 * zz_dir + 0.3 * _sign(live_delta)
        spikes = [s for s in r.signals if s.bars_ago <= 3]
        if spikes:
            bias += 0.2 * spikes[-1].direction
        if legs:
            lg = legs[-1]
            if _sign(lg["delta"]) != lg["dir"]:
                bias += 0.15 * (-lg["dir"])
        r.bias = bias
        r.confidence = 0.45
        for u in untested:
            r.add_level(f"POC non testato gamba {'up' if u['bull'] else 'down'}", u["price"], "magnet", 0.9)
        r.add_level("Ultimo pivot strutturale", last_p, "support" if zz_dir == 1 else "resistance", 0.8)
        r.add_level("Estremo gamba in corso", zz_hi if zz_dir == 1 else zz_lo, "resistance" if zz_dir == 1 else "support", 0.5)
        r.metrics.update({
            "leg_direction": zz_dir, "live_leg_start": last_b, "live_leg_delta": live_delta, "live_leg_volume": live_vol,
            "last_legs": [{k: lg[k] for k in ("dir", "start_price", "end_price", "volume", "delta", "poc")} for lg in legs[-3:]],
            "untested_pocs": [u["price"] for u in untested], "legs_found": len(legs),
        })
        r.notes.append(f"Gamba in corso {'RIALZISTA' if zz_dir == 1 else 'RIBASSISTA'} da {_fmt(last_p)} "
                       f"({t - last_b} barre), delta live {'+' if live_delta >= 0 else ''}{live_delta:,.0f}.")
        if legs:
            lg = legs[-1]
            div = " (DIVERGENZA prezzo/delta)" if _sign(lg["delta"]) != lg["dir"] else ""
            r.notes.append(f"Ultima gamba completata {'up' if lg['dir'] == 1 else 'down'} {_fmt(lg['start_price'])} -> "
                           f"{_fmt(lg['end_price'])}, delta {lg['delta']:+,.0f}, POC {_fmt(lg['poc'])}{div}.")
        if untested:
            r.notes.append("POC non testati: " + ", ".join(_fmt(u["price"]) for u in untested) + ".")
        return r


@register_module
class TemporalVolumeProfile3D(IndicatorModule):
    """
    Temporal Volume Profile 3D [LuxAlgo]  -  (c) LuxAlgo, CC BY-NC-SA 4.0

    COME FUNZIONA (Pine)
      * Ultime 250 barre divise in 25 "fette" temporali; per ogni fetta un
        volume profile a 45 livelli di prezzo (volume ripartito uniformemente
        tra i livelli toccati dalla candela) -> matrice tempo x prezzo,
        normalizzata 0-100 e smussata (media 5x5).
      * Rendering 3D a creste con la linea del POC attraverso il tempo (mostra
        la MIGRAZIONE del valore) e il tracker del prezzo attuale; avviso se il
        prezzo e' dentro una "montagna" di volume (>= 75%) nella fetta recente.

    COSA RESTITUISCE QUI
      migrazione del POC (in ATR) sulle fette recenti, profilo composito
      (POC/VAH/VAL), intensita' di volume al prezzo attuale (HVN = zona di
      equilibrio / supporto-resistenza), voto di regime (valore che migra =
      trend; POC fermo e prezzo in HVN = bilanciamento).
    """
    key = "tvp"
    title = "Temporal Volume Profile 3D"
    style = "volume"
    batch = 3
    min_bars = 60

    @dataclass
    class Params:
        lookback: int = 250
        price_bins: int = 45
        time_steps: int = 25
        smooth_len: int = 2
        peak_warn: float = 75.0
        migration_slices: int = 8
        value_area_pct: float = 70.0

    def compute(self, md: MarketData) -> ModuleResult:
        p, r = self.params, self.new_result()
        n, t = md.n, md.n - 1
        L = min(p.lookback, n)
        hh, ll, vv = md.high[::-1][:L], md.low[::-1][:L], np.nan_to_num(md.volume[::-1][:L])
        maxp, minp = float(hh.max()), float(ll.min())
        nb, ts = p.price_bins, p.time_steps
        bs = (maxp - minp) / nb
        terr = np.zeros((ts, nb))
        if bs > 0:
            for k in range(L):
                step = int(math.floor(k / (L / ts)))
                y = max(0, min(ts - 1, ts - 1 - step))
                if hh[k] == ll[k]:
                    b = max(0, min(nb - 1, int((hh[k] - minp) / bs)))
                    terr[y, b] += vv[k]
                else:
                    sb = max(0, int((ll[k] - minp) / bs))
                    eb = min(nb - 1, int((hh[k] - minp) / bs))
                    cnt = eb - sb + 1
                    terr[y, sb:eb + 1] += vv[k] / cnt
        raw = terr.copy()
        mx = terr.max()
        if mx > 0:
            terr = terr / mx * 100.0
        if p.smooth_len > 0:
            s = p.smooth_len
            pad = np.pad(terr, s, mode="constant", constant_values=0.0)
            ones = np.pad(np.ones_like(terr), s, mode="constant", constant_values=0.0)
            acc = np.zeros_like(terr)
            cnt = np.zeros_like(terr)
            for dy in range(2 * s + 1):
                for dx in range(2 * s + 1):
                    acc += pad[dy:dy + ts, dx:dx + nb]
                    cnt += ones[dy:dy + ts, dx:dx + nb]
            terr = acc / cnt
        poc_idx = terr.argmax(axis=1)
        poc_price = minp + (poc_idx + 0.5) * bs
        cur_bin = max(0, min(nb - 1, int((md.close[t] - minp) / bs))) if bs > 0 else 0
        front_z = float(terr[ts - 1, cur_bin])
        near_peak = front_z >= p.peak_warn
        a14 = md.last_atr(14)
        k = max(2, min(p.migration_slices, ts))
        ys = poc_price[-k:]
        slope = float(np.polyfit(np.arange(k), ys, 1)[0]) if bs > 0 else 0.0
        mig_atr = slope * (k - 1) / a14 if a14 > 0 else 0.0
        comp = raw.sum(axis=0)
        pb, lo_i, hi_i = value_area(comp, p.value_area_pct)
        cpoc = minp + (pb + 0.5) * bs
        vah, val_ = minp + (hi_i + 1) * bs, minp + lo_i * bs
        half = max((vah - val_) / 2.0, 1e-12)
        pos_comp = _clip((md.close[t] - cpoc) / half)
        r.bias = 0.5 * _clip(mig_atr / 2.0) + 0.5 * pos_comp
        r.regime = _clip(2.0 * _clip(abs(mig_atr) / 2.0, 0.0, 1.0) - 1.0 - (0.3 if near_peak else 0.0))
        r.regime_confidence = 0.4
        r.confidence = 0.45
        r.add_level("POC composito (250 barre)", cpoc, "magnet", 1.2)
        r.add_level("VAH composito", vah, "resistance", 0.8)
        r.add_level("VAL composito", val_, "support", 0.8)
        r.add_level("POC fetta piu' recente", float(poc_price[-1]), "magnet", 0.8)
        r.metrics.update({"poc_migration_atr": mig_atr, "poc_path": [float(x) for x in poc_price],
                          "composite_poc": cpoc, "vah": vah, "val": val_, "front_intensity": front_z,
                          "in_high_volume_node": near_peak, "lookback": L})
        r.notes.append(f"Migrazione del POC nelle ultime {k} fette: {mig_atr:+.2f} ATR "
                       f"({'valore in salita' if mig_atr > 0.3 else 'valore in discesa' if mig_atr < -0.3 else 'valore stabile'}).")
        r.notes.append(f"Profilo composito: POC {_fmt(cpoc)}, VA {_fmt(val_)} - {_fmt(vah)}; intensita' al prezzo attuale "
                       f"{front_z:.0f}/100{' (dentro un HVN)' if near_peak else ''}.")
        return r


# =============================================================================
# SEZIONE 8 - BATCH 4 e 5
# =============================================================================

@register_module
class EqualHighsLowsLiquidity(IndicatorModule):
    """
    EQH/EQL Liquidity Zones [LuxAlgo]  -  (c) LuxAlgo, CC BY-NC-SA 4.0

    COME FUNZIONA (Pine)
      * Pivot high/low (10 a sinistra, 2 a destra).  Un nuovo pivot che dista
        <= 0.03% da uno dei 50 pivot precedenti dello stesso tipo forma una zona
        di "massimi uguali" (EQH) o "minimi uguali" (EQL): li' si accumulano gli
        stop -> bacino di liquidita'.  Volume della zona = somma dei due pivot.
      * La zona resta attiva finche' il prezzo non la "spazza" (massimo oltre il
        top dell'EQH / minimo sotto il bottom dell'EQL), dalla barra successiva
        alla conferma.  Max 60 zone; etichette raggruppate entro 3x la soglia.

    COSA RESTITUISCE QUI
      bacini di liquidita' attivi sopra/sotto (i target naturali del prezzo),
      sweep recenti classificati come "sweep & reclaim" (presa di liquidita' e
      rientro = segnale di inversione) oppure "breakout" (chiusura oltre).
    """
    key = "eqhl"
    title = "EQH/EQL Liquidity Zones"
    style = "structure"
    batch = 4
    min_bars = 30

    @dataclass
    class Params:
        left: int = 10
        right: int = 2
        threshold_pct: float = 0.03
        max_zones: int = 60
        recent_bars: int = 5

    def compute(self, md: MarketData) -> ModuleResult:
        p, r = self.params, self.new_result()
        n, t = md.n, md.n - 1
        h, l, c, v = md.high, md.low, md.close, md.volume
        ph = pivothigh(h, p.left, p.right)
        pl = pivotlow(l, p.left, p.right)
        hist = {True: [], False: []}
        active: List[Dict[str, Any]] = []
        sweeps: List[Dict[str, Any]] = []
        for i in range(n):
            for is_high, arr in ((True, ph), (False, pl)):
                if math.isnan(arr[i]):
                    continue
                pv, pidx, vol = float(arr[i]), i - p.right, float(v[i - p.right])
                for prev in hist[is_high]:
                    if abs(pv - prev[0]) / prev[0] * 100.0 <= p.threshold_pct:
                        top, bot = max(pv, prev[0]), min(pv, prev[0])
                        active.append(dict(top=top, bottom=bot, level=top if is_high else bot, vol=prev[2] + vol,
                                           created=i, left=prev[1], high=is_high))
                        break
                hist[is_high].insert(0, (pv, pidx, vol))
                del hist[is_high][50:]
            keep = []
            for z in active:
                if i > z["created"] and ((z["high"] and h[i] > z["level"]) or (not z["high"] and l[i] < z["level"])):
                    sweeps.append(dict(z, idx=i, close=c[i]))
                    continue
                keep.append(z)
            active = keep[-p.max_zones:]
        price = c[t]
        for s in sweeps:
            if t - s["idx"] > 50:
                continue
            if s["high"]:
                rej = s["close"] < s["level"]
                r.add_signal(md, "EQH_SWEEP_REJECT" if rej else "EQH_BREAKOUT", -1 if rej else 1, s["idx"], s["level"],
                             0.7 if rej else 0.5, "liquidita' sopra massimi uguali presa")
            else:
                rej = s["close"] > s["level"]
                r.add_signal(md, "EQL_SWEEP_RECLAIM" if rej else "EQL_BREAKDOWN", 1 if rej else -1, s["idx"], s["level"],
                             0.7 if rej else 0.5, "liquidita' sotto minimi uguali presa")
        bias = 0.0
        rec = [s for s in sweeps if t - s["idx"] <= p.recent_bars]
        if rec:
            s = rec[-1]
            dec = _decay(t - s["idx"], p.recent_bars + 1)
            if s["high"]:
                bias = -0.6 * dec if price < s["level"] else 0.3 * dec
            else:
                bias = 0.6 * dec if price > s["level"] else -0.3 * dec
        r.bias = bias
        r.confidence = 0.45
        above = sorted([z for z in active if z["high"] and z["level"] > price], key=lambda z: z["level"])
        below = sorted([z for z in active if not z["high"] and z["level"] < price], key=lambda z: -z["level"])

        def cluster(zs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            out: List[Dict[str, Any]] = []
            for z in zs:
                for cl in out:
                    if abs(cl["level"] - z["level"]) / cl["level"] * 100.0 <= p.threshold_pct * 3:
                        cl["count"] += 1
                        cl["vol"] += z["vol"]
                        break
                else:
                    out.append(dict(level=z["level"], count=1, vol=z["vol"], top=z["top"], bottom=z["bottom"]))
            return out

        ca, cb = cluster(above), cluster(below)
        for k, cl in enumerate(ca[:3]):
            r.add_level(f"EQH x{cl['count']} (liquidita' buy-side)", cl["level"], "liquidity", 0.6 + 0.1 * min(cl["count"], 4),
                        cl["top"], cl["bottom"])
        for k, cl in enumerate(cb[:3]):
            r.add_level(f"EQL x{cl['count']} (liquidita' sell-side)", cl["level"], "liquidity", 0.6 + 0.1 * min(cl["count"], 4),
                        cl["top"], cl["bottom"])
        r.metrics.update({"active_eqh": len(above), "active_eql": len(below),
                          "eqh_clusters": [{"level": x["level"], "count": x["count"], "volume": x["vol"]} for x in ca[:5]],
                          "eql_clusters": [{"level": x["level"], "count": x["count"], "volume": x["vol"]} for x in cb[:5]],
                          "sweeps_last_50": len([s for s in sweeps if t - s["idx"] <= 50])})
        r.notes.append(f"Liquidita' attiva: {len(above)} EQH sopra (piu' vicino {_fmt(ca[0]['level']) if ca else 'n/d'}), "
                       f"{len(below)} EQL sotto (piu' vicino {_fmt(cb[0]['level']) if cb else 'n/d'}).")
        if rec:
            s = rec[-1]
            kind = ("EQH" if s["high"] else "EQL")
            outcome = ("rientro (sweep & reclaim)" if (s["high"] and price < s["level"]) or (not s["high"] and price > s["level"])
                       else "chiusura oltre (breakout)")
            r.notes.append(f"Sweep {kind} {t - s['idx']} barre fa a {_fmt(s['level'])}: {outcome}.")
        return r


@register_module
class UltimateOpeningRangeBreakout(IndicatorModule):
    """
    Ultimate Opening Range Breakout [LuxAlgo]  -  (c) LuxAlgo, CC BY-NC-SA 4.0

    COME FUNZIONA (Pine)
      * Opening Range = massimo/minimo della sessione 09:30-10:00 (UTC-5), ogni
        giorno.  Estensioni: OR high + 1/2/3 x ampiezza (o Fibonacci 0.382/0.618/1)
        e simmetriche sotto l'OR low.
      * Hit-rate storico di ogni estensione (quante sessioni l'hanno raggiunta).
      * Breakout: chiusura che incrocia l'OR high (o low) dopo la fine del
        range, una volta per direzione al giorno, entro l'orario di plotting
        (fino a 17:00 "New York Close").  Trailing stop ATR(14) x 2; uscita a
        fine giornata di plotting.  Volume del breakout HV/LV vs SMA20.
      * Profilo di volume dell'opening range; ottimizzatore dello stop 1..3 ATR.

    COSA RESTITUISCE QUI
      livelli OR di oggi con probabilita' storiche dei target (usate come
      target del piano di trade), stato del breakout e del trailing stop.
      Applicabile solo a timeframe intraday piu' corti della giornata; su
      timeframe >= 1 ora il range coincide con la barra che contiene 09:30.
    """
    key = "orb"
    title = "Ultimate Opening Range Breakout"
    style = "breakout"
    batch = 4
    min_bars = 50

    @dataclass
    class Params:
        session: str = "0930-1000"
        days: str = "1234567"
        tz: str = "UTC-5"
        src: str = "High/Low"
        ext_type: str = "Multiples"
        mult1: float = 1.0
        mult2: float = 2.0
        mult3: float = 3.0
        stop_plotting: bool = True
        end_time: str = "1700"
        trail_mult: float = 2.0
        trail_atr: int = 14
        recent_bars: int = 12

    def compute(self, md: MarketData) -> ModuleResult:
        p, r = self.params, self.new_result()
        n, t = md.n, md.n - 1
        if not md.is_intraday or md.bar_minutes > 240:
            r.applicable = False
            r.error = "ORB applicabile solo a timeframe intraday (<= H4)"
            return r
        h, l, o, c, v = md.high, md.low, md.open, md.close, md.volume
        loc = md.local_index(p.tz)
        in_s = session_mask(loc, md.bar_minutes, p.session, p.days)
        dkey = np.asarray(loc.year * 10000 + loc.month * 100 + loc.day)
        new_day = np.r_[True, dkey[1:] != dkey[:-1]]
        disp = session_mask(loc, md.bar_minutes, p.session.split("-")[0] + "-" + p.end_time, p.days) \
            if p.stop_plotting else np.ones(n, dtype=bool)
        a_tr = md.atr(p.trail_atr)
        vol20 = sma(v, 20)
        fs = (0.382, 0.618, 1.0) if p.ext_type == "Fibonacci" else (p.mult1, p.mult2, p.mult3)
        orh = orl = NAN
        ended = False
        total = 0
        hits = {k: 0 for k in ("U1", "U2", "U3", "D1", "D2", "D3")}
        reached = {k: False for k in hits}
        can_up = can_dn = True
        active, entry, trail, trail_prev = 0, NAN, NAN, NAN
        total_profit = 0.0
        prev_c, prev_orh, prev_orl = NAN, NAN, NAN
        breaks: List[Dict[str, Any]] = []
        or_start = -1
        for i in range(n):
            prev_in = in_s[i - 1] if i > 0 else False
            if new_day[i] or (in_s[i] and not prev_in):
                orh = orl = NAN
                ended = False
                reached = {k: False for k in hits}
                entry = NAN
                or_start = i
            if in_s[i]:
                ch = h[i] if p.src == "High/Low" else max(o[i], c[i])
                cl = l[i] if p.src == "High/Low" else min(o[i], c[i])
                orh = ch if math.isnan(orh) else max(orh, ch)
                orl = cl if math.isnan(orl) else min(orl, cl)
            if not in_s[i] and prev_in:
                ended = True
                total += 1
            rng = orh - orl
            ext = {"U%d" % (k + 1): orh + rng * f for k, f in enumerate(fs)}
            ext.update({"D%d" % (k + 1): orl - rng * f for k, f in enumerate(fs)})
            if ended:
                for k, lv in ext.items():
                    if not math.isnan(lv) and not reached[k] and ((k[0] == "U" and h[i] >= lv) or (k[0] == "D" and l[i] <= lv)):
                        hits[k] += 1
                        reached[k] = True
            up = (c[i] > orh and prev_c <= prev_orh) and not in_s[i] and ended
            dn = (c[i] < orl and prev_c >= prev_orl) and not in_s[i] and ended
            if new_day[i] or in_s[i]:
                can_up = can_dn = True
                active, trail = 0, NAN
            if up and can_up and disp[i]:
                can_up = False
                breaks.append(dict(idx=i, dir=1, level=orh, hv=bool(v[i] > _nz(vol20[i], np.inf))))
                if active == 0:
                    active, entry, trail = 1, orh, l[i] - a_tr[i] * p.trail_mult
            if dn and can_dn and disp[i]:
                can_dn = False
                breaks.append(dict(idx=i, dir=-1, level=orl, hv=bool(v[i] > _nz(vol20[i], np.inf))))
                if active == 0:
                    active, entry, trail = -1, orl, h[i] + a_tr[i] * p.trail_mult
            if active == 1:
                base = l[i] - a_tr[i] * p.trail_mult
                trail = max(_nz(trail_prev, base), base)
                if c[i] < trail or not disp[i]:
                    total_profit += c[i] - entry
                    active, trail = 0, NAN
            elif active == -1:
                base = h[i] + a_tr[i] * p.trail_mult
                trail = min(_nz(trail_prev, base), base)
                if c[i] > trail or not disp[i]:
                    total_profit += entry - c[i]
                    active, trail = 0, NAN
            trail_prev = trail
            prev_c, prev_orh, prev_orl = c[i], orh, orl
        rates = {k: (hits[k] / total if total else NAN) for k in hits}
        for b in breaks:
            if t - b["idx"] <= 100:
                r.add_signal(md, "ORB_BULL_BREAK" if b["dir"] == 1 else "ORB_BEAR_BREAK", b["dir"], b["idx"], b["level"],
                             0.8 if b["hv"] else 0.5, "breakout opening range " + ("(HV)" if b["hv"] else "(LV)"))
        price = c[t]
        formed = not math.isnan(orh)
        bias = 0.0
        if active != 0:
            bias = 0.6 * active
        elif formed and ended:
            bias = 0.3 if price > orh else (-0.3 if price < orl else 0.0)
        last = [s for s in r.signals if s.bars_ago <= p.recent_bars]
        if last:
            s = last[-1]
            bias = s.direction * max(abs(bias) if _sign(bias) == s.direction else 0.0,
                                     0.8 * _decay(s.bars_ago, p.recent_bars) * (1.0 if s.strength > 0.6 else 0.8))
        r.bias = bias
        dirk = "U1" if bias >= 0 else "D1"
        rate = rates[dirk]
        r.confidence = (0.3 + 0.5 * _clip((rate - 0.3) / 0.4, 0.0, 1.0)) if total >= 10 else 0.4
        if formed:
            r.add_level("OR high", orh, "resistance" if price < orh else "support", 0.9)
            r.add_level("OR low", orl, "support" if price > orl else "resistance", 0.9)
            for k in ("U1", "U2", "U3", "D1", "D2", "D3"):
                lv = (orh + (orh - orl) * fs[int(k[1]) - 1]) if k[0] == "U" else (orl - (orh - orl) * fs[int(k[1]) - 1])
                rk = rates[k]
                r.add_level(f"ORB target {k} (hit {_fmt(rk * 100 if not _isnan(rk) else NAN, 0)}%)", lv, "target",
                            0.4 + 0.5 * _nz(rk, 0.0))
        if active != 0 and not math.isnan(trail):
            r.add_level("ORB trailing stop", trail, "support" if active == 1 else "resistance", 0.6)
        r.metrics.update({"or_high": orh, "or_low": orl, "or_range": orh - orl if formed else NAN,
                          "session_ended": ended, "sessions_tracked": total,
                          "hit_rates": {k: rates[k] for k in hits}, "active_trade": active, "trail_stop": trail,
                          "cumulative_trail_profit": total_profit, "or_forming": bool(in_s[t]), "or_start_bar": or_start})
        if formed:
            r.notes.append(f"Opening range oggi ({p.session} {p.tz}): {_fmt(orl)} - {_fmt(orh)}; "
                           f"{'in formazione' if in_s[t] else 'completato'}; prezzo "
                           f"{'sopra' if price > orh else 'sotto' if price < orl else 'dentro'}.")
        r.notes.append(f"Hit-rate target su {total} sessioni: " +
                       ", ".join(f"{k} {_fmt(rates[k] * 100 if not _isnan(rates[k]) else NAN, 0)}%" for k in hits) + ".")
        if active != 0:
            r.notes.append(f"Breakout {'LONG' if active == 1 else 'SHORT'} attivo, trailing stop {_fmt(trail)}.")
        return r


@register_module
class OmniFlowConsensus(IndicatorModule):
    """
    Omni-Flow Consensus [LuxAlgo]  -  (c) LuxAlgo, CC BY-NC-SA 4.0

    COME FUNZIONA (Pine)
      * Pressione di volume = (close-open)/(high-low) x volume (o True Range se
        il volume manca), media a 24 barre, normalizzata tra il minimo e il
        massimo delle ultime 48 -> oscillatore -100..+100, "boost" non lineare
        (esponente 1/1.5) e filtro adattivo (ASF) guidato dall'ATR.
      * Linea di segnale = EMA(5).  |flusso| > 50 = flusso direzionale
        (BULLISH/BEARISH FLOW), altrimenti ACCUMULATION.
      * Impulsi ("injection") confermati: incrocio del flusso sul segnale che
        tiene per 3 barre con |flusso| > 15.

    COSA RESTITUISCE QUI
      flusso normalizzato (bias), regime (flusso direzionale vs accumulazione),
      impulsi recenti.
    NOTE
      Il filtro ASF confronta la variazione dell'oscillatore con l'ATR del
      prezzo: su strumenti con prezzi piccoli (forex) il filtro e' quasi
      trasparente, esattamente come nell'originale.
    """
    key = "ofc"
    title = "Omni-Flow Consensus"
    style = "momentum"
    batch = 4
    min_bars = 100

    @dataclass
    class Params:
        flow_len: int = 24
        spectral_len: int = 10
        boost: float = 1.5
        smooth_signals: bool = True
        strictness: int = 3
        threshold: float = 15.0
        recent_bars: int = 5

    def compute(self, md: MarketData) -> ModuleResult:
        p, r = self.params, self.new_result()
        n, t = md.n, md.n - 1
        h, l, o, c, v = md.high, md.low, md.open, md.close, md.volume
        tr0 = md.tr(False)
        smart = np.where((~np.isnan(v)) & (v > 0), v, tr0)
        vp = (c - o) / np.maximum(h - l, md.mintick) * smart
        raw = sma(vp, p.flow_len)
        hi, lo = highest(raw, p.flow_len * 2), lowest(raw, p.flow_len * 2)
        rngv = np.maximum(hi - lo, md.mintick)
        norm = (raw - lo) / rngv * 200.0 - 100.0
        with np.errstate(invalid="ignore"):
            boosted = np.sign(norm) * np.power(np.abs(norm) / 100.0, 1.0 / p.boost) * 100.0
        alpha = 2.0 / (p.spectral_len + 1)
        diff = md.atr(p.spectral_len)
        flow = np.full(n, np.nan)
        prev = NAN
        for i in range(n):
            src = boosted[i]
            if math.isnan(prev):
                prev = src
            else:
                s1 = boosted[i - 1]
                ad = min(1.0, alpha * abs(src - s1) / (diff[i] + md.mintick)) if not (math.isnan(s1) or math.isnan(diff[i])) else NAN
                prev = prev + ad * (src - prev) if not math.isnan(ad) else NAN
            flow[i] = prev
        sig = ema(flow, 5)
        with np.errstate(invalid="ignore"):
            up_x, dn_x = crossover(flow, sig), crossunder(flow, sig)
            bs_up, bs_dn = barssince(up_x), barssince(dn_x)
            bull_ok = (bs_up < p.strictness) & (flow > sig)
            bear_ok = (bs_dn < p.strictness) & (flow < sig)
            if p.smooth_signals:
                imp_b = crossover(barssince(~bull_ok), p.strictness - 1) & (flow > p.threshold)
                imp_s = crossover(barssince(~bear_ok), p.strictness - 1) & (flow < -p.threshold)
            else:
                imp_b = up_x & (flow > 0)
                imp_s = dn_x & ~(flow > 0)
        for i in range(max(0, n - 50), n):
            if imp_b[i]:
                r.add_signal(md, "BULL_INJECTION", 1, i, c[i], 0.7, f"impulso di flusso ({flow[i]:.0f})")
            if imp_s[i]:
                r.add_signal(md, "BEAR_INJECTION", -1, i, c[i], 0.7, f"impulso di flusso ({flow[i]:.0f})")
        f_t, s_t = _nz(flow[t]), _nz(sig[t])
        bias = 0.7 * f_t / 100.0 + 0.3 * _sign(f_t - s_t)
        rec = [s for s in r.signals if s.bars_ago <= p.recent_bars]
        if rec:
            bias += 0.3 * rec[-1].direction * _decay(rec[-1].bars_ago, p.recent_bars + 1)
        r.bias = bias
        r.regime = _clip((abs(f_t) - 50.0) / 50.0)
        r.regime_confidence = 0.4
        r.confidence = 0.45
        regime = "ACCUMULATION" if abs(f_t) <= 50 else ("BULLISH FLOW" if f_t > 0 else "BEARISH FLOW")
        r.metrics.update({"flow": f_t, "signal": s_t, "regime": regime, "intensity_pct": abs(f_t)})
        r.notes.append(f"Omni-Flow {f_t:+.0f} (segnale {s_t:+.0f}) -> {regime}.")
        if rec:
            r.notes.append(f"{rec[-1].name} {rec[-1].bars_ago} barre fa.")
        return r


@register_module
class MarketStructureScatter(IndicatorModule):
    """
    Market Structure & Scatter Dashboard [LuxAlgo]  -  (c) LuxAlgo, CC BY-NC-SA 4.0

    COME FUNZIONA (Pine)
      * Swing (pivot 10/10).  Chiusura oltre l'ultimo swing high non ancora
        rotto = rottura rialzista: CHoCH se il trend era ribassista/neutro
        (cambio di carattere), BOS se era gia' rialzista (continuazione).
        Speculare al ribasso.
      * Sequenza alternata di swing (high/low) -> per ogni terna: "impulso" %
        e "pullback" % -> grafico a dispersione impulso/pullback e colorazione
        delle candele in base al pullback corrente.

    COSA RESTITUISCE QUI
      trend strutturale (+1/-1), ultimo evento BOS/CHoCH, livelli di rottura
      (swing non ancora rotti), rapporto BOS/CHoCH (voto di regime: molti BOS
      = trend che continua, molti CHoCH = mercato che inverte/laterale),
      impulso e ritracciamento correnti vs la media storica.
    """
    key = "mss"
    title = "Market Structure & Scatter"
    style = "trend"
    batch = 4
    min_bars = 40

    @dataclass
    class Params:
        pivot_len: int = 10
        max_history: int = 100
        recent_bars: int = 10
        regime_events: int = 10

    def compute(self, md: MarketData) -> ModuleResult:
        p, r = self.params, self.new_result()
        n, t = md.n, md.n - 1
        c = md.close
        ph, pl = pivothigh(md.high, p.pivot_len, p.pivot_len), pivotlow(md.low, p.pivot_len, p.pivot_len)
        top_y = btm_y = NAN
        top_cross = btm_cross = True
        trend = 0
        events: List[Dict[str, Any]] = []
        alt_p: List[float] = []
        alt_t: List[int] = []
        for i in range(n):
            if not math.isnan(ph[i]):
                top_y, top_cross = float(ph[i]), False
                if not alt_t or alt_t[-1] == -1:
                    alt_p.append(float(ph[i]))
                    alt_t.append(1)
                elif ph[i] > alt_p[-1]:
                    alt_p[-1] = float(ph[i])
            if not math.isnan(pl[i]):
                btm_y, btm_cross = float(pl[i]), False
                if not alt_t or alt_t[-1] == 1:
                    alt_p.append(float(pl[i]))
                    alt_t.append(-1)
                elif pl[i] < alt_p[-1]:
                    alt_p[-1] = float(pl[i])
            del alt_p[:-p.max_history], alt_t[:-p.max_history]
            if not top_cross and c[i] > top_y:
                top_cross = True
                events.append(dict(idx=i, dir=1, type="CHoCH" if trend <= 0 else "BOS", level=top_y))
                trend = 1
            if not btm_cross and c[i] < btm_y:
                btm_cross = True
                events.append(dict(idx=i, dir=-1, type="CHoCH" if trend >= 0 else "BOS", level=btm_y))
                trend = -1
        for e in events:
            if t - e["idx"] <= 100:
                r.add_signal(md, f"{e['type']}_{'UP' if e['dir'] == 1 else 'DOWN'}", e["dir"], e["idx"], e["level"],
                             1.0 if e["type"] == "CHoCH" else 0.7, "rottura di struttura")
        # impulso/pullback storici
        hist_ratios = []
        for i in range(2, len(alt_p)):
            p0, p1, p2 = alt_p[i - 2], alt_p[i - 1], alt_p[i]
            if alt_t[i] == 1:
                imp, pb = (p0 - p1) / p0 * 100, (p2 - p1) / p1 * 100
            else:
                imp, pb = (p1 - p0) / p0 * 100, (p1 - p2) / p1 * 100
            if imp > 0 and pb > 0:
                hist_ratios.append(pb / imp)
        imp_dir, impulse, pullback, retr = 0, NAN, NAN, NAN
        if len(alt_p) >= 2:
            p0, p1, p2 = alt_p[-2], alt_p[-1], c[t]
            if -alt_t[-1] == 1:
                impulse, pullback, imp_dir = (p0 - p1) / p0 * 100, (p2 - p1) / p1 * 100, -1
            else:
                impulse, pullback, imp_dir = (p1 - p0) / p0 * 100, (p1 - p2) / p1 * 100, 1
            if impulse > 0 and pullback > 0:
                retr = pullback / impulse
            elif impulse > 0:
                retr = 0.0
        bias = 0.7 * trend
        if imp_dir and not _isnan(retr):
            bias += 0.3 * imp_dir * _clip(1.0 - retr)
        rec = [e for e in events if t - e["idx"] <= p.recent_bars]
        if rec and rec[-1]["type"] == "CHoCH":
            e = rec[-1]
            bias = e["dir"] * max(abs(bias) if _sign(bias) == e["dir"] else 0.0, 0.8 * _decay(t - e["idx"], p.recent_bars))
        r.bias = bias
        last_ev = events[-p.regime_events:]
        if len(last_ev) >= 4:
            bos_ratio = sum(1 for e in last_ev if e["type"] == "BOS") / len(last_ev)
            r.regime = _clip((bos_ratio - 0.5) * 2.5)
            r.regime_confidence = 0.5
        else:
            bos_ratio = NAN
        r.confidence = 0.55
        if not top_cross:
            r.add_level("Swing high (trigger BOS/CHoCH)", top_y, "resistance", 1.0)
        if not btm_cross:
            r.add_level("Swing low (trigger BOS/CHoCH)", btm_y, "support", 1.0)
        if events:
            e = events[-1]
            r.add_level(f"Livello ultimo {e['type']}", e["level"], "support" if e["dir"] == 1 else "resistance", 0.7)
        avg_ratio = float(np.mean(hist_ratios)) if hist_ratios else NAN
        r.metrics.update({"trend": trend, "last_event": ({k: events[-1][k] for k in ("type", "dir", "level")} |
                                                         {"bars_ago": t - events[-1]["idx"]}) if events else None,
                          "bos_ratio": bos_ratio, "impulse_pct": impulse, "pullback_pct": pullback, "retracement": retr,
                          "impulse_direction": imp_dir, "avg_hist_retracement": avg_ratio,
                          "swing_high": top_y if not top_cross else None, "swing_low": btm_y if not btm_cross else None})
        r.notes.append(f"Struttura {'RIALZISTA' if trend == 1 else 'RIBASSISTA' if trend == -1 else 'neutra'}"
                       + (f"; ultimo evento {events[-1]['type']} {'up' if events[-1]['dir'] == 1 else 'down'} "
                          f"{t - events[-1]['idx']} barre fa a {_fmt(events[-1]['level'])}" if events else "") + ".")
        if not _isnan(retr):
            r.notes.append(f"Impulso {'rialzista' if imp_dir == 1 else 'ribassista'} {impulse:.2f}%, ritracciamento attuale "
                           f"{retr * 100:.0f}% (media storica {_fmt(avg_ratio * 100 if not _isnan(avg_ratio) else NAN, 0)}%); "
                           f"BOS/eventi recenti {_fmt(bos_ratio, 2)}.")
        return r


@register_module
class UniversalSignalBacktester(IndicatorModule):
    """
    Universal Signal Backtester [LuxAlgo]  -  (c) LuxAlgo, CC BY-NC-SA 4.0

    COME FUNZIONA (Pine)
      * Segnali: incrocio EMA 9/21 (predefinito; anche 12/26 EMA o 50/200 SMA)
        o sorgenti/segnali esterni, filtro ATR opzionale.
      * Ogni trade ha 3 TP (1/2/3 ATR, uscite parziali di 1/3) e 3 SL
        (1.5/2.5/3.5 ATR, valutati PRIMA dei TP = approccio conservativo);
        chiusura anche sul segnale opposto.  PnL in tick, costi opzionali.
      * Statistiche: win-rate, profit factor, Sharpe, recovery factor,
        stagnazione, frequenza di raggiungimento dei TP, PnL per ora e per
        giorno della settimana, TP suggerito.

    COSA RESTITUISCE QUI
      stato dell'incrocio, trade simulato aperto (con TP/SL), statistiche,
      probabilita' storica dei 3 TP (usata per scegliere il target), edge
      dell'ora corrente (performance storica dei trade aperti a quest'ora).
    """
    key = "usb"
    title = "Universal Signal Backtester"
    style = "trend"
    batch = 4
    min_bars = 60

    @dataclass
    class Params:
        predef: str = "9/21 EMA Cross"
        trade_direction: str = "Both"
        use_atr_filter: bool = False
        atr_filter_len: int = 50
        atr_len: int = 14
        tps: Tuple[float, float, float] = (1.0, 2.0, 3.0)
        sls: Tuple[float, float, float] = (1.5, 2.5, 3.5)
        spread_ticks: float = 0.0
        commission_pct: float = 0.0
        suggest_metric: str = "Hit Rate"
        recent_bars: int = 5

    def compute(self, md: MarketData) -> ModuleResult:
        p, r = self.params, self.new_result()
        n, t = md.n, md.n - 1
        h, l, c = md.high.tolist(), md.low.tolist(), md.close.tolist()
        if p.predef == "12/26 EMA Cross":
            fast, slow = ema(md.close, 12), ema(md.close, 26)
        elif p.predef.startswith("Golden"):
            fast, slow = sma(md.close, 50), sma(md.close, 200)
        else:
            fast, slow = ema(md.close, 9), ema(md.close, 21)
        a14 = np.nan_to_num(md.atr(14))
        filt = (a14 > sma(a14, p.atr_filter_len)) if p.use_atr_filter else np.ones(n, dtype=bool)
        lc = crossover(fast, slow) & filt
        sc = crossunder(fast, slow) & filt
        can_l, can_s = p.trade_direction in ("Both", "Long Only"), p.trade_direction in ("Both", "Short Only")
        av = np.nan_to_num(md.atr(p.atr_len)).tolist()
        tick = md.mintick
        hours = md.local_index(md.data_tz).hour.to_numpy()
        active, d, entry, eidx, qty, pnl = False, 0, NAN, -1, 0.0, 0.0
        tp_px, sl_px = [NAN] * 3, [NAN] * 3
        tp_hit, sl_hit = [False] * 3, [False] * 3
        tp_counts = [0, 0, 0]
        trades: List[float] = []
        hourly = np.zeros(24)
        hourly_n = np.zeros(24, dtype=int)
        entries: List[Tuple[int, int]] = []
        cost = lambda q: (p.spread_ticks + (entry * (p.commission_pct / 100.0) / tick)) * q
        for i in range(n):
            if active:
                closed = False
                for k in range(3):
                    if not sl_hit[k] and ((d == 1 and l[i] <= sl_px[k]) or (d == -1 and h[i] >= sl_px[k])):
                        sl_hit[k] = True
                if any(sl_hit):
                    ex = sl_px[0] if sl_hit[0] else (sl_px[1] if sl_hit[1] else sl_px[2])
                    pnl += (ex - entry) * d / tick * qty - cost(qty)
                    qty, closed = 0.0, True
                if not closed:
                    tq = 1.0 / 3.0
                    for k in range(3):
                        if not tp_hit[k] and ((d == 1 and h[i] >= tp_px[k]) or (d == -1 and l[i] <= tp_px[k])):
                            tp_hit[k] = True
                            tp_counts[k] += 1
                            pnl += (tp_px[k] - entry) * d / tick * tq - cost(tq)
                            qty -= tq
                    if qty <= 0.001:
                        closed = True
                if not closed and ((d == 1 and sc[i]) or (d == -1 and lc[i])):
                    pnl += (c[i] - entry) * d / tick * qty - cost(qty)
                    qty, closed = 0.0, True
                if closed:
                    active = False
                    trades.append(pnl)
                    hourly[hours[eidx]] += pnl
                    hourly_n[hours[eidx]] += 1
            if not active:
                nd = 1 if (lc[i] and can_l) else (-1 if (sc[i] and can_s) else 0)
                if nd != 0:
                    active, d, entry, eidx, qty, pnl = True, nd, c[i], i, 1.0, 0.0
                    tp_px = [c[i] + nd * m * av[i] for m in p.tps]
                    sl_px = [c[i] - nd * m * av[i] for m in p.sls]
                    tp_hit, sl_hit = [False] * 3, [False] * 3
                    entries.append((i, nd))
        st = _trade_stats(trades)
        tot = max(1, st["trades"])
        rates = [x / tot for x in tp_counts]
        exp_val = [rates[k] * p.tps[k] for k in range(3)]
        best_exp = int(np.argmax(exp_val)) + 1
        for i, dd in entries:
            if t - i <= 50:
                r.add_signal(md, "EMA_CROSS_LONG" if dd == 1 else "EMA_CROSS_SHORT", dd, i, c[i], 0.6,
                             f"incrocio {p.predef}")
        cross_dir = _sign(fast[t] - slow[t])
        bias = 0.5 * cross_dir
        rec = [s for s in r.signals if s.bars_ago <= p.recent_bars]
        if rec:
            bias += 0.5 * rec[-1].direction * _decay(rec[-1].bars_ago, p.recent_bars + 1)
        if active:
            bias = d * max(abs(bias) if _sign(bias) == d else 0.0, 0.3)
        r.bias = bias
        conf = (0.3 + 0.4 * _clip((st["profit_factor"] - 0.8) / 0.7, 0.0, 1.0)) if st["trades"] >= 10 else 0.4
        cur_h = int(hours[t])
        hour_edge = hourly[cur_h] / hourly_n[cur_h] if hourly_n[cur_h] else NAN
        if hourly_n[cur_h] >= 5 and hour_edge < 0:
            conf *= 0.8
        r.confidence = conf
        if active:
            for k in range(3):
                if not tp_hit[k]:
                    r.add_level(f"USB TP{k + 1} (storico {rates[k] * 100:.0f}%)", tp_px[k], "level", 0.3 + 0.5 * rates[k])
                if not sl_hit[k]:
                    r.add_level(f"USB SL{k + 1}", sl_px[k], "support" if d == 1 else "resistance", 0.3)
        r.add_level(f"MA lenta ({p.predef})", float(slow[t]), "support" if c[t] > slow[t] else "resistance", 0.5)
        best_hours = [int(x) for x in np.argsort(-hourly)[:3] if hourly_n[x] > 0]
        r.metrics.update({"predef": p.predef, "cross_state": cross_dir, "trades": st["trades"], "win_rate": st["win_rate"],
                          "profit_factor": st["profit_factor"], "net_ticks": st["net"], "sharpe": st["sharpe"],
                          "max_dd_ticks": st["max_dd"],
                          "recovery_factor": (st["net"] / st["max_dd"]) if st["max_dd"] > 0 else NAN,
                          "tp_hit_rates": rates, "suggested_tp_hit_rate": 1, "suggested_tp_expectancy": best_exp,
                          "active_trade": {"dir": d, "entry": entry, "tp": tp_px, "sl": sl_px, "tp_hit": tp_hit} if active else None,
                          "current_hour": cur_h, "current_hour_avg_pnl_ticks": hour_edge, "best_hours": best_hours})
        r.notes.append(f"{p.predef}: EMA veloce {'sopra' if cross_dir > 0 else 'sotto'} la lenta; backtest {st['trades']} trade, "
                       f"WR {st['win_rate']:.0f}%, PF {st['profit_factor']:.2f}.")
        r.notes.append("Frequenza TP storica: " + ", ".join(f"TP{k + 1} ({p.tps[k]:g} ATR) {rates[k] * 100:.0f}%" for k in range(3))
                       + f"; TP con aspettativa migliore: TP{best_exp}.")
        if active:
            r.notes.append(f"Trade simulato {'LONG' if d == 1 else 'SHORT'} aperto da {_fmt(entry)}.")
        if not _isnan(hour_edge):
            r.notes.append(f"Ora corrente ({cur_h}:00) PnL medio storico dei trade aperti a quest'ora: {hour_edge:+.0f} tick.")
        return r


@register_module
class OrderFlow3DDeltaProfile(IndicatorModule):
    """
    Order Flow 3D Delta Profile [LuxAlgo]  -  (c) LuxAlgo, CC BY-NC-SA 4.0

    COME FUNZIONA (Pine)
      * Ultime 200 barre, 35 livelli tra minimo e massimo del periodo.  Il volume
        di ogni candela va nel livello del suo hl2, come volume "bull" se la
        candela chiude sopra l'apertura, "bear" se sotto.
      * POC, Value Area 70% (espansione dal POC verso il lato piu' carico),
        delta per livello (colore verde/rosso), rendering 3D.
      * Candele con volume > 2.5x la media evidenziate e collegate al profilo
        finche' il prezzo non torna sul loro hl2 ("raggio laser").

    COSA RESTITUISCE QUI
      POC/VAH/VAL, delta complessivo e al livello del prezzo attuale, posizione
      rispetto alla value area (dentro = bilanciamento -> voto RANGE; fuori =
      accettazione di nuovi prezzi -> voto TREND), nodi ad alto volume non
      ancora ritestati (calamite).
    """
    key = "of3d"
    title = "Order Flow 3D Delta Profile"
    style = "volume"
    batch = 5
    min_bars = 50

    @dataclass
    class Params:
        length: int = 200
        buckets: int = 35
        va_pct: float = 70.0
        vol_mult: float = 2.5

    def compute(self, md: MarketData) -> ModuleResult:
        p, r = self.params, self.new_result()
        n, t = md.n, md.n - 1
        L = min(p.length, n)
        s = slice(n - L, n)
        h, l, o, c, v, m = md.high[s], md.low[s], md.open[s], md.close[s], np.nan_to_num(md.volume[s]), md.hl2[s]
        top, bot = float(h.max()), float(l.min())
        step = (top - bot) / p.buckets
        bu, be = np.zeros(p.buckets), np.zeros(p.buckets)
        if step > 0:
            j = np.floor((m - bot) / step).astype(int)
            ok = (j >= 0) & (j < p.buckets)
            np.add.at(bu, j[ok & (c > o)], v[ok & (c > o)])
            np.add.at(be, j[ok & (c < o)], v[ok & (c < o)])
        tot = bu + be
        pb, lo_i, hi_i = value_area(tot, p.va_pct)
        poc = bot + (pb + 0.5) * step
        vah, val_ = bot + (hi_i + 1) * step, bot + lo_i * step
        delta_ratio = _safe_div(bu.sum() - be.sum(), tot.sum())
        price = md.close[t]
        cb = int(min(p.buckets - 1, max(0, math.floor((price - bot) / step)))) if step > 0 else 0
        delta_here = _safe_div(bu[cb] - be[cb], tot[cb])
        half = max((vah - val_) / 2.0, 1e-12)
        if price > vah:
            pos, where = 1.0, "sopra la value area"
        elif price < val_:
            pos, where = -1.0, "sotto la value area"
        else:
            pos, where = 0.5 * _clip((price - poc) / half), "dentro la value area"
        r.bias = 0.4 * _clip(2 * delta_ratio) + 0.6 * pos
        r.regime = 0.5 if abs(pos) >= 1.0 else -0.5
        r.regime_confidence = 0.4
        r.confidence = 0.45
        avg = v.mean() if L else 0.0
        naked = []
        for k in range(L):
            if v[k] > avg * p.vol_mult:
                mid = m[k]
                later_h, later_l = h[k + 1:], l[k + 1:]
                if not np.any((later_h >= mid) & (later_l <= mid)):
                    naked.append((n - L + k, float(mid), 1 if c[k] > o[k] else -1))
        r.add_level("POC delta profile", poc, "magnet", 1.2)
        r.add_level("VAH delta profile", vah, "resistance", 0.8)
        r.add_level("VAL delta profile", val_, "support", 0.8)
        for idx, mid, dd in naked[-4:]:
            r.add_level(f"Nodo alto volume non ritestato ({'bull' if dd == 1 else 'bear'})", mid, "magnet", 0.7)
        r.metrics.update({"poc": poc, "vah": vah, "val": val_, "delta_ratio": delta_ratio, "delta_at_price": delta_here,
                          "position": where, "window_high": top, "window_low": bot,
                          "naked_hv_nodes": [x[1] for x in naked[-4:]]})
        r.notes.append(f"Profilo {L} barre: POC {_fmt(poc)}, VA {_fmt(val_)} - {_fmt(vah)}; prezzo {where}.")
        r.notes.append(f"Delta complessivo {delta_ratio:+.2f}, delta al livello attuale {delta_here:+.2f}; "
                       f"nodi HV non ritestati: {len(naked)}.")
        return r


# =============================================================================
# SEZIONE 9 - MOTORE DI CONFLUENZA
# =============================================================================

STYLE_LABELS = {
    "trend": "Trend", "momentum": "Momentum/Flusso", "breakout": "Breakout", "reversion": "Mean-reversion",
    "hybrid": "Ibrido (trend+reversion)", "structure": "Struttura/Liquidita'", "volume": "Volume profile",
    "ensemble": "Ensemble/Backtest", "volatility": "Volatilita'",
}


@dataclass
class ConfluenceConfig:
    """Parametri del motore.  Tutti modificabili senza toccare i moduli."""
    module_weights: Dict[str, float] = field(default_factory=lambda: {
        "vrh": 1.0, "rb": 0.9, "mspo": 1.2, "rsid": 0.8, "st3d": 1.2,
        "svma": 0.7, "par": 0.7, "sf": 1.0, "atrp": 0.3,
        "hlph": 0.4, "ofvd": 1.0, "ldp": 0.8, "slp": 0.8, "tvp": 0.7,
        "eqhl": 0.7, "orb": 0.7, "ofc": 0.9, "mss": 1.1, "usb": 0.8, "of3d": 0.8,
    })
    # sensibilita' dello stile al regime: moltiplicatore = 1 + regime_score * k
    style_regime_k: Dict[str, float] = field(default_factory=lambda: {
        "trend": 0.5, "momentum": 0.4, "breakout": 0.3, "ensemble": 0.1, "structure": 0.0,
        "hybrid": 0.0, "volume": 0.0, "reversion": -0.5, "volatility": 0.0,
    })
    regime_threshold: float = 0.20
    trade_threshold: float = 0.20      # |score| minimo per BUY/SELL
    strong_threshold: float = 0.45     # |score| per "forte"
    min_agreement: float = 0.55        # quota di peso direzionale concorde
    setup_bonus: float = 0.08          # bonus per setup concorde (x forza)
    max_setup_bonus: float = 0.20
    counter_trend_veto: float = 0.60   # |consenso ST3D| oltre il quale un trade contro-trend viene bloccato
    level_cluster_atr: float = 0.25    # tolleranza di clustering dei livelli (in ATR)
    max_level_distance_atr: float = 12.0
    atr_len: int = 14
    sl_min_atr: float = 1.0
    sl_max_atr: float = 3.5
    sl_buffer_atr: float = 0.2
    default_sl_atr: Dict[str, float] = field(default_factory=lambda: {"Quiet": 1.5, "Normal": 2.0, "High Vol": 2.5})
    min_stop_score: float = 1.0
    min_rr: float = 1.5
    disabled_modules: Tuple[str, ...] = ()
    module_params: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class UnifiedAnalysis:
    symbol: Optional[str]
    timeframe: Optional[str]
    last_time: Optional[str]
    last_close: float
    atr: float
    bars: int
    decision: str
    strength: str
    score: float
    raw_score: float
    agreement: float
    confidence_pct: float
    regime_label: str
    regime_score: float
    regime_votes: List[Dict[str, Any]]
    volatility_label: str
    volatility: Dict[str, Any]
    family_scores: Dict[str, float]
    contributions: List[Dict[str, Any]]
    setups: List[Dict[str, Any]]
    trade_plan: Optional[Dict[str, Any]]
    supports: List[Dict[str, Any]]
    resistances: List[Dict[str, Any]]
    warnings: List[str]
    modules: Dict[str, ModuleResult]
    version: str = __version__

    # ------------------------------------------------------------------ output
    def to_dict(self, include_modules: bool = True) -> Dict[str, Any]:
        out = {k: getattr(self, k) for k in (
            "version", "symbol", "timeframe", "last_time", "last_close", "atr", "bars", "decision", "strength", "score",
            "raw_score", "agreement", "confidence_pct", "regime_label", "regime_score", "regime_votes",
            "volatility_label", "volatility", "family_scores", "contributions", "setups", "trade_plan",
            "supports", "resistances", "warnings")}
        if include_modules:
            out["modules"] = {k: v.to_dict() for k, v in self.modules.items()}
        return _to_py(out)

    def to_json(self, indent: Optional[int] = 2, include_modules: bool = True) -> str:
        return json.dumps(self.to_dict(include_modules), indent=indent, ensure_ascii=False)

    def summary_line(self) -> str:
        return (f"{self.symbol or ''} {self.timeframe or ''} -> {self.decision} ({self.strength}) score {self.score:+.2f}, "
                f"accordo {self.agreement * 100:.0f}%, confidenza {self.confidence_pct:.0f}%, regime {self.regime_label}, "
                f"volatilita' {self.volatility_label}").strip()

    def to_markdown(self, detail: bool = True) -> str:
        L: List[str] = []
        head = " ".join(x for x in (self.symbol, self.timeframe) if x)
        L.append(f"# Analisi unificata 20 indicatori LuxAlgo{(' - ' + head) if head else ''}")
        L.append(f"Ultima barra chiusa: {self.last_time} UTC | Prezzo {_fmt(self.last_close)} | ATR(14) {_fmt(self.atr)} | "
                 f"Barre analizzate: {self.bars}")
        L.append("")
        L.append("## Verdetto")
        L.append(f"**Indicazione del motore: {self.decision}** ({self.strength}) - score {self.score:+.2f} "
                 f"(grezzo {self.raw_score:+.2f}), accordo tra moduli {self.agreement * 100:.0f}%, "
                 f"confidenza {self.confidence_pct:.0f}%.")
        L.append(f"Regime: **{self.regime_label}** ({self.regime_score:+.2f}) | Volatilita': **{self.volatility_label}**"
                 + (f" (z ATR {self.volatility.get('atr_z'):+.2f}, prob. espansione {self.volatility.get('expansion_prob_pct', 0):.0f}%)"
                    if self.volatility.get("atr_z") is not None and not _isnan(self.volatility.get("atr_z")) else ""))
        L.append("")
        if self.trade_plan:
            tp = self.trade_plan
            L.append(f"## Piano di trade ({'LONG' if tp['direction'] == 1 else 'SHORT'})")
            L.append("| Voce | Prezzo | Distanza (ATR) | R:R | Motivazione |")
            L.append("|---|---|---|---|---|")
            L.append(f"| Entry | {_fmt(tp['entry'])} | - | - | {tp['entry_basis']} |")
            L.append(f"| Stop loss | {_fmt(tp['stop'])} | {tp['risk_atr']:.2f} | - | {tp['stop_basis']} |")
            for k, tg in enumerate(tp["targets"], 1):
                L.append(f"| TP{k} | {_fmt(tg['price'])} | {tg['distance_atr']:.2f} | {tg['rr']:.2f} | {tg['basis']} |")
            if tp.get("notes"):
                for nt in tp["notes"]:
                    L.append(f"- {nt}")
            L.append("")
        else:
            L.append("## Nessun trade: livelli chiave da monitorare")
            if self.resistances:
                r0 = self.resistances[0]
                L.append(f"- Sopra: {_fmt(r0['price'])} (forza {r0['score']:.1f}, {', '.join(r0['modules'])}) -> "
                         f"chiusura sopra = scenario rialzista.")
            if self.supports:
                s0 = self.supports[0]
                L.append(f"- Sotto: {_fmt(s0['price'])} (forza {s0['score']:.1f}, {', '.join(s0['modules'])}) -> "
                         f"chiusura sotto = scenario ribassista.")
            L.append("")
        L.append("## Setup riconosciuti")
        if self.setups:
            for s in self.setups:
                L.append(f"- **{s['name']}** {'LONG' if s['direction'] == 1 else 'SHORT'} (forza {s['strength']:.2f}): "
                         f"{s['description']} Condizioni: {'; '.join(s['conditions'])}.")
        else:
            L.append("- Nessun setup nominato soddisfatto.")
        L.append("")
        L.append("## Punteggio per famiglia")
        L.append(" | ".join(f"{STYLE_LABELS.get(k, k)} {v:+.2f}" for k, v in self.family_scores.items()))
        L.append("")
        L.append("Voti di regime: " + ", ".join(f"{v['module']} {v['vote']:+.2f}" for v in self.regime_votes))
        L.append("")
        L.append("## Contributi dei moduli (ordinati per impatto)")
        L.append("| Modulo | Stile | Bias | Conf. | Peso eff. | Contributo | Lettura |")
        L.append("|---|---|---|---|---|---|---|")
        for c in self.contributions:
            L.append(f"| {c['title']} | {c['style']} | {c['bias']:+.2f} | {c['confidence']:.2f} | {c['weight']:.2f} | "
                     f"{c['contribution']:+.3f} | {c['headline']} |")
        L.append("")
        L.append("## Mappa dei livelli di confluenza")
        L.append("| Lato | Prezzo | Distanza (ATR) | Forza | Moduli | Dettaglio |")
        L.append("|---|---|---|---|---|---|")
        for side, lst in (("Resistenza", self.resistances[:6]), ("Supporto", self.supports[:6])):
            for cl in lst:
                L.append(f"| {side} | {_fmt(cl['price'])} | {cl['distance_atr']:+.2f} | {cl['score']:.2f} "
                         f"({cl['strength']}) | {len(cl['modules'])} | {'; '.join(cl['names'][:4])} |")
        L.append("")
        if detail:
            L.append("## Dettaglio degli indicatori")
            for k, m in self.modules.items():
                if not m.applicable:
                    L.append(f"- **{m.title}**: non applicabile ({m.error}).")
                    continue
                L.append(f"- **{m.title}** [{m.style}] bias {m.bias:+.2f}, conf {m.confidence:.2f}: " + " ".join(m.notes))
            L.append("")
        if self.warnings:
            L.append("## Avvertenze")
            for w in self.warnings:
                L.append(f"- {w}")
            L.append("")
        L.append("_Output quantitativo di supporto alle decisioni: non costituisce consulenza finanziaria. "
                 "Verificare sempre con gestione del rischio e backtest propri._")
        return "\n".join(L)


class UnifiedEngine:
    """Esegue tutti i moduli registrati e ne combina i risultati (vedi docstring del file)."""

    def __init__(self, config: Optional[ConfluenceConfig] = None, modules: Optional[Sequence[str]] = None,
                 module_params: Optional[Dict[str, Dict[str, Any]]] = None):
        self.config = config or ConfluenceConfig()
        params = dict(self.config.module_params)
        params.update(module_params or {})
        keys = list(modules) if modules else list(MODULE_REGISTRY)
        unknown = [k for k in keys if k not in MODULE_REGISTRY]
        if unknown:
            raise ValueError(f"Moduli sconosciuti: {unknown}. Disponibili: {list(MODULE_REGISTRY)}")
        self.modules = [MODULE_REGISTRY[k](**params.get(k, {})) for k in keys if k not in self.config.disabled_modules]

    # ------------------------------------------------------------------ API
    def analyze(self, df: pd.DataFrame, symbol: Optional[str] = None, timeframe: Optional[str] = None,
                data_tz: Any = "UTC", mintick: Optional[float] = None) -> UnifiedAnalysis:
        md = MarketData(df, data_tz=data_tz, mintick=mintick, symbol=symbol, timeframe=timeframe)
        results: Dict[str, ModuleResult] = {m.key: m.run(md) for m in self.modules}
        return self.combine(md, results)

    def combine(self, md: MarketData, R: Dict[str, ModuleResult]) -> UnifiedAnalysis:
        cfg = self.config
        t = md.n - 1
        price = float(md.close[t])
        atr_v = md.last_atr(cfg.atr_len)
        ok = {k: r for k, r in R.items() if r.applicable}
        warnings: List[str] = [f"{r.title}: {r.error}" for r in R.values() if not r.applicable]

        # 1) REGIME ------------------------------------------------------------
        votes, num, den = [], 0.0, 0.0
        for k, r in ok.items():
            if r.regime is None or r.regime_confidence <= 0:
                continue
            w = cfg.module_weights.get(k, 1.0) * r.regime_confidence
            num += w * r.regime
            den += w
            votes.append({"module": k, "vote": r.regime, "weight": w})
        regime_score = _safe_div(num, den)
        if regime_score >= cfg.regime_threshold:
            regime_label = "TREND"
        elif regime_score <= -cfg.regime_threshold:
            regime_label = "RANGE"
        else:
            regime_label = "TRANSIZIONE"

        # 2) VOLATILITA' --------------------------------------------------------
        vol = {"vol_regime": "Normal", "atr_z": NAN, "expansion_prob_pct": NAN, "cluster_edge_pct": NAN}
        if "atrp" in ok:
            vol.update({k: ok["atrp"].metrics.get(k) for k in ("vol_regime", "atr_z", "expansion_prob_pct",
                                                                "cluster_edge_pct", "freq_z", "last_bar_exceeded")})
        vol_label = vol.get("vol_regime") or "Normal"
        vol_expanding = (_nz(vol.get("cluster_edge_pct"), 0) > 0 and bool(vol.get("last_bar_exceeded"))) or \
                        _nz(vol.get("freq_z"), 0) > 1.0

        # 3) DIREZIONE ----------------------------------------------------------
        contribs = []
        num = den = 0.0
        fam_num: Dict[str, float] = {}
        fam_den: Dict[str, float] = {}
        for k, r in ok.items():
            base_w = cfg.module_weights.get(k, 1.0)
            mult = max(0.2, 1.0 + regime_score * cfg.style_regime_k.get(r.style, 0.0))
            if r.style == "breakout" and vol_expanding:
                mult *= 1.2
            w = base_w * mult
            cw = r.confidence * w
            contrib = r.bias * cw
            num += contrib
            den += cw
            fam_num[r.style] = fam_num.get(r.style, 0.0) + contrib
            fam_den[r.style] = fam_den.get(r.style, 0.0) + cw
            contribs.append({"module": k, "title": r.title, "style": r.style, "bias": r.bias, "confidence": r.confidence,
                             "weight": w, "contribution": contrib, "headline": (r.notes[0] if r.notes else "")})
        raw_score = _safe_div(num, den)
        d0 = _sign(raw_score)
        aligned = sum(c["confidence"] * c["weight"] * max(0.0, d0 * c["bias"]) for c in contribs)
        total_dir = sum(c["confidence"] * c["weight"] * abs(c["bias"]) for c in contribs)
        agreement = _safe_div(aligned, total_dir)
        for c in contribs:
            c["contribution"] = _safe_div(c["contribution"], den)
        contribs.sort(key=lambda c: -abs(c["contribution"]))
        family = {s: _safe_div(fam_num[s], fam_den[s]) for s in fam_num}

        # 4) LIVELLI -------------------------------------------------------------
        supports, resistances = self._level_map(md, ok, price, atr_v)

        # 5) SETUP ---------------------------------------------------------------
        setups = self._detect_setups(md, ok, regime_score, vol_expanding, supports, resistances, price, atr_v)
        bonus = 0.0
        for s in setups:
            bonus += cfg.setup_bonus * s["direction"] * s["strength"]
        bonus = _clip(bonus, -cfg.max_setup_bonus, cfg.max_setup_bonus)
        score = _clip(raw_score + bonus)

        # 6) DECISIONE -----------------------------------------------------------
        direction = _sign(score)
        agreement_final = agreement if direction == d0 or d0 == 0 else 1.0 - agreement
        decision, strength = "HOLD", "neutro"
        if abs(score) >= cfg.trade_threshold and agreement_final >= cfg.min_agreement:
            decision = "BUY" if direction == 1 else "SELL"
            strength = "forte" if (abs(score) >= cfg.strong_threshold and agreement_final >= 0.65) else "moderato"
        elif abs(score) >= cfg.trade_threshold * 0.6:
            strength = "debole " + ("rialzista" if direction == 1 else "ribassista")
        if decision != "HOLD" and "st3d" in ok:
            cons = (ok["st3d"].metrics.get("consensus_up_pct", 50.0) - 50.0) / 50.0
            reversal = any(s["direction"] == direction and s["name"] in ("LIQUIDITY_SWEEP_REVERSAL", "DIVERGENCE_AT_EXTREME")
                           for s in setups)
            if regime_label == "TREND" and cons * direction <= -cfg.counter_trend_veto and not reversal:
                warnings.append(f"Veto contro-trend: {decision} bloccato (consenso Supertrend {cons * 100 + 0:+.0f}% "
                                f"opposto in regime TREND, nessun setup di inversione).")
                decision, strength = "HOLD", "veto contro-trend"
        plan = None
        if decision != "HOLD":
            plan = self._trade_plan(direction, price, atr_v, vol_label, supports, resistances)
            first_rr = plan["targets"][0]["rr"] if plan["targets"] else 0.0
            best_rr = max((tg["rr"] for tg in plan["targets"]), default=0.0)
            if best_rr < 1.0:
                warnings.append("Rischio/rendimento < 1 verso tutti i target: trade scartato.")
                decision, strength, plan = "HOLD", "R:R insufficiente", None
            else:
                if first_rr < cfg.min_rr - 1e-6:
                    if strength == "forte":
                        strength = "moderato"
                    plan["notes"].append(f"TP1 con R:R {first_rr:.2f} < {cfg.min_rr:g}: gestire parziali o attendere un'entry migliore.")
                obs = plan.get("obstacle")
                if obs and obs["score"] >= 4.0 and obs["rr"] < 0.5:
                    strength = "debole" if strength != "forte" else "moderato"
                    warnings.append(f"Ingresso a ridosso di una confluenza forte opposta ({_fmt(obs['price'])}, forza "
                                    f"{obs['score']:.1f}): meglio attendere la rottura o un pullback.")
        coverage = _safe_div(len(ok), len(R))
        quality = _safe_div(sum(c["confidence"] * c["weight"] for c in contribs), sum(c["weight"] for c in contribs))
        conf = (0.30 * _clip(abs(score) / 0.7, 0, 1) + 0.25 * agreement_final + 0.15 * coverage + 0.20 * quality
                + min(0.10, 0.05 * sum(1 for s in setups if s["direction"] == direction)))
        confidence_pct = 100.0 * _clip(conf, 0.0, 1.0) if decision != "HOLD" else 100.0 * _clip(conf * 0.6, 0.0, 1.0)

        # avvertenze ---------------------------------------------------------------
        trend_f = _safe_div(sum(fam_num.get(s, 0) for s in ("trend", "momentum")),
                            sum(fam_den.get(s, 0) for s in ("trend", "momentum")))
        rev_f = family.get("reversion", 0.0)
        if trend_f * rev_f < 0 and abs(trend_f) >= 0.3 and abs(rev_f) >= 0.3:
            warnings.append(f"Conflitto: famiglie trend/momentum {trend_f:+.2f} contro mean-reversion {rev_f:+.2f} "
                            f"(tipico di fine trend o di pullback).")
        if vol_label == "High Vol":
            warnings.append("Volatilita' elevata: stop piu' larghi e dimensione ridotta.")
        if md.n < 1000:
            warnings.append(f"Solo {md.n} barre: alcuni moduli (VRH, MSPO, RSID) lavorano con storia ridotta.")
        warnings.append("MSPO, ST3D e RSID-IS scelgono i parametri sulla storia analizzata (in-sample): "
                        "le loro statistiche sono ottimistiche.")

        return UnifiedAnalysis(
            symbol=md.symbol, timeframe=md.timeframe, last_time=md.ts(t), last_close=price, atr=atr_v, bars=md.n,
            decision=decision, strength=strength, score=score, raw_score=raw_score, agreement=agreement_final,
            confidence_pct=confidence_pct, regime_label=regime_label, regime_score=regime_score, regime_votes=votes,
            volatility_label=vol_label, volatility=vol, family_scores=family, contributions=contribs, setups=setups,
            trade_plan=plan, supports=supports, resistances=resistances, warnings=warnings, modules=R)

    # ------------------------------------------------------------------ livelli
    def _level_map(self, md: MarketData, ok: Dict[str, ModuleResult], price: float,
                   atr_v: float) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        cfg = self.config
        tol = max(cfg.level_cluster_atr * atr_v, md.mintick)
        pts = []
        for k, r in ok.items():
            for lv in r.levels:
                if _isnan(lv.price) or abs(lv.price - price) > cfg.max_level_distance_atr * atr_v:
                    continue
                pts.append(lv)
        pts.sort(key=lambda x: x.price)
        clusters: List[Dict[str, Any]] = []
        for lv in pts:
            if clusters and lv.price - clusters[-1]["max"] <= tol and lv.price - clusters[-1]["min"] <= 3 * tol:
                cl = clusters[-1]
            else:
                cl = {"min": lv.price, "max": lv.price, "items": []}
                clusters.append(cl)
            cl["items"].append(lv)
            cl["max"] = max(cl["max"], lv.price)
        out_s, out_r = [], []
        for cl in clusters:
            per_mod: Dict[str, float] = {}
            for lv in cl["items"]:
                per_mod[lv.module] = max(per_mod.get(lv.module, 0.0), lv.weight)
            score = sum(per_mod.values())
            wsum = sum(lv.weight for lv in cl["items"])
            cp = sum(lv.price * lv.weight for lv in cl["items"]) / wsum if wsum > 0 else cl["min"]
            kinds = sorted({lv.kind for lv in cl["items"]})
            item = {"price": cp, "low": cl["min"], "high": cl["max"], "score": score,
                    "strength": "forte" if score >= 3.0 else ("media" if score >= 1.8 else "debole"),
                    "modules": sorted(per_mod), "kinds": kinds, "liquidity": "liquidity" in kinds or "target" in kinds,
                    "has_liquidity_pool": "liquidity" in kinds,
                    "names": [f"{lv.module}: {lv.name}" for lv in sorted(cl["items"], key=lambda x: -x.weight)],
                    "distance_atr": (cp - price) / atr_v if atr_v > 0 else 0.0}
            if cp >= price:
                out_r.append(item)
            else:
                out_s.append(item)
        out_r.sort(key=lambda x: x["price"])
        out_s.sort(key=lambda x: -x["price"])
        return out_s, out_r

    # ------------------------------------------------------------------ setup
    def _detect_setups(self, md: MarketData, ok: Dict[str, ModuleResult], regime: float, vol_expanding: bool,
                       supports: List[Dict[str, Any]], resistances: List[Dict[str, Any]], price: float,
                       atr_v: float) -> List[Dict[str, Any]]:
        cfg = self.config

        def met(key: str, name: str, default: Any = None) -> Any:
            r = ok.get(key)
            if r is None:
                return default
            v = r.metrics.get(name, default)
            return default if v is None else v

        def bias(key: str) -> float:
            return ok[key].bias if key in ok else 0.0

        def has_sig(key: str, prefixes: Tuple[str, ...], d: int, max_bars: int) -> Optional[Signal]:
            r = ok.get(key)
            if r is None:
                return None
            cands = [s for s in r.signals if s.direction == d and s.bars_ago <= max_bars and s.name.startswith(prefixes)]
            return cands[-1] if cands else None

        cons = (met("st3d", "consensus_up_pct", 50.0) - 50.0) / 50.0
        mss_tr = met("mss", "trend", 0)
        vrh_z = _nz(met("vrh", "z_score", 0.0))
        ofvd_z = _nz(met("ofvd", "vwap_z", 0.0))
        flow = _nz(met("ofc", "flow", 0.0))
        setups: List[Dict[str, Any]] = []

        def near_level(lst: List[Dict[str, Any]], max_atr: float, min_score: float) -> Optional[Dict[str, Any]]:
            for cl in lst:
                if abs(cl["price"] - price) <= max_atr * atr_v and cl["score"] >= min_score:
                    return cl
            return None

        def add(name: str, d: int, conds: List[str], need: int, total: int, desc: str) -> None:
            if len(conds) >= need:
                setups.append({"name": name, "direction": d, "strength": min(1.0, len(conds) / float(total)),
                               "conditions": conds, "description": desc})

        for d in (1, -1):
            lbl = "rialzista" if d == 1 else "ribassista"
            # 1. TREND_CONTINUATION ------------------------------------------------
            c1: List[str] = []
            core = 0
            if regime >= cfg.regime_threshold:
                c1.append(f"regime TREND ({regime:+.2f})")
            if cons * d >= 0.5:
                c1.append(f"consenso Supertrend {50 + cons * 50:.0f}% up")
                core += 1
            if mss_tr == d:
                c1.append(f"struttura di mercato {lbl}")
                core += 1
            if flow * d > 30 or bias("mspo") * d > 0.3:
                c1.append("flusso Omni-Flow / ensemble MSPO concordi")
            if vrh_z * d < 2.0 and ofvd_z * d < 2.0:
                c1.append("prezzo non in estensione estrema (VRH/VWAP < 2 sd)")
            if core == 2:
                add("TREND_CONTINUATION", d, c1, 4, 5, f"Trend {lbl} confermato da consenso, struttura e flusso.")
            # 2. PULLBACK_IN_TREND -------------------------------------------------
            if cons * d >= 0.3 and mss_tr == d and regime > -cfg.regime_threshold:
                c2 = [f"trend {lbl} (Supertrend + struttura)"]
                lvl = near_level(supports if d == 1 else resistances, 1.0, 1.5)
                if lvl:
                    c2.append(f"prezzo su confluenza {'di supporto' if d == 1 else 'di resistenza'} {_fmt(lvl['price'])} "
                              f"(forza {lvl['score']:.1f})")
                retr = met("mss", "retracement", NAN)
                if (not _isnan(retr) and 0.25 <= retr <= 1.0 and met("mss", "impulse_direction", 0) == d) or vrh_z * d < 0 \
                        or ofvd_z * d < 0:
                    c2.append("ritracciamento in corso (sotto regressione/VWAP o ritracciamento 25-100%)")
                if lvl:
                    add("PULLBACK_IN_TREND", d, c2, 3, 3, f"Ritracciamento dentro un trend {lbl} su un livello di confluenza.")
            # 3. BREAKOUT_CONFIRMED ---------------------------------------------------
            ev = [s for s in (has_sig("rb", ("BREAK",), d, 10), has_sig("orb", ("ORB_",), d, 12),
                              has_sig("mss", ("BOS", "CHoCH"), d, 5), has_sig("eqhl", ("EQH_BREAKOUT", "EQL_BREAKDOWN"), d, 5),
                              has_sig("par", ("RANGE_",), d, 5)) if s is not None]
            if ev:
                c3 = [f"breakout {s.module.upper()} {s.name} {s.bars_ago} barre fa" for s in ev]
                if vol_expanding or _nz(met("atrp", "atr_z", 0.0)) > 0.5:
                    c3.append("volatilita' in espansione (ATR/clustering)")
                if flow * d > 50:
                    c3.append("Omni-Flow direzionale nello stesso verso")
                pos = met("of3d", "position", "")
                if (d == 1 and pos.startswith("sopra")) or (d == -1 and pos.startswith("sotto")):
                    c3.append("prezzo fuori dalla value area nel verso del breakout")
                if _nz(met("tvp", "poc_migration_atr", 0.0)) * d > 0.3:
                    c3.append("POC in migrazione nel verso del breakout")
                add("BREAKOUT_CONFIRMED", d, c3, len(ev) + 2, len(ev) + 4, f"Rottura {lbl} con conferme di volatilita'/flusso/valore.")
            # 4. LIQUIDITY_SWEEP_REVERSAL ----------------------------------------------
            sw = [s for s in (has_sig("ldp", ("ABS", "EXH", "DIV", "REJ"), d, 5),
                              has_sig("eqhl", ("EQH_SWEEP", "EQL_SWEEP"), d, 5),
                              has_sig("ofvd", ("BUY_STOPS", "SELL_STOPS"), d, 5)) if s is not None]
            if sw:
                c4 = [f"presa di liquidita' {s.module.upper()} {s.name} {s.bars_ago} barre fa" for s in sw]
                if has_sig("rsid", ("BULL_DIV", "BEAR_DIV"), d, 10):
                    c4.append("divergenza RSI concorde")
                if vrh_z * d <= -1.5 or ofvd_z * d <= -1.5:
                    c4.append("prezzo a un estremo statistico (<= -1.5 sd nel verso opposto)")
                if has_sig("mss", ("CHoCH",), d, 5):
                    c4.append("CHoCH concorde")
                if has_sig("ofc", ("BULL_INJ", "BEAR_INJ"), d, 5):
                    c4.append("impulso di flusso concorde")
                add("LIQUIDITY_SWEEP_REVERSAL", d, c4, len(sw) + 1, len(sw) + 3,
                    f"Sweep della liquidita' {'sotto i minimi' if d == 1 else 'sopra i massimi'} con segnali di inversione.")
            # 5. RANGE_MEAN_REVERSION ----------------------------------------------------
            if regime <= -cfg.regime_threshold and abs(cons) < 0.6:
                c5 = [f"regime RANGE ({regime:+.2f})"]
                if has_sig("vrh", ("MR_",), d, 3) or vrh_z * d <= -1.8:
                    c5.append(f"VRH all'estremo del canale (z {vrh_z:+.2f})")
                if ofvd_z * d <= -1.8:
                    c5.append(f"deviazione VWAP estrema ({ofvd_z:+.2f} sd)")
                pos = met("of3d", "position", "")
                if (d == 1 and pos.startswith("sotto")) or (d == -1 and pos.startswith("sopra")):
                    c5.append("prezzo fuori dalla value area (ritorno verso il POC atteso)")
                add("RANGE_MEAN_REVERSION", d, c5, 3, 4, "Mercato laterale con prezzo all'estremo: ritorno verso POC/VWAP.")
            # 6. DIVERGENCE_AT_EXTREME ------------------------------------------------------
            dv = has_sig("rsid", ("BULL_DIV", "BEAR_DIV"), d, 10)
            if dv:
                c6 = [f"divergenza RSI{met('rsid', 'visual_length', '')} {dv.bars_ago} barre fa"]
                if vrh_z * d <= -1.0 or ofvd_z * d <= -1.0:
                    c6.append("prezzo esteso rispetto a regressione/VWAP")
                if near_level(supports if d == 1 else resistances, 0.75, 1.5):
                    c6.append("su un livello di confluenza")
                if str(met("rsid", "validation", "")).startswith("VALIDATO"):
                    c6.append("RSI validato fuori campione")
                add("DIVERGENCE_AT_EXTREME", d, c6, 2, 4, "Divergenza RSI su un estremo di prezzo.")
            # 7. MOMENTUM_IGNITION ----------------------------------------------------------
            inj = has_sig("ofc", ("BULL_INJ", "BEAR_INJ"), d, 5)
            if inj:
                c7 = [f"impulso Omni-Flow {inj.bars_ago} barre fa"]
                bulls, bears = met("sf", "bullish", 0), met("sf", "bearish", 0)
                if (bulls - bears) * d >= 5:
                    c7.append(f"Signal Forge {bulls} vs {bears}")
                if met("usb", "cross_state", 0) == d:
                    c7.append("EMA 9/21 concordi")
                dp = met("svma", "delta_pct", 50.0)
                if (dp - 50.0) * d >= 5:
                    c7.append(f"delta di sessione {dp:.0f}%")
                add("MOMENTUM_IGNITION", d, c7, 3, 4, f"Accensione di momentum {lbl} confermata dal pannello indicatori.")
        return setups

    # ------------------------------------------------------------------ piano
    def _trade_plan(self, d: int, entry: float, atr_v: float, vol_label: str, supports: List[Dict[str, Any]],
                    resistances: List[Dict[str, Any]]) -> Dict[str, Any]:
        cfg = self.config
        notes: List[str] = []
        protect = supports if d == 1 else resistances
        stop, basis = None, ""
        for cl in protect:
            edge = cl["low"] if d == 1 else cl["high"]
            dist = (entry - edge) * d
            if cfg.sl_min_atr * atr_v <= dist + cfg.sl_buffer_atr * atr_v <= cfg.sl_max_atr * atr_v \
                    and cl["score"] >= cfg.min_stop_score:
                stop = edge - d * cfg.sl_buffer_atr * atr_v
                basis = f"oltre confluenza {_fmt(cl['price'])} (forza {cl['score']:.1f}: {', '.join(cl['modules'][:4])})"
                break
        if stop is None:
            m = cfg.default_sl_atr.get(vol_label, 2.0)
            stop = entry - d * m * atr_v
            basis = f"{m:g} x ATR (nessuna confluenza utile entro {cfg.sl_min_atr:g}-{cfg.sl_max_atr:g} ATR)"
        risk = abs(entry - stop)
        tgt_side = resistances if d == 1 else supports
        cands = [cl for cl in tgt_side if (cl["price"] - entry) * d >= 0.3 * atr_v and (cl["score"] >= 0.8 or cl["liquidity"])]
        targets: List[Dict[str, Any]] = []

        def mk(px: float, why: str) -> Dict[str, Any]:
            return {"price": px, "rr": abs(px - entry) / risk if risk > 0 else 0.0,
                    "distance_atr": abs(px - entry) / atr_v if atr_v > 0 else 0.0, "basis": why}

        def why(cl: Dict[str, Any]) -> str:
            mods = ", ".join(cl["modules"][:4])
            if "liquidity" in cl["kinds"]:
                return f"liquidita' + confluenza {cl['strength']} ({mods})"
            if "target" in cl["kinds"]:
                return f"target statistico + confluenza {cl['strength']} ({mods})"
            return f"confluenza {cl['strength']} ({mods})"

        def pick(lo_rr: float, hi_rr: float, used: set, liquidity_only: bool = False) -> Optional[int]:
            for k, cl in enumerate(cands):
                edge = cl["low"] if d == 1 else cl["high"]
                rr = abs(edge - entry) / risk if risk > 0 else 0.0
                if k in used or rr < lo_rr or rr > hi_rr or (liquidity_only and not cl["liquidity"]):
                    continue
                return k
            return None

        used: set = set()
        # TP1: prima confluenza tra 1R e 3R, altrimenti 1.5R
        k1 = pick(1.0, 3.0, used)
        if k1 is not None:
            used.add(k1)
            cl = cands[k1]
            targets.append(mk(cl["low"] if d == 1 else cl["high"], why(cl)))
        else:
            targets.append(mk(entry + d * 1.5 * risk, "1.5R (nessuna confluenza tra 1R e 3R)"))
        # TP2: confluenza successiva fino a 5R, altrimenti TP1 + 1R (min 2.5R)
        k2 = pick(max(1.8, targets[-1]["rr"] + 0.4), 5.0, used)
        if k2 is not None:
            used.add(k2)
            cl = cands[k2]
            targets.append(mk(cl["low"] if d == 1 else cl["high"], why(cl)))
        else:
            m2 = max(2.5, targets[-1]["rr"] + 1.0)
            targets.append(mk(entry + d * m2 * risk, f"{m2:.1f}R (nessuna confluenza adatta)"))
        # TP3: bacino di liquidita' oltre TP2 (fino a 8R), altrimenti estensione
        k3 = pick(targets[-1]["rr"] + 0.3, 8.0, used, liquidity_only=True)
        if k3 is not None:
            cl = cands[k3]
            targets.append(mk(cl["price"], why(cl)))
        else:
            m3 = max(4.0, targets[-1]["rr"] + 1.5)
            targets.append(mk(entry + d * m3 * risk, f"estensione {m3:.1f}R"))
        obstacle = None
        for cl in tgt_side:
            if 0 < (cl["price"] - entry) * d < risk and cl["score"] >= 2.5:
                obstacle = {"price": cl["price"], "score": cl["score"], "rr": abs(cl["price"] - entry) / risk if risk else 0.0}
                notes.append(f"Ostacolo: confluenza forte a {_fmt(cl['price'])} prima di 1R (forza {cl['score']:.1f}).")
                break
        return {"direction": d, "entry": entry, "entry_basis": "chiusura dell'ultima barra", "stop": stop,
                "stop_basis": basis, "risk": risk, "risk_atr": risk / atr_v if atr_v > 0 else 0.0,
                "targets": targets, "obstacle": obstacle, "notes": notes}


# =============================================================================
# SEZIONE 10 - MetaTrader 5, TradingAgents e riga di comando
# =============================================================================

# Fuso dell'ora server del broker (es. "Europe/Athens" o "UTC+2"); impostabile anche con la variabile
# d'ambiente UNIFIED_INDICATORS_SERVER_TZ oppure assegnando unified_indicators.DEFAULT_SERVER_TZ.
DEFAULT_SERVER_TZ: Optional[str] = os.environ.get("UNIFIED_INDICATORS_SERVER_TZ") or None

_TF_ALIASES = {
    "1": "M1", "1M": "M1", "M1": "M1", "5": "M5", "5M": "M5", "M5": "M5", "15": "M15", "15M": "M15", "M15": "M15",
    "30": "M30", "30M": "M30", "M30": "M30", "60": "H1", "1H": "H1", "H1": "H1", "120": "H2", "2H": "H2", "H2": "H2",
    "240": "H4", "4H": "H4", "H4": "H4", "D": "D1", "1D": "D1", "D1": "D1", "W": "W1", "1W": "W1", "W1": "W1",
    "MN": "MN1", "MN1": "MN1",
}


def normalize_timeframe(tf: str) -> str:
    key = str(tf).strip().upper()
    if key not in _TF_ALIASES:
        raise ValueError(f"Timeframe non riconosciuto: {tf}")
    return _TF_ALIASES[key]


def load_mt5_ohlcv(symbol: str, timeframe: str = "H1", bars: int = 3000, include_current_bar: bool = False,
                   server_tz: Optional[str] = None, initialize: bool = True, **init_kwargs: Any) -> pd.DataFrame:
    """Scarica le barre da MetaTrader 5.  Per default esclude la barra in formazione.
    server_tz: fuso dell'ora server del broker (MT5 restituisce l'ora server come se fosse UTC)."""
    try:
        import MetaTrader5 as mt5  # type: ignore
    except ImportError as exc:  # pragma: no cover - dipende dall'ambiente
        raise ImportError("Pacchetto MetaTrader5 non installato (pip install MetaTrader5)") from exc
    if initialize and not mt5.initialize(**init_kwargs):
        raise RuntimeError(f"MT5 initialize() fallita: {mt5.last_error()}")
    tf = normalize_timeframe(timeframe)
    mt5.symbol_select(symbol, True)
    rates = mt5.copy_rates_from_pos(symbol, getattr(mt5, "TIMEFRAME_" + tf), 0 if include_current_bar else 1, int(bars))
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"Nessun dato MT5 per {symbol} {tf}: {mt5.last_error()}")
    df = pd.DataFrame(rates)
    df["time"] = pd.to_datetime(df["time"], unit="s")
    df = df.set_index("time")
    tz = server_tz or DEFAULT_SERVER_TZ
    if tz:
        df.index = localize_index(pd.DatetimeIndex(df.index), tz)
    info = mt5.symbol_info(symbol)
    df.attrs.update(symbol=symbol, timeframe=tf, mintick=getattr(info, "point", None) if info else None)
    return df


def analyze_symbol(symbol: str, timeframe: str = "H1", bars: int = 3000, server_tz: Optional[str] = None,
                   config: Optional[ConfluenceConfig] = None) -> UnifiedAnalysis:
    df = load_mt5_ohlcv(symbol, timeframe, bars, server_tz=server_tz)
    tz = server_tz or DEFAULT_SERVER_TZ or "UTC"
    return UnifiedEngine(config).analyze(df, symbol=symbol, timeframe=normalize_timeframe(timeframe), data_tz=tz)


def get_unified_indicators_report(symbol: str, timeframe: str = "H1", bars: int = 3000,
                                  server_tz: Optional[str] = None) -> str:
    """Report Markdown per gli agenti LLM.  Non solleva eccezioni: in caso di errore restituisce il messaggio."""
    try:
        return analyze_symbol(symbol, timeframe, bars, server_tz).to_markdown()
    except Exception as exc:  # pragma: no cover - dipende da MT5
        log.exception("Analisi unificata fallita")
        return f"Analisi unificata non disponibile per {symbol} {timeframe}: {type(exc).__name__}: {exc}"


try:  # tool LangChain opzionale per TradingAgents
    from langchain_core.tools import tool as _lc_tool  # type: ignore
except Exception:  # pragma: no cover
    _lc_tool = None

if _lc_tool is not None:
    @_lc_tool
    def get_unified_indicators(
        symbol: Annotated[str, "Simbolo MetaTrader 5, es. EURUSD, XAUUSD, US500"],
        timeframe: Annotated[str, "Timeframe: M1, M5, M15, M30, H1, H4, D1"] = "H1",
        bars: Annotated[int, "Barre da analizzare (consigliato 1500-3000)"] = 3000,
    ) -> str:
        """Analisi di confluenza di 20 indicatori LuxAlgo (trend, struttura di mercato, liquidita', volume
        profile, order flow, volatilita') sui dati MetaTrader 5. Restituisce in Markdown: regime di mercato,
        indicazione BUY/SELL/HOLD con score e confidenza, setup riconosciuti, mappa dei livelli di confluenza
        e piano di trade (entry, stop, target, R:R)."""
        return get_unified_indicators_report(symbol, timeframe, bars)
else:
    get_unified_indicators = None


def demo_data(n: int = 3000, seed: int = 7, freq: str = "h", start: str = "2025-01-01") -> pd.DataFrame:
    """Dati sintetici con fasi di trend e di range (solo per test)."""
    rng = np.random.default_rng(seed)
    drift = np.repeat([0.0004, 0.0, -0.0005, 0.0, 0.0006, -0.0002], int(math.ceil(n / 6)))[:n]
    ret = drift + rng.standard_t(4, n) * 0.0022
    close = 1.10 * np.exp(np.cumsum(ret))
    op = np.r_[close[0], close[:-1]] * (1 + rng.normal(0, 0.0004, n))
    hi = np.maximum(op, close) * (1 + np.abs(rng.normal(0, 0.0015, n)))
    lo = np.minimum(op, close) * (1 - np.abs(rng.normal(0, 0.0015, n)))
    vol = rng.integers(500, 3000, n) * (1 + 3 * np.abs(ret) / 0.003)
    idx = pd.date_range(start, periods=n, freq=freq, tz="UTC")
    return pd.DataFrame({"open": op.round(5), "high": hi.round(5), "low": lo.round(5), "close": close.round(5),
                         "tick_volume": vol.round()}, index=idx)


def _main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Motore unificato di 20 indicatori LuxAlgo (TradingAgents-Mt5)")
    ap.add_argument("--symbol", help="simbolo MT5 (richiede il pacchetto MetaTrader5)")
    ap.add_argument("--timeframe", default="H1")
    ap.add_argument("--bars", type=int, default=3000)
    ap.add_argument("--server-tz", default=None, help="fuso dell'ora server/dati, es. Europe/Athens o UTC+2")
    ap.add_argument("--csv", help="file CSV con colonne time, open, high, low, close, volume/tick_volume")
    ap.add_argument("--demo", action="store_true", help="usa dati sintetici")
    ap.add_argument("--modules", help="sottoinsieme di moduli separati da virgola (default: tutti)")
    ap.add_argument("--json", action="store_true", help="stampa JSON invece del Markdown")
    ap.add_argument("--out", help="salva l'output su file")
    ap.add_argument("--list", action="store_true", help="elenca i moduli disponibili")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    if a.list:
        for k, cls in MODULE_REGISTRY.items():
            print(f"{k:6s} batch {cls.batch}  {cls.style:10s} {cls.title}  [{cls.license}]")
        return 0
    engine = UnifiedEngine(modules=a.modules.split(",") if a.modules else None)
    tz = a.server_tz or DEFAULT_SERVER_TZ or "UTC"
    if a.demo:
        res = engine.analyze(demo_data(), symbol="DEMO", timeframe="H1")
    elif a.csv:
        res = engine.analyze(pd.read_csv(a.csv), symbol=a.symbol or a.csv, timeframe=a.timeframe, data_tz=tz)
    elif a.symbol:
        df = load_mt5_ohlcv(a.symbol, a.timeframe, a.bars, server_tz=a.server_tz)
        res = engine.analyze(df, symbol=a.symbol, timeframe=normalize_timeframe(a.timeframe), data_tz=tz)
    else:
        ap.print_help()
        return 2
    text = res.to_json() if a.json else res.to_markdown()
    if a.out:
        with open(a.out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(res.summary_line())
    else:
        print(text)
    return 0


__all__ = [
    "UnifiedEngine", "UnifiedAnalysis", "ConfluenceConfig", "MarketData", "ModuleResult", "Signal", "Level",
    "IndicatorModule", "MODULE_REGISTRY", "register_module", "load_mt5_ohlcv", "analyze_symbol",
    "get_unified_indicators_report", "get_unified_indicators", "normalize_ohlcv", "demo_data", "DEFAULT_SERVER_TZ",
] + [cls.__name__ for cls in MODULE_REGISTRY.values()]


if __name__ == "__main__":
    sys.exit(_main())

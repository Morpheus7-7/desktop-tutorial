"""Motore a confluenza: unisce struttura, OB, liquidita' e divergenze.

Elabora le barre chiuse in ordine cronologico e produce TradeSignal quando
un trigger (reversal su sweep di liquidita' oppure retest di order block)
raggiunge il punteggio minimo di confluenza:

    +1  trend strutturale swing concorde
    +1  prezzo in discount (long) / premium (short)
    +1  divergenza RSI attiva nella direzione del trade
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd

from ..config import StrategyConfig
from .divergence import DivergenceEngine
from .indicators import atr_wilder, rsi_wilder
from .liquidity import LiquidityEngine
from .order_blocks import OrderBlockBook
from .structure import PremiumDiscountTracker, StructureEngine


@dataclasses.dataclass
class TradeSignal:
    direction: int          # +1 long, -1 short
    sl_price: float         # stop loss suggerito (buffer ATR incluso)
    reason: str             # es. "LDP-REJ", "OB retest"
    score: int              # punteggio di confluenza raggiunto
    bar_time: pd.Timestamp  # tempo della barra che ha generato il segnale


class ConfluenceEngine:
    """Mantiene lo stato della strategia e valuta ogni barra chiusa."""

    def __init__(self, cfg: StrategyConfig):
        self.cfg = cfg
        self.swing = StructureEngine(cfg.swing_length)
        self.internal = StructureEngine(cfg.internal_length)
        self.pd_tracker = PremiumDiscountTracker()
        self.obs = OrderBlockBook(cfg.max_order_blocks, cfg.ob_max_age_bars)
        self.liq = LiquidityEngine(cfg.ldp_length, cfg.ldp_max_zones, cfg.signals)
        self.div = DivergenceEngine(cfg.div_lookback, cfg.div_valid_bars)
        self._n_processed = 0

    # ------------------------------------------------------------------ state
    def confluence_score(self, direction: int, close: float, i: int) -> int:
        score = 0
        if self.swing.trend == direction:
            score += 1
        if self.cfg.use_premium_discount:
            if direction == +1 and self.pd_tracker.in_discount(close):
                score += 1
            elif direction == -1 and self.pd_tracker.in_premium(close):
                score += 1
        else:
            score += 1
        div_ok = (self.div.bull_active(i) if direction == +1
                  else self.div.bear_active(i))
        if div_ok:
            score += 1
        return score

    def divergence_ok(self, direction: int, i: int) -> bool:
        if not self.cfg.require_divergence:
            return True
        return (self.div.bull_active(i) if direction == +1
                else self.div.bear_active(i))

    # -------------------------------------------------------------- main loop
    def process(self, df: pd.DataFrame) -> list[TradeSignal]:
        """Elabora le barre non ancora viste di ``df`` (OHLCV cronologico).

        df richiede colonne: time, open, high, low, close, tick_volume.
        Ritorna i segnali generati dalle barre nuove (di norma 0 o 1 in live,
        molti in backtest).
        """
        o = df["open"].to_numpy(float)
        h = df["high"].to_numpy(float)
        l = df["low"].to_numpy(float)
        c = df["close"].to_numpy(float)
        v = df["tick_volume"].to_numpy(float)
        t = df["time"]

        atr = atr_wilder(h, l, c, self.cfg.atr_period)
        rsi = rsi_wilder(c, self.cfg.rsi_period)

        signals: list[TradeSignal] = []
        start = max(self._n_processed, 1)

        for i in range(start, len(df)):
            sig = self._process_bar(o, h, l, c, v, atr, rsi, i)
            if sig is not None:
                sig.bar_time = t.iloc[i]
                signals.append(sig)

        self._n_processed = len(df)
        return signals

    def _process_bar(self, o, h, l, c, v, atr, rsi, i) -> TradeSignal | None:
        # 1. struttura swing + range premium/discount
        brk = self.swing.update(h, l, c, i)
        if brk is not None:
            self.pd_tracker.on_swing_break(self.swing)
        self.pd_tracker.on_bar(float(h[i]), float(l[i]))

        # 2. struttura interna -> order blocks
        brk_in = self.internal.update(h, l, c, i)
        if brk_in is not None:
            self.obs.add_from_break(h, l, brk_in.pivot_idx, i, brk_in.direction)
        self.obs.mitigate(float(h[i]), float(l[i]), i)

        # 3. zone di liquidita'
        self.liq.create_zones(o, h, l, c, atr, i)
        rev = self.liq.process_bar(float(o[i]), float(h[i]), float(l[i]),
                                   float(c[i]), float(v[i]), i)

        # 4. divergenze RSI
        self.div.update(h, l, rsi, i)

        if np.isnan(atr[i]) or atr[i] <= 0:
            return None
        buf = self.cfg.sl_buffer_atr * float(atr[i])

        use_sweep = self.cfg.entry_model in ("sweep", "both")
        use_ob = self.cfg.entry_model in ("ob", "both")

        candidates: list[TradeSignal] = []

        if use_sweep and rev is not None:
            sl = rev.sl_price - buf if rev.direction == +1 else rev.sl_price + buf
            candidates.append(TradeSignal(rev.direction, sl,
                                          f"LDP-{rev.tag}", 0, None))

        if use_ob:
            ob_long = self.obs.check_retest(float(h[i]), float(l[i]),
                                            float(c[i]), i, +1)
            if ob_long is not None:
                candidates.append(TradeSignal(+1, ob_long.bottom - buf,
                                              "OB retest", 0, None))
            ob_short = self.obs.check_retest(float(h[i]), float(l[i]),
                                             float(c[i]), i, -1)
            if ob_short is not None:
                candidates.append(TradeSignal(-1, ob_short.top + buf,
                                              "OB retest", 0, None))

        for cand in candidates:
            if not self.divergence_ok(cand.direction, i):
                continue
            score = self.confluence_score(cand.direction, float(c[i]), i)
            if score >= self.cfg.min_confluence:
                cand.score = score
                return cand
        return None

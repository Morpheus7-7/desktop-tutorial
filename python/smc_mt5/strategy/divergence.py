"""Divergenze RSI regolari sui pivot dell'oscillatore (filtro mediana 50)."""

from __future__ import annotations

import numpy as np


class DivergenceEngine:
    def __init__(self, lookback: int = 5, valid_bars: int = 12):
        self.lb = lookback
        self.valid_bars = valid_bars
        self._prev_pl_rsi = None
        self._prev_pl_price = None
        self._prev_ph_rsi = None
        self._prev_ph_price = None
        self.bull_until = -1        # indice barra fino a cui la div e' valida
        self.bear_until = -1

    def _is_rsi_pivot(self, rsi: np.ndarray, p: int, low_pivot: bool) -> bool:
        if p - self.lb < 0 or p + self.lb >= len(rsi):
            return False
        window = rsi[p - self.lb:p + self.lb + 1]
        if np.isnan(window).any():
            return False
        cand = rsi[p]
        others = np.delete(window, self.lb)
        return bool((others > cand).all() if low_pivot else (others < cand).all())

    def update(self, high: np.ndarray, low: np.ndarray, rsi: np.ndarray, i: int):
        p = i - self.lb
        if p < 0:
            return

        if self._is_rsi_pivot(rsi, p, low_pivot=True):
            price_low = float(low[p])
            val = float(rsi[p])
            if (self._prev_pl_rsi is not None
                    and price_low < self._prev_pl_price
                    and val > self._prev_pl_rsi
                    and val < 50):
                self.bull_until = i + self.valid_bars
            self._prev_pl_rsi = val
            self._prev_pl_price = price_low

        if self._is_rsi_pivot(rsi, p, low_pivot=False):
            price_high = float(high[p])
            val = float(rsi[p])
            if (self._prev_ph_rsi is not None
                    and price_high > self._prev_ph_price
                    and val < self._prev_ph_rsi
                    and val > 50):
                self.bear_until = i + self.valid_bars
            self._prev_ph_rsi = val
            self._prev_ph_price = price_high

    def bull_active(self, i: int) -> bool:
        return i <= self.bull_until

    def bear_active(self, i: int) -> bool:
        return i <= self.bear_until

"""Strategia incrocio di medie mobili (fast vs slow)."""
from __future__ import annotations

import pandas as pd

from ..data.indicators import ema
from ..types import Signal
from .base import Strategy


class MACrossoverStrategy(Strategy):
    name = "ma_crossover"

    def __init__(self, weight=1.0, fast=20, slow=50, **_):
        super().__init__(weight=weight)
        self.fast, self.slow = int(fast), int(slow)

    def generate(self, df: pd.DataFrame) -> Signal:
        if not self._need(df, self.slow + 2):
            return Signal(self.name, 0, 0.0)
        fast = ema(df["close"], self.fast)
        slow = ema(df["close"], self.slow)
        f0, f1 = float(fast.iloc[-1]), float(fast.iloc[-2])
        s0, s1 = float(slow.iloc[-1]), float(slow.iloc[-2])

        spread = abs(f0 - s0) / s0 if s0 else 0.0
        if f1 <= s1 and f0 > s0:   # golden cross
            return Signal(self.name, 1, min(1.0, 0.6 + spread * 20))
        if f1 >= s1 and f0 < s0:   # death cross
            return Signal(self.name, -1, min(1.0, 0.6 + spread * 20))

        # trend in corso: segnale debole
        direction = 1 if f0 > s0 else -1
        return Signal(self.name, direction, min(0.35, spread * 15))

"""Strategia MACD: incrocio MACD/Signal con conferma dell'istogramma."""
from __future__ import annotations

import pandas as pd

from ..data.indicators import macd
from ..types import Signal
from .base import Strategy


class MACDStrategy(Strategy):
    name = "macd"

    def __init__(self, weight=1.0, fast=12, slow=26, signal=9, **_):
        super().__init__(weight=weight)
        self.fast, self.slow, self.signal = int(fast), int(slow), int(signal)

    def generate(self, df: pd.DataFrame) -> Signal:
        if not self._need(df, self.slow + self.signal + 2):
            return Signal(self.name, 0, 0.0)
        macd_line, signal_line, hist = macd(df["close"], self.fast, self.slow, self.signal)
        h0, h1 = float(hist.iloc[-1]), float(hist.iloc[-2])

        # incrocio dell'istogramma sopra/sotto lo zero
        if h1 <= 0 < h0:
            return Signal(self.name, 1, min(1.0, 0.5 + abs(h0) * 50), meta={"hist": h0})
        if h1 >= 0 > h0:
            return Signal(self.name, -1, min(1.0, 0.5 + abs(h0) * 50), meta={"hist": h0})

        # nessun incrocio: segnale debole nella direzione dell'istogramma
        direction = 1 if h0 > 0 else -1 if h0 < 0 else 0
        return Signal(self.name, direction, min(0.4, abs(h0) * 30), meta={"hist": h0})

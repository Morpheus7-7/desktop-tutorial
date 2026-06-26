"""Strategia RSI: ipervenduto -> long, ipercomprato -> short."""
from __future__ import annotations

import pandas as pd

from ..data.indicators import rsi
from ..types import Signal
from .base import Strategy


class RSIStrategy(Strategy):
    name = "rsi"

    def __init__(self, weight=1.0, period=14, oversold=30, overbought=70, **_):
        super().__init__(weight=weight)
        self.period = int(period)
        self.oversold = float(oversold)
        self.overbought = float(overbought)

    def generate(self, df: pd.DataFrame) -> Signal:
        if not self._need(df, self.period + 2):
            return Signal(self.name, 0, 0.0)
        value = float(rsi(df["close"], self.period).iloc[-1])

        if value <= self.oversold:
            # più è basso, più confidenza (0 a oversold -> 1)
            conf = min(1.0, (self.oversold - value) / self.oversold + 0.3)
            return Signal(self.name, 1, conf, meta={"rsi": value})
        if value >= self.overbought:
            conf = min(1.0, (value - self.overbought) / (100 - self.overbought) + 0.3)
            return Signal(self.name, -1, conf, meta={"rsi": value})
        return Signal(self.name, 0, 0.0, meta={"rsi": value})

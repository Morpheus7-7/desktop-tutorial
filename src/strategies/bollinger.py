"""Strategia Bollinger Bands: ritorno verso la media dopo aver toccato le bande."""
from __future__ import annotations

import pandas as pd

from ..data.indicators import bollinger
from ..types import Signal
from .base import Strategy


class BollingerStrategy(Strategy):
    name = "bollinger"

    def __init__(self, weight=1.0, period=20, std=2.0, **_):
        super().__init__(weight=weight)
        self.period, self.std = int(period), float(std)

    def generate(self, df: pd.DataFrame) -> Signal:
        if not self._need(df, self.period + 2):
            return Signal(self.name, 0, 0.0)
        upper, mid, lower = bollinger(df["close"], self.period, self.std)
        price = float(df["close"].iloc[-1])
        up, mp, lp = float(upper.iloc[-1]), float(mid.iloc[-1]), float(lower.iloc[-1])
        width = up - lp

        if width <= 0:
            return Signal(self.name, 0, 0.0)
        if price <= lp:                      # sotto la banda inferiore -> rimbalzo long
            conf = min(1.0, 0.5 + (lp - price) / width)
            return Signal(self.name, 1, conf)
        if price >= up:                      # sopra la banda superiore -> short
            conf = min(1.0, 0.5 + (price - up) / width)
            return Signal(self.name, -1, conf)
        return Signal(self.name, 0, 0.0)

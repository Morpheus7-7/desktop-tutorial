"""Struttura SMC: pivot swing/internal, BOS/CHoCH, premium/discount."""

from __future__ import annotations

import dataclasses

import numpy as np

from .indicators import is_pivot_high, is_pivot_low


@dataclasses.dataclass
class StructureBreak:
    direction: int          # +1 rialzista, -1 ribassista
    was_choch: bool         # True = CHoCH (contro trend), False = BOS
    pivot_idx: int          # indice barra del pivot rotto
    break_idx: int          # indice barra della rottura


class StructureEngine:
    """Motore di struttura per un set di pivot (swing oppure internal).

    Replica la logica dell'indicatore: un pivot high/low confermato resta
    'attivo' finche' una chiusura non lo attraversa; la rottura e' BOS se
    conferma il trend, CHoCH se lo inverte.
    """

    def __init__(self, length: int):
        self.length = length
        self.high_lvl = 0.0
        self.low_lvl = 0.0
        self.high_crossed = True
        self.low_crossed = True
        self.high_idx = -1
        self.low_idx = -1
        self.trend = 0

    def update(self, high: np.ndarray, low: np.ndarray, close: np.ndarray,
               i: int) -> StructureBreak | None:
        """Elabora la barra chiusa di indice ``i`` (cronologico)."""
        p = i - self.length
        if p >= 0:
            if is_pivot_high(high, p, self.length):
                self.high_lvl = float(high[p])
                self.high_crossed = False
                self.high_idx = p
            if is_pivot_low(low, p, self.length):
                self.low_lvl = float(low[p])
                self.low_crossed = False
                self.low_idx = p

        if i < 1:
            return None

        if (self.high_lvl > 0 and not self.high_crossed
                and close[i] > self.high_lvl and close[i - 1] <= self.high_lvl):
            was_choch = self.trend == -1
            self.high_crossed = True
            self.trend = +1
            return StructureBreak(+1, was_choch, self.high_idx, i)

        if (self.low_lvl > 0 and not self.low_crossed
                and close[i] < self.low_lvl and close[i - 1] >= self.low_lvl):
            was_choch = self.trend == +1
            self.low_crossed = True
            self.trend = -1
            return StructureBreak(-1, was_choch, self.low_idx, i)

        return None


class PremiumDiscountTracker:
    """Range trailing tra swing high/low per il filtro premium/discount."""

    def __init__(self):
        self.top = 0.0
        self.bottom = 0.0

    def on_swing_break(self, swing: StructureEngine):
        if swing.high_lvl > 0:
            self.top = swing.high_lvl
        if swing.low_lvl > 0:
            self.bottom = swing.low_lvl

    def on_bar(self, high: float, low: float):
        if self.top > 0 and high > self.top:
            self.top = high
        if self.bottom > 0 and low < self.bottom:
            self.bottom = low

    @property
    def valid(self) -> bool:
        return self.top > self.bottom > 0

    def equilibrium(self) -> float:
        return (self.top + self.bottom) / 2.0

    def in_discount(self, price: float) -> bool:
        return self.valid and price < self.equilibrium()

    def in_premium(self, price: float) -> bool:
        return self.valid and price > self.equilibrium()

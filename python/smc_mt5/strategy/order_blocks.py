"""Order Blocks: creazione sui break di struttura interna, mitigazione, retest."""

from __future__ import annotations

import dataclasses

import numpy as np


@dataclasses.dataclass
class OrderBlock:
    top: float
    bottom: float
    bias: int              # +1 bullish, -1 bearish
    created_idx: int
    active: bool = True


class OrderBlockBook:
    def __init__(self, max_per_side: int = 10, max_age_bars: int = 300):
        self.max_per_side = max_per_side
        self.max_age_bars = max_age_bars
        self.blocks: list[OrderBlock] = []

    def add_from_break(self, high: np.ndarray, low: np.ndarray,
                       pivot_idx: int, break_idx: int, bias: int):
        """OB = barra con l'estremo opposto del leg tra pivot e rottura."""
        if pivot_idx < 0 or pivot_idx >= break_idx:
            return
        seg = slice(pivot_idx, break_idx + 1)
        if bias == +1:
            best = pivot_idx + int(np.argmin(low[seg]))
        else:
            best = pivot_idx + int(np.argmax(high[seg]))
        ob = OrderBlock(top=float(high[best]), bottom=float(low[best]),
                        bias=bias, created_idx=best)
        same = [b for b in self.blocks if b.active and b.bias == bias]
        if len(same) >= self.max_per_side:
            oldest = min(same, key=lambda b: b.created_idx)
            oldest.active = False
        self.blocks.append(ob)
        self.blocks = [b for b in self.blocks if b.active]

    def mitigate(self, high: float, low: float, i: int):
        """Modalita' high/low: l'OB muore se attraversato dal lato opposto."""
        for b in self.blocks:
            if not b.active:
                continue
            if i - b.created_idx > self.max_age_bars:
                b.active = False
            elif b.bias == +1 and low < b.bottom:
                b.active = False
            elif b.bias == -1 and high > b.top:
                b.active = False

    def check_retest(self, high: float, low: float, close: float,
                     i: int, bias: int) -> OrderBlock | None:
        """Wick dentro la zona, chiusura oltre il bordo (retest confermato)."""
        for b in self.blocks:
            if not b.active or b.bias != bias or b.created_idx >= i:
                continue
            if bias == +1:
                if b.bottom <= low <= b.top and close > b.top:
                    return b
            else:
                if b.bottom <= high <= b.top and close < b.bottom:
                    return b
        return None

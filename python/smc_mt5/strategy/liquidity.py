"""Liquidity Delta Profiler: zone BSL/SSL, delta per quadrante, sweep e reversal.

Replica le regole dell'indicatore LDP:
  ABS - absorption all'estremo (sweep con delta esterno contrario, ratio > 0.2)
  EXH - exhaustion / dry sweep (ratio < 0.1)
  DIV - delta divergence / FOMO intrappolato (chiude dentro, ratio > 0.6)
  REJ - snapback rejection (sweep + chiusura di rifiuto + delta barra contrario)
"""

from __future__ import annotations

import dataclasses

import numpy as np

from .indicators import is_pivot_high, is_pivot_low


@dataclasses.dataclass
class LiquidityZone:
    top: float
    bottom: float
    is_bsl: bool                       # True = buy-side (sopra pivot high)
    created_idx: int
    deltas: list = dataclasses.field(default_factory=lambda: [0.0] * 4)
    vol_traded: float = 0.0
    swept: bool = False
    signaled: bool = False
    active: bool = True


@dataclasses.dataclass
class ReversalSignal:
    tag: str               # ABS | EXH | DIV | REJ
    direction: int         # +1 long (sweep SSL), -1 short (sweep BSL)
    sl_price: float        # oltre l'estremo dello sweep (buffer escluso)
    zone: LiquidityZone


class LiquidityEngine:
    def __init__(self, length: int = 15, max_zones: int = 10,
                 enabled_signals: tuple = ("ABS", "EXH", "DIV", "REJ")):
        self.length = length
        self.max_zones = max_zones
        self.enabled = set(enabled_signals)
        self.zones: list[LiquidityZone] = []

    # ----------------------------------------------------------------- create
    def _add_zone(self, top: float, bottom: float, is_bsl: bool, idx: int):
        for z in self.zones:
            if not z.active or z.is_bsl != is_bsl:
                continue
            if max(bottom, z.bottom) <= min(top, z.top):   # overlap -> scarta
                return
        same = [z for z in self.zones if z.active and z.is_bsl == is_bsl]
        if len(same) >= self.max_zones:
            oldest = min(same, key=lambda z: z.created_idx)
            oldest.active = False
        self.zones.append(LiquidityZone(top, bottom, is_bsl, idx))
        self.zones = [z for z in self.zones if z.active]

    def create_zones(self, o: np.ndarray, h: np.ndarray, l: np.ndarray,
                     c: np.ndarray, atr: np.ndarray, i: int):
        p = i - self.length
        if p < 0 or np.isnan(atr[p]) or atr[p] <= 0:
            return
        if is_pivot_high(h, p, self.length):
            top = float(h[p])
            bot = float(max(o[p], c[p]))
            if top - bot < atr[p] * 0.1:
                bot = top - atr[p] * 0.1
            self._add_zone(top, bot, True, p)
        if is_pivot_low(l, p, self.length):
            bot = float(l[p])
            top = float(min(o[p], c[p]))
            if top - bot < atr[p] * 0.1:
                top = bot + atr[p] * 0.1
            self._add_zone(top, bot, False, p)

    # ---------------------------------------------------------------- process
    def _classify(self, z: LiquidityZone, bar_h: float, bar_l: float,
                  bar_c: float, bar_delta: float, bar_vol: float) -> str:
        abs_total = sum(abs(d) for d in z.deltas)
        if abs_total <= 0:
            return ""
        outer = z.deltas[3] if z.is_bsl else z.deltas[0]
        ratio = abs(outer) / (abs_total + 1e-4)

        sweeping = bar_h > z.top if z.is_bsl else bar_l < z.bottom
        closes_inside = z.bottom <= bar_c <= z.top
        mid = (z.top + z.bottom) / 2.0
        closes_rejecting = bar_c < mid if z.is_bsl else bar_c > mid

        if ("ABS" in self.enabled and sweeping and ratio > 0.2
                and ((z.is_bsl and outer < 0) or (not z.is_bsl and outer > 0))):
            return "ABS"
        if "EXH" in self.enabled and sweeping and ratio < 0.1:
            return "EXH"
        if ("DIV" in self.enabled and closes_inside and ratio > 0.6
                and ((z.is_bsl and outer > 0) or (not z.is_bsl and outer < 0))):
            return "DIV"
        if "REJ" in self.enabled and sweeping and closes_rejecting:
            bar_ratio = abs(bar_delta) / (bar_vol + 1e-4)
            if bar_ratio > 0.2 and ((z.is_bsl and bar_delta < 0)
                                    or (not z.is_bsl and bar_delta > 0)):
                return "REJ"
        return ""

    def process_bar(self, o: float, h: float, l: float, c: float,
                    v: float, i: int) -> ReversalSignal | None:
        rng = h - l
        bar_delta = 0.0 if rng <= 0 else v * (c - o) / rng
        signal: ReversalSignal | None = None

        for z in self.zones:
            if not z.active or z.swept or z.created_idx >= i:
                continue

            step = (z.top - z.bottom) / 4.0
            hit = False
            for q in range(4):
                q_bot = z.bottom + q * step
                q_top = q_bot + step
                ovl = min(h, q_top) - max(l, q_bot)
                if ovl > 0 and rng > 0:
                    hit = True
                    r = ovl / rng
                    z.deltas[q] += bar_delta * r
                    z.vol_traded += v * r

            sweep = h > z.top if z.is_bsl else l < z.bottom

            if (hit or sweep) and not z.signaled:
                tag = self._classify(z, h, l, c, bar_delta, v)
                if tag:
                    z.signaled = True
                    if z.is_bsl:
                        sig = ReversalSignal(tag, -1, max(h, z.top), z)
                    else:
                        sig = ReversalSignal(tag, +1, min(l, z.bottom), z)
                    if signal is None:
                        signal = sig

            if sweep:
                z.swept = True

        return signal

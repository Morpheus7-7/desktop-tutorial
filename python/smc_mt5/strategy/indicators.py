"""Indicatori di base (RSI e ATR di Wilder) e pivot classici."""

from __future__ import annotations

import numpy as np
import pandas as pd


def rsi_wilder(close: np.ndarray, period: int = 14) -> np.ndarray:
    """RSI con smoothing di Wilder (equivalente a iRSI di MT5)."""
    close = np.asarray(close, dtype=float)
    delta = np.diff(close, prepend=close[0])
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    alpha = 1.0 / period
    avg_gain = pd.Series(gain).ewm(alpha=alpha, adjust=False).mean().to_numpy(copy=True)
    avg_loss = pd.Series(loss).ewm(alpha=alpha, adjust=False).mean().to_numpy(copy=True)
    rs = np.divide(avg_gain, avg_loss, out=np.full_like(avg_gain, np.inf),
                   where=avg_loss != 0)
    out = 100.0 - 100.0 / (1.0 + rs)
    out[:period] = np.nan
    return out


def atr_wilder(high: np.ndarray, low: np.ndarray, close: np.ndarray,
               period: int = 14) -> np.ndarray:
    """ATR con smoothing di Wilder (equivalente a iATR di MT5)."""
    high = np.asarray(high, dtype=float)
    low = np.asarray(low, dtype=float)
    close = np.asarray(close, dtype=float)
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    tr = np.maximum(high - low,
                    np.maximum(np.abs(high - prev_close),
                               np.abs(low - prev_close)))
    out = pd.Series(tr).ewm(alpha=1.0 / period, adjust=False).mean().to_numpy(copy=True)
    out[:period] = np.nan
    return out


def is_pivot_high(high: np.ndarray, i: int, length: int) -> bool:
    """True se high[i] e' strettamente il massimo di length barre per lato."""
    if i - length < 0 or i + length >= len(high):
        return False
    cand = high[i]
    left = high[i - length:i]
    right = high[i + 1:i + length + 1]
    return bool((left < cand).all() and (right < cand).all())


def is_pivot_low(low: np.ndarray, i: int, length: int) -> bool:
    """True se low[i] e' strettamente il minimo di length barre per lato."""
    if i - length < 0 or i + length >= len(low):
        return False
    cand = low[i]
    left = low[i - length:i]
    right = low[i + 1:i + length + 1]
    return bool((left > cand).all() and (right > cand).all())

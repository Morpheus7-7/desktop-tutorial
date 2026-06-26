"""Test di base su indicatori e strategie."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.data.indicators import atr, bollinger, ema, macd, rsi
from src.strategies.bollinger import BollingerStrategy
from src.strategies.ma_crossover import MACrossoverStrategy
from src.strategies.macd import MACDStrategy
from src.strategies.rsi import RSIStrategy


def _make_df(n=300, trend=0.0, seed=1):
    rng = np.random.default_rng(seed)
    rets = rng.normal(trend, 0.001, n)
    close = 100 * np.exp(np.cumsum(rets))
    df = pd.DataFrame({
        "open": close,
        "high": close * 1.001,
        "low": close * 0.999,
        "close": close,
        "volume": rng.integers(100, 500, n).astype(float),
    })
    return df


def test_rsi_bounds():
    df = _make_df()
    r = rsi(df["close"], 14)
    assert r.between(0, 100).all()


def test_atr_positive():
    df = _make_df()
    a = atr(df, 14).dropna()
    assert (a >= 0).all()


def test_bollinger_order():
    df = _make_df()
    up, mid, low = bollinger(df["close"], 20, 2.0)
    valid = up.dropna()
    assert (up.dropna() >= mid.dropna()).all()
    assert (mid.dropna() >= low.dropna()).all()


@pytest.mark.parametrize("strategy", [
    RSIStrategy(period=14),
    MACDStrategy(),
    MACrossoverStrategy(fast=20, slow=50),
    BollingerStrategy(period=20),
])
def test_strategy_signal_shape(strategy):
    df = _make_df()
    sig = strategy.generate(df)
    assert sig.direction in (-1, 0, 1)
    assert 0.0 <= sig.confidence <= 1.0
    assert sig.name == strategy.name


def test_strategy_handles_short_history():
    df = _make_df(n=5)
    sig = RSIStrategy(period=14).generate(df)
    assert sig.direction == 0
    assert sig.confidence == 0.0

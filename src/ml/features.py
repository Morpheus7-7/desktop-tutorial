"""Feature engineering per il modello ML.

Trasforma le candele OHLCV in feature numeriche (indicatori, rendimenti,
volatilità) usate per prevedere la direzione della candela successiva.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..data.indicators import atr, bollinger, ema, macd, rsi

# Ordine canonico delle feature: deve restare identico fra training e inferenza.
FEATURE_COLUMNS = [
    "ret_1", "ret_3", "ret_5",
    "rsi_14",
    "macd_hist",
    "ema_fast_slow",
    "bb_pos",
    "atr_norm",
    "vol_change",
]


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Calcola il DataFrame delle feature (stesso indice temporale di df)."""
    close = df["close"]
    out = pd.DataFrame(index=df.index)

    out["ret_1"] = close.pct_change(1)
    out["ret_3"] = close.pct_change(3)
    out["ret_5"] = close.pct_change(5)
    out["rsi_14"] = rsi(close, 14) / 100.0
    _, _, hist = macd(close)
    out["macd_hist"] = hist
    ema_fast, ema_slow = ema(close, 12), ema(close, 26)
    out["ema_fast_slow"] = (ema_fast - ema_slow) / close
    upper, mid, lower = bollinger(close, 20, 2.0)
    width = (upper - lower).replace(0, np.nan)
    out["bb_pos"] = ((close - lower) / width).clip(0, 1)
    out["atr_norm"] = atr(df, 14) / close
    out["vol_change"] = df["volume"].pct_change(1).replace([np.inf, -np.inf], 0)

    return out[FEATURE_COLUMNS]


def make_training_set(
    df: pd.DataFrame, horizon: int = 1, threshold: float = 0.0
) -> tuple[pd.DataFrame, pd.Series]:
    """Crea (X, y) per il training.

    y = 1 se il prezzo dopo `horizon` candele sale oltre `threshold`, altrimenti 0.
    """
    features = build_features(df)
    future_ret = df["close"].shift(-horizon) / df["close"] - 1.0
    target = (future_ret > threshold).astype(int)

    data = features.copy()
    data["__target__"] = target
    data = data.replace([np.inf, -np.inf], np.nan).dropna()
    y = data.pop("__target__")
    return data, y


def latest_feature_row(df: pd.DataFrame) -> pd.DataFrame | None:
    """Restituisce l'ultima riga di feature valida (per l'inferenza live)."""
    features = build_features(df).replace([np.inf, -np.inf], np.nan).dropna()
    if features.empty:
        return None
    return features.iloc[[-1]]

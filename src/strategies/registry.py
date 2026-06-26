"""Costruisce le strategie abilitate a partire dalla configurazione."""
from __future__ import annotations

from ..config import Config
from .base import Strategy
from .bollinger import BollingerStrategy
from .ma_crossover import MACrossoverStrategy
from .macd import MACDStrategy
from .rsi import RSIStrategy

_REGISTRY: dict[str, type[Strategy]] = {
    "rsi": RSIStrategy,
    "macd": MACDStrategy,
    "ma_crossover": MACrossoverStrategy,
    "bollinger": BollingerStrategy,
}


def build_strategies(config: Config) -> list[Strategy]:
    """Istanzia solo le strategie con enabled: true nel config."""
    strategies: list[Strategy] = []
    cfg = config.get("strategies", default={}) or {}
    for key, params in cfg.items():
        if not isinstance(params, dict) or not params.get("enabled", False):
            continue
        cls = _REGISTRY.get(key)
        if cls is None:
            continue
        kwargs = {k: v for k, v in params.items() if k != "enabled"}
        strategies.append(cls(**kwargs))
    return strategies

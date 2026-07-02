"""Caricamento e validazione della configurazione YAML."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import yaml


@dataclasses.dataclass
class Mt5Config:
    terminal_path: str = ""
    login: int = 0
    password: str = ""
    server: str = ""


@dataclasses.dataclass
class TradingConfig:
    symbol: str = "EURUSD"
    timeframe: str = "M15"
    magic: int = 260704
    risk_percent: float = 1.0
    reward_risk: float = 2.0
    breakeven_at_1r: bool = True
    max_spread_points: int = 30
    max_trades_per_day: int = 3
    daily_loss_limit_percent: float = 3.0
    session_start_hour: int = 8
    entry_cutoff_hour: int = 19
    close_all_hour: int = 21
    close_all_minute: int = 30
    close_end_of_day: bool = True


@dataclasses.dataclass
class StrategyConfig:
    entry_model: str = "both"          # sweep | ob | both
    min_confluence: int = 2
    require_divergence: bool = False
    sl_buffer_atr: float = 0.20
    swing_length: int = 50
    internal_length: int = 5
    use_premium_discount: bool = True
    max_order_blocks: int = 10
    ob_max_age_bars: int = 300
    ldp_length: int = 15
    ldp_max_zones: int = 10
    signals: tuple = ("ABS", "EXH", "DIV", "REJ")
    rsi_period: int = 14
    div_lookback: int = 5
    div_valid_bars: int = 12
    atr_period: int = 14
    warmup_bars: int = 1000


@dataclasses.dataclass
class TradingViewConfig:
    enabled: bool = False
    mode: str = "confirm"              # off | confirm | trigger
    confirm_valid_bars: int = 3
    webhook_host: str = "0.0.0.0"
    webhook_port: int = 8642
    secret: str = ""


@dataclasses.dataclass
class AppConfig:
    mt5: Mt5Config
    trading: TradingConfig
    strategy: StrategyConfig
    tradingview: TradingViewConfig


def _build(cls, data: dict):
    fields = {f.name for f in dataclasses.fields(cls)}
    kwargs = {k: v for k, v in (data or {}).items() if k in fields}
    if "signals" in kwargs and isinstance(kwargs["signals"], list):
        kwargs["signals"] = tuple(kwargs["signals"])
    return cls(**kwargs)


def load_config(path: str | Path = "config.yaml") -> AppConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    cfg = AppConfig(
        mt5=_build(Mt5Config, raw.get("mt5")),
        trading=_build(TradingConfig, raw.get("trading")),
        strategy=_build(StrategyConfig, raw.get("strategy")),
        tradingview=_build(TradingViewConfig, raw.get("tradingview")),
    )
    if cfg.tradingview.enabled and not cfg.tradingview.secret:
        raise ValueError("tradingview.secret obbligatorio quando il webhook e' attivo")
    if cfg.trading.risk_percent <= 0 or cfg.trading.risk_percent > 5:
        raise ValueError("trading.risk_percent fuori dal range prudente (0-5]")
    return cfg

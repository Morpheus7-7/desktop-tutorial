"""Segnali tecnici aggregati da TradingView (opzionale).

Usa la libreria `tradingview-ta` che interroga le raccomandazioni pubbliche di
TradingView (BUY/SELL/NEUTRAL su decine di indicatori). NON è un feed di prezzi
real-time: serve solo come segnale aggiuntivo/di conferma.
"""
from __future__ import annotations

from ..logging_setup import get_logger
from ..types import Signal

log = get_logger("data.tradingview")


def get_tradingview_signal(symbol: str, exchange: str = "FX_IDC", interval: str = "15m") -> Signal:
    """Restituisce un Signal dalla raccomandazione aggregata di TradingView."""
    try:
        from tradingview_ta import Interval, TA_Handler  # type: ignore
    except ImportError:
        log.warning("tradingview-ta non installato: segnale TradingView ignorato.")
        return Signal(name="tradingview", direction=0, confidence=0.0)

    interval_map = {
        "1m": Interval.INTERVAL_1_MINUTE,
        "5m": Interval.INTERVAL_5_MINUTES,
        "15m": Interval.INTERVAL_15_MINUTES,
        "1h": Interval.INTERVAL_1_HOUR,
        "4h": Interval.INTERVAL_4_HOURS,
        "1d": Interval.INTERVAL_1_DAY,
    }
    try:
        handler = TA_Handler(
            symbol=symbol,
            screener="forex",
            exchange=exchange,
            interval=interval_map.get(interval, Interval.INTERVAL_15_MINUTES),
        )
        analysis = handler.get_analysis()
        rec = analysis.summary["RECOMMENDATION"]  # STRONG_BUY..STRONG_SELL
        scores = {
            "STRONG_BUY": (1, 0.9),
            "BUY": (1, 0.6),
            "NEUTRAL": (0, 0.0),
            "SELL": (-1, 0.6),
            "STRONG_SELL": (-1, 0.9),
        }
        direction, conf = scores.get(rec, (0, 0.0))
        return Signal(name="tradingview", direction=direction, confidence=conf,
                      meta={"recommendation": rec})
    except Exception as exc:  # rete, simbolo errato, ecc.
        log.warning("TradingView non disponibile per %s: %s", symbol, exc)
        return Signal(name="tradingview", direction=0, confidence=0.0)

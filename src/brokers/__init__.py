"""Broker: astrazione per dati di mercato ed esecuzione ordini."""
from __future__ import annotations

from ..config import Config
from .base import Broker
from .paper_broker import PaperBroker


def build_broker(config: Config) -> Broker:
    """Factory: crea il broker giusto in base alla modalità configurata."""
    mode = config.mode
    if mode == "paper":
        return PaperBroker(config)

    # demo / live -> MT5 (import ritardato: la libreria esiste solo su Windows)
    from .mt5_broker import MT5Broker
    return MT5Broker(config)

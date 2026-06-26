"""Interfaccia astratta del broker.

Qualsiasi fonte dati/esecuzione (MT5, simulatore, altri broker) implementa
questa interfaccia, così il resto del sistema non dipende da MetaTrader 5.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from ..types import Account, OrderResult, Position, Side


class Broker(ABC):
    @abstractmethod
    def connect(self) -> bool:
        """Apre la connessione. Restituisce True se ok."""

    @abstractmethod
    def shutdown(self) -> None:
        """Chiude la connessione."""

    @abstractmethod
    def get_bars(self, symbol: str, timeframe: str, count: int) -> pd.DataFrame:
        """Restituisce un DataFrame OHLCV indicizzato per tempo.

        Colonne attese: open, high, low, close, volume.
        """

    @abstractmethod
    def get_tick(self, symbol: str) -> dict:
        """Ultimo prezzo: {'bid': float, 'ask': float, 'time': ...}."""

    @abstractmethod
    def get_account(self) -> Account:
        ...

    @abstractmethod
    def get_positions(self, symbol: str | None = None) -> list[Position]:
        ...

    @abstractmethod
    def place_order(
        self,
        symbol: str,
        side: Side,
        volume: float,
        sl: float = 0.0,
        tp: float = 0.0,
        comment: str = "",
    ) -> OrderResult:
        ...

    @abstractmethod
    def close_position(self, ticket: int) -> OrderResult:
        ...

    def symbol_info(self, symbol: str) -> dict:
        """Metadati simbolo (point, digits, volume step...). Override se serve."""
        return {"point": 0.0001, "digits": 5, "volume_step": 0.01}

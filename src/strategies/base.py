"""Interfaccia comune delle strategie."""
from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from ..types import Signal


class Strategy(ABC):
    """Una strategia riceve le candele e produce un Signal.

    weight: peso relativo della strategia nel voto aggregato.
    """
    name: str = "base"

    def __init__(self, weight: float = 1.0, **params):
        self.weight = float(weight)
        self.params = params

    @abstractmethod
    def generate(self, df: pd.DataFrame) -> Signal:
        """Calcola il segnale sull'ultima candela disponibile."""

    def _need(self, df: pd.DataFrame, min_rows: int) -> bool:
        return df is not None and len(df) >= min_rows

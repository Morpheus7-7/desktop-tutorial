"""Strutture dati condivise tra i moduli."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"

    @property
    def sign(self) -> int:
        return 1 if self is Side.BUY else -1


@dataclass
class Signal:
    """Segnale prodotto da una strategia o da un modello.

    direction:  -1 (short) | 0 (neutro) | +1 (long)
    confidence: 0.0 .. 1.0
    """
    name: str
    direction: int
    confidence: float = 0.0
    meta: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.direction = max(-1, min(1, int(self.direction)))
        self.confidence = max(0.0, min(1.0, float(self.confidence)))


@dataclass
class Decision:
    """Esito del motore decisionale per un simbolo."""
    symbol: str
    side: Side | None          # None = nessuna operazione
    score: float               # punteggio combinato in [-1, 1]
    confidence: float          # 0 .. 1
    signals: list[Signal] = field(default_factory=list)
    reason: str = ""

    @property
    def is_actionable(self) -> bool:
        return self.side is not None


@dataclass
class Position:
    """Posizione aperta sul broker."""
    ticket: int
    symbol: str
    side: Side
    volume: float
    entry_price: float
    sl: float = 0.0
    tp: float = 0.0
    profit: float = 0.0


@dataclass
class Account:
    """Stato del conto."""
    balance: float
    equity: float
    margin_free: float
    currency: str = "USD"
    is_demo: bool = True
    leverage: int = 100


@dataclass
class OrderResult:
    """Risultato di un tentativo di ordine."""
    ok: bool
    ticket: int | None = None
    message: str = ""
    raw: Any = None

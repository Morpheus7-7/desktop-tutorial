"""Motore delle strategie classiche."""
from __future__ import annotations

from .base import Strategy
from .registry import build_strategies

__all__ = ["Strategy", "build_strategies"]

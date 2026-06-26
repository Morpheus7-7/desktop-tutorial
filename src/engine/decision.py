"""Motore decisionale: aggrega strategie + ML in una decisione.

Punteggio combinato in [-1, 1]:
  score = (Σ peso_i * direzione_i * confidenza_i)  normalizzato
          + peso_ml * (proba_up - 0.5) * 2
Sopra la soglia di ingresso si propone BUY/SELL; il veto del LLM è applicato
a parte nell'orchestratore.
"""
from __future__ import annotations

import pandas as pd

from ..config import Config
from ..ml.model import DirectionModel
from ..strategies.base import Strategy
from ..types import Decision, Side, Signal


class DecisionEngine:
    def __init__(self, config: Config, strategies: list[Strategy], model: DirectionModel | None):
        self.config = config
        self.strategies = strategies
        self.model = model
        self.ml_weight = float(config.get("ml", "weight", default=1.5))
        self.ml_min_proba = float(config.get("ml", "min_proba", default=0.55))
        self.ml_enabled = bool(config.get("ml", "enabled", default=True))
        self.entry_threshold = float(config.get("decision", "entry_threshold", default=0.4))
        self.min_confidence = float(config.get("decision", "min_confidence", default=0.4))

    # ------------------------------------------------------------------ #
    def decide(self, symbol: str, df: pd.DataFrame) -> tuple[Decision, float]:
        """Restituisce (Decision, proba_up_ml)."""
        signals: list[Signal] = [s.generate(df) for s in self.strategies]

        # contributo strategie (media pesata)
        total_weight = sum(s.weight for s in self.strategies) or 1.0
        strat_score = sum(
            s.weight * sig.direction * sig.confidence
            for s, sig in zip(self.strategies, signals)
        ) / total_weight

        # contributo ML
        proba_up = 0.5
        ml_score = 0.0
        if self.ml_enabled and self.model is not None:
            proba_up = self.model.predict_proba_up(df)
            if abs(proba_up - 0.5) * 2 >= (self.ml_min_proba - 0.5) * 2:
                ml_score = (proba_up - 0.5) * 2  # in [-1, 1]

        # punteggio combinato normalizzato sui pesi effettivi
        denom = 1.0 + (self.ml_weight if self.ml_enabled else 0.0)
        score = (strat_score + self.ml_weight * ml_score) / denom
        score = max(-1.0, min(1.0, score))
        confidence = abs(score)

        side: Side | None = None
        reason = "sotto soglia"
        if confidence >= self.min_confidence and abs(score) >= self.entry_threshold:
            side = Side.BUY if score > 0 else Side.SELL
            reason = f"score={score:+.2f} strat={strat_score:+.2f} ml={ml_score:+.2f}"

        decision = Decision(
            symbol=symbol,
            side=side,
            score=score,
            confidence=confidence,
            signals=signals,
            reason=reason,
        )
        return decision, proba_up

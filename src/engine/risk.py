"""Gestione del rischio: position sizing, SL/TP e limiti operativi."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from ..config import Config
from ..data.indicators import atr
from ..logging_setup import get_logger
from ..types import Account, Decision, Position, Side

log = get_logger("engine.risk")


@dataclass
class RiskDecision:
    """Esito del controllo di rischio su una decisione."""
    allowed: bool
    volume: float = 0.0
    sl: float = 0.0
    tp: float = 0.0
    reason: str = ""


class RiskManager:
    def __init__(self, config: Config):
        r = config.get("risk", default={}) or {}
        self.risk_per_trade = float(r.get("risk_per_trade", 0.01))
        self.max_open_positions = int(r.get("max_open_positions", 4))
        self.max_per_symbol = int(r.get("max_positions_per_symbol", 1))
        self.max_daily_loss = float(r.get("max_daily_loss", 0.05))
        self.atr_period = int(r.get("atr_period", 14))
        self.sl_atr_mult = float(r.get("sl_atr_mult", 2.0))
        self.tp_rr = float(r.get("tp_rr", 1.5))
        self.min_volume = float(r.get("min_volume", 0.01))
        self.max_volume = float(r.get("max_volume", 2.0))
        self._day_start_equity: float | None = None

    # ------------------------------------------------------------------ #
    def daily_loss_breached(self, account: Account) -> bool:
        if self._day_start_equity is None:
            self._day_start_equity = account.equity
        loss = (self._day_start_equity - account.equity) / self._day_start_equity
        return loss >= self.max_daily_loss

    def reset_day(self, account: Account) -> None:
        self._day_start_equity = account.equity

    # ------------------------------------------------------------------ #
    def evaluate(
        self,
        decision: Decision,
        df: pd.DataFrame,
        account: Account,
        price: float,
        all_positions: list[Position],
        symbol_info: dict,
    ) -> RiskDecision:
        if not decision.is_actionable or decision.side is None:
            return RiskDecision(False, reason="nessuna azione")

        if self.daily_loss_breached(account):
            return RiskDecision(False, reason="stop loss giornaliero raggiunto")

        if len(all_positions) >= self.max_open_positions:
            return RiskDecision(False, reason="max posizioni aperte raggiunto")

        on_symbol = [p for p in all_positions if p.symbol == decision.symbol]
        if len(on_symbol) >= self.max_per_symbol:
            return RiskDecision(False, reason="max posizioni per simbolo raggiunto")

        # distanza dello stop in base all'ATR
        atr_series = atr(df, self.atr_period)
        atr_value = float(atr_series.iloc[-1]) if not atr_series.empty else 0.0
        if atr_value <= 0:
            return RiskDecision(False, reason="ATR non valido")

        sl_distance = self.sl_atr_mult * atr_value
        if decision.side is Side.BUY:
            sl = price - sl_distance
            tp = price + self.tp_rr * sl_distance
        else:
            sl = price + sl_distance
            tp = price - self.tp_rr * sl_distance

        volume = self._position_size(account, price, sl_distance, symbol_info)
        if volume < self.min_volume:
            return RiskDecision(False, reason="volume calcolato sotto il minimo")

        digits = int(symbol_info.get("digits", 5))
        return RiskDecision(
            allowed=True,
            volume=round(volume, 2),
            sl=round(sl, digits),
            tp=round(tp, digits),
            reason="ok",
        )

    # ------------------------------------------------------------------ #
    def _position_size(self, account: Account, price: float, sl_distance: float,
                       symbol_info: dict) -> float:
        """Calcola i lotti rischiando risk_per_trade dell'equity sullo stop.

        Perdita per 1 lotto allo stop ≈ sl_distance * contract_size (in valuta quota).
        """
        risk_amount = account.equity * self.risk_per_trade
        contract_size = float(symbol_info.get("trade_contract_size", 100_000))
        loss_per_lot = sl_distance * contract_size
        if loss_per_lot <= 0:
            return 0.0
        volume = risk_amount / loss_per_lot

        step = float(symbol_info.get("volume_step", 0.01))
        volume = max(self.min_volume, min(self.max_volume, volume))
        if step > 0:
            volume = round(volume / step) * step
        return volume

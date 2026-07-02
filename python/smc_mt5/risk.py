"""Risk management: sizing, limiti giornalieri, sessione, breakeven."""

from __future__ import annotations

import logging
import math
from datetime import datetime

from .config import TradingConfig
from .mt5_client import Mt5Client

log = logging.getLogger(__name__)


class RiskManager:
    def __init__(self, cfg: TradingConfig, client: Mt5Client):
        self.cfg = cfg
        self.client = client
        self._halted_day = None

    # ------------------------------------------------------------------ sizing
    def calc_lots(self, sl_distance: float) -> float:
        if sl_distance <= 0:
            return 0.0
        specs = self.client.symbol_specs(self.cfg.symbol)
        if specs["tick_value"] <= 0 or specs["tick_size"] <= 0:
            return 0.0
        risk_money = self.client.balance() * self.cfg.risk_percent / 100.0
        loss_per_lot = sl_distance / specs["tick_size"] * specs["tick_value"]
        if loss_per_lot <= 0:
            return 0.0
        lots = risk_money / loss_per_lot
        step = specs["vol_step"] or 0.01
        lots = math.floor(lots / step) * step
        lots = max(specs["vol_min"], min(specs["vol_max"], lots))
        if specs["vol_min"] * loss_per_lot > risk_money * 1.5:
            log.warning("Anche il lotto minimo supera il rischio consentito: skip")
            return 0.0
        return round(lots, 2)

    # --------------------------------------------------------------- filtri
    @staticmethod
    def _day_start(now: datetime) -> datetime:
        return now.replace(hour=0, minute=0, second=0, microsecond=0)

    def in_entry_window(self, now: datetime) -> bool:
        return self.cfg.session_start_hour <= now.hour < self.cfg.entry_cutoff_hour

    def past_close_all(self, now: datetime) -> bool:
        if not self.cfg.close_end_of_day:
            return False
        return (now.hour, now.minute) >= (self.cfg.close_all_hour,
                                          self.cfg.close_all_minute)

    def spread_ok(self) -> bool:
        if self.cfg.max_spread_points <= 0:
            return True
        return self.client.spread_points(self.cfg.symbol) <= self.cfg.max_spread_points

    def trades_today(self, now: datetime) -> int:
        deals = self.client.deals_today(self.cfg.symbol, self.cfg.magic,
                                        self._day_start(now))
        return sum(1 for d in deals if d.entry == 0)   # DEAL_ENTRY_IN

    def daily_loss_hit(self, now: datetime) -> bool:
        if self.cfg.daily_loss_limit_percent <= 0:
            return False
        deals = self.client.deals_today(self.cfg.symbol, self.cfg.magic,
                                        self._day_start(now))
        pnl = sum(d.profit + d.commission + d.swap for d in deals)
        limit = self.client.balance() * self.cfg.daily_loss_limit_percent / 100.0
        return pnl <= -limit

    def can_open(self, now: datetime) -> tuple[bool, str]:
        day = now.date()
        if self._halted_day == day:
            return False, "trading sospeso per limite giornaliero"
        if self.daily_loss_hit(now):
            self._halted_day = day
            return False, "limite di perdita giornaliero raggiunto"
        if not self.in_entry_window(now):
            return False, "fuori finestra oraria"
        if not self.spread_ok():
            return False, "spread troppo alto"
        if self.trades_today(now) >= self.cfg.max_trades_per_day:
            return False, "max trade giornalieri raggiunti"
        return True, ""

    # ------------------------------------------------------------- gestione
    def manage_positions(self):
        """Breakeven a 1R sulle posizioni aperte."""
        if not self.cfg.breakeven_at_1r:
            return
        import MetaTrader5 as mt5
        specs = self.client.symbol_specs(self.cfg.symbol)
        tick = mt5.symbol_info_tick(self.cfg.symbol)
        for p in self.client.our_positions(self.cfg.symbol, self.cfg.magic):
            if p.type == mt5.POSITION_TYPE_BUY:
                risk = p.price_open - p.sl
                if risk > 0 and p.sl < p.price_open and tick.bid >= p.price_open + risk:
                    self.client.modify_sl(p, p.price_open + specs["point"])
                    log.info("Breakeven long #%s", p.ticket)
            else:
                risk = p.sl - p.price_open
                if risk > 0 and p.sl > p.price_open and tick.ask <= p.price_open - risk:
                    self.client.modify_sl(p, p.price_open - specs["point"])
                    log.info("Breakeven short #%s", p.ticket)

    def close_all(self, reason: str):
        for p in self.client.our_positions(self.cfg.symbol, self.cfg.magic):
            if self.client.close_position(p, reason):
                log.info("Posizione #%s chiusa: %s", p.ticket, reason)

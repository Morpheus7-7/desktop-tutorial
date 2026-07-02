"""Loop principale: Python pensa, TradingView conferma, MetaTrader esegue.

Uso:
    python -m smc_mt5.main --config config.yaml
"""

from __future__ import annotations

import argparse
import logging
import time

import pandas as pd

from .config import AppConfig, load_config
from .mt5_client import Mt5Client
from .risk import RiskManager
from .strategy import ConfluenceEngine, TradeSignal
from .strategy.indicators import atr_wilder
from .webhook import TradingViewWebhook, TvAlert

log = logging.getLogger("smc_mt5")

POLL_SECONDS = 2.0
BAR_SECONDS = {"M1": 60, "M5": 300, "M15": 900, "M30": 1800,
               "H1": 3600, "H4": 14400, "D1": 86400}


class TradingApp:
    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self.client = Mt5Client(cfg.mt5)
        self.risk = RiskManager(cfg.trading, self.client)
        self.engine = ConfluenceEngine(cfg.strategy)
        self.webhook: TradingViewWebhook | None = None
        self.tv_alerts: list[TvAlert] = []
        self.df: pd.DataFrame | None = None    # storico cumulativo barre chiuse

        if cfg.tradingview.enabled and cfg.tradingview.mode != "off":
            self.webhook = TradingViewWebhook(
                cfg.tradingview.webhook_host,
                cfg.tradingview.webhook_port,
                cfg.tradingview.secret,
            )

    # --------------------------------------------------------------- dataframe
    def _append_new_bars(self) -> bool:
        """Aggiunge le barre chiuse piu' recenti. True se ne e' arrivata almeno una."""
        recent = self.client.get_bars(self.cfg.trading.symbol,
                                      self.cfg.trading.timeframe, 10)
        last_time = self.df["time"].iloc[-1]
        new_rows = recent[recent["time"] > last_time]
        if new_rows.empty:
            return False
        self.df = pd.concat([self.df, new_rows], ignore_index=True)

        # trim periodico: mantiene la memoria limitata e ricostruisce lo stato
        cap = self.cfg.strategy.warmup_bars
        if len(self.df) > cap * 2:
            self.df = self.df.iloc[-cap:].reset_index(drop=True)
            self.engine = ConfluenceEngine(self.cfg.strategy)
            self.engine.process(self.df.iloc[:-len(new_rows)])
            log.info("Storico compattato a %s barre, stato ricostruito", cap)
        return True

    # ------------------------------------------------------------ tradingview
    def _collect_tv_alerts(self):
        if self.webhook is None:
            return
        for alert in self.webhook.drain():
            if alert.symbol and alert.symbol not in self.cfg.trading.symbol:
                continue
            self.tv_alerts.append(alert)
        horizon = (self.cfg.tradingview.confirm_valid_bars
                   * BAR_SECONDS[self.cfg.trading.timeframe])
        now = time.time()
        self.tv_alerts = [a for a in self.tv_alerts
                          if now - a.received_at <= horizon]

    def _tv_confirms(self, direction: int) -> bool:
        """In modalita' confirm serve un alert TV concorde recente."""
        if self.webhook is None or self.cfg.tradingview.mode != "confirm":
            return True
        return any(a.direction == direction for a in self.tv_alerts)

    def _tv_trigger_signal(self) -> TradeSignal | None:
        """In modalita' trigger un alert TV diventa un candidato di ingresso,
        che passa comunque da confluenza Python e risk management."""
        if self.webhook is None or self.cfg.tradingview.mode != "trigger":
            return None
        if not self.tv_alerts:
            return None
        alert = self.tv_alerts.pop(0)
        atr = atr_wilder(self.df["high"].to_numpy(), self.df["low"].to_numpy(),
                         self.df["close"].to_numpy(), self.cfg.strategy.atr_period)
        last = self.df.iloc[-1]
        buf = self.cfg.strategy.sl_buffer_atr * float(atr[-1])
        sl = (float(last["low"]) - buf if alert.direction == +1
              else float(last["high"]) + buf)
        i = len(self.df) - 1
        score = self.engine.confluence_score(alert.direction,
                                             float(last["close"]), i)
        if score < self.cfg.strategy.min_confluence:
            log.info("Alert TV scartato: confluenza %s < %s",
                     score, self.cfg.strategy.min_confluence)
            return None
        return TradeSignal(alert.direction, sl, f"TV-{alert.signal}",
                           score, last["time"])

    # ---------------------------------------------------------------- execute
    def _execute(self, sig: TradeSignal):
        import MetaTrader5 as mt5
        symbol = self.cfg.trading.symbol
        tick = mt5.symbol_info_tick(symbol)
        entry = tick.ask if sig.direction == +1 else tick.bid
        sl_dist = (entry - sig.sl_price) if sig.direction == +1 \
                  else (sig.sl_price - entry)
        if sl_dist <= 0:
            log.warning("SL non valido per il segnale %s: skip", sig.reason)
            return
        tp = entry + sig.direction * self.cfg.trading.reward_risk * sl_dist
        lots = self.risk.calc_lots(sl_dist)
        if lots <= 0:
            return
        self.client.market_order(symbol, sig.direction, lots, sig.sl_price,
                                 tp, self.cfg.trading.magic,
                                 f"{sig.reason} c{sig.score}")

    # ------------------------------------------------------------------- run
    def run(self):
        self.client.connect()
        if self.webhook is not None:
            self.webhook.start()

        symbol = self.cfg.trading.symbol
        tf = self.cfg.trading.timeframe

        # warm-up: ricostruisce lo stato dallo storico senza tradare
        self.df = self.client.get_bars(symbol, tf, self.cfg.strategy.warmup_bars)
        self.engine.process(self.df)
        log.info("Warm-up completato su %s barre (%s %s), trend swing: %s",
                 len(self.df), symbol, tf, self.engine.swing.trend)

        try:
            while True:
                time.sleep(POLL_SECONDS)
                self._collect_tv_alerts()
                now = self.client.server_time(symbol)

                if self.risk.past_close_all(now):
                    self.risk.close_all("fine giornata")
                    continue

                self.risk.manage_positions()

                if not self._append_new_bars():
                    continue

                # nuova barra chiusa: il cervello elabora
                signals = self.engine.process(self.df)
                sig = signals[-1] if signals else None
                if sig is None:
                    sig = self._tv_trigger_signal()
                if sig is None:
                    continue

                if self.client.our_positions(symbol, self.cfg.trading.magic):
                    continue
                ok, reason = self.risk.can_open(now)
                if not ok:
                    log.info("Segnale %s ignorato: %s", sig.reason, reason)
                    continue
                if not self._tv_confirms(sig.direction):
                    log.info("Segnale %s in attesa di conferma TradingView",
                             sig.reason)
                    continue
                self._execute(sig)
        finally:
            self.client.shutdown()


def main():
    parser = argparse.ArgumentParser(description="SMC-MT5 trading brain")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    cfg = load_config(args.config)
    TradingApp(cfg).run()


if __name__ == "__main__":
    main()

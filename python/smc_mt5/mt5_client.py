"""Client MetaTrader 5: connessione, dati, esecuzione ordini.

Richiede il terminale MT5 in esecuzione sulla stessa macchina (Windows,
oppure Linux via Wine) e il pacchetto ufficiale ``MetaTrader5``.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import pandas as pd

try:
    import MetaTrader5 as mt5
except ImportError:                      # permette import su macchine non-Windows
    mt5 = None

from .config import Mt5Config

log = logging.getLogger(__name__)

TIMEFRAMES = {}
if mt5 is not None:
    TIMEFRAMES = {
        "M1": mt5.TIMEFRAME_M1, "M5": mt5.TIMEFRAME_M5, "M15": mt5.TIMEFRAME_M15,
        "M30": mt5.TIMEFRAME_M30, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4,
        "D1": mt5.TIMEFRAME_D1,
    }


class Mt5Client:
    def __init__(self, cfg: Mt5Config):
        if mt5 is None:
            raise RuntimeError(
                "Pacchetto MetaTrader5 non disponibile: serve Windows "
                "(o Wine) con il terminale MT5 installato.")
        self.cfg = cfg

    # ------------------------------------------------------------ connessione
    def connect(self):
        kwargs = {}
        if self.cfg.terminal_path:
            kwargs["path"] = self.cfg.terminal_path
        if self.cfg.login:
            kwargs.update(login=self.cfg.login, password=self.cfg.password,
                          server=self.cfg.server)
        if not mt5.initialize(**kwargs):
            raise RuntimeError(f"mt5.initialize fallita: {mt5.last_error()}")
        info = mt5.account_info()
        if info is None:
            raise RuntimeError("Nessun account loggato nel terminale MT5")
        log.info("Connesso a MT5: account %s (%s), balance %.2f %s",
                 info.login, info.server, info.balance, info.currency)

    def shutdown(self):
        mt5.shutdown()

    # ------------------------------------------------------------------- dati
    def get_bars(self, symbol: str, timeframe: str, count: int) -> pd.DataFrame:
        """Barre CHIUSE piu' recenti (esclude la barra 0 in formazione)."""
        tf = TIMEFRAMES[timeframe]
        rates = mt5.copy_rates_from_pos(symbol, tf, 1, count)
        if rates is None or len(rates) == 0:
            raise RuntimeError(f"copy_rates fallita: {mt5.last_error()}")
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        return df

    def last_closed_bar_time(self, symbol: str, timeframe: str) -> pd.Timestamp:
        return self.get_bars(symbol, timeframe, 1)["time"].iloc[0]

    def server_time(self, symbol: str) -> datetime:
        tick = mt5.symbol_info_tick(symbol)
        return datetime.utcfromtimestamp(tick.time)

    # ---------------------------------------------------------------- account
    def balance(self) -> float:
        return float(mt5.account_info().balance)

    def spread_points(self, symbol: str) -> int:
        return int(mt5.symbol_info(symbol).spread)

    def symbol_specs(self, symbol: str) -> dict:
        si = mt5.symbol_info(symbol)
        return {
            "point": si.point, "digits": si.digits,
            "tick_value": si.trade_tick_value, "tick_size": si.trade_tick_size,
            "vol_min": si.volume_min, "vol_max": si.volume_max,
            "vol_step": si.volume_step,
        }

    # -------------------------------------------------------------- posizioni
    def our_positions(self, symbol: str, magic: int) -> list:
        positions = mt5.positions_get(symbol=symbol) or []
        return [p for p in positions if p.magic == magic]

    def deals_today(self, symbol: str, magic: int, day_start: datetime) -> list:
        deals = mt5.history_deals_get(day_start, datetime.now() + timedelta(hours=48)) or []
        return [d for d in deals if d.magic == magic and d.symbol == symbol]

    # --------------------------------------------------------------- esecuzione
    def market_order(self, symbol: str, direction: int, lots: float,
                     sl: float, tp: float, magic: int, comment: str) -> bool:
        tick = mt5.symbol_info_tick(symbol)
        price = tick.ask if direction == +1 else tick.bid
        digits = mt5.symbol_info(symbol).digits
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lots,
            "type": mt5.ORDER_TYPE_BUY if direction == +1 else mt5.ORDER_TYPE_SELL,
            "price": price,
            "sl": round(sl, digits),
            "tp": round(tp, digits),
            "deviation": 20,
            "magic": magic,
            "comment": comment[:31],
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result is None or result.retcode != mt5.TRADE_RETCODE_DONE:
            # ritenta con filling FOK (alcuni broker non accettano IOC)
            request["type_filling"] = mt5.ORDER_FILLING_FOK
            result = mt5.order_send(request)
        ok = result is not None and result.retcode == mt5.TRADE_RETCODE_DONE
        if ok:
            log.info("Ordine eseguito: %s %s %.2f lots @ %.5f SL %.5f TP %.5f (%s)",
                     "BUY" if direction == +1 else "SELL", symbol, lots,
                     price, sl, tp, comment)
        else:
            log.error("Ordine fallito: retcode=%s %s",
                      getattr(result, "retcode", None),
                      getattr(result, "comment", mt5.last_error()))
        return ok

    def modify_sl(self, position, new_sl: float) -> bool:
        request = {
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": position.symbol,
            "position": position.ticket,
            "sl": new_sl,
            "tp": position.tp,
        }
        result = mt5.order_send(request)
        return result is not None and result.retcode == mt5.TRADE_RETCODE_DONE

    def close_position(self, position, comment: str = "") -> bool:
        tick = mt5.symbol_info_tick(position.symbol)
        is_buy = position.type == mt5.POSITION_TYPE_BUY
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": position.symbol,
            "volume": position.volume,
            "type": mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY,
            "position": position.ticket,
            "price": tick.bid if is_buy else tick.ask,
            "deviation": 20,
            "magic": position.magic,
            "comment": comment[:31],
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        return result is not None and result.retcode == mt5.TRADE_RETCODE_DONE

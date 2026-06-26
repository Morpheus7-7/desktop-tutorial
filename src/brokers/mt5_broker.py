"""Broker MetaTrader 5.

Richiede il pacchetto `MetaTrader5` e il terminale MT5 installato (Windows,
oppure Linux/Mac tramite Wine). L'import è ritardato dentro connect() così il
resto del progetto resta importabile anche dove MT5 non è disponibile.
"""
from __future__ import annotations

from datetime import datetime

import pandas as pd

from ..config import Config
from ..logging_setup import get_logger
from ..types import Account, OrderResult, Position, Side
from .base import Broker

log = get_logger("broker.mt5")


# Mappa timeframe testuale -> costante MT5 (valorizzata in connect()).
_TF_NAMES = {
    "M1": "TIMEFRAME_M1",
    "M5": "TIMEFRAME_M5",
    "M15": "TIMEFRAME_M15",
    "M30": "TIMEFRAME_M30",
    "H1": "TIMEFRAME_H1",
    "H4": "TIMEFRAME_H4",
    "D1": "TIMEFRAME_D1",
}


class MT5Broker(Broker):
    def __init__(self, config: Config):
        self.config = config
        self._mt5 = None  # modulo MetaTrader5
        self._tf_map: dict[str, int] = {}

    # ------------------------------------------------------------------ #
    def connect(self) -> bool:
        try:
            import MetaTrader5 as mt5  # type: ignore
        except ImportError as exc:
            raise RuntimeError(
                "Pacchetto MetaTrader5 non installato. Su Windows: "
                "`pip install MetaTrader5`. Per sviluppo senza MT5 usa mode: paper."
            ) from exc

        self._mt5 = mt5
        self._tf_map = {k: getattr(mt5, v) for k, v in _TF_NAMES.items()}

        creds = self.config.credentials
        init_kwargs: dict = {}
        if creds.mt5_terminal_path:
            init_kwargs["path"] = creds.mt5_terminal_path
        if creds.mt5_login:
            init_kwargs.update(
                login=creds.mt5_login,
                password=creds.mt5_password,
                server=creds.mt5_server,
            )

        if not mt5.initialize(**init_kwargs):
            log.error("MT5 initialize fallita: %s", mt5.last_error())
            return False

        info = mt5.account_info()
        if info is None:
            log.error("Impossibile leggere account_info: %s", mt5.last_error())
            return False

        # --- guard di sicurezza: blocca il live non autorizzato ---
        is_demo = info.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO
        if not is_demo and not creds.allow_live_trading:
            mt5.shutdown()
            raise RuntimeError(
                "ATTENZIONE: account REALE rilevato ma ALLOW_LIVE_TRADING non è 'true'. "
                "Connessione interrotta per sicurezza. Usa un account demo oppure "
                "abilita esplicitamente il live nel .env."
            )

        # Assicura che i simboli configurati siano nel Market Watch
        for sym in self.config.symbols:
            if not mt5.symbol_select(sym, True):
                log.warning("Simbolo non selezionabile nel Market Watch: %s", sym)

        log.info(
            "Connesso a MT5 | account=%s | %s | server=%s",
            info.login,
            "DEMO" if is_demo else "REALE",
            info.server,
        )
        return True

    def shutdown(self) -> None:
        if self._mt5 is not None:
            self._mt5.shutdown()

    # ------------------------------------------------------------------ #
    def get_bars(self, symbol: str, timeframe: str, count: int) -> pd.DataFrame:
        tf = self._tf_map.get(timeframe.upper())
        if tf is None:
            raise ValueError(f"Timeframe non supportato: {timeframe}")
        rates = self._mt5.copy_rates_from_pos(symbol, tf, 0, count)
        if rates is None or len(rates) == 0:
            log.warning("Nessun dato per %s %s", symbol, timeframe)
            return pd.DataFrame()
        df = pd.DataFrame(rates)
        df["time"] = pd.to_datetime(df["time"], unit="s")
        df = df.set_index("time")
        df = df.rename(columns={"tick_volume": "volume"})
        return df[["open", "high", "low", "close", "volume"]]

    def get_tick(self, symbol: str) -> dict:
        tick = self._mt5.symbol_info_tick(symbol)
        if tick is None:
            return {}
        return {
            "bid": tick.bid,
            "ask": tick.ask,
            "time": datetime.fromtimestamp(tick.time),
        }

    def get_account(self) -> Account:
        info = self._mt5.account_info()
        is_demo = info.trade_mode == self._mt5.ACCOUNT_TRADE_MODE_DEMO
        return Account(
            balance=info.balance,
            equity=info.equity,
            margin_free=info.margin_free,
            currency=info.currency,
            is_demo=is_demo,
            leverage=info.leverage,
        )

    def get_positions(self, symbol: str | None = None) -> list[Position]:
        raw = self._mt5.positions_get(symbol=symbol) if symbol else self._mt5.positions_get()
        if raw is None:
            return []
        out: list[Position] = []
        for p in raw:
            side = Side.BUY if p.type == self._mt5.POSITION_TYPE_BUY else Side.SELL
            out.append(
                Position(
                    ticket=p.ticket,
                    symbol=p.symbol,
                    side=side,
                    volume=p.volume,
                    entry_price=p.price_open,
                    sl=p.sl,
                    tp=p.tp,
                    profit=p.profit,
                )
            )
        return out

    # ------------------------------------------------------------------ #
    def place_order(
        self,
        symbol: str,
        side: Side,
        volume: float,
        sl: float = 0.0,
        tp: float = 0.0,
        comment: str = "",
    ) -> OrderResult:
        mt5 = self._mt5
        tick = mt5.symbol_info_tick(symbol)
        if tick is None:
            return OrderResult(ok=False, message=f"Nessun tick per {symbol}")

        order_type = mt5.ORDER_TYPE_BUY if side is Side.BUY else mt5.ORDER_TYPE_SELL
        price = tick.ask if side is Side.BUY else tick.bid

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": float(volume),
            "type": order_type,
            "price": price,
            "sl": float(sl),
            "tp": float(tp),
            "deviation": 20,
            "magic": 770077,
            "comment": comment[:31],
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result is None:
            return OrderResult(ok=False, message=f"order_send None: {mt5.last_error()}")
        ok = result.retcode == mt5.TRADE_RETCODE_DONE
        return OrderResult(
            ok=ok,
            ticket=getattr(result, "order", None),
            message=f"retcode={result.retcode} {result.comment}",
            raw=result,
        )

    def close_position(self, ticket: int) -> OrderResult:
        mt5 = self._mt5
        positions = mt5.positions_get(ticket=ticket)
        if not positions:
            return OrderResult(ok=False, message=f"Posizione {ticket} non trovata")
        p = positions[0]
        tick = mt5.symbol_info_tick(p.symbol)
        if p.type == mt5.POSITION_TYPE_BUY:
            order_type = mt5.ORDER_TYPE_SELL
            price = tick.bid
        else:
            order_type = mt5.ORDER_TYPE_BUY
            price = tick.ask

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": p.symbol,
            "volume": p.volume,
            "type": order_type,
            "position": ticket,
            "price": price,
            "deviation": 20,
            "magic": 770077,
            "comment": "close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        ok = result is not None and result.retcode == mt5.TRADE_RETCODE_DONE
        return OrderResult(ok=ok, ticket=ticket, message=str(result.comment if result else mt5.last_error()))

    def symbol_info(self, symbol: str) -> dict:
        info = self._mt5.symbol_info(symbol)
        if info is None:
            return super().symbol_info(symbol)
        return {
            "point": info.point,
            "digits": info.digits,
            "volume_step": info.volume_step,
            "volume_min": info.volume_min,
            "volume_max": info.volume_max,
            "trade_contract_size": info.trade_contract_size,
        }

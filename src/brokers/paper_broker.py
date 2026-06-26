"""Broker simulato (paper trading / backtest).

Non si connette a nulla: serve a sviluppare e validare la pipeline senza
rischi e senza MetaTrader 5. I dati provengono da CSV (data/<symbol>.csv) o,
se assenti, da un random-walk sintetico così l'intero sistema è eseguibile
ovunque.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from ..config import Config
from ..logging_setup import get_logger
from ..types import Account, OrderResult, Position, Side

from .base import Broker

log = get_logger("broker.paper")

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"


def _synthetic_series(symbol: str, n: int = 3000, start: float = 100.0) -> pd.DataFrame:
    """Genera OHLCV plausibili con un random walk (seed deterministico per simbolo)."""
    rng = np.random.default_rng(abs(hash(symbol)) % (2**32))
    returns = rng.normal(0, 0.001, n)
    close = start * np.exp(np.cumsum(returns))
    high = close * (1 + np.abs(rng.normal(0, 0.0008, n)))
    low = close * (1 - np.abs(rng.normal(0, 0.0008, n)))
    open_ = np.concatenate([[close[0]], close[:-1]])
    volume = rng.integers(50, 500, n).astype(float)
    idx = pd.date_range(end=datetime.utcnow(), periods=n, freq="15min")
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


class PaperBroker(Broker):
    def __init__(self, config: Config, spread_pct: float = 0.00005):
        self.config = config
        self.spread_pct = spread_pct
        self._data: dict[str, pd.DataFrame] = {}
        self._cursor: dict[str, int] = {}
        self._positions: dict[int, Position] = {}
        self._next_ticket = 1
        self.starting_balance = 10_000.0
        self.balance = self.starting_balance

    # ------------------------------------------------------------------ #
    def connect(self) -> bool:
        for sym in self.config.symbols:
            csv = DATA_DIR / f"{sym}.csv"
            if csv.exists():
                df = pd.read_csv(csv, parse_dates=[0], index_col=0)
                df.columns = [c.lower() for c in df.columns]
                self._data[sym] = df
                log.info("Caricati %d bar da %s", len(df), csv.name)
            else:
                self._data[sym] = _synthetic_series(sym)
                log.info("Dati sintetici generati per %s (nessun CSV trovato)", sym)
            # parti con uno storico sufficiente per gli indicatori
            self._cursor[sym] = min(200, len(self._data[sym]) - 1)
        log.info("PaperBroker pronto | balance iniziale=%.2f", self.balance)
        return True

    def shutdown(self) -> None:
        pass

    def seek_end(self) -> None:
        """Porta il cursore all'ultima candela (per leggere tutto lo storico,
        es. in fase di training). Il backtest usa invece step()."""
        for sym, df in self._data.items():
            self._cursor[sym] = len(df) - 1

    # ------------------------------------------------------------------ #
    def get_bars(self, symbol: str, timeframe: str, count: int) -> pd.DataFrame:
        df = self._data.get(symbol)
        if df is None:
            return pd.DataFrame()
        end = self._cursor[symbol] + 1
        start = max(0, end - count)
        return df.iloc[start:end].copy()

    def get_tick(self, symbol: str) -> dict:
        price = self._price(symbol)
        half = price * self.spread_pct
        return {"bid": price - half, "ask": price + half, "time": self._time(symbol)}

    def _price(self, symbol: str) -> float:
        return float(self._data[symbol].iloc[self._cursor[symbol]]["close"])

    def _time(self, symbol: str):
        return self._data[symbol].index[self._cursor[symbol]]

    def get_account(self) -> Account:
        equity = self.balance + sum(self._unrealized(p) for p in self._positions.values())
        return Account(
            balance=self.balance,
            equity=equity,
            margin_free=equity,
            currency="USD",
            is_demo=True,
        )

    def get_positions(self, symbol: str | None = None) -> list[Position]:
        for p in self._positions.values():
            p.profit = self._unrealized(p)
        return [p for p in self._positions.values() if symbol is None or p.symbol == symbol]

    def _unrealized(self, p: Position) -> float:
        # P&L semplificato: (prezzo - ingresso) * direzione * lotti * contract_size.
        # Approssimazione valida per il paper trading (non considera la valuta del conto).
        price = self._price(p.symbol)
        contract_size = 100_000
        return (price - p.entry_price) * p.side.sign * p.volume * contract_size

    # ------------------------------------------------------------------ #
    def place_order(self, symbol, side, volume, sl=0.0, tp=0.0, comment="") -> OrderResult:
        tick = self.get_tick(symbol)
        price = tick["ask"] if side is Side.BUY else tick["bid"]
        ticket = self._next_ticket
        self._next_ticket += 1
        self._positions[ticket] = Position(
            ticket=ticket, symbol=symbol, side=side, volume=volume,
            entry_price=price, sl=sl, tp=tp,
        )
        log.info("[PAPER] APRE %s %s vol=%.2f @ %.5f sl=%.5f tp=%.5f",
                 side.value.upper(), symbol, volume, price, sl, tp)
        return OrderResult(ok=True, ticket=ticket, message="paper fill")

    def close_position(self, ticket: int) -> OrderResult:
        p = self._positions.pop(ticket, None)
        if p is None:
            return OrderResult(ok=False, message="ticket non trovato")
        pnl = self._unrealized(p)
        self.balance += pnl
        log.info("[PAPER] CHIUDE %s %s pnl=%.2f | balance=%.2f",
                 p.side.value.upper(), p.symbol, pnl, self.balance)
        return OrderResult(ok=True, ticket=ticket, message=f"pnl={pnl:.2f}")

    # ------------------------------------------------------------------ #
    def step(self) -> bool:
        """Avanza il tempo di una candela (per il backtest).

        Applica SL/TP alle posizioni aperte. Restituisce False quando i dati
        sono finiti.
        """
        advanced = False
        for sym, df in self._data.items():
            if self._cursor[sym] < len(df) - 1:
                self._cursor[sym] += 1
                advanced = True
        self._check_sl_tp()
        return advanced

    def _check_sl_tp(self) -> None:
        for ticket in list(self._positions):
            p = self._positions[ticket]
            bar = self._data[p.symbol].iloc[self._cursor[p.symbol]]
            hit = None
            if p.side is Side.BUY:
                if p.sl and bar["low"] <= p.sl:
                    hit = p.sl
                elif p.tp and bar["high"] >= p.tp:
                    hit = p.tp
            else:
                if p.sl and bar["high"] >= p.sl:
                    hit = p.sl
                elif p.tp and bar["low"] <= p.tp:
                    hit = p.tp
            if hit is not None:
                pnl = (hit - p.entry_price) * p.side.sign * p.volume * 100_000
                self.balance += pnl
                del self._positions[ticket]
                log.info("[PAPER] SL/TP %s @ %.5f pnl=%.2f | balance=%.2f",
                         p.symbol, hit, pnl, self.balance)

"""Backtest della strategia a confluenza su dati storici.

Con MT5 disponibile:
    python -m smc_mt5.backtest --config config.yaml --bars 20000

Con un CSV (colonne: time,open,high,low,close,tick_volume):
    python -m smc_mt5.backtest --config config.yaml --csv dati.csv

Simulazione semplice bar-by-bar: ingresso all'open della barra successiva
al segnale, SL/TP intra-bar (worst case: prima lo stop), breakeven a 1R,
un solo trade per volta. Costi modellati con uno spread fisso in punti.
"""

from __future__ import annotations

import argparse
import dataclasses
import logging

import numpy as np
import pandas as pd

from .config import load_config
from .strategy import ConfluenceEngine

log = logging.getLogger(__name__)


@dataclasses.dataclass
class Trade:
    direction: int
    entry: float
    sl: float
    tp: float
    entry_idx: int
    reason: str
    exit_price: float = 0.0
    exit_idx: int = -1
    r_multiple: float = 0.0


def run_backtest(df: pd.DataFrame, cfg, spread_points: float = 10,
                 point: float = 0.0001) -> list[Trade]:
    engine = ConfluenceEngine(cfg.strategy)

    o = df["open"].to_numpy(float)
    h = df["high"].to_numpy(float)
    l = df["low"].to_numpy(float)
    spread = spread_points * point

    # 1. genera tutti i segnali con il motore (stato incrementale)
    signals = engine.process(df)
    sig_by_idx = {}
    time_to_idx = {t: i for i, t in enumerate(df["time"])}
    for s in signals:
        idx = time_to_idx.get(s.bar_time)
        if idx is not None:
            sig_by_idx[idx] = s

    # 2. simulazione sequenziale
    trades: list[Trade] = []
    open_trade: Trade | None = None
    be_done = False

    for i in range(1, len(df) - 1):
        # gestione trade aperto sulla barra i
        if open_trade is not None:
            t = open_trade
            risk = abs(t.entry - t.sl)
            # breakeven a 1R
            if cfg.trading.breakeven_at_1r and not be_done and risk > 0:
                if t.direction == +1 and h[i] >= t.entry + risk:
                    t.sl = t.entry
                    be_done = True
                elif t.direction == -1 and l[i] <= t.entry - risk:
                    t.sl = t.entry
                    be_done = True
            # uscite (worst case: SL prima del TP nella stessa barra)
            hit_sl = l[i] <= t.sl if t.direction == +1 else h[i] >= t.sl
            hit_tp = h[i] >= t.tp if t.direction == +1 else l[i] <= t.tp
            if hit_sl:
                t.exit_price, t.exit_idx = t.sl, i
            elif hit_tp:
                t.exit_price, t.exit_idx = t.tp, i
            if t.exit_idx >= 0:
                # r_multiple riferito al rischio iniziale (TP = entry + RR*rischio)
                r0 = abs(t.tp - t.entry) / cfg.trading.reward_risk
                t.r_multiple = t.direction * (t.exit_price - t.entry) / r0 if r0 > 0 else 0
                trades.append(t)
                open_trade = None
                be_done = False

        # nuovo segnale sulla barra i -> ingresso all'open di i+1
        if open_trade is None and i in sig_by_idx:
            s = sig_by_idx[i]
            entry = o[i + 1] + (spread if s.direction == +1 else 0.0)
            sl = s.sl_price
            sl_dist = (entry - sl) if s.direction == +1 else (sl - entry)
            if sl_dist <= 0:
                continue
            tp = entry + s.direction * cfg.trading.reward_risk * sl_dist
            open_trade = Trade(s.direction, entry, sl, tp, i + 1, s.reason)
            be_done = False

    return trades


def print_stats(trades: list[Trade]):
    if not trades:
        print("Nessun trade generato.")
        return
    rs = np.array([t.r_multiple for t in trades])
    wins = rs[rs > 0]
    losses = rs[rs <= 0]
    gross_win = wins.sum()
    gross_loss = -losses.sum()
    pf = gross_win / gross_loss if gross_loss > 0 else float("inf")
    equity = np.cumsum(rs)
    peak = np.maximum.accumulate(equity)
    max_dd = float((peak - equity).max())

    print(f"\n===== RISULTATI BACKTEST =====")
    print(f"Trade totali:      {len(trades)}")
    print(f"Win rate:          {len(wins) / len(trades) * 100:.1f}%")
    print(f"Profit factor:     {pf:.2f}")
    print(f"Attesa media:      {rs.mean():+.2f} R")
    print(f"Totale:            {rs.sum():+.1f} R")
    print(f"Max drawdown:      {max_dd:.1f} R")
    print(f"NOTA: servono almeno 200 trade per significativita' statistica.")
    by_reason: dict[str, list[float]] = {}
    for t in trades:
        by_reason.setdefault(t.reason, []).append(t.r_multiple)
    print("\nPer tipo di segnale:")
    for reason, vals in sorted(by_reason.items()):
        arr = np.array(vals)
        wr = (arr > 0).mean() * 100
        print(f"  {reason:<12} n={len(arr):<5} win={wr:5.1f}%  tot={arr.sum():+7.1f} R")


def main():
    parser = argparse.ArgumentParser(description="Backtest SMC confluence")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--bars", type=int, default=20000)
    parser.add_argument("--csv", default="")
    parser.add_argument("--spread-points", type=float, default=10)
    parser.add_argument("--point", type=float, default=0.0001)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    cfg = load_config(args.config)

    if args.csv:
        df = pd.read_csv(args.csv, parse_dates=["time"])
    else:
        from .mt5_client import Mt5Client
        client = Mt5Client(cfg.mt5)
        client.connect()
        df = client.get_bars(cfg.trading.symbol, cfg.trading.timeframe, args.bars)
        client.shutdown()

    print(f"Backtest su {len(df)} barre "
          f"({df['time'].iloc[0]} -> {df['time'].iloc[-1]})")
    trades = run_backtest(df, cfg, args.spread_points, args.point)
    print_stats(trades)


if __name__ == "__main__":
    main()

"""Backtest della strategia sul PaperBroker.

Forza la modalità 'paper' e fa avanzare il simulatore candela per candela,
applicando l'intera pipeline (strategie + ML + rischio). Il supervisore LLM è
disattivato per default nel backtest (troppo lento candela per candela); puoi
riattivarlo con --use-llm.

Uso:
    python -m scripts.backtest --steps 1000
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.brokers.paper_broker import PaperBroker
from src.config import load_config
from src.engine import DecisionEngine, RiskManager
from src.logging_setup import setup_logging
from src.ml.model import DirectionModel
from src.strategies import build_strategies

log = setup_logging("INFO")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest su PaperBroker")
    parser.add_argument("--config", default=None)
    parser.add_argument("--steps", type=int, default=1000)
    args = parser.parse_args()

    config = load_config(args.config)
    config.raw["mode"] = "paper"  # forza la simulazione

    broker = PaperBroker(config)
    broker.connect()

    strategies = build_strategies(config)
    model = None
    if config.get("ml", "enabled", default=True):
        model = DirectionModel(config.get("ml", "model_path",
                                          default="models/xgb_direction.joblib"))
        model.load()
    engine = DecisionEngine(config, strategies, model)
    risk = RiskManager(config)
    risk.reset_day(broker.get_account())

    start_equity = broker.get_account().equity
    trades = 0

    for _ in range(args.steps):
        if not broker.step():
            break
        account = broker.get_account()
        positions = broker.get_positions()
        for symbol in config.symbols:
            df = broker.get_bars(symbol, config.timeframe, config.get("bars_history", default=500))
            if df is None or len(df) < 60:
                continue
            decision, _ = engine.decide(symbol, df)
            if not decision.is_actionable:
                continue
            tick = broker.get_tick(symbol)
            price = tick["ask"] if decision.side.value == "buy" else tick["bid"]
            rd = risk.evaluate(decision, df, account, price, positions,
                               broker.symbol_info(symbol))
            if rd.allowed:
                res = broker.place_order(symbol, decision.side, rd.volume, rd.sl, rd.tp)
                if res.ok:
                    trades += 1
                    positions = broker.get_positions()

    final = broker.get_account()
    ret = (final.equity - start_equity) / start_equity * 100
    log.info("=" * 50)
    log.info("BACKTEST | trade aperti=%d", trades)
    log.info("Equity iniziale=%.2f  finale=%.2f  rendimento=%.2f%%",
             start_equity, final.equity, ret)
    log.info("Balance finale (chiusi)=%.2f", final.balance)


if __name__ == "__main__":
    main()

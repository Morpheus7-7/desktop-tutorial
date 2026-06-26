"""Allena il modello ML di direzione.

Sorgente dati:
  - CSV in data/<symbol>.csv  (colonne: time,open,high,low,close,volume), oppure
  - dati scaricati da MT5 se la modalità non è 'paper', oppure
  - dati sintetici di fallback (solo per testare la pipeline).

Uso:
    python -m scripts.train_model --symbols EURUSD GBPUSD --bars 5000
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.brokers import build_broker
from src.config import load_config
from src.logging_setup import setup_logging
from src.ml.features import make_training_set
from src.ml.model import DirectionModel

log = setup_logging("INFO")


def main() -> None:
    parser = argparse.ArgumentParser(description="Training modello ML di direzione")
    parser.add_argument("--config", default=None)
    parser.add_argument("--symbols", nargs="*", default=None,
                        help="override dei simboli del config")
    parser.add_argument("--bars", type=int, default=5000)
    parser.add_argument("--horizon", type=int, default=1,
                        help="candele in avanti per definire il target")
    parser.add_argument("--paper", action="store_true",
                        help="usa dati locali/sintetici (PaperBroker) invece di MT5")
    args = parser.parse_args()

    config = load_config(args.config)
    if args.paper:
        config.raw["mode"] = "paper"
    symbols = args.symbols or config.symbols
    model_path = config.get("ml", "model_path", default="models/xgb_direction.joblib")

    broker = build_broker(config)
    if not broker.connect():
        raise SystemExit("Connessione al broker fallita.")
    # in paper mode leggi tutto lo storico disponibile, non solo fino al cursore
    if hasattr(broker, "seek_end"):
        broker.seek_end()

    frames: list[pd.DataFrame] = []
    for sym in symbols:
        df = broker.get_bars(sym, config.timeframe, args.bars)
        if df is None or df.empty:
            log.warning("Nessun dato per %s, salto.", sym)
            continue
        X, y = make_training_set(df, horizon=args.horizon)
        if not X.empty:
            X = X.copy()
            X["__y__"] = y.values
            frames.append(X)
            log.info("%s: %d campioni di training", sym, len(X))
    broker.shutdown()

    if not frames:
        raise SystemExit("Nessun dato di training disponibile.")

    data = pd.concat(frames, ignore_index=True)
    y_all = data.pop("__y__")
    metrics = DirectionModel.train(data, y_all, model_path)
    log.info("Training completato. Metriche: %s", metrics)


if __name__ == "__main__":
    main()

"""Avvia il trading bot in tempo reale.

Uso:
    python -m scripts.run_live                 # usa config/config.yaml
    python -m scripts.run_live --config altro.yaml

La modalità (paper/demo/live) è decisa dal file di configurazione.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import load_config
from src.logging_setup import setup_logging
from src.orchestrator import Orchestrator


def main() -> None:
    parser = argparse.ArgumentParser(description="Trading AI bot")
    parser.add_argument("--config", default=None, help="percorso del file di config")
    args = parser.parse_args()

    config = load_config(args.config)
    setup_logging(
        level=config.get("logging", "level", default="INFO"),
        log_file=config.get("logging", "file", default="logs/trading.log"),
    )

    if config.mode == "live" and not config.credentials.allow_live_trading:
        raise SystemExit(
            "Modalità 'live' richiesta ma ALLOW_LIVE_TRADING non è 'true' nel .env. "
            "Operazione bloccata per sicurezza."
        )

    Orchestrator(config).start()


if __name__ == "__main__":
    main()

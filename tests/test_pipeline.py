"""Test d'integrazione: decisione, rischio e broker simulato."""
from __future__ import annotations

from src.config import Config
from src.brokers.paper_broker import PaperBroker
from src.engine import DecisionEngine, RiskManager
from src.ml.model import DirectionModel
from src.strategies import build_strategies
from src.types import Side


def _config() -> Config:
    raw = {
        "mode": "paper",
        "symbols": ["EURUSD"],
        "timeframe": "M15",
        "bars_history": 300,
        "strategies": {
            "rsi": {"enabled": True, "weight": 1.0, "period": 14},
            "macd": {"enabled": True, "weight": 1.0},
            "ma_crossover": {"enabled": True, "weight": 1.0, "fast": 20, "slow": 50},
            "bollinger": {"enabled": True, "weight": 0.8, "period": 20},
        },
        "ml": {"enabled": False},
        "decision": {"entry_threshold": 0.1, "min_confidence": 0.1},
        "risk": {"risk_per_trade": 0.01, "max_open_positions": 4,
                 "max_positions_per_symbol": 1, "atr_period": 14},
    }
    return Config(raw=raw)


def test_paper_broker_connect_and_bars():
    broker = PaperBroker(_config())
    assert broker.connect()
    df = broker.get_bars("EURUSD", "M15", 200)
    assert len(df) > 50
    assert list(df.columns) == ["open", "high", "low", "close", "volume"]


def test_decision_engine_returns_decision():
    config = _config()
    broker = PaperBroker(config)
    broker.connect()
    engine = DecisionEngine(config, build_strategies(config), None)
    df = broker.get_bars("EURUSD", "M15", 300)
    decision, proba = engine.decide("EURUSD", df)
    assert -1.0 <= decision.score <= 1.0
    assert proba == 0.5  # ML disabilitato
    assert decision.side in (None, Side.BUY, Side.SELL)


def test_risk_manager_blocks_when_max_positions():
    config = _config()
    broker = PaperBroker(config)
    broker.connect()
    engine = DecisionEngine(config, build_strategies(config), None)
    risk = RiskManager(config)
    account = broker.get_account()
    risk.reset_day(account)
    df = broker.get_bars("EURUSD", "M15", 300)
    decision, _ = engine.decide("EURUSD", df)

    # forziamo un'azione per testare il limite posizioni
    if not decision.is_actionable:
        decision.side = Side.BUY
    price = broker.get_tick("EURUSD")["ask"]
    info = broker.symbol_info("EURUSD")

    # con 1 posizione già aperta sul simbolo e max_per_symbol=1 -> bloccato
    from src.types import Position
    existing = [Position(ticket=1, symbol="EURUSD", side=Side.BUY,
                         volume=0.1, entry_price=price)]
    rd = risk.evaluate(decision, df, account, price, existing, info)
    assert not rd.allowed


def test_paper_broker_full_cycle():
    config = _config()
    broker = PaperBroker(config)
    broker.connect()
    res = broker.place_order("EURUSD", Side.BUY, 0.1)
    assert res.ok
    assert len(broker.get_positions()) == 1
    broker.step()
    close = broker.close_position(res.ticket)
    assert close.ok
    assert len(broker.get_positions()) == 0

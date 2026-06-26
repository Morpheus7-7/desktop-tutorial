"""Orchestratore: il ciclo di trading in tempo reale.

Per ogni simbolo, ad ogni iterazione:
  1. scarica le candele dal broker
  2. esegue strategie classiche + modello ML  -> decisione aggregata
  3. il supervisore LLM approva o pone il veto
  4. il risk manager dimensiona la posizione e calcola SL/TP
  5. il broker esegue l'ordine (DEMO/PAPER di default)
Gestisce anche le posizioni già aperte (per ora: lasciate a SL/TP del broker).
"""
from __future__ import annotations

import time

import pandas as pd

from .brokers import build_broker
from .config import Config
from .data.indicators import atr, ema, rsi
from .engine import DecisionEngine, RiskManager
from .llm import LLMSupervisor
from .logging_setup import get_logger
from .ml.model import DirectionModel
from .strategies import build_strategies
from .types import Decision

log = get_logger("orchestrator")


class Orchestrator:
    def __init__(self, config: Config):
        self.config = config
        self.symbols = config.symbols
        self.timeframe = config.timeframe
        self.bars_history = int(config.get("bars_history", default=500))
        self.interval = int(config.get("loop_interval_seconds", default=30))

        self.broker = build_broker(config)
        self.strategies = build_strategies(config)

        self.model = None
        if config.get("ml", "enabled", default=True):
            self.model = DirectionModel(config.get("ml", "model_path",
                                                   default="models/xgb_direction.joblib"))
            self.model.load()

        self.engine = DecisionEngine(config, self.strategies, self.model)
        self.risk = RiskManager(config)

        self.llm = None
        self.llm_veto = bool(config.get("llm", "veto_enabled", default=True))
        if config.get("llm", "enabled", default=True):
            creds = config.credentials
            self.llm = LLMSupervisor(
                host=creds.ollama_host,
                model=creds.ollama_model,
                timeout=int(config.get("llm", "timeout_seconds", default=20)),
                on_error=str(config.get("llm", "on_error", default="approve")),
            )

    # ------------------------------------------------------------------ #
    def start(self) -> None:
        if not self.broker.connect():
            log.error("Connessione al broker fallita. Uscita.")
            return

        account = self.broker.get_account()
        self.risk.reset_day(account)
        log.info("Avvio | modalità=%s | strategie=%s | simboli=%s | equity=%.2f %s",
                 self.config.mode,
                 [s.name for s in self.strategies],
                 self.symbols, account.equity, account.currency)

        try:
            while True:
                self.run_once()
                time.sleep(self.interval)
        except KeyboardInterrupt:
            log.info("Interruzione richiesta dall'utente. Chiusura...")
        finally:
            self.broker.shutdown()

    # ------------------------------------------------------------------ #
    def run_once(self) -> None:
        """Una singola iterazione su tutti i simboli."""
        account = self.broker.get_account()
        if self.risk.daily_loss_breached(account):
            log.warning("Stop giornaliero attivo: nessuna nuova operazione.")
            return

        all_positions = self.broker.get_positions()
        for symbol in self.symbols:
            try:
                self._process_symbol(symbol, account, all_positions)
            except Exception as exc:  # un simbolo non deve far cadere il loop
                log.exception("Errore elaborando %s: %s", symbol, exc)

    # ------------------------------------------------------------------ #
    def _process_symbol(self, symbol, account, all_positions) -> None:
        df = self.broker.get_bars(symbol, self.timeframe, self.bars_history)
        if df is None or len(df) < 60:
            log.debug("Dati insufficienti per %s", symbol)
            return

        decision, proba_up = self.engine.decide(symbol, df)
        log.info("%s | %s | %s", symbol,
                 decision.side.value.upper() if decision.side else "FLAT",
                 decision.reason)

        if not decision.is_actionable:
            return

        # --- veto del supervisore LLM ---
        if self.llm is not None and self.llm_veto:
            context = self._market_context(df, proba_up, symbol, all_positions)
            verdict = self.llm.review(decision, context)
            if not verdict.approve:
                log.info("%s | VETO LLM: %s", symbol, verdict.reason)
                return
            log.info("%s | LLM approva (conf=%.2f): %s",
                     symbol, verdict.confidence, verdict.reason)

        # --- controllo di rischio + esecuzione ---
        tick = self.broker.get_tick(symbol)
        price = tick.get("ask") if decision.side.value == "buy" else tick.get("bid")
        if not price:
            return
        symbol_info = self.broker.symbol_info(symbol)
        rd = self.risk.evaluate(decision, df, account, price, all_positions, symbol_info)
        if not rd.allowed:
            log.info("%s | rischio: %s", symbol, rd.reason)
            return

        result = self.broker.place_order(
            symbol=symbol, side=decision.side, volume=rd.volume,
            sl=rd.sl, tp=rd.tp, comment=f"ai {decision.score:+.2f}",
        )
        if result.ok:
            log.info("%s | ORDINE ESEGUITO ticket=%s vol=%.2f sl=%.5f tp=%.5f",
                     symbol, result.ticket, rd.volume, rd.sl, rd.tp)
            all_positions.extend(self.broker.get_positions(symbol))
        else:
            log.error("%s | ordine fallito: %s", symbol, result.message)

    # ------------------------------------------------------------------ #
    def _market_context(self, df: pd.DataFrame, proba_up: float, symbol, positions) -> dict:
        close = df["close"]
        ema20, ema50 = float(ema(close, 20).iloc[-1]), float(ema(close, 50).iloc[-1])
        atr_val = float(atr(df, 14).iloc[-1])
        price = float(close.iloc[-1])
        return {
            "price": round(price, 5),
            "rsi": round(float(rsi(close, 14).iloc[-1]), 1),
            "atr_pct": round(atr_val / price * 100, 3) if price else 0,
            "trend": "rialzista" if ema20 > ema50 else "ribassista",
            "ml_proba_up": round(proba_up, 3),
            "open_positions": sum(1 for p in positions if p.symbol == symbol),
        }

"""Webhook FastAPI per gli alert di TradingView.

TradingView (piano con webhook) invia un POST JSON come:

    {
      "secret": "...",
      "symbol": "EURUSD",
      "action": "buy",          // buy | sell
      "signal": "SMC-BOS",      // etichetta libera dal Pine script
      "price": 1.08123          // opzionale
    }

Gli alert validi finiscono in una coda thread-safe letta dal loop principale.
Il webhook NON esegue mai ordini direttamente: decide sempre il cervello
Python (confluenza + risk management).
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass, field

import uvicorn
from fastapi import FastAPI, HTTPException, Request

log = logging.getLogger(__name__)


@dataclass
class TvAlert:
    symbol: str
    direction: int          # +1 buy, -1 sell
    signal: str
    price: float | None
    received_at: float = field(default_factory=time.time)


class TradingViewWebhook:
    def __init__(self, host: str, port: int, secret: str):
        self.host = host
        self.port = port
        self.secret = secret
        self.alerts: "queue.Queue[TvAlert]" = queue.Queue()
        self._app = FastAPI(title="SMC-MT5 TradingView Webhook")
        self._register_routes()
        self._server_thread: threading.Thread | None = None

    def _register_routes(self):
        app = self._app

        @app.get("/health")
        async def health():
            return {"status": "ok"}

        @app.post("/webhook")
        async def webhook(request: Request):
            try:
                payload = await request.json()
            except Exception:
                raise HTTPException(400, "JSON non valido")
            if payload.get("secret") != self.secret:
                log.warning("Webhook: secret errato da %s", request.client.host)
                raise HTTPException(403, "forbidden")
            action = str(payload.get("action", "")).lower()
            if action not in ("buy", "sell"):
                raise HTTPException(400, "action deve essere buy o sell")
            alert = TvAlert(
                symbol=str(payload.get("symbol", "")).upper(),
                direction=+1 if action == "buy" else -1,
                signal=str(payload.get("signal", "tv-alert")),
                price=payload.get("price"),
            )
            self.alerts.put(alert)
            log.info("Alert TV ricevuto: %s %s (%s)",
                     action.upper(), alert.symbol, alert.signal)
            return {"status": "queued"}

    def start(self):
        """Avvia il server in un thread separato (non blocca il loop)."""
        config = uvicorn.Config(self._app, host=self.host, port=self.port,
                                log_level="warning")
        server = uvicorn.Server(config)
        self._server_thread = threading.Thread(target=server.run, daemon=True)
        self._server_thread.start()
        log.info("Webhook TradingView in ascolto su %s:%s/webhook",
                 self.host, self.port)

    def drain(self) -> list[TvAlert]:
        """Preleva tutti gli alert in coda."""
        out = []
        while True:
            try:
                out.append(self.alerts.get_nowait())
            except queue.Empty:
                return out

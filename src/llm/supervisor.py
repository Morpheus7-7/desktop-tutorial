"""Supervisore LLM locale via Ollama.

Riceve la decisione proposta dal motore (segnali delle strategie + ML) insieme
al contesto di mercato e risponde se approvare o porre il veto. NON genera
segnali da solo: agisce come "secondo parere" prudente sopra l'analisi numerica.

Richiede Ollama in esecuzione in locale (https://ollama.com) con un modello
scaricato, es:  `ollama pull llama3.1`
"""
from __future__ import annotations

import json
from dataclasses import dataclass

import requests

from ..logging_setup import get_logger
from ..types import Decision

log = get_logger("llm.supervisor")


@dataclass
class SupervisorVerdict:
    approve: bool
    confidence: float
    reason: str


SYSTEM_PROMPT = (
    "Sei un risk manager prudente di un sistema di trading algoritmico. "
    "Ricevi una decisione proposta da modelli quantitativi e devi solo APPROVARE "
    "o porre il VETO, valutando coerenza e rischio. Non inventare dati. "
    "Rispondi ESCLUSIVAMENTE con un oggetto JSON valido nel formato: "
    '{"approve": true/false, "confidence": 0.0-1.0, "reason": "breve motivazione"}.'
)


class LLMSupervisor:
    def __init__(self, host: str, model: str, timeout: int = 20, on_error: str = "approve"):
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.on_error = on_error  # "approve" | "reject"

    # ------------------------------------------------------------------ #
    def review(self, decision: Decision, context: dict) -> SupervisorVerdict:
        """Chiede al LLM di validare la decisione. Fallisce in modo sicuro."""
        prompt = self._build_prompt(decision, context)
        try:
            resp = requests.post(
                f"{self.host}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "stream": False,
                    "format": "json",
                    "options": {"temperature": 0.1},
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            content = resp.json()["message"]["content"]
            return self._parse(content)
        except Exception as exc:
            approve = self.on_error == "approve"
            log.warning("Supervisore LLM non raggiungibile (%s) -> fallback '%s'",
                        exc, self.on_error)
            return SupervisorVerdict(
                approve=approve,
                confidence=0.0,
                reason=f"LLM non disponibile, fallback={self.on_error}",
            )

    # ------------------------------------------------------------------ #
    def _build_prompt(self, decision: Decision, context: dict) -> str:
        signals = ", ".join(
            f"{s.name}={s.direction:+d}({s.confidence:.2f})" for s in decision.signals
        )
        side = decision.side.value if decision.side else "nessuna"
        return (
            f"Simbolo: {decision.symbol}\n"
            f"Azione proposta: {side.upper()}\n"
            f"Punteggio combinato: {decision.score:+.2f} (confidenza {decision.confidence:.2f})\n"
            f"Segnali strategie: {signals}\n"
            f"Probabilità ML rialzo: {context.get('ml_proba_up', 0.5):.2f}\n"
            f"Prezzo: {context.get('price')}  RSI(14): {context.get('rsi')}  "
            f"ATR%: {context.get('atr_pct')}\n"
            f"Trend EMA20 vs EMA50: {context.get('trend')}\n"
            f"Posizioni aperte sul simbolo: {context.get('open_positions', 0)}\n\n"
            "Valuta se l'operazione è coerente e ragionevole dal punto di vista del rischio. "
            "Poni il veto se i segnali sono contraddittori, la confidenza è bassa o il "
            "contesto è sfavorevole."
        )

    def _parse(self, content: str) -> SupervisorVerdict:
        try:
            data = json.loads(content)
            return SupervisorVerdict(
                approve=bool(data.get("approve", False)),
                confidence=float(data.get("confidence", 0.0)),
                reason=str(data.get("reason", ""))[:300],
            )
        except (json.JSONDecodeError, ValueError, TypeError):
            log.warning("Risposta LLM non in JSON valido: %s", content[:200])
            approve = self.on_error == "approve"
            return SupervisorVerdict(approve=approve, confidence=0.0,
                                     reason="parsing fallito")

"""Caricamento della configurazione (config.yaml + variabili d'ambiente .env)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

try:
    from dotenv import load_dotenv
except ImportError:  # python-dotenv non installato
    def load_dotenv(*_args, **_kwargs):  # type: ignore
        return False


PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class Credentials:
    """Segreti letti dalle variabili d'ambiente."""
    mt5_login: int | None = None
    mt5_password: str | None = None
    mt5_server: str | None = None
    mt5_terminal_path: str | None = None
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    allow_live_trading: bool = False


@dataclass
class Config:
    """Configurazione completa dell'applicazione."""
    raw: dict[str, Any] = field(default_factory=dict)
    credentials: Credentials = field(default_factory=Credentials)

    # --- accessori comodi ---
    def get(self, *keys: str, default: Any = None) -> Any:
        """Accesso annidato sicuro: config.get('risk', 'risk_per_trade')."""
        node: Any = self.raw
        for key in keys:
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node

    @property
    def mode(self) -> str:
        return str(self.raw.get("mode", "paper")).lower()

    @property
    def symbols(self) -> list[str]:
        return list(self.raw.get("symbols", []))

    @property
    def timeframe(self) -> str:
        return str(self.raw.get("timeframe", "M15"))


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def load_config(config_path: str | Path | None = None) -> Config:
    """Carica config.yaml e .env e restituisce un oggetto Config."""
    load_dotenv(PROJECT_ROOT / ".env")

    if config_path is None:
        config_path = PROJECT_ROOT / "config" / "config.yaml"
    config_path = Path(config_path)

    raw: dict[str, Any] = {}
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as fh:
            raw = yaml.safe_load(fh) or {}

    login = os.getenv("MT5_LOGIN")
    creds = Credentials(
        mt5_login=int(login) if login and login.isdigit() else None,
        mt5_password=os.getenv("MT5_PASSWORD"),
        mt5_server=os.getenv("MT5_SERVER"),
        mt5_terminal_path=os.getenv("MT5_TERMINAL_PATH") or None,
        ollama_host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
        ollama_model=os.getenv("OLLAMA_MODEL", "llama3.1"),
        allow_live_trading=_as_bool(os.getenv("ALLOW_LIVE_TRADING"), False),
    )
    return Config(raw=raw, credentials=creds)

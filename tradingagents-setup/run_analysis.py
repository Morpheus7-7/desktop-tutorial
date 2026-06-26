"""Esegue un'analisi TradingAgents in LOCALE (Ollama) e stampa la decisione.

Uso (dentro la venv creata da setup):
    python run_analysis.py AAPL
    python run_analysis.py BTC-USD --date 2026-06-25
    python run_analysis.py NVDA --deep qwen2.5:14b --quick llama3.1 --rounds 2

Configurazione 100% locale: nessuna API key a pagamento. I dati di mercato
arrivano da yfinance (gratis); l'IA gira su Ollama sul tuo PC.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date


def main() -> None:
    parser = argparse.ArgumentParser(description="Analisi TradingAgents in locale (Ollama)")
    parser.add_argument("ticker", help="es. AAPL, NVDA, BTC-USD, 0700.HK")
    parser.add_argument("--date", default=date.today().isoformat(),
                        help="data dell'analisi (YYYY-MM-DD), usa un giorno feriale recente")
    parser.add_argument("--deep", default=os.getenv("TRADINGAGENTS_DEEP_THINK_LLM", "qwen2.5:14b"),
                        help="modello Ollama per il ragionamento 'profondo'")
    parser.add_argument("--quick", default=os.getenv("TRADINGAGENTS_QUICK_THINK_LLM", "llama3.1"),
                        help="modello Ollama 'veloce'")
    parser.add_argument("--rounds", type=int,
                        default=int(os.getenv("TRADINGAGENTS_MAX_DEBATE_ROUNDS", "1")),
                        help="round di dibattito tra gli agenti (più alto = più lento)")
    args = parser.parse_args()

    try:
        from tradingagents.default_config import DEFAULT_CONFIG
        from tradingagents.graph.trading_graph import TradingAgentsGraph
    except ImportError:
        sys.exit(
            "ERRORE: il pacchetto 'tradingagents' non è installato in questo ambiente.\n"
            "Esegui prima lo script di setup (setup.ps1 su Windows / setup.sh su Mac-Linux) "
            "e attiva la venv."
        )

    config = DEFAULT_CONFIG.copy()
    config["llm_provider"] = "ollama"
    config["backend_url"] = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    config["deep_think_llm"] = args.deep
    config["quick_think_llm"] = args.quick
    config["max_debate_rounds"] = args.rounds
    config["max_risk_discuss_rounds"] = args.rounds
    config["output_language"] = os.getenv("TRADINGAGENTS_OUTPUT_LANGUAGE", "Italian")

    print(f"▶ Analisi {args.ticker} @ {args.date}")
    print(f"  Modelli Ollama: deep={args.deep} | quick={args.quick} | round={args.rounds}")
    print("  Con modelli locali può richiedere diversi minuti. Attendere...\n")

    try:
        ta = TradingAgentsGraph(debug=True, config=config)
        _, decision = ta.propagate(args.ticker, args.date)
    except Exception as exc:  # noqa: BLE001 - vogliamo un messaggio guidato
        sys.exit(
            f"\nERRORE durante l'analisi: {exc}\n\n"
            "Verifica che:\n"
            "  1) Ollama sia in esecuzione (avvia l'app, oppure: ollama serve)\n"
            f"  2) i modelli siano scaricati:  ollama pull {args.deep}  &&  ollama pull {args.quick}\n"
            "  3) il ticker e la data siano validi (giorno feriale con dati di borsa)\n"
        )

    print("\n" + "=" * 60)
    print(f"DECISIONE per {args.ticker} ({args.date}):")
    print("=" * 60)
    print(decision)


if __name__ == "__main__":
    main()

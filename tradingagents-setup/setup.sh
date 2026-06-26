#!/usr/bin/env bash
# ============================================================
#  Setup TradingAgents in locale — Mac / Linux
#  Eseguire dalla cartella tradingagents-setup:
#     cd tradingagents-setup && bash setup.sh
# ============================================================
set -euo pipefail
cd "$(dirname "$0")"

echo "==> 1/4  Clono TradingAgents (se manca)..."
if [ ! -d "TradingAgents" ]; then
    git clone https://github.com/TauricResearch/TradingAgents.git
else
    echo "    già presente, salto."
fi

echo "==> 2/4  Creo l'ambiente virtuale Python..."
[ -d ".venv" ] || python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate

echo "==> 3/4  Installo TradingAgents e le dipendenze (può volerci qualche minuto)..."
python -m pip install --upgrade pip
pip install ./TradingAgents

echo "==> 4/4  Preparo il file .env..."
[ -f ".env" ] || cp .env.example .env

echo ""
echo "✅ Setup completato!"
echo "Prossimi passi:"
echo "  1) Installa Ollama da https://ollama.com e avvialo (ollama serve)"
echo "  2) Scarica i modelli:   ollama pull qwen2.5:14b  &&  ollama pull llama3.1"
echo "  3) Lancia un'analisi:    python run_analysis.py AAPL"
echo "     (oppure la CLI guidata:  python -m cli.main  dentro la cartella TradingAgents)"

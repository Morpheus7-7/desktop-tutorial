# ============================================================
#  Setup TradingAgents in locale — Windows (PowerShell)
#  Eseguire dalla cartella tradingagents-setup:
#     cd tradingagents-setup
#     powershell -ExecutionPolicy Bypass -File .\setup.ps1
# ============================================================
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "==> 1/4  Clono TradingAgents (se manca)..." -ForegroundColor Cyan
if (-not (Test-Path "TradingAgents")) {
    git clone https://github.com/TauricResearch/TradingAgents.git
} else {
    Write-Host "    già presente, salto." -ForegroundColor DarkGray
}

Write-Host "==> 2/4  Creo l'ambiente virtuale Python..." -ForegroundColor Cyan
if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
& ".\.venv\Scripts\Activate.ps1"

Write-Host "==> 3/4  Installo TradingAgents e le dipendenze (può volerci qualche minuto)..." -ForegroundColor Cyan
python -m pip install --upgrade pip
pip install .\TradingAgents

Write-Host "==> 4/4  Preparo il file .env..." -ForegroundColor Cyan
if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "    creato .env (modificalo se vuoi cambiare i modelli)." -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "✅ Setup completato!" -ForegroundColor Green
Write-Host "Prossimi passi:" -ForegroundColor Yellow
Write-Host "  1) Installa Ollama da https://ollama.com e avvialo"
Write-Host "  2) Scarica i modelli:   ollama pull qwen2.5:14b   &&   ollama pull llama3.1"
Write-Host "  3) Lancia un'analisi:   python run_analysis.py AAPL"
Write-Host "     (oppure la CLI guidata:  python -m cli.main  dentro la cartella TradingAgents)"

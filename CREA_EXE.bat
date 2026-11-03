@echo off
chcp 65001 >nul
setlocal
title Gestionale Assicurativo - creazione del programma
cd /d "%~dp0"

echo ============================================================
echo   Gestionale Assicurativo - creazione di GestionaleAssicurativo.exe
echo ============================================================
echo.

rem --- Python 3.11 o successivo (launcher "py" installato con Python da python.org)
set "PY="
py -3.11 --version >nul 2>&1 && set "PY=py -3.11"
if not defined PY py -3 --version >nul 2>&1 && set "PY=py -3"
if not defined PY python --version >nul 2>&1 && set "PY=python"
if not defined PY (
  echo Python non e' installato.
  echo Scaricalo da https://www.python.org/downloads/ ^(Windows installer 64-bit^)
  echo e durante l'installazione spunta "Add Python to PATH". Poi rilancia questo file.
  start "" https://www.python.org/downloads/windows/
  pause
  exit /b 1
)
echo Uso: %PY%
%PY% --version

rem --- Ambiente separato, per non toccare altri programmi Python
if not exist ".venv-build\Scripts\python.exe" (
  echo.
  echo Preparo l'ambiente di costruzione...
  %PY% -m venv .venv-build || goto errore
)
set "VPY=.venv-build\Scripts\python.exe"

echo.
echo Installo i componenti necessari ^(serve internet, qualche minuto la prima volta^)...
"%VPY%" -m pip install --upgrade pip >nul
"%VPY%" -m pip install -r requirements-build.txt || goto errore

echo.
echo Creo l'eseguibile...
"%VPY%" -m PyInstaller gestionale.spec --noconfirm --clean || goto errore

if not exist "dist\GestionaleAssicurativo.exe" goto errore

echo.
echo ============================================================
echo   FATTO! Il programma e' in:
echo   %CD%\dist\GestionaleAssicurativo.exe
echo.
echo   Copialo dove vuoi ^(es. Desktop^) e avvialo con doppio clic.
echo   Se Windows mostra "Windows ha protetto il PC": Ulteriori
echo   informazioni ^> Esegui comunque.
echo ============================================================
explorer "%CD%\dist"
pause
exit /b 0

:errore
echo.
echo ============================================================
echo   Qualcosa non e' andato a buon fine: leggi i messaggi qui sopra.
echo   Controlla la connessione a internet e riprova; se l'errore resta,
echo   copia questi messaggi e mandali a chi ti assiste.
echo ============================================================
pause
exit /b 1

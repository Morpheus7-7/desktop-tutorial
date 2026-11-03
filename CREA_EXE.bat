@echo off
chcp 65001 >nul
setlocal
title Deal Combined - creazione del programma
cd /d "%~dp0"

echo ============================================================
echo   Deal Combined - creazione di DealCombined.exe e dell'installatore
echo ============================================================
echo.

rem --- Python 3.11 o successivo (launcher "py" installato con Python da python.org)
set "PY="
rem Versioni supportate da tutti i componenti (finestra compresa): dalla 3.11 alla 3.14.
rem Si preferisce la 3.13 (la piu' collaudata con la finestra); la 3.14 va bene lo stesso.
for %%V in (3.13 3.12 3.14 3.11) do if not defined PY py -%%V --version >nul 2>&1 && set "PY=py -%%V"
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

if not exist "dist\DealCombined.exe" goto errore

rem --- Installatore (se c'e' Inno Setup 6): aggiorna Deal Combined gia' installato
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"
set "INSTALLATORE="
rem (la versione si legge fuori dal blocco: dentro le parentesi %VERSIONE% sarebbe ancora vuota)
for /f "delims=" %%v in ('"%VPY%" -c "import gestionale; print(gestionale.__version__)"') do set "VERSIONE=%%v"
if exist "%ISCC%" (
  echo.
  echo Creo l'installatore...
  "%ISCC%" /Q /DVersioneApp=%VERSIONE% installer\DealCombined.iss && set "INSTALLATORE=1"
)

echo.
echo ============================================================
echo   FATTO! Il programma e' in:
echo   %CD%\dist\DealCombined.exe
if defined INSTALLATORE (
  echo.
  echo   Installatore: %CD%\dist\Installa-DealCombined.exe
  echo   Avvialo per aggiornare Deal Combined gia' installato: i dati in
  echo   Documenti\Deal Combined restano dove sono ^(e prima si fa un backup^).
)
echo.
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

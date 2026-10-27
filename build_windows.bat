@echo off
rem Crea DealCombined.exe e l'installatore Installa-DealCombined.exe.
rem Requisiti: Python 3.11+ (con "Add Python to PATH") e, per l'installatore,
rem Inno Setup 6 (https://jrsoftware.org/isinfo.php).
setlocal
cd /d "%~dp0"

echo [1/3] Installo le dipendenze di build...
python -m pip install --upgrade pip || goto :errore
python -m pip install -r requirements-build.txt || goto :errore

echo [2/3] Compilo DealCombined.exe...
python -m PyInstaller gestionale.spec --noconfirm || goto :errore

echo [3/3] Creo l'installatore...
set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" (
  echo.
  echo Inno Setup non trovato: l'eseguibile e' pronto in dist\DealCombined.exe,
  echo per l'installatore installa Inno Setup 6 e rilancia questo file.
  goto :fine
)
"%ISCC%" installer\DealCombined.iss || goto :errore

echo.
echo Fatto: dist\Installa-DealCombined.exe
goto :fine

:errore
echo.
echo Si e' verificato un errore: controlla i messaggi qui sopra.
exit /b 1

:fine
endlocal
pause

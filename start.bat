@echo off
setlocal

REM ------------------------------------------------------------
REM BikeToursArchive - Startscript
REM ------------------------------------------------------------

REM 1) Projektpfad (anpassen falls du es verschoben hast)
set "PROJECT_DIR=C:\Users\Markus\PycharmProjects\BikeToursArchive"

REM 2) Python/venv
set "VENV_ACTIVATE=%PROJECT_DIR%\.venv\Scripts\activate.bat"

REM 3) URL
set "URL=http://127.0.0.1:5000/"

REM 4) Chrome Pfad (Standard-Installationsorte)
set "CHROME_EXE=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME_EXE%" set "CHROME_EXE=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"

cd /d "%PROJECT_DIR%"

REM venv aktivieren, falls vorhanden
if exist "%VENV_ACTIVATE%" (
    call "%VENV_ACTIVATE%"
) else (
    echo [WARN] Keine .venv gefunden unter: %VENV_ACTIVATE%
    echo        Es wird das globale Python verwendet.
)

REM Flask im Produktionsmodus ohne Reload-Doppelstart (stabiler für BAT)
set "FLASK_ENV=production"
set "FLASK_DEBUG=0"
set "PYTHONUNBUFFERED=1"

REM Server in neuem Fenster starten
start "BikeToursArchive Server" /D "%PROJECT_DIR%" cmd /c ^
    "python app.py"

REM Kurz warten, bis der Server lauscht (bei Bedarf erhöhen)
timeout /t 2 /nobreak >nul

REM Chrome öffnen
if exist "%CHROME_EXE%" (
    start "" "%CHROME_EXE%" --new-window "%URL%"
) else (
    echo [WARN] Chrome nicht gefunden. Oeffne URL im Standardbrowser...
    start "" "%URL%"
)

endlocal

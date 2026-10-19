@echo off
:: TRAKKART — setup + launch (TRAKK family standard)
set "APP_DIR=%~dp0"
cd /d "%APP_DIR%"

if not exist ".venv\Scripts\python.exe" (
    echo [TRAKKART] Creating virtual environment...
    python -m venv .venv
    if errorlevel 1 (
        echo [TRAKKART] ERROR: python -m venv failed. Install Python 3.11+ with "Add to PATH".
        pause
        exit /b 1
    )
)

echo [TRAKKART] Installing dependencies...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [TRAKKART] ERROR: pip install failed.
    pause
    exit /b 1
)

echo [TRAKKART] Starting...
".venv\Scripts\python.exe" main.py

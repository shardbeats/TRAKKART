@echo off
:: TRAKKART — setup + launch (central venv if present, else local .venv)
:: Override: set CENTRAL_VENV=D:\otra\ruta before calling.
set "APP_DIR=%~dp0"
cd /d "%APP_DIR%"
if not defined CENTRAL_VENV set "CENTRAL_VENV=C:\venvs\dev"

set "PY="
if exist "%CENTRAL_VENV%\Scripts\python.exe" set "PY=%CENTRAL_VENV%\Scripts\python.exe"
if not defined PY (
    if not exist ".venv\Scripts\python.exe" (
        echo [TRAKKART] Creating local virtual environment...
        python -m venv .venv
        if errorlevel 1 (
            echo [TRAKKART] ERROR: python -m venv failed. Install Python 3.11+ with "Add to PATH".
            pause
            exit /b 1
        )
    )
    set "PY=.venv\Scripts\python.exe"
)

echo [TRAKKART] Installing dependencies into %PY% ...
"%PY%" -m pip install --upgrade pip
"%PY%" -m pip install -r requirements.txt
if errorlevel 1 (
    echo [TRAKKART] ERROR: pip install failed.
    pause
    exit /b 1
)

echo [TRAKKART] Starting...
"%PY%" main.py

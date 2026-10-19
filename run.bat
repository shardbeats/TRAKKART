@echo off
:: TRAKKART — launch with existing .venv
set "APP_DIR=%~dp0"
cd /d "%APP_DIR%"

if not exist ".venv\Scripts\python.exe" (
    echo [TRAKKART] No .venv, running start.bat...
    call "%APP_DIR%start.bat"
    exit /b %ERRORLEVEL%
)

".venv\Scripts\python.exe" main.py

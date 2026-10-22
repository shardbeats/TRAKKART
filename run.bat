@echo off
:: TRAKKART — launch (central venv first, local .venv fallback)
:: Override: set CENTRAL_VENV=D:\otra\ruta before calling.
set "APP_DIR=%~dp0"
cd /d "%APP_DIR%"
if not defined CENTRAL_VENV set "CENTRAL_VENV=C:\venvs\dev"

if exist "%CENTRAL_VENV%\Scripts\python.exe" (
    "%CENTRAL_VENV%\Scripts\python.exe" main.py
    exit /b %ERRORLEVEL%
)

if not exist ".venv\Scripts\python.exe" (
    echo [TRAKKART] No venv found, running start.bat...
    call "%APP_DIR%start.bat"
    exit /b %ERRORLEVEL%
)

".venv\Scripts\python.exe" main.py

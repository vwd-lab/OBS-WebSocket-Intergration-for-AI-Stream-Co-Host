@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

REM OBS WebSocket Bridge launcher
REM ------------------------------
REM Starts obs_gui.py as a subprocess. The GUI shows the live log and lets you
REM configure host, port, password, scene, source, and overlay behaviour.

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

if not exist ".env" (
    echo [obs] .env not found. Run setup_obs_gui.bat first to configure.
    pause
    exit /b 1
)

echo Starting OBS WebSocket Bridge...
"%PY%" obs_gui.py
pause
endlocal

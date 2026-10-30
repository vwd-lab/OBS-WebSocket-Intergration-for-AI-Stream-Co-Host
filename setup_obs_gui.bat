@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

REM ========================================================================
REM OBS WebSocket Bridge Setup - interactive configuration before launching obs_gui
REM ========================================================================
REM Prompts for your OBS WebSocket settings, writes .env, then launches
REM obs_gui.py so you can start/stop the bridge from the GUI.
REM ========================================================================

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

echo.
echo ============================================================
echo   OBS WebSocket Bridge Setup
echo ============================================================
echo.

set "ENABLED="
set /p ENABLED="Enable OBS overlay? [yes/no] (default yes): "
if not defined ENABLED set ENABLED=yes

set "HOST="
set /p HOST="OBS WebSocket host (default localhost): "
if not defined HOST set HOST=localhost

set "PORT="
set /p PORT="OBS WebSocket port (default 4455): "
if not defined PORT set PORT=4455

set "PASSWORD="
set /p PASSWORD="OBS WebSocket password (press Enter to skip): "

set "SCENE="
set /p SCENE="Scene name containing the image source (default Main): "
if not defined SCENE set SCENE=Main

set "SOURCE="
set /p SOURCE="Exact Image source name in that scene (default Bot Name): "
if not defined SOURCE set SOURCE=Bot Name

set "HIDE="
set /p HIDE="Hide image on connect? [yes/no] (default yes): "
if not defined HIDE set HIDE=yes

set "TIMEOUT="
set /p TIMEOUT="Connection timeout seconds (default 3.0): "
if not defined TIMEOUT set TIMEOUT=3.0

REM Write .env via Python for safe quoting
%PY% -c "
import os

enabled  = os.environ.get('ENABLED', 'yes').strip().lower() in ('1', 'y', 'yes', 'true')
host     = os.environ.get('HOST', 'localhost').strip() or 'localhost'
port     = os.environ.get('PORT', '4455').strip() or '4455'
password = os.environ.get('PASSWORD', '').strip()
scene    = os.environ.get('SCENE', 'Main').strip() or 'Main'
source   = os.environ.get('SOURCE', 'Bot Name').strip() or 'Bot Name'
hide     = os.environ.get('HIDE', 'yes').strip().lower() in ('1', 'y', 'yes', 'true')
timeout  = os.environ.get('TIMEOUT', '3.0').strip() or '3.0'

env = {
    'OBS_ENABLED': '1' if enabled else '0',
    'OBS_HOST': host,
    'OBS_PORT': port,
    'OBS_PASSWORD': password,
    'OBS_SCENE': scene,
    'OBS_SOURCE': source,
    'OBS_HIDE_ON_CONNECT': '1' if hide else '0',
    'OBS_TIMEOUT_S': timeout,
}

with open('.env', 'w', encoding='utf-8') as f:
    for k, v in env.items():
        f.write(f'{k}={v}\n')

print('.env written.')
"

echo.
echo ============================================================
echo   Setup complete. Launching OBS GUI...
echo ============================================================
echo.

"%PY%" obs_gui.py
pause
endlocal

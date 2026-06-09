@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PY_CMD=.venv\Scripts\python.exe"
if not exist "%PY_CMD%" set "PY_CMD=python"

echo [INFO] Syncing Owner/Action/Reason from latest DFV_actions_*.xlsx ...
"%PY_CMD%" dfv_tool\sync_owners.py

echo.
echo [INFO] Press any key to close.
pause >nul

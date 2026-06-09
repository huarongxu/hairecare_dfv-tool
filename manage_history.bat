@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PY_CMD=.venv\Scripts\python.exe"
if not exist "%PY_CMD%" set "PY_CMD=python"

"%PY_CMD%" dfv_tool\manage_history.py

echo.
echo [INFO] Press any key to close.
pause >nul

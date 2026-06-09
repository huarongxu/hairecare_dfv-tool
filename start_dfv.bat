@echo off
setlocal EnableExtensions

cd /d "%~dp0"

set "PY_CMD="
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" --version >nul 2>&1
    if not errorlevel 1 set "PY_CMD=.venv\Scripts\python.exe"
)

if "%PY_CMD%"=="" (
    echo [INFO] Creating virtual environment...
    where py >nul 2>&1
    if not errorlevel 1 (
        py -3 -m venv .venv
    ) else (
        python -m venv .venv
    )
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        goto :fail
    )
    set "PY_CMD=.venv\Scripts\python.exe"
)

echo [INFO] Installing/updating dependencies...
"%PY_CMD%" -m pip install --disable-pip-version-check -r requirements.txt
if errorlevel 1 (
    echo [ERROR] Dependency installation failed.
    goto :fail
)

echo [INFO] Running full DFV workflow...
"%PY_CMD%" dfv_tool\run.py
if errorlevel 1 (
    echo [WARN] Full AO run failed. Trying pipeline with latest CSV...
    "%PY_CMD%" dfv_tool\pipeline.py
    if errorlevel 1 (
        echo [ERROR] Pipeline fallback failed.
        goto :fail
    )
)

if exist "output\DFV_Dashboard.html" (
    echo [INFO] Opening dashboard...
    start "" "output\DFV_Dashboard.html"
    echo [OK] Done.
    exit /b 0
)

echo [ERROR] Dashboard file not found: output\DFV_Dashboard.html

:fail
echo [INFO] Press any key to close.
pause >nul
exit /b 1

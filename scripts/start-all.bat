@echo off
setlocal enabledelayedexpansion

echo ==================================================
echo   Starting MediFlux Autonomous Pharma Platform
echo ==================================================

set "SCRIPT_DIR=%~dp0"
set "ROOT_DIR=%SCRIPT_DIR%.."
set "BACKEND_DIR=%ROOT_DIR%\backend"
set "FRONTEND_DIR=%ROOT_DIR%\frontend"
set "DESKTOP_DIR=%ROOT_DIR%\desktop"

REM Check Python
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python 3.11+ is required but not found in PATH.
    exit /b 1
)

REM Check Node / npm
where npm >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] npm is required but not found in PATH.
    exit /b 1
)

set "LAN_FLAG="
set "CHECK_ONLY="
set "DESKTOP_FLAG="

for %%A in (%*) do (
    if "%%A"=="--lan" set "LAN_FLAG=--lan"
    if "%%A"=="--check-only" set "CHECK_ONLY=--check-only"
    if "%%A"=="--desktop" set "DESKTOP_FLAG=--desktop"
)

REM Check if --check-only argument passed
if defined CHECK_ONLY (
    python "%SCRIPT_DIR%start_all.py" !LAN_FLAG! --check-only
    exit /b !ERRORLEVEL!
)

REM Determine python interpreter
if exist "%BACKEND_DIR%\venv\Scripts\python.exe" (
    set "PYTHON_EXEC=%BACKEND_DIR%\venv\Scripts\python.exe"
    echo [Backend] Using virtual environment at backend\venv
) else (
    set "PYTHON_EXEC=python"
    echo [Backend] Using system Python executable
)

if defined LAN_FLAG (
    set "UVICORN_HOST=0.0.0.0"
    echo [Backend] Starting FastAPI server on host 0.0.0.0:8000 (LAN enabled) ...
) else (
    set "UVICORN_HOST=127.0.0.1"
    echo [Backend] Starting FastAPI server on http://localhost:8000 ...
)

start "MediFlux Backend" /D "%BACKEND_DIR%" "%PYTHON_EXEC%" -m uvicorn app.main:app --reload --host !UVICORN_HOST! --port 8000

echo [Frontend] Starting Vite development server on http://localhost:5173 ...
start "MediFlux Frontend" /D "%FRONTEND_DIR%" npm.cmd run dev

if defined DESKTOP_FLAG (
    echo [Desktop] Starting MediFlux Desktop application...
    start "MediFlux Desktop" /D "%DESKTOP_DIR%" npm.cmd run desktop:dev
)

echo.
echo MediFlux services initiated:
echo   - Backend API:    http://localhost:8000/docs
echo   - Health Check:   http://localhost:8000/health
echo   - Frontend Web:   http://localhost:5173
echo.
echo Use scripts\start-all.bat --desktop to launch the desktop shell.


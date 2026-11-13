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

REM Check if --check-only argument passed
if "%~1"=="--check-only" (
    python "%SCRIPT_DIR%start_all.py" --check-only
    exit /b %ERRORLEVEL%
)

REM Determine python interpreter
if exist "%BACKEND_DIR%\venv\Scripts\python.exe" (
    set "PYTHON_EXEC=%BACKEND_DIR%\venv\Scripts\python.exe"
    echo [Backend] Using virtual environment at backend\venv
) else (
    set "PYTHON_EXEC=python"
    echo [Backend] Using system Python executable
)

echo [Backend] Starting FastAPI server on http://localhost:8000 ...
start "MediFlux Backend" /D "%BACKEND_DIR%" "%PYTHON_EXEC%" -m uvicorn app.main:app --reload --port 8000

echo [Frontend] Starting Vite development server on http://localhost:5173 ...
start "MediFlux Frontend" /D "%FRONTEND_DIR%" npm.cmd run dev

REM Check if desktop flag is requested
if "%~1"=="--desktop" (
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

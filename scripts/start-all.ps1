# MediFlux Startup Script (PowerShell for Windows)
# Starts FastAPI backend and Vite frontend concurrently

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir = Split-Path -Parent $ScriptDir
$BackendDir = Join-Path $RootDir "backend"
$FrontendDir = Join-Path $RootDir "frontend"

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "  Starting MediFlux Autonomous Pharma Platform     " -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

# Validate prerequisites
if (-not (Get-Command "python" -ErrorAction SilentlyContinue)) {
    Write-Error "Python 3.11+ is required but not found in PATH."
    exit 1
}

if (-not (Get-Command "npm" -ErrorAction SilentlyContinue)) {
    Write-Error "npm is required but not found in PATH."
    exit 1
}

# Determine Python executable (venv or system python)
$VenvPython = Join-Path $BackendDir "venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
    $PythonExec = $VenvPython
    Write-Host "[Backend] Using virtual environment at backend/venv" -ForegroundColor Green
} else {
    $PythonExec = "python"
    Write-Host "[Backend] Using system Python executable" -ForegroundColor Yellow
}

Write-Host "[Backend] Starting FastAPI server on http://localhost:8000 ..." -ForegroundColor Green
$BackendProcess = Start-Process -FilePath $PythonExec -ArgumentList "-m uvicorn app.main:app --reload --port 8000" -WorkingDirectory $BackendDir -PassThru

Write-Host "[Frontend] Starting Vite development server on http://localhost:5173 ..." -ForegroundColor Green
$FrontendProcess = Start-Process -FilePath "npm.cmd" -ArgumentList "run dev" -WorkingDirectory $FrontendDir -PassThru

Write-Host ""
Write-Host "MediFlux services initiated successfully:" -ForegroundColor Cyan
Write-Host "  - Backend API:    http://localhost:8000/docs" -ForegroundColor White
Write-Host "  - Health Check:   http://localhost:8000/health" -ForegroundColor White
Write-Host "  - Frontend Web:   http://localhost:5173" -ForegroundColor White
Write-Host ""
Write-Host "Press Ctrl+C to stop all services..." -ForegroundColor Gray

try {
    while ($true) {
        Start-Sleep -Seconds 1
        if ($BackendProcess.HasExited -or $FrontendProcess.HasExited) {
            Write-Host "One of the services terminated unexpectedly." -ForegroundColor Red
            break
        }
    }
} finally {
    Write-Host "Stopping MediFlux background processes..." -ForegroundColor Yellow
    if ($BackendProcess -and -not $BackendProcess.HasExited) {
        Stop-Process -Id $BackendProcess.Id -Force -ErrorAction SilentlyContinue
    }
    if ($FrontendProcess -and -not $FrontendProcess.HasExited) {
        Stop-Process -Id $FrontendProcess.Id -Force -ErrorAction SilentlyContinue
    }
    Write-Host "All processes stopped cleanly." -ForegroundColor Green
}


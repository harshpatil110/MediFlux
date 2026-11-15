# ===================================================
#   MediFlux / NexusChain OpenAPI TypeScript Generator
# ===================================================

$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $RootDir

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "  MediFlux OpenAPI TypeScript Client Generator     " -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan

$PythonExe = Join-Path $RootDir "backend\venv\Scripts\python.exe"
if (-not (Test-Path $PythonExe)) {
    $PythonExe = "python"
}

& $PythonExe (Join-Path $RootDir "scripts\gen_api.py")

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n[SUCCESS] OpenAPI TypeScript schemas successfully generated!" -ForegroundColor Green
} else {
    Write-Host "`n[ERROR] Code generation failed with exit code $LASTEXITCODE" -ForegroundColor Red
    exit $LASTEXITCODE
}


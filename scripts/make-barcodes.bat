@echo off
REM MediFlux - Barcode Generator Script
setlocal
cd /d "%~dp0\.."
if exist "backend\venv\Scripts\python.exe" (
    backend\venv\Scripts\python.exe scripts\make_barcodes.py %*
) else (
    python scripts\make_barcodes.py %*
)
endlocal

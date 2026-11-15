@echo off
setlocal
echo ===================================================
echo   MediFlux / NexusChain OpenAPI TypeScript Generator
echo ===================================================

cd /d "%~dp0\.."

if exist "backend\venv\Scripts\python.exe" (
    "backend\venv\Scripts\python.exe" scripts\gen_api.py
) else (
    python scripts\gen_api.py
)

if %ERRORLEVEL% EQU 0 (
    echo [SUCCESS] OpenAPI schemas synchronized to shared, mobile, and frontend.
) else (
    echo [ERROR] OpenAPI code generation failed with code %ERRORLEVEL%.
)
exit /b %ERRORLEVEL%

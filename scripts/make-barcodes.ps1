# MediFlux - Barcode Generator PowerShell Script
[CmdletBinding()]
param()

$ProjectRoot = Resolve-Path "$PSScriptRoot\.."
Set-Location $ProjectRoot

$VenvPython = Join-Path $ProjectRoot "backend\venv\Scripts\python.exe"
if (Test-Path $VenvPython) {
    & $VenvPython "scripts\make_barcodes.py" $args
} else {
    python "scripts\make_barcodes.py" $args
}

param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$DataDir = '',
    [string]$UploadDir = ''
)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $ProjectRoot
if ($DataDir) { $env:PIZZA_PRONTO_DATA_DIR = $DataDir }
if ($UploadDir) { $env:PIZZA_PRONTO_UPLOAD_DIR = $UploadDir }
$projectPython = Join-Path $ProjectRoot '.venv/Scripts/python.exe'
& $projectPython -m backend.maintenance backup
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

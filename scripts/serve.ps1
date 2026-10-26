# Serves the built SPA + API with waitress (production-style, single process).
#
# NOTE: keep this file ASCII-only.
param(
    [string]$Listen = '0.0.0.0:8000',
    [int]$Threads = 8
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

$env:TMP = Join-Path $root '.tmp'
$env:TEMP = $env:TMP
New-Item -ItemType Directory -Force -Path $env:TMP | Out-Null
$env:PYTHONPATH = @(
    (Join-Path $root '.devshim'),
    (Join-Path $root '.pylibs'),
    (Join-Path $root 'backend')
) -join ';'

if (-not (Test-Path (Join-Path $root 'frontend\dist\index.html'))) {
    Write-Warning 'frontend\dist not found - run scripts\build-frontend.ps1 first. Serving API only.'
}

Push-Location (Join-Path $root 'backend')
try {
    & python -m waitress --listen=$Listen --threads=$Threads wsgi:app
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}

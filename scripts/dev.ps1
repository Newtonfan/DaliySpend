# Runs a Python command with the sandbox-friendly environment used by this repo.
#
#   scripts\dev.ps1 -m pytest backend\tests
#   scripts\dev.ps1 -m flask --app wsgi run --port 5000
#
# .pylibs holds the installed dependencies (see scripts\bootstrap.ps1), and
# .devshim fixes the Python 3.13 Windows temp-directory ACL problem inside the
# DSH sandbox.
#
# NOTE: keep this file ASCII-only. Windows PowerShell 5.1 reads BOM-less files
# as ANSI and multi-byte characters break the parser.
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArgs
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

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw 'python is not installed or not on PATH'
}

Push-Location -Path (Join-Path $root 'backend')
try {
    & python @RemainingArgs
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}

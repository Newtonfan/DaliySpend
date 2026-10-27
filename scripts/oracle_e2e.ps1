# One-shot Oracle verification.
#
#   scripts\oracle_e2e.ps1 -Url 'oracle+oracledb://dailyspend:pwd@localhost:1521/?service_name=FREEPDB1'
#   scripts\oracle_e2e.ps1 -Url <app-url> -TestUrl <throwaway-url> -IncludeBrowser
#
# Steps:
#   1. flask db upgrade against -Url (creates the schema)
#   2. scripts\oracle_check.py (version / user / tables / row counts)
#   3. pytest tests\test_oracle_live.py against -TestUrl (destructive: drop/create)
#   4. optional browser smoke against -TestUrl
#
# NOTE: keep this file ASCII-only.
param(
    [Parameter(Mandatory = $true)][string]$Url,
    [string]$TestUrl = '',
    [switch]$IncludeBrowser
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root 'backend'

$env:TMP = Join-Path $root '.tmp'
$env:TEMP = $env:TMP
New-Item -ItemType Directory -Force -Path $env:TMP | Out-Null
$env:PYTHONPATH = @(
    (Join-Path $root '.devshim'),
    (Join-Path $root '.pylibs'),
    $backend
) -join ';'

function Invoke-Python {
    param([string[]]$Arguments)
    Push-Location $backend
    try {
        & python @Arguments
        $code = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
    if ($code -ne 0) { throw ("python {0} failed with {1}" -f ($Arguments -join ' '), $code) }
}

Write-Output '=== 1/4 flask db upgrade (application schema) ==='
$env:DS_DATABASE_URL = $Url
Remove-Item Env:DS_ORACLE_TEST_URL -ErrorAction SilentlyContinue
Invoke-Python @('-m', 'flask', '--app', 'wsgi:app', 'db', 'upgrade')

Write-Output '=== 2/4 oracle_check.py (read-only inspection) ==='
Invoke-Python @((Join-Path $root 'scripts\oracle_check.py'))

if ($TestUrl) {
    Write-Output '=== 3/4 pytest tests\test_oracle_live.py (destructive, throw-away schema) ==='
    $env:DS_ORACLE_TEST_URL = $TestUrl
    Invoke-Python @('-m', 'pytest', 'tests\test_oracle_live.py', '-v', '--tb=short')

    if ($IncludeBrowser) {
        Write-Output '=== 4/4 browser smoke against Oracle ==='
        $env:E2E_DATABASE_URL = $TestUrl
        $env:E2E_ALLOW_DESTRUCTIVE = '1'
        & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $root 'scripts\dev.ps1') '..\scripts\e2e_smoke.py'
        if ($LASTEXITCODE -ne 0) { throw "browser smoke failed with $LASTEXITCODE" }
    }
    else {
        Write-Output '=== 4/4 browser smoke skipped (pass -IncludeBrowser) ==='
    }
}
else {
    Write-Output '=== 3/4 and 4/4 skipped (pass -TestUrl <throwaway-url>) ==='
}

Write-Output 'Oracle verification finished.'

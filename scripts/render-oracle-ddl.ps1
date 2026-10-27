# Renders the Alembic migrations as Oracle DDL (offline mode, no database needed)
# and writes docs\oracle-schema.sql.  Re-run this after changing models or
# migrations so the committed schema snapshot never drifts.
#
# NOTE: keep this file ASCII-only.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root 'backend'
$target = Join-Path $root 'docs\oracle-schema.sql'
$raw = Join-Path $root '.tmp\oracle_ddl.sql'

$env:TMP = Join-Path $root '.tmp'
$env:TEMP = $env:TMP
New-Item -ItemType Directory -Force -Path $env:TMP | Out-Null
$env:PYTHONPATH = @(
    (Join-Path $root '.devshim'),
    (Join-Path $root '.pylibs'),
    $backend
) -join ';'

# The URL only has to look like Oracle: offline mode never connects.
$env:DS_DATABASE_URL = 'oracle+oracledb://dailyspend:offline-render@localhost:1521/?service_name=FREEPDB1'

Push-Location $backend
try {
    $err = Join-Path $root '.tmp\oracle_ddl.err'
    # Run through cmd: PowerShell 5.1 turns native stderr into an error record,
    # which would abort this script before the exit code is checked.
    $command = 'python -m flask --app wsgi:app db upgrade --sql > "' + $raw + '" 2> "' + $err + '"'
    cmd /c $command
    if ($LASTEXITCODE -ne 0) { throw "flask db upgrade --sql failed with $LASTEXITCODE" }
}
finally {
    Pop-Location
    Remove-Item Env:DS_DATABASE_URL -ErrorAction SilentlyContinue
}

$header = @(
    '-- DailySpend: Oracle DDL rendered by Alembic in offline mode.',
    '--',
    '-- Regenerate after changing models or migrations:',
    '--     scripts\render-oracle-ddl.ps1',
    '--',
    '-- Apply it by hand (instead of `flask db upgrade`) if you prefer SQL*Plus:',
    '--     sqlplus dailyspend/pwd@//localhost:1521/FREEPDB1 @docs/oracle-schema.sql',
    '--',
    '-- Notes',
    '--   * targets Oracle 23ai (native BOOLEAN); on 19c SQLAlchemy emits NUMBER(1)',
    '--   * identifiers are lowercase and quoted by SQLAlchemy, so raw SQL must quote them',
    '--   * generated file: do not edit by hand',
    '--   * "/" terminates each statement (SQL*Plus / SQLcl requirement)',
    ''
)

$body = Get-Content $raw -Encoding utf8
$lines = $header + $body
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllLines($target, $lines, $utf8NoBom)

Write-Output ("wrote {0} ({1} lines)" -f $target, $lines.Count)

# Installs the Python dependencies into .pylibs (workspace-local, no venv needed
# because the DSH sandbox blocks the piped subprocess that `python -m venv` uses).
#
# NOTE: keep this file ASCII-only.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot

$env:TMP = Join-Path $root '.tmp'
$env:TEMP = $env:TMP
New-Item -ItemType Directory -Force -Path $env:TMP | Out-Null
$env:PYTHONPATH = Join-Path $root '.devshim'

& python -m pip install --no-cache-dir --disable-pip-version-check --target (Join-Path $root '.pylibs') -r (Join-Path $root 'requirements.txt')
exit $LASTEXITCODE

# Builds the Vue frontend into frontend\dist, or starts the Vite dev server
# when called with -Dev.
#
# NOTE: keep this file ASCII-only.
param(
    [switch]$Dev
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$frontend = Join-Path $root 'frontend'
$bundledNode = Join-Path $root '.tools\node'

if (Test-Path $bundledNode) {
    $env:PATH = "$bundledNode;$env:PATH"
}

$env:TMP = Join-Path $root '.tmp'
$env:TEMP = $env:TMP
New-Item -ItemType Directory -Force -Path $env:TMP | Out-Null
$env:npm_config_cache = Join-Path $env:TMP 'npm-cache'
$env:npm_config_registry = 'https://registry.npmmirror.com'
$env:npm_config_fetch_timeout = '180000'
$env:npm_config_fetch_retries = '5'
$env:npm_config_update_notifier = 'false'
$env:npm_config_fund = 'false'
$env:npm_config_audit = 'false'

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    throw 'node not found. Unzip the official Node LTS build into .tools\node first.'
}

Push-Location $frontend
try {
    if (-not (Test-Path 'node_modules')) {
        & npm.cmd install --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) { throw "npm install failed with $LASTEXITCODE" }
    }
    if ($Dev) {
        & npm.cmd run dev
    } else {
        & npm.cmd run build
    }
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}

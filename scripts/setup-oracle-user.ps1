# Creates the Oracle schema users for DailySpend by prompting for the SYSTEM/SYS
# password.  Uses the thin driver, so it works even though `sqlplus / as sysdba`
# is blocked by ORA-12241 on this machine.
#
#   scripts\setup-oracle-user.ps1
#   scripts\setup-oracle-user.ps1 -WriteEnv            # also append .env
#   scripts\setup-oracle-user.ps1 -SysUser SYS -Sysdba # use SYS AS SYSDBA
#
# NOTE: keep this file ASCII-only.
param(
    [string]$SysUser = 'SYSTEM',
    [string]$Connect = '//localhost:1521/FREEPDB1',
    [switch]$Sysdba,
    [switch]$WriteEnv
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

$secure = Read-Host -Prompt ("Password for {0}" -f $SysUser) -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}

# Passed through the environment so the password never appears in argv.
$env:ORA_SYS_USER = $SysUser
$env:ORA_SYS_PASSWORD = $plain
$env:ORA_CONNECT = $Connect
if ($Sysdba) { $env:ORA_SYS_MODE = 'SYSDBA' } else { Remove-Item Env:ORA_SYS_MODE -ErrorAction SilentlyContinue }
if ($WriteEnv) { $env:ORA_WRITE_ENV = '1' } else { Remove-Item Env:ORA_WRITE_ENV -ErrorAction SilentlyContinue }

try {
    & python (Join-Path $root 'scripts\create_oracle_users.py')
    exit $LASTEXITCODE
}
finally {
    Remove-Item Env:ORA_SYS_PASSWORD -ErrorAction SilentlyContinue
    Remove-Item Env:ORA_SYS_USER -ErrorAction SilentlyContinue
    Remove-Item Env:ORA_CONNECT -ErrorAction SilentlyContinue
    Remove-Item Env:ORA_SYS_MODE -ErrorAction SilentlyContinue
    Remove-Item Env:ORA_WRITE_ENV -ErrorAction SilentlyContinue
}

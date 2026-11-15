$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
if (Test-Path -LiteralPath '.env') { throw '.env already exists. Existing configuration was not changed.' }
function New-RandomHex([int]$Length) {
    $bytes = New-Object byte[] $Length
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $rng.GetBytes($bytes) } finally { $rng.Dispose() }
    return [BitConverter]::ToString($bytes).Replace('-', '')
}
$template = Get-Content -LiteralPath '.env.example' -Raw
$config = $template.Replace('replace-with-a-long-random-secret', (New-RandomHex 48)).Replace('replace-with-a-random-password', (New-RandomHex 24))
[System.IO.File]::WriteAllText((Join-Path (Get-Location) '.env'), $config, (New-Object System.Text.UTF8Encoding($false)))
Write-Output 'Created .env for a NEW local installation. LAN HTTPS requires additional host and certificate settings.'

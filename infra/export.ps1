$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
New-Item -ItemType Directory -Force dist-release/infra | Out-Null
docker image save -o dist-release/images.tar nachat-app:0.1.0 nachat-web:0.1.0 postgres:17.7-alpine redis:7.4.7-alpine
if ($LASTEXITCODE -ne 0) { throw 'Image export failed' }
Copy-Item compose.yaml,compose.lan.yaml,.env.example,README.md dist-release/
Copy-Item infra/nginx.tls.conf,infra/backup.sh,infra/restore.sh,infra/backup.ps1,infra/restore.ps1 dist-release/infra/
docker compose images --format json | Set-Content dist-release/images.json
Get-FileHash dist-release/images.tar | Select-Object Algorithm,Hash | ConvertTo-Json | Set-Content dist-release/checksum.json
Write-Output 'Portable release saved to dist-release/'

$ErrorActionPreference = 'Stop'
Set-Location (Join-Path $PSScriptRoot '..')
$backupDir = Join-Path (Get-Location) ('backups/' + (Get-Date -Format 'yyyyMMddTHHmmss'))
New-Item -ItemType Directory -Path $backupDir | Out-Null
docker compose stop proxy app
if ($LASTEXITCODE -ne 0) { throw 'Could not stop application' }
try {
    docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc -f /tmp/nachat-backup.dump'
    if ($LASTEXITCODE -ne 0) { throw 'Database backup failed' }
    docker compose cp db:/tmp/nachat-backup.dump (Join-Path $backupDir 'database.dump')
    if ($LASTEXITCODE -ne 0) { throw 'Database copy failed' }
    docker compose run --rm --no-deps -v "${backupDir}:/backup" app python -c "import tarfile; t=tarfile.open('/backup/media.tar.gz','w:gz'); t.add('/data/media',arcname='.'); t.close()"
    if ($LASTEXITCODE -ne 0) { throw 'Attachment backup failed' }
    docker compose images --format json | Set-Content (Join-Path $backupDir 'images.json')
    Write-Output "Backup saved: $backupDir"
} finally {
    docker compose start app proxy
}

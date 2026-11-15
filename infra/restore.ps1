param([Parameter(Mandatory=$true)][string]$BackupDirectory,[string]$RestoreProject='nachat-restore')
$ErrorActionPreference='Stop'
Set-Location (Join-Path $PSScriptRoot '..')
if ($RestoreProject -eq 'nachat' -or $RestoreProject -notmatch '^nachat-restore[-a-z0-9]*$') { throw 'Use a new nachat-restore project name' }
$restoreDir=(Resolve-Path -LiteralPath $BackupDirectory).Path
if (!(Test-Path -LiteralPath (Join-Path $restoreDir 'database.dump')) -or !(Test-Path -LiteralPath (Join-Path $restoreDir 'media.tar.gz'))) { throw 'Backup files missing' }
docker compose -p $RestoreProject up -d --wait db redis
if ($LASTEXITCODE -ne 0) { throw 'Target startup failed' }
$tables=docker compose -p $RestoreProject exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT count(*) FROM pg_tables WHERE schemaname = current_schema()"'
if ($LASTEXITCODE -ne 0 -or $tables.Trim() -ne '0') { throw 'Target database is not empty; refusing to overwrite' }
docker compose -p $RestoreProject cp (Join-Path $restoreDir 'database.dump') db:/tmp/restore.dump
if ($LASTEXITCODE -ne 0) { throw 'Copy failed' }
docker compose -p $RestoreProject exec -T db sh -c 'pg_restore --exit-on-error --no-owner -U "$POSTGRES_USER" -d "$POSTGRES_DB" /tmp/restore.dump'
if ($LASTEXITCODE -ne 0) { throw 'Database restore failed' }
docker compose -p $RestoreProject run --rm --no-deps -v "${restoreDir}:/restore:ro" app python -c "import tarfile; t=tarfile.open('/restore/media.tar.gz'); t.extractall('/data/media',filter='data'); t.close()"
if ($LASTEXITCODE -ne 0) { throw 'Attachment restore failed' }
Write-Output "Restored into $RestoreProject. Assign a separate port before starting its proxy."

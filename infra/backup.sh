#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
umask 077
destination="$(pwd)/backups/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$destination"
docker compose stop proxy app
trap 'docker compose start app proxy' EXIT
docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$destination/database.dump"
docker compose run --rm --no-deps -T app tar -C /data/media -czf - . > "$destination/media.tar.gz"
docker compose images --format json > "$destination/images.json"
printf 'Backup: %s\nCopy this folder to a separate host. Store .env and TLS keys separately.\n' "$destination"

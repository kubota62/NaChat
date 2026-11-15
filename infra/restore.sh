#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source_dir="$(realpath "${1:?Usage: bash infra/restore.sh /absolute/backup/path}")"
test -f "$source_dir/database.dump"
test -f "$source_dir/media.tar.gz"
# Restore only into an empty, separately named Compose project.
: "${COMPOSE_PROJECT_NAME:?Set a NEW COMPOSE_PROJECT_NAME for restore}"
if [ "$COMPOSE_PROJECT_NAME" = nachat ]; then echo 'Use a new project name, not nachat'; exit 1; fi
docker compose up -d --wait db redis
count="$(docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Atc "SELECT count(*) FROM pg_tables WHERE schemaname = current_schema()"')"
if [ "$count" != 0 ]; then echo 'Target database is not empty; refusing to overwrite'; exit 1; fi
docker compose exec -T db sh -c 'pg_restore --exit-on-error --no-owner -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < "$source_dir/database.dump"
docker compose run --rm --no-deps -T app tar -C /data/media -xzf - < "$source_dir/media.tar.gz"
echo 'Restored. Verify data, configure a free port and TLS, then start the application.'

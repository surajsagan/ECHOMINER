#!/usr/bin/env bash
# Compressed logical backup of the database. Keeps the newest 14 dumps.
# Usage: infra/scripts/backup.sh [label]
set -euo pipefail
cd "$(dirname "$0")/../.."
DEST=/var/backups/echominer
mkdir -p "$DEST"
set -a; . ./.env.deploy; set +a
stamp=$(date -u +%Y%m%dT%H%M%SZ)
file="$DEST/echominer-${stamp}${1:+-$1}.sql.gz"
docker compose -f infra/compose/docker-compose.yml --env-file .env.deploy exec -T postgres \
  pg_dump -U "${POSTGRES_USER:-echominer}" -d "${POSTGRES_DB:-echominer}" --no-owner --clean --if-exists \
  | gzip -9 > "$file"
[ -s "$file" ] || { echo "backup is empty" >&2; rm -f "$file"; exit 1; }
ls -1t "$DEST"/echominer-*.sql.gz | tail -n +15 | xargs -r rm -f
echo "$file"

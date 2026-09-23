#!/usr/bin/env bash
# Restores a dump produced by backup.sh. DESTRUCTIVE: replaces current data.
# Usage: infra/scripts/restore.sh /var/backups/echominer/echominer-XXXX.sql.gz
set -euo pipefail
cd "$(dirname "$0")/../.."
file=${1:?path to .sql.gz}
set -a; . ./.env.deploy; set +a
read -r -p "Replace the live database with $(basename "$file")? Type RESTORE: " ok
[ "$ok" = "RESTORE" ] || { echo "aborted"; exit 1; }
C="docker compose -f infra/compose/docker-compose.yml --env-file .env.deploy"
$C stop api worker
gunzip -c "$file" | $C exec -T postgres psql -v ON_ERROR_STOP=1 -q \
  -U "${POSTGRES_USER:-echominer}" -d "${POSTGRES_DB:-echominer}"
$C start api worker
echo "restored $(basename "$file")"

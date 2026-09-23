#!/usr/bin/env bash
# Deploys origin/main on the server: safety backup -> build -> migrate -> restart
# -> smoke test -> automatic rollback of the code if the smoke test fails.
# Run on the server from the repo directory (GitHub Actions does this over SSH).
set -euo pipefail
cd "$(dirname "$0")/../.."
C="docker compose -f infra/compose/docker-compose.yml --env-file .env.deploy"

smoke() {
  for _ in $(seq 1 30); do
    if curl -fsS -o /dev/null --resolve echominer.in:443:127.0.0.1 -k https://echominer.in/readyz \
       && curl -fsS -o /dev/null --resolve echominer.in:443:127.0.0.1 -k https://echominer.in/; then
      return 0
    fi
    sleep 4
  done
  return 1
}

previous=$(git rev-parse HEAD)
git fetch --quiet origin main
target=$(git rev-parse origin/main)
echo "==> deploying ${target:0:7} (was ${previous:0:7})"

if $C ps --status running postgres | grep -q postgres; then
  echo "==> safety backup"
  infra/scripts/backup.sh "pre-${target:0:7}"
fi

git reset --hard --quiet "$target"
$C build
$C up -d --remove-orphans

echo "==> smoke test"
if smoke; then
  docker image prune -f >/dev/null
  echo "==> deployed ${target:0:7}"
  exit 0
fi

echo "!! smoke test failed -- rolling code back to ${previous:0:7}" >&2
$C logs --tail 80 api worker web nginx >&2 || true
git reset --hard --quiet "$previous"
$C build && $C up -d --remove-orphans
echo "!! rolled back. If a migration ran, see docs/DEPLOYMENT.md > Rollback." >&2
exit 1

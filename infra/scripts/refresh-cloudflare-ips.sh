#!/usr/bin/env bash
# Regenerates the Cloudflare range lists used by nginx, then reloads nginx.
set -euo pipefail
cd "$(dirname "$0")/../nginx"
v4=$(curl -fsS https://www.cloudflare.com/ips-v4/); v6=$(curl -fsS https://www.cloudflare.com/ips-v6/)
[ -n "$v4" ] && [ -n "$v6" ] || { echo "empty list from cloudflare; aborting" >&2; exit 1; }
{ echo "# Cloudflare edge ranges (https://www.cloudflare.com/ips/). Refreshed $(date -u +%F)"
  for r in $v4 $v6; do echo "set_real_ip_from $r;"; done; } > cloudflare-ips.inc
{ echo "# Cloudflare edge ranges for the origin lock. Refreshed $(date -u +%F)"
  for r in $v4 $v6; do echo "$r 1;"; done; } > cloudflare-geo.inc
cd ../..
docker compose -f infra/compose/docker-compose.yml --env-file .env.deploy exec -T nginx nginx -t
docker compose -f infra/compose/docker-compose.yml --env-file .env.deploy exec -T nginx nginx -s reload
echo "cloudflare ranges refreshed"

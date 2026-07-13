#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT_DIR"
file="${1:-}"
[[ -n "$file" && -f "$file" && -s "$file" ]] || { echo "A non-empty backup file is required" >&2; exit 1; }
read -r -p "Type RESTORE to replace the current database: " confirmation
[[ "$confirmation" == "RESTORE" ]] || { echo "Restore cancelled"; exit 0; }

docker compose stop bot api
docker compose up -d postgres
for attempt in $(seq 1 30); do
  docker compose exec -T postgres sh -c \
    'pg_isready -U "$POSTGRES_USER" -d "$POSTGRES_DB"' >/dev/null 2>&1 && break
  [[ "$attempt" == 30 ]] && { echo "PostgreSQL not ready" >&2; exit 1; }
  sleep 2
done
docker compose exec -T postgres sh -c \
  'exec psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  <"$file"
docker compose up -d api bot frontend || {
  echo "Application services failed to start after restore" >&2
  exit 1
}
for attempt in $(seq 1 60); do
  docker compose exec -T api python -c \
    "import urllib.request; urllib.request.urlopen('http://localhost:8000/ready', timeout=2)" \
    >/dev/null 2>&1 && exit 0
  [[ "$attempt" == 60 ]] && {
    echo "API/database readiness failed after restore" >&2
    exit 1
  }
  sleep 2
done

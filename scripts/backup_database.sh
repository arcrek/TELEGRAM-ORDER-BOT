#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT_DIR"
umask 077
mkdir -p backups
name="${1:-backup_$(date -u +%Y%m%d_%H%M%S)}"
[[ "$name" =~ ^[A-Za-z0-9._-]+$ ]] || { echo "Invalid backup name" >&2; exit 1; }
target="backups/${name}.sql"
tmp="$(mktemp "backups/.${name}.sql.tmp.XXXXXX")"
trap 'rm -f "$tmp"' EXIT

docker compose exec -T postgres sh -c \
  'exec pg_dump -U "$POSTGRES_USER" --clean --if-exists "$POSTGRES_DB"' \
  >"$tmp"
[[ -s "$tmp" ]] || { echo "Backup is empty" >&2; exit 1; }
mv "$tmp" "$target"
trap - EXIT
printf '%s\n' "$target"

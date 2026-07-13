#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT_DIR"

tracked_env="$(git ls-files -- '.env*')"
while IFS= read -r path; do
  if [[ -n "$path" && "$path" != ".env.example" ]]; then
    echo "Tracked private artifact matches: .env*" >&2
    exit 1
  fi
done <<<"$tracked_env"

for forbidden in '*.db' '*.sqlite' '*.sql' '*.dump' '*.pem' '*.key' 'backups/*' 'data/*' '.claude/*'; do
  tracked="$(git ls-files -- "$forbidden")"
  if [[ -n "$tracked" ]]; then
    echo "Tracked private artifact matches: $forbidden" >&2
    exit 1
  fi
done

docker run --rm -v "$ROOT_DIR:/repo" zricethezav/gitleaks:v8.30.1 \
  dir /repo --redact --no-banner

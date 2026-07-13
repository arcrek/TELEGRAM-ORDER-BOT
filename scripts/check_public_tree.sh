#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT_DIR"

for forbidden in .env '*.db' '*.sqlite' '*.sql' '*.dump' '*.pem' '*.key' 'backups/*' 'data/*' '.claude/*'; do
  if [[ -n "$(git ls-files -- "$forbidden")" ]]; then
    echo "Tracked private artifact matches: $forbidden" >&2
    exit 1
  fi
done

docker run --rm -v "$ROOT_DIR:/repo" zricethezav/gitleaks:v8.30.1 \
  dir /repo --redact --no-banner

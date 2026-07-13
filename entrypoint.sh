#!/usr/bin/env bash
set -Eeuo pipefail

echo "Running database migrations..."
alembic upgrade head
echo "Starting application..."
exec "$@"

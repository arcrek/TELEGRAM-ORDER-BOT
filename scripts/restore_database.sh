#!/bin/bash
#
#
# PostgreSQL Database Restore Script for MTK Bot Order System
# Usage: ./scripts/restore_database.sh <backup_file.sql>
#
set -e

BACKUP_FILE="$1"

if [ -z "$BACKUP_FILE" ]; then
    echo "Error: Backup file not specified"
    echo "Usage: $0 <backup_file.sql>"
    exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: Backup file '$BACKUP_FILE' not found"
    exit 1
fi

SERVICE="postgres"
DB_NAME="${DB_NAME:-mtkbot}"
DB_USER="${DB_USER:-mtkbot}"

echo "=== MTK Bot Order System - PostgreSQL Restore ==="
echo "Service: $SERVICE"
echo "Database: $DB_NAME"
echo "Backup file: $BACKUP_FILE"
echo "WARNING: This will replace the current database!"
read -p "Are you sure you want to continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Restore cancelled"
    exit 0
fi

echo "Stopping application services..."
docker compose stop bot bot_supplier api || true

echo "Restoring database..."
BACKUP_ABS_PATH=$(realpath "$BACKUP_FILE")
BACKUP_DIR=$(dirname "$BACKUP_ABS_PATH")
BACKUP_NAME=$(basename "$BACKUP_ABS_PATH")

docker compose exec -T "$SERVICE" bash -c "psql -U \"$DB_USER\" -d \"$DB_NAME\" -f \"/backup/$BACKUP_NAME\"" \
  -v "${BACKUP_DIR}:/backup"

echo "Restore completed."

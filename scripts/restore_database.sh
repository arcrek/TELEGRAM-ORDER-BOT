#!/bin/bash
#
# PostgreSQL Database Restore Script for MTK Bot Order System
# Usage: ./scripts/restore_database.sh [dev|prod] <backup_file.sql>
#
set -e

ENVIRONMENT="${1:-dev}"
BACKUP_FILE="$2"

if [ -z "$BACKUP_FILE" ]; then
    echo "Error: Backup file not specified"
    echo "Usage: $0 [dev|prod] <backup_file.sql>"
    exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Error: Backup file '$BACKUP_FILE' not found"
    exit 1
fi

if [ "$ENVIRONMENT" = "prod" ]; then
    SERVICE="postgres-prod"
    DB_NAME="${PROD_DB_NAME:-mtkbot_prod}"
    DB_USER="${PROD_DB_USER:-mtkbot_prod}"
else
    SERVICE="postgres-dev"
    DB_NAME="${DEV_DB_NAME:-mtkbot_dev}"
    DB_USER="${DEV_DB_USER:-mtkbot_dev}"
fi

echo "=== MTK Bot Order System - PostgreSQL Restore ($ENVIRONMENT) ==="
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

#!/bin/bash
#
# PostgreSQL Database Backup Script for MTK Bot Order System
# Usage: ./scripts/backup_database.sh [dev|prod] [backup_name]
#
set -e

ENVIRONMENT="${1:-dev}"
BACKUP_DIR="./backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="${2:-backup_${ENVIRONMENT}_${TIMESTAMP}}"

mkdir -p "$BACKUP_DIR"

if [ "$ENVIRONMENT" = "prod" ]; then
    SERVICE="postgres-prod"
    DB_NAME="${PROD_DB_NAME:-mtkbot_prod}"
    DB_USER="${PROD_DB_USER:-mtkbot_prod}"
else
    SERVICE="postgres-dev"
    DB_NAME="${DEV_DB_NAME:-mtkbot_dev}"
    DB_USER="${DEV_DB_USER:-mtkbot_dev}"
fi

echo "=== MTK Bot Order System - PostgreSQL Backup ($ENVIRONMENT) ==="
echo "Service: $SERVICE"
echo "Database: $DB_NAME"
echo "Backup: $BACKUP_DIR/${BACKUP_NAME}.sql"
echo

docker compose exec "$SERVICE" pg_dump -U "$DB_USER" "$DB_NAME" > "${BACKUP_DIR}/${BACKUP_NAME}.sql"

echo "Backup completed: ${BACKUP_DIR}/${BACKUP_NAME}.sql"

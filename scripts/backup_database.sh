#!/bin/bash
#
#
# PostgreSQL Database Backup Script for MTK Bot Order System
# Usage: ./scripts/backup_database.sh [backup_name]
#
set -e

BACKUP_DIR="./backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="${1:-backup_${TIMESTAMP}}"

DB_NAME="${DB_NAME:-mtkbot}"
DB_USER="${DB_USER:-mtkbot}"
SERVICE="postgres"

mkdir -p "$BACKUP_DIR"

echo "=== MTK Bot Order System - PostgreSQL Backup ==="
echo "Service: $SERVICE"
echo "Database: $DB_NAME"
echo "Backup: $BACKUP_DIR/${BACKUP_NAME}.sql"
echo

docker compose exec "$SERVICE" pg_dump -U "$DB_USER" "$DB_NAME" > "${BACKUP_DIR}/${BACKUP_NAME}.sql"

echo "Backup completed: ${BACKUP_DIR}/${BACKUP_NAME}.sql"

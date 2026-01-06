#!/bin/bash
#
# Database Restore Script for MTK Bot Order System
# Usage: ./scripts/restore_database.sh <backup_file>
#
set -e

# Configuration
VOLUME_NAME="database-data"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== MTK Bot Order System - Database Restore ===${NC}"
echo ""

# Check if backup file is provided
if [ -z "$1" ]; then
    echo -e "${RED}Error: Backup file not specified${NC}"
    echo "Usage: $0 <backup_file>"
    echo ""
    echo "Available backups:"
    ls -lh ./backups/*.db 2>/dev/null | awk '{print "  " $9 " (" $5 ")"}'
    exit 1
fi

BACKUP_FILE="$1"

# Check if backup file exists
if [ ! -f "$BACKUP_FILE" ]; then
    echo -e "${RED}Error: Backup file '$BACKUP_FILE' not found${NC}"
    exit 1
fi

# Check if docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running${NC}"
    exit 1
fi

echo -e "${YELLOW}WARNING: This will replace the current database!${NC}"
echo "Backup file: $BACKUP_FILE"
echo ""
read -p "Are you sure you want to continue? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo -e "${YELLOW}Restore cancelled${NC}"
    exit 0
fi

echo ""
echo -e "${YELLOW}Stopping services...${NC}"
docker compose stop bot bot_supplier api

echo -e "${YELLOW}Restoring database...${NC}"

# Get absolute path of backup file
BACKUP_ABS_PATH=$(realpath "$BACKUP_FILE")
BACKUP_DIR=$(dirname "$BACKUP_ABS_PATH")
BACKUP_NAME=$(basename "$BACKUP_ABS_PATH")

# Restore backup using a temporary container
docker run --rm \
    -v ${VOLUME_NAME}:/data \
    -v "${BACKUP_DIR}:/backup" \
    busybox \
    cp /backup/${BACKUP_NAME} /data/database.db

echo -e "${GREEN}✓ Database restored successfully!${NC}"
echo ""
echo -e "${YELLOW}Starting services...${NC}"
docker compose up -d

echo ""
echo -e "${GREEN}Done! Services are starting up...${NC}"
echo "Wait a few seconds for services to be ready."


#!/bin/bash
#
# Database Backup Script for MTK Bot Order System
# Usage: ./scripts/backup_database.sh [backup_name]
#
set -e

# Configuration
BACKUP_DIR="./backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="${1:-backup_${TIMESTAMP}}"
VOLUME_NAME="database-data"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== MTK Bot Order System - Database Backup ===${NC}"
echo ""

# Create backup directory if it doesn't exist
mkdir -p "$BACKUP_DIR"

# Check if docker is running
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}Error: Docker is not running${NC}"
    exit 1
fi

# Check if volume exists
if ! docker volume inspect "$VOLUME_NAME" > /dev/null 2>&1; then
    echo -e "${RED}Error: Volume '$VOLUME_NAME' not found${NC}"
    exit 1
fi

echo -e "${YELLOW}Backing up database...${NC}"
echo "Volume: $VOLUME_NAME"
echo "Backup: $BACKUP_DIR/${BACKUP_NAME}.db"
echo ""

# Create backup using a temporary container
docker run --rm \
    -v ${VOLUME_NAME}:/data \
    -v "$(pwd)/${BACKUP_DIR}:/backup" \
    busybox \
    cp /data/database.db /backup/${BACKUP_NAME}.db

# Verify backup was created
if [ -f "$BACKUP_DIR/${BACKUP_NAME}.db" ]; then
    SIZE=$(du -h "$BACKUP_DIR/${BACKUP_NAME}.db" | cut -f1)
    echo -e "${GREEN}✓ Backup completed successfully!${NC}"
    echo "  File: $BACKUP_DIR/${BACKUP_NAME}.db"
    echo "  Size: $SIZE"
    echo ""
    
    # List all backups
    echo -e "${YELLOW}Available backups:${NC}"
    ls -lh "$BACKUP_DIR"/*.db 2>/dev/null | awk '{print "  " $9 " (" $5 ")"}'
else
    echo -e "${RED}✗ Backup failed!${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}Done!${NC}"


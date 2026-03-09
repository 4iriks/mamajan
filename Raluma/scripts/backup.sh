#!/bin/bash
# Backup SQLite database for Ралюма
# Usage: ./backup.sh
# Cron (daily at 03:00): 0 3 * * * /opt/mamajan/Raluma/scripts/backup.sh >> /var/log/raluma-backup.log 2>&1

set -e

DB_FILE="/opt/mamajan/Raluma/backend/raluma.db"
BACKUP_DIR="/opt/mamajan/backups"
KEEP_DAYS=30
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/raluma_${TIMESTAMP}.db"

# Create backup dir if needed
mkdir -p "$BACKUP_DIR"

# Check source exists
if [ ! -f "$DB_FILE" ]; then
    echo "[$(date)] ERROR: DB file not found: $DB_FILE"
    exit 1
fi

# Copy DB (SQLite is safe to copy while app is running — WAL mode)
cp "$DB_FILE" "$BACKUP_FILE"
echo "[$(date)] Backup created: $BACKUP_FILE ($(du -h "$BACKUP_FILE" | cut -f1))"

# Remove backups older than KEEP_DAYS days
DELETED=$(find "$BACKUP_DIR" -name "raluma_*.db" -mtime +$KEEP_DAYS -print -delete | wc -l)
if [ "$DELETED" -gt 0 ]; then
    echo "[$(date)] Removed $DELETED old backup(s)"
fi

TOTAL=$(find "$BACKUP_DIR" -name "raluma_*.db" | wc -l)
echo "[$(date)] Total backups: $TOTAL"

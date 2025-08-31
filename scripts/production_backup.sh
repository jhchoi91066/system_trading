#!/bin/bash

# Production Backup System
# 🚀 Phase 16: Final Production Deployment

set -euo pipefail

# Configuration
BACKUP_DIR="/app/backups"
DATE=$(date +%Y%m%d_%H%M%S)
DB_NAME="trading_bot_prod"
DB_USER="tradingbot_prod"
S3_BUCKET="your-backup-bucket"
RETENTION_DAYS=30

# Logging
LOG_FILE="/app/logs/backup_${DATE}.log"
exec 1> >(tee -a "$LOG_FILE")
exec 2>&1

echo "🔄 Starting production backup: $DATE"

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Database Backup
echo "📊 Creating database backup..."
pg_dump -h postgres -U "$DB_USER" -d "$DB_NAME" \
    --format=custom \
    --compress=9 \
    --verbose \
    --file="$BACKUP_DIR/db_backup_$DATE.dump"

if [ $? -eq 0 ]; then
    echo "✅ Database backup completed successfully"
else
    echo "❌ Database backup failed"
    exit 1
fi

# Application Data Backup
echo "📁 Creating application data backup..."
tar -czf "$BACKUP_DIR/app_data_$DATE.tar.gz" \
    -C /app \
    --exclude='backups' \
    --exclude='logs/*.log' \
    --exclude='*.pyc' \
    --exclude='__pycache__' \
    data/ config/ logs/

if [ $? -eq 0 ]; then
    echo "✅ Application data backup completed successfully"
else
    echo "❌ Application data backup failed"
    exit 1
fi

# Configuration Backup
echo "⚙️ Creating configuration backup..."
tar -czf "$BACKUP_DIR/config_backup_$DATE.tar.gz" \
    -C /app \
    config/ \
    docker/ \
    sql/ \
    scripts/

# Upload to S3 (if configured)
if command -v aws &> /dev/null && [ -n "${AWS_ACCESS_KEY_ID:-}" ]; then
    echo "☁️ Uploading backups to S3..."
    
    aws s3 cp "$BACKUP_DIR/db_backup_$DATE.dump" \
        "s3://$S3_BUCKET/database/" \
        --storage-class STANDARD_IA
        
    aws s3 cp "$BACKUP_DIR/app_data_$DATE.tar.gz" \
        "s3://$S3_BUCKET/application/" \
        --storage-class STANDARD_IA
        
    aws s3 cp "$BACKUP_DIR/config_backup_$DATE.tar.gz" \
        "s3://$S3_BUCKET/configuration/" \
        --storage-class STANDARD_IA
        
    echo "✅ S3 upload completed successfully"
fi

# Cleanup old local backups
echo "🧹 Cleaning up old backups (older than $RETENTION_DAYS days)..."
find "$BACKUP_DIR" -name "*.dump" -mtime +$RETENTION_DAYS -delete
find "$BACKUP_DIR" -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete

# Verify backup integrity
echo "🔍 Verifying backup integrity..."
if pg_restore --list "$BACKUP_DIR/db_backup_$DATE.dump" > /dev/null 2>&1; then
    echo "✅ Database backup integrity verified"
else
    echo "❌ Database backup integrity check failed"
    exit 1
fi

if tar -tzf "$BACKUP_DIR/app_data_$DATE.tar.gz" > /dev/null 2>&1; then
    echo "✅ Application data backup integrity verified"
else
    echo "❌ Application data backup integrity check failed"
    exit 1
fi

# Calculate backup sizes
DB_SIZE=$(du -h "$BACKUP_DIR/db_backup_$DATE.dump" | cut -f1)
APP_SIZE=$(du -h "$BACKUP_DIR/app_data_$DATE.tar.gz" | cut -f1)
CONFIG_SIZE=$(du -h "$BACKUP_DIR/config_backup_$DATE.tar.gz" | cut -f1)

echo "📈 Backup Summary:"
echo "   Database: $DB_SIZE"
echo "   Application Data: $APP_SIZE"
echo "   Configuration: $CONFIG_SIZE"
echo "   Total Backups: $(ls -1 $BACKUP_DIR | wc -l)"

# Send success notification
curl -X POST "${WEBHOOK_URL:-}" \
    -H "Content-Type: application/json" \
    -d "{
        \"text\": \"✅ Production backup completed successfully\",
        \"attachments\": [{
            \"color\": \"good\",
            \"fields\": [
                {\"title\": \"Database\", \"value\": \"$DB_SIZE\", \"short\": true},
                {\"title\": \"Application\", \"value\": \"$APP_SIZE\", \"short\": true},
                {\"title\": \"Configuration\", \"value\": \"CONFIG_SIZE\", \"short\": true},
                {\"title\": \"Timestamp\", \"value\": \"$DATE\", \"short\": true}
            ]
        }]
    }" 2>/dev/null || true

echo "🎉 Production backup completed successfully: $DATE"
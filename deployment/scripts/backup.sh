#!/bin/bash
# =============================================================================
# Mesob Inventory Management System - Backup Script
# =============================================================================
#
# Comprehensive backup script that backs up:
#   - PostgreSQL database
#   - Odoo filestore (attachments, uploads)
#   - Configuration files
#
# Usage:
#   ./scripts/backup.sh [backup_name]
#
# Backup Structure:
#   /backups/
#     ├── daily/     (7 days retention)
#     ├── weekly/    (4 weeks retention)
#     └── monthly/   (12 months retention)
#
# =============================================================================

set -euo pipefail
IFS=$'\n\t'

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOYMENT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$DEPLOYMENT_DIR/.env"

# Load environment variables
if [[ -f "$ENV_FILE" ]]; then
    source "$ENV_FILE"
fi

BACKUP_BASE_DIR="${BACKUP_DIR:-/opt/mesob-inventory/backups}"
BACKUP_NAME="${1:-mesob_inventory_$(date +%Y%m%d_%H%M%S)}"
TEMP_DIR="/tmp/mesob_backup_$$"

# Retention settings
DAILY_RETENTION="${BACKUP_RETENTION_DAILY:-7}"
WEEKLY_RETENTION="${BACKUP_RETENTION_WEEKLY:-4}"
MONTHLY_RETENTION="${BACKUP_RETENTION_MONTHLY:-12}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

log_info() {
    echo -e "${BLUE}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

log_error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

cleanup() {
    if [[ -d "$TEMP_DIR" ]]; then
        rm -rf "$TEMP_DIR"
    fi
}

trap cleanup EXIT

# -----------------------------------------------------------------------------
# Backup Functions
# -----------------------------------------------------------------------------

create_temp_dir() {
    mkdir -p "$TEMP_DIR"
    log_info "Created temporary directory: $TEMP_DIR"
}

backup_database() {
    log_info "Backing up PostgreSQL database..."
    
    cd "$DEPLOYMENT_DIR"
    
    # Get list of all databases (excluding system databases)
    local databases=$(docker compose exec -T postgres psql -U "${POSTGRES_USER:-postgres}" -t -c \
        "SELECT datname FROM pg_database WHERE datistemplate = false AND datname NOT IN ('postgres', 'template0', 'template1');")
    
    # Backup each database
    for db in $databases; do
        db=$(echo "$db" | xargs)  # Trim whitespace
        
        if [[ -n "$db" ]]; then
            log_info "Dumping database: $db"
            
            docker compose exec -T postgres pg_dump \
                -U "${POSTGRES_USER:-postgres}" \
                -Fc \
                -f "/backups/${db}.dump" \
                "$db"
            
            # Copy dump from container to temp directory
            docker cp mesob-postgres:/backups/${db}.dump "$TEMP_DIR/${db}.dump"
            
            # Remove dump from container
            docker compose exec -T postgres rm -f "/backups/${db}.dump"
            
            log_success "Database $db backed up"
        fi
    done
}

backup_filestore() {
    log_info "Backing up Odoo filestore..."
    
    cd "$DEPLOYMENT_DIR"
    
    # Copy filestore data
    docker compose exec -T odoo tar czf /tmp/filestore.tar.gz -C /var/lib/odoo . 2>/dev/null || true
    docker cp mesob-odoo:/tmp/filestore.tar.gz "$TEMP_DIR/filestore.tar.gz"
    docker compose exec -T odoo rm -f /tmp/filestore.tar.gz
    
    log_success "Filestore backed up"
}

backup_config() {
    log_info "Backing up configuration files..."
    
    # Copy configuration files
    mkdir -p "$TEMP_DIR/config"
    cp -r "$DEPLOYMENT_DIR/config" "$TEMP_DIR/"
    cp "$ENV_FILE" "$TEMP_DIR/.env.backup"
    
    log_success "Configuration backed up"
}

create_archive() {
    log_info "Creating backup archive..."
    
    local backup_type="daily"
    local day_of_week=$(date +%u)
    local day_of_month=$(date +%d)
    
    # Determine backup type
    if [[ "$day_of_month" == "01" ]]; then
        backup_type="monthly"
    elif [[ "$day_of_week" == "7" ]]; then
        backup_type="weekly"
    fi
    
    local backup_dir="$BACKUP_BASE_DIR/$backup_type"
    mkdir -p "$backup_dir"
    
    local archive_path="$backup_dir/${BACKUP_NAME}.tar.gz"
    
    # Create compressed archive
    tar czf "$archive_path" -C "$TEMP_DIR" .
    
    # Calculate file size
    local size=$(du -h "$archive_path" | cut -f1)
    
    log_success "Backup created: $archive_path (Size: $size)"
    
    echo "$archive_path"
}

verify_backup() {
    local archive_path="$1"
    
    log_info "Verifying backup integrity..."
    
    if tar tzf "$archive_path" > /dev/null; then
        log_success "Backup verification passed"
        return 0
    else
        log_error "Backup verification failed!"
        return 1
    fi
}

cleanup_old_backups() {
    log_info "Cleaning up old backups..."
    
    # Cleanup daily backups
    find "$BACKUP_BASE_DIR/daily" -name "*.tar.gz" -type f -mtime +${DAILY_RETENTION} -delete 2>/dev/null || true
    
    # Cleanup weekly backups
    find "$BACKUP_BASE_DIR/weekly" -name "*.tar.gz" -type f -mtime +$((WEEKLY_RETENTION * 7)) -delete 2>/dev/null || true
    
    # Cleanup monthly backups
    find "$BACKUP_BASE_DIR/monthly" -name "*.tar.gz" -type f -mtime +$((MONTHLY_RETENTION * 30)) -delete 2>/dev/null || true
    
    log_success "Old backups cleaned up"
}

send_notification() {
    local status="$1"
    local message="$2"
    
    # Send email notification (if configured)
    if [[ -n "${ADMIN_EMAIL:-}" ]] && command -v mail &> /dev/null; then
        echo "$message" | mail -s "Mesob Inventory Backup: $status" "$ADMIN_EMAIL"
    fi
}

# -----------------------------------------------------------------------------
# Main Execution
# -----------------------------------------------------------------------------

main() {
    log_info "==================================================================="
    log_info "Mesob Inventory Backup Started"
    log_info "==================================================================="
    
    local start_time=$(date +%s)
    
    # Create temporary directory
    create_temp_dir
    
    # Perform backups
    backup_database
    backup_filestore
    backup_config
    
    # Create and verify archive
    local archive_path=$(create_archive)
    
    if verify_backup "$archive_path"; then
        # Cleanup old backups
        cleanup_old_backups
        
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        
        log_success "==================================================================="
        log_success "Backup Completed Successfully!"
        log_success "==================================================================="
        log_info "Duration: ${duration} seconds"
        log_info "Archive: $archive_path"
        
        send_notification "SUCCESS" "Backup completed successfully: $archive_path"
        exit 0
    else
        log_error "Backup verification failed!"
        send_notification "FAILED" "Backup verification failed for: $archive_path"
        exit 1
    fi
}

# Run main function
main "$@"

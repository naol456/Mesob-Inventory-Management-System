#!/bin/bash
# =============================================================================
# Mesob Inventory Management System - Restore Script
# =============================================================================
#
# Restores a backup created by backup.sh
#
# Usage:
#   ./scripts/restore.sh /path/to/backup.tar.gz
#
# WARNING: This will stop services and replace current data!
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

BACKUP_FILE="${1:-}"
TEMP_DIR="/tmp/mesob_restore_$$"

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

log_warning() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

cleanup() {
    if [[ -d "$TEMP_DIR" ]]; then
        rm -rf "$TEMP_DIR"
    fi
}

trap cleanup EXIT

# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------

if [[ -z "$BACKUP_FILE" ]]; then
    log_error "Usage: $0 /path/to/backup.tar.gz"
    exit 1
fi

if [[ ! -f "$BACKUP_FILE" ]]; then
    log_error "Backup file not found: $BACKUP_FILE"
    exit 1
fi

# Load environment
if [[ -f "$ENV_FILE" ]]; then
    source "$ENV_FILE"
fi

# -----------------------------------------------------------------------------
# Confirmation
# -----------------------------------------------------------------------------

log_warning "==================================================================="
log_warning "WARNING: This will REPLACE all current data with the backup!"
log_warning "==================================================================="
log_warning "Backup file: $BACKUP_FILE"
log_warning "This action cannot be undone!"
echo ""
read -p "Are you sure you want to continue? (type 'yes' to confirm): " confirmation

if [[ "$confirmation" != "yes" ]]; then
    log_info "Restore cancelled"
    exit 0
fi

# -----------------------------------------------------------------------------
# Restore Functions
# -----------------------------------------------------------------------------

extract_backup() {
    log_info "Extracting backup archive..."
    
    mkdir -p "$TEMP_DIR"
    tar xzf "$BACKUP_FILE" -C "$TEMP_DIR"
    
    log_success "Backup extracted"
}

stop_services() {
    log_info "Stopping services..."
    
    cd "$DEPLOYMENT_DIR"
    docker compose down
    
    log_success "Services stopped"
}

restore_database() {
    log_info "Restoring database..."
    
    cd "$DEPLOYMENT_DIR"
    
    # Start only PostgreSQL
    docker compose up -d postgres
    sleep 10
    
    # Find database dumps
    for dump_file in "$TEMP_DIR"/*.dump; do
        if [[ -f "$dump_file" ]]; then
            local db_name=$(basename "$dump_file" .dump)
            
            log_info "Restoring database: $db_name"
            
            # Drop existing database if exists
            docker compose exec -T postgres psql -U "${POSTGRES_USER:-postgres}" -c \
                "DROP DATABASE IF EXISTS \"$db_name\";" || true
            
            # Create fresh database
            docker compose exec -T postgres psql -U "${POSTGRES_USER:-postgres}" -c \
                "CREATE DATABASE \"$db_name\" OWNER \"${POSTGRES_ODOO_USER:-odoo}\";"
            
            # Copy dump to container
            docker cp "$dump_file" mesob-postgres:/tmp/restore.dump
            
            # Restore database
            docker compose exec -T postgres pg_restore \
                -U "${POSTGRES_USER:-postgres}" \
                -d "$db_name" \
                -c \
                /tmp/restore.dump || log_warning "Some errors occurred during restore (may be normal)"
            
            # Cleanup
            docker compose exec -T postgres rm -f /tmp/restore.dump
            
            log_success "Database $db_name restored"
        fi
    done
}

restore_filestore() {
    log_info "Restoring filestore..."
    
    if [[ -f "$TEMP_DIR/filestore.tar.gz" ]]; then
        cd "$DEPLOYMENT_DIR"
        
        # Copy filestore archive to container
        docker cp "$TEMP_DIR/filestore.tar.gz" mesob-odoo:/tmp/filestore.tar.gz
        
        # Extract filestore
        docker compose exec -T odoo tar xzf /tmp/filestore.tar.gz -C /var/lib/odoo
        
        # Cleanup
        docker compose exec -T odoo rm -f /tmp/filestore.tar.gz
        
        log_success "Filestore restored"
    else
        log_warning "No filestore backup found"
    fi
}

start_services() {
    log_info "Starting services..."
    
    cd "$DEPLOYMENT_DIR"
    docker compose up -d
    
    # Wait for services
    sleep 15
    
    log_success "Services started"
}

# -----------------------------------------------------------------------------
# Main Execution
# -----------------------------------------------------------------------------

main() {
    log_info "==================================================================="
    log_info "Mesob Inventory Restore Started"
    log_info "==================================================================="
    
    local start_time=$(date +%s)
    
    # Extract backup
    extract_backup
    
    # Stop services
    stop_services
    
    # Restore data
    restore_database
    restore_filestore
    
    # Start services
    start_services
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    log_success "==================================================================="
    log_success "Restore Completed Successfully!"
    log_success "==================================================================="
    log_info "Duration: ${duration} seconds"
    log_info "Please verify your data and test the system"
}

# Run main function
main "$@"

#!/bin/bash
# =============================================================================
# Mesob Inventory Management System - Automated Deployment Script
# =============================================================================
#
# This script automates the complete deployment of the Mesob Inventory
# Management System on an Ubuntu VPS.
#
# Usage:
#   sudo ./scripts/deploy.sh
#
# Requirements:
#   - Ubuntu 22.04 LTS or 24.04 LTS
#   - Root or sudo access
#   - Configured .env file
#
# =============================================================================

set -euo pipefail  # Exit on error, undefined vars, pipe failures
IFS=$'\n\t'

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOYMENT_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(dirname "$DEPLOYMENT_DIR")"
ENV_FILE="$DEPLOYMENT_DIR/.env"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# -----------------------------------------------------------------------------
# Helper Functions
# -----------------------------------------------------------------------------

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "This script must be run as root or with sudo"
        exit 1
    fi
}

check_ubuntu() {
    if [[ ! -f /etc/lsb-release ]]; then
        log_error "This script is designed for Ubuntu only"
        exit 1
    fi
    
    source /etc/lsb-release
    if [[ "$DISTRIB_ID" != "Ubuntu" ]]; then
        log_error "This script requires Ubuntu"
        exit 1
    fi
    
    log_info "Detected: Ubuntu $DISTRIB_RELEASE"
}

check_env_file() {
    if [[ ! -f "$ENV_FILE" ]]; then
        log_error ".env file not found at $ENV_FILE"
        log_info "Please copy .env.example to .env and configure it"
        exit 1
    fi
    
    source "$ENV_FILE"
    
    # Check critical variables
    local required_vars=(
        "POSTGRES_PASSWORD"
        "POSTGRES_ODOO_PASSWORD"
        "ODOO_MASTER_PASSWORD"
        "DOMAIN"
    )
    
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var:-}" ]]; then
            log_error "Required variable $var is not set in .env file"
            exit 1
        fi
        
        if [[ "${!var}" == *"CHANGE_ME"* ]]; then
            log_error "Variable $var still contains default CHANGE_ME value"
            log_info "Please configure all passwords in .env file"
            exit 1
        fi
    done
    
    log_success "Environment configuration validated"
}

# -----------------------------------------------------------------------------
# Installation Functions
# -----------------------------------------------------------------------------

update_system() {
    log_info "Updating system packages..."
    apt-get update -qq
    apt-get upgrade -y -qq
    log_success "System updated"
}

install_docker() {
    if command -v docker &> /dev/null; then
        log_info "Docker already installed: $(docker --version)"
        return 0
    fi
    
    log_info "Installing Docker..."
    
    # Install prerequisites
    apt-get install -y -qq \
        ca-certificates \
        curl \
        gnupg \
        lsb-release
    
    # Add Docker GPG key
    mkdir -p /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    
    # Add Docker repository
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    # Install Docker
    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    
    # Start and enable Docker
    systemctl enable docker
    systemctl start docker
    
    log_success "Docker installed: $(docker --version)"
}

setup_firewall() {
    log_info "Configuring firewall (UFW)..."
    
    # Install UFW if not present
    if ! command -v ufw &> /dev/null; then
        apt-get install -y -qq ufw
    fi
    
    # Reset firewall to default
    ufw --force reset
    
    # Default policies
    ufw default deny incoming
    ufw default allow outgoing
    
    # Allow SSH
    ufw allow "${SSH_PORT:-22}/tcp" comment "SSH"
    
    # Allow HTTP and HTTPS
    ufw allow 80/tcp comment "HTTP"
    ufw allow 443/tcp comment "HTTPS"
    
    # Enable firewall
    ufw --force enable
    
    log_success "Firewall configured"
}

setup_directories() {
    log_info "Creating directory structure..."
    
    local base_dir="${BACKUP_DIR:-/opt/mesob-inventory}"
    
    # Create directories
    mkdir -p "$base_dir"/{data/{postgres,odoo},backups/{daily,weekly,monthly},logs}
    mkdir -p /var/log/mesob-inventory/{nginx,odoo}
    
    # Set permissions
    chown -R 1000:1000 "$base_dir/data/odoo"
    chown -R 999:999 "$base_dir/data/postgres"
    chmod -R 755 "$base_dir"
    
    log_success "Directory structure created"
}

setup_ssl() {
    log_info "Setting up SSL certificate..."
    
    # Check if domain is configured
    if [[ "${DOMAIN:-}" == "" ]]; then
        log_warning "No domain configured, skipping SSL setup"
        return 0
    fi
    
    # Verify DNS is pointing to this server
    local server_ip=$(curl -s ifconfig.me)
    local dns_ip=$(dig +short "$DOMAIN" | tail -n1)
    
    if [[ "$server_ip" != "$dns_ip" ]]; then
        log_warning "DNS not pointing to this server yet"
        log_warning "Server IP: $server_ip, DNS IP: $dns_ip"
        log_info "Please update DNS and run setup-ssl.sh manually later"
        return 0
    fi
    
    # Install certbot
    apt-get install -y -qq certbot
    
    # Obtain certificate
    certbot certonly --standalone \
        --non-interactive \
        --agree-tos \
        --email "${ADMIN_EMAIL}" \
        --domains "$DOMAIN" \
        --pre-hook "systemctl stop nginx" \
        --post-hook "systemctl start nginx" \
        || log_warning "SSL certificate setup failed, you can run setup-ssl.sh later"
    
    log_success "SSL certificate configured"
}

build_images() {
    log_info "Building Docker images..."
    
    cd "$DEPLOYMENT_DIR"
    docker compose build --no-cache
    
    log_success "Docker images built"
}

initialize_database() {
    log_info "Initializing database..."
    
    cd "$DEPLOYMENT_DIR"
    
    # Start only PostgreSQL
    docker compose up -d postgres
    
    # Wait for PostgreSQL to be ready
    log_info "Waiting for PostgreSQL to be ready..."
    sleep 10
    
    # Check PostgreSQL health
    docker compose exec -T postgres pg_isready -U postgres || {
        log_error "PostgreSQL failed to start"
        exit 1
    }
    
    log_success "Database initialized"
}

start_services() {
    log_info "Starting all services..."
    
    cd "$DEPLOYMENT_DIR"
    docker compose up -d
    
    # Wait for services to start
    sleep 15
    
    # Check service health
    docker compose ps
    
    log_success "All services started"
}

setup_backups() {
    log_info "Configuring automated backups..."
    
    # Make backup script executable
    chmod +x "$SCRIPT_DIR/backup.sh"
    
    # Add cron job for daily backups
    local backup_schedule="${BACKUP_SCHEDULE:-0 2 * * *}"
    local cron_cmd="$backup_schedule $SCRIPT_DIR/backup.sh >> /var/log/mesob-inventory/backup.log 2>&1"
    
    # Add to crontab if not already present
    (crontab -l 2>/dev/null | grep -v "backup.sh"; echo "$cron_cmd") | crontab -
    
    log_success "Automated backups configured"
}

setup_log_rotation() {
    log_info "Configuring log rotation..."
    
    cat > /etc/logrotate.d/mesob-inventory <<EOF
/var/log/mesob-inventory/*.log {
    daily
    rotate 30
    compress
    delaycompress
    notifempty
    create 0640 root root
    sharedscripts
    postrotate
        docker compose -f $DEPLOYMENT_DIR/docker-compose.yml exec -T nginx nginx -s reload > /dev/null 2>&1 || true
    endscript
}
EOF
    
    log_success "Log rotation configured"
}

print_summary() {
    log_success "==================================================================="
    log_success "Deployment Complete!"
    log_success "==================================================================="
    echo ""
    log_info "Services Status:"
    cd "$DEPLOYMENT_DIR" && docker compose ps
    echo ""
    log_info "Access your system:"
    echo "  - URL: https://${DOMAIN}"
    echo "  - Database: ${ODOO_DB_NAME}"
    echo ""
    log_info "Useful Commands:"
    echo "  - View logs: docker compose logs -f"
    echo "  - Restart:   docker compose restart"
    echo "  - Stop:      docker compose down"
    echo "  - Backup:    ./scripts/backup.sh"
    echo ""
    log_warning "Next Steps:"
    echo "  1. Create initial database and configure Odoo"
    echo "  2. Install mesob_inventory_base module"
    echo "  3. Configure users and permissions"
    echo "  4. Test backup/restore procedure"
    echo ""
}

# -----------------------------------------------------------------------------
# Main Execution
# -----------------------------------------------------------------------------

main() {
    log_info "==================================================================="
    log_info "Mesob Inventory Management System - Deployment"
    log_info "==================================================================="
    echo ""
    
    # Pre-flight checks
    check_root
    check_ubuntu
    check_env_file
    
    # System setup
    update_system
    install_docker
    setup_firewall
    setup_directories
    
    # SSL setup (optional, may fail if DNS not configured)
    setup_ssl
    
    # Application deployment
    build_images
    initialize_database
    start_services
    
    # Post-deployment
    setup_backups
    setup_log_rotation
    
    # Summary
    print_summary
    
    log_success "Deployment script completed successfully!"
}

# Run main function
main "$@"

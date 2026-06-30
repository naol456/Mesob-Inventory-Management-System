# Mesob Inventory Management System - Production Deployment Guide

## Overview

This directory contains everything needed to deploy the Mesob Inventory Management System to an Ubuntu VPS in a **production-ready** configuration.

## Architecture

```
Internet
    ↓
[Nginx Reverse Proxy] ← SSL/TLS (Let's Encrypt)
    ↓
[Odoo 19 Container] ← Application Server
    ↓
[PostgreSQL 16] ← Database Server
    ↓
[Volume Storage] ← Persistent Data (DB + Filestore)
```

## Directory Structure

```
deployment/
├── README.md                    # This file
├── docker-compose.yml           # Multi-container orchestration
├── Dockerfile                   # Custom Odoo image with dependencies
├── .env.example                 # Environment variables template
├── config/
│   ├── odoo.conf               # Odoo configuration template
│   └── nginx/
│       ├── nginx.conf          # Nginx main config
│       └── mesob.conf          # Site-specific config
├── scripts/
│   ├── deploy.sh               # Deployment automation
│   ├── backup.sh               # Automated backup script
│   ├── restore.sh              # Restore from backup
│   ├── health-check.sh         # System health monitoring
│   └── setup-ssl.sh            # Let's Encrypt SSL setup
├── systemd/
│   └── mesob-inventory.service # SystemD service definition
└── docs/
    ├── DEPLOYMENT.md           # Step-by-step deployment guide
    ├── SECURITY.md             # Security hardening checklist
    ├── MAINTENANCE.md          # Ongoing maintenance procedures
    └── TROUBLESHOOTING.md      # Common issues and solutions
```

## Prerequisites

### Server Requirements

- **OS**: Ubuntu 22.04 LTS or 24.04 LTS (recommended)
- **RAM**: Minimum 4GB (8GB+ recommended for production)
- **CPU**: 2+ cores
- **Storage**: 40GB+ (SSD recommended)
- **Network**: Static IP or domain name pointing to server

### Software Requirements

- Docker Engine 24.0+
- Docker Compose V2
- UFW (Uncomplicated Firewall)
- Certbot (for SSL certificates)

### Access Requirements

- Root or sudo access
- SSH access to server
- Domain name with DNS configured (for SSL)

## Quick Start

### 1. Clone Repository on Server

```bash
# SSH into your Ubuntu VPS
ssh user@your-server-ip

# Clone the repository
git clone <repository-url> /opt/mesob-inventory
cd /opt/mesob-inventory
```

### 2. Configure Environment

```bash
# Copy environment template
cp deployment/.env.example deployment/.env

# Edit configuration (use nano or vim)
nano deployment/.env
```

**Required Configuration:**
- Database credentials
- Admin password
- Domain name
- Email settings

### 3. Run Deployment Script

```bash
cd deployment
chmod +x scripts/*.sh
sudo ./scripts/deploy.sh
```

The script will:
- ✅ Install Docker and dependencies
- ✅ Configure firewall (UFW)
- ✅ Set up SSL certificates
- ✅ Initialize database
- ✅ Start all services
- ✅ Configure automated backups

### 4. Access Your System

```
https://your-domain.com
```

**Initial Login:**
- Database: Use database name from .env
- Email: admin@yourdomain.com
- Password: (Set in .env file)

## Production Checklist

Before going live, ensure:

- [ ] `.env` file configured with strong passwords
- [ ] Domain DNS pointing to server IP
- [ ] SSL certificate obtained and valid
- [ ] Firewall configured (only 80, 443, 22 open)
- [ ] Database backups automated and tested
- [ ] Monitoring configured
- [ ] Test accounts removed from database
- [ ] Email server configured (SMTP)
- [ ] Log rotation configured
- [ ] Security hardening completed

## Management Commands

### Start Services
```bash
cd /opt/mesob-inventory/deployment
docker compose up -d
```

### Stop Services
```bash
docker compose down
```

### View Logs
```bash
docker compose logs -f odoo
docker compose logs -f nginx
docker compose logs -f postgres
```

### Backup Database
```bash
./scripts/backup.sh
```

### Restore Database
```bash
./scripts/restore.sh /path/to/backup.zip
```

### Update Module
```bash
docker compose exec odoo odoo -c /etc/odoo/odoo.conf -d <database> -u mesob_inventory_base --stop-after-init
docker compose restart odoo
```

## Security

### Hardening Checklist

- [x] Non-root container user
- [x] Strong database passwords
- [x] SSL/TLS encryption
- [x] Firewall configured
- [x] Fail2ban for SSH protection
- [x] Regular security updates
- [x] Database access restricted to localhost
- [x] Odoo admin interface protected

See `docs/SECURITY.md` for complete security guide.

## Monitoring

### Health Checks

```bash
./scripts/health-check.sh
```

### Key Metrics to Monitor

- CPU usage
- Memory usage
- Disk space
- Database connections
- Response time
- Error logs

## Backup Strategy

### Automated Backups

- **Frequency**: Daily at 2:00 AM (configurable)
- **Retention**: 7 daily, 4 weekly, 12 monthly
- **Location**: `/opt/mesob-inventory/backups`
- **Contents**: PostgreSQL dump + Filestore

### Off-site Backup

Configure S3, rsync, or similar for disaster recovery.

## Maintenance

### Regular Tasks

**Daily** (Automated):
- Database backup
- Log rotation
- Health check

**Weekly**:
- Review error logs
- Check disk space
- Monitor performance

**Monthly**:
- Security updates
- Test restore procedure
- Review access logs

See `docs/MAINTENANCE.md` for detailed procedures.

## Troubleshooting

### Service won't start
```bash
docker compose logs
```

### Database connection error
```bash
docker compose exec postgres pg_isready
```

### SSL certificate issues
```bash
sudo certbot renew --dry-run
```

See `docs/TROUBLESHOOTING.md` for complete troubleshooting guide.

## Support

- **Documentation**: `deployment/docs/`
- **Logs**: `docker compose logs`
- **Health Check**: `./scripts/health-check.sh`

## Version

- **Odoo Version**: 19.0
- **Module Version**: 19.0.1.7.0
- **Deployment Version**: 1.0.0
- **Last Updated**: 2026-07-01

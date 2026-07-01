# Mesob Inventory Management System - Complete Deployment Guide

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Pre-Deployment Checklist](#pre-deployment-checklist)
3. [Server Preparation](#server-preparation)
4. [Installation Steps](#installation-steps)
5. [Post-Deployment Configuration](#post-deployment-configuration)
6. [Verification](#verification)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Server Requirements

**Minimum Specifications:**
- **OS**: Ubuntu 22.04 LTS or 24.04 LTS (64-bit)
- **RAM**: 4GB (8GB+ recommended for production)
- **CPU**: 2 cores (4+ recommended)
- **Storage**: 40GB SSD (100GB+ recommended for production)
- **Network**: Public IP address or domain name

**Recommended Specifications (Production):**
- **RAM**: 16GB
- **CPU**: 4-8 cores
- **Storage**: 200GB+ SSD
- **Network**: 1Gbps, static IP

### Domain & DNS

- Domain name pointed to server IP (A record)
- DNS propagation completed (verify with `nslookup your-domain.com`)
- Email address for SSL certificate notifications

### Access Requirements

- Root or sudo access to Ubuntu server
- SSH key-based authentication configured
- Firewall access (ports 22, 80, 443)

---

## Pre-Deployment Checklist

Before starting deployment, ensure you have:

- [ ] Fresh Ubuntu 22.04/24.04 installation with updates applied
- [ ] Root/sudo access configured
- [ ] SSH access working
- [ ] Domain DNS configured and propagated
- [ ] Email account for SMTP (for notifications)
- [ ] Backup storage plan (local or cloud)
- [ ] Strong passwords generated for:
  - [ ] PostgreSQL admin password
  - [ ] PostgreSQL Odoo user password
  - [ ] Odoo master password
  - [ ] SMTP password (if using authenticated SMTP)

---

## Server Preparation

### Step 1: Update System

```bash
# SSH into your server
ssh user@your-server-ip

# Update package lists and upgrade
sudo apt update
sudo apt upgrade -y

# Reboot if kernel was updated
sudo reboot
```

### Step 2: Configure Hostname

```bash
# Set hostname
sudo hostnamectl set-hostname mesob-inventory

# Update /etc/hosts
sudo nano /etc/hosts
```

Add:
```
127.0.0.1 localhost mesob-inventory
your-server-ip your-domain.com mesob-inventory
```

### Step 3: Configure Timezone

```bash
# Set to Ethiopia timezone
sudo timedatectl set-timezone Africa/Addis_Ababa

# Verify
timedatectl
```

### Step 4: Create Deployment User (Optional but Recommended)

```bash
# Create dedicated user for application
sudo adduser mesob --disabled-password

# Add to docker group (we'll install docker later)
sudo usermod -aG sudo mesob

# Switch to mesob user
sudo su - mesob
```

---

## Installation Steps

### Step 1: Clone Repository

```bash
# Create application directory
sudo mkdir -p /opt/mesob-inventory
sudo chown -R $USER:$USER /opt/mesob-inventory

# Clone repository
cd /opt
git clone <your-repository-url> mesob-inventory
cd mesob-inventory
```

### Step 2: Configure Environment

```bash
# Copy environment template
cd deployment
cp .env.example .env

# Edit configuration
nano .env
```

**Required Configuration Values:**

```bash
# Domain
DOMAIN=inventory.mesobcenter.et

# Admin email
ADMIN_EMAIL=admin@mesobcenter.et

# PostgreSQL passwords (generate strong passwords!)
POSTGRES_PASSWORD=<generate-strong-password-32-chars>
POSTGRES_ODOO_PASSWORD=<generate-strong-password-32-chars>

# Odoo master password (min 20 characters)
ODOO_MASTER_PASSWORD=<generate-strong-password-20-chars>

# Database settings
ODOO_DB_NAME=mesob_inventory_production
ODOO_WORKERS=5  # (CPU cores * 2) + 1

# SMTP settings (for email notifications)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=noreply@mesobcenter.et
SMTP_PASSWORD=<your-smtp-password>
EMAIL_FROM="Mesob Inventory <noreply@mesobcenter.et>"
```

**Generate strong passwords:**

```bash
# Generate 32-character password
openssl rand -base64 32

# Generate 20-character password
openssl rand -base64 20
```

**Secure the .env file:**

```bash
chmod 600 .env
chown $USER:$USER .env
```

### Step 3: Run Automated Deployment

```bash
# Make scripts executable
chmod +x scripts/*.sh

# Run deployment script
sudo ./scripts/deploy.sh
```

The deployment script will automatically:
- ✅ Install Docker and Docker Compose
- ✅ Configure UFW firewall
- ✅ Create directory structure
- ✅ Set up SSL certificates (Let's Encrypt)
- ✅ Build Docker images
- ✅ Initialize PostgreSQL database
- ✅ Start all services
- ✅ Configure automated backups
- ✅ Set up log rotation

**Deployment time:** Approximately 10-15 minutes

---

## Post-Deployment Configuration

### Step 1: Verify Services

```bash
cd /opt/mesob-inventory/deployment

# Check service status
docker compose ps

# All services should show "Up (healthy)"
```

### Step 2: Create Initial Database

1. Access your domain: `https://your-domain.com`
2. You'll see the Odoo database manager
3. Create a new database:
   - **Master Password**: (from your .env file: ODOO_MASTER_PASSWORD)
   - **Database Name**: mesob_inventory_production (or as configured)
   - **Email**: admin@yourdomain.com
   - **Password**: (create strong admin password)
   - **Language**: English
   - **Country**: Ethiopia
   - **Demo Data**: Uncheck this box!

### Step 3: Install Mesob Inventory Module

1. Log in with admin credentials
2. Go to **Apps** menu
3. Remove the "Apps" filter
4. Search for "Mesob Inventory"
5. Click **Install** on `mesob_inventory_base`
6. Wait for installation (may take 2-3 minutes)

### Step 4: Configure Users and Security

1. **Remove Demo Users**:
   - Go to Settings → Users & Companies → Users
   - Delete or disable any demo/test users
   - Remove or change default passwords

2. **Create Real Users**:
   - Create users with real email addresses
   - Assign appropriate security groups
   - Enable two-factor authentication (recommended)

3. **Configure Company**:
   - Settings → Companies
   - Update company information
   - Upload logo
   - Configure address, phone, email

4. **Email Configuration**:
   - Settings → Technical → Outgoing Mail Servers
   - Verify SMTP configuration
   - Test email sending

### Step 5: Initial Data Setup

1. **Departments**: Configure your organization's departments
2. **Major Classifications**: Review and update stock classifications (4401-4418)
3. **Sub Classifications**: Add sub-classifications as needed
4. **Items**: Import or create inventory items
5. **Suppliers**: Add supplier records

---

## Verification

### System Health Check

```bash
cd /opt/mesob-inventory/deployment

# Run health check
./scripts/health-check.sh

# Check logs
docker compose logs -f odoo
docker compose logs -f postgres
docker compose logs -f nginx
```

### Performance Test

```bash
# Check resource usage
docker stats

# Monitor CPU and memory
htop
```

### Backup Test

```bash
# Run manual backup
./scripts/backup.sh

# Verify backup created
ls -lh /opt/mesob-inventory/backups/daily/

# Test restore (on test environment only!)
# ./scripts/restore.sh /path/to/backup.tar.gz
```

### SSL Certificate Test

```bash
# Check SSL certificate
sudo certbot certificates

# Test SSL configuration
curl -I https://your-domain.com
```

---

## Troubleshooting

### Services Won't Start

```bash
# Check logs
docker compose logs

# Restart services
docker compose down
docker compose up -d

# Check firewall
sudo ufw status
```

### Database Connection Issues

```bash
# Check PostgreSQL
docker compose exec postgres pg_isready

# View PostgreSQL logs
docker compose logs postgres

# Test connection
docker compose exec postgres psql -U postgres -c "SELECT version();"
```

### SSL Certificate Issues

```bash
# Check certificate status
sudo certbot certificates

# Force certificate renewal
sudo certbot renew --force-renewal

# Check nginx configuration
docker compose exec nginx nginx -t
```

### Performance Issues

```bash
# Check resource usage
docker stats

# Increase worker count (in .env file)
ODOO_WORKERS=9  # For 4 CPU cores

# Restart Odoo
docker compose restart odoo
```

### Backup Failures

```bash
# Check backup logs
cat /var/log/mesob-inventory/backup.log

# Test backup manually
cd /opt/mesob-inventory/deployment
sudo ./scripts/backup.sh test_backup

# Check disk space
df -h
```

---

## Next Steps

After successful deployment:

1. **Security Hardening**: Review [SECURITY.md](SECURITY.md)
2. **Monitoring Setup**: Configure monitoring tools
3. **User Training**: Train staff on system usage
4. **Documentation**: Document custom configurations
5. **Regular Maintenance**: Schedule weekly maintenance windows

---

## Support

For issues or questions:

1. Check logs: `docker compose logs`
2. Run health check: `./scripts/health-check.sh`
3. Review troubleshooting section above
4. Check system resources: `docker stats`
5. Consult [TROUBLESHOOTING.md](TROUBLESHOOTING.md)

---

## Production Checklist

Before going live:

- [ ] SSL certificate valid and auto-renewal configured
- [ ] All demo/test users removed
- [ ] Strong passwords configured
- [ ] Firewall rules verified (only 22, 80, 443 open)
- [ ] Automated backups tested and verified
- [ ] Email notifications working
- [ ] Database optimization completed
- [ ] Performance testing done
- [ ] Security audit completed
- [ ] User training completed
- [ ] Documentation updated
- [ ] Disaster recovery plan documented
- [ ] Monitoring configured
- [ ] Log rotation verified

---

**Deployment Version**: 1.0.0  
**Last Updated**: 2026-07-01  
**Odoo Version**: 19.0  
**Module Version**: 19.0.1.7.0

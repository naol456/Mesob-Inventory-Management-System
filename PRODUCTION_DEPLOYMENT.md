# Mesob Inventory Management System - Production Deployment

## 🚀 Quick Start for Production Deployment

This document provides a high-level overview of deploying the Mesob Inventory Management System to production on an Ubuntu VPS.

---

## 📋 What's Included

Your project is now **production-ready** with:

✅ **Docker-based deployment** (industry standard)  
✅ **Multi-service architecture** (Odoo, PostgreSQL, Nginx, Certbot)  
✅ **SSL/TLS with Let's Encrypt** (automatic certificate management)  
✅ **Automated backups** (daily/weekly/monthly with retention)  
✅ **Security hardening** (firewall, fail2ban, secure configurations)  
✅ **Health checks & monitoring**  
✅ **Professional documentation**  
✅ **Disaster recovery procedures**  

---

## 📁 New Deployment Files

```
Mesob-Inventory-Management-System/
├── deployment/                          # Production deployment
│   ├── README.md                       # Deployment overview
│   ├── Dockerfile                      # Custom Odoo image
│   ├── docker-compose.yml              # Multi-container orchestration
│   ├── .env.example                    # Environment template (copy to .env)
│   ├── config/
│   │   ├── odoo.conf                  # Odoo configuration
│   │   └── nginx/
│   │       ├── nginx.conf             # Nginx main config
│   │       └── mesob.conf             # Site-specific config
│   ├── scripts/
│   │   ├── deploy.sh                  # Automated deployment
│   │   ├── backup.sh                  # Backup automation
│   │   ├── restore.sh                 # Restore from backup
│   │   ├── init-db.sh                 # Database initialization
│   │   └── healthcheck.py             # Health check script
│   └── docs/
│       ├── DEPLOYMENT_GUIDE.md        # Complete step-by-step guide
│       └── SECURITY.md                # Security hardening checklist
├── requirements.txt                    # Python dependencies
└── PRODUCTION_DEPLOYMENT.md           # This file
```

---

## ⚡ Deployment in 4 Steps

### 1️⃣ Prepare Your Ubuntu VPS

**Requirements:**
- Ubuntu 22.04 LTS or 24.04 LTS
- 4GB+ RAM (8GB+ recommended)
- 2+ CPU cores
- 40GB+ storage
- Domain name with DNS configured

```bash
# SSH into your server
ssh user@your-server-ip

# Clone repository
sudo mkdir -p /opt/mesob-inventory
cd /opt
git clone <your-repo-url> mesob-inventory
cd mesob-inventory
```

### 2️⃣ Configure Environment

```bash
cd deployment

# Copy environment template
cp .env.example .env

# Edit configuration (IMPORTANT: change ALL passwords!)
nano .env
```

**Critical settings to change:**
- `DOMAIN` - Your domain name
- `ADMIN_EMAIL` - Your email
- `POSTGRES_PASSWORD` - Strong password (32+ chars)
- `POSTGRES_ODOO_PASSWORD` - Strong password (32+ chars)
- `ODOO_MASTER_PASSWORD` - Strong password (20+ chars)
- `SMTP_*` - Email configuration

**Generate strong passwords:**
```bash
openssl rand -base64 32  # For database passwords
openssl rand -base64 20  # For Odoo master password
```

### 3️⃣ Run Automated Deployment

```bash
# Make scripts executable
chmod +x scripts/*.sh

# Run deployment (takes 10-15 minutes)
sudo ./scripts/deploy.sh
```

The script automatically installs and configures:
- ✅ Docker & Docker Compose
- ✅ Firewall (UFW)
- ✅ SSL certificate (Let's Encrypt)
- ✅ All services (Odoo, PostgreSQL, Nginx)
- ✅ Automated backups
- ✅ Log rotation

### 4️⃣ Access & Configure

1. **Open your browser**: `https://your-domain.com`

2. **Create database**:
   - Master password: (from .env: ODOO_MASTER_PASSWORD)
   - Database name: mesob_inventory_production
   - Email: admin@yourdomain.com
   - Password: (create strong password)
   - ⚠️ **UNCHECK "Load demo data"**

3. **Install module**:
   - Go to Apps
   - Search "Mesob Inventory"
   - Install `mesob_inventory_base`

4. **Remove demo accounts**:
   - Settings → Users
   - Delete/disable all test users
   - Create real users with proper roles

---

## 🔒 Security Checklist

Before going live, verify:

- [ ] All passwords changed from defaults
- [ ] Demo/test accounts removed
- [ ] SSL certificate valid (https://your-domain.com)
- [ ] Firewall enabled (only ports 22, 80, 443 open)
- [ ] Database manager disabled
- [ ] Backups tested and working
- [ ] Email notifications configured
- [ ] Log rotation configured
- [ ] Security headers verified

**Detailed security guide**: `deployment/docs/SECURITY.md`

---

## 📊 Management Commands

### Service Management

```bash
cd /opt/mesob-inventory/deployment

# Start services
docker compose up -d

# Stop services
docker compose down

# Restart services
docker compose restart

# View status
docker compose ps

# View logs
docker compose logs -f odoo
docker compose logs -f postgres
docker compose logs -f nginx
```

### Backup & Restore

```bash
# Run manual backup
./scripts/backup.sh

# List backups
ls -lh /opt/mesob-inventory/backups/daily/

# Restore from backup (WARNING: replaces current data!)
./scripts/restore.sh /path/to/backup.tar.gz
```

### Module Updates

```bash
# Update module
docker compose exec odoo odoo \
  -c /etc/odoo/odoo.conf \
  -d mesob_inventory_production \
  -u mesob_inventory_base \
  --stop-after-init

# Restart Odoo
docker compose restart odoo
```

### System Monitoring

```bash
# Resource usage
docker stats

# Disk usage
df -h

# Service health
docker compose ps
```

---

## 🔧 Common Operations

### Check SSL Certificate

```bash
# View certificate details
sudo certbot certificates

# Test SSL configuration
curl -I https://your-domain.com

# Manual renewal (usually automatic)
sudo certbot renew
```

### Database Operations

```bash
# Connect to database
docker compose exec postgres psql -U postgres -d mesob_inventory_production

# Backup specific database
docker compose exec postgres pg_dump \
  -U postgres \
  -Fc mesob_inventory_production > backup.dump

# List databases
docker compose exec postgres psql -U postgres -c "\l"
```

### Performance Tuning

```bash
# Adjust worker count (in .env file)
# Formula: (CPU cores * 2) + 1
# For 4 CPUs: ODOO_WORKERS=9

# Adjust PostgreSQL memory (in .env file)
# Shared buffers: 25% of RAM
# Effective cache: 50-75% of RAM

# Restart after changes
docker compose down
docker compose up -d
```

---

## 🆘 Troubleshooting

### Services Won't Start

```bash
# Check logs for errors
docker compose logs

# Verify .env file
cat .env | grep -v '^#' | grep -v '^$'

# Check disk space
df -h

# Check firewall
sudo ufw status
```

### Database Connection Failed

```bash
# Check PostgreSQL status
docker compose exec postgres pg_isready

# View PostgreSQL logs
docker compose logs postgres

# Verify credentials in .env
echo $POSTGRES_ODOO_PASSWORD
```

### Can't Access via HTTPS

```bash
# Check nginx status
docker compose logs nginx

# Verify DNS
nslookup your-domain.com

# Check SSL certificate
sudo certbot certificates

# Test ports
sudo netstat -tulpn | grep -E ':(80|443)'
```

### Slow Performance

```bash
# Check resources
docker stats
htop

# Review Odoo logs for errors
docker compose logs odoo | grep ERROR

# Increase worker count
# Edit .env: ODOO_WORKERS=9 (for 4 CPUs)
docker compose restart odoo
```

**Complete troubleshooting guide**: `deployment/docs/DEPLOYMENT_GUIDE.md#troubleshooting`

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| **deployment/README.md** | Deployment overview |
| **deployment/docs/DEPLOYMENT_GUIDE.md** | Complete step-by-step deployment guide |
| **deployment/docs/SECURITY.md** | Security hardening checklist |
| **requirements.txt** | Python dependencies |
| **deployment/.env.example** | Environment configuration template |

---

## 🎯 Architecture Overview

```
Internet
    ↓
[ Firewall (UFW) ]
    ↓
[ Nginx (Port 80/443) ]  ← SSL/TLS (Let's Encrypt)
    ↓                      Rate limiting
    ↓                      Security headers
    ↓
[ Odoo (Port 8069) ]     ← Application server
    ↓                      5 workers (default)
    ↓                      Health checks
    ↓
[ PostgreSQL (Port 5432) ] ← Database (localhost only)
    ↓                        Optimized for performance
    ↓                        Automated backups
    ↓
[ Persistent Storage ]     ← Docker volumes
    ├── Database data
    ├── Filestore (uploads)
    └── Backups
```

---

## ✅ Production Readiness Checklist

### Before Deployment

- [ ] Domain DNS configured and propagated
- [ ] VPS provisioned with required specs
- [ ] .env file configured with strong passwords
- [ ] Email/SMTP credentials ready
- [ ] Backup storage plan in place

### After Deployment

- [ ] SSL certificate obtained and valid
- [ ] Odoo accessible via HTTPS
- [ ] Database created and module installed
- [ ] Demo accounts removed
- [ ] Real users created with proper permissions
- [ ] Company information configured
- [ ] Email notifications tested
- [ ] Backups tested (backup + restore)
- [ ] Monitoring configured
- [ ] Documentation reviewed

### Go-Live

- [ ] Security audit completed
- [ ] Performance testing done
- [ ] User training completed
- [ ] Disaster recovery plan documented
- [ ] Support contacts established

---

## 📞 Support

For deployment issues:

1. **Check logs**: `docker compose logs`
2. **Run health check**: `./scripts/health-check.sh`
3. **Review documentation**: `deployment/docs/`
4. **Check resources**: `docker stats`
5. **Verify configuration**: Review .env file

---

## 🔄 Maintenance

### Daily (Automated)
- Backup at 2:00 AM
- Log rotation
- Health checks

### Weekly
- Review error logs
- Check disk space
- Monitor performance
- Review security logs

### Monthly
- Security updates
- Test backup restore
- Review user access
- Performance optimization

**Maintenance guide**: `deployment/docs/DEPLOYMENT_GUIDE.md#maintenance`

---

## 📈 What's Next?

After successful deployment:

1. **User Training**: Train staff on system usage
2. **Data Migration**: Import existing data (if applicable)
3. **Customization**: Configure workflows, reports, etc.
4. **Monitoring**: Set up monitoring tools (Prometheus, Grafana)
5. **Optimization**: Fine-tune performance based on usage
6. **Documentation**: Document custom configurations

---

## 🎉 Success!

Your Mesob Inventory Management System is now ready for production deployment!

**Key Points:**
- ✅ Professional-grade deployment setup
- ✅ Security-first architecture
- ✅ Automated backups and monitoring
- ✅ Complete documentation
- ✅ Disaster recovery ready

**Deployment Time:** 10-15 minutes (automated)  
**Next Step:** Run `sudo ./scripts/deploy.sh`

---

**Document Version**: 1.0.0  
**Odoo Version**: 19.0  
**Module Version**: 19.0.1.7.0  
**Created**: 2026-07-01  
**For**: Ubuntu 22.04 LTS / 24.04 LTS

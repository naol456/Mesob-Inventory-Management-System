# Mesob Inventory - Quick Reference Card

## 🚀 Essential Commands

### Service Management

```bash
cd /opt/mesob-inventory/deployment

# Start all services
docker compose up -d

# Stop all services
docker compose down

# Restart specific service
docker compose restart odoo
docker compose restart postgres
docker compose restart nginx

# View service status
docker compose ps

# View resource usage
docker stats
```

### Logs

```bash
# View Odoo logs (follow)
docker compose logs -f odoo

# View last 100 lines
docker compose logs --tail=100 odoo

# View all service logs
docker compose logs -f

# View PostgreSQL logs
docker compose logs postgres

# View Nginx logs
docker compose logs nginx

# System logs
tail -f /var/log/mesob-inventory/backup.log
```

### Backup & Restore

```bash
# Run manual backup
./scripts/backup.sh

# Run backup with custom name
./scripts/backup.sh my_backup_name

# List backups
ls -lh /opt/mesob-inventory/backups/daily/
ls -lh /opt/mesob-inventory/backups/weekly/
ls -lh /opt/mesob-inventory/backups/monthly/

# Restore from backup (⚠️ REPLACES CURRENT DATA!)
./scripts/restore.sh /path/to/backup.tar.gz
```

### Module Management

```bash
# Update module
docker compose exec odoo odoo \
  -c /etc/odoo/odoo.conf \
  -d mesob_inventory_production \
  -u mesob_inventory_base \
  --stop-after-init

# Restart after update
docker compose restart odoo

# Install new module
docker compose exec odoo odoo \
  -c /etc/odoo/odoo.conf \
  -d mesob_inventory_production \
  -i module_name \
  --stop-after-init
```

### Database Operations

```bash
# Connect to PostgreSQL
docker compose exec postgres psql -U postgres

# List databases
docker compose exec postgres psql -U postgres -c "\l"

# Database size
docker compose exec postgres psql -U postgres -c \
  "SELECT pg_database.datname, pg_size_pretty(pg_database_size(pg_database.datname)) FROM pg_database;"

# Backup specific database
docker compose exec postgres pg_dump \
  -U postgres -Fc mesob_inventory_production > backup.dump

# Vacuum database (optimize)
docker compose exec postgres psql -U postgres -d mesob_inventory_production -c "VACUUM ANALYZE;"
```

### SSL Certificate

```bash
# View certificate info
sudo certbot certificates

# Manual renewal
sudo certbot renew

# Test renewal
sudo certbot renew --dry-run

# Force renewal
sudo certbot renew --force-renewal
```

### System Monitoring

```bash
# Disk usage
df -h

# Memory usage
free -h

# CPU and process monitoring
htop

# Docker resource usage
docker stats

# Nginx status
docker compose exec nginx nginx -t

# PostgreSQL status
docker compose exec postgres pg_isready
```

### Firewall

```bash
# Check firewall status
sudo ufw status

# Check firewall rules
sudo ufw status numbered

# Allow specific IP for SSH
sudo ufw allow from 203.0.113.10 to any port 22

# Delete rule by number
sudo ufw delete <number>
```

---

## 📋 Troubleshooting Quick Fixes

### Service Won't Start

```bash
# Check logs
docker compose logs

# Restart all services
docker compose down
docker compose up -d

# Rebuild if needed
docker compose build --no-cache
docker compose up -d
```

### Out of Memory

```bash
# Check memory
free -h

# Restart Odoo to free memory
docker compose restart odoo

# Reduce worker count (edit .env)
ODOO_WORKERS=3
docker compose down
docker compose up -d
```

### Database Connection Error

```bash
# Check PostgreSQL
docker compose exec postgres pg_isready

# Restart PostgreSQL
docker compose restart postgres

# Check credentials
cat .env | grep POSTGRES
```

### SSL Certificate Expired

```bash
# Renew certificate
sudo certbot renew --force-renewal

# Restart nginx
docker compose restart nginx
```

### Disk Full

```bash
# Check disk usage
df -h

# Clean up old Docker images
docker system prune -a

# Clean up old backups
find /opt/mesob-inventory/backups -type f -mtime +30 -delete

# Clean up logs
docker compose exec odoo find /var/log/odoo -name "*.log" -mtime +30 -delete
```

---

## 🔑 Important Paths

```
/opt/mesob-inventory/                   # Application root
├── deployment/
│   ├── .env                            # Configuration (SECURE!)
│   ├── docker-compose.yml              # Container orchestration
│   ├── config/                         # Configuration files
│   ├── scripts/                        # Management scripts
│   └── docs/                           # Documentation
├── backups/                            # Backup storage
│   ├── daily/                          # Daily backups (7 days)
│   ├── weekly/                         # Weekly backups (4 weeks)
│   └── monthly/                        # Monthly backups (12 months)
├── data/                               # Persistent data
│   ├── postgres/                       # Database files
│   └── odoo/                           # Odoo filestore
└── /var/log/mesob-inventory/           # Application logs
    ├── odoo/                           # Odoo logs
    ├── nginx/                          # Nginx logs
    └── backup.log                      # Backup logs
```

---

## 🌐 Access URLs

```
Production:  https://your-domain.com
Database:    mesob_inventory_production
Admin:       (use credentials from setup)
```

---

## 📞 Emergency Contacts

```
System Admin:    _________________
Security Team:   _________________
Database Admin:  _________________
Odoo Support:    _________________
Hosting Provider: _________________
```

---

## ⚡ Performance Tuning

### Increase Workers (for more traffic)

```bash
# Edit .env file
nano /opt/mesob-inventory/deployment/.env

# Set workers: (CPU cores * 2) + 1
# For 4 CPUs: ODOO_WORKERS=9
# For 8 CPUs: ODOO_WORKERS=17

# Restart
cd /opt/mesob-inventory/deployment
docker compose down
docker compose up -d
```

### Optimize PostgreSQL

```bash
# Edit .env file
nano /opt/mesob-inventory/deployment/.env

# For 8GB RAM server:
POSTGRES_SHARED_BUFFERS=2GB
POSTGRES_EFFECTIVE_CACHE_SIZE=6GB

# Restart
docker compose restart postgres
```

---

## 🔒 Security Quick Checks

```bash
# Check firewall
sudo ufw status

# Check SSL certificate
sudo certbot certificates

# Check open ports
sudo netstat -tulpn

# Review failed login attempts
docker compose logs nginx | grep "401\|403"

# Check disk space (prevent DoS)
df -h

# Verify services running
docker compose ps
```

---

## 📊 Health Check

```bash
# Quick health check
curl -I https://your-domain.com

# Detailed check
docker compose ps
docker stats --no-stream
df -h
free -h

# Test database
docker compose exec postgres pg_isready

# Test Odoo
curl http://localhost:8069/web/health
```

---

## 🔄 Update Checklist

**Monthly Security Updates:**

```bash
# 1. Backup first!
cd /opt/mesob-inventory/deployment
./scripts/backup.sh

# 2. Update system
sudo apt update
sudo apt upgrade -y

# 3. Update Docker images
docker compose pull

# 4. Recreate containers
docker compose down
docker compose up -d

# 5. Verify all services
docker compose ps
```

---

## 📝 Common Tasks

### Add New User

1. Log in as admin
2. Settings → Users & Companies → Users
3. Click "New"
4. Fill in details
5. Assign security groups
6. Send invite

### Change User Password

1. Settings → Users & Companies → Users
2. Select user
3. Click "Change Password"
4. Enter new password
5. Save

### Export Data

1. Select records
2. Action → Export
3. Choose fields
4. Download CSV

### Import Data

1. List view of model
2. Favorites → Import records
3. Upload CSV/Excel
4. Map fields
5. Test import

---

## 💾 Backup Schedule

- **Automated**: Daily at 2:00 AM (Africa/Addis_Ababa time)
- **Retention**: 
  - Daily: 7 days
  - Weekly: 4 weeks
  - Monthly: 12 months
- **Location**: `/opt/mesob-inventory/backups/`

---

## 🆘 Emergency Procedures

### System Compromised

```bash
# 1. Disconnect from internet (if possible)
sudo ufw deny out

# 2. Stop services
docker compose down

# 3. Backup current state
./scripts/backup.sh emergency_$(date +%Y%m%d)

# 4. Review logs
docker compose logs > emergency_logs.txt

# 5. Contact security team
# 6. Restore from clean backup if needed
```

### Data Corruption

```bash
# 1. Stop services immediately
docker compose down

# 2. Backup current state (even if corrupted)
./scripts/backup.sh corrupted_$(date +%Y%m%d)

# 3. Restore from last known good backup
./scripts/restore.sh /path/to/good_backup.tar.gz

# 4. Verify data
# 5. Start services
docker compose up -d
```

---

## 📱 Mobile Access

System is responsive and mobile-friendly:
- Access same URL from mobile browser
- Full functionality on tablets
- Basic features on phones

---

## 🎓 Training Resources

- **User Guide**: Settings → Help → Documentation
- **Video Tutorials**: (Add your links)
- **Support Portal**: (Add your links)

---

**Keep this document handy for daily operations!**

---

**Last Updated**: 2026-07-01  
**Version**: 1.0.0

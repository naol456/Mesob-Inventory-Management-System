# Mesob Inventory Management System

[![Odoo](https://img.shields.io/badge/Odoo-19.0-714B67?style=flat-square&logo=odoo)](https://www.odoo.com)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python)](https://www.python.org)
[![License](https://img.shields.io/badge/License-LGPL--3-blue?style=flat-square)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker)](deployment/)

A comprehensive, production-ready inventory management system built on Odoo 19 for the Federal Democratic Republic of Ethiopia (FDRE) Mesob Center. The system provides complete stock control, procurement, and asset tracking capabilities compliant with FDRE government standards.

---

## 🎯 Overview

The Mesob Inventory Management System is a professional-grade ERP module designed specifically for Ethiopian government institutions, implementing FDRE-compliant inventory control processes and documentation.

### Key Features

#### 📦 **Inventory Management**
- **Item Master** with Major/Sub Classifications (4401-4418)
- **Multi-store support** with department-based access control
- **Bin Card** and **Stock Record Card** tracking
- **ABC Classification** for inventory optimization
- **Reorder Alert System** with automated notifications

#### 📋 **Document Management**
- **Store Requisition** (Model 20)
- **Receiving & Inspection Voucher**
- **Issue Voucher** (Model 19)
- **Gate Pass & Dispatch Control**
- **Daily Stock Register (DSR)**
- Four-copy distribution system (FDRE compliant)

#### 🚛 **Procurement**
- **Purchase Request** workflow
- **Purchase Order** management
- **Supplier Management** with performance tracking
- **Receiving & Inspection** process
- Complete procurement audit trail

#### 📊 **Reporting & Analytics**
- Real-time dashboards and KPIs
- Stock movement reports
- Asset location mapping
- Procurement analytics
- Consumption pattern analysis
- Custom report generation

#### 🔐 **Security & Compliance**
- Role-based access control (RBAC)
- Storekeeper, Requester, Receiver, Inspector roles
- Department-based data isolation
- Comprehensive audit logging
- FDRE government standards compliance

#### 🌍 **Localization**
- **Amharic (አማርኛ)** translation support
- Ethiopian date/time formats
- FDRE document formatting
- Local business process adaptation

---

## 🏗️ Architecture

```
mesob-inventory-management-system/
├── addons/
│   └── mesob_inventory_base/          # Main application module
│       ├── models/                    # Business logic
│       ├── views/                     # User interface
│       ├── security/                  # Access control
│       ├── data/                      # Master data
│       ├── wizard/                    # Interactive wizards
│       ├── reports/                   # Report templates
│       ├── static/                    # CSS, JS, images
│       └── i18n/                      # Translations (Amharic)
├── deployment/                        # Production deployment
│   ├── docker-compose.yml            # Container orchestration
│   ├── Dockerfile                    # Application image
│   ├── config/                       # Configuration files
│   ├── scripts/                      # Automation scripts
│   └── docs/                         # Deployment guides
├── requirements.txt                   # Python dependencies
└── README.md                         # This file
```

---

## 🚀 Quick Start

### Prerequisites

- **Ubuntu 22.04 LTS / 24.04 LTS** (for production)
- **Docker 24.0+** and **Docker Compose V2**
- **4GB+ RAM** (8GB+ recommended)
- **2+ CPU cores**
- **40GB+ storage** (SSD recommended)
- **Domain name** (for SSL/HTTPS)

### Local Development

For development on Windows/macOS/Linux:

```bash
# Clone repository
git clone <repository-url>
cd mesob-inventory-management-system

# Install Odoo 19 (if not already installed)
# See: https://www.odoo.com/documentation/19.0/administration/install.html

# Start Odoo with custom addons
odoo -c odoo.conf --addons-path=addons
```

Access at: `http://localhost:8069`

### Production Deployment

**One-command deployment for Ubuntu VPS:**

```bash
# 1. Clone on server
git clone <repository-url> /opt/mesob-inventory
cd /opt/mesob-inventory/deployment

# 2. Configure environment
cp .env.example .env
nano .env  # Set passwords, domain, email

# 3. Deploy
sudo ./scripts/deploy.sh
```

**The deployment script automatically:**
- ✅ Installs Docker and dependencies
- ✅ Configures firewall (UFW)
- ✅ Sets up SSL/TLS (Let's Encrypt)
- ✅ Initializes database
- ✅ Starts all services
- ✅ Configures automated backups
- ✅ Sets up log rotation

**Access your system:** `https://your-domain.com`

📖 **Full deployment guide:** [deployment/README.md](deployment/README.md)

---

## 📦 Module Information

| Property | Value |
|----------|-------|
| **Module Name** | Mesob Inventory Management System |
| **Technical Name** | `mesob_inventory_base` |
| **Version** | 19.0.1.7.0 |
| **Category** | Inventory/Inventory |
| **License** | LGPL-3 |
| **Author** | FDRE Mesob Center |
| **Odoo Version** | 19.0 |
| **Dependencies** | `stock`, `mail` |

---

## 🔧 Configuration

### Initial Setup

1. **Create Database**
   - Access: `https://your-domain.com`
   - Master Password: From `.env` file
   - Database Name: `mesob_inventory_production`
   - ⚠️ **Uncheck "Load demonstration data"**

2. **Install Module**
   - Go to **Apps** menu
   - Search: `mesob_inventory_base`
   - Click **Install**

3. **Configure Company**
   - Settings → Companies
   - Update company information
   - Configure Ethiopian localization

4. **Setup Users**
   - Settings → Users & Companies → Users
   - Create users with appropriate roles:
     - **Storekeeper**: Full inventory control
     - **Requester**: Create requisitions
     - **Receiver**: Process receiving
     - **Inspector**: Quality inspection
     - **Admin**: System administration

5. **Configure Departments**
   - Inventory → Configuration → Departments
   - Create organizational departments
   - Assign stores to departments

6. **Setup Classifications**
   - Inventory → Configuration → Classifications
   - Review Major Classifications (4401-4418)
   - Create Sub-Classifications as needed

---

## 👥 User Roles & Permissions

| Role | Permissions |
|------|-------------|
| **Store Manager** | Full access to all inventory operations, reporting, and configuration |
| **Storekeeper** | Create/approve requisitions, issue items, record receipts, manage gate passes |
| **Requester** | Create and submit store requisitions |
| **Receiver** | Process receiving vouchers and inspections |
| **Inspector** | Conduct quality inspections and approvals |
| **Viewer** | Read-only access to inventory data |

---

## 📊 Key Workflows

### 1. Store Requisition Workflow
```
Requester → Create Requisition → Submit
    ↓
Storekeeper → Review → Approve
    ↓
Issue Voucher → Pick Items → Deliver
    ↓
Requester → Receive → Confirm
```

### 2. Receiving Workflow
```
Purchase Order → Goods Arrival
    ↓
Receiver → Create Receiving Voucher → Record Details
    ↓
Inspector → Quality Check → Approve/Reject
    ↓
Storekeeper → Update Stock → Store Items
```

### 3. Gate Pass Workflow
```
Department → Request Gate Pass
    ↓
Security → Review Documents
    ↓
Items Exit → Record Dispatch
    ↓
Gate Pass Closed → Archive
```

---

## 🛠️ Management

### Service Control

```bash
cd /opt/mesob-inventory/deployment

# Start services
docker compose up -d

# Stop services
docker compose down

# Restart services
docker compose restart

# View logs
docker compose logs -f odoo

# Service status
docker compose ps
```

### Backup & Restore

```bash
# Manual backup
./scripts/backup.sh

# List backups
ls -lh /opt/mesob-inventory/backups/

# Restore from backup
./scripts/restore.sh /path/to/backup.tar.gz
```

**Automated backups run daily at 2:00 AM** (configurable in `.env`)

### Module Updates

```bash
# Update module
docker compose exec odoo odoo \
  -c /etc/odoo/odoo.conf \
  -d mesob_inventory_production \
  -u mesob_inventory_base \
  --stop-after-init

# Restart
docker compose restart odoo
```

---

## 📈 Monitoring

### Health Checks

```bash
# System health
./scripts/health-check.sh

# Resource usage
docker stats

# Disk space
df -h

# Database size
docker compose exec postgres psql -U postgres -c "SELECT pg_database_size('mesob_inventory_production');"
```

### Key Metrics

- CPU and memory usage
- Database connections
- Response time
- Active users
- Stock levels
- Error rates

---

## 🔒 Security

### Security Features

- ✅ **SSL/TLS encryption** (Let's Encrypt)
- ✅ **Role-based access control** (RBAC)
- ✅ **Database access restricted** to localhost
- ✅ **Firewall configured** (UFW)
- ✅ **Automated security updates**
- ✅ **Audit logging** for all operations
- ✅ **Session management** with timeout
- ✅ **Password policies** enforced

### Security Best Practices

1. **Change all default passwords** in `.env` file
2. **Use strong passwords** (32+ characters for database)
3. **Enable automatic security updates**
4. **Review access logs regularly**
5. **Backup encryption keys**
6. **Limit SSH access** by IP
7. **Disable database manager** in production
8. **Regular security audits**

📖 **Full security guide:** [deployment/docs/SECURITY.md](deployment/docs/SECURITY.md)

---

## 🌍 Localization

### Amharic Translation

The system includes complete Amharic translation:

```
addons/mesob_inventory_base/i18n/am.po
```

**To update translations:**

```bash
# Generate PO file
docker compose exec odoo odoo \
  -c /etc/odoo/odoo.conf \
  -d mesob_inventory_production \
  --i18n-export=am.po \
  --modules=mesob_inventory_base

# Edit translations
nano addons/mesob_inventory_base/i18n/am.po

# Reload translations
docker compose restart odoo
```

---

## 📚 Documentation

| Document | Description |
|----------|-------------|
| [deployment/README.md](deployment/README.md) | Production deployment guide |
| [deployment/docs/DEPLOYMENT_GUIDE.md](deployment/docs/DEPLOYMENT_GUIDE.md) | Step-by-step deployment instructions |
| [deployment/docs/SECURITY.md](deployment/docs/SECURITY.md) | Security hardening checklist |
| [requirements.txt](requirements.txt) | Python dependencies |

---

## 🆘 Troubleshooting

### Common Issues

**Services won't start**
```bash
docker compose logs
docker compose ps
```

**Database connection error**
```bash
docker compose exec postgres pg_isready
```

**SSL certificate issues**
```bash
sudo certbot certificates
sudo certbot renew --dry-run
```

**Slow performance**
```bash
docker stats
htop
```

**Full troubleshooting guide:** [deployment/docs/DEPLOYMENT_GUIDE.md#troubleshooting](deployment/docs/DEPLOYMENT_GUIDE.md#troubleshooting)

---

## 🔄 Maintenance

### Regular Tasks

**Daily (Automated)**
- Database backup at 2:00 AM
- Log rotation
- Health checks

**Weekly**
- Review error logs
- Check disk space
- Monitor performance
- Security log review

**Monthly**
- System updates
- Test backup restore
- Review user access
- Performance optimization
- Security audit

---

## 🤝 Contributing

This is a private project developed for FDRE Mesob Center. For internal contributions:

1. Create feature branch: `git checkout -b feature/your-feature`
2. Make changes following coding standards
3. Test thoroughly
4. Submit pull request to `develop` branch

---

## 📄 License

This project is licensed under the **LGPL-3** license.

```
Mesob Inventory Management System
Copyright (C) 2024-2026 FDRE Mesob Center

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Lesser General Public License as published
by the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.
```

---

## 📞 Support

### For Deployment Issues

1. Check logs: `docker compose logs`
2. Review documentation: `deployment/docs/`
3. Run health check: `./scripts/health-check.sh`
4. Contact system administrator

### For Module Issues

1. Check Odoo logs: `docker compose logs odoo`
2. Review user permissions
3. Verify configuration
4. Contact development team

---

## 🎉 Acknowledgments

**Developed for:**
- Federal Democratic Republic of Ethiopia (FDRE)
- Mesob Center

**Built with:**
- [Odoo 19](https://www.odoo.com) - Enterprise Resource Planning
- [PostgreSQL 16](https://www.postgresql.org) - Database
- [Docker](https://www.docker.com) - Containerization
- [Nginx](https://www.nginx.com) - Web Server
- [Let's Encrypt](https://letsencrypt.org) - SSL/TLS

---

## 📊 Project Status

| Metric | Status |
|--------|--------|
| **Version** | 19.0.1.7.0 |
| **Status** | ✅ Production Ready |
| **Odoo Compatibility** | 19.0 |
| **Python Version** | 3.11+ |
| **Last Updated** | 2026-07-01 |

---

## 🚀 Getting Started

1. **[Deploy to production](deployment/README.md)** - Complete deployment guide
2. **Install module** - Via Odoo Apps menu
3. **Configure system** - Setup users, departments, classifications
4. **Train users** - Assign roles and provide training
5. **Go live** - Start managing inventory

---

**For production deployment instructions, see [deployment/README.md](deployment/README.md)**

---

*Made with ❤️ for FDRE Mesob Center*

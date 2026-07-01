# Mesob Inventory Management System - Security Hardening Guide

## Security Checklist

### Critical Security Measures (Must Implement)

- [ ] Change all default passwords
- [ ] Remove/disable demo accounts
- [ ] Configure SSL/TLS (HTTPS only)
- [ ] Enable firewall (UFW) with minimal open ports
- [ ] Disable PostgreSQL remote access
- [ ] Disable Odoo database manager interface
- [ ] Implement fail2ban for SSH protection
- [ ] Enable automatic security updates
- [ ] Configure regular security audits
- [ ] Implement proper backup encryption

---

## 1. Password Security

### Strong Password Policy

**Minimum Requirements:**
- Length: 20+ characters for admin passwords
- Complexity: Mix of uppercase, lowercase, numbers, symbols
- Uniqueness: Never reuse passwords
- Rotation: Change every 90 days

**Generate Strong Passwords:**

```bash
# Generate 32-character password
openssl rand -base64 32

# Generate 24-character password with special chars
pwgen -s -y 24 1
```

### Password Storage

- ✅ Store passwords in password manager (1Password, Bitwarden, etc.)
- ✅ Never commit passwords to version control
- ✅ Use environment variables for secrets
- ✅ Encrypt .env file at rest
- ❌ Never email passwords in plain text
- ❌ Never store passwords in code comments

---

## 2. Firewall Configuration

### UFW (Uncomplicated Firewall)

```bash
# Reset firewall
sudo ufw --force reset

# Default policies
sudo ufw default deny incoming
sudo ufw default allow outgoing

# Allow SSH (change 22 to your custom port)
sudo ufw allow 22/tcp comment 'SSH'

# Allow HTTP and HTTPS
sudo ufw allow 80/tcp comment 'HTTP'
sudo ufw allow 443/tcp comment 'HTTPS'

# Enable firewall
sudo ufw enable

# Verify rules
sudo ufw status verbose
```

### Advanced: Restrict SSH by IP

```bash
# Allow SSH only from specific IPs
sudo ufw delete allow 22/tcp
sudo ufw allow from 203.0.113.10 to any port 22 proto tcp comment 'SSH from office'
sudo ufw allow from 203.0.113.20 to any port 22 proto tcp comment 'SSH from admin'
```

---

## 3. SSH Hardening

### Disable Password Authentication

```bash
sudo nano /etc/ssh/sshd_config
```

Configure:
```
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
X11Forwarding no
MaxAuthTries 3
ClientAliveInterval 300
ClientAliveCountMax 2
```

Restart SSH:
```bash
sudo systemctl restart sshd
```

### Change SSH Port (Optional)

```bash
# Edit SSH config
sudo nano /etc/ssh/sshd_config

# Change port
Port 2222

# Update firewall
sudo ufw allow 2222/tcp
sudo ufw delete allow 22/tcp

# Restart SSH
sudo systemctl restart sshd
```

---

## 4. Fail2Ban Configuration

### Install and Configure

```bash
# Install fail2ban
sudo apt install fail2ban -y

# Create local config
sudo cp /etc/fail2ban/jail.conf /etc/fail2ban/jail.local

# Edit configuration
sudo nano /etc/fail2ban/jail.local
```

Configure SSH protection:
```ini
[sshd]
enabled = true
port = 22
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
bantime = 3600
findtime = 600
```

Configure Nginx protection:
```ini
[nginx-limit-req]
enabled = true
port = http,https
filter = nginx-limit-req
logpath = /var/log/mesob-inventory/nginx/error.log
maxretry = 5
findtime = 600
bantime = 3600
```

```bash
# Start fail2ban
sudo systemctl enable fail2ban
sudo systemctl start fail2ban

# Check status
sudo fail2ban-client status
```

---

## 5. PostgreSQL Security

### Restrict Network Access

Already configured in docker-compose.yml to only bind to localhost:

```yaml
ports:
  - "127.0.0.1:5432:5432"  # Only accessible from localhost
```

### Database User Permissions

```bash
# Connect to PostgreSQL
docker compose exec postgres psql -U postgres

# Create read-only user for backups
CREATE ROLE backup_user WITH LOGIN PASSWORD 'strong_password';
GRANT CONNECT ON DATABASE mesob_inventory_production TO backup_user;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO backup_user;
```

### Enable SSL for PostgreSQL

```bash
# Generate SSL certificate
openssl req -new -x509 -days 365 -nodes -text \
  -out /path/to/certs/server.crt \
  -keyout /path/to/certs/server.key

# Configure PostgreSQL to use SSL
# (Add to docker-compose.yml postgres command)
-c ssl=on
-c ssl_cert_file=/var/lib/postgresql/server.crt
-c ssl_key_file=/var/lib/postgresql/server.key
```

---

## 6. Odoo Security

### Disable Database Manager

In `deployment/config/odoo.conf`:

```ini
# Disable web-based database management (CRITICAL for production)
list_db = False
db_manager = False
```

### Restrict Database Access

```ini
# Only allow databases matching pattern
dbfilter = ^mesob.*$
```

### Configure Secure Cookies

```ini
# Require HTTPS for cookies
secure_cookie = True
```

### Disable Debug Mode

```bash
# In .env file, ensure these are NOT set or are false
DEBUG_MODE=false
DEV_MODE=
TEST_ENABLE=false
```

---

## 7. Nginx Security

### SSL/TLS Configuration

Already configured in `deployment/config/nginx/mesob.conf` with:

- ✅ TLS 1.2 and 1.3 only
- ✅ Strong cipher suites (Mozilla Modern)
- ✅ HSTS (HTTP Strict Transport Security)
- ✅ OCSP stapling
- ✅ Security headers

### Additional Headers

```nginx
# Already configured in mesob.conf
add_header X-Frame-Options "SAMEORIGIN" always;
add_header X-Content-Type-Options "nosniff" always;
add_header X-XSS-Protection "1; mode=block" always;
add_header Referrer-Policy "strict-origin-when-cross-origin" always;
add_header Strict-Transport-Security "max-age=63072000; includeSubDomains; preload" always;
```

### Rate Limiting

Already configured to prevent:
- ✅ Brute force attacks on login
- ✅ API abuse
- ✅ DDoS attacks

---

## 8. Automatic Security Updates

### Enable Unattended Upgrades

```bash
# Install unattended-upgrades
sudo apt install unattended-upgrades apt-listchanges -y

# Configure
sudo dpkg-reconfigure -plow unattended-upgrades

# Verify configuration
sudo nano /etc/apt/apt.conf.d/50unattended-upgrades
```

Enable security updates only:
```
Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}-security";
};
```

---

## 9. File Permissions

### Secure Configuration Files

```bash
# Secure .env file
chmod 600 /opt/mesob-inventory/deployment/.env
chown root:root /opt/mesob-inventory/deployment/.env

# Secure odoo.conf
chmod 600 /opt/mesob-inventory/deployment/config/odoo.conf
chown 101:101 /opt/mesob-inventory/deployment/config/odoo.conf

# Secure SSL certificates
chmod 600 /etc/letsencrypt/live/*/privkey.pem
```

### Docker Volume Permissions

```bash
# Set proper ownership
sudo chown -R 1000:1000 /opt/mesob-inventory/data/odoo
sudo chown -R 999:999 /opt/mesob-inventory/data/postgres
```

---

## 10. Backup Security

### Encrypt Backups

```bash
# Encrypt backup with GPG
gpg --symmetric --cipher-algo AES256 backup.tar.gz

# Decrypt when needed
gpg backup.tar.gz.gpg
```

### Secure Backup Storage

- ✅ Store backups off-site (S3, Backblaze, etc.)
- ✅ Encrypt backups at rest and in transit
- ✅ Implement backup access controls
- ✅ Test restore procedures regularly
- ✅ Monitor backup success/failure

---

## 11. Monitoring & Logging

### Enable Audit Logging

```bash
# Install auditd
sudo apt install auditd -y

# Configure audit rules
sudo nano /etc/audit/rules.d/mesob.rules
```

Add rules:
```
# Monitor config changes
-w /opt/mesob-inventory/deployment/.env -p wa -k mesob_config
-w /opt/mesob-inventory/deployment/config/ -p wa -k mesob_config

# Monitor sensitive files
-w /etc/passwd -p wa -k passwd_changes
-w /etc/shadow -p wa -k shadow_changes
```

### Centralized Logging

Configure log forwarding to external service (Papertrail, Loggly, etc.)

---

## 12. Security Scanning

### Vulnerability Scanning

```bash
# Install and run Lynis
sudo apt install lynis -y
sudo lynis audit system

# Check Docker security
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  aquasec/trivy image mesob-inventory:19.0
```

### Penetration Testing

Schedule regular penetration testing:
- Application security testing
- Infrastructure testing
- Social engineering testing

---

## 13. Incident Response

### Security Incident Checklist

1. **Detect**: Monitor logs for suspicious activity
2. **Contain**: Isolate affected systems
3. **Investigate**: Analyze logs and identify root cause
4. **Remediate**: Patch vulnerabilities
5. **Recover**: Restore from clean backups
6. **Document**: Record incident details
7. **Review**: Update security procedures

### Emergency Contacts

Maintain list of:
- Security team contacts
- Incident response team
- Third-party security consultants
- Law enforcement (if needed)

---

## 14. Compliance

### Data Protection (GDPR-style)

- ✅ Encrypt data at rest and in transit
- ✅ Implement access controls
- ✅ Log all data access
- ✅ Provide data export functionality
- ✅ Implement data retention policies
- ✅ Enable data deletion on request

### Audit Requirements

- ✅ Enable comprehensive logging
- ✅ Retain logs for required period (1 year+)
- ✅ Implement log integrity checks
- ✅ Regular security audits
- ✅ Access control reviews

---

## 15. Security Testing

### Regular Security Checks

**Weekly:**
- Review firewall logs
- Check failed login attempts
- Monitor disk space
- Review backup logs

**Monthly:**
- Update all packages
- Review user access
- Test backup restore
- Security scan

**Quarterly:**
- Password rotation
- Access control review
- Penetration testing
- Security training

---

## Security Resources

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CIS Ubuntu Hardening Guide](https://www.cisecurity.org/)
- [Docker Security Best Practices](https://docs.docker.com/engine/security/)
- [Odoo Security Documentation](https://www.odoo.com/documentation/19.0/administration/security.html)
- [Let's Encrypt Best Practices](https://letsencrypt.org/docs/)

---

**Document Version**: 1.0.0  
**Last Updated**: 2026-07-01  
**Review Frequency**: Quarterly

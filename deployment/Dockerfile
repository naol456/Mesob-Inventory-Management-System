# =============================================================================
# Mesob Inventory Management System - Production Dockerfile
# =============================================================================
# 
# Multi-stage build for optimized, secure Odoo 19 container
# Based on official Odoo image with custom dependencies and security hardening
#
# =============================================================================

FROM odoo:19.0 AS base

# Metadata
LABEL maintainer="FDRE Mesob Center <admin@mesobcenter.et>"
LABEL description="Mesob Inventory Management System - Odoo 19 Production Container"
LABEL version="19.0.1.7.0"

# Set environment variables
ENV ODOO_VERSION=19.0 \
    ODOO_RC=/etc/odoo/odoo.conf \
    DEBIAN_FRONTEND=noninteractive

# Switch to root for system-level installations
USER root

# -----------------------------------------------------------------------------
# System Dependencies
# -----------------------------------------------------------------------------

RUN apt-get update && apt-get install -y --no-install-recommends \
    # Build essentials
    build-essential \
    # Python development headers
    python3-dev \
    # SSL/TLS support
    ca-certificates \
    # XML processing (required by mesob_inventory_base)
    libxml2-dev \
    libxslt1-dev \
    # PostgreSQL client
    postgresql-client \
    # Locale support for Amharic
    locales \
    # Image processing
    libjpeg-dev \
    libpng-dev \
    # Fonts for PDF reports
    fonts-liberation \
    fonts-dejavu \
    # Utilities
    curl \
    wget \
    # Clean up
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------------------
# Locale Configuration (Amharic + English)
# -----------------------------------------------------------------------------

RUN echo "en_US.UTF-8 UTF-8" >> /etc/locale.gen \
    && echo "am_ET.UTF-8 UTF-8" >> /etc/locale.gen \
    && locale-gen \
    && update-locale LANG=en_US.UTF-8

ENV LANG=en_US.UTF-8 \
    LANGUAGE=en_US:en \
    LC_ALL=en_US.UTF-8

# -----------------------------------------------------------------------------
# Python Dependencies
# -----------------------------------------------------------------------------

# Copy requirements file
COPY requirements.txt /tmp/requirements.txt

# Install Python dependencies
RUN pip3 install --no-cache-dir --upgrade pip setuptools wheel \
    && pip3 install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt

# -----------------------------------------------------------------------------
# Custom Addons
# -----------------------------------------------------------------------------

# Create custom addons directory
RUN mkdir -p /mnt/extra-addons

# Copy custom modules
COPY --chown=odoo:odoo addons/ /mnt/extra-addons/

# Set proper permissions
RUN chmod -R 755 /mnt/extra-addons \
    && find /mnt/extra-addons -type f -exec chmod 644 {} \; \
    && find /mnt/extra-addons -type d -exec chmod 755 {} \;

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

# Create config directory
RUN mkdir -p /etc/odoo \
    && chown -R odoo:odoo /etc/odoo

# Copy Odoo configuration
COPY --chown=odoo:odoo config/odoo.conf /etc/odoo/odoo.conf

# Secure configuration file permissions
RUN chmod 600 /etc/odoo/odoo.conf

# -----------------------------------------------------------------------------
# Data Directories
# -----------------------------------------------------------------------------

# Create data directories with proper ownership
RUN mkdir -p /var/lib/odoo \
    && mkdir -p /var/log/odoo \
    && chown -R odoo:odoo /var/lib/odoo \
    && chown -R odoo:odoo /var/log/odoo

# -----------------------------------------------------------------------------
# Health Check
# -----------------------------------------------------------------------------

# Copy health check script
COPY --chown=odoo:odoo scripts/healthcheck.py /usr/local/bin/healthcheck.py
RUN chmod +x /usr/local/bin/healthcheck.py

# Configure Docker health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD python3 /usr/local/bin/healthcheck.py || exit 1

# -----------------------------------------------------------------------------
# Security Hardening
# -----------------------------------------------------------------------------

# Remove unnecessary packages and files
RUN apt-get autoremove -y \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* \
    && rm -rf /var/tmp/*

# Create non-root user directories
RUN mkdir -p /home/odoo/.local \
    && chown -R odoo:odoo /home/odoo

# -----------------------------------------------------------------------------
# Runtime Configuration
# -----------------------------------------------------------------------------

# Switch to odoo user (non-root)
USER odoo

# Set working directory
WORKDIR /mnt/extra-addons

# Expose Odoo services
# 8069: HTTP (behind nginx reverse proxy)
# 8072: Longpolling (for real-time features)
EXPOSE 8069 8072

# Volumes for persistent data
VOLUME ["/var/lib/odoo", "/var/log/odoo"]

# Default command (can be overridden in docker-compose.yml)
CMD ["odoo", "-c", "/etc/odoo/odoo.conf"]

# =============================================================================
# Build Instructions:
# 
# docker build -t mesob-inventory:19.0.1.7.0 -f deployment/Dockerfile .
#
# =============================================================================

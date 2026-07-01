#!/usr/bin/env python3
"""
=============================================================================
Mesob Inventory Management System - Health Check Script
=============================================================================

Docker health check script that verifies Odoo is responsive and healthy.

Returns:
    Exit 0: Healthy
    Exit 1: Unhealthy

=============================================================================
"""

import sys
import urllib.request
import urllib.error
import socket


def check_odoo_http():
    """Check if Odoo HTTP server is responding."""
    try:
        url = "http://localhost:8069/web/health"
        req = urllib.request.Request(url, method='GET')
        req.add_header('User-Agent', 'Mesob-HealthCheck/1.0')
        
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                return True
    except (urllib.error.URLError, urllib.error.HTTPError, socket.timeout):
        pass
    
    return False


def check_database_connection():
    """Check if database connection is available."""
    try:
        import psycopg2
        import os
        
        conn = psycopg2.connect(
            host=os.environ.get('HOST', 'postgres'),
            port=os.environ.get('PORT', '5432'),
            user=os.environ.get('USER', 'odoo'),
            password=os.environ.get('PASSWORD', ''),
            database='postgres',
            connect_timeout=5
        )
        conn.close()
        return True
    except Exception:
        pass
    
    return False


def main():
    """Main health check execution."""
    # Check HTTP endpoint
    if not check_odoo_http():
        print("UNHEALTHY: Odoo HTTP server not responding", file=sys.stderr)
        sys.exit(1)
    
    # Check database connection
    if not check_database_connection():
        print("UNHEALTHY: Database connection failed", file=sys.stderr)
        sys.exit(1)
    
    print("HEALTHY: All checks passed")
    sys.exit(0)


if __name__ == "__main__":
    main()

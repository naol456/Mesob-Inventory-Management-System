#!/bin/bash
# =============================================================================
# Mesob Inventory Management System - Database Initialization Script
# =============================================================================
#
# This script runs during PostgreSQL container initialization to:
#   - Create Odoo database user
#   - Grant appropriate permissions
#   - Configure database settings
#
# =============================================================================

set -e

# Create Odoo database user if it doesn't exist
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Create Odoo user if not exists
    DO \$\$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '${POSTGRES_ODOO_USER:-odoo}') THEN
            CREATE ROLE "${POSTGRES_ODOO_USER:-odoo}" WITH LOGIN PASSWORD '${POSTGRES_ODOO_PASSWORD}';
        END IF;
    END
    \$\$;

    -- Grant database creation privilege
    ALTER ROLE "${POSTGRES_ODOO_USER:-odoo}" CREATEDB;

    -- Grant necessary permissions
    GRANT ALL PRIVILEGES ON DATABASE postgres TO "${POSTGRES_ODOO_USER:-odoo}";

    -- Create extensions (if needed)
    CREATE EXTENSION IF NOT EXISTS "unaccent";
    CREATE EXTENSION IF NOT EXISTS "pg_trgm";

EOSQL

echo "Database initialization completed successfully"

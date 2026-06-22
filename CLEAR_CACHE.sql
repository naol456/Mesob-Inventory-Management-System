-- Clear Odoo Web Assets Cache
-- Run this SQL query directly in your PostgreSQL database to clear cached assets
-- This can resolve issues with stale CSS/JS or module loading errors

DELETE FROM ir_attachment WHERE name LIKE '%assets%';

-- Optional: Clear all view cache
DELETE FROM ir_ui_view WHERE type = 'qweb';

-- To run this from command line (adjust connection details):
-- psql -U odoo -d your_database_name -f CLEAR_CACHE.sql

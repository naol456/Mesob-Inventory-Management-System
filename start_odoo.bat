@echo off
REM ────────────────────────────────═══════════════════════════════════════
REM Mesob Odoo Local Development Script (With Auto-PDF Path Injection)
REM ────────────────────────────────═══════════════════════════════════════
REM Automatically appends Odoo's thirdparty wkhtmltopdf folder to Windows PATH
REM and runs Odoo with auto-reload, SCSS recompilation, and GraceDB db-filter!
REM ────────────────────────────────═══════════════════════════════════════

SET PATH=%PATH%;C:\Program Files\Odoo 19.0.20260218\thirdparty

"C:\Program Files\Odoo 19.0.20260218\python\python.exe" "C:\Program Files\Odoo 19.0.20260218\server\odoo-bin" -c "C:\Program Files\Odoo 19.0.20260218\server\odoo.conf" -d GraceDB --db-filter=^GraceDB$ --longpolling-port=0 --dev=all %*

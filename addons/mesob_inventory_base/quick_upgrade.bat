@echo off
echo ========================================
echo Quick Upgrade - Version 19.0.1.10.1
echo SRS 4.8: Stock Taking (Loading Order Fixed)
echo ========================================
echo.

cd /d "C:\Program Files\Odoo 19.0.20260218\server"

python odoo-bin -d mesob_fresh -u mesob_inventory_base --stop-after-init

echo.
echo ========================================
echo Upgrade Complete!
echo ========================================
echo.
echo NOW: Press Ctrl+F5 in your browser!
echo.
echo Check: Inventory -^> Stock Taking menu
echo.
pause

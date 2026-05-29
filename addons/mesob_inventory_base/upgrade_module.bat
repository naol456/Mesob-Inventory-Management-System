@echo off
echo ========================================
echo Upgrading mesob_inventory_base module
echo ========================================
echo.

cd /d "C:\Program Files\Odoo 19.0.20260218\server"

echo Running upgrade command...
python odoo-bin -d mesob_fresh -u mesob_inventory_base --stop-after-init

echo.
echo ========================================
echo Upgrade complete!
echo ========================================
pause

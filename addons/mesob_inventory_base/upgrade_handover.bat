@echo off
echo ========================================
echo Upgrading Mesob Inventory Base Module
echo Adding Handover Feature (SRS 4.9)
echo Version: 19.0.1.11.0
echo ========================================
echo.

cd "C:\Program Files\Odoo 19.0.20260218\server"
"C:\Users\HP\AppData\Local\Programs\Python\Python312\python.exe" odoo-bin -d mesob_fresh -u mesob_inventory_base --stop-after-init

echo.
echo ========================================
echo Upgrade Complete!
echo ========================================
echo.
echo IMPORTANT: You must restart the Odoo server for the new models to be loaded!
echo.
pause

@echo off
echo ========================================
echo CRITICAL FIX: Storekeeper Stock Records
echo ========================================
echo.
echo Version: 19.0.1.5.2
echo Database: mesob_fresh
echo.
echo PROBLEM: Storekeepers cannot confirm receiving orders
echo ERROR: "Access Error - not allowed to create Stock Record Card"
echo.
echo SOLUTION: Add Storekeeper access to:
echo - Stock Record Cards (full access)
echo - FIFO Layers (full access)
echo.
echo This will allow Storekeepers to:
echo - Confirm receiving orders
echo - Confirm issue vouchers
echo - Auto-create stock records
echo.
pause

echo.
echo Changing to Odoo server directory...
cd "C:\Program Files\Odoo 19.0.20260218\server"

echo.
echo Running module upgrade...
echo.
python odoo-bin -d mesob_fresh -u mesob_inventory_base --stop-after-init

echo.
echo ========================================
echo Fix Applied!
echo ========================================
echo.
echo Next steps:
echo 1. Start Odoo server: python odoo-bin -c odoo.conf
echo 2. Login as Storekeeper
echo 3. Try to confirm a receiving order
echo 4. Should work without errors!
echo.
pause

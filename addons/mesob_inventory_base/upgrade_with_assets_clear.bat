@echo off
echo ========================================
echo Upgrading mesob_inventory_base module
echo WITH ASSETS CACHE CLEAR
echo ========================================
echo.

cd /d "C:\Program Files\Odoo 19.0.20260218\server"

echo Step 1: Clearing assets cache...
python odoo-bin -d mesob_fresh --dev=all --stop-after-init

echo.
echo Step 2: Running upgrade command...
python odoo-bin -d mesob_fresh -u mesob_inventory_base --stop-after-init

echo.
echo ========================================
echo Upgrade complete!
echo ========================================
echo.
echo IMPORTANT: Now do the following:
echo 1. Go to your browser
echo 2. Press Ctrl+Shift+Delete to open Clear Browsing Data
echo 3. Select "Cached images and files"
echo 4. Click "Clear data"
echo 5. OR simply press Ctrl+F5 on the Odoo page
echo.
pause

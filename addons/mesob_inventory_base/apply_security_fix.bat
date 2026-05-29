@echo off
echo ========================================
echo Security Fix: Receiving Process Access
echo ========================================
echo.
echo Version: 19.0.1.5.1
echo Database: mesob_fresh
echo.
echo This will add PAO access for:
echo - Receiving Orders
echo - Model 19 Inspection Reports
echo - Daily Stock Reports (DSR)
echo.
echo Access restricted to: PAO and Storekeeper ONLY
echo All other users: Read-only access
echo.
echo Total: 6 new access rules will be added
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
echo Security Fix Applied!
echo ========================================
echo.
echo Next steps:
echo 1. Start Odoo server: python odoo-bin -c odoo.conf
echo 2. Test PAO access to Receiving Orders
echo 3. Verify Storekeeper access unchanged
echo 4. Verify other users have read-only access
echo.
echo See SECURITY_FIX_SUMMARY.md for testing details
echo.
pause

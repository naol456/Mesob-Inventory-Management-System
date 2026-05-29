@echo off
echo ========================================
echo UI FIX: Issue Voucher Interface
echo ========================================
echo.
echo Version: 19.0.1.5.3
echo Database: mesob_fresh
echo.
echo PROBLEM: Issue voucher UI is invisible/unresponsive
echo - Text appearing invisible
echo - Complex styling causing display issues
echo - Unresponsive interface
echo.
echo SOLUTION: Clean, simple, responsive design
echo - Removed complex gradients and styling
echo - Standard Bootstrap layout
echo - Better readability and usability
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
echo UI Fix Applied!
echo ========================================
echo.
echo Next steps:
echo 1. Start Odoo server: python odoo-bin -c odoo.conf
echo 2. Go to Issue Vouchers
echo 3. Open or create an issue voucher
echo 4. UI should now be clean and readable!
echo.
pause

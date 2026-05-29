@echo off
echo ========================================
echo MAJOR FIX: Issue Voucher Usability
echo ========================================
echo.
echo Version: 19.0.1.5.4
echo Database: mesob_fresh
echo.
echo PROBLEMS FIXED:
echo 1. Requisition field not editable (was readonly + required)
echo 2. Department field not editable (was related field)
echo 3. Lines not saving after adding them
echo 4. Confusing UI with complex styling
echo.
echo SOLUTIONS:
echo 1. Requisition now OPTIONAL and editable
echo 2. Department now EDITABLE text field
echo 3. Added purpose field
echo 4. Simple, clean UI
echo 5. Lines will save properly
echo.
echo You can now create issue vouchers WITHOUT requisition!
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
echo 2. Go to Issue Vouchers
echo 3. Click "New"
echo 4. Enter Department name directly
echo 5. Add items - they will SAVE!
echo 6. Optionally select requisition (auto-fills department)
echo.
pause

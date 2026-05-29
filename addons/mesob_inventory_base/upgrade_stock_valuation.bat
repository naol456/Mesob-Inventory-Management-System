@echo off
echo ========================================
echo Upgrading mesob_inventory_base to 19.0.1.7.0
echo Adding Stock Valuation Reports (SRS 4.6)
echo ========================================
echo.

echo Running upgrade...
cd /d "C:\Program Files\Odoo 19.0.20260218\server"
python odoo-bin -d mesob_fresh -u mesob_inventory_base --stop-after-init

echo.
echo ========================================
echo Upgrade complete!
echo ========================================
echo.
echo New features added:
echo - Stock Valuation by Classification report
echo - Stock Valuation Summary report
echo - FIFO-based valuation with estimated cost tracking
echo.
echo Access the reports from:
echo Stock Records ^> Stock Valuation by Classification
echo Stock Records ^> Stock Valuation Summary
echo.
pause

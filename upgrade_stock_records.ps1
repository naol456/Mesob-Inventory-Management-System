# Upgrade script for Stock Records & Valuation features

Write-Host "╔══════════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║                                                              ║" -ForegroundColor Cyan
Write-Host "║   Stock Records & Valuation Module Upgrade                  ║" -ForegroundColor Cyan
Write-Host "║                                                              ║" -ForegroundColor Cyan
Write-Host "╚══════════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""

# Step 1: Stop Odoo
Write-Host "📦 Step 1: Stopping Odoo..." -ForegroundColor Yellow
docker-compose down
Write-Host "✅ Odoo stopped" -ForegroundColor Green
Write-Host ""

# Step 2: Start Odoo
Write-Host "🚀 Step 2: Starting Odoo..." -ForegroundColor Yellow
docker-compose up -d
Write-Host "⏳ Waiting for Odoo to start (15 seconds)..." -ForegroundColor Yellow
Start-Sleep -Seconds 15
Write-Host "✅ Odoo started" -ForegroundColor Green
Write-Host ""

# Step 3: Upgrade Module
Write-Host "⬆️  Step 3: Upgrading mesob_inventory_base module..." -ForegroundColor Yellow
docker-compose exec -T web odoo -d mesoob -u mesob_inventory_base --stop-after-init
Write-Host "✅ Module upgraded" -ForegroundColor Green
Write-Host ""

# Step 4: Restart Odoo
Write-Host "🔄 Step 4: Restarting Odoo..." -ForegroundColor Yellow
docker-compose restart web
Write-Host "⏳ Waiting for restart (10 seconds)..." -ForegroundColor Yellow
Start-Sleep -Seconds 10
Write-Host "✅ Odoo restarted" -ForegroundColor Green
Write-Host ""

# Step 5: Verify
Write-Host "🔍 Step 5: Verifying installation..." -ForegroundColor Yellow
Write-Host ""
docker-compose exec -T db psql -U odoo -d mesoob -c "SELECT name, state FROM ir_module_module WHERE name = 'mesob_inventory_base';"
Write-Host ""

Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host "✅ UPGRADE COMPLETE!" -ForegroundColor Green
Write-Host "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" -ForegroundColor Cyan
Write-Host ""
Write-Host "📋 Next Steps:" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. Open Odoo: http://localhost:8069"
Write-Host "2. Login with your credentials"
Write-Host "3. Go to: Mesob Inventory → Stock Records & Valuation"
Write-Host "4. Verify new menus:"
Write-Host "   ✓ Bin Cards"
Write-Host "   ✓ Stock Record Cards"
Write-Host "   ✓ FIFO Cost Layers"
Write-Host "   ✓ Valuation Configuration"
Write-Host ""
Write-Host "📖 Documentation: STOCK_RECORDS_COMPLETE.md" -ForegroundColor Cyan
Write-Host "📚 User Guide: addons/mesob_inventory_base/material/STOCK_RECORDS_VALUATION_GUIDE.md" -ForegroundColor Cyan
Write-Host ""
Write-Host "🎉 Happy tracking!" -ForegroundColor Green
Write-Host ""

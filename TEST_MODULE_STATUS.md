# Module Status Check

## How to verify the Issue of Stocks module is working:

### 1. Check Menu Items
- Go to **Mesob Inventory** in the main menu
- Click **Operations**
- You should see:
  - Requisitions (Model 20)
  - **Issue Vouchers (Model 22)** ← NEW

### 2. Test Requisition Enhancement
- Go to **Mesob Inventory → Operations → Requisitions**
- Open any existing requisition OR create a new one
- The requisition should have these NEW states in the statusbar:
  - Draft → Submitted → Approved → **Issued** → **Received**

### 3. Test Issue Voucher Creation
- Create a requisition
- Submit it
- As PAO user, approve it
- You should see a NEW button: **Create Issue Voucher**
- Click it to create an issue voucher

### 4. Check Developer Mode
If the above doesn't work:
1. Enable Developer Mode: Settings → Activate developer mode
2. Go to Settings → Technical → Database Structure → Models
3. Search for "mesob.inventory.issue.voucher"
4. If you see it, the model is loaded

### 5. Force Module Update
If nothing works, try:
1. Go to Apps
2. Remove "Apps" filter
3. Search "mesob"
4. Click on "Mesob Inventory Base"
5. Top right, click "Upgrade" button
6. Wait for page to reload

### 6. Check Browser Console
- Press F12 to open browser console
- Look for any JavaScript errors
- Try clicking Upgrade again and watch for errors

## If Module Won't Upgrade

The module files are correct and loaded (no Python errors in logs).
The issue might be:
- Browser cache - Try Ctrl+F5 to hard refresh
- Session issue - Try logging out and back in
- Database state - The module might already be at the latest version

## Verification Commands

You can also verify from the Odoo shell. In your terminal:

```bash
docker-compose exec web odoo shell -d odoo
```

Then in the Odoo shell:
```python
# Check if model exists
env['ir.model'].search([('model', '=', 'mesob.inventory.issue.voucher')])

# Check module state
env['ir.module.module'].search([('name', '=', 'mesob_inventory_base')]).state

# List all mesob models
env['ir.model'].search([('model', 'like', 'mesob%')]).mapped('model')
```

## Current Status

Based on the logs:
- ✅ No Python syntax errors
- ✅ Module loads successfully
- ✅ Models are registered
- ⚠️ Warnings about 'tracking' and 'states' parameters (these are just warnings, not errors)

The module SHOULD be working. The upgrade button not responding might be a UI issue, not a module issue.

# Emergency Upgrade Instructions

## Problem
The view is cached in database with old structure. We need to force update.

## Solution: Upgrade from Command Line

### Step 1: Stop Odoo
- Stop the Odoo service/server completely

### Step 2: Open Command Prompt as Administrator
- Press Windows + X
- Click "Command Prompt (Admin)" or "PowerShell (Admin)"

### Step 3: Navigate to Odoo Directory
```cmd
cd "C:\Program Files\Odoo 19.0.20260218\server"
```

### Step 4: Run Upgrade Command
```cmd
python odoo-bin -u mesob_inventory_base -d your_database_name --stop-after-init
```

**Replace `your_database_name` with your actual database name!**

### Step 5: Start Odoo Normally
- Start Odoo service again
- Login to Odoo
- Module should be upgraded

---

## If That Still Fails - Delete Cached View

### From Odoo UI (Easiest)

1. **Enable Developer Mode:**
   - Go to **Settings**
   - Scroll to bottom
   - Click **Activate the developer mode**

2. **Delete the problematic view:**
   - Go to: **Settings** → **Technical** → **User Interface** → **Views**
   - In search box, type: **"issue.voucher.form"**
   - Find view named **"mesob.inventory.issue.voucher.form"**
   - Click on it
   - Click **Action** → **Delete** (or Archive)

3. **Upgrade again:**
   - Go to **Apps**
   - Search "Mesob Inventory"
   - Click **Upgrade**

---

## Fastest Solution: Use Database Manager

If you have access:

```sql
DELETE FROM ir_ui_view WHERE name LIKE '%issue_voucher%';
```

Then restart and upgrade.

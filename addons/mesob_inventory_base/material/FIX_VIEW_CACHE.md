# Fix View Cache Error - Step by Step Guide

## Problem
You're getting this error when trying to upgrade:
```
Field "item_id" does not exist in model "mesob.inventory.issue.voucher"
```

This is because Odoo has a **cached view** in the database with the wrong structure. The view thinks `item_id` belongs to the header model, but it actually belongs to the line model.

## Solution Options

### Option A: Delete View via Odoo UI (Easiest - If You Can Access Developer Mode)

#### Step 1: Activate Developer Mode
1. **Open Odoo** in your browser: http://localhost:8069
2. **Log in** to your database
3. **In the URL bar**, add `?debug=1` to the end
   - Example: Change `http://localhost:8069/web#menu_id=...`
   - To: `http://localhost:8069/web?debug=1`
4. **Press Enter** - the page will reload
5. **Look for a bug icon** 🐞 in the top right corner (this confirms Developer Mode is active)

#### Step 2: Delete the Cached View
1. **Go to Settings** menu
2. **Click on Technical** (should now be visible)
3. **Click on User Interface** → **Views**
4. **In the search box**, type: `mesob.inventory.issue.voucher.form`
5. **Click on the view** to open it
6. **Click the Action menu** (⚙️ gear icon) → **Delete**
7. **Confirm** the deletion

#### Step 3: Upgrade the Module
1. **Go to Apps** menu
2. **Remove the "Apps" filter** (click ❌ on the search bar)
3. **Search for**: `mesob_inventory_base`
4. **Click "Upgrade"** button
5. **Wait** for upgrade to complete
6. ✅ **Success!** The view will be recreated from your XML file

---

### Option B: Delete View via PostgreSQL (If Option A Doesn't Work)

If you can't access Developer Mode or can't find the view in the UI, you can delete it directly from the PostgreSQL database.

#### Step 1: Find Your Database Connection Info
1. **Open Odoo configuration file**: `C:\Program Files\Odoo 19.0.20260218\server\odoo.conf`
2. **Look for these lines**:
   ```
   db_host = localhost
   db_port = 5432
   db_user = odoo
   db_password = [your password]
   ```
3. **Also note your database name** (you used it to login to Odoo)

#### Step 2: Connect to PostgreSQL

**Using pgAdmin (If installed):**
1. **Open pgAdmin**
2. **Connect to** PostgreSQL server (localhost:5432)
3. **Expand** Databases → [Your Database Name]
4. **Right-click** on your database → **Query Tool**
5. **Skip to Step 3**

**Using psql Command Line:**
1. **Open Command Prompt** (cmd)
2. **Navigate to** PostgreSQL bin folder:
   ```cmd
   cd "C:\Program Files\PostgreSQL\[version]\bin"
   ```
3. **Connect to** your database:
   ```cmd
   psql -U odoo -d [your_database_name]
   ```
4. **Enter password** when prompted

#### Step 3: Run SQL to Delete Cached View

**Copy and paste this SQL command:**

```sql
-- Delete the cached form view
DELETE FROM ir_ui_view 
WHERE name = 'mesob.inventory.issue.voucher.form'
AND model = 'mesob.inventory.issue.voucher';

-- Check if it was deleted (should return 0 rows)
SELECT id, name, model FROM ir_ui_view 
WHERE name = 'mesob.inventory.issue.voucher.form';
```

**Expected output:**
- First command: `DELETE 1` (or similar - means 1 view was deleted)
- Second command: `(0 rows)` (means the view is gone)

#### Step 4: Upgrade the Module in Odoo
1. **Go back to Odoo** in your browser
2. **Go to Apps** menu
3. **Search for**: `mesob_inventory_base`
4. **Click "Upgrade"** button
5. ✅ **Success!** Module should upgrade without errors

---

### Option C: Uninstall and Reinstall (Last Resort - Will Lose Data)

⚠️ **WARNING**: This will delete all your inventory data! Only use if you have a backup or if this is a test system.

1. **Backup your database** (Settings → Database Manager → Backup)
2. **Go to Apps** → Search for `mesob_inventory_base`
3. **Click "Uninstall"**
4. **Confirm** uninstall
5. **Click "Install"** to reinstall with clean views

---

## Why This Happened

The issue occurred because:
1. We changed the model structure (moved `item_id` field to the line model)
2. Odoo **cached the old view** in the `ir_ui_view` database table
3. When upgrading, Odoo **validates against the cached view** (wrong structure)
4. The validation fails because it's looking for `item_id` in the wrong model

## Why Your UI Design is Safe

Your beautiful UI design (navy/yellow Ethiopian colors) is stored in:
- ✅ `views/mesob_inventory_issue_voucher_views.xml` (the XML file we edited)
- ✅ `static/src/scss/mesob_inventory_modern.scss` (the CSS/SCSS files)

**NOT** in the database cache! When you delete the cached view and upgrade:
- The database cache is deleted ❌
- Odoo reads your XML file ✅
- Creates a new cache from your XML ✅
- Your design is preserved ✅

---

## Need Help?

If you get stuck at any step:
1. **Take a screenshot** of the error
2. **Note which step** you're on
3. **Ask for help** with specific details

## After Success

Once the upgrade works, test the Issue Voucher:
1. Go to **Inventory → Requisitions**
2. Create and approve a requisition
3. Click **"Create Issue Voucher"** button
4. The lines should now fill automatically ✅
5. Click **"Issue Materials"** button
6. Check that bin cards and stock records are posted ✅

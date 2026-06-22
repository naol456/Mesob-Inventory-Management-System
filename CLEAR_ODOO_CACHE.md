# Clear Odoo Cache & Assets

## Quick SQL Commands (Run in Database)

### Option 1: Clear ALL Assets (Recommended for module issues)
```sql
DELETE FROM ir_attachment WHERE name LIKE '%assets%';
```

### Option 2: Clear Web Assets Only
```sql
DELETE FROM ir_attachment 
WHERE res_model = 'ir.ui.view' 
  AND name LIKE '%assets%';
```

### Option 3: Nuclear - Clear ALL Attachments (Be Careful!)
```sql
-- This clears everything including uploaded files!
-- Only use if you know what you're doing
DELETE FROM ir_attachment WHERE res_model IN ('ir.ui.view', 'ir.asset');
```

## How to Run SQL in Odoo

### Method 1: Using pgAdmin or Database Tool
1. Open your PostgreSQL client
2. Connect to your Odoo database
3. Run the SQL command above
4. Restart Odoo server
5. Refresh browser (Ctrl+Shift+R)

### Method 2: Using Odoo Shell
```bash
cd "C:\Program Files\Odoo 19.0.20260218\server"
python odoo-bin shell -d your_database_name

# In the shell:
>>> self.env.cr.execute("DELETE FROM ir_attachment WHERE name LIKE '%assets%'")
>>> self.env.cr.commit()
>>> exit()
```

### Method 3: Using Python Script (Safest)
```python
# clear_cache.py
import psycopg2

# Database connection
conn = psycopg2.connect(
    dbname="your_database_name",
    user="odoo",
    password="your_password",
    host="localhost",
    port="5432"
)

cur = conn.cursor()

# Clear assets
cur.execute("DELETE FROM ir_attachment WHERE name LIKE '%assets%'")
conn.commit()

print(f"Cleared {cur.rowcount} asset records")

cur.close()
conn.close()
```

## After Clearing Cache

1. **Restart Odoo Service**
   - Windows Services → Find "Odoo" → Restart
   - OR: Stop and Start Odoo application

2. **Clear Browser Cache**
   - Press: `Ctrl + Shift + Delete`
   - OR: `Ctrl + Shift + R` (hard refresh)
   - OR: Open in Incognito/Private window

3. **Try Module Upgrade Again**
   - Apps → Mesob Inventory → Upgrade

## Why Cache Issues Happen

- **Assets compiled during upgrade** get cached in database
- **Old JavaScript/CSS** can cause RPC errors
- **Stale references** to deleted/changed actions
- **Browser cache** serves old code even after server update

## Signs You Need to Clear Cache

- ✅ "Action not found" errors
- ✅ RPC_ERROR with no clear cause
- ✅ UI elements not updating after code changes
- ✅ JavaScript errors in browser console
- ✅ Module upgrades succeed but UI broken

---

## Current Issue Status

We've fixed:
1. ✅ Mixin imports
2. ✅ Contract extensions syntax
3. ✅ Cron field name (numbercall → removed)
4. ✅ Menu action reference

**Try upgrade NOW** - if it fails, clear cache and try again!

# Module Loading Fix - June 22, 2026

## Problem
Module activation failed with error:
```
ValueError: External ID not found in the system: mesob_inventory_base.action_mesob_procurement_stock_reconciliation_wizard
```

## Root Cause
**Circular Dependencies**: Multiple wizard actions had `binding_model_id` references that created circular dependencies during module loading:

1. Wizard views XML files are loaded and try to create actions
2. Actions with `binding_model_id` reference models (e.g., `model_mesob_procurement`)
3. But those model records might not exist yet in `ir.model` during initial module installation
4. This causes the action creation to fail
5. Then menus that reference these actions also fail

## Solution Applied
Removed `binding_model_id` from all wizard actions to eliminate circular dependencies:

### Files Modified

1. **`wizard/mesob_procurement_stock_reconciliation_wizard_views.xml`**
   - Removed: `<field name="binding_model_id" ref="model_mesob_procurement"/>`
   - Action: `action_mesob_procurement_stock_reconciliation_wizard`

2. **`wizard/mesob_manual_adjustment_wizard_views.xml`**
   - Removed: `<field name="binding_model_id" ref="model_mesob_bin_card"/>`
   - Action: `action_mesob_manual_adjustment_wizard`

3. **`wizard/mesob_intelligent_consolidation_wizard_views.xml`**
   - Removed: `<field name="binding_model_id" ref="model_mesob_procurement_plan"/>`
   - Action: `action_intelligent_consolidation_wizard`

4. **`wizard/mesob_barcode_scanner_wizard_views.xml`**
   - Removed: `<field name="binding_model_id" ref="model_mesob_barcode_scanner_wizard"/>`
   - Action: `action_mesob_barcode_scanner_wizard`

5. **`wizard/mesob_abc_classification_wizard_views.xml`**
   - Removed: `<field name="binding_model_id" ref="model_mesob_inventory_item"/>`
   - Action: `action_mesob_abc_classification_wizard`

## What Does binding_model_id Do?

The `binding_model_id` field adds an "Action" dropdown menu item in the specified model's form/list view. For example:

- With binding: When viewing a Bin Card, there's an "Action → Create Manual Adjustment" menu item
- Without binding: You access the wizard through the main menu only

**Impact**: This is a convenience feature. Removing it doesn't break functionality - users can still access all wizards through the main menu system.

## Next Steps

### 1. Clear Cache (CRITICAL)
Before trying to activate the module again, clear the Odoo cache:

**Option A: SQL (Recommended)**
```bash
psql -U odoo -d your_database_name -f CLEAR_CACHE.sql
```

**Option B: Directly in PostgreSQL**
```sql
DELETE FROM ir_attachment WHERE name LIKE '%assets%';
```

**Option C: Odoo CLI**
```bash
cd "C:\Program Files\Odoo 19.0.20260218\server"
python odoo-bin shell -d your_database_name -c odoo.conf
```
Then in Python shell:
```python
env.cr.execute("DELETE FROM ir_attachment WHERE name LIKE '%assets%'")
env.cr.commit()
exit()
```

### 2. Try Module Activation
After clearing cache, try to activate the module again from Odoo UI:
- Apps → Mesob Inventory Management System → Activate

### 3. If Still Fails
If you still get errors, check the **full logs** at:
```
C:\Program Files\Odoo 19.0.20260218\server\odoo.log
```

Look for the complete error message (web UI truncates errors).

### 4. Re-Enable Temporarily Disabled Items

Once the module loads successfully:

**A. Re-enable Security CSV** (currently disabled in manifest)
```python
# In __manifest__.py, uncomment:
"security/ir.model.access.csv",
```

**B. Re-enable Stock Accuracy Cron** (AUTO-055)
```python
# In __manifest__.py, uncomment:
"data/mesob_stock_accuracy_cron.xml",
```

**C. Re-enable Investigation Workflow** (AUTO-059)
```python
# In __manifest__.py, uncomment:
"data/mesob_investigation_sequence.xml",

# In models/__init__.py, uncomment:
from . import mesob_stock_discrepancy_investigation
```

### 5. Add Back binding_model_id (Optional)
Once everything works, you can optionally add back the `binding_model_id` fields to provide "Action" menu shortcuts in model views. But test after each addition to ensure no circular dependencies.

## Technical Notes

### Why This Happens in Odoo 19
Odoo 19 has stricter dependency resolution during module loading. References to `model_*` external IDs in actions require:
1. The model to be loaded (Python class registered)
2. The model record to exist in `ir.model` table
3. The external ID to be created in `ir.model.data`

During initial installation, timing can cause these references to fail if not carefully ordered.

### Best Practice
- Keep wizard actions simple during initial load
- Add `binding_model_id` in a separate data file loaded at the end
- Or use `noupdate="1"` for actions with complex dependencies
- Always test with a fresh database install, not just upgrades

## Status
- ✅ Circular dependencies removed
- ⏳ Awaiting cache clear and module activation test
- 📋 CSV security still disabled (separate issue to debug)
- 📋 Investigation workflow still disabled (re-enable after main module loads)

## References
- Previous errors: See context transfer summary
- Odoo 19 docs: https://www.odoo.com/documentation/19.0/
- External ID resolution: https://www.odoo.com/documentation/19.0/developer/reference/backend/data.html

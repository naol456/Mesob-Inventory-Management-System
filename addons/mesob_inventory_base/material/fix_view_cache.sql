-- ============================================================================
-- SQL Script to Fix Issue Voucher View Cache Error
-- ============================================================================
-- 
-- PROBLEM: Upgrade fails with error:
--   "Field 'item_id' does not exist in model 'mesob.inventory.issue.voucher'"
--
-- CAUSE: Cached view in database has wrong structure
--
-- SOLUTION: Delete the cached view, then upgrade module
--
-- ============================================================================

-- Step 1: Check if the problematic view exists
SELECT id, name, model, type, xml_id
FROM ir_ui_view
WHERE name = 'mesob.inventory.issue.voucher.form';

-- Step 2: Delete the cached form view
DELETE FROM ir_ui_view
WHERE name = 'mesob.inventory.issue.voucher.form'
AND model = 'mesob.inventory.issue.voucher';

-- Step 3: Verify deletion (should return 0 rows)
SELECT id, name, model FROM ir_ui_view
WHERE name = 'mesob.inventory.issue.voucher.form';

-- Step 4: Also delete any other issue voucher views if they exist
DELETE FROM ir_ui_view
WHERE model = 'mesob.inventory.issue.voucher'
AND name LIKE '%issue.voucher%';

-- Step 5: Commit the changes
COMMIT;

-- ============================================================================
-- NEXT STEPS:
-- 1. Go back to Odoo in your browser
-- 2. Go to Apps menu
-- 3. Search for: mesob_inventory_base
-- 4. Click "Upgrade" button
-- 5. The module should now upgrade successfully!
-- ============================================================================

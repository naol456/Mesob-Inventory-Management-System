# Receiving Line Fix - Testing Guide & Workflow

## What Was Fixed

### Issue
The `mesob.inventory.receiving.line` model was missing a required `name` field, causing view validation errors during module upgrade.

### Solution
Added a computed `name` field to the receiving line model that generates a meaningful display name based on:
- Item code and name (for existing catalogued items)
- Major/Sub classification codes with description (for auto-generated items)
- Description only (as fallback)

---

## Testing Workflow

### Prerequisites
1. Ensure the module upgrades successfully without errors
2. Log in as a user with Storekeeper permissions
3. Have at least one Major Classification and Sub Classification configured
4. Have at least one supplier configured

---

## Test Flow 1: Create Receiving Order with Existing Items

### Step 1: Navigate to Receiving Orders
```
Inventory → Receiving → Receiving Orders → Create
```

### Step 2: Fill Basic Information
- **Source Type**: Supplier
- **Supplier**: Select any supplier
- **Purchase Order Reference**: Enter "PO/TEST/001"
- **Received By**: Auto-filled (current user)
- **Received Date**: Auto-filled (today)

### Step 3: Add Receiving Line with Existing Item
In the "Receiving Lines" tab, click "Add a line":

**Option A: Using existing catalogued item**
1. Select **Item** from dropdown (if you have catalogued items)
2. Enter **Qty Expected**: 10
3. Enter **Qty Received**: 10
4. Enter **Qty Accepted**: 10
5. Enter **Unit Price**: 100.00
6. **Total Price** should auto-calculate to 1,000.00

**Expected Result**: The line should display with item code and name in the list view

### Step 4: Save and Verify
- Click "Save"
- The receiving line should display properly in the list
- Check that the computed `name` field shows correctly

---

## Test Flow 2: Create Receiving Order with Auto-Generated Items

### Step 1: Create New Receiving Order
```
Inventory → Receiving → Receiving Orders → Create
```

### Step 2: Fill Basic Information
- **Source Type**: Supplier
- **Supplier**: Select any supplier
- **Purchase Order Reference**: "PO/TEST/002"

### Step 3: Add Receiving Line for New Items
In the "Receiving Lines" tab, click "Add a line":

1. **Major Classification**: Select (e.g., "3345 - Office Equipment")
2. **Sub Classification**: Select from filtered list (e.g., "456 - Computers")
3. **Description**: "Dell Laptop i7"
4. **Qty Expected**: 5
5. **Qty Received**: 5
6. **Qty Accepted**: 5
7. **Unit Price**: 50000.00
8. **Auto Generate Items**: Should be checked automatically

**Expected Result**: The line name should show as "3345-456: Dell Laptop i7"

### Step 4: Complete Receiving Workflow
1. Click "Save"
2. Click "Mark Received" button
3. Click "Start Inspection" button
4. Click "Accept" button
5. Click "Finalize" button

**Expected Result**: 
- No errors should occur
- If "Auto Generate Items" was enabled, individual item codes should be created
- Bin card and stock record entries should be created

---

## Test Flow 3: Verify Inspection Checklist (AUTO-039)

### Step 1: Create Receiving Order
Follow Test Flow 1 or 2 to create a receiving order

### Step 2: Navigate to Inspection
1. Save the receiving order
2. Click "Mark Received"
3. Click "Start Inspection"

### Step 3: Open Line Details
In the Receiving Lines list, click on a line to open the form view

### Step 4: Go to Inspection Checklist Tab
Click on "📋 Inspection Checklist (AUTO-039)" tab

### Step 5: Complete Checklist
Verify the following fields are present:
- ✓ **Quality Specifications** (text area)
- ✓ **Quantity Matches PO** (checkbox)
- ✓ **Quality Meets Specifications** (checkbox)
- ✓ **Packaging Intact** (checkbox)
- ✓ **Documentation Complete** (checkbox)
- ✓ **Expiry Date Valid** (checkbox)
- ✓ **All Checks Passed** (readonly, computed)
- ✓ **Inspector's Notes** (text area)

### Step 6: Fill Checklist
1. Check all the checkboxes
2. **Expected Result**: "All Checks Passed" should automatically become True
3. Add notes in "Inspector's Notes"

### Step 7: Test Rejection
1. Uncheck one checkbox
2. **Expected Result**: "All Checks Passed" should automatically become False

---

## Test Flow 4: Verify Generated Items Display

### Step 1: Create Receiving with Auto-Generation
Follow Test Flow 2 with auto-generation enabled

### Step 2: Complete to Accepted State
1. Mark Received
2. Start Inspection
3. Accept

### Step 3: View Generated Items
In the receiving line form view:
1. Click on "Generated Items" tab
2. **Expected Result**: Should see a list of generated items showing:
   - Item Code
   - Name

### Step 4: Verify No Errors
- The list should display without field validation errors
- Should be able to navigate through the generated items

---

## Verification Checklist

### ✅ Module Upgrade
- [ ] Module upgrades without errors
- [ ] No "Field does not exist" errors
- [ ] All views load properly

### ✅ Receiving Line Name Field
- [ ] Receiving lines display with proper names in list view
- [ ] Name shows item code + name for existing items
- [ ] Name shows classification codes + description for new items
- [ ] Name shows description as fallback

### ✅ Inspection Checklist
- [ ] Inspection checklist tab is visible
- [ ] All checkbox fields are present
- [ ] "All Checks Passed" computes correctly
- [ ] Inspector notes field works

### ✅ Generated Items
- [ ] Generated items tab displays without errors
- [ ] Item list shows item codes and names
- [ ] No "classification_id does not exist" errors

### ✅ Complete Workflow
- [ ] Can create receiving order
- [ ] Can add receiving lines
- [ ] Can save without errors
- [ ] Can move through workflow states (draft → received → inspecting → accepted → done)
- [ ] Generated items are created when auto-generation is enabled
- [ ] Bin card entries are created
- [ ] Stock record entries are created

---

## Expected Behavior Summary

### Name Field Display Examples

1. **Existing Item**: `"3345-456-001 - Dell Laptop Core i7"`
2. **New Item with Auto-Gen**: `"3345-456: Dell Laptop Core i7"`
3. **Description Only**: `"Office Chair Executive"`
4. **Fallback**: `"Receiving Line"`

### Inspection Checklist Behavior

- All checkboxes must be checked for "All Checks Passed" to be True
- Field is computed automatically (cannot be manually edited)
- Helps ensure proper receiving inspection compliance

### Generated Items Behavior

- Only visible when items have been generated (count > 0)
- Shows simplified list with item code and name
- No classification fields in nested view (prevents validation errors)

---

## Troubleshooting

### If Module Won't Upgrade

**Error**: "Field 'name' does not exist"
- **Solution**: Ensure you've pulled the latest code with the computed name field

**Error**: "Field 'classification_id' does not exist"  
- **Solution**: Ensure the generated items tree view only shows basic fields (item_code, name)

**Error**: "Invalid view definition"
- **Solution**: Check XML syntax in view files, ensure all tags are properly closed

### If Fields Don't Display

1. Clear browser cache
2. Restart Odoo server
3. Upgrade module again
4. Check developer mode for any JS console errors

---

## Database State Verification

After successful upgrade, verify in database (optional):

```sql
-- Check receiving line records have name field populated
SELECT id, name, description, item_id, major_classification_id 
FROM mesob_inventory_receiving_line 
LIMIT 10;

-- Check view definitions loaded
SELECT id, name, model 
FROM ir_ui_view 
WHERE model = 'mesob.inventory.receiving.line';
```

---

## Success Criteria

✅ **Module loads without errors**
✅ **All receiving views display correctly**
✅ **Receiving lines show meaningful names**
✅ **Inspection checklist is functional**
✅ **Generated items display without validation errors**
✅ **Complete receiving workflow works end-to-end**

---

## Next Steps After Testing

Once testing is complete and successful:

1. **Document** any issues found
2. **Report** any additional enhancements needed
3. **Deploy** to staging/production environment
4. **Train** users on the inspection checklist feature
5. **Monitor** for any runtime issues

---

## Contact & Support

If you encounter issues during testing:
- Check the Odoo server logs for detailed error messages
- Enable debug mode in Odoo for more detailed information
- Review the model definition in `mesob_inventory_receiving_line.py`
- Check view definitions in `mesob_inventory_receiving_views.xml`

---

**Document Version**: 1.0  
**Last Updated**: 2026-06-19  
**Module**: mesob_inventory_base

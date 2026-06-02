# Issue Voucher (Model 22) - User Guide

## Problem Fixed ✅

**Issue 1:** Lines weren't being copied from requisition to issue voucher  
**Solution:** Enhanced the `action_create_issue_voucher` method with better validation and error messages

**Issue 2:** Error about missing `mesob_product_code` field  
**Solution:** Updated product creation to handle optional fields and provide fallback

## How to Use Issue Voucher (Step by Step)

### Step 1: Create Requisition (Model 20)

1. Go to: **Mesob Inventory → Operations → Requisitions (Model 20)**
2. Click **New** (or Create button)
3. Fill in the form:
   - **Requesting Department**: Your department name
   - **Issue Mode**: Select one:
     - Imprest Basis (scheduled periodic issue)
     - Replacement Issue (replace consumed items)
     - Non-Stock Issue (one-time special)
   - **Requested On**: Today (auto-filled)

4. **Add Lines** (the items you need):
   - Click **Add a line** in the "Requisition Lines" section
   - Select **Item** (must have items created first!)
   - Enter **Quantity**
   - Select **Unit of Measure** (auto-filled from item)
   - Add **Remarks** (optional)
   - Repeat for all items you need

5. Click **Submit** button
   - Status changes to "Submitted"
   - Requisition is now waiting for PAO approval

### Step 2: PAO Approves Requisition

1. **Login as PAO** (Property Administration Officer)
2. Go to **Mesob Inventory → Operations → Requisitions**
3. Filter by **Submitted** status
4. Open the requisition
5. Review the items and quantities
6. Click **Approve** button
   - Status changes to "Approved"
   - Now ready to create Issue Voucher

### Step 3: Create Issue Voucher from Approved Requisition

1. **Still on the approved requisition form**
2. Click **Create Issue Voucher** button (purple/blue button)
3. **System automatically**:
   - Creates new Issue Voucher (Model 22)
   - Copies ALL lines from requisition
   - Sets requesting department
   - Sets issue date to today
   - Opens the new voucher

### Step 4: Review Issue Voucher

The Issue Voucher form now shows:
- **Voucher Number**: Auto-generated (e.g., IV/00001)
- **Requisition**: Linked to original requisition
- **Requesting Department**: Auto-filled
- **Issue Lines Tab**: Shows all items (copied from requisition)

**Important:** The lines are **already filled** - you don't need to add them manually!

### Step 5: Issue Materials (Storekeeper)

1. **Login as Storekeeper**
2. Open the Issue Voucher
3. Review the lines in "📦 Issue Lines" tab
4. Click **Issue Materials** button
5. System will:
   - ✅ Check stock availability
   - ✅ Create stock picking
   - ✅ Validate stock movement
   - ✅ Post to Bin Cards (quantity tracking)
   - ✅ Post to Stock Record Cards (quantity + value with FIFO)
   - ✅ Mark three-copy distribution
   - ✅ Change status to "Issued"

### Step 6: Department Confirms Receipt

1. **Department user** opens the issued voucher
2. Click **Confirm Receipt** button
3. Wizard opens with checkboxes:
   - ✅ Quantity Verified
   - ✅ Inspection Confirmed
   - ✅ Approval Verified
4. Add receipt notes (optional)
5. Click **Confirm**
6. Status changes to "Received"

---

## Common Errors and Solutions

### Error: "Missing required value for 'mesob_product_code'"

**Cause:** Your system has another module that requires this field on products

**Solution:**
1. **Before issuing materials**, link products to inventory items:
   - Go to **Mesob Inventory → Master Data → Inventory Items**
   - Open each item
   - In "Linked Product" field, select or create product
   - Save

2. **OR** Create products manually first:
   - Go to **Inventory → Products**
   - Create product with:
     - Name: Match item name
     - Internal Reference: Match item code (e.g., 4401-001-001)
     - **mesob_product_code**: Enter the item code
   - Then link to inventory item

### Error: "Lines not copied from requisition"

**Cause:** Requisition lines were empty or had validation issues

**Solution:**
1. Check requisition lines have:
   - ✅ Item selected (not blank)
   - ✅ Quantity > 0
   - ✅ Unit of measure selected
2. Re-approve requisition
3. Click "Create Issue Voucher" again

### Error: "Insufficient stock"

**Cause:** Not enough stock in warehouse

**Solution:**
1. Check current stock:
   - Go to **Inventory → Products**
   - Find the product
   - Check "Quantity On Hand"
2. If no stock, create receiving first:
   - **Mesob Inventory → Operations → Receiving Orders**
   - Receive materials
   - Then try issuing again

---

## Best Practices

### 1. Setup Inventory Items First
Before creating requisitions:
- Create major classifications (4401-4418)
- Create sub classifications
- Create inventory items with proper codes
- Link products to items

### 2. Keep Products and Items Linked
- When creating a new inventory item, immediately link or create its product
- Use the same code (item code = product internal reference)
- This prevents issues during stock operations

### 3. Use Proper Workflow
Always follow this order:
1. Requisition (Model 20) → Submit → Approve
2. Create Issue Voucher from requisition
3. Issue materials
4. Confirm receipt

**Do NOT:**
- Skip requisition and try to create voucher directly
- Edit voucher after it's issued
- Delete issued vouchers (cancel instead)

### 4. Check Stock Before Requisition
Before creating requisition:
- Check if items are in stock
- Check minimum stock levels
- Create receiving if needed

---

## Three-Copy Distribution (FR-ISSUE-005)

When materials are issued, three copies are distributed:

1. **Original + Requisition → Stock Clerk**
   - For posting to stock records
   - Kept as permanent record

2. **Duplicate → Requesting Department**
   - Department keeps for their records
   - Used to confirm receipt

3. **Triplicate → Storekeeper**
   - Retained by storekeeper
   - Filed with pad

---

## Troubleshooting Checklist

If Issue Voucher is not working:

- [ ] Is the requisition approved? (status = "Approved")
- [ ] Do requisition lines have items selected?
- [ ] Are quantities positive (> 0)?
- [ ] Are inventory items linked to products?
- [ ] Is there sufficient stock in warehouse?
- [ ] Is the user logged in as Storekeeper?
- [ ] Has the module been upgraded after code changes?

---

## Module Upgrade

After code changes, upgrade the module:

```bash
# Stop Odoo
# Then run:
odoo-bin -u mesob_inventory_base -d your_database_name
```

Or from UI:
1. Go to **Apps**
2. Remove "Apps" filter
3. Search "Mesob Inventory"
4. Click **Upgrade**

---

## Need Help?

Check:
1. This guide
2. SRS document (material/srs.md)
3. Code review report (material/CODE_REVIEW_REPORT.md)
4. System logs (debug mode)

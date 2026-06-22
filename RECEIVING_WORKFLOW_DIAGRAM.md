# Receiving Order Workflow - Visual Flow

## Overall Receiving Process Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    RECEIVING ORDER LIFECYCLE                         │
└─────────────────────────────────────────────────────────────────────┘

    [Purchase Order Approved]
              │
              ▼
    ┌──────────────────┐
    │   CREATE         │  Storekeeper creates receiving order
    │   RECEIVING      │  - Links to PO reference
    │   ORDER          │  - Enters supplier details
    │   (Draft)        │  - Adds expected items/quantities
    └────────┬─────────┘
              │
              │ Click "Mark Received"
              ▼
    ┌──────────────────┐
    │   GOODS          │  Physical delivery arrives
    │   RECEIVED       │  - Verify quantities
    │   (Received)     │  - Record actual received qty
    └────────┬─────────┘
              │
              │ Click "Start Inspection"
              ▼
    ┌──────────────────┐
    │   INSPECTION     │  Quality check process
    │   IN PROGRESS    │  ✓ AUTO-039: Inspection Checklist
    │   (Inspecting)   │  - Quantity matches PO
    └────────┬─────────┘  - Quality meets specs
              │            - Packaging intact
              │            - Documentation complete
              │            - Expiry date valid
              │
      ┌───────┴────────┐
      │                │
      ▼                ▼
  [Accept]        [Reject]
      │                │
      ▼                ▼
┌──────────┐    ┌──────────┐
│ ACCEPTED │    │ REJECTED │
│          │    │   (DSR)  │
└────┬─────┘    └────┬─────┘
      │                │
      │ Finalize       │ Finalize
      ▼                ▼
┌──────────┐    ┌──────────┐
│   DONE   │    │   DONE   │
│(Model 19)│    │   (DSR)  │
└──────────┘    └──────────┘
      │
      ▼
[Inventory Updated]
[Stock Records Created]
```

---

## Receiving Line Creation Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    RECEIVING LINE SCENARIOS                          │
└─────────────────────────────────────────────────────────────────────┘

SCENARIO 1: Existing Catalogued Item
═══════════════════════════════════════
    ┌─────────────────┐
    │ Select Item     │
    │ from Catalog    │
    └────────┬────────┘
              │
              ▼
    ┌─────────────────┐
    │ Auto-fill       │
    │ Classifications │
    │ Description     │
    └────────┬────────┘
              │
              ▼
    ┌─────────────────┐
    │ Enter Quantities│
    │ & Unit Price    │
    └────────┬────────┘
              │
              ▼
    ┌─────────────────┐
    │ Name Generated: │
    │"3345-456-001 -  │
    │ Dell Laptop"    │
    └─────────────────┘


SCENARIO 2: New Item (Auto-Generation)
═══════════════════════════════════════
    ┌─────────────────┐
    │ Select Major    │
    │ Classification  │
    └────────┬────────┘
              │
              ▼
    ┌─────────────────┐
    │ Select Sub      │
    │ Classification  │
    │ (filtered)      │
    └────────┬────────┘
              │
              ▼
    ┌─────────────────┐
    │ Enter           │
    │ Description     │
    └────────┬────────┘
              │
              ▼
    ┌─────────────────┐
    │ Auto-Generate   │
    │ Items: ✓        │
    └────────┬────────┘
              │
              ▼
    ┌─────────────────┐
    │ Name Generated: │
    │"3345-456:       │
    │ Dell Laptop"    │
    └────────┬────────┘
              │
              │ On Accept
              ▼
    ┌─────────────────┐
    │ Generate Item   │
    │ Codes:          │
    │ 3345-456-001    │
    │ 3345-456-002    │
    │ 3345-456-003    │
    └─────────────────┘
```

---

## AUTO-039: Inspection Checklist Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│              INSPECTION CHECKLIST PROCESS (AUTO-039)                 │
└─────────────────────────────────────────────────────────────────────┘

    ┌──────────────────┐
    │ Receiving Line   │
    │ in "Inspecting"  │
    │ State            │
    └────────┬─────────┘
              │
              ▼
    ┌─────────────────────────────────────────┐
    │  📋 INSPECTION CHECKLIST TAB            │
    ├─────────────────────────────────────────┤
    │                                         │
    │  Quality Specifications:                │
    │  ┌───────────────────────────────────┐ │
    │  │ (From PO/tender specifications)   │ │
    │  └───────────────────────────────────┘ │
    │                                         │
    │  Acceptance Criteria:                   │
    │  ☐ Quantity Matches PO                  │
    │  ☐ Quality Meets Specifications         │
    │  ☐ Packaging Intact                     │
    │  ☐ Documentation Complete               │
    │  ☐ Expiry Date Valid                    │
    │                                         │
    │  ⚙️ All Checks Passed: ✗ (computed)    │
    │                                         │
    │  Inspector's Notes:                     │
    │  ┌───────────────────────────────────┐ │
    │  │ (Observations & findings)         │ │
    │  └───────────────────────────────────┘ │
    └────────┬────────────────────────────────┘
              │
      ┌───────┴────────┐
      │                │
      ▼                ▼
  All Checked      Not All Checked
      │                │
      ▼                ▼
  ✅ Passed        ❌ Not Passed
      │                │
      ▼                ▼
  [Accept]         [Reject]
      │                │
      ▼                ▼
  [Model 19]       [DSR]
```

---

## Item Code Generation Logic

```
┌─────────────────────────────────────────────────────────────────────┐
│                 ITEM CODE GENERATION LOGIC                           │
└─────────────────────────────────────────────────────────────────────┘

Input:
├─ Major Classification: 3345 (Office Equipment)
├─ Sub Classification: 456 (Computers)
└─ Quantity Accepted: 5

         │
         ▼
    ┌────────────────┐
    │ Check Sub      │ NO   ┌──────────────────┐
    │ Classification ├─────→│ Create ONE       │
    │ is Fixed Asset?│      │ Master Item      │
    └────────┬───────┘      │ 3345-456-001     │
             │ YES          │ (Consumable)     │
             │              └──────────────────┘
             ▼                       │
    ┌────────────────┐               │
    │ Generate       │               │
    │ Individual     │               ▼
    │ Items          │      ┌──────────────────┐
    └────────┬───────┘      │ ONE Stock Record │
             │              │ Quantity: 5      │
             │              └──────────────────┘
             ▼
    ┌────────────────┐
    │ 3345-456-001   │
    │ 3345-456-002   │
    │ 3345-456-003   │  ← Individual items
    │ 3345-456-004   │     for tracking
    │ 3345-456-005   │
    └────────┬───────┘
             │
             ▼
    ┌────────────────┐
    │ 5 Stock        │
    │ Records        │
    │ (Qty: 1 each)  │
    └────────────────┘
```

---

## Backend Data Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                    DATA CREATION FLOW                                │
└─────────────────────────────────────────────────────────────────────┘

    [Accept Receiving]
            │
            ├────────────┬────────────┬────────────┐
            │            │            │            │
            ▼            ▼            ▼            ▼
    ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
    │ Generate │  │  Create  │  │  Create  │  │  Create  │
    │  Items   │  │ Bin Card │  │  Stock   │  │ Model 19 │
    │  Codes   │  │  Entry   │  │  Record  │  │Document  │
    └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘
         │             │             │             │
         │             │             │             │
         └─────────────┴─────────────┴─────────────┘
                            │
                            ▼
                  ┌──────────────────┐
                  │ Inventory System │
                  │ Updated          │
                  └──────────────────┘

Details:
─────────
1. Generate Items Codes
   └─ mesob.inventory.item records created
   └─ Sequential codes: MAJOR-SUB-###

2. Create Bin Card Entry
   └─ mesob.bin.card record
   └─ Aggregated by sub-classification
   └─ Tracks total quantity received

3. Create Stock Records
   └─ mesob.stock.record.card records
   └─ Individual or aggregated based on asset type
   └─ Creates FIFO layers for valuation

4. Create Model 19 Document
   └─ mesob.inventory.model19 record
   └─ Official Goods Received Note
   └─ Links to receiving order
```

---

## Name Field Computation Logic

```
┌─────────────────────────────────────────────────────────────────────┐
│              RECEIVING LINE NAME COMPUTATION                         │
└─────────────────────────────────────────────────────────────────────┘

@depends("item_id", "major_classification_id", 
         "sub_classification_id", "description")

         ┌─────────────┐
         │ Compute     │
         │ Name        │
         └──────┬──────┘
                │
         ┌──────┴──────┐
         │             │
         ▼             ▼
    Has Item?      No Item?
         │             │
         │             ▼
         │      Has Major + Sub?
         │             │
         ▼      ┌──────┴──────┐
    Use Item    │             │
    Code +      ▼             ▼
    Name       YES           NO
         │      │             │
         │      ▼             ▼
         │   Use Code +   Has Description?
         │   Description     │
         │      │      ┌──────┴──────┐
         │      │      │             │
         └──────┴──────┤             ▼
                       ▼            NO
                  Description       │
                       │            ▼
                       └──────→ "Receiving Line"
                                (Fallback)

Examples:
─────────
✓ Item Selected:
  "3345-456-001 - Dell Laptop Core i7"

✓ New Item (Auto-gen):
  "3345-456: Dell Laptop Core i7"

✓ Description Only:
  "Office Supplies Miscellaneous"

✓ Fallback:
  "Receiving Line"
```

---

## Testing Checkpoints

```
┌─────────────────────────────────────────────────────────────────────┐
│                     TESTING CHECKPOINTS                              │
└─────────────────────────────────────────────────────────────────────┘

Checkpoint 1: Module Upgrade
════════════════════════════
    ✓ No "Field does not exist" errors
    ✓ All views load without validation errors
    ✓ Database schema updated correctly

Checkpoint 2: Create Receiving Order
═══════════════════════════════════
    ✓ Form loads without errors
    ✓ Can select supplier
    ✓ Can enter PO reference
    ✓ Dates auto-fill correctly

Checkpoint 3: Add Receiving Lines
════════════════════════════════
    ✓ Can add lines with existing items
    ✓ Can add lines with new items (auto-gen)
    ✓ Name field displays correctly in list
    ✓ Quantities calculate correctly

Checkpoint 4: Inspection Checklist
═════════════════════════════════
    ✓ Checklist tab is visible
    ✓ All checkboxes are functional
    ✓ "All Checks Passed" computes correctly
    ✓ Notes field saves properly

Checkpoint 5: Accept & Finalize
══════════════════════════════
    ✓ Accept button works
    ✓ Items are generated (if auto-gen enabled)
    ✓ Bin card entries created
    ✓ Stock records created
    ✓ Model 19 document generated

Checkpoint 6: View Generated Items
════════════════════════════════
    ✓ Generated items tab displays
    ✓ Item codes shown correctly
    ✓ No field validation errors
    ✓ Can navigate to item details
```

---

## Summary of Changes

### Files Modified
1. **mesob_inventory_receiving_line.py**
   - Added `name` field (computed)
   - Added `_compute_name()` method

2. **mesob_inventory_receiving_views.xml**
   - Added `generated_item_ids` to invisible fields list
   - Simplified generated items tree view (removed problematic fields)
   - Added `uom_id` to receiving line list view

### Key Features
- ✅ Computed name field for receiving lines
- ✅ Inspection checklist (AUTO-039)
- ✅ Auto-generation support for new items
- ✅ Fixed asset vs consumable logic
- ✅ Bin card and stock record creation
- ✅ FIFO layer tracking

---

**End of Workflow Documentation**

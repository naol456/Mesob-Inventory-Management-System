# Bin Card Integration - Complete Documentation

## Overview

Bin cards are now automatically updated for all major inventory transactions. This provides real-time tracking of physical stock movements across all locations.

---

## Integrated Transactions

### 1. ✅ Receiving (Materials Coming In)

**When:** Materials are received and accepted  
**Trigger:** `action_accept()` method in Receiving Order  
**Transaction Type:** `receipt`  
**Location:** `Main Store`

**Fields Posted:**
- Item
- Quantity IN (accepted quantity)
- Date (received date)
- Reference (receiving order number + PO reference)
- Description (supplier name)
- Received By (storekeeper)
- Verified By (inspector)

**Example Entry:**
```
Date: 2026-06-02
Type: Receipt
Reference: REC/2026/00001 / PO-12345
Description: Receipt from ABC Suppliers
Quantity In: 100
Balance: 100
```

---

### 2. ✅ Issue Voucher (Materials Going Out to Departments)

**When:** Materials are issued to requesting departments  
**Trigger:** `action_issue()` method in Issue Voucher  
**Transaction Type:** `issue`  
**Location:** `Main Store`

**Fields Posted:**
- Item
- Quantity OUT (issued quantity)
- Date (issue date)
- Reference (issue voucher number + requisition reference)
- Description (requesting department name)
- Received By (storekeeper who issued)

**Example Entry:**
```
Date: 2026-06-02
Type: Issue
Reference: IV/2026/00001 / REQ/2026/00001
Description: Issue to IT Department
Quantity Out: 20
Balance: 80
```

---

### 3. ✅ Gate Pass (Materials Leaving Compound)

**When:** Materials are dispatched through security gate  
**Trigger:** `action_dispatch()` method in Gate Pass  
**Transaction Type:** `issue`  
**Location:** `Gate/Exit`

**Fields Posted:**
- Item
- Quantity OUT (dispatched quantity)
- Date (dispatch date)
- Reference (gate pass number)
- Description (receiver organization + destination)
- Received By (security guard)

**Example Entry:**
```
Date: 2026-06-02
Type: Issue
Reference: GP/2026/00001 - Gate Pass
Description: Dispatched to External Agency - Addis Ababa
Quantity Out: 5
Balance: 75
```

**Note:** Gate pass posting is OPTIONAL and tracks materials leaving the physical compound. Issue vouchers already track departmental issues.

---

## 4. Future Integrations (Not Yet Implemented)

### Stock Adjustments
- **Purpose:** Track inventory corrections, physical count adjustments
- **Transaction Type:** `adjustment`
- **When:** Physical counts reveal discrepancies

### Stock Transfers
- **Purpose:** Track movements between storage locations
- **Transaction Type:** `transfer`
- **When:** Items moved from one bin/shelf to another

### Department Returns
- **Purpose:** Track materials returned by departments
- **Transaction Type:** `receipt`
- **When:** Unused materials are returned to store

---

## Running Balance Calculation

The bin card maintains a **running balance** that automatically updates based on:

```
New Balance = Previous Balance + Quantity In - Quantity Out
```

### Balance Computation Method

The system uses an **improved compute method** that:
1. Groups records by Item + Location
2. Sorts by Date + ID (chronological order)
3. Calculates running balance sequentially
4. Handles multiple transactions per day correctly

### Example Balance Flow

| Date | Type | Qty In | Qty Out | Balance |
|------|------|--------|---------|---------|
| Jun 1 | Receipt | 100 | 0 | 100 |
| Jun 2 | Issue | 0 | 20 | 80 |
| Jun 2 | Issue | 0 | 15 | 65 |
| Jun 3 | Receipt | 50 | 0 | 115 |
| Jun 3 | Issue | 0 | 25 | 90 |

---

## Location Tracking

### Current Locations

1. **Main Store** - Primary storage location for most items
2. **Gate/Exit** - Virtual location for gate pass tracking

### Future Locations (Configurable)

- Shelf A-1, Shelf A-2, etc.
- Room 1, Room 2, etc.
- Warehouse Section A, B, C
- Any custom physical locations

**How to Add Locations:**
Currently hardcoded as `'Main Store'`. Future enhancement will add:
- Location master data model
- Location picker on transactions
- Multi-location balance tracking

---

## Verification & Audit Trail

Each bin card entry captures:

✅ **Who:** User who performed the transaction  
✅ **What:** Item, quantity, transaction type  
✅ **When:** Date of transaction  
✅ **Where:** Physical location (bin/shelf)  
✅ **Why:** Reference to source document  
✅ **How:** Description of the transaction  

This provides complete audit trail for inventory movements.

---

## Viewing Bin Cards

### Via Menu
**Path:** Inventory → Reports → Bin Cards

### Search & Filter Options
- By Item
- By Location
- By Date Range
- By Transaction Type
- By Reference Document

### Typical Use Cases

1. **Stock Verification:** Check current balance for an item
2. **Movement History:** See all transactions for an item
3. **Discrepancy Investigation:** Trace when/why stock changed
4. **Location Audit:** View all items in a specific location
5. **Period Reports:** Generate movement report for date range

---

## Integration with Stock Record Cards

**Bin Cards** vs **Stock Record Cards:**

| Feature | Bin Card | Stock Record Card |
|---------|----------|-------------------|
| **Purpose** | Physical tracking | Financial tracking |
| **Tracks** | Quantities only | Quantities + Values |
| **Location** | Yes | No |
| **Costing** | No | Yes (FIFO) |
| **Use Case** | Warehouse management | Accounting/Valuation |

**Both are updated together** when transactions occur, providing:
- Physical view (Bin Card)
- Financial view (Stock Record Card)

---

## Testing Bin Card Integration

### Test Scenario 1: Receiving Flow
1. Create receiving order
2. Add line with item + quantity
3. Start inspection
4. Accept materials
5. **Check:** Bin card shows receipt entry ✅

### Test Scenario 2: Issue Flow
1. Create requisition
2. Approve requisition
3. Create issue voucher
4. Issue materials
5. **Check:** Bin card shows issue entry ✅

### Test Scenario 3: Gate Pass Flow
1. Create gate pass (link to issue voucher)
2. PAO authorizes
3. Security dispatches
4. **Check:** Bin card shows gate exit entry ✅

### Test Scenario 4: Running Balance
1. Receive 100 units
2. Issue 20 units
3. Issue 30 units
4. Receive 50 units
5. **Check:** Balance = 100 - 20 - 30 + 50 = 100 ✅

---

## Troubleshooting

### Balance Not Updating
**Solution:** Recompute balances
1. Go to Bin Cards
2. Select all records
3. Action → Recompute → Select "balance"

### Duplicate Entries
**Cause:** Transaction button clicked multiple times
**Solution:** Delete duplicate entries manually

### Missing Entries
**Cause:** Transaction failed before bin card posting
**Solution:** Re-run the transaction or create manual adjustment

---

## Configuration Settings

### Future Configuration Options (Planned)

1. **Auto-posting Toggle:** Enable/disable automatic bin card posting
2. **Location Management:** Configure physical storage locations
3. **Transaction Types:** Add custom transaction types
4. **Required Fields:** Configure which fields are mandatory
5. **Approval Workflow:** Require approval for manual adjustments

---

## SRS Compliance

This bin card integration supports the following SRS requirements:

- **FR-REC-001:** Track receiving transactions
- **FR-ISSUE-001:** Track issue transactions
- **FR-GATE-001:** Track gate pass transactions
- **FR-TRACK-001:** Maintain physical stock tracking
- **FR-AUDIT-001:** Provide complete audit trail

---

## Summary

✅ **Receiving** → Bin Card (Receipt)  
✅ **Issue Voucher** → Bin Card (Issue)  
✅ **Gate Pass** → Bin Card (Issue/Exit)  
🔄 **Running Balance** → Auto-computed  
📊 **Location Tracking** → By bin/location  
🔍 **Full Audit Trail** → Who/What/When/Where/Why  

The bin card system is now fully integrated with all major inventory transactions!

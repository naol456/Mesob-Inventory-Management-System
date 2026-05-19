# Issue of Stocks - Workflow Quick Reference

## Overview

This guide provides step-by-step instructions for the complete requisition and issue workflow.

## Workflow Diagram

```
┌─────────────────┐
│ Department User │
│ Creates         │
│ Requisition     │
│ (Model 20)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Submit for      │
│ Approval        │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ PAO Reviews     │
│ & Approves      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Storekeeper     │
│ Creates Issue   │
│ Voucher         │
│ (Model 22)      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Storekeeper     │
│ Issues          │
│ Materials       │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Department      │
│ Confirms        │
│ Receipt         │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Stock Clerk     │
│ Posts to        │
│ Records         │
└─────────────────┘
```

## Step-by-Step Procedures

### 1. Create Requisition (Department User)

**Navigation:** Mesob Inventory → Operations → Requisitions (Model 20)

**Steps:**
1. Click **Create** button
2. Fill in requisition details:
   - **Issue Mode:** Select Imprest, Replacement, or Non-Stock
   - **Department:** Enter your department name
   - **Requested By:** Auto-filled (current user)
   - **Requested On:** Auto-filled (today's date)
3. Add requisition lines:
   - Click **Add a line**
   - Select **Item** from dropdown
   - Enter **Quantity Requested**
   - Select **Unit of Measure**
   - Add **Remarks** if needed
4. Add internal notes if needed
5. Click **Save**
6. Click **Submit** button
7. Requisition state changes to **Submitted**

**Result:** Requisition is now pending PAO approval

---

### 2. Approve Requisition (PAO)

**Navigation:** Mesob Inventory → Operations → Requisitions (Model 20)

**Steps:**
1. Filter by **Pending Approval** or search for requisition
2. Open the requisition
3. Review requisition details:
   - Verify department and requester
   - Check requested items and quantities
   - Review justification/notes
4. Decision:
   - **To Approve:** Click **Approve** button
   - **To Reject:** Click **Reject** button, enter rejection reason
5. Requisition state changes to **Approved** or **Rejected**

**Result:** 
- If approved: Storekeeper can now create issue voucher
- If rejected: Requester can reset to draft and resubmit

---

### 3. Create Issue Voucher (Storekeeper)

**Navigation:** Mesob Inventory → Operations → Requisitions (Model 20)

**Steps:**
1. Filter by **Approved** requisitions
2. Open the approved requisition
3. Click **Create Issue Voucher** button
4. System creates new issue voucher with:
   - Auto-generated voucher number
   - Linked requisition
   - Copied requisition lines
   - Current date and user
5. Review issue voucher details
6. Modify quantities if needed (partial issue)
7. Click **Save**

**Result:** Issue voucher created in **Draft** state

---

### 4. Issue Materials (Storekeeper)

**Navigation:** Mesob Inventory → Operations → Issue Vouchers (Model 22)

**Steps:**
1. Open the draft issue voucher
2. Verify all details are correct
3. Click **Issue Materials** button
4. System performs:
   - Stock availability validation
   - Creates stock picking
   - Validates inventory movement
   - Marks three-copy distribution:
     - ✓ Original + Requisition → Stock Clerk
     - ✓ Duplicate → Requesting Department
     - ✓ Triplicate → Storekeeper
5. Voucher state changes to **Issued**
6. Stock quantities updated automatically

**Result:** 
- Materials issued from stock
- Awaiting department receipt confirmation
- Stock picking created and validated

**Troubleshooting:**
- **Error: Insufficient stock** → Check stock quantities, adjust issue quantity, or wait for receiving
- **Error: Item not linked to product** → Configure product linkage in item master

---

### 5. Confirm Receipt (Department Receiver)

**Navigation:** Mesob Inventory → Operations → Issue Vouchers (Model 22)

**Steps:**
1. Filter by **Issued** vouchers or search by department
2. Open the issued voucher
3. Click **Confirm Receipt** button
4. Receipt confirmation wizard opens
5. Verify and confirm:
   - ☑ **Quantity Verified:** Quantities match requisition
   - ☑ **Inspection Confirmed:** Items in acceptable condition
   - ☑ **Approval Verified:** Requisition properly approved
6. Add **Receipt Notes** if any observations
7. Click **Confirm Receipt** button
8. Voucher state changes to **Received**
9. Requisition state changes to **Received**

**Result:** 
- Receipt confirmed
- Workflow complete
- Audit trail updated

**Note:** All three verification checks must be confirmed. If there are issues, add notes and contact storekeeper before confirming.

---

### 6. Post to Records (Stock Clerk)

**Navigation:** Mesob Inventory → Operations → Issue Vouchers (Model 22)

**Steps:**
1. Filter by **Received** vouchers
2. Review issue vouchers for posting
3. Verify stock picking is validated
4. Post to stock record cards:
   - Update quantity issued
   - Update value (FIFO)
   - Update balance
5. File original voucher + requisition

**Result:** Stock records updated, documents filed

---

## Special Scenarios

### Controlled Materials Issue

**Additional Requirements:**
- Item must be flagged as **Controlled Material**
- Only authorized users can issue
- Additional approval may be required

**Steps:**
1. Follow normal issue workflow
2. System validates issuer authorization
3. Additional approval step (if configured)
4. Enhanced audit trail for controlled items

---

### Partial Issue

**Scenario:** Not all requested quantities available

**Steps:**
1. Create issue voucher as normal
2. Adjust quantities in issue lines to available amounts
3. Issue materials
4. Create second issue voucher for remaining quantities later

---

### Issue Cancellation

**Before Issue:**
1. Open draft issue voucher
2. Click **Cancel** button
3. Voucher state changes to **Cancelled**
4. Can reset to draft if needed

**After Issue (Before Receipt):**
1. Open issued voucher
2. Click **Cancel** button
3. System cancels stock picking
4. Inventory movement reversed
5. Voucher state changes to **Cancelled**

**After Receipt:**
- Cannot cancel
- Must create return/adjustment if needed

---

### Requisition Rejection

**PAO Rejects Requisition:**
1. PAO clicks **Reject** button
2. Enters rejection reason
3. Requisition state changes to **Rejected**

**Requester Resubmits:**
1. Open rejected requisition
2. Click **Reset to Draft** button
3. Make corrections based on rejection reason
4. Click **Submit** again

---

## Role Permissions Summary

| Action | Department User | Storekeeper | Stock Clerk | PAO |
|--------|----------------|-------------|-------------|-----|
| Create Requisition | ✓ | ✓ | ✓ | ✓ |
| Submit Requisition | ✓ | ✓ | ✓ | ✓ |
| Approve Requisition | ✗ | ✗ | ✗ | ✓ |
| Reject Requisition | ✗ | ✗ | ✗ | ✓ |
| Create Issue Voucher | ✗ | ✓ | ✗ | ✓ |
| Issue Materials | ✗ | ✓ | ✗ | ✓ |
| Confirm Receipt | ✓ | ✓ | ✓ | ✓ |
| Post to Records | ✗ | ✗ | ✓ | ✓ |
| View All | ✗ | Approved Only | ✓ | ✓ |

---

## Audit Trail

All actions are automatically logged with:
- User who performed action
- Date and time
- State changes
- Field modifications
- Comments and notes

**View Audit Trail:**
1. Open requisition or issue voucher
2. Scroll to bottom (Chatter section)
3. Review all logged activities

---

## Reporting

### Pending Requisitions
**Filter:** State = Submitted
**Use:** PAO approval queue

### Approved Requisitions
**Filter:** State = Approved
**Use:** Storekeeper issue queue

### Issued Materials
**View:** Issue Vouchers → Filter: Issued
**Use:** Track pending receipts

### Departmental Consumption
**Group By:** Department
**Use:** Analyze consumption patterns

### Controlled Material Issues
**Filter:** Item → Controlled Material = Yes
**Use:** Audit controlled substances

---

## Best Practices

### For Department Users
1. Provide clear justification in notes
2. Verify item codes and quantities before submit
3. Submit requisitions with adequate lead time
4. Confirm receipt promptly upon delivery

### For PAO
1. Review requisitions daily
2. Verify budget availability before approval
3. Check for duplicate requisitions
4. Provide clear rejection reasons

### For Storekeepers
1. Verify stock availability before creating voucher
2. Issue materials promptly after approval
3. Ensure proper labeling and packaging
4. Retain triplicate copy for records

### For Stock Clerks
1. Post to records daily
2. Verify FIFO valuation
3. Reconcile with physical stock
4. File documents systematically

---

## Troubleshooting

### Cannot Submit Requisition
- **Cause:** No requisition lines added
- **Solution:** Add at least one line item

### Cannot Approve Requisition
- **Cause:** User not in PAO group
- **Solution:** Contact system administrator

### Cannot Create Issue Voucher
- **Cause:** Requisition not approved
- **Solution:** Wait for PAO approval

### Insufficient Stock Error
- **Cause:** Requested quantity exceeds available stock
- **Solution:** Adjust quantity or wait for receiving

### Cannot Confirm Receipt
- **Cause:** Not all verification checks confirmed
- **Solution:** Confirm all three checkboxes

---

## Support

For technical issues or questions:
- Contact: System Administrator
- Email: [support@mesob.et]
- Phone: [+251-xxx-xxxx]

For process questions:
- Contact: Property Administration Officer (PAO)
- Department: Administration

---

## Document Version

- **Version:** 1.0
- **Date:** March 2026
- **Module:** mesob_inventory_base
- **Section:** 4.3 Issue of Stocks

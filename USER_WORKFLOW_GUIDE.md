# **MESOB IMS - USER WORKFLOW GUIDE**
## **Complete User Flow for Manual Testing**

**Version:** 1.0  
**Date:** June 22, 2026  
**Purpose:** Step-by-step guide for testing all automation features  
**Audience:** Absolute beginners, testers, trainers

---

## **HOW TO USE THIS GUIDE**

### **🎯 What This Document Is**
- A **complete walkthrough** of every workflow in the system
- Written for **absolute beginners** (no technical knowledge required)
- Real examples with **sample data** you can copy
- Step-by-step **screenshots guidance** (where to click, what to type)

### **📋 Testing Approach**
1. **Read each workflow** start to finish before testing
2. **Follow steps exactly** - don't skip anything
3. **Check "Expected Result"** after each step
4. **Mark ✅ if working, ❌ if broken**

### **👥 User Roles Reference**

| Role | Short Name | What They Do |
|------|-----------|--------------|
| Department Head | DH | Submits needs, approves department actions |
| Procurement Officer | PO/SPO | Manages procurement process |
| Property Admin Officer | PAO | Approves requisitions, oversees compliance |
| Procurement Unit Head | PUH | First approval level for APP |
| Procurement Evaluation Committee | PEC | Second approval level for APP |
| Head of Public Entity | HOPE | Final approval authority |
| Storekeeper | SK | Physical custody of stock, receives/issues items |
| Stock Clerk | SC | Maintains records (bin cards, stock record cards) |
| Accounts Unit | ACC | Payment processing, financial records |

---

## **TABLE OF CONTENTS**

1. [Annual Procurement Planning (APP) Workflow](#1-annual-procurement-planning-app)
2. [Procurement Execution Workflow](#2-procurement-execution)
3. [Receiving & Inspection Workflow](#3-receiving--inspection)
4. [Payment Processing Workflow](#4-payment-processing)
5. [Stock Requisition & Issue Workflow](#5-stock-requisition--issue)
6. [Dispatch & Gate Pass Workflow](#6-dispatch--gate-pass)
7. [Stock Taking Workflow](#7-stock-taking)
8. [Stock Handover/Takeover Workflow](#8-stock-handovertakeover)
9. [Stock Control & Replenishment Workflow](#9-stock-control--replenishment)
10. [Disposal Workflow](#10-disposal)
11. [Reporting Workflows](#11-reporting)

---


## **1. ANNUAL PROCUREMENT PLANNING (APP)**

### **Overview**
Departments submit their needs → System consolidates → Approval workflow → Ready for procurement

### **Workflow Diagram**
```
Department Head → Submit Needs → System Validates Budget → SPO Consolidates 
  → System Groups Similar Items → Create Lots → PUH Approves → PEC Approves 
  → HOPE Approves → APP Ready
```

---

### **STEP 1: Department Needs Submission (AUTO-001)**

**Who:** Department Head (Finance, HR, IT, etc.)  
**When:** At start of fiscal year planning

#### **📋 BEFORE AUTOMATION (Manual Process):**

**The Old Way:**
1. Procurement Officer **physically walks** to each department office
2. Hands out **paper forms** (printed blank needs forms)
3. Department Head **manually writes** item descriptions, quantities, estimates
4. Department Head **physically signs** paper form
5. Procurement Officer **collects forms** one-by-one over several days/weeks
6. Department realizes they forgot items → Procurement Officer walks back again
7. **NO budget check** until much later (after consolidation)
8. Result: **Takes 2-3 weeks** just to collect forms

**Problems:**
- ❌ Time-consuming: Procurement Officer spends days collecting forms
- ❌ No real-time validation: Wrong item codes, misspellings, invalid items accepted
- ❌ Budget surprises: Department submits needs, later told "no budget"
- ❌ Lost forms: Paper gets misplaced
- ❌ No tracking: Who submitted? Who's pending?

#### **✨ WITH AUTOMATION (New Way):**

**Benefits:**
- ✅ **Self-service:** Department submits directly online
- ✅ **Real-time validation:** System checks item codes, budget instantly
- ✅ **No travel:** Procurement Officer receives all submissions in dashboard
- ✅ **Audit trail:** Who submitted, when, what changed
- ✅ **Result:** Collection time reduced from **2-3 weeks to 2-3 days**

---

#### **Actions:**

1. **Login** to system as Department Head
   - Username: `dh_finance@mesob.gov.et`
   - Password: `[provided by admin]`

2. **Navigate:** Main Menu → Procurement → Annual Planning → **My Department Needs**

3. **Click:** "Create" button (top-left)

4. **Fill Form:**
   ```
   Department: Finance Department [auto-filled]
   Fiscal Year: 2026/2027 [select from dropdown]
   Justification: "Annual office supplies and equipment renewal"
   ```

5. **Add Items (Click "Add a line"):**
   
   **Item 1:**
   ```
   Item Code: 4402-001-005 [type and select "Office Paper A4"]
   Description: Office Paper A4, 80gsm
   Quantity: 500
   Unit: Ream
   Estimated Unit Price: 150.00 [system suggests last price]
   Total Estimated Value: 75,000.00 [auto-calculated]
   Justification: "Monthly consumption 50 reams"
   ```
   
   **Item 2:**
   ```
   Item Code: 4403-002-010 [type and select "Printer Toner HP"]
   Description: HP LaserJet Toner Cartridge
   Quantity: 20
   Unit: Piece
   Estimated Unit Price: 2,500.00
   Total Estimated Value: 50,000.00
   Justification: "Replacement stock for 10 printers"
   ```

6. **Click:** "Check Budget Availability" button

   **✅ Expected Result:**
   - System shows: "Budget Available: 200,000 ETB | Requested: 125,000 ETB | Status: ✅ OK"
   - If budget insufficient: System shows red warning "Budget Exceeded by [amount]"

7. **Click:** "Submit for Approval" button

   **✅ Expected Result:**
   - Status changes to "Pending Approval"
   - Notification sent to PAO: "New needs submission from Finance Department awaiting approval"
   - Dashboard shows submission in "Pending" list

---

### **STEP 2: PAO Review & Approval**

**Who:** Property Administration Officer  
**When:** After department submission

#### **📋 BEFORE AUTOMATION:**

**The Old Way:**
1. PAO receives **stack of paper forms** from Procurement Officer
2. **Manually checks** each form:
   - Reads handwriting (sometimes illegible)
   - Looks up item codes in **printed catalog**
   - Uses **calculator** to check totals
   - Checks budget in **separate Excel file**
3. If rejecting: **Writes rejection note** on paper, physically returns to department
4. If approving: **Stamps and signs** paper, moves to next stack
5. Result: **Takes 3-5 days** to review all departments

**Problems:**
- ❌ Slow: Each form reviewed manually
- ❌ Error-prone: Can't read handwriting, calculation mistakes
- ❌ No notification: Department doesn't know status until paper returned
- ❌ Bottleneck: PAO reviews alone, can't delegate

#### **✨ WITH AUTOMATION:**

**Benefits:**
- ✅ **One dashboard:** All submissions in one place with filters
- ✅ **Pre-validated:** System already checked item codes, budget
- ✅ **Instant notification:** Department gets email when approved/rejected
- ✅ **Audit trail:** Every action logged with timestamp
- ✅ **Result:** Review time reduced from **3-5 days to few hours**

---

#### **Actions:**

1. **Login** as PAO: `pao@mesob.gov.et`

2. **Check Notification:**
   - Bell icon (top-right) shows: "3 new needs submissions"
   - Click notification → Opens list

3. **Navigate:** Procurement → Annual Planning → **Needs Submissions**

4. **Filter:** Status = "Pending Approval"

5. **Open:** Finance Department submission

6. **Review:**
   - Check item codes valid (system shows ✅ next to valid codes)
   - Check budget availability (green badge if OK)
   - Review justifications

7. **Decision:**
   
   **If Approving:**
   - Click "Approve" button
   - Add comment: "Approved - aligns with annual plan"
   - ✅ Expected: Status → "Approved", Notification to Dept Head

   **If Rejecting:**
   - Click "Reject" button
   - **Required:** Type reason: "Item 4403-002-010 not in approved catalog"
   - ✅ Expected: Status → "Rejected", Department can revise and resubmit

---

### **STEP 3: Intelligent Consolidation (AUTO-002)**

**Who:** Senior Procurement Officer (SPO)  
**When:** After all departments submitted needs

#### **📋 BEFORE AUTOMATION:**

**The Old Way:**
1. SPO receives **hundreds of paper forms** from all departments
2. **Manually reads** each form line-by-line
3. **Writes on separate paper:**
   - Finance needs: Paper A4 - 500 reams
   - HR needs: A4 Paper - 200 reams
   - IT needs: Office paper A4 - 100 reams
4. **Realizes** these are same item (different descriptions!)
5. Uses **calculator:** 500 + 200 + 100 = 800 reams
6. **Manually writes** consolidated list
7. **Looks up** last purchase price in old files
8. Uses **calculator** to estimate total value
9. **Manually decides** procurement method (checks threshold in printed manual)
10. **Repeats** for every item (could be 200+ items!)
11. Result: **Takes 1-2 weeks** for consolidation

**Problems:**
- ❌ **Extremely time-consuming:** Entire week spent on manual grouping
- ❌ **Error-prone:** Easy to miss similar items, calculation mistakes
- ❌ **Inconsistent:** "A4 Paper" vs "Paper A4" treated as different items
- ❌ **No history:** Last purchase price requires digging through old files

#### **✨ WITH AUTOMATION:**

**Benefits:**
- ✅ **Automatic grouping:** System groups identical item codes instantly
- ✅ **Keyword matching:** Finds similar descriptions ("A4 Paper" = "Paper A4")
- ✅ **Auto-calculation:** Totals, values, methods calculated automatically
- ✅ **Historical prices:** System suggests last purchase price
- ✅ **Threshold-based:** System suggests procurement method based on value
- ✅ **Result:** Consolidation time reduced from **1-2 weeks to 1-2 hours**

---

#### **Actions:**

1. **Login** as SPO: `spo@mesob.gov.et`

2. **Navigate:** Procurement → Annual Planning → **Consolidation Wizard**

3. **Click:** "Start Consolidation" button

4. **System Automatic Actions:**
   - Groups identical item codes from all departments
   - Calculates total quantities
   - Shows potentially similar items (keyword matching)

5. **Review Consolidation:**

   **Example Screen:**
   ```
   Item Code: 4402-001-005 (Office Paper A4)
   ├── Finance Dept: 500 reams
   ├── HR Dept: 200 reams
   ├── IT Dept: 100 reams
   └── Total: 800 reams
   
   Suggested Lot:
   ├── Total Quantity: 800 reams
   ├── Total Value: 120,000 ETB
   ├── Suggested Method: RFQ (below NCB threshold)
   └── Lead Time: 30 days
   ```

6. **Check Similar Items Warning:**
   ```
   ⚠️ Potential Duplicates Found:
   - 4402-001-005 "Office Paper A4"
   - 4402-001-007 "A4 Paper White"
   
   Action: [Merge] [Keep Separate]
   ```
   - Click "Merge" if same item
   - Select primary code: 4402-001-005

7. **Approve Consolidation:**
   - Review all grouped items
   - Click "Create Procurement Lots"
   
   **✅ Expected Result:**
   - System creates lot records
   - Status: "Ready for Approval Workflow"
   - Lots visible in "Procurement Lots" menu

---


### **STEP 4: Approval Workflow (AUTO-004)**

**Who:** PUH → PEC → HOPE (sequential)  
**When:** After lot creation

#### **Actions:**

**4A. PUH Approval**

1. **Login** as PUH: `puh@mesob.gov.et`

2. **Check Dashboard:**
   - "Pending My Approval" widget shows: "5 lots waiting"
   - Days in approval: 0 days (green)

3. **Navigate:** Procurement → Annual Planning → **Lots Pending Approval**

4. **Filter:** Approval Stage = "PUH Review"

5. **Open:** Lot "LOT-2026-001 - Office Supplies"

6. **Review:**
   - Total value: 120,000 ETB
   - Items: 8 items consolidated
   - Suggested method: RFQ
   - Budget status: ✅ Available

7. **Approve:**
   - Click "Approve" button
   - Add note: "Approved for tendering"
   
   **✅ Expected Result:**
   - Status → "PUH Approved"
   - Notification to PEC: "New lot awaiting your approval"
   - Dashboard updates: "Days at PEC: 0 days"

**4B. PEC Approval** (Same steps as PUH, login as `pec@mesob.gov.et`)

**4C. HOPE Final Approval** (Same steps, login as `hope@mesob.gov.et`)

**✅ Final Expected Result:**
- Lot status → "Fully Approved"
- Ready for tender preparation
- Email notification to SPO: "Lot LOT-2026-001 approved - proceed to tender"

---

### **STEP 5: SLA Alert Testing (AUTO-004)**

**Purpose:** Verify system alerts when approvals delayed

#### **Actions:**

1. **As Admin:** Navigate to Settings → Technical → Scheduled Actions

2. **Find:** "Procurement Approval SLA Checker"

3. **Click:** "Run Manually" (or wait for cron)

4. **Expected Behavior:**
   - If lot at PUH > 3 days → Yellow warning badge
   - If lot at PUH > 5 days → Red alert + email to PUH + escalation to PEC
   - If lot at PEC > 5 days → Email to HOPE

5. **Test:**
   - Create test lot
   - Set approval date to 6 days ago (using developer tools or SQL)
   - Run cron
   - Check notifications

   **✅ Expected:**
   - Email sent to approver: "Lot LOT-2026-001 overdue for approval (6 days)"
   - Dashboard shows red badge

---

## **2. PROCUREMENT EXECUTION**

### **Overview**
Approved lot → Select method → Prepare tender → Receive bids → Evaluate → Award contract

---

### **STEP 1: Procurement Method Selection (AUTO-006)**

**Who:** SPO  
**When:** After lot approval

#### **Actions:**

1. **Login** as SPO

2. **Navigate:** Procurement → Lots → **Approved Lots**

3. **Open:** LOT-2026-001

4. **Check System Suggestion:**
   ```
   Suggested Procurement Method: RFQ
   Reason: Total value (120,000 ETB) below NCB threshold (200,000 ETB)
   
   Thresholds (from settings):
   - Shopping: 0 - 50,000 ETB
   - RFQ: 50,001 - 200,000 ETB
   - NCB: 200,001 - 2,000,000 ETB
   - ICB: Above 2,000,000 ETB
   ```

5. **Decision:**
   - Accept suggestion: Click "Use Suggested Method"
   - OR Override: Select different method + provide justification

6. **If Overriding to Direct/Single-Source:**
   ```
   Method: Single Source
   Justification: [REQUIRED] "Only supplier certified for this equipment"
   Supporting Document: [Upload certificate]
   ```
   
   **✅ Expected:**
   - System requires justification if non-standard method
   - Logs override in audit trail

---

### **STEP 2: Supplier Registration Check (AUTO-008)**

**Who:** SPO (before creating tender)  
**When:** Selecting suppliers

#### **📋 BEFORE AUTOMATION:**

**The Old Way:**
1. SPO opens **filing cabinet**, looks for supplier folder
2. **Finds paper registration certificate** (if not misplaced)
3. **Reads expiry date** manually
4. Uses calculator/counts fingers: "Today is June 22... expiry July 15... 23 days left"
5. **Forgets** to follow up
6. **Week later:** Creates PO for supplier whose registration expired
7. **Audit finding:** "PO issued to expired supplier!"

**Problems:**
- ❌ Manual date checking (error-prone)
- ❌ No alerts when registration expiring
- ❌ Easy to create PO for expired supplier
- ❌ Audit findings after the fact

#### **✨ WITH AUTOMATION:**

**Benefits:**
- ✅ Automatic monitoring (60/30/15 day alerts)
- ✅ System blocks PO creation for expired suppliers
- ✅ Dashboard shows all supplier statuses
- ✅ Email reminders to suppliers to renew
- ✅ Zero audit findings

---

#### **Actions:**

1. **Navigate:** Procurement → Suppliers → **Supplier List**

2. **Open:** Supplier "ABC Trading PLC"

3. **Check Registration Status:**
   ```
   Registration Details:
   ├── Registration Number: REG-2024-1234
   ├── Registration Date: Jan 15, 2024
   ├── Expiry Date: Jan 14, 2026 ⚠️ [60 days remaining]
   ├── Status: 🟡 Expiring Soon
   └── Documents: [View]
   ```

4. **Alert Verification:**
   - System shows yellow badge: "⚠️ Registration expires in 60 days"
   - Notification sent to supplier (if email configured)
   - Notification sent to SPO: "3 suppliers expiring soon"

5. **Test Expired Supplier:**
   - Try to add expired supplier to tender
   
   **✅ Expected:**
   - System blocks: "Cannot add supplier ABC Trading - Registration expired on Jan 14, 2025"
   - Red badge shows on supplier card

---

### **STEP 3: Bid Deadline Enforcement (AUTO-011, AUTO-012)**

**Who:** SPO (creating tender) + Bidders (submitting bids)

#### **📋 BEFORE AUTOMATION:**

**The Old Way:**
1. Tender deadline: "June 29, 15:00 hrs"
2. Suppliers submit by **email, paper, hand-delivery**
3. Supplier arrives at 15:30: "Sorry, late!"
4. Supplier argues: "Traffic was bad! I sent email at 14:55!"
5. **No conclusive proof** of exact submission time
6. **Disputes, complaints, legal threats**
7. To avoid trouble: Late bid accepted (unfair to others!)

**Problems:**
- ❌ No tamper-proof timestamps
- ❌ Disputes about submission time
- ❌ Inconsistent enforcement
- ❌ Legal risks
- ❌ Wasted committee time

#### **✨ WITH AUTOMATION:**

**Benefits:**
- ✅ System-enforced deadlines (automatic rejection)
- ✅ Tamper-proof server timestamps
- ✅ Zero disputes (timestamp is proof)
- ✅ Fair enforcement (same rules for all)
- ✅ FPPA compliance

---

#### **Actions - Creating Tender:**

1. **Navigate:** Procurement → Tenders → **Create Tender**

2. **Fill Details:**
   ```
   Tender Number: TND-2026-001 [auto-generated]
   Lot Reference: LOT-2026-001
   Procurement Method: RFQ
   Invitation Date: June 22, 2026 [today]
   ```

3. **Set Deadline:**
   - Try to set: June 23, 2026 (1 day)
   
   **✅ Expected:**
   - System blocks: "Minimum advertising period for RFQ is 7 days per FR-PROC-014"
   - Earliest allowed date: June 29, 2026

4. **Set Valid Deadline:**
   ```
   Submission Deadline: June 29, 2026 at 15:00 hrs
   ```
   - Click "Publish Tender"

#### **Actions - Late Bid Submission:**

1. **Login** as Supplier: `supplier1@abctrading.com`

2. **Navigate:** Supplier Portal → **Open Tenders**

3. **Open:** TND-2026-001

4. **Try Submit After Deadline:**
   - Wait until June 29, 2026 15:01 (or change system time for testing)
   - Fill bid form
   - Click "Submit Bid"

   **✅ Expected:**
   - System rejects: "Bid rejected - Late submission!"
   - Shows: "Deadline: Jun 29, 15:00 | Your submission: Jun 29, 15:01 | Late by: 1 minute"
   - Bid not saved
   - System logs rejection with timestamp

---


### **STEP 4: RFQ Three-Quotation Rule (AUTO-013)**

**Who:** SPO (awarding contract)  
**When:** After bid submission deadline

#### **Actions:**

1. **Navigate:** Procurement → Tenders → **TND-2026-001**

2. **Check Submissions:**
   ```
   Valid Bids Received: 2
   - ABC Trading PLC: 115,000 ETB
   - XYZ Suppliers: 118,000 ETB
   ```

3. **Try to Award:**
   - Click "Award Contract" button
   - Select winner: ABC Trading PLC

   **✅ Expected:**
   - System blocks: "Cannot award - Minimum 3 quotations required for RFQ (FR-PROC-016)"
   - Shows: "Current quotations: 2 | Required: 3"

4. **Provide Justification (PAO Override):**
   - Dialog appears: "Override Reason Required"
   - Type: "Only 2 qualified suppliers available in market for this item"
   - Upload: Market research document
   - Click "Confirm Override"

   **✅ Expected:**
   - System allows award WITH documented justification
   - Logs override in audit trail with PAO signature

---

### **STEP 4: Domestic Preference Calculation (AUTO-015)**

**Who:** Evaluation Committee  
**When:** Evaluating bids

#### **📋 BEFORE AUTOMATION:**

**The Old Way:**
1. Evaluator has **3-5 bids** to evaluate
2. **Manually checks** supplier local content % (from registration files)
3. Uses **calculator** for EACH bid:
   - If ≥70% local: Bid × 13.5% = Preference amount
   - If 40-70% local: Bid × 11% = Preference amount
   - If <40%: No preference
4. **Subtracts** preference from bid price to get "evaluated price"
5. **Manually ranks** by evaluated price
6. **Types** evaluation report in Word
7. **Often makes mistakes:** Wrong %, wrong formula, wrong ranking

**Real Example of Manual Error:**
```
Bid A: 115,000 ETB, 75% local
Manual calc: 115,000 × 0.135 = 15,525
Evaluated: 115,000 - 15,525 = 99,475 ✓ [CORRECT]

Bid B: 118,000 ETB, 50% local  
Manual calc: 118,000 × 0.135 = 15,930 ❌ [WRONG - should be 11%!]
Evaluated: 118,000 - 15,930 = 102,070 [INCORRECT]

Result: Wrong winner selected due to calculation error!
```

**Problems:**
- ❌ Calculator fatigue (many bids, many calculations)
- ❌ Formula confusion (13.5% vs 11% vs 0%)
- ❌ Ranking errors
- ❌ Must type report manually
- ❌ Audit findings when errors discovered

#### **✨ WITH AUTOMATION:**

**Benefits:**
- ✅ System reads local content % from supplier master
- ✅ Auto-applies correct formula (13.5%, 11%, or 0%)
- ✅ Auto-calculates evaluated price
- ✅ Auto-ranks bids (lowest evaluated = winner)
- ✅ Auto-generates evaluation report with worksheet
- ✅ Zero calculation errors

---

#### **Actions:**

1. **Navigate:** Procurement → Tenders → TND-2026-001 → **Bid Evaluation**

2. **Review Bids:**
   ```
   Bid 1: ABC Trading PLC
   ├── Bid Price: 115,000 ETB
   ├── Local Content: 75% [from supplier registration]
   ├── Domestic Preference: 13.5% [≥70% local content per BR-PROC-003]
   ├── Preference Amount: 15,525 ETB [auto-calculated]
   ├── Evaluated Price: 99,475 ETB [115,000 - 15,525]
   └── Rank: 1st

   Bid 2: XYZ Suppliers
   ├── Bid Price: 118,000 ETB
   ├── Local Content: 50%
   ├── Domestic Preference: 11% [40-70% local content]
   ├── Preference Amount: 12,980 ETB
   ├── Evaluated Price: 105,020 ETB
   └── Rank: 2nd
   
   Bid 3: Foreign Supplier Ltd
   ├── Bid Price: 110,000 ETB
   ├── Local Content: 0% [foreign]
   ├── Domestic Preference: 0%
   ├── Preference Amount: 0 ETB
   ├── Evaluated Price: 110,000 ETB [no preference]
   └── Rank: 3rd
   ```

3. **System Auto-Ranks:** by Evaluated Price (lowest first)

4. **Generate Evaluation Report:**
   - Click "Generate Report" button
   
   **✅ Expected:**
   - System creates evaluation report with:
     - All bids table (bid price vs evaluated price)
     - Preference calculation worksheet
     - Recommendation: "Award to ABC Trading PLC as lowest evaluated responsive bid"
   - Report in PDF format for PEC/HOPE approval

---

### **STEP 6: Contract Generation (AUTO-018)**

**Who:** SPO  
**When:** After contract awarded

#### **📋 BEFORE AUTOMATION:**

**The Old Way:**
1. SPO opens **Word template** (if one exists)
2. **Manually types** every detail:
   - Supplier name, address, TIN (from registration file)
   - Contract number (checks last number in register)
   - Item codes, descriptions, quantities, prices (from winning bid)
   - Delivery dates (manually calculates from today + lead time)
   - Standard clauses (copy-paste from old contracts)
3. **Proofreading:** Typos, wrong amounts, copy-paste errors
4. **Printing:** 2-3 copies
5. **Time:** 2-4 hours per contract

**Real Horror Story:**
```
Contract typed for ABC Trading:
- Supplier address copied from OLD contract (still shows previous supplier!)
- Item quantity: 80 reams (should be 800 - missed a zero!)
- Delivery date: August 22, 2025 (typo - should be 2026!)
- Payment terms: From different contract (50% advance vs agreed 30% advance)

Result:
→ Supplier refuses to sign (errors throughout)
→ SPO must retype entire contract
→ 2 more days wasted
→ Supplier frustrated
```

**Problems:**
- ❌ **2-4 hours** to type one contract
- ❌ Typos and copy-paste errors
- ❌ Inconsistent formatting
- ❌ Wrong details (old supplier info, wrong dates)
- ❌ Must proofread multiple times

#### **✨ WITH AUTOMATION:**

**Benefits:**
- ✅ One-click contract generation (1 minute vs 2-4 hours)
- ✅ All details auto-filled from bid/supplier master
- ✅ Zero typos (no manual typing)
- ✅ Professional formatting (HTML/PDF)
- ✅ Consistent clauses
- ✅ Auto-calculated dates and amounts

---

#### **Actions:**

1. **Navigate:** Procurement → Contracts → **Create from Tender**

2. **Select:** TND-2026-001 (awarded)

3. **System Auto-Fills:**
   ```
   Contract Number: CNT-2026-001 [auto-generated]
   Supplier: ABC Trading PLC
   ├── Address: [from supplier master]
   ├── TIN: 0012345678
   └── Contact: +251-11-1234567
   
   Contract Value: 115,000 ETB [bid price, NOT evaluated price]
   
   Items:
   ├── Item 1: Office Paper A4 - 800 reams @ 150 ETB = 120,000 ETB
   └── [from winning bid]
   
   Delivery Schedule:
   ├── Delivery Date: August 22, 2026 [90 days from contract signature]
   └── Delivery Location: Main Warehouse [from lot specification]
   
   Standard Clauses:
   ├── Payment Terms: Net 30 days after delivery
   ├── Liquidated Damages: 1/1000 per day delay (max 10%)
   ├── Warranty: 90 days
   └── Performance Security: 10% of contract value
   ```

4. **Review & Customize:**
   - Add special clause: "All items must be delivered in original packaging"
   - Set payment terms: 50% advance, 50% on delivery

5. **Generate Contract Document:**
   - Click "Generate Contract" button
   
   **✅ Expected:**
   - Professional HTML contract with all details
   - Ready for signature
   - Two copies: Original (supplier), Duplicate (office)

---

### **STEP 7: Contract Milestone Tracking (AUTO-020)**

**Who:** SPO (monitoring) + System (automatic alerts)

#### **Actions:**

1. **Navigate:** Procurement → Contracts → **CNT-2026-001**

2. **Check Milestones:**
   ```
   Milestone 1: Advance Payment
   ├── Due Date: July 5, 2026
   ├── Status: ⏳ Pending
   └── Alert: -14 days (notification sent)
   
   Milestone 2: Delivery
   ├── Due Date: August 22, 2026
   ├── Status: 🕐 Upcoming
   └── Alert: -14 days (notification scheduled)
   
   Milestone 3: Final Payment
   ├── Due Date: September 21, 2026
   ├── Status: 🔜 Scheduled
   └── Depends on: Delivery completion
   ```

3. **Test Overdue Alert:**
   - Change delivery date to 5 days ago (admin/testing only)
   - Run cron: "Contract Milestone Checker"

   **✅ Expected:**
   - Milestone status → 🔴 Overdue (5 days)
   - Email to SPO: "Contract CNT-2026-001 delivery overdue by 5 days"
   - Email to supplier: "Reminder: Contract delivery 5 days overdue"
   - Dashboard shows red flag

---


## **3. RECEIVING & INSPECTION**

### **Overview**
Goods arrive → Storekeeper notified → Inspection → Accept (Model 19) or Reject (DSR)

---

### **STEP 1: PO-to-Receiving Handoff (AUTO-025)**

**Who:** System (automatic) → Storekeeper (receives notification)

#### **📋 BEFORE AUTOMATION:**

**The Old Way:**
1. SPO creates Purchase Order
2. **Prints** PO, files one copy
3. **Hopes to remember** to tell Storekeeper
4. **Days later:** SPO calls Storekeeper: "By the way, expecting delivery from ABC Trading next week"
5. Storekeeper: "What items? How many?"
6. SPO: "Check your email... or I'll send you a copy"
7. **OR:** Supplier arrives **unexpectedly**, Storekeeper unprepared
8. Storekeeper scrambles to find PO details, check what was ordered

**Real Chaos:**
```
Monday 10 AM: Delivery truck arrives
Storekeeper: "Who are you? What delivery?"
Driver: "ABC Trading - Paper delivery"
Storekeeper: "I wasn't told about this!"
[Searches emails, calls SPO (not answering), checks files]
[30 minutes wasted, truck waiting]
Storekeeper: "OK, unload, I'll figure it out later"
[Receives items without proper PO reference]
[Later: Can't match to PO, payment delayed]
```

**Problems:**
- ❌ No advance notice to Storekeeper
- ❌ Unprepared receiving area
- ❌ Don't know what inspection type needed
- ❌ Delayed receiving process
- ❌ Manual phone calls/emails to coordinate

#### **✨ WITH AUTOMATION:**

**Benefits:**
- ✅ Automatic notification when PO confirmed
- ✅ Storekeeper sees expected delivery details
- ✅ Inspection type pre-assigned
- ✅ Receiving area can be prepared in advance
- ✅ Dashboard shows "Expected Deliveries"

---

#### **Setup - Create Purchase Order:**

1. **Login** as SPO

2. **Navigate:** Procurement → Purchase Orders → **Create**

3. **Fill:**
   ```
   PO Number: PO-2026-001
   Supplier: ABC Trading PLC
   Contract Reference: CNT-2026-001
   Expected Delivery Date: August 22, 2026
   
   Items:
   - Office Paper A4: 800 reams @ 150 ETB
   ```

4. **Click:** "Confirm PO"

#### **Automatic Notification:**

**✅ Expected Result:**
- System automatically sends notification to Storekeeper:
  ```
  Subject: Expected Delivery - PO-2026-001
  
  Dear Storekeeper,
  
  A new purchase order has been issued. Please prepare for delivery:
  
  PO Number: PO-2026-001
  Supplier: ABC Trading PLC
  Expected Date: August 22, 2026
  
  Items to Receive:
  1. Office Paper A4 (4402-001-005) - 800 reams
  
  Inspection Type: Storekeeper Inspection [auto-assigned based on item classification]
  
  Please ensure receiving area is ready.
  ```

---

### **STEP 2: Receiving Process**

**Who:** Storekeeper  
**When:** Goods arrive

#### **📋 BEFORE AUTOMATION (CASE A: Acceptance):**

**The Old Way:**
1. Goods arrive, Storekeeper **physically counts**
2. **Writes on Model 19 form** (paper):
   - Item description (handwritten)
   - Quantity received (handwritten)
   - Supplier name (handwritten)
   - Date (handwritten)
3. **Signs** Model 19
4. **Makes 4 photocopies** (often poor quality)
5. **Physically walks** to:
   - Accounts Unit (delivers original)
   - Stock Clerk office (delivers duplicate)
   - Finds driver (gives triplicate for supplier)
   - Keeps book copy
6. **Manually writes** in Bin Card (quantity received)
7. **Time:** 1-2 hours for receiving + distribution

**Problems:**
- ❌ Handwriting (illegible, errors)
- ❌ Photocopies (poor quality, cost)
- ❌ Physical distribution (time-consuming, copies lost)
- ❌ Manual Bin Card updates (can forget)
- ❌ No automatic PO update

#### **📋 BEFORE AUTOMATION (CASE B: Rejection/DSR):**

**The Old Way:**
1. Storekeeper finds damaged items
2. **Writes DSR form** by hand:
   - What's wrong, how many rejected
3. **Makes 4 photocopies**
4. **Walks** to deliver copies:
   - Supplier (with rejected goods)
   - Accounts (to block payment)
   - Procurement Officer (to follow up)
5. **Calls** Procurement Officer: "I rejected 50 reams, you need to get replacement"
6. Procurement Officer: "OK, I'll call supplier"
7. **Weeks pass** - no tracking of replacement status
8. **Payment accidentally processed** (Accounts didn't get DSR copy!)

**Problems:**
- ❌ Manual DSR creation (errors)
- ❌ Paper distribution (copies lost, Accounts doesn't get it)
- ❌ No automatic payment block
- ❌ No replacement tracking
- ❌ Manual follow-up calls

#### **✨ WITH AUTOMATION:**

**Benefits:**
- ✅ Digital Model 19 generation (one click)
- ✅ Automatic four-copy distribution (email notifications)
- ✅ Auto-update Bin Card, Stock Record Card
- ✅ Auto-update PO status
- ✅ Auto-enable three-way match for payment
- ✅ DSR auto-blocks payment
- ✅ Replacement tracking workflow

---

#### **Actions:**

1. **Login** as Storekeeper: `storekeeper@mesob.gov.et`

2. **Check Dashboard:**
   - "Expected Deliveries" widget shows: PO-2026-001 (Due: Today)

3. **Navigate:** Inventory → Receiving → **Create Receiving**

4. **Select PO:**
   - Type: PO-2026-001
   - System auto-fills items from PO

5. **Physical Check:**
   ```
   Expected (from PO): 800 reams
   Delivered (count): 800 reams [enter actual count]
   
   Inspection Checklist [auto-populated from PO]:
   ☑ Packaging intact
   ☑ Correct item code (4402-001-005)
   ☑ Quantity matches
   ☑ Quality acceptable (no damage)
   ☑ Expiry date valid (if applicable)
   ```

6. **Decision:**

**CASE A: FULL ACCEPTANCE**

7A. **All Items Accepted:**
   - Mark all items as "Accepted"
   - Click "Generate Model 19"

   **✅ Expected Result:**
   ```
   Model 19 Generated: M19-2026-001
   Date: August 22, 2026
   
   Items Received:
   - Office Paper A4: 800 reams @ 150 ETB = 120,000 ETB
   
   Automatic Actions:
   ✓ Four copies created and distributed:
     - Original → Accounts Unit [notification sent]
     - Duplicate → Stock Clerk [notification sent]
     - Triplicate → Supplier ABC Trading [email sent]
     - Book Copy → Storekeeper [retained in system]
   
   ✓ PO Status updated: "Received"
   ✓ Bin Card updated: +800 reams
   ✓ Stock Record Card updated: +800 reams @ 150 ETB
   ✓ Three-way match enabled for payment
   ```

**CASE B: REJECTION (Partial or Full)**

7B. **Items Rejected:**
   - Delivered quantity: 800 reams
   - Inspection finding: "50 reams damaged by water"
   - Accepted: 750 reams
   - Rejected: 50 reams

8B. **Generate DSR:**
   - Click "Create DSR" for rejected items
   
   **Fill DSR Form:**
   ```
   DSR Number: DSR-2026-001 [auto-generated]
   Date: August 22, 2026
   PO Reference: PO-2026-001
   Supplier: ABC Trading PLC
   
   Discrepancy Type: ☑ Damaged
   
   Details:
   Item: Office Paper A4 (4402-001-005)
   Ordered: 800 reams
   Delivered: 800 reams
   Accepted: 750 reams
   Rejected: 50 reams
   Reason: "Water damage - packaging soaked, paper unusable"
   
   Action Required: Replacement within 7 days
   
   [Attach Photo] [Optional]
   ```

9B. **Confirm DSR:**

   **✅ Expected Result:**
   ```
   DSR-2026-001 Generated
   
   Automatic Actions:
   ✓ Four copies distributed:
     - Original → Supplier [with rejected goods, email sent]
     - Duplicate → Accounts/Finance [payment blocked]
     - Triplicate → Procurement Officer [replacement workflow]
     - Book Copy → Storekeeper
   
   ✓ PO Status: "Pending Replacement"
   ✓ Payment blocked until replacement received
   ✓ Model 19 generated for ACCEPTED items only (750 reams)
   ✓ Bin Card updated: +750 reams (not 800)
   ```

---

### **STEP 3: DSR Loop Closure (AUTO-028)**

**Who:** Procurement Officer (tracking) + Supplier (replacement)

#### **Actions:**

1. **Login** as Procurement Officer

2. **Check Notification:**
   - "DSR-2026-001 created - Supplier replacement required"

3. **Navigate:** Procurement → **Open DSRs**

4. **Open:** DSR-2026-001

5. **Track Replacement:**
   ```
   DSR Status: 🟡 Pending Supplier Response
   Created: Aug 22, 2026
   Days Open: 2 days
   
   Timeline:
   ├── Aug 22: DSR created
   ├── Aug 23: Supplier notified [email sent]
   ├── Aug 24: Supplier acknowledged [logged]
   └── Aug 29: Replacement due date [auto-calculated: 7 days]
   
   Actions:
   [Contact Supplier] [Request Update] [Escalate to Contract Manager]
   ```

6. **When Replacement Arrives:**
   - Storekeeper receives replacement (50 reams)
   - Creates new receiving: RCV-2026-002
   - Links to DSR-2026-001
   - Generates Model 19 for replacement

   **✅ Expected Result:**
   ```
   ✓ DSR Status: "Closed - Replacement Received"
   ✓ PO Status: "Fully Received" (750 + 50 = 800)
   ✓ Payment unblocked
   ✓ Supplier performance score updated (DSR affects rating)
   ```

---


## **4. PAYMENT PROCESSING**

### **Overview**
Supplier invoice received → Three-way match → Calculate adjustments → Approve payment

---

### **STEP 1: Three-Way Match (AUTO-029)**

**Who:** Accounts Unit  
**When:** Invoice received from supplier

#### **📋 BEFORE AUTOMATION:**

**The Old Way:**
1. Accounts clerk has **3 paper documents:**
   - Purchase Order (from Procurement)
   - Model 19 (from Storekeeper)
   - Invoice (from Supplier)
2. **Manually compares** line by line:
   - Reads item code from PO: "4402-001-005"
   - Reads item code from Model 19: "4402-001-005" ✓
   - Reads item code from Invoice: "4402-001-005" ✓
3. **Manually compares** quantities:
   - PO: 800 reams
   - Model 19: 800 reams ✓
   - Invoice: 800 reams ✓
4. **Uses calculator** for prices:
   - PO: 150 ETB × 800 = 120,000 ETB
   - Invoice: 150 ETB × 800 = 120,000 ETB ✓
5. **Repeats** for EVERY line item (could be 20+ items!)
6. **Time:** 1-2 hours per invoice

**Real Disaster:**
```
Accounts clerk tired after checking 15 items...

Item 16:
- PO: 100 units @ 500 ETB = 50,000 ETB
- Model 19: 100 units [clerk skips, assumes OK]
- Invoice: 120 units @ 500 ETB = 60,000 ETB

MISTAKE: Clerk missed that Invoice shows 120 units but only 100 received!
→ Payment processed for 60,000 ETB
→ Actual delivery: 50,000 ETB worth
→ Overpayment: 10,000 ETB
→ Audit finding 6 months later
→ Trying to recover money from supplier (difficult!)
```

**Problems:**
- ❌ **1-2 hours** per invoice (manual checking)
- ❌ Human fatigue errors (miss discrepancies)
- ❌ Calculator mistakes
- ❌ Easy to miss DSR (payment not blocked)
- ❌ Overpayments discovered months later

#### **✨ WITH AUTOMATION:**

**Benefits:**
- ✅ Automatic comparison (item codes, quantities, prices)
- ✅ Instant detection of mismatches
- ✅ Auto-check for open DSRs (payment blocking)
- ✅ Tolerance checking (alert if price variance > 2%)
- ✅ Time reduced from 1-2 hours to 5 minutes

---

#### **Actions:**

1. **Login** as Accounts Clerk: `accounts@mesob.gov.et`

2. **Navigate:** Accounting → Supplier Invoices → **Create Invoice**

3. **Enter Invoice Details:**
   ```
   Supplier: ABC Trading PLC
   Invoice Number: INV-ABC-2026-001
   Invoice Date: August 25, 2026
   PO Reference: PO-2026-001 [select from dropdown]
   ```

4. **System Auto-Loads PO Items:**
   ```
   Item: Office Paper A4
   Ordered (PO): 800 reams @ 150 ETB = 120,000 ETB
   Received (Model 19): 800 reams [system checks]
   Invoiced (Invoice): [enter from invoice]
   ```

5. **Enter Invoice Quantities:**
   ```
   Invoice Quantity: 800 reams
   Invoice Unit Price: 150 ETB
   Invoice Total: 120,000 ETB
   ```

6. **Click:** "Validate Three-Way Match"

**CASE A: PERFECT MATCH**

   **✅ Expected Result:**
   ```
   ✅ Three-Way Match Successful
   
   Validation Results:
   ├── Item Codes: ✅ Match (PO, Model 19, Invoice)
   ├── Quantities: ✅ Match (800 = 800 = 800)
   ├── Unit Price: ✅ Match (150 = 150, variance: 0%)
   └── Open DSR: ✅ None
   
   Status: Ready for Payment Approval
   Next: [Approve Payment]
   ```

**CASE B: QUANTITY MISMATCH**

5B. **Invoice has different quantity:**
   ```
   Invoice Quantity: 850 reams [MORE than Model 19]
   ```

   **✅ Expected Result:**
   ```
   ❌ Three-Way Match Failed - Quantity Mismatch
   
   Details:
   ├── PO Quantity: 800 reams
   ├── Model 19 Quantity: 800 reams [actually received]
   ├── Invoice Quantity: 850 reams ⚠️
   └── Discrepancy: +50 reams over-invoiced
   
   Action: Payment BLOCKED
   Reason: "Invoice quantity exceeds received quantity. Contact supplier for correction."
   ```

**CASE C: PRICE VARIANCE (Within Tolerance)**

5C. **Invoice price slightly different:**
   ```
   Invoice Unit Price: 152 ETB [+2 ETB = 1.33% variance]
   Tolerance Setting: 2% [from company settings]
   ```

   **✅ Expected Result:**
   ```
   ⚠️ Three-Way Match - Price Variance (Within Tolerance)
   
   Details:
   ├── PO Price: 150 ETB
   ├── Invoice Price: 152 ETB
   ├── Variance: 1.33% [within 2% tolerance]
   └── Total Difference: 1,600 ETB
   
   Status: Match Successful with Variance Note
   Approval: Requires PAO authorization for variance
   ```

**CASE D: OPEN DSR BLOCKS PAYMENT**

5D. **DSR exists for this PO:**

   **✅ Expected Result:**
   ```
   ❌ Payment BLOCKED - Open DSR
   
   Reason: DSR-2026-001 is pending closure
   Details: 50 reams rejected, awaiting replacement
   
   Action Required:
   1. Wait for DSR closure (replacement received)
   2. OR Request PAO override with justification
   
   Current Status: Cannot process payment until DSR resolved
   ```

---

### **STEP 2: Liquidated Damages Calculation (AUTO-030)**

**Who:** Accounts Unit  
**When:** Delivery was late

#### **📋 BEFORE AUTOMATION:**

**The Old Way:**
1. Accounts clerk checks delivery dates:
   - Contract: "Delivery by August 22, 2026"
   - Model 19: "Received August 30, 2026"
2. **Uses calendar** to count delay: "22... 23... 30... that's 8 days"
3. **But wait:** Must exclude weekends!
   - August 24-25 (Sat-Sun) = 2 days
   - Actual working days: 8 - 2 = 6 days (or is it 7? Confusion!)
4. **Opens contract** to find penalty rate: "1/1000 per day"
5. **Uses calculator:**
   - 120,000 × 0.001 × 6 = 720 ETB
   - Wait, is it 6 or 7 or 8 days? Recalculates...
   - 120,000 × 0.001 × 8 = 960 ETB
6. **Checks** if cap exceeded: "10% of 120,000 = 12,000 ETB... 960 is below, OK"
7. **Manually deducts** from payment
8. **Types** explanation memo

**Real Mistakes:**
```
Clerk A calculates: 6 working days = 720 ETB LD
Clerk B verifies: 8 calendar days = 960 ETB LD

Who's right? Argument ensues.
Check contract: "working days" means exclude weekends
Recount: 8 total - 2 weekend = 6 working days

But then: "Did we exclude public holidays?"
[More confusion, more time wasted]
```

**Problems:**
- ❌ Manual date counting (errors)
- ❌ Confusion: Working days vs calendar days
- ❌ Calculator mistakes
- ❌ Forget to check 10% cap
- ❌ Inconsistent LD application

#### **✨ WITH AUTOMATION:**

**Benefits:**
- ✅ Auto-calculate delay (working days, excluding weekends/holidays)
- ✅ Auto-apply correct formula (1/1000 per working day)
- ✅ Auto-check 10% cap
- ✅ Auto-deduct from payment
- ✅ Generate calculation worksheet for transparency
- ✅ Zero errors

---

#### **Actions:**

1. **In Invoice Validation Screen:**

2. **System Checks Delivery Date:**
   ```
   Contract Delivery Date: August 22, 2026
   Actual Delivery Date (Model 19): August 30, 2026
   Delay: 8 working days [excludes weekends]
   ```

3. **Auto-Calculate Liquidated Damages:**
   ```
   Contract Value: 120,000 ETB
   Penalty Rate: 1/1000 per working day [from contract]
   Delay Days: 8 working days
   
   LD Calculation:
   = 120,000 × (1/1000) × 8
   = 120,000 × 0.001 × 8
   = 960 ETB
   
   LD Cap: 10% of contract = 12,000 ETB
   Actual LD: 960 ETB [below cap ✓]
   ```

4. **Payment Adjustment:**
   ```
   Invoice Amount: 120,000 ETB
   Less: Liquidated Damages: (960 ETB)
   Net Payment: 119,040 ETB
   ```

5. **Generate Payment Certificate:**

   **✅ Expected Result:**
   ```
   Payment Certificate: PC-2026-001
   
   Supplier: ABC Trading PLC
   Invoice: INV-ABC-2026-001
   Gross Amount: 120,000 ETB
   Deductions:
   ├── Liquidated Damages: (960 ETB)
   ├── Retention (10%): (12,000 ETB)
   └── Tax Withholding (2%): (2,400 ETB)
   
   Net Payable: 104,640 ETB
   
   Calculation Worksheet: [View PDF]
   Approval Status: Pending PAO
   ```

---

### **STEP 3: Payment Approval**

**Who:** PAO  
**When:** Payment certificate generated

#### **Actions:**

1. **Login** as PAO

2. **Navigate:** Accounting → **Pending Payment Approvals**

3. **Open:** PC-2026-001

4. **Review:**
   - Three-way match status: ✅ Validated
   - LD calculation: ✅ Correct (960 ETB deducted)
   - Retention: ✅ Applied (12,000 ETB held)
   - Supporting documents: PO, Model 19, Invoice [all attached]

5. **Approve:**
   - Click "Approve Payment"
   - Digital signature: [PIN or biometric]

   **✅ Expected Result:**
   ```
   ✓ Payment approved
   ✓ Sent to bank for processing
   ✓ Supplier notified: "Payment PC-2026-001 approved - ETA 3 days"
   ✓ Retention balance updated: 12,000 ETB held
   ```

---



### **STEP 4: RFQ Three-Quotation Rule (AUTO-013)**

**Who:** SPO (awarding contract)  
**When:** After bid submission deadline

#### **📋 BEFORE AUTOMATION:**

**The Old Way:**
1. SPO manually counts quotations received: "1... 2... only 2 quotations"
2. **Knows** rule requires minimum 3 for RFQ
3. **Dilemma:** Award with 2 quotations OR re-advertise (delays project)
4. Awards anyway, hoping no one notices
5. **Audit review:** "RFQ awarded with only 2 quotations - violation of FR-PROC-016"
6. **Or:** Writes justification on paper, files somewhere, hope it's enough

**Problems:**
- ❌ Manual counting (can miss quotations)
- ❌ Rule violations (awards made with insufficient quotations)
- ❌ Inconsistent justification documentation
- ❌ Audit findings

#### **✨ WITH AUTOMATION:**

**Benefits:**
- ✅ System auto-counts valid quotations
- ✅ Blocks award if < 3 quotations
- ✅ Forces structured justification with PAO approval
- ✅ Audit trail of override
- ✅ Compliance with FR-PROC-016

---

#### **Actions:**

1. **Navigate:** Procurement → Tenders → **TND-2026-001**

2. **Check Submissions:**
   ```
   Valid Bids Received: 2
   - ABC Trading PLC: 115,000 ETB
   - XYZ Suppliers: 118,000 ETB
   ```

3. **Try to Award:**
   - Click "Award Contract" button
   - Select winner: ABC Trading PLC

   **✅ Expected:**
   - System blocks: "Cannot award - Minimum 3 quotations required for RFQ (FR-PROC-016)"
   - Shows: "Current quotations: 2 | Required: 3"

4. **Provide Justification (PAO Override):**
   - Dialog appears: "Override Reason Required"
   - Type: "Only 2 qualified suppliers available in market for this item"
   - Upload: Market research document
   - Click "Confirm Override"

   **✅ Expected:**
   - System allows award WITH documented justification
   - Logs override in audit trail with PAO signature

---


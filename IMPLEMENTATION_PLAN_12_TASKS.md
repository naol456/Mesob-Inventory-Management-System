# Implementation Plan: 12 Automation Tasks

**Priority-Based Sequential Implementation**  
**Date:** June 19, 2026  
**Status:** Ready for Implementation

---

## 🔴 HIGH PRIORITY (Critical - Enforce SRS, Prevent Violations)

### Task 1: AUTO-046 - Gate Pass Prerequisite Validation
**Priority:** CRITICAL  
**Effort:** Medium (2-3 days)  
**Dependencies:** None  
**Impact:** Prevents FR-DISP-003 violations - unauthorized dispatch

**Implementation:**
- Modify `mesob_gate_pass.py` model
- Add `@api.constrains` validation before create/write
- Check for signed Model 22 OR PAO authorization
- Validate materials match Model 22 items
- Add override mechanism for PAO emergencies

**Files to modify:**
- `models/mesob_gate_pass.py`
- `views/mesob_gate_pass_views.xml` (add warning messages)

---

### Task 2: AUTO-050 - Stock Movement Posting Approval Workflow
**Priority:** CRITICAL  
**Effort:** Medium (2-3 days)  
**Dependencies:** None  
**Impact:** Prevents unauthorized stock adjustments (fraud prevention)

**Implementation:**
- Modify `mesob_stock_movement_mixin.py`
- Add approval workflow for manual adjustments
- Require PAO approval before posting non-transaction movements
- Log reason, supporting document, approver, timestamp
- Auto-approve Model 19/22 triggered movements

**Files to modify:**
- `models/mesob_stock_movement_mixin.py`
- `models/mesob_bin_card.py`
- `models/mesob_stock_record_card.py`
- Add wizard: `wizard/mesob_manual_adjustment_wizard.py`

**Status:** Document says "complete" - needs verification and testing

---

### Task 3: AUTO-022 - Auto-PO Generation from Approved Lot
**Priority:** HIGH  
**Effort:** Small (1-2 days)  
**Dependencies:** None  
**Impact:** Reduces FR-PROC-026 transcription errors, completes TODO

**Implementation:**
- Complete existing TODO in `mesob_auto_po_generator.py`
- Generate draft PO from approved procurement lot
- Pre-fill: item codes, quantities, unit prices, delivery location
- Add officer review and approval step
- Ensure PAO approval workflow unchanged

**Files to modify:**
- `models/mesob_auto_po_generator.py` (complete TODO)
- `models/mesob_procurement.py` (add action button)
- `views/mesob_procurement_views.xml` (add "Generate PO" button)

---

## 🟡 MEDIUM PRIORITY (Improve Efficiency, Low Risk)

### Task 4: AUTO-038 - Duplicate Item Detection (Keyword Matching)
**Priority:** MEDIUM  
**Effort:** Medium (2-3 days)  
**Dependencies:** None  
**Impact:** Improves BR-ID-001 compliance, better data quality

**Implementation:**
- Add duplicate detection on item create
- Search by classification + keyword matching in description
- Show similar items alert
- User confirms to use existing or create new
- Add "merge items" utility for existing duplicates

**Files to modify:**
- `models/mesob_inventory_item.py` (add `@api.model_create_multi` check)
- `wizard/mesob_duplicate_item_wizard.py` (new)
- `views/mesob_inventory_item_views.xml` (add wizard)

---

### Task 5: AUTO-047 - Gate Pass Three-Copy Auto-Distribution
**Priority:** MEDIUM  
**Effort:** Medium (2-3 days)  
**Dependencies:** Task 1 (AUTO-046)  
**Impact:** Implements FR-DISP-004 distribution requirement

**Implementation:**
- Auto-distribute Gate Pass copies on approval
- Original → PDF with QR code for receiver
- Duplicate → notify Storekeeper
- Triplicate → notify Security Officer with gate alert
- Add QR code generation library
- Security scans QR to confirm dispatch and timestamp

**Files to modify:**
- `models/mesob_gate_pass.py` (add distribution logic)
- `reports/mesob_gate_pass_report.xml` (add QR code)
- Add QR library to requirements: `python-qrcode`

---

### Task 6: AUTO-054 - Quarterly Movement Report with Dead-Stock Flagging
**Priority:** MEDIUM  
**Effort:** Medium (2-3 days)  
**Dependencies:** None  
**Impact:** Implements FR-REP-002, identifies disposal candidates

**Implementation:**
- Create automated quarterly report generator
- Calculate: Opening | Receipts | Issues | Closing | Movement frequency
- Flag dead stock (0 issues in 12 months)
- Flag slow-moving (issues < 25% avg consumption)
- Flag dormant (no movement in 6 months)
- Recommend disposal review per Section 4.11

**Files to create:**
- `wizard/mesob_quarterly_movement_report_wizard.py`
- `wizard/mesob_quarterly_movement_report_wizard_views.xml`
- `reports/mesob_quarterly_movement_report.xml`

---

### Task 7: Push Notification System
**Priority:** MEDIUM  
**Effort:** Large (3-5 days)  
**Dependencies:** None  
**Impact:** Speeds up all approval workflows

**Implementation:**
- In-app notification center
- Real-time alerts for pending approvals
- Configurable notification preferences per user
- Alert types:
  - Pending requisition approvals (PAO)
  - Pending PO approvals (HOPE)
  - Stock reorder alerts (Procurement)
  - Gate Pass pending (Security)
  - Overdue POs (Procurement Officer)
- Optional email/SMS integration (future phase)

**Files to create:**
- `models/mesob_notification.py`
- `models/mesob_notification_preference.py`
- `views/mesob_notification_views.xml`
- Modify all approval models to trigger notifications

---

## 🟢 LOW PRIORITY (Nice-to-Have Enhancements)

### Task 8: AUTO-048 - Gate Pass Expiry Alert
**Priority:** LOW  
**Effort:** Small (1 day)  
**Dependencies:** Task 1 (AUTO-046), Task 5 (AUTO-047)  
**Impact:** Adds security beyond SRS

**Implementation:**
- Set validity period on Gate Pass (configurable, default 24 hours)
- Add `expiry_datetime` field
- Alert security if expired Gate Pass scanned
- Require PAO re-authorization to extend
- Auto-expire passes and block usage

**Files to modify:**
- `models/mesob_gate_pass.py` (add expiry logic)
- `views/mesob_gate_pass_views.xml` (show expiry warning)

---

### Task 9: Barcode/QR Code Integration
**Priority:** LOW  
**Effort:** Large (4-5 days)  
**Dependencies:** Task 5 (AUTO-047 for Gate Pass QR)  
**Impact:** Efficiency boost for receiving, dispatch, stock-taking

**Implementation:**
- Add QR codes to:
  - Items (item_code as QR)
  - Requisitions (requisition number)
  - Gate Passes (already in Task 5)
  - Bin Cards (location + item)
- Mobile scanning interface
- Auto-populate forms from QR scan
- Link physical items to digital records

**Files to modify:**
- `models/mesob_inventory_item.py` (add QR generation)
- `models/mesob_inventory_requisition.py`
- `reports/` (add QR to all printable reports)
- Add scanning wizard: `wizard/mesob_barcode_scanner_wizard.py`

---

### Task 10: Mobile Access for Field Operations
**Priority:** LOW  
**Effort:** Very Large (1-2 weeks)  
**Dependencies:** Task 9 (Barcode/QR)  
**Impact:** Enables field operations

**Implementation:**
- Mobile-responsive UI for key workflows
- Offline-capable for poor connectivity
- GPS tagging for location verification
- Mobile workflows:
  - Receiving inspection (scan QR, check items)
  - Gate Pass scanning at gate
  - Stock-taking counts
- Security features:
  - Device encryption requirement
  - Remote wipe capability
  - Session timeouts (15 min)
  - Biometric authentication

**Technology:**
- Use Odoo mobile framework (responsive web)
- OR build native mobile app (Flutter/React Native)
- Implement OAuth2 for mobile authentication

**Files to create:**
- `controllers/mobile_api.py` (REST API for mobile)
- Mobile-specific views (responsive templates)

---

### Task 11: Digital Signature Enhancement
**Priority:** LOW  
**Effort:** Medium (2-3 days)  
**Dependencies:** None  
**Impact:** Legal/audit enhancement, strengthens NFR-SEC-002

**Implementation:**
- Add cryptographic digital signatures to critical documents:
  - Requisitions (PAO approval)
  - Gate Passes (PAO authorization)
  - Stock adjustments (PAO approval)
  - POs (HOPE approval)
- Timestamp + signer identity verification
- Audit trail showing who signed when
- Compliance with Ethiopia Proclamation No. 1072/2018 (e-signature law)

**Requirements:**
- Integrate with Ethiopian PKI (if available)
- OR use qualified certificate provider
- Add signature verification on document view

**Files to create:**
- `models/mesob_digital_signature.py`
- `wizard/mesob_digital_signature_wizard.py`
- Add signature verification library

---

### Task 12: Dashboard Polish & Analytics
**Priority:** LOW  
**Effort:** Medium (2-3 days)  
**Dependencies:** All tasks (uses data from all modules)  
**Impact:** Better UI/UX, management visibility

**Implementation:**
- Enhanced dashboards per role:
  - **PAO Dashboard:**
    - Pending approvals count
    - Budget utilization vs. APP allocation
    - Stock value by classification
    - Overdue POs count
  - **Storekeeper Dashboard:**
    - Stock levels (reorder alerts)
    - Pending receipts
    - Pending issues
  - **Procurement Dashboard:**
    - Open POs status
    - Supplier performance scores
    - Contract expiry alerts
- KPI trends:
  - Stock accuracy %
  - PO delivery on-time %
  - Requisition approval cycle time
  - Dead stock value
- Drill-down to transaction details
- Export to Excel/PDF

**Files to modify:**
- `views/mesob_inventory_dashboard_views.xml` (enhance existing)
- `models/mesob_dashboard_kpi.py` (new - calculate KPIs)
- Add charts: Use Odoo web graph/pivot widgets

---

## 📊 IMPLEMENTATION SCHEDULE

### **Phase 1: HIGH PRIORITY (Week 1-2)**
- Day 1-3: Task 1 (AUTO-046 Gate Pass Validation)
- Day 4-6: Task 2 (AUTO-050 Stock Movement Approval)
- Day 7-9: Task 3 (AUTO-022 Auto-PO Generation)

**Milestone 1:** Critical security and compliance tasks complete

---

### **Phase 2: MEDIUM PRIORITY (Week 3-5)**
- Week 3 Day 1-3: Task 4 (AUTO-038 Duplicate Detection)
- Week 3 Day 4-6: Task 5 (AUTO-047 Gate Pass Distribution)
- Week 4 Day 1-3: Task 6 (AUTO-054 Quarterly Reports)
- Week 4 Day 4-6 + Week 5 Day 1-2: Task 7 (Push Notifications)

**Milestone 2:** Efficiency improvements complete

---

### **Phase 3: LOW PRIORITY (Week 6-9)**
- Week 6 Day 1: Task 8 (AUTO-048 Gate Pass Expiry)
- Week 6 Day 2-6: Task 9 (Barcode/QR Integration)
- Week 7-8: Task 10 (Mobile Access)
- Week 9 Day 1-3: Task 11 (Digital Signatures)
- Week 9 Day 4-6: Task 12 (Dashboard Polish)

**Milestone 3:** All enhancements complete

---

## 🎯 SUCCESS CRITERIA

### Task 1 (AUTO-046) Success:
- ✅ Cannot create Gate Pass without Model 22 or PAO authorization
- ✅ Materials validation prevents mismatched items
- ✅ PAO override mechanism works with justification logging

### Task 2 (AUTO-050) Success:
- ✅ Manual adjustments blocked until PAO approves
- ✅ Adjustment reason and document captured
- ✅ Model 19/22 movements auto-post without approval
- ✅ Audit trail shows all adjustments with approver

### Task 3 (AUTO-022) Success:
- ✅ PO generation button appears on approved lots
- ✅ Generated PO pre-fills all fields from lot/bid
- ✅ Officer can edit before submission
- ✅ PAO approval workflow unchanged
- ✅ TODO comments removed, code documented

---

## 🚀 NEXT STEPS

1. **Create feature branch:** `feature/12-automation-tasks`
2. **Start with Task 1 (AUTO-046)** - Gate Pass Prerequisite Validation
3. **Test each task thoroughly** before moving to next
4. **Commit after each task** completion with descriptive message
5. **Upgrade module and test** with different user roles
6. **Document any deviations** from plan in commit messages

---

**Ready to implement? Confirm to start with Task 1 (AUTO-046).**

# Mesob IMS Automation Calculation Engines
## Phase 3: Lelisa's Intelligent Automation Features

**Version:** 1.0  
**Developer:** Lelisa  
**Date:** June 2026  
**Branch:** `feature/lelisa-automation-calculations`

---

## Overview

This document describes 6 automation calculation engines implemented as part of the Mesob IMS intelligent automation initiative. These features transform manual calculation workflows into automated, audit-ready, and compliance-verified processes.

All features strictly adhere to:
- **FPPA Proclamation 1210/2012** (Federal Public Procurement)
- **MoFED Stock Management Manual** (May 2010)
- **Mesob IMS SRS v2.0** with Procurement (June 2026)
- **Ethiopian federal regulations and business rules**

---

## Implemented Features

### AUTO-009: Supplier Performance Scoring System
**Model:** `res.partner` (inherited)  
**Compliance:** FR-PROC-040

#### Description
Automated real-time calculation of supplier performance scores based on delivery history, quality, and complaints.

#### Key Capabilities
- **Automatic Score Calculation** from PO/delivery/DSR/complaint data
- **Component Metrics**:
  - On-Time Delivery Rate (50% weight)
  - DSR Rejection Rate (30% weight, inverted)
  - Complaint Count (20% weight, inverted)
- **Performance Rating Bands**:
  - Excellent: 90-100
  - Good: 75-89
  - Satisfactory: 60-74
  - Poor: 0-59
- **Blacklist Auto-Disqualification**: Score = 0 if supplier blacklisted
- **Manual Refresh Button** for on-demand recalculation
- **Detailed Performance Reports** per supplier

#### Technical Details
```python
# Score Formula
on_time_score = on_time_rate * 0.50
dsr_score = (100 - dsr_rate) * 0.30
complaint_score = complaint_penalty * 0.20
total_score = on_time_score + dsr_score + complaint_score
```

#### Integration Points
- Feeds bid evaluation scoring (FR-PROC-017)
- Supplier qualification decisions (FR-PROC-010)
- Supplier Performance Report (FR-PROC-040)

---

### AUTO-015: Domestic Preference Calculation Engine
**Models:** `mesob.domestic.preference.calculation`, `mesob.domestic.preference.calculation.line`  
**Compliance:** FR-PROC-018, BR-PROC-003, FPPA Article 27(4)

#### Description
Automated Ethiopian domestic preference calculation for procurement bid evaluation per FPPA Proclamation 1210/2012 Article 27(4).

#### Key Capabilities
- **Automatic Preference Calculation**:
  - ≥70% local content → 13.5% preference
  - 40-70% local content → 11% preference
  - <40% local content → 0% preference
- **Dual Pricing**:
  - **Evaluated Price** = Bid Price - Preference Amount (for ranking only)
  - **Contract Price** = Original Bid Price (BR-PROC-003 compliance)
- **Automatic Ranking** by evaluated price
- **Award Recommendation** generation
- **Audit-Ready Calculation Worksheet** with full transparency
- **Validation Workflow**: Draft → Calculated → Validated

#### Technical Details
```python
# Preference Calculation
if local_content >= 70%:
    preference_pct = 13.5%
elif local_content >= 40%:
    preference_pct = 11.0%
else:
    preference_pct = 0%

evaluated_price = bid_price × (1 - preference_pct)
# Contract uses bid_price, NOT evaluated_price!
```

#### Integration Points
- Bid evaluation workflow (FR-PROC-017)
- Evaluation report generation (FR-PROC-019)
- Contract formation (FR-PROC-021)

---

### AUTO-030: Liquidated Damages Auto-Calculation
**Model:** `mesob.liquidated.damages.calculation`  
**Compliance:** FR-PROC-036

#### Description
Automated calculation of liquidated damages for late delivery with working-day precision and contract-defined penalty caps.

#### Key Capabilities
- **Automatic Delay Calculation**: Working days or calendar days
- **Standard Formula**: Contract Value × 1/1000 × Delay Days
- **Penalty Cap**: Typically 10% of contract value (configurable)
- **Three-Way Approval**: Draft → Calculated → Approved → Deducted
- **Payment Integration**: Auto-deduction from payment certificates
- **Detailed Breakdown**: Transparent calculation for audit

#### Technical Details
```python
# LD Calculation
delay_days = count_working_days(contract_date, actual_date)
ld_uncapped = contract_value × penalty_rate × delay_days
ld_capped = min(ld_uncapped, contract_value × max_penalty_pct)
net_payable = contract_value - ld_capped
```

**Default Parameters:**
- Penalty Rate: 0.001 (1/1000 per day)
- Max Penalty: 10% of contract value
- Working Days: Monday-Friday (weekends excluded)

#### Integration Points
- Contract delivery milestone tracking (FR-PROC-024)
- Payment certificate processing (FR-PROC-034)
- Supplier performance scoring (AUTO-009)

---

### AUTO-031: Price Adjustment Calculation Engine
**Model:** `mesob.price.adjustment.calculation`  
**Compliance:** FR-PROC-035, BR-PROC-007

#### Description
Automated price adjustment calculation for adjustable-price contracts using weighted index formulas. **Financial adjustment only** - does NOT affect FIFO stock costs (BR-PROC-007).

#### Key Capabilities
- **Index-Based Formula**: Labor + Material + Fixed components
- **Weighted Adjustment**:
  ```
  Overall Factor = (Labor Weight × L/L0) + (Material Weight × M/M0) + Fixed Weight
  Adjusted Value = Base Contract Value × Overall Factor
  ```
- **BR-PROC-007 Compliance**: Original PO price remains FIFO cost basis
- **Approval Workflow**: Draft → Calculated → Approved → Applied
- **Payment Certificate Integration**
- **Comprehensive Calculation Worksheet**

#### Technical Details
```python
# Example Formula: 30% Labor, 40% Material, 30% Fixed
labor_factor = current_labor_index / base_labor_index
material_factor = current_material_index / base_material_index

overall_factor = (0.30 × labor_factor) + (0.40 × material_factor) + 0.30
adjusted_value = base_value × overall_factor
adjustment_amount = adjusted_value - base_value
```

**Important:** Price adjustments apply to **payment only**, never to stock valuation!

#### Integration Points
- Contract price provisions (FR-PROC-021)
- Payment certificate processing (FR-PROC-035)
- Financial reporting (NOT stock valuation per BR-PROC-007)

---

### AUTO-035: Procurement-to-Stock Reconciliation Report
**Models:** `mesob.procurement.stock.reconciliation`, `mesob.procurement.stock.reconciliation.line`  
**Compliance:** FR-PROC-042

#### Description
Automated monthly reconciliation matching the complete procurement-to-stock flow: PO → Model 19 → Bin Card → Stock Record Card → Payment.

#### Key Capabilities
- **Five-Way Data Matching**:
  1. PO Quantity & Unit Cost
  2. Model 19 Received Quantity
  3. Bin Card Debit
  4. Stock Record Card Debit & Unit Cost
  5. Payment Quantity & Amount
- **Gap Detection**:
  - Quantity Gaps: PO ≠ Received OR Received ≠ Stocked
  - Cost Gaps: PO Unit Cost ≠ Stock Record Unit Cost
  - Payment Gaps: Paid Quantity ≠ Received Quantity
- **Reconciliation Rate**: (Fully Reconciled / Total POs) × 100%
- **Top 50 Discrepancies** for PAO investigation
- **Monthly Auto-Generation** for early fraud/error detection

#### Technical Details
```python
# Gap Detection (tolerance: 0.01 qty, 1.0 ETB)
quantity_gap = abs(po_qty - model19_qty) > 0.01 OR
               abs(model19_qty - stock_record_qty) > 0.01

cost_gap = abs(po_unit_cost - stock_record_unit_cost) > 1.0

payment_gap = abs(model19_qty - payment_qty) > 0.01

fully_reconciled = NOT (quantity_gap OR cost_gap OR payment_gap)
```

**Rating Thresholds:**
- Excellent: ≥95% reconciliation rate
- Good: 85-95%
- Needs Attention: <85%

#### Integration Points
- All procurement documents (FR-PROC-026 through FR-PROC-034)
- Stock records (FR-RECARD-001, FR-RECARD-002)
- Discrepancy investigation (FR-ST-006, FR-ST-007)

---

### AUTO-055: Stock Accuracy Scorecard
**Models:** `mesob.stock.accuracy.scorecard`, `mesob.stock.accuracy.scorecard.line`  
**Compliance:** FR-REP-003

#### Description
Monthly stock accuracy monitoring with visual scorecard, trend analysis, and continuous improvement tracking.

#### Key Capabilities
- **Accuracy Score**: (Items Accurate / Total Items) × 100%
- **Rating Bands**:
  - Excellent: ≥98%
  - Good: 95-98%
  - Fair: 90-95%
  - Poor: <90%
- **Trend Analysis**: Month-over-month comparison (Improving/Stable/Declining)
- **Variance Analysis**:
  - Total variance quantity and value
  - Top 10 items with largest variance
- **Visual Scorecard**: Color-coded metrics with large score display
- **Monthly Auto-Generation** from stock taking results

#### Technical Details
```python
# Accuracy Calculation
items_accurate = count(items with variance == 0)
total_items = count(all items counted)
accuracy_score = (items_accurate / total_items) × 100

# Trend Analysis
trend_change = current_month_score - previous_month_score
if trend_change >= +2%: trend = 'Improving'
elif trend_change <= -2%: trend = 'Declining'
else: trend = 'Stable'
```

**Target:** ≥98% accuracy (Excellent rating)

#### Integration Points
- Stock taking workflow (Section 4.8)
- Discrepancy investigation (FR-ST-006, FR-ST-007)
- Process improvement initiatives (FR-REP-003)

---

## Common Design Patterns

All 6 automation engines follow consistent professional patterns:

### 1. State-Based Workflows
```
Draft → Calculated → Approved/Reviewed
```
Each transition is logged with user, timestamp, and reason.

### 2. Computed Fields with `store=True`
All calculations use `@api.depends` decorators and store results for performance.

### 3. Rich HTML Reports
Every calculation generates a comprehensive HTML report with:
- Color-coded metrics
- Detailed breakdown tables
- Compliance notes
- Audit trail references

### 4. Validation Constraints
- `@api.constrains` for business rule enforcement
- User-friendly error messages
- Prevents invalid data entry

### 5. Audit Trail
- All calculations logged with `_logger.info()`
- User/timestamp tracking on all state changes
- Message posting for major events

### 6. Action Buttons
- `action_calculate()`: Trigger calculation
- `action_approve()`: Approve results
- `action_refresh()`: Manual refresh
- All return user notifications

---

## Database Schema

### New Models Created
1. `mesob.domestic.preference.calculation`
2. `mesob.domestic.preference.calculation.line`
3. `mesob.liquidated.damages.calculation`
4. `mesob.price.adjustment.calculation`
5. `mesob.procurement.stock.reconciliation`
6. `mesob.procurement.stock.reconciliation.line`
7. `mesob.stock.accuracy.scorecard`
8. `mesob.stock.accuracy.scorecard.line`

### Enhanced Models
- `res.partner`: Added supplier performance fields and scoring logic

### Sequence Definitions
- `mesob.domestic.preference.calc`: DP/YYYY/####
- `mesob.liquidated.damages`: LD/YYYY/####
- `mesob.price.adjustment`: PA/YYYY/####
- `mesob.procurement.stock.recon`: PSR/YYYY/####
- (Stock Accuracy Scorecard uses period-based format: SAS/YYYY/MM)

---

## Installation & Setup

### Prerequisites
- Odoo 19.0
- Mesob Inventory Base module installed
- Python 3.10+

### Installation Steps

1. **Merge Feature Branch**
```bash
git checkout develop
git merge feature/lelisa-automation-calculations
```

2. **Update Module**
```bash
# Restart Odoo server
# Navigate to Apps → Mesob Inventory Management System → Upgrade
```

3. **Verify Installation**
- Check Models: Settings → Technical → Models
  - Search for "domestic preference", "liquidated damages", etc.
- Check Sequences: Settings → Technical → Sequences
  - Verify DP, LD, PA, PSR sequences exist

### Access Control
All new models inherit security rules from existing Mesob roles:
- **PAO**: Full access (approve/review)
- **Procurement Officer**: Calculate and submit
- **Stock Clerk**: Read-only for reconciliation
- **Finance/Accounts**: Payment integration access

---

## Usage Examples

### Example 1: Domestic Preference Calculation
```python
# 1. Create calculation for a tender
calc = env['mesob.domestic.preference.calculation'].create({
    'tender_ref': 'TDR/2026/001',
    'lot_id': lot.id,
})

# 2. Add bidders
calc.calculation_line_ids.create({
    'calculation_id': calc.id,
    'bidder_name': 'ABC Trading PLC',
    'local_content_percentage': 75.0,  # ≥70% → 13.5% preference
    'bid_price': 1000000.0,
})

# 3. Calculate and rank
calc.action_calculate()
# Result: evaluated_price = 865,000 ETB (1M × 86.5%)
# Contract price = 1,000,000 ETB (original)

# 4. Validate
calc.action_validate()
```

### Example 2: Liquidated Damages
```python
# 1. Create LD calculation
ld = env['mesob.liquidated.damages.calculation'].create({
    'contract_ref': 'CTR/2026/050',
    'supplier_id': supplier.id,
    'contract_value': 5000000.0,
    'contract_delivery_date': '2026-05-01',
    'actual_delivery_date': '2026-05-15',  # 10 working days late
    'penalty_rate_per_day': 0.001,  # 1/1000
    'max_penalty_percentage': 10.0,
})

# 2. Calculate
ld.action_calculate()
# Result: LD = 5M × 0.001 × 10 = 50,000 ETB
# Net Payable = 4,950,000 ETB

# 3. Approve and apply
ld.action_approve()
ld.action_apply_deduction()
```

### Example 3: Stock Accuracy Scorecard
```python
# 1. Create monthly scorecard
scorecard = env['mesob.stock.accuracy.scorecard'].create({
    'period_month': '6',  # June
    'period_year': '2026',
})

# 2. Calculate from stock taking results
scorecard.action_calculate_scorecard()
# Automatically queries stock taking records from June 2026
# Calculates accuracy score, trend, variance

# 3. Review by PAO
scorecard.action_pao_review()
```

---

## Testing

### Unit Test Coverage
All models include:
- Constraint validation tests
- Calculation accuracy tests
- Workflow state transition tests
- Integration point tests

### Test Files Location
```
addons/mesob_inventory_base/tests/
├── test_domestic_preference_calc.py
├── test_liquidated_damages_calc.py
├── test_price_adjustment_calc.py
├── test_procurement_stock_reconciliation.py
└── test_stock_accuracy_scorecard.py
```

### Running Tests
```bash
odoo-bin -c odoo.conf -d mesob_test \
  --test-enable \
  --stop-after-init \
  -i mesob_inventory_base
```

---

## Performance Considerations

### Computed Field Strategy
- All calculation fields use `store=True` for fast retrieval
- `@api.depends()` triggers recompute only when dependencies change
- Large reports use `compute='method'` to defer until accessed

### Query Optimization
- Reconciliation queries use date ranges and classification filters
- Bulk create operations for reconciliation lines
- Indexed fields: `po_reference`, `item_code`, `supplier_id`

### Batch Processing
- Monthly reconciliation: Process in batches of 1000 PO lines
- Stock accuracy: Process by classification to limit dataset
- Supplier performance: Update scores asynchronously

---

## Troubleshooting

### Issue: Domestic preference calculation shows 0%
**Cause:** Supplier's `local_content_percentage` not set in vendor master  
**Fix:** Update `res.partner` record with correct local content %

### Issue: LD calculation negative days
**Cause:** `actual_delivery_date < contract_delivery_date`  
**Fix:** Constraint prevents this - check date entry order

### Issue: Reconciliation shows no data
**Cause:** No completed stock takings in selected period  
**Fix:** Ensure stock taking state = 'completed' before generating report

### Issue: Stock accuracy scorecard trend = N/A
**Cause:** No previous month scorecard for comparison  
**Fix:** Generate scorecards for at least 2 consecutive months

---

## Maintenance & Support

### Logging
All calculations log to Odoo logger with prefix `AUTO-XXX:`
```python
_logger.info('AUTO-015: Domestic preference calculated for 5 bidders')
```

View logs: Settings → Technical → Database Structure → Logging

### Scheduled Actions
- **Monthly Reconciliation**: 1st of each month, 2:00 AM
- **Monthly Scorecard**: 3rd of each month, 3:00 AM
- **Supplier Score Refresh**: Weekly, Sunday 1:00 AM

Configure: Settings → Technical → Automation → Scheduled Actions

---

## Future Enhancements (Roadmap)

### Phase 4 Candidates
1. **AUTO-016**: Auto-RFQ quota generation (FR-PROC-016)
2. **AUTO-024**: Overdue PO escalation with auto-LD calculation
3. **AUTO-034**: Real-time APP execution progress dashboard
4. **AUTO-062**: Auto-control level calculation from historical usage

### Integration Wishlist
- Email notifications for calculation completion
- PDF export of calculation worksheets
- Excel export of reconciliation details
- Power BI connector for trend analysis

---

## Compliance Matrix

| Automation | SRS Requirement | FPPA/MoFED Reference | Business Rule | Status |
|------------|----------------|----------------------|---------------|--------|
| AUTO-009   | FR-PROC-040    | Proclamation 1210/2012 | -  | ✅ Complete |
| AUTO-015   | FR-PROC-018    | Article 27(4)        | BR-PROC-003 | ✅ Complete |
| AUTO-030   | FR-PROC-036    | Contract Terms       | -           | ✅ Complete |
| AUTO-031   | FR-PROC-035    | Adjustable Contracts | BR-PROC-007 | ✅ Complete |
| AUTO-035   | FR-PROC-042    | FR-ST-006/007        | -           | ✅ Complete |
| AUTO-055   | FR-REP-003     | Stock Management Manual | -        | ✅ Complete |

---

## Credits

**Developer:** Lelisa  
**Team:** Mesob IMS Development Team (Group I)  
**Organization:** FDRE Mesob Center (HQ)  
**Date:** June 2026 / Sene 2018

**Special Thanks:**
- Ethiopian Federal Procurement Agency (FPPA) for regulatory guidance
- Ministry of Finance & Economic Development (MoFED) for stock management standards
- Mesob Center leadership for vision and support

---

## License

**Copyright © 2026 MESOB Center. All rights reserved.**  
Licensed under LGPL-3 (GNU Lesser General Public License v3.0)

---

## Contact & Support

**Technical Support:** lelisa@mesob.gov.et  
**Documentation:** [Internal Mesob Wiki]  
**Bug Reports:** Mesob JIRA Project → Component: Automation Calculations

---

**End of Documentation**  
*Last Updated: June 19, 2026*

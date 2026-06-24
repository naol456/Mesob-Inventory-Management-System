# AUTO-025 & AUTO-026 Verification Checklist

## Manual Verification Steps

Use this checklist to verify AUTO-025 and AUTO-026 are working correctly in your environment.

---

## Prerequisites

- [ ] Odoo instance running with `mesob_inventory_base` module installed
- [ ] At least one user assigned to **Mesob Inventory / Storekeeper** group
- [ ] Test supplier created
- [ ] Test inventory items with proper classifications created
- [ ] Annual Procurement Plan (APP) and Lots configured

---

## Test Scenario 1: Office Supplies (Storekeeper Inspection)

### Setup
1. Create test items:
   - Item Code: `4401-001-001`
   - Name: "A4 Copy 
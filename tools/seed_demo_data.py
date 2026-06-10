# -*- coding: utf-8 -*-
# Python Data-Seeding Script for GraceDB
# Execute via:
# & "C:\Program Files\Odoo 19.0.20260218\python\python.exe" "C:\Program Files\Odoo 19.0.20260218\server\odoo-bin" -c "C:\Program Files\Odoo 19.0.20260218\server\odoo.conf" -d GraceDB shell --no-html --stop-after-init < tools/seed_demo_data.py

import logging
_logger = logging.getLogger('odoo.tools.seeder')

# Fetch models
partner_model = env['res.partner']
item_model = env['mesob.inventory.item']
major_model = env['mesob.inventory.major.classification']
sub_model = env['mesob.inventory.sub.classification']
uom_unit = env.ref('uom.product_uom_unit')

print("\nSTARTING FEDERAL DEMO DATA SEEDING FOR GRACEDB...")

# 1. Create supplier partners
supplier_fppa = partner_model.create({
    'name': 'Ethiopian Federal Procurement Agency (FPPA)',
    'tin': '555666777',
})
supplier_national = partner_model.create({
    'name': 'National Trade Depot',
    'tin': '888999111',
})

# 2. Create Major Classifications
classification_it = major_model.create({
    'code': '4401',
    'name': 'Information Technology Equipment',
})
classification_stationery = major_model.create({
    'code': '4402',
    'name': 'Office Stationery & Supplies',
})

# 3. Create Sub Classifications
sub_pcs = sub_model.create({
    'code': '001',
    'name': 'Computers & Laptops',
    'major_classification_id': classification_it.id,
})
sub_paper = sub_model.create({
    'code': '002',
    'name': 'Paper & Copy Supplies',
    'major_classification_id': classification_stationery.id,
})

# 4. Create Items
item_laptop = item_model.create({
    'item_code': '4401-001-001',
    'name': 'Lenovo ThinkPad Core i7',
    'classification_id': classification_it.id,
    'sub_classification_id': sub_pcs.id,
    'reorder_level': 5.0,
    'minimum_level': 2.0,
    'uom_id': uom_unit.id,
})
item_paper = item_model.create({
    'item_code': '4402-002-001',
    'name': 'Double A Copy Paper A4',
    'classification_id': classification_stationery.id,
    'sub_classification_id': sub_paper.id,
    'reorder_level': 15.0,
    'minimum_level': 5.0,
    'uom_id': uom_unit.id,
})

# 5. Create initial stock record cards to populate FIFO cost layers
card_laptop_1 = env['mesob.stock.record.card'].create({
    'item_id': item_laptop.id,
    'transaction_type': 'receipt',
    'quantity_in': 10.0,
    'unit_cost': 45000.0,
    'quantity_balance': 10.0,
    'balance_value': 450000.0,
    'uom_id': uom_unit.id,
})
card_laptop_1.action_create_fifo_layers()

card_laptop_2 = env['mesob.stock.record.card'].create({
    'item_id': item_laptop.id,
    'transaction_type': 'receipt',
    'quantity_in': 5.0,
    'unit_cost': 50000.0,
    'quantity_balance': 15.0,
    'balance_value': 700000.0,
    'uom_id': uom_unit.id,
})
card_laptop_2.action_create_fifo_layers()

# Seed paper stock
card_paper = env['mesob.stock.record.card'].create({
    'item_id': item_paper.id,
    'transaction_type': 'receipt',
    'quantity_in': 50.0,
    'unit_cost': 350.0,
    'quantity_balance': 50.0,
    'balance_value': 17500.0,
    'uom_id': uom_unit.id,
})
card_paper.action_create_fifo_layers()

# 6. Create beautiful, realistic department requisitions
req_it = env['mesob.inventory.requisition'].create({
    'issue_mode': 'imprest',
    'department': 'ministry_transport_logistics',
    'requested_by_id': env.user.id,
})
env['mesob.inventory.requisition.line'].create({
    'requisition_id': req_it.id,
    'item_id': item_laptop.id,
    'quantity': 3.0,
    'uom_id': uom_unit.id,
    'note': 'For regional GIS mapping project',
})

req_it.write({'state': 'approved'})

# 7. Create Issue Vouchers
iv_it = env['mesob.inventory.issue.voucher'].create({
    'requisition_id': req_it.id,
    'issued_by_id': env.user.id,
})
# Process lines
for line in iv_it.line_ids:
    line.qty_issued = 3.0

# 8. Create Gate Pass (Dispatch)
env['mesob.gate.pass'].create({
    'issue_voucher_id': iv_it.id,
    'destination': 'Addis Ababa Science Hub',
    'receiver_name': 'Abebe Kebede',
    'receiver_organization': 'Science Academy',
    'vehicle_plate': 'AA-3-B45672',
    'driver_name': 'Bekele Chala',
})

# 9. Trigger stock-alert checks to populate alert graphs
env['mesob.stock.reorder.alert']._cron_check_stock_levels()

# Commit changes
env.cr.commit()
print("\nSEEDING COMPLETED FLAWLESSLY! YOUR BI DASHBOARDS ARE NOW LIVE!")

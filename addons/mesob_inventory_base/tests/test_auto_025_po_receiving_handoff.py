# -*- coding: utf-8 -*-
"""
Test AUTO-025: PO-to-Receiving Handoff Notification

Verifies that when a Purchase Order is approved, the system automatically
notifies Storekeeper users with comprehensive delivery information including:
- Expected items (codes, descriptions, quantities)
- Supplier name and contact
- Expected delivery date
- Assigned inspection type
- Preparation checklist

Compliance: FR-PROC-030, FR-PROC-027, FR-REC-001
"""

from odoo.tests.common import TransactionCase
from datetime import timedelta
from odoo import fields


class TestAUTO025POReceivingHandoff(TransactionCase):
    """Test automatic PO-to-Receiving handoff notifications."""

    def setUp(self):
        super().setUp()
        
        # Get Storekeeper group
        self.storekeeper_group = self.env.ref(
            'mesob_inventory_base.group_mesob_storekeeper'
        )
        
        # Create test Storekeeper user
        self.storekeeper_user = self.env['res.users'].create({
            'name': 'Test Storekeeper',
            'login': 'test_storekeeper',
            'email': 'storekeeper@test.com',
            'groups_id': [(6, 0, [self.storekeeper_group.id])]
        })
        
        # Create test supplier
        self.supplier = self.env['res.partner'].create({
            'name': 'Test Supplier Ltd',
            'phone': '+251911234567',
            'email': 'supplier@test.com',
            'is_company': True,
            'supplier_rank': 1
        })
        
        # Create major classification (4401 - Office Supplies)
        self.major_class = self.env['mesob.inventory.major.classification'].create({
            'code': '4401',
            'name': 'Office Supplies and Materials',
        })
        
        # Create sub classification
        self.sub_class = self.env['mesob.inventory.sub.classification'].create({
            'code': '001',
            'name': 'Stationery Items',
            'major_classification_id': self.major_class.id,
            'is_fixed_asset': False
        })
        
        # Create test inventory item
        self.item = self.env['mesob.inventory.item'].create({
            'item_code': '4401-001-001',
            'name': 'A4 Copy Paper',
            'classification_id': self.major_class.id,
            'sub_classification_id': self.sub_class.id,
        })
        
        # Create Annual Procurement Plan
        self.plan = self.env['mesob.procurement.plan'].create({
            'name': 'APP 2026',
            'fiscal_year': '2026',
            'planning_type': 'annual',
            'execution_type': 'goods',
        })
        
        # Create Procurement Lot
        self.lot = self.env['mesob.procurement.plan.lot'].create({
            'plan_id': self.plan.id,
            'name': 'Office Supplies Lot',
            'sub_classification_id': self.sub_class.id,
            'procurement_mechanism': 'shopping',
            'estimated_value': 50000.0,
        })
    
    def test_auto025_notification_on_po_approval(self):
        """Test that PO approval triggers receiving handoff notification."""
        
        # Create Purchase Order
        po = self.env['mesob.procurement.order'].create({
            'supplier_id': self.supplier.id,
            'plan_lot_id': self.lot.id,
            'date_order': fields.Date.today(),
            'state': 'pending',
            'line_ids': [(0, 0, {
                'item_id': self.item.id,
                'description': 'A4 Copy Paper - 500 sheets per ream',
                'quantity': 100.0,
                'price_unit': 250.0,
            })]
        })
        
        # Track messages before approval
        messages_before = len(po.message_ids)
        
        # Approve PO (should trigger AUTO-025)
        po.action_approve()
        
        # Verify PO is approved
        self.assertEqual(po.state, 'approved', "PO should be in approved state")
        
        # Verify notification was sent (new message posted)
        messages_after = len(po.message_ids)
        self.assertGreater(
            messages_after, 
            messages_before,
            "AUTO-025: Notification message should be posted to PO"
        )
        
        # Get the latest notification message
        notification = po.message_ids[0]
        
        # Verify message content includes required elements
        self.assertIn(
            'AUTO-025',
            notification.body,
            "Message should be tagged with AUTO-025"
        )
        self.assertIn(
            'Expected Delivery Notification',
            notification.body,
            "Message should indicate it's a delivery notification"
        )
        self.assertIn(
            po.name,
            notification.body,
            "Message should include PO reference"
        )
        self.assertIn(
            self.supplier.name,
            notification.body,
            "Message should include supplier name"
        )
        self.assertIn(
            self.item.item_code,
            notification.body,
            "Message should include item code"
        )
        self.assertIn(
            'Preparation Checklist',
            notification.body,
            "Message should include preparation checklist"
        )
        
        # Verify inspection type was assigned (AUTO-026)
        self.assertIsNotNone(
            po.inspection_type,
            "AUTO-026: Inspection type should be auto-assigned"
        )
        self.assertEqual(
            po.inspection_type,
            'storekeeper',
            "Office supplies (4401) should trigger storekeeper inspection"
        )
    
    def test_auto025_notification_includes_multiple_items(self):
        """Test notification includes all items from PO."""
        
        # Create another item
        item2 = self.env['mesob.inventory.item'].create({
            'item_code': '4401-001-002',
            'name': 'Ballpoint Pens',
            'classification_id': self.major_class.id,
            'sub_classification_id': self.sub_class.id,
        })
        
        # Create PO with multiple items
        po = self.env['mesob.procurement.order'].create({
            'supplier_id': self.supplier.id,
            'plan_lot_id': self.lot.id,
            'date_order': fields.Date.today(),
            'state': 'pending',
            'line_ids': [
                (0, 0, {
                    'item_id': self.item.id,
                    'description': 'A4 Copy Paper',
                    'quantity': 100.0,
                    'price_unit': 250.0,
                }),
                (0, 0, {
                    'item_id': item2.id,
                    'description': 'Ballpoint Pens - Blue',
                    'quantity': 500.0,
                    'price_unit': 10.0,
                })
            ]
        })
        
        # Approve PO
        po.action_approve()
        
        # Get notification
        notification = po.message_ids[0]
        
        # Verify both items are in notification
        self.assertIn(
            self.item.item_code,
            notification.body,
            "First item should be in notification"
        )
        self.assertIn(
            item2.item_code,
            notification.body,
            "Second item should be in notification"
        )
        self.assertIn(
            '100',
            notification.body,
            "First item quantity should be in notification"
        )
        self.assertIn(
            '500',
            notification.body,
            "Second item quantity should be in notification"
        )
    
    def test_auto025_inspection_type_technical(self):
        """Test notification includes correct checklist for technical inspection."""
        
        # Create fuel classification (4405)
        fuel_class = self.env['mesob.inventory.major.classification'].create({
            'code': '4405',
            'name': 'Fuel and Lubricants',
        })
        
        fuel_sub = self.env['mesob.inventory.sub.classification'].create({
            'code': '001',
            'name': 'Diesel Fuel',
            'major_classification_id': fuel_class.id,
        })
        
        fuel_item = self.env['mesob.inventory.item'].create({
            'item_code': '4405-001-001',
            'name': 'Diesel Fuel',
            'classification_id': fuel_class.id,
            'sub_classification_id': fuel_sub.id,
        })
        
        # Create lot for fuel
        fuel_lot = self.env['mesob.procurement.plan.lot'].create({
            'plan_id': self.plan.id,
            'name': 'Fuel Procurement',
            'sub_classification_id': fuel_sub.id,
            'procurement_mechanism': 'shopping',
            'estimated_value': 100000.0,
        })
        
        # Create PO for fuel
        po = self.env['mesob.procurement.order'].create({
            'supplier_id': self.supplier.id,
            'plan_lot_id': fuel_lot.id,
            'date_order': fields.Date.today(),
            'state': 'pending',
            'line_ids': [(0, 0, {
                'item_id': fuel_item.id,
                'description': 'Diesel Fuel',
                'quantity': 1000.0,
                'price_unit': 45.0,
            })]
        })
        
        # Approve PO
        po.action_approve()
        
        # Verify inspection type is technical
        self.assertEqual(
            po.inspection_type,
            'technical',
            "Fuel (4405) should trigger technical inspection"
        )
        
        # Get notification
        notification = po.message_ids[0]
        
        # Verify technical checklist items are present
        self.assertIn(
            'technical staff',
            notification.body.lower(),
            "Notification should mention technical staff for fuel inspection"
        )
        self.assertIn(
            'specialized testing',
            notification.body.lower(),
            "Notification should mention specialized testing"
        )
    
    def test_auto025_expected_delivery_date_calculation(self):
        """Test that expected delivery date is calculated (PO date + 30 days)."""
        
        po_date = fields.Date.today()
        expected_date = po_date + timedelta(days=30)
        
        # Create PO
        po = self.env['mesob.procurement.order'].create({
            'supplier_id': self.supplier.id,
            'plan_lot_id': self.lot.id,
            'date_order': po_date,
            'state': 'pending',
            'line_ids': [(0, 0, {
                'item_id': self.item.id,
                'description': 'Test Item',
                'quantity': 50.0,
                'price_unit': 100.0,
            })]
        })
        
        # Approve PO
        po.action_approve()
        
        # Get notification
        notification = po.message_ids[0]
        
        # Verify expected delivery date is mentioned
        self.assertIn(
            str(expected_date),
            notification.body,
            "Notification should include calculated expected delivery date"
        )
    
    def test_receiving_integration_po_details_exposure(self):
        """Test that Receiving module can see PO details (FR-PROC-030)."""
        
        # Create and approve PO
        po = self.env['mesob.procurement.order'].create({
            'supplier_id': self.supplier.id,
            'plan_lot_id': self.lot.id,
            'date_order': fields.Date.today(),
            'state': 'pending',
            'line_ids': [(0, 0, {
                'item_id': self.item.id,
                'description': 'A4 Paper',
                'quantity': 100.0,
                'price_unit': 250.0,
            })]
        })
        po.action_approve()
        
        # Create Receiving record linked to PO
        receiving = self.env['mesob.inventory.receiving'].create({
            'source_type': 'supplier',
            'purchase_order_ref': po.name,
        })
        
        # Verify PO details are exposed to Receiving
        self.assertEqual(
            receiving.supplier_id.id,
            self.supplier.id,
            "Receiving should see supplier from PO"
        )
        self.assertEqual(
            receiving.inspection_type,
            po.inspection_type,
            "Receiving should see inspection type from PO (FR-PROC-031)"
        )
        self.assertEqual(
            len(receiving.line_ids),
            len(po.line_ids),
            "Receiving should see all PO line items"
        )
        
        # Verify receiving line details match PO
        receiving_line = receiving.line_ids[0]
        po_line = po.line_ids[0]
        
        self.assertEqual(
            receiving_line.item_id.id,
            po_line.item_id.id,
            "Receiving line should match PO item"
        )
        self.assertEqual(
            receiving_line.qty_expected,
            po_line.quantity,
            "Receiving line should show expected quantity from PO"
        )
        self.assertEqual(
            receiving_line.unit_price,
            po_line.price_unit,
            "Receiving line should show unit price from PO for FIFO costing"
        )

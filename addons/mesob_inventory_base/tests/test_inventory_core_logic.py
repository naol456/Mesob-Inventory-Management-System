from odoo.tests.common import TransactionCase
from odoo.exceptions import ValidationError
from odoo import fields


class TestMesobInventoryCoreLogic(TransactionCase):
    """Automated Functional Audit Tests for Mesob Core Inventory & FIFO Valuation"""

    def setUp(self):
        super(TestMesobInventoryCoreLogic, self).setUp()
        self.item_model = self.env["mesob.inventory.item"]
        self.requisition_model = self.env["mesob.inventory.requisition"]
        self.receiving_model = self.env["mesob.inventory.receiving"]
        self.issue_voucher_model = self.env["mesob.inventory.issue.voucher"]
        self.gate_pass_model = self.env["mesob.gate.pass"]
        self.alert_model = self.env["mesob.stock.reorder.alert"]
        self.stock_card_model = self.env["mesob.stock.record.card"]
        self.bin_card_model = self.env["mesob.bin.card"]

        # Fetch standard unit of measure
        self.uom_unit = self.env.ref("uom.product_uom_unit")

        # Base Classification and Item setup
        self.classification = self.env["mesob.inventory.major.classification"].create({
            "code": "4403",
            "name": "Hardware Equipment",
        })
        self.sub_classification = self.env["mesob.inventory.sub.classification"].create({
            "code": "001",
            "name": "Power Tools",
            "major_classification_id": self.classification.id,
        })
        self.item = self.item_model.create({
            "item_code": "4403-001-001",
            "name": "Electric Drill",
            "classification_id": self.classification.id,
            "sub_classification_id": self.sub_classification.id,
            "reorder_level": 5.0,
            "minimum_level": 2.0,
            "uom_id": self.uom_unit.id,
        })

        # Test users
        self.user_storekeeper = self.env["res.users"].create({
            "name": "Storekeeper Auditor",
            "login": "sk_auditor",
            "email": "sk_auditor@mesob.com",
        })
        self.user_storekeeper.write({
            "group_ids": [(4, self.env.ref("mesob_inventory_base.group_mesob_storekeeper").id)],
        })

    def test_01_document_sequence_generation(self):
        """FR-SEQ-001: Ensure sequences generate sequential formatted IDs upon record creation."""
        # 1. Test Requisition (Model 20)
        req = self.requisition_model.create({
            "issue_mode": "imprest",
            "department": "ministry_transport_logistics",
            "requested_by_id": self.env.user.id,
        })
        self.assertTrue(req.name)
        self.assertNotEqual(req.name, "New")

        # 2. Test Receiving Order
        receiving = self.receiving_model.create({
            "source_type": "supplier",
            "received_by_id": self.user_storekeeper.id,
        })
        self.assertTrue(receiving.name)
        self.assertNotEqual(receiving.name, "New")

        # 3. Test Issue Voucher (Model 22) - Requisition must be approved first!
        req.write({"state": "approved"})
        iv = self.issue_voucher_model.create({
            "requisition_id": req.id,
            "issued_by_id": self.user_storekeeper.id,
        })
        self.assertTrue(iv.name)
        self.assertNotEqual(iv.name, "New")

        # 4. Test Gate Pass (Dispatch)
        gate_pass = self.gate_pass_model.create({
            "issue_voucher_id": iv.id,
            "destination": "Regional Lab",
            "receiver_name": "Lami Chache",
            "receiver_organization": "Federal Science Hub",
        })
        self.assertTrue(gate_pass.name)
        self.assertNotEqual(gate_pass.name, "New")

    def test_02_reorder_alert_trigger(self):
        """FR-SC-001 / FR-SC-003: Trigger reorder alert when current stock falls below reorder level."""
        # Purge any pre-existing alerts for this item to ensure transaction state isolation
        self.alert_model.search([("item_id", "=", self.item.id)]).unlink()

        # Set minimum_level to 0.0 and flush to guarantee alert is of type 'reorder' and not 'minimum'
        self.item.write({"minimum_level": 0.0})
        self.env.flush_all()

        # Force low stock simulation by creating sequential Bin Card records
        # 1. Receipt record to load 4.0 units
        self.bin_card_model.create({
            "major_classification_id": self.classification.id,
            "sub_classification_id": self.sub_classification.id,
            "transaction_type": "receipt",
            "quantity_received": 4.0,
            "quantity_distributed": 0.0,
            "location": "A-12",
            "uom_id": self.uom_unit.id,
        })
        self.env.flush_all()

        # 2. Issue record to distribute 1.0 unit (leaving 3.0 units running balance!)
        self.bin_card_model.create({
            "major_classification_id": self.classification.id,
            "sub_classification_id": self.sub_classification.id,
            "transaction_type": "issue",
            "quantity_received": 0.0,
            "quantity_distributed": 1.0,
            "location": "A-12",
            "uom_id": self.uom_unit.id,
        })
        self.env.flush_all()

        # Run the daily cron checking logic
        self.alert_model._cron_check_stock_levels()

        # Check if an alert was automatically triggered for our Electric Drill item
        alert = self.alert_model.search([("item_id", "=", self.item.id)])
        self.assertTrue(alert)
        print(f"\n\nDEBUG ALERT: Found alert for item {alert.item_id.name}, type: {alert.alert_type}, current_stock: {alert.current_stock}, minimum_level: {alert.minimum_level}, reorder_level: {alert.reorder_level}\n\n")
        self.assertEqual(alert.alert_type, "reorder")
        self.assertEqual(alert.state, "new")

    def test_03_fifo_costing_layer_valuation(self):
        """FR-VAL-001: Ensure stock receipts create FIFO layers and issues consume early layers first."""
        # 1. First stock arrival: 10 units at $15 each (Total: $150)
        card1 = self.stock_card_model.create({
            "item_id": self.item.id,
            "transaction_type": "receipt",
            "quantity_in": 10.0,
            "unit_cost": 15.0,
            "quantity_balance": 10.0,
            "balance_value": 150.0,
            "uom_id": self.uom_unit.id,
        })
        card1.action_create_fifo_layers()

        # 2. Second stock arrival: 5 units at $20 each (Total: $100, New Balance: $250)
        card2 = self.stock_card_model.create({
            "item_id": self.item.id,
            "transaction_type": "receipt",
            "quantity_in": 5.0,
            "unit_cost": 20.0,
            "quantity_balance": 15.0,
            "balance_value": 250.0,
            "uom_id": self.uom_unit.id,
        })
        card2.action_create_fifo_layers()

        # 3. Verify that we have exactly 2 active FIFO cost layers
        layers = self.env["mesob.stock.fifo.layer"].search([
            ("item_id", "=", self.item.id),
            ("is_exhausted", "=", False)
        ], order="date asc")
        self.assertEqual(len(layers), 2)
        self.assertEqual(layers[0].quantity_remaining, 10.0)
        self.assertEqual(layers[1].quantity_remaining, 5.0)

        # 4. Issue 12 units from stock.
        # According to GAAP FIFO:
        # - It must consume all 10 units of the $15 layer (value: $150).
        # - It must consume 2 units of the $20 layer (value: $40).
        # - Total Cost Out must be exactly $190.
        # - Remaining Balance Value must be exactly $60 (3 units remaining at $20/unit).
        issue_record = self.stock_card_model.create({
            "item_id": self.item.id,
            "transaction_type": "issue",
            "quantity_out": 12.0,
            "quantity_balance": 3.0,
            "uom_id": self.uom_unit.id,
        })

        # Trigger FIFO consumption computations (if not automated in create override)
        if hasattr(issue_record, "action_consume_fifo"):
            issue_record.action_consume_fifo()

        # Re-fetch active FIFO layers
        active_layers = self.env["mesob.stock.fifo.layer"].search([
            ("item_id", "=", self.item.id),
            ("is_exhausted", "=", False)
        ])
        
        # Only 1 layer (the $20 one) should still be active, with exactly 3.0 units remaining
        self.assertEqual(len(active_layers), 1)
        self.assertEqual(active_layers[0].unit_cost, 20.0)
        self.assertEqual(active_layers[0].quantity_remaining, 3.0)

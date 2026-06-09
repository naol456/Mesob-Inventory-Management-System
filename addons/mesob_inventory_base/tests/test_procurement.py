from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError
from odoo import fields


class TestMesobProcurement(TransactionCase):
    """Automated Unit Tests for Mesob Procurement Subsystem (Section 4.13)"""

    def setUp(self):
        super(TestMesobProcurement, self).setUp()
        self.partner_model = self.env["res.partner"]
        self.item_model = self.env["mesob.inventory.item"]
        self.plan_model = self.env["mesob.procurement.plan"]
        self.need_model = self.env["mesob.procurement.need"]
        self.tender_model = self.env["mesob.procurement.tender"]
        self.bid_model = self.env["mesob.procurement.bid"]
        self.contract_model = self.env["mesob.procurement.contract"]
        self.po_model = self.env["mesob.procurement.order"]
        self.pay_model = self.env["mesob.procurement.payment.certificate"]

        # Set up a test classification and stock item
        self.classification = self.env["mesob.inventory.major.classification"].create({
            "code": "4402",
            "name": "Office Supplies",
        })
        self.sub_classification = self.env["mesob.inventory.sub_classification"].create({
            "code": "001",
            "name": "Paper Supplies",
            "major_classification_id": self.classification.id,
        })
        self.item = self.item_model.create({
            "item_code": "4402-001-001",
            "name": "Test Paper",
            "classification_id": self.classification.id,
            "sub_classification_id": self.sub_classification.id,
            "reorder_level": 10.0,
        })

        # Set up suppliers
        self.supplier_domestic_70 = self.partner_model.create({
            "name": "Bidder A (Domestic 70%)",
            "tin": "123456789",
            "is_blacklisted": False,
        })
        self.supplier_domestic_40 = self.partner_model.create({
            "name": "Bidder B (Domestic 40%)",
            "tin": "987654321",
            "is_blacklisted": False,
        })
        self.supplier_foreign = self.partner_model.create({
            "name": "Bidder C (Foreign)",
            "tin": "111222333",
            "is_blacklisted": False,
        })
        self.supplier_blacklisted = self.partner_model.create({
            "name": "Blacklisted Supplier",
            "tin": "444555666",
            "is_blacklisted": True,
        })

    def test_01_supplier_blacklist_validation(self):
        """FR-PROC-012: Ensure blacklisted supplier blocks PO creation."""
        # Create an APP and a Lot (budget below threshold to pass lot constraints)
        plan = self.plan_model.create({
            "fiscal_year": "2018 E.C.",
        })
        lot = self.env["mesob.procurement.plan.lot"].create({
            "plan_id": plan.id,
            "name": "Lot 1",
            "budget": 150000.0,
            "mechanism": "shopping",
        })

        with self.assertRaises(ValidationError):
            self.po_model.create({
                "plan_lot_id": lot.id,
                "supplier_id": self.supplier_blacklisted.id,
            })

    def test_02_bid_evaluation_domestic_preference(self):
        """FR-PROC-018 & AC-PROC-002: Test domestic preference margin ranking."""
        plan = self.plan_model.create({"fiscal_year": "2018 E.C."})
        lot = self.env["mesob.procurement.plan.lot"].create({
            "plan_id": plan.id,
            "name": "Lot Tendering",
            "mechanism": "bidding",
            "budget": 1000000000.0,
        })
        tender = self.tender_model.create({
            "lot_id": lot.id,
            "technical_specifications": "Standard High-Quality Goods",
        })

        # Add bid submissions (Values matching AC-PROC-002 exactly)
        bid_a = self.bid_model.create({
            "tender_id": tender.id,
            "supplier_id": self.supplier_domestic_70.id,
            "bid_price": 900000000.0,
            "local_content": 70.0,
        })
        bid_b = self.bid_model.create({
            "tender_id": tender.id,
            "supplier_id": self.supplier_domestic_40.id,
            "bid_price": 840000000.0,
            "local_content": 40.0,
        })
        bid_c = self.bid_model.create({
            "tender_id": tender.id,
            "supplier_id": self.supplier_foreign.id,
            "bid_price": 750000000.0,
            "local_content": 0.0,
        })

        # Process Tender states to evaluate
        tender.action_approve_spec()
        tender.action_advertise()
        tender.action_open_bids()
        tender.action_evaluate()

        # Check adjusted evaluation prices (AC-PROC-002)
        # Bidder B Evaluated Price: 840M * 0.89 = 747.6M
        self.assertAlmostEqual(bid_b.evaluated_price, 747600000.0)
        # Bidder A Evaluated Price: 900M * 0.865 = 778.5M
        self.assertAlmostEqual(bid_a.evaluated_price, 778500000.0)
        # Bidder C Evaluated Price: 750M (No preference)
        self.assertAlmostEqual(bid_c.evaluated_price, 750000000.0)

        # Check rankings
        self.assertEqual(bid_b.ranking, 1)  # Rank 1: Bidder B (747.6M)
        self.assertEqual(bid_c.ranking, 2)  # Rank 2: Bidder C (750M)
        self.assertEqual(bid_a.ranking, 3)  # Rank 3: Bidder A (778.5M)

    def test_03_payment_certificate_matching_and_liquidated_damages(self):
        """FR-PROC-034 & AC-PROC-005: 3-way match block & late delivery penalty."""
        plan = self.plan_model.create({"fiscal_year": "2018 E.C."})
        lot = self.env["mesob.procurement.plan.lot"].create({
            "plan_id": plan.id,
            "name": "Lot 2",
            "budget": 5000000.0,
            "mechanism": "bidding",  # Budget is above 200,000 so must be bidding/tendering
        })
        po = self.po_model.create({
            "plan_lot_id": lot.id,
            "supplier_id": self.supplier_domestic_70.id,
        })

        # Create Payment certificate (Contract/Invoice amount gross: 4,000,000)
        pay_cert = self.pay_model.create({
            "order_id": po.id,
            "amount_gross": 4000000.0,
            "days_delay": 1,         # 1 day delay
            "penalty_rate": 0.1,     # 1/1000 = 0.1% per day
            "retention_percent": 5.0, # 5% retention
        })

        # Liquidated damages calculation: 4,000,000 * 0.1% * 1 = 4,000
        self.assertAlmostEqual(pay_cert.liquidated_damages, 4000.0)
        # Retention calculation: 4,000,000 * 5% = 200,000
        self.assertAlmostEqual(pay_cert.retention_amount, 200000.0)
        # Net Payable: 4,000,000 - 4,000 - 200,000 = 3,796,000
        self.assertAlmostEqual(pay_cert.net_payable, 3796000.0)

        # 3-Way Match hard-block verification (FR-PROC-034)
        with self.assertRaises(UserError):
            pay_cert.action_approve()  # Missing verified invoice/model 19/po flags

        pay_cert.write({
            "has_po": True,
            "has_model19": True,
            "has_invoice": True,
        })
        pay_cert.action_approve()
        self.assertEqual(pay_cert.state, "approved")

    def test_04_surplus_and_disposal_po_block(self):
        """BR-PROC-008 & AC-PROC-006: Disposal surplus block rule."""
        plan = self.plan_model.create({"fiscal_year": "2018 E.C."})
        lot = self.env["mesob.procurement.plan.lot"].create({
            "plan_id": plan.id,
            "name": "Office Assets Lot",
            "budget": 150000.0,
            "mechanism": "shopping",
        })
        po = self.po_model.create({
            "plan_lot_id": lot.id,
            "supplier_id": self.supplier_domestic_70.id,
        })
        self.env["mesob.procurement.order.line"].create({
            "order_id": po.id,
            "major_classification_id": self.classification.id,
            "sub_classification_id": self.sub_classification.id,
            "quantity": 5.0,
            "price_unit": 100.0,
        })

        po.action_submit()

        # Flag item as surplus
        self.item.write({"is_surplus": True})

        # Approval must be hard blocked
        with self.assertRaises(UserError):
            po.action_approve()

        # Unflag surplus
        self.item.write({"is_surplus": False})
        po.action_approve()
        self.assertEqual(po.state, "approved")

    def test_05_fppa_shopping_threshold_restriction(self):
        """FPPA Directives: Ensure a Shopping/RFQ lot budget cannot exceed ETB 200,000."""
        plan = self.plan_model.create({"fiscal_year": "2018 E.C."})
        with self.assertRaises(ValidationError):
            self.env["mesob.procurement.plan.lot"].create({
                "plan_id": plan.id,
                "name": "High Budget Shopping",
                "budget": 200001.0,  # Exceeds ETB 200,000 limit
                "mechanism": "shopping",
            })

    def test_06_fppa_splitting_ban_restriction(self):
        """FPPA Directives Article 26: Ensure splitting same-category lots to bypass bidding is blocked."""
        plan = self.plan_model.create({"fiscal_year": "2018 E.C."})
        self.env["mesob.procurement.plan.lot"].create({
            "plan_id": plan.id,
            "name": "Supplies Part 1",
            "category": "supplies",
            "budget": 100000.0,
            "mechanism": "shopping",
        })
        # Attempting to add a duplicate 'supplies' category lot under 'shopping' must trigger a ValidationError
        with self.assertRaises(ValidationError):
            self.env["mesob.procurement.plan.lot"].create({
                "plan_id": plan.id,
                "name": "Supplies Part 2 (Split Lot)",
                "category": "supplies",
                "budget": 100000.0,
                "mechanism": "shopping",
            })

from odoo.tests.common import TransactionCase
from odoo.exceptions import UserError, ValidationError


class TestMesobStockTakingHandover(TransactionCase):
    """Automated Unit Tests for Stock-Taking & Custody Handovers (Section 4.8 & 4.9)"""

    def setUp(self):
        super(TestMesobStockTakingHandover, self).setUp()
        self.item_model = self.env["mesob.inventory.item"]
        self.stock_taking_model = self.env["mesob.stock.taking"]
        self.handover_model = self.env["mesob.stock.handover"]
        
        # Groups and users
        self.user_pao = self.env["res.users"].create({
            "name": "PAO Supervisor",
            "login": "pao_super",
            "email": "pao@mesob.com",
            "groups_id": [(4, self.env.ref("mesob_inventory_base.group_mesob_pao").id)],
        })
        self.user_sk_1 = self.env["res.users"].create({
            "name": "Storekeeper Outgoing",
            "login": "sk_out",
            "email": "sk1@mesob.com",
            "groups_id": [(4, self.env.ref("mesob_inventory_base.group_mesob_storekeeper").id)],
        })
        self.user_sk_2 = self.env["res.users"].create({
            "name": "Storekeeper Incoming",
            "login": "sk_in",
            "email": "sk2@mesob.com",
            "groups_id": [(4, self.env.ref("mesob_inventory_base.group_mesob_storekeeper").id)],
        })
        self.user_witness = self.env["res.users"].create({
            "name": "Auditor Witness",
            "login": "witness_aud",
            "email": "witness@mesob.com",
            "groups_id": [(4, self.env.ref("mesob_inventory_base.group_mesob_auditor").id)],
        })

    def test_01_stock_taking_storekeeper_exclusion(self):
        """FR-ST-009 / BR-ST-001: Ensure storekeeper cannot be a counting team member."""
        with self.assertRaises(ValidationError):
            self.stock_taking_model.create({
                "pao_id": self.user_pao.id,
                "instructions": "Physical count of warehouse A",
                "team_member_ids": [(4, self.user_sk_1.id)],  # Storekeeper
            })

    def test_02_stock_taking_workflow(self):
        """FR-ST-001/002/006: Complete Stock-taking event and verify adjustments."""
        # Create valid stock take
        st = self.stock_taking_model.create({
            "pao_id": self.user_pao.id,
            "instructions": "Full year physical count",
            "team_member_ids": [(4, self.user_witness.id)],  # Auditor (Allowed)
            "is_pre_training_done": True,
        })
        
        # Start counting
        st.action_start_stock_taking()
        self.assertEqual(st.state, "ongoing")
        
        # Count all sheets lines
        for line in st.line_ids:
            line.write({
                "physical_qty": line.recorded_qty + 2.0,  # Simulate overage
                "is_counted": True,
                "discrepancy_reason": "overage",
            })
            
        # Reconcile & complete
        st.action_complete_and_reconcile()
        self.assertEqual(st.state, "completed")

    def test_03_handover_distinctive_participants(self):
        """FR-HO-002: Outgoing and incoming storekeeper must be distinct."""
        with self.assertRaises(ValidationError):
            self.handover_model.create({
                "trigger_event": "leave",
                "outgoing_storekeeper_id": self.user_sk_1.id,
                "incoming_storekeeper_id": self.user_sk_1.id,  # Same
                "witness_id": self.user_witness.id,
            })

    def test_04_handover_workflow(self):
        """FR-HO-001/002/003: Check handover workflow triggers and states."""
        ho = self.handover_model.create({
            "trigger_event": "transfer",
            "outgoing_storekeeper_id": self.user_sk_1.id,
            "incoming_storekeeper_id": self.user_sk_2.id,
            "witness_id": self.user_witness.id,
        })
        
        # Start counting custody
        ho.action_start_counting()
        self.assertEqual(ho.state, "counting")
        self.assertTrue(ho.certificate)
        
        # Verify signing
        ho.action_sign_handover()
        self.assertEqual(ho.state, "signed")
        
        # Finalize custody transfer
        ho.action_finalize_handover()
        self.assertEqual(ho.state, "done")


class TestMesobStorageSecurity(TransactionCase):
    """Automated Unit Tests for Warehouse Storage Safety & Security (Section 4.12)"""

    def setUp(self):
        super(TestMesobStorageSecurity, self).setUp()
        self.plan_model = self.env["mesob.storage.plan"]
        self.key_model = self.env["mesob.storage.key.register"]
        self.visitor_model = self.env["mesob.storage.visitor.log"]
        self.safety_model = self.env["mesob.storage.safety.checklist"]

    def test_01_storage_plan_approval(self):
        """FR-STOR-002: Test creation and approval of a storage physical plan."""
        plan = self.plan_model.create({
            "name": "HQ Store Layout v1",
            "aisles": "Aisles A, B, C, D",
            "gates_count": 2,
        })
        self.assertEqual(plan.state, "draft")
        plan.action_approve()
        self.assertEqual(plan.state, "approved")

    def test_02_key_custody_tracking(self):
        """FR-STOR-003: Ensure key collected and deposited timestamps record correctly."""
        key_record = self.key_model.create({
            "key_id": "Main-Gate-Key-01",
            "collected_by_id": self.env.user.id,
        })
        self.assertTrue(key_record.collected_at)
        self.assertFalse(key_record.deposited_at)
        
        key_record.action_deposit_keys()
        self.assertTrue(key_record.deposited_at)

    def test_03_visitor_log(self):
        """FR-STOR-004: Validate visitor entrance and exit time registration."""
        visitor = self.visitor_model.create({
            "visitor_name": "Abebe Kebede",
            "purpose": "IT Infrastructure Network Audit",
        })
        self.assertTrue(visitor.entry_time)
        self.assertFalse(visitor.exit_time)
        
        visitor.action_exit()
        self.assertTrue(visitor.exit_time)

    def test_04_safety_precautions_checklist(self):
        """FR-STOR-005/006: Verify safety check compliance inputs."""
        checklist = self.safety_model.create({
            "has_fire_extinguishers_checked": True,
            "has_ppe_available": True,
            "has_first_aid_kit": True,
            "has_emergency_exits_clear": True,
            "remarks": "All safety metrics pass.",
        })
        self.assertTrue(checklist.name)
        self.assertTrue(checklist.has_fire_extinguishers_checked)
        self.assertTrue(checklist.has_ppe_available)

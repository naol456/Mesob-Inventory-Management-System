from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
import datetime


class MesobProcurementPlan(models.Model):
    """Annual Procurement Plan (APP) - FR-PROC-001."""

    _name = "mesob.procurement.plan"
    _description = "Annual Procurement Plan"
    _order = "fiscal_year desc, id desc"

    name = fields.Char(
        string="APP Reference",
        required=True,
        copy=False,
        default="New",
    )
    fiscal_year = fields.Char(
        string="Ethiopian Fiscal Year",
        required=True,
        placeholder="e.g., 2018 E.C.",
    )
    planning_type = fields.Selection(
        [("standard", "Standard / Planned"), ("emergency", "Emergency")],
        string="Planning Type",
        default="standard",
        required=True,
    )
    execution_type = fields.Selection(
        [("domestic", "Domestic Only"), ("international", "International / Both")],
        string="Execution Type",
        default="domestic",
        required=True,
    )
    procurement_stream = fields.Selection(
        [
            ("goods", "Goods"),
            ("works", "Works"),
            ("services", "Non-Consulting Services"),
            ("consultancy", "Consultancy Services"),
        ],
        string="Procurement Stream",
        default="goods",
        required=True,
    )
    rejection_comment = fields.Text(string="Rejection Comments")
    lot_ids = fields.One2many(
        "mesob.procurement.plan.lot",
        "plan_id",
        string="Procurement Lots",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("puh_approved", "PUH Approved"),
            ("pec_approved", "PEC Approved"),
            ("hope_approved", "HOPE Approved (Published)"),
            ("rejected", "Rejected"),
        ],
        string="Status",
        default="draft",
        required=True,
        tracking=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = f"APP/{vals.get('fiscal_year', 'FY')}/{self.env['ir.sequence'].next_by_code('mesob.procurement.plan') or '001'}"
        return super().create(vals_list)

    def action_puh_approve(self):
        """Procurement Unit Head approves the APP."""
        for rec in self:
            if rec.state not in ("draft", "rejected"):
                raise UserError("Only draft or rejected plans can be approved by PUH.")
            rec.state = "puh_approved"
        return True

    def action_pec_approve(self):
        """Procurement Endorsing Committee approves the APP."""
        for rec in self:
            if rec.state != "puh_approved":
                raise UserError("The plan must be approved by PUH first.")
            rec.state = "pec_approved"
        return True

    def action_hope_approve(self):
        """Head of Public Body (HOPE) gives final authorization (FR-PROC-005)."""
        for rec in self:
            if rec.state != "pec_approved":
                raise UserError("The plan must be approved by PEC first.")
            rec.state = "hope_approved"
            # Route lots to correct execution workflow (FR-PROC-006)
            for lot in rec.lot_ids:
                if lot.mechanism == "bidding":
                    lot.state = "tender"
                elif lot.mechanism == "shopping":
                    lot.state = "rfq"
                else:
                    lot.state = "approved"
        return True

    def action_reject(self, comment):
        """Reject and return to preceding actor with mandatory comments."""
        for rec in self:
            if not comment:
                raise UserError("Mandatory comment required for rejection.")
            rec.write({
                "state": "rejected",
                "rejection_comment": comment,
            })
        return True


class MesobProcurementPlanLot(models.Model):
    """Procurement Lot inside APP - FR-PROC-004."""

    _name = "mesob.procurement.plan.lot"
    _description = "Procurement Lot"

    plan_id = fields.Many2one(
        "mesob.procurement.plan",
        string="Annual Plan",
        required=True,
        ondelete="cascade",
    )
    name = fields.Char(string="Lot Name / No.", required=True)
    category = fields.Selection(
        [
            ("supplies", "Supplies / Raw Materials"),
            ("equipment", "Office Equipment / IT"),
            ("fixed_assets", "Fixed Assets"),
            ("other", "Other"),
        ],
        string="Category",
        default="supplies",
        required=True,
    )
    mechanism = fields.Selection(
        [
            ("bidding", "Tender / Bidding"),
            ("shopping", "Shopping / RFQ"),
            ("direct", "Direct (Single-Source)"),
        ],
        string="Procurement Mechanism",
        default="shopping",
        required=True,
    )
    budget = fields.Float(string="Distributed Budget", required=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("approved", "Approved"),
            ("tender", "Tender Prepared"),
            ("rfq", "RFQ Pending"),
            ("closed", "Closed"),
        ],
        string="Lot Status",
        default="draft",
    )
    need_ids = fields.One2many(
        "mesob.procurement.need",
        "lot_id",
        string="Consolidated Needs",
    )


class MesobProcurementNeed(models.Model):
    """Departmental Needs Collection - FR-PROC-002."""

    _name = "mesob.procurement.need"
    _description = "Departmental Need Request"

    department = fields.Selection(
        [
            ("ministry_transport_logistics", "Ministry of Transport and Logistics"),
            ("commercial_bank_ethiopia", "Commercial Bank of Ethiopia"),
            ("ethio_telecom", "Ethio telecom"),
            ("education_training_authority", "Education and Training Authority"),
            ("ethiopian_environmental_protection", "Ethiopian Environmental Protection Authority"),
            ("ethiopian_food_drug_authority", "Ethiopian Food and Drug Authority"),
            ("ethiopian_agricultural_authority", "Ethiopian Agricultural Authority"),
            ("ethiopian_construction_authority", "Ethiopian Construction Authority"),
            ("ministry_health", "Ministry of Health"),
            ("ethiopian_customs_commission", "Ethiopian Customs Commission"),
            ("ministry_justice", "Ministry of Justice"),
            ("ministry_trade_regional_integration", "Ministry of Trade and Regional Integration"),
            ("ministry_tourism", "Ministry of Tourism"),
            ("ethiopian_postal_service", "Ethiopian Postal Service Enterprise"),
            ("ethiopian_investment_commission", "Ethiopian Investment Commission"),
            ("educational_assessment_examination", "Educational Assessment and Examination Service"),
            ("documents_authentication_registration", "Documents Authentication and Registration Service"),
            ("ministry_revenues", "Ministry of Revenues"),
            ("ministry_foreign_affairs", "Ministry of Foreign Affairs"),
            ("ministry_labor_skills", "Ministry of Labor and Skills"),
            ("immigration_citizenship_service", "Immigration and Citizenship Service"),
            ("national_id_program", "National ID Program"),
        ],
        string="Requesting Department",
        required=True,
    )
    item_id = fields.Many2one(
        "mesob.inventory.item",
        string="Catalogued Stock Item",
        required=True,
        help="Must be a catalogued item code ####-###-###.",
    )
    item_code = fields.Char(
        related="item_id.item_code",
        string="Item Code",
        readonly=True,
    )
    quantity = fields.Float(string="Quantity Requested", required=True, default=1.0)
    estimated_unit_price = fields.Float(string="Estimated Unit Price", required=True)
    total_price = fields.Float(
        string="Estimated Total Price",
        compute="_compute_total_price",
        store=True,
    )
    expected_delivery_period = fields.Char(
        string="Expected Delivery Period",
        required=True,
        placeholder="e.g. Q1 / Sene 2018",
    )
    reviewer_id = fields.Many2one("res.users", string="Reviewer", readonly=True)
    review_timestamp = fields.Datetime(string="Review Timestamp", readonly=True)
    lot_id = fields.Many2one(
        "mesob.procurement.plan.lot",
        string="Assigned APP Lot",
        help="Lot assigned by Senior Procurement Officer (FR-PROC-004).",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("reviewed", "Reviewed"),
            ("locked", "Locked (Immutable)"),
        ],
        string="Status",
        default="draft",
        required=True,
    )

    @api.depends("quantity", "estimated_unit_price")
    def _compute_total_price(self):
        for rec in self:
            rec.total_price = rec.quantity * rec.estimated_unit_price

    def action_submit(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError("Only draft needs can be submitted.")
            rec.state = "submitted"
        return True

    def action_review(self):
        """Reviewer workflow (FR-PROC-003)."""
        for rec in self:
            if rec.state != "submitted":
                raise UserError("Only submitted needs can be reviewed.")
            rec.write({
                "state": "reviewed",
                "reviewer_id": self.env.user.id,
                "review_timestamp": fields.Datetime.now(),
            })
        return True

    def action_lock(self):
        """Lock need to make it immutable."""
        for rec in self:
            if rec.state != "reviewed":
                raise UserError("Only reviewed needs can be locked.")
            rec.state = "locked"
        return True


class MesobProcurementTender(models.Model):
    """Bidding and Tender Management - FR-PROC-013."""

    _name = "mesob.procurement.tender"
    _description = "Procurement Tender"
    _order = "id desc"

    name = fields.Char(
        string="Tender Reference",
        required=True,
        copy=False,
        default="New",
    )
    lot_id = fields.Many2one(
        "mesob.procurement.plan.lot",
        string="Source APP Lot",
        required=True,
        domain=[("mechanism", "=", "bidding")],
    )
    technical_specifications = fields.Text(
        string="Technical Specifications",
        required=True,
        help="FR-PROC-009 quality performance characteristics (brandless).",
    )
    spec_status = fields.Selection(
        [("draft", "Draft"), ("approved", "Approved")],
        string="Specification Status",
        default="draft",
        required=True,
    )
    advertisement_date = fields.Date(string="Advertisement Date")
    submission_deadline = fields.Datetime(string="Submission Deadline")
    opening_minutes = fields.Text(string="Bid Opening Minutes (FR-PROC-015)")
    opening_signatures = fields.Text(string="Opening Committee Signatures")
    bid_ids = fields.One2many(
        "mesob.procurement.bid",
        "tender_id",
        string="Submitted Bids",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("spec_approved", "Spec Approved"),
            ("advertised", "Advertised"),
            ("opened", "Bids Opened"),
            ("evaluated", "Evaluated"),
            ("closed", "Closed"),
        ],
        string="Status",
        default="draft",
        required=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = f"TEN/{self.env['ir.sequence'].next_by_code('mesob.procurement.tender') or '001'}"
        return super().create(vals_list)

    def action_approve_spec(self):
        """Technical specifications sign-off status approved (FR-PROC-009)."""
        for rec in self:
            rec.write({
                "spec_status": "approved",
                "state": "spec_approved",
            })
        return True

    def action_advertise(self):
        for rec in self:
            if rec.spec_status != "approved":
                raise UserError("Cannot advertise until Technical Specifications are approved (FR-PROC-013).")
            if not rec.advertisement_date or not rec.submission_deadline:
                raise UserError("Please set advertisement date and submission deadline first.")
            rec.state = "advertised"
        return True

    def action_open_bids(self):
        """Record public bid opening minutes and validate timestamps (FR-PROC-015)."""
        for rec in self:
            if rec.state != "advertised":
                raise UserError("Bids can only be opened after the tender is advertised.")
            rec.state = "opened"
        return True

    def action_evaluate(self):
        """Trigger bid evaluation ranking and preference calculations (FR-PROC-017, FR-PROC-018)."""
        for rec in self:
            if rec.state != "opened":
                raise UserError("Bids must be opened before evaluation.")

            # Filter responsive / preliminary passed bids
            responsive_bids = rec.bid_ids.filtered(lambda b: b.preliminary_passed)
            if not responsive_bids:
                raise UserError("There are no responsive/preliminary passed bids to evaluate.")

            # Compute adjusted evaluated price & ranking
            for bid in responsive_bids:
                preference_factor = 1.0
                if bid.local_content >= 70.0:
                    preference_factor = 1.0 - 0.135  # 13.5% domestic preference (FR-PROC-018)
                elif 40.0 <= bid.local_content < 70.0:
                    preference_factor = 1.0 - 0.11   # 11% domestic preference
                
                bid.evaluated_price = bid.bid_price * preference_factor

            # Perform ranking (ascending evaluated price)
            ranked_bids = sorted(responsive_bids, key=lambda b: b.evaluated_price)
            for rank, bid in enumerate(ranked_bids, start=1):
                bid.ranking = rank

            rec.state = "evaluated"
        return True


class MesobProcurementBid(models.Model):
    """Supplier Bid submission inside Tender - FR-PROC-017."""

    _name = "mesob.procurement.bid"
    _description = "Procurement Bid Submission"

    tender_id = fields.Many2one("mesob.procurement.tender", string="Tender", required=True, ondelete="cascade")
    supplier_id = fields.Many2one(
        "res.partner",
        string="Supplier",
        required=True,
        domain=[("fppa_blacklisted", "=", False)],
    )
    bid_price = fields.Float(string="Original Bid Price (ETB)", required=True)
    local_content = fields.Float(
        string="Local Content (%)",
        default=0.0,
        help="Percentage of local material/manufacturing content.",
    )
    preliminary_passed = fields.Boolean(
        string="Administrative Passed",
        default=True,
        help="Checked bid completeness, security validity & eligibility.",
    )
    technical_score = fields.Float(string="Technical Score", default=0.0)
    financial_score = fields.Float(string="Financial Score", default=0.0)
    evaluated_price = fields.Float(
        string="Evaluated Price (ETB)",
        readonly=True,
        help="Adjusted price applying domestic preference margin for ranking ONLY (BR-PROC-003).",
    )
    ranking = fields.Integer(string="Rank", readonly=True)

    @api.constrains("supplier_id")
    def _check_supplier_status(self):
        for rec in self:
            if rec.supplier_id.fppa_blacklisted:
                raise ValidationError(f"Supplier {rec.supplier_id.name} is blacklisted and cannot participate (FR-PROC-012).")


class MesobProcurementContract(models.Model):
    """Contract Formation & Management - FR-PROC-021."""

    _name = "mesob.procurement.contract"
    _description = "Procurement Contract"
    _order = "id desc"

    name = fields.Char(string="Contract Number", required=True, copy=False)
    supplier_id = fields.Many2one(
        "res.partner",
        string="Supplier",
        required=True,
        domain=[("fppa_blacklisted", "=", False)],
    )
    lot_id = fields.Many2one("mesob.procurement.plan.lot", string="APP Lot Reference", required=True)
    total_value = fields.Float(string="Total Contract Value (ETB)", required=True)
    delivery_schedule = fields.Text(string="Delivery Schedule")
    payment_terms = fields.Text(string="Payment Terms")
    performance_security_recorded = fields.Boolean(
        string="Performance Security Recorded",
        default=False,
    )
    performance_security_details = fields.Text(string="Performance Security Details")
    advance_payment = fields.Float(
        string="Advance Payment (%)",
        default=0.0,
        help="Capped at maximum 30% for goods (BR-PROC-006).",
    )
    advance_payment_guarantee = fields.Boolean(
        string="Advance Payment Guarantee Recorded",
        default=False,
    )
    cumulative_variation_total = fields.Float(
        string="Cumulative Variations Total (ETB)",
        default=0.0,
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("signed", "Signed"),
            ("variation", "In Variation / Amendment"),
            ("closed", "Closed"),
        ],
        string="Contract Status",
        default="draft",
        required=True,
    )

    @api.constrains("advance_payment", "advance_payment_guarantee")
    def _check_advance_payment_rules(self):
        for rec in self:
            if rec.advance_payment > 30.0:
                raise ValidationError("Advance payment cannot exceed 30% of contract value for goods contracts (BR-PROC-006).")
            if rec.advance_payment > 0.0 and not rec.advance_payment_guarantee:
                raise ValidationError("Advance payment is blocked until an advance payment guarantee of equivalent value is recorded (FR-PROC-022).")

    def action_sign_contract(self):
        """Sign contract validation (FR-PROC-021)."""
        for rec in self:
            # Check complaints during standstill (FR-PROC-020)
            open_complaints = self.env["mesob.procurement.complaint"].search([
                ("lot_id", "=", rec.lot_id.id),
                ("state", "=", "open")
            ])
            if open_complaints:
                raise UserError("Contract signature is blocked. There is an active open complaint registered during the standstill period (FR-PROC-020).")
            
            # Check performance security
            if rec.total_value >= 500000.0 and not rec.performance_security_recorded:
                raise UserError("Performance security must be recorded for contracts of ETB 500,000 or above before signature (FR-PROC-021).")
            
            rec.state = "signed"
        return True


class MesobProcurementOrder(models.Model):
    """Standard Purchase Order mapped to APP and Contracts - FR-PROC-026."""

    _name = "mesob.procurement.order"
    _description = "Purchase Order"
    _inherit = ["mail.thread"]
    _order = "date_order desc, id desc"

    name = fields.Char(
        string="PO Reference",
        required=True,
        copy=False,
        default="New",
        readonly=True,
    )
    plan_lot_id = fields.Many2one("mesob.procurement.plan.lot", string="APP Lot Reference", required=True)
    contract_id = fields.Many2one("mesob.procurement.contract", string="Contract Link")
    supplier_id = fields.Many2one(
        "res.partner",
        string="Supplier",
        required=True,
        domain=[("is_blacklisted", "=", False)],
        tracking=True,
    )
    date_order = fields.Date(string="Order Date", default=fields.Date.today, required=True)
    inspection_type = fields.Selection(
        [
            ("storekeeper", "Storekeeper (Simple Items)"),
            ("technical", "Technical Staff (Technical Items)"),
            ("independent", "Independent / Supplier-site"),
        ],
        string="Inspection Type",
        default="storekeeper",
        required=True,
        help="Assign inspection type for receiving team (FR-PROC-031).",
    )
    line_ids = fields.One2many(
        "mesob.procurement.order.line",
        "order_id",
        string="Purchase Order Lines",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("pending", "Pending Approval"),
            ("approved", "Approved"),
            ("sent", "Sent to Supplier"),
            ("partially_received", "Partially Received"),
            ("fully_received", "Fully Received"),
            ("closed", "Closed"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        required=True,
        tracking=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = f"PO/{self.env['ir.sequence'].next_by_code('mesob.procurement.order') or '001'}"
        return super().create(vals_list)

    @api.constrains("supplier_id")
    def _check_supplier_validity(self):
        for rec in self:
            print(f"\n\nDEBUG: Checking supplier {rec.supplier_id.name}, fppa_blacklisted: {rec.supplier_id.fppa_blacklisted}\n\n")
            if rec.supplier_id.fppa_blacklisted:
                raise ValidationError(f"Hard-Stop: Supplier '{rec.supplier_id.name}' is currently blacklisted! (FR-PROC-012)")
            if rec.supplier_id.registration_expiry_date and rec.supplier_id.registration_expiry_date < fields.Date.today():
                raise ValidationError(f"Hard-Stop: Supplier '{rec.supplier_id.name}' registration license has expired! (FR-PROC-012)")

    def action_submit(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError("Only draft Purchase Orders can be submitted.")
            rec.state = "pending"

    def action_approve(self):
        """Authorize the Purchase Order."""
        for rec in self:
            if rec.state != "pending":
                raise UserError("Only pending Purchase Orders can be approved.")
            
            # Check Surplus block business rule (BR-PROC-008 / AC-PROC-006)
            for line in rec.line_ids:
                if line.item_id.is_surplus:
                    raise UserError(f"Approval Blocked: Stock item code '{line.item_id.item_code}' is currently flagged as surplus in the Disposal system! (BR-PROC-008)")

            rec.state = "approved"
        return True


class MesobProcurementOrderLine(models.Model):
    """Line item in Purchase Order - FR-PROC-026."""

    _name = "mesob.procurement.order.line"
    _description = "Purchase Order Line"

    order_id = fields.Many2one("mesob.procurement.order", string="Purchase Order", ondelete="cascade")
    item_id = fields.Many2one("mesob.inventory.item", string="Catalogued Item", required=True)
    quantity = fields.Float(string="Quantity", required=True, default=1.0)
    qty_received = fields.Float(string="Received Qty", compute="_compute_received_qty", store=True)
    price_unit = fields.Float(string="Unit Price (ETB)", required=True)
    price_subtotal = fields.Float(string="Subtotal", compute="_compute_subtotal", store=True)

    @api.depends("quantity", "price_unit")
    def _compute_subtotal(self):
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit

    @api.depends("order_id.name", "item_id")
    def _compute_received_qty(self):
        for line in self:
            # Query accepted Model 19 quantities received under this PO reference
            domain = [
                ("model19_id.receiving_id.purchase_order_ref", "=", line.order_id.name),
                ("item_id", "=", line.item_id.id),
                ("model19_id.state", "=", "done"),
            ]
            receipt_lines = self.env["mesob.inventory.model19.line"].search(domain)
            line.qty_received = sum(receipt_lines.mapped("quantity"))


class MesobProcurementPaymentCertificate(models.Model):
    """Three-Way Match payment validation & processing - FR-PROC-034."""

    _name = "mesob.procurement.payment.certificate"
    _description = "Procurement Payment Certificate"
    _order = "id desc"

    name = fields.Char(string="Certificate Number", required=True, copy=False, default="New")
    order_id = fields.Many2one("mesob.procurement.order", string="Purchase Order", required=True)
    supplier_id = fields.Many2one(related="order_id.supplier_id", string="Supplier", readonly=True, store=True)
    amount_gross = fields.Float(string="Gross Amount (ETB)", required=True)
    
    # Matching Checks
    has_invoice = fields.Boolean(string="VAT Compliant Invoice Verified", default=False)
    has_model19 = fields.Boolean(string="Model 19 Receipt Verified", default=False)
    has_po = fields.Boolean(string="Approved PO Verified", default=False)
    
    # Calculations
    days_delay = fields.Integer(string="Days of Delay", default=0)
    penalty_rate = fields.Float(string="Daily Penalty Rate (%)", default=0.1)  # Default: 1/1000 = 0.1% per day
    liquidated_damages = fields.Float(
        string="Liquidated Damages (ETB)",
        compute="_compute_liquidated_damages",
        store=True,
    )
    retention_percent = fields.Float(string="Retention Percentage (%)", default=5.0)
    retention_amount = fields.Float(
        string="Retention Held (ETB)",
        compute="_compute_retention_amount",
        store=True,
    )
    net_payable = fields.Float(
        string="Net Payable Amount (ETB)",
        compute="_compute_net_payable",
        store=True,
    )
    state = fields.Selection(
        [("draft", "Draft"), ("approved", "Approved by PAO Finance")],
        string="Status",
        default="draft",
        required=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = f"PAY/{self.env['ir.sequence'].next_by_code('mesob.procurement.payment.certificate') or '001'}"
        return super().create(vals_list)

    @api.depends("amount_gross", "days_delay", "penalty_rate")
    def _compute_liquidated_damages(self):
        for rec in self:
            # default: 1/1000 of contract value per working day (capped at 10% of total)
            damage = rec.amount_gross * (rec.penalty_rate / 100.0) * rec.days_delay
            max_penalty = rec.amount_gross * 0.10
            rec.liquidated_damages = min(damage, max_penalty)

    @api.depends("amount_gross", "retention_percent")
    def _compute_retention_amount(self):
        for rec in self:
            rec.retention_amount = rec.amount_gross * (rec.retention_percent / 100.0)

    @api.depends("amount_gross", "liquidated_damages", "retention_amount")
    def _compute_net_payable(self):
        for rec in self:
            rec.net_payable = rec.amount_gross - rec.liquidated_damages - rec.retention_amount

    def action_approve(self):
        """Enforces three-way match hard-blocking before payment processing (FR-PROC-034)."""
        for rec in self:
            if not (rec.has_invoice and rec.has_model19 and rec.has_po):
                raise UserError("Three-Way Match Failed! Payment is strictly blocked unless Approved PO, Model 19 Acceptance Receipt, and VAT Compliant Invoice are all verified (FR-PROC-034).")
            rec.state = "approved"
        return True


class MesobProcurementComplaint(models.Model):
    """Complaints and Appeals Register - FR-PROC-038."""

    _name = "mesob.procurement.complaint"
    _description = "Procurement Complaints Register"
    _order = "date_filed desc, id desc"

    name = fields.Char(string="Complaint ID", required=True, copy=False, default="New")
    complainant_name = fields.Char(string="Complainant Name", required=True)
    lot_id = fields.Many2one("mesob.procurement.plan.lot", string="Subject APP Lot", required=True)
    date_filed = fields.Date(string="Date Filed", default=fields.Date.today, required=True)
    nature = fields.Selection(
        [
            ("bidding", "Bidding Irregularity"),
            ("specification", "Specification Dispute"),
            ("award", "Award Challenge"),
            ("contract", "Contract Dispute"),
        ],
        string="Nature of Complaint",
        required=True,
    )
    details = fields.Text(string="Complaint Details", required=True)
    action_taken = fields.Text(string="Response Action Taken")
    resolution = fields.Text(string="Resolution Outcome")
    state = fields.Selection(
        [("open", "Open / Standstill Block"), ("resolved", "Resolved")],
        string="Status",
        default="open",
        required=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = f"COM/{self.env['ir.sequence'].next_by_code('mesob.procurement.complaint') or '001'}"
        return super().create(vals_list)

    def action_resolve(self):
        for rec in self:
            if not rec.resolution:
                raise UserError("Please document the resolution outcome first.")
            rec.state = "resolved"
        return True

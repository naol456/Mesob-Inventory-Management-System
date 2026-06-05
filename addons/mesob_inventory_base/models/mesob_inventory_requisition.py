from odoo import api, fields, models
from odoo.exceptions import UserError


class MesobInventoryRequisition(models.Model):
    """Stores Requisition (Model 20).

    Raised by user departments and approved by PAO before stock issue.
    Supports three issue modes: imprest, replacement, and non-stock.
    (SRS: FR-ISSUE-001, FR-ISSUE-002, FR-ISSUE-003)
    """

    _name = "mesob.inventory.requisition"
    _description = "Stores Requisition (Model 20)"
    _order = "requested_on desc, id desc"

    name = fields.Char(
        string="Requisition Reference",
        required=True,
        index=True,
        default=lambda self: self.env["ir.sequence"].next_by_code(
            "mesob.inventory.requisition"
        ) or "New",
        copy=False,
        readonly=True,
        help="Auto-generated controlled reference number.",
    )

    # ── Issue Mode (FR-ISSUE-001) ───────────────────────────────────────

    issue_mode = fields.Selection(
        [
            ("imprest", "Imprest Basis"),
            ("replacement", "Replacement Issue"),
            ("non_stock", "Non-Stock Issue"),
        ],
        string="Issue Mode",
        required=True,
        default="imprest",
        help=(
            "Imprest: scheduled periodic issue. "
            "Replacement: replace consumed items. "
            "Non-stock: one-time special issue."
        ),
    )

    # ── Requester Info ──────────────────────────────────────────────────

    requested_by_id = fields.Many2one(
        "res.users",
        string="Requested By",
        required=True,
        default=lambda self: self.env.user,
    )
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
        help="Department requesting the materials.",
    )
    requested_on = fields.Date(
        string="Requested On",
        required=True,
        default=fields.Date.today,
    )

    # ── Approval Info ───────────────────────────────────────────────────

    approved_by_id = fields.Many2one(
        "res.users",
        string="Approved By (PAO)",
        readonly=True,
        copy=False,
    )
    approved_on = fields.Date(
        string="Approved On",
        readonly=True,
        copy=False,
    )
    rejection_reason = fields.Text(
        string="Rejection Reason",
        readonly=True,
        copy=False,
    )

    # ── State Machine ───────────────────────────────────────────────────

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("issued", "Issued"),
            ("received", "Received"),
            ("cancelled", "Cancelled"),
        ],
        required=True,
        default="draft",
        copy=False,
        index=True,
        tracking=True,
    )

    # ── Lines ───────────────────────────────────────────────────────────

    line_ids = fields.One2many(
        "mesob.inventory.requisition.line",
        "requisition_id",
        string="Requisition Lines",
        copy=True,
    )

    # ── Issue Vouchers ──────────────────────────────────────────────────

    issue_voucher_ids = fields.One2many(
        "mesob.inventory.issue.voucher",
        "requisition_id",
        string="Issue Vouchers",
        readonly=True,
    )

    issue_voucher_count = fields.Integer(
        string="Issue Voucher Count",
        compute="_compute_issue_voucher_count",
    )

    note = fields.Text(string="Internal Notes")

    # ── Computed Fields ─────────────────────────────────────────────────

    @api.depends("issue_voucher_ids")
    def _compute_issue_voucher_count(self):
        for record in self:
            record.issue_voucher_count = len(record.issue_voucher_ids)

    # ── Actions ─────────────────────────────────────────────────────────

    def action_submit(self):
        """Submit requisition for PAO approval."""
        for record in self:
            if record.state != "draft":
                raise UserError("Only draft requisitions can be submitted.")
            if not record.line_ids:
                raise UserError("Add at least one line before submitting.")
            record.state = "submitted"
        return True

    def action_approve(self):
        """PAO approves the requisition (FR-ISSUE-002)."""
        for record in self:
            if record.state != "submitted":
                raise UserError("Only submitted requisitions can be approved.")
            record.approved_by_id = self.env.user
            record.approved_on = fields.Date.today()
            record.state = "approved"
        return True

    def action_reject(self):
        """PAO rejects the requisition with reason."""
        for record in self:
            if record.state != "submitted":
                raise UserError("Only submitted requisitions can be rejected.")
            record.state = "rejected"
        return True

    def action_set_to_draft(self):
        """Reset to draft for corrections."""
        for record in self:
            if record.state not in ("rejected", "cancelled"):
                raise UserError(
                    "Only rejected or cancelled requisitions can be reset to draft."
                )
            record.approved_by_id = False
            record.approved_on = False
            record.rejection_reason = False
            record.state = "draft"
        return True

    def action_cancel(self):
        """Cancel the requisition."""
        for record in self:
            if record.state in ("cancelled",):
                raise UserError("Requisition is already cancelled.")
            if record.state in ("issued", "received"):
                raise UserError(
                    "Cannot cancel requisition that has been issued. "
                    "Please cancel the issue voucher first."
                )
            record.state = "cancelled"
        return True

    def action_create_issue_voucher(self):
        """Create Issue Voucher (Model 22) from approved requisition."""
        self.ensure_one()
        
        if self.state != "approved":
            raise UserError("Only approved requisitions can generate issue vouchers.")
        
        if not self.line_ids:
            raise UserError("Cannot create issue voucher: no requisition lines found.")
        
        # Create issue voucher
        voucher_vals = {
            "requisition_id": self.id,
            "issue_date": fields.Date.today(),
            "issued_by_id": self.env.user.id,
            "line_ids": [],
        }
        
        # Copy requisition lines to issue voucher lines
        for req_line in self.line_ids:
            # If line has specific item, use it
            if req_line.item_id:
                voucher_vals["line_ids"].append((0, 0, {
                    "item_id": req_line.item_id.id,
                    "quantity_issued": req_line.quantity,
                    "uom_id": req_line.uom_id.id if req_line.uom_id else req_line.item_id.uom_id.id,
                    "note": req_line.note,
                }))
            # If line has classifications, find available items
            elif req_line.major_classification_id:
                # Build domain for finding items
                domain = [
                    ('classification_id', '=', req_line.major_classification_id.id),
                    ('active', '=', True)
                ]
                if req_line.sub_classification_id:
                    domain.append(('sub_classification_id', '=', req_line.sub_classification_id.id))
                
                # Find all items matching the classification
                all_items = self.env['mesob.inventory.item'].search(domain)
                
                if not all_items:
                    raise UserError(
                        f"No items found for Major Classification "
                        f"'{req_line.major_classification_id.name}'"
                        f"{(' / Sub ' + req_line.sub_classification_id.name) if req_line.sub_classification_id else ''}. "
                        f"Please receive items first before creating issue voucher."
                    )
                
                # Filter out already issued items
                # Get items that have NOT been issued yet
                issued_item_ids = self.env['mesob.inventory.issue.voucher.line'].search([
                    ('voucher_id.state', 'in', ['issued', 'received'])
                ]).mapped('item_id').ids
                
                available_items = all_items.filtered(lambda i: i.id not in issued_item_ids)
                
                if not available_items:
                    raise UserError(
                        f"No available items found for classification "
                        f"'{req_line.major_classification_id.name}'"
                        f"{(' / Sub ' + req_line.sub_classification_id.name) if req_line.sub_classification_id else ''}. "
                        f"All items ({len(all_items)}) have already been issued."
                    )
                
                # Limit to requested quantity
                available_items = available_items[:int(req_line.quantity)]
                
                if len(available_items) < req_line.quantity:
                    raise UserError(
                        f"Not enough available items for classification "
                        f"'{req_line.major_classification_id.name}'. "
                        f"Requested: {int(req_line.quantity)}, Available: {len(available_items)}, "
                        f"Total: {len(all_items)}."
                    )
                
                # Create issue line for each available item
                for item in available_items:
                    voucher_vals["line_ids"].append((0, 0, {
                        "item_id": item.id,
                        "quantity_issued": 1.0,  # One unit per item
                        "uom_id": item.uom_id.id if item.uom_id else req_line.uom_id.id,
                        "note": req_line.note,
                    }))
            else:
                raise UserError(
                    "Invalid requisition line: must have either a specific item or classifications."
                )
        
        voucher = self.env["mesob.inventory.issue.voucher"].create(voucher_vals)
        
        # Update requisition state
        self.state = "issued"
        
        # Return action to open the new voucher
        return {
            "name": "Issue Voucher",
            "type": "ir.actions.act_window",
            "res_model": "mesob.inventory.issue.voucher",
            "res_id": voucher.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_view_issue_vouchers(self):
        """View related issue vouchers."""
        self.ensure_one()
        return {
            "name": "Issue Vouchers",
            "type": "ir.actions.act_window",
            "res_model": "mesob.inventory.issue.voucher",
            "view_mode": "list,form",
            "domain": [("requisition_id", "=", self.id)],
            "context": {"default_requisition_id": self.id},
        }

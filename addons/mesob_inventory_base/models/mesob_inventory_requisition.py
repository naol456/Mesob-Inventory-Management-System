from odoo import api, fields, models
from odoo.exceptions import UserError
from lxml import etree


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
    department_id = fields.Many2one(
        "mesob.department",
        string="Requesting Department",
        required=True,
        domain="[('active', '=', True)]",
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

    # ── View Customization ──────────────────────────────────────────────

    @api.model
    def get_view(self, view_id=None, view_type="form", **options):
        """Hide New button for PAO and Storekeeper on both list and form views.

        Only staff (group_mesob_inventory_user) may create requisitions.

        - list view:  create="0" removes the toolbar New button.
        - form view:  create="0" removes the New button in the breadcrumb
                      pager (the one visible when browsing an existing record).

        Uses lxml to safely set the attribute on the root node instead of
        fragile string replacement.
        """
        result = super().get_view(view_id, view_type, **options)

        if view_type in ("list", "form"):
            user = self.env.user
            is_pao = user.has_group("mesob_inventory_base.group_mesob_pao")
            is_storekeeper = user.has_group(
                "mesob_inventory_base.group_mesob_storekeeper"
            )
            is_stock_clerk = user.has_group(
                "mesob_inventory_base.group_mesob_stock_clerk"
            )

            if is_pao or is_storekeeper or is_stock_clerk:
                arch = result.get("arch", "")
                if isinstance(arch, str):
                    arch = arch.encode("utf-8")
                root = etree.fromstring(arch)
                root.set("create", "0")
                result["arch"] = etree.tostring(
                    root, encoding="unicode", pretty_print=False
                )

        return result

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

    def action_mark_received(self):
        """Mark requisition as received by requester.
        
        Also marks all related Issue Vouchers as received with the same user and date.
        """
        for record in self:
            if record.state != "issued":
                raise UserError(
                    "Only issued requisitions can be marked as received."
                )
            # Verify that the current user is the original requester
            if record.requested_by_id != self.env.user:
                raise UserError(
                    "Only the original requester can mark this requisition as received."
                )
            
            # Mark requisition as received
            record.state = "received"
            
            # Also mark all related Issue Vouchers as received
            for issue_voucher in record.issue_voucher_ids:
                if issue_voucher.state == "issued":
                    issue_voucher.write({
                        'state': 'received',
                        'received_by_id': self.env.user.id,
                        'received_on': fields.Date.today(),
                        'quantity_verified': True,
                        'inspection_confirmed': True,
                        'approval_verified': True,
                    })
        return True
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
            if record.state == "cancelled":
                raise UserError("Requisition is already cancelled.")
            if record.state in ("issued", "received"):
                raise UserError(
                    "Cannot cancel a requisition that has been issued. "
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

        voucher_vals = {
            "requisition_id": self.id,
            "issue_date": fields.Date.today(),
            "issued_by_id": self.env.user.id,
            "line_ids": [],
        }

        for req_line in self.line_ids:

            # ── Case 1: specific item on the line ──────────────────────
            if req_line.item_id:
                voucher_vals["line_ids"].append((0, 0, {
                    "item_id": req_line.item_id.id,
                    "quantity_issued": req_line.quantity,
                    "uom_id": (
                        req_line.uom_id.id
                        if req_line.uom_id
                        else req_line.item_id.uom_id.id
                    ),
                    "note": req_line.note,
                }))

            # ── Case 2: classification-only line ───────────────────────
            elif req_line.major_classification_id:
                domain = [
                    ("classification_id", "=", req_line.major_classification_id.id),
                    ("active", "=", True),
                ]
                if req_line.sub_classification_id:
                    domain.append((
                        "sub_classification_id",
                        "=",
                        req_line.sub_classification_id.id,
                    ))

                all_items = self.env["mesob.inventory.item"].search(domain)

                if not all_items:
                    sub_label = (
                        f" / Sub {req_line.sub_classification_id.name}"
                        if req_line.sub_classification_id
                        else ""
                    )
                    raise UserError(
                        f"No items found for Major Classification "
                        f"'{req_line.major_classification_id.name}'{sub_label}. "
                        "Please receive items first before creating an issue voucher."
                    )

                issued_item_ids = (
                    self.env["mesob.inventory.issue.voucher.line"]
                    .search([("voucher_id.state", "in", ["issued", "received"])])
                    .mapped("item_id")
                    .ids
                )

                available_items = all_items.filtered(
                    lambda i: i.id not in issued_item_ids
                )

                if not available_items:
                    sub_label = (
                        f" / Sub {req_line.sub_classification_id.name}"
                        if req_line.sub_classification_id
                        else ""
                    )
                    raise UserError(
                        f"No available items found for classification "
                        f"'{req_line.major_classification_id.name}'{sub_label}. "
                        f"All {len(all_items)} item(s) have already been issued."
                    )

                available_items = available_items[: int(req_line.quantity)]

                if len(available_items) < req_line.quantity:
                    raise UserError(
                        f"Not enough available items for classification "
                        f"'{req_line.major_classification_id.name}'. "
                        f"Requested: {int(req_line.quantity)}, "
                        f"Available: {len(available_items)}, "
                        f"Total: {len(all_items)}."
                    )

                for item in available_items:
                    voucher_vals["line_ids"].append((0, 0, {
                        "item_id": item.id,
                        "quantity_issued": 1.0,
                        "uom_id": (
                            item.uom_id.id if item.uom_id else req_line.uom_id.id
                        ),
                        "note": req_line.note,
                    }))

            # ── Case 3: invalid line ────────────────────────────────────
            else:
                raise UserError(
                    "Invalid requisition line: must have either a specific item "
                    "or a major classification."
                )

        voucher = self.env["mesob.inventory.issue.voucher"].create(voucher_vals)
        self.state = "issued"

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
from odoo import api, fields, models
from odoo.exceptions import UserError


class MesobInventoryModel19(models.Model):
    """Receipt for Articles/Property (Model 19).

    Auto-generated when a receiving order is accepted.
    Tracks four-copy distribution as required by FDRE procedures.
    (SRS: FR-REC-005, FR-REC-006, FR-REC-007)
    """

    _name = "mesob.inventory.model19"
    _description = "Receipt for Articles/Property (Model 19)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date desc, id desc"
    _rec_name = "name"

    # ── Reference ───────────────────────────────────────────────────
    name = fields.Char(
        string="Model 19 Reference",
        required=True,
        index=True,
        default=lambda self: self.env["ir.sequence"].next_by_code(
            "mesob.inventory.model19"
        ) or "New",
        copy=False,
        readonly=True,
    )

    # ── Source ──────────────────────────────────────────────────────
    receiving_id = fields.Many2one(
        "mesob.inventory.receiving",
        string="Receiving Order",
        readonly=True,
        index=True,
        help="Source receiving order that generated this Model 19.",
    )

    date = fields.Date(
        string="Receipt Date",
        required=True,
        default=fields.Date.today,
    )

    supplier_id = fields.Many2one(
        "res.partner",
        string="Supplier / Source",
        help="Supplier, donor, or returning department.",
    )

    # ── Department Return Flag (FR-REC-007) ────────────────────────
    is_no_payment = fields.Boolean(
        string="No Payment (Dept Return)",
        default=False,
        help="For department returns — no payment will be effected. "
             "Accounts copy retained with pad (FR-REC-007).",
    )

    # ── Copy Distribution (FR-REC-006) ─────────────────────────────
    copy_accounts = fields.Selection(
        [("pending", "Pending"), ("distributed", "Distributed")],
        string="Original → Accounts Unit",
        default="pending",
        help="Original with supplier invoice → Accounts Unit.",
    )
    copy_stock_clerk = fields.Selection(
        [("pending", "Pending"), ("distributed", "Distributed")],
        string="Duplicate → Stock Clerk",
        default="pending",
        help="Duplicate copy → Stock Clerk for posting.",
    )
    copy_supplier = fields.Selection(
        [("pending", "Pending"), ("distributed", "Distributed")],
        string="Triplicate → Supplier",
        default="pending",
        help="Triplicate copy → Supplier/deliverer.",
    )
    copy_storekeeper = fields.Selection(
        [("pending", "Pending"), ("distributed", "Distributed")],
        string="Book Copy → Storekeeper",
        default="pending",
        help="Book copy retained by Storekeeper.",
    )

    all_copies_distributed = fields.Boolean(
        string="All Copies Distributed",
        compute="_compute_all_copies_distributed",
    )

    # ── Lines ──────────────────────────────────────────────────────
    line_ids = fields.One2many(
        "mesob.inventory.model19.line",
        "model19_id",
        string="Receipt Lines",
    )

    # ── State ──────────────────────────────────────────────────────
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("distributed", "Distributed"),
        ],
        required=True,
        default="draft",
        copy=False,
        index=True,
        tracking=True,
    )

    note = fields.Text(string="Notes")

    # ── Totals ─────────────────────────────────────────────────────
    total_amount = fields.Float(
        string="Total Amount",
        compute="_compute_total_amount",
        store=True,
    )

    # ── Computed ───────────────────────────────────────────────────

    @api.depends("line_ids.total_price")
    def _compute_total_amount(self):
        for rec in self:
            rec.total_amount = sum(rec.line_ids.mapped("total_price"))

    @api.depends(
        "copy_accounts", "copy_stock_clerk",
        "copy_supplier", "copy_storekeeper"
    )
    def _compute_all_copies_distributed(self):
        for rec in self:
            rec.all_copies_distributed = all([
                rec.copy_accounts == "distributed",
                rec.copy_stock_clerk == "distributed",
                rec.copy_supplier == "distributed",
                rec.copy_storekeeper == "distributed",
            ])

    # ── Actions ────────────────────────────────────────────────────

    def action_confirm(self):
        """Confirm the Model 19 receipt."""
        for rec in self:
            if rec.state != "draft":
                raise UserError("Only draft receipts can be confirmed.")
            rec.state = "confirmed"
        return True

    def action_mark_distributed(self):
        """Mark all copies as distributed."""
        for rec in self:
            if rec.state != "confirmed":
                raise UserError(
                    "Only confirmed receipts can be marked as distributed."
                )
            if not rec.all_copies_distributed:
                raise UserError(
                    "Please mark all four copies as distributed first."
                )
            rec.state = "distributed"
        return True

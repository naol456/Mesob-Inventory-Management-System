from odoo import api, fields, models
from odoo.exceptions import UserError
from lxml import etree


class MesobInventoryModel19(models.Model):
    """Receipt for Articles/Property (Model 19).

    Auto-generated when a receiving order is accepted.
    Tracks four-copy distribution as required by FDRE procedures.
    (SRS: FR-REC-005, FR-REC-006, FR-REC-007)
    
    AUTO-027: Model 19 Auto-Generation & Three-Way Match Trigger
    - Auto-generates when receiving is completed and accepted
    - Automatically posts to Bin Card and Stock Record Card via AUTO-049
    - Triggers three-way match for payment processing (AUTO-029)
    - Tracks four-copy distribution: Accounts, Stock clerk, Supplier, Storekeeper
    """

    _name = "mesob.inventory.model19"
    _description = "Receipt for Articles/Property (Model 19)"
    _inherit = ['mesob.stock.movement.mixin', 'mail.thread', 'mail.activity.mixin']
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

    # ── View Customization ──────────────────────────────────────────

    @api.model
    def get_view(self, view_id=None, view_type="form", **options):
        """Hide New button for PAO and Stock Clerk on both list and form views.
        
        Model 19 receipts are auto-generated from Receiving Orders.
        Only Storekeeper can manually create (if needed).
        """
        result = super().get_view(view_id, view_type, **options)
        
        if view_type in ("list", "form"):
            user = self.env.user
            is_pao = user.has_group("mesob_inventory_base.group_mesob_pao")
            is_stock_clerk = user.has_group("mesob_inventory_base.group_mesob_stock_clerk")
            
            if is_pao or is_stock_clerk:
                arch = result.get("arch", "")
                if isinstance(arch, str):
                    arch = arch.encode("utf-8")
                root = etree.fromstring(arch)
                root.set("create", "0")
                result["arch"] = etree.tostring(root, encoding="unicode", pretty_print=False)
        
        return result

    # ── Actions ────────────────────────────────────────────────────

    def action_confirm(self):
        """AUTO-027: Confirm Model 19 and auto-post stock movements.
        
        Compliance: FR-REC-005, FR-PROC-033, FR-RECARD-001, FR-RECARD-002
        """
        for rec in self:
            if rec.state != "draft":
                raise UserError("Only draft receipts can be confirmed.")
            
            # AUTO-027: Auto-post stock movements to Bin Card and Stock Record Card
            if not rec.stock_movements_posted and rec.line_ids:
                movements_data = []
                for line in rec.line_ids:
                    if line.item_id and line.quantity_accepted > 0:
                        movements_data.append({
                            'item_id': line.item_id.id,
                            'quantity': line.quantity_accepted,
                            'transaction_type': 'receipt',
                            'unit_cost': line.unit_price or 0.0,
                            'reference': rec.name,
                        })
                
                if movements_data:
                    rec.action_post_stock_movements(movements_data)
            
            rec.state = "confirmed"
            
            # AUTO-027: Trigger three-way match notification
            rec.message_post(
                body=f"""<div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px;">
                    <h4>✅ Model 19 Confirmed - Ready for Payment Match</h4>
                    <p><strong>Reference:</strong> {rec.name}</p>
                    <p><strong>Date:</strong> {rec.date}</p>
                    <p><strong>Supplier:</strong> {rec.supplier_id.name if rec.supplier_id else 'N/A'}</p>
                    <p><strong>Lines:</strong> {len(rec.line_ids)}</p>
                    <p><em>AUTO-027: Stock movements posted. This receipt is now available for three-way match (PO + Model 19 + Invoice).</em></p>
                </div>""",
                subject='Model 19 Confirmed - Three-Way Match Ready',
                message_type='comment'
            )
        
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

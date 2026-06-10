from odoo import api, fields, models
from odoo.exceptions import UserError
from lxml import etree


class MesobInventoryDSR(models.Model):
    """Damage/Shortage Report (DSR).

    Auto-generated when a receiving order has rejected items.
    Tracks four-copy distribution and discrepancy details.
    (SRS: FR-REC-008, FR-REC-009)
    """

    _name = "mesob.inventory.dsr"
    _description = "Damage/Shortage Report (DSR)"
    _order = "date desc, id desc"
    _rec_name = "name"

    # ── Reference ───────────────────────────────────────────────────
    name = fields.Char(
        string="DSR Reference",
        required=True,
        index=True,
        default=lambda self: self.env["ir.sequence"].next_by_code(
            "mesob.inventory.dsr"
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
        help="Source receiving order that generated this DSR.",
    )

    date = fields.Date(
        string="Report Date",
        required=True,
        default=fields.Date.today,
    )

    supplier_id = fields.Many2one(
        "res.partner",
        string="Supplier",
        help="Supplier whose goods were rejected.",
    )

    # ── Copy Distribution (FR-REC-008) ─────────────────────────────
    copy_supplier = fields.Selection(
        [("pending", "Pending"), ("distributed", "Distributed")],
        string="Original → Supplier",
        default="pending",
        help="Original accompanies rejected goods back to supplier.",
    )
    copy_accounts = fields.Selection(
        [("pending", "Pending"), ("distributed", "Distributed")],
        string="Duplicate → Accounts/Finance",
        default="pending",
        help="Duplicate copy → Accounts/Finance unit.",
    )
    copy_procurement = fields.Selection(
        [("pending", "Pending"), ("distributed", "Distributed")],
        string="Triplicate → Procurement Officer",
        default="pending",
        help="Triplicate copy → Procurement Officer.",
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
        "mesob.inventory.dsr.line",
        "dsr_id",
        string="DSR Lines",
    )

    # ── State ──────────────────────────────────────────────────────
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("returned", "Goods Returned"),
        ],
        required=True,
        default="draft",
        copy=False,
        index=True,
        tracking=True,
    )

    note = fields.Text(string="Notes")

    # ── Computed ───────────────────────────────────────────────────

    @api.depends(
        "copy_supplier", "copy_accounts",
        "copy_procurement", "copy_storekeeper"
    )
    def _compute_all_copies_distributed(self):
        for rec in self:
            rec.all_copies_distributed = all([
                rec.copy_supplier == "distributed",
                rec.copy_accounts == "distributed",
                rec.copy_procurement == "distributed",
                rec.copy_storekeeper == "distributed",
            ])

    # ── View Customization ──────────────────────────────────────────

    @api.model
    def get_view(self, view_id=None, view_type="form", **options):
        """Hide New button for PAO and Stock Clerk on both list and form views.
        
        DSRs are auto-generated from Receiving Orders when items are rejected.
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
        """Confirm the DSR."""
        for rec in self:
            if rec.state != "draft":
                raise UserError("Only draft DSRs can be confirmed.")
            rec.state = "confirmed"
        return True

    def action_mark_returned(self):
        """Mark goods as returned to supplier."""
        for rec in self:
            if rec.state != "confirmed":
                raise UserError(
                    "Only confirmed DSRs can be marked as returned."
                )
            rec.state = "returned"
        return True

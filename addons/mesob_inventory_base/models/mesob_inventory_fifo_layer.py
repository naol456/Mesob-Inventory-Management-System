from odoo import api, fields, models


class MesobInventoryFifoLayer(models.Model):
    """FIFO Cost Layer for proper First-In-First-Out valuation.
    
    FR-VAL-001: Value stock using FIFO for costing of issues and ending balance.
    Each receipt creates a new layer; issues consume from oldest layers first.
    """

    _name = "mesob.inventory.fifo.layer"
    _description = "FIFO Cost Layer"
    _order = "date asc, id asc"

    # ── Item Reference ──────────────────────────────────────────────
    item_id = fields.Many2one(
        "mesob.inventory.item",
        string="Stock Item",
        required=True,
        index=True,
        ondelete="restrict",
    )

    # ── Layer Details ───────────────────────────────────────────────
    date = fields.Date(
        string="Receipt Date",
        required=True,
        index=True,
        help="Date when this layer was created (receipt date).",
    )

    quantity = fields.Float(
        string="Original Quantity",
        digits="Product Unit of Measure",
        required=True,
        help="Original quantity received in this layer.",
    )

    remaining_quantity = fields.Float(
        string="Remaining Quantity",
        digits="Product Unit of Measure",
        required=True,
        help="Quantity still available in this layer (not yet issued).",
    )

    unit_price = fields.Monetary(
        string="Unit Price",
        currency_field="currency_id",
        required=True,
        help="Unit cost for this layer (including freight, duties, etc.).",
    )
    
    is_estimated_cost = fields.Boolean(
        string="Estimated Cost",
        default=False,
        help="True if cost is estimated (not actual). FR-VAL-003",
    )
    
    cost_note = fields.Char(
        string="Cost Note",
        help="Note about cost estimation or source",
    )

    total_value = fields.Monetary(
        string="Total Value",
        currency_field="currency_id",
        compute="_compute_total_value",
        store=True,
        help="Total value of this layer (quantity × unit price).",
    )

    remaining_value = fields.Monetary(
        string="Remaining Value",
        currency_field="currency_id",
        compute="_compute_remaining_value",
        store=True,
        help="Value of remaining quantity in this layer.",
    )

    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )

    # ── Reference ───────────────────────────────────────────────────
    reference = fields.Char(
        string="Reference",
        help="Document reference (Model 19, etc.).",
    )

    stock_record_card_id = fields.Many2one(
        "mesob.inventory.stock.record.card",
        string="Stock Record Card Entry",
        ondelete="cascade",
        help="The stock record card entry that created this layer.",
    )

    # ── Status ──────────────────────────────────────────────────────
    is_fully_consumed = fields.Boolean(
        string="Fully Consumed",
        compute="_compute_is_fully_consumed",
        store=True,
        help="True if this layer has been fully consumed.",
    )

    # ── Computed Fields ─────────────────────────────────────────────
    @api.depends("quantity", "unit_price")
    def _compute_total_value(self):
        for record in self:
            record.total_value = record.quantity * record.unit_price

    @api.depends("remaining_quantity", "unit_price")
    def _compute_remaining_value(self):
        for record in self:
            record.remaining_value = record.remaining_quantity * record.unit_price

    @api.depends("remaining_quantity")
    def _compute_is_fully_consumed(self):
        for record in self:
            record.is_fully_consumed = record.remaining_quantity <= 0.0

    # ── Constraints ─────────────────────────────────────────────────
    _sql_constraints = [
        (
            "check_quantities",
            "CHECK(quantity >= 0 AND remaining_quantity >= 0 AND remaining_quantity <= quantity)",
            "Quantities must be valid (remaining <= original).",
        ),
        (
            "check_unit_price",
            "CHECK(unit_price >= 0)",
            "Unit price must be non-negative.",
        ),
    ]

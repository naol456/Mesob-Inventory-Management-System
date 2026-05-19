from odoo import api, fields, models
from odoo.exceptions import ValidationError


class MesobInventoryReceivingLine(models.Model):
    """Individual line item on a Receiving Order.

    Each line references an inventory item and tracks expected,
    received, accepted, and rejected quantities with rejection
    reasons for the inspection workflow.
    (SRS: FR-REC-003, FR-REC-009)
    """

    _name = "mesob.inventory.receiving.line"
    _description = "Receiving Order Line"

    receiving_id = fields.Many2one(
        "mesob.inventory.receiving",
        required=True,
        ondelete="cascade",
    )
    
    # Related field to access parent state
    state = fields.Selection(
        related="receiving_id.state",
        string="Status",
        store=False,
        readonly=True,
    )

    item_id = fields.Many2one(
        "mesob.inventory.item",
        string="Item",
        help="Stock item being received.",
    )

    description = fields.Char(
        string="Description",
        help="Description of the item (for items not yet coded).",
    )

    qty_expected = fields.Float(
        string="Qty Expected",
        default=0.0,
        help="Quantity per purchase order or packing slip.",
    )

    qty_received = fields.Float(
        string="Qty Received",
        default=0.0,
        help="Actual quantity received at unloading.",
    )

    qty_accepted = fields.Float(
        string="Qty Accepted",
        default=0.0,
        help="Quantity passing inspection (for Model 19).",
    )

    qty_rejected = fields.Float(
        string="Qty Rejected",
        default=0.0,
        help="Quantity failing inspection (for DSR).",
    )

    uom_id = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
    )

    unit_price = fields.Float(
        string="Unit Price",
        default=0.0,
        help="Unit price for stock valuation.",
    )

    total_price = fields.Float(
        string="Total Price",
        compute="_compute_total_price",
        store=True,
    )

    # ── Rejection Details (FR-REC-009) ─────────────────────────────
    rejection_reason = fields.Selection(
        [
            ("damaged", "Damaged"),
            ("shortage", "Shortage"),
            ("overage", "Overage"),
            ("wrong_quality", "Not Right Quality"),
        ],
        string="Rejection Reason",
        help="Type of discrepancy found during inspection (FR-REC-009).",
    )

    rejection_notes = fields.Text(
        string="Rejection Notes",
        help="Detailed description of the rejection reason.",
    )

    # ── Computed ───────────────────────────────────────────────────

    @api.depends("qty_accepted", "unit_price")
    def _compute_total_price(self):
        for line in self:
            line.total_price = line.qty_accepted * line.unit_price

    # ── Validation ─────────────────────────────────────────────────

    @api.constrains("qty_accepted", "qty_rejected", "qty_received")
    def _check_quantities(self):
        for line in self:
            if line.qty_accepted < 0 or line.qty_rejected < 0:
                raise ValidationError(
                    "Accepted and rejected quantities cannot be negative."
                )
            if line.qty_received < 0:
                raise ValidationError(
                    "Received quantity cannot be negative."
                )
            # Allow accepted + rejected to exceed received (will auto-adjust received)
            # This makes the workflow more flexible

    @api.onchange("item_id")
    def _onchange_item_id(self):
        """Auto-fill description and UoM from item master."""
        if self.item_id:
            if not self.description:
                self.description = self.item_id.name
            if not self.uom_id and self.item_id.uom_id:
                self.uom_id = self.item_id.uom_id

    @api.onchange("qty_received")
    def _onchange_qty_received(self):
        """Auto-fill qty_accepted when qty_received is entered."""
        if self.qty_received > 0 and self.qty_accepted == 0 and self.qty_rejected == 0:
            # Auto-accept all received items by default
            self.qty_accepted = self.qty_received

    @api.onchange("qty_expected")
    def _onchange_qty_expected(self):
        """Auto-fill qty_received and qty_accepted with expected quantity."""
        if self.qty_expected > 0:
            if self.qty_received == 0:
                self.qty_received = self.qty_expected
            if self.qty_accepted == 0 and self.qty_rejected == 0:
                self.qty_accepted = self.qty_expected
    
    @api.onchange("qty_accepted", "qty_rejected")
    def _onchange_accepted_rejected(self):
        """Auto-adjust qty_received when accepted/rejected are changed."""
        if self.qty_accepted > 0 or self.qty_rejected > 0:
            total = self.qty_accepted + self.qty_rejected
            if total > self.qty_received:
                self.qty_received = total

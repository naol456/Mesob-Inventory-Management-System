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
            if (line.qty_accepted + line.qty_rejected) > line.qty_received and line.qty_received > 0:
                raise ValidationError(
                    "Accepted + Rejected quantities cannot exceed "
                    "the received quantity."
                )

    @api.onchange("item_id")
    def _onchange_item_id(self):
        """Auto-fill description and UoM from item master."""
        if self.item_id:
            if not self.description:
                self.description = self.item_id.name
            if not self.uom_id and self.item_id.uom_id:
                self.uom_id = self.item_id.uom_id

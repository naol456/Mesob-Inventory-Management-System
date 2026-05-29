from odoo import api, fields, models
from odoo.exceptions import ValidationError


class MesobGatePassLine(models.Model):
    """Gate Pass Line Item.

    Individual line items on a Gate Pass, representing materials being dispatched.
    Supports auto-population from Issue Voucher lines and manual entry.
    """

    _name = "mesob.gate.pass.line"
    _description = "Gate Pass Line Item"
    _order = "gate_pass_id, sequence, id"

    # ── Core Fields ─────────────────────────────────────────────────

    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Sequence for ordering line items.",
    )

    gate_pass_id = fields.Many2one(
        "mesob.gate.pass",
        string="Gate Pass",
        required=True,
        ondelete="cascade",
        index=True,
    )

    item_id = fields.Many2one(
        "mesob.inventory.item",
        string="Item",
        required=True,
        index=True,
        help="Inventory item being dispatched.",
    )

    description = fields.Char(
        string="Description",
        help="Item description (auto-filled from item master).",
    )

    quantity = fields.Float(
        string="Quantity",
        required=True,
        default=1.0,
        digits=(16, 2),
        help="Quantity being dispatched.",
    )

    uom_id = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
        help="Unit of measure for this line item.",
    )

    serial_numbers = fields.Text(
        string="Serial Numbers",
        help="Serial numbers for serialized/controlled items.",
    )

    remarks = fields.Char(
        string="Remarks",
        help="Additional remarks for this line item.",
    )

    # ── Constraints ─────────────────────────────────────────────────

    @api.constrains("quantity")
    def _check_quantity_positive(self):
        """Ensure quantity is positive."""
        for record in self:
            if record.quantity <= 0:
                raise ValidationError(
                    f"Quantity must be positive. Current value: {record.quantity}"
                )

    # ── Onchange Methods ────────────────────────────────────────────

    @api.onchange("item_id")
    def _onchange_item_id(self):
        """Auto-fill description and UOM from item master."""
        if self.item_id:
            self.description = self.item_id.name
            if self.item_id.uom_id:
                self.uom_id = self.item_id.uom_id

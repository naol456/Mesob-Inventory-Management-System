from odoo import api, fields, models


class MesobInventoryModel19Line(models.Model):
    """Line item on a Model 19 receipt document.

    Each line records an accepted item with quantity, unit price,
    and computed total value for stock valuation purposes.
    """

    _name = "mesob.inventory.model19.line"
    _description = "Model 19 Line"

    model19_id = fields.Many2one(
        "mesob.inventory.model19",
        required=True,
        ondelete="cascade",
    )

    item_id = fields.Many2one(
        "mesob.inventory.item",
        string="Item",
    )

    description = fields.Char(
        string="Description",
        help="Item description.",
    )

    quantity = fields.Float(
        string="Quantity Accepted",
        required=True,
        default=0.0,
    )

    uom_id = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
    )

    unit_price = fields.Float(
        string="Unit Price",
        default=0.0,
    )

    total_price = fields.Float(
        string="Total Price",
        compute="_compute_total_price",
        store=True,
    )

    @api.depends("quantity", "unit_price")
    def _compute_total_price(self):
        for line in self:
            line.total_price = line.quantity * line.unit_price

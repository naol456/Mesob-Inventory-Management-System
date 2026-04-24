from odoo import fields, models


class MesobInventoryRequisitionLine(models.Model):
    """Individual line item on a Stores Requisition (Model 20).

    Each line references an inventory item and specifies the quantity
    requested along with the unit of measure.
    """

    _name = "mesob.inventory.requisition.line"
    _description = "Stores Requisition Line"

    requisition_id = fields.Many2one(
        "mesob.inventory.requisition",
        required=True,
        ondelete="cascade",
    )
    item_id = fields.Many2one(
        "mesob.inventory.item",
        string="Item",
        required=True,
    )
    quantity = fields.Float(
        string="Quantity Requested",
        required=True,
        default=1.0,
    )
    uom_id = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
        help="Unit of measure for this requisition line.",
    )
    note = fields.Char(string="Remarks")

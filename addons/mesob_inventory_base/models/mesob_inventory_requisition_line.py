from odoo import fields, models


class MesobInventoryRequisitionLine(models.Model):
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
    quantity = fields.Float(required=True, default=1.0)
    uom_name = fields.Char(string="UoM")
    note = fields.Char()

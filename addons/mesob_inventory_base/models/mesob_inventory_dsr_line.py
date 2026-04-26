from odoo import fields, models


class MesobInventoryDSRLine(models.Model):
    """Line item on a Damage/Shortage Report (DSR).

    Each line records a rejected item with quantity, discrepancy type,
    and detailed notes explaining the rejection reason.
    (SRS: FR-REC-009)
    """

    _name = "mesob.inventory.dsr.line"
    _description = "DSR Line"

    dsr_id = fields.Many2one(
        "mesob.inventory.dsr",
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
        string="Quantity Rejected",
        required=True,
        default=0.0,
    )

    uom_id = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
    )

    discrepancy_type = fields.Selection(
        [
            ("damaged", "Damaged"),
            ("shortage", "Shortage"),
            ("overage", "Overage"),
            ("wrong_quality", "Not Right Quality"),
        ],
        string="Discrepancy Type",
        required=True,
        default="damaged",
        help="Type of discrepancy found (FR-REC-009).",
    )

    notes = fields.Text(
        string="Discrepancy Details",
        help="Detailed description of the discrepancy.",
    )

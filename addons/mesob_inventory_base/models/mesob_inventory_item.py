import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError


_ITEM_CODE_PATTERN = re.compile(r"^\d{4}-\d{3}-\d{3}$")


class MesobInventoryItem(models.Model):
    _name = "mesob.inventory.item"
    _description = "Inventory Item"
    _rec_name = "item_code"

    _item_code_unique = models.Constraint(
        "UNIQUE(item_code)",
        "Item Code must be unique.",
    )

    _item_code_format = models.Constraint(
        "CHECK(item_code ~ '^[0-9]{4}-[0-9]{3}-[0-9]{3}$')",
        "Item Code must follow the format ####-###-### (digits and dashes).",
    )

    item_code = fields.Char(
        string="Item Code",
        required=True,
        index=True,
        copy=False,
        help="FDRE item code format: ####-###-###",
    )
    name = fields.Char(required=True, index=True)
    description = fields.Text()
    active = fields.Boolean(default=True)

    @api.constrains("item_code")
    def _check_item_code_format(self):
        for record in self:
            if not record.item_code:
                continue
            if not _ITEM_CODE_PATTERN.fullmatch(record.item_code):
                raise ValidationError(
                    "Item Code must follow the format ####-###-### (digits and dashes)."
                )

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class MesobInventorySubClassification(models.Model):
    """Sub Classification / Sub Code under Major Classification.

    Each Sub Classification belongs to exactly one Major Classification
    and provides finer categorization for inventory items.
    Example: Major 3345 (Cleaning Materials) → Sub 4456 (Soap)
    """

    _name = "mesob.inventory.sub.classification"
    _description = "Sub Classification / Sub Code"
    _order = "major_classification_id, code"
    _rec_name = "name"

    _sql_constraints = [
        (
            'code_major_unique',
            'UNIQUE(code, major_classification_id)',
            'Sub Classification code must be unique within the same Major Classification.'
        ),
        (
            'code_format',
            "CHECK(code ~ '^[0-9]{3}$')",
            'Sub Classification code must be exactly 3 digits.'
        ),
    ]

    code = fields.Char(
        string="Sub Code",
        required=True,
        size=3,
        index=True,
        copy=False,
        help="3-digit sub classification code (e.g., 456).",
    )
    name = fields.Char(
        string="Name",
        required=True,
        help="Name of the sub classification (e.g., Soap).",
    )
    major_classification_id = fields.Many2one(
        comodel_name="mesob.inventory.major.classification",
        string="Major Classification",
        required=True,
        ondelete="restrict",
        index=True,
        help="Parent major classification this sub code belongs to.",
    )
    active = fields.Boolean(
        default=True,
        help="Inactive sub classifications are hidden from selection.",
    )
    is_fixed_asset = fields.Boolean(
        string="Fixed Asset",
        default=False,
        help="Check if this sub-classification represents fixed assets requiring individual item tracking.",
    )
    item_count = fields.Integer(
        string="Items",
        compute="_compute_item_count",
        help="Number of items using this sub classification.",
    )
    item_ids = fields.One2many(
        comodel_name="mesob.inventory.item",
        inverse_name="sub_classification_id",
        string="Items",
    )
    bin_card_ids = fields.One2many(
        comodel_name="mesob.bin.card",
        inverse_name="sub_classification_id",
        string="Bin Card Transactions",
    )
    stock_record_ids = fields.One2many(
        comodel_name="mesob.stock.record.card",
        inverse_name="sub_classification_id",
        string="Stock Record Ledger",
    )

    @api.depends("code", "name", "major_classification_id")
    def _compute_display_name(self):
        for rec in self:
            if rec.code and rec.name and rec.major_classification_id:
                rec.display_name = f"[{rec.major_classification_id.code}-{rec.code}] {rec.name}"
            elif rec.code and rec.name:
                rec.display_name = f"[{rec.code}] {rec.name}"
            else:
                rec.display_name = rec.name or rec.code or ""

    def _compute_item_count(self):
        """Count items associated with this sub classification."""
        for rec in self:
            rec.item_count = self.env["mesob.inventory.item"].search_count(
                [("sub_classification_id", "=", rec.id)]
            )

    @api.constrains('code')
    def _check_code_format(self):
        """Validate that code is exactly 3 digits."""
        for rec in self:
            if rec.code and (len(rec.code) != 3 or not rec.code.isdigit()):
                raise ValidationError(
                    _("Sub Classification code must be exactly 3 digits. Got: %s") % rec.code
                )

    def action_view_items(self):
        """Open list of items belonging to this sub classification."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Items — {self.display_name}",
            "res_model": "mesob.inventory.item",
            "view_mode": "list,form",
            "domain": [("sub_classification_id", "=", self.id)],
            "context": {"default_sub_classification_id": self.id},
        }

    def action_view_bin_card_details(self):
        """Open the detailed form/ledger view of this sub-classification."""
        self.ensure_one()
        view_id = self.env.ref("mesob_inventory_base.view_mesob_sub_classification_form_ledger").id
        return {
            "type": "ir.actions.act_window",
            "name": f"Ledger — {self.name}",
            "res_model": "mesob.inventory.sub.classification",
            "view_mode": "form",
            "res_id": self.id,
            "view_id": view_id,
            "target": "current",
        }

    def action_view_items_stock_card(self):
        """Open the items list under this sub-classification in the stock card flow."""
        self.ensure_one()
        view_id = self.env.ref("mesob_inventory_base.view_mesob_inventory_item_kanban_stock_card").id
        return {
            "type": "ir.actions.act_window",
            "name": f"Items under {self.name}",
            "res_model": "mesob.inventory.item",
            "views": [(view_id, "kanban"), (False, "list")],
            "domain": [("sub_classification_id", "=", self.id)],
            "context": {
                "default_sub_classification_id": self.id,
            },
        }

    def action_view_stock_card_details(self):
        """Open the detailed Stock Card (Model 19) ledger form view for this sub-classification."""
        self.ensure_one()
        view_id = self.env.ref("mesob_inventory_base.view_mesob_sub_classification_form_stock_ledger").id
        return {
            "type": "ir.actions.act_window",
            "name": f"Stock Card — {self.name}",
            "res_model": "mesob.inventory.sub.classification",
            "view_mode": "form",
            "res_id": self.id,
            "view_id": view_id,
            "target": "current",
        }

from odoo import api, fields, models


class MesobInventoryMajorClassification(models.Model):
    """Major stock classification aligned to chart-of-accounts codes 4401–4418.

    Each classification groups like-with-like stock items and maps directly
    to a control account code used for stock valuation and reporting.
    (SRS: FR-ID-001, BR-ID-001, BR-COD-001)
    """

    _name = "mesob.inventory.major.classification"
    _description = "Major Stock Classification (4401–4418)"
    _order = "code"
    _rec_name = "name"

    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Classification code must be unique.'),
        ('code_format', "CHECK(code ~ '^[0-9]{4}$')", 'Classification code must be exactly 4 digits.'),
    ]

    code = fields.Char(
        string="Classification Code",
        required=True,
        index=True,
        copy=False,
        help="4-digit chart-of-accounts code (e.g. 4401).",
    )
    name = fields.Char(
        string="Name (English)",
        required=True,
    )
    name_am = fields.Char(
        string="Name (Amharic)",
        help="Amharic translation of the classification name.",
    )
    description = fields.Text(
        string="Description",
    )
    active = fields.Boolean(default=True)

    item_count = fields.Integer(
        string="Items",
        compute="_compute_item_count",
    )
    sub_classification_ids = fields.One2many(
        comodel_name="mesob.inventory.sub.classification",
        inverse_name="major_classification_id",
        string="Sub Classifications",
    )
    sub_classification_count = fields.Integer(
        string="Sub Classifications Count",
        compute="_compute_sub_classification_count",
    )

    @api.depends("code", "name")
    def _compute_display_name(self):
        for rec in self:
            if rec.code and rec.name:
                rec.display_name = f"[{rec.code}] {rec.name}"
            else:
                rec.display_name = rec.name or rec.code or ""

    def _compute_item_count(self):
        for rec in self:
            rec.item_count = self.env["mesob.inventory.item"].search_count(
                [("classification_id", "=", rec.id)]
            )

    def _compute_sub_classification_count(self):
        for rec in self:
            rec.sub_classification_count = len(rec.sub_classification_ids)

    def action_view_sub_classifications(self):
        """Open list of sub classifications belonging to this major classification."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Sub Classifications — {self.display_name}",
            "res_model": "mesob.inventory.sub.classification",
            "view_mode": "list,form",
            "domain": [("major_classification_id", "=", self.id)],
            "context": {"default_major_classification_id": self.id},
        }

    def action_view_items(self):
        """Open list of items belonging to this classification."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Items — {self.display_name}",
            "res_model": "mesob.inventory.item",
            "view_mode": "list,form",
            "domain": [("classification_id", "=", self.id)],
            "context": {"default_classification_id": self.id},
        }

    def action_view_sub_classifications_bin_card(self):
        """Open the sub-classifications navigation for this major classification."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Sub Classifications under {self.name}",
            "res_model": "mesob.inventory.sub.classification",
            "view_mode": "kanban,list,form",
            "domain": [("major_classification_id", "=", self.id)],
            "context": {
                "default_major_classification_id": self.id,
            },
        }

    def action_view_sub_classifications_stock_card(self):
        """Open the sub-classifications navigation for this major classification in the stock card flow."""
        self.ensure_one()
        view_id = self.env.ref("mesob_inventory_base.view_mesob_sub_classification_kanban_stock_card").id
        return {
            "type": "ir.actions.act_window",
            "name": f"Sub Classifications under {self.name}",
            "res_model": "mesob.inventory.sub.classification",
            "views": [(view_id, "kanban"), (False, "list")],
            "domain": [("major_classification_id", "=", self.id)],
            "context": {
                "default_major_classification_id": self.id,
            },
        }

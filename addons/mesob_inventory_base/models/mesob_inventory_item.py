import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError


_ITEM_CODE_PATTERN = re.compile(r"^(?P<major>\d{4})-(?P<sub>\d{3})-(?P<specific>\d{3})$")


class MesobInventoryItem(models.Model):
    """Inventory item master with FDRE-standard coding and stock-control levels.

    Coding format: ####-###-### (FR-ID-002)
    Classification: linked to chart-of-accounts 4401–4418 (FR-ID-001)
    Stock control: min/max/reorder/safety levels & ABC class (FR-SC-001, FR-SC-005)
    """

    _name = "mesob.inventory.item"
    _description = "Inventory Item"
    _rec_name = "item_code"
    _order = "item_code"

    _item_code_unique = models.Constraint(
        "UNIQUE(item_code)",
        "Item Code must be unique.",
    )

    _item_code_format = models.Constraint(
        "CHECK(item_code ~ '^[0-9]{4}-[0-9]{3}-[0-9]{3}$')",
        "Item Code must follow the format ####-###-### (digits and dashes).",
    )

    # ── Identification ──────────────────────────────────────────────────

    item_code = fields.Char(
        string="Item Code",
        required=True,
        index=True,
        copy=False,
        help="FDRE item code format: ####-###-### (10 digits total).",
    )

    major_code = fields.Char(
        string="Major Code",
        compute="_compute_item_code_segments",
        inverse="_inverse_item_code_segments",
        store=True,
        help="First 4 digits of the FDRE item code (classification aligned to chart of accounts).",
    )
    sub_code = fields.Char(
        string="Sub Code",
        compute="_compute_item_code_segments",
        inverse="_inverse_item_code_segments",
        store=True,
        help="Middle 3 digits of the FDRE item code (sub-class).",
    )
    specific_code = fields.Char(
        string="Specific Code",
        compute="_compute_item_code_segments",
        inverse="_inverse_item_code_segments",
        store=True,
        help="Last 3 digits of the FDRE item code (specific item).",
    )

    classification_id = fields.Many2one(
        "mesob.inventory.major.classification",
        string="Major Classification",
        index=True,
        help="Chart-of-accounts classification (4401–4418).",
    )

    name = fields.Char(
        string="Name (English)",
        required=True,
        index=True,
    )
    name_am = fields.Char(
        string="Name (Amharic)",
        help="Amharic translation of the item name.",
    )
    description = fields.Text()
    active = fields.Boolean(default=True)


    # ── Unit of Measure ─────────────────────────────────────────────────

    uom_id = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
        help="Default unit of measure for this item.",
    )

    # ── Stock Control Levels (FR-SC-001) ────────────────────────────────

    minimum_level = fields.Float(
        string="Minimum Level",
        default=0.0,
        help="Minimum stock quantity before alert.",
    )
    maximum_level = fields.Float(
        string="Maximum Level",
        default=0.0,
        help="Maximum stock quantity allowed.",
    )
    reorder_level = fields.Float(
        string="Reorder Level",
        default=0.0,
        help="Stock level at which to trigger a purchase/requisition.",
    )
    hastening_level = fields.Float(
        string="Hastening Level",
        default=0.0,
        help="Level at which to expedite pending deliveries.",
    )
    safety_stock = fields.Float(
        string="Safety Stock",
        default=0.0,
        help="Buffer stock to cover demand variability.",
    )

    # ── Lead Times (FR-SC-002) ──────────────────────────────────────────

    admin_lead_time = fields.Integer(
        string="Administrative Lead Time (days)",
        default=0,
        help="Days for internal processing before order is placed.",
    )
    supplier_lead_time = fields.Integer(
        string="Supplier Lead Time (days)",
        default=0,
        help="Days from order placement to delivery.",
    )

    # ── ABC Classification (FR-SC-005) ──────────────────────────────────

    abc_class = fields.Selection(
        [
            ("A", "A — High Value / High Priority"),
            ("B", "B — Medium Value / Medium Priority"),
            ("C", "C — Low Value / Low Priority"),
        ],
        string="ABC Class",
        help="ABC analysis classification by usage value to prioritize management attention.",
    )

    # ── Controlled Material Flag (FR-ISSUE-004) ─────────────────────────

    is_controlled = fields.Boolean(
        string="Controlled Material",
        default=False,
        help="If checked, issue restricted to authorized individuals only "
             "(e.g. drugs, chemicals, explosives).",
    )

    # ── Catalog Exclusion (FR-ID-006) ───────────────────────────────────

    exclude_from_catalog = fields.Boolean(
        string="Exclude from Catalog",
        default=False,
        help="Mark seldom-required/non-repetitive items excluded from the coding catalog.",
    )

    # ── Computed / Validation ───────────────────────────────────────────

    @api.depends("item_code", "name")
    def _compute_display_name(self):
        for rec in self:
            if rec.item_code and rec.name:
                rec.display_name = f"[{rec.item_code}] {rec.name}"
            else:
                rec.display_name = rec.name or rec.item_code or ""

    @api.constrains("item_code")
    def _check_item_code_format(self):
        for record in self:
            if not record.item_code:
                continue
            if not _ITEM_CODE_PATTERN.fullmatch(record.item_code):
                raise ValidationError(
                    "Item Code must follow the format ####-###-### (digits and dashes)."
                )

    @api.depends("item_code")
    def _compute_item_code_segments(self):
        for record in self:
            match = _ITEM_CODE_PATTERN.fullmatch(record.item_code or "")
            if not match:
                record.major_code = False
                record.sub_code = False
                record.specific_code = False
                continue
            record.major_code = match.group("major")
            record.sub_code = match.group("sub")
            record.specific_code = match.group("specific")

    def _inverse_item_code_segments(self):
        for record in self:
            if not (record.major_code and record.sub_code and record.specific_code):
                continue

            major = (record.major_code or "").strip()
            sub = (record.sub_code or "").strip()
            specific = (record.specific_code or "").strip()
            record.item_code = f"{major}-{sub}-{specific}"

    @api.onchange("classification_id")
    def _onchange_classification_id(self):
        """Auto-fill major code prefix from classification selection."""
        if self.classification_id and self.classification_id.code:
            self.major_code = self.classification_id.code

    @api.onchange("major_code")
    def _onchange_major_code(self):
        """Auto-link classification when major code is typed manually."""
        if self.major_code:
            classification = self.env["mesob.inventory.major.classification"].search(
                [("code", "=", self.major_code)], limit=1
            )
            if classification:
                self.classification_id = classification.id

    # ── Stock Records (FR-RECARD-001, FR-RECARD-002) ────────────────────

    bin_card_count = fields.Integer(
        string="Bin Card Entries",
        compute="_compute_bin_card_count",
        help="Number of bin card entries for this item.",
    )

    stock_record_card_count = fields.Integer(
        string="Stock Record Card Entries",
        compute="_compute_stock_record_card_count",
        help="Number of stock record card entries for this item.",
    )

    current_stock_quantity = fields.Float(
        string="Current Stock Quantity",
        compute="_compute_current_stock",
        help="Current stock quantity from latest bin card entry.",
    )

    current_stock_value = fields.Monetary(
        string="Current Stock Value",
        currency_field="currency_id",
        compute="_compute_current_stock",
        help="Current stock value from latest stock record card entry.",
    )

    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        default=lambda self: self.env.company.currency_id,
    )

    def _compute_bin_card_count(self):
        for record in self:
            record.bin_card_count = self.env["mesob.inventory.bin.card"].search_count(
                [("item_id", "=", record.id)]
            )

    def _compute_stock_record_card_count(self):
        for record in self:
            record.stock_record_card_count = self.env[
                "mesob.inventory.stock.record.card"
            ].search_count([("item_id", "=", record.id)])

    def _compute_current_stock(self):
        for record in self:
            # Get latest bin card entry for quantity
            latest_bin_card = self.env["mesob.inventory.bin.card"].search(
                [("item_id", "=", record.id)],
                order="date desc, id desc",
                limit=1,
            )
            record.current_stock_quantity = (
                latest_bin_card.quantity_balance if latest_bin_card else 0.0
            )

            # Get latest stock record card entry for value
            latest_stock_record = self.env["mesob.inventory.stock.record.card"].search(
                [("item_id", "=", record.id)],
                order="date desc, id desc",
                limit=1,
            )
            record.current_stock_value = (
                latest_stock_record.balance_total_value if latest_stock_record else 0.0
            )

    def action_view_bin_card(self):
        """Open bin card entries for this item."""
        self.ensure_one()
        return {
            "name": f"Bin Card - {self.item_code}",
            "type": "ir.actions.act_window",
            "res_model": "mesob.inventory.bin.card",
            "view_mode": "list,form,graph",
            "domain": [("item_id", "=", self.id)],
            "context": {"default_item_id": self.id},
        }

    def action_view_stock_record_card(self):
        """Open stock record card entries for this item."""
        self.ensure_one()
        return {
            "name": f"Stock Record Card - {self.item_code}",
            "type": "ir.actions.act_window",
            "res_model": "mesob.inventory.stock.record.card",
            "view_mode": "list,form,graph",
            "domain": [("item_id", "=", self.id)],
            "context": {"default_item_id": self.id},
        }

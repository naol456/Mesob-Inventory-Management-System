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

    _sql_constraints = [
        ('item_code_unique', 'UNIQUE(item_code)', 'Item Code must be unique.'),
        ('item_code_format', "CHECK(item_code ~ '^[0-9]{4}-[0-9]{3}-[0-9]{3}$')", 
         'Item Code must follow the format ####-###-### (digits and dashes).'),
    ]

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

    sub_classification_id = fields.Many2one(
        "mesob.inventory.sub.classification",
        string="Sub Classification",
        index=True,
        help="Sub classification under major classification.",
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

    # ── Product Linkage ─────────────────────────────────────────────────

    product_id = fields.Many2one(
        "product.product",
        string="Linked Product",
        help="Odoo product for stock operations and valuation.",
        index=True,
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

    # ── Stock Status & Monitoring ───────────────────────────────────────

    current_stock = fields.Float(
        string="Current Stock",
        compute="_compute_current_stock",
        help="Current stock balance from bin card"
    )

    stock_status = fields.Selection([
        ('critical', 'Critical - Below Minimum'),
        ('low', 'Low - Below Reorder'),
        ('hasten', 'Hasten - Below Hastening'),
        ('normal', 'Normal'),
        ('high', 'High - Above Maximum'),
    ], string="Stock Status", compute="_compute_stock_status", store=True)

    issue_status = fields.Selection([
        ('issued', 'Issued'),
        ('not_issued', 'Not Issued'),
    ], string="Issue Status", compute="_compute_issue_status")

    current_holder = fields.Char(
        string="Current Holder",
        compute="_compute_current_holder",
        help="The actual employee, department, or requester currently holding the item. Shows department or initials + name."
    )

    total_lead_time = fields.Integer(
        string="Total Lead Time (days)",
        compute="_compute_total_lead_time",
        store=True,
        help="Total lead time = Administrative + Supplier lead time"
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

    @api.constrains("classification_id", "major_code")
    def _check_classification_consistency(self):
        """Validate that major_code matches classification_id.code."""
        for record in self:
            if record.classification_id and record.major_code:
                if record.classification_id.code != record.major_code:
                    raise ValidationError(
                        f"Major code {record.major_code} does not match "
                        f"classification code {record.classification_id.code}."
                    )

    @api.constrains("sub_classification_id", "sub_code")
    def _check_sub_classification_consistency(self):
        """Validate that sub_code matches sub_classification_id.code."""
        for record in self:
            if record.sub_classification_id and record.sub_code:
                if record.sub_classification_id.code != record.sub_code:
                    raise ValidationError(
                        f"Sub code {record.sub_code} does not match "
                        f"sub classification code {record.sub_classification_id.code}."
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

    # ── Stock Control Validations & Computations ───────────────────────

    @api.constrains('minimum_level', 'reorder_level', 'hastening_level', 'maximum_level', 'safety_stock')
    def _check_control_levels(self):
        """Validate control level relationships (FR-SC-001)"""
        for item in self:
            if item.minimum_level < 0 or item.maximum_level < 0 or item.reorder_level < 0:
                raise ValidationError('Control levels cannot be negative.')
            
            if item.maximum_level > 0 and item.minimum_level > item.maximum_level:
                raise ValidationError(
                    f'Item {item.item_code}: Minimum level ({item.minimum_level}) '
                    f'cannot exceed maximum level ({item.maximum_level}).'
                )
            
            if item.reorder_level > 0:
                if item.minimum_level > 0 and item.reorder_level < item.minimum_level:
                    raise ValidationError(
                        f'Item {item.item_code}: Reorder level ({item.reorder_level}) '
                        f'should be >= minimum level ({item.minimum_level}).'
                    )
                if item.maximum_level > 0 and item.reorder_level > item.maximum_level:
                    raise ValidationError(
                        f'Item {item.item_code}: Reorder level ({item.reorder_level}) '
                        f'should be <= maximum level ({item.maximum_level}).'
                    )

    @api.depends('admin_lead_time', 'supplier_lead_time')
    def _compute_total_lead_time(self):
        """Calculate total lead time (FR-SC-002)"""
        for item in self:
            item.total_lead_time = item.admin_lead_time + item.supplier_lead_time

    def _compute_current_stock(self):
        """Get current stock from bin card aggregated by sub-classification (FR-SC-001)"""
        for item in self:
            if not item.sub_classification_id:
                item.current_stock = 0.0
                continue
            
            # Get the latest bin card balance for this sub-classification
            bin_card = self.env['mesob.bin.card'].search([
                ('sub_classification_id', '=', item.sub_classification_id.id)
            ], limit=1, order='date desc, id desc')
            item.current_stock = bin_card.balance if bin_card else 0.0

    @api.depends('current_stock', 'minimum_level', 'reorder_level', 'hastening_level', 'maximum_level')
    def _compute_stock_status(self):
        """Determine stock status based on control levels (FR-SC-001)"""
        for item in self:
            current = item.current_stock
            
            if item.minimum_level > 0 and current < item.minimum_level:
                item.stock_status = 'critical'
            elif item.reorder_level > 0 and current < item.reorder_level:
                item.stock_status = 'low'
            elif item.hastening_level > 0 and current < item.hastening_level:
                item.stock_status = 'hasten'
            elif item.maximum_level > 0 and current > item.maximum_level:
                item.stock_status = 'high'
            else:
                item.stock_status = 'normal'

    def _compute_issue_status(self):
        for rec in self:
            issued_lines = self.env['mesob.inventory.issue.voucher.line'].search_count([
                ('item_id', '=', rec.id),
                ('voucher_id.state', 'in', ['issued', 'received']),
            ])
            rec.issue_status = 'issued' if issued_lines > 0 else 'not_issued'

    def _compute_current_holder(self):
        for rec in self:
            # Find the latest issue voucher line for this item
            line = self.env['mesob.inventory.issue.voucher.line'].search([
                ('item_id', '=', rec.id),
                ('voucher_id.state', 'in', ['issued', 'received'])
            ], order='id desc', limit=1)
            
            if line:
                voucher = line.voucher_id
                requisition = voucher.requisition_id
                if requisition:
                    if requisition.department:
                        rec.current_holder = f"🏢 {requisition.department}"
                    elif requisition.requested_by_id:
                        user = requisition.requested_by_id
                        name = user.name or ""
                        parts = name.split()
                        initials = "".join([p[0].upper() for p in parts if p])[:2]
                        rec.current_holder = f"👤 {initials} {name}"
                    else:
                        rec.current_holder = ""
                else:
                    rec.current_holder = ""
            else:
                rec.current_holder = ""

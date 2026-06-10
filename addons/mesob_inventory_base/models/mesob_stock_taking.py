from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class MesobStockTaking(models.Model):
    """Stock Taking event managed by Property Admin Officer (PAO) - Section 4.8.

    Enforces pre-training, logical layout sequencing, pre-numbered sheets,
    and exclusion of storekeepers from the count team (FR-ST-001 through FR-ST-009).
    """

    _name = "mesob.stock.taking"
    _description = "Stock Taking Event"
    _order = "date_start desc, id desc"

    name = fields.Char(
        string="Stock-Take Reference",
        required=True,
        copy=False,
        default="New",
    )
    pao_id = fields.Many2one(
        "res.users",
        string="Property Admin Officer (PAO)",
        required=True,
        default=lambda self: self.env.user,
        help="Supervising officer who manages stock taking (FR-ST-001).",
    )
    date_start = fields.Date(
        string="Start Date",
        required=True,
        default=fields.Date.today,
    )
    date_end = fields.Date(string="End Date")
    instructions = fields.Text(
        string="Stock-Taking Instructions",
        required=True,
        help="Instructions issued by PAO for the counting teams.",
    )
    is_pre_training_done = fields.Boolean(
        string="Pre-Stocktaking Training Performed",
        default=False,
        help="Must be checked to confirm team training was completed (FR-ST-001).",
    )
    team_member_ids = fields.Many2many(
        "res.users",
        "mesob_stock_taking_team_users_rel",
        "stock_taking_id",
        "user_id",
        string="Stock-Taking Team",
        help="Team members conducting the count. Storekeepers are strictly excluded (FR-ST-009).",
    )
    guide_storekeeper_ids = fields.Many2many(
        "res.users",
        "mesob_stock_taking_guides_users_rel",
        "stock_taking_id",
        "user_id",
        string="Storekeeper Guides / Witnesses",
        help="Storekeepers may act as guides or witnesses only (FR-ST-009).",
    )
    line_ids = fields.One2many(
        "mesob.stock.taking.line",
        "stock_taking_id",
        string="Stock taking Sheets",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("ongoing", "Ongoing / Counting"),
            ("completed", "Completed & Reconciled"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        required=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("mesob.stock.taking") or "New"
        return super().create(vals_list)

    @api.constrains("team_member_ids", "guide_storekeeper_ids")
    def _check_storekeeper_exclusion(self):
        """Enforces that storekeepers are strictly excluded from count teams (FR-ST-009 / BR-ST-001)."""
        for rec in self:
            storekeeper_group = self.env.ref("mesob_inventory_base.group_mesob_storekeeper")
            for member in rec.team_member_ids:
                if storekeeper_group in member.group_ids:
                    raise ValidationError(
                        f"Validation Block: User '{member.name}' is a Storekeeper and "
                        f"MUST NOT be a member of the stock-taking counting team! (FR-ST-009)"
                    )

    def action_start_stock_taking(self):
        """Initiates the stock-taking event, pre-generates sheets in logical storage order (FR-ST-002)."""
        for rec in self:
            if rec.state != "draft":
                raise UserError("Stock-taking has already been started.")
            if not rec.is_pre_training_done:
                raise UserError("You must perform and record pre-stocktaking training before starting (FR-ST-001).")
            if not rec.team_member_ids:
                raise UserError("Please assign at least one team member to conduct the counts.")

            # Clear any existing lines
            rec.line_ids.unlink()

            # Pre-generate sheets in logical order matching classifications & storage layout (FR-ST-002)
            items = self.env["mesob.inventory.item"].search([], order="classification_id, item_code")
            serial_num = 1
            for item in items:
                # Fetch system stock balance
                item._compute_current_stock()
                self.env["mesob.stock.taking.line"].create({
                    "stock_taking_id": rec.id,
                    "serial_number": serial_num,
                    "item_id": item.id,
                    "recorded_qty": item.current_stock,
                    "location_label": item.sub_classification_id.name or "Store A",
                })
                serial_num += 1

            rec.state = "ongoing"
        return True

    def action_complete_and_reconcile(self):
        """Finalizes count sheet and posts red-ink Equivalent markers on Bin Cards (FR-ST-008)."""
        for rec in self:
            if rec.state != "ongoing":
                raise UserError("Only ongoing stock-taking events can be finalized.")

            uncounted = rec.line_ids.filtered(lambda l: not l.is_counted)
            if uncounted:
                raise UserError(
                    f"Please complete counting for all items. {len(uncounted)} lines are still uncounted."
                )

            # Reconcile counts and update red ink indicators
            for line in rec.line_ids:
                if line.discrepancy != 0.0:
                    # Record adjustment on the Bin Card
                    sub_class = line.item_id.sub_classification_id
                    if sub_class:
                        self.env["mesob.bin.card"].create({
                            "sub_classification_id": sub_class.id,
                            "date": fields.Date.today(),
                            "reference": f"Stock-Take Adj ({rec.name})",
                            "receipt_qty": line.physical_qty if line.discrepancy > 0 else 0.0,
                            "issue_qty": abs(line.discrepancy) if line.discrepancy < 0 else 0.0,
                            "remarks": f"Red-Ink Audit Check: {line.discrepancy_reason or 'No reason provided'}",
                        })

            rec.write({
                "state": "completed",
                "date_end": fields.Date.today(),
            })
        return True


class MesobStockTakingLine(models.Model):
    """Pre-numbered count sheet lines - FR-ST-002/006."""

    _name = "mesob.stock.taking.line"
    _description = "Stock Taking count Line"
    _order = "serial_number asc"

    stock_taking_id = fields.Many2one(
        "mesob.stock.taking",
        string="Stock-Taking Event",
        required=True,
        ondelete="cascade",
    )
    serial_number = fields.Integer(string="Sheet Serial No.", required=True)
    item_id = fields.Many2one("mesob.inventory.item", string="Catalogued Item", required=True)
    item_code = fields.Char(related="item_id.item_code", string="Item Code", readonly=True)
    location_label = fields.Char(string="Storage Location / Shelf")
    
    recorded_qty = fields.Float(string="System Book Balance", readonly=True)
    physical_qty = fields.Float(string="Physical Count", default=0.0)
    discrepancy = fields.Float(
        string="Discrepancy (Qty)",
        compute="_compute_discrepancy",
        store=True,
    )
    is_counted = fields.Boolean(
        string="Counted (Sticker Attached)",
        default=False,
        help="Colored-sticker counting marker is placed (FR-ST-005).",
    )
    discrepancy_reason = fields.Selection(
        [
            ("damaged", "Damaged Items"),
            ("shortage", "Unexplained Shortage"),
            ("overage", "Unrecorded Overage"),
            ("wrong_quality", "Inferior Quality / Expired"),
            ("theft", "Pilferage / Theft"),
        ],
        string="Reason for Discrepancy",
    )
    corrective_action = fields.Text(string="Proposed Corrective Action")
    notes = fields.Text(string="Witness/Team Notes")

    @api.depends("recorded_qty", "physical_qty")
    def _compute_discrepancy(self):
        for line in self:
            line.discrepancy = line.physical_qty - line.recorded_qty

    @api.onchange("physical_qty")
    def _onchange_physical_qty(self):
        """Auto-mark counted with sticker upon physical qty entry (FR-ST-005)."""
        if self.physical_qty > 0.0 or self.is_counted:
            self.is_counted = True

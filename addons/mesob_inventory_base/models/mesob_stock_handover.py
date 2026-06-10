from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class MesobStockHandover(models.Model):
    """Stocks Handing/Taking-Over custody transfer - Section 4.9.

    Triggered by storekeeper transfer, duty travel, training, medical leave,
    promotion, or retirement. Formulates official certificate and counted sheet lines
    in presence of competent witness, distributed in triplicate (FR-HO-001/002/003).
    """

    _name = "mesob.stock.handover"
    _description = "Storekeeper Stock Handover"
    _order = "date desc, id desc"

    name = fields.Char(
        string="Handover Reference",
        required=True,
        copy=False,
        default="New",
    )
    trigger_event = fields.Selection(
        [
            ("leave", "Annual/Sick Leave"),
            ("retirement", "Retirement"),
            ("duty_travel", "Duty Travel outside station"),
            ("training", "Training outside station"),
            ("promotion", "Promotion"),
            ("transfer", "Transfer to another branch"),
            ("medical", "Medical Treatment"),
        ],
        string="Triggering Status Change",
        required=True,
        help="The official reasons trigger custody transfers (FR-HO-001).",
    )
    outgoing_storekeeper_id = fields.Many2one(
        "res.users",
        string="Outgoing Storekeeper (Custodian)",
        required=True,
        help="Outgoing storekeeper transferring custody (FR-HO-002).",
    )
    incoming_storekeeper_id = fields.Many2one(
        "res.users",
        string="Incoming Storekeeper (Receiver)",
        required=True,
        help="Incoming storekeeper taking custody (FR-HO-002).",
    )
    witness_id = fields.Many2one(
        "res.users",
        string="Competent Witness / PAO",
        required=True,
        help="Witness who oversees the custody count and signs off (FR-HO-002).",
    )
    date = fields.Date(
        string="Handover Date",
        required=True,
        default=fields.Date.today,
    )
    certificate = fields.Text(
        string="Handover Custody Certificate",
        help="Official custody transfer statement signed in presence of the witness.",
    )
    line_ids = fields.One2many(
        "mesob.stock.handover.line",
        "handover_id",
        string="Handover Count Sheet",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("counting", "Physical Counting"),
            ("signed", "Witness Signed"),
            ("done", "Custody Transferred"),
        ],
        string="Status",
        default="draft",
        required=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("mesob.stock.handover") or "New"
        return super().create(vals_list)

    @api.constrains("outgoing_storekeeper_id", "incoming_storekeeper_id", "witness_id")
    def _check_distinct_participants(self):
        for rec in self:
            if rec.outgoing_storekeeper_id == rec.incoming_storekeeper_id:
                raise ValidationError("Outgoing and Incoming storekeepers must be distinct individuals.")
            if rec.witness_id in (rec.outgoing_storekeeper_id, rec.incoming_storekeeper_id):
                raise ValidationError("The witness must be an independent participant and cannot be a storekeeper.")

    def action_start_counting(self):
        """Pre-populates the handover count sheet with current system balances (FR-HO-002)."""
        for rec in self:
            if rec.state != "draft":
                raise UserError("Custody counting has already been initiated.")
            
            # Clear lines
            rec.line_ids.unlink()

            # Prepopulate lines
            items = self.env["mesob.inventory.item"].search([])
            for item in items:
                item._compute_current_stock()
                self.env["mesob.stock.handover.line"].create({
                    "handover_id": rec.id,
                    "item_id": item.id,
                    "system_qty": item.current_stock,
                    "counted_qty": item.current_stock,  # Default to matching
                })
            
            # Generate default certificate template text
            rec.certificate = (
                f"I, {rec.outgoing_storekeeper_id.name}, hereby hand over absolute custody of "
                f"the stock items listed below to the incoming storekeeper, {rec.incoming_storekeeper_id.name}, "
                f"under the supervision and witnessing of {rec.witness_id.name} on {rec.date} "
                f"due to triggering status change: '{dict(rec._fields['trigger_event'].selection).get(rec.trigger_event)}'."
            )
            rec.state = "counting"
        return True

    def action_sign_handover(self):
        """Witness and both storekeepers confirm and sign off (FR-HO-002)."""
        for rec in self:
            if rec.state != "counting":
                raise UserError("Only active counts can be signed.")
            rec.state = "signed"
        return True

    def action_finalize_handover(self):
        """Finalizes handover custody and closes the record (FR-HO-003)."""
        for rec in self:
            if rec.state != "signed":
                raise UserError("Handover must be signed by all parties before completion.")
            rec.state = "done"
        return True


class MesobStockHandoverLine(models.Model):
    """Line item in Handover custody count sheet - FR-HO-002."""

    _name = "mesob.stock.handover.line"
    _description = "Stock Handover Line"

    handover_id = fields.Many2one(
        "mesob.stock.handover",
        string="Handover Event",
        required=True,
        ondelete="cascade",
    )
    item_id = fields.Many2one("mesob.inventory.item", string="Catalogued Item", required=True)
    item_code = fields.Char(related="item_id.item_code", string="Item Code", readonly=True)
    system_qty = fields.Float(string="System Balance", readonly=True)
    counted_qty = fields.Float(string="Physical Counted", required=True, default=0.0)
    discrepancy = fields.Float(
        string="Discrepancy",
        compute="_compute_discrepancy",
        store=True,
    )

    @api.depends("system_qty", "counted_qty")
    def _compute_discrepancy(self):
        for line in self:
            line.discrepancy = line.counted_qty - line.system_qty

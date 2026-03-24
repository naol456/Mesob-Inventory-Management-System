from odoo import fields, models
from odoo.exceptions import UserError


class MesobInventoryRequisition(models.Model):
    _name = "mesob.inventory.requisition"
    _description = "Stores Requisition (Model 20)"

    name = fields.Char(
        string="Requisition Reference",
        required=True,
        index=True,
        default="New",
        copy=False,
        help="Temporary reference. A controlled numbering sequence will be added next.",
    )

    requested_by_id = fields.Many2one(
        "res.users",
        string="Requested By",
        required=True,
        default=lambda self: self.env.user,
    )
    requested_on = fields.Date(
        string="Requested On",
        required=True,
        default=fields.Date.today,
    )

    approved_by_id = fields.Many2one(
        "res.users",
        string="Approved By",
        readonly=True,
        copy=False,
    )
    approved_on = fields.Date(
        string="Approved On",
        readonly=True,
        copy=False,
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("cancelled", "Cancelled"),
        ],
        required=True,
        default="draft",
        copy=False,
        index=True,
    )

    line_ids = fields.One2many(
        "mesob.inventory.requisition.line",
        "requisition_id",
        string="Lines",
        copy=True,
    )

    note = fields.Text()

    def action_submit(self):
        for record in self:
            if not record.line_ids:
                raise UserError("Add at least one line before submitting.")
            record.state = "submitted"
        return True

    def action_approve(self):
        for record in self:
            record.approved_by_id = self.env.user
            record.approved_on = fields.Date.today()
            record.state = "approved"
        return True

    def action_reject(self):
        for record in self:
            record.state = "rejected"
        return True

    def action_set_to_draft(self):
        for record in self:
            record.state = "draft"
        return True

    def action_cancel(self):
        for record in self:
            record.state = "cancelled"
        return True

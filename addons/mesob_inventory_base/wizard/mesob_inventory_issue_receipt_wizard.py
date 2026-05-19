from odoo import api, fields, models
from odoo.exceptions import UserError


class MesobInventoryIssueReceiptWizard(models.TransientModel):
    """Wizard for department to confirm receipt of issued materials (FR-ISSUE-006)."""

    _name = "mesob.inventory.issue.receipt.wizard"
    _description = "Issue Receipt Confirmation Wizard"

    voucher_id = fields.Many2one(
        "mesob.inventory.issue.voucher",
        string="Issue Voucher",
        required=True,
        readonly=True,
    )

    quantity_verified = fields.Boolean(
        string="Quantity Verified",
        default=True,
        help="I confirm that the quantities received match the requisition.",
    )

    inspection_confirmed = fields.Boolean(
        string="Inspection Confirmed",
        default=True,
        help="I confirm that the items are in acceptable condition.",
    )

    approval_verified = fields.Boolean(
        string="Approval Verified",
        default=True,
        help="I confirm that the requisition was properly approved.",
    )

    receipt_notes = fields.Text(
        string="Receipt Notes",
        help="Any remarks or observations about the received materials.",
    )

    def action_confirm_receipt(self):
        """Confirm receipt and update voucher."""
        self.ensure_one()

        if not (self.quantity_verified and self.inspection_confirmed and self.approval_verified):
            raise UserError(
                "All verification checks must be confirmed before completing receipt. "
                "If there are issues, please add notes and contact the storekeeper."
            )

        self.voucher_id.write({
            "state": "received",
            "received_by_id": self.env.user.id,
            "received_on": fields.Date.today(),
            "quantity_verified": self.quantity_verified,
            "inspection_confirmed": self.inspection_confirmed,
            "approval_verified": self.approval_verified,
            "receipt_notes": self.receipt_notes,
        })

        # Update requisition state
        self.voucher_id.requisition_id.write({"state": "received"})

        # Post message to chatter
        self.voucher_id.message_post(
            body=f"Receipt confirmed by {self.env.user.name}. "
                 f"Quantity verified: {self.quantity_verified}, "
                 f"Inspection confirmed: {self.inspection_confirmed}, "
                 f"Approval verified: {self.approval_verified}."
        )

        return {"type": "ir.actions.act_window_close"}

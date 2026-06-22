"""AUTO-046: PAO Emergency Override Wizard for Gate Pass.

This wizard allows PAO to override prerequisite validation in emergencies,
requiring justification and creating a complete audit trail.
"""

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


class MesobGatePassOverrideWizard(models.TransientModel):
    """Wizard for PAO to grant emergency override on Gate Pass prerequisites."""
    
    _name = "mesob.gate.pass.override.wizard"
    _description = "Gate Pass PAO Emergency Override Wizard"
    
    gate_pass_id = fields.Many2one(
        "mesob.gate.pass",
        string="Gate Pass",
        required=True,
        readonly=True,
        help="Gate Pass requiring emergency override.",
    )
    
    override_reason = fields.Text(
        string="Justification for Override",
        required=True,
        help=(
            "Required: Explain why emergency override is necessary.\n"
            "Example: Urgent medical supply dispatch, humanitarian emergency, etc."
        ),
    )
    
    confirm_emergency = fields.Boolean(
        string="I confirm this is a genuine emergency",
        required=True,
        help="PAO must confirm this is a legitimate emergency requiring override.",
    )
    
    @api.constrains("override_reason")
    def _check_override_reason(self):
        """Ensure override reason is meaningful (not just whitespace)."""
        for record in self:
            if not record.override_reason or not record.override_reason.strip():
                raise ValidationError(
                    "Override justification cannot be empty. "
                    "Please provide a detailed explanation for this emergency override."
                )
            
            if len(record.override_reason.strip()) < 20:
                raise ValidationError(
                    "Override justification is too short. "
                    "Please provide a detailed explanation (minimum 20 characters)."
                )
    
    def action_grant_override(self):
        """Grant PAO emergency override and create audit trail."""
        self.ensure_one()
        
        # Verify PAO role
        if not self.env.user.has_group("mesob_inventory_base.group_mesob_pao"):
            raise UserError(
                "Only Property Administration Officers (PAO) can grant emergency overrides."
            )
        
        # Verify confirmation
        if not self.confirm_emergency:
            raise UserError(
                "You must confirm this is a genuine emergency before granting override."
            )
        
        # Verify gate pass exists
        if not self.gate_pass_id:
            raise UserError("Gate Pass not found.")
        
        # Grant override
        self.gate_pass_id.write({
            "pao_override": True,
            "pao_override_reason": self.override_reason,
            "pao_override_by_id": self.env.user.id,
            "pao_override_on": fields.Datetime.now(),
        })
        
        # Post message to chatter for audit trail
        self.gate_pass_id.message_post(
            body=(
                f"<b>PAO EMERGENCY OVERRIDE GRANTED</b><br/>"
                f"<b>Authorized by:</b> {self.env.user.name}<br/>"
                f"<b>Timestamp:</b> {fields.Datetime.now()}<br/>"
                f"<b>Justification:</b> {self.override_reason}<br/><br/>"
                f"<i>This override bypasses prerequisite validation. "
                f"Gate Pass can now be authorized without matching Issue Voucher items.</i>"
            ),
            subject="PAO Emergency Override Granted",
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Emergency Override Granted',
                'message': 'PAO emergency override has been granted for this Gate Pass. '
                          'Prerequisite validation has been bypassed. '
                          'This action has been logged for audit purposes.',
                'type': 'success',
                'sticky': False,
            }
        }

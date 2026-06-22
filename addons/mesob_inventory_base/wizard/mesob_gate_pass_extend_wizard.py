# -*- coding: utf-8 -*-
"""
AUTO-048: Gate Pass Expiry Alert - Extension Wizard
====================================================

Wizard for PAO to extend gate pass validity when expired or expiring soon.
Requires justification for audit trail.
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class MesobGatePassExtendWizard(models.TransientModel):
    """Wizard for PAO to extend gate pass validity."""
    
    _name = 'mesob.gate.pass.extend.wizard'
    _description = 'Gate Pass Validity Extension'

    gate_pass_id = fields.Many2one(
        'mesob.gate.pass',
        string='Gate Pass',
        required=True,
        readonly=True,
    )
    
    current_expiry = fields.Datetime(
        string='Current Expiry',
        readonly=True,
        help='When this gate pass currently expires'
    )
    
    current_validity_hours = fields.Integer(
        string='Current Validity (Hours)',
        readonly=True,
    )
    
    additional_hours = fields.Integer(
        string='Additional Hours',
        required=True,
        default=24,
        help='Number of hours to add to validity period'
    )
    
    new_expiry = fields.Datetime(
        string='New Expiry',
        compute='_compute_new_expiry',
        help='Calculated new expiry datetime'
    )
    
    extension_reason = fields.Text(
        string='Justification for Extension',
        required=True,
        help='AUTO-048: Explain why this gate pass needs extended validity'
    )
    
    @api.depends('current_expiry', 'additional_hours')
    def _compute_new_expiry(self):
        """Calculate new expiry based on additional hours."""
        for wizard in self:
            if wizard.current_expiry and wizard.additional_hours > 0:
                from datetime import timedelta
                wizard.new_expiry = wizard.current_expiry + timedelta(hours=wizard.additional_hours)
            else:
                wizard.new_expiry = False
    
    @api.constrains('additional_hours')
    def _check_additional_hours(self):
        """Validate additional hours is positive."""
        for wizard in self:
            if wizard.additional_hours <= 0:
                raise UserError(_("Additional hours must be greater than 0."))
            if wizard.additional_hours > 168:  # 1 week
                raise UserError(_(
                    "AUTO-048: Cannot extend validity by more than 168 hours (1 week). "
                    "If longer validity is needed, create a new gate pass."
                ))
    
    @api.constrains('extension_reason')
    def _check_extension_reason(self):
        """Validate justification is meaningful."""
        for wizard in self:
            if not wizard.extension_reason or len(wizard.extension_reason.strip()) < 20:
                raise UserError(_(
                    "AUTO-048: Justification must be at least 20 characters. "
                    "Please explain why this extension is necessary."
                ))
    
    def action_extend(self):
        """Extend gate pass validity."""
        self.ensure_one()
        
        # Verify PAO role (double-check)
        if not self.env.user.has_group("mesob_inventory_base.group_mesob_pao"):
            raise UserError(_("Only PAO can extend gate pass validity."))
        
        # Perform extension
        self.gate_pass_id._do_extend_validity(
            additional_hours=self.additional_hours,
            extension_reason=self.extension_reason,
        )
        
        # Return notification
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Validity Extended'),
                'message': _(
                    f"Gate Pass {self.gate_pass_id.name} validity extended by {self.additional_hours} hours. "
                    f"New expiry: {self.new_expiry}"
                ),
                'type': 'success',
                'sticky': False,
            }
        }

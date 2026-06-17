# -*- coding: utf-8 -*-
"""AUTO-001: Procurement Need Rejection Wizard.

Allows SPO to reject submitted needs with mandatory reason.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class MesobProcurementNeedRejectWizard(models.TransientModel):
    """Wizard for rejecting procurement needs with mandatory reason."""
    
    _name = 'mesob.procurement.need.reject.wizard'
    _description = 'Reject Procurement Need'
    
    need_id = fields.Many2one(
        'mesob.procurement.need',
        string='Procurement Need',
        required=True,
        readonly=True
    )
    
    rejection_reason = fields.Text(
        string='Rejection Reason',
        required=True,
        help='Explain why this need is being rejected (minimum 10 characters)'
    )
    
    def action_confirm_reject(self):
        """Confirm rejection and return to need."""
        self.ensure_one()
        
        if not self.rejection_reason or len(self.rejection_reason) < 10:
            raise ValidationError("Rejection reason must be at least 10 characters.")
        
        # Call need's internal rejection method
        self.need_id._confirm_rejection(self.rejection_reason)
        
        return {'type': 'ir.actions.act_window_close'}

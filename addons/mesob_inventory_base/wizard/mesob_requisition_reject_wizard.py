# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError


class MesobRequisitionRejectWizard(models.TransientModel):
    """AUTO-042: Wizard for PAO to reject requisition with mandatory comment."""
    
    _name = 'mesob.requisition.reject.wizard'
    _description = 'Requisition Rejection Wizard'
    
    requisition_id = fields.Many2one(
        'mesob.inventory.requisition',
        string='Requisition',
        required=True,
        readonly=True
    )
    
    rejection_reason = fields.Text(
        string='Rejection Reason',
        required=True,
        help='Explain why this requisition is being rejected (minimum 10 characters)'
    )
    
    def action_confirm_rejection(self):
        """Confirm rejection and return to requester with comment."""
        self.ensure_one()
        
        if not self.rejection_reason or len(self.rejection_reason) < 10:
            raise UserError("Rejection reason must be at least 10 characters.")
        
        # Call the requisition's internal rejection method
        self.requisition_id._confirm_rejection(self.rejection_reason)
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Requisition Rejected',
                'message': f'Requisition {self.requisition_id.name} has been rejected and requester notified.',
                'type': 'success',
                'sticky': False,
            }
        }

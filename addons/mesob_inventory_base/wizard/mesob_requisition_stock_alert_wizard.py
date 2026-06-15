"""AUTO-043: Stock Availability Alert Wizard.

Displayed when PAO attempts to approve a requisition with insufficient stock.
Shows real-time stock levels, pending requisitions, and expected deliveries.
Allows PAO to approve partial quantity, defer, or override with justification.
"""

from odoo import api, fields, models
from odoo.exceptions import UserError


class MesobRequisitionStockAlertWizard(models.TransientModel):
    """Wizard to display stock availability alerts during requisition approval."""
    
    _name = 'mesob.requisition.stock.alert.wizard'
    _description = 'Stock Availability Alert'
    
    requisition_id = fields.Many2one(
        'mesob.inventory.requisition',
        string='Requisition',
        required=True,
        readonly=True
    )
    
    warning_message = fields.Html(
        string='Stock Warnings',
        readonly=True,
        help='AUTO-043: Stock availability details'
    )
    
    stock_warnings = fields.Text(
        string='Raw Warnings Data',
        readonly=True,
        help='JSON-encoded warning data for processing'
    )
    
    action_type = fields.Selection([
        ('defer', 'Defer Until Stock Available'),
        ('partial', 'Approve Partial Quantity'),
        ('override', 'Override and Approve Anyway'),
    ], string='Action', default='defer', required=True)
    
    override_reason = fields.Text(
        string='Override Justification',
        help='Required if choosing to override stock shortage'
    )
    
    def action_proceed(self):
        """Process PAO decision on stock alert."""
        self.ensure_one()
        
        if self.action_type == 'defer':
            # Keep requisition in submitted state, add note
            self.requisition_id.message_post(
                body=f"""<div style="background-color: #d1ecf1; border-left: 4px solid #0c5460; padding: 15px;">
                    <h4>📋 Approval Deferred</h4>
                    <p><strong>Deferred By:</strong> {self.env.user.name}</p>
                    <p><strong>Date:</strong> {fields.Datetime.now()}</p>
                    <p><strong>Reason:</strong> Insufficient stock availability</p>
                    <p><em>Waiting for stock replenishment before approval.</em></p>
                </div>""",
                subject='Requisition Approval Deferred - Stock Shortage',
                message_type='comment'
            )
            
            return {'type': 'ir.actions.act_window_close'}
        
        elif self.action_type == 'partial':
            # TODO: Implement partial approval (reduce line quantities to available stock)
            raise UserError(
                "Partial approval feature coming soon.\n\n"
                "For now, please either:\n"
                "1. Defer approval until stock is available, or\n"
                "2. Override and approve with justification"
            )
        
        elif self.action_type == 'override':
            # Require justification
            if not self.override_reason or len(self.override_reason.strip()) < 10:
                raise UserError(
                    "Override justification is required and must be at least 10 characters.\n\n"
                    "Please explain why this requisition must be approved despite stock shortages."
                )
            
            # Log override and approve
            self.requisition_id.message_post(
                body=f"""<div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px;">
                    <h4>⚠ Stock Shortage Override</h4>
                    <p><strong>Approved By:</strong> {self.env.user.name}</p>
                    <p><strong>Date:</strong> {fields.Datetime.now()}</p>
                    <p><strong>Justification:</strong></p>
                    <p style="white-space: pre-wrap; background-color: #fff; padding: 10px; border-radius: 4px;">{self.override_reason}</p>
                    <p><em>PAO approved this requisition despite stock availability warnings.</em></p>
                </div>""",
                subject='Requisition Approved with Stock Override',
                message_type='comment'
            )
            
            self.requisition_id.write({
                'approved_by_id': self.env.user.id,
                'approved_on': fields.Date.today(),
                'state': 'approved',
            })
            
            return {'type': 'ir.actions.act_window_close'}
        
        return {'type': 'ir.actions.act_window_close'}

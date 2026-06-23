# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class MesobComplaintPortal(models.Model):
    """AUTO-033: Self-Service Supplier Complaint Portal.
    
    Allows suppliers to submit complaints directly without manual officer intervention.
    Complaints are automatically linked to tenders/contracts and routed to responsible officers.
    """
    
    _name = 'mesob.complaint.portal'
    _description = 'Supplier Complaint Portal'
    _inherit = ['portal.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = 'create_date desc'
    
    name = fields.Char(
        string='Portal Reference',
        default='New',
        readonly=True,
        copy=False
    )
    
    supplier_id = fields.Many2one(
        'res.partner',
        string='Your Company',
        required=True,
        default=lambda self: self._get_current_supplier(),
        help='AUTO-033: Supplier submitting the complaint'
    )
    
    complaint_subject = fields.Char(
        string='Complaint Subject',
        required=True,
        help='Brief summary of your complaint'
    )
    
    complaint_description = fields.Text(
        string='Detailed Description',
        required=True,
        help='Please provide complete details of your complaint'
    )
    
    tender_reference = fields.Char(
        string='Tender Reference Number',
        help='If complaint relates to specific tender, provide reference (e.g., TEN/001)'
    )
    
    contract_reference = fields.Char(
        string='Contract Reference Number',
        help='If complaint relates to specific contract, provide reference'
    )
    
    complaint_category = fields.Selection([
        ('tender_process', 'Tender Process / Bid Evaluation'),
        ('disqualification', 'Disqualification Decision'),
        ('technical_specs', 'Technical Specifications'),
        ('payment_delay', 'Payment Delay'),
        ('contract_terms', 'Contract Terms'),
        ('delivery_dispute', 'Delivery / Acceptance Dispute'),
        ('other', 'Other'),
    ], string='Complaint Category', required=True)
    
    supporting_documents = fields.Many2many(
        'ir.attachment',
        string='Supporting Documents',
        help='Upload any documents supporting your complaint'
    )
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted - Pending Review'),
        ('registered', 'Registered - Under Investigation'),
        ('resolved', 'Resolved'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft', tracking=True)
    
    complaint_id = fields.Many2one(
        'mesob.procurement.complaint',
        string='Registered Complaint',
        readonly=True,
        help='AUTO-033: Linked complaint record created after submission'
    )
    
    submission_confirmation = fields.Text(
        string='Submission Confirmation',
        readonly=True,
        help='Confirmation message sent to supplier after submission'
    )
    
    @api.model
    def _get_current_supplier(self):
        """Get current portal user's partner."""
        if self.env.user.partner_id and self.env.user.partner_id.supplier_rank > 0:
            return self.env.user.partner_id
        return False
    
    def action_submit_complaint(self):
        """AUTO-033: Submit complaint and create official complaint register entry."""
        self.ensure_one()
        
        if self.state != 'draft':
            raise UserError("Only draft complaints can be submitted.")
        
        if not self.supplier_id:
            raise UserError("Supplier information is required.")
        
        # Create official complaint record
        complaint_vals = {
            'supplier_id': self.supplier_id.id,
            'complaint_subject': self.complaint_subject,
            'complaint_description': self.complaint_description,
            'complaint_type': self.complaint_category,
            'state': 'submitted',
        }
        
        # Try to auto-link to tender
        if self.tender_reference:
            tender = self.env['mesob.procurement.tender'].search([
                ('name', '=', self.tender_reference)
            ], limit=1)
            if tender:
                complaint_vals['related_tender_id'] = tender.id
                complaint_vals['related_lot_id'] = tender.lot_id.id if tender.lot_id else False
        
        # Try to auto-link to contract
        if self.contract_reference:
            contract = self.env['mesob.procurement.contract'].search([
                ('name', '=', self.contract_reference)
            ], limit=1)
            if contract:
                complaint_vals['related_contract_id'] = contract.id
        
        # Create complaint
        complaint = self.env['mesob.procurement.complaint'].create(complaint_vals)
        
        # Link portal entry to complaint
        self.write({
            'complaint_id': complaint.id,
            'state': 'registered',
            'name': complaint.name,
            'submission_confirmation': self._generate_confirmation_message(complaint)
        })
        
        # Send confirmation email
        self._send_confirmation_email(complaint)
        
        _logger.info(
            f"AUTO-033: Portal complaint submitted by {self.supplier_id.name} "
            f"→ Registered as {complaint.name}"
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Complaint Submitted Successfully',
                'message': f'Your complaint has been registered as {complaint.name}. You will receive updates via email.',
                'type': 'success',
                'sticky': True,
            }
        }
    
    def _generate_confirmation_message(self, complaint):
        """Generate confirmation message for supplier."""
        return f"""
Dear {self.supplier_id.name},

Your complaint has been successfully submitted and registered.

COMPLAINT DETAILS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Complaint Reference: {complaint.name}
Submission Date: {fields.Date.today()}
Category: {dict(self._fields['complaint_category'].selection).get(self.complaint_category)}
Subject: {self.complaint_subject}

NEXT STEPS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
1. Your complaint will be reviewed by the Procurement Administration Office
2. You will receive updates via email as the investigation progresses
3. Resolution target: Within 10 business days (FR-PROC-038)
4. If you have additional information, you may respond to email updates

TRACKING:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
You can track your complaint status by logging into the supplier portal.

If you have urgent questions, please contact:
Procurement Administration Office
FDRE Mesob Center
Email: procurement@mesob.gov.et

Thank you for bringing this matter to our attention.

Sincerely,
FDRE Mesob Center Procurement Unit
        """
    
    def _send_confirmation_email(self, complaint):
        """Send confirmation email to supplier."""
        if not self.supplier_id.email:
            return
        
        mail_values = {
            'subject': f'Complaint Submitted: {complaint.name}',
            'body_html': f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
                <div style="background-color: #007bff; color: white; padding: 20px; text-align: center;">
                    <h2>Complaint Submission Confirmation</h2>
                </div>
                
                <div style="padding: 20px; background-color: #f8f9fa;">
                    <p>Dear {self.supplier_id.name},</p>
                    
                    <p>Your complaint has been successfully submitted and registered in our system.</p>
                    
                    <div style="background-color: white; border-left: 4px solid #007bff; padding: 15px; margin: 20px 0;">
                        <h3 style="margin-top: 0;">Complaint Details</h3>
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr>
                                <td style="padding: 8px; font-weight: bold;">Reference:</td>
                                <td style="padding: 8px;">{complaint.name}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px; font-weight: bold;">Date:</td>
                                <td style="padding: 8px;">{fields.Date.today()}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px; font-weight: bold;">Category:</td>
                                <td style="padding: 8px;">{dict(self._fields['complaint_category'].selection).get(self.complaint_category)}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px; font-weight: bold;">Subject:</td>
                                <td style="padding: 8px;">{self.complaint_subject}</td>
                            </tr>
                        </table>
                    </div>
                    
                    <h3>What Happens Next?</h3>
                    <ol>
                        <li>Your complaint will be reviewed by the Procurement Administration Office</li>
                        <li>You will receive email updates as the investigation progresses</li>
                        <li>Target resolution time: Within 10 business days</li>
                        <li>You can track status through the supplier portal</li>
                    </ol>
                    
                    <div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0;">
                        <p style="margin: 0;"><strong>Important:</strong> If you have additional information to support your complaint, please reply to this email with the details.</p>
                    </div>
                    
                    <hr style="border: 1px solid #dee2e6; margin: 20px 0;"/>
                    
                    <p style="font-size: 12px; color: #6c757d;">
                        <strong>Contact Information:</strong><br/>
                        Procurement Administration Office<br/>
                        FDRE Mesob Center<br/>
                        Email: procurement@mesob.gov.et<br/>
                        <br/>
                        <em>This is an automated message from AUTO-033: Complaint Register System</em>
                    </p>
                </div>
            </div>
            """,
            'email_to': self.supplier_id.email,
            'email_from': self.env.company.email or 'procurement@mesob.gov.et',
            'auto_delete': False,
        }
        
        mail = self.env['mail.mail'].create(mail_values)
        mail.send()
        
        _logger.info(f"AUTO-033: Confirmation email sent to {self.supplier_id.name} ({self.supplier_id.email})")


class MesobProcurementComplaintExtended(models.Model):
    """AUTO-033: Extended Complaint Register with Contract Blocking Logic."""
    
    _inherit = 'mesob.procurement.complaint'
    
    blocks_contract_signature = fields.Boolean(
        string='Blocks Contract Signature',
        compute='_compute_contract_blocking',
        store=True,
        help='AUTO-033: True if this complaint blocks contract signature per FR-PROC-020'
    )
    
    was_blocking = fields.Boolean(
        string='Previously Blocked Contract',
        default=False,
        help='AUTO-033: Tracks if complaint was blocking contract before resolution'
    )
    
    @api.depends('state', 'is_standstill_complaint', 'related_contract_id')
    def _compute_contract_blocking(self):
        """AUTO-033: Determine if complaint blocks contract signature."""
        for rec in self:
            # Block if:
            # 1. Complaint is during standstill period AND
            # 2. Complaint is not yet resolved AND
            # 3. Related to a contract
            rec.blocks_contract_signature = (
                rec.is_standstill_complaint and
                rec.state not in ('resolved', 'rejected') and
                bool(rec.related_contract_id)
            )
    
    def action_resolve(self):
        """AUTO-033: Resolve complaint and unblock contract if applicable."""
        res = super().action_resolve()
        
        for rec in self:
            if rec.related_contract_id and rec.was_blocking:
                # Notify that contract is now unblocked
                rec.related_contract_id.message_post(
                    body=f"""<div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px;">
                        <h3 style="color: #155724;">✅ AUTO-033: Contract Signature Unblocked</h3>
                        <p><strong>Complaint Resolved:</strong> {rec.name}</p>
                        <p><strong>Resolution:</strong> {rec.resolution_description or 'Complaint resolved'}</p>
                        <p><strong>Contract:</strong> {rec.related_contract_id.name}</p>
                        <hr/>
                        <p><em>Standstill period complaint has been resolved. Contract signature may now proceed (FR-PROC-020).</em></p>
                    </div>""",
                    subject='Contract Signature Unblocked',
                    message_type='notification'
                )
                
                _logger.info(
                    f"AUTO-033: Contract {rec.related_contract_id.name} unblocked - "
                    f"Complaint {rec.name} resolved"
                )
        
        return res
    
    @api.model
    def check_contract_blocking(self, contract_id):
        """AUTO-033: Check if any complaints block the given contract.
        
        Args:
            contract_id: ID of contract to check
            
        Returns:
            dict: {'blocked': bool, 'blocking_complaints': recordset}
        """
        blocking_complaints = self.search([
            ('related_contract_id', '=', contract_id),
            ('blocks_contract_signature', '=', True)
        ])
        
        return {
            'blocked': len(blocking_complaints) > 0,
            'blocking_complaints': blocking_complaints
        }

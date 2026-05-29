# -*- coding: utf-8 -*-
"""
Mesob Inventory Handover Event (SRS 4.9)
FR-HO-001, FR-HO-002, FR-HO-003: Storekeeper handover stock taking
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class MesobInventoryHandoverEvent(models.Model):
    """
    FR-HO-001: Handover stock-taking workflow triggered by storekeeper status changes
    FR-HO-002: Incoming and outgoing storekeepers conduct stock-taking with witness
    FR-HO-003: Generate handover certificate in triplicate distribution
    """
    _name = 'mesob.inventory.handover.event'
    _description = 'Storekeeper Handover Event'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'handover_date desc, id desc'

    # Basic Information
    name = fields.Char(string='Reference', required=True, copy=False, readonly=True,
                      default=lambda self: _('New'), tracking=True)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('scheduled', 'Scheduled'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled')
    ], string='Status', default='draft', required=True, tracking=True)
    
    # FR-HO-001: Trigger Reasons
    trigger_reason = fields.Selection([
        ('leave', 'Leave/Retirement'),
        ('duty_travel', 'Duty Travel'),
        ('training', 'Training Outside Station'),
        ('promotion', 'Promotion'),
        ('transfer', 'Transfer'),
        ('medical', 'Medical Treatment'),
        ('other', 'Other')
    ], string='Handover Reason', required=True, tracking=True,
       help='Reason for storekeeper handover')
    reason_details = fields.Text(string='Reason Details')
    
    # FR-HO-002: Storekeepers
    outgoing_storekeeper_id = fields.Many2one('res.users', string='Outgoing Storekeeper',
                                             required=True, tracking=True,
                                             domain=[('groups_id', 'in', [lambda self: self.env.ref('mesob_inventory_base.group_mesob_storekeeper').id])])
    incoming_storekeeper_id = fields.Many2one('res.users', string='Incoming Storekeeper',
                                             required=True, tracking=True,
                                             domain=[('groups_id', 'in', [lambda self: self.env.ref('mesob_inventory_base.group_mesob_storekeeper').id])])
    
    # FR-HO-002: Witness Requirement
    witness_id = fields.Many2one('res.users', string='Competent Witness',
                                required=True, tracking=True,
                                help='Competent witness present during handover')
    witness_signature_date = fields.Datetime(string='Witness Signature Date/Time', readonly=True)
    
    # Dates
    handover_date = fields.Date(string='Handover Date', required=True, tracking=True,
                               default=fields.Date.today)
    scheduled_start = fields.Datetime(string='Scheduled Start')
    actual_start = fields.Datetime(string='Actual Start', readonly=True)
    actual_completion = fields.Datetime(string='Actual Completion', readonly=True)
    
    # Signatures
    outgoing_signature_date = fields.Datetime(string='Outgoing Signature Date/Time', readonly=True)
    incoming_signature_date = fields.Datetime(string='Incoming Signature Date/Time', readonly=True)
    
    # Stock Taking Integration
    stock_taking_event_id = fields.Many2one('mesob.inventory.stock.taking.event',
                                           string='Stock Taking Event',
                                           help='Associated stock taking event for this handover')
    
    # Locations
    location_ids = fields.Many2many('stock.location', string='Locations to Handover',
                                   help='Storage locations included in this handover')
    
    # FR-HO-003: Certificate
    certificate_generated = fields.Boolean(string='Certificate Generated', readonly=True)
    certificate_date = fields.Datetime(string='Certificate Generation Date', readonly=True)
    
    # Distribution Tracking (Triplicate)
    original_distributed = fields.Boolean(string='Original to PAO', tracking=True)
    original_distribution_date = fields.Datetime(string='Original Distribution Date')
    duplicate_distributed = fields.Boolean(string='Duplicate to Incoming', tracking=True)
    duplicate_distribution_date = fields.Datetime(string='Duplicate Distribution Date')
    triplicate_distributed = fields.Boolean(string='Triplicate to Outgoing', tracking=True)
    triplicate_distribution_date = fields.Datetime(string='Triplicate Distribution Date')
    
    # Responsible
    responsible_id = fields.Many2one('res.users', string='Responsible (PAO)',
                                    default=lambda self: self.env.user,
                                    required=True, tracking=True)
    
    # Notes
    notes = fields.Text(string='Notes')
    handover_notes = fields.Text(string='Handover Notes',
                                help='Notes from outgoing storekeeper about stock status')
    
    # Company
    company_id = fields.Many2one('res.company', string='Company',
                                default=lambda self: self.env.company)

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('mesob.handover.event') or _('New')
        return super().create(vals)

    @api.constrains('outgoing_storekeeper_id', 'incoming_storekeeper_id')
    def _check_different_storekeepers(self):
        """Ensure outgoing and incoming storekeepers are different"""
        for handover in self:
            if handover.outgoing_storekeeper_id == handover.incoming_storekeeper_id:
                raise ValidationError(_(
                    'Outgoing and incoming storekeepers must be different persons.'
                ))

    @api.constrains('witness_id', 'outgoing_storekeeper_id', 'incoming_storekeeper_id')
    def _check_witness_not_storekeeper(self):
        """Ensure witness is not one of the storekeepers"""
        for handover in self:
            if handover.witness_id in (handover.outgoing_storekeeper_id | handover.incoming_storekeeper_id):
                raise ValidationError(_(
                    'Witness cannot be the same person as outgoing or incoming storekeeper.'
                ))

    def action_schedule(self):
        """Schedule the handover"""
        self.ensure_one()
        if not self.location_ids:
            raise UserError(_('Please select at least one location for handover.'))
        self.state = 'scheduled'

    def action_start(self):
        """Start the handover process"""
        self.ensure_one()
        if self.state != 'scheduled':
            raise UserError(_('Only scheduled handovers can be started.'))
        
        # Create associated stock taking event
        if not self.stock_taking_event_id:
            stock_taking = self.env['mesob.inventory.stock.taking.event'].create({
                'name': _('Handover Stock Taking: %s') % self.name,
                'date_scheduled': self.handover_date,
                'location_ids': [(6, 0, self.location_ids.ids)],
                'responsible_id': self.responsible_id.id,
                'instructions': _('Stock taking for handover from %s to %s') % (
                    self.outgoing_storekeeper_id.name,
                    self.incoming_storekeeper_id.name
                ),
            })
            
            # Add team members
            stock_taking.team_member_ids.create([
                {
                    'event_id': stock_taking.id,
                    'user_id': self.incoming_storekeeper_id.id,
                    'role': 'counter',
                },
                {
                    'event_id': stock_taking.id,
                    'user_id': self.witness_id.id,
                    'role': 'witness',
                },
                {
                    'event_id': stock_taking.id,
                    'user_id': self.outgoing_storekeeper_id.id,
                    'role': 'guide',
                },
            ])
            
            self.stock_taking_event_id = stock_taking.id
        
        self.write({
            'state': 'in_progress',
            'actual_start': fields.Datetime.now()
        })

    def action_sign_outgoing(self):
        """Outgoing storekeeper signs"""
        self.ensure_one()
        if self.state != 'in_progress':
            raise UserError(_('Handover must be in progress to sign.'))
        self.outgoing_signature_date = fields.Datetime.now()

    def action_sign_incoming(self):
        """Incoming storekeeper signs"""
        self.ensure_one()
        if self.state != 'in_progress':
            raise UserError(_('Handover must be in progress to sign.'))
        self.incoming_signature_date = fields.Datetime.now()

    def action_sign_witness(self):
        """Witness signs"""
        self.ensure_one()
        if self.state != 'in_progress':
            raise UserError(_('Handover must be in progress to sign.'))
        self.witness_signature_date = fields.Datetime.now()

    def action_generate_certificate(self):
        """
        FR-HO-003: Generate handover certificate
        """
        self.ensure_one()
        if self.state != 'in_progress':
            raise UserError(_('Handover must be in progress to generate certificate.'))
        
        # Check all signatures
        if not all([self.outgoing_signature_date, self.incoming_signature_date, self.witness_signature_date]):
            raise UserError(_('All parties (outgoing, incoming, witness) must sign before generating certificate.'))
        
        # Check stock taking is completed
        if self.stock_taking_event_id and self.stock_taking_event_id.state != 'completed':
            raise UserError(_('Stock taking must be completed before generating certificate.'))
        
        self.write({
            'certificate_generated': True,
            'certificate_date': fields.Datetime.now()
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Certificate Generated'),
                'message': _('Handover certificate has been generated. Please distribute copies.'),
                'type': 'success',
                'sticky': True,
            }
        }

    def action_distribute_original(self):
        """Distribute original to PAO"""
        self.ensure_one()
        if not self.certificate_generated:
            raise UserError(_('Certificate must be generated first.'))
        self.write({
            'original_distributed': True,
            'original_distribution_date': fields.Datetime.now()
        })

    def action_distribute_duplicate(self):
        """Distribute duplicate to incoming storekeeper"""
        self.ensure_one()
        if not self.certificate_generated:
            raise UserError(_('Certificate must be generated first.'))
        self.write({
            'duplicate_distributed': True,
            'duplicate_distribution_date': fields.Datetime.now()
        })

    def action_distribute_triplicate(self):
        """Distribute triplicate to outgoing storekeeper"""
        self.ensure_one()
        if not self.certificate_generated:
            raise UserError(_('Certificate must be generated first.'))
        self.write({
            'triplicate_distributed': True,
            'triplicate_distribution_date': fields.Datetime.now()
        })

    def action_complete(self):
        """Complete the handover"""
        self.ensure_one()
        if self.state != 'in_progress':
            raise UserError(_('Only in-progress handovers can be completed.'))
        
        if not self.certificate_generated:
            raise UserError(_('Certificate must be generated before completing.'))
        
        if not all([self.original_distributed, self.duplicate_distributed, self.triplicate_distributed]):
            raise UserError(_('All certificate copies must be distributed before completing.'))
        
        self.write({
            'state': 'completed',
            'actual_completion': fields.Datetime.now()
        })

    def action_cancel(self):
        """Cancel the handover"""
        self.ensure_one()
        if self.state == 'completed':
            raise UserError(_('Completed handovers cannot be cancelled.'))
        self.state = 'cancelled'

    def action_view_stock_taking(self):
        """Smart button: View associated stock taking"""
        self.ensure_one()
        if not self.stock_taking_event_id:
            raise UserError(_('No stock taking event associated with this handover.'))
        
        return {
            'name': _('Stock Taking Event'),
            'type': 'ir.actions.act_window',
            'res_model': 'mesob.inventory.stock.taking.event',
            'res_id': self.stock_taking_event_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

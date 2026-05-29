# -*- coding: utf-8 -*-
"""
Mesob Inventory Stock Taking Event (SRS 4.8)
Manages stock taking exercises with preparation, execution, and verification
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime


class MesobInventoryStockTakingEvent(models.Model):
    """
    FR-ST-001, FR-ST-002, FR-ST-003: Stock Taking Event Management
    Represents a complete stock taking exercise from planning to completion
    """
    _name = 'mesob.inventory.stock.taking.event'
    _description = 'Stock Taking Event'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_scheduled desc, id desc'

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
    
    # FR-ST-001: Instructions and Training
    instructions = fields.Text(string='Stock Taking Instructions',
                              help='PAO instructions for the stock taking team')
    training_completed = fields.Boolean(string='Pre-Stock Taking Training Completed',
                                       tracking=True)
    training_date = fields.Date(string='Training Date')
    training_notes = fields.Text(string='Training Notes')
    
    # FR-ST-003: Scheduling
    date_scheduled = fields.Date(string='Scheduled Date', required=True, tracking=True)
    date_started = fields.Datetime(string='Actual Start Date/Time', readonly=True)
    date_completed = fields.Datetime(string='Actual Completion Date/Time', readonly=True)
    start_time = fields.Float(string='Start Time (Hours)', help='e.g., 8.0 for 8:00 AM')
    end_time = fields.Float(string='End Time (Hours)', help='e.g., 17.0 for 5:00 PM')
    break_time_start = fields.Float(string='Break Start (Hours)')
    break_time_end = fields.Float(string='Break End (Hours)')
    
    # Locations
    location_ids = fields.Many2many('stock.location', string='Locations to Count',
                                   help='Storage locations included in this stock taking')
    
    # Relationships
    team_member_ids = fields.One2many('mesob.inventory.stock.taking.team.member', 
                                     'event_id', string='Team Members')
    sheet_ids = fields.One2many('mesob.inventory.stock.taking.sheet', 
                               'event_id', string='Stock Taking Sheets')
    
    # Responsible
    responsible_id = fields.Many2one('res.users', string='Responsible (PAO)',
                                    default=lambda self: self.env.user,
                                    required=True, tracking=True)
    
    # Computed Fields
    sheet_count = fields.Integer(string='Sheet Count', compute='_compute_counts', store=True)
    sheet_issued_count = fields.Integer(string='Sheets Issued', compute='_compute_counts', store=True)
    sheet_verified_count = fields.Integer(string='Sheets Verified', compute='_compute_counts', store=True)
    discrepancy_count = fields.Integer(string='Discrepancy Count', compute='_compute_discrepancy_count', store=True)
    
    # Notes
    notes = fields.Text(string='Notes')
    
    # Company
    company_id = fields.Many2one('res.company', string='Company',
                                default=lambda self: self.env.company)

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('mesob.stock.taking.event') or _('New')
        return super().create(vals)

    @api.depends('sheet_ids', 'sheet_ids.state')
    def _compute_counts(self):
        for event in self:
            event.sheet_count = len(event.sheet_ids)
            event.sheet_issued_count = len(event.sheet_ids.filtered(lambda s: s.state in ['issued', 'returned', 'verified']))
            event.sheet_verified_count = len(event.sheet_ids.filtered(lambda s: s.state == 'verified'))

    @api.depends('sheet_ids', 'sheet_ids.line_ids', 'sheet_ids.line_ids.has_discrepancy')
    def _compute_discrepancy_count(self):
        for event in self:
            discrepancy_lines = event.sheet_ids.mapped('line_ids').filtered(lambda l: l.has_discrepancy)
            event.discrepancy_count = len(discrepancy_lines)

    def action_schedule(self):
        """Mark event as scheduled"""
        self.ensure_one()
        if not self.training_completed:
            raise UserError(_('Pre-stock taking training must be completed before scheduling.'))
        if not self.location_ids:
            raise UserError(_('Please select at least one location to count.'))
        if not self.team_member_ids:
            raise UserError(_('Please add team members before scheduling.'))
        self.state = 'scheduled'

    def action_generate_sheets(self):
        """
        FR-ST-002: Generate serially numbered stock-taking sheets
        in logical order matching storage layout and records
        """
        self.ensure_one()
        if self.state not in ['draft', 'scheduled']:
            raise UserError(_('Sheets can only be generated in Draft or Scheduled state.'))
        if not self.location_ids:
            raise UserError(_('Please select locations before generating sheets.'))
        
        # Clear existing draft sheets
        self.sheet_ids.filtered(lambda s: s.state == 'draft').unlink()
        
        # Get all items with stock in selected locations
        StockQuant = self.env['stock.quant']
        BinCard = self.env['mesob.inventory.bin.card']
        Sheet = self.env['mesob.inventory.stock.taking.sheet']
        
        sheet_sequence = 1
        for location in self.location_ids.sorted(key=lambda l: l.name):
            # Get items in this location from bin cards
            bin_cards = BinCard.search([
                ('location_id', '=', location.id),
                ('balance_quantity', '>', 0)
            ], order='classification_code, item_code')
            
            if not bin_cards:
                continue
            
            # Create a sheet for this location
            sheet = Sheet.create({
                'event_id': self.id,
                'location_id': location.id,
                'sequence': sheet_sequence,
                'state': 'draft'
            })
            
            # Add lines for each item
            for bin_card in bin_cards:
                sheet.line_ids.create({
                    'sheet_id': sheet.id,
                    'item_id': bin_card.item_id.id,
                    'location_id': location.id,
                    'expected_quantity': bin_card.balance_quantity,
                    'bin_card_balance': bin_card.balance_quantity,
                })
            
            sheet_sequence += 1
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sheets Generated'),
                'message': _('%d stock taking sheets have been generated.') % (sheet_sequence - 1),
                'type': 'success',
                'sticky': False,
            }
        }

    def action_start(self):
        """Start the stock taking event"""
        self.ensure_one()
        if self.state != 'scheduled':
            raise UserError(_('Only scheduled events can be started.'))
        if not self.sheet_ids:
            raise UserError(_('Please generate sheets before starting.'))
        self.write({
            'state': 'in_progress',
            'date_started': fields.Datetime.now()
        })

    def action_complete(self):
        """Complete the stock taking event"""
        self.ensure_one()
        if self.state != 'in_progress':
            raise UserError(_('Only in-progress events can be completed.'))
        
        # Check all sheets are verified
        unverified = self.sheet_ids.filtered(lambda s: s.state != 'verified')
        if unverified:
            raise UserError(_('All sheets must be verified before completing. %d sheets are still pending.') % len(unverified))
        
        self.write({
            'state': 'completed',
            'date_completed': fields.Datetime.now()
        })

    def action_cancel(self):
        """Cancel the stock taking event"""
        self.ensure_one()
        if self.state == 'completed':
            raise UserError(_('Completed events cannot be cancelled.'))
        self.state = 'cancelled'

    def action_view_sheets(self):
        """Smart button: View sheets"""
        self.ensure_one()
        return {
            'name': _('Stock Taking Sheets'),
            'type': 'ir.actions.act_window',
            'res_model': 'mesob.inventory.stock.taking.sheet',
            'view_mode': 'list,kanban,form',
            'domain': [('event_id', '=', self.id)],
            'context': {'default_event_id': self.id}
        }

    def action_view_discrepancies(self):
        """Smart button: View discrepancies"""
        self.ensure_one()
        discrepancy_lines = self.sheet_ids.mapped('line_ids').filtered(lambda l: l.has_discrepancy)
        return {
            'name': _('Discrepancies'),
            'type': 'ir.actions.act_window',
            'res_model': 'mesob.inventory.stock.taking.sheet.line',
            'view_mode': 'list,form',
            'domain': [('id', 'in', discrepancy_lines.ids)],
            'context': {'search_default_has_discrepancy': 1}
        }

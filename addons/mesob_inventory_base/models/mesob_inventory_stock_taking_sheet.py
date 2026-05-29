# -*- coding: utf-8 -*-
"""
Mesob Inventory Stock Taking Sheet (SRS 4.8)
FR-ST-002, FR-ST-004: Serially numbered sheets with issuance tracking
"""

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class MesobInventoryStockTakingSheet(models.Model):
    """
    FR-ST-002: Serially numbered stock-taking sheets
    FR-ST-004: Sheet issuance tracking with signature and return
    """
    _name = 'mesob.inventory.stock.taking.sheet'
    _description = 'Stock Taking Sheet'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'event_id desc, sequence, name'

    # Basic Information
    name = fields.Char(string='Sheet Number', required=True, copy=False, readonly=True,
                      default=lambda self: _('New'))
    event_id = fields.Many2one('mesob.inventory.stock.taking.event', string='Stock Taking Event',
                              required=True, ondelete='cascade', tracking=True)
    sequence = fields.Integer(string='Sequence', default=10,
                             help='Order of sheets in logical storage layout')
    location_id = fields.Many2one('stock.location', string='Location', required=True)
    
    # FR-ST-004: Issuance Tracking
    state = fields.Selection([
        ('draft', 'Draft'),
        ('issued', 'Issued'),
        ('returned', 'Returned'),
        ('verified', 'Verified')
    ], string='Status', default='draft', required=True, tracking=True)
    
    issued_to_id = fields.Many2one('res.users', string='Issued To (Recorder)',
                                   tracking=True)
    issued_date = fields.Datetime(string='Issue Date/Time', readonly=True)
    returned_date = fields.Datetime(string='Return Date/Time', readonly=True)
    verified_by_id = fields.Many2one('res.users', string='Verified By', readonly=True)
    verified_date = fields.Datetime(string='Verification Date/Time', readonly=True)
    
    # Lines
    line_ids = fields.One2many('mesob.inventory.stock.taking.sheet.line', 
                               'sheet_id', string='Sheet Lines')
    
    # Computed Fields
    line_count = fields.Integer(string='Line Count', compute='_compute_counts', store=True)
    counted_line_count = fields.Integer(string='Counted Lines', compute='_compute_counts', store=True)
    discrepancy_line_count = fields.Integer(string='Discrepancies', compute='_compute_counts', store=True)
    
    # Notes
    notes = fields.Text(string='Notes')
    
    # Company
    company_id = fields.Many2one(related='event_id.company_id', store=True)

    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('mesob.stock.taking.sheet') or _('New')
        return super().create(vals)

    @api.depends('line_ids', 'line_ids.is_counted', 'line_ids.has_discrepancy')
    def _compute_counts(self):
        for sheet in self:
            sheet.line_count = len(sheet.line_ids)
            sheet.counted_line_count = len(sheet.line_ids.filtered(lambda l: l.is_counted))
            sheet.discrepancy_line_count = len(sheet.line_ids.filtered(lambda l: l.has_discrepancy))

    def action_issue(self):
        """
        FR-ST-004: Issue sheet to recorder with signature requirement
        """
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(_('Only draft sheets can be issued.'))
        if not self.issued_to_id:
            raise UserError(_('Please select a recorder to issue this sheet to.'))
        
        self.write({
            'state': 'issued',
            'issued_date': fields.Datetime.now()
        })
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Sheet Issued'),
                'message': _('Sheet %s has been issued to %s') % (self.name, self.issued_to_id.name),
                'type': 'success',
            }
        }

    def action_return(self):
        """
        FR-ST-004: Mark sheet as returned by recorder
        """
        self.ensure_one()
        if self.state != 'issued':
            raise UserError(_('Only issued sheets can be returned.'))
        
        # Check if all lines are counted
        uncounted = self.line_ids.filtered(lambda l: not l.is_counted)
        if uncounted:
            raise UserError(_(
                'Cannot return sheet. %d items have not been counted yet.'
            ) % len(uncounted))
        
        self.write({
            'state': 'returned',
            'returned_date': fields.Datetime.now()
        })

    def action_verify(self):
        """
        FR-ST-006, FR-ST-008: Verify sheet and update bin cards
        Compare physical counts vs records and note bin cards
        """
        self.ensure_one()
        if self.state != 'returned':
            raise UserError(_('Only returned sheets can be verified.'))
        
        # FR-ST-008: Update bin cards with verification date (red-ink equivalent)
        BinCard = self.env['mesob.inventory.bin.card']
        for line in self.line_ids:
            # Find the latest bin card entry for this item/location
            bin_card = BinCard.search([
                ('item_id', '=', line.item_id.id),
                ('location_id', '=', line.location_id.id)
            ], order='date desc, id desc', limit=1)
            
            if bin_card:
                # Mark bin card as verified (red-ink equivalent)
                bin_card.write({
                    'last_stock_take_date': fields.Date.today(),
                    'verified_by_id': self.env.user.id
                })
        
        self.write({
            'state': 'verified',
            'verified_by_id': self.env.user.id,
            'verified_date': fields.Datetime.now()
        })
        
        # Show discrepancy summary if any
        if self.discrepancy_line_count > 0:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sheet Verified'),
                    'message': _('Sheet verified with %d discrepancies found.') % self.discrepancy_line_count,
                    'type': 'warning',
                    'sticky': True,
                }
            }
        else:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': _('Sheet Verified'),
                    'message': _('Sheet verified successfully. No discrepancies found.'),
                    'type': 'success',
                }
            }

    def action_reset_to_draft(self):
        """Reset sheet to draft (for corrections)"""
        self.ensure_one()
        if self.state == 'verified':
            raise UserError(_('Verified sheets cannot be reset.'))
        self.write({
            'state': 'draft',
            'issued_date': False,
            'returned_date': False
        })

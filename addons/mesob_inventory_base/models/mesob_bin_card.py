# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class MesobBinCard(models.Model):
    """
    Bin Card - Physical location tracking for inventory items
    Records all movements in/out of specific storage locations
    """
    _name = 'mesob.bin.card'
    _description = 'Bin Card (Physical Storage Location)'
    _order = 'date desc, id desc'
    _rec_name = 'display_name'

    # Header Information
    item_id = fields.Many2one('mesob.inventory.item', string='Item', required=True, ondelete='restrict')
    location = fields.Char(string='Bin Location', required=True, help='Physical storage location (e.g., Shelf A-1, Room 3)')
    date = fields.Date(string='Date', required=True, default=fields.Date.context_today)
    
    # Transaction Details
    transaction_type = fields.Selection([
        ('receipt', 'Receipt'),
        ('issue', 'Issue'),
        ('adjustment', 'Adjustment'),
        ('transfer', 'Transfer'),
    ], string='Transaction Type', required=True)
    
    reference = fields.Char(string='Reference', help='Document reference (voucher number, etc.)')
    description = fields.Text(string='Description')
    
    # Quantities
    quantity_in = fields.Float(string='Quantity In', digits='Product Unit of Measure', default=0.0)
    quantity_out = fields.Float(string='Quantity Out', digits='Product Unit of Measure', default=0.0)
    balance = fields.Float(string='Balance', digits='Product Unit of Measure', compute='_compute_balance', store=True)
    
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', required=True)
    
    # Tracking
    received_by_id = fields.Many2one('res.users', string='Received/Issued By')
    verified_by_id = fields.Many2one('res.users', string='Verified By')
    
    # Computed Fields
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)
    
    @api.depends('item_id', 'location', 'date')
    def _compute_display_name(self):
        for record in self:
            if record.item_id and record.location:
                record.display_name = f"{record.item_id.name} - {record.location} ({record.date})"
            else:
                record.display_name = _('New Bin Card')
    
    @api.depends('quantity_in', 'quantity_out')
    def _compute_balance(self):
        """Compute running balance for each bin location"""
        # Group by item and location
        items_locations = {}
        for record in self:
            key = (record.item_id.id, record.location)
            if key not in items_locations:
                items_locations[key] = []
            items_locations[key].append(record)
        
        # Calculate balance for each group
        for (item_id, location), records in items_locations.items():
            # Get all records for this item/location ordered by date
            all_records = self.search([
                ('item_id', '=', item_id),
                ('location', '=', location),
            ], order='date asc, id asc')
            
            running_balance = 0.0
            for rec in all_records:
                running_balance = running_balance + rec.quantity_in - rec.quantity_out
                rec.balance = running_balance
    
    @api.constrains('quantity_in', 'quantity_out')
    def _check_quantities(self):
        for record in self:
            if record.quantity_in < 0 or record.quantity_out < 0:
                raise ValidationError(_('Quantities cannot be negative.'))
            if record.quantity_in > 0 and record.quantity_out > 0:
                raise ValidationError(_('A transaction cannot have both quantity in and quantity out.'))


class MesobBinCardLine(models.Model):
    """
    Bin Card Line - Individual transaction line items
    """
    _name = 'mesob.bin.card.line'
    _description = 'Bin Card Line'
    _order = 'date desc'

    bin_card_id = fields.Many2one('mesob.bin.card', string='Bin Card', required=True, ondelete='cascade')
    item_id = fields.Many2one(related='bin_card_id.item_id', string='Item', store=True)
    date = fields.Date(string='Date', required=True, default=fields.Date.context_today)
    reference = fields.Char(string='Reference')
    quantity_in = fields.Float(string='In', digits='Product Unit of Measure')
    quantity_out = fields.Float(string='Out', digits='Product Unit of Measure')
    balance = fields.Float(string='Balance', digits='Product Unit of Measure')
    remarks = fields.Char(string='Remarks')

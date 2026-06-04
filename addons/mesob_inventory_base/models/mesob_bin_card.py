# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class MesobBinCard(models.Model):
    """
    Bin Card - Physical location tracking for inventory items at sub-classification level
    Records all movements in/out of specific storage locations aggregated by sub-classification
    """
    _name = 'mesob.bin.card'
    _description = 'Bin Card (Physical Storage Location)'
    _order = 'date desc, id desc'
    _rec_name = 'display_name'

    # Header Information - Track by Sub-Classification instead of individual items
    major_classification_id = fields.Many2one(
        'mesob.inventory.major.classification', 
        string='Major Classification', 
        required=True, 
        ondelete='restrict'
    )
    sub_classification_id = fields.Many2one(
        'mesob.inventory.sub.classification', 
        string='Sub Classification', 
        required=True, 
        ondelete='restrict',
        index=True
    )
    location = fields.Char(
        string='Bin Location', 
        required=True, 
        default='Main Store',
        help='Physical storage location (e.g., Shelf A-1, Room 3)'
    )
    date = fields.Date(
        string='Date', 
        required=True, 
        default=fields.Date.context_today
    )
    
    # Transaction Details
    transaction_type = fields.Selection([
        ('receipt', 'Receipt'),
        ('issue', 'Issue'),
        ('adjustment', 'Adjustment'),
        ('transfer', 'Transfer'),
    ], string='Transaction Type', required=True)
    
    reference = fields.Char(string='Reference', help='Document reference (voucher number, etc.)')
    description = fields.Text(string='Description')
    
    # Quantities - Renamed for clarity
    quantity_received = fields.Float(
        string='Received', 
        digits='Product Unit of Measure', 
        default=0.0,
        help='Quantity received in this transaction'
    )
    quantity_distributed = fields.Float(
        string='Distributed', 
        digits='Product Unit of Measure', 
        default=0.0,
        help='Quantity distributed/issued in this transaction'
    )
    balance = fields.Float(
        string='Balance', 
        digits='Product Unit of Measure', 
        compute='_compute_balance', 
        store=True,
        help='Running balance after this transaction'
    )
    
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', required=True)
    
    # Tracking
    received_by_id = fields.Many2one('res.users', string='Received/Issued By')
    verified_by_id = fields.Many2one('res.users', string='Verified By')
    
    # Computed Fields
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)
    item_count = fields.Integer(
        string='Item Count',
        compute='_compute_item_count',
        help='Number of individual items in this sub-classification'
    )
    
    @api.depends('sub_classification_id', 'location', 'date')
    def _compute_display_name(self):
        for record in self:
            if record.sub_classification_id and record.location:
                record.display_name = f"{record.sub_classification_id.name} - {record.location} ({record.date})"
            else:
                record.display_name = _('New Bin Card')
    
    def _compute_item_count(self):
        """Count individual items in this sub-classification"""
        for record in self:
            if record.sub_classification_id:
                record.item_count = self.env['mesob.inventory.item'].search_count([
                    ('sub_classification_id', '=', record.sub_classification_id.id)
                ])
            else:
                record.item_count = 0
    
    @api.depends('quantity_received', 'quantity_distributed')
    def _compute_balance(self):
        """Compute running balance for each sub-classification at location"""
        for record in self:
            # Get previous balance
            previous_records = self.search([
                ('sub_classification_id', '=', record.sub_classification_id.id),
                ('location', '=', record.location),
                ('date', '<', record.date),
            ], order='date desc, id desc', limit=1)
            
            if not previous_records:
                # Also check same date but earlier ID
                previous_records = self.search([
                    ('sub_classification_id', '=', record.sub_classification_id.id),
                    ('location', '=', record.location),
                    ('date', '=', record.date),
                    ('id', '<', record.id),
                ], order='date desc, id desc', limit=1)
            
            previous_balance = previous_records[0].balance if previous_records else 0.0
            record.balance = previous_balance + record.quantity_received - record.quantity_distributed
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to recompute balances after inserting new records"""
        records = super().create(vals_list)
        
        # Recompute balances for all affected sub-classifications
        for record in records:
            if record.sub_classification_id:
                self._recompute_balances_for_subclass(
                    record.sub_classification_id.id,
                    record.location
                )
        
        return records
    
    def _recompute_balances_for_subclass(self, sub_classification_id, location):
        """Recompute all balances for a sub-classification at a location in chronological order"""
        # Get all bin card entries for this sub-classification at this location
        all_entries = self.search([
            ('sub_classification_id', '=', sub_classification_id),
            ('location', '=', location)
        ], order='date asc, id asc')
        
        running_balance = 0.0
        for entry in all_entries:
            running_balance = running_balance + entry.quantity_received - entry.quantity_distributed
            # Direct SQL update to avoid recursion
            self.env.cr.execute(
                "UPDATE mesob_bin_card SET balance = %s WHERE id = %s",
                (running_balance, entry.id)
            )
        
        # Invalidate cache to force refresh
        all_entries.invalidate_recordset(['balance'])
    
    @api.constrains('quantity_received', 'quantity_distributed')
    def _check_quantities(self):
        for record in self:
            if record.quantity_received < 0 or record.quantity_distributed < 0:
                raise ValidationError(_('Quantities cannot be negative.'))
            if record.quantity_received > 0 and record.quantity_distributed > 0:
                raise ValidationError(_('A transaction cannot have both received and distributed quantities.'))
    
    def action_view_items(self):
        """Open list of individual items in this sub-classification"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Items: {self.sub_classification_id.name}',
            'res_model': 'mesob.inventory.item',
            'view_mode': 'list,form',
            'domain': [('sub_classification_id', '=', self.sub_classification_id.id)],
            'context': {
                'create': False,
                'default_sub_classification_id': self.sub_classification_id.id,
                'default_classification_id': self.major_classification_id.id,
            },
        }


class MesobBinCardLine(models.Model):
    """
    Bin Card Line - Deprecated, keeping for backwards compatibility
    Now bin cards track at sub-classification level directly
    """
    _name = 'mesob.bin.card.line'
    _description = 'Bin Card Line (Deprecated)'
    _order = 'date desc'

    bin_card_id = fields.Many2one('mesob.bin.card', string='Bin Card', ondelete='cascade')
    date = fields.Date(string='Date', default=fields.Date.context_today)
    reference = fields.Char(string='Reference')
    quantity_in = fields.Float(string='In', digits='Product Unit of Measure')
    quantity_out = fields.Float(string='Out', digits='Product Unit of Measure')
    balance = fields.Float(string='Balance', digits='Product Unit of Measure')
    remarks = fields.Char(string='Remarks')

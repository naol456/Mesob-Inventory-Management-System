# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from lxml import etree


class MesobStockRecordCard(models.Model):
    """
    Stock Record Card - Comprehensive inventory tracking with FIFO valuation
    Tracks all stock movements with cost and valuation
    """
    _name = 'mesob.stock.record.card'
    _description = 'Stock Record Card (Model 19)'
    _order = 'date desc, id desc'
    _rec_name = 'display_name'

    # Header
    item_id = fields.Many2one('mesob.inventory.item', string='Item', required=True, ondelete='restrict', index=True)
    sub_classification_id = fields.Many2one(
        comodel_name='mesob.inventory.sub.classification',
        string='Sub Classification',
        related='item_id.sub_classification_id',
        store=True,
        index=True
    )
    date = fields.Date(string='Date', required=True, default=fields.Date.context_today, index=True)
    
    # Transaction Details
    transaction_type = fields.Selection([
        ('opening', 'Opening Balance'),
        ('receipt', 'Receipt'),
        ('issue', 'Issue'),
        ('adjustment', 'Adjustment'),
        ('return', 'Return'),
    ], string='Transaction Type', required=True, index=True)
    
    reference = fields.Char(string='Reference Document', help='Voucher number, PO number, etc.')
    description = fields.Text(string='Description')
    
    # Quantities
    quantity_in = fields.Float(string='Quantity Received', digits='Product Unit of Measure', default=0.0)
    quantity_out = fields.Float(string='Quantity Issued', digits='Product Unit of Measure', default=0.0)
    quantity_balance = fields.Float(string='Balance Quantity', digits='Product Unit of Measure', compute='_compute_balance', store=True)
    
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', required=True)
    
    # Valuation (FIFO)
    unit_cost = fields.Monetary(string='Unit Cost', currency_field='currency_id')
    unit_cost_out = fields.Monetary(string='Issued Unit Price', currency_field='currency_id', compute='_compute_unit_cost_out')
    total_cost_in = fields.Monetary(string='Total Cost In', currency_field='currency_id', compute='_compute_costs', store=True)
    total_cost_out = fields.Monetary(string='Total Cost Out', currency_field='currency_id', compute='_compute_costs', store=True)
    balance_value = fields.Monetary(string='Balance Value', currency_field='currency_id', compute='_compute_balance', store=True)
    average_cost = fields.Monetary(string='Average Unit Cost', currency_field='currency_id', compute='_compute_balance', store=True)
    
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    
    # FIFO Layers
    fifo_layer_ids = fields.One2many('mesob.stock.fifo.layer', 'stock_record_id', string='FIFO Layers')
    
    # Tracking
    source_document = fields.Char(string='Source Document')
    created_by_id = fields.Many2one('res.users', string='Created By', default=lambda self: self.env.user)
    
    # Computed
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)
    
    @api.depends('item_id', 'date', 'reference')
    def _compute_display_name(self):
        for record in self:
            if record.item_id:
                parts = [record.item_id.name, record.date.strftime('%Y-%m-%d') if record.date else '']
                if record.reference:
                    parts.append(record.reference)
                record.display_name = ' - '.join(filter(None, parts))
            else:
                record.display_name = _('New Stock Record')
    
    @api.model
    def get_view(self, view_id=None, view_type='form', **options):
        """Override to hide 'New' button for Storekeeper and PAO (read-only roles)"""
        result = super(MesobStockRecordCard, self).get_view(view_id, view_type, **options)
        
        if view_type in ['tree', 'form']:
            doc = etree.XML(result['arch'])
            
            # Stock Clerk: Full access (maintains stock record cards)
            # Storekeeper: Read-only (for reference)
            # PAO: Read-only (oversight)
            
            is_storekeeper = self.env.user.has_group('mesob_inventory_base.group_mesob_storekeeper')
            is_pao = self.env.user.has_group('mesob_inventory_base.group_mesob_pao')
            is_stock_clerk = self.env.user.has_group('mesob_inventory_base.group_mesob_stock_clerk')
            
            # Hide create/edit/delete for Storekeeper and PAO (read-only)
            if (is_storekeeper or is_pao) and not is_stock_clerk:
                if view_type == 'tree':
                    # Hide "New" button in list view
                    for node in doc.xpath("//tree"):
                        node.set('create', '0')
                        node.set('edit', '0')
                        node.set('delete', '0')
                elif view_type == 'form':
                    # Hide "New", "Edit", "Duplicate", "Delete" in form view
                    for node in doc.xpath("//form"):
                        node.set('create', '0')
                        node.set('edit', '0')
                        node.set('delete', '0')
            
            result['arch'] = etree.tostring(doc, encoding='unicode')
        
        return result
    
    @api.depends('quantity_in', 'unit_cost')
    def _compute_costs(self):
        for record in self:
            record.total_cost_in = record.quantity_in * record.unit_cost
            # Cost out is calculated from FIFO layers
            record.total_cost_out = sum(record.fifo_layer_ids.mapped('cost_out'))

    @api.depends('quantity_out', 'total_cost_out')
    def _compute_unit_cost_out(self):
        for record in self:
            if record.quantity_out > 0:
                record.unit_cost_out = record.total_cost_out / record.quantity_out
            else:
                record.unit_cost_out = 0.0
    
    @api.depends('quantity_in', 'quantity_out', 'total_cost_in', 'total_cost_out')
    def _compute_balance(self):
        """Compute running balance using FIFO"""
        for record in self:
            # Get previous balance
            previous = self.search([
                ('item_id', '=', record.item_id.id),
                ('date', '<', record.date),
            ], order='date desc, id desc', limit=1)
            
            prev_qty = previous.quantity_balance if previous else 0.0
            prev_value = previous.balance_value if previous else 0.0
            
            # Calculate new balance
            record.quantity_balance = prev_qty + record.quantity_in - record.quantity_out
            record.balance_value = prev_value + record.total_cost_in - record.total_cost_out
            
            # Calculate average cost
            if record.quantity_balance > 0:
                record.average_cost = record.balance_value / record.quantity_balance
            else:
                record.average_cost = 0.0
    
    @api.constrains('quantity_in', 'quantity_out')
    def _check_quantities(self):
        for record in self:
            if record.quantity_in < 0 or record.quantity_out < 0:
                raise ValidationError(_('Quantities cannot be negative.'))
    
    def action_create_fifo_layers(self):
        """Create FIFO layers for receipts"""
        self.ensure_one()
        if self.transaction_type == 'receipt' and self.quantity_in > 0:
            self.env['mesob.stock.fifo.layer'].create({
                'stock_record_id': self.id,
                'item_id': self.item_id.id,
                'date': self.date,
                'quantity': self.quantity_in,
                'quantity_remaining': self.quantity_in,
                'unit_cost': self.unit_cost,
                'total_cost': self.total_cost_in,
            })

    def action_consume_fifo(self):
        """Consume FIFO layers for issues/issuances"""
        self.ensure_one()
        if self.transaction_type == 'issue' and self.quantity_out > 0:
            qty_to_consume = self.quantity_out
            total_cost_consumed = 0.0
            
            # Find all active (unexhausted) cost layers for this item in date asc order
            active_layers = self.env['mesob.stock.fifo.layer'].search([
                ('item_id', '=', self.item_id.id),
                ('is_exhausted', '=', False)
            ], order='date asc, id asc')
            
            for layer in active_layers:
                if qty_to_consume <= 0.0:
                    break
                
                # Consume from this layer
                consume_qty = min(qty_to_consume, layer.quantity_remaining)
                cost_consumed = layer.consume_quantity(consume_qty)
                
                qty_to_consume -= consume_qty
                total_cost_consumed += cost_consumed
                
            self.total_cost_out = total_cost_consumed


class MesobStockFIFOLayer(models.Model):
    """
    FIFO Layer - Tracks cost layers for FIFO valuation
    Each receipt creates a new layer, issues consume from oldest layers first
    """
    _name = 'mesob.stock.fifo.layer'
    _description = 'Stock FIFO Cost Layer'
    _order = 'date asc, id asc'

    stock_record_id = fields.Many2one('mesob.stock.record.card', string='Stock Record', required=True, ondelete='cascade')
    item_id = fields.Many2one('mesob.inventory.item', string='Item', required=True, ondelete='restrict')
    date = fields.Date(string='Receipt Date', required=True)
    
    # Quantities
    quantity = fields.Float(string='Original Quantity', digits='Product Unit of Measure', required=True)
    quantity_remaining = fields.Float(string='Remaining Quantity', digits='Product Unit of Measure', required=True)
    quantity_consumed = fields.Float(string='Consumed Quantity', digits='Product Unit of Measure', compute='_compute_consumed')
    
    # Costs
    unit_cost = fields.Monetary(string='Unit Cost', currency_field='currency_id', required=True)
    total_cost = fields.Monetary(string='Total Cost', currency_field='currency_id', compute='_compute_total_cost', store=True)
    cost_out = fields.Monetary(string='Cost Out', currency_field='currency_id', default=0.0)
    
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    
    # Status
    is_exhausted = fields.Boolean(string='Exhausted', compute='_compute_exhausted', store=True)
    
    @api.depends('quantity', 'quantity_remaining')
    def _compute_consumed(self):
        for record in self:
            record.quantity_consumed = record.quantity - record.quantity_remaining
    
    @api.depends('quantity', 'unit_cost')
    def _compute_total_cost(self):
        for record in self:
            record.total_cost = record.quantity * record.unit_cost
    
    @api.depends('quantity_remaining')
    def _compute_exhausted(self):
        for record in self:
            record.is_exhausted = record.quantity_remaining <= 0.0
    
    def consume_quantity(self, qty_to_consume):
        """Consume quantity from this FIFO layer"""
        self.ensure_one()
        if qty_to_consume > self.quantity_remaining:
            raise ValidationError(_('Cannot consume more than remaining quantity.'))
        
        cost_consumed = qty_to_consume * self.unit_cost
        self.quantity_remaining -= qty_to_consume
        self.cost_out += cost_consumed
        
        return cost_consumed


class MesobStockValuationConfig(models.Model):
    """
    Stock Valuation Configuration
    Defines valuation methods and settings per item or category
    """
    _name = 'mesob.stock.valuation.config'
    _description = 'Stock Valuation Configuration'

    name = fields.Char(string='Configuration Name', required=True)
    
    # Scope
    item_id = fields.Many2one('mesob.inventory.item', string='Specific Item', ondelete='cascade')
    classification_id = fields.Many2one('mesob.inventory.major.classification', string='Classification', ondelete='cascade')
    
    # Valuation Method
    valuation_method = fields.Selection([
        ('fifo', 'FIFO (First In, First Out)'),
        ('average', 'Average Cost'),
        ('standard', 'Standard Cost'),
    ], string='Valuation Method', required=True, default='fifo')
    
    # Settings
    auto_create_layers = fields.Boolean(string='Auto Create FIFO Layers', default=True)
    track_by_location = fields.Boolean(string='Track by Location', default=False)
    allow_negative_stock = fields.Boolean(string='Allow Negative Stock', default=False)
    
    # Default Costs
    standard_cost = fields.Monetary(string='Standard Cost', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    
    active = fields.Boolean(string='Active', default=True)

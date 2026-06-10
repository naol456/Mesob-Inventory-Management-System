# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MesobStockReorderAlert(models.Model):
    """Stock Reorder Alert - Automated alerts for low stock (FR-SC-003)"""
    _name = 'mesob.stock.reorder.alert'
    _description = 'Stock Reorder Alert'
    _order = 'alert_date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char('Alert Reference', required=True, default='New', readonly=True, copy=False)
    
    item_id = fields.Many2one('mesob.inventory.item', 'Item', required=True, tracking=True)
    alert_date = fields.Date('Alert Date', default=fields.Date.today, required=True, tracking=True)
    
    alert_type = fields.Selection([
        ('reorder', 'Reorder Level Reached'),
        ('minimum', 'Below Minimum Level'),
        ('hasten', 'Hasten Pending Delivery'),
    ], required=True, tracking=True)
    
    # Stock levels
    current_stock = fields.Float('Current Stock', required=True)
    reorder_level = fields.Float('Reorder Level')
    minimum_level = fields.Float('Minimum Level')
    maximum_level = fields.Float('Maximum Level')
    
    # Outstanding deliveries
    outstanding_qty = fields.Float('Outstanding Delivery Qty', default=0.0)
    outstanding_order_ids = fields.Many2many(
        'mesob.inventory.receiving',
        string='Outstanding Orders',
        help='Pending receiving orders for this item'
    )
    
    # Recommended action
    recommended_order_qty = fields.Float(
        'Recommended Order Qty',
        compute='_compute_recommended_qty',
        store=True,
        help='Recommended quantity to order'
    )
    
    state = fields.Selection([
        ('new', 'New Alert'),
        ('acknowledged', 'Acknowledged'),
        ('ordered', 'Order Created'),
        ('resolved', 'Resolved'),
        ('dismissed', 'Dismissed'),
    ], default='new', required=True, tracking=True)
    
    # Actions taken
    notes = fields.Text('Notes')
    acknowledged_by_id = fields.Many2one('res.users', 'Acknowledged By', tracking=True)
    acknowledged_date = fields.Datetime('Acknowledged Date')
    
    requisition_id = fields.Many2one('mesob.inventory.requisition', 'Created Requisition')
    resolved_by_id = fields.Many2one('res.users', 'Resolved By')
    resolved_date = fields.Datetime('Resolved Date')
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('mesob.stock.reorder.alert') or 'New'
        return super().create(vals_list)
    
    @api.depends('item_id', 'current_stock', 'outstanding_qty', 'maximum_level', 'reorder_level')
    def _compute_recommended_qty(self):
        """Calculate recommended order quantity (FR-SC-003)"""
        for alert in self:
            if not alert.item_id:
                alert.recommended_order_qty = 0.0
                continue
            
            # Target = Maximum level (or reorder level * 2 if no max)
            target = alert.maximum_level or (alert.reorder_level * 2)
            
            # Recommended = Target - Current - Outstanding
            recommended = target - alert.current_stock - alert.outstanding_qty
            alert.recommended_order_qty = max(0.0, recommended)
    
    def action_acknowledge(self):
        """Acknowledge the alert"""
        self.ensure_one()
        if self.state != 'new':
            raise UserError('Only new alerts can be acknowledged.')
        
        self.write({
            'state': 'acknowledged',
            'acknowledged_by_id': self.env.user.id,
            'acknowledged_date': fields.Datetime.now(),
        })
        
        self.message_post(body=f'Alert acknowledged by {self.env.user.name}')
    
    def action_create_requisition(self):
        """Create requisition from alert"""
        self.ensure_one()
        
        if self.state not in ['new', 'acknowledged']:
            raise UserError('Cannot create requisition from this alert state.')
        
        # Create requisition
        requisition = self.env['mesob.inventory.requisition'].create({
            'requisition_date': fields.Date.today(),
            'requested_by_id': self.env.user.id,
            'notes': f'Auto-generated from reorder alert {self.name}',
        })
        
        # Add line
        self.env['mesob.inventory.requisition.line'].create({
            'requisition_id': requisition.id,
            'item_id': self.item_id.id,
            'quantity_requested': self.recommended_order_qty,
            'uom_id': self.item_id.uom_id.id,
        })
        
        self.write({
            'state': 'ordered',
            'requisition_id': requisition.id,
        })
        
        self.message_post(body=f'Requisition {requisition.name} created')
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mesob.inventory.requisition',
            'res_id': requisition.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_resolve(self):
        """Mark alert as resolved"""
        self.ensure_one()
        
        self.write({
            'state': 'resolved',
            'resolved_by_id': self.env.user.id,
            'resolved_date': fields.Datetime.now(),
        })
        
        self.message_post(body=f'Alert resolved by {self.env.user.name}')
    
    def action_dismiss(self):
        """Dismiss the alert"""
        self.ensure_one()
        
        self.write({'state': 'dismissed'})
        self.message_post(body=f'Alert dismissed by {self.env.user.name}')
    
    @api.model
    def _cron_check_stock_levels(self):
        """Scheduled action to check stock levels and create alerts (FR-SC-003)"""
        items = self.env['mesob.inventory.item'].search([
            ('active', '=', True),
            ('reorder_level', '>', 0),
        ])
        
        alerts_created = 0
        
        for item in items:
            # Get current stock
            bin_card = self.env['mesob.bin.card'].search([
                ('sub_classification_id', '=', item.sub_classification_id.id)
            ], limit=1, order='date desc, id desc')
            current_stock = bin_card.balance if bin_card else 0.0
            
            # Check if below reorder level
            if current_stock <= item.reorder_level:
                # Check for outstanding deliveries
                outstanding_orders = self.env['mesob.inventory.receiving'].search([
                    ('state', 'in', ['draft', 'in_progress']),
                    ('line_ids.item_id', '=', item.id),
                ])
                
                outstanding_qty = sum(
                    line.qty_received 
                    for order in outstanding_orders 
                    for line in order.line_ids 
                    if line.item_id.id == item.id
                )
                
                # Check if alert already exists
                existing_alert = self.search([
                    ('item_id', '=', item.id),
                    ('state', 'in', ['new', 'acknowledged']),
                ], limit=1)
                
                if not existing_alert:
                    # Determine alert type
                    if current_stock < item.minimum_level:
                        alert_type = 'minimum'
                    elif item.hastening_level > 0 and current_stock < item.hastening_level:
                        alert_type = 'hasten'
                    else:
                        alert_type = 'reorder'
                    
                    # Create new alert
                    self.create({
                        'item_id': item.id,
                        'alert_type': alert_type,
                        'current_stock': current_stock,
                        'reorder_level': item.reorder_level,
                        'minimum_level': item.minimum_level,
                        'maximum_level': item.maximum_level,
                        'outstanding_qty': outstanding_qty,
                        'outstanding_order_ids': [(6, 0, outstanding_orders.ids)],
                    })
                    
                    alerts_created += 1
        
        return alerts_created

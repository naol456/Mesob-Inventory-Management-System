# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class MesobStockReorderAlert(models.Model):
    """Stock Reorder Alert - Automated alerts for low stock (FR-SC-003)
    
    AUTO-023: Reorder-Level Auto-Requisition
    - System monitors stock on hand vs. reorder level (FR-SC-003)
    - Auto-checks for outstanding POs to prevent duplicate orders
    - Auto-generates draft Purchase Requisition if no outstanding delivery
    - Notifies Procurement Officer with suggested order quantity
    """
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
    
    # AUTO-063: Outstanding deliveries tracking
    outstanding_qty = fields.Float('Outstanding Delivery Qty', default=0.0)
    outstanding_order_ids = fields.Many2many(
        'mesob.inventory.receiving',
        string='Outstanding Orders',
        help='AUTO-063: Pending receiving orders for this item'
    )
    has_outstanding_delivery = fields.Boolean(
        'Has Outstanding Delivery',
        compute='_compute_outstanding_delivery',
        store=True,
        help='AUTO-063: True if there are open POs for this item'
    )
    earliest_expected_delivery = fields.Date(
        'Earliest Expected Delivery',
        compute='_compute_outstanding_delivery',
        store=True,
        help='AUTO-063: Earliest expected delivery date from outstanding POs'
    )
    should_create_new_order = fields.Boolean(
        'Should Create New Order',
        compute='_compute_should_create_order',
        help='AUTO-063: False if outstanding delivery will arrive within lead time'
    )
    lead_time_days = fields.Integer(
        'Lead Time (Days)',
        related='item_id.total_lead_time',
        help='AUTO-063: Item lead time for delivery check'
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
    
    @api.depends('outstanding_order_ids', 'outstanding_qty')
    def _compute_outstanding_delivery(self):
        """AUTO-063: Check if there are outstanding deliveries and calculate earliest ETA."""
        for alert in self:
            if alert.outstanding_order_ids:
                alert.has_outstanding_delivery = True
                # Find earliest expected delivery date
                expected_dates = alert.outstanding_order_ids.filtered(
                    lambda o: o.expected_delivery_date
                ).mapped('expected_delivery_date')
                alert.earliest_expected_delivery = min(expected_dates) if expected_dates else False
            else:
                alert.has_outstanding_delivery = False
                alert.earliest_expected_delivery = False
    
    @api.depends('has_outstanding_delivery', 'earliest_expected_delivery', 'lead_time_days', 'alert_date')
    def _compute_should_create_order(self):
        """AUTO-063: Determine if new order should be created based on outstanding deliveries.
        
        Logic (FR-SC-003):
        - If no outstanding delivery: CREATE NEW ORDER
        - If outstanding delivery exists:
          - Check if expected delivery is within lead time
          - If YES: DO NOT CREATE (alert only)
          - If NO or unknown: CREATE NEW ORDER
        
        This prevents duplicate orders while ensuring timely restocking.
        """
        for alert in self:
            if not alert.has_outstanding_delivery:
                # No outstanding delivery - need new order
                alert.should_create_new_order = True
            elif not alert.earliest_expected_delivery:
                # Outstanding but no delivery date - create order to be safe
                alert.should_create_new_order = True
            else:
                # Check if delivery is within lead time
                today = fields.Date.today()
                lead_time_days = alert.lead_time_days or 30  # Default 30 days
                days_until_delivery = (alert.earliest_expected_delivery - today).days
                
                if days_until_delivery <= lead_time_days:
                    # Delivery will arrive within lead time - don't create duplicate
                    alert.should_create_new_order = False
                else:
                    # Delivery too far out - need new order
                    alert.should_create_new_order = True
    
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
        """AUTO-063: Acknowledge the alert with smart notification."""
        self.ensure_one()
        if self.state != 'new':
            raise UserError('Only new alerts can be acknowledged.')
        
        self.write({
            'state': 'acknowledged',
            'acknowledged_by_id': self.env.user.id,
            'acknowledged_date': fields.Datetime.now(),
        })
        
        # AUTO-063: Smart acknowledgment message
        if self.has_outstanding_delivery:
            if self.should_create_new_order:
                message = f"""Alert acknowledged by {self.env.user.name}.
                <br/><strong>AUTO-063 Note:</strong> Outstanding delivery exists (ETA: {self.earliest_expected_delivery}), 
                but delivery is beyond lead time. New order recommended."""
            else:
                message = f"""Alert acknowledged by {self.env.user.name}.
                <br/><strong>AUTO-063 Note:</strong> Outstanding delivery exists (ETA: {self.earliest_expected_delivery}). 
                Expected delivery within lead time - no new order needed."""
        else:
            message = f"""Alert acknowledged by {self.env.user.name}.
            <br/><strong>AUTO-063 Note:</strong> No outstanding deliveries found. New order required."""
        
        self.message_post(body=message)
        
        return True
    
    def action_create_requisition(self):
        """AUTO-063: Create requisition from alert with duplicate order prevention."""
        self.ensure_one()
        
        if self.state not in ['new', 'acknowledged']:
            raise UserError('Cannot create requisition from this alert state.')
        
        # AUTO-063: Warn if outstanding delivery exists within lead time
        if self.has_outstanding_delivery and not self.should_create_new_order:
            raise UserError(
                f'AUTO-063 Duplicate Order Prevention:\n\n'
                f'Outstanding delivery for this item already exists!\n'
                f'PO Number(s): {", ".join(self.outstanding_order_ids.mapped("name"))}\n'
                f'Outstanding Quantity: {self.outstanding_qty:.2f}\n'
                f'Expected Delivery: {self.earliest_expected_delivery}\n'
                f'Days Until Delivery: {(self.earliest_expected_delivery - fields.Date.today()).days}\n\n'
                f'The outstanding delivery is expected within the lead time ({self.lead_time_days} days).\n'
                f'Creating a duplicate order is not recommended.\n\n'
                f'If you still want to proceed, dismiss this alert and create a manual requisition.'
            )
        
        # Create requisition
        requisition = self.env['mesob.inventory.requisition'].create({
            'requisition_date': fields.Date.today(),
            'requested_by_id': self.env.user.id,
            'notes': f'Auto-generated from reorder alert {self.name}\n'
                     f'AUTO-063: No duplicate order detected. Safe to proceed.',
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
        
        # AUTO-063: Enhanced notification
        self.message_post(
            body=f"""<div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px;">
                <h3>✅ Requisition Created: {requisition.name}</h3>
                <p><strong>Item:</strong> {self.item_id.item_code} - {self.item_id.name}</p>
                <p><strong>Quantity:</strong> {self.recommended_order_qty:.2f} {self.item_id.uom_id.name}</p>
                <hr/>
                <p><em>AUTO-063: Duplicate order check passed. No conflicting outstanding deliveries found.</em></p>
            </div>"""
        )
        
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
        """AUTO-063: Scheduled action to check stock levels with outstanding delivery intelligence (FR-SC-003).
        
        Smart Features:
        - Detects items below reorder level
        - Checks for outstanding deliveries (open POs)
        - Calculates if existing PO will arrive within lead time
        - Prevents duplicate order alerts
        - Recommends action based on delivery timing
        """
        items = self.env['mesob.inventory.item'].search([
            ('active', '=', True),
            ('reorder_level', '>', 0),
        ])
        
        alerts_created = 0
        duplicate_orders_prevented = 0
        
        for item in items:
            # Get current stock
            bin_card = self.env['mesob.bin.card'].search([
                ('sub_classification_id', '=', item.sub_classification_id.id)
            ], limit=1, order='date desc, id desc')
            current_stock = bin_card.balance if bin_card else 0.0
            
            # AUTO-063: Check if below reorder level
            if current_stock <= item.reorder_level:
                # AUTO-063: Check for outstanding deliveries
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
                    elif hasattr(item, 'hastening_level') and item.hastening_level > 0 and current_stock < item.hastening_level:
                        alert_type = 'hasten'
                    else:
                        alert_type = 'reorder'
                    
                    # AUTO-063: Create new alert with outstanding delivery data
                    new_alert = self.create({
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
                    
                    # AUTO-063: Send smart notification
                    if new_alert.has_outstanding_delivery:
                        if new_alert.should_create_new_order:
                            notification_type = "warning"
                            message = f"""<div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px;">
                                <h3>⚠ AUTO-063: Reorder Alert with Outstanding Delivery</h3>
                                <p><strong>Item:</strong> {item.item_code} - {item.name}</p>
                                <p><strong>Current Stock:</strong> {current_stock:.2f} (Reorder Level: {item.reorder_level:.2f})</p>
                                <p><strong>Outstanding PO:</strong> {", ".join(outstanding_orders.mapped("name"))}</p>
                                <p><strong>Outstanding Qty:</strong> {outstanding_qty:.2f}</p>
                                <p><strong>Expected Delivery:</strong> {new_alert.earliest_expected_delivery or "Unknown"}</p>
                                <hr/>
                                <p style="color: #856404;"><strong>⚠ ALERT:</strong> Outstanding delivery exists but is beyond lead time ({item.lead_time_days} days).</p>
                                <p><strong>Recommendation:</strong> Consider creating additional order or hastening existing delivery.</p>
                            </div>"""
                        else:
                            notification_type = "info"
                            message = f"""<div style="background-color: #d1ecf1; border-left: 4px solid #0c5460; padding: 15px;">
                                <h3>ℹ AUTO-063: Reorder Alert - No Action Needed</h3>
                                <p><strong>Item:</strong> {item.item_code} - {item.name}</p>
                                <p><strong>Current Stock:</strong> {current_stock:.2f} (Reorder Level: {item.reorder_level:.2f})</p>
                                <p><strong>Outstanding PO:</strong> {", ".join(outstanding_orders.mapped("name"))}</p>
                                <p><strong>Outstanding Qty:</strong> {outstanding_qty:.2f}</p>
                                <p><strong>Expected Delivery:</strong> {new_alert.earliest_expected_delivery}</p>
                                <p><strong>Days Until Delivery:</strong> {(new_alert.earliest_expected_delivery - fields.Date.today()).days}</p>
                                <hr/>
                                <p style="color: #0c5460;"><strong>✓ Good News:</strong> Outstanding delivery will arrive within lead time.</p>
                                <p><strong>Recommendation:</strong> Monitor delivery. No duplicate order needed.</p>
                            </div>"""
                            duplicate_orders_prevented += 1
                    else:
                        notification_type = "danger"
                        message = f"""<div style="background-color: #f8d7da; border-left: 4px solid #dc3545; padding: 15px;">
                            <h3>🚨 AUTO-063: Urgent Reorder Alert</h3>
                            <p><strong>Item:</strong> {item.item_code} - {item.name}</p>
                            <p><strong>Current Stock:</strong> {current_stock:.2f} (Reorder Level: {item.reorder_level:.2f})</p>
                            <p><strong>Outstanding Deliveries:</strong> None</p>
                            <hr/>
                            <p style="color: #721c24;"><strong>⚠ URGENT:</strong> No outstanding orders found for this item.</p>
                            <p><strong>Recommendation:</strong> Create requisition immediately.</p>
                        </div>"""
                    
                    new_alert.message_post(body=message)
        
        # Summary log
        import logging
        _logger = logging.getLogger(__name__)
        _logger.info(
            f"AUTO-063: Stock level check completed - "
            f"Alerts created: {alerts_created}, "
            f"Duplicate orders prevented: {duplicate_orders_prevented}"
        )
        
        return {
            'alerts_created': alerts_created,
            'duplicate_orders_prevented': duplicate_orders_prevented,
        }

    # ── Role-Based Access Control (UI Level) ────────────────────────

    @api.model
    def get_view(self, view_id=None, view_type="form", **options):
        """Hide New button for Stock Clerk on both list and form views.
        
        Stock Clerks can acknowledge alerts and create requisitions,
        but cannot create new alerts (system/PAO only).
        """
        result = super(MesobStockReorderAlert, self).get_view(view_id, view_type, **options)
        
        # Import lxml for XML manipulation
        from lxml import etree
        
        # Check if user is Stock Clerk
        is_stock_clerk = self.env.user.has_group("mesob_inventory_base.group_mesob_stock_clerk")
        
        # Hide "New" button for Stock Clerk in list and form views
        if is_stock_clerk and view_type in ("list", "form"):
            doc = etree.XML(result["arch"])
            
            # For list view, hide create button
            if view_type == "list":
                # Set create="false" on tree/list element
                for node in doc.xpath("//list | //tree"):
                    node.set("create", "false")
            
            # For form view, hide create button in breadcrumb
            elif view_type == "form":
                # Set create="false" on form element
                for node in doc.xpath("//form"):
                    node.set("create", "false")
            
            result["arch"] = etree.tostring(doc, encoding="unicode")
        
        return result

# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from datetime import datetime


class MesobAssetRegister(models.Model):
    """
    Unified Asset Register - Central Asset Management Workspace
    
    Executive/Management interface answering:
    - How many laptops do we own?
    - Who has them (with photo & full contact)?
    - Which branch/department owns them?
    - Which assets are missing/idle?
    - Which employee has the most assets?
    - Where is this printer?
    - Which assets belong to Finance?
    
    Auto-syncs with inventory items and aggregates custody/location/lifecycle data.
    """
    _name = 'mesob.asset.dashboard'
    _description = 'Asset Register'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'display_name'
    _order = 'item_code'
    
    # Core Identification
    item_id = fields.Many2one('mesob.inventory.item', string='Inventory Item', 
                              required=True, ondelete='cascade', index=True)
    item_code = fields.Char(related='item_id.item_code', string='Asset Code', store=True, index=True)
    display_name = fields.Char(compute='_compute_display_name', store=True)
    item_name = fields.Char(related='item_id.name', string='Asset Name', store=True)
    item_name_am = fields.Char(related='item_id.name_am', store=True)
    description = fields.Text(related='item_id.description')
    
    # Classification
    major_classification_id = fields.Many2one(related='item_id.classification_id', store=True)
    sub_classification_id = fields.Many2one(related='item_id.sub_classification_id', store=True)
    is_controlled = fields.Boolean(related='item_id.is_controlled', store=True)
    is_surplus = fields.Boolean(related='item_id.is_surplus', store=True)
    
    # Asset State (Executive View)
    asset_state = fields.Selection([
        ('in_stock', 'In Stock'),
        ('issued', 'Issued'),
        ('idle', 'Idle'),
        ('missing', 'Missing'),
    ], compute='_compute_asset_state', store=True)
    
    # Quantities
    quantity_total = fields.Float(compute='_compute_quantities', digits='Product Unit of Measure')
    quantity_in_stock = fields.Float(compute='_compute_quantities', digits='Product Unit of Measure')
    quantity_issued = fields.Float(compute='_compute_quantities', digits='Product Unit of Measure')
    quantity_available = fields.Float(compute='_compute_quantities', digits='Product Unit of Measure')
    
    # Custody (with photo)
    current_holder_id = fields.Many2one('res.users', compute='_compute_custody', store=True)
    holder_name = fields.Char(related='current_holder_id.name', store=True)
    holder_email = fields.Char(related='current_holder_id.email')
    holder_phone = fields.Char(related='current_holder_id.phone')
    holder_image = fields.Image(related='current_holder_id.image_128')
    
    # Location & Ownership
    current_location = fields.Char(compute='_compute_location', store=True)
    owning_branch = fields.Char(default='Headquarters (HQ)')
    using_department_id = fields.Many2one('mesob.department', compute='_compute_custody', store=True)
    
    # Financial
    unit_cost = fields.Monetary(compute='_compute_valuation', currency_field='currency_id')
    total_value = fields.Monetary(compute='_compute_valuation', currency_field='currency_id')
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    
    # Lifecycle
    first_received_date = fields.Date(compute='_compute_lifecycle', store=True)
    last_movement_date = fields.Datetime(compute='_compute_lifecycle', store=True)
    days_since_last_movement = fields.Integer(compute='_compute_lifecycle')
    issue_count = fields.Integer(compute='_compute_lifecycle')
    
    @api.depends('item_code', 'item_name')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.item_code} - {rec.item_name}" if rec.item_code and rec.item_name else ''
    
    @api.depends('item_id')
    def _compute_quantities(self):
        for rec in self:
            stock_record = self.env['mesob.stock.record.card'].search([
                ('item_id', '=', rec.item_id.id)
            ], order='date desc', limit=1)
            rec.quantity_total = stock_record.quantity_balance if stock_record else 0.0
            rec.quantity_in_stock = stock_record.quantity_balance if stock_record else 0.0
            issued_lines = self.env['mesob.inventory.issue.voucher.line'].search([
                ('item_id', '=', rec.item_id.id),
                ('voucher_id.state', 'in', ['issued', 'received'])
            ])
            rec.quantity_issued = sum(issued_lines.mapped('quantity_issued'))
            rec.quantity_available = rec.quantity_in_stock - rec.quantity_issued
    
    @api.depends('item_id', 'quantity_issued', 'days_since_last_movement')
    def _compute_asset_state(self):
        for rec in self:
            if rec.quantity_issued > 0:
                rec.asset_state = 'issued'
            elif rec.quantity_in_stock <= 0:
                rec.asset_state = 'missing'
            elif rec.days_since_last_movement and rec.days_since_last_movement > 180:
                rec.asset_state = 'idle'
            else:
                rec.asset_state = 'in_stock'
    
    @api.depends('item_id')
    def _compute_custody(self):
        for rec in self:
            issue_line = self.env['mesob.inventory.issue.voucher.line'].search([
                ('item_id', '=', rec.item_id.id),
                ('voucher_id.state', 'in', ['issued', 'received'])
            ], order='id desc', limit=1)
            if issue_line and issue_line.voucher_id.requisition_id:
                req = issue_line.voucher_id.requisition_id
                rec.current_holder_id = req.requested_by_id.id if req.requested_by_id else False
                rec.using_department_id = req.department_id.id if req.department_id else False
            else:
                rec.current_holder_id = False
                rec.using_department_id = False
    
    @api.depends('item_id')
    def _compute_location(self):
        for rec in self:
            issue_line = self.env['mesob.inventory.issue.voucher.line'].search([
                ('item_id', '=', rec.item_id.id),
                ('voucher_id.state', 'in', ['issued', 'received'])
            ], order='id desc', limit=1)
            if issue_line and issue_line.voucher_id:
                rec.current_location = 'Issued to User'
            else:
                bin_card = self.env['mesob.bin.card'].search([
                    ('sub_classification_id', '=', rec.sub_classification_id.id)
                ], order='id desc', limit=1)
                rec.current_location = bin_card.location if bin_card else 'Main Store'
    
    @api.depends('item_id')
    def _compute_valuation(self):
        for rec in self:
            stock_record = self.env['mesob.stock.record.card'].search([
                ('item_id', '=', rec.item_id.id),
                ('transaction_type', '=', 'receipt')
            ], order='date desc', limit=1)
            rec.unit_cost = stock_record.unit_cost if stock_record else 0.0
            rec.total_value = rec.unit_cost * rec.quantity_total
    
    @api.depends('item_id')
    def _compute_lifecycle(self):
        for rec in self:
            first_receipt = self.env['mesob.inventory.receiving.line'].search([
                ('sub_classification_id', '=', rec.sub_classification_id.id if rec.sub_classification_id else False),
                ('receiving_id.state', '=', 'accepted')
            ], order='id asc', limit=1)
            if first_receipt and first_receipt.receiving_id:
                rec.first_received_date = first_receipt.receiving_id.received_date
            else:
                rec.first_received_date = False
            
            last_stock = self.env['mesob.stock.record.card'].search([
                ('item_id', '=', rec.item_id.id)
            ], order='date desc', limit=1)
            rec.last_movement_date = last_stock.date if last_stock else False
            if rec.last_movement_date:
                delta = datetime.now() - datetime.combine(
                    rec.last_movement_date.date() if isinstance(rec.last_movement_date, datetime) else rec.last_movement_date,
                    datetime.min.time()
                )
                rec.days_since_last_movement = delta.days
            else:
                rec.days_since_last_movement = 0
            rec.issue_count = self.env['mesob.inventory.issue.voucher.line'].search_count([
                ('item_id', '=', rec.item_id.id)
            ])
    
    def action_view_history(self):
        self.ensure_one()
        return {
            'name': f'History: {self.item_code}',
            'type': 'ir.actions.act_window',
            'res_model': 'mesob.stock.record.card',
            'view_mode': 'list,form',
            'domain': [('item_id', '=', self.item_id.id)],
        }
    
    @api.model
    def action_sync_from_items(self):
        """Auto-populate from existing items"""
        items = self.env['mesob.inventory.item'].search([])
        created = 0
        for item in items:
            if not self.search([('item_id', '=', item.id)], limit=1):
                self.create({'item_id': item.id})
                created += 1
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Asset Register Synchronized'),
                'message': _('%s assets registered') % created,
                'type': 'success',
            }
        }

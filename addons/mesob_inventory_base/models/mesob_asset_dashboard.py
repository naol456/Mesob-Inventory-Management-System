# -*- coding: utf-8 -*-
from odoo import models, fields, api, _


class MesobAssetDashboard(models.Model):
    """
    Professional Asset Management Dashboard
    
    Comprehensive view answering:
    - What are the assets?
    - Where are they?
    - Who holds them?
    - What's their condition?
    - Purchase & maintenance history
    - Custody & transfer history
    - Warranty & disposal status
    
    All information consolidated in one professional dashboard.
    """
    _name = 'mesob.asset.dashboard'
    _description = 'Asset Management Dashboard'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _rec_name = 'item_id'
    _order = 'item_code'
    
    # ═══════════════════════════════════════════════════════════════
    # CORE ASSET IDENTIFICATION
    # ═══════════════════════════════════════════════════════════════
    
    item_id = fields.Many2one(
        'mesob.inventory.item',
        string='Asset',
        required=True,
        ondelete='cascade',
    )
    
    item_code = fields.Char(
        related='item_id.item_code',
        string='Asset Code',
        store=True,
        index=True,
    )
    
    item_name = fields.Char(
        related='item_id.name',
        string='Asset Name',
        store=True,
    )
    
    item_name_am = fields.Char(
        related='item_id.name_am',
        string='Asset Name (Amharic)',
        store=True,
    )
    
    description = fields.Text(
        related='item_id.description',
        string='Description',
    )
    
    # ═══════════════════════════════════════════════════════════════
    # CLASSIFICATION & ORGANIZATION
    # ═══════════════════════════════════════════════════════════════
    
    major_classification_id = fields.Many2one(
        related='item_id.classification_id',
        string='Major Classification',
        store=True,
    )
    
    sub_classification_id = fields.Many2one(
        related='item_id.sub_classification_id',
        string='Sub Classification',
        store=True,
    )
    
    # ═══════════════════════════════════════════════════════════════
    # CURRENT LOCATION & CUSTODY
    # ═══════════════════════════════════════════════════════════════
    
    current_location = fields.Char(
        string='Current Location',
        compute='_compute_asset_details',
        store=True,
        help='Physical storage location or bin',
    )
    
    current_holder = fields.Char(
        string='Current Holder',
        compute='_compute_asset_details',
        store=True,
        help='Person currently holding/using the asset',
    )
    
    holder_full_name = fields.Char(
        string='Holder Full Name',
        compute='_compute_asset_details',
        store=True,
    )
    
    holder_email = fields.Char(
        string='Holder Email',
        compute='_compute_asset_details',
        store=True,
    )
    
    holder_phone = fields.Char(
        string='Holder Phone',
        compute='_compute_asset_details',
        store=True,
    )
    
    using_department_id = fields.Many2one(
        'mesob.department',
        string='Using Department',
        compute='_compute_asset_details',
        store=True,
        help='Department currently using the asset',
    )
    
    # ═══════════════════════════════════════════════════════════════
    # OWNERSHIP & APPROVAL
    # ═══════════════════════════════════════════════════════════════
    
    owning_organization = fields.Char(
        string='Owning Organization',
        default='FDRE Mesob Center',
        help='Organization that owns the asset',
    )
    
    approved_by = fields.Many2one(
        'res.users',
        string='Assignment Approved By',
        compute='_compute_asset_details',
        store=True,
        help='User who approved the current assignment',
    )
    
    approval_date = fields.Datetime(
        string='Approval Date',
        compute='_compute_asset_details',
        store=True,
    )
    
    # ═══════════════════════════════════════════════════════════════
    # STOCK STATUS & CONDITION
    # ═══════════════════════════════════════════════════════════════
    
    quantity_on_hand = fields.Float(
        string='Quantity on Hand',
        compute='_compute_stock_details',
        digits='Product Unit of Measure',
    )
    
    quantity_issued = fields.Float(
        string='Quantity Issued',
        compute='_compute_stock_details',
        digits='Product Unit of Measure',
    )
    
    quantity_available = fields.Float(
        string='Quantity Available',
        compute='_compute_stock_details',
        digits='Product Unit of Measure',
    )
    
    condition = fields.Selection([
        ('excellent', 'Excellent'),
        ('good', 'Good'),
        ('fair', 'Fair'),
        ('poor', 'Poor'),
        ('damaged', 'Damaged'),
        ('under_repair', 'Under Repair'),
    ], string='Condition', default='good')
    
    is_controlled = fields.Boolean(
        related='item_id.is_controlled',
        string='Controlled Material',
        store=True,
    )
    
    is_surplus = fields.Boolean(
        related='item_id.is_surplus',
        string='Surplus/Disposal Candidate',
        store=True,
    )
    
    # ═══════════════════════════════════════════════════════════════
    # PURCHASE & ACQUISITION
    # ═══════════════════════════════════════════════════════════════
    
    purchase_date = fields.Date(
        string='Purchase Date',
        compute='_compute_purchase_details',
        store=True,
    )
    
    supplier_id = fields.Many2one(
        'res.partner',
        string='Supplier',
        compute='_compute_purchase_details',
        store=True,
    )
    
    purchase_order_ref = fields.Char(
        string='Purchase Order',
        compute='_compute_purchase_details',
        store=True,
    )
    
    unit_cost = fields.Monetary(
        string='Unit Cost',
        compute='_compute_purchase_details',
        currency_field='currency_id',
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
    )
    
    # ═══════════════════════════════════════════════════════════════
    # WARRANTY & MAINTENANCE
    # ═══════════════════════════════════════════════════════════════
    
    warranty_start_date = fields.Date(
        string='Warranty Start',
        compute='_compute_warranty_details',
        store=True,
    )
    
    warranty_end_date = fields.Date(
        string='Warranty End',
    )
    
    is_under_warranty = fields.Boolean(
        string='Under Warranty',
        compute='_compute_warranty_status',
    )
    
    days_until_warranty_expires = fields.Integer(
        string='Days Until Warranty Expires',
        compute='_compute_warranty_status',
    )
    
    maintenance_status = fields.Selection([
        ('up_to_date', 'Up to Date'),
        ('due_soon', 'Due Soon'),
        ('overdue', 'Overdue'),
        ('not_applicable', 'Not Applicable'),
    ], string='Maintenance Status', default='not_applicable')
    
    last_maintenance_date = fields.Date(
        string='Last Maintenance',
    )
    
    next_maintenance_date = fields.Date(
        string='Next Maintenance Due',
    )
    
    # ═══════════════════════════════════════════════════════════════
    # TRANSFER & MOVEMENT HISTORY
    # ═══════════════════════════════════════════════════════════════
    
    transfer_count = fields.Integer(
        string='Number of Transfers',
        compute='_compute_transfer_history',
    )
    
    last_transfer_date = fields.Datetime(
        string='Last Transfer Date',
        compute='_compute_transfer_history',
    )
    
    previous_location = fields.Char(
        string='Previous Location',
        compute='_compute_transfer_history',
    )
    
    previous_holder = fields.Char(
        string='Previous Holder',
        compute='_compute_transfer_history',
    )
    
    # ═══════════════════════════════════════════════════════════════
    # DISPOSAL STATUS
    # ═══════════════════════════════════════════════════════════════
    
    scheduled_for_disposal = fields.Boolean(
        string='Scheduled for Disposal',
        default=False,
    )
    
    disposal_reason = fields.Text(
        string='Disposal Reason',
    )
    
    disposal_date = fields.Date(
        string='Scheduled Disposal Date',
    )
    
    # ═══════════════════════════════════════════════════════════════
    # COMPUTED FIELDS
    # ═══════════════════════════════════════════════════════════════
    
    @api.depends('item_id')
    def _compute_asset_details(self):
        """Compute current holder, location, department, and approval details"""
        for rec in self:
            # Find the latest issue voucher for this item
            issue_line = self.env['mesob.inventory.issue.voucher.line'].search([
                ('item_id', '=', rec.item_id.id),
                ('voucher_id.state', 'in', ['issued', 'received'])
            ], order='id desc', limit=1)
            
            if issue_line and issue_line.voucher_id:
                voucher = issue_line.voucher_id
                requisition = voucher.requisition_id
                
                if requisition:
                    # Holder information
                    if requisition.requested_by_id:
                        user = requisition.requested_by_id
                        rec.current_holder = user.name
                        rec.holder_full_name = user.name
                        rec.holder_email = user.email or ''
                        rec.holder_phone = user.phone or ''
                    else:
                        rec.current_holder = ''
                        rec.holder_full_name = ''
                        rec.holder_email = ''
                        rec.holder_phone = ''
                    
                    # Department
                    rec.using_department_id = requisition.department_id.id if requisition.department_id else False
                    
                    # Approval details
                    rec.approved_by = requisition.reviewed_by_id.id if requisition.reviewed_by_id else False
                    rec.approval_date = requisition.reviewed_at
                else:
                    rec.current_holder = ''
                    rec.holder_full_name = ''
                    rec.holder_email = ''
                    rec.holder_phone = ''
                    rec.using_department_id = False
                    rec.approved_by = False
                    rec.approval_date = False
                
                # Location from voucher
                rec.current_location = voucher.location or 'Main Store'
            else:
                # Not issued - check bin card for location
                bin_card = self.env['mesob.bin.card'].search([
                    ('sub_classification_id', '=', rec.sub_classification_id.id)
                ], order='id desc', limit=1)
                
                rec.current_location = bin_card.location if bin_card else 'Main Store'
                rec.current_holder = 'In Stock'
                rec.holder_full_name = ''
                rec.holder_email = ''
                rec.holder_phone = ''
                rec.using_department_id = False
                rec.approved_by = False
                rec.approval_date = False
    
    @api.depends('item_id')
    def _compute_stock_details(self):
        """Compute stock quantities"""
        for rec in self:
            # Get latest stock record card for this item
            stock_record = self.env['mesob.stock.record.card'].search([
                ('item_id', '=', rec.item_id.id)
            ], order='date desc, id desc', limit=1)
            
            if stock_record:
                rec.quantity_on_hand = stock_record.quantity_balance
            else:
                rec.quantity_on_hand = 0.0
            
            # Count issued quantity
            issued_lines = self.env['mesob.inventory.issue.voucher.line'].search([
                ('item_id', '=', rec.item_id.id),
                ('voucher_id.state', 'in', ['issued', 'received'])
            ])
            rec.quantity_issued = sum(issued_lines.mapped('quantity'))
            
            # Available = On Hand - Issued
            rec.quantity_available = rec.quantity_on_hand - rec.quantity_issued
    
    @api.depends('item_id')
    def _compute_purchase_details(self):
        """Compute purchase information"""
        for rec in self:
            # Find the first receiving record for this item
            receiving_line = self.env['mesob.inventory.receiving.line'].search([
                ('sub_classification_id', '=', rec.sub_classification_id.id if rec.sub_classification_id else False),
                ('receiving_id.state', '=', 'accepted')
            ], order='receiving_id.received_date asc', limit=1)
            
            if receiving_line and receiving_line.receiving_id:
                receiving = receiving_line.receiving_id
                rec.purchase_date = receiving.received_date
                rec.supplier_id = receiving.supplier_id.id if receiving.supplier_id else False
                rec.purchase_order_ref = receiving.purchase_order_ref or ''
                
                # Try to get unit cost from stock record
                stock_record = self.env['mesob.stock.record.card'].search([
                    ('item_id', '=', rec.item_id.id),
                    ('transaction_type', '=', 'receipt')
                ], order='date asc', limit=1)
                rec.unit_cost = stock_record.unit_cost if stock_record else 0.0
            else:
                rec.purchase_date = False
                rec.supplier_id = False
                rec.purchase_order_ref = ''
                rec.unit_cost = 0.0
    
    @api.depends('purchase_date')
    def _compute_warranty_details(self):
        """Compute warranty start date (same as purchase date)"""
        for rec in self:
            rec.warranty_start_date = rec.purchase_date
    
    @api.depends('warranty_start_date', 'warranty_end_date')
    def _compute_warranty_status(self):
        """Compute if item is under warranty and days remaining"""
        today = fields.Date.today()
        for rec in self:
            if rec.warranty_end_date:
                rec.is_under_warranty = rec.warranty_end_date >= today
                if rec.is_under_warranty:
                    delta = rec.warranty_end_date - today
                    rec.days_until_warranty_expires = delta.days
                else:
                    rec.days_until_warranty_expires = 0
            else:
                rec.is_under_warranty = False
                rec.days_until_warranty_expires = 0
    
    @api.depends('item_id')
    def _compute_transfer_history(self):
        """Compute transfer history"""
        for rec in self:
            # Count gate passes for this item
            gate_passes = self.env['mesob.gate.pass.line'].search([
                ('item_id', '=', rec.item_id.id),
                ('gate_pass_id.state', '=', 'approved')
            ])
            
            rec.transfer_count = len(gate_passes)
            
            if gate_passes:
                latest_pass = gate_passes.sorted(key=lambda x: x.gate_pass_id.departure_datetime, reverse=True)[0]
                rec.last_transfer_date = latest_pass.gate_pass_id.departure_datetime
                rec.previous_location = 'Previous location data not available'
                rec.previous_holder = 'Previous holder data not available'
            else:
                rec.last_transfer_date = False
                rec.previous_location = ''
                rec.previous_holder = ''
    
    # ═══════════════════════════════════════════════════════════════
    # ACTIONS
    # ═══════════════════════════════════════════════════════════════
    
    def action_view_full_history(self):
        """Open full transaction history for this asset"""
        self.ensure_one()
        return {
            'name': f'Asset History: {self.item_code}',
            'type': 'ir.actions.act_window',
            'res_model': 'mesob.stock.record.card',
            'view_mode': 'list,form',
            'domain': [('item_id', '=', self.item_id.id)],
            'context': {'default_item_id': self.item_id.id},
        }
    
    def action_view_transfers(self):
        """View all gate passes/transfers for this asset"""
        self.ensure_one()
        return {
            'name': f'Transfers: {self.item_code}',
            'type': 'ir.actions.act_window',
            'res_model': 'mesob.gate.pass',
            'view_mode': 'list,form',
            'domain': [('line_ids.item_id', '=', self.item_id.id)],
        }
    
    def action_schedule_maintenance(self):
        """Schedule maintenance for this asset"""
        self.ensure_one()
        # Placeholder for future maintenance scheduling feature
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Maintenance Scheduling'),
                'message': _('Maintenance scheduling feature coming soon.'),
                'type': 'info',
                'sticky': False,
            }
        }

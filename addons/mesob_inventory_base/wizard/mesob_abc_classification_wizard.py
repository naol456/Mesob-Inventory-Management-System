# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MesobABCClassificationWizard(models.TransientModel):
    """ABC Classification Wizard - Calculate ABC classes (FR-SC-005)"""
    _name = 'mesob.abc.classification.wizard'
    _description = 'ABC Classification Wizard'
    
    # Classification criteria
    class_a_percentage = fields.Float(
        'Class A Threshold (%)',
        default=80.0,
        required=True,
        help='Cumulative value % for Class A (typically 70-80%)'
    )
    class_b_percentage = fields.Float(
        'Class B Threshold (%)',
        default=95.0,
        required=True,
        help='Cumulative value % for Class B (typically 90-95%)'
    )
    
    # Filters
    classification_id = fields.Many2one(
        'mesob.inventory.major.classification',
        'Filter by Classification',
        help='Optional: Calculate ABC only for specific classification'
    )
    
    # Period for usage calculation
    period_months = fields.Integer(
        'Period (Months)',
        default=12,
        required=True,
        help='Number of months to analyze for usage value'
    )
    
    # Results
    result_line_ids = fields.One2many(
        'mesob.abc.classification.wizard.line',
        'wizard_id',
        'Classification Results'
    )
    
    total_items = fields.Integer('Total Items', compute='_compute_summary')
    class_a_count = fields.Integer('Class A Count', compute='_compute_summary')
    class_b_count = fields.Integer('Class B Count', compute='_compute_summary')
    class_c_count = fields.Integer('Class C Count', compute='_compute_summary')
    total_value = fields.Monetary('Total Usage Value', compute='_compute_summary', currency_field='currency_id')
    
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    
    @api.depends('result_line_ids')
    def _compute_summary(self):
        for wizard in self:
            wizard.total_items = len(wizard.result_line_ids)
            wizard.class_a_count = len(wizard.result_line_ids.filtered(lambda l: l.recommended_class == 'A'))
            wizard.class_b_count = len(wizard.result_line_ids.filtered(lambda l: l.recommended_class == 'B'))
            wizard.class_c_count = len(wizard.result_line_ids.filtered(lambda l: l.recommended_class == 'C'))
            wizard.total_value = sum(wizard.result_line_ids.mapped('usage_value'))
    
    def action_calculate_abc(self):
        """Calculate ABC classification"""
        self.ensure_one()
        
        # Clear previous results
        self.result_line_ids.unlink()
        
        # Get all active items
        domain = [('active', '=', True)]
        if self.classification_id:
            domain.append(('classification_id', '=', self.classification_id.id))
        
        items = self.env['mesob.inventory.item'].search(domain)
        
        if not items:
            raise UserError('No items found matching the criteria.')
        
        # Calculate usage value for each item
        from datetime import timedelta
        period_start = fields.Date.today() - timedelta(days=self.period_months * 30)
        
        item_usage = []
        for item in items:
            # Get issue voucher lines for this item in the period
            issue_lines = self.env['mesob.inventory.issue.voucher.line'].search([
                ('item_id', '=', item.id),
                ('issue_voucher_id.issue_date', '>=', period_start),
                ('issue_voucher_id.state', '=', 'issued'),
            ])
            
            # Calculate total usage value
            usage_value = sum(issue_lines.mapped('total_value'))
            usage_qty = sum(issue_lines.mapped('quantity_issued'))
            
            item_usage.append({
                'item': item,
                'usage_value': usage_value,
                'usage_qty': usage_qty,
            })
        
        # Sort by usage value (descending)
        item_usage.sort(key=lambda x: x['usage_value'], reverse=True)
        
        # Calculate total usage value
        total_value = sum(item['usage_value'] for item in item_usage)
        
        if total_value == 0:
            raise UserError('No usage data available for the selected period. Cannot calculate ABC classification.')
        
        # Assign ABC classes based on cumulative percentage
        cumulative_value = 0.0
        result_lines = []
        
        for item_data in item_usage:
            cumulative_value += item_data['usage_value']
            cumulative_percentage = (cumulative_value / total_value) * 100
            
            # Determine ABC class
            if cumulative_percentage <= self.class_a_percentage:
                abc_class = 'A'
            elif cumulative_percentage <= self.class_b_percentage:
                abc_class = 'B'
            else:
                abc_class = 'C'
            
            # Create result line
            result_lines.append((0, 0, {
                'item_id': item_data['item'].id,
                'current_class': item_data['item'].abc_class,
                'recommended_class': abc_class,
                'usage_value': item_data['usage_value'],
                'usage_qty': item_data['usage_qty'],
                'usage_percentage': (item_data['usage_value'] / total_value) * 100,
                'cumulative_percentage': cumulative_percentage,
            }))
        
        self.result_line_ids = result_lines
        
        # Return wizard view
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mesob.abc.classification.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }
    
    def action_apply_classification(self):
        """Apply ABC classification to items"""
        self.ensure_one()
        
        applied_count = 0
        for line in self.result_line_ids.filtered('apply'):
            line.item_id.abc_class = line.recommended_class
            applied_count += 1
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('ABC Classification Applied'),
                'message': _('%d items updated with new ABC classification.') % applied_count,
                'type': 'success',
                'sticky': False,
            }
        }


class MesobABCClassificationWizardLine(models.TransientModel):
    """ABC Classification Result Line"""
    _name = 'mesob.abc.classification.wizard.line'
    _description = 'ABC Classification Result Line'
    _order = 'cumulative_percentage'
    
    wizard_id = fields.Many2one('mesob.abc.classification.wizard', 'Wizard', required=True, ondelete='cascade')
    item_id = fields.Many2one('mesob.inventory.item', 'Item', required=True)
    
    current_class = fields.Selection([
        ('A', 'A'), ('B', 'B'), ('C', 'C')
    ], 'Current Class')
    
    recommended_class = fields.Selection([
        ('A', 'A'), ('B', 'B'), ('C', 'C')
    ], 'Recommended Class', required=True)
    
    usage_value = fields.Monetary('Usage Value', currency_field='currency_id')
    usage_qty = fields.Float('Usage Quantity')
    usage_percentage = fields.Float('Usage %', digits=(5, 2))
    cumulative_percentage = fields.Float('Cumulative %', digits=(5, 2))
    
    apply = fields.Boolean('Apply', default=True)
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id)
    
    class_changed = fields.Boolean('Class Changed', compute='_compute_class_changed')
    
    @api.depends('current_class', 'recommended_class')
    def _compute_class_changed(self):
        for line in self:
            line.class_changed = line.current_class != line.recommended_class

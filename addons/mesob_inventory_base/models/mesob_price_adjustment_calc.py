# -*- coding: utf-8 -*-
"""AUTO-031: Price Adjustment Calculation Engine

Automated calculation of price adjustments for contracts with adjustable price provisions.
Complies with FR-PROC-035 and BR-PROC-007.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class MesobPriceAdjustmentCalculation(models.Model):
    """AUTO-031: Price Adjustment Calculation for Adjustable Price Contracts (FR-PROC-035)."""
    
    _name = 'mesob.price.adjustment.calculation'
    _description = 'Price Adjustment Calculation Engine'
    _order = 'calculation_date desc, id desc'
    _rec_name = 'display_name'
    
    # Header
    name = fields.Char(string='Adjustment Reference', required=True, copy=False, default='New')
    calculation_date = fields.Date(string='Calculation Date', required=True, default=fields.Date.context_today)
    
    # Contract Reference
    contract_ref = fields.Char(string='Contract Reference', required=True)
    po_ref = fields.Char(string='Purchase Order Reference')
    supplier_id = fields.Many2one('res.partner', string='Supplier', required=True, domain=[('supplier_rank', '>', 0)])
    
    # Contract Terms
    contract_type = fields.Selection([
        ('fixed', 'Fixed Price (Non-Adjustable)'),
        ('adjustable', 'Adjustable Price'),
    ], string='Contract Type', required=True, default='adjustable')
    
    base_contract_value = fields.Monetary(
        string='Base Contract Value (ETB)',
        required=True,
        currency_field='currency_id',
        help='Original contract value at signing'
    )
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    
    # Price Adjustment Formula Components (FR-PROC-035)
    adjustment_formula = fields.Text(
        string='Adjustment Formula',
        help='Price adjustment formula per contract (e.g., P = P0 × (0.30 × L/L0 + 0.40 × M/M0 + 0.30))'
    )
    
    # Weighting Factors
    labor_weight = fields.Float(string='Labor Weight', default=0.30, help='Weight factor for labor index (0-1)')
    material_weight = fields.Float(string='Material Weight', default=0.40, help='Weight factor for material index (0-1)')
    fixed_weight = fields.Float(string='Fixed Weight', default=0.30, help='Non-adjustable component (0-1)')
    
    # Base Indices (at contract signing)
    base_labor_index = fields.Float(string='Base Labor Index (L0)', required=True, help='Labor index at contract date')
    base_material_index = fields.Float(string='Base Material Index (M0)', required=True, help='Material index at contract date')
    
    # Current Indices (at payment/adjustment date)
    current_labor_index = fields.Float(string='Current Labor Index (L)', required=True, help='Labor index at adjustment date')
    current_material_index = fields.Float(string='Current Material Index (M)', required=True, help='Material index at adjustment date')
    
    # Calculation Results (AUTO-031)
    labor_adjustment_factor = fields.Float(
        string='Labor Adjustment Factor (L/L0)',
        compute='_compute_adjustment_factors',
        store=True,
        help='AUTO-031: Ratio of current to base labor index'
    )
    material_adjustment_factor = fields.Float(
        string='Material Adjustment Factor (M/M0)',
        compute='_compute_adjustment_factors',
        store=True,
        help='AUTO-031: Ratio of current to base material index'
    )
    overall_adjustment_factor = fields.Float(
        string='Overall Adjustment Factor',
        compute='_compute_overall_adjustment',
        store=True,
        help='AUTO-031: Weighted sum of adjustment factors plus fixed component'
    )
    
    adjusted_contract_value = fields.Monetary(
        string='Adjusted Contract Value (ETB)',
        compute='_compute_adjusted_value',
        store=True,
        currency_field='currency_id',
        help='AUTO-031: Base value × Overall adjustment factor'
    )
    adjustment_amount = fields.Monetary(
        string='Adjustment Amount (ETB)',
        compute='_compute_adjusted_value',
        store=True,
        currency_field='currency_id',
        help='AUTO-031: Adjusted value - Base value (can be positive or negative)'
    )
    adjustment_percentage = fields.Float(
        string='Adjustment %',
        compute='_compute_adjusted_value',
        store=True,
        help='AUTO-031: Adjustment as percentage of base contract value'
    )
    
    # Important Note (BR-PROC-007)
    affects_fifo_cost = fields.Boolean(
        string='AFFECTS FIFO Stock Cost?',
        default=False,
        readonly=True,
        help='BR-PROC-007: Price adjustments DO NOT alter FIFO stock cost. Original PO price remains cost basis.'
    )
    
    # Payment Integration
    payment_certificate_ref = fields.Char(string='Payment Certificate Reference')
    payment_date = fields.Date(string='Payment Date')
    net_payable_amount = fields.Monetary(
        string='Net Payable Amount',
        compute='_compute_net_payable',
        store=True,
        currency_field='currency_id',
        help='Adjusted contract value (used for payment calculation only)'
    )
    
    # Tracking
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)
    created_by_id = fields.Many2one('res.users', string='Calculated By', default=lambda self: self.env.user)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('calculated', 'Calculated'),
        ('approved', 'Approved'),
        ('applied', 'Applied to Payment'),
    ], string='Status', default='draft', tracking=True)
    
    # Calculation details
    calculation_details = fields.Html(
        string='Calculation Details',
        compute='_compute_calculation_details',
        help='AUTO-031: Detailed breakdown for audit trail (FR-PROC-035)'
    )
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('mesob.price.adjustment') or 'PA-NEW'
        return super().create(vals_list)
    
    @api.depends('contract_ref', 'supplier_id')
    def _compute_display_name(self):
        for rec in self:
            if rec.supplier_id and rec.contract_ref:
                rec.display_name = f'Price Adjustment: {rec.contract_ref} - {rec.supplier_id.name}'
            else:
                rec.display_name = f'Price Adjustment: {rec.name}'
    
    @api.depends('base_labor_index', 'current_labor_index', 'base_material_index', 'current_material_index')
    def _compute_adjustment_factors(self):
        """AUTO-031: Calculate individual index adjustment factors."""
        for rec in self:
            if rec.base_labor_index > 0:
                rec.labor_adjustment_factor = rec.current_labor_index / rec.base_labor_index
            else:
                rec.labor_adjustment_factor = 1.0
            
            if rec.base_material_index > 0:
                rec.material_adjustment_factor = rec.current_material_index / rec.base_material_index
            else:
                rec.material_adjustment_factor = 1.0
    
    @api.depends('labor_adjustment_factor', 'material_adjustment_factor', 'labor_weight', 'material_weight', 'fixed_weight')
    def _compute_overall_adjustment(self):
        """AUTO-031: Calculate overall weighted adjustment factor per FR-PROC-035.
        
        Formula: Overall Factor = (Labor Weight × L/L0) + (Material Weight × M/M0) + Fixed Weight
        """
        for rec in self:
            # Validate weights sum to 1.0
            total_weight = rec.labor_weight + rec.material_weight + rec.fixed_weight
            if not (0.99 <= total_weight <= 1.01):  # Allow small floating point error
                _logger.warning(f'AUTO-031: Weight factors do not sum to 1.0 for {rec.name}: {total_weight}')
            
            rec.overall_adjustment_factor = (
                (rec.labor_weight * rec.labor_adjustment_factor) +
                (rec.material_weight * rec.material_adjustment_factor) +
                rec.fixed_weight
            )
    
    @api.depends('base_contract_value', 'overall_adjustment_factor')
    def _compute_adjusted_value(self):
        """AUTO-031: Calculate adjusted contract value (FR-PROC-035)."""
        for rec in self:
            if rec.contract_type == 'fixed':
                # Fixed price contracts: no adjustment
                rec.adjusted_contract_value = rec.base_contract_value
                rec.adjustment_amount = 0.0
                rec.adjustment_percentage = 0.0
            else:
                # Adjustable price contracts: apply adjustment factor
                rec.adjusted_contract_value = rec.base_contract_value * rec.overall_adjustment_factor
                rec.adjustment_amount = rec.adjusted_contract_value - rec.base_contract_value
                
                if rec.base_contract_value > 0:
                    rec.adjustment_percentage = (rec.adjustment_amount / rec.base_contract_value) * 100.0
                else:
                    rec.adjustment_percentage = 0.0
    
    @api.depends('adjusted_contract_value')
    def _compute_net_payable(self):
        """Calculate net payable amount (adjusted value)."""
        for rec in self:
            rec.net_payable_amount = rec.adjusted_contract_value
    
    @api.depends('contract_type', 'overall_adjustment_factor', 'adjustment_amount')
    def _compute_calculation_details(self):
        """AUTO-031: Generate detailed calculation breakdown for transparency."""
        for rec in self:
            if rec.contract_type == 'fixed':
                rec.calculation_details = '''
                <div style="background-color: #e7f3ff; padding: 15px; border-left: 4px solid #2196f3;">
                    <h3 style="color: #0c5460;">ℹ Fixed Price Contract</h3>
                    <p style="color: #0c5460;">This is a fixed price (non-adjustable) contract. No price adjustment applicable.</p>
                </div>
                '''
                continue
            
            # Calculate percentage changes
            labor_change_pct = ((rec.labor_adjustment_factor - 1.0) * 100.0) if rec.labor_adjustment_factor else 0.0
            material_change_pct = ((rec.material_adjustment_factor - 1.0) * 100.0) if rec.material_adjustment_factor else 0.0
            overall_change_pct = ((rec.overall_adjustment_factor - 1.0) * 100.0) if rec.overall_adjustment_factor else 0.0
            
            # Determine color based on adjustment direction
            if rec.adjustment_amount > 0:
                adjustment_color = '#dc3545'  # Red (increase)
                adjustment_icon = '📈'
                adjustment_direction = 'INCREASE'
            elif rec.adjustment_amount < 0:
                adjustment_color = '#28a745'  # Green (decrease)
                adjustment_icon = '📉'
                adjustment_direction = 'DECREASE'
            else:
                adjustment_color = '#6c757d'  # Gray (no change)
                adjustment_icon = '➖'
                adjustment_direction = 'NO CHANGE'
            
            html = f'''
            <div style="font-family: Arial, sans-serif; padding: 20px;">
                <h2 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px;">
                    AUTO-031: Price Adjustment Calculation
                </h2>
                
                <div style="background-color: #e7f3ff; padding: 15px; margin: 15px 0; border-left: 4px solid #2196f3;">
                    <h3 style="margin-top: 0; color: #0c5460;">📋 Contract Information</h3>
                    <table style="width: 100%; margin-top: 10px;">
                        <tr>
                            <td style="padding: 5px;"><strong>Contract Reference:</strong></td>
                            <td style="padding: 5px;">{rec.contract_ref}</td>
                        </tr>
                        <tr>
                            <td style="padding: 5px;"><strong>Supplier:</strong></td>
                            <td style="padding: 5px;">{rec.supplier_id.name}</td>
                        </tr>
                        <tr>
                            <td style="padding: 5px;"><strong>Contract Type:</strong></td>
                            <td style="padding: 5px;">Adjustable Price (FR-PROC-035)</td>
                        </tr>
                        <tr>
                            <td style="padding: 5px;"><strong>Base Contract Value:</strong></td>
                            <td style="padding: 5px;">ETB {rec.base_contract_value:,.2f}</td>
                        </tr>
                    </table>
                </div>
                
                <h3 style="color: #2c3e50; margin-top: 25px;">Index Analysis</h3>
                <table style="width: 100%; border-collapse: collapse; margin-top: 10px;">
                    <thead style="background-color: #34495e; color: white;">
                        <tr>
                            <th style="border: 1px solid #bdc3c7; padding: 10px; text-align: left;">Component</th>
                            <th style="border: 1px solid #bdc3c7; padding: 10px; text-align: right;">Base Index</th>
                            <th style="border: 1px solid #bdc3c7; padding: 10px; text-align: right;">Current Index</th>
                            <th style="border: 1px solid #bdc3c7; padding: 10px; text-align: right;">Factor</th>
                            <th style="border: 1px solid #bdc3c7; padding: 10px; text-align: right;">Change %</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td style="border: 1px solid #bdc3c7; padding: 10px;">Labor</td>
                            <td style="border: 1px solid #bdc3c7; padding: 10px; text-align: right;">{rec.base_labor_index:.4f}</td>
                            <td style="border: 1px solid #bdc3c7; padding: 10px; text-align: right;">{rec.current_labor_index:.4f}</td>
                            <td style="border: 1px solid #bdc3c7; padding: 10px; text-align: right; font-weight: bold;">{rec.labor_adjustment_factor:.4f}</td>
                            <td style="border: 1px solid #bdc3c7; padding: 10px; text-align: right;">{labor_change_pct:+.2f}%</td>
                        </tr>
                        <tr style="background-color: #f8f9fa;">
                            <td style="border: 1px solid #bdc3c7; padding: 10px;">Material</td>
                            <td style="border: 1px solid #bdc3c7; padding: 10px; text-align: right;">{rec.base_material_index:.4f}</td>
                            <td style="border: 1px solid #bdc3c7; padding: 10px; text-align: right;">{rec.current_material_index:.4f}</td>
                            <td style="border: 1px solid #bdc3c7; padding: 10px; text-align: right; font-weight: bold;">{rec.material_adjustment_factor:.4f}</td>
                            <td style="border: 1px solid #bdc3c7; padding: 10px; text-align: right;">{material_change_pct:+.2f}%</td>
                        </tr>
                    </tbody>
                </table>
                
                <h3 style="color: #2c3e50; margin-top: 25px;">Weighted Adjustment Calculation</h3>
                <table style="width: 100%; border-collapse: collapse; margin-top: 10px;">
                    <tr style="background-color: #ecf0f1;">
                        <td style="border: 1px solid #bdc3c7; padding: 10px;">Labor Component</td>
                        <td style="border: 1px solid #bdc3c7; padding: 10px; text-align: right;">
                            {rec.labor_weight:.2f} × {rec.labor_adjustment_factor:.4f} = {rec.labor_weight * rec.labor_adjustment_factor:.4f}
                        </td>
                    </tr>
                    <tr>
                        <td style="border: 1px solid #bdc3c7; padding: 10px;">Material Component</td>
                        <td style="border: 1px solid #bdc3c7; padding: 10px; text-align: right;">
                            {rec.material_weight:.2f} × {rec.material_adjustment_factor:.4f} = {rec.material_weight * rec.material_adjustment_factor:.4f}
                        </td>
                    </tr>
                    <tr style="background-color: #ecf0f1;">
                        <td style="border: 1px solid #bdc3c7; padding: 10px;">Fixed Component (Non-Adjustable)</td>
                        <td style="border: 1px solid #bdc3c7; padding: 10px; text-align: right;">
                            {rec.fixed_weight:.2f}
                        </td>
                    </tr>
                    <tr style="background-color: #fff3cd;">
                        <td style="border: 1px solid #bdc3c7; padding: 10px; font-weight: bold;">Overall Adjustment Factor</td>
                        <td style="border: 1px solid #bdc3c7; padding: 10px; text-align: right; font-weight: bold;">
                            {rec.overall_adjustment_factor:.4f} ({overall_change_pct:+.2f}%)
                        </td>
                    </tr>
                </table>
                
                <h3 style="color: #2c3e50; margin-top: 25px;">Price Adjustment Result</h3>
                <div style="background-color: {adjustment_color}15; border-left: 4px solid {adjustment_color}; padding: 15px; margin-top: 10px;">
                    <table style="width: 100%; margin-top: 10px;">
                        <tr>
                            <td style="padding: 5px;"><strong>Base Contract Value:</strong></td>
                            <td style="padding: 5px; text-align: right;">ETB {rec.base_contract_value:,.2f}</td>
                        </tr>
                        <tr>
                            <td style="padding: 5px;"><strong>Overall Adjustment Factor:</strong></td>
                            <td style="padding: 5px; text-align: right;">× {rec.overall_adjustment_factor:.4f}</td>
                        </tr>
                        <tr style="border-top: 2px solid {adjustment_color};">
                            <td style="padding: 10px; font-weight: bold;"><strong>Adjusted Contract Value:</strong></td>
                            <td style="padding: 10px; text-align: right; font-weight: bold; font-size: 18px;">
                                ETB {rec.adjusted_contract_value:,.2f}
                            </td>
                        </tr>
                        <tr style="background-color: {adjustment_color}30;">
                            <td style="padding: 10px; font-weight: bold;"><strong>{adjustment_icon} Adjustment Amount:</strong></td>
                            <td style="padding: 10px; text-align: right; font-weight: bold; color: {adjustment_color}; font-size: 16px;">
                                ETB {rec.adjustment_amount:+,.2f} ({rec.adjustment_percentage:+.2f}%)
                            </td>
                        </tr>
                    </table>
                </div>
                
                <div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin-top: 20px;">
                    <h4 style="margin-top: 0; color: #856404;">⚠ BR-PROC-007: Stock Cost Impact</h4>
                    <p style="color: #856404; margin: 0;">
                        <strong>IMPORTANT:</strong> This price adjustment is a <u>financial adjustment ONLY</u>.
                        <br/><br/>
                        ✅ <strong>Applied to:</strong> Payment certificates and financial records
                        <br/>❌ <strong>NOT applied to:</strong> FIFO stock cost in Stock Record Cards (FR-VAL-001)
                        <br/><br/>
                        <em>The original PO unit price remains the FIFO cost basis per BR-PROC-007.</em>
                    </p>
                </div>
                
                <div style="margin-top: 30px; padding-top: 15px; border-top: 1px solid #bdc3c7; color: #7f8c8d; font-size: 12px;">
                    <p><em>AUTO-031: Calculation follows FR-PROC-035 adjustable price provisions.</em></p>
                    <p><em>Formula: Adjusted Value = Base Value × [(Labor Weight × L/L0) + (Material Weight × M/M0) + Fixed Weight]</em></p>
                </div>
            </div>
            '''
            
            rec.calculation_details = html
    
    def action_calculate(self):
        """AUTO-031: Trigger price adjustment calculation."""
        self.ensure_one()
        
        if self.contract_type == 'fixed':
            raise ValidationError('Cannot calculate price adjustment for fixed price contracts.')
        
        # Force recalculation
        self._compute_adjustment_factors()
        self._compute_overall_adjustment()
        self._compute_adjusted_value()
        self._compute_net_payable()
        self._compute_calculation_details()
        
        self.state = 'calculated'
        
        _logger.info(
            f'AUTO-031: Price adjustment calculated - {self.contract_ref}: '
            f'ETB {self.adjustment_amount:+,.2f} ({self.adjustment_percentage:+.2f}%)'
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Price Adjustment Calculated',
                'message': f'Adjustment: ETB {self.adjustment_amount:+,.2f} ({self.adjustment_percentage:+.2f}%)',
                'type': 'info',
                'sticky': False,
            }
        }
    
    def action_approve(self):
        """Approve price adjustment calculation (PAO/Finance approval)."""
        self.ensure_one()
        
        if self.state != 'calculated':
            raise ValidationError('Please calculate adjustment before approving.')
        
        self.state = 'approved'
        
        self.message_post(
            body=f'''<div style="background-color: #e7f3ff; padding: 15px; border-left: 4px solid #2196f3;">
                <h3>✅ Price Adjustment Approved</h3>
                <p><strong>Contract:</strong> {self.contract_ref}</p>
                <p><strong>Supplier:</strong> {self.supplier_id.name}</p>
                <p><strong>Base Value:</strong> ETB {self.base_contract_value:,.2f}</p>
                <p><strong>Adjusted Value:</strong> ETB {self.adjusted_contract_value:,.2f}</p>
                <p><strong>Adjustment:</strong> ETB {self.adjustment_amount:+,.2f} ({self.adjustment_percentage:+.2f}%)</p>
                <p><em>Approved by: {self.env.user.name}</em></p>
                <hr/>
                <p style="color: #856404;"><em>⚠ Note: This adjustment does NOT affect FIFO stock costs (BR-PROC-007).</em></p>
            </div>''',
            subject='Price Adjustment Approved',
        )
        
        return True
    
    def action_apply_to_payment(self):
        """Apply price adjustment to payment certificate."""
        self.ensure_one()
        
        if self.state != 'approved':
            raise ValidationError('Please approve price adjustment before applying to payment.')
        
        self.write({
            'state': 'applied',
            'payment_date': fields.Date.today(),
        })
        
        _logger.info(
            f'AUTO-031: Price adjustment applied to payment - {self.contract_ref}: '
            f'ETB {self.adjustment_amount:+,.2f}'
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Adjustment Applied',
                'message': f'Price adjustment of ETB {self.adjustment_amount:+,.2f} applied to payment certificate.',
                'type': 'success',
                'sticky': False,
            }
        }
    
    @api.constrains('labor_weight', 'material_weight', 'fixed_weight')
    def _check_weight_factors(self):
        for rec in self:
            total_weight = rec.labor_weight + rec.material_weight + rec.fixed_weight
            if not (0.99 <= total_weight <= 1.01):  # Allow small floating point error
                raise ValidationError(
                    f'Weight factors must sum to 1.0 (100%). Current sum: {total_weight:.4f}\n'
                    f'Labor: {rec.labor_weight}, Material: {rec.material_weight}, Fixed: {rec.fixed_weight}'
                )
            
            if rec.labor_weight < 0 or rec.material_weight < 0 or rec.fixed_weight < 0:
                raise ValidationError('Weight factors cannot be negative.')
    
    @api.constrains('base_labor_index', 'base_material_index', 'current_labor_index', 'current_material_index')
    def _check_indices(self):
        for rec in self:
            if rec.base_labor_index <= 0 or rec.base_material_index <= 0:
                raise ValidationError('Base indices must be greater than zero.')
            if rec.current_labor_index <= 0 or rec.current_material_index <= 0:
                raise ValidationError('Current indices must be greater than zero.')

# -*- coding: utf-8 -*-
"""AUTO-030: Liquidated Damages Auto-Calculation

Automated calculation of liquidated damages for late delivery per FPPA contract terms.
Complies with FR-PROC-036.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)


class MesobLiquidatedDamagesCalculation(models.Model):
    """AUTO-030: Liquidated Damages Calculation for Late Delivery (FR-PROC-036)."""
    
    _name = 'mesob.liquidated.damages.calculation'
    _description = 'Liquidated Damages Calculation Engine'
    _order = 'calculation_date desc, id desc'
    _rec_name = 'display_name'
    
    # Header
    name = fields.Char(string='LD Reference', required=True, copy=False, default='New')
    calculation_date = fields.Date(string='Calculation Date', required=True, default=fields.Date.context_today)
    
    # Contract/PO Reference
    contract_ref = fields.Char(string='Contract Reference', required=True)
    po_ref = fields.Char(string='Purchase Order Reference')
    supplier_id = fields.Many2one('res.partner', string='Supplier', required=True, domain=[('supplier_rank', '>', 0)])
    
    # Contract Terms
    contract_value = fields.Monetary(
        string='Contract Value (ETB)',
        required=True,
        currency_field='currency_id',
        help='Total contract value for percentage-based LD calculation'
    )
    contract_delivery_date = fields.Date(
        string='Contract Delivery Date',
        required=True,
        help='Agreed delivery date per contract'
    )
    actual_delivery_date = fields.Date(
        string='Actual Delivery Date',
        required=True,
        help='Date when Model 19 acceptance was confirmed (FR-REC-005)'
    )
    
    # LD Parameters
    penalty_rate_per_day = fields.Float(
        string='Penalty Rate per Day',
        default=0.001,
        required=True,
        help='Default: 1/1000 (0.001) of contract value per working day (FR-PROC-036)'
    )
    max_penalty_percentage = fields.Float(
        string='Maximum Penalty (%)',
        default=10.0,
        required=True,
        help='Maximum total LD as percentage of contract value (typically 10%)'
    )
    use_working_days_only = fields.Boolean(
        string='Use Working Days Only',
        default=True,
        help='Exclude weekends and holidays from delay calculation'
    )
    
    # Calculation Results (AUTO-030)
    delay_days = fields.Integer(
        string='Delay Days',
        compute='_compute_liquidated_damages',
        store=True,
        help='AUTO-030: Number of days late (working days if configured)'
    )
    ld_amount = fields.Monetary(
        string='Liquidated Damages (ETB)',
        compute='_compute_liquidated_damages',
        store=True,
        currency_field='currency_id',
        help='AUTO-030: Calculated liquidated damages amount'
    )
    ld_capped_amount = fields.Monetary(
        string='LD Amount (Capped)',
        compute='_compute_liquidated_damages',
        store=True,
        currency_id='currency_id',
        help='AUTO-030: LD amount after applying maximum penalty cap'
    )
    is_capped = fields.Boolean(
        string='Penalty Capped',
        compute='_compute_liquidated_damages',
        store=True,
        help='Whether the calculated LD exceeded maximum penalty'
    )
    
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    
    # Payment Deduction
    deduction_applied = fields.Boolean(string='Deduction Applied to Payment', default=False, tracking=True)
    deduction_date = fields.Date(string='Deduction Date')
    payment_certificate_ref = fields.Char(string='Payment Certificate Reference')
    net_payable_amount = fields.Monetary(
        string='Net Payable (After LD)',
        compute='_compute_net_payable',
        store=True,
        currency_field='currency_id',
        help='Contract value minus liquidated damages'
    )
    
    # Tracking
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)
    created_by_id = fields.Many2one('res.users', string='Calculated By', default=lambda self: self.env.user)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('calculated', 'Calculated'),
        ('approved', 'Approved'),
        ('deducted', 'Deducted from Payment'),
    ], string='Status', default='draft', tracking=True)
    
    # Calculation details
    calculation_details = fields.Html(
        string='Calculation Details',
        compute='_compute_calculation_details',
        help='AUTO-030: Detailed breakdown for audit trail (FR-PROC-036)'
    )
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('mesob.liquidated.damages') or 'LD-NEW'
        return super().create(vals_list)
    
    @api.depends('contract_ref', 'supplier_id')
    def _compute_display_name(self):
        for rec in self:
            if rec.supplier_id and rec.contract_ref:
                rec.display_name = f'LD: {rec.contract_ref} - {rec.supplier_id.name}'
            else:
                rec.display_name = f'LD: {rec.name}'
    
    @api.depends('contract_delivery_date', 'actual_delivery_date', 'contract_value', 'penalty_rate_per_day', 'max_penalty_percentage', 'use_working_days_only')
    def _compute_liquidated_damages(self):
        """AUTO-030: Calculate liquidated damages per FR-PROC-036.
        
        Formula:
        LD = Contract Value × Penalty Rate × Delay Days
        Capped at: Contract Value × Max Penalty %
        
        Default: 1/1000 per working day, max 10%
        """
        for rec in self:
            if not rec.contract_delivery_date or not rec.actual_delivery_date:
                rec.delay_days = 0
                rec.ld_amount = 0.0
                rec.ld_capped_amount = 0.0
                rec.is_capped = False
                continue
            
            # Calculate delay
            if rec.actual_delivery_date <= rec.contract_delivery_date:
                # On time or early - no penalty
                rec.delay_days = 0
                rec.ld_amount = 0.0
                rec.ld_capped_amount = 0.0
                rec.is_capped = False
                continue
            
            # Calculate delay days
            if rec.use_working_days_only:
                # Count working days (exclude weekends)
                delay_days = rec._count_working_days(rec.contract_delivery_date, rec.actual_delivery_date)
            else:
                # Count all calendar days
                delay_days = (rec.actual_delivery_date - rec.contract_delivery_date).days
            
            rec.delay_days = delay_days
            
            # Calculate LD
            ld_uncapped = rec.contract_value * rec.penalty_rate_per_day * delay_days
            max_ld = rec.contract_value * (rec.max_penalty_percentage / 100.0)
            
            rec.ld_amount = ld_uncapped
            rec.ld_capped_amount = min(ld_uncapped, max_ld)
            rec.is_capped = (ld_uncapped > max_ld)
            
            _logger.info(
                f'AUTO-030: LD calculated for {rec.contract_ref} - '
                f'Delay: {delay_days} days, LD: ETB {rec.ld_capped_amount:,.2f} '
                f'{"(CAPPED)" if rec.is_capped else ""}'
            )
    
    def _count_working_days(self, start_date, end_date):
        """Count working days between two dates (Monday-Friday)."""
        working_days = 0
        current_date = start_date + timedelta(days=1)  # Start from day after contract date
        
        while current_date <= end_date:
            # Monday=0, Sunday=6
            if current_date.weekday() < 5:  # Monday-Friday
                working_days += 1
            current_date += timedelta(days=1)
        
        return working_days
    
    @api.depends('contract_value', 'ld_capped_amount')
    def _compute_net_payable(self):
        """Calculate net amount payable after LD deduction."""
        for rec in self:
            rec.net_payable_amount = rec.contract_value - rec.ld_capped_amount
    
    @api.depends('delay_days', 'ld_amount', 'ld_capped_amount', 'is_capped')
    def _compute_calculation_details(self):
        """AUTO-030: Generate detailed calculation breakdown for transparency."""
        for rec in self:
            if rec.delay_days == 0:
                rec.calculation_details = '''
                <div style="background-color: #d4edda; padding: 15px; border-left: 4px solid #28a745;">
                    <h3 style="color: #155724;">✅ No Liquidated Damages</h3>
                    <p style="color: #155724;">Delivery was on time or early. No penalty applicable.</p>
                </div>
                '''
                continue
            
            # Working days explanation
            day_type = 'working days (Mon-Fri)' if rec.use_working_days_only else 'calendar days'
            
            html = f'''
            <div style="font-family: Arial, sans-serif; padding: 20px;">
                <h2 style="color: #dc3545; border-bottom: 2px solid #dc3545; padding-bottom: 10px;">
                    AUTO-030: Liquidated Damages Calculation
                </h2>
                
                <div style="background-color: #f8d7da; padding: 15px; margin: 15px 0; border-left: 4px solid #dc3545;">
                    <h3 style="margin-top: 0; color: #721c24;">⚠ Late Delivery Penalty</h3>
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
                            <td style="padding: 5px;"><strong>Contract Value:</strong></td>
                            <td style="padding: 5px;">ETB {rec.contract_value:,.2f}</td>
                        </tr>
                    </table>
                </div>
                
                <h3 style="color: #2c3e50; margin-top: 25px;">Delay Calculation</h3>
                <table style="width: 100%; border-collapse: collapse; margin-top: 10px;">
                    <tr style="background-color: #ecf0f1;">
                        <td style="border: 1px solid #bdc3c7; padding: 10px; font-weight: bold;">Contract Delivery Date</td>
                        <td style="border: 1px solid #bdc3c7; padding: 10px;">{rec.contract_delivery_date}</td>
                    </tr>
                    <tr>
                        <td style="border: 1px solid #bdc3c7; padding: 10px; font-weight: bold;">Actual Delivery Date</td>
                        <td style="border: 1px solid #bdc3c7; padding: 10px;">{rec.actual_delivery_date}</td>
                    </tr>
                    <tr style="background-color: #fff3cd;">
                        <td style="border: 1px solid #bdc3c7; padding: 10px; font-weight: bold;">Delay</td>
                        <td style="border: 1px solid #bdc3c7; padding: 10px; font-weight: bold; color: #dc3545;">
                            {rec.delay_days} {day_type}
                        </td>
                    </tr>
                </table>
                
                <h3 style="color: #2c3e50; margin-top: 25px;">Penalty Calculation (FR-PROC-036)</h3>
                <table style="width: 100%; border-collapse: collapse; margin-top: 10px;">
                    <tr style="background-color: #ecf0f1;">
                        <td style="border: 1px solid #bdc3c7; padding: 10px;">Contract Value</td>
                        <td style="border: 1px solid #bdc3c7; padding: 10px; text-align: right;">ETB {rec.contract_value:,.2f}</td>
                    </tr>
                    <tr>
                        <td style="border: 1px solid #bdc3c7; padding: 10px;">Penalty Rate per Day</td>
                        <td style="border: 1px solid #bdc3c7; padding: 10px; text-align: right;">{rec.penalty_rate_per_day:.4f} ({rec.penalty_rate_per_day * 1000:.1f}/1000)</td>
                    </tr>
                    <tr>
                        <td style="border: 1px solid #bdc3c7; padding: 10px;">Delay Days</td>
                        <td style="border: 1px solid #bdc3c7; padding: 10px; text-align: right;">{rec.delay_days}</td>
                    </tr>
                    <tr style="background-color: #fff3cd;">
                        <td style="border: 1px solid #bdc3c7; padding: 10px; font-weight: bold;">Calculated LD</td>
                        <td style="border: 1px solid #bdc3c7; padding: 10px; text-align: right; font-weight: bold;">
                            ETB {rec.ld_amount:,.2f}
                        </td>
                    </tr>
                    <tr style="background-color: #ecf0f1;">
                        <td style="border: 1px solid #bdc3c7; padding: 10px;">Maximum Penalty ({rec.max_penalty_percentage}%)</td>
                        <td style="border: 1px solid #bdc3c7; padding: 10px; text-align: right;">
                            ETB {rec.contract_value * (rec.max_penalty_percentage / 100.0):,.2f}
                        </td>
                    </tr>
            '''
            
            if rec.is_capped:
                html += f'''
                    <tr style="background-color: #f8d7da;">
                        <td style="border: 1px solid #dc3545; padding: 10px; font-weight: bold; color: #721c24;">
                            ⚠ LD Amount (Capped)
                        </td>
                        <td style="border: 1px solid #dc3545; padding: 10px; text-align: right; font-weight: bold; color: #721c24;">
                            ETB {rec.ld_capped_amount:,.2f}
                        </td>
                    </tr>
                '''
            else:
                html += f'''
                    <tr style="background-color: #f8d7da;">
                        <td style="border: 1px solid #dc3545; padding: 10px; font-weight: bold; color: #721c24;">
                            Final LD Amount
                        </td>
                        <td style="border: 1px solid #dc3545; padding: 10px; text-align: right; font-weight: bold; color: #721c24;">
                            ETB {rec.ld_capped_amount:,.2f}
                        </td>
                    </tr>
                '''
            
            html += '''
                </table>
            '''
            
            if rec.is_capped:
                html += f'''
                <div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin-top: 20px;">
                    <h4 style="margin-top: 0; color: #856404;">⚠ Penalty Capped</h4>
                    <p style="color: #856404; margin: 0;">
                        The calculated liquidated damages (ETB {rec.ld_amount:,.2f}) exceeded the maximum penalty allowed 
                        ({rec.max_penalty_percentage}% of contract value = ETB {rec.contract_value * (rec.max_penalty_percentage / 100.0):,.2f}).
                        <br/><strong>The penalty has been capped at ETB {rec.ld_capped_amount:,.2f}.</strong>
                    </p>
                </div>
                '''
            
            html += f'''
                <div style="background-color: #e7f3ff; border-left: 4px solid #2196f3; padding: 15px; margin-top: 20px;">
                    <h4 style="margin-top: 0; color: #0c5460;">💰 Net Payment</h4>
                    <table style="width: 100%; margin-top: 10px;">
                        <tr>
                            <td style="padding: 5px;"><strong>Contract Value:</strong></td>
                            <td style="padding: 5px; text-align: right;">ETB {rec.contract_value:,.2f}</td>
                        </tr>
                        <tr style="color: #dc3545;">
                            <td style="padding: 5px;"><strong>Liquidated Damages Deduction:</strong></td>
                            <td style="padding: 5px; text-align: right;">(ETB {rec.ld_capped_amount:,.2f})</td>
                        </tr>
                        <tr style="background-color: #d4edda; font-weight: bold;">
                            <td style="padding: 10px; border-top: 2px solid #28a745;"><strong>Net Payable Amount:</strong></td>
                            <td style="padding: 10px; text-align: right; border-top: 2px solid #28a745; color: #155724;">
                                ETB {rec.net_payable_amount:,.2f}
                            </td>
                        </tr>
                    </table>
                </div>
                
                <div style="margin-top: 30px; padding-top: 15px; border-top: 1px solid #bdc3c7; color: #7f8c8d; font-size: 12px;">
                    <p><em>AUTO-030: Calculation follows FR-PROC-036 liquidated damages formula.</em></p>
                    <p><em>Formula: LD = Contract Value × {rec.penalty_rate_per_day:.4f} × Delay Days, capped at {rec.max_penalty_percentage}% of contract value.</em></p>
                </div>
            </div>
            '''
            
            rec.calculation_details = html
    
    def action_calculate(self):
        """AUTO-030: Trigger LD calculation."""
        self.ensure_one()
        
        # Force recalculation
        self._compute_liquidated_damages()
        self._compute_net_payable()
        self._compute_calculation_details()
        
        self.state = 'calculated'
        
        _logger.info(
            f'AUTO-030: LD calculated - {self.contract_ref}: ETB {self.ld_capped_amount:,.2f} '
            f'({self.delay_days} days late)'
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'LD Calculated',
                'message': f'Liquidated Damages: ETB {self.ld_capped_amount:,.2f} ({self.delay_days} days late)',
                'type': 'warning' if self.ld_capped_amount > 0 else 'success',
                'sticky': False,
            }
        }
    
    def action_approve(self):
        """Approve LD calculation (PAO/Finance approval)."""
        self.ensure_one()
        
        if self.state != 'calculated':
            raise ValidationError('Please calculate LD before approving.')
        
        self.state = 'approved'
        
        self.message_post(
            body=f'''<div style="background-color: #fff3cd; padding: 15px; border-left: 4px solid #ffc107;">
                <h3>✅ Liquidated Damages Approved</h3>
                <p><strong>Contract:</strong> {self.contract_ref}</p>
                <p><strong>Supplier:</strong> {self.supplier_id.name}</p>
                <p><strong>Delay:</strong> {self.delay_days} days</p>
                <p><strong>LD Amount:</strong> ETB {self.ld_capped_amount:,.2f}</p>
                <p><strong>Net Payable:</strong> ETB {self.net_payable_amount:,.2f}</p>
                <p><em>Approved by: {self.env.user.name}</em></p>
            </div>''',
            subject='Liquidated Damages Approved',
        )
        
        return True
    
    def action_apply_deduction(self):
        """Apply LD deduction to payment certificate."""
        self.ensure_one()
        
        if self.state != 'approved':
            raise ValidationError('Please approve LD calculation before applying deduction.')
        
        if self.deduction_applied:
            raise ValidationError('Deduction has already been applied.')
        
        self.write({
            'deduction_applied': True,
            'deduction_date': fields.Date.today(),
            'state': 'deducted',
        })
        
        _logger.info(
            f'AUTO-030: LD deduction applied - {self.contract_ref}: ETB {self.ld_capped_amount:,.2f}'
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Deduction Applied',
                'message': f'LD deduction of ETB {self.ld_capped_amount:,.2f} applied to payment.',
                'type': 'success',
                'sticky': False,
            }
        }
    
    @api.constrains('contract_delivery_date', 'actual_delivery_date')
    def _check_dates(self):
        for rec in self:
            if rec.contract_delivery_date and rec.actual_delivery_date:
                if rec.actual_delivery_date < rec.contract_delivery_date:
                    raise ValidationError('Actual delivery date cannot be before contract delivery date.')
    
    @api.constrains('penalty_rate_per_day', 'max_penalty_percentage')
    def _check_penalty_parameters(self):
        for rec in self:
            if rec.penalty_rate_per_day < 0 or rec.penalty_rate_per_day > 1:
                raise ValidationError('Penalty rate must be between 0 and 1 (0-100%).')
            if rec.max_penalty_percentage < 0 or rec.max_penalty_percentage > 100:
                raise ValidationError('Maximum penalty percentage must be between 0 and 100.')

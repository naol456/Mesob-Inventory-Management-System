# -*- coding: utf-8 -*-
"""AUTO-015: Domestic Preference Calculation Engine

Automated calculation of Ethiopian domestic preference margin per FPPA Proclamation 1210/2012, Article 27(4).
Complies with FR-PROC-018 and BR-PROC-003.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class MesobDomesticPreferenceCalculation(models.Model):
    """AUTO-015: Domestic Preference Calculation for Bid Evaluation (FR-PROC-018)."""
    
    _name = 'mesob.domestic.preference.calculation'
    _description = 'Domestic Preference Calculation Engine'
    _order = 'date desc, id desc'
    _rec_name = 'display_name'
    
    # Header
    name = fields.Char(string='Calculation Reference', required=True, copy=False, default='New')
    date = fields.Date(string='Calculation Date', required=True, default=fields.Date.context_today)
    lot_id = fields.Many2one('mesob.procurement.plan.lot', string='Procurement Lot', ondelete='cascade')
    tender_ref = fields.Char(string='Tender Reference', help='Bidding document reference')
    
    # Calculation Lines (Bidders)
    calculation_line_ids = fields.One2many(
        'mesob.domestic.preference.calculation.line',
        'calculation_id',
        string='Bidder Calculations'
    )
    
    # Summary
    total_bidders = fields.Integer(string='Total Bidders', compute='_compute_summary', store=True)
    lowest_evaluated_bidder_id = fields.Many2one(
        'mesob.domestic.preference.calculation.line',
        string='Recommended Awardee',
        compute='_compute_ranking',
        store=True,
        help='AUTO-015: Bidder with lowest evaluated price (after preference adjustment)'
    )
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)
    
    # Tracking
    created_by_id = fields.Many2one('res.users', string='Calculated By', default=lambda self: self.env.user)
    state = fields.Selection([
        ('draft', 'Draft'),
        ('calculated', 'Calculated'),
        ('validated', 'Validated'),
    ], string='Status', default='draft', tracking=True)
    
    # Export fields for evaluation report
    calculation_worksheet = fields.Html(
        string='Calculation Worksheet',
        compute='_compute_calculation_worksheet',
        help='AUTO-015: Detailed calculation worksheet for audit (FR-PROC-018)'
    )
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('mesob.domestic.preference.calc') or 'DP-NEW'
        return super().create(vals_list)
    
    @api.depends('tender_ref', 'date')
    def _compute_display_name(self):
        for rec in self:
            if rec.tender_ref:
                rec.display_name = f'Domestic Preference Calc: {rec.tender_ref} ({rec.date})'
            else:
                rec.display_name = f'Domestic Preference Calc: {rec.name}'
    
    @api.depends('calculation_line_ids')
    def _compute_summary(self):
        for rec in self:
            rec.total_bidders = len(rec.calculation_line_ids)
    
    @api.depends('calculation_line_ids.evaluated_price')
    def _compute_ranking(self):
        """AUTO-015: Rank bidders by evaluated price and identify lowest (FR-PROC-019)."""
        for rec in self:
            if not rec.calculation_line_ids:
                rec.lowest_evaluated_bidder_id = False
                continue
            
            # Sort by evaluated price ascending
            sorted_lines = rec.calculation_line_ids.sorted('evaluated_price')
            rec.lowest_evaluated_bidder_id = sorted_lines[0] if sorted_lines else False
            
            # Assign ranks
            for idx, line in enumerate(sorted_lines, start=1):
                line.rank = idx
    
    @api.depends('calculation_line_ids')
    def _compute_calculation_worksheet(self):
        """AUTO-015: Generate detailed calculation worksheet for audit trail."""
        for rec in self:
            if not rec.calculation_line_ids:
                rec.calculation_worksheet = '<p><em>No bidders added yet.</em></p>'
                continue
            
            html = f'''
            <div style="font-family: Arial, sans-serif; padding: 20px;">
                <h2 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px;">
                    AUTO-015: Domestic Preference Calculation Worksheet
                </h2>
                <div style="background-color: #ecf0f1; padding: 15px; margin: 15px 0; border-left: 4px solid #3498db;">
                    <p><strong>Tender Reference:</strong> {rec.tender_ref or 'N/A'}</p>
                    <p><strong>Calculation Date:</strong> {rec.date}</p>
                    <p><strong>Total Bidders:</strong> {rec.total_bidders}</p>
                    <p><strong>Compliance:</strong> FR-PROC-018, BR-PROC-003, FPPA Proclamation 1210/2012 Article 27(4)</p>
                </div>
                
                <h3 style="color: #2c3e50; margin-top: 25px;">Bidder Evaluation Table</h3>
                <table style="width: 100%; border-collapse: collapse; margin-top: 15px;">
                    <thead style="background-color: #34495e; color: white;">
                        <tr>
                            <th style="border: 1px solid #bdc3c7; padding: 12px; text-align: left;">Rank</th>
                            <th style="border: 1px solid #bdc3c7; padding: 12px; text-align: left;">Bidder</th>
                            <th style="border: 1px solid #bdc3c7; padding: 12px; text-align: left;">Local Content</th>
                            <th style="border: 1px solid #bdc3c7; padding: 12px; text-align: right;">Bid Price (ETB)</th>
                            <th style="border: 1px solid #bdc3c7; padding: 12px; text-align: center;">Preference %</th>
                            <th style="border: 1px solid #bdc3c7; padding: 12px; text-align: right;">Preference Amt</th>
                            <th style="border: 1px solid #bdc3c7; padding: 12px; text-align: right;">Evaluated Price</th>
                        </tr>
                    </thead>
                    <tbody>
            '''
            
            sorted_lines = rec.calculation_line_ids.sorted('evaluated_price')
            for line in sorted_lines:
                row_color = '#d5f4e6' if line.rank == 1 else '#ffffff'
                html += f'''
                    <tr style="background-color: {row_color};">
                        <td style="border: 1px solid #bdc3c7; padding: 10px; text-align: left; font-weight: {'bold' if line.rank == 1 else 'normal'};">{line.rank or '-'}</td>
                        <td style="border: 1px solid #bdc3c7; padding: 10px; text-align: left;">{line.bidder_name}</td>
                        <td style="border: 1px solid #bdc3c7; padding: 10px; text-align: left;">{line.local_content_percentage:.1f}%</td>
                        <td style="border: 1px solid #bdc3c7; padding: 10px; text-align: right;">{line.bid_price:,.2f}</td>
                        <td style="border: 1px solid #bdc3c7; padding: 10px; text-align: center; font-weight: bold; color: #27ae60;">{line.preference_percentage:.1f}%</td>
                        <td style="border: 1px solid #bdc3c7; padding: 10px; text-align: right;">({line.preference_amount:,.2f})</td>
                        <td style="border: 1px solid #bdc3c7; padding: 10px; text-align: right; font-weight: bold;">{line.evaluated_price:,.2f}</td>
                    </tr>
                '''
            
            html += '''
                    </tbody>
                </table>
                
                <div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin-top: 25px;">
                    <h4 style="margin-top: 0; color: #856404;">📋 Calculation Methodology (FPPA Article 27(4))</h4>
                    <ul style="margin: 10px 0; color: #856404;">
                        <li><strong>≥70% Local Content:</strong> 13.5% preference deduction from bid price</li>
                        <li><strong>40-70% Local Content:</strong> 11% preference deduction from bid price</li>
                        <li><strong>&lt;40% Local Content (Foreign):</strong> 0% preference</li>
                    </ul>
                    <p style="color: #856404; margin-bottom: 0;"><strong>Note:</strong> <em>Evaluated Price = Bid Price × (1 - Preference %)</em><br/>
                    Contract value uses <u>original bid price</u>, not adjusted price (BR-PROC-003).</p>
                </div>
            '''
            
            if rec.lowest_evaluated_bidder_id:
                html += f'''
                <div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px; margin-top: 20px;">
                    <h4 style="margin-top: 0; color: #155724;">✅ Recommended Award</h4>
                    <p style="color: #155724; margin: 0;"><strong>Bidder:</strong> {rec.lowest_evaluated_bidder_id.bidder_name}</p>
                    <p style="color: #155724; margin: 5px 0 0 0;">
                        <strong>Evaluated Price:</strong> ETB {rec.lowest_evaluated_bidder_id.evaluated_price:,.2f}<br/>
                        <strong>Contract Price:</strong> ETB {rec.lowest_evaluated_bidder_id.bid_price:,.2f} (original bid price per BR-PROC-003)
                    </p>
                </div>
                '''
            
            html += '''
                <div style="margin-top: 30px; padding-top: 15px; border-top: 1px solid #bdc3c7; color: #7f8c8d; font-size: 12px;">
                    <p><em>AUTO-015: This calculation worksheet is automatically generated for audit compliance (FR-PROC-019).</em></p>
                    <p><em>All calculations follow FPPA Proclamation 1210/2012 Article 27(4) and Ethiopian Federal Procurement rules.</em></p>
                </div>
            </div>
            '''
            
            rec.calculation_worksheet = html
    
    def action_calculate(self):
        """AUTO-015: Trigger calculation for all bidder lines."""
        self.ensure_one()
        
        if not self.calculation_line_ids:
            raise ValidationError('Please add bidders before calculating.')
        
        # Force recalculation of all lines
        for line in self.calculation_line_ids:
            line._compute_preference_percentage()
            line._compute_preference_amount()
            line._compute_evaluated_price()
        
        # Recompute ranking
        self._compute_ranking()
        
        self.state = 'calculated'
        
        _logger.info(
            f'AUTO-015: Domestic preference calculated for {len(self.calculation_line_ids)} bidders - '
            f'Lowest evaluated: {self.lowest_evaluated_bidder_id.bidder_name if self.lowest_evaluated_bidder_id else "N/A"}'
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Calculation Complete',
                'message': f'Domestic preference calculated. Recommended awardee: {self.lowest_evaluated_bidder_id.bidder_name if self.lowest_evaluated_bidder_id else "N/A"}',
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_validate(self):
        """AUTO-015: Validate calculation (PAO/PEC approval)."""
        self.ensure_one()
        
        if self.state != 'calculated':
            raise ValidationError('Please calculate before validating.')
        
        self.state = 'validated'
        
        self.message_post(
            body=f'''<div style="background-color: #d4edda; padding: 15px; border-left: 4px solid #28a745;">
                <h3>✅ Domestic Preference Calculation Validated</h3>
                <p><strong>Recommended Awardee:</strong> {self.lowest_evaluated_bidder_id.bidder_name if self.lowest_evaluated_bidder_id else 'N/A'}</p>
                <p><strong>Evaluated Price:</strong> ETB {self.lowest_evaluated_bidder_id.evaluated_price:,.2f if self.lowest_evaluated_bidder_id else 0}</p>
                <p><strong>Contract Price:</strong> ETB {self.lowest_evaluated_bidder_id.bid_price:,.2f if self.lowest_evaluated_bidder_id else 0}</p>
                <p><em>Validated by: {self.env.user.name}</em></p>
            </div>''',
            subject='Domestic Preference Calculation Validated',
        )
        
        return True


class MesobDomesticPreferenceCalculationLine(models.Model):
    """AUTO-015: Individual bidder preference calculation line."""
    
    _name = 'mesob.domestic.preference.calculation.line'
    _description = 'Domestic Preference Calculation Line (Bidder)'
    _order = 'evaluated_price asc, id asc'
    
    calculation_id = fields.Many2one(
        'mesob.domestic.preference.calculation',
        string='Calculation',
        required=True,
        ondelete='cascade'
    )
    
    # Bidder Information
    bidder_id = fields.Many2one('res.partner', string='Bidder (Supplier)', required=True)
    bidder_name = fields.Char(string='Bidder Name', required=True)
    local_content_percentage = fields.Float(
        string='Local Content (%)',
        required=True,
        help='Percentage of local Ethiopian content in the bid (0-100)'
    )
    
    # Bid Price
    bid_price = fields.Monetary(
        string='Bid Price (ETB)',
        required=True,
        currency_field='currency_id',
        help='Original bid price submitted by bidder'
    )
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)
    
    # Preference Calculation (FR-PROC-018, BR-PROC-003)
    preference_percentage = fields.Float(
        string='Preference %',
        compute='_compute_preference_percentage',
        store=True,
        help='AUTO-015: Calculated preference percentage per FPPA Article 27(4)'
    )
    preference_amount = fields.Monetary(
        string='Preference Deduction Amount (ETB)',
        compute='_compute_preference_amount',
        store=True,
        currency_field='currency_id',
        help='AUTO-015: Monetary amount deducted for evaluation ranking only'
    )
    evaluated_price = fields.Monetary(
        string='Evaluated Price (ETB)',
        compute='_compute_evaluated_price',
        store=True,
        currency_field='currency_id',
        help='AUTO-015: Bid Price minus Preference Amount (for ranking only, not contract value)'
    )
    
    # Ranking
    rank = fields.Integer(string='Rank', help='Ranking by evaluated price (1 = lowest/best)')
    is_recommended = fields.Boolean(string='Recommended Awardee', compute='_compute_is_recommended', store=True)
    
    @api.depends('local_content_percentage')
    def _compute_preference_percentage(self):
        """AUTO-015: Calculate preference percentage per FPPA Proclamation 1210/2012 Article 27(4).
        
        Rules:
        - ≥70% local content: 13.5% preference
        - 40-70% local content: 11% preference
        - <40% local content: 0% preference (foreign)
        """
        for line in self:
            if line.local_content_percentage >= 70.0:
                line.preference_percentage = 13.5
            elif line.local_content_percentage >= 40.0:
                line.preference_percentage = 11.0
            else:
                line.preference_percentage = 0.0
    
    @api.depends('bid_price', 'preference_percentage')
    def _compute_preference_amount(self):
        """AUTO-015: Calculate monetary preference deduction amount."""
        for line in self:
            line.preference_amount = line.bid_price * (line.preference_percentage / 100.0)
    
    @api.depends('bid_price', 'preference_amount')
    def _compute_evaluated_price(self):
        """AUTO-015: Calculate evaluated price for ranking (BR-PROC-003).
        
        Note: Evaluated price is ONLY used for ranking bidders.
        Contract value uses original bid_price without deduction (BR-PROC-003).
        """
        for line in self:
            line.evaluated_price = line.bid_price - line.preference_amount
    
    @api.depends('rank')
    def _compute_is_recommended(self):
        """Mark the rank 1 bidder as recommended awardee."""
        for line in self:
            line.is_recommended = (line.rank == 1)
    
    @api.constrains('local_content_percentage')
    def _check_local_content(self):
        for line in self:
            if not (0 <= line.local_content_percentage <= 100):
                raise ValidationError('Local content percentage must be between 0 and 100.')
    
    @api.constrains('bid_price')
    def _check_bid_price(self):
        for line in self:
            if line.bid_price <= 0:
                raise ValidationError('Bid price must be greater than zero.')

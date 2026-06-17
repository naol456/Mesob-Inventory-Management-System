# -*- coding: utf-8 -*-
"""AUTO-053: One-Click Fiscal Year-End Valuation Report.

Generates comprehensive valuation report using FIFO costing from Stock Record Cards.
Compliance: FR-REP-001, FR-VAL-001
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from dateutil.relativedelta import relativedelta
import logging

_logger = logging.getLogger(__name__)


class MesobFiscalYearValuationWizard(models.TransientModel):
    """AUTO-053: One-Click Fiscal Year-End Valuation Report Wizard."""
    
    _name = 'mesob.fiscal.year.valuation.wizard'
    _description = 'Fiscal Year-End Valuation Report Wizard'
    
    # ── Report Parameters ───────────────────────────────────────────
    fiscal_year_start = fields.Date(
        string='Fiscal Year Start',
        required=True,
        default=lambda self: fields.Date.today().replace(month=7, day=8),
        help='Ethiopian fiscal year starts July 8 (Hamle 1)'
    )
    
    fiscal_year_end = fields.Date(
        string='Fiscal Year End',
        required=True,
        default=lambda self: fields.Date.today().replace(month=7, day=7) + relativedelta(years=1),
        help='Ethiopian fiscal year ends July 7 (Sene 30)'
    )
    
    report_date = fields.Date(
        string='Report Date',
        required=True,
        default=fields.Date.today,
        help='Date of report generation'
    )
    
    classification_ids = fields.Many2many(
        'mesob.inventory.major.classification',
        string='Classifications',
        help='Leave empty to include all classifications'
    )
    
    include_zero_balance = fields.Boolean(
        string='Include Zero Balance Items',
        default=False,
        help='Include items with zero quantity at year-end'
    )
    
    grouping = fields.Selection([
        ('classification', 'By Major Classification'),
        ('sub_classification', 'By Sub-Classification'),
        ('item', 'By Item'),
    ], string='Group By', default='classification', required=True)
    
    # ── Report Output ───────────────────────────────────────────────
    report_generated = fields.Boolean(default=False)
    report_html = fields.Html(string='Valuation Report', readonly=True)
    
    total_items = fields.Integer(string='Total Items', readonly=True)
    total_quantity = fields.Float(string='Total Quantity', readonly=True)
    total_value = fields.Monetary(
        string='Total Inventory Value',
        currency_field='currency_id',
        readonly=True
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )
    
    # ── Actions ─────────────────────────────────────────────────────
    
    def action_generate_report(self):
        """AUTO-053: Generate fiscal year-end valuation report (FR-REP-001).
        
        Process:
        1. Query all Stock Record Cards for final balances at fiscal year-end
        2. Calculate FIFO valuation for each item (FR-VAL-001)
        3. Group by classification as requested
        4. Generate HTML report with summary and detail sections
        5. Log generation for audit trail
        """
        self.ensure_one()
        
        # Validate dates
        if self.fiscal_year_end <= self.fiscal_year_start:
            raise UserError(_("Fiscal year end date must be after start date."))
        
        _logger.info(
            f"AUTO-053: Generating fiscal year-end valuation report for "
            f"{self.fiscal_year_start} to {self.fiscal_year_end}"
        )
        
        # Get valuation data
        valuation_data = self._get_valuation_data()
        
        # Generate HTML report
        report_html = self._generate_html_report(valuation_data)
        
        # Calculate totals
        total_items = sum(item['item_count'] for item in valuation_data)
        total_quantity = sum(item['quantity'] for item in valuation_data)
        total_value = sum(item['value'] for item in valuation_data)
        
        self.write({
            'report_generated': True,
            'report_html': report_html,
            'total_items': total_items,
            'total_quantity': total_quantity,
            'total_value': total_value,
        })
        
        _logger.info(
            f"AUTO-053: Valuation report generated - "
            f"Items: {total_items}, Quantity: {total_quantity:,.2f}, "
            f"Value: ETB {total_value:,.2f}"
        )
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }
    
    def _get_valuation_data(self):
        """Query stock record cards for fiscal year-end balances."""
        StockRecord = self.env['mesob.stock.record.card']
        Item = self.env['mesob.inventory.item']
        
        # Build domain for classifications if specified
        item_domain = []
        if self.classification_ids:
            item_domain = [('classification_id', 'in', self.classification_ids.ids)]
        
        items = Item.search(item_domain)
        
        valuation_data = []
        
        if self.grouping == 'classification':
            # Group by major classification
            classifications = items.mapped('classification_id')
            
            for classification in classifications:
                class_items = items.filtered(lambda i: i.classification_id == classification)
                class_value = 0.0
                class_quantity = 0.0
                
                for item in class_items:
                    # Get latest stock record within fiscal year
                    latest_record = StockRecord.search([
                        ('item_id', '=', item.id),
                        ('date', '<=', self.fiscal_year_end),
                        ('date', '>=', self.fiscal_year_start),
                    ], order='date desc, id desc', limit=1)
                    
                    if latest_record:
                        if latest_record.quantity_balance > 0 or self.include_zero_balance:
                            class_quantity += latest_record.quantity_balance
                            class_value += latest_record.balance_value
                
                if class_quantity > 0 or self.include_zero_balance:
                    valuation_data.append({
                        'name': classification.name,
                        'code': classification.code,
                        'item_count': len(class_items),
                        'quantity': class_quantity,
                        'value': class_value,
                        'average_cost': class_value / class_quantity if class_quantity > 0 else 0.0,
                        'items': []
                    })
        
        elif self.grouping == 'sub_classification':
            # Group by sub-classification
            sub_classifications = items.mapped('sub_classification_id')
            
            for sub_class in sub_classifications:
                sub_items = items.filtered(lambda i: i.sub_classification_id == sub_class)
                sub_value = 0.0
                sub_quantity = 0.0
                
                for item in sub_items:
                    latest_record = StockRecord.search([
                        ('item_id', '=', item.id),
                        ('date', '<=', self.fiscal_year_end),
                        ('date', '>=', self.fiscal_year_start),
                    ], order='date desc, id desc', limit=1)
                    
                    if latest_record:
                        if latest_record.quantity_balance > 0 or self.include_zero_balance:
                            sub_quantity += latest_record.quantity_balance
                            sub_value += latest_record.balance_value
                
                if sub_quantity > 0 or self.include_zero_balance:
                    valuation_data.append({
                        'name': sub_class.name,
                        'code': sub_class.code,
                        'item_count': len(sub_items),
                        'quantity': sub_quantity,
                        'value': sub_value,
                        'average_cost': sub_value / sub_quantity if sub_quantity > 0 else 0.0,
                        'items': []
                    })
        
        else:  # item
            # Item-level detail
            for item in items:
                latest_record = StockRecord.search([
                    ('item_id', '=', item.id),
                    ('date', '<=', self.fiscal_year_end),
                    ('date', '>=', self.fiscal_year_start),
                ], order='date desc, id desc', limit=1)
                
                if latest_record:
                    if latest_record.quantity_balance > 0 or self.include_zero_balance:
                        valuation_data.append({
                            'name': item.name,
                            'code': item.item_code,
                            'item_count': 1,
                            'quantity': latest_record.quantity_balance,
                            'value': latest_record.balance_value,
                            'average_cost': latest_record.average_cost,
                            'classification': item.classification_id.name,
                            'sub_classification': item.sub_classification_id.name,
                            'uom': item.uom_id.name if item.uom_id else '',
                            'items': []
                        })
        
        return sorted(valuation_data, key=lambda x: x['value'], reverse=True)
    
    def _generate_html_report(self, valuation_data):
        """Generate HTML report from valuation data."""
        total_value = sum(item['value'] for item in valuation_data)
        total_quantity = sum(item['quantity'] for item in valuation_data)
        total_items = sum(item['item_count'] for item in valuation_data)
        
        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 1200px; margin: 20px auto;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
                <h1 style="margin: 0; font-size: 28px;">Fiscal Year-End Inventory Valuation Report</h1>
                <p style="margin: 10px 0 0 0; opacity: 0.9;">AUTO-053: FIFO Valuation per FR-VAL-001</p>
            </div>
            
            <div style="background-color: #f8f9fa; padding: 20px; border-left: 4px solid #667eea;">
                <h3 style="margin-top: 0;">Report Parameters</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 8px; font-weight: bold; width: 200px;">Fiscal Year:</td>
                        <td style="padding: 8px;">{self.fiscal_year_start} to {self.fiscal_year_end}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; font-weight: bold;">Report Date:</td>
                        <td style="padding: 8px;">{self.report_date}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; font-weight: bold;">Grouping:</td>
                        <td style="padding: 8px;">{dict(self._fields['grouping'].selection).get(self.grouping)}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; font-weight: bold;">Generated By:</td>
                        <td style="padding: 8px;">{self.env.user.name}</td>
                    </tr>
                </table>
            </div>
            
            <div style="background-color: #d4edda; padding: 20px; margin-top: 20px; border-left: 4px solid #28a745;">
                <h3 style="margin-top: 0;">Summary</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 12px; font-size: 18px; font-weight: bold;">Total Items:</td>
                        <td style="padding: 12px; font-size: 18px; text-align: right;">{total_items:,}</td>
                    </tr>
                    <tr>
                        <td style="padding: 12px; font-size: 18px; font-weight: bold;">Total Quantity:</td>
                        <td style="padding: 12px; font-size: 18px; text-align: right;">{total_quantity:,.2f}</td>
                    </tr>
                    <tr style="background-color: #c3e6cb;">
                        <td style="padding: 15px; font-size: 22px; font-weight: bold;">Total Inventory Value:</td>
                        <td style="padding: 15px; font-size: 22px; text-align: right; color: #155724;">ETB {total_value:,.2f}</td>
                    </tr>
                </table>
            </div>
            
            <div style="margin-top: 30px;">
                <h3 style="border-bottom: 3px solid #667eea; padding-bottom: 10px;">Valuation Detail</h3>
                <table style="width: 100%; border-collapse: collapse; margin-top: 20px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <thead>
                        <tr style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white;">
                            <th style="padding: 15px; text-align: left;">{'Classification' if self.grouping == 'classification' else 'Sub-Classification' if self.grouping == 'sub_classification' else 'Item'}</th>
                            <th style="padding: 15px; text-align: left;">Code</th>
                            <th style="padding: 15px; text-align: right;">Items</th>
                            <th style="padding: 15px; text-align: right;">Quantity</th>
                            <th style="padding: 15px; text-align: right;">Avg Cost</th>
                            <th style="padding: 15px; text-align: right;">Total Value</th>
                            <th style="padding: 15px; text-align: right;">% of Total</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        
        for idx, item_data in enumerate(valuation_data):
            bg_color = '#f8f9fa' if idx % 2 == 0 else 'white'
            percentage = (item_data['value'] / total_value * 100) if total_value > 0 else 0
            
            html += f"""
                        <tr style="background-color: {bg_color};">
                            <td style="padding: 12px; border-bottom: 1px solid #dee2e6;">{item_data['name']}</td>
                            <td style="padding: 12px; border-bottom: 1px solid #dee2e6; font-family: monospace;">{item_data['code']}</td>
                            <td style="padding: 12px; border-bottom: 1px solid #dee2e6; text-align: right;">{item_data['item_count']}</td>
                            <td style="padding: 12px; border-bottom: 1px solid #dee2e6; text-align: right;">{item_data['quantity']:,.2f}</td>
                            <td style="padding: 12px; border-bottom: 1px solid #dee2e6; text-align: right;">ETB {item_data['average_cost']:,.2f}</td>
                            <td style="padding: 12px; border-bottom: 1px solid #dee2e6; text-align: right; font-weight: bold;">ETB {item_data['value']:,.2f}</td>
                            <td style="padding: 12px; border-bottom: 1px solid #dee2e6; text-align: right;">{percentage:.1f}%</td>
                        </tr>
            """
        
        html += f"""
                    </tbody>
                    <tfoot>
                        <tr style="background-color: #667eea; color: white; font-weight: bold; font-size: 16px;">
                            <td style="padding: 15px;" colspan="2">TOTAL</td>
                            <td style="padding: 15px; text-align: right;">{total_items}</td>
                            <td style="padding: 15px; text-align: right;">{total_quantity:,.2f}</td>
                            <td style="padding: 15px; text-align: right;">-</td>
                            <td style="padding: 15px; text-align: right;">ETB {total_value:,.2f}</td>
                            <td style="padding: 15px; text-align: right;">100.0%</td>
                        </tr>
                    </tfoot>
                </table>
            </div>
            
            <div style="background-color: #e7f3ff; padding: 15px; margin-top: 30px; border-left: 4px solid #0066cc; border-radius: 5px;">
                <p style="margin: 0;"><strong>ℹ️ Compliance Notes:</strong></p>
                <ul style="margin: 10px 0 0 20px;">
                    <li><strong>FR-VAL-001:</strong> Valuation calculated using FIFO (First-In-First-Out) method from Stock Record Cards</li>
                    <li><strong>FR-REP-001:</strong> Fiscal year-end valuation report generated automatically per SRS requirements</li>
                    <li><strong>NFR-QUAL-001:</strong> Real-time data from integrated Bin Card and Stock Record Card system</li>
                </ul>
            </div>
            
            <div style="text-align: center; margin-top: 30px; padding: 20px; background-color: #f8f9fa; border-radius: 5px;">
                <p style="margin: 0; color: #6c757d;">Report generated by Mesob Inventory Management System</p>
                <p style="margin: 5px 0 0 0; color: #6c757d; font-size: 12px;">Federal Democratic Republic of Ethiopia</p>
            </div>
        </div>
        """
        
        return html
    
    def action_print_report(self):
        """Print/export the valuation report."""
        self.ensure_one()
        
        if not self.report_generated:
            raise UserError(_("Please generate the report first."))
        
        return self.env.ref('mesob_inventory_base.action_report_fiscal_year_valuation').report_action(self)
    
    def action_export_excel(self):
        """Export valuation data to Excel."""
        self.ensure_one()
        
        if not self.report_generated:
            raise UserError(_("Please generate the report first."))
        
        # TODO: Implement Excel export using xlsxwriter or openpyxl
        raise UserError(_("Excel export coming soon. Use Print for now."))

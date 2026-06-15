# -*- coding: utf-8 -*-
"""AUTO-053: Fiscal Year-End Valuation Report Wizard.

One-click generation of stock valuation report by classification (4401-4418)
for fiscal year-end accounting (FR-REP-001).
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class MesobFiscalYearValuationWizard(models.TransientModel):
    """AUTO-053: One-Click Fiscal Year-End Valuation Report Generator."""
    
    _name = 'mesob.fiscal.year.valuation.wizard'
    _description = 'Fiscal Year-End Stock Valuation Report'
    
    # ── Report Parameters ───────────────────────────────────────────
    fiscal_year = fields.Char(
        string='Ethiopian Fiscal Year',
        required=True,
        default='2018 E.C.',
        help='Ethiopian fiscal year (e.g., 2018 E.C.)'
    )
    
    valuation_date = fields.Date(
        string='Valuation Date',
        required=True,
        default=fields.Date.today,
        help='Date for stock valuation calculation (typically fiscal year-end)'
    )
    
    classification_ids = fields.Many2many(
        'mesob.inventory.major.classification',
        string='Classifications',
        help='Leave empty to include all classifications (4401-4418)'
    )
    
    include_zero_balance = fields.Boolean(
        string='Include Zero Balance Items',
        default=False,
        help='Include items with zero stock balance in the report'
    )
    
    group_by_sub_classification = fields.Boolean(
        string='Group by Sub-Classification',
        default=True,
        help='Show subtotals per sub-classification'
    )
    
    # ── Report Results ──────────────────────────────────────────────
    report_generated = fields.Boolean(
        string='Report Generated',
        default=False,
        readonly=True
    )
    
    line_ids = fields.One2many(
        'mesob.fiscal.year.valuation.line',
        'wizard_id',
        string='Valuation Lines',
        readonly=True
    )
    
    # ── Summary Totals ──────────────────────────────────────────────
    total_quantity = fields.Float(
        string='Total Quantity',
        compute='_compute_totals',
        store=True
    )
    
    total_value = fields.Monetary(
        string='Total Value',
        compute='_compute_totals',
        store=True,
        currency_field='currency_id'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )
    
    @api.depends('line_ids.balance_value')
    def _compute_totals(self):
        for wizard in self:
            wizard.total_quantity = sum(wizard.line_ids.mapped('balance_quantity'))
            wizard.total_value = sum(wizard.line_ids.mapped('balance_value'))
    
    # ── Actions ─────────────────────────────────────────────────────
    
    def action_generate_report(self):
        """AUTO-053: Generate fiscal year-end valuation report (FR-REP-001)."""
        self.ensure_one()
        
        # Clear previous lines
        self.line_ids.unlink()
        
        # Get classifications (all if not specified)
        classifications = self.classification_ids if self.classification_ids else \
            self.env['mesob.inventory.major.classification'].search([])
        
        if not classifications:
            raise UserError(_('No classifications found. Please configure major classifications first.'))
        
        valuation_lines = []
        
        for classification in classifications:
            # Get all items in this classification
            items = self.env['mesob.inventory.item'].search([
                ('classification_id', '=', classification.id),
                ('active', '=', True)
            ])
            
            for item in items:
                # Get latest stock record card balance as of valuation date
                stock_record = self.env['mesob.stock.record.card'].search([
                    ('item_id', '=', item.id),
                    ('date', '<=', self.valuation_date)
                ], order='date desc, id desc', limit=1)
                
                balance_qty = stock_record.quantity_balance if stock_record else 0.0
                balance_value = stock_record.balance_value if stock_record else 0.0
                avg_cost = stock_record.average_cost if stock_record else 0.0
                
                # Skip zero balance items if not requested
                if not self.include_zero_balance and balance_qty == 0.0:
                    continue
                
                valuation_lines.append((0, 0, {
                    'wizard_id': self.id,
                    'classification_id': classification.id,
                    'sub_classification_id': item.sub_classification_id.id if item.sub_classification_id else False,
                    'item_id': item.id,
                    'item_code': item.item_code,
                    'item_name': item.name,
                    'balance_quantity': balance_qty,
                    'average_unit_cost': avg_cost,
                    'balance_value': balance_value,
                }))
        
        if not valuation_lines:
            raise UserError(_('No stock items found for the selected criteria.'))
        
        self.write({
            'line_ids': valuation_lines,
            'report_generated': True
        })
        
        _logger.info(
            f"AUTO-053: Fiscal year-end valuation report generated - "
            f"Year: {self.fiscal_year}, Date: {self.valuation_date}, "
            f"Lines: {len(valuation_lines)}, Total Value: ETB {self.total_value:,.2f}"
        )
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Fiscal Year Valuation: {self.fiscal_year}',
            'res_model': 'mesob.fiscal.year.valuation.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
    
    def action_export_excel(self):
        """Export report to Excel."""
        self.ensure_one()
        
        if not self.report_generated:
            raise UserError(_('Please generate the report first.'))
        
        # TODO: Implement Excel export using xlsxwriter
        # For now, return tree view for review
        return {
            'type': 'ir.actions.act_window',
            'name': f'Valuation Report: {self.fiscal_year}',
            'res_model': 'mesob.fiscal.year.valuation.line',
            'view_mode': 'tree',
            'domain': [('wizard_id', '=', self.id)],
            'context': {'group_by': ['classification_id', 'sub_classification_id']},
        }
    
    def action_send_to_accounts(self):
        """AUTO-053: Send valuation report to Accounts Unit (FR-REP-001)."""
        self.ensure_one()
        
        if not self.report_generated:
            raise UserError(_('Please generate the report first.'))
        
        # Find Accounts/PAO users
        accounts_users = self.env.ref('mesob_inventory_base.group_mesob_pao', raise_if_not_found=False)
        
        if not accounts_users or not accounts_users.users:
            raise UserError(_('No Accounts Unit users found. Please configure user groups.'))
        
        # Generate summary by classification
        summary_by_classification = {}
        for line in self.line_ids:
            class_code = line.classification_id.code
            class_name = line.classification_id.name
            
            if class_code not in summary_by_classification:
                summary_by_classification[class_code] = {
                    'name': class_name,
                    'total_value': 0.0,
                    'item_count': 0
                }
            
            summary_by_classification[class_code]['total_value'] += line.balance_value
            summary_by_classification[class_code]['item_count'] += 1
        
        # Build summary HTML
        summary_html = '<table border="1" cellpadding="5" style="border-collapse: collapse; width: 100%;">'
        summary_html += '<thead><tr style="background-color: #f0f0f0;"><th>Classification</th><th>Items</th><th>Total Value (ETB)</th></tr></thead>'
        summary_html += '<tbody>'
        
        for class_code in sorted(summary_by_classification.keys()):
            data = summary_by_classification[class_code]
            summary_html += f'''<tr>
                <td><strong>{class_code}</strong> - {data["name"]}</td>
                <td style="text-align: center;">{data["item_count"]}</td>
                <td style="text-align: right;">{data["total_value"]:,.2f}</td>
            </tr>'''
        
        summary_html += f'''<tr style="background-color: #e8f4f8; font-weight: bold;">
            <td>GRAND TOTAL</td>
            <td style="text-align: center;">{len(self.line_ids)}</td>
            <td style="text-align: right;">{self.total_value:,.2f}</td>
        </tr>'''
        summary_html += '</tbody></table>'
        
        # Send notification
        self.message_post(
            body=f"""<div>
                <h2>Fiscal Year-End Stock Valuation Report</h2>
                <p><strong>Ethiopian Fiscal Year:</strong> {self.fiscal_year}</p>
                <p><strong>Valuation Date:</strong> {self.valuation_date}</p>
                <hr/>
                <h3>Summary by Classification (FR-REP-001)</h3>
                {summary_html}
                <hr/>
                <p><em>This report has been auto-generated by the Inventory Management System (AUTO-053).</em></p>
                <p><em>For detailed line items, please access the full report in the system.</em></p>
            </div>""",
            subject=f'Fiscal Year-End Valuation Report: {self.fiscal_year}',
            message_type='notification',
            partner_ids=accounts_users.users.mapped('partner_id').ids
        )
        
        _logger.info(
            f"AUTO-053: Valuation report sent to Accounts Unit - "
            f"{len(accounts_users.users)} recipients"
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Report Sent'),
                'message': _(f'Fiscal year-end valuation report sent to {len(accounts_users.users)} Accounts Unit users.'),
                'type': 'success',
                'sticky': False,
            }
        }


class MesobFiscalYearValuationLine(models.TransientModel):
    """Valuation Report Line Detail."""
    
    _name = 'mesob.fiscal.year.valuation.line'
    _description = 'Fiscal Year Valuation Line'
    _order = 'classification_id, sub_classification_id, item_code'
    
    wizard_id = fields.Many2one(
        'mesob.fiscal.year.valuation.wizard',
        string='Wizard',
        required=True,
        ondelete='cascade'
    )
    
    classification_id = fields.Many2one(
        'mesob.inventory.major.classification',
        string='Major Classification',
        required=True
    )
    
    sub_classification_id = fields.Many2one(
        'mesob.inventory.sub.classification',
        string='Sub Classification'
    )
    
    item_id = fields.Many2one(
        'mesob.inventory.item',
        string='Item',
        required=True
    )
    
    item_code = fields.Char(string='Item Code', required=True)
    item_name = fields.Char(string='Item Name', required=True)
    
    balance_quantity = fields.Float(
        string='Balance Quantity',
        digits='Product Unit of Measure'
    )
    
    average_unit_cost = fields.Monetary(
        string='Average Unit Cost',
        currency_field='currency_id'
    )
    
    balance_value = fields.Monetary(
        string='Balance Value',
        currency_field='currency_id'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )

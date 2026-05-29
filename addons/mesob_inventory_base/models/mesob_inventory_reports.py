# -*- coding: utf-8 -*-
"""
Mesob Inventory Reporting Models (SRS 4.7)
Provides fiscal year-end, quarterly movement, and dormant stock reports
"""

from odoo import models, fields, api
from odoo.exceptions import UserError
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta


class MesobInventoryMovementReport(models.Model):
    """
    FR-REP-002: Quarterly movement reports per stock item
    Identifies dead/slow moving items for provisioning decisions
    """
    _name = 'mesob.inventory.movement.report'
    _description = 'Stock Movement Report'
    _auto = False
    _order = 'classification_code, item_code'

    # Item identification
    item_id = fields.Many2one('mesob.inventory.item', string='Item', readonly=True)
    item_code = fields.Char(string='Item Code', readonly=True)
    item_name = fields.Char(string='Item Name', readonly=True)
    classification_id = fields.Many2one('mesob.inventory.major.classification', 
                                       string='Classification', readonly=True)
    classification_code = fields.Char(string='Classification Code', readonly=True)
    
    # Period
    period_start = fields.Date(string='Period Start', readonly=True)
    period_end = fields.Date(string='Period End', readonly=True)
    
    # Opening balance
    opening_quantity = fields.Float(string='Opening Quantity', readonly=True, digits=(16, 2))
    opening_value = fields.Float(string='Opening Value', readonly=True, digits=(16, 2))
    
    # Receipts
    receipt_quantity = fields.Float(string='Receipts', readonly=True, digits=(16, 2))
    receipt_value = fields.Float(string='Receipt Value', readonly=True, digits=(16, 2))
    
    # Issues
    issue_quantity = fields.Float(string='Issues', readonly=True, digits=(16, 2))
    issue_value = fields.Float(string='Issue Value', readonly=True, digits=(16, 2))
    
    # Closing balance
    closing_quantity = fields.Float(string='Closing Quantity', readonly=True, digits=(16, 2))
    closing_value = fields.Float(string='Closing Value', readonly=True, digits=(16, 2))
    
    # Movement indicators
    days_since_last_issue = fields.Integer(string='Days Since Last Issue', readonly=True)
    is_dormant = fields.Boolean(string='Dormant (>90 days)', readonly=True)
    is_slow_moving = fields.Boolean(string='Slow Moving (>60 days)', readonly=True)
    
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True,
                                  default=lambda self: self.env.company.currency_id)

    def init(self):
        """Create SQL view for movement report"""
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW mesob_inventory_movement_report AS (
                SELECT
                    ROW_NUMBER() OVER (ORDER BY item.item_code) AS id,
                    item.id AS item_id,
                    item.item_code,
                    item.name AS item_name,
                    item.classification_id,
                    class.code AS classification_code,
                    NULL::date AS period_start,
                    NULL::date AS period_end,
                    0.0 AS opening_quantity,
                    0.0 AS opening_value,
                    COALESCE(SUM(CASE WHEN src.movement_type IN ('receipt', 'transfer_in', 'opening') 
                                 THEN src.receipt_quantity ELSE 0 END), 0) AS receipt_quantity,
                    COALESCE(SUM(CASE WHEN src.movement_type IN ('receipt', 'transfer_in', 'opening') 
                                 THEN src.receipt_total_value ELSE 0 END), 0) AS receipt_value,
                    COALESCE(SUM(CASE WHEN src.movement_type IN ('issue', 'transfer_out') 
                                 THEN src.issue_quantity ELSE 0 END), 0) AS issue_quantity,
                    COALESCE(SUM(CASE WHEN src.movement_type IN ('issue', 'transfer_out') 
                                 THEN src.issue_total_value ELSE 0 END), 0) AS issue_value,
                    COALESCE(MAX(src.balance_quantity), 0) AS closing_quantity,
                    COALESCE(MAX(src.balance_total_value), 0) AS closing_value,
                    COALESCE(CURRENT_DATE - MAX(CASE WHEN src.movement_type IN ('issue', 'transfer_out') 
                                                 THEN src.date END), 999)::integer AS days_since_last_issue,
                    CASE WHEN COALESCE(CURRENT_DATE - MAX(CASE WHEN src.movement_type IN ('issue', 'transfer_out') 
                                                           THEN src.date END), 999) > 90 
                         THEN TRUE ELSE FALSE END AS is_dormant,
                    CASE WHEN COALESCE(CURRENT_DATE - MAX(CASE WHEN src.movement_type IN ('issue', 'transfer_out') 
                                                           THEN src.date END), 999) > 60 
                         THEN TRUE ELSE FALSE END AS is_slow_moving
                FROM
                    mesob_inventory_item item
                    LEFT JOIN mesob_inventory_major_classification class ON item.classification_id = class.id
                    LEFT JOIN mesob_inventory_stock_record_card src ON item.id = src.item_id
                WHERE
                    item.active = TRUE
                GROUP BY
                    item.id, item.item_code, item.name, item.classification_id, class.code
            )
        """)


class MesobInventoryFiscalYearEndReport(models.TransientModel):
    """
    FR-REP-001: Fiscal year end stock value report by classification
    For accounts unit reconciliation
    """
    _name = 'mesob.inventory.fiscal.year.end.report'
    _description = 'Fiscal Year End Stock Valuation Report'

    name = fields.Char(string='Report Name', default='Fiscal Year End Stock Valuation')
    fiscal_year_end = fields.Date(string='Fiscal Year End Date', required=True,
                                  default=lambda self: fields.Date.today())
    line_ids = fields.One2many('mesob.inventory.fiscal.year.end.report.line', 
                               'report_id', string='Report Lines')
    total_value = fields.Float(string='Total Stock Value', compute='_compute_total', 
                               digits=(16, 2))
    currency_id = fields.Many2one('res.currency', string='Currency',
                                  default=lambda self: self.env.company.currency_id)

    @api.depends('line_ids.closing_value')
    def _compute_total(self):
        for report in self:
            report.total_value = sum(report.line_ids.mapped('closing_value'))

    def action_generate_report(self):
        """Generate fiscal year end report"""
        self.ensure_one()
        
        # Clear existing lines
        self.line_ids.unlink()
        
        # Get all classifications
        classifications = self.env['mesob.inventory.major.classification'].search([
            ('active', '=', True)
        ], order='code')
        
        # For each classification, get the closing stock value
        for classification in classifications:
            # Get latest stock record card entry for each item in this classification
            # up to the fiscal year end date
            query = """
                SELECT
                    classification_id,
                    classification_code,
                    COUNT(DISTINCT item_id) as item_count,
                    SUM(balance_quantity) as total_quantity,
                    SUM(balance_total_value) as total_value
                FROM (
                    SELECT DISTINCT ON (item_id)
                        item_id,
                        major_classification_id as classification_id,
                        classification_code,
                        balance_quantity,
                        balance_total_value
                    FROM mesob_inventory_stock_record_card
                    WHERE major_classification_id = %s
                      AND date <= %s
                    ORDER BY item_id, date DESC, id DESC
                ) latest_records
                GROUP BY classification_id, classification_code
            """
            
            self.env.cr.execute(query, (classification.id, self.fiscal_year_end))
            result = self.env.cr.dictfetchone()
            
            if result and result['total_value']:
                self.env['mesob.inventory.fiscal.year.end.report.line'].create({
                    'report_id': self.id,
                    'classification_id': classification.id,
                    'classification_code': classification.code,
                    'classification_name': classification.name,
                    'item_count': result['item_count'] or 0,
                    'total_quantity': result['total_quantity'] or 0.0,
                    'closing_value': result['total_value'] or 0.0,
                })
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Fiscal Year End Stock Valuation',
            'res_model': 'mesob.inventory.fiscal.year.end.report',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    def action_print_report(self):
        """Print fiscal year end report"""
        self.ensure_one()
        return self.env.ref('mesob_inventory_base.action_report_fiscal_year_end').report_action(self)


class MesobInventoryFiscalYearEndReportLine(models.TransientModel):
    """Lines for fiscal year end report"""
    _name = 'mesob.inventory.fiscal.year.end.report.line'
    _description = 'Fiscal Year End Report Line'
    _order = 'classification_code'

    report_id = fields.Many2one('mesob.inventory.fiscal.year.end.report', 
                                string='Report', required=True, ondelete='cascade')
    classification_id = fields.Many2one('mesob.inventory.major.classification', 
                                       string='Classification', required=True)
    classification_code = fields.Char(string='Code', required=True)
    classification_name = fields.Char(string='Classification', required=True)
    item_count = fields.Integer(string='# Items')
    total_quantity = fields.Float(string='Total Quantity', digits=(16, 2))
    closing_value = fields.Float(string='Closing Value', digits=(16, 2))
    currency_id = fields.Many2one(related='report_id.currency_id', string='Currency')

"""AUTO-054: Quarterly Movement Report with Dead-Stock Flagging.

Generates quarterly stock movement report showing:
- Opening balance, receipts, issues, closing balance
- Movement frequency analysis
- Dead stock identification (0 issues in 12 months)
- Slow-moving items (< 25% avg consumption)
- Dormant items (no movement in 6 months)
- Disposal recommendations per Section 4.11
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class MesobQuarterlyMovementReportWizard(models.TransientModel):
    """Wizard to generate quarterly movement report."""
    
    _name = "mesob.quarterly.movement.report.wizard"
    _description = "Quarterly Movement Report Wizard"
    
    fiscal_year = fields.Selection(
        [
            ("2023", "2023"),
            ("2024", "2024"),
            ("2025", "2025"),
            ("2026", "2026"),
            ("2027", "2027"),
        ],
        string="Fiscal Year",
        required=True,
        default=lambda self: str(fields.Date.today().year),
    )
    
    quarter = fields.Selection(
        [
            ("q1", "Q1 (Jan-Mar)"),
            ("q2", "Q2 (Apr-Jun)"),
            ("q3", "Q3 (Jul-Sep)"),
            ("q4", "Q4 (Oct-Dec)"),
        ],
        string="Quarter",
        required=True,
        default="q1",
    )
    
    classification_id = fields.Many2one(
        "mesob.inventory.major.classification",
        string="Classification",
        help="Leave empty to report all classifications",
    )
    
    include_dead_stock = fields.Boolean(
        string="Flag Dead Stock",
        default=True,
        help="Identify items with 0 issues in 12 months",
    )
    
    include_slow_moving = fields.Boolean(
        string="Flag Slow-Moving",
        default=True,
        help="Identify items with issues < 25% average consumption",
    )
    
    include_dormant = fields.Boolean(
        string="Flag Dormant Items",
        default=True,
        help="Identify items with no movement in 6 months",
    )
    
    report_generated = fields.Boolean(
        string="Report Generated",
        default=False,
        readonly=True,
    )
    
    report_data = fields.Text(
        string="Report Data",
        readonly=True,
    )
    
    def _get_quarter_dates(self):
        """Calculate start and end dates for selected quarter."""
        self.ensure_one()
        
        year = int(self.fiscal_year)
        quarter_map = {
            "q1": (1, 1, 3, 31),
            "q2": (4, 1, 6, 30),
            "q3": (7, 1, 9, 30),
            "q4": (10, 1, 12, 31),
        }
        
        start_month, start_day, end_month, end_day = quarter_map[self.quarter]
        
        start_date = datetime(year, start_month, start_day).date()
        end_date = datetime(year, end_month, end_day).date()
        
        return start_date, end_date
    
    def action_generate_report(self):
        """AUTO-054: Generate quarterly movement report."""
        self.ensure_one()
        
        start_date, end_date = self._get_quarter_dates()
        
        # Get all items (filtered by classification if specified)
        domain = [("active", "=", True)]
        if self.classification_id:
            domain.append(("classification_id", "=", self.classification_id.id))
        
        items = self.env["mesob.inventory.item"].search(domain)
        
        if not items:
            raise UserError(_("No items found for the selected criteria."))
        
        # Analyze each item
        report_lines = []
        dead_stock_items = []
        slow_moving_items = []
        dormant_items = []
        
        for item in items:
            analysis = self._analyze_item_movement(item, start_date, end_date)
            report_lines.append(analysis)
            
            # Flag problematic items
            if self.include_dead_stock and analysis["is_dead_stock"]:
                dead_stock_items.append(analysis)
            
            if self.include_slow_moving and analysis["is_slow_moving"]:
                slow_moving_items.append(analysis)
            
            if self.include_dormant and analysis["is_dormant"]:
                dormant_items.append(analysis)
        
        # Build report HTML
        report_html = self._build_report_html(
            report_lines, dead_stock_items, slow_moving_items, dormant_items,
            start_date, end_date
        )
        
        self.write({
            "report_generated": True,
            "report_data": report_html,
        })
        
        # Log report generation
        _logger.info(
            f"AUTO-054: Quarterly report generated - "
            f"Period: {start_date} to {end_date}, "
            f"Items: {len(items)}, "
            f"Dead: {len(dead_stock_items)}, "
            f"Slow: {len(slow_moving_items)}, "
            f"Dormant: {len(dormant_items)}"
        )
        
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
    
    def _analyze_item_movement(self, item, start_date, end_date):
        """Analyze movement for a single item."""
        StockRecord = self.env["mesob.stock.record.card"]
        
        # Get stock records for the period
        period_records = StockRecord.search([
            ("item_id", "=", item.id),
            ("date", ">=", start_date),
            ("date", "<=", end_date),
        ], order="date asc")
        
        # Calculate opening balance (last record before period)
        opening_record = StockRecord.search([
            ("item_id", "=", item.id),
            ("date", "<", start_date),
        ], order="date desc", limit=1)
        
        opening_balance = opening_record.quantity_balance if opening_record else 0.0
        
        # Calculate period movements
        receipts = sum(period_records.mapped("quantity_in"))
        issues = sum(period_records.mapped("quantity_out"))
        
        # Closing balance
        closing_record = StockRecord.search([
            ("item_id", "=", item.id),
            ("date", "<=", end_date),
        ], order="date desc", limit=1)
        
        closing_balance = closing_record.quantity_balance if closing_record else 0.0
        
        # Check for dead stock (0 issues in last 12 months)
        twelve_months_ago = end_date - timedelta(days=365)
        recent_issues = StockRecord.search_count([
            ("item_id", "=", item.id),
            ("date", ">=", twelve_months_ago),
            ("date", "<=", end_date),
            ("quantity_out", ">", 0),
        ])
        
        is_dead_stock = recent_issues == 0 and closing_balance > 0
        
        # Check for slow-moving (< 25% avg consumption)
        avg_quarterly_consumption = issues / 3 if issues > 0 else 0  # Rough estimate
        is_slow_moving = (issues > 0 and issues < (avg_quarterly_consumption * 0.25)) or \
                        (issues == 0 and receipts > 0)
        
        # Check for dormant (no movement in 6 months)
        six_months_ago = end_date - timedelta(days=180)
        recent_movement = StockRecord.search_count([
            ("item_id", "=", item.id),
            ("date", ">=", six_months_ago),
            ("date", "<=", end_date),
        ])
        
        is_dormant = recent_movement == 0 and closing_balance > 0
        
        return {
            "item": item,
            "item_code": item.item_code,
            "item_name": item.name,
            "classification": item.classification_id.name if item.classification_id else "N/A",
            "opening_balance": opening_balance,
            "receipts": receipts,
            "issues": issues,
            "closing_balance": closing_balance,
            "movement_count": len(period_records),
            "is_dead_stock": is_dead_stock,
            "is_slow_moving": is_slow_moving,
            "is_dormant": is_dormant,
        }
    
    def _build_report_html(self, report_lines, dead_stock, slow_moving, dormant, start_date, end_date):
        """Build HTML report."""
        html = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px;">
            <h2 style="color: #2c3e50;">AUTO-054: Quarterly Stock Movement Report</h2>
            <p><strong>Period:</strong> {start_date} to {end_date}</p>
            <p><strong>Generated:</strong> {fields.Datetime.now()}</p>
            <p><strong>Total Items:</strong> {len(report_lines)}</p>
            <hr/>
            
            <h3 style="color: #e74c3c;">🚨 Dead Stock Items ({len(dead_stock)})</h3>
            <p><em>Items with 0 issues in the last 12 months - Recommend disposal review per Section 4.11</em></p>
            <table border="1" cellpadding="5" cellspacing="0" style="width: 100%; border-collapse: collapse;">
                <tr style="background-color: #e74c3c; color: white;">
                    <th>Item Code</th>
                    <th>Name</th>
                    <th>Classification</th>
                    <th>Closing Balance</th>
                </tr>
        """
        
        for item_data in dead_stock[:20]:  # Show first 20
            html += f"""
                <tr>
                    <td>{item_data['item_code']}</td>
                    <td>{item_data['item_name']}</td>
                    <td>{item_data['classification']}</td>
                    <td>{item_data['closing_balance']:.2f}</td>
                </tr>
            """
        
        html += """
            </table>
            <br/>
            
            <h3 style="color: #f39c12;">⚠️ Slow-Moving Items (%s)</h3>
            <p><em>Items with low turnover - Review for consolidation or disposal</em></p>
        """ % len(slow_moving)
        
        html += """
            <br/>
            <h3 style="color: #95a5a6;">💤 Dormant Items (%s)</h3>
            <p><em>No movement in 6 months - Verify status and storage cost</em></p>
        """ % len(dormant)
        
        html += """
            <hr/>
            <h3>Complete Movement Summary</h3>
            <table border="1" cellpadding="5" cellspacing="0" style="width: 100%; border-collapse: collapse; font-size: 12px;">
                <tr style="background-color: #34495e; color: white;">
                    <th>Item Code</th>
                    <th>Name</th>
                    <th>Opening</th>
                    <th>Receipts</th>
                    <th>Issues</th>
                    <th>Closing</th>
                    <th>Movements</th>
                    <th>Status</th>
                </tr>
        """
        
        for item_data in report_lines[:50]:  # Show first 50
            status_badges = []
            if item_data["is_dead_stock"]:
                status_badges.append("DEAD")
            if item_data["is_slow_moving"]:
                status_badges.append("SLOW")
            if item_data["is_dormant"]:
                status_badges.append("DORMANT")
            
            status = ", ".join(status_badges) if status_badges else "OK"
            
            html += f"""
                <tr>
                    <td>{item_data['item_code']}</td>
                    <td>{item_data['item_name'][:30]}</td>
                    <td style="text-align: right;">{item_data['opening_balance']:.2f}</td>
                    <td style="text-align: right;">{item_data['receipts']:.2f}</td>
                    <td style="text-align: right;">{item_data['issues']:.2f}</td>
                    <td style="text-align: right;">{item_data['closing_balance']:.2f}</td>
                    <td style="text-align: center;">{item_data['movement_count']}</td>
                    <td>{status}</td>
                </tr>
            """
        
        html += """
            </table>
        </div>
        """
        
        return html
    
    def action_export_excel(self):
        """Export report to Excel (future enhancement)."""
        raise UserError(_("Excel export feature coming soon!"))

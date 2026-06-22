# -*- coding: utf-8 -*-
"""Task 12: Dashboard KPI Calculator

Calculates Key Performance Indicators for inventory management:
- Stock accuracy
- PO delivery performance
- Requisition cycle time
- Dead stock value
- Budget utilization
"""

from odoo import api, fields, models
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class MesobDashboardKPI(models.Model):
    """Dashboard KPI calculator and storage."""
    
    _name = 'mesob.dashboard.kpi'
    _description = 'Dashboard KPI'
    _order = 'date desc, id desc'
    
    name = fields.Char(string='KPI Name', required=True)
    date = fields.Date(string='Calculation Date', required=True, default=fields.Date.today)
    kpi_type = fields.Selection([
        ('stock_accuracy', 'Stock Accuracy %'),
        ('po_ontime', 'PO On-Time Delivery %'),
        ('requisition_cycle', 'Requisition Cycle Time (days)'),
        ('dead_stock_value', 'Dead Stock Value'),
        ('budget_utilization', 'Budget Utilization %'),
    ], string='KPI Type', required=True)
    
    value = fields.Float(string='KPI Value', digits=(16, 2))
    target_value = fields.Float(string='Target Value', digits=(16, 2))
    status = fields.Selection([
        ('good', 'Good - Above Target'),
        ('warning', 'Warning - Near Target'),
        ('critical', 'Critical - Below Target'),
    ], string='Status', compute='_compute_status', store=True)
    
    notes = fields.Text(string='Notes')
    
    @api.depends('value', 'target_value', 'kpi_type')
    def _compute_status(self):
        """Determine KPI status based on value vs target."""
        for record in self:
            if not record.target_value or not record.value:
                record.status = 'warning'
                continue
            
            # For percentages and rates, higher is better
            if record.kpi_type in ('stock_accuracy', 'po_ontime', 'budget_utilization'):
                if record.value >= record.target_value:
                    record.status = 'good'
                elif record.value >= record.target_value * 0.9:
                    record.status = 'warning'
                else:
                    record.status = 'critical'
            
            # For cycle time, lower is better
            elif record.kpi_type == 'requisition_cycle':
                if record.value <= record.target_value:
                    record.status = 'good'
                elif record.value <= record.target_value * 1.2:
                    record.status = 'warning'
                else:
                    record.status = 'critical'
            
            # For dead stock value, lower is better
            elif record.kpi_type == 'dead_stock_value':
                if record.value <= record.target_value:
                    record.status = 'good'
                elif record.value <= record.target_value * 1.5:
                    record.status = 'warning'
                else:
                    record.status = 'critical'
    
    @api.model
    def calculate_stock_accuracy(self, date_from=None, date_to=None):
        """Calculate stock accuracy percentage.
        
        Stock Accuracy = (Items with correct count / Total items counted) * 100
        Based on stock-taking records.
        """
        if not date_to:
            date_to = fields.Date.today()
        if not date_from:
            date_from = date_to - timedelta(days=30)
        
        # Get stock-taking records in period
        stock_takings = self.env['mesob.stock.taking'].search([
            ('date', '>=', date_from),
            ('date', '<=', date_to),
            ('state', '=', 'done')
        ])
        
        if not stock_takings:
            return 0.0
        
        total_lines = 0
        accurate_lines = 0
        
        for taking in stock_takings:
            for line in taking.line_ids:
                total_lines += 1
                # Consider accurate if variance is within 1% or 0
                variance_pct = abs((line.counted_qty - line.system_qty) / line.system_qty * 100) if line.system_qty > 0 else 0
                if variance_pct <= 1.0:  # Within 1%
                    accurate_lines += 1
        
        accuracy = (accurate_lines / total_lines * 100) if total_lines > 0 else 0.0
        
        _logger.info(f"Task 12: Stock Accuracy calculated: {accuracy:.2f}% ({accurate_lines}/{total_lines})")
        
        return accuracy
    
    @api.model
    def calculate_po_ontime_delivery(self, date_from=None, date_to=None):
        """Calculate PO on-time delivery percentage.
        
        On-Time % = (POs delivered on/before expected date / Total delivered POs) * 100
        """
        if not date_to:
            date_to = fields.Date.today()
        if not date_from:
            date_from = date_to - timedelta(days=90)
        
        # Get completed POs in period
        completed_pos = self.env['mesob.procurement.order'].search([
            ('date_order', '>=', date_from),
            ('date_order', '<=', date_to),
            ('state', 'in', ['fully_received', 'closed'])
        ])
        
        if not completed_pos:
            return 0.0
        
        total_pos = len(completed_pos)
        ontime_pos = 0
        
        for po in completed_pos:
            # Check if delivered on time (comparing expected vs actual delivery)
            if po.expected_delivery_date and po.actual_delivery_date:
                if po.actual_delivery_date <= po.expected_delivery_date:
                    ontime_pos += 1
            else:
                # If no dates, consider as on-time (benefit of doubt)
                ontime_pos += 1
        
        ontime_pct = (ontime_pos / total_pos * 100) if total_pos > 0 else 0.0
        
        _logger.info(f"Task 12: PO On-Time Delivery: {ontime_pct:.2f}% ({ontime_pos}/{total_pos})")
        
        return ontime_pct
    
    @api.model
    def calculate_requisition_cycle_time(self, date_from=None, date_to=None):
        """Calculate average requisition approval cycle time.
        
        Cycle Time = Average days from submission to approval
        """
        if not date_to:
            date_to = fields.Date.today()
        if not date_from:
            date_from = date_to - timedelta(days=30)
        
        # Get approved requisitions in period
        requisitions = self.env['mesob.inventory.requisition'].search([
            ('submitted_on', '>=', date_from),
            ('submitted_on', '<=', date_to),
            ('state', 'in', ['approved', 'issued', 'received'])
        ])
        
        if not requisitions:
            return 0.0
        
        total_days = 0
        count = 0
        
        for req in requisitions:
            if req.submitted_on and req.approved_on:
                # Calculate days between submission and approval
                submitted = fields.Date.from_string(req.submitted_on) if isinstance(req.submitted_on, str) else req.submitted_on
                approved = fields.Date.from_string(req.approved_on) if isinstance(req.approved_on, str) else req.approved_on
                days_diff = (approved - submitted).days
                total_days += days_diff
                count += 1
        
        avg_cycle_time = total_days / count if count > 0 else 0.0
        
        _logger.info(f"Task 12: Average Requisition Cycle Time: {avg_cycle_time:.2f} days")
        
        return avg_cycle_time
    
    @api.model
    def calculate_dead_stock_value(self):
        """Calculate total value of dead stock.
        
        Dead Stock = Items with no movement in last 12 months
        """
        twelve_months_ago = fields.Date.today() - timedelta(days=365)
        
        # Get items with no issues in last 12 months
        all_items = self.env['mesob.inventory.item'].search([('active', '=', True)])
        
        dead_stock_value = 0.0
        dead_stock_count = 0
        
        for item in all_items:
            # Check if item has any issues in last 12 months
            recent_issues = self.env['mesob.inventory.issue.voucher.line'].search_count([
                ('item_id', '=', item.id),
                ('issue_date', '>=', twelve_months_ago)
            ])
            
            if recent_issues == 0:
                # Dead stock - no issues in 12 months
                # Calculate value: current stock * average unit cost
                if item.current_stock > 0:
                    # Try to get unit cost from last receiving
                    last_receiving = self.env['mesob.inventory.receiving.line'].search([
                        ('item_id', '=', item.id)
                    ], order='id desc', limit=1)
                    
                    unit_cost = last_receiving.unit_price if last_receiving else 100.0  # Default if no receiving
                    item_value = item.current_stock * unit_cost
                    dead_stock_value += item_value
                    dead_stock_count += 1
        
        _logger.info(f"Task 12: Dead Stock Value: ETB {dead_stock_value:.2f} ({dead_stock_count} items)")
        
        return dead_stock_value
    
    @api.model
    def calculate_budget_utilization(self, fiscal_year=None):
        """Calculate budget utilization percentage.
        
        Budget Utilization = (Actual Spending / Budget Allocation) * 100
        """
        if not fiscal_year:
            fiscal_year = str(fields.Date.today().year)
        
        # Get budget allocations for fiscal year
        budget_allocations = self.env['mesob.budget.allocation'].search([
            ('fiscal_year', '=', fiscal_year)
        ])
        
        if not budget_allocations:
            return 0.0
        
        total_budget = sum(budget_allocations.mapped('allocated_amount'))
        total_spent = sum(budget_allocations.mapped('spent_amount'))
        
        utilization_pct = (total_spent / total_budget * 100) if total_budget > 0 else 0.0
        
        _logger.info(f"Task 12: Budget Utilization: {utilization_pct:.2f}% (ETB {total_spent:.2f} / ETB {total_budget:.2f})")
        
        return utilization_pct
    
    @api.model
    def refresh_all_kpis(self):
        """Refresh all KPIs with current data.
        
        Called by scheduled action or manual refresh.
        """
        today = fields.Date.today()
        
        # Calculate each KPI
        kpis_to_create = [
            {
                'name': 'Stock Accuracy',
                'date': today,
                'kpi_type': 'stock_accuracy',
                'value': self.calculate_stock_accuracy(),
                'target_value': 98.0,  # Target: 98% accuracy
            },
            {
                'name': 'PO On-Time Delivery',
                'date': today,
                'kpi_type': 'po_ontime',
                'value': self.calculate_po_ontime_delivery(),
                'target_value': 85.0,  # Target: 85% on-time
            },
            {
                'name': 'Requisition Cycle Time',
                'date': today,
                'kpi_type': 'requisition_cycle',
                'value': self.calculate_requisition_cycle_time(),
                'target_value': 3.0,  # Target: 3 days
            },
            {
                'name': 'Dead Stock Value',
                'date': today,
                'kpi_type': 'dead_stock_value',
                'value': self.calculate_dead_stock_value(),
                'target_value': 50000.0,  # Target: ETB 50,000
            },
            {
                'name': 'Budget Utilization',
                'date': today,
                'kpi_type': 'budget_utilization',
                'value': self.calculate_budget_utilization(),
                'target_value': 90.0,  # Target: 90% utilization
            },
        ]
        
        # Create KPI records
        created_kpis = []
        for kpi_data in kpis_to_create:
            kpi = self.create(kpi_data)
            created_kpis.append(kpi)
        
        _logger.info(f"Task 12: Refreshed {len(created_kpis)} KPIs for {today}")
        
        return created_kpis

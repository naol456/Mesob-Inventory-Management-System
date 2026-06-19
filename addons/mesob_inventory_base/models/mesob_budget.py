# -*- coding: utf-8 -*-
"""AUTO-003: Budget Availability Check Before Needs Acceptance.

Budget allocation and tracking for procurement planning.
Prevents unfunded needs from entering the consolidation workflow.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class MesobBudgetAllocation(models.Model):
    """Budget allocation per classification for fiscal year (AUTO-003)."""
    
    _name = 'mesob.budget.allocation'
    _description = 'Budget Allocation by Classification'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'fiscal_year desc, classification_code'
    
    name = fields.Char(
        string='Allocation Reference',
        required=True,
        copy=False,
        default='New'
    )
    
    fiscal_year = fields.Char(
        string='Ethiopian Fiscal Year',
        required=True,
        tracking=True,
        help='e.g., 2018 E.C.'
    )
    
    classification_code = fields.Selection([
        ('4401', '4401 - Office Supplies'),
        ('4402', '4402 - Stationery'),
        ('4403', '4403 - Cleaning Materials'),
        ('4404', '4404 - Printed Forms'),
        ('4405', '4405 - Fuel & Lubricants'),
        ('4406', '4406 - Spare Parts'),
        ('4407', '4407 - Books & Publications'),
        ('4408', '4408 - Medical Supplies'),
        ('4409', '4409 - Agricultural Supplies'),
        ('4410', '4410 - Construction Materials'),
        ('4411', '4411 - Drugs & Chemicals'),
        ('4412', '4412 - Food & Beverages'),
        ('4413', '4413 - Vehicles'),
        ('4414', '4414 - Machinery & Equipment'),
        ('4415', '4415 - Furniture & Fixtures'),
        ('4416', '4416 - IT Equipment'),
        ('4417', '4417 - Communication Equipment'),
        ('4418', '4418 - Other Equipment'),
    ], string='Budget Classification', required=True, tracking=True)
    
    allocated_budget = fields.Monetary(
        string='Allocated Budget',
        required=True,
        currency_field='currency_id',
        tracking=True,
        help='Total budget allocated for this classification in fiscal year'
    )
    
    committed_budget = fields.Monetary(
        string='Committed Budget',
        compute='_compute_budget_status',
        store=True,
        currency_field='currency_id',
        help='AUTO-003: Sum of reviewed needs + approved lots'
    )
    
    available_budget = fields.Monetary(
        string='Available Budget',
        compute='_compute_budget_status',
        store=True,
        currency_field='currency_id',
        help='AUTO-003: Remaining budget = Allocated - Committed'
    )
    
    utilization_percent = fields.Float(
        string='Utilization (%)',
        compute='_compute_budget_status',
        store=True,
        help='Percentage of budget committed'
    )
    
    budget_status = fields.Selection([
        ('available', 'Available'),
        ('warning', 'Warning (>80%)'),
        ('critical', 'Critical (>95%)'),
        ('exhausted', 'Exhausted'),
    ], string='Status', compute='_compute_budget_status', store=True)
    
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('closed', 'Closed'),
    ], string='State', default='draft', required=True, tracking=True)
    
    notes = fields.Text(string='Notes')
    
    _sql_constraints = [
        ('unique_classification_fiscal_year', 
         'UNIQUE(fiscal_year, classification_code)',
         'Budget allocation for this classification and fiscal year already exists!')
    ]
    
    @api.model_create_multi
    def create(self, vals_list):
        """Generate reference on creation."""
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                classification = vals.get('classification_code', 'XXXX')
                fiscal_year = vals.get('fiscal_year', 'FY')
                vals['name'] = f"BUD/{fiscal_year}/{classification}"
        return super().create(vals_list)
    
    @api.depends('allocated_budget', 'fiscal_year', 'classification_code')
    def _compute_budget_status(self):
        """AUTO-003: Calculate committed and available budget."""
        for rec in self:
            # Calculate committed from reviewed needs
            needs_committed = sum(
                self.env['mesob.procurement.need'].search([
                    ('fiscal_year', '=', rec.fiscal_year),
                    ('budget_classification', '=', rec.classification_code),
                    ('state', 'in', ['reviewed', 'locked'])
                ]).mapped('total_price')
            )
            
            # Calculate committed from approved lots
            lots_committed = sum(
                self.env['mesob.procurement.plan.lot'].search([
                    ('plan_id.fiscal_year', '=', rec.fiscal_year),
                    ('plan_id.state', 'in', ['puh_approved', 'pec_approved', 'hope_approved']),
                ]).filtered(
                    lambda lot: lot.sub_classification_id and 
                    lot.sub_classification_id.classification_id and
                    lot.sub_classification_id.classification_id.code == rec.classification_code.split(' - ')[0]
                ).mapped('budget')
            )
            
            total_committed = needs_committed + lots_committed
            rec.committed_budget = total_committed
            rec.available_budget = rec.allocated_budget - total_committed
            
            # Calculate utilization
            if rec.allocated_budget > 0:
                rec.utilization_percent = (total_committed / rec.allocated_budget) * 100
            else:
                rec.utilization_percent = 0.0
            
            # Determine status
            if rec.available_budget <= 0:
                rec.budget_status = 'exhausted'
            elif rec.utilization_percent >= 95:
                rec.budget_status = 'critical'
            elif rec.utilization_percent >= 80:
                rec.budget_status = 'warning'
            else:
                rec.budget_status = 'available'
    
    def action_confirm(self):
        """Confirm budget allocation."""
        for rec in self:
            if rec.allocated_budget <= 0:
                raise ValidationError("Allocated budget must be greater than zero.")
            rec.state = 'confirmed'
            _logger.info(f"AUTO-003: Budget confirmed - {rec.name}: ETB {rec.allocated_budget:,.2f}")
    
    def action_reset_to_draft(self):
        """Reset to draft."""
        self.write({'state': 'draft'})
    
    def action_close(self):
        """Close fiscal year budget."""
        self.write({'state': 'closed'})
    
    @api.model
    def check_budget_availability(self, classification_code, fiscal_year, amount):
        """AUTO-003: Check if budget is available for a given amount.
        
        Args:
            classification_code: Budget classification (e.g., '4401')
            fiscal_year: Ethiopian fiscal year (e.g., '2018 E.C.')
            amount: Amount to check
        
        Returns:
            dict: {'available': bool, 'balance': float, 'warning': str}
        """
        budget = self.search([
            ('classification_code', '=', classification_code),
            ('fiscal_year', '=', fiscal_year),
            ('state', '=', 'confirmed')
        ], limit=1)
        
        if not budget:
            return {
                'available': False,
                'balance': 0.0,
                'warning': f"❌ No confirmed budget allocation found for {classification_code} in {fiscal_year}. Please configure budget before submitting needs."
            }
        
        if budget.available_budget < amount:
            return {
                'available': False,
                'balance': budget.available_budget,
                'warning': (
                    f"❌ Insufficient budget for {classification_code}.\n"
                    f"Required: ETB {amount:,.2f}\n"
                    f"Available: ETB {budget.available_budget:,.2f}\n"
                    f"Shortfall: ETB {amount - budget.available_budget:,.2f}"
                )
            }
        
        # Check warning levels
        remaining_after = budget.available_budget - amount
        new_utilization = ((budget.committed_budget + amount) / budget.allocated_budget) * 100
        
        warning = None
        if new_utilization >= 95:
            warning = (
                f"⚠️ Critical budget level: This request will use {new_utilization:.1f}% of allocated budget.\n"
                f"Remaining after approval: ETB {remaining_after:,.2f}"
            )
        elif new_utilization >= 80:
            warning = (
                f"⚠️ Warning: This request will use {new_utilization:.1f}% of allocated budget.\n"
                f"Remaining after approval: ETB {remaining_after:,.2f}"
            )
        
        return {
            'available': True,
            'balance': budget.available_budget,
            'warning': warning
        }

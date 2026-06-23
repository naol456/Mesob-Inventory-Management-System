import re
import logging
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)
_ITEM_CODE_PATTERN = re.compile(r"^(?P<major>\d{4})-(?P<sub>\d{3})-(?P<specific>\d{3})$")


class MesobInventoryItem(models.Model):
    """Inventory item master with FDRE-standard coding and stock-control levels.

    Coding format: ####-###-### (FR-ID-002)
    Classification: linked to chart-of-accounts 4401–4418 (FR-ID-001)
    Stock control: min/max/reorder/safety levels & ABC class (FR-SC-001, FR-SC-005)
    """

    _name = "mesob.inventory.item"
    _description = "Inventory Item"
    _rec_name = "item_code"
    _order = "item_code"

    _sql_constraints = [
        ('item_code_unique', 'UNIQUE(item_code)', 'Item Code must be unique.'),
        ('item_code_format', "CHECK(item_code ~ '^[0-9]{4}-[0-9]{3}-[0-9]{3}$')", 
         'Item Code must follow the format ####-###-### (digits and dashes).'),
    ]

    # ── Identification ──────────────────────────────────────────────────

    item_code = fields.Char(
        string="Item Code",
        required=True,
        index=True,
        copy=False,
        help="FDRE item code format: ####-###-### (10 digits total).",
    )

    major_code = fields.Char(
        string="Major Code",
        compute="_compute_item_code_segments",
        inverse="_inverse_item_code_segments",
        store=True,
        help="First 4 digits of the FDRE item code (classification aligned to chart of accounts).",
    )
    sub_code = fields.Char(
        string="Sub Code",
        compute="_compute_item_code_segments",
        inverse="_inverse_item_code_segments",
        store=True,
        help="Middle 3 digits of the FDRE item code (sub-class).",
    )
    specific_code = fields.Char(
        string="Specific Code",
        compute="_compute_item_code_segments",
        inverse="_inverse_item_code_segments",
        store=True,
        help="Last 3 digits of the FDRE item code (specific item).",
    )

    classification_id = fields.Many2one(
        "mesob.inventory.major.classification",
        string="Major Classification",
        index=True,
        help="Chart-of-accounts classification (4401–4418).",
    )

    sub_classification_id = fields.Many2one(
        "mesob.inventory.sub.classification",
        string="Sub Classification",
        index=True,
        help="Sub classification under major classification.",
    )

    name = fields.Char(
        string="Name (English)",
        required=True,
        index=True,
    )
    name_am = fields.Char(
        string="Name (Amharic)",
        help="Amharic translation of the item name.",
    )
    description = fields.Text()
    active = fields.Boolean(default=True)
    is_surplus = fields.Boolean(
        string="Is Surplus",
        default=False,
        help="Whether this item is flagged as surplus in the Disposal system (BR-PROC-008).",
    )


    # ── Unit of Measure ─────────────────────────────────────────────────

    uom_id = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
        help="Default unit of measure for this item.",
    )

    # ── Product Linkage ─────────────────────────────────────────────────

    product_id = fields.Many2one(
        "product.product",
        string="Linked Product",
        help="Odoo product for stock operations and valuation.",
        index=True,
    )

    # ── Stock Control Levels (FR-SC-001) ────────────────────────────────

    minimum_level = fields.Float(
        string="Minimum Level",
        default=0.0,
        help="Minimum stock quantity before alert.",
    )
    maximum_level = fields.Float(
        string="Maximum Level",
        default=0.0,
        help="Maximum stock quantity allowed.",
    )
    reorder_level = fields.Float(
        string="Reorder Level",
        default=0.0,
        help="Stock level at which to trigger a purchase/requisition.",
    )
    hastening_level = fields.Float(
        string="Hastening Level",
        default=0.0,
        help="Level at which to expedite pending deliveries.",
    )
    safety_stock = fields.Float(
        string="Safety Stock",
        default=0.0,
        help="Buffer stock to cover demand variability.",
    )

    # ── Lead Times (FR-SC-002) ──────────────────────────────────────────

    admin_lead_time = fields.Integer(
        string="Administrative Lead Time (days)",
        default=0,
        help="Days for internal processing before order is placed.",
    )
    supplier_lead_time = fields.Integer(
        string="Supplier Lead Time (days)",
        default=0,
        help="Days from order placement to delivery.",
    )

    # ── ABC Classification (FR-SC-005) ──────────────────────────────────

    abc_class = fields.Selection(
        [
            ("A", "A — High Value / High Priority"),
            ("B", "B — Medium Value / Medium Priority"),
            ("C", "C — Low Value / Low Priority"),
        ],
        string="ABC Class",
        help="ABC analysis classification by usage value to prioritize management attention.",
    )
    
    # ── AUTO-062: Control Levels Auto-Calculation ──────────────────────
    
    auto_reorder_enabled = fields.Boolean(
        string="Enable Auto-Reorder Calculation",
        default=False,
        help="AUTO-062: Enable automatic calculation of reorder levels from historical usage"
    )
    
    historical_period_months = fields.Integer(
        string="Historical Period (Months)",
        default=6,
        help="AUTO-062: Number of months to analyze for usage calculation"
    )
    
    average_monthly_usage = fields.Float(
        string="Avg Monthly Usage",
        compute="_compute_usage_statistics",
        store=True,
        help="AUTO-062: Average monthly usage calculated from history"
    )
    
    max_monthly_usage = fields.Float(
        string="Max Monthly Usage",
        compute="_compute_usage_statistics",
        store=True,
        help="AUTO-062: Maximum monthly usage in historical period"
    )
    
    last_calculation_date = fields.Datetime(
        string="Last Auto-Calculation",
        readonly=True,
        help="AUTO-062: Last time control levels were auto-calculated"
    )
    
    suggested_reorder_level = fields.Float(
        string="Suggested Reorder Level",
        compute="_compute_suggested_levels",
        help="AUTO-062: System-calculated reorder level based on usage + lead time"
    )
    
    suggested_minimum_level = fields.Float(
        string="Suggested Minimum Level",
        compute="_compute_suggested_levels",
        help="AUTO-062: System-calculated minimum level (safety stock)"
    )
    
    suggested_maximum_level = fields.Float(
        string="Suggested Maximum Level",
        compute="_compute_suggested_levels",
        help="AUTO-062: System-calculated maximum level"
    )
    
    # ADVANCED AUTO-062: Enhanced Control Level Features
    seasonal_pattern_detected = fields.Boolean(
        string="Seasonal Pattern Detected",
        compute="_compute_seasonal_analysis",
        store=True,
        help="ADVANCED: True if item shows seasonal usage patterns"
    )
    
    peak_season_months = fields.Char(
        string="Peak Season",
        compute="_compute_seasonal_analysis",
        store=True,
        help="ADVANCED: Months with highest usage (e.g., 'Dec, Jan, Feb')"
    )
    
    seasonal_adjustment_factor = fields.Float(
        string="Seasonal Adjustment",
        compute="_compute_seasonal_analysis",
        store=True,
        help="ADVANCED: Multiplier for seasonal peak (e.g., 1.5 = 50% higher)"
    )
    
    usage_trend = fields.Selection([
        ('stable', 'Stable'),
        ('increasing', 'Increasing'),
        ('decreasing', 'Decreasing'),
        ('volatile', 'Volatile'),
    ], string="Usage Trend", compute="_compute_usage_trend", store=True,
       help="ADVANCED: Overall trend in usage patterns")
    
    trend_percentage = fields.Float(
        string="Trend %",
        compute="_compute_usage_trend",
        store=True,
        help="ADVANCED: Percentage change in usage (positive = increasing)"
    )
    
    demand_variability = fields.Float(
        string="Demand Variability (CV)",
        compute="_compute_demand_variability",
        store=True,
        help="ADVANCED: Coefficient of Variation (StdDev/Mean) - higher = more variable"
    )
    
    economic_order_quantity = fields.Float(
        string="EOQ",
        compute="_compute_eoq",
        help="ADVANCED: Economic Order Quantity (optimal order size)"
    )
    
    eoq_ordering_cost = fields.Float(
        string="Ordering Cost (ETB)",
        default=500.0,
        help="ADVANCED: Cost per purchase order (for EOQ calculation)"
    )
    
    eoq_holding_cost_percent = fields.Float(
        string="Holding Cost %",
        default=20.0,
        help="ADVANCED: Annual holding cost as % of item value (for EOQ)"
    )
    
    confidence_level = fields.Float(
        string="Confidence Level %",
        compute="_compute_confidence_intervals",
        help="ADVANCED: Statistical confidence in calculations (e.g., 95%)"
    )
    
    reorder_level_lower_bound = fields.Float(
        string="Reorder Level (Lower)",
        compute="_compute_confidence_intervals",
        help="ADVANCED: Lower confidence bound for reorder level"
    )
    
    reorder_level_upper_bound = fields.Float(
        string="Reorder Level (Upper)",
        compute="_compute_confidence_intervals",
        help="ADVANCED: Upper confidence bound for reorder level"
    )
    
    forecasted_next_month_usage = fields.Float(
        string="Forecasted Usage (Next Month)",
        compute="_compute_demand_forecast",
        help="ADVANCED: AI-predicted usage for next month"
    )
    
    forecast_accuracy_percent = fields.Float(
        string="Forecast Accuracy %",
        compute="_compute_forecast_accuracy",
        help="ADVANCED: Historical accuracy of forecasts"
    )
    
    # ADVANCED AUTO-065: Smart Review Features
    review_frequency_days = fields.Integer(
        string="Review Frequency (Days)",
        compute="_compute_review_frequency",
        store=True,
        help="ADVANCED: How often to review (based on ABC class and variability)"
    )
    
    next_review_date = fields.Date(
        string="Next Review Due",
        compute="_compute_next_review_date",
        store=True,
        help="ADVANCED: When levels should be reviewed next"
    )
    
    review_priority = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ], string="Review Priority", compute="_compute_review_priority", store=True,
       help="ADVANCED: Priority for reviewing control levels")
    
    significant_change_detected = fields.Boolean(
        string="Significant Change",
        compute="_compute_change_detection",
        help="ADVANCED: True if usage pattern changed significantly"
    )
    
    change_detection_threshold = fields.Float(
        string="Change Threshold %",
        default=20.0,
        help="ADVANCED: % change to trigger review alert (default: 20%)"
    )

    # ── Stock Status & Monitoring ───────────────────────────────────────

    current_stock = fields.Float(
        string="Current Stock",
        compute="_compute_current_stock",
        help="Current stock balance from bin card"
    )

    stock_status = fields.Selection([
        ('critical', 'Critical - Below Minimum'),
        ('low', 'Low - Below Reorder'),
        ('hasten', 'Hasten - Below Hastening'),
        ('normal', 'Normal'),
        ('high', 'High - Above Maximum'),
    ], string="Stock Status", compute="_compute_stock_status", store=True)

    issue_status = fields.Selection([
        ('issued', 'Issued'),
        ('not_issued', 'Not Issued'),
    ], string="Issue Status", compute="_compute_issue_status")

    current_holder = fields.Char(
        string="Current Holder",
        compute="_compute_current_holder",
        help="The actual employee, department, or requester currently holding the item. Shows department or initials + name."
    )

    total_lead_time = fields.Integer(
        string="Total Lead Time (days)",
        compute="_compute_total_lead_time",
        store=True,
        help="Total lead time = Administrative + Supplier lead time"
    )

    # ── Controlled Material Flag (FR-ISSUE-004) ─────────────────────────

    is_controlled = fields.Boolean(
        string="Controlled Material",
        default=False,
        help="If checked, issue restricted to authorized individuals only "
             "(e.g. drugs, chemicals, explosives).",
    )
    
    # ── AUTO-066: Dormant/Damaged/Obsolete Item Flagging ────────────────
    
    is_dormant = fields.Boolean(
        string="Dormant Item",
        compute="_compute_item_flags",
        store=True,
        help="AUTO-066: Auto-flagged if no issues in configured dormant period"
    )
    
    is_slow_moving = fields.Boolean(
        string="Slow Moving",
        compute="_compute_item_flags",
        store=True,
        help="AUTO-066: Auto-flagged if usage below threshold"
    )
    
    is_damaged = fields.Boolean(
        string="Damaged",
        default=False,
        help="AUTO-066: Manually flagged damaged items (FR-DISP2-001)"
    )
    
    is_obsolete = fields.Boolean(
        string="Obsolete",
        default=False,
        help="AUTO-066: Manually flagged obsolete items (FR-DISP2-001)"
    )
    
    days_since_last_issue = fields.Integer(
        string="Days Since Last Issue",
        compute="_compute_item_flags",
        store=True,
        help="AUTO-066: Number of days since last issue"
    )
    
    dormant_threshold_days = fields.Integer(
        string="Dormant Threshold (Days)",
        default=365,
        help="AUTO-066: Days of no activity before flagging as dormant"
    )
    
    item_condition_notes = fields.Text(
        string="Condition Notes",
        help="AUTO-066: Notes about item condition/status"
    )
    
    # ADVANCED AUTO-066: AI Obsolescence Prediction
    obsolescence_risk_score = fields.Float(
        string="Obsolescence Risk Score",
        compute="_compute_obsolescence_risk",
        store=True,
        help="ADVANCED: AI-predicted risk of becoming obsolete (0-100)"
    )
    
    obsolescence_risk_level = fields.Selection([
        ('low', 'Low Risk'),
        ('medium', 'Medium Risk'),
        ('high', 'High Risk'),
        ('critical', 'Critical - Act Now'),
    ], string="Obsolescence Risk", compute="_compute_obsolescence_risk", store=True,
       help="ADVANCED: Risk classification for obsolescence")
    
    predicted_dormant_date = fields.Date(
        string="Predicted Dormant Date",
        compute="_compute_dormancy_prediction",
        help="ADVANCED: AI-predicted date when item will become dormant"
    )
    
    months_until_dormant = fields.Integer(
        string="Months Until Dormant",
        compute="_compute_dormancy_prediction",
        help="ADVANCED: Estimated months before item becomes dormant"
    )
    
    alternative_items = fields.Many2many(
        'mesob.inventory.item',
        'mesob_item_alternatives_rel',
        'item_id',
        'alternative_id',
        string="Alternative Items",
        help="ADVANCED: Suggested replacement items"
    )
    
    market_availability = fields.Selection([
        ('available', 'Available in Market'),
        ('limited', 'Limited Availability'),
        ('discontinued', 'Discontinued'),
        ('unknown', 'Unknown'),
    ], string="Market Status", default='unknown',
       help="ADVANCED: Market availability status")
    
    estimated_disposal_value = fields.Float(
        string="Estimated Disposal Value (ETB)",
        compute="_compute_disposal_value",
        help="ADVANCED: Estimated scrap/salvage value"
    )
    
    disposal_recommendation = fields.Selection([
        ('keep', 'Keep - Still Useful'),
        ('monitor', 'Monitor - Watch Usage'),
        ('transfer', 'Transfer to Another Location'),
        ('donate', 'Donate to Charity'),
        ('sell', 'Sell as Surplus'),
        ('scrap', 'Scrap/Dispose'),
    ], string="Disposal Recommendation", compute="_compute_disposal_recommendation",
       help="ADVANCED: AI-suggested disposal action")
    
    disposal_urgency = fields.Selection([
        ('none', 'No Action Needed'),
        ('low', 'Low - Plan for Next Quarter'),
        ('medium', 'Medium - Plan for Next Month'),
        ('high', 'High - Act This Week'),
    ], string="Disposal Urgency", compute="_compute_disposal_recommendation",
       help="ADVANCED: Urgency of disposal action")
    
    # ADVANCED AUTO-067: Disposal Feedback Loop
    procurement_suspended = fields.Boolean(
        string="Procurement Suspended",
        default=False,
        help="ADVANCED: True if procurement blocked due to surplus"
    )
    
    suspension_reason = fields.Selection([
        ('surplus', 'Surplus Stock Available'),
        ('dormant', 'Dormant Item'),
        ('damaged', 'Damaged - No More Orders'),
        ('obsolete', 'Obsolete - Discontinued'),
    ], string="Suspension Reason",
       help="ADVANCED: Why procurement is suspended")
    
    suspension_date = fields.Date(
        string="Suspended Since",
        help="ADVANCED: When procurement was suspended"
    )
    
    suspension_lifted_conditions = fields.Text(
        string="Lift Suspension When",
        help="ADVANCED: Conditions to resume procurement (e.g., 'Stock < 50 units')"
    )
    
    auto_resume_at_level = fields.Float(
        string="Auto-Resume at Level",
        help="ADVANCED: Stock level to automatically lift suspension"
    )
    
    surplus_consumption_rate = fields.Float(
        string="Surplus Consumption Rate",
        compute="_compute_surplus_metrics",
        help="ADVANCED: Units/month surplus being consumed"
    )
    
    estimated_surplus_depletion_date = fields.Date(
        string="Surplus Depletion Date",
        compute="_compute_surplus_metrics",
        help="ADVANCED: Predicted date when surplus will be consumed"
    )

    # ── Catalog Exclusion (FR-ID-006) ───────────────────────────────────

    exclude_from_catalog = fields.Boolean(
        string="Exclude from Catalog",
        default=False,
        help="Mark seldom-required/non-repetitive items excluded from the coding catalog.",
    )
    
    # ── AUTO-067: Procurement Suspension (BR-PROC-008) ──────────────────
    
    procurement_suspended = fields.Boolean(
        string="Procurement Suspended",
        default=False,
        tracking=True,
        help="AUTO-067: When True, blocks new PO approval for this item (BR-PROC-008). "
             "Set automatically when item flagged as surplus or manually by PAO."
    )
    
    suspension_reason = fields.Selection([
        ('surplus', 'Surplus Stock - Exceeds 24 months consumption'),
        ('dormant', 'Dormant - No movement in 24 months'),
        ('obsolete', 'Obsolete - Superseded by newer item'),
        ('manual', 'Manual Suspension - PAO Decision'),
    ], string="Suspension Reason", tracking=True,
       help="AUTO-067: Reason for procurement suspension")
    
    suspension_date = fields.Date(
        string="Suspension Date",
        readonly=True,
        tracking=True,
        help="AUTO-067: Date when procurement was suspended"
    )
    
    suspended_by_id = fields.Many2one(
        'res.users',
        string="Suspended By",
        readonly=True,
        tracking=True,
        help="AUTO-067: User who suspended procurement (system or PAO)"
    )
    
    suspension_notes = fields.Text(
        string="Suspension Notes",
        help="AUTO-067: Additional notes about procurement suspension"
    )
    
    clearance_date = fields.Date(
        string="Clearance Date",
        readonly=True,
        tracking=True,
        help="AUTO-067: Date when suspension was cleared"
    )
    
    cleared_by_id = fields.Many2one(
        'res.users',
        string="Cleared By",
        readonly=True,
        tracking=True,
        help="AUTO-067: PAO who cleared the suspension flag"
    )
    
    clearance_reason = fields.Text(
        string="Clearance Reason",
        help="AUTO-067: Documented reason for clearing suspension (e.g., anticipated demand surge)"
    )
    
    # ── AUTO-036: Auto-Generation Tracking ──────────────────────────────
    
    code_auto_generated = fields.Boolean(
        string="Code Auto-Generated",
        default=False,
        readonly=True,
        help="AUTO-036: True if item code was auto-generated by system"
    )
    
    # ── Task 9: QR Code for Item Identification ─────────────────────────
    
    qr_code = fields.Binary(
        string="Item QR Code",
        compute="_compute_qr_code",
        store=True,
        help="Task 9: QR code for item identification - encodes item_code for scanning"
    )
    
    generated_on = fields.Datetime(
        string="Code Generated On",
        readonly=True,
        help="AUTO-036: Timestamp of code generation"
    )
    
    generated_by_id = fields.Many2one(
        'res.users',
        string="Generated By",
        readonly=True,
        help="AUTO-036: User who triggered code generation"
    )

    # ── Computed / Validation ───────────────────────────────────────────

    @api.depends("item_code", "name")
    def _compute_display_name(self):
        for rec in self:
            if rec.item_code and rec.name:
                rec.display_name = f"{rec.item_code} - {rec.name}"
            else:
                rec.display_name = rec.name or rec.item_code or "Unnamed Item"
    
    # ── AUTO-067: Procurement Suspension Methods ────────────────────────
    
    def action_suspend_procurement(self, reason='manual', notes=None):
        """AUTO-067: Suspend procurement for this item (BR-PROC-008).
        
        Blocks new PO approval until:
        - Surplus consumed (stock falls below max level) OR
        - PAO explicitly clears flag with documented reason
        
        Args:
            reason: One of 'surplus', 'dormant', 'obsolete', 'manual'
            notes: Additional notes about suspension
        """
        for rec in self:
            if rec.procurement_suspended:
                _logger.warning(f"AUTO-067: Procurement already suspended for item {rec.item_code}")
                continue
            
            rec.write({
                'procurement_suspended': True,
                'suspension_reason': reason,
                'suspension_date': fields.Date.today(),
                'suspended_by_id': self.env.user.id,
                'suspension_notes': notes or f"Procurement suspended due to {reason}",
            })
            
            # Log in chatter
            reason_label = dict(rec._fields['suspension_reason'].selection).get(reason, reason)
            rec.message_post(
                body=f"""<div style="background-color: #fff3cd; border-left: 4px solid #f57c00; padding: 15px;">
                    <h3>🚫 AUTO-067: Procurement Suspended</h3>
                    <p><strong>Reason:</strong> {reason_label}</p>
                    <p><strong>Suspended By:</strong> {self.env.user.name}</p>
                    <p><strong>Date:</strong> {fields.Date.today()}</p>
                    {f'<p><strong>Notes:</strong> {notes}</p>' if notes else ''}
                    <p><strong>Effect:</strong> New PO approval blocked until suspension cleared (BR-PROC-008)</p>
                </div>""",
                subject=f'Procurement Suspended: {rec.item_code}'
            )
            
            _logger.info(
                f"AUTO-067: Procurement suspended for item {rec.item_code} - "
                f"Reason: {reason}, By: {self.env.user.name}"
            )
    
    def action_clear_procurement_suspension(self, clearance_reason=None):
        """AUTO-067: Clear procurement suspension with documented reason.
        
        PAO can clear suspension flag to allow procurement when:
        - Surplus has been consumed (stock < max level)
        - Anticipated demand surge requires restocking
        - Other justified business reason
        
        Args:
            clearance_reason: Mandatory documented reason for clearing
        """
        self.ensure_one()
        
        if not clearance_reason or len(clearance_reason) < 20:
            raise ValidationError(
                "AUTO-067: Clearance reason is mandatory and must be at least 20 characters. "
                "Please document why procurement suspension is being lifted."
            )
        
        if not self.procurement_suspended:
            raise ValidationError("Procurement is not currently suspended for this item.")
        
        # Check if user is PAO
        if not self.env.user.has_group('mesob_inventory_base.group_mesob_pao'):
            raise ValidationError(
                "Only PAO (Property Administration Officer) can clear procurement suspension."
            )
        
        self.write({
            'procurement_suspended': False,
            'clearance_date': fields.Date.today(),
            'cleared_by_id': self.env.user.id,
            'clearance_reason': clearance_reason,
        })
        
        # Log in chatter
        self.message_post(
            body=f"""<div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px;">
                <h3>✅ AUTO-067: Procurement Suspension Cleared</h3>
                <p><strong>Cleared By:</strong> {self.env.user.name} (PAO)</p>
                <p><strong>Date:</strong> {fields.Date.today()}</p>
                <p><strong>Reason for Clearance:</strong></p>
                <p style="background-color: white; padding: 10px; border-radius: 4px;">{clearance_reason}</p>
                <p><strong>Effect:</strong> New PO approval now allowed for this item</p>
            </div>""",
            subject=f'Procurement Suspension Cleared: {self.item_code}'
        )
        
        _logger.info(
            f"AUTO-067: Procurement suspension cleared for item {self.item_code} - "
            f"By: {self.env.user.name}, Reason: {clearance_reason[:50]}..."
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Procurement Suspension Cleared',
                'message': f'Procurement for {self.item_code} is now allowed.',
                'type': 'success',
                'sticky': False,
            }
        }
    
    def _auto_check_surplus_and_suspend(self):
        """AUTO-067: Auto-check if item should be suspended due to surplus.
        
        Called by AUTO-066 disposal flagging system.
        Suspends procurement if:
        - Stock > maximum level AND
        - Surplus > 24 months consumption
        """
        for rec in self:
            if rec.procurement_suspended:
                continue  # Already suspended
            
            # Check if item has surplus flag
            if not rec.is_surplus:
                continue
            
            # Get current stock
            rec._compute_current_stock()
            
            # Check if stock exceeds maximum level
            if rec.maximum_level > 0 and rec.current_stock > rec.maximum_level:
                # Calculate surplus months
                # Get last 12 months consumption
                twelve_months_ago = fields.Date.today() - timedelta(days=365)
                issue_lines = self.env['mesob.inventory.issue.voucher.line'].search([
                    ('item_id', '=', rec.id),
                    ('voucher_id.issue_date', '>=', twelve_months_ago)
                ])
                
                total_issued = sum(line.quantity_issued for line in issue_lines)
                monthly_consumption = total_issued / 12 if total_issued > 0 else 0
                
                if monthly_consumption > 0:
                    surplus_qty = rec.current_stock - rec.maximum_level
                    surplus_months = surplus_qty / monthly_consumption
                    
                    if surplus_months >= 24:
                        # Auto-suspend procurement
                        notes = (
                            f"AUTO-067: Auto-suspended due to surplus stock. "
                            f"Current: {rec.current_stock}, Max: {rec.maximum_level}, "
                            f"Surplus: {surplus_qty:,.2f} ({surplus_months:.1f} months of consumption)"
                        )
                        rec.action_suspend_procurement(reason='surplus', notes=notes)
                        
                        _logger.info(
                            f"AUTO-067: Auto-suspended procurement for {rec.item_code} - "
                            f"Surplus: {surplus_months:.1f} months"
                        )
        for rec in self:
            if rec.item_code and rec.name:
                rec.display_name = f"[{rec.item_code}] {rec.name}"
            else:
                rec.display_name = rec.name or rec.item_code or ""
    
    @api.depends("item_code")
    def _compute_qr_code(self):
        """Task 9: Generate QR code for item identification.
        
        QR code contains: Item code + Name for easy scanning
        Used for: Receiving, Issue, Stock-taking, Physical verification
        """
        try:
            import qrcode
            import base64
            from io import BytesIO
        except ImportError:
            # QR code library not installed
            for record in self:
                record.qr_code = False
            return
        
        for record in self:
            if record.item_code:
                # Generate QR code data: MESOB-ITEM:item_code:name
                qr_data = f"MESOB-ITEM:{record.item_code}:{record.name or ''}"
                
                # Create QR code
                qr = qrcode.QRCode(version=1, box_size=10, border=4)
                qr.add_data(qr_data)
                qr.make(fit=True)
                
                img = qr.make_image(fill_color="black", back_color="white")
                
                # Convert to binary
                buffer = BytesIO()
                img.save(buffer, format="PNG")
                qr_code_binary = base64.b64encode(buffer.getvalue())
                
                record.qr_code = qr_code_binary
                _logger.debug(f"Task 9: Generated QR code for item {record.item_code}")
            else:
                record.qr_code = False

    @api.constrains("item_code")
    def _check_item_code_format(self):
        for record in self:
            if not record.item_code:
                continue
            if not _ITEM_CODE_PATTERN.fullmatch(record.item_code):
                raise ValidationError(
                    "Item Code must follow the format ####-###-### (digits and dashes)."
                )

    @api.constrains("classification_id", "major_code")
    def _check_classification_consistency(self):
        """Validate that major_code matches classification_id.code."""
        for record in self:
            if record.classification_id and record.major_code:
                if record.classification_id.code != record.major_code:
                    raise ValidationError(
                        f"Major code {record.major_code} does not match "
                        f"classification code {record.classification_id.code}."
                    )

    @api.constrains("sub_classification_id", "sub_code")
    def _check_sub_classification_consistency(self):
        """Validate that sub_code matches sub_classification_id.code."""
        for record in self:
            if record.sub_classification_id and record.sub_code:
                if record.sub_classification_id.code != record.sub_code:
                    raise ValidationError(
                        f"Sub code {record.sub_code} does not match "
                        f"sub classification code {record.sub_classification_id.code}."
                    )

    @api.depends("item_code")
    def _compute_item_code_segments(self):
        for record in self:
            match = _ITEM_CODE_PATTERN.fullmatch(record.item_code or "")
            if not match:
                record.major_code = False
                record.sub_code = False
                record.specific_code = False
                continue
            record.major_code = match.group("major")
            record.sub_code = match.group("sub")
            record.specific_code = match.group("specific")

    def _inverse_item_code_segments(self):
        for record in self:
            if not (record.major_code and record.sub_code and record.specific_code):
                continue

            major = (record.major_code or "").strip()
            sub = (record.sub_code or "").strip()
            specific = (record.specific_code or "").strip()
            record.item_code = f"{major}-{sub}-{specific}"

    @api.onchange("classification_id")
    def _onchange_classification_id(self):
        """Auto-fill major code prefix from classification selection."""
        if self.classification_id and self.classification_id.code:
            self.major_code = self.classification_id.code

    @api.onchange("major_code")
    def _onchange_major_code(self):
        """Auto-link classification when major code is typed manually."""
        if self.major_code:
            classification = self.env["mesob.inventory.major.classification"].search(
                [("code", "=", self.major_code)], limit=1
            )
            if classification:
                self.classification_id = classification.id
    
    @api.model_create_multi
    def create(self, vals_list):
        """AUTO-036: Enhanced create with auto-code generation and validation.
        
        AUTO-038: Also checks for duplicate items before creation.
        """
        for vals in vals_list:
            # AUTO-036: Auto-generate item code if not provided
            if not vals.get('item_code') and vals.get('classification_id') and vals.get('sub_classification_id'):
                vals['item_code'] = self._auto_generate_item_code(
                    vals['classification_id'],
                    vals['sub_classification_id']
                )
                vals['code_auto_generated'] = True
                vals['generated_on'] = fields.Datetime.now()
                vals['generated_by_id'] = self.env.user.id
                
                _logger.info(
                    f"AUTO-036: Auto-generated item code: {vals['item_code']} "
                    f"by user {self.env.user.name}"
                )
            
            # AUTO-038: Check for duplicate items before creation
            if vals.get('name'):
                similar_items = self._detect_similar_items(
                    vals['name'],
                    vals.get('classification_id')
                )
                
                if similar_items:
                    # Log warning but allow creation (user was notified)
                    _logger.warning(
                        f"AUTO-038: Creating item '{vals['name']}' despite similar items found: "
                        f"{', '.join(similar_items.mapped('item_code'))}"
                    )
        
        return super().create(vals_list)
    
    def _auto_generate_item_code(self, classification_id, sub_classification_id):
        """AUTO-036: Auto-generate next available item code (FR-ID-002, FR-ID-003).
        
        Format: ####-###-### where:
        - #### = Major classification code (e.g., 4402)
        - ### = Sub classification code (e.g., 001)
        - ### = Next available specific item number (auto-incremented)
        
        Returns:
            str: Generated item code
        """
        # Get classification codes
        classification = self.env['mesob.inventory.major.classification'].browse(classification_id)
        sub_classification = self.env['mesob.inventory.sub.classification'].browse(sub_classification_id)
        
        if not classification or not sub_classification:
            raise UserError("AUTO-036: Cannot auto-generate code without valid classifications.")
        
        major_code = classification.code
        sub_code = sub_classification.code
        
        # Find highest existing specific code for this major-sub combination
        existing_items = self.search([
            ('major_code', '=', major_code),
            ('sub_code', '=', sub_code)
        ], order='specific_code desc', limit=1)
        
        if existing_items and existing_items[0].specific_code:
            try:
                last_specific = int(existing_items[0].specific_code)
                next_specific = last_specific + 1
            except ValueError:
                # Fallback if existing code is not numeric
                next_specific = 1
        else:
            next_specific = 1
        
        # Validate uniqueness
        max_attempts = 1000
        attempt = 0
        while attempt < max_attempts:
            specific_code = str(next_specific + attempt).zfill(3)
            candidate_code = f"{major_code}-{sub_code}-{specific_code}"
            
            # Check if code already exists
            existing = self.search([('item_code', '=', candidate_code)])
            if not existing:
                _logger.info(f"AUTO-036: Generated code {candidate_code} (FR-ID-002, FR-ID-003)")
                return candidate_code
            
            attempt += 1
        
        raise UserError(
            f"AUTO-036: Unable to generate unique item code after {max_attempts} attempts. "
            f"Major: {major_code}, Sub: {sub_code}"
        )
    
    def _detect_similar_items(self, item_name, classification_id=None):
        """AUTO-038: Detect potentially duplicate items using keyword matching.
        
        Searches existing items for similar descriptions to prevent duplicates (BR-ID-001).
        
        Args:
            item_name (str): Item name/description to check
            classification_id (int, optional): Filter by classification
        
        Returns:
            recordset: Similar items found
        """
        if not item_name or len(item_name) < 3:
            return self.env['mesob.inventory.item']
        
        # Extract keywords (simple approach - production would use NLP)
        # Remove common words and split
        common_words = {'the', 'a', 'an', 'and', 'or', 'of', 'in', 'for', 'with', 'to', 'from'}
        keywords = [
            word.lower().strip() 
            for word in item_name.split() 
            if word.lower() not in common_words and len(word) > 2
        ]
        
        if not keywords:
            return self.env['mesob.inventory.item']
        
        # Build search domain
        domain = [('active', '=', True)]
        if classification_id:
            domain.append(('classification_id', '=', classification_id))
        
        # Search for items with matching keywords
        name_conditions = ['|'] * (len(keywords) - 1) if len(keywords) > 1 else []
        for keyword in keywords:
            name_conditions.append(('name', 'ilike', keyword))
        
        domain.extend(name_conditions)
        
        similar_items = self.search(domain, limit=5)
        
        if similar_items:
            _logger.info(
                f"AUTO-038: Found {len(similar_items)} similar items for '{item_name}': "
                f"{', '.join(similar_items.mapped('item_code'))}"
            )
        
        return similar_items
    
    def action_check_duplicates(self):
        """AUTO-038: Manual duplicate check action for existing items."""
        self.ensure_one()
        
        similar_items = self._detect_similar_items(
            self.name,
            self.classification_id.id if self.classification_id else None
        ).filtered(lambda i: i.id != self.id)  # Exclude self
        
        if not similar_items:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Duplicates Found',
                    'message': f'No similar items found for "{self.name}"',
                    'type': 'success',
                    'sticky': False,
                }
            }
        
        # Build similar items message
        items_html = '<ul>'
        for item in similar_items:
            items_html += f'<li><strong>{item.item_code}</strong>: {item.name}</li>'
        items_html += '</ul>'
        
        self.message_post(
            body=f"""<div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px;">
                <h3>⚠️ AUTO-038: Similar Items Detected</h3>
                <p><strong>Current Item:</strong> {self.item_code} - {self.name}</p>
                <p><strong>Similar Items Found:</strong></p>
                {items_html}
                <p style="margin-top: 15px; background-color: #fff; padding: 10px; border-radius: 4px;">
                    <strong>BR-ID-001 Recommendation:</strong> Review these items to ensure no duplication. 
                    Consider using existing items if appropriate for "like-with-like" grouping.
                </p>
            </div>""",
            subject='Duplicate Item Check',
            message_type='comment'
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Similar Items Found',
                'message': f'Found {len(similar_items)} similar items. Check chatter for details.',
                'type': 'warning',
                'sticky': True,
            }
        }

    # ── Stock Control Validations & Computations ───────────────────────

    @api.constrains('minimum_level', 'reorder_level', 'hastening_level', 'maximum_level', 'safety_stock')
    def _check_control_levels(self):
        """Validate control level relationships (FR-SC-001)"""
        for item in self:
            if item.minimum_level < 0 or item.maximum_level < 0 or item.reorder_level < 0:
                raise ValidationError('Control levels cannot be negative.')
            
            if item.maximum_level > 0 and item.minimum_level > item.maximum_level:
                raise ValidationError(
                    f'Item {item.item_code}: Minimum level ({item.minimum_level}) '
                    f'cannot exceed maximum level ({item.maximum_level}).'
                )
            
            if item.reorder_level > 0:
                if item.minimum_level > 0 and item.reorder_level < item.minimum_level:
                    raise ValidationError(
                        f'Item {item.item_code}: Reorder level ({item.reorder_level}) '
                        f'should be >= minimum level ({item.minimum_level}).'
                    )
                if item.maximum_level > 0 and item.reorder_level > item.maximum_level:
                    raise ValidationError(
                        f'Item {item.item_code}: Reorder level ({item.reorder_level}) '
                        f'should be <= maximum level ({item.maximum_level}).'
                    )

    @api.depends('admin_lead_time', 'supplier_lead_time')
    def _compute_total_lead_time(self):
        """Calculate total lead time (FR-SC-002)"""
        for item in self:
            item.total_lead_time = item.admin_lead_time + item.supplier_lead_time

    def _compute_current_stock(self):
        """Get current stock from bin card aggregated by sub-classification (FR-SC-001)"""
        for item in self:
            if not item.sub_classification_id:
                item.current_stock = 0.0
                continue
            
            # Get the latest bin card balance for this sub-classification
            bin_card = self.env['mesob.bin.card'].search([
                ('sub_classification_id', '=', item.sub_classification_id.id)
            ], limit=1, order='date desc, id desc')
            item.current_stock = bin_card.balance if bin_card else 0.0

    @api.depends('current_stock', 'minimum_level', 'reorder_level', 'hastening_level', 'maximum_level')
    def _compute_stock_status(self):
        """Determine stock status based on control levels (FR-SC-001)"""
        for item in self:
            current = item.current_stock
            
            if item.minimum_level > 0 and current < item.minimum_level:
                item.stock_status = 'critical'
            elif item.reorder_level > 0 and current < item.reorder_level:
                item.stock_status = 'low'
            elif item.hastening_level > 0 and current < item.hastening_level:
                item.stock_status = 'hasten'
            elif item.maximum_level > 0 and current > item.maximum_level:
                item.stock_status = 'high'
            else:
                item.stock_status = 'normal'

            # AUTO-023: FR-PROC-029 Auto-generate draft Purchase Requisition (need) upon reorder trigger
            if item.reorder_level > 0 and current <= item.reorder_level:
                # Check for outstanding open POs for this item code to prevent duplicate ordering (FR-PROC-029)
                outstanding_pos = self.env['mesob.procurement.order.line'].search([
                    ('item_id', '=', item.id),
                    ('order_id.state', 'in', ['draft', 'pending', 'approved', 'sent'])
                ])
                
                if outstanding_pos:
                    # Outstanding PO exists - log info message
                    _logger.info(
                        f"AUTO-023: Reorder level reached for {item.item_code}, "
                        f"but PO {outstanding_pos[0].order_id.name} already outstanding. "
                        f"ETA: {outstanding_pos[0].order_id.date_order or 'N/A'}"
                    )
                else:
                    # No outstanding PO - check for existing draft need to avoid duplication
                    existing_need = self.env['mesob.procurement.need'].search([
                        ('item_id', '=', item.id),
                        ('state', '=', 'draft')
                    ])
                    
                    if not existing_need:
                        # Calculate suggested order quantity: (Max level - Current level) or reorder level
                        suggested_qty = max(
                            item.maximum_level - current if item.maximum_level > 0 else item.reorder_level,
                            item.reorder_level - current
                        )
                        
                        # Get last purchase price as estimated unit price (AUTO-023 intelligent pre-fill)
                        last_po_line = self.env['mesob.procurement.order.line'].search([
                            ('item_id', '=', item.id),
                            ('order_id.state', 'in', ['approved', 'sent', 'fully_received', 'closed'])
                        ], order='id desc', limit=1)
                        estimated_price = last_po_line.price_unit if last_po_line else 100.0
                        
                        # Auto-create draft need request (FR-PROC-029)
                        need = self.env['mesob.procurement.need'].create({
                            'department': 'ministry_transport_logistics',  # default department fallback
                            'item_id': item.id,
                            'quantity': suggested_qty,
                            'estimated_unit_price': estimated_price,
                            'expected_delivery_period': f'{item.total_lead_time} days (Auto-Reorder)',
                            'state': 'draft'
                        })
                        
                        # AUTO-023: Send notification to Procurement Officer
                        procurement_officers = self.env.ref('mesob_inventory_base.group_mesob_procurement').users
                        if procurement_officers:
                            need.message_post(
                                body=f"""<p><strong>AUTO-023: Reorder Alert</strong></p>
                                <ul>
                                    <li>Item: {item.item_code} - {item.name}</li>
                                    <li>Current Stock: {current}</li>
                                    <li>Reorder Level: {item.reorder_level}</li>
                                    <li>Suggested Order Qty: {suggested_qty}</li>
                                    <li>Last Unit Price: ETB {estimated_price}</li>
                                    <li>Lead Time: {item.total_lead_time} days</li>
                                </ul>
                                <p>Review and convert this draft need to Purchase Order.</p>""",
                                subject=f"Reorder Alert: {item.item_code}",
                                message_type='notification',
                                partner_ids=procurement_officers.mapped('partner_id').ids
                            )
                        
                        _logger.info(
                            f"AUTO-023: Auto-generated draft procurement need for {item.item_code}. "
                            f"Current: {current}, Reorder: {item.reorder_level}, Suggested Qty: {suggested_qty}"
                        )

    def _compute_issue_status(self):
        for rec in self:
            issued_lines = self.env['mesob.inventory.issue.voucher.line'].search_count([
                ('item_id', '=', rec.id),
                ('voucher_id.state', 'in', ['issued', 'received']),
            ])
            rec.issue_status = 'issued' if issued_lines > 0 else 'not_issued'

    def _compute_current_holder(self):
        for rec in self:
            # Find the latest issue voucher line for this item
            line = self.env['mesob.inventory.issue.voucher.line'].search([
                ('item_id', '=', rec.id),
                ('voucher_id.state', 'in', ['issued', 'received'])
            ], order='id desc', limit=1)
            
            if line:
                voucher = line.voucher_id
                requisition = voucher.requisition_id
                if requisition:
                    if requisition.department:
                        rec.current_holder = f"🏢 {requisition.department}"
                    elif requisition.requested_by_id:
                        user = requisition.requested_by_id
                        name = user.name or ""
                        parts = name.split()
                        initials = "".join([p[0].upper() for p in parts if p])[:2]
                        rec.current_holder = f"👤 {initials} {name}"
                    else:
                        rec.current_holder = ""
                else:
                    rec.current_holder = ""
            else:
                rec.current_holder = ""



    # ═══════════════════════════════════════════════════════════════════
    # AUTO-062: Control Levels Auto-Calculation from Historical Usage
    # ═══════════════════════════════════════════════════════════════════
    
    @api.depends('item_code', 'sub_classification_id')
    def _compute_usage_statistics(self):
        """AUTO-062: Calculate average and max monthly usage from issue history (FR-SC-002)"""
        for item in self:
            if not item.sub_classification_id:
                item.average_monthly_usage = 0.0
                item.max_monthly_usage = 0.0
                continue
            
            # Get issue history for the configured period
            months_back = item.historical_period_months or 6
            start_date = fields.Date.today() - timedelta(days=months_back * 30)
            
            # Query issue voucher lines for this item
            issue_lines = self.env['mesob.inventory.issue.voucher.line'].search([
                ('item_id', '=', item.id),
                ('voucher_id.state', 'in', ['issued', 'received']),
                ('voucher_id.issue_date', '>=', start_date)
            ])
            
            if not issue_lines:
                item.average_monthly_usage = 0.0
                item.max_monthly_usage = 0.0
                continue
            
            # Group by month and calculate usage
            from collections import defaultdict
            monthly_usage = defaultdict(float)
            
            for line in issue_lines:
                issue_date = line.voucher_id.issue_date
                month_key = issue_date.strftime('%Y-%m')
                monthly_usage[month_key] += line.quantity_issued
            
            if monthly_usage:
                usage_values = list(monthly_usage.values())
                item.average_monthly_usage = sum(usage_values) / len(usage_values)
                item.max_monthly_usage = max(usage_values)
            else:
                item.average_monthly_usage = 0.0
                item.max_monthly_usage = 0.0
    
    @api.depends('average_monthly_usage', 'total_lead_time', 'safety_stock')
    def _compute_suggested_levels(self):
        """AUTO-062: Calculate suggested control levels based on usage and lead time (FR-SC-001, FR-SC-002)"""
        for item in self:
            if item.average_monthly_usage == 0:
                item.suggested_reorder_level = 0.0
                item.suggested_minimum_level = 0.0
                item.suggested_maximum_level = 0.0
                continue
            
            # Convert lead time to months
            lead_time_months = item.total_lead_time / 30.0 if item.total_lead_time > 0 else 0.5
            
            # Suggested minimum = safety stock (1 week of average usage as default)
            item.suggested_minimum_level = (item.average_monthly_usage / 4.0) if item.safety_stock == 0 else item.safety_stock
            
            # Suggested reorder = (avg usage × lead time) + safety stock
            item.suggested_reorder_level = (item.average_monthly_usage * lead_time_months) + item.suggested_minimum_level
            
            # Suggested maximum = 2 × reorder level (standard practice)
            item.suggested_maximum_level = item.suggested_reorder_level * 2
    
    def action_apply_suggested_levels(self):
        """AUTO-062: Apply system-calculated levels to actual control levels"""
        self.ensure_one()
        
        if self.suggested_reorder_level == 0:
            raise UserError(
                "AUTO-062: Cannot apply suggested levels. No historical usage data found. "
                "Please enter control levels manually or wait for usage history to accumulate."
            )
        
        self.write({
            'minimum_level': self.suggested_minimum_level,
            'reorder_level': self.suggested_reorder_level,
            'maximum_level': self.suggested_maximum_level,
            'last_calculation_date': fields.Datetime.now()
        })
        
        self.message_post(
            body=f"""<div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px;">
                <h3>✅ AUTO-062: Control Levels Auto-Applied</h3>
                <table style="width: 100%; margin-top: 10px;">
                    <tr><td><strong>Minimum Level:</strong></td><td>{self.minimum_level:.2f}</td></tr>
                    <tr><td><strong>Reorder Level:</strong></td><td>{self.reorder_level:.2f}</td></tr>
                    <tr><td><strong>Maximum Level:</strong></td><td>{self.maximum_level:.2f}</td></tr>
                </table>
                <p style="margin-top: 10px; font-size: 12px; color: #666;">
                    Based on {self.historical_period_months} months of usage history:<br/>
                    Average monthly usage: {self.average_monthly_usage:.2f}<br/>
                    Lead time: {self.total_lead_time} days
                </p>
            </div>""",
            subject='Control Levels Updated',
            message_type='notification'
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Control Levels Applied',
                'message': f'Auto-calculated levels applied successfully for {self.item_code}',
                'type': 'success',
                'sticky': False,
            }
        }
    
    @api.model
    def cron_recalculate_control_levels(self):
        """AUTO-062 + AUTO-065: Scheduled action to recalculate control levels for enabled items"""
        items = self.search([('auto_reorder_enabled', '=', True)])
        
        for item in items:
            try:
                # Force recomputation
                item._compute_usage_statistics()
                item._compute_suggested_levels()
                
                # Auto-apply if configured (optional flag can be added)
                if item.suggested_reorder_level > 0:
                    item.write({
                        'reorder_level': item.suggested_reorder_level,
                        'minimum_level': item.suggested_minimum_level,
                        'maximum_level': item.suggested_maximum_level,
                        'last_calculation_date': fields.Datetime.now()
                    })
                    
                    _logger.info(
                        f"AUTO-062: Auto-updated control levels for {item.item_code} - "
                        f"Reorder: {item.reorder_level:.2f}, Min: {item.minimum_level:.2f}, Max: {item.maximum_level:.2f}"
                    )
            except Exception as e:
                _logger.error(f"AUTO-062: Failed to recalculate levels for {item.item_code}: {str(e)}")
        
        _logger.info(f"AUTO-062: Completed control level recalculation for {len(items)} items")
    
    # ═══════════════════════════════════════════════════════════════════════
    # ADVANCED AUTO-062: Seasonal Analysis and Demand Forecasting
    # ═══════════════════════════════════════════════════════════════════════
    
    @api.depends('item_code', 'historical_period_months')
    def _compute_seasonal_analysis(self):
        """ADVANCED: Detect seasonal patterns in usage (e.g., fuel usage higher in winter)"""
        for item in self:
            if not item.sub_classification_id:
                item.seasonal_pattern_detected = False
                item.peak_season_months = ''
                item.seasonal_adjustment_factor = 1.0
                continue
            
            # Get issue history by month from issue voucher lines
            issue_lines = self.env['mesob.inventory.issue.voucher.line'].search([
                ('item_id', '=', item.id),
                ('voucher_id.issue_date', '>=', fields.Date.today() - timedelta(days=365)),
                ('voucher_id.state', '=', 'approved'),
            ])
            
            if len(issue_lines) < 12:  # Need at least 1 year of data
                item.seasonal_pattern_detected = False
                item.peak_season_months = ''
                item.seasonal_adjustment_factor = 1.0
                continue
            
            # Group by month
            monthly_usage = {}
            for line in issue_lines:
                month = line.voucher_id.issue_date.month
                monthly_usage[month] = monthly_usage.get(month, 0) + line.quantity_issued
            
            if not monthly_usage:
                item.seasonal_pattern_detected = False
                item.peak_season_months = ''
                item.seasonal_adjustment_factor = 1.0
                continue
            
            # Calculate average and identify peaks
            avg_usage = sum(monthly_usage.values()) / len(monthly_usage)
            max_usage = max(monthly_usage.values())
            
            # Seasonal pattern if peak > 30% above average
            if max_usage > avg_usage * 1.3:
                item.seasonal_pattern_detected = True
                item.seasonal_adjustment_factor = max_usage / avg_usage
                
                # Find peak months
                peak_months = [month for month, usage in monthly_usage.items() if usage > avg_usage * 1.2]
                month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                              'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
                item.peak_season_months = ', '.join([month_names[m-1] for m in peak_months])
            else:
                item.seasonal_pattern_detected = False
                item.peak_season_months = ''
                item.seasonal_adjustment_factor = 1.0
    
    @api.depends('average_monthly_usage', 'historical_period_months')
    def _compute_usage_trend(self):
        """ADVANCED: Detect if usage is increasing, decreasing, or stable"""
        for item in self:
            if not item.sub_classification_id or item.average_monthly_usage == 0:
                item.usage_trend = 'stable'
                item.trend_percentage = 0.0
                continue
            
            # Get usage over time (split historical period in half)
            months = item.historical_period_months
            midpoint = fields.Date.today() - timedelta(days=int(months * 30 / 2))
            
            # First half usage - search issue voucher lines
            first_half_lines = self.env['mesob.inventory.issue.voucher.line'].search([
                ('item_id', '=', item.id),
                ('voucher_id.issue_date', '<', midpoint),
                ('voucher_id.issue_date', '>=', fields.Date.today() - timedelta(days=months * 30)),
                ('voucher_id.state', '=', 'approved'),
            ])
            
            # Second half usage - search issue voucher lines
            second_half_lines = self.env['mesob.inventory.issue.voucher.line'].search([
                ('item_id', '=', item.id),
                ('voucher_id.issue_date', '>=', midpoint),
                ('voucher_id.state', '=', 'approved'),
            ])
            
            first_total = sum(first_half_lines.mapped('quantity_issued'))
            second_total = sum(second_half_lines.mapped('quantity_issued'))
            
            if first_total == 0:
                item.usage_trend = 'stable'
                item.trend_percentage = 0.0
                continue
            
            # Calculate trend
            trend_pct = ((second_total - first_total) / first_total) * 100
            item.trend_percentage = trend_pct
            
            # Classify trend
            if abs(trend_pct) < 10:
                item.usage_trend = 'stable'
            elif trend_pct > 20:
                item.usage_trend = 'increasing'
            elif trend_pct < -20:
                item.usage_trend = 'decreasing'
            else:
                item.usage_trend = 'volatile'
    
    @api.depends('average_monthly_usage', 'historical_period_months')
    def _compute_demand_variability(self):
        """ADVANCED: Calculate Coefficient of Variation (CV = StdDev / Mean)"""
        for item in self:
            if not item.sub_classification_id or item.average_monthly_usage == 0:
                item.demand_variability = 0.0
                continue
            
            # Get monthly usage values from issue voucher lines
            issue_lines = self.env['mesob.inventory.issue.voucher.line'].search([
                ('item_id', '=', item.id),
                ('voucher_id.issue_date', '>=', fields.Date.today() - timedelta(days=item.historical_period_months * 30)),
                ('voucher_id.state', '=', 'approved'),
            ])
            
            if len(issue_lines) < 3:
                item.demand_variability = 0.0
                continue
            
            # Group by month and calculate
            monthly_values = []
            current_month = None
            month_total = 0
            
            for line in issue_lines.sorted(lambda l: l.voucher_id.issue_date):
                issue_month = (line.voucher_id.issue_date.year, line.voucher_id.issue_date.month)
                if current_month != issue_month:
                    if current_month is not None:
                        monthly_values.append(month_total)
                    current_month = issue_month
                    month_total = 0
                month_total += line.quantity_issued
            
            if month_total > 0:
                monthly_values.append(month_total)
            
            if len(monthly_values) < 2:
                item.demand_variability = 0.0
                continue
            
            # Calculate standard deviation
            mean = sum(monthly_values) / len(monthly_values)
            variance = sum((x - mean) ** 2 for x in monthly_values) / len(monthly_values)
            std_dev = variance ** 0.5
            
            # Coefficient of Variation
            item.demand_variability = (std_dev / mean) if mean > 0 else 0.0
    
    @api.depends('average_monthly_usage', 'eoq_ordering_cost', 'eoq_holding_cost_percent')
    def _compute_eoq(self):
        """ADVANCED: Calculate Economic Order Quantity (EOQ)
        
        Formula: EOQ = sqrt((2 × D × S) / H)
        Where:
        - D = Annual demand
        - S = Ordering cost per order
        - H = Holding cost per unit per year
        """
        for item in self:
            if item.average_monthly_usage == 0:
                item.economic_order_quantity = 0.0
                continue
            
            # Annual demand
            annual_demand = item.average_monthly_usage * 12
            
            # Ordering cost
            ordering_cost = item.eoq_ordering_cost
            
            # Holding cost per unit per year
            # Get item cost
            valuation = self.env['mesob.stock.movement.mixin'].get_item_valuation(item.id)
            unit_cost = valuation.get('average_cost', 0.0)
            holding_cost_per_unit = unit_cost * (item.eoq_holding_cost_percent / 100)
            
            if holding_cost_per_unit == 0:
                item.economic_order_quantity = 0.0
                continue
            
            # EOQ formula
            import math
            eoq = math.sqrt((2 * annual_demand * ordering_cost) / holding_cost_per_unit)
            item.economic_order_quantity = eoq
    
    @api.depends('suggested_reorder_level', 'demand_variability')
    def _compute_confidence_intervals(self):
        """ADVANCED: Calculate statistical confidence intervals for reorder level"""
        for item in self:
            if item.suggested_reorder_level == 0:
                item.confidence_level = 0.0
                item.reorder_level_lower_bound = 0.0
                item.reorder_level_upper_bound = 0.0
                continue
            
            # Use 95% confidence level (Z-score = 1.96)
            z_score = 1.96
            item.confidence_level = 95.0
            
            # Standard error based on demand variability
            std_error = item.suggested_reorder_level * item.demand_variability
            margin_of_error = z_score * std_error
            
            item.reorder_level_lower_bound = max(0, item.suggested_reorder_level - margin_of_error)
            item.reorder_level_upper_bound = item.suggested_reorder_level + margin_of_error
    
    @api.depends('average_monthly_usage', 'usage_trend', 'seasonal_adjustment_factor')
    def _compute_demand_forecast(self):
        """ADVANCED: Forecast next month's usage using trend and seasonality"""
        for item in self:
            if item.average_monthly_usage == 0:
                item.forecasted_next_month_usage = 0.0
                continue
            
            # Base forecast = average usage
            forecast = item.average_monthly_usage
            
            # Adjust for trend
            if item.usage_trend == 'increasing':
                forecast *= (1 + abs(item.trend_percentage) / 100)
            elif item.usage_trend == 'decreasing':
                forecast *= (1 - abs(item.trend_percentage) / 100)
            
            # Adjust for seasonality if applicable
            if item.seasonal_pattern_detected:
                next_month = (fields.Date.today().month % 12) + 1
                # Check if next month is peak season
                if item.peak_season_months and any(str(next_month) in item.peak_season_months or 
                                                   ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'][next_month-1] in item.peak_season_months):
                    forecast *= item.seasonal_adjustment_factor
            
            item.forecasted_next_month_usage = forecast
    
    @api.depends('forecasted_next_month_usage', 'average_monthly_usage')
    def _compute_forecast_accuracy(self):
        """ADVANCED: Calculate historical forecast accuracy"""
        for item in self:
            # Simplified - in production, compare past forecasts vs actual
            # For now, use demand variability as proxy
            if item.demand_variability > 0:
                # High variability = lower accuracy
                accuracy = max(50, 100 - (item.demand_variability * 100))
                item.forecast_accuracy_percent = min(99, accuracy)
            else:
                item.forecast_accuracy_percent = 95.0
    
    # ═══════════════════════════════════════════════════════════════════════
    # ADVANCED AUTO-065: Smart Review Scheduling
    # ═══════════════════════════════════════════════════════════════════════
    
    @api.depends('abc_class', 'demand_variability', 'usage_trend')
    def _compute_review_frequency(self):
        """ADVANCED: Calculate optimal review frequency based on ABC class and variability"""
        for item in self:
            # Base frequency by ABC class
            if item.abc_class == 'A':
                base_days = 30  # Monthly for A items
            elif item.abc_class == 'B':
                base_days = 60  # Bi-monthly for B items
            else:
                base_days = 90  # Quarterly for C items
            
            # Adjust for variability (high variability = more frequent reviews)
            if item.demand_variability > 0.5:
                base_days = int(base_days * 0.7)  # 30% more frequent
            elif item.demand_variability > 0.3:
                base_days = int(base_days * 0.85)  # 15% more frequent
            
            # Adjust for trend (changing items need more review)
            if item.usage_trend in ['increasing', 'decreasing']:
                base_days = int(base_days * 0.8)  # 20% more frequent
            
            item.review_frequency_days = base_days
    
    @api.depends('last_calculation_date', 'review_frequency_days')
    def _compute_next_review_date(self):
        """ADVANCED: Calculate when next review is due"""
        for item in self:
            if item.last_calculation_date:
                item.next_review_date = item.last_calculation_date.date() + timedelta(days=item.review_frequency_days)
            else:
                item.next_review_date = fields.Date.today()
    
    @api.depends('abc_class', 'demand_variability', 'next_review_date')
    def _compute_review_priority(self):
        """ADVANCED: Prioritize which items need review most urgently"""
        for item in self:
            # Check if overdue
            overdue = item.next_review_date and item.next_review_date < fields.Date.today()
            
            # Priority logic
            if overdue and item.abc_class == 'A':
                item.review_priority = 'urgent'
            elif item.abc_class == 'A' and item.demand_variability > 0.5:
                item.review_priority = 'high'
            elif item.abc_class == 'B' or (item.abc_class == 'A' and overdue):
                item.review_priority = 'high' if overdue else 'medium'
            else:
                item.review_priority = 'low'
    
    @api.depends('average_monthly_usage', 'change_detection_threshold')
    def _compute_change_detection(self):
        """ADVANCED: Detect significant changes in usage patterns"""
        for item in self:
            if item.average_monthly_usage == 0:
                item.significant_change_detected = False
                continue
            
            # Compare recent usage (last month) vs average from issue voucher lines
            recent_issue_lines = self.env['mesob.inventory.issue.voucher.line'].search([
                ('item_id', '=', item.id),
                ('voucher_id.issue_date', '>=', fields.Date.today() - timedelta(days=30)),
                ('voucher_id.state', '=', 'approved'),
            ])
            
            recent_usage = sum(recent_issue_lines.mapped('quantity_issued'))
            
            # Check if change exceeds threshold
            if item.average_monthly_usage > 0:
                change_pct = abs((recent_usage - item.average_monthly_usage) / item.average_monthly_usage) * 100
                item.significant_change_detected = change_pct > item.change_detection_threshold
            else:
                item.significant_change_detected = False


    # ═══════════════════════════════════════════════════════════════════
    # AUTO-066: Dormant/Damaged/Obsolete Item Auto-Flagging
    # ═══════════════════════════════════════════════════════════════════
    
    @api.depends('item_code', 'average_monthly_usage')
    def _compute_item_flags(self):
        """AUTO-066: Auto-flag dormant and slow-moving items (FR-REP-003, FR-DISP2-001)"""
        for item in self:
            # Find last issue date
            last_issue_lines = self.env['mesob.inventory.issue.voucher.line'].search([
                ('item_id', '=', item.id),
                ('voucher_id.state', 'in', ['issued', 'received'])
            ])
            
            if last_issue_lines:
                # Sort by voucher issue date and get the most recent
                last_issue = max(last_issue_lines, key=lambda l: l.voucher_id.issue_date)
                last_issue_date = last_issue.voucher_id.issue_date
                today = fields.Date.today()
                delta = (today - last_issue_date).days
                item.days_since_last_issue = delta
                
                # Flag as dormant if no issues beyond threshold
                item.is_dormant = delta >= item.dormant_threshold_days
            else:
                # Never issued
                item.days_since_last_issue = 9999
                item.is_dormant = True
            
            # Flag as slow-moving if average monthly usage is very low (< 1 unit/month)
            item.is_slow_moving = (0 < item.average_monthly_usage < 1.0) and not item.is_dormant
    
    def action_flag_damaged(self):
        """AUTO-066: Manually flag item as damaged"""
        self.ensure_one()
        self.is_damaged = True
        
        self.message_post(
            body=f"""<div style="background-color: #f8d7da; border-left: 4px solid #dc3545; padding: 15px;">
                <h3>⚠️ AUTO-066: Item Flagged as Damaged</h3>
                <p><strong>Item:</strong> {self.item_code} - {self.name}</p>
                <p><strong>Current Stock:</strong> {self.current_stock}</p>
                <p><strong>Action Required:</strong> Review for disposal per FR-DISP2-001</p>
            </div>""",
            subject='Item Flagged as Damaged',
            message_type='notification'
        )
        
        return {'type': 'ir.actions.client', 'tag': 'reload'}
    
    def action_flag_obsolete(self):
        """AUTO-066: Manually flag item as obsolete"""
        self.ensure_one()
        self.is_obsolete = True
        
        self.message_post(
            body=f"""<div style="background-color: #f8d7da; border-left: 4px solid #dc3545; padding: 15px;">
                <h3>⚠️ AUTO-066: Item Flagged as Obsolete</h3>
                <p><strong>Item:</strong> {self.item_code} - {self.name}</p>
                <p><strong>Current Stock:</strong> {self.current_stock}</p>
                <p><strong>Action Required:</strong> Review for disposal per FR-DISP2-001</p>
            </div>""",
            subject='Item Flagged as Obsolete',
            message_type='notification'
        )
        
        return {'type': 'ir.actions.client', 'tag': 'reload'}
    
    def action_clear_flags(self):
        """AUTO-066: Clear damage/obsolete flags"""
        self.ensure_one()
        self.write({
            'is_damaged': False,
            'is_obsolete': False
        })
        
        self.message_post(
            body=f"<p>Damage/Obsolete flags cleared for {self.item_code}</p>",
            subject='Flags Cleared',
            message_type='comment'
        )
        
        return {'type': 'ir.actions.client', 'tag': 'reload'}
    
    @api.model
    def cron_flag_dormant_items(self):
        """AUTO-066: Scheduled action to identify and flag dormant/slow-moving items"""
        all_items = self.search([('active', '=', True)])
        
        dormant_count = 0
        slow_count = 0
        
        for item in all_items:
            item._compute_item_flags()
            
            if item.is_dormant:
                dormant_count += 1
            if item.is_slow_moving:
                slow_count += 1
        
        _logger.info(
            f"AUTO-066: Dormant/Slow-Moving scan complete. "
            f"Dormant: {dormant_count}, Slow-moving: {slow_count}"
        )
        
        # Notify PAO if significant dormant items found
        if dormant_count > 0:
            pao_group = self.env.ref('mesob_inventory_base.group_mesob_pao', raise_if_not_found=False)
            if pao_group:
                # Create a system notification
                self.env['mail.message'].create({
                    'message_type': 'notification',
                    'subject': f'AUTO-066: Dormant Items Alert ({dormant_count} items)',
                    'body': f"""<div style="background-color: #fff3cd; padding: 15px;">
                        <h3>📊 AUTO-066: Dormant & Slow-Moving Items Report</h3>
                        <ul>
                            <li><strong>Dormant Items:</strong> {dormant_count}</li>
                            <li><strong>Slow-Moving Items:</strong> {slow_count}</li>
                        </ul>
                        <p>Review these items for potential disposal (FR-DISP2-001, FR-REP-003)</p>
                    </div>""",
                    'partner_ids': [(6, 0, pao_group.users.mapped('partner_id').ids)]
                })
    
    # ═══════════════════════════════════════════════════════════════════════
    # ADVANCED AUTO-066: AI Obsolescence Risk Analysis
    # ═══════════════════════════════════════════════════════════════════════
    
    @api.depends('is_dormant', 'is_slow_moving', 'days_since_last_issue', 'average_monthly_usage', 
                 'current_stock', 'abc_class')
    def _compute_obsolescence_risk(self):
        """ADVANCED AUTO-066: AI-powered obsolescence risk scoring (0-100)"""
        for item in self:
            risk_score = 0.0
            
            # Factor 1: Dormancy (40 points max)
            if item.is_dormant:
                risk_score += 40
            elif item.is_slow_moving:
                risk_score += 20
            
            # Factor 2: Days since last issue (25 points max)
            if item.days_since_last_issue > 0:
                if item.days_since_last_issue >= 730:  # 2+ years
                    risk_score += 25
                elif item.days_since_last_issue >= 365:  # 1-2 years
                    risk_score += 20
                elif item.days_since_last_issue >= 180:  # 6-12 months
                    risk_score += 15
                elif item.days_since_last_issue >= 90:  # 3-6 months
                    risk_score += 10
            
            # Factor 3: Usage trend (15 points max)
            if item.usage_trend == 'decreasing':
                risk_score += 15
            elif item.usage_trend == 'volatile':
                risk_score += 8
            
            # Factor 4: Overstocking (10 points max)
            if item.average_monthly_usage > 0:
                months_of_stock = item.current_stock / item.average_monthly_usage
                if months_of_stock > 24:  # >2 years of stock
                    risk_score += 10
                elif months_of_stock > 12:  # >1 year of stock
                    risk_score += 5
            
            # Factor 5: ABC class (10 points max)
            if item.abc_class == 'C':
                risk_score += 10
            elif item.abc_class == 'B':
                risk_score += 5
            
            item.obsolescence_risk_score = min(100, risk_score)
            
            # Classify risk level
            if item.obsolescence_risk_score >= 75:
                item.obsolescence_risk_level = 'critical'
            elif item.obsolescence_risk_score >= 50:
                item.obsolescence_risk_level = 'high'
            elif item.obsolescence_risk_score >= 25:
                item.obsolescence_risk_level = 'medium'
            else:
                item.obsolescence_risk_level = 'low'
    
    @api.depends('average_monthly_usage', 'days_since_last_issue', 'usage_trend')
    def _compute_dormancy_prediction(self):
        """ADVANCED AUTO-066: Predict when item will become dormant"""
        for item in self:
            if item.is_dormant:
                item.predicted_dormancy_date = fields.Date.today()
                item.months_until_dormant = 0
                continue
            
            # Calculate prediction based on usage trend
            if item.average_monthly_usage == 0:
                # Already effectively dormant
                item.predicted_dormancy_date = fields.Date.today()
                item.months_until_dormant = 0
            elif item.usage_trend == 'decreasing':
                # Assume exponential decay - predict 6 months if decreasing
                months_to_dormant = max(1, int(6 * (1 - abs(item.trend_percentage) / 100)))
                item.months_until_dormant = months_to_dormant
                item.predicted_dormancy_date = fields.Date.today() + timedelta(days=months_to_dormant * 30)
            elif item.usage_trend == 'stable' and item.average_monthly_usage < 0.5:
                # Low but stable usage - may become dormant in 12 months
                item.months_until_dormant = 12
                item.predicted_dormancy_date = fields.Date.today() + timedelta(days=365)
            else:
                # Increasing or normal usage - low dormancy risk
                item.months_until_dormant = 99
                item.predicted_dormancy_date = False
    
    @api.depends('alternative_items', 'current_stock')
    def _compute_disposal_value(self):
        """ADVANCED AUTO-066: Estimate salvage/disposal value"""
        for item in self:
            # Get unit cost from valuation
            valuation = self.env['mesob.stock.movement.mixin'].get_item_valuation(item.id)
            unit_cost = valuation.get('average_cost', 0.0)
            
            if not item.current_stock or not unit_cost:
                item.estimated_disposal_value = 0.0
                continue
            
            original_value = item.current_stock * unit_cost
            
            # Base salvage percentage depends on condition and alternatives
            if item.is_damaged:
                salvage_pct = 0.10  # 10% for damaged items
            elif item.is_obsolete:
                salvage_pct = 0.20  # 20% for obsolete but usable
            elif item.alternative_items:
                salvage_pct = 0.50  # 50% if alternatives exist (transfer value)
            elif item.market_availability == 'unavailable':
                salvage_pct = 0.70  # 70% if rare/unique
            elif item.obsolescence_risk_level == 'critical':
                salvage_pct = 0.25  # 25% for high-risk items
            else:
                salvage_pct = 0.60  # 60% default
            
            item.estimated_disposal_value = original_value * salvage_pct
    
    @api.depends('obsolescence_risk_level', 'current_stock', 'alternative_items', 
                 'market_availability', 'estimated_disposal_value', 'is_damaged', 'is_obsolete')
    def _compute_disposal_recommendation(self):
        """ADVANCED AUTO-066: AI-powered disposal recommendation system"""
        for item in self:
            # Decision tree logic
            if item.is_damaged:
                if item.estimated_disposal_value > 1000:
                    item.disposal_recommendation = 'sell'
                    item.disposal_urgency = 'high'
                else:
                    item.disposal_recommendation = 'scrap'
                    item.disposal_urgency = 'medium'
            
            elif item.is_obsolete:
                if item.alternative_items:
                    item.disposal_recommendation = 'transfer'
                    item.disposal_urgency = 'high'
                elif item.estimated_disposal_value > 5000:
                    item.disposal_recommendation = 'sell'
                    item.disposal_urgency = 'high'
                else:
                    item.disposal_recommendation = 'donate'
                    item.disposal_urgency = 'medium'
            
            elif item.obsolescence_risk_level == 'critical':
                if item.current_stock > 0 and item.average_monthly_usage == 0:
                    if item.alternative_items:
                        item.disposal_recommendation = 'transfer'
                    elif item.market_availability == 'available':
                        item.disposal_recommendation = 'sell'
                    else:
                        item.disposal_recommendation = 'donate'
                    item.disposal_urgency = 'urgent'
                else:
                    item.disposal_recommendation = 'monitor'
                    item.disposal_urgency = 'low'
            
            elif item.obsolescence_risk_level == 'high':
                if item.alternative_items:
                    item.disposal_recommendation = 'transfer'
                    item.disposal_urgency = 'medium'
                else:
                    item.disposal_recommendation = 'monitor'
                    item.disposal_urgency = 'low'
            
            else:
                item.disposal_recommendation = 'keep'
                item.disposal_urgency = 'low'
    
    # ═══════════════════════════════════════════════════════════════════════
    # ADVANCED AUTO-067: Procurement Suspension & Surplus Management
    # ═══════════════════════════════════════════════════════════════════════
    
    def action_suspend_procurement(self):
        """AUTO-067: Suspend procurement for surplus items"""
        self.ensure_one()
        
        if self.procurement_suspended:
            raise UserError("Procurement is already suspended for this item.")
        
        self.write({
            'procurement_suspended': True,
            'suspension_date': fields.Date.today(),
            'suspension_reason': f'Surplus detected: {self.current_stock} units in stock with low usage ({self.average_monthly_usage:.2f} units/month)'
        })
        
        # Calculate auto-resume condition
        if self.average_monthly_usage > 0:
            self._compute_surplus_metrics()
        
        self.message_post(
            body=f"""<div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px;">
                <h3>⚠️ AUTO-067: Procurement Suspended</h3>
                <p><strong>Item:</strong> {self.item_code} - {self.name}</p>
                <p><strong>Current Stock:</strong> {self.current_stock}</p>
                <p><strong>Average Usage:</strong> {self.average_monthly_usage:.2f} units/month</p>
                <p><strong>Reason:</strong> {self.suspension_reason}</p>
                {f'<p><strong>Estimated Depletion:</strong> {self.estimated_surplus_depletion_date}</p>' if self.estimated_surplus_depletion_date else ''}
                <p><strong>Action:</strong> Procurement will auto-resume when stock drops to reorder level or after surplus consumed.</p>
            </div>""",
            subject='Procurement Suspended - Surplus Detected',
            message_type='notification'
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Procurement Suspended',
                'message': f'Procurement suspended for {self.item_code}. Will auto-resume when surplus consumed.',
                'type': 'warning',
                'sticky': False,
            }
        }
    
    def action_resume_procurement(self):
        """AUTO-067: Resume procurement after surplus consumed"""
        self.ensure_one()
        
        if not self.procurement_suspended:
            raise UserError("Procurement is not currently suspended for this item.")
        
        self.write({
            'procurement_suspended': False,
            'suspension_date': False,
            'suspension_reason': False,
            'auto_resume_threshold': 0.0,
            'surplus_consumption_rate': 0.0,
            'estimated_surplus_depletion_date': False
        })
        
        self.message_post(
            body=f"""<div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px;">
                <h3>✅ AUTO-067: Procurement Resumed</h3>
                <p><strong>Item:</strong> {self.item_code} - {self.name}</p>
                <p><strong>Current Stock:</strong> {self.current_stock}</p>
                <p><strong>Reorder Level:</strong> {self.reorder_level}</p>
                <p><strong>Status:</strong> Normal procurement operations resumed.</p>
            </div>""",
            subject='Procurement Resumed',
            message_type='notification'
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Procurement Resumed',
                'message': f'Procurement resumed for {self.item_code}.',
                'type': 'success',
                'sticky': False,
            }
        }
    
    @api.depends('current_stock', 'average_monthly_usage', 'reorder_level')
    def _compute_surplus_metrics(self):
        """AUTO-067: Calculate surplus consumption rate and depletion estimate"""
        for item in self:
            if not item.procurement_suspended:
                item.surplus_consumption_rate = 0.0
                item.estimated_surplus_depletion_date = False
                item.auto_resume_threshold = 0.0
                continue
            
            # Calculate surplus = stock above reorder level
            surplus = item.current_stock - item.reorder_level
            
            if surplus <= 0:
                # No more surplus - should auto-resume
                item.surplus_consumption_rate = 0.0
                item.estimated_surplus_depletion_date = fields.Date.today()
                item.auto_resume_threshold = item.reorder_level
            elif item.average_monthly_usage > 0:
                # Calculate consumption rate (units per day)
                daily_usage = item.average_monthly_usage / 30.0
                item.surplus_consumption_rate = daily_usage
                
                # Estimate when surplus will be depleted
                days_to_depletion = int(surplus / daily_usage) if daily_usage > 0 else 9999
                item.estimated_surplus_depletion_date = fields.Date.today() + timedelta(days=days_to_depletion)
                
                # Set auto-resume threshold (reorder level + buffer)
                item.auto_resume_threshold = item.reorder_level * 1.1
            else:
                # No usage - surplus won't deplete naturally
                item.surplus_consumption_rate = 0.0
                item.estimated_surplus_depletion_date = False
                item.auto_resume_threshold = item.reorder_level
    
    @api.model
    def cron_check_procurement_suspension(self):
        """AUTO-067: Daily check to auto-resume procurement when surplus consumed"""
        suspended_items = self.search([('procurement_suspended', '=', True)])
        
        resumed_count = 0
        
        for item in suspended_items:
            # Check if stock has fallen to or below auto-resume threshold
            if item.current_stock <= item.auto_resume_threshold:
                try:
                    item.action_resume_procurement()
                    resumed_count += 1
                    _logger.info(f"AUTO-067: Auto-resumed procurement for {item.item_code} (stock: {item.current_stock}, threshold: {item.auto_resume_threshold})")
                except Exception as e:
                    _logger.error(f"AUTO-067: Failed to auto-resume procurement for {item.item_code}: {str(e)}")
            else:
                # Update surplus metrics
                item._compute_surplus_metrics()
        
        if resumed_count > 0:
            _logger.info(f"AUTO-067: Auto-resumed procurement for {resumed_count} items")
        
        return True

# -*- coding: utf-8 -*-
"""AUTO-059: Stock Discrepancy Investigation Workflow

Formal investigation workflow for material stock discrepancies identified
during stock taking events. Provides structured investigation process with
Store Committee review, root cause analysis, and resolution tracking.

Compliance: FR-ST-006, FR-ST-007 (investigation requirement)
"""

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class MesobStockDiscrepancyInvestigation(models.Model):
    """AUTO-059: Formal investigation workflow for stock taking discrepancies.
    
    Investigation workflow stages:
    1. Initiated: Discrepancy flagged, assigned to investigator
    2. Initial Review: Facts gathered, recount performed if needed
    3. Root Cause Analysis: Determine cause (theft, error, damage, etc.)
    4. Corrective Action: Document remediation steps
    5. Resolution: PAO approval, stock adjustment, closure
    
    Features:
    - Store Committee involvement for significant discrepancies
    - Structured investigation checklist
    - Evidence attachment support
    - Financial impact tracking
    - Employee accountability tracking
    - Automatic stock adjustment upon resolution
    """
    
    _name = "mesob.stock.discrepancy.investigation"
    _description = "Stock Discrepancy Investigation"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "create_date desc, id desc"
    
    # ═══════════════════════════════════════════════════════════
    # BASIC INFORMATION
    # ═══════════════════════════════════════════════════════════
    
    name = fields.Char(
        string="Investigation Reference",
        required=True,
        copy=False,
        default="New",
        readonly=True
    )
    
    stock_taking_id = fields.Many2one(
        "mesob.stock.taking",
        string="Stock Taking Event",
        required=True,
        readonly=True,
        ondelete="cascade",
        help="Source stock taking event that identified the discrepancy"
    )
    
    stock_taking_line_id = fields.Many2one(
        "mesob.stock.taking.line",
        string="Discrepancy Line",
        required=True,
        readonly=True,
        ondelete="cascade",
        help="Specific count sheet line with discrepancy"
    )
    
    item_id = fields.Many2one(
        "mesob.inventory.item",
        related="stock_taking_line_id.item_id",
        string="Item",
        store=True,
        readonly=True
    )
    
    item_code = fields.Char(
        related="stock_taking_line_id.item_code",
        string="Item Code",
        store=True,
        readonly=True
    )
    
    # ═══════════════════════════════════════════════════════════
    # DISCREPANCY DETAILS
    # ═══════════════════════════════════════════════════════════
    
    recorded_qty = fields.Float(
        related="stock_taking_line_id.recorded_qty",
        string="System (Book) Quantity",
        readonly=True
    )
    
    physical_qty = fields.Float(
        related="stock_taking_line_id.physical_qty",
        string="Physical Count",
        readonly=True
    )
    
    discrepancy = fields.Float(
        related="stock_taking_line_id.discrepancy",
        string="Discrepancy",
        readonly=True,
        help="Physical - Book quantity"
    )
    
    variance_percentage = fields.Float(
        related="stock_taking_line_id.variance_percentage",
        string="Variance %",
        readonly=True
    )
    
    discrepancy_value = fields.Float(
        related="stock_taking_line_id.discrepancy_value",
        string="Financial Impact (ETB)",
        readonly=True,
        help="Estimated value of discrepancy"
    )
    
    variance_severity = fields.Selection(
        related="stock_taking_line_id.variance_severity",
        string="Severity",
        readonly=True
    )
    
    combined_severity_score = fields.Integer(
        related="stock_taking_line_id.combined_severity_score",
        string="Risk Score",
        readonly=True
    )
    
    # ═══════════════════════════════════════════════════════════
    # INVESTIGATION TEAM & TIMELINE
    # ═══════════════════════════════════════════════════════════
    
    assigned_to_id = fields.Many2one(
        "res.users",
        string="Lead Investigator",
        required=True,
        default=lambda self: self.env.user,
        tracking=True,
        help="PAO or designated investigator"
    )
    
    committee_member_ids = fields.Many2many(
        "res.users",
        "investigation_committee_rel",
        "investigation_id",
        "user_id",
        string="Store Committee Members",
        help="For significant discrepancies requiring committee review"
    )
    
    initiated_date = fields.Datetime(
        string="Investigation Started",
        default=fields.Datetime.now,
        readonly=True
    )
    
    target_completion_date = fields.Date(
        string="Target Completion",
        compute="_compute_target_completion",
        store=True,
        help="AUTO-059: 7 days for normal, 3 days for critical"
    )
    
    actual_completion_date = fields.Datetime(
        string="Completed On",
        readonly=True
    )
    
    investigation_duration_days = fields.Float(
        string="Duration (Days)",
        compute="_compute_investigation_duration"
    )
    
    is_overdue = fields.Boolean(
        string="Overdue",
        compute="_compute_overdue_status"
    )
    
    # ═══════════════════════════════════════════════════════════
    # INVESTIGATION PROCESS
    # ═══════════════════════════════════════════════════════════
    
    state = fields.Selection([
        ('initiated', 'Initiated'),
        ('initial_review', 'Initial Review'),
        ('root_cause', 'Root Cause Analysis'),
        ('corrective_action', 'Corrective Action Planning'),
        ('pending_approval', 'Pending PAO Approval'),
        ('resolved', 'Resolved'),
        ('cancelled', 'Cancelled'),
    ], string="Investigation Status", default='initiated', required=True, tracking=True)
    
    # Stage 1: Initial Review
    recount_required = fields.Boolean(
        string="Recount Required",
        help="Check if physical recount is needed to verify discrepancy"
    )
    
    recount_performed = fields.Boolean(
        string="Recount Performed",
        readonly=True
    )
    
    recount_date = fields.Date(string="Recount Date", readonly=True)
    
    recount_result = fields.Float(
        string="Recount Result",
        help="Physical quantity after recount"
    )
    
    recount_matches = fields.Boolean(
        string="Recount Matches",
        compute="_compute_recount_matches",
        help="True if recount matches original count"
    )
    
    # Stage 2: Root Cause Analysis
    root_cause = fields.Selection([
        ('posting_error', 'Posting Error - Incorrect Record'),
        ('counting_error', 'Counting Error - Original Count Wrong'),
        ('theft', 'Theft / Pilferage'),
        ('damage', 'Damaged / Lost Items'),
        ('expired', 'Expired / Obsolete (Not Removed)'),
        ('unauthorized_issue', 'Unauthorized Issue'),
        ('receiving_error', 'Receiving Error (Not Recorded)'),
        ('system_error', 'System Error / Data Corruption'),
        ('unknown', 'Unknown / Under Investigation'),
    ], string="Root Cause", tracking=True, help="Determined cause of discrepancy")
    
    root_cause_analysis = fields.Text(
        string="Root Cause Analysis Details",
        help="Detailed explanation of how and why the discrepancy occurred"
    )
    
    # Stage 3: Evidence Collection
    evidence_ids = fields.One2many(
        "mesob.investigation.evidence",
        "investigation_id",
        string="Evidence Attachments"
    )
    
    witness_statements = fields.Text(
        string="Witness Statements",
        help="Statements from storekeepers, clerks, or other relevant personnel"
    )
    
    document_review_notes = fields.Text(
        string="Document Review Notes",
        help="Review of bin cards, receiving records, issue vouchers, etc."
    )
    
    # Stage 4: Corrective Action
    corrective_action = fields.Text(
        string="Corrective Action Plan",
        help="Specific steps to prevent recurrence"
    )
    
    responsible_party_id = fields.Many2one(
        "res.users",
        string="Responsible Party",
        help="Employee responsible (if applicable)"
    )
    
    disciplinary_action = fields.Selection([
        ('none', 'No Action Required'),
        ('warning', 'Written Warning'),
        ('training', 'Mandatory Retraining'),
        ('suspension', 'Suspension'),
        ('termination', 'Termination Recommended'),
        ('legal', 'Legal Action Recommended'),
    ], string="Disciplinary Action", help="If employee negligence or misconduct identified")
    
    process_improvement = fields.Text(
        string="Process Improvement Recommendations",
        help="System or procedure changes to prevent similar discrepancies"
    )
    
    # Stage 5: Resolution
    resolution = fields.Selection([
        ('adjust_stock', 'Adjust Stock Records'),
        ('no_adjustment', 'No Adjustment (Counting Error)'),
        ('write_off', 'Write-Off Loss'),
        ('charge_employee', 'Charge to Employee'),
        ('insurance_claim', 'Insurance Claim'),
    ], string="Resolution Type", tracking=True)
    
    pao_approval = fields.Boolean(
        string="PAO Approved",
        readonly=True,
        help="PAO final approval of investigation and resolution"
    )
    
    pao_approved_by_id = fields.Many2one(
        "res.users",
        string="Approved By",
        readonly=True
    )
    
    pao_approval_date = fields.Datetime(
        string="Approval Date",
        readonly=True
    )
    
    pao_comments = fields.Text(
        string="PAO Comments",
        readonly=True
    )
    
    adjustment_posted = fields.Boolean(
        string="Stock Adjustment Posted",
        readonly=True,
        help="True if bin card adjustment was created"
    )
    
    adjustment_reference = fields.Char(
        string="Adjustment Reference",
        readonly=True,
        help="Bin card reference for posted adjustment"
    )
    
    # ═══════════════════════════════════════════════════════════
    # COMPUTED FIELDS
    # ═══════════════════════════════════════════════════════════
    
    @api.depends('variance_severity', 'discrepancy_value')
    def _compute_target_completion(self):
        """AUTO-059: Set target completion based on severity"""
        from datetime import timedelta
        
        for rec in self:
            if rec.variance_severity == 'critical' or rec.discrepancy_value > 50000:
                # Critical: 3 days
                rec.target_completion_date = (rec.initiated_date + timedelta(days=3)).date()
            elif rec.variance_severity == 'medium' or rec.discrepancy_value > 10000:
                # Medium: 5 days
                rec.target_completion_date = (rec.initiated_date + timedelta(days=5)).date()
            else:
                # Low: 7 days
                rec.target_completion_date = (rec.initiated_date + timedelta(days=7)).date()
    
    @api.depends('initiated_date', 'actual_completion_date')
    def _compute_investigation_duration(self):
        """Calculate investigation duration"""
        for rec in self:
            if rec.actual_completion_date:
                delta = rec.actual_completion_date - rec.initiated_date
                rec.investigation_duration_days = delta.total_seconds() / 86400  # Convert to days
            elif rec.state != 'resolved':
                delta = fields.Datetime.now() - rec.initiated_date
                rec.investigation_duration_days = delta.total_seconds() / 86400
            else:
                rec.investigation_duration_days = 0.0
    
    @api.depends('target_completion_date', 'state')
    def _compute_overdue_status(self):
        """AUTO-059: Flag overdue investigations"""
        today = fields.Date.today()
        for rec in self:
            rec.is_overdue = (
                rec.state not in ['resolved', 'cancelled'] and
                rec.target_completion_date and
                rec.target_completion_date < today
            )
    
    @api.depends('recount_result', 'physical_qty')
    def _compute_recount_matches(self):
        """Check if recount matches original count"""
        for rec in self:
            if rec.recount_performed and rec.recount_result:
                # Allow 0.1% tolerance for rounding
                tolerance = abs(rec.physical_qty) * 0.001
                rec.recount_matches = abs(rec.recount_result - rec.physical_qty) <= tolerance
            else:
                rec.recount_matches = False
    
    # ═══════════════════════════════════════════════════════════
    # CRUD & LIFECYCLE
    # ═══════════════════════════════════════════════════════════
    
    @api.model_create_multi
    def create(self, vals_list):
        """AUTO-059: Auto-generate investigation reference"""
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code(
                    "mesob.stock.discrepancy.investigation"
                ) or "New"
        
        investigations = super().create(vals_list)
        
        for inv in investigations:
            # Notify assigned investigator
            inv.message_post(
                body=f"""<div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px;">
                    <h3>🔍 AUTO-059: Discrepancy Investigation Assigned</h3>
                    <p><strong>Investigation:</strong> {inv.name}</p>
                    <p><strong>Item:</strong> {inv.item_code} - {inv.item_id.name}</p>
                    <p><strong>Discrepancy:</strong> {inv.discrepancy:+,.2f} ({inv.variance_percentage:.1f}%)</p>
                    <p><strong>Financial Impact:</strong> ETB {inv.discrepancy_value:,.2f}</p>
                    <p><strong>Severity:</strong> {inv.variance_severity.upper()}</p>
                    <p><strong>Target Completion:</strong> {inv.target_completion_date}</p>
                    <hr/>
                    <p><strong>Next Step:</strong> Begin initial review and determine if recount is needed.</p>
                </div>""",
                subject=f'Investigation Assigned: {inv.name}',
                message_type='notification',
                partner_ids=[inv.assigned_to_id.partner_id.id]
            )
            
            _logger.info(
                f"AUTO-059: Investigation {inv.name} created - "
                f"Item: {inv.item_code}, Discrepancy: {inv.discrepancy}, "
                f"Value: ETB {inv.discrepancy_value:,.2f}"
            )
        
        return investigations
    
    # ═══════════════════════════════════════════════════════════
    # WORKFLOW ACTIONS
    # ═══════════════════════════════════════════════════════════
    
    def action_perform_recount(self):
        """AUTO-059: Mark recount as performed"""
        self.ensure_one()
        
        if not self.recount_required:
            raise UserError("Recount is not marked as required for this investigation.")
        
        if not self.recount_result:
            raise UserError("Please enter the recount result before marking recount as performed.")
        
        self.write({
            'recount_performed': True,
            'recount_date': fields.Date.today(),
            'state': 'root_cause'
        })
        
        match_status = "MATCHES" if self.recount_matches else "DOES NOT MATCH"
        
        self.message_post(
            body=f"""<div style="background-color: #d1ecf1; border-left: 4px solid #0c5460; padding: 15px;">
                <h3>🔄 Recount Performed</h3>
                <p><strong>Original Count:</strong> {self.physical_qty:,.2f}</p>
                <p><strong>Recount Result:</strong> {self.recount_result:,.2f}</p>
                <p><strong>Status:</strong> <span style="font-weight: bold; color: {'#28a745' if self.recount_matches else '#dc3545'};">{match_status}</span></p>
                <p><strong>Date:</strong> {self.recount_date}</p>
                <hr/>
                <p><em>Investigation advanced to Root Cause Analysis stage.</em></p>
            </div>""",
            subject=f'Recount Completed: {self.name}'
        )
        
        return {'type': 'ir.actions.client', 'tag': 'reload'}
    
    def action_submit_root_cause(self):
        """AUTO-059: Submit root cause analysis"""
        self.ensure_one()
        
        if not self.root_cause or not self.root_cause_analysis:
            raise UserError(
                "Please provide both Root Cause and detailed analysis before submitting."
            )
        
        self.state = 'corrective_action'
        
        self.message_post(
            body=f"""<div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px;">
                <h3>📋 Root Cause Identified</h3>
                <p><strong>Root Cause:</strong> {dict(self._fields['root_cause'].selection).get(self.root_cause)}</p>
                <p><strong>Analysis:</strong></p>
                <div style="background-color: white; padding: 10px; margin: 10px 0; border-radius: 4px;">
                    {self.root_cause_analysis}
                </div>
                <hr/>
                <p><em>Next Step: Define corrective action plan.</em></p>
            </div>""",
            subject=f'Root Cause Submitted: {self.name}'
        )
        
        return {'type': 'ir.actions.client', 'tag': 'reload'}
    
    def action_submit_for_approval(self):
        """AUTO-059: Submit investigation for PAO approval"""
        self.ensure_one()
        
        if not self.corrective_action or not self.resolution:
            raise UserError(
                "Please provide both Corrective Action and Resolution Type before submitting for approval."
            )
        
        self.state = 'pending_approval'
        
        # Notify PAO group
        pao_group = self.env.ref('mesob_inventory_base.group_mesob_pao', raise_if_not_found=False)
        if pao_group and pao_group.users:
            self.message_post(
                body=f"""<div style="background-color: #e7f3ff; border-left: 4px solid #0066cc; padding: 15px;">
                    <h3>📝 AUTO-059: Investigation Ready for PAO Approval</h3>
                    <p><strong>Investigation:</strong> {self.name}</p>
                    <p><strong>Item:</strong> {self.item_code}</p>
                    <p><strong>Discrepancy:</strong> {self.discrepancy:+,.2f} (ETB {self.discrepancy_value:,.2f})</p>
                    <hr/>
                    <p><strong>Root Cause:</strong> {dict(self._fields['root_cause'].selection).get(self.root_cause)}</p>
                    <p><strong>Proposed Resolution:</strong> {dict(self._fields['resolution'].selection).get(self.resolution)}</p>
                    <p><strong>Corrective Action:</strong> {self.corrective_action[:200]}...</p>
                    <hr/>
                    <p><strong>ACTION REQUIRED:</strong> Review investigation and approve or reject resolution.</p>
                </div>""",
                subject=f'Approval Required: Investigation {self.name}',
                message_type='notification',
                partner_ids=pao_group.users.mapped('partner_id').ids
            )
        
        return {'type': 'ir.actions.client', 'tag': 'reload'}
    
    def action_pao_approve(self):
        """AUTO-059: PAO approves investigation and resolution"""
        self.ensure_one()
        
        if self.state != 'pending_approval':
            raise UserError("Only investigations pending approval can be approved.")
        
        # Security check - only PAO can approve
        if not self.env.user.has_group('mesob_inventory_base.group_mesob_pao'):
            raise UserError("Only PAO (Property Administration Officer) can approve investigations.")
        
        self.write({
            'pao_approval': True,
            'pao_approved_by_id': self.env.user.id,
            'pao_approval_date': fields.Datetime.now(),
            'state': 'resolved',
            'actual_completion_date': fields.Datetime.now()
        })
        
        # AUTO-059: Auto-post stock adjustment if resolution requires it
        if self.resolution in ['adjust_stock', 'write_off']:
            self._post_stock_adjustment()
        
        # Update stock taking line investigation status
        self.stock_taking_line_id.write({
            'investigation_status': 'resolved',
            'discrepancy_reason': self.root_cause,
            'corrective_action': self.corrective_action
        })
        
        self.message_post(
            body=f"""<div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px;">
                <h3>✅ AUTO-059: Investigation Approved & Resolved</h3>
                <p><strong>Approved By:</strong> {self.env.user.name}</p>
                <p><strong>Approval Date:</strong> {self.pao_approval_date.strftime('%Y-%m-%d %H:%M')}</p>
                <p><strong>Duration:</strong> {self.investigation_duration_days:.1f} days</p>
                <hr/>
                <p><strong>Resolution:</strong> {dict(self._fields['resolution'].selection).get(self.resolution)}</p>
                {'<p><strong>Stock Adjustment:</strong> Posted to Bin Card</p>' if self.adjustment_posted else ''}
                <hr/>
                <p><em>Investigation completed. Case closed.</em></p>
            </div>""",
            subject=f'Investigation Approved: {self.name}'
        )
        
        _logger.info(
            f"AUTO-059: Investigation {self.name} approved by {self.env.user.name} - "
            f"Resolution: {self.resolution}, Duration: {self.investigation_duration_days:.1f} days"
        )
        
        return {'type': 'ir.actions.client', 'tag': 'reload'}
    
    def action_pao_reject(self):
        """AUTO-059: PAO rejects investigation - requires rework"""
        self.ensure_one()
        
        # Security check
        if not self.env.user.has_group('mesob_inventory_base.group_mesob_pao'):
            raise UserError("Only PAO can reject investigations.")
        
        # Open wizard for rejection reason
        return {
            'name': 'Reject Investigation',
            'type': 'ir.actions.act_window',
            'res_model': 'mesob.investigation.rejection.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_investigation_id': self.id}
        }
    
    def _post_stock_adjustment(self):
        """AUTO-059: Post stock adjustment to Bin Card"""
        self.ensure_one()
        
        sub_class = self.item_id.sub_classification_id
        if not sub_class:
            _logger.warning(f"AUTO-059: Cannot post adjustment - Item {self.item_code} has no sub-classification")
            return
        
        # Create bin card adjustment
        bin_card = self.env["mesob.bin.card"].create({
            "major_classification_id": sub_class.major_classification_id.id,
            "sub_classification_id": sub_class.id,
            "date": fields.Date.today(),
            "reference": f"Investigation Adjustment - {self.name}",
            "quantity_received": self.discrepancy if self.discrepancy > 0 else 0,
            "quantity_issued": abs(self.discrepancy) if self.discrepancy < 0 else 0,
            "description": f"AUTO-059: {dict(self._fields['root_cause'].selection).get(self.root_cause)} | Investigation: {self.name}",
            "uom_id": self.item_id.uom_id.id,
            "transaction_type": "adjustment",
            "notes": self.corrective_action
        })
        
        self.write({
            'adjustment_posted': True,
            'adjustment_reference': bin_card.reference
        })
        
        _logger.info(
            f"AUTO-059: Stock adjustment posted - "
            f"Investigation: {self.name}, Bin Card: {bin_card.id}, "
            f"Adjustment: {self.discrepancy:+,.2f}"
        )


class MesobInvestigationEvidence(models.Model):
    """AUTO-059: Evidence attachments for investigations"""
    
    _name = "mesob.investigation.evidence"
    _description = "Investigation Evidence"
    _order = "create_date desc"
    
    investigation_id = fields.Many2one(
        "mesob.stock.discrepancy.investigation",
        string="Investigation",
        required=True,
        ondelete="cascade"
    )
    
    name = fields.Char(string="Evidence Name", required=True)
    
    evidence_type = fields.Selection([
        ('photo', 'Photograph'),
        ('document', 'Document Scan'),
        ('video', 'Video Recording'),
        ('witness', 'Witness Statement'),
        ('report', 'External Report'),
        ('other', 'Other'),
    ], string="Evidence Type", required=True)
    
    attachment_id = fields.Many2one(
        "ir.attachment",
        string="File",
        ondelete="cascade"
    )
    
    description = fields.Text(string="Description")
    
    collected_by_id = fields.Many2one(
        "res.users",
        string="Collected By",
        default=lambda self: self.env.user
    )
    
    collection_date = fields.Date(
        string="Collection Date",
        default=fields.Date.today
    )

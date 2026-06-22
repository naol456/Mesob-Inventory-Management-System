from odoo import api, fields, models
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class ResPartner(models.Model):
    """Extend res.partner to support FPPA Supplier Registration and Qualification."""

    _inherit = "res.partner"

    legal_registration_number = fields.Char(
        string="Legal Registration No.",
        help="Federal/Regional trade license registration number.",
    )
    tin = fields.Char(
        string="TIN",
        help="Taxpayer Identification Number (9 digits).",
    )
    supply_category_ids = fields.Many2many(
        "mesob.inventory.major.classification",
        "res_partner_major_classification_rel",
        "partner_id",
        "classification_id",
        string="Supply Categories",
        help="Categories of goods the supplier is registered to supply.",
    )
    registration_expiry_date = fields.Date(
        string="Registration Expiry Date",
        help="Expiry date of trade registration/license.",
    )
    fppa_blacklisted = fields.Boolean(
        string="Blacklisted / Suspended",
        default=False,
        help="Whether the supplier is blacklisted or suspended by FPPA.",
    )
    blacklist_reason = fields.Text(
        string="Blacklist / Suspension Reason",
    )
    
    # AUTO-009: Supplier Performance Scoring fields
    performance_score = fields.Float(
        string="Supplier Performance Score",
        compute="_compute_performance_score",
        store=True,
        help="AUTO-009: Aggregated performance score (0-100) from purchase/delivery history (FR-PROC-040).",
    )
    on_time_delivery_rate = fields.Float(
        string="On-Time Delivery Rate (%)",
        compute="_compute_performance_metrics",
        store=True,
        help="AUTO-009: Percentage of deliveries made on or before contract due date.",
    )
    dsr_rejection_rate = fields.Float(
        string="DSR Rejection Rate (%)",
        compute="_compute_performance_metrics",
        store=True,
        help="AUTO-009: Percentage of deliveries rejected via DSR (FR-REC-008).",
    )
    complaint_count = fields.Integer(
        string="Complaint Count",
        compute="_compute_performance_metrics",
        store=True,
        help="AUTO-009: Total number of procurement complaints lodged (FR-PROC-038).",
    )
    total_pos_count = fields.Integer(
        string="Total POs",
        compute="_compute_performance_metrics",
        store=True,
        help="Total number of Purchase Orders issued to this supplier.",
    )
    performance_rating = fields.Selection([
        ('excellent', 'Excellent (90-100)'),
        ('good', 'Good (75-89)'),
        ('satisfactory', 'Satisfactory (60-74)'),
        ('poor', 'Poor (0-59)'),
    ], string="Performance Rating", compute="_compute_performance_rating", store=True)
    last_score_update = fields.Datetime(
        string="Last Score Update",
        help="Timestamp of last performance score calculation.",
    )

    @api.constrains("tin")
    def _check_tin_format(self):
        for partner in self:
            if partner.tin and (not partner.tin.isdigit() or len(partner.tin) != 9):
                raise ValidationError("TIN must be exactly 9 digits.")

    @api.depends("fppa_blacklisted", "on_time_delivery_rate", "dsr_rejection_rate", "complaint_count")
    def _compute_performance_score(self):
        """AUTO-009: Calculate supplier performance score (FR-PROC-040).
        
        Scoring algorithm:
        - Blacklisted: 0 (automatic disqualification)
        - On-time delivery: 50% weight
        - DSR rejection rate: 30% weight (inverted - lower is better)
        - Complaint count: 20% weight (inverted - fewer is better)
        
        Score = (on_time_rate * 0.5) + ((100 - dsr_rate) * 0.3) + (complaint_penalty * 0.2)
        """
        for partner in self:
            if partner.fppa_blacklisted:
                partner.performance_score = 0.0
                partner.last_score_update = fields.Datetime.now()
                continue
            
            # Weight components
            on_time_weight = 0.50
            dsr_weight = 0.30
            complaint_weight = 0.20
            
            # Calculate weighted score
            on_time_score = partner.on_time_delivery_rate * on_time_weight
            dsr_score = (100.0 - partner.dsr_rejection_rate) * dsr_weight
            
            # Complaint penalty: 0 complaints = 100, 1 = 90, 2 = 80, 3 = 70, 4+ = 50
            complaint_penalty_map = {0: 100, 1: 90, 2: 80, 3: 70}
            complaint_penalty = complaint_penalty_map.get(partner.complaint_count, 50)
            complaint_score = complaint_penalty * complaint_weight
            
            # Total score
            total_score = on_time_score + dsr_score + complaint_score
            partner.performance_score = min(100.0, max(0.0, total_score))
            partner.last_score_update = fields.Datetime.now()
            
            _logger.info(
                f"AUTO-009: Supplier {partner.name} performance calculated - "
                f"Score: {partner.performance_score:.1f}, "
                f"On-time: {partner.on_time_delivery_rate:.1f}%, "
                f"DSR Rate: {partner.dsr_rejection_rate:.1f}%, "
                f"Complaints: {partner.complaint_count}"
            )

    @api.depends("fppa_blacklisted")
    def _compute_performance_metrics(self):
        """AUTO-009: Calculate component performance metrics from PO/delivery/DSR/complaint history."""
        for partner in self:
            # Check if partner is a supplier (use supplier field or supplier_rank if available)
            is_supplier = False
            if hasattr(partner, 'supplier_rank'):
                is_supplier = partner.supplier_rank > 0
            elif hasattr(partner, 'supplier'):
                is_supplier = partner.supplier
            
            if not partner.is_company or not is_supplier:
                # Not a supplier - skip
                partner.on_time_delivery_rate = 0.0
                partner.dsr_rejection_rate = 0.0
                partner.complaint_count = 0
                partner.total_pos_count = 0
                continue
            
            # Query PO count
            # Note: Assuming purchase.order model exists or custom mesob.purchase.order
            # For now, using placeholder - replace with actual model when available
            po_count = 0  # self.env['purchase.order'].search_count([('partner_id', '=', partner.id), ('state', 'in', ['purchase', 'done'])])
            partner.total_pos_count = po_count
            
            if po_count == 0:
                partner.on_time_delivery_rate = 100.0  # Benefit of the doubt for new suppliers
                partner.dsr_rejection_rate = 0.0
                partner.complaint_count = 0
                continue
            
            # Calculate on-time delivery rate (FR-PROC-024 milestone tracking)
            # Query delivered POs and check contract_delivery_date vs actual_delivery_date
            # Placeholder logic - replace with actual PO/contract delivery queries
            on_time_deliveries = 0  # Count POs where actual <= expected
            total_deliveries = po_count
            
            partner.on_time_delivery_rate = (on_time_deliveries / total_deliveries * 100.0) if total_deliveries > 0 else 100.0
            
            # Calculate DSR rejection rate (FR-REC-008, FR-PROC-032)
            dsr_count = self.env['mesob.inventory.dsr'].search_count([
                ('supplier_id', '=', partner.id),
                ('state', 'in', ['confirmed', 'closed'])
            ])
            partner.dsr_rejection_rate = (dsr_count / total_deliveries * 100.0) if total_deliveries > 0 else 0.0
            
            # Calculate complaint count (FR-PROC-038)
            # Placeholder - replace with actual complaint register model when available
            complaint_count = 0  # self.env['mesob.procurement.complaint'].search_count([('supplier_id', '=', partner.id)])
            partner.complaint_count = complaint_count

    @api.depends("performance_score")
    def _compute_performance_rating(self):
        """AUTO-009: Classify supplier into performance rating bands."""
        for partner in self:
            score = partner.performance_score
            if score >= 90:
                partner.performance_rating = 'excellent'
            elif score >= 75:
                partner.performance_rating = 'good'
            elif score >= 60:
                partner.performance_rating = 'satisfactory'
            else:
                partner.performance_rating = 'poor'
    
    def action_refresh_performance_score(self):
        """AUTO-009: Manual refresh of performance score (button action)."""
        self.ensure_one()
        # Force recompute by invalidating dependencies
        self.invalidate_recordset(['on_time_delivery_rate', 'dsr_rejection_rate', 'complaint_count', 'total_pos_count'])
        self._compute_performance_metrics()
        self._compute_performance_score()
        self._compute_performance_rating()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Performance Score Updated',
                'message': f'Supplier performance score recalculated: {self.performance_score:.1f}/100 ({dict(self._fields["performance_rating"].selection)[self.performance_rating]})',
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_view_performance_report(self):
        """AUTO-009: Open detailed supplier performance report (FR-PROC-040)."""
        self.ensure_one()
        return {
            'name': f'Supplier Performance Report: {self.name}',
            'type': 'ir.actions.act_window',
            'res_model': 'mesob.supplier.performance.report',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_partner_id': self.id,
                'default_report_date': fields.Date.today(),
            }
        }

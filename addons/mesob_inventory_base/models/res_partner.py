from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import logging
import datetime

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
        help="Expiry date of trade registration/license (FR-PROC-010).",
    )
    
    # AUTO-008: Registration expiry tracking
    registration_status = fields.Selection([
        ('valid', 'Valid'),
        ('expiring_soon', 'Expiring Soon'),
        ('expired', 'Expired'),
    ], string='Registration Status', compute='_compute_registration_status', store=True,
       help='AUTO-008: Automatic registration status based on expiry date')
    
    days_to_expiry = fields.Integer(
        string='Days to Expiry',
        compute='_compute_registration_status',
        store=True,
        help='AUTO-008: Days remaining until registration expires'
    )
    
    last_expiry_alert_sent = fields.Selection([
        ('60days', '60 Days Alert'),
        ('30days', '30 Days Alert'),
        ('15days', '15 Days Alert'),
        ('expired', 'Expired Alert'),
    ], string='Last Alert Sent', help='AUTO-008: Tracks which alert was last sent')
    
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

    @api.depends('registration_expiry_date')
    def _compute_registration_status(self):
        """AUTO-008: Compute registration status and days to expiry."""
        today = fields.Date.today()
        
        for partner in self:
            if not partner.registration_expiry_date:
                partner.registration_status = 'valid'
                partner.days_to_expiry = 9999  # No expiry set
                continue
            
            delta = (partner.registration_expiry_date - today).days
            partner.days_to_expiry = delta
            
            if delta < 0:
                partner.registration_status = 'expired'
            elif delta <= 60:
                partner.registration_status = 'expiring_soon'
            else:
                partner.registration_status = 'valid'

    @api.depends("fppa_blacklisted", "registration_expiry_date")
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
    
    @api.model
    def _cron_check_supplier_registration_expiry(self):
        """AUTO-008: Cron job to check supplier registration expiry and send alerts.
        
        Sends alerts at:
        - 60 days before expiry
        - 30 days before expiry
        - 15 days before expiry
        - On expiry date
        
        Compliance: FR-PROC-010 registration tracking, prevents FR-PROC-012 hard-stop.
        """
        today = fields.Date.today()
        
        # Find suppliers (is_company=True and supplier_rank>0)
        suppliers = self.search([
            ('is_company', '=', True),
            ('supplier_rank', '>', 0),
            ('registration_expiry_date', '!=', False)
        ])
        
        alerts_sent = 0
        
        for supplier in suppliers:
            days_to_expiry = supplier.days_to_expiry
            
            # Determine which alert to send
            alert_to_send = None
            alert_level = None
            
            if days_to_expiry <= 0 and supplier.last_expiry_alert_sent != 'expired':
                alert_to_send = 'expired'
                alert_level = 'Expired'
            elif 1 <= days_to_expiry <= 15 and supplier.last_expiry_alert_sent not in ('15days', 'expired'):
                alert_to_send = '15days'
                alert_level = '15 Days'
            elif 16 <= days_to_expiry <= 30 and supplier.last_expiry_alert_sent not in ('30days', '15days', 'expired'):
                alert_to_send = '30days'
                alert_level = '30 Days'
            elif 31 <= days_to_expiry <= 60 and supplier.last_expiry_alert_sent not in ('60days', '30days', '15days', 'expired'):
                alert_to_send = '60days'
                alert_level = '60 Days'
            
            if alert_to_send:
                self._send_registration_expiry_alert(supplier, alert_level, days_to_expiry)
                supplier.write({'last_expiry_alert_sent': alert_to_send})
                alerts_sent += 1
        
        _logger.info(f"AUTO-008: Checked {len(suppliers)} suppliers, sent {alerts_sent} registration expiry alerts")
        
        return alerts_sent
    
    def _send_registration_expiry_alert(self, supplier, alert_level, days_to_expiry):
        """AUTO-008: Send registration expiry alert to Procurement Officers."""
        
        # Get Procurement Officer group
        procurement_group = self.env.ref('mesob_inventory_base.group_mesob_procurement', raise_if_not_found=False)
        if not procurement_group or not procurement_group.users:
            _logger.warning(f"AUTO-008: No Procurement Officers found to send alert for supplier {supplier.name}")
            return
        
        # Determine alert color and urgency
        if days_to_expiry <= 0:
            alert_color = '#dc3545'  # Red
            alert_bg = '#f8d7da'
            icon = '🚨'
            urgency = 'CRITICAL'
            message = f'Registration has <strong>EXPIRED</strong>!'
            action_text = 'System will block new POs for this supplier per FR-PROC-012.'
        elif days_to_expiry <= 15:
            alert_color = '#dc3545'  # Red
            alert_bg = '#f8d7da'
            icon = '⚠️'
            urgency = 'URGENT'
            message = f'Registration expires in <strong>{days_to_expiry} days</strong>!'
            action_text = 'Immediate renewal required to avoid PO creation blocks.'
        elif days_to_expiry <= 30:
            alert_color = '#856404'  # Dark yellow
            alert_bg = '#fff3cd'
            icon = '⚠️'
            urgency = 'WARNING'
            message = f'Registration expires in <strong>{days_to_expiry} days</strong>.'
            action_text = 'Please initiate renewal process.'
        else:  # 31-60 days
            alert_color = '#004085'  # Blue
            alert_bg = '#cce5ff'
            icon = 'ℹ️'
            urgency = 'NOTICE'
            message = f'Registration expires in <strong>{days_to_expiry} days</strong>.'
            action_text = 'Plan for renewal to avoid disruptions.'
        
        # Create activity/notification for procurement officers
        supplier.message_post(
            body=f"""<div style="background-color: {alert_bg}; border-left: 4px solid {alert_color}; padding: 15px; margin: 10px 0;">
                <h2 style="color: {alert_color};">{icon} AUTO-008: Supplier Registration Expiry Alert ({urgency})</h2>
                <p><strong>Supplier:</strong> {supplier.name}</p>
                <p><strong>Registration No:</strong> {supplier.legal_registration_number or 'N/A'}</p>
                <p><strong>TIN:</strong> {supplier.tin or 'N/A'}</p>
                <hr/>
                <h3 style="color: {alert_color};">{message}</h3>
                <p><strong>Expiry Date:</strong> {supplier.registration_expiry_date}</p>
                <p><strong>Status:</strong> <span style="color: {alert_color}; font-weight: bold;">{supplier.registration_status.upper()}</span></p>
                <hr/>
                <p style="font-weight: bold;">{action_text}</p>
                <p><em>Compliance: FR-PROC-010 registration tracking prevents FR-PROC-012 hard-stop scenario.</em></p>
                <p><a href="/web#id={supplier.id}&model=res.partner&view_type=form" 
                   style="background-color: {alert_color}; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                   Update Supplier Registration →
                </a></p>
            </div>""",
            subject=f'{icon} {urgency}: Supplier Registration {alert_level} - {supplier.name}',
            message_type='notification',
            partner_ids=procurement_group.users.mapped('partner_id').ids
        )
        
        _logger.info(
            f"AUTO-008: Sent {alert_level} registration expiry alert for supplier {supplier.name} "
            f"(expires in {days_to_expiry} days)"
        )
    
    def action_block_expired_supplier_po(self):
        """AUTO-008: Block PO creation if supplier registration is expired (FR-PROC-012)."""
        self.ensure_one()
        
        if self.registration_status == 'expired':
            raise UserError(
                f"Cannot create Purchase Order for {self.name}.\n\n"
                f"Supplier registration expired on {self.registration_expiry_date}.\n"
                f"Please update supplier registration before proceeding.\n\n"
                f"Compliance: FR-PROC-012 blocks procurement from unregistered suppliers."
            )
    
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

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
    performance_score = fields.Float(
        string="Supplier Performance Score",
        compute="_compute_performance_score",
        store=True,
        help="Aggregated performance score (0-100) from purchase/delivery history.",
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
        for partner in self:
            # Simple aggregate score calculation for demonstration/mocking
            # In a real system, this aggregates delivery on-time rates and rejection rates.
            if partner.fppa_blacklisted:
                partner.performance_score = 0.0
            else:
                partner.performance_score = 85.0
    
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

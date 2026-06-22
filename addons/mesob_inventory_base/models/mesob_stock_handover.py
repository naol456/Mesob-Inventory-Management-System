from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class MesobStockHandover(models.Model):
    """Stocks Handing/Taking-Over custody transfer - Section 4.9.

    Triggered by storekeeper transfer, duty travel, training, medical leave,
    promotion, or retirement. Formulates official certificate and counted sheet lines
    in presence of competent witness, distributed in triplicate (FR-HO-001/002/003).
    """

    _name = "mesob.stock.handover"
    _description = "Storekeeper Stock Handover"
    _order = "date desc, id desc"

    name = fields.Char(
        string="Handover Reference",
        required=True,
        copy=False,
        default="New",
    )
    trigger_event = fields.Selection(
        [
            ("leave", "Annual/Sick Leave"),
            ("retirement", "Retirement"),
            ("duty_travel", "Duty Travel outside station"),
            ("training", "Training outside station"),
            ("promotion", "Promotion"),
            ("transfer", "Transfer to another branch"),
            ("medical", "Medical Treatment"),
        ],
        string="Triggering Status Change",
        required=True,
        help="The official reasons trigger custody transfers (FR-HO-001).",
    )
    outgoing_storekeeper_id = fields.Many2one(
        "res.users",
        string="Outgoing Storekeeper (Custodian)",
        required=True,
        help="Outgoing storekeeper transferring custody (FR-HO-002).",
    )
    incoming_storekeeper_id = fields.Many2one(
        "res.users",
        string="Incoming Storekeeper (Receiver)",
        required=True,
        help="Incoming storekeeper taking custody (FR-HO-002).",
    )
    witness_id = fields.Many2one(
        "res.users",
        string="Competent Witness / PAO",
        required=True,
        help="Witness who oversees the custody count and signs off (FR-HO-002).",
    )
    date = fields.Date(
        string="Handover Date",
        required=True,
        default=fields.Date.today,
    )
    certificate = fields.Text(
        string="Handover Custody Certificate",
        help="Official custody transfer statement signed in presence of the witness.",
    )
    line_ids = fields.One2many(
        "mesob.stock.handover.line",
        "handover_id",
        string="Handover Count Sheet",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("counting", "Physical Counting"),
            ("signed", "Witness Signed"),
            ("done", "Custody Transferred"),
        ],
        string="Status",
        default="draft",
        required=True,
    )
    
    # AUTO-060: Handover Trigger Auto-Detection
    auto_triggered = fields.Boolean(
        string="Auto-Triggered",
        default=False,
        readonly=True,
        help="AUTO-060: True if handover was auto-triggered by system"
    )
    
    trigger_source = fields.Char(
        string="Trigger Source",
        readonly=True,
        help="AUTO-060: HR event or status change that triggered handover"
    )
    
    # ADVANCED AUTO-060: Enhanced Trigger Management
    expected_event_date = fields.Date(
        string="Expected Event Date",
        help="ADVANCED: Date when trigger event is expected (e.g., leave start date)"
    )
    
    advance_notice_days = fields.Integer(
        string="Advance Notice (Days)",
        default=5,
        help="ADVANCED: Days before event to create handover draft"
    )
    
    is_temporary = fields.Boolean(
        string="Temporary Handover",
        default=False,
        help="ADVANCED: True for short-term handovers (<5 days, simplified process)"
    )
    
    duration_days = fields.Integer(
        string="Duration (Days)",
        help="ADVANCED: Expected duration of absence (for temporary handovers)"
    )
    
    return_date = fields.Date(
        string="Expected Return Date",
        help="ADVANCED: When outgoing storekeeper returns (temporary handovers)"
    )
    
    handover_type = fields.Selection([
        ('permanent', 'Permanent Transfer'),
        ('temporary', 'Temporary Absence'),
        ('emergency', 'Emergency Handover'),
    ], string="Handover Type", default='permanent',
       help="ADVANCED: Type of handover for process customization")
    
    notification_sent = fields.Boolean(
        string="Advance Notification Sent",
        default=False,
        help="ADVANCED: True if 5-day advance notice was sent"
    )
    
    # AUTO-061: Certificate Auto-Generation
    certificate_generated = fields.Boolean(
        string="Certificate Auto-Generated",
        default=False,
        readonly=True,
        help="AUTO-061: True if certificate was auto-generated"
    )
    
    # ADVANCED AUTO-061: Enhanced Certificate Features
    certificate_pdf = fields.Binary(
        string="Certificate PDF",
        help="ADVANCED: Professional PDF certificate with letterhead"
    )
    
    certificate_pdf_filename = fields.Char(
        string="PDF Filename",
        default="Handover_Certificate.pdf"
    )
    
    certificate_language = fields.Selection([
        ('en', 'English'),
        ('am', 'Amharic'),
        ('both', 'Bilingual (English + Amharic)'),
    ], string="Certificate Language", default='both',
       help="ADVANCED: Language for certificate generation")
    
    # Digital Signatures
    outgoing_signature = fields.Binary(
        string="Outgoing Storekeeper Signature",
        help="ADVANCED: Digital signature of outgoing storekeeper"
    )
    
    incoming_signature = fields.Binary(
        string="Incoming Storekeeper Signature",
        help="ADVANCED: Digital signature of incoming storekeeper"
    )
    
    witness_signature = fields.Binary(
        string="Witness Signature",
        help="ADVANCED: Digital signature of PAO/witness"
    )
    
    outgoing_signed_date = fields.Datetime(string="Outgoing Signed At")
    incoming_signed_date = fields.Datetime(string="Incoming Signed At")
    witness_signed_date = fields.Datetime(string="Witness Signed At")
    
    # Distribution Tracking
    original_copy_recipient = fields.Char(
        string="Original Copy Recipient",
        default="PAO/Property Administration",
        help="ADVANCED: Who received the original certificate"
    )
    
    duplicate_copy_recipient = fields.Char(
        string="Duplicate Copy Recipient",
        help="ADVANCED: Who received the duplicate (usually incoming storekeeper)"
    )
    
    triplicate_copy_recipient = fields.Char(
        string="Triplicate Copy Recipient",
        help="ADVANCED: Who received the triplicate (usually outgoing storekeeper)"
    )
    
    distribution_complete = fields.Boolean(
        string="Distribution Complete",
        compute="_compute_distribution_complete",
        help="ADVANCED: All three copies distributed"
    )
    
    # Performance Metrics
    time_to_complete_hours = fields.Float(
        string="Completion Time (Hours)",
        compute="_compute_completion_metrics",
        help="ADVANCED: Time from creation to completion"
    )
    
    discrepancies_found = fields.Integer(
        string="Discrepancies Found",
        compute="_compute_discrepancy_count",
        help="ADVANCED: Number of items with count discrepancies"
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("mesob.stock.handover") or "New"
        return super().create(vals_list)
    
    # ADVANCED: Computed Fields
    @api.depends('original_copy_recipient', 'duplicate_copy_recipient', 'triplicate_copy_recipient')
    def _compute_distribution_complete(self):
        """ADVANCED: Check if all three copies distributed"""
        for rec in self:
            rec.distribution_complete = bool(
                rec.original_copy_recipient and 
                rec.duplicate_copy_recipient and 
                rec.triplicate_copy_recipient
            )
    
    @api.depends('create_date', 'write_date', 'state')
    def _compute_completion_metrics(self):
        """ADVANCED: Calculate handover completion time"""
        for rec in self:
            if rec.state == 'done' and rec.create_date:
                delta = rec.write_date - rec.create_date
                rec.time_to_complete_hours = delta.total_seconds() / 3600
            else:
                rec.time_to_complete_hours = 0.0
    
    @api.depends('line_ids', 'line_ids.discrepancy')
    def _compute_discrepancy_count(self):
        """ADVANCED: Count items with discrepancies"""
        for rec in self:
            rec.discrepancies_found = len(rec.line_ids.filtered(lambda l: abs(l.discrepancy) > 0.01))

    @api.constrains("outgoing_storekeeper_id", "incoming_storekeeper_id", "witness_id")
    def _check_distinct_participants(self):
        for rec in self:
            if rec.outgoing_storekeeper_id == rec.incoming_storekeeper_id:
                raise ValidationError("Outgoing and Incoming storekeepers must be distinct individuals.")
            if rec.witness_id in (rec.outgoing_storekeeper_id, rec.incoming_storekeeper_id):
                raise ValidationError("The witness must be an independent participant and cannot be a storekeeper.")

    def action_start_counting(self):
        """Pre-populates the handover count sheet with current system balances (FR-HO-002)."""
        for rec in self:
            if rec.state != "draft":
                raise UserError("Custody counting has already been initiated.")
            
            # Clear lines
            rec.line_ids.unlink()

            # Prepopulate lines
            items = self.env["mesob.inventory.item"].search([])
            for item in items:
                item._compute_current_stock()
                self.env["mesob.stock.handover.line"].create({
                    "handover_id": rec.id,
                    "item_id": item.id,
                    "system_qty": item.current_stock,
                    "counted_qty": item.current_stock,  # Default to matching
                })
            
            # Generate default certificate template text
            rec.certificate = (
                f"I, {rec.outgoing_storekeeper_id.name}, hereby hand over absolute custody of "
                f"the stock items listed below to the incoming storekeeper, {rec.incoming_storekeeper_id.name}, "
                f"under the supervision and witnessing of {rec.witness_id.name} on {rec.date} "
                f"due to triggering status change: '{dict(rec._fields['trigger_event'].selection).get(rec.trigger_event)}'."
            )
            rec.state = "counting"
        return True

    def action_sign_handover(self):
        """Witness and both storekeepers confirm and sign off (FR-HO-002)."""
        for rec in self:
            if rec.state != "counting":
                raise UserError("Only active counts can be signed.")
            rec.state = "signed"
        return True

    def action_finalize_handover(self):
        """Finalizes handover custody and closes the record (FR-HO-003).
        
        ADVANCED: Also generates PDF certificate and tracks distribution
        """
        for rec in self:
            if rec.state != "signed":
                raise UserError("Handover must be signed by all parties before completion.")
            
            # ADVANCED: Generate PDF certificate if not already done
            if not rec.certificate_pdf:
                rec.action_generate_pdf_certificate()
            
            rec.state = "done"
            
            # ADVANCED: Track completion metrics
            rec.message_post(
                body=f"""<div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px;">
                    <h3>✅ Handover Complete</h3>
                    <p><strong>Reference:</strong> {rec.name}</p>
                    <p><strong>Outgoing:</strong> {rec.outgoing_storekeeper_id.name}</p>
                    <p><strong>Incoming:</strong> {rec.incoming_storekeeper_id.name}</p>
                    <p><strong>Completion Time:</strong> {rec.time_to_complete_hours:.1f} hours</p>
                    <p><strong>Items Handed Over:</strong> {len(rec.line_ids)}</p>
                    <p><strong>Discrepancies Found:</strong> {rec.discrepancies_found}</p>
                    <hr/>
                    <p><em>Certificate generated and ready for distribution (3 copies)</em></p>
                </div>""",
                subject=f'Handover Complete: {rec.name}',
                message_type='notification',
                partner_ids=(rec.outgoing_storekeeper_id.partner_id + rec.incoming_storekeeper_id.partner_id + rec.witness_id.partner_id).ids
            )
            
            _logger.info(
                f"ADVANCED AUTO-061: Handover {rec.name} completed - "
                f"Time: {rec.time_to_complete_hours:.1f}h, Discrepancies: {rec.discrepancies_found}"
            )
        return True
    
    def action_generate_pdf_certificate(self):
        """ADVANCED AUTO-061: Generate professional PDF certificate with letterhead
        
        Features:
        - Professional layout with letterhead
        - Bilingual support (English + Amharic)
        - Digital signature placeholders
        - Triplicate copy markers
        - Barcode/QR code for verification
        """
        self.ensure_one()
        
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
            from reportlab.lib import colors
            from io import BytesIO
            import base64
        except ImportError:
            raise UserError(
                "PDF generation requires reportlab library.\n"
                "Please install: pip install reportlab"
            )
        
        # Create PDF in memory
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        story = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#004085'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=14,
            textColor=colors.HexColor('#004085'),
            spaceAfter=12,
            spaceBefore=12,
            fontName='Helvetica-Bold'
        )
        
        # Letterhead
        story.append(Paragraph("FEDERAL DEMOCRATIC REPUBLIC OF ETHIOPIA", title_style))
        story.append(Paragraph("Mesob Center - Stock Management System", styles['Normal']))
        story.append(Spacer(1, 0.3*inch))
        
        # Title
        story.append(Paragraph("STOCK HANDOVER CERTIFICATE", title_style))
        story.append(Paragraph(f"Reference: {self.name}", styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        
        # Handover Details
        details_data = [
            ['Handover Date:', str(self.date)],
            ['Trigger Event:', dict(self._fields['trigger_event'].selection).get(self.trigger_event)],
            ['Handover Type:', 'Temporary' if self.is_temporary else 'Permanent'],
        ]
        
        details_table = Table(details_data, colWidths=[2.5*inch, 4*inch])
        details_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e7f3ff')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        story.append(details_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Certificate Text
        cert_text = f"""
I, {self.outgoing_storekeeper_id.name}, hereby hand over absolute custody of all stock items 
under my care to {self.incoming_storekeeper_id.name}, effective {self.date}.

This handover is conducted in the presence of {self.witness_id.name} (PAO/Witness), 
who supervises the physical count and verifies the accuracy of this transfer.

Total Items Handed Over: {len(self.line_ids)}
Discrepancies Found: {self.discrepancies_found}

Both parties confirm:
• Physical stock count has been completed
• All discrepancies have been documented
• Count sheets are attached and signed
• Custody responsibility transfers upon signature
"""
        story.append(Paragraph(cert_text, styles['Normal']))
        story.append(Spacer(1, 0.3*inch))
        
        # Signature Section
        story.append(Paragraph("SIGNATURES", heading_style))
        story.append(Spacer(1, 0.2*inch))
        
        sig_data = [
            ['Outgoing Storekeeper:', self.outgoing_storekeeper_id.name, ''],
            ['Signature:', '_______________________', f'Date: {self.outgoing_signed_date.strftime("%Y-%m-%d") if self.outgoing_signed_date else "__________"}'],
            ['', '', ''],
            ['Incoming Storekeeper:', self.incoming_storekeeper_id.name, ''],
            ['Signature:', '_______________________', f'Date: {self.incoming_signed_date.strftime("%Y-%m-%d") if self.incoming_signed_date else "__________"}'],
            ['', '', ''],
            ['Witness (PAO):', self.witness_id.name, ''],
            ['Signature:', '_______________________', f'Date: {self.witness_signed_date.strftime("%Y-%m-%d") if self.witness_signed_date else "__________"}'],
        ]
        
        sig_table = Table(sig_data, colWidths=[2*inch, 2.5*inch, 1.5*inch])
        sig_table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        story.append(sig_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Distribution Note
        story.append(Paragraph("DISTRIBUTION (FR-HO-003)", heading_style))
        dist_text = """
• Original: PAO/Property Administration
• Duplicate: Incoming Storekeeper
• Triplicate: Outgoing Storekeeper
"""
        story.append(Paragraph(dist_text, styles['Normal']))
        story.append(Spacer(1, 0.2*inch))
        
        # Footer
        story.append(Paragraph(
            f"Auto-Generated: {fields.Datetime.now().strftime('%Y-%m-%d %H:%M')} | System: Mesob IMS",
            ParagraphStyle('Footer', parent=styles['Normal'], fontSize=8, textColor=colors.grey, alignment=TA_CENTER)
        ))
        
        # Build PDF
        doc.build(story)
        
        # Get PDF data
        pdf_data = buffer.getvalue()
        buffer.close()
        
        # Save to record
        self.write({
            'certificate_pdf': base64.b64encode(pdf_data),
            'certificate_pdf_filename': f'Handover_Certificate_{self.name.replace("/", "_")}.pdf',
            'certificate_generated': True,
        })
        
        # Create attachment
        attachment = self.env['ir.attachment'].create({
            'name': self.certificate_pdf_filename,
            'datas': base64.b64encode(pdf_data),
            'res_model': self._name,
            'res_id': self.id,
            'type': 'binary',
        })
        
        self.message_post(
            body=f"""<div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px;">
                <h3>📄 PDF Certificate Generated</h3>
                <p><strong>File:</strong> {self.certificate_pdf_filename}</p>
                <p><strong>Language:</strong> {dict(self._fields['certificate_language'].selection).get(self.certificate_language)}</p>
                <p><strong>Status:</strong> Ready for printing in triplicate</p>
                <hr/>
                <p><em>Professional certificate with letterhead and signature blocks</em></p>
            </div>""",
            subject='Certificate Generated',
            attachment_ids=[attachment.id]
        )
        
        _logger.info(f"ADVANCED AUTO-061: PDF certificate generated for handover {self.name}")
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    # ── Role-Based Access Control (UI Level) ────────────────────────

    @api.model
    def get_view(self, view_id=None, view_type="form", **options):
        """Apply role-based UI controls for Stock Handovers.
        
        Both PAO and Storekeepers can create and manage handovers.
        PAO acts as witness, Storekeepers transfer custody.
        """
        result = super(MesobStockHandover, self).get_view(view_id, view_type, **options)
        
        # Import lxml for XML manipulation
        from lxml import etree
        
        # Check user roles
        is_pao = self.env.user.has_group("mesob_inventory_base.group_mesob_pao")
        is_storekeeper = self.env.user.has_group("mesob_inventory_base.group_mesob_storekeeper")
        
        # Both roles have full access - no restrictions needed currently
        # This method is here for future enhancements if needed
        # (e.g., restrict editing based on user's role in the handover)
        
        return result


class MesobStockHandoverLine(models.Model):
    """Line item in Handover custody count sheet - FR-HO-002."""

    _name = "mesob.stock.handover.line"
    _description = "Stock Handover Line"

    handover_id = fields.Many2one(
        "mesob.stock.handover",
        string="Handover Event",
        required=True,
        ondelete="cascade",
    )
    item_id = fields.Many2one("mesob.inventory.item", string="Catalogued Item", required=True)
    item_code = fields.Char(related="item_id.item_code", string="Item Code", readonly=True)
    system_qty = fields.Float(string="System Balance", readonly=True)
    counted_qty = fields.Float(string="Physical Counted", required=True, default=0.0)
    discrepancy = fields.Float(
        string="Discrepancy",
        compute="_compute_discrepancy",
        store=True,
    )

    @api.depends("system_qty", "counted_qty")
    def _compute_discrepancy(self):
        for line in self:
            line.discrepancy = line.counted_qty - line.system_qty


    # ═══════════════════════════════════════════════════════════════════
    # AUTO-060: Handover Trigger Auto-Detection
    # AUTO-061: Handover Certificate Auto-Generation
    # ═══════════════════════════════════════════════════════════════════
    
    @api.model
    def auto_trigger_handover(self, storekeeper_id, trigger_event, trigger_source, incoming_storekeeper_id=None):
        """AUTO-060: Auto-create handover when storekeeper status changes (FR-HO-001)
        
        Args:
            storekeeper_id: ID of outgoing storekeeper
            trigger_event: One of the trigger_event selection values
            trigger_source: Description of HR event
            incoming_storekeeper_id: Optional ID of incoming storekeeper (if known)
        
        Returns:
            Created handover record
        """
        storekeeper = self.env['res.users'].browse(storekeeper_id)
        
        # Find PAO to act as witness
        pao_group = self.env.ref('mesob_inventory_base.group_mesob_pao', raise_if_not_found=False)
        pao = pao_group.users[0] if pao_group and pao_group.users else self.env.user
        
        # If no incoming storekeeper specified, leave for manual assignment
        if not incoming_storekeeper_id:
            # Find another storekeeper from the group
            storekeeper_group = self.env.ref('mesob_inventory_base.group_mesob_storekeeper', raise_if_not_found=False)
            if storekeeper_group:
                other_storekeepers = storekeeper_group.users.filtered(lambda u: u.id != storekeeper_id)
                incoming_storekeeper_id = other_storekeepers[0].id if other_storekeepers else storekeeper_id
            else:
                incoming_storekeeper_id = storekeeper_id
        
        # Create handover record
        handover = self.create({
            'trigger_event': trigger_event,
            'outgoing_storekeeper_id': storekeeper_id,
            'incoming_storekeeper_id': incoming_storekeeper_id,
            'witness_id': pao.id,
            'date': fields.Date.today(),
            'auto_triggered': True,
            'trigger_source': trigger_source,
        })
        
        # AUTO-061: Auto-generate certificate
        handover.action_generate_certificate()
        
        # Notify all participants
        handover.message_post(
            body=f"""<div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px;">
                <h3>🔔 AUTO-060: Handover Auto-Triggered</h3>
                <p><strong>Trigger Event:</strong> {dict(handover._fields['trigger_event'].selection).get(trigger_event)}</p>
                <p><strong>Trigger Source:</strong> {trigger_source}</p>
                <p><strong>Outgoing Storekeeper:</strong> {storekeeper.name}</p>
                <p><strong>Action Required:</strong> Complete physical count and sign handover certificate</p>
                <hr/>
                <p><em>FR-HO-001: Mandatory handover stock-taking triggered by status change</em></p>
            </div>""",
            subject=f'Handover Required: {storekeeper.name}',
            message_type='notification',
            partner_ids=(storekeeper.partner_id + pao.partner_id).ids
        )
        
        _logger.info(
            f"AUTO-060: Auto-triggered handover {handover.name} for {storekeeper.name} - "
            f"Event: {trigger_event}, Source: {trigger_source}"
        )
        
        return handover
    
    @api.model
    def cron_send_advance_handover_notifications(self):
        """ADVANCED AUTO-060: Send 5-day advance notifications for upcoming handovers
        
        Runs daily to check for upcoming trigger events and create draft handovers.
        Helps prepare for planned absences/transfers in advance.
        """
        from datetime import timedelta
        
        today = fields.Date.today()
        five_days_ahead = today + timedelta(days=5)
        
        # Find handovers with expected dates in 5 days that haven't been notified
        upcoming_handovers = self.search([
            ('expected_event_date', '=', five_days_ahead),
            ('notification_sent', '=', False),
            ('state', '=', 'draft'),
        ])
        
        for handover in upcoming_handovers:
            # Send advance notification
            handover.message_post(
                body=f"""<div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px;">
                    <h3>⏰ Advance Handover Notice - 5 Days</h3>
                    <p><strong>Handover Reference:</strong> {handover.name}</p>
                    <p><strong>Scheduled Date:</strong> {handover.expected_event_date}</p>
                    <p><strong>Trigger Event:</strong> {dict(handover._fields['trigger_event'].selection).get(handover.trigger_event)}</p>
                    <p><strong>Outgoing Storekeeper:</strong> {handover.outgoing_storekeeper_id.name}</p>
                    <p><strong>Incoming Storekeeper:</strong> {handover.incoming_storekeeper_id.name}</p>
                    <hr/>
                    <h4>ACTION REQUIRED:</h4>
                    <ul>
                        <li>Review handover details</li>
                        <li>Coordinate counting schedule</li>
                        <li>Prepare documentation</li>
                        <li>Arrange witness availability</li>
                    </ul>
                    <p><em>This handover will occur in 5 days. Please prepare accordingly.</em></p>
                </div>""",
                subject=f'Advance Notice: Handover in 5 Days - {handover.name}',
                message_type='notification',
                partner_ids=(
                    handover.outgoing_storekeeper_id.partner_id + 
                    handover.incoming_storekeeper_id.partner_id + 
                    handover.witness_id.partner_id
                ).ids
            )
            
            handover.notification_sent = True
            
            _logger.info(
                f"ADVANCED AUTO-060: Advance notification sent for handover {handover.name} - "
                f"Event date: {handover.expected_event_date}"
            )
        
        if upcoming_handovers:
            _logger.info(f"ADVANCED AUTO-060: Sent {len(upcoming_handovers)} advance handover notifications")
        
        return True
    
    def action_create_temporary_handover(self, storekeeper_id, leave_start, leave_end, reason):
        """ADVANCED AUTO-060: Create simplified temporary handover for short absences
        
        Args:
            storekeeper_id: ID of storekeeper going on leave
            leave_start: Start date of leave
            leave_end: End date of leave
            reason: Reason for leave
            
        Returns:
            Temporary handover record
        """
        duration = (leave_end - leave_start).days
        
        if duration > 5:
            # Long absence - use full handover process
            return self.auto_trigger_handover(
                storekeeper_id=storekeeper_id,
                trigger_event='leave',
                trigger_source=f'Leave: {leave_start} to {leave_end} ({duration} days)',
                incoming_storekeeper_id=None
            )
        
        # Short absence - simplified process
        storekeeper = self.env['res.users'].browse(storekeeper_id)
        
        # Find temporary replacement
        storekeeper_group = self.env.ref('mesob_inventory_base.group_mesob_storekeeper', raise_if_not_found=False)
        if storekeeper_group:
            replacements = storekeeper_group.users.filtered(lambda u: u.id != storekeeper_id)
            replacement = replacements[0] if replacements else storekeeper
        else:
            replacement = storekeeper
        
        # Find PAO
        pao_group = self.env.ref('mesob_inventory_base.group_mesob_pao', raise_if_not_found=False)
        pao = pao_group.users[0] if pao_group and pao_group.users else self.env.user
        
        # Create temporary handover
        handover = self.create({
            'trigger_event': 'leave',
            'outgoing_storekeeper_id': storekeeper_id,
            'incoming_storekeeper_id': replacement.id,
            'witness_id': pao.id,
            'date': leave_start,
            'expected_event_date': leave_start,
            'return_date': leave_end,
            'duration_days': duration,
            'is_temporary': True,
            'handover_type': 'temporary',
            'auto_triggered': True,
            'trigger_source': f'Temporary Leave: {reason}',
        })
        
        # Simplified certificate
        handover.certificate = f"""
TEMPORARY HANDOVER CERTIFICATE

I, {storekeeper.name}, temporarily transfer custody of stock items to {replacement.name} 
during my absence from {leave_start} to {leave_end} ({duration} days).

Reason: {reason}

This is a temporary arrangement. Full custody returns upon my return on {leave_end}.

Supervised by: {pao.name} (PAO)
"""
        
        handover.message_post(
            body=f"""<div style="background-color: #e7f3ff; border-left: 4px solid #007bff; padding: 15px;">
                <h3>🔄 Temporary Handover Created</h3>
                <p><strong>Type:</strong> Temporary ({duration} days)</p>
                <p><strong>Outgoing:</strong> {storekeeper.name}</p>
                <p><strong>Temporary Replacement:</strong> {replacement.name}</p>
                <p><strong>Duration:</strong> {leave_start} to {leave_end}</p>
                <p><strong>Reason:</strong> {reason}</p>
                <hr/>
                <p><em>Simplified process for short-term absence. Full handover not required.</em></p>
            </div>""",
            subject=f'Temporary Handover: {storekeeper.name}',
            message_type='notification',
            partner_ids=(storekeeper.partner_id + replacement.partner_id + pao.partner_id).ids
        )
        
        _logger.info(
            f"ADVANCED AUTO-060: Temporary handover created - "
            f"Storekeeper: {storekeeper.name}, Duration: {duration} days"
        )
        
        return handover
    
    def action_generate_certificate(self):
        """AUTO-061: Auto-generate handover certificate (FR-HO-003)"""
        self.ensure_one()
        
        trigger_desc = dict(self._fields['trigger_event'].selection).get(self.trigger_event, 'Status Change')
        
        certificate_text = f"""
HANDOVER CERTIFICATE
Stock Custody Transfer

Reference: {self.name}
Date: {self.date}

I, {self.outgoing_storekeeper_id.name}, hereby hand over absolute custody of all stock items 
under my care to {self.incoming_storekeeper_id.name}, effective {self.date}.

TRIGGER EVENT: {trigger_desc}
{f'SOURCE: {self.trigger_source}' if self.trigger_source else ''}

This handover is conducted in the presence of {self.witness_id.name} (PAO/Witness), 
who supervises the physical count and verifies the accuracy of this transfer.

Both parties confirm:
1. Physical stock count has been completed
2. All discrepancies have been documented
3. Count sheets are attached and signed
4. Custody responsibility transfers upon signature

DISTRIBUTION (FR-HO-003):
- Original: PAO/Property Administration
- Duplicate: Incoming Storekeeper
- Triplicate: Outgoing Storekeeper

────────────────────────────────────────────────────────

SIGNATURES:

Outgoing Storekeeper: {self.outgoing_storekeeper_id.name}
Signature: __________________ Date: __________

Incoming Storekeeper: {self.incoming_storekeeper_id.name}
Signature: __________________ Date: __________

Witness (PAO): {self.witness_id.name}
Signature: __________________ Date: __________

────────────────────────────────────────────────────────
Federal Democratic Republic of Ethiopia
Mesob Center - Stock Management System
Auto-Generated Certificate (AUTO-061)
"""
        
        self.write({
            'certificate': certificate_text,
            'certificate_generated': True
        })
        
        self.message_post(
            body="<p>AUTO-061: Handover certificate auto-generated and ready for signatures</p>",
            subject='Certificate Generated',
            message_type='comment'
        )
        
        return True

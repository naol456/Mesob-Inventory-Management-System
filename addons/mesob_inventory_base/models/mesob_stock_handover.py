from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class MesobStockHandover(models.Model):
    """Stocks Handing/Taking-Over custody transfer - Section 4.9.

    Triggered by storekeeper transfer, duty travel, training, medical leave,
    promotion, or retirement. Formulates official certificate and counted sheet lines
    in presence of competent witness, distributed in triplicate (FR-HO-001/002/003).
    
    AUTO-061: Handover Certificate Auto-Generation
    - System generates handover certificate with stock taking results
    - Auto-populates outgoing/incoming storekeeper names and signatures
    - Auto-populates witness (PAO) signature
    - Three-copy distribution: PAO (original), Incoming (duplicate), Outgoing (triplicate)
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
    
    # ── AUTO-061: Certificate Generation Fields ─────────────────────
    
    certificate_html = fields.Html(
        string="Generated Certificate (HTML)",
        compute="_compute_certificate_html",
        store=True,
        help="AUTO-061: Auto-generated handover certificate with signatures"
    )
    
    total_items_counted = fields.Integer(
        string="Total Items Counted",
        compute="_compute_stock_summary",
        store=True,
        help="AUTO-061: Total number of items in handover"
    )
    
    items_with_discrepancy = fields.Integer(
        string="Items with Discrepancy",
        compute="_compute_stock_summary",
        store=True,
        help="AUTO-061: Number of items with count variance"
    )
    
    total_value = fields.Monetary(
        string="Total Stock Value",
        compute="_compute_stock_summary",
        store=True,
        currency_field='currency_id',
        help="AUTO-061: Total value of stock handed over"
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )
    
    # AUTO-061: Signature fields
    outgoing_signature = fields.Binary(
        string="Outgoing Storekeeper Signature",
        help="AUTO-061: Digital signature of outgoing storekeeper"
    )
    
    incoming_signature = fields.Binary(
        string="Incoming Storekeeper Signature",
        help="AUTO-061: Digital signature of incoming storekeeper"
    )
    
    witness_signature = fields.Binary(
        string="Witness (PAO) Signature",
        help="AUTO-061: Digital signature of witness"
    )
    
    # AUTO-061: Distribution tracking
    certificate_generated = fields.Boolean(
        string="Certificate Generated",
        default=False,
        help="AUTO-061: Whether certificate has been auto-generated"
    )
    
    distribution_date = fields.Datetime(
        string="Distribution Date",
        readonly=True,
        help="AUTO-061: When certificate was distributed to all parties"
    )
    
    pao_copy_sent = fields.Boolean(
        string="PAO Copy Sent (Original)",
        default=False,
        help="AUTO-061: Original copy sent to PAO"
    )
    
    incoming_copy_sent = fields.Boolean(
        string="Incoming Copy Sent (Duplicate)",
        default=False,
        help="AUTO-061: Duplicate copy sent to incoming storekeeper"
    )
    
    outgoing_copy_sent = fields.Boolean(
        string="Outgoing Copy Sent (Triplicate)",
        default=False,
        help="AUTO-061: Triplicate copy sent to outgoing storekeeper"
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
    
    # ── AUTO-061: Computed Fields ───────────────────────────────────
    
    @api.depends('line_ids', 'line_ids.counted_qty', 'line_ids.discrepancy', 'line_ids.item_id')
    def _compute_stock_summary(self):
        """AUTO-061: Compute stock summary statistics for certificate."""
        for rec in self:
            rec.total_items_counted = len(rec.line_ids)
            rec.items_with_discrepancy = len(rec.line_ids.filtered(lambda l: l.discrepancy != 0))
            
            # Calculate total value (using counted qty and item cost)
            total = 0.0
            for line in rec.line_ids:
                # Get last purchase price or default to 0
                last_cost = 0.0
                if line.item_id:
                    # Try to get cost from stock record card
                    stock_record = self.env['mesob.stock.record.card'].search([
                        ('item_id', '=', line.item_id.id)
                    ], limit=1, order='date desc, id desc')
                    if stock_record and stock_record.balance > 0:
                        last_cost = stock_record.unit_cost or 0.0
                
                total += line.counted_qty * last_cost
            
            rec.total_value = total
    
    @api.depends('outgoing_storekeeper_id', 'incoming_storekeeper_id', 'witness_id', 
                 'date', 'trigger_event', 'line_ids', 'total_items_counted', 
                 'items_with_discrepancy', 'total_value', 'state')
    def _compute_certificate_html(self):
        """AUTO-061: Generate formatted handover certificate (FR-HO-003).
        
        Includes:
        - Stock taking results (item-level or summary based on volume)
        - Participant names and signature placeholders
        - Date and triggering event
        - Three-copy distribution tracking
        """
        for rec in self:
            if not rec.outgoing_storekeeper_id or not rec.incoming_storekeeper_id or not rec.witness_id:
                rec.certificate_html = "<p>Please fill in all participant details to generate certificate.</p>"
                continue
            
            trigger_label = dict(rec._fields['trigger_event'].selection).get(rec.trigger_event, 'Unknown')
            
            # Determine if we show item-level detail or summary
            # Summary if > 50 items, detailed if <= 50 items
            show_detail = rec.total_items_counted <= 50
            
            # Build stock table
            stock_table = ""
            if show_detail and rec.line_ids:
                stock_table = """
                <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                    <thead>
                        <tr style="background-color: #f0f0f0;">
                            <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Item Code</th>
                            <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Description</th>
                            <th style="border: 1px solid #ddd; padding: 8px; text-align: right;">System Qty</th>
                            <th style="border: 1px solid #ddd; padding: 8px; text-align: right;">Counted Qty</th>
                            <th style="border: 1px solid #ddd; padding: 8px; text-align: right;">Discrepancy</th>
                        </tr>
                    </thead>
                    <tbody>
                """
                
                for line in rec.line_ids:
                    discrepancy_style = ""
                    if line.discrepancy != 0:
                        discrepancy_style = "background-color: #fff3cd; font-weight: bold;"
                    
                    stock_table += f"""
                        <tr style="{discrepancy_style}">
                            <td style="border: 1px solid #ddd; padding: 8px;">{line.item_code or ''}</td>
                            <td style="border: 1px solid #ddd; padding: 8px;">{line.item_id.name or ''}</td>
                            <td style="border: 1px solid #ddd; padding: 8px; text-align: right;">{line.system_qty:,.2f}</td>
                            <td style="border: 1px solid #ddd; padding: 8px; text-align: right;">{line.counted_qty:,.2f}</td>
                            <td style="border: 1px solid #ddd; padding: 8px; text-align: right;">{line.discrepancy:+,.2f}</td>
                        </tr>
                    """
                
                stock_table += """
                    </tbody>
                </table>
                """
            else:
                # Summary view for large inventories
                stock_table = f"""
                <div style="background-color: #e7f3ff; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <h4 style="margin-top: 0;">Stock Summary</h4>
                    <table style="width: 100%;">
                        <tr>
                            <td style="padding: 5px 0;"><strong>Total Items Counted:</strong></td>
                            <td style="padding: 5px 0; text-align: right;">{rec.total_items_counted}</td>
                        </tr>
                        <tr>
                            <td style="padding: 5px 0;"><strong>Items with Discrepancy:</strong></td>
                            <td style="padding: 5px 0; text-align: right;">{rec.items_with_discrepancy}</td>
                        </tr>
                        <tr style="background-color: white;">
                            <td style="padding: 5px 0;"><strong>Total Stock Value:</strong></td>
                            <td style="padding: 5px 0; text-align: right; font-weight: bold;">ETB {rec.total_value:,.2f}</td>
                        </tr>
                    </table>
                    <p style="margin-bottom: 0; font-style: italic; font-size: 0.9em;">
                        (Detailed item list available in Handover Count Sheet)
                    </p>
                </div>
                """
            
            # Generate certificate HTML
            rec.certificate_html = f"""
            <div style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
                <div style="text-align: center; margin-bottom: 30px;">
                    <h2 style="color: #2c3e50; margin-bottom: 5px;">STOCK HANDOVER CERTIFICATE</h2>
                    <p style="color: #7f8c8d; margin: 0;">Reference: {rec.name}</p>
                    <p style="color: #7f8c8d; margin: 0;">Date: {rec.date.strftime('%B %d, %Y') if rec.date else ''}</p>
                </div>
                
                <div style="background-color: #f8f9fa; padding: 20px; border-left: 4px solid #3498db; margin-bottom: 20px;">
                    <h3 style="margin-top: 0; color: #2c3e50;">Custody Transfer Statement</h3>
                    <p style="line-height: 1.8; text-align: justify;">
                        I, <strong>{rec.outgoing_storekeeper_id.name}</strong>, hereby officially hand over 
                        absolute custody and responsibility of the stock items detailed below to 
                        <strong>{rec.incoming_storekeeper_id.name}</strong>, under the supervision and 
                        witnessing of <strong>{rec.witness_id.name}</strong> (PAO/Competent Authority), 
                        effective <strong>{rec.date.strftime('%B %d, %Y') if rec.date else ''}</strong>.
                    </p>
                    <p style="margin-bottom: 0;">
                        <strong>Reason for Handover:</strong> {trigger_label}
                    </p>
                </div>
                
                <div style="margin-bottom: 30px;">
                    <h3 style="color: #2c3e50;">Stock Taking Results</h3>
                    {stock_table}
                </div>
                
                <div style="margin-top: 40px; page-break-inside: avoid;">
                    <h3 style="color: #2c3e50;">Signatures and Acknowledgments</h3>
                    
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr>
                            <td style="width: 33%; padding: 20px; vertical-align: top; border-right: 1px solid #ddd;">
                                <p style="margin: 0;"><strong>Outgoing Storekeeper</strong></p>
                                <p style="margin: 5px 0 20px 0; font-size: 0.9em; color: #7f8c8d;">
                                    {rec.outgoing_storekeeper_id.name}
                                </p>
                                <div style="border-bottom: 1px solid #000; margin-bottom: 5px; height: 40px;">
                                    {('<img src="data:image/png;base64,' + rec.outgoing_signature.decode('utf-8') + '" style="max-height: 35px;"/>') if rec.outgoing_signature else ''}
                                </div>
                                <p style="margin: 0; font-size: 0.8em;">Signature & Date</p>
                            </td>
                            
                            <td style="width: 33%; padding: 20px; vertical-align: top; border-right: 1px solid #ddd;">
                                <p style="margin: 0;"><strong>Incoming Storekeeper</strong></p>
                                <p style="margin: 5px 0 20px 0; font-size: 0.9em; color: #7f8c8d;">
                                    {rec.incoming_storekeeper_id.name}
                                </p>
                                <div style="border-bottom: 1px solid #000; margin-bottom: 5px; height: 40px;">
                                    {('<img src="data:image/png;base64,' + rec.incoming_signature.decode('utf-8') + '" style="max-height: 35px;"/>') if rec.incoming_signature else ''}
                                </div>
                                <p style="margin: 0; font-size: 0.8em;">Signature & Date</p>
                            </td>
                            
                            <td style="width: 33%; padding: 20px; vertical-align: top;">
                                <p style="margin: 0;"><strong>Witness (PAO)</strong></p>
                                <p style="margin: 5px 0 20px 0; font-size: 0.9em; color: #7f8c8d;">
                                    {rec.witness_id.name}
                                </p>
                                <div style="border-bottom: 1px solid #000; margin-bottom: 5px; height: 40px;">
                                    {('<img src="data:image/png;base64,' + rec.witness_signature.decode('utf-8') + '" style="max-height: 35px;"/>') if rec.witness_signature else ''}
                                </div>
                                <p style="margin: 0; font-size: 0.8em;">Signature & Date</p>
                            </td>
                        </tr>
                    </table>
                </div>
                
                <div style="margin-top: 30px; padding: 15px; background-color: #e8f5e9; border-radius: 5px;">
                    <h4 style="margin-top: 0; color: #2e7d32;">Certificate Distribution (FR-HO-003)</h4>
                    <ul style="margin: 10px 0; padding-left: 20px;">
                        <li style="margin: 5px 0;">
                            <strong>Original Copy:</strong> PAO / Competent Authority 
                            {'<span style="color: #2e7d32;">✓ Sent</span>' if rec.pao_copy_sent else '<span style="color: #d32f2f;">⧖ Pending</span>'}
                        </li>
                        <li style="margin: 5px 0;">
                            <strong>Duplicate Copy:</strong> Incoming Storekeeper 
                            {'<span style="color: #2e7d32;">✓ Sent</span>' if rec.incoming_copy_sent else '<span style="color: #d32f2f;">⧖ Pending</span>'}
                        </li>
                        <li style="margin: 5px 0;">
                            <strong>Triplicate Copy:</strong> Outgoing Storekeeper 
                            {'<span style="color: #2e7d32;">✓ Sent</span>' if rec.outgoing_copy_sent else '<span style="color: #d32f2f;">⧖ Pending</span>'}
                        </li>
                    </ul>
                </div>
                
                <div style="margin-top: 20px; text-align: center; font-size: 0.85em; color: #7f8c8d;">
                    <p style="margin: 5px 0;">This certificate was auto-generated by Mesob IMS (AUTO-061)</p>
                    <p style="margin: 5px 0;">Compliant with FR-HO-003 Handover Certificate Requirements</p>
                </div>
            </div>
            """
            
            rec.certificate_generated = True
            _logger.info(f"AUTO-061: Certificate generated for handover {rec.name}")

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
        """AUTO-061: Finalizes handover custody and auto-distributes certificate (FR-HO-003).
        
        Three-copy distribution:
        - Original → PAO (witness)
        - Duplicate → Incoming Storekeeper
        - Triplicate → Outgoing Storekeeper
        """
        for rec in self:
            if rec.state != "signed":
                raise UserError("Handover must be signed by all parties before completion.")
            
            # Auto-distribute certificate copies
            rec._auto_distribute_certificate_copies()
            
            rec.write({
                'state': 'done',
                'distribution_date': fields.Datetime.now(),
            })
            
            _logger.info(
                f"AUTO-061: Handover {rec.name} finalized and certificate distributed to "
                f"{rec.outgoing_storekeeper_id.name} → {rec.incoming_storekeeper_id.name}, "
                f"witnessed by {rec.witness_id.name}"
            )
        
        return True
    
    # ── AUTO-061: Certificate Distribution ──────────────────────────
    
    def _auto_distribute_certificate_copies(self):
        """AUTO-061: Auto-distribute three copies of handover certificate (FR-HO-003).
        
        Original → PAO
        Duplicate → Incoming Storekeeper
        Triplicate → Outgoing Storekeeper
        """
        self.ensure_one()
        
        if not self.certificate_generated:
            _logger.warning(f"AUTO-061: Certificate not generated for handover {self.name}")
            return
        
        # Prepare certificate content for distribution
        certificate_body = self.certificate_html
        
        # Send to PAO (Original Copy)
        if self.witness_id and self.witness_id.partner_id:
            self.message_post(
                body=f"""<div style="background-color: #e8f5e9; border-left: 4px solid #2e7d32; padding: 15px;">
                    <h3>📋 AUTO-061: Handover Certificate (ORIGINAL COPY - PAO)</h3>
                    <p>This is the <strong>ORIGINAL</strong> copy of the handover certificate for your records.</p>
                    <hr/>
                    {certificate_body}
                </div>""",
                subject=f'Handover Certificate (Original) - {self.name}',
                message_type='notification',
                partner_ids=[self.witness_id.partner_id.id]
            )
            self.pao_copy_sent = True
            _logger.info(f"AUTO-061: Original certificate sent to PAO {self.witness_id.name}")
        
        # Send to Incoming Storekeeper (Duplicate Copy)
        if self.incoming_storekeeper_id and self.incoming_storekeeper_id.partner_id:
            self.message_post(
                body=f"""<div style="background-color: #e3f2fd; border-left: 4px solid #1976d2; padding: 15px;">
                    <h3>📋 AUTO-061: Handover Certificate (DUPLICATE COPY - Incoming)</h3>
                    <p>This is the <strong>DUPLICATE</strong> copy for the incoming storekeeper's records.</p>
                    <p><strong>Action Required:</strong> You are now responsible for the custody of items listed in this certificate.</p>
                    <hr/>
                    {certificate_body}
                </div>""",
                subject=f'Handover Certificate (Duplicate) - {self.name}',
                message_type='notification',
                partner_ids=[self.incoming_storekeeper_id.partner_id.id]
            )
            self.incoming_copy_sent = True
            _logger.info(f"AUTO-061: Duplicate certificate sent to incoming storekeeper {self.incoming_storekeeper_id.name}")
        
        # Send to Outgoing Storekeeper (Triplicate Copy)
        if self.outgoing_storekeeper_id and self.outgoing_storekeeper_id.partner_id:
            self.message_post(
                body=f"""<div style="background-color: #fff3e0; border-left: 4px solid #f57c00; padding: 15px;">
                    <h3>📋 AUTO-061: Handover Certificate (TRIPLICATE COPY - Outgoing)</h3>
                    <p>This is the <strong>TRIPLICATE</strong> copy for the outgoing storekeeper's records.</p>
                    <p><strong>Note:</strong> Your custody responsibility for these items has been officially transferred.</p>
                    <hr/>
                    {certificate_body}
                </div>""",
                subject=f'Handover Certificate (Triplicate) - {self.name}',
                message_type='notification',
                partner_ids=[self.outgoing_storekeeper_id.partner_id.id]
            )
            self.outgoing_copy_sent = True
            _logger.info(f"AUTO-061: Triplicate certificate sent to outgoing storekeeper {self.outgoing_storekeeper_id.name}")
        
        # Log summary
        _logger.info(
            f"AUTO-061: Certificate distribution complete for handover {self.name} - "
            f"PAO: {self.pao_copy_sent}, Incoming: {self.incoming_copy_sent}, Outgoing: {self.outgoing_copy_sent}"
        )
    
    def action_preview_certificate(self):
        """Preview generated certificate before finalization."""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Preview Handover Certificate',
            'res_model': 'mesob.stock.handover',
            'res_id': self.id,
            'view_mode': 'form',
            'view_id': self.env.ref('mesob_inventory_base.view_mesob_stock_handover_certificate_preview').id,
            'target': 'new',
        }
    
    def action_regenerate_certificate(self):
        """Manually trigger certificate regeneration."""
        self.ensure_one()
        self._compute_certificate_html()
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Certificate Regenerated',
                'message': 'Handover certificate has been regenerated with current data.',
                'type': 'success',
                'sticky': False,
            }
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

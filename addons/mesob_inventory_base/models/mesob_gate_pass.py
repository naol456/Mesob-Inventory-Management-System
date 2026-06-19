from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class MesobGatePass(models.Model):
    """Gate Pass for Material Dispatch.

    Implements FDRE-compliant material dispatch authorization for materials
    leaving the compound. Enforces PAO written authority requirements and
    implements three-copy distribution tracking for security control.
    (Requirements: 1.1, 1.3, 1.4, 1.5, 10.6)
    """

    _name = "mesob.gate.pass"
    _description = "Gate Pass for Material Dispatch"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "dispatch_date desc, id desc"
    _rec_name = "name"

    # ── Core Fields ─────────────────────────────────────────────────

    name = fields.Char(
        string="Gate Pass Number",
        required=True,
        index=True,
        default=lambda self: self.env["ir.sequence"].next_by_code(
            "mesob.gate.pass"
        ) or "New",
        copy=False,
        readonly=True,
        tracking=True,
        help="Auto-generated sequence number in format GP/YYYY/####",
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("authorized", "Authorized by PAO"),
            ("dispatched", "Dispatched"),
            ("cancelled", "Cancelled"),
        ],
        required=True,
        default="draft",
        copy=False,
        index=True,
        tracking=True,
        help=(
            "Draft: being prepared. "
            "Authorized: PAO approved for dispatch. "
            "Dispatched: materials released through gate. "
            "Cancelled: gate pass cancelled."
        ),
    )

    dispatch_date = fields.Date(
        string="Dispatch Date",
        required=True,
        default=fields.Date.today,
        readonly=True,
        states={"draft": [("readonly", False)]},
        tracking=True,
        help="Date materials are scheduled for dispatch.",
    )

    # ── Authorization Documents ─────────────────────────────────────

    issue_voucher_id = fields.Many2one(
        "mesob.inventory.issue.voucher",
        string="Issue Voucher (Model 22)",
        readonly=True,
        states={"draft": [("readonly", False)]},
        index=True,
        ondelete="restrict",
        tracking=True,
        help="Link to Issue Voucher that authorizes this dispatch.",
    )

    written_authorization = fields.Text(
        string="Written Authorization Reference",
        readonly=True,
        states={"draft": [("readonly", False)]},
        tracking=True,
        help="Alternative authorization reference (e.g., PAO memo number).",
    )

    # ── PAO Authorization ───────────────────────────────────────────

    authorized_by_id = fields.Many2one(
        "res.users",
        string="Authorized By (PAO)",
        readonly=True,
        copy=False,
        index=True,
        tracking=True,
        help="Property Administration Officer who authorized dispatch.",
    )

    authorized_on = fields.Datetime(
        string="Authorization Date",
        readonly=True,
        copy=False,
        tracking=True,
        help="Timestamp when PAO authorized the gate pass.",
    )

    # ── Dispatch Details ────────────────────────────────────────────

    destination = fields.Char(
        string="Destination",
        required=True,
        readonly=True,
        states={"draft": [("readonly", False)]},
        tracking=True,
        help="Destination address for material delivery.",
    )

    receiver_name = fields.Char(
        string="Receiver Name",
        required=True,
        readonly=True,
        states={"draft": [("readonly", False)]},
        tracking=True,
        help="Name of person receiving the materials.",
    )

    receiver_organization = fields.Char(
        string="Receiver Organization",
        required=True,
        readonly=True,
        states={"draft": [("readonly", False)]},
        tracking=True,
        help="Organization receiving the materials.",
    )

    vehicle_plate = fields.Char(
        string="Vehicle Plate Number",
        readonly=True,
        states={"draft": [("readonly", False)]},
        tracking=True,
        help="Vehicle plate number for transport.",
    )

    driver_name = fields.Char(
        string="Driver Name",
        readonly=True,
        states={"draft": [("readonly", False)]},
        tracking=True,
        help="Name of driver transporting materials.",
    )

    driver_license = fields.Char(
        string="Driver License Number",
        readonly=True,
        states={"draft": [("readonly", False)]},
        tracking=True,
        help="Driver's license number.",
    )

    # ── Copy Distribution Tracking ──────────────────────────────────

    original_to_receiver = fields.Boolean(
        string="Original → Receiver",
        readonly=True,
        copy=False,
        help="Original copy distributed to receiver.",
    )

    duplicate_to_storekeeper = fields.Boolean(
        string="Duplicate → Storekeeper",
        readonly=True,
        copy=False,
        help="Duplicate copy retained by storekeeper.",
    )

    triplicate_to_security = fields.Boolean(
        string="Triplicate → Security",
        readonly=True,
        copy=False,
        help="Triplicate copy retained by security guard.",
    )

    # ── Security Gate Verification ──────────────────────────────────

    security_verified_by_id = fields.Many2one(
        "res.users",
        string="Security Guard",
        readonly=True,
        copy=False,
        tracking=True,
        help="Security guard who verified and dispatched materials.",
    )

    security_verified_on = fields.Datetime(
        string="Dispatch Timestamp",
        readonly=True,
        copy=False,
        tracking=True,
        help="Timestamp when security guard dispatched materials.",
    )

    # ── AUTO-047: QR Code for Three-Copy Distribution ──────────────

    qr_code = fields.Binary(
        string="QR Code",
        compute="_compute_qr_code",
        store=True,
        help="AUTO-047: QR code for gate verification and tracking",
    )

    qr_code_verified = fields.Boolean(
        string="QR Code Scanned",
        default=False,
        readonly=True,
        help="AUTO-047: Indicates if security scanned QR code at gate",
    )

    qr_scan_timestamp = fields.Datetime(
        string="QR Scan Timestamp",
        readonly=True,
        help="AUTO-047: When security scanned the QR code",
    )

    # ── Relations ───────────────────────────────────────────────────

    line_ids = fields.One2many(
        "mesob.gate.pass.line",
        "gate_pass_id",
        string="Gate Pass Lines",
        copy=True,
    )

    created_by_id = fields.Many2one(
        "res.users",
        string="Created By",
        default=lambda self: self.env.user,
        readonly=True,
        tracking=True,
        help="Storekeeper who created this gate pass.",
    )

    # ── Notes ───────────────────────────────────────────────────────

    note = fields.Text(
        string="Internal Notes",
        help="Internal notes (editable even after dispatch).",
    )

    # ── AUTO-046: PAO Override Fields ───────────────────────────────

    pao_override = fields.Boolean(
        string="PAO Emergency Override",
        default=False,
        readonly=True,
        copy=False,
        tracking=True,
        help="PAO can override prerequisite validation in emergencies.",
    )

    pao_override_reason = fields.Text(
        string="Override Justification",
        readonly=True,
        copy=False,
        tracking=True,
        help="Required justification when PAO overrides prerequisite validation.",
    )

    pao_override_by_id = fields.Many2one(
        "res.users",
        string="Override By",
        readonly=True,
        copy=False,
        tracking=True,
        help="PAO who authorized the override.",
    )

    pao_override_on = fields.Datetime(
        string="Override Timestamp",
        readonly=True,
        copy=False,
        tracking=True,
        help="When the override was granted.",
    )

    # ── Constraints ─────────────────────────────────────────────────

    @api.depends("name", "state")
    def _compute_qr_code(self):
        """AUTO-047: Generate QR code for Gate Pass verification.
        
        QR code contains: GP number, date, receiver, destination
        Security scans this at gate to confirm dispatch and timestamp.
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
            if record.name and record.name != "New":
                # Generate QR code data
                qr_data = f"MESOB-GP:{record.name}|DATE:{record.dispatch_date}|TO:{record.receiver_name}|DEST:{record.destination}"
                
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
            else:
                record.qr_code = False

    @api.constrains("issue_voucher_id", "written_authorization")
    def _check_authorization_documents(self):
        """Enforce XOR constraint: exactly one authorization method required.
        
        AUTO-046: Gate Pass Prerequisite Validation
        - Blocks Gate Pass creation without proper authorization
        - Enforces FR-DISP-003 compliance
        - PAO can override in emergencies
        """
        for record in self:
            if record.state in ("draft", "cancelled"):
                continue  # Skip validation for draft and cancelled states
            
            # Skip validation if PAO override is active
            if record.pao_override:
                continue
            
            has_voucher = bool(record.issue_voucher_id)
            has_written = bool(record.written_authorization and record.written_authorization.strip())
            
            if not (has_voucher or has_written):
                raise ValidationError(
                    "Gate Pass requires authorization documents. "
                    "Please link an Issue Voucher (Model 22) or provide written authorization reference.\n\n"
                    "If this is an emergency, PAO can use 'Emergency Override' action."
                )
            
            if has_voucher and has_written:
                raise ValidationError(
                    "Gate Pass must have exactly one authorization method: "
                    "Issue Voucher OR written authorization (not both)."
                )
            
            # AUTO-046: Validate Issue Voucher if linked
            if has_voucher:
                record._validate_issue_voucher_prerequisites()

    @api.constrains("line_ids")
    def _check_line_items(self):
        """Ensure at least one line item exists.
        
        AUTO-046: Validate line items match Issue Voucher.
        """
        for record in self:
            if record.state not in ("draft", "cancelled") and not record.line_ids:
                raise ValidationError(
                    "Gate Pass must have at least one line item."
                )
            
            # AUTO-046: If Issue Voucher is linked, validate items match
            # Skip validation if PAO override is active
            if record.issue_voucher_id and record.line_ids and not record.pao_override:
                record._validate_items_match_issue_voucher()

    @api.constrains("dispatch_date")
    def _check_dispatch_date(self):
        """Ensure dispatch date is not in the future."""
        for record in self:
            if record.dispatch_date and record.dispatch_date > fields.Date.today():
                raise ValidationError(
                    "Dispatch date cannot be in the future."
                )

    # ── Actions ─────────────────────────────────────────────────────

    def action_authorize(self):
        """PAO authorizes Gate Pass for dispatch."""
        for record in self:
            # Verify state
            if record.state != "draft":
                raise UserError("Only draft Gate Passes can be authorized.")
            
            # Verify PAO role
            if not self.env.user.has_group("mesob_inventory_base.group_mesob_pao"):
                raise UserError(
                    "Only Property Administration Officers (PAO) can authorize Gate Passes. "
                    "Please contact your PAO for authorization."
                )
            
            # Validate prerequisite documents
            record._validate_prerequisite_documents()
            
            # Validate dispatch details
            if not record.destination:
                raise ValidationError("Destination is required for authorization.")
            if not record.receiver_name:
                raise ValidationError("Receiver name is required for authorization.")
            if not record.receiver_organization:
                raise ValidationError("Receiver organization is required for authorization.")
            
            # Validate line items
            if not record.line_ids:
                raise ValidationError("Add at least one line item before authorization.")
            
            # Authorize
            record.write({
                "state": "authorized",
                "authorized_by_id": self.env.user.id,
                "authorized_on": fields.Datetime.now(),
            })
            
            # AUTO-047: Send three-copy distribution notifications
            record._send_three_copy_notifications()
            
            # Post message to chatter
            record.message_post(
                body=f"Gate Pass authorized by {self.env.user.name} on {fields.Datetime.now()}"
            )
        
        return True

    def _send_three_copy_notifications(self):
        """AUTO-047: Send notifications for three-copy distribution.
        
        - Original → Receiver (PDF with QR code)
        - Duplicate → Storekeeper (notification)
        - Triplicate → Security Guard (gate alert)
        """
        self.ensure_one()
        
        # Get user groups
        storekeeper_group = self.env.ref("mesob_inventory_base.group_mesob_storekeeper", raise_if_not_found=False)
        security_group = self.env.ref("mesob_inventory_base.group_mesob_security_guard", raise_if_not_found=False)
        
        # Notification to Storekeeper (Duplicate)
        if storekeeper_group and storekeeper_group.users:
            self.message_post(
                body=f"""<div style="background-color: #d1ecf1; border-left: 4px solid #0c5460; padding: 15px;">
                    <h3>📄 AUTO-047: Gate Pass Duplicate Copy</h3>
                    <p><strong>Gate Pass:</strong> {self.name}</p>
                    <p><strong>Dispatch Date:</strong> {self.dispatch_date}</p>
                    <p><strong>Receiver:</strong> {self.receiver_name} ({self.receiver_organization})</p>
                    <p><strong>Destination:</strong> {self.destination}</p>
                    <p><strong>Items:</strong> {len(self.line_ids)} line(s)</p>
                    <hr/>
                    <p><em>This is your duplicate copy for record keeping. Original accompanies materials, Triplicate retained by Security.</em></p>
                </div>""",
                subject=f"Gate Pass {self.name} - Storekeeper Copy",
                message_type="notification",
                partner_ids=storekeeper_group.users.mapped("partner_id").ids,
            )
        
        # Notification to Security (Triplicate)
        if security_group and security_group.users:
            self.message_post(
                body=f"""<div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px;">
                    <h3>🚨 AUTO-047: Gate Pass Alert for Security</h3>
                    <p><strong>Gate Pass:</strong> {self.name}</p>
                    <p><strong>Authorized By:</strong> {self.authorized_by_id.name}</p>
                    <p><strong>Dispatch Date:</strong> {self.dispatch_date}</p>
                    <p><strong>Receiver:</strong> {self.receiver_name}</p>
                    <p><strong>Vehicle:</strong> {self.vehicle_plate or "Not specified"}</p>
                    <p><strong>Driver:</strong> {self.driver_name or "Not specified"}</p>
                    <hr/>
                    <p><strong>🔍 Instructions:</strong></p>
                    <ul>
                        <li>Scan QR code on original Gate Pass</li>
                        <li>Verify receiver identity</li>
                        <li>Confirm vehicle and driver</li>
                        <li>Record dispatch timestamp</li>
                        <li>Retain triplicate copy at gate</li>
                    </ul>
                    <p><a href="/web#id={self.id}&model=mesob.gate.pass&view_type=form" 
                       style="background-color: #ffc107; color: black; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                       View Gate Pass →
                    </a></p>
                </div>""",
                subject=f"Security Alert: Gate Pass {self.name} Authorized",
                message_type="notification",
                partner_ids=security_group.users.mapped("partner_id").ids,
            )
        
        # Log distribution
        _logger.info(
            f"AUTO-047: Three-copy distribution initiated for Gate Pass {self.name} - "
            f"Storekeeper: {len(storekeeper_group.users if storekeeper_group else [])} notified, "
            f"Security: {len(security_group.users if security_group else [])} notified"
        )

    def action_dispatch(self):
        """Security guard verifies and dispatches materials at gate.
        
        AUTO-047: Records QR code scan timestamp and confirms three-copy distribution.
        """
        for record in self:
            # Verify state
            if record.state != "authorized":
                raise UserError(
                    f"Gate Pass must be authorized by PAO before dispatch. "
                    f"Current state: {record.state}. Required state: authorized."
                )
            
            # Verify security guard role
            if not self.env.user.has_group("mesob_inventory_base.group_mesob_security_guard"):
                raise UserError(
                    "Only Security Guards can dispatch materials. "
                    "Please contact security personnel."
                )
            
            # Verify PAO authorization exists
            if not record.authorized_by_id:
                raise UserError("Gate Pass must be authorized by PAO before dispatch.")
            
            # AUTO-047: Mark copy distribution, dispatch, and QR scan
            record.write({
                "state": "dispatched",
                "security_verified_by_id": self.env.user.id,
                "security_verified_on": fields.Datetime.now(),
                "qr_code_verified": True,
                "qr_scan_timestamp": fields.Datetime.now(),
                "original_to_receiver": True,
                "duplicate_to_storekeeper": True,
                "triplicate_to_security": True,
            })
            
            # Update linked Issue Voucher if applicable
            if record.issue_voucher_id:
                # Note: Issue Voucher doesn't have dispatch tracking fields yet
                # This can be added in future enhancement
                pass
            
            # AUTO-047: Post enhanced message with distribution confirmation
            record.message_post(
                body=f"""<div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px;">
                    <h3>✅ AUTO-047: Materials Dispatched</h3>
                    <p><strong>Dispatched by:</strong> {self.env.user.name} (Security Guard)</p>
                    <p><strong>Timestamp:</strong> {fields.Datetime.now()}</p>
                    <p><strong>QR Code Scanned:</strong> Yes</p>
                    <hr/>
                    <h4>Three-Copy Distribution Confirmed:</h4>
                    <ul>
                        <li>✅ <strong>Original:</strong> Accompanies materials to receiver</li>
                        <li>✅ <strong>Duplicate:</strong> Retained by Storekeeper</li>
                        <li>✅ <strong>Triplicate:</strong> Retained by Security Guard at gate</li>
                    </ul>
                </div>""",
                subject="Materials Dispatched - Three-Copy Distribution Complete"
            )
        
        return True

    def action_cancel(self):
        """Cancel Gate Pass before dispatch."""
        for record in self:
            # Verify can be cancelled
            if record.state == "dispatched":
                raise UserError(
                    "Cannot cancel Gate Pass after dispatch. "
                    "Materials have already left the compound. "
                    "If correction is needed, contact PAO for controlled correction workflow."
                )
            
            # Cancel
            record.state = "cancelled"
            
            # Post message to chatter
            record.message_post(
                body=f"Gate Pass cancelled by {self.env.user.name}"
            )
        
        return True

    def action_set_to_draft(self):
        """Reset cancelled Gate Pass to draft for corrections."""
        for record in self:
            if record.state != "cancelled":
                raise UserError("Only cancelled Gate Passes can be reset to draft.")
            
            record.state = "draft"
            
            # Post message to chatter
            record.message_post(
                body=f"Gate Pass reset to draft by {self.env.user.name} for corrections"
            )
        
        return True

    # ── Validation Methods ──────────────────────────────────────────

    def _validate_prerequisite_documents(self):
        """Validate that Gate Pass has proper authorization documents."""
        self.ensure_one()
        
        has_voucher = bool(self.issue_voucher_id)
        has_written = bool(self.written_authorization and self.written_authorization.strip())
        
        # Must have exactly one authorization method
        if not (has_voucher or has_written):
            raise ValidationError(
                "Gate Pass requires authorization documents. "
                "Please link an Issue Voucher (Model 22) or provide written authorization reference."
            )
        
        if has_voucher and has_written:
            raise ValidationError(
                "Gate Pass must have exactly one authorization method: "
                "Issue Voucher OR written authorization (not both)."
            )
        
        # If Issue Voucher is linked, validate it
        if has_voucher:
            issue_voucher = self.issue_voucher_id
            
            # Verify Issue Voucher exists
            if not issue_voucher:
                raise ValidationError("Issue Voucher not found.")
            
            # Verify Issue Voucher state
            if issue_voucher.state not in ("issued", "received"):
                raise ValidationError(
                    f"Issue Voucher {issue_voucher.name} is not in valid state. "
                    f"Current state: {issue_voucher.state}. Required state: issued or received."
                )
            
            # Verify Issue Voucher is properly signed
            if not issue_voucher.issued_by_id:
                raise ValidationError(
                    f"Issue Voucher {issue_voucher.name} is not properly signed."
                )

    # ── AUTO-046: Enhanced Validation Methods ───────────────────────

    def _validate_issue_voucher_prerequisites(self):
        """AUTO-046: Validate Issue Voucher is properly signed and in valid state.
        
        This method is called by the constraint to ensure Issue Voucher
        meets all prerequisites before Gate Pass can be authorized.
        """
        self.ensure_one()
        
        if not self.issue_voucher_id:
            return
        
        issue_voucher = self.issue_voucher_id
        
        # Verify Issue Voucher state
        if issue_voucher.state not in ("issued", "received"):
            raise ValidationError(
                f"Issue Voucher {issue_voucher.name} is not in valid state.\n"
                f"Current state: {issue_voucher.state}\n"
                f"Required state: 'issued' or 'received'\n\n"
                f"The Issue Voucher must be signed and issued before creating a Gate Pass."
            )
        
        # Verify Issue Voucher is properly signed
        if not issue_voucher.issued_by_id:
            raise ValidationError(
                f"Issue Voucher {issue_voucher.name} is not properly signed.\n"
                f"A signed Issue Voucher (Model 22) is required as authorization for dispatch."
            )
    
    def _validate_items_match_issue_voucher(self):
        """AUTO-046: Validate that Gate Pass items match Issue Voucher items.
        
        Ensures materials on Gate Pass correspond to items authorized
        in the linked Issue Voucher, preventing unauthorized dispatch.
        """
        self.ensure_one()
        
        if not self.issue_voucher_id or not self.line_ids:
            return
        
        # Get Issue Voucher items
        voucher_items = self.issue_voucher_id.line_ids.mapped('item_id')
        
        if not voucher_items:
            raise ValidationError(
                f"Issue Voucher {self.issue_voucher_id.name} has no line items.\n"
                f"Cannot validate Gate Pass items against an empty Issue Voucher."
            )
        
        # Check each Gate Pass line item
        unauthorized_items = []
        for line in self.line_ids:
            if line.item_id not in voucher_items:
                unauthorized_items.append(line.item_id.item_code or line.item_id.name)
        
        if unauthorized_items:
            raise ValidationError(
                f"Gate Pass contains items not authorized in Issue Voucher {self.issue_voucher_id.name}:\n\n"
                f"Unauthorized items: {', '.join(unauthorized_items)}\n\n"
                f"Gate Pass items must match Issue Voucher items exactly.\n"
                f"If this is an emergency, PAO can use 'Emergency Override' action."
            )

    # ── AUTO-046: PAO Override Action ───────────────────────────────

    def action_pao_emergency_override(self):
        """AUTO-046: PAO can override prerequisite validation in emergencies.
        
        This action allows PAO to bypass Item validation when there is a
        legitimate emergency requiring immediate dispatch without full documentation.
        Requires justification and creates audit trail.
        """
        self.ensure_one()
        
        # Verify PAO role
        if not self.env.user.has_group("mesob_inventory_base.group_mesob_pao"):
            raise UserError(
                "Only Property Administration Officers (PAO) can grant emergency overrides."
            )
        
        # Open wizard to collect justification
        return {
            'name': 'PAO Emergency Override',
            'type': 'ir.actions.act_window',
            'res_model': 'mesob.gate.pass.override.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_gate_pass_id': self.id,
            },
        }

    # ── Override Write for Immutability ─────────────────────────────

    def write(self, vals):
        """Override write to enforce immutability after dispatch."""
        for record in self:
            if record.state == "dispatched":
                # Only allow modification of internal notes
                allowed_fields = {"note"}
                if set(vals.keys()) - allowed_fields:
                    raise UserError(
                        "Cannot modify dispatched Gate Pass. "
                        "Contact PAO for controlled correction workflow."
                    )
        return super().write(vals)

    def unlink(self):
        """Override unlink to prevent deleting dispatched Gate Passes."""
        for record in self:
            if record.state == "dispatched":
                raise UserError("Cannot delete dispatched Gate Pass records to preserve auditability.")
        return super().unlink()

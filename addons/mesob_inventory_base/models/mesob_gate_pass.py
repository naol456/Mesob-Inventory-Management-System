from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


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

    # ── Constraints ─────────────────────────────────────────────────

    @api.constrains("issue_voucher_id", "written_authorization")
    def _check_authorization_documents(self):
        """Enforce XOR constraint: exactly one authorization method required."""
        for record in self:
            if record.state in ("draft", "cancelled"):
                continue  # Skip validation for draft and cancelled states
            
            has_voucher = bool(record.issue_voucher_id)
            has_written = bool(record.written_authorization and record.written_authorization.strip())
            
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

    @api.constrains("line_ids")
    def _check_line_items(self):
        """Ensure at least one line item exists."""
        for record in self:
            if record.state not in ("draft", "cancelled") and not record.line_ids:
                raise ValidationError(
                    "Gate Pass must have at least one line item."
                )

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
            
            # Post message to chatter
            record.message_post(
                body=f"Gate Pass authorized by {self.env.user.name} on {fields.Datetime.now()}"
            )
        
        return True

    def action_dispatch(self):
        """Security guard verifies and dispatches materials at gate."""
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
            
            # Mark copy distribution and dispatch
            record.write({
                "state": "dispatched",
                "security_verified_by_id": self.env.user.id,
                "security_verified_on": fields.Datetime.now(),
                "original_to_receiver": True,
                "duplicate_to_storekeeper": True,
                "triplicate_to_security": True,
            })
            
            # Update linked Issue Voucher if applicable
            if record.issue_voucher_id:
                # Note: Issue Voucher doesn't have dispatch tracking fields yet
                # This can be added in future enhancement
                pass
            
            # Post message to chatter
            record.message_post(
                body=f"Materials dispatched by security guard {self.env.user.name}. "
                     f"Three-copy distribution: Original→Receiver, Duplicate→Storekeeper, Triplicate→Security."
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

    # ── Role-Based Access Control (UI Level) ────────────────────────

    @api.model
    def get_view(self, view_id=None, view_type="form", **options):
        """Hide New button for Security Guard on both list and form views.
        
        Security Guards can only dispatch authorized Gate Passes,
        not create new ones. PAO and Storekeeper can create.
        """
        result = super(MesobGatePass, self).get_view(view_id, view_type, **options)
        
        # Import lxml for XML manipulation
        from lxml import etree
        
        # Check if user is Security Guard
        is_security_guard = self.env.user.has_group("mesob_inventory_base.group_mesob_security_guard")
        
        # Hide "New" button for Security Guard in list and form views
        if is_security_guard and view_type in ("list", "form"):
            doc = etree.XML(result["arch"])
            
            # For list view, hide create button
            if view_type == "list":
                # Set create="false" on tree/list element
                for node in doc.xpath("//list | //tree"):
                    node.set("create", "false")
            
            # For form view, hide create button in breadcrumb
            elif view_type == "form":
                # Set create="false" on form element
                for node in doc.xpath("//form"):
                    node.set("create", "false")
            
            result["arch"] = etree.tostring(doc, encoding="unicode")
        
        return result

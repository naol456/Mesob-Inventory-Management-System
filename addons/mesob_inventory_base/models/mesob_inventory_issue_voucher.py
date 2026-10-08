from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
from lxml import etree


class MesobInventoryIssueVoucher(models.Model):
    """Issue Voucher (Model 22).

    Generated after requisition approval to document stock issue to departments.
    Tracks three-copy distribution and department receipt confirmation.
    (SRS: FR-ISSUE-005, FR-ISSUE-006)
    """

    _name = "mesob.inventory.issue.voucher"
    _description = "Issue Voucher (Model 22)"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "issue_date desc, id desc"

    name = fields.Char(
        string="Issue Voucher Number",
        required=True,
        index=True,
        default=lambda self: self.env["ir.sequence"].next_by_code(
            "mesob.inventory.issue.voucher"
        ) or "New",
        copy=False,
        readonly=True,
        tracking=True,
        help="Auto-generated controlled reference number for Model 22.",
    )

    # ── Linked Requisition ──────────────────────────────────────────────

    requisition_id = fields.Many2one(
        "mesob.inventory.requisition",
        string="Requisition (Model 20)",
        required=True,
        readonly=True,
        index=True,
        ondelete="restrict",
        tracking=True,
        help="The approved requisition that authorized this issue.",
    )

    requisition_name = fields.Char(
        related="requisition_id.name",
        string="Requisition Reference",
        store=True,
        readonly=True,
    )

    requesting_department_id = fields.Many2one(
        "mesob.department",
        related="requisition_id.department_id",
        string="Requesting Department",
        store=True,
        readonly=True,
    )

    # ── Assignment (User-based) ─────────────────────────────────────────

    requested_by_id = fields.Many2one(
        "res.users",
        related="requisition_id.requested_by_id",
        string="Requested By",
        store=True,
        readonly=True,
        help="User who requested these items",
    )

    assigned_to_id = fields.Many2one(
        "res.users",
        string="Assigned To",
        compute="_compute_assigned_to",
        store=True,
        readonly=True,
        help="User to whom the items are assigned",
    )

    # ── Issue Details ───────────────────────────────────────────────────

    issue_date = fields.Date(
        string="Issue Date",
        required=True,
        default=fields.Date.today,
        readonly=True,
        states={"draft": [("readonly", False)]},
        tracking=True,
    )

    issued_by_id = fields.Many2one(
        "res.users",
        string="Issued By (Storekeeper)",
        required=True,
        default=lambda self: self.env.user,
        readonly=True,
        states={"draft": [("readonly", False)]},
        tracking=True,
        help="Storekeeper who issued the materials.",
    )

    # ── Issue Lines ─────────────────────────────────────────────────────

    line_ids = fields.One2many(
        "mesob.inventory.issue.voucher.line",
        "voucher_id",
        string="Issue Lines",
        copy=True,
    )

    # ── State Machine ───────────────────────────────────────────────────

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("issued", "Issued"),
            ("received", "Received"),
            ("cancelled", "Cancelled"),
        ],
        required=True,
        default="draft",
        copy=False,
        index=True,
        tracking=True,
        help=(
            "Draft: being prepared. "
            "Issued: materials issued, awaiting confirmation. "
            "Received: confirmed receipt by requester. "
            "Cancelled: issue cancelled."
        ),
    )

    # ── Copy Distribution Tracking (FR-ISSUE-005) ───────────────────────

    original_to_stock_clerk = fields.Boolean(
        string="Original + Requisition → Stock Clerk",
        readonly=True,
        copy=False,
        help="Original copy sent to stock clerk for posting to stock records.",
    )
    duplicate_to_department = fields.Boolean(
        string="Duplicate → Requesting Department",
        readonly=True,
        copy=False,
        help="Duplicate copy sent to requesting department.",
    )
    triplicate_retained = fields.Boolean(
        string="Triplicate → Storekeeper",
        readonly=True,
        copy=False,
        help="Triplicate copy retained by storekeeper.",
    )

    # ── Receipt Confirmation (FR-ISSUE-006) ─────────────────────────────

    received_by_id = fields.Many2one(
        "res.users",
        string="Received By",
        readonly=True,
        copy=False,
        tracking=True,
        help="Department representative who confirmed receipt.",
    )
    received_on = fields.Date(
        string="Received On",
        readonly=True,
        copy=False,
        tracking=True,
    )
    quantity_verified = fields.Boolean(
        string="Quantity Verified",
        readonly=True,
        copy=False,
        help="Department confirmed quantities match requisition.",
    )
    inspection_confirmed = fields.Boolean(
        string="Inspection Confirmed",
        readonly=True,
        copy=False,
        help="Department confirmed items are in acceptable condition.",
    )
    approval_verified = fields.Boolean(
        string="Approval Verified",
        readonly=True,
        copy=False,
        help="Department confirmed requisition was properly approved.",
    )
    receipt_notes = fields.Text(
        string="Receipt Notes",
        readonly=True,
        copy=False,
        help="Any remarks from the receiving department.",
    )

    # ── Stock Integration ───────────────────────────────────────────────

    picking_id = fields.Many2one(
        "stock.picking",
        string="Stock Picking",
        readonly=True,
        copy=False,
        help="Linked stock picking for inventory movement.",
    )

    note = fields.Text(string="Internal Notes")

    # ── Computed Fields ─────────────────────────────────────────────────

    receipt_status_display = fields.Char(
        string="Receipt Status",
        compute="_compute_receipt_status_display",
        help="Shows who received the items"
    )

    @api.depends("state", "received_by_id")
    def _compute_receipt_status_display(self):
        """Display receipt status with person's name"""
        for rec in self:
            if rec.state == "received" and rec.received_by_id:
                rec.receipt_status_display = f"Received by {rec.received_by_id.name}"
            elif rec.state == "issued":
                rec.receipt_status_display = "Awaiting Receipt Confirmation"
            elif rec.state == "draft":
                rec.receipt_status_display = "Draft"
            elif rec.state == "cancelled":
                rec.receipt_status_display = "Cancelled"
            else:
                rec.receipt_status_display = rec.state.capitalize()

    @api.depends("requisition_id.requested_by_id")
    def _compute_assigned_to(self):
        """Assign items to the user who requested them"""
        for rec in self:
            rec.assigned_to_id = rec.requisition_id.requested_by_id if rec.requisition_id else False

    @api.depends("line_ids.quantity_issued", "line_ids.item_id", "assigned_to_id")
    def _compute_display_name(self):
        for rec in self:
            if rec.name and rec.requesting_department_id:
                rec.display_name = f"{rec.name} - {rec.requesting_department_id.name}"
            else:
                rec.display_name = rec.name or "New Issue Voucher"

    # ── View Customization ──────────────────────────────────────────────

    @api.model
    def get_view(self, view_id=None, view_type="form", **options):
        """Hide New button for PAO and Stock Clerk on both list and form views.
        
        Only Storekeeper can create Issue Vouchers.
        
        - list view:  create="0" removes the toolbar New button.
        - form view:  create="0" removes the New button in the breadcrumb pager.
        """
        result = super().get_view(view_id, view_type, **options)
        
        if view_type in ("list", "form"):
            user = self.env.user
            is_pao = user.has_group("mesob_inventory_base.group_mesob_pao")
            is_stock_clerk = user.has_group("mesob_inventory_base.group_mesob_stock_clerk")
            
            if is_pao or is_stock_clerk:
                arch = result.get("arch", "")
                if isinstance(arch, str):
                    arch = arch.encode("utf-8")
                root = etree.fromstring(arch)
                root.set("create", "0")
                result["arch"] = etree.tostring(root, encoding="unicode", pretty_print=False)
        
        return result

    # ── Actions ─────────────────────────────────────────────────────────

    def action_issue(self):
        """Issue materials and mark copy distribution (FR-ISSUE-005)."""
        for record in self:
            if record.state != "draft":
                raise UserError("Only draft vouchers can be issued.")
            if not record.line_ids:
                raise UserError("Add at least one line before issuing.")

            # Validate stock availability
            record._validate_stock_availability()

            # Create stock picking for inventory movement
            record._create_stock_picking()
            
            # Update bin cards for issued items
            record._update_bin_cards_on_issue()

            # Mark copy distribution
            record.write({
                "state": "issued",
                "original_to_stock_clerk": True,
                "duplicate_to_department": True,
                "triplicate_retained": True,
            })

            # Post message to chatter
            record.message_post(
                body=f"Issue Voucher {record.name} issued by {record.issued_by_id.name}. "
                     f"Copies distributed: Original→Stock Clerk, Duplicate→Department, Triplicate→Storekeeper."
            )

        return True
    
    def _update_bin_cards_on_issue(self):
        """Create bin card entries for issued items (distributed quantity)."""
        self.ensure_one()
        
        # Group items by sub-classification
        items_by_subclass = {}
        for line in self.line_ids:
            if not line.item_id or not line.item_id.sub_classification_id:
                continue
            
            sub_id = line.item_id.sub_classification_id.id
            major_id = line.item_id.classification_id.id
            
            if sub_id not in items_by_subclass:
                items_by_subclass[sub_id] = {
                    'major_id': major_id,
                    'sub_id': sub_id,
                    'quantity': 0.0
                }
            
            items_by_subclass[sub_id]['quantity'] += line.quantity_issued
        
        # Create bin card entry for each sub-classification
        BinCard = self.env['mesob.bin.card']
        uom_unit = self.env.ref('uom.product_uom_unit', raise_if_not_found=False)
        if not uom_unit:
            uom_unit = self.env['uom.uom'].search([], limit=1)
        
        for subclass_data in items_by_subclass.values():
            BinCard.create({
                'major_classification_id': subclass_data['major_id'],
                'sub_classification_id': subclass_data['sub_id'],
                'location': 'Main Store',
                'transaction_type': 'issue',
                'date': self.issue_date or fields.Date.today(),
                'quantity_received': 0.0,
                'quantity_distributed': subclass_data['quantity'],
                'reference': self.name,
                'description': f"Issue Voucher: {self.name}",
                'uom_id': uom_unit.id if uom_unit else False,
                'received_by_id': self.issued_by_id.id,
            })

    def action_confirm_receipt(self):
        """Department confirms receipt of materials (FR-ISSUE-006)."""
        return self._open_receipt_confirmation_wizard()

    def _open_receipt_confirmation_wizard(self):
        """Open wizard for department to confirm receipt."""
        self.ensure_one()
        return {
            "name": "Confirm Receipt",
            "type": "ir.actions.act_window",
            "res_model": "mesob.inventory.issue.receipt.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_voucher_id": self.id,
                "default_quantity_verified": True,
                "default_inspection_confirmed": True,
                "default_approval_verified": True,
            },
        }

    def action_cancel(self):
        """Cancel the issue voucher."""
        for record in self:
            if record.state == "received":
                raise UserError("Cannot cancel a voucher that has been received.")
            if record.picking_id and record.picking_id.state == "done":
                raise UserError(
                    "Cannot cancel: stock picking is already done. "
                    "Create a return picking instead."
                )
            record.state = "cancelled"
            if record.picking_id:
                record.picking_id.action_cancel()
        return True

    def action_set_to_draft(self):
        """Reset to draft for corrections."""
        for record in self:
            if record.state not in ("cancelled",):
                raise UserError("Only cancelled vouchers can be reset to draft.")
            record.state = "draft"
        return True

    # ── Stock Integration Methods ───────────────────────────────────────

    def _validate_stock_availability(self):
        """Validate that sufficient stock is available for issue based on bin card balances."""
        self.ensure_one()
        
        # Group items by sub-classification to check bin card balances
        items_by_subclass = {}
        for line in self.line_ids:
            if not line.item_id or not line.item_id.sub_classification_id:
                continue
            
            sub_id = line.item_id.sub_classification_id.id
            if sub_id not in items_by_subclass:
                items_by_subclass[sub_id] = {
                    'sub_classification': line.item_id.sub_classification_id,
                    'quantity': 0.0,
                    'items': []
                }
            
            items_by_subclass[sub_id]['quantity'] += line.quantity_issued
            items_by_subclass[sub_id]['items'].append(line.item_id.item_code)
        
        # Check bin card balance for each sub-classification
        BinCard = self.env['mesob.bin.card']
        for subclass_data in items_by_subclass.values():
            # Get latest bin card balance
            latest_bin_card = BinCard.search([
                ('sub_classification_id', '=', subclass_data['sub_classification'].id),
                ('location', '=', 'Main Store')
            ], order='date desc, id desc', limit=1)
            
            available_qty = latest_bin_card.balance if latest_bin_card else 0.0
            requested_qty = subclass_data['quantity']
            
            if available_qty < requested_qty:
                raise ValidationError(
                    f"Insufficient stock for {subclass_data['sub_classification'].name}. "
                    f"Available: {available_qty}, Requested: {requested_qty}\n"
                    f"Items: {', '.join(subclass_data['items'][:5])}"
                    f"{'...' if len(subclass_data['items']) > 5 else ''}"
                )
    
    def _create_product_for_item(self, item):
        """Auto-create product for inventory item."""
        # Get default product category (fallback to first available)
        default_category = self.env["product.category"].search([], limit=1)
        if not default_category:
            # Create a default category if none exists
            default_category = self.env["product.category"].create({
                "name": "Inventory Items",
            })
        
        product_vals = {
            "name": f"[{item.item_code}] {item.name}",
            "default_code": item.item_code,
            "type": "consu",  # consumable/storable product in Odoo 19
            "categ_id": default_category.id,
            "uom_id": item.uom_id.id if item.uom_id else self.env.ref("uom.product_uom_unit").id,
        }
        product = self.env["product.product"].create(product_vals)
        return product

    def _create_stock_picking(self):
        """Create stock picking for inventory movement (optional - we use bin cards)."""
        self.ensure_one()
        
        # Skip stock picking creation - we use bin cards for inventory tracking
        # This method is kept for compatibility but does nothing
        return True

    # ── Constraints ─────────────────────────────────────────────────────

    @api.constrains("requisition_id")
    def _check_requisition_approved(self):
        """Ensure requisition is approved before creating issue voucher."""
        for record in self:
            if record.requisition_id.state != "approved":
                raise ValidationError(
                    f"Cannot create issue voucher: requisition {record.requisition_id.name} "
                    f"is not approved (current state: {record.requisition_id.state})."
                )


class MesobInventoryIssueVoucherLine(models.Model):
    """Individual line item on an Issue Voucher (Model 22)."""

    _name = "mesob.inventory.issue.voucher.line"
    _description = "Issue Voucher Line"

    voucher_id = fields.Many2one(
        "mesob.inventory.issue.voucher",
        required=True,
        ondelete="cascade",
    )

    item_id = fields.Many2one(
        "mesob.inventory.item",
        string="Item",
        required=True,
    )

    quantity_issued = fields.Float(
        string="Quantity Issued",
        required=True,
        default=1.0,
    )

    uom_id = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
        help="Unit of measure for this issue line.",
    )

    note = fields.Char(string="Remarks")

    # ── Computed Fields ─────────────────────────────────────────────────

    @api.onchange("item_id")
    def _onchange_item_id(self):
        """Auto-fill UOM from item master."""
        if self.item_id and self.item_id.uom_id:
            self.uom_id = self.item_id.uom_id

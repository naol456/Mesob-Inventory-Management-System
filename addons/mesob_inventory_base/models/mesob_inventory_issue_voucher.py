from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError


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

    requesting_department = fields.Char(
        related="requisition_id.department",
        string="Requesting Department",
        store=True,
        readonly=True,
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
            ("received", "Received by Department"),
            ("cancelled", "Cancelled"),
        ],
        required=True,
        default="draft",
        copy=False,
        index=True,
        tracking=True,
        help=(
            "Draft: being prepared. "
            "Issued: materials issued, awaiting department confirmation. "
            "Received: department confirmed receipt. "
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

    @api.depends("line_ids.quantity_issued", "line_ids.item_id")
    def _compute_display_name(self):
        for rec in self:
            if rec.name and rec.requesting_department:
                rec.display_name = f"{rec.name} - {rec.requesting_department}"
            else:
                rec.display_name = rec.name or "New Issue Voucher"

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
        """Validate that sufficient stock is available for issue."""
        self.ensure_one()
        StockQuant = self.env["stock.quant"]
        
        for line in self.line_ids:
            # Auto-create product if not linked
            if not line.item_id.product_id:
                product = self._create_product_for_item(line.item_id)
                line.item_id.product_id = product
            
            # Get available quantity in stock location
            available_qty = StockQuant._get_available_quantity(
                line.item_id.product_id,
                self.env.ref("stock.stock_location_stock"),
            )
            
            if available_qty < line.quantity_issued:
                raise ValidationError(
                    f"Insufficient stock for item {line.item_id.item_code} ({line.item_id.name}). "
                    f"Available: {available_qty}, Requested: {line.quantity_issued}"
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
        """Create stock picking for inventory movement."""
        self.ensure_one()
        
        if not self.line_ids:
            return
        
        # Get or create picking type for internal transfers
        picking_type = self.env["stock.picking.type"].search([
            ("code", "=", "internal"),
            ("warehouse_id.company_id", "=", self.env.company.id),
        ], limit=1)
        
        if not picking_type:
            raise UserError(
                "No internal picking type found. Please configure warehouse settings."
            )
        
        # Create picking
        picking_vals = {
            "picking_type_id": picking_type.id,
            "location_id": self.env.ref("stock.stock_location_stock").id,
            "location_dest_id": self.env.ref("stock.stock_location_customers").id,  # Issued to department
            "origin": f"{self.requisition_id.name} / {self.name}",
            "move_ids_without_package": [],
        }
        
        # Create stock moves for each line
        for line in self.line_ids:
            if not line.item_id.product_id:
                continue
                
            move_vals = {
                "name": line.item_id.name,
                "product_id": line.item_id.product_id.id,
                "product_uom_qty": line.quantity_issued,
                "product_uom": line.uom_id.id or line.item_id.product_id.uom_id.id,
                "location_id": self.env.ref("stock.stock_location_stock").id,
                "location_dest_id": self.env.ref("stock.stock_location_customers").id,
            }
            picking_vals["move_ids_without_package"].append((0, 0, move_vals))
        
        picking = self.env["stock.picking"].create(picking_vals)
        picking.action_confirm()
        picking.action_assign()
        
        # Auto-validate the picking
        for move in picking.move_ids_without_package:
            move.quantity = move.product_uom_qty
        picking.button_validate()
        
        self.picking_id = picking.id

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

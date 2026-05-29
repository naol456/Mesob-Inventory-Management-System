from odoo import api, fields, models


class MesobInventoryBinCard(models.Model):
    """Bin Card - Quantity tracking per item (maintained by storekeeper).
    
    FR-RECARD-001: Support Bin Card per item showing quantity received,
    issued, and balance; maintained by storekeeper.
    """

    _name = "mesob.inventory.bin.card"
    _description = "Bin Card (Quantity Record)"
    _order = "item_id, date desc, id desc"
    _rec_name = "item_id"

    # ── Item Reference ──────────────────────────────────────────────
    item_id = fields.Many2one(
        "mesob.inventory.item",
        string="Stock Item",
        required=True,
        index=True,
        ondelete="restrict",
        help="The inventory item this bin card tracks.",
    )

    item_code = fields.Char(
        related="item_id.item_code",
        string="Item Code",
        store=True,
        index=True,
    )

    major_classification_id = fields.Many2one(
        related="item_id.classification_id",
        string="Major Classification",
        store=True,
        index=True,
    )

    # ── Movement Details ────────────────────────────────────────────
    date = fields.Date(
        string="Date",
        required=True,
        default=fields.Date.today,
        index=True,
        help="Date of the stock movement.",
    )

    reference = fields.Char(
        string="Reference",
        help="Document reference (Model 19, Model 22, etc.)",
    )

    movement_type = fields.Selection(
        [
            ("receipt", "Receipt"),
            ("issue", "Issue"),
            ("adjustment", "Adjustment"),
            ("opening", "Opening Balance"),
            ("stock_take", "Stock Taking Adjustment"),
            ("transfer_in", "Transfer In"),
            ("transfer_out", "Transfer Out"),
        ],
        string="Movement Type",
        required=True,
        help="Type of stock movement.",
    )

    # ── Quantities ──────────────────────────────────────────────────
    quantity_received = fields.Float(
        string="Quantity Received",
        digits="Product Unit of Measure",
        help="Quantity received (inbound movement).",
    )

    quantity_issued = fields.Float(
        string="Quantity Issued",
        digits="Product Unit of Measure",
        help="Quantity issued (outbound movement).",
    )

    quantity_balance = fields.Float(
        string="Balance",
        digits="Product Unit of Measure",
        required=True,
        help="Running balance after this movement.",
    )

    uom_id = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
        required=True,
    )

    # ── Location ────────────────────────────────────────────────────
    location_id = fields.Many2one(
        "stock.location",
        string="Storage Location",
        help="Physical location/bin where item is stored.",
    )

    # ── Responsible User ────────────────────────────────────────────
    storekeeper_id = fields.Many2one(
        "res.users",
        string="Storekeeper",
        default=lambda self: self.env.user,
        help="Storekeeper who recorded this entry.",
    )

    # ── Notes ───────────────────────────────────────────────────────
    note = fields.Text(
        string="Remarks",
        help="Additional notes about this movement.",
    )

    # ── Source Document Links ───────────────────────────────────────
    receiving_id = fields.Many2one(
        "mesob.inventory.receiving",
        string="Receiving Order",
        ondelete="set null",
    )

    stock_move_id = fields.Many2one(
        "stock.move",
        string="Stock Move",
        ondelete="set null",
        help="Link to underlying ERP stock move if applicable.",
    )

    # ── Audit Trail ─────────────────────────────────────────────────
    create_date = fields.Datetime(
        string="Created On",
        readonly=True,
    )

    create_uid = fields.Many2one(
        "res.users",
        string="Created By",
        readonly=True,
    )

    # ── Stock Taking Verification (FR-ST-008) ───────────────────────
    last_stock_take_date = fields.Date(
        string="Last Stock Take Date",
        help="Date when this item was last verified during stock taking (red-ink equivalent).",
    )

    verified_by_id = fields.Many2one(
        "res.users",
        string="Verified By",
        help="User who verified this item during stock taking.",
    )

    # ── Constraints ─────────────────────────────────────────────────
    _sql_constraints = [
        (
            "check_quantities",
            "CHECK(quantity_received >= 0 AND quantity_issued >= 0)",
            "Quantities must be non-negative.",
        ),
    ]

    # ── Methods ─────────────────────────────────────────────────────
    @api.model
    def create_bin_card_entry(
        self,
        item_id,
        movement_type,
        quantity,
        reference=None,
        location_id=None,
        receiving_id=None,
        stock_move_id=None,
        note=None,
    ):
        """Create a bin card entry and compute running balance.
        
        Args:
            item_id: ID of the inventory item
            movement_type: Type of movement (receipt, issue, etc.)
            quantity: Quantity (positive for receipt, negative for issue)
            reference: Document reference
            location_id: Storage location ID
            receiving_id: Related receiving order ID
            stock_move_id: Related stock move ID
            note: Additional remarks
            
        Returns:
            Created bin card record
        """
        item = self.env["mesob.inventory.item"].browse(item_id)
        
        # Get last balance for this item
        last_entry = self.search(
            [("item_id", "=", item_id)],
            order="date desc, id desc",
            limit=1,
        )
        previous_balance = last_entry.quantity_balance if last_entry else 0.0

        # Determine received/issued quantities
        qty_received = 0.0
        qty_issued = 0.0
        
        if movement_type in ("receipt", "transfer_in", "opening"):
            qty_received = abs(quantity)
            new_balance = previous_balance + qty_received
        elif movement_type in ("issue", "transfer_out"):
            qty_issued = abs(quantity)
            new_balance = previous_balance - qty_issued
        elif movement_type in ("adjustment", "stock_take"):
            # For adjustments, quantity is the net change
            if quantity >= 0:
                qty_received = quantity
                new_balance = previous_balance + quantity
            else:
                qty_issued = abs(quantity)
                new_balance = previous_balance - abs(quantity)
        else:
            new_balance = previous_balance

        # Create bin card entry
        vals = {
            "item_id": item_id,
            "date": fields.Date.today(),
            "reference": reference,
            "movement_type": movement_type,
            "quantity_received": qty_received,
            "quantity_issued": qty_issued,
            "quantity_balance": new_balance,
            "uom_id": item.uom_id.id,
            "location_id": location_id,
            "receiving_id": receiving_id,
            "stock_move_id": stock_move_id,
            "note": note,
        }

        return self.create(vals)

    def action_view_source_document(self):
        """Navigate to the source document (receiving, stock move, etc.)."""
        self.ensure_one()
        
        if self.receiving_id:
            return {
                "name": "Receiving Order",
                "type": "ir.actions.act_window",
                "res_model": "mesob.inventory.receiving",
                "res_id": self.receiving_id.id,
                "view_mode": "form",
                "target": "current",
            }
        elif self.stock_move_id:
            return {
                "name": "Stock Move",
                "type": "ir.actions.act_window",
                "res_model": "stock.move",
                "res_id": self.stock_move_id.id,
                "view_mode": "form",
                "target": "current",
            }

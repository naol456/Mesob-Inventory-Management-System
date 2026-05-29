from odoo import api, fields, models


class MesobInventoryStockRecordCard(models.Model):
    """Stock Record Card - Quantity and value tracking (maintained by stock clerk).
    
    FR-RECARD-002: Support Stock Record Card per item, maintained by stock clerk,
    including quantity, unit price, total value for receipts/issues/balance.
    FR-RECARD-003: Organized by classification/coding.
    FR-VAL-001: FIFO valuation for costing of issues and ending balance.
    """

    _name = "mesob.inventory.stock.record.card"
    _description = "Stock Record Card (Quantity + Value Record)"
    _order = "item_id, date desc, id desc"
    _rec_name = "item_id"

    # ── Item Reference ──────────────────────────────────────────────
    item_id = fields.Many2one(
        "mesob.inventory.item",
        string="Stock Item",
        required=True,
        index=True,
        ondelete="restrict",
        help="The inventory item this stock record card tracks.",
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

    classification_code = fields.Char(
        related="item_id.classification_id.code",
        string="Classification Code",
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

    # ── Receipt Columns ─────────────────────────────────────────────
    receipt_quantity = fields.Float(
        string="Receipt Qty",
        digits="Product Unit of Measure",
        help="Quantity received.",
    )

    receipt_unit_price = fields.Monetary(
        string="Receipt Unit Price",
        currency_field="currency_id",
        help="Unit price for received items (including freight, duties, etc.).",
    )

    receipt_total_value = fields.Monetary(
        string="Receipt Total Value",
        currency_field="currency_id",
        compute="_compute_receipt_total",
        store=True,
        help="Total value of receipt (quantity × unit price).",
    )

    # ── Issue Columns ───────────────────────────────────────────────
    issue_quantity = fields.Float(
        string="Issue Qty",
        digits="Product Unit of Measure",
        help="Quantity issued.",
    )

    issue_unit_price = fields.Monetary(
        string="Issue Unit Price",
        currency_field="currency_id",
        help="Unit price for issued items (FIFO costing).",
    )

    issue_total_value = fields.Monetary(
        string="Issue Total Value",
        currency_field="currency_id",
        compute="_compute_issue_total",
        store=True,
        help="Total value of issue (quantity × unit price).",
    )

    # ── Balance Columns ─────────────────────────────────────────────
    balance_quantity = fields.Float(
        string="Balance Qty",
        digits="Product Unit of Measure",
        required=True,
        help="Running quantity balance after this movement.",
    )

    balance_unit_price = fields.Monetary(
        string="Balance Unit Price",
        currency_field="currency_id",
        help="Weighted average unit price of remaining balance.",
    )

    balance_total_value = fields.Monetary(
        string="Balance Total Value",
        currency_field="currency_id",
        required=True,
        help="Total value of remaining balance.",
    )

    # ── Unit of Measure & Currency ──────────────────────────────────
    uom_id = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
        required=True,
    )

    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        required=True,
        default=lambda self: self.env.company.currency_id,
    )

    # ── Responsible User ────────────────────────────────────────────
    stock_clerk_id = fields.Many2one(
        "res.users",
        string="Stock Clerk",
        default=lambda self: self.env.user,
        help="Stock clerk who recorded this entry.",
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

    # ── FIFO Layers (for proper FIFO costing) ──────────────────────
    fifo_layer_ids = fields.One2many(
        "mesob.inventory.fifo.layer",
        "stock_record_card_id",
        string="FIFO Layers",
        help="FIFO cost layers for this entry.",
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

    # ── Computed Fields ─────────────────────────────────────────────
    @api.depends("receipt_quantity", "receipt_unit_price")
    def _compute_receipt_total(self):
        for record in self:
            record.receipt_total_value = (
                record.receipt_quantity * record.receipt_unit_price
            )

    @api.depends("issue_quantity", "issue_unit_price")
    def _compute_issue_total(self):
        for record in self:
            record.issue_total_value = record.issue_quantity * record.issue_unit_price

    # ── Constraints ─────────────────────────────────────────────────
    _sql_constraints = [
        (
            "check_quantities",
            "CHECK(receipt_quantity >= 0 AND issue_quantity >= 0 AND balance_quantity >= 0)",
            "Quantities must be non-negative.",
        ),
        (
            "check_values",
            "CHECK(receipt_total_value >= 0 AND issue_total_value >= 0 AND balance_total_value >= 0)",
            "Values must be non-negative.",
        ),
    ]

    # ── Methods ─────────────────────────────────────────────────────
    @api.model
    def create_stock_record_entry(
        self,
        item_id,
        movement_type,
        quantity,
        unit_price=0.0,
        reference=None,
        receiving_id=None,
        issue_voucher_id=None,
        stock_move_id=None,
        note=None,
    ):
        """Create a stock record card entry with FIFO valuation.
        
        Args:
            item_id: ID of the inventory item
            movement_type: Type of movement (receipt, issue, etc.)
            quantity: Quantity (positive for receipt, negative for issue)
            unit_price: Unit price (for receipts; issues use FIFO)
            reference: Document reference
            receiving_id: Related receiving order ID
            issue_voucher_id: Related issue voucher ID
            stock_move_id: Related stock move ID
            note: Additional remarks
            
        Returns:
            Created stock record card record
        """
        item = self.env["mesob.inventory.item"].browse(item_id)
        
        # Get last balance for this item
        last_entry = self.search(
            [("item_id", "=", item_id)],
            order="date desc, id desc",
            limit=1,
        )
        previous_qty = last_entry.balance_quantity if last_entry else 0.0
        previous_value = last_entry.balance_total_value if last_entry else 0.0

        # Initialize values
        receipt_qty = 0.0
        receipt_price = 0.0
        receipt_value = 0.0
        issue_qty = 0.0
        issue_price = 0.0
        issue_value = 0.0

        # Process based on movement type
        if movement_type in ("receipt", "transfer_in", "opening"):
            receipt_qty = abs(quantity)
            receipt_price = unit_price
            receipt_value = receipt_qty * receipt_price
            new_qty = previous_qty + receipt_qty
            new_value = previous_value + receipt_value
            
        elif movement_type in ("issue", "transfer_out"):
            issue_qty = abs(quantity)
            # Use FIFO to calculate issue cost
            issue_price, issue_value = self._calculate_fifo_issue_cost(
                item_id, issue_qty
            )
            new_qty = previous_qty - issue_qty
            new_value = previous_value - issue_value
            
        elif movement_type in ("adjustment", "stock_take"):
            if quantity >= 0:
                receipt_qty = quantity
                receipt_price = unit_price
                receipt_value = receipt_qty * receipt_price
                new_qty = previous_qty + quantity
                new_value = previous_value + receipt_value
            else:
                issue_qty = abs(quantity)
                issue_price, issue_value = self._calculate_fifo_issue_cost(
                    item_id, issue_qty
                )
                new_qty = previous_qty - issue_qty
                new_value = previous_value - issue_value
        else:
            new_qty = previous_qty
            new_value = previous_value

        # Calculate balance unit price
        balance_unit_price = new_value / new_qty if new_qty > 0 else 0.0

        # Create stock record card entry
        vals = {
            "item_id": item_id,
            "date": fields.Date.today(),
            "reference": reference,
            "movement_type": movement_type,
            "receipt_quantity": receipt_qty,
            "receipt_unit_price": receipt_price,
            "issue_quantity": issue_qty,
            "issue_unit_price": issue_price,
            "balance_quantity": new_qty,
            "balance_unit_price": balance_unit_price,
            "balance_total_value": new_value,
            "uom_id": item.uom_id.id,
            "receiving_id": receiving_id,
            "issue_voucher_id": issue_voucher_id,
            "stock_move_id": stock_move_id,
            "note": note,
        }

        record = self.create(vals)
        
        # Update FIFO layers
        if movement_type in ("receipt", "transfer_in", "opening"):
            self._create_fifo_layer(record, receipt_qty, receipt_price)
        elif movement_type in ("issue", "transfer_out"):
            self._consume_fifo_layers(item_id, issue_qty)

        return record

    def _calculate_fifo_issue_cost(self, item_id, quantity):
        """Calculate the cost of issuing quantity using FIFO method.
        
        Returns:
            tuple: (average_unit_price, total_value)
        """
        FifoLayer = self.env["mesob.inventory.fifo.layer"]
        
        # Get available FIFO layers ordered by date (FIFO)
        layers = FifoLayer.search(
            [
                ("item_id", "=", item_id),
                ("remaining_quantity", ">", 0),
            ],
            order="date asc, id asc",
        )

        total_value = 0.0
        remaining_to_issue = quantity

        for layer in layers:
            if remaining_to_issue <= 0:
                break
                
            qty_from_layer = min(layer.remaining_quantity, remaining_to_issue)
            value_from_layer = qty_from_layer * layer.unit_price
            
            total_value += value_from_layer
            remaining_to_issue -= qty_from_layer

        # Calculate average unit price
        avg_unit_price = total_value / quantity if quantity > 0 else 0.0
        
        return avg_unit_price, total_value

    def _create_fifo_layer(self, record, quantity, unit_price):
        """Create a new FIFO layer for a receipt."""
        self.env["mesob.inventory.fifo.layer"].create({
            "item_id": record.item_id.id,
            "stock_record_card_id": record.id,
            "date": record.date,
            "quantity": quantity,
            "remaining_quantity": quantity,
            "unit_price": unit_price,
            "reference": record.reference,
        })

    def _consume_fifo_layers(self, item_id, quantity):
        """Consume FIFO layers for an issue using FIFO method."""
        FifoLayer = self.env["mesob.inventory.fifo.layer"]
        
        layers = FifoLayer.search(
            [
                ("item_id", "=", item_id),
                ("remaining_quantity", ">", 0),
            ],
            order="date asc, id asc",
        )

        remaining_to_consume = quantity

        for layer in layers:
            if remaining_to_consume <= 0:
                break
                
            qty_to_consume = min(layer.remaining_quantity, remaining_to_consume)
            layer.remaining_quantity -= qty_to_consume
            remaining_to_consume -= qty_to_consume

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

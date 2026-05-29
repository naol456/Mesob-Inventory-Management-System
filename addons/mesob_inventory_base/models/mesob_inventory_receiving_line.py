from odoo import api, fields, models
from odoo.exceptions import ValidationError


class MesobInventoryReceivingLine(models.Model):
    """Individual line item on a Receiving Order.

    Each line references an inventory item and tracks expected,
    received, accepted, and rejected quantities with rejection
    reasons for the inspection workflow.
    (SRS: FR-REC-003, FR-REC-009)
    """

    _name = "mesob.inventory.receiving.line"
    _description = "Receiving Order Line"

    receiving_id = fields.Many2one(
        "mesob.inventory.receiving",
        required=True,
        ondelete="cascade",
    )
    
    # Related field to access parent state
    state = fields.Selection(
        related="receiving_id.state",
        string="Status",
        store=False,
        readonly=True,
    )

    item_id = fields.Many2one(
        "mesob.inventory.item",
        string="Item",
        help="Stock item being received.",
    )

    # ── Auto-Generation Fields ─────────────────────────────────────
    major_classification_id = fields.Many2one(
        "mesob.inventory.major.classification",
        string="Major Classification",
        help="Major classification for auto-generating items.",
    )

    sub_classification_id = fields.Many2one(
        "mesob.inventory.sub.classification",
        string="Sub Classification",
        help="Sub classification for auto-generating items.",
    )

    auto_generate_items = fields.Boolean(
        string="Auto-Generate Items",
        default=False,
        help="If enabled, system will automatically generate item codes during receiving.",
    )

    generated_item_ids = fields.Many2many(
        "mesob.inventory.item",
        "mesob_receiving_line_item_rel",
        "receiving_line_id",
        "item_id",
        string="Generated Items",
        help="Items automatically generated from this receiving line.",
    )

    generated_item_count = fields.Integer(
        string="Generated Items",
        compute="_compute_generated_item_count",
    )

    description = fields.Char(
        string="Description",
        help="Description of the item (for items not yet coded).",
    )

    qty_expected = fields.Float(
        string="Qty Expected",
        default=0.0,
        help="Quantity per purchase order or packing slip.",
    )

    qty_received = fields.Float(
        string="Qty Received",
        default=0.0,
        help="Actual quantity received at unloading.",
    )

    qty_accepted = fields.Float(
        string="Qty Accepted",
        default=0.0,
        help="Quantity passing inspection (for Model 19).",
    )

    qty_rejected = fields.Float(
        string="Qty Rejected",
        default=0.0,
        help="Quantity failing inspection (for DSR).",
    )

    uom_id = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
    )

    unit_price = fields.Float(
        string="Unit Price",
        default=0.0,
        help="Unit price for stock valuation.",
    )

    total_price = fields.Float(
        string="Total Price",
        compute="_compute_total_price",
        store=True,
    )

    # ── Rejection Details (FR-REC-009) ─────────────────────────────
    rejection_reason = fields.Selection(
        [
            ("damaged", "Damaged"),
            ("shortage", "Shortage"),
            ("overage", "Overage"),
            ("wrong_quality", "Not Right Quality"),
        ],
        string="Rejection Reason",
        help="Type of discrepancy found during inspection (FR-REC-009).",
    )

    rejection_notes = fields.Text(
        string="Rejection Notes",
        help="Detailed description of the rejection reason.",
    )

    # ── Computed ───────────────────────────────────────────────────

    @api.depends("qty_accepted", "unit_price")
    def _compute_total_price(self):
        for line in self:
            line.total_price = line.qty_accepted * line.unit_price

    def _compute_generated_item_count(self):
        """Count generated items."""
        for line in self:
            line.generated_item_count = len(line.generated_item_ids)

    # ── Validation ─────────────────────────────────────────────────

    @api.constrains("qty_accepted", "qty_rejected", "qty_received")
    def _check_quantities(self):
        for line in self:
            if line.qty_accepted < 0 or line.qty_rejected < 0:
                raise ValidationError(
                    "Accepted and rejected quantities cannot be negative."
                )
            if line.qty_received < 0:
                raise ValidationError(
                    "Received quantity cannot be negative."
                )
            # Allow accepted + rejected to exceed received (will auto-adjust received)
            # This makes the workflow more flexible

    @api.onchange("item_id")
    def _onchange_item_id(self):
        """Auto-fill description and UoM from item master."""
        if self.item_id:
            if not self.description:
                self.description = self.item_id.name
            if not self.uom_id and self.item_id.uom_id:
                self.uom_id = self.item_id.uom_id

    @api.onchange("major_classification_id")
    def _onchange_major_classification(self):
        """Filter sub classifications when major classification changes."""
        # Clear sub classification if it doesn't belong to the new major
        if self.sub_classification_id and self.major_classification_id:
            if self.sub_classification_id.major_classification_id != self.major_classification_id:
                self.sub_classification_id = False
        
        # Return domain to filter sub classifications
        if self.major_classification_id:
            return {
                'domain': {
                    'sub_classification_id': [
                        ('major_classification_id', '=', self.major_classification_id.id),
                        ('active', '=', True)
                    ]
                }
            }
        else:
            # No major selected - hide all sub classifications
            return {
                'domain': {
                    'sub_classification_id': [('id', '=', False)]
                }
            }

    @api.onchange("qty_received")
    def _onchange_qty_received(self):
        """Auto-fill qty_accepted when qty_received is entered."""
        if self.qty_received > 0 and self.qty_accepted == 0 and self.qty_rejected == 0:
            # Auto-accept all received items by default
            self.qty_accepted = self.qty_received

    @api.onchange("qty_expected")
    def _onchange_qty_expected(self):
        """Auto-fill qty_received and qty_accepted with expected quantity."""
        if self.qty_expected > 0:
            if self.qty_received == 0:
                self.qty_received = self.qty_expected
            if self.qty_accepted == 0 and self.qty_rejected == 0:
                self.qty_accepted = self.qty_expected
    
    @api.onchange("qty_accepted")
    def _onchange_qty_accepted(self):
        """Auto-calculate rejected quantity when accepted quantity is entered."""
        if self.qty_accepted > 0 and self.qty_received > 0:
            # Calculate rejected as: received - accepted
            calculated_rejected = self.qty_received - self.qty_accepted
            if calculated_rejected >= 0:
                self.qty_rejected = calculated_rejected
            else:
                # If accepted > received, adjust received to match
                self.qty_received = self.qty_accepted
                self.qty_rejected = 0.0
    
    @api.onchange("qty_accepted", "qty_rejected")
    def _onchange_accepted_rejected(self):
        """Auto-adjust qty_received when accepted/rejected are changed."""
        if self.qty_accepted > 0 or self.qty_rejected > 0:
            total = self.qty_accepted + self.qty_rejected
            if total > self.qty_received:
                self.qty_received = total

    # ── Item Code Generation ───────────────────────────────────────

    def generate_item_code(self, major_code, sub_code):
        """Generate unique item code in format MAJOR-SUB-SPECIFIC.

        Args:
            major_code (str): 4-digit major classification code
            sub_code (str): 3-digit sub classification code

        Returns:
            str: Generated item code (e.g., "3345-456-001")

        Raises:
            ValidationError: If code format is invalid
        """
        # Get next specific code from sequence tracker
        sequence_model = self.env['mesob.item.code.sequence']
        specific_code = sequence_model.get_next_specific_code(major_code, sub_code)

        # Format as MAJOR-SUB-SPECIFIC
        item_code = f"{major_code}-{sub_code}-{specific_code}"

        # Validate format
        import re
        if not re.match(r'^\d{4}-\d{3}-\d{3}$', item_code):
            raise ValidationError(
                f"Generated item code does not match required format. Got: {item_code}"
            )

        return item_code

    def generate_items_for_receiving(self):
        """Generate multiple item records with auto-incremented codes.

        This method creates individual item records for each unit in qty_accepted,
        automatically generating unique sequential codes and creating corresponding
        bin card and stock record entries.

        Returns:
            list: IDs of created items

        Raises:
            ValidationError: If required fields are missing or invalid
        """
        self.ensure_one()

        # Validation
        if not self.auto_generate_items:
            return []

        if not self.major_classification_id:
            raise ValidationError("Major Classification is required for auto-generation.")

        if not self.sub_classification_id:
            raise ValidationError("Sub Classification is required for auto-generation.")

        if self.qty_accepted <= 0:
            raise ValidationError("Accepted quantity must be greater than zero.")

        if self.unit_price < 0:
            raise ValidationError("Unit price cannot be negative.")

        if not self.uom_id:
            raise ValidationError("Unit of Measure is required for auto-generation.")

        # Extract codes
        major_code = self.major_classification_id.code
        sub_code = self.sub_classification_id.code
        quantity = int(self.qty_accepted)

        # Reference data
        reference = self.receiving_id.name or "Receiving"
        date = self.receiving_id.received_date or fields.Date.today()

        created_item_ids = []

        try:
            # Generate items in a loop
            for i in range(quantity):
                # Generate unique item code
                item_code = self.generate_item_code(major_code, sub_code)

                # Create item record
                item = self.env['mesob.inventory.item'].create({
                    'item_code': item_code,
                    'classification_id': self.major_classification_id.id,
                    'sub_classification_id': self.sub_classification_id.id,
                    'uom_id': self.uom_id.id,
                    'name': self.description or f"Item {item_code}",
                    'active': True,
                })

                created_item_ids.append(item.id)

                # Create bin card entry
                self.create_bin_card_for_item(item.id, reference, date)

                # Create stock record entry
                self.create_stock_record_for_item(item.id, reference, date)

            # Link generated items to receiving line
            self.generated_item_ids = [(6, 0, created_item_ids)]

            return created_item_ids

        except Exception as e:
            # Rollback handled by Odoo transaction management
            raise ValidationError(
                f"Failed to generate items: {str(e)}"
            )

    def create_bin_card_for_item(self, item_id, reference, date):
        """Create bin card entry for received item.

        Args:
            item_id (int): ID of the inventory item
            reference (str): Receiving document reference
            date (date): Received date
        """
        # Get previous balance
        previous_entries = self.env['mesob.bin.card'].search(
            [('item_id', '=', item_id)],
            order='transaction_date desc, id desc',
            limit=1
        )
        previous_balance = previous_entries[0].balance if previous_entries else 0.0

        # Create bin card entry
        self.env['mesob.bin.card'].create({
            'item_id': item_id,
            'transaction_type': 'receipt',
            'transaction_date': date,
            'quantity_in': 1.0,
            'quantity_out': 0.0,
            'balance': previous_balance + 1.0,
            'reference': reference,
        })

    def create_stock_record_for_item(self, item_id, reference, date):
        """Create stock record card entry for received item.

        Args:
            item_id (int): ID of the inventory item
            reference (str): Receiving document reference
            date (date): Received date
        """
        # Get previous balance value
        previous_entries = self.env['mesob.stock.record.card'].search(
            [('item_id', '=', item_id)],
            order='transaction_date desc, id desc',
            limit=1
        )
        previous_balance_value = previous_entries[0].balance_value if previous_entries else 0.0

        total_cost_in = 1.0 * self.unit_price

        # Create stock record entry
        stock_record = self.env['mesob.stock.record.card'].create({
            'item_id': item_id,
            'transaction_type': 'receipt',
            'transaction_date': date,
            'quantity_in': 1.0,
            'quantity_out': 0.0,
            'unit_cost': self.unit_price,
            'total_cost_in': total_cost_in,
            'total_cost_out': 0.0,
            'balance_value': previous_balance_value + total_cost_in,
            'reference': reference,
        })

        # Create FIFO layer
        self.create_fifo_layer_for_receipt(stock_record.id, item_id, 1.0, self.unit_price)

    def create_fifo_layer_for_receipt(self, stock_record_id, item_id, quantity, unit_cost):
        """Create FIFO layer for receipt transaction.

        Args:
            stock_record_id (int): ID of the stock record entry
            item_id (int): ID of the inventory item
            quantity (float): Quantity received
            unit_cost (float): Unit cost
        """
        self.env['mesob.stock.fifo.layer'].create({
            'stock_record_id': stock_record_id,
            'item_id': item_id,
            'quantity': quantity,
            'quantity_remaining': quantity,
            'unit_cost': unit_cost,
            'total_cost': quantity * unit_cost,
        })

    def action_view_generated_items(self):
        """Open list of generated items."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Generated Items — {self.receiving_id.name}",
            "res_model": "mesob.inventory.item",
            "view_mode": "list,form",
            "domain": [("id", "in", self.generated_item_ids.ids)],
            "context": {"create": False},
        }

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

    name = fields.Char(
        string="Line Reference",
        compute="_compute_name",
        store=True,
        help="Display name for the receiving line"
    )

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
    
    # Related field for easy access to item code
    item_code = fields.Char(
        related="item_id.item_code",
        string="Item Code",
        store=True,
        readonly=True,
        help="Item code from the linked inventory item"
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

    # ── AUTO-039: Inspection Checklist Fields (FR-REC-003) ─────────
    quality_specifications = fields.Text(
        string="Quality Specifications",
        help="AUTO-039: Technical specifications from PO/tender for inspection reference (FR-PROC-009)",
    )
    
    # Acceptance criteria checkboxes (standard inspection points)
    check_quantity_match = fields.Boolean(
        string="✓ Quantity Matches PO",
        default=False,
        help="AUTO-039: Verify received quantity matches purchase order",
    )
    
    check_quality_standard = fields.Boolean(
        string="✓ Quality Meets Specifications",
        default=False,
        help="AUTO-039: Verify item quality meets technical specifications",
    )
    
    check_packaging_intact = fields.Boolean(
        string="✓ Packaging Intact",
        default=False,
        help="AUTO-039: Verify packaging is undamaged and proper",
    )
    
    check_documentation_complete = fields.Boolean(
        string="✓ Documentation Complete",
        default=False,
        help="AUTO-039: Verify all required documents received (invoice, packing slip, certificates)",
    )
    
    check_expiry_date = fields.Boolean(
        string="✓ Expiry Date Valid (if applicable)",
        default=False,
        help="AUTO-039: Verify expiry dates are acceptable for perishable items",
    )
    
    inspection_notes = fields.Text(
        string="Inspector's Notes",
        help="AUTO-039: Additional observations during physical inspection",
    )
    
    inspection_passed = fields.Boolean(
        string="All Checks Passed",
        compute="_compute_inspection_passed",
        store=True,
        help="AUTO-039: Auto-computed based on all checkboxes",
    )

    # ── Computed ───────────────────────────────────────────────────

    @api.depends("item_id", "major_classification_id", "sub_classification_id", "description")
    def _compute_name(self):
        """Compute display name for the receiving line."""
        for line in self:
            if line.item_id:
                line.name = f"{line.item_id.item_code} - {line.item_id.name}"
            elif line.major_classification_id and line.sub_classification_id:
                line.name = f"{line.major_classification_id.code}-{line.sub_classification_id.code}: {line.description or 'New Item'}"
            elif line.description:
                line.name = line.description
            else:
                line.name = "Receiving Line"

    @api.depends("qty_accepted", "unit_price")
    def _compute_total_price(self):
        for line in self:
            line.total_price = line.qty_accepted * line.unit_price

    def _compute_generated_item_count(self):
        """Count generated items."""
        for line in self:
            line.generated_item_count = len(line.generated_item_ids)
    
    @api.depends('check_quantity_match', 'check_quality_standard', 'check_packaging_intact', 
                 'check_documentation_complete', 'check_expiry_date')
    def _compute_inspection_passed(self):
        """AUTO-039: Compute if all required inspection checks are passed."""
        for line in self:
            # All mandatory checks must be True
            line.inspection_passed = (
                line.check_quantity_match and
                line.check_quality_standard and
                line.check_packaging_intact and
                line.check_documentation_complete and
                line.check_expiry_date
            )

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
        """Auto-fill description from item master."""
        if self.item_id:
            if not self.description:
                self.description = self.item_id.name

    @api.onchange("major_classification_id")
    def _onchange_major_classification(self):
        """Filter sub classifications when major classification changes."""
        # Clear sub classification if it doesn't belong to the new major
        if self.sub_classification_id and self.major_classification_id:
            if self.sub_classification_id.major_classification_id != self.major_classification_id:
                self.sub_classification_id = False
        
        # Auto-enable generation if major is selected
        if self.major_classification_id:
            self.auto_generate_items = True
        else:
            self.auto_generate_items = False
        
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

    @api.onchange("sub_classification_id")
    def _onchange_sub_classification(self):
        """Auto-enable generation when sub is selected."""
        if self.sub_classification_id:
            self.auto_generate_items = True

    @api.onchange("qty_received")
    def _onchange_qty_received(self):
        """Auto-fill qty_accepted when qty_received is entered."""
        # Removed auto-fill - let user enter manually
        pass

    @api.onchange("qty_expected")
    def _onchange_qty_expected(self):
        """Auto-fill qty_received and qty_accepted with expected quantity."""
        # Removed auto-fill - let user enter manually
        pass
    
    @api.onchange("qty_accepted")
    def _onchange_qty_accepted(self):
        """Auto-calculate rejected quantity when accepted quantity is entered."""
        if self.qty_received > 0 and self.qty_accepted >= 0:
            # Calculate rejected as: received - accepted
            self.qty_rejected = self.qty_received - self.qty_accepted
    
    @api.onchange("qty_accepted", "qty_rejected")
    def _onchange_accepted_rejected(self):
        """Auto-adjust qty_received when accepted/rejected are changed."""
        # Removed auto-adjustment - let inspector enter manually
        pass

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
            if self.item_id and self.qty_accepted > 0:
                reference = self.receiving_id.name or "Receiving"
                date = self.receiving_id.received_date or fields.Date.today()
                quantity = self.qty_accepted
                
                # Create aggregated bin card entry ONCE for the entire quantity
                self.create_bin_card_for_receiving(
                    self.item_id.classification_id.id,
                    self.item_id.sub_classification_id.id,
                    quantity,
                    reference,
                    date
                )
                
                # Create stock record entry once for the entire quantity
                self.create_stock_record_for_item(self.item_id.id, reference, date, quantity)
            return []

        if not self.major_classification_id:
            raise ValidationError("Major Classification is required for auto-generation.")

        if not self.sub_classification_id:
            raise ValidationError("Sub Classification is required for auto-generation.")

        if self.qty_accepted <= 0:
            raise ValidationError("Accepted quantity must be greater than zero.")

        if self.unit_price < 0:
            raise ValidationError("Unit price cannot be negative.")

        # Extract codes
        major_code = self.major_classification_id.code
        sub_code = self.sub_classification_id.code
        quantity = int(self.qty_accepted)

        # Reference data
        reference = self.receiving_id.name or "Receiving"
        date = self.receiving_id.received_date or fields.Date.today()

        created_item_ids = []

        try:
            # Create aggregated bin card entry ONCE for the entire quantity
            self.create_bin_card_for_receiving(
                self.major_classification_id.id,
                self.sub_classification_id.id,
                quantity,
                reference,
                date
            )

            # Check if this sub-classification is a Fixed Asset
            if self.sub_classification_id.is_fixed_asset:
                # FIXED ASSET: Generate individual items
                for i in range(quantity):
                    # Generate unique item code
                    item_code = self.generate_item_code(major_code, sub_code)

                    # Create item record
                    item = self.env['mesob.inventory.item'].create({
                        'item_code': item_code,
                        'classification_id': self.major_classification_id.id,
                        'sub_classification_id': self.sub_classification_id.id,
                        'uom_id': self.uom_id.id if self.uom_id else False,
                        'name': self.description or f"Item {item_code}",
                        'active': True,
                    })

                    created_item_ids.append(item.id)

                    # Create stock record entry per item for individual tracking
                    self.create_stock_record_for_item(item.id, reference, date, 1.0)

                # Link generated items to receiving line
                self.generated_item_ids = [(6, 0, created_item_ids)]
            else:
                # NON-FIXED ASSET (CONSUMABLE): Do NOT create individual item records.
                # Instead, find if there is an existing item record for this Sub-Classification,
                # or create ONE master item record for this Sub-Classification if none exists yet.
                master_item = self.env['mesob.inventory.item'].search([
                    ('sub_classification_id', '=', self.sub_classification_id.id),
                    ('active', '=', True)
                ], limit=1)
                
                if not master_item:
                    # Create ONE master item record for this Sub-Classification (code suffix "-001")
                    item_code = f"{major_code}-{sub_code}-001"
                    master_item = self.env['mesob.inventory.item'].create({
                        'item_code': item_code,
                        'classification_id': self.major_classification_id.id,
                        'sub_classification_id': self.sub_classification_id.id,
                        'uom_id': self.uom_id.id if self.uom_id else False,
                        'name': self.description or self.sub_classification_id.name,
                        'active': True,
                    })
                
                # Create ONE stock record entry for the entire quantity under the master item
                self.create_stock_record_for_item(master_item.id, reference, date, quantity)
                
                created_item_ids.append(master_item.id)
                self.generated_item_ids = [(6, 0, created_item_ids)]

            return created_item_ids

        except Exception as e:
            # Rollback handled by Odoo transaction management
            raise ValidationError(
                f"Failed to generate items: {str(e)}"
            )

    def create_bin_card_for_receiving(self, major_classification_id, sub_classification_id, quantity, reference, date):
        """Create or update aggregated bin card entry at sub-classification level.

        Instead of creating individual bin cards per item, this creates one entry
        per sub-classification showing total received quantity.

        Args:
            major_classification_id (int): ID of major classification
            sub_classification_id (int): ID of sub classification
            quantity (float): Quantity received
            reference (str): Receiving document reference
            date (date): Received date
        """
        # Get default UoM (unit)
        uom_unit = self.env.ref('uom.product_uom_unit', raise_if_not_found=False)
        if not uom_unit:
            # Fallback: get any UoM
            uom_unit = self.env['uom.uom'].search([], limit=1)
        
        # Get default location
        default_location = 'Main Store'
        
        # Create bin card entry (aggregated by sub-classification)
        self.env['mesob.bin.card'].create({
            'major_classification_id': major_classification_id,
            'sub_classification_id': sub_classification_id,
            'location': default_location,
            'transaction_type': 'receipt',
            'date': date,
            'quantity_received': quantity,
            'quantity_distributed': 0.0,
            'reference': reference,
            'uom_id': uom_unit.id if uom_unit else False,
            'received_by_id': self.env.user.id,
        })

    def create_stock_record_for_item(self, item_id, reference, date, quantity=1.0):
        """Create stock record card entry for received item.
        
        AUTO-052: Uses landed cost from PO if available (FR-VAL-002).

        Args:
            item_id (int): ID of the inventory item
            reference (str): Receiving document reference
            date (date): Received date
            quantity (float): Quantity received
        """
        # Get default UoM (unit)
        uom_unit = self.env.ref('uom.product_uom_unit', raise_if_not_found=False)
        if not uom_unit:
            # Fallback: get any UoM
            uom_unit = self.env['uom.uom'].search([], limit=1)
        
        # AUTO-052: Use unit_price (which should already be landed cost from PO)
        unit_cost = self.unit_price
        
        # Get previous balance value
        previous_entries = self.env['mesob.stock.record.card'].search(
            [('item_id', '=', item_id)],
            order='date desc, id desc',
            limit=1
        )
        previous_balance_value = previous_entries[0].balance_value if previous_entries else 0.0

        total_cost_in = quantity * unit_cost

        # Create stock record entry
        stock_record = self.env['mesob.stock.record.card'].create({
            'item_id': item_id,
            'transaction_type': 'receipt',
            'date': date,
            'quantity_in': quantity,
            'quantity_out': 0.0,
            'unit_cost': unit_cost,
            'reference': reference,
            'uom_id': uom_unit.id if uom_unit else False,
        })

        # AUTO-051 & AUTO-052: Create FIFO layer with landed cost
        self.create_fifo_layer_for_receipt(stock_record.id, item_id, quantity, unit_cost)

    def create_fifo_layer_for_receipt(self, stock_record_id, item_id, quantity, unit_cost):
        """Create FIFO layer for receipt transaction.
        
        AUTO-051: FIFO batch tracking
        AUTO-052: Uses landed cost for accurate valuation (FR-VAL-002)

        Args:
            stock_record_id (int): ID of the stock record entry
            item_id (int): ID of the inventory item
            quantity (float): Quantity received
            unit_cost (float): Landed cost per unit (includes all cost components)
        """
        self.env['mesob.stock.fifo.layer'].create({
            'stock_record_id': stock_record_id,
            'item_id': item_id,
            'date': self.receiving_id.received_date or fields.Date.today(),
            'quantity': quantity,
            'quantity_remaining': quantity,
            'unit_cost': unit_cost,  # AUTO-052: Landed cost from PO
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

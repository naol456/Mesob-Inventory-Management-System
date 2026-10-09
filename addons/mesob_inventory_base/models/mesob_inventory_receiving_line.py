import logging
from odoo import api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


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
        readonly=False,
        help="Check this for fixed assets to generate individual item codes with unique tracking. Leave unchecked for consumables.",
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

    # ── Onchange Methods ───────────────────────────────────────────

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
            return {
                'domain': {
                    'sub_classification_id': [('id', '=', False)]
                }
            }

    @api.onchange("sub_classification_id")
    def _onchange_sub_classification(self):
        """Suggest auto_generate_items setting based on asset type (user can override)."""
        if self.sub_classification_id:
            # Suggest based on is_fixed_asset but user can override manually
            self.auto_generate_items = self.sub_classification_id.is_fixed_asset
        else:
            self.auto_generate_items = False

    @api.onchange("qty_accepted")
    def _onchange_qty_accepted(self):
        """Auto-calculate rejected quantity when accepted quantity is entered."""
        if self.qty_received > 0 and self.qty_accepted >= 0:
            self.qty_rejected = self.qty_received - self.qty_accepted

    # ── Item Code Generation ───────────────────────────────────────

    def generate_item_code(self, major_code, sub_code):
        """Generate unique item code in format MAJOR-SUB-SPECIFIC.

        Args:
            major_code (str): 4-digit major classification code
            sub_code (str): 3-digit sub classification code

        Returns:
            str: Generated item code (e.g., "3345-456-001")
        """
        sequence_model = self.env['mesob.item.code.sequence']
        specific_code = sequence_model.get_next_specific_code(major_code, sub_code)
        item_code = f"{major_code}-{sub_code}-{specific_code}"
        
        import re
        if not re.match(r'^\d{4}-\d{3}-\d{3}$', item_code):
            raise ValidationError(f"Invalid item code format: {item_code}")
        
        return item_code

    def generate_items_for_receiving(self):
        """Generate items and create bin cards/stock records based on auto_generate_items flag.

        Logic:
        - If auto_generate_items = True (Fixed Assets):
          * Create individual item records (one per unit)
          * Create individual stock records (one per item)
          * Do NOT create bin cards
        
        - If auto_generate_items = False (Consumables):
          * Create ONE aggregated bin card entry
          * Find or create ONE master item for the sub-classification
          * Create ONE stock record for the total quantity

        Returns:
            list: IDs of created items
        """
        self.ensure_one()
        
        _logger.info(f"[GENERATE_ITEMS] START - Line: {self.sub_classification_id.name if self.sub_classification_id else 'N/A'}, auto_generate={self.auto_generate_items}, qty={self.qty_accepted}")

        # Validation
        if not self.major_classification_id:
            raise ValidationError("Major Classification is required.")
        if not self.sub_classification_id:
            raise ValidationError("Sub Classification is required.")
        if self.qty_accepted <= 0:
            raise ValidationError("Accepted quantity must be greater than zero.")
        if self.unit_price < 0:
            raise ValidationError("Unit price cannot be negative.")

        # Extract codes and reference data
        major_code = self.major_classification_id.code
        sub_code = self.sub_classification_id.code
        quantity = int(self.qty_accepted)
        reference = self.receiving_id.name or "Receiving"
        date = self.receiving_id.received_date or fields.Date.today()

        created_item_ids = []

        try:
            if self.auto_generate_items:
                # ═══════════════════════════════════════════════════════
                # FIXED ASSETS: Create individual items with unique codes
                # ═══════════════════════════════════════════════════════
                _logger.info(f"[FIXED ASSET] Creating {quantity} individual items")
                
                for i in range(quantity):
                    # Generate unique code for each item
                    item_code = self.generate_item_code(major_code, sub_code)
                    
                    # Create individual item record
                    item = self.env['mesob.inventory.item'].create({
                        'item_code': item_code,
                        'classification_id': self.major_classification_id.id,
                        'sub_classification_id': self.sub_classification_id.id,
                        'uom_id': self.uom_id.id if self.uom_id else False,
                        'name': self.description or f"Item {item_code}",
                        'active': True,
                    })
                    
                    created_item_ids.append(item.id)
                    _logger.info(f"[FIXED ASSET] Created item: {item_code}")
                    
                    # Create stock record for individual item (qty=1.0)
                    self.create_stock_record_for_item(item.id, reference, date, 1.0)
                
                # Link all generated items to this receiving line
                self.generated_item_ids = [(6, 0, created_item_ids)]
                _logger.info(f"[FIXED ASSET] SUCCESS - Created {len(created_item_ids)} items, NO bin cards")
                
            else:
                # ═══════════════════════════════════════════════════════
                # CONSUMABLES: Create aggregated bin card + one master item
                # ═══════════════════════════════════════════════════════
                _logger.info(f"[CONSUMABLE] Creating bin card and master item, qty={quantity}")
                
                # Step 1: Create bin card entry (aggregate transaction ledger)
                _logger.info(f"[CONSUMABLE] Creating bin card...")
                self.create_bin_card_for_receiving(
                    self.major_classification_id.id,
                    self.sub_classification_id.id,
                    quantity,
                    reference,
                    date
                )
                _logger.info(f"[CONSUMABLE] Bin card created successfully")
                
                # Step 2: Find or create ONE master item for this sub-classification
                master_item = self.env['mesob.inventory.item'].search([
                    ('sub_classification_id', '=', self.sub_classification_id.id),
                    ('active', '=', True)
                ], limit=1)
                
                if not master_item:
                    # Create master item with code ending in -001
                    item_code = f"{major_code}-{sub_code}-001"
                    _logger.info(f"[CONSUMABLE] Creating master item: {item_code}")
                    master_item = self.env['mesob.inventory.item'].create({
                        'item_code': item_code,
                        'classification_id': self.major_classification_id.id,
                        'sub_classification_id': self.sub_classification_id.id,
                        'uom_id': self.uom_id.id if self.uom_id else False,
                        'name': self.description or self.sub_classification_id.name,
                        'active': True,
                    })
                else:
                    _logger.info(f"[CONSUMABLE] Using existing master item: {master_item.item_code}")
                
                # Step 3: Create ONE stock record for total quantity
                self.create_stock_record_for_item(master_item.id, reference, date, quantity)
                
                created_item_ids.append(master_item.id)
                self.generated_item_ids = [(6, 0, created_item_ids)]
                _logger.info(f"[CONSUMABLE] SUCCESS - Bin card + master item + stock record created")

            return created_item_ids

        except Exception as e:
            _logger.error(f"[GENERATE_ITEMS] FAILED: {str(e)}")
            raise ValidationError(f"Failed to generate items: {str(e)}")

    def create_bin_card_for_receiving(self, major_classification_id, sub_classification_id, quantity, reference, date):
        """Create aggregated bin card entry at sub-classification level.
        
        This creates ONE entry per sub-classification showing the received quantity
        in the Bin Card Transaction Ledger.
        """
        # Get default UoM
        uom_unit = self.env.ref('uom.product_uom_unit', raise_if_not_found=False)
        if not uom_unit:
            uom_unit = self.env['uom.uom'].search([], limit=1)
        
        default_location = 'Main Store'
        
        # Create bin card entry
        bin_card = self.env['mesob.bin.card'].create({
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
        _logger.info(f"[BIN_CARD] Created bin card ID={bin_card.id}, qty={quantity}")

    def create_stock_record_for_item(self, item_id, reference, date, quantity=1.0):
        """Create stock record card entry for received item."""
        # Get default UoM
        uom_unit = self.env.ref('uom.product_uom_unit', raise_if_not_found=False)
        if not uom_unit:
            uom_unit = self.env['uom.uom'].search([], limit=1)

        # Create stock record entry
        stock_record = self.env['mesob.stock.record.card'].create({
            'item_id': item_id,
            'transaction_type': 'receipt',
            'date': date,
            'quantity_in': quantity,
            'quantity_out': 0.0,
            'unit_cost': self.unit_price,
            'reference': reference,
            'uom_id': uom_unit.id if uom_unit else False,
        })

        # Create FIFO layer
        self.create_fifo_layer_for_receipt(stock_record.id, item_id, quantity, self.unit_price)
        _logger.info(f"[STOCK_RECORD] Created stock record ID={stock_record.id}, item={item_id}, qty={quantity}")

    def create_fifo_layer_for_receipt(self, stock_record_id, item_id, quantity, unit_cost):
        """Create FIFO layer for receipt transaction."""
        self.env['mesob.stock.fifo.layer'].create({
            'stock_record_id': stock_record_id,
            'item_id': item_id,
            'date': self.receiving_id.received_date or fields.Date.today(),
            'quantity': quantity,
            'quantity_remaining': quantity,
            'unit_cost': unit_cost,
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

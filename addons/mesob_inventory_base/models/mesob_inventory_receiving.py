from odoo import api, fields, models
from odoo.exceptions import UserError
from lxml import etree


class MesobInventoryReceiving(models.Model):
    """Receiving Order for goods arriving at store.

    Supports receiving from outside suppliers and returns from
    user departments, with inspection, acceptance, and rejection flows.
    (SRS: FR-REC-001 through FR-REC-009)
    """

    _name = "mesob.inventory.receiving"
    _description = "Receiving Order"
    _order = "received_date desc, id desc"
    _rec_name = "name"

    # ── Reference ───────────────────────────────────────────────────
    name = fields.Char(
        string="Reference",
        required=True,
        index=True,
        default=lambda self: self.env["ir.sequence"].next_by_code(
            "mesob.inventory.receiving"
        ) or "New",
        copy=False,
        readonly=True,
        help="Auto-generated receiving order reference.",
    )

    # ── Source Information ──────────────────────────────────────────
    source_type = fields.Selection(
        [
            ("supplier", "Supplier"),
            ("dept_return", "Department Return"),
        ],
        string="Source Type",
        required=True,
        default="supplier",
        help="Origin of received goods.",
    )

    supplier_id = fields.Many2one(
        "res.partner",
        string="Supplier",
        help="Supplier providing the goods.",
        domain="[('is_company', '=', True)]"
    )
    
    department_id = fields.Many2one(
        "mesob.department",
        string="Returning Department",
        domain="[('active', '=', True)]",
        help="Department returning the goods.",
    )

    purchase_order_ref = fields.Char(
        string="PO / Packing Slip Reference",
        help="Reference to purchase order or packing slip.",
    )

    # ── Receiving Details ──────────────────────────────────────────
    received_by_id = fields.Many2one(
        "res.users",
        string="Received By",
        default=lambda self: self.env.user,
        help="Storekeeper who received the goods.",
    )
    received_date = fields.Date(
        string="Received Date",
        default=fields.Date.today,
        help="Date goods arrived at store.",
    )

    # ── Inspection (FR-REC-004) ────────────────────────────────────
    inspection_type = fields.Selection(
        [
            ("storekeeper", "Storekeeper (Simple Items)"),
            ("technical", "Technical Staff (Technical Items)"),
            ("independent", "Independent / Supplier-site"),
        ],
        string="Inspection Type",
        default="storekeeper",
        help="Who performs the inspection (FR-REC-004).",
    )
    inspector_id = fields.Many2one(
        "res.users",
        string="Inspector",
        domain=lambda self: self._get_inspector_domain(),
        help="Person assigned to inspect the goods.",
    )
    inspection_date = fields.Date(
        string="Inspection Date",
    )
    inspection_notes = fields.Text(
        string="Inspection Notes",
        help="Observations from the inspection process.",
    )

    # ── Department Return Flag (FR-REC-007) ────────────────────────
    is_no_payment = fields.Boolean(
        string="No Payment (Dept Return)",
        default=False,
        help="For department returns — no payment will be effected. "
             "Accounts copy retained with pad (FR-REC-007).",
    )

    # ── State Machine (FR-REC-003) ─────────────────────────────────
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("received", "Received"),
            ("inspecting", "Under Inspection"),
            ("accepted", "Accepted"),
            ("rejected", "Rejected"),
            ("done", "Done"),
            ("cancelled", "Cancelled"),
        ],
        required=True,
        default="draft",
        copy=False,
        index=True,
        tracking=True,
    )

    # ── Lines ──────────────────────────────────────────────────────
    line_ids = fields.One2many(
        "mesob.inventory.receiving.line",
        "receiving_id",
        string="Receiving Lines",
        copy=True,
    )

    # ── Generated Documents ────────────────────────────────────────
    model19_id = fields.Many2one(
        "mesob.inventory.model19",
        string="Model 19 (Receipt)",
        readonly=True,
        copy=False,
        help="Auto-generated receipt document for accepted items.",
    )
    dsr_id = fields.Many2one(
        "mesob.inventory.dsr",
        string="DSR (Damage/Shortage Report)",
        readonly=True,
        copy=False,
        help="Auto-generated report for rejected items.",
    )

    note = fields.Text(string="Internal Notes")

    # ── Computed ───────────────────────────────────────────────────
    has_accepted_lines = fields.Boolean(
        compute="_compute_line_summary",
    )
    has_rejected_lines = fields.Boolean(
        compute="_compute_line_summary",
    )

    @api.depends("line_ids.qty_accepted", "line_ids.qty_rejected")
    def _compute_line_summary(self):
        for rec in self:
            rec.has_accepted_lines = any(
                line.qty_accepted > 0 for line in rec.line_ids
            )
            rec.has_rejected_lines = any(
                line.qty_rejected > 0 for line in rec.line_ids
            )

    # ── Onchange ───────────────────────────────────────────────────
    
    def _get_inspector_domain(self):
        """Get domain to filter inspector users."""
        inspector_group = self.env.ref('mesob_inventory_base.group_mesob_inspector', raise_if_not_found=False)
        if not inspector_group:
            # If group doesn't exist, return domain that matches no users
            return [('id', '=', False)]
            
        # Query through the many2many relationship from the group side
        self.env.cr.execute("""
            SELECT uid 
            FROM res_groups_users_rel 
            WHERE gid = %s
        """, (inspector_group.id,))
        
        inspector_user_ids = [row[0] for row in self.env.cr.fetchall()]
        
        # Filter out portal users
        if inspector_user_ids:
            inspector_users = self.env['res.users'].browse(inspector_user_ids).filtered(
                lambda u: not u.share
            )
            inspector_user_ids = inspector_users.ids
        
        if inspector_user_ids:
            return [('id', 'in', inspector_user_ids)]
        
        # If no inspectors found, return domain that matches no users
        return [('id', '=', False)]
    
    @api.onchange("source_type")
    def _onchange_source_type(self):
        """Auto-set no-payment flag and clear/reset fields based on source type.
        
        - For 'supplier': Show supplier_id field, hide department_id
        - For 'dept_return': Show department_id field, hide supplier_id
        """
        # Auto-set no-payment flag for department returns
        if self.source_type == "dept_return":
            self.is_no_payment = True
            self.supplier_id = False  # Clear supplier when switching to department
        else:
            self.is_no_payment = False
            self.department_id = False  # Clear department when switching to supplier

    @api.onchange("purchase_order_ref")
    def _onchange_purchase_order_ref(self):
        """Auto-populate supplier and lines when selecting an approved/sent Purchase Order."""
        if self.purchase_order_ref:
            # Query the approved/sent PO in procurement (FR-PROC-027/FR-PROC-030)
            po = self.env["mesob.procurement.order"].search([
                ("name", "=", self.purchase_order_ref),
                ("state", "in", ("approved", "sent", "partially_received"))
            ], limit=1)
            if po:
                self.supplier_id = po.supplier_id
                self.inspection_type = po.inspection_type
                
                # Auto-generate receiving lines matching the PO lines
                new_lines = []
                for line in po.line_ids:
                    # Robust fallback to APP Lot classification if empty in legacy PO records
                    major_id = line.major_classification_id.id if line.major_classification_id else False
                    sub_id = line.sub_classification_id.id if line.sub_classification_id else False
                    
                    if not major_id or not sub_id:
                        lot = po.plan_lot_id
                        if lot and lot.sub_classification_id:
                            if not sub_id:
                                sub_id = lot.sub_classification_id.id
                            if not major_id and lot.sub_classification_id.major_classification_id:
                                major_id = lot.sub_classification_id.major_classification_id.id

                    line_vals = {
                        "item_id": line.item_id.id if line.item_id else False,
                        "major_classification_id": major_id,
                        "sub_classification_id": sub_id,
                        "auto_generate_items": line.auto_generate_items,
                        "description": line.description or (line.item_id.name if line.item_id else ""),
                        "qty_expected": line.quantity,
                        "qty_received": line.quantity,  # pre-fill received qty as same
                        "unit_price": line.price_unit,
                    }
                    new_lines.append((0, 0, line_vals))
                
                # Assign the list to line_ids
                self.line_ids = new_lines
    
    # ── Actions ────────────────────────────────────────────────────

    @api.model
    def get_view(self, view_id=None, view_type="form", **options):
        """Hide New button for PAO and Stock Clerk on both list and form views.
        
        Only Storekeeper can create Receiving Orders.
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

    def action_receive(self):
        """Mark goods as physically received at store."""
        for rec in self:
            if rec.state != "draft":
                raise UserError("Only draft orders can be marked as received.")
            if not rec.line_ids:
                raise UserError("Add at least one line before receiving.")
            rec.state = "received"
        return True

    def action_start_inspection(self):
        """Assign inspector and begin inspection (FR-REC-004)."""
        for rec in self:
            if rec.state != "received":
                raise UserError(
                    "Only received orders can move to inspection."
                )
            if not rec.inspector_id:
                raise UserError("Please assign an inspector before starting.")
            
            # If current user is an inspector, verify they are the assigned inspector
            current_user = self.env.user
            is_inspector = current_user.has_group("mesob_inventory_base.group_mesob_inspector")
            if is_inspector and rec.inspector_id != current_user:
                raise UserError(
                    f"You can only inspect orders assigned to you. "
                    f"This order is assigned to {rec.inspector_id.name}."
                )
            
            rec.inspection_date = fields.Date.today()
            rec.state = "inspecting"
        return True

    def action_accept(self):
        """Accept goods and generate Model 19 (FR-REC-005).

        Supports partial acceptance — if some lines also have rejected
        quantities, a DSR is generated simultaneously.
        
        Only the assigned inspector can complete the inspection.
        """
        for rec in self:
            if rec.state != "inspecting":
                raise UserError(
                    "Only orders under inspection can be accepted."
                )
            
            # Verify the current user is the assigned inspector
            current_user = self.env.user
            is_inspector = current_user.has_group("mesob_inventory_base.group_mesob_inspector")
            if is_inspector and rec.inspector_id != current_user:
                raise UserError(
                    f"Only the assigned inspector can complete this inspection. "
                    f"This order is assigned to {rec.inspector_id.name}."
                )
            
            # Auto-fill qty_received from qty_accepted if not set
            for line in rec.line_ids:
                if line.qty_accepted > 0 and line.qty_received == 0:
                    line.qty_received = line.qty_accepted + line.qty_rejected
            
            if not rec.has_accepted_lines:
                raise UserError(
                    "No accepted quantities found. Fill in accepted "
                    "quantities on at least one line."
                )

            # Process auto-generation lines first
            for line in rec.line_ids:
                if line.auto_generate_items and line.qty_accepted > 0:
                    line.generate_items_for_receiving()
            
            # Aggregate and create bin cards for non-auto-generation lines
            rec._create_aggregated_bin_cards()

            # Generate Model 19 for accepted items
            rec._generate_model19()

            # If there are also rejected items, generate DSR too
            if rec.has_rejected_lines:
                rec._generate_dsr()

            rec.state = "accepted"
        return True

    def action_reject(self):
        """Reject goods and generate DSR (FR-REC-008).

        Supports partial rejection — if some lines also have accepted
        quantities, a Model 19 is generated simultaneously.
        """
        for rec in self:
            if rec.state != "inspecting":
                raise UserError(
                    "Only orders under inspection can be rejected."
                )
            
            # Auto-fill qty_received from qty_rejected if not set
            for line in rec.line_ids:
                if line.qty_rejected > 0 and line.qty_received == 0:
                    line.qty_received = line.qty_accepted + line.qty_rejected
            
            if not rec.has_rejected_lines:
                raise UserError(
                    "No rejected quantities found. Fill in rejected "
                    "quantities on at least one line."
                )

            # Generate DSR for rejected items
            rec._generate_dsr()

            # If there are also accepted items, generate Model 19 too
            if rec.has_accepted_lines:
                rec._generate_model19()

            rec.state = "rejected"
        return True

    def action_done(self):
        """Finalize the receiving order (FR-REC-002)."""
        for rec in self:
            if rec.state not in ("accepted", "rejected"):
                raise UserError(
                    "Only accepted or rejected orders can be finalized."
                )
            rec.state = "done"
        return True

    def action_cancel(self):
        """Cancel the receiving order."""
        for rec in self:
            if rec.state == "done":
                raise UserError("Finalized orders cannot be cancelled.")
            rec.state = "cancelled"
        return True

    def action_set_to_draft(self):
        """Reset cancelled order to draft for corrections."""
        for rec in self:
            if rec.state != "cancelled":
                raise UserError(
                    "Only cancelled orders can be reset to draft."
                )
            rec.state = "draft"
        return True

    # ── Document Generation ────────────────────────────────────────

    def _create_aggregated_bin_cards(self):
        """Create aggregated bin card entries and/or individual items for non-auto-generation lines.
        
        For Fixed Assets: Creates individual item records with unique codes
        For Consumables: Creates ONE aggregated bin card entry per sub-classification
        """
        self.ensure_one()
        
        # Dictionary to aggregate quantities by sub-classification
        # Key: (major_classification_id, sub_classification_id, is_fixed_asset)
        # Value: {'total_qty': float, 'lines': [line records]}
        aggregated = {}
        
        for line in self.line_ids:
            # Skip auto-generation lines (already handled)
            if line.auto_generate_items:
                continue
            
            # Skip lines with no accepted quantity
            if line.qty_accepted <= 0:
                continue
            
            # Determine classification
            major_id = None
            sub_id = None
            sub_classification = None
            
            if line.major_classification_id and line.sub_classification_id:
                major_id = line.major_classification_id.id
                sub_id = line.sub_classification_id.id
                sub_classification = line.sub_classification_id
            elif line.item_id:
                if line.item_id.classification_id and line.item_id.sub_classification_id:
                    major_id = line.item_id.classification_id.id
                    sub_id = line.item_id.sub_classification_id.id
                    sub_classification = line.item_id.sub_classification_id
            
            # Skip if no classifications found
            if not major_id or not sub_id or not sub_classification:
                continue
            
            # Check if this is a fixed asset
            is_fixed_asset = sub_classification.is_fixed_asset
            
            # Aggregate by sub-classification and asset type
            key = (major_id, sub_id, is_fixed_asset)
            if key not in aggregated:
                aggregated[key] = {
                    'total_qty': 0.0,
                    'lines': [],
                    'major_classification': line.major_classification_id or line.item_id.classification_id,
                    'sub_classification': sub_classification,
                }
            aggregated[key]['total_qty'] += line.qty_accepted
            aggregated[key]['lines'].append(line)
        
        # Process aggregated data
        reference = self.name or "Receiving"
        date = self.received_date or fields.Date.today()
        
        for (major_id, sub_id, is_fixed_asset), data in aggregated.items():
            if is_fixed_asset:
                # FIXED ASSET: Generate individual items with specific codes
                self._create_fixed_asset_items(
                    data['major_classification'],
                    data['sub_classification'],
                    data['lines'],
                    reference,
                    date
                )
            else:
                # CONSUMABLE: Create one aggregated bin card entry
                self._create_bin_card_entry(
                    major_id,
                    sub_id,
                    data['total_qty'],
                    reference,
                    date
                )
    
    def _create_fixed_asset_items(self, major_classification, sub_classification, lines, reference, date):
        """Create individual item records for fixed assets.
        
        Args:
            major_classification: Major classification record
            sub_classification: Sub classification record
            lines: List of receiving line records
            reference: Receiving document reference
            date: Received date
        """
        major_code = major_classification.code
        sub_code = sub_classification.code
        
        # Total quantity across all lines
        total_qty = sum(line.qty_accepted for line in lines)
        
        # Create aggregated bin card entry ONCE
        self._create_bin_card_entry(
            major_classification.id,
            sub_classification.id,
            total_qty,
            reference,
            date
        )
        
        # Generate individual item records for tracking
        item_code_sequence = self.env['mesob.item.code.sequence']
        created_items = []
        
        for line in lines:
            qty = int(line.qty_accepted)
            for i in range(qty):
                # Generate unique item code
                specific_code = item_code_sequence.get_next_specific_code(major_code, sub_code)
                item_code = f"{major_code}-{sub_code}-{specific_code}"
                
                # Get UoM
                uom_id = False
                if line.uom_id:
                    uom_id = line.uom_id.id
                else:
                    uom_unit = self.env.ref('uom.product_uom_unit', raise_if_not_found=False)
                    if uom_unit:
                        uom_id = uom_unit.id
                
                # Create item record
                item = self.env['mesob.inventory.item'].create({
                    'item_code': item_code,
                    'classification_id': major_classification.id,
                    'sub_classification_id': sub_classification.id,
                    'uom_id': uom_id,
                    'name': line.description or sub_classification.name,
                    'active': True,
                })
                
                created_items.append(item.id)
                
                # Create stock record entry for individual tracking
                self._create_stock_record_for_fixed_asset(item.id, line.unit_price, reference, date)
        
        # Link all created items to the first line (for reference)
        if created_items and lines:
            lines[0].generated_item_ids = [(6, 0, created_items)]
    
    def _create_stock_record_for_fixed_asset(self, item_id, unit_price, reference, date):
        """Create stock record card entry for fixed asset item.
        
        Args:
            item_id: ID of the inventory item
            unit_price: Unit cost
            reference: Receiving document reference
            date: Received date
        """
        # Get default UoM
        uom_unit = self.env.ref('uom.product_uom_unit', raise_if_not_found=False)
        if not uom_unit:
            uom_unit = self.env['uom.uom'].search([], limit=1)
        
        # Create stock record entry
        stock_record = self.env['mesob.stock.record.card'].create({
            'item_id': item_id,
            'transaction_type': 'receipt',
            'date': date,
            'quantity_in': 1.0,
            'quantity_out': 0.0,
            'unit_cost': unit_price,
            'reference': reference,
            'uom_id': uom_unit.id if uom_unit else False,
        })
        
        # Create FIFO layer
        self.env['mesob.stock.fifo.layer'].create({
            'stock_record_id': stock_record.id,
            'item_id': item_id,
            'date': date,
            'quantity': 1.0,
            'quantity_remaining': 1.0,
            'unit_cost': unit_price,
        })
    
    def _create_bin_card_entry(self, major_classification_id, sub_classification_id, quantity, reference, date):
        """Create a single bin card entry for receiving.
        
        Args:
            major_classification_id (int): ID of major classification
            sub_classification_id (int): ID of sub classification
            quantity (float): Total quantity received
            reference (str): Receiving document reference
            date (date): Received date
        """
        # Get default UoM (unit)
        uom_unit = self.env.ref('uom.product_uom_unit', raise_if_not_found=False)
        if not uom_unit:
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

    def _generate_model19(self):
        """Create Model 19 receipt document from accepted lines."""
        self.ensure_one()
        if self.model19_id:
            return  # Already generated

        accepted_lines = self.line_ids.filtered(
            lambda l: l.qty_accepted > 0
        )
        if not accepted_lines:
            return

        model19_vals = {
            "receiving_id": self.id,
            "date": fields.Date.today(),
            "supplier_id": self.supplier_id.id if self.supplier_id else False,
            "is_no_payment": self.is_no_payment,
            "line_ids": [
                (0, 0, {
                    "item_id": line.item_id.id if line.item_id else False,
                    "description": line.description,
                    "quantity": line.qty_accepted,
                    "uom_id": line.uom_id.id if line.uom_id else False,
                    "unit_price": line.unit_price,
                })
                for line in accepted_lines
            ],
        }
        model19 = self.env["mesob.inventory.model19"].create(model19_vals)
        self.model19_id = model19.id

    def _generate_dsr(self):
        """Create DSR from rejected lines (FR-REC-008)."""
        self.ensure_one()
        if self.dsr_id:
            return  # Already generated

        rejected_lines = self.line_ids.filtered(
            lambda l: l.qty_rejected > 0
        )
        if not rejected_lines:
            return

        dsr_vals = {
            "receiving_id": self.id,
            "date": fields.Date.today(),
            "supplier_id": self.supplier_id.id if self.supplier_id else False,
            "line_ids": [
                (0, 0, {
                    "item_id": line.item_id.id if line.item_id else False,
                    "description": line.description,
                    "quantity": line.qty_rejected,
                    "uom_id": line.uom_id.id if line.uom_id else False,
                    "discrepancy_type": line.rejection_reason or "damaged",
                    "notes": line.rejection_notes,
                })
                for line in rejected_lines
            ],
        }
        dsr = self.env["mesob.inventory.dsr"].create(dsr_vals)
        self.dsr_id = dsr.id

    # ── Smart Buttons ──────────────────────────────────────────────

    def action_view_model19(self):
        """Open the generated Model 19 document."""
        self.ensure_one()
        if not self.model19_id:
            raise UserError("No Model 19 has been generated yet.")
        return {
            "type": "ir.actions.act_window",
            "name": f"Model 19 — {self.model19_id.name}",
            "res_model": "mesob.inventory.model19",
            "view_mode": "form",
            "res_id": self.model19_id.id,
        }

    def action_view_dsr(self):
        """Open the generated DSR document."""
        self.ensure_one()
        if not self.dsr_id:
            raise UserError("No DSR has been generated yet.")
        return {
            "type": "ir.actions.act_window",
            "name": f"DSR — {self.dsr_id.name}",
            "res_model": "mesob.inventory.dsr",
            "view_mode": "form",
            "res_id": self.dsr_id.id,
        }

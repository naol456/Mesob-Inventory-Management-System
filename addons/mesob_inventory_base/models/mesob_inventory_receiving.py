from odoo import api, fields, models
from odoo.exceptions import UserError
from lxml import etree
import logging

_logger = logging.getLogger(__name__)


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
    
    department_id = fields.Selection(
        [
            ("ministry_transport_logistics", "Ministry of Transport and Logistics"),
            ("commercial_bank_ethiopia", "Commercial Bank of Ethiopia"),
            ("ethio_telecom", "Ethio telecom"),
            ("education_training_authority", "Education and Training Authority"),
            ("ethiopian_environmental_protection", "Ethiopian Environmental Protection Authority"),
            ("ethiopian_food_drug_authority", "Ethiopian Food and Drug Authority"),
            ("ethiopian_agricultural_authority", "Ethiopian Agricultural Authority"),
            ("ethiopian_construction_authority", "Ethiopian Construction Authority"),
            ("ministry_health", "Ministry of Health"),
            ("ethiopian_customs_commission", "Ethiopian Customs Commission"),
            ("ministry_justice", "Ministry of Justice"),
            ("ministry_trade_regional_integration", "Ministry of Trade and Regional Integration"),
            ("ministry_tourism", "Ministry of Tourism"),
            ("ethiopian_postal_service", "Ethiopian Postal Service Enterprise"),
            ("ethiopian_investment_commission", "Ethiopian Investment Commission"),
            ("educational_assessment_examination", "Educational Assessment and Examination Service"),
            ("documents_authentication_registration", "Documents Authentication and Registration Service"),
            ("ministry_revenues", "Ministry of Revenues"),
            ("ministry_foreign_affairs", "Ministry of Foreign Affairs"),
            ("ministry_labor_skills", "Ministry of Labor and Skills"),
            ("immigration_citizenship_service", "Immigration and Citizenship Service"),
            ("national_id_program", "National ID Program"),
        ],
        string="Returning Department",
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
            rec.inspection_date = fields.Date.today()
            rec.state = "inspecting"
        return True

    def action_accept(self):
        """Accept goods and generate Model 19 (FR-REC-005).

        Supports partial acceptance — if some lines also have rejected
        quantities, a DSR is generated simultaneously.
        """
        for rec in self:
            if rec.state != "inspecting":
                raise UserError(
                    "Only orders under inspection can be accepted."
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

            # Auto-generate items for lines with auto_generate_items flag
            for line in rec.line_ids:
                if line.auto_generate_items and line.qty_accepted > 0:
                    line.generate_items_for_receiving()

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

    def _generate_model19(self):
        """AUTO-027: Create Model 19 receipt document from accepted lines with auto-distribution.
        
        Enhanced automation features:
        - Auto-generates Model 19 from accepted receiving lines (FR-REC-005)
        - Auto-distributes four copies digitally (FR-REC-006)
        - Sends notifications to all recipients (Accounts, Stock Clerk, Supplier, Storekeeper)
        - Triggers Bin Card and Stock Record Card updates (AUTO-049)
        - Links to Purchase Order for three-way match (AUTO-029)
        """
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
        
        # AUTO-027: Auto-confirm Model 19 to trigger downstream automations
        model19.action_confirm()
        
        # AUTO-027: Auto-distribute copies digitally (FR-REC-006)
        self._auto_distribute_model19_copies(model19)
        
        # AUTO-027: Trigger Bin Card and Stock Record Card updates (AUTO-049)
        self._auto_update_stock_records(model19)
        
        # AUTO-027: Update linked PO status if exists (for AUTO-029 three-way match)
        self._update_po_receipt_status(model19)
        
        _logger.info(
            f"AUTO-027: Model 19 {model19.name} auto-generated, distributed, "
            f"and stock records updated for Receiving {self.name}"
        )

    def _auto_distribute_model19_copies(self, model19):
        """AUTO-027: Auto-distribute Model 19 four copies digitally (FR-REC-006).
        
        Distribution:
        - Original → Accounts Unit (with supplier invoice)
        - Duplicate → Stock Clerk (for posting)
        - Triplicate → Supplier/Deliverer
        - Book Copy → Storekeeper
        """
        # Find user groups for notification
        accounts_users = self.env.ref('mesob_inventory_base.group_mesob_pao', raise_if_not_found=False)
        stock_clerk_users = self.env.ref('mesob_inventory_base.group_mesob_stock_clerk', raise_if_not_found=False)
        storekeeper_users = self.env.ref('mesob_inventory_base.group_mesob_storekeeper', raise_if_not_found=False)
        
        # Auto-mark copies as distributed
        model19.write({
            'copy_accounts': 'distributed',
            'copy_stock_clerk': 'distributed',
            'copy_supplier': 'distributed',
            'copy_storekeeper': 'distributed',
        })
        
        # Notification body
        notification_body = f"""<div>
            <h3>Model 19 Receipt Generated</h3>
            <p><strong>Reference:</strong> {model19.name}</p>
            <p><strong>Date:</strong> {model19.date}</p>
            <p><strong>Supplier:</strong> {model19.supplier_id.name if model19.supplier_id else 'N/A'}</p>
            <p><strong>Total Amount:</strong> ETB {model19.total_amount:,.2f}</p>
            <p><strong>Items:</strong></p>
            <ul>
                {''.join([f'<li>{line.description}: {line.quantity} {line.uom_id.name if line.uom_id else ""}</li>' for line in model19.line_ids])}
            </ul>
        </div>"""
        
        # Send to Accounts Unit (Original)
        if accounts_users and accounts_users.users:
            model19.message_post(
                body=f"""<p><strong>Original Copy → Accounts Unit</strong></p>{notification_body}
                <p><em>Attach supplier invoice for payment processing (FR-PROC-034 three-way match).</em></p>""",
                subject=f"Model 19 Original: {model19.name}",
                message_type='notification',
                partner_ids=accounts_users.users.mapped('partner_id').ids
            )
        
        # Send to Stock Clerk (Duplicate)
        if stock_clerk_users and stock_clerk_users.users:
            model19.message_post(
                body=f"""<p><strong>Duplicate Copy → Stock Clerk</strong></p>{notification_body}
                <p><em>Stock records have been auto-updated (Bin Card & Stock Record Card).</em></p>""",
                subject=f"Model 19 Duplicate: {model19.name}",
                message_type='notification',
                partner_ids=stock_clerk_users.users.mapped('partner_id').ids
            )
        
        # Send to Supplier (Triplicate) - if email available
        if model19.supplier_id and model19.supplier_id.email:
            model19.message_post(
                body=f"""<p><strong>Triplicate Copy → Supplier</strong></p>{notification_body}
                <p><em>This confirms receipt and acceptance of your delivery.</em></p>""",
                subject=f"Receipt Confirmation: {model19.name}",
                message_type='email',
                partner_ids=[model19.supplier_id.id]
            )
        
        # Send to Storekeeper (Book Copy)
        if storekeeper_users and storekeeper_users.users:
            model19.message_post(
                body=f"""<p><strong>Book Copy → Storekeeper</strong></p>{notification_body}
                <p><em>Retained for your records.</em></p>""",
                subject=f"Model 19 Book Copy: {model19.name}",
                message_type='notification',
                partner_ids=storekeeper_users.users.mapped('partner_id').ids
            )
        
        # Mark as distributed
        model19.action_mark_distributed()
        
        _logger.info(f"AUTO-027: Model 19 {model19.name} - Four copies auto-distributed digitally")

    def _auto_update_stock_records(self, model19):
        """AUTO-049: Trigger real-time Bin Card and Stock Record Card updates.
        
        When Model 19 is confirmed:
        - Create Bin Card entry (quantity received) per sub-classification
        - Create Stock Record Card entry (quantity + value) with FIFO cost
        - Update PO status to Partially/Fully Received
        """
        for line in model19.line_ids:
            if not line.item_id:
                continue
            
            # AUTO-049: Create Bin Card entry (FR-RECARD-001)
            if line.item_id.sub_classification_id:
                self.env['mesob.bin.card'].create({
                    'major_classification_id': line.item_id.classification_id.id,
                    'sub_classification_id': line.item_id.sub_classification_id.id,
                    'location': 'Main Store',  # Default location
                    'date': model19.date,
                    'transaction_type': 'receipt',
                    'reference': model19.name,
                    'description': f'Receipt: {line.description}',
                    'quantity_received': line.quantity,
                    'quantity_distributed': 0.0,
                    'uom_id': line.uom_id.id if line.uom_id else line.item_id.uom_id.id,
                    'received_by_id': self.env.user.id,
                })
                _logger.info(
                    f"AUTO-049: Bin Card created for {line.item_id.item_code} - "
                    f"Qty: {line.quantity}"
                )
            
            # AUTO-049: Create Stock Record Card entry (FR-RECARD-002) with FIFO
            stock_record = self.env['mesob.stock.record.card'].create({
                'item_id': line.item_id.id,
                'date': model19.date,
                'transaction_type': 'receipt',
                'reference': model19.name,
                'description': f'Receipt: {line.description}',
                'quantity_in': line.quantity,
                'quantity_out': 0.0,
                'uom_id': line.uom_id.id if line.uom_id else line.item_id.uom_id.id,
                'unit_cost': line.unit_price,  # From PO unit price (FR-VAL-001)
                'source_document': self.purchase_order_ref or model19.name,
            })
            
            # Create FIFO layer for this receipt (FR-VAL-001)
            stock_record.action_create_fifo_layers()
            
            _logger.info(
                f"AUTO-049: Stock Record Card created for {line.item_id.item_code} - "
                f"Qty: {line.quantity}, Unit Cost: ETB {line.unit_price}"
            )

    def _update_po_receipt_status(self, model19):
        """AUTO-027: Update linked Purchase Order status for three-way match.
        
        Links Model 19 to PO and updates PO status:
        - Partially Received if some lines pending
        - Fully Received if all lines received
        
        Enables AUTO-029 three-way match (PO + Model 19 + Invoice).
        """
        if not self.purchase_order_ref:
            return
        
        # Find linked PO by reference
        po = self.env['mesob.procurement.order'].search([
            ('name', '=', self.purchase_order_ref)
        ], limit=1)
        
        if not po:
            _logger.warning(
                f"AUTO-027: PO {self.purchase_order_ref} not found for Model 19 {model19.name}"
            )
            return
        
        # Update PO status based on receipt completion
        total_ordered = sum(po.line_ids.mapped('quantity'))
        total_received = sum([
            line.quantity for line in model19.line_ids if line.item_id
        ])
        
        if total_received >= total_ordered:
            po.state = 'fully_received'
            _logger.info(f"AUTO-027: PO {po.name} marked as Fully Received")
        else:
            po.state = 'partially_received'
            _logger.info(f"AUTO-027: PO {po.name} marked as Partially Received")
        
        # Link Model 19 to PO for three-way match (AUTO-029)
        po.message_post(
            body=f"""<p><strong>Model 19 Linked for Three-Way Match</strong></p>
            <p>Model 19: {model19.name}</p>
            <p>Received: {total_received} / {total_ordered} items</p>
            <p><em>Ready for payment processing once supplier invoice is received.</em></p>""",
            subject=f"Receipt Confirmation: {model19.name}"
        )

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

from odoo import api, fields, models
from odoo.exceptions import UserError
from lxml import etree
import logging

_logger = logging.getLogger(__name__)


class MesobInventoryModel19(models.Model):
    """Receipt for Articles/Property (Model 19).

    Auto-generated when a receiving order is accepted.
    Tracks four-copy distribution as required by FDRE procedures.
    (SRS: FR-REC-005, FR-REC-006, FR-REC-007)
    
    AUTO-027: Model 19 Auto-Generation & Three-Way Match Trigger
    - Auto-generates when receiving is completed and accepted
    - Automatically posts to Bin Card and Stock Record Card via AUTO-049
    - Triggers three-way match for payment processing (AUTO-029)
    - Tracks four-copy distribution: Accounts, Stock clerk, Supplier, Storekeeper
    """

    _name = "mesob.inventory.model19"
    _description = "Receipt for Articles/Property (Model 19)"
    _inherit = ['mesob.stock.movement.mixin', 'mail.thread', 'mail.activity.mixin']
    _order = "date desc, id desc"
    _rec_name = "name"

    # ── Reference ───────────────────────────────────────────────────
    name = fields.Char(
        string="Model 19 Reference",
        required=True,
        index=True,
        default=lambda self: self.env["ir.sequence"].next_by_code(
            "mesob.inventory.model19"
        ) or "New",
        copy=False,
        readonly=True,
    )

    # ── Source ──────────────────────────────────────────────────────
    receiving_id = fields.Many2one(
        "mesob.inventory.receiving",
        string="Receiving Order",
        readonly=True,
        index=True,
        help="Source receiving order that generated this Model 19.",
    )

    date = fields.Date(
        string="Receipt Date",
        required=True,
        default=fields.Date.today,
    )

    supplier_id = fields.Many2one(
        "res.partner",
        string="Supplier / Source",
        help="Supplier, donor, or returning department.",
    )

    # ── Department Return Flag (FR-REC-007) ────────────────────────
    is_no_payment = fields.Boolean(
        string="No Payment (Dept Return)",
        default=False,
        help="For department returns — no payment will be effected. "
             "Accounts copy retained with pad (FR-REC-007).",
    )

    # ── Copy Distribution (FR-REC-006) ─────────────────────────────
    copy_accounts = fields.Selection(
        [("pending", "Pending"), ("distributed", "Distributed")],
        string="Original → Accounts Unit",
        default="pending",
        help="Original with supplier invoice → Accounts Unit.",
    )
    copy_stock_clerk = fields.Selection(
        [("pending", "Pending"), ("distributed", "Distributed")],
        string="Duplicate → Stock Clerk",
        default="pending",
        help="Duplicate copy → Stock Clerk for posting.",
    )
    copy_supplier = fields.Selection(
        [("pending", "Pending"), ("distributed", "Distributed")],
        string="Triplicate → Supplier",
        default="pending",
        help="Triplicate copy → Supplier/deliverer.",
    )
    copy_storekeeper = fields.Selection(
        [("pending", "Pending"), ("distributed", "Distributed")],
        string="Book Copy → Storekeeper",
        default="pending",
        help="Book copy retained by Storekeeper.",
    )

    all_copies_distributed = fields.Boolean(
        string="All Copies Distributed",
        compute="_compute_all_copies_distributed",
    )

    # ── Lines ──────────────────────────────────────────────────────
    line_ids = fields.One2many(
        "mesob.inventory.model19.line",
        "model19_id",
        string="Receipt Lines",
    )

    # ── State ──────────────────────────────────────────────────────
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("distributed", "Distributed"),
        ],
        required=True,
        default="draft",
        copy=False,
        index=True,
        tracking=True,
    )

    note = fields.Text(string="Notes")

    # ── Totals ─────────────────────────────────────────────────────
    total_amount = fields.Float(
        string="Total Amount",
        compute="_compute_total_amount",
        store=True,
    )

    # ── Computed ───────────────────────────────────────────────────

    @api.depends("line_ids.total_price")
    def _compute_total_amount(self):
        for rec in self:
            rec.total_amount = sum(rec.line_ids.mapped("total_price"))

    @api.depends(
        "copy_accounts", "copy_stock_clerk",
        "copy_supplier", "copy_storekeeper"
    )
    def _compute_all_copies_distributed(self):
        for rec in self:
            rec.all_copies_distributed = all([
                rec.copy_accounts == "distributed",
                rec.copy_stock_clerk == "distributed",
                rec.copy_supplier == "distributed",
                rec.copy_storekeeper == "distributed",
            ])

    # ── View Customization ──────────────────────────────────────────

    @api.model
    def get_view(self, view_id=None, view_type="form", **options):
        """Hide New button for PAO and Stock Clerk on both list and form views.
        
        Model 19 receipts are auto-generated from Receiving Orders.
        Only Storekeeper can manually create (if needed).
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

    # ── Actions ────────────────────────────────────────────────────

    def action_confirm(self):
        """AUTO-027: Confirm Model 19 and auto-post stock movements.
        AUTO-040: Auto-route four-copy distribution digitally.
        
        Compliance: FR-REC-005, FR-REC-006, FR-PROC-033, FR-RECARD-001, FR-RECARD-002
        """
        for rec in self:
            if rec.state != "draft":
                raise UserError("Only draft receipts can be confirmed.")
            
            # AUTO-027: Auto-post stock movements to Bin Card and Stock Record Card
            if not rec.stock_movements_posted and rec.line_ids:
                movements_data = []
                for line in rec.line_ids:
                    if line.item_id and line.quantity_accepted > 0:
                        movements_data.append({
                            'item_id': line.item_id.id,
                            'quantity': line.quantity_accepted,
                            'transaction_type': 'receipt',
                            'unit_cost': line.unit_price or 0.0,
                            'reference': rec.name,
                        })
                
                if movements_data:
                    rec.action_post_stock_movements(movements_data)
            
            rec.state = "confirmed"
            
            # AUTO-040: Four-copy digital distribution (FR-REC-006)
            rec._send_four_copy_distribution_notifications()
            
            # AUTO-027: Trigger three-way match notification
            rec.message_post(
                body=f"""<div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px;">
                    <h4>✅ Model 19 Confirmed - Ready for Payment Match</h4>
                    <p><strong>Reference:</strong> {rec.name}</p>
                    <p><strong>Date:</strong> {rec.date}</p>
                    <p><strong>Supplier:</strong> {rec.supplier_id.name if rec.supplier_id else 'N/A'}</p>
                    <p><strong>Lines:</strong> {len(rec.line_ids)}</p>
                    <p><em>AUTO-027: Stock movements posted. This receipt is now available for three-way match (PO + Model 19 + Invoice).</em></p>
                </div>""",
                subject='Model 19 Confirmed - Three-Way Match Ready',
                message_type='comment'
            )
        
        return True
    
    def _send_four_copy_distribution_notifications(self):
        """AUTO-040: Four-Copy Digital Distribution Auto-Routing (FR-REC-006).
        
        Distribution per FR-REC-006:
        1. Original + Supplier Invoice → Accounts Unit (for payment processing)
        2. Duplicate → Stock Clerk (for bin card and stock record card posting)
        3. Triplicate → Supplier/Deliverer (receipt acknowledgment)
        4. Book Copy → Storekeeper (retained in system)
        
        Special case (FR-REC-007): For department returns (no payment),
        Accounts copy is retained with pad instead of being forwarded.
        """
        self.ensure_one()
        
        # Build items summary
        items_summary = '<ul>'
        for line in self.line_ids:
            items_summary += f'<li><strong>{line.item_id.item_code if line.item_id else "N/A"}</strong>: {line.quantity_accepted} {line.uom_id.name if line.uom_id else "units"} @ ETB {line.unit_price:,.2f}/unit = ETB {line.total_price:,.2f}</li>'
        items_summary += '</ul>'
        
        total_value = sum(line.total_price for line in self.line_ids)
        
        # 1. Original → Accounts Unit (FR-REC-006)
        accounts_users = self.env.ref('mesob_inventory_base.group_mesob_pao', raise_if_not_found=False)
        
        if self.is_no_payment:
            # FR-REC-007: Department return - Accounts copy retained with pad
            accounts_message = f"""<div style="background-color: #e7f3ff; border-left: 4px solid #0066cc; padding: 15px;">
                <h3>📄 Model 19 - ORIGINAL COPY (Accounts - Retained)</h3>
                <p><strong>Receipt Reference:</strong> {self.name}</p>
                <p><strong>Date:</strong> {self.date}</p>
                <p><strong>Type:</strong> ⚠️ DEPARTMENT RETURN (No Payment)</p>
                <hr/>
                <h4>Items Received:</h4>
                {items_summary}
                <p><strong>Total Value:</strong> ETB {total_value:,.2f}</p>
                <hr/>
                <div style="background-color: #fff3cd; padding: 10px; border-radius: 4px; margin-top: 15px;">
                    <p style="margin: 0;"><strong>FR-REC-007:</strong> Department return detected.</p>
                    <p style="margin: 5px 0 0 0;">This is a returned item from a department - <strong>NO PAYMENT will be effected</strong>. This copy is retained with pad for accounting records only.</p>
                </div>
            </div>"""
        else:
            # Normal receipt - forward with invoice for payment
            accounts_message = f"""<div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px;">
                <h3>📄 Model 19 - ORIGINAL COPY (Accounts Unit)</h3>
                <p><strong>Receipt Reference:</strong> {self.name}</p>
                <p><strong>Date:</strong> {self.date}</p>
                <p><strong>Supplier:</strong> {self.supplier_id.name if self.supplier_id else 'N/A'}</p>
                <p><strong>Receiving Order:</strong> {self.receiving_id.name if self.receiving_id else 'N/A'}</p>
                <hr/>
                <h4>Items Received:</h4>
                {items_summary}
                <p><strong>Total Value:</strong> ETB {total_value:,.2f}</p>
                <hr/>
                <div style="background-color: #e7f3ff; padding: 10px; border-radius: 4px; margin-top: 15px;">
                    <p style="margin: 0;"><strong>⚠ ACTION REQUIRED:</strong></p>
                    <p style="margin: 5px 0 0 0;">Forward this copy with supplier's VAT-compliant tax invoice for three-way match payment processing (FR-PROC-033, FR-PROC-034).</p>
                </div>
                <p style="margin-top: 15px;"><a href="/web#id={self.id}&model=mesob.inventory.model19&view_type=form" 
                   style="background-color: #ffc107; color: #000; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                   View Receipt →
                </a></p>
            </div>"""
        
        if accounts_users and accounts_users.users:
            self.message_post(
                body=accounts_message,
                subject=f'[ORIGINAL] Model 19 Receipt: {self.name}',
                message_type='notification',
                partner_ids=accounts_users.users.mapped('partner_id').ids
            )
            _logger.info(f"AUTO-040: Original copy sent to {len(accounts_users.users)} Accounts users")
        
        # 2. Duplicate → Stock Clerk (FR-REC-006)
        stock_clerk_users = self.env.ref('mesob_inventory_base.group_mesob_stock_clerk', raise_if_not_found=False)
        if stock_clerk_users and stock_clerk_users.users:
            self.message_post(
                body=f"""<div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px;">
                    <h3>📄 Model 19 - DUPLICATE COPY (Stock Clerk)</h3>
                    <p><strong>Receipt Reference:</strong> {self.name}</p>
                    <p><strong>Date:</strong> {self.date}</p>
                    <p><strong>Supplier:</strong> {self.supplier_id.name if self.supplier_id else 'N/A'}</p>
                    <hr/>
                    <h4>Items Received:</h4>
                    {items_summary}
                    <p><strong>Total Value:</strong> ETB {total_value:,.2f}</p>
                    <hr/>
                    <div style="background-color: #e7f3ff; padding: 10px; border-radius: 4px; margin-top: 15px;">
                        <p style="margin: 0;"><strong>⚠ ACTION REQUIRED:</strong></p>
                        <p style="margin: 5px 0 0 0;">Post these transactions to Bin Cards and Stock Record Cards (FR-RECARD-001, FR-RECARD-002).</p>
                        <p style="margin: 5px 0 0 0;"><em>Note: AUTO-049 has already auto-posted these entries. Please verify and confirm.</em></p>
                    </div>
                    <p style="margin-top: 15px;"><a href="/web#id={self.id}&model=mesob.inventory.model19&view_type=form" 
                       style="background-color: #28a745; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                       View Receipt →
                    </a></p>
                </div>""",
                subject=f'[DUPLICATE] Model 19 for Bin Card Posting: {self.name}',
                message_type='notification',
                partner_ids=stock_clerk_users.users.mapped('partner_id').ids
            )
            _logger.info(f"AUTO-040: Duplicate copy sent to {len(stock_clerk_users.users)} Stock Clerk users")
        
        # 3. Triplicate → Supplier/Deliverer (FR-REC-006)
        if self.supplier_id and not self.is_no_payment:
            supplier_message = f"""<div style="background-color: #f8d7da; border-left: 4px solid #dc3545; padding: 15px;">
                <h3>📄 Model 19 - TRIPLICATE COPY (Supplier)</h3>
                <p><strong>Receipt Reference:</strong> {self.name}</p>
                <p><strong>Date:</strong> {self.date}</p>
                <p><strong>Delivered To:</strong> {self.env.company.name}</p>
                <hr/>
                <h4>Items Received and Accepted:</h4>
                {items_summary}
                <p><strong>Total Value:</strong> ETB {total_value:,.2f}</p>
                <hr/>
                <p style="margin-top: 15px;"><em>This is your official acknowledgment of receipt. Please submit your VAT-compliant tax invoice to Accounts Unit for payment processing.</em></p>
            </div>"""
            
            # Try to send email to supplier if email is configured
            if self.supplier_id.email:
                self.message_post(
                    body=supplier_message,
                    subject=f'Receipt Acknowledgment: {self.name}',
                    message_type='email',
                    partner_ids=[self.supplier_id.id],
                    email_from=self.env.company.email or self.env.user.email,
                )
                _logger.info(f"AUTO-040: Triplicate copy sent to supplier {self.supplier_id.name} via email")
            else:
                # Post as notification if no email
                self.message_post(
                    body=supplier_message,
                    subject=f'[TRIPLICATE] Receipt for Supplier: {self.name}',
                    message_type='comment',
                    partner_ids=[self.supplier_id.id] if self.supplier_id else []
                )
                _logger.info(f"AUTO-040: Triplicate copy logged for supplier {self.supplier_id.name} (no email)")
        
        # 4. Book Copy → Storekeeper (FR-REC-006)
        storekeeper_users = self.env.ref('mesob_inventory_base.group_mesob_storekeeper', raise_if_not_found=False)
        if storekeeper_users and storekeeper_users.users:
            self.message_post(
                body=f"""<div style="background-color: #d1ecf1; border-left: 4px solid #0c5460; padding: 15px;">
                    <h3>📄 Model 19 - BOOK COPY (Storekeeper)</h3>
                    <p><strong>Receipt Reference:</strong> {self.name}</p>
                    <p><strong>Date:</strong> {self.date}</p>
                    <p><strong>Supplier:</strong> {self.supplier_id.name if self.supplier_id else 'N/A'}</p>
                    <hr/>
                    <h4>Items Received:</h4>
                    {items_summary}
                    <p><strong>Total Value:</strong> ETB {total_value:,.2f}</p>
                    <hr/>
                    <p><em>This is your retained copy for store records. All other copies have been distributed electronically per FR-REC-006.</em></p>
                </div>""",
                subject=f'[BOOK COPY] Model 19 Retained: {self.name}',
                message_type='comment',
                partner_ids=storekeeper_users.users.mapped('partner_id').ids
            )
            _logger.info(f"AUTO-040: Book copy retained for {len(storekeeper_users.users)} Storekeeper users")
        
        _logger.info(
            f"AUTO-040: Four-copy distribution completed for Model 19 {self.name} - "
            f"Supplier: {self.supplier_id.name if self.supplier_id else 'N/A'}, "
            f"Total Value: ETB {total_value:,.2f}, "
            f"Department Return: {self.is_no_payment}"
        )

    def action_mark_distributed(self):
        """Mark all copies as distributed."""
        for rec in self:
            if rec.state != "confirmed":
                raise UserError(
                    "Only confirmed receipts can be marked as distributed."
                )
            if not rec.all_copies_distributed:
                raise UserError(
                    "Please mark all four copies as distributed first."
                )
            rec.state = "distributed"
        return True

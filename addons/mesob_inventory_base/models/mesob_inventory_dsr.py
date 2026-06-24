from odoo import api, fields, models
from odoo.exceptions import UserError
from lxml import etree
import logging

_logger = logging.getLogger(__name__)


class MesobInventoryDSR(models.Model):
    """Damage/Shortage Report (DSR).

    Auto-generated when a receiving order has rejected items.
    Tracks four-copy distribution and discrepancy details.
    (SRS: FR-REC-008, FR-REC-009)
    """

    _name = "mesob.inventory.dsr"
    _description = "Damage/Shortage Report (DSR)"
    _order = "date desc, id desc"
    _rec_name = "name"

    # ── Reference ───────────────────────────────────────────────────
    name = fields.Char(
        string="DSR Reference",
        required=True,
        index=True,
        default=lambda self: self.env["ir.sequence"].next_by_code(
            "mesob.inventory.dsr"
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
        help="Source receiving order that generated this DSR.",
    )

    date = fields.Date(
        string="Report Date",
        required=True,
        default=fields.Date.today,
    )

    supplier_id = fields.Many2one(
        "res.partner",
        string="Supplier",
        help="Supplier whose goods were rejected.",
    )

    # ── Copy Distribution (FR-REC-008) ─────────────────────────────
    copy_supplier = fields.Selection(
        [("pending", "Pending"), ("distributed", "Distributed")],
        string="Original → Supplier",
        default="pending",
        help="Original accompanies rejected goods back to supplier.",
    )
    copy_accounts = fields.Selection(
        [("pending", "Pending"), ("distributed", "Distributed")],
        string="Duplicate → Accounts/Finance",
        default="pending",
        help="Duplicate copy → Accounts/Finance unit.",
    )
    copy_procurement = fields.Selection(
        [("pending", "Pending"), ("distributed", "Distributed")],
        string="Triplicate → Procurement Officer",
        default="pending",
        help="Triplicate copy → Procurement Officer.",
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
        "mesob.inventory.dsr.line",
        "dsr_id",
        string="DSR Lines",
    )

    # ── State ──────────────────────────────────────────────────────
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("confirmed", "Confirmed"),
            ("pending_replacement", "Pending Replacement"),
            ("replaced", "Replacement Received"),
            ("closed", "Closed"),
        ],
        required=True,
        default="draft",
        copy=False,
        index=True,
        tracking=True,
    )
    
    # ── AUTO-028: Replacement Tracking ──────────────────────────────
    purchase_order_ref = fields.Char(
        string="Linked PO Reference",
        compute="_compute_purchase_order_ref",
        store=True,
        help="AUTO-028: Linked Purchase Order for payment blocking."
    )
    
    replacement_expected_date = fields.Date(
        string="Expected Replacement Date",
        help="AUTO-028: Expected date for supplier to deliver replacement."
    )
    
    replacement_received_date = fields.Date(
        string="Actual Replacement Date",
        readonly=True,
        help="AUTO-028: Actual date when replacement was received."
    )
    
    replacement_model19_id = fields.Many2one(
        "mesob.inventory.model19",
        string="Replacement Receipt (Model 19)",
        readonly=True,
        help="AUTO-028: Model 19 for replacement goods."
    )
    
    days_overdue = fields.Integer(
        string="Days Overdue",
        compute="_compute_days_overdue",
        help="AUTO-028: Days past expected replacement date."
    )
    
    payment_blocked = fields.Boolean(
        string="Payment Blocked",
        default=False,
        help="AUTO-028: Payment blocked until replacement received (BR-PROC-002)."
    )

    note = fields.Text(string="Notes")

    # ── Computed ───────────────────────────────────────────────────
    
    @api.depends("receiving_id.purchase_order_ref")
    def _compute_purchase_order_ref(self):
        """AUTO-028: Link DSR to PO for payment blocking."""
        for rec in self:
            rec.purchase_order_ref = rec.receiving_id.purchase_order_ref if rec.receiving_id else False
    
    @api.depends("replacement_expected_date", "replacement_received_date", "state")
    def _compute_days_overdue(self):
        """AUTO-028: Calculate days overdue for replacement."""
        for rec in self:
            if rec.state == "pending_replacement" and rec.replacement_expected_date:
                if rec.replacement_received_date:
                    delta = (rec.replacement_received_date - rec.replacement_expected_date).days
                else:
                    delta = (fields.Date.today() - rec.replacement_expected_date).days
                rec.days_overdue = max(0, delta)
            else:
                rec.days_overdue = 0

    @api.depends(
        "copy_supplier", "copy_accounts",
        "copy_procurement", "copy_storekeeper"
    )
    def _compute_all_copies_distributed(self):
        for rec in self:
            rec.all_copies_distributed = all([
                rec.copy_supplier == "distributed",
                rec.copy_accounts == "distributed",
                rec.copy_procurement == "distributed",
                rec.copy_storekeeper == "distributed",
            ])

    # ── View Customization ──────────────────────────────────────────

    @api.model
    def get_view(self, view_id=None, view_type="form", **options):
        """Hide New button for PAO and Stock Clerk on both list and form views.
        
        DSRs are auto-generated from Receiving Orders when items are rejected.
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
        """AUTO-028: Confirm DSR and trigger procurement loop closure.
        
        Compliance: FR-REC-008, FR-PROC-032, BR-PROC-002
        """
        for rec in self:
            if rec.state != "draft":
                raise UserError("Only draft DSRs can be confirmed.")
            
            rec.state = "confirmed"
            
            # AUTO-028: Auto-distribute four copies digitally (FR-REC-008)
            rec._auto_distribute_dsr_copies()
            
            # AUTO-028: Notify Procurement Officer (FR-PROC-032)
            rec._notify_procurement_officer()
            
            # AUTO-028: Block payment on linked PO (BR-PROC-002)
            rec._block_payment_on_po()
            
            # AUTO-028: Set to pending replacement
            rec.state = "pending_replacement"
            rec.payment_blocked = True
            
            _logger.info(
                f"AUTO-028: DSR {rec.name} confirmed - Payment blocked on PO {rec.purchase_order_ref}, "
                f"Procurement notified"
            )
        
        return True
    
    def _auto_distribute_dsr_copies(self):
        """AUTO-041: Four-Copy DSR Distribution Auto-Routing (FR-REC-008).
        
        Distribution per FR-REC-008:
        1. Original → Supplier (accompanies rejected goods)
        2. Duplicate → Accounts/Finance (blocks payment)
        3. Triplicate → Procurement Officer (triggers return workflow)
        4. Book Copy → Storekeeper (retained)
        """
        self.ensure_one()
        
        # Build items summary
        items_summary = '<ul>'
        for line in self.line_ids:
            discrepancy_label = dict(line._fields['discrepancy_type'].selection).get(line.discrepancy_type, 'Unknown')
            items_summary += f'<li><strong>{line.item_id.item_code if line.item_id else "N/A"}</strong>: {line.quantity} {line.uom_id.name if line.uom_id else "units"} - <span style="color: #dc3545;">{discrepancy_label}</span>{" - " + line.notes if line.notes else ""}</li>'
        items_summary += '</ul>'
        
        # 1. Original → Supplier
        if self.supplier_id:
            supplier_message = f"""<div style="background-color: #f8d7da; border-left: 4px solid #dc3545; padding: 15px;">
                <h3>🚫 DSR - ORIGINAL COPY (Supplier)</h3>
                <p><strong>DSR Reference:</strong> {self.name}</p>
                <p><strong>Date:</strong> {self.date}</p>
                <p><strong>PO Reference:</strong> {self.purchase_order_ref or 'N/A'}</p>
                <hr/>
                <h4>Rejected Items:</h4>
                {items_summary}
                <hr/>
                <div style="background-color: #fff3cd; padding: 10px; border-radius: 4px; margin-top: 15px;">
                    <p style="margin: 0;"><strong>⚠ ACTION REQUIRED:</strong></p>
                    <p style="margin: 5px 0 0 0;">These items have been rejected. Please arrange replacement delivery as per contract terms. This copy accompanies the rejected goods being returned to you.</p>
                </div>
            </div>"""
            
            if self.supplier_id.email:
                self.message_post(
                    body=supplier_message,
                    subject=f'Rejection Notice (DSR): {self.name}',
                    message_type='email',
                    partner_ids=[self.supplier_id.id],
                    email_from=self.env.company.email or self.env.user.email,
                )
                _logger.info(f"AUTO-041: DSR {self.name} original copy sent to supplier via email")
            else:
                self.message_post(
                    body=supplier_message,
                    subject=f'[ORIGINAL] DSR for Supplier: {self.name}',
                    message_type='comment',
                    partner_ids=[self.supplier_id.id]
                )
                _logger.info(f"AUTO-041: DSR {self.name} original copy logged for supplier (no email)")
        
        # 2. Duplicate → Accounts/Finance (blocks payment per BR-PROC-002)
        accounts_users = self.env.ref('mesob_inventory_base.group_mesob_pao', raise_if_not_found=False)
        if accounts_users and accounts_users.users:
            self.message_post(
                body=f"""<div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px;">
                    <h3>🚫 DSR - DUPLICATE COPY (Accounts/Finance)</h3>
                    <p><strong>DSR Reference:</strong> {self.name}</p>
                    <p><strong>Date:</strong> {self.date}</p>
                    <p><strong>Supplier:</strong> {self.supplier_id.name if self.supplier_id else 'N/A'}</p>
                    <p><strong>PO Reference:</strong> {self.purchase_order_ref or 'N/A'}</p>
                    <hr/>
                    <h4>Rejected Items:</h4>
                    {items_summary}
                    <hr/>
                    <div style="background-color: #dc3545; color: white; padding: 10px; border-radius: 4px; margin-top: 15px;">
                        <p style="margin: 0;"><strong>🚫 PAYMENT BLOCKED (BR-PROC-002)</strong></p>
                        <p style="margin: 5px 0 0 0;">Payment for PO {self.purchase_order_ref or 'N/A'} is now <strong>BLOCKED</strong> until replacement goods are received and accepted (Model 19 issued). Do NOT process payment until this DSR is closed.</p>
                    </div>
                </div>""",
                subject=f'[DUPLICATE] DSR - Payment Blocked: {self.name}',
                message_type='notification',
                partner_ids=accounts_users.users.mapped('partner_id').ids
            )
            _logger.info(f"AUTO-041: DSR {self.name} duplicate copy sent to Accounts (payment blocked)")
        
        # 3. Triplicate → Procurement Officer (triggers return workflow per FR-PROC-032)
        procurement_users = self.env.ref('mesob_inventory_base.group_mesob_procurement', raise_if_not_found=False)
        if procurement_users and procurement_users.users:
            self.message_post(
                body=f"""<div style="background-color: #e7f3ff; border-left: 4px solid #0066cc; padding: 15px;">
                    <h3>🚫 DSR - TRIPLICATE COPY (Procurement Officer)</h3>
                    <p><strong>DSR Reference:</strong> {self.name}</p>
                    <p><strong>Date:</strong> {self.date}</p>
                    <p><strong>Supplier:</strong> {self.supplier_id.name if self.supplier_id else 'N/A'}</p>
                    <p><strong>PO Reference:</strong> {self.purchase_order_ref or 'N/A'}</p>
                    <hr/>
                    <h4>Rejected Items:</h4>
                    {items_summary}
                    <hr/>
                    <div style="background-color: #fff3cd; padding: 10px; border-radius: 4px; margin-top: 15px;">
                        <p style="margin: 0;"><strong>⚠ ACTION REQUIRED (FR-PROC-032):</strong></p>
                        <ul style="margin: 5px 0 0 0;">
                            <li>Issue formal rejection notice to supplier</li>
                            <li>Track supplier response and replacement timeline</li>
                            <li>Update PO delivery status to "Pending Replacement"</li>
                            <li>Monitor replacement delivery</li>
                            <li>Coordinate with Storekeeper for replacement inspection</li>
                        </ul>
                        <p style="margin: 10px 0 0 0;"><em>AUTO-028: PO status updated automatically. Payment blocked until replacement received.</em></p>
                    </div>
                    <p style="margin-top: 15px;"><a href="/web#id={self.id}&model=mesob.inventory.dsr&view_type=form" 
                       style="background-color: #0066cc; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                       View DSR & Track Replacement →
                    </a></p>
                </div>""",
                subject=f'[TRIPLICATE] DSR - Supplier Return Required: {self.name}',
                message_type='notification',
                partner_ids=procurement_users.users.mapped('partner_id').ids
            )
            _logger.info(f"AUTO-041: DSR {self.name} triplicate copy sent to Procurement Officer")
        
        # 4. Book Copy → Storekeeper
        storekeeper_users = self.env.ref('mesob_inventory_base.group_mesob_storekeeper', raise_if_not_found=False)
        if storekeeper_users and storekeeper_users.users:
            self.message_post(
                body=f"""<div style="background-color: #d1ecf1; border-left: 4px solid #0c5460; padding: 15px;">
                    <h3>🚫 DSR - BOOK COPY (Storekeeper)</h3>
                    <p><strong>DSR Reference:</strong> {self.name}</p>
                    <p><strong>Date:</strong> {self.date}</p>
                    <p><strong>Supplier:</strong> {self.supplier_id.name if self.supplier_id else 'N/A'}</p>
                    <hr/>
                    <h4>Rejected Items:</h4>
                    {items_summary}
                    <hr/>
                    <p><em>This is your retained copy for store records. Rejected goods should be segregated and returned to supplier per Procurement Officer instructions.</em></p>
                </div>""",
                subject=f'[BOOK COPY] DSR Retained: {self.name}',
                message_type='comment',
                partner_ids=storekeeper_users.users.mapped('partner_id').ids
            )
            _logger.info(f"AUTO-041: DSR {self.name} book copy retained for Storekeeper")
        
        # Mark all copies as distributed
        self.write({
            'copy_supplier': 'distributed',
            'copy_accounts': 'distributed',
            'copy_procurement': 'distributed',
            'copy_storekeeper': 'distributed',
        })
        
        _logger.info(f"AUTO-041: DSR {self.name} - Four copies auto-distributed digitally")
    
    def _notify_procurement_officer(self):
        """AUTO-028: Notify Procurement Officer of rejection (FR-PROC-032).
        
        Enhanced notification:
        - Alerts PAO of supplier deficiency
        - Tracks replacement expected date
        - Provides action guidance for supplier coordination
        """
        self.ensure_one()
        
        # Find PAO users
        pao_group = self.env.ref('mesob_inventory_base.group_mesob_pao', raise_if_not_found=False)
        if not pao_group or not pao_group.users:
            _logger.warning(f"AUTO-028: PAO group not found or has no users for DSR {self.name}")
            return
        
        # Build items summary
        items_summary = '<ul>'
        for line in self.line_ids:
            items_summary += (
                f'<li><strong>{line.item_id.item_code}</strong>: {line.rejected_quantity} '
                f'{line.uom_id.name if line.uom_id else "units"} - {line.item_id.name}<br/>'
                f'<em>Reason: {line.rejection_reason or "See main DSR reason"}</em></li>'
            )
        items_summary += '</ul>'
        
        # Send notification to PAO
        self.message_post(
            body=f"""<div style="background-color: #fff3cd; border-left: 4px solid #ff6b6b; padding: 15px;">
                <h3>🚨 AUTO-028: DSR Issued - Supplier Action Required</h3>
                <p><strong>DSR Number:</strong> {self.name}</p>
                <p><strong>Supplier:</strong> {self.supplier_id.name if self.supplier_id else 'N/A'}</p>
                <p><strong>Purchase Order:</strong> {self.purchase_order_ref or 'N/A'}</p>
                <p><strong>Issue Date:</strong> {self.issue_date or fields.Date.today()}</p>
                <hr/>
                <h4>Rejection Details:</h4>
                <p><strong>Reason:</strong> {self.rejection_reason or 'Not specified'}</p>
                <p><strong>Deficiency Type:</strong> {dict(self._fields['deficiency_type'].selection).get(self.deficiency_type, 'N/A') if self.deficiency_type else 'N/A'}</p>
                <hr/>
                <h4>Rejected Items:</h4>
                {items_summary}
                <hr/>
                <div style="background-color: #ffe7e7; padding: 10px; border-radius: 4px; margin-top: 15px;">
                    <p style="margin: 0;"><strong>⚠️ CRITICAL ACTION REQUIRED:</strong></p>
                    <ul style="margin: 5px 0;">
                        <li><strong>Coordinate with supplier</strong> for replacement delivery</li>
                        <li><strong>Expected Replacement Date:</strong> {self.replacement_expected_date or '<em>To be determined</em>'}</li>
                        <li><strong>Payment Status:</strong> <span style="color: #dc3545; font-weight: bold;">BLOCKED (BR-PROC-002)</span></li>
                        <li><strong>Payment will remain blocked</strong> until replacement goods are received and accepted</li>
                    </ul>
                </div>
                <hr/>
                <div style="background-color: #e7f3ff; padding: 10px; border-radius: 4px; margin-top: 10px;">
                    <p style="margin: 0;"><strong>Next Steps:</strong></p>
                    <ol style="margin: 5px 0;">
                        <li>Contact supplier immediately regarding rejected items</li>
                        <li>Negotiate replacement delivery date</li>
                        <li>Update DSR with expected replacement date</li>
                        <li>Monitor supplier compliance</li>
                        <li>Once replacement received, mark DSR as resolved</li>
                    </ol>
                </div>
                <p style="margin-top: 15px;"><a href="/web#id={self.id}&model=mesob.inventory.dsr&view_type=form" 
                   style="background-color: #ff6b6b; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                   Review DSR Details →
                </a></p>
            </div>""",
            subject=f'[URGENT] DSR {self.name} - Supplier Replacement Required',
            partner_ids=pao_group.users.mapped('partner_id').ids,
            message_type='notification'
        )
        
        _logger.info(
            f"AUTO-028: PAO notified of DSR {self.name} - Supplier: {self.supplier_id.name if self.supplier_id else 'N/A'}, "
            f"Expected Replacement: {self.replacement_expected_date or 'TBD'}"
        )
    
    def _block_payment_on_po(self):
        """AUTO-028: Block payment on linked PO (BR-PROC-002).
        
        Updates PO status and posts blocking notification.
        """
        self.ensure_one()
        
        if not self.purchase_order_ref:
            _logger.warning(f"AUTO-028: DSR {self.name} has no linked PO reference")
            return
        
        # Find linked PO
        po = self.env['mesob.procurement.order'].search([
            ('name', '=', self.purchase_order_ref)
        ], limit=1)
        
        if not po:
            _logger.warning(f"AUTO-028: PO {self.purchase_order_ref} not found for DSR {self.name}")
            return
        
        # Update PO status
        po.write({
            'state': 'pending_replacement',
        })
        
        # Post payment block notification to PO
        po.message_post(
            body=f"""<div style="background-color: #f8d7da; border-left: 4px solid #dc3545; padding: 15px;">
                <h4>🚫 PAYMENT BLOCKED (BR-PROC-002)</h4>
                <p><strong>DSR Created:</strong> {self.name}</p>
                <p><strong>Date:</strong> {self.date}</p>
                <p><strong>Rejected Items:</strong> {len(self.line_ids)} line(s)</p>
                <hr/>
                <p><strong>⚠ Payment for this Purchase Order is now BLOCKED</strong> until replacement goods are:</p>
                <ol>
                    <li>Delivered by supplier</li>
                    <li>Inspected and accepted by Storekeeper</li>
                    <li>Model 19 (replacement receipt) issued</li>
                    <li>DSR closed by Procurement Officer</li>
                </ol>
                <p><em>AUTO-028: This is an automated payment block per BR-PROC-002. Do NOT process payment until this DSR is resolved.</em></p>
                <p style="margin-top: 15px;"><a href="/web#id={self.id}&model=mesob.inventory.dsr&view_type=form" 
                   style="background-color: #dc3545; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                   View DSR →
                </a></p>
            </div>""",
            subject=f'Payment Blocked - DSR {self.name}',
            message_type='comment'
        )
        
        _logger.info(
            f"AUTO-028: Payment blocked on PO {po.name} due to DSR {self.name} - "
            f"Status changed to 'pending_replacement'"
        )
    
    def action_record_replacement_received(self, model19_id):
        """AUTO-028: Record replacement goods received and unblock payment.
        
        Called when replacement goods are accepted and Model 19 is issued.
        Closes the DSR loop and unblocks payment.
        """
        self.ensure_one()
        
        if self.state != "pending_replacement":
            raise UserError("Only DSRs pending replacement can be closed.")
        
        self.write({
            'state': 'replaced',
            'replacement_model19_id': model19_id,
            'replacement_received_date': fields.Date.today(),
            'payment_blocked': False,
        })
        
        # Unblock payment on PO
        if self.purchase_order_ref:
            po = self.env['mesob.procurement.order'].search([
                ('name', '=', self.purchase_order_ref)
            ], limit=1)
            
            if po:
                # Check if all DSRs for this PO are resolved
                open_dsrs = self.search([
                    ('purchase_order_ref', '=', self.purchase_order_ref),
                    ('state', '=', 'pending_replacement')
                ])
                
                if not open_dsrs:
                    # All DSRs resolved - unblock payment
                    po.write({
                        'state': 'partially_received',  # Or fully_received if appropriate
                    })
                    
                    po.message_post(
                        body=f"""<div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px;">
                            <h4>✅ PAYMENT UNBLOCKED</h4>
                            <p><strong>DSR Resolved:</strong> {self.name}</p>
                            <p><strong>Replacement Receipt:</strong> {model19_id.name if model19_id else 'N/A'}</p>
                            <p><strong>Date:</strong> {fields.Date.today()}</p>
                            <hr/>
                            <p>All DSRs for this PO have been resolved. Replacement goods received and accepted. Payment is now UNBLOCKED and can proceed through three-way match.</p>
                            <p><em>AUTO-028: Automated payment unblock per DSR closure.</em></p>
                        </div>""",
                        subject=f'Payment Unblocked - DSR {self.name} Resolved'
                    )
                    
                    _logger.info(
                        f"AUTO-028: Payment unblocked on PO {po.name} - "
                        f"DSR {self.name} resolved with replacement Model 19 {model19_id.name if model19_id else 'N/A'}"
                    )
        
        # Notify Procurement Officer
        procurement_users = self.env.ref('mesob_inventory_base.group_mesob_procurement', raise_if_not_found=False)
        if procurement_users and procurement_users.users:
            self.message_post(
                body=f"""<div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px;">
                    <h4>✅ AUTO-028: DSR Closed - Replacement Received</h4>
                    <p><strong>DSR:</strong> {self.name}</p>
                    <p><strong>Replacement Receipt:</strong> {model19_id.name if model19_id else 'N/A'}</p>
                    <p><strong>Received Date:</strong> {fields.Date.today()}</p>
                    {f'<p><strong>Days Late:</strong> {self.days_overdue} days</p>' if self.days_overdue > 0 else ''}
                    <hr/>
                    <p>Replacement goods have been received and accepted. DSR loop closed. Payment unblocked.</p>
                </div>""",
                subject=f'DSR Closed: {self.name}',
                message_type='notification',
                partner_ids=procurement_users.users.mapped('partner_id').ids
            )
        
        return True
    
    def action_close_dsr(self):
        """Close DSR manually (e.g., supplier credit note issued instead of replacement)."""
        for rec in self:
            if rec.state not in ("pending_replacement", "replaced"):
                raise UserError("Only pending or replaced DSRs can be closed.")
            
            rec.state = "closed"
            rec.payment_blocked = False
            
            # Unblock payment if needed
            if rec.purchase_order_ref:
                po = self.env['mesob.procurement.order'].search([
                    ('name', '=', rec.purchase_order_ref)
                ], limit=1)
                
                if po:
                    open_dsrs = self.search([
                        ('purchase_order_ref', '=', rec.purchase_order_ref),
                        ('payment_blocked', '=', True)
                    ])
                    
                    if not open_dsrs:
                        po.message_post(
                            body=f"""<p><strong>Payment Unblocked:</strong> DSR {rec.name} closed manually.</p>""",
                            subject='Payment Unblocked'
                        )
        
        return True

    def action_mark_returned(self):
        """Mark goods as returned to supplier (deprecated - use action_confirm instead)."""
        for rec in self:
            if rec.state != "confirmed":
                raise UserError(
                    "Only confirmed DSRs can be marked as returned."
                )
            # This method is kept for backward compatibility but state flow changed
            rec.state = "pending_replacement"
        return True

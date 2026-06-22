from odoo import api, fields, models
from odoo.exceptions import UserError
from lxml import etree
import logging

_logger = logging.getLogger(__name__)


class MesobInventoryRequisition(models.Model):
    """Stores Requisition (Model 20).

    Raised by user departments and approved by PAO before stock issue.
    Supports three issue modes: imprest, replacement, and non-stock.
    (SRS: FR-ISSUE-001, FR-ISSUE-002, FR-ISSUE-003)
    
    AUTO-042: Self-Service Requisition Submission
    - Department users submit requisitions online via self-service form
    - Real-time stock availability display at submission time
    - System pre-fills last issued quantity and suggests order quantity
    - System checks requester authorization vs. item restrictions (FR-ISSUE-004)
    - Auto-routes to PAO for approval with 1-click interface
    - Rejection returns to requester with mandatory comment
    
    AUTO-043: Stock Availability Alert Before Approval
    - Displays real-time stock on hand per item during PAO approval
    - Alerts if stock insufficient with:
      * Current stock level
      * Pending open requisitions for same item
      * Expected delivery date from open PO
    - PAO can approve partial quantity or defer until stock available
    """

    _name = "mesob.inventory.requisition"
    _description = "Stores Requisition (Model 20)"
    _inherit = ['mail.thread', 'mail.activity.mixin', 'mesob.notification.mixin', 'mesob.signable.mixin']  # Task 7: notification, Task 11: digital signature
    _order = "requested_on desc, id desc"

    name = fields.Char(
        string="Requisition Reference",
        required=True,
        index=True,
        default=lambda self: self.env["ir.sequence"].next_by_code(
            "mesob.inventory.requisition"
        ) or "New",
        copy=False,
        readonly=True,
        help="Auto-generated controlled reference number.",
    )

    # ── Issue Mode (FR-ISSUE-001) ───────────────────────────────────────

    issue_mode = fields.Selection(
        [
            ("imprest", "Imprest Basis"),
            ("replacement", "Replacement Issue"),
            ("non_stock", "Non-Stock Issue"),
        ],
        string="Issue Mode",
        required=True,
        default="imprest",
        help=(
            "Imprest: scheduled periodic issue. "
            "Replacement: replace consumed items. "
            "Non-stock: one-time special issue."
        ),
    )

    # ── Requester Info ──────────────────────────────────────────────────

    requested_by_id = fields.Many2one(
        "res.users",
        string="Requested By",
        required=True,
        default=lambda self: self.env.user,
        tracking=True,
    )
    
    # AUTO-042: Requester role and authorization tracking
    requester_role = fields.Selection([
        ('staff', 'Staff'),
        ('department_head', 'Department Head'),
        ('authorized_officer', 'Authorized Officer'),
    ], string="Requester Role", compute='_compute_requester_role', store=True)
    
    department = fields.Selection(
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
        string="Requesting Department",
        required=True,
        tracking=True,
        help="AUTO-042: Department requesting the materials (self-service submission).",
    )
    requested_on = fields.Date(
        string="Requested On",
        required=True,
        default=fields.Date.today,
        tracking=True,
    )
    
    # AUTO-042: Submission tracking
    submitted_on = fields.Datetime(
        string="Submitted On",
        readonly=True,
        tracking=True,
        help="AUTO-042: Timestamp when requisition was submitted to PAO"
    )
    
    purpose = fields.Text(
        string="Purpose/Justification",
        required=True,
        help="AUTO-042: Explain why these items are needed (mandatory for submission)"
    )

    # ── Approval Info ───────────────────────────────────────────────────

    approved_by_id = fields.Many2one(
        "res.users",
        string="Approved By (PAO)",
        readonly=True,
        copy=False,
    )
    approved_on = fields.Date(
        string="Approved On",
        readonly=True,
        copy=False,
    )
    rejection_reason = fields.Text(
        string="Rejection Reason",
        readonly=True,
        copy=False,
    )

    # ── State Machine ───────────────────────────────────────────────────

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
            ("issued", "Issued"),
            ("received", "Received"),
            ("cancelled", "Cancelled"),
        ],
        required=True,
        default="draft",
        copy=False,
        index=True,
        tracking=True,
    )

    # ── Lines ───────────────────────────────────────────────────────────

    line_ids = fields.One2many(
        "mesob.inventory.requisition.line",
        "requisition_id",
        string="Requisition Lines",
        copy=True,
    )

    # ── Issue Vouchers ──────────────────────────────────────────────────

    issue_voucher_ids = fields.One2many(
        "mesob.inventory.issue.voucher",
        "requisition_id",
        string="Issue Vouchers",
        readonly=True,
    )

    issue_voucher_count = fields.Integer(
        string="Issue Voucher Count",
        compute="_compute_issue_voucher_count",
    )

    note = fields.Text(string="Internal Notes")
    
    # ── Task 9: QR Code for Requisition Identification ─────────────────
    
    qr_code = fields.Binary(
        string="Requisition QR Code",
        compute="_compute_qr_code",
        store=True,
        help="Task 9: QR code for requisition identification - encodes requisition number"
    )

    # ── Computed Fields ─────────────────────────────────────────────────

    @api.depends("issue_voucher_ids")
    def _compute_issue_voucher_count(self):
        for record in self:
            record.issue_voucher_count = len(record.issue_voucher_ids)
    
    @api.depends("name", "state")
    def _compute_qr_code(self):
        """Task 9: Generate QR code for requisition identification.
        
        QR code contains: Requisition number + Department + Requested date
        Used for: Tracking, Issue Voucher linking, Stock-taking
        """
        try:
            import qrcode
            import base64
            from io import BytesIO
            import logging
            _logger = logging.getLogger(__name__)
        except ImportError:
            # QR code library not installed
            for record in self:
                record.qr_code = False
            return
        
        for record in self:
            if record.name and record.name != "New":
                # Generate QR code data
                dept_label = dict(record._fields['department'].selection).get(record.department, 'Unknown')
                qr_data = f"MESOB-REQ:{record.name}|DEPT:{dept_label}|DATE:{record.requested_on}"
                
                # Create QR code
                qr = qrcode.QRCode(version=1, box_size=10, border=4)
                qr.add_data(qr_data)
                qr.make(fit=True)
                
                img = qr.make_image(fill_color="black", back_color="white")
                
                # Convert to binary
                buffer = BytesIO()
                img.save(buffer, format="PNG")
                qr_code_binary = base64.b64encode(buffer.getvalue())
                
                record.qr_code = qr_code_binary
                _logger.debug(f"Task 9: Generated QR code for requisition {record.name}")
            else:
                record.qr_code = False
    
    @api.depends('requested_by_id')
    def _compute_requester_role(self):
        """AUTO-042: Determine requester role from user groups."""
        for record in self:
            user = record.requested_by_id
            if not user:
                record.requester_role = 'staff'
                continue
            
            # Check roles in priority order
            if user.has_group('mesob_inventory_base.group_mesob_pao'):
                record.requester_role = 'authorized_officer'
            elif user.has_group('base.group_user'):  # Typically department heads
                record.requester_role = 'department_head'
            else:
                record.requester_role = 'staff'

    # ── View Customization ──────────────────────────────────────────────

    @api.model
    def get_view(self, view_id=None, view_type="form", **options):
        """Hide New button for operational roles even if they also have Inventory User group.
        
        Priority-based logic:
        1. If user is PAO, Storekeeper, or Stock Clerk → HIDE create (even if also Inventory User)
        2. Only if user is PURELY Inventory User → SHOW create
        
        This handles cases where PAO might also have Inventory User group assigned.

        Covers: kanban, list, form views
        """
        result = super().get_view(view_id, view_type, **options)

        if view_type in ("kanban", "list", "form"):
            user = self.env.user
            
            # Check operational roles FIRST (these should NOT create)
            is_pao = user.has_group("mesob_inventory_base.group_mesob_pao")
            is_storekeeper = user.has_group("mesob_inventory_base.group_mesob_storekeeper")
            is_stock_clerk = user.has_group("mesob_inventory_base.group_mesob_stock_clerk")
            is_auditor = user.has_group("mesob_inventory_base.group_mesob_auditor")
            
            # If user has ANY operational role, hide create button (even if they also have inventory_user)
            if is_pao or is_storekeeper or is_stock_clerk or is_auditor:
                arch = result.get("arch", "")
                if isinstance(arch, str):
                    arch = arch.encode("utf-8")
                root = etree.fromstring(arch)
                root.set("create", "0")
                result["arch"] = etree.tostring(
                    root, encoding="unicode", pretty_print=False
                )

        return result

    # ── Actions ─────────────────────────────────────────────────────────

    def action_submit(self):
        """AUTO-042: Department user submits requisition for PAO approval (FR-ISSUE-002).
        
        Enhanced with:
        - Validation of purpose/justification (mandatory)
        - Authorization check for controlled items (FR-ISSUE-004)
        - Real-time stock availability display
        - Auto-notification to PAO with requisition summary
        """
        for record in self:
            if record.state != "draft":
                raise UserError("Only draft requisitions can be submitted.")
            if not record.line_ids:
                raise UserError("Please add at least one item before submitting.")
            
            # AUTO-042: Validate purpose/justification
            if not record.purpose or len(record.purpose) < 20:
                raise UserError(
                    "AUTO-042: Purpose/Justification is mandatory and must be at least 20 characters.\n"
                    "Please explain why these items are needed."
                )
            
            # AUTO-042: Check authorization for controlled items (FR-ISSUE-004)
            unauthorized_items = record._check_controlled_item_authorization()
            if unauthorized_items:
                items_list = '\n'.join([f"• {item}" for item in unauthorized_items])
                raise UserError(
                    f"AUTO-042 / FR-ISSUE-004: You are not authorized to request the following controlled items:\n\n"
                    f"{items_list}\n\n"
                    f"Controlled items require authorized personnel approval."
                )
            
            # Submit requisition
            record.write({
                'state': 'submitted',
                'submitted_on': fields.Datetime.now(),
            })
            
            # AUTO-042: Send notification to PAO
            record._notify_pao_new_requisition()
            
            _logger.info(
                f"AUTO-042: Requisition {record.name} submitted by {record.requested_by_id.name} - "
                f"Department: {record.department}, Items: {len(record.line_ids)}"
            )
            
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Requisition Submitted',
                'message': 'Your requisition has been submitted to PAO for approval.',
                'type': 'success',
                'sticky': False,
            }
        }
    
    def _check_controlled_item_authorization(self):
        """AUTO-042: Check if requester is authorized for controlled items (FR-ISSUE-004).
        
        Returns list of unauthorized controlled item names.
        """
        self.ensure_one()
        
        unauthorized_items = []
        
        for line in self.line_ids:
            if line.item_id and line.item_id.is_controlled:
                # Check if requester has authorization for controlled items
                # TODO: Implement proper authorization matrix
                # For now, only PAO and authorized officers can request controlled items
                if self.requester_role not in ['authorized_officer']:
                    unauthorized_items.append(
                        f"{line.item_id.item_code} - {line.item_id.name} (Controlled Material)"
                    )
        
        return unauthorized_items
    
    def _notify_pao_new_requisition(self):
        """AUTO-042: Send notification to PAO of new requisition submission.
        
        Task 7: Enhanced with activity notification for real-time alerts.
        """
        self.ensure_one()
        
        # Get PAO users
        pao_group = self.env.ref('mesob_inventory_base.group_mesob_pao', raise_if_not_found=False)
        if not pao_group or not pao_group.users:
            return
        
        dept_label = dict(self._fields['department'].selection).get(self.department, 'Unknown')
        
        # Build items summary
        items_html = '<ul>'
        for line in self.line_ids:
            if line.item_id:
                items_html += f'<li><strong>{line.item_id.item_code}</strong> - {line.item_id.name}: Qty {line.quantity}</li>'
            else:
                items_html += f'<li>{line.major_classification_id.name if line.major_classification_id else "Unknown"}: Qty {line.quantity}</li>'
        items_html += '</ul>'
        
        # Task 7: Schedule activity for PAO users
        self._schedule_activity(
            activity_code='mesob_activity_requisition_approval',
            user_ids=pao_group.users.ids,
            summary=f'Requisition Approval Required: {self.name}',
            note=f"""<p><strong>Department:</strong> {dept_label}</p>
                <p><strong>Requested by:</strong> {self.requested_by_id.name}</p>
                <p><strong>Items:</strong> {len(self.line_ids)}</p>
                <p><strong>Purpose:</strong> {self.purpose or 'Not specified'}</p>""",
        )
        
        # Send chatter notification (for audit trail)
        self.message_post(
            body=f"""<div style="background-color: #d1ecf1; border-left: 4px solid #0c5460; padding: 15px;">
                <h3>📝 AUTO-042: New Requisition Submitted</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 5px 0;"><strong>Requisition:</strong></td>
                        <td style="padding: 5px 0;">{self.name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 0;"><strong>Department:</strong></td>
                        <td style="padding: 5px 0;">{dept_label}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 0;"><strong>Requested By:</strong></td>
                        <td style="padding: 5px 0;">{self.requested_by_id.name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 0;"><strong>Issue Mode:</strong></td>
                        <td style="padding: 5px 0;">{dict(self._fields['issue_mode'].selection).get(self.issue_mode, '')}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 0;"><strong>Items:</strong></td>
                        <td style="padding: 5px 0;">{len(self.line_ids)} item(s)</td>
                    </tr>
                </table>
                <hr/>
                <h4>Items Requested:</h4>
                {items_html}
                <hr/>
                <p><strong>Purpose:</strong></p>
                <p style="background-color: white; padding: 10px; border-radius: 4px;">{self.purpose}</p>
                <p style="margin-top: 15px;">
                    <a href="/web#id={self.id}&model=mesob.inventory.requisition&view_type=form" 
                       style="background-color: #17a2b8; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                       Review & Approve →
                    </a>
                </p>
            </div>""",
            subject=f'New Requisition: {self.name} - {dept_label}',
            message_type='notification',
            partner_ids=pao_group.users.mapped('partner_id').ids
        )
        
        _logger.info(
            f"AUTO-042: Notification sent to {len(pao_group.users)} PAO users for requisition {self.name}"
        )

    def action_approve(self):
        """PAO approves the requisition (FR-ISSUE-002).
        
        AUTO-043: Enhanced with stock availability alert before approval.
        Task 7: Mark notification activity as done.
        """
        for record in self:
            if record.state != "submitted":
                raise UserError("Only submitted requisitions can be approved.")
            
            # AUTO-043: Check stock availability before approval
            stock_warnings = self._check_stock_availability()
            
            if stock_warnings:
                # Show stock availability alert
                warning_html = self._format_stock_availability_alert(stock_warnings)
                
                # Return wizard to show stock warnings
                return {
                    'name': 'Stock Availability Alert',
                    'type': 'ir.actions.act_window',
                    'res_model': 'mesob.requisition.stock.alert.wizard',
                    'view_mode': 'form',
                    'target': 'new',
                    'context': {
                        'default_requisition_id': record.id,
                        'default_warning_message': warning_html,
                        'default_stock_warnings': stock_warnings,
                    },
                }
            
            # If no warnings, proceed with approval
            record.approved_by_id = self.env.user
            record.approved_on = fields.Date.today()
            record.state = "approved"
            
            # Task 11: Create digital signature for PAO approval
            record.action_create_digital_signature(
                signature_type='approval',
                reason=f'PAO Approval of Requisition {record.name}'
            )
            
            # Task 7: Mark approval activity as done
            activity_type = record._get_activity_type('mesob_activity_requisition_approval')
            activities = record.activity_ids.filtered(
                lambda a: a.activity_type_id == activity_type and a.user_id == self.env.user
            )
            if activities:
                activities.action_done()
        
        return True
    
    def _check_stock_availability(self):
        """AUTO-043: Check real-time stock availability for all requisition lines.
        
        Returns list of warnings with:
        - Item code and name
        - Requested quantity
        - Current stock level (from latest bin card balance)
        - Pending requisitions for same item
        - Expected delivery date from open POs
        """
        self.ensure_one()
        warnings = []
        
        StockMixin = self.env['mesob.stock.movement.mixin']
        
        for line in self.line_ids:
            if not line.item_id:
                continue
            
            # AUTO-049: Get real-time stock level
            current_stock = StockMixin.get_current_stock_level(line.item_id.id)
            
            if current_stock < line.quantity_requested:
                shortfall = line.quantity_requested - current_stock
                
                # Check pending requisitions
                pending_qty = sum(
                    self.env['mesob.inventory.requisition.line'].search([
                        ('item_id', '=', line.item_id.id),
                        ('requisition_id.state', 'in', ['approved']),
                        ('requisition_id.id', '!=', self.id),
                    ]).mapped('quantity_requested')
                )
                
                warnings.append({
                    'item_id': line.item_id.id,
                    'item_name': line.item_id.name,
                    'item_code': line.item_id.code or '',
                    'requested': line.quantity_requested,
                    'available': current_stock,
                    'shortfall': shortfall,
                    'pending_requisitions_qty': pending_qty,
                    'expected_delivery_date': None,  # TODO: From open POs
                })
        
        return warnings
        
        for line in self.line_ids:
            if not line.item_id:
                continue
            
            item = line.item_id
            requested_qty = line.quantity
            
            # Get current stock level from latest bin card
            latest_bin_card = BinCard.search([
                ('sub_classification_id', '=', item.sub_classification_id.id),
                ('location', '=', 'Main Store')
            ], order='date desc, id desc', limit=1)
            
            current_stock = latest_bin_card.balance if latest_bin_card else 0.0
            
            # Get pending approved requisitions for same item (excluding this one)
            pending_requisitions = Requisition.search([
                ('state', '=', 'approved'),
                ('id', '!=', self.id)
            ])
            
            pending_qty = 0.0
            for pending_req in pending_requisitions:
                for pending_line in pending_req.line_ids.filtered(lambda l: l.item_id == item):
                    pending_qty += pending_line.quantity
            
            # Calculate available stock after pending requisitions
            available_stock = current_stock - pending_qty
            
            # Check if stock is insufficient
            if available_stock < requested_qty:
                # Find open POs with this item
                open_pos = PurchaseOrder.search([
                    ('state', 'in', ['approved', 'sent']),
                ])
                
                expected_delivery = None
                expected_qty = 0.0
                
                for po in open_pos:
                    for po_line in po.line_ids.filtered(lambda l: l.item_id == item):
                        remaining_qty = po_line.quantity - po_line.qty_received
                        if remaining_qty > 0:
                            expected_qty += remaining_qty
                            # Use PO order date + estimated lead time (assume 30 days if not specified)
                            if po.date_order:
                                from datetime import timedelta
                                estimated_delivery = po.date_order + timedelta(days=30)
                                if not expected_delivery or estimated_delivery < expected_delivery:
                                    expected_delivery = estimated_delivery
                
                warnings.append({
                    'item_code': item.item_code,
                    'item_name': item.name,
                    'requested_qty': requested_qty,
                    'current_stock': current_stock,
                    'pending_qty': pending_qty,
                    'available_stock': available_stock,
                    'shortage': requested_qty - available_stock,
                    'expected_delivery': expected_delivery,
                    'expected_qty': expected_qty,
                    'can_partial': available_stock > 0,
                })
        
        return warnings
    
    def _format_stock_availability_alert(self, warnings):
        """AUTO-043: Format stock warnings into HTML for display."""
        html = """<div style="font-family: Arial, sans-serif;">
            <h3 style="color: #856404; background-color: #fff3cd; padding: 10px; border-left: 4px solid #ffc107;">
                ⚠ Stock Availability Alert
            </h3>
            <p>The following items have insufficient stock to fulfill this requisition:</p>
            <table style="width: 100%; border-collapse: collapse; margin-top: 15px;">
                <thead style="background-color: #f8f9fa;">
                    <tr>
                        <th style="border: 1px solid #dee2e6; padding: 8px; text-align: left;">Item</th>
                        <th style="border: 1px solid #dee2e6; padding: 8px; text-align: right;">Requested</th>
                        <th style="border: 1px solid #dee2e6; padding: 8px; text-align: right;">Current Stock</th>
                        <th style="border: 1px solid #dee2e6; padding: 8px; text-align: right;">Pending</th>
                        <th style="border: 1px solid #dee2e6; padding: 8px; text-align: right;">Available</th>
                        <th style="border: 1px solid #dee2e6; padding: 8px; text-align: right;">Shortage</th>
                        <th style="border: 1px solid #dee2e6; padding: 8px; text-align: left;">Expected Delivery</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        for warning in warnings:
            shortage_color = '#dc3545' if warning['shortage'] > 0 else '#28a745'
            html += f"""
                <tr>
                    <td style="border: 1px solid #dee2e6; padding: 8px;">
                        <strong>{warning['item_code']}</strong><br/>
                        <small>{warning['item_name']}</small>
                    </td>
                    <td style="border: 1px solid #dee2e6; padding: 8px; text-align: right;">{warning['requested_qty']:.0f}</td>
                    <td style="border: 1px solid #dee2e6; padding: 8px; text-align: right;">{warning['current_stock']:.0f}</td>
                    <td style="border: 1px solid #dee2e6; padding: 8px; text-align: right;">{warning['pending_qty']:.0f}</td>
                    <td style="border: 1px solid #dee2e6; padding: 8px; text-align: right;">{warning['available_stock']:.0f}</td>
                    <td style="border: 1px solid #dee2e6; padding: 8px; text-align: right; color: {shortage_color}; font-weight: bold;">
                        {warning['shortage']:.0f}
                    </td>
                    <td style="border: 1px solid #dee2e6; padding: 8px;">
                        {warning['expected_delivery'].strftime('%Y-%m-%d') if warning['expected_delivery'] else 'Not scheduled'}
                        {f"<br/><small>({warning['expected_qty']:.0f} units)</small>" if warning['expected_qty'] > 0 else ''}
                    </td>
                </tr>
            """
        
        html += """
                </tbody>
            </table>
            <div style="margin-top: 20px; padding: 15px; background-color: #e7f3ff; border-left: 4px solid #2196F3;">
                <h4 style="margin-top: 0;">Options:</h4>
                <ol>
                    <li><strong>Approve Partial Quantity:</strong> Approve only the available quantity</li>
                    <li><strong>Defer Until Stock Available:</strong> Wait for expected delivery</li>
                    <li><strong>Override and Approve:</strong> Approve anyway (requires justification)</li>
                </ol>
            </div>
        </div>
        """
        
        return html
    
    def action_force_approve(self):
        """AUTO-043: Force approve requisition despite stock shortages (requires PAO override)."""
        self.ensure_one()
        
        if self.state != "submitted":
            raise UserError("Only submitted requisitions can be approved.")
        
        # Log override action
        self.message_post(
            body=f"""<div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px;">
                <h4>⚠ Stock Shortage Override</h4>
                <p><strong>Approved By:</strong> {self.env.user.name}</p>
                <p><strong>Date:</strong> {fields.Datetime.now()}</p>
                <p><em>PAO approved this requisition despite stock availability warnings.</em></p>
            </div>""",
            subject='Requisition Approved with Stock Override',
            message_type='comment'
        )
        
        self.approved_by_id = self.env.user
        self.approved_on = fields.Date.today()
        self.state = "approved"
        
        return True

    def action_reject(self):
        """AUTO-042: PAO rejects requisition with mandatory comment (returns to requester)."""
        self.ensure_one()
        
        if self.state != "submitted":
            raise UserError("Only submitted requisitions can be rejected.")
        
        # Open wizard for rejection reason
        return {
            'name': 'Reject Requisition',
            'type': 'ir.actions.act_window',
            'res_model': 'mesob.requisition.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_requisition_id': self.id}
        }
    
    def _confirm_rejection(self, reason):
        """AUTO-042: Internal method to confirm rejection with reason and notify requester."""
        self.ensure_one()
        
        if not reason or len(reason) < 10:
            raise UserError("Rejection reason must be at least 10 characters.")
        
        self.write({
            'state': 'rejected',
            'rejection_reason': reason,
            'approved_by_id': self.env.user.id,
            'approved_on': fields.Date.today(),
        })
        
        # AUTO-042: Notify requester of rejection
        if self.requested_by_id:
            dept_label = dict(self._fields['department'].selection).get(self.department, 'Unknown')
            
            self.message_post(
                body=f"""<div style="background-color: #f8d7da; border-left: 4px solid #dc3545; padding: 15px;">
                    <h3>❌ AUTO-042: Requisition Rejected</h3>
                    <p><strong>Requisition:</strong> {self.name}</p>
                    <p><strong>Department:</strong> {dept_label}</p>
                    <p><strong>Rejected By:</strong> {self.env.user.name} (PAO)</p>
                    <p><strong>Rejected On:</strong> {fields.Date.today()}</p>
                    <hr/>
                    <h4>Rejection Reason:</h4>
                    <p style="background-color: white; padding: 10px; border-radius: 4px; color: #dc3545; font-weight: bold;">{reason}</p>
                    <hr/>
                    <p><em>You may reset this requisition to draft, make corrections, and resubmit.</em></p>
                    <p style="margin-top: 15px;">
                        <a href="/web#id={self.id}&model=mesob.inventory.requisition&view_type=form" 
                           style="background-color: #dc3545; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                           View Rejection Details →
                        </a>
                    </p>
                </div>""",
                subject=f'Requisition Rejected: {self.name}',
                message_type='notification',
                partner_ids=[self.requested_by_id.partner_id.id]
            )
            
            _logger.info(
                f"AUTO-042: Requisition {self.name} rejected by {self.env.user.name} - "
                f"Requester: {self.requested_by_id.name}, Reason: {reason[:50]}..."
            )
        
        return True

    def action_set_to_draft(self):
        """Reset to draft for corrections."""
        for record in self:
            if record.state not in ("rejected", "cancelled"):
                raise UserError(
                    "Only rejected or cancelled requisitions can be reset to draft."
                )
            record.approved_by_id = False
            record.approved_on = False
            record.rejection_reason = False
            record.state = "draft"
        return True

    def action_cancel(self):
        """Cancel the requisition."""
        for record in self:
            if record.state == "cancelled":
                raise UserError("Requisition is already cancelled.")
            if record.state in ("issued", "received"):
                raise UserError(
                    "Cannot cancel a requisition that has been issued. "
                    "Please cancel the issue voucher first."
                )
            record.state = "cancelled"
        return True

    def action_create_issue_voucher(self):
        """AUTO-044: Enhanced Model 22 auto-generation from approved requisition.
        
        Creates Issue Voucher (Model 22) with:
        - Auto-populates items from approved requisition
        - Three-copy digital distribution (FR-ISSUE-005):
          * Original + Requisition → Stock Clerk (for bin card posting)
          * Duplicate → Requesting Department
          * Triplicate → Storekeeper (retained)
        - Auto-sends notifications to all recipients
        - Tracks acknowledgment status per recipient
        """
        self.ensure_one()

        if self.state != "approved":
            raise UserError("Only approved requisitions can generate issue vouchers.")

        if not self.line_ids:
            raise UserError("Cannot create issue voucher: no requisition lines found.")

        voucher_vals = {
            "requisition_id": self.id,
            "issue_date": fields.Date.today(),
            "issued_by_id": self.env.user.id,
            "line_ids": [],
        }

        for req_line in self.line_ids:

            # ── Case 1: specific item on the line ──────────────────────
            if req_line.item_id:
                voucher_vals["line_ids"].append((0, 0, {
                    "item_id": req_line.item_id.id,
                    "quantity_issued": req_line.quantity,
                    "uom_id": (
                        req_line.uom_id.id
                        if req_line.uom_id
                        else req_line.item_id.uom_id.id
                    ),
                    "note": req_line.note,
                }))

            # ── Case 2: classification-only line ───────────────────────
            elif req_line.major_classification_id:
                domain = [
                    ("classification_id", "=", req_line.major_classification_id.id),
                    ("active", "=", True),
                ]
                if req_line.sub_classification_id:
                    domain.append((
                        "sub_classification_id",
                        "=",
                        req_line.sub_classification_id.id,
                    ))

                all_items = self.env["mesob.inventory.item"].search(domain)

                if not all_items:
                    sub_label = (
                        f" / Sub {req_line.sub_classification_id.name}"
                        if req_line.sub_classification_id
                        else ""
                    )
                    raise UserError(
                        f"No items found for Major Classification "
                        f"'{req_line.major_classification_id.name}'{sub_label}. "
                        "Please receive items first before creating an issue voucher."
                    )

                issued_item_ids = (
                    self.env["mesob.inventory.issue.voucher.line"]
                    .search([("voucher_id.state", "in", ["issued", "received"])])
                    .mapped("item_id")
                    .ids
                )

                available_items = all_items.filtered(
                    lambda i: i.id not in issued_item_ids
                )

                if not available_items:
                    sub_label = (
                        f" / Sub {req_line.sub_classification_id.name}"
                        if req_line.sub_classification_id
                        else ""
                    )
                    raise UserError(
                        f"No available items found for classification "
                        f"'{req_line.major_classification_id.name}'{sub_label}. "
                        f"All {len(all_items)} item(s) have already been issued."
                    )

                available_items = available_items[: int(req_line.quantity)]

                if len(available_items) < req_line.quantity:
                    raise UserError(
                        f"Not enough available items for classification "
                        f"'{req_line.major_classification_id.name}'. "
                        f"Requested: {int(req_line.quantity)}, "
                        f"Available: {len(available_items)}, "
                        f"Total: {len(all_items)}."
                    )

                for item in available_items:
                    voucher_vals["line_ids"].append((0, 0, {
                        "item_id": item.id,
                        "quantity_issued": 1.0,
                        "uom_id": (
                            item.uom_id.id if item.uom_id else req_line.uom_id.id
                        ),
                        "note": req_line.note,
                    }))

            # ── Case 3: invalid line ────────────────────────────────────
            else:
                raise UserError(
                    "Invalid requisition line: must have either a specific item "
                    "or a major classification."
                )

        voucher = self.env["mesob.inventory.issue.voucher"].create(voucher_vals)
        self.state = "issued"
        
        # AUTO-044: Send three-copy distribution notifications
        voucher._send_three_copy_distribution_notifications()

        return {
            "name": "Issue Voucher",
            "type": "ir.actions.act_window",
            "res_model": "mesob.inventory.issue.voucher",
            "res_id": voucher.id,
            "view_mode": "form",
            "target": "current",
        }

    def action_view_issue_vouchers(self):
        """View related issue vouchers."""
        self.ensure_one()
        return {
            "name": "Issue Vouchers",
            "type": "ir.actions.act_window",
            "res_model": "mesob.inventory.issue.voucher",
            "view_mode": "list,form",
            "domain": [("requisition_id", "=", self.id)],
            "context": {"default_requisition_id": self.id},
        }
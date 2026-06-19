# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from lxml import etree


class MesobBinCard(models.Model):
    """
    Bin Card - Physical location tracking for inventory items at sub-classification level
    Records all movements in/out of specific storage locations aggregated by sub-classification
    """
    _name = 'mesob.bin.card'
    _description = 'Bin Card (Physical Storage Location)'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'mesob.notification.mixin']  # Task 7: Add notification
    _order = 'date desc, id desc'
    _rec_name = 'display_name'

    # Header Information - Track by Sub-Classification instead of individual items
    major_classification_id = fields.Many2one(
        'mesob.inventory.major.classification', 
        string='Major Classification', 
        required=True, 
        ondelete='restrict'
    )
    sub_classification_id = fields.Many2one(
        'mesob.inventory.sub.classification', 
        string='Sub Classification', 
        required=True, 
        ondelete='restrict',
        index=True
    )
    location = fields.Char(
        string='Bin Location', 
        required=True, 
        default='Main Store',
        help='Physical storage location (e.g., Shelf A-1, Room 3)'
    )
    date = fields.Date(
        string='Date', 
        required=True, 
        default=fields.Date.context_today
    )
    
    # Transaction Details
    transaction_type = fields.Selection([
        ('receipt', 'Receipt'),
        ('issue', 'Issue'),
        ('adjustment', 'Adjustment'),
        ('transfer', 'Transfer'),
    ], string='Transaction Type', required=True)
    
    reference = fields.Char(string='Reference', help='Document reference (voucher number, etc.)')
    description = fields.Text(string='Description')
    
    # Quantities - Renamed for clarity
    quantity_received = fields.Float(
        string='Received', 
        digits='Product Unit of Measure', 
        default=0.0,
        help='Quantity received in this transaction'
    )
    quantity_distributed = fields.Float(
        string='Distributed', 
        digits='Product Unit of Measure', 
        default=0.0,
        help='Quantity distributed/issued in this transaction'
    )
    balance = fields.Float(
        string='Balance', 
        digits='Product Unit of Measure', 
        compute='_compute_balance', 
        store=True,
        help='Running balance after this transaction'
    )
    
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure', required=True)
    
    # Tracking
    received_by_id = fields.Many2one('res.users', string='Received/Issued By')
    verified_by_id = fields.Many2one('res.users', string='Verified By')
    
    # AUTO-050: Manual Adjustment Approval Fields
    state = fields.Selection([
        ('draft', 'Draft'),
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('posted', 'Posted'),
    ], string='State', default='posted', required=True, tracking=True,
       help='AUTO-050: Manual adjustments require PAO approval before posting')
    
    requires_approval = fields.Boolean(
        string='Requires PAO Approval',
        compute='_compute_requires_approval',
        store=True,
        help='AUTO-050: True if this is a manual adjustment requiring PAO approval'
    )
    
    adjustment_reason = fields.Text(
        string='Adjustment Reason',
        help='AUTO-050: Required justification for manual adjustments'
    )
    
    supporting_document = fields.Char(
        string='Supporting Document Reference',
        help='AUTO-050: Reference to physical count, memo, or other supporting document'
    )
    
    approved_by_id = fields.Many2one(
        'res.users',
        string='Approved By (PAO)',
        readonly=True,
        tracking=True,
        help='AUTO-050: PAO who approved this manual adjustment'
    )
    
    approved_on = fields.Datetime(
        string='Approval Timestamp',
        readonly=True,
        tracking=True,
        help='AUTO-050: When PAO approved the adjustment'
    )
    
    # Computed Fields
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)
    item_count = fields.Integer(
        string='Item Count',
        compute='_compute_item_count',
        help='Number of individual items in this sub-classification'
    )
    
    # ── Task 9: QR Code for Bin Location Identification ────────────────
    
    qr_code = fields.Binary(
        string="Bin Location QR Code",
        compute="_compute_qr_code",
        store=True,
        help="Task 9: QR code for bin location - encodes location + sub-classification"
    )
    
    @api.depends('sub_classification_id', 'location', 'date')
    def _compute_display_name(self):
        for record in self:
            if record.sub_classification_id and record.location:
                record.display_name = f"{record.sub_classification_id.name} - {record.location} ({record.date})"
            else:
                record.display_name = _('New Bin Card')
    
    def _compute_item_count(self):
        """Count individual items in this sub-classification"""
        for record in self:
            if record.sub_classification_id:
                record.item_count = self.env['mesob.inventory.item'].search_count([
                    ('sub_classification_id', '=', record.sub_classification_id.id)
                ])
            else:
                record.item_count = 0
    
    @api.depends('sub_classification_id', 'location')
    def _compute_qr_code(self):
        """Task 9: Generate QR code for bin location identification.
        
        QR code contains: Location + Sub-classification + Major classification
        Used for: Stock-taking, Physical verification, Location tracking
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
            if record.sub_classification_id and record.location:
                # Generate QR code data
                qr_data = (
                    f"MESOB-BIN:{record.location}|"
                    f"SUB:{record.sub_classification_id.code}-{record.sub_classification_id.name}|"
                    f"MAJ:{record.major_classification_id.code if record.major_classification_id else 'N/A'}"
                )
                
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
                _logger.debug(f"Task 9: Generated QR code for bin location {record.location}")
            else:
                record.qr_code = False
    
    # AUTO-050: Compute Methods
    
    @api.depends('transaction_type', 'reference')
    def _compute_requires_approval(self):
        """AUTO-050: Determine if this entry requires PAO approval.
        
        Manual adjustments (not from Model 19/22) require approval.
        Automatic movements from documents are auto-approved.
        """
        for record in self:
            # Check if this is an adjustment transaction
            is_adjustment = record.transaction_type == 'adjustment'
            
            # Check if this came from an automated document (Model 19/22)
            is_automated = record.reference and any([
                'Model 19' in record.reference,
                'Model 22' in record.reference,
                'AUTO-049' in (record.description or ''),
                'Auto-posted' in (record.description or ''),
            ])
            
            # Require approval for manual adjustments only
            record.requires_approval = is_adjustment and not is_automated
    
    @api.depends('quantity_received', 'quantity_distributed')
    def _compute_balance(self):
        """Compute running balance for each sub-classification at location"""
        for record in self:
            # Get previous balance
            previous_records = self.search([
                ('sub_classification_id', '=', record.sub_classification_id.id),
                ('location', '=', record.location),
                ('date', '<', record.date),
            ], order='date desc, id desc', limit=1)
            
            if not previous_records:
                # Also check same date but earlier ID
                previous_records = self.search([
                    ('sub_classification_id', '=', record.sub_classification_id.id),
                    ('location', '=', record.location),
                    ('date', '=', record.date),
                    ('id', '<', record.id),
                ], order='date desc, id desc', limit=1)
            
            previous_balance = previous_records[0].balance if previous_records else 0.0
            record.balance = previous_balance + record.quantity_received - record.quantity_distributed
    
    # ── View Customization ──────────────────────────────────────────
    
    @api.model
    def get_view(self, view_id=None, view_type="form", **options):
        """Hide New button for Stock Clerk and PAO on both tree and form views.
        
        Bin Cards are maintained by Storekeeper only.
        Stock Clerk and PAO have read-only oversight.
        """
        result = super().get_view(view_id, view_type, **options)
        
        if view_type in ("tree", "form"):
            user = self.env.user
            is_pao = user.has_group("mesob_inventory_base.group_mesob_pao")
            is_stock_clerk = user.has_group("mesob_inventory_base.group_mesob_stock_clerk")
            is_storekeeper = user.has_group("mesob_inventory_base.group_mesob_storekeeper")
            
            # Stock Clerk and PAO: completely read-only (cannot create/edit/delete)
            if (is_pao or is_stock_clerk) and not is_storekeeper:
                arch = result.get("arch", "")
                if isinstance(arch, str):
                    arch = arch.encode("utf-8")
                root = etree.fromstring(arch)
                root.set("create", "0")
                root.set("edit", "0")
                root.set("delete", "0")
                result["arch"] = etree.tostring(root, encoding="unicode", pretty_print=False)
        
        return result
    
    # ── AUTO-050: Approval Workflow ─────────────────────────────────
    
    def action_request_pao_approval(self):
        """AUTO-050: Submit manual adjustment for PAO approval."""
        for record in self:
            if not record.requires_approval:
                continue
            
            if record.state != 'draft':
                raise ValidationError(_("Only draft adjustments can be submitted for approval."))
            
            if not record.adjustment_reason or not record.adjustment_reason.strip():
                raise ValidationError(_("Adjustment reason is required for PAO approval."))
            
            record.state = 'pending'
    
    def action_pao_approve(self):
        """AUTO-050: PAO approves manual adjustment."""
        for record in self:
            # Verify PAO role
            if not self.env.user.has_group("mesob_inventory_base.group_mesob_pao"):
                raise ValidationError(
                    _("Only Property Administration Officers (PAO) can approve manual adjustments.")
                )
            
            if record.state not in ('draft', 'pending'):
                raise ValidationError(_("Only pending adjustments can be approved."))
            
            if record.requires_approval and (not record.adjustment_reason or not record.adjustment_reason.strip()):
                raise ValidationError(_("Adjustment reason is required before approval."))
            
            # Approve and post
            record.write({
                'state': 'approved',
                'approved_by_id': self.env.user.id,
                'approved_on': fields.Datetime.now(),
            })
            
            # Log approval in chatter
            record.message_post(
                body=_(
                    f"<b>Manual Adjustment Approved by PAO</b><br/>"
                    f"<b>Approved by:</b> {self.env.user.name}<br/>"
                    f"<b>Timestamp:</b> {fields.Datetime.now()}<br/>"
                    f"<b>Reason:</b> {record.adjustment_reason}<br/>"
                    f"<b>Supporting Document:</b> {record.supporting_document or 'N/A'}"
                ),
                subject="Manual Adjustment Approved"
            )
        
        return True
    
    @api.constrains('adjustment_reason')
    def _check_adjustment_reason(self):
        """AUTO-050: Ensure manual adjustments have a reason."""
        for record in self:
            if record.requires_approval and record.state != 'draft':
                if not record.adjustment_reason or not record.adjustment_reason.strip():
                    raise ValidationError(
                        _("Manual adjustments require a justification reason before approval.")
                    )
    
    # ── CRUD Operations ────────────────────────────────────────────
    
    @api.model_create_multi
    def create(self, vals_list):
        """Override create to recompute balances after inserting new records"""
        records = super().create(vals_list)
        
        # Recompute balances for all affected sub-classifications
        for record in records:
            if record.sub_classification_id:
                self._recompute_balances_for_subclass(
                    record.sub_classification_id.id,
                    record.location
                )
        
        return records
    
    def _recompute_balances_for_subclass(self, sub_classification_id, location):
        """Recompute all balances for a sub-classification at a location in chronological order"""
        # Get all bin card entries for this sub-classification at this location
        all_entries = self.search([
            ('sub_classification_id', '=', sub_classification_id),
            ('location', '=', location)
        ], order='date asc, id asc')
        
        running_balance = 0.0
        for entry in all_entries:
            running_balance = running_balance + entry.quantity_received - entry.quantity_distributed
            # Direct SQL update to avoid recursion
            self.env.cr.execute(
                "UPDATE mesob_bin_card SET balance = %s WHERE id = %s",
                (running_balance, entry.id)
            )
        
        # Invalidate cache to force refresh
        all_entries.invalidate_recordset(['balance'])
    
    @api.constrains('quantity_received', 'quantity_distributed')
    def _check_quantities(self):
        for record in self:
            if record.quantity_received < 0 or record.quantity_distributed < 0:
                raise ValidationError(_('Quantities cannot be negative.'))
            if record.quantity_received > 0 and record.quantity_distributed > 0:
                raise ValidationError(_('A transaction cannot have both received and distributed quantities.'))
    
    def action_view_items(self):
        """Open list of individual items in this sub-classification"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Items: {self.sub_classification_id.name}',
            'res_model': 'mesob.inventory.item',
            'view_mode': 'list,form',
            'domain': [('sub_classification_id', '=', self.sub_classification_id.id)],
            'context': {
                'create': False,
                'default_sub_classification_id': self.sub_classification_id.id,
                'default_classification_id': self.major_classification_id.id,
            },
        }


class MesobBinCardLine(models.Model):
    """
    Bin Card Line - Deprecated, keeping for backwards compatibility
    Now bin cards track at sub-classification level directly
    """
    _name = 'mesob.bin.card.line'
    _description = 'Bin Card Line (Deprecated)'
    _order = 'date desc'

    bin_card_id = fields.Many2one('mesob.bin.card', string='Bin Card', ondelete='cascade')
    date = fields.Date(string='Date', default=fields.Date.context_today)
    reference = fields.Char(string='Reference')
    quantity_in = fields.Float(string='In', digits='Product Unit of Measure')
    quantity_out = fields.Float(string='Out', digits='Product Unit of Measure')
    balance = fields.Float(string='Balance', digits='Product Unit of Measure')
    remarks = fields.Char(string='Remarks')

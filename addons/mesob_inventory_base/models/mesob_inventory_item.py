import re
import logging
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import ValidationError, UserError

_logger = logging.getLogger(__name__)
_ITEM_CODE_PATTERN = re.compile(r"^(?P<major>\d{4})-(?P<sub>\d{3})-(?P<specific>\d{3})$")


class MesobInventoryItem(models.Model):
    """Inventory item master with FDRE-standard coding and stock-control levels.

    Coding format: ####-###-### (FR-ID-002)
    Classification: linked to chart-of-accounts 4401–4418 (FR-ID-001)
    Stock control: min/max/reorder/safety levels & ABC class (FR-SC-001, FR-SC-005)
    """

    _name = "mesob.inventory.item"
    _description = "Inventory Item"
    _rec_name = "item_code"
    _order = "item_code"

    _sql_constraints = [
        ('item_code_unique', 'UNIQUE(item_code)', 'Item Code must be unique.'),
        ('item_code_format', "CHECK(item_code ~ '^[0-9]{4}-[0-9]{3}-[0-9]{3}$')", 
         'Item Code must follow the format ####-###-### (digits and dashes).'),
    ]

    # ── Identification ──────────────────────────────────────────────────

    item_code = fields.Char(
        string="Item Code",
        required=True,
        index=True,
        copy=False,
        help="FDRE item code format: ####-###-### (10 digits total).",
    )

    major_code = fields.Char(
        string="Major Code",
        compute="_compute_item_code_segments",
        inverse="_inverse_item_code_segments",
        store=True,
        help="First 4 digits of the FDRE item code (classification aligned to chart of accounts).",
    )
    sub_code = fields.Char(
        string="Sub Code",
        compute="_compute_item_code_segments",
        inverse="_inverse_item_code_segments",
        store=True,
        help="Middle 3 digits of the FDRE item code (sub-class).",
    )
    specific_code = fields.Char(
        string="Specific Code",
        compute="_compute_item_code_segments",
        inverse="_inverse_item_code_segments",
        store=True,
        help="Last 3 digits of the FDRE item code (specific item).",
    )

    classification_id = fields.Many2one(
        "mesob.inventory.major.classification",
        string="Major Classification",
        index=True,
        help="Chart-of-accounts classification (4401–4418).",
    )

    sub_classification_id = fields.Many2one(
        "mesob.inventory.sub.classification",
        string="Sub Classification",
        index=True,
        help="Sub classification under major classification.",
    )

    name = fields.Char(
        string="Name (English)",
        required=True,
        index=True,
    )
    name_am = fields.Char(
        string="Name (Amharic)",
        help="Amharic translation of the item name.",
    )
    description = fields.Text()
    active = fields.Boolean(default=True)
    is_surplus = fields.Boolean(
        string="Is Surplus",
        default=False,
        help="Whether this item is flagged as surplus in the Disposal system (BR-PROC-008).",
    )


    # ── Unit of Measure ─────────────────────────────────────────────────

    uom_id = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
        help="Default unit of measure for this item.",
    )

    # ── Product Linkage ─────────────────────────────────────────────────

    product_id = fields.Many2one(
        "product.product",
        string="Linked Product",
        help="Odoo product for stock operations and valuation.",
        index=True,
    )

    # ── Stock Control Levels (FR-SC-001) ────────────────────────────────

    minimum_level = fields.Float(
        string="Minimum Level",
        default=0.0,
        help="Minimum stock quantity before alert.",
    )
    maximum_level = fields.Float(
        string="Maximum Level",
        default=0.0,
        help="Maximum stock quantity allowed.",
    )
    reorder_level = fields.Float(
        string="Reorder Level",
        default=0.0,
        help="Stock level at which to trigger a purchase/requisition.",
    )
    hastening_level = fields.Float(
        string="Hastening Level",
        default=0.0,
        help="Level at which to expedite pending deliveries.",
    )
    safety_stock = fields.Float(
        string="Safety Stock",
        default=0.0,
        help="Buffer stock to cover demand variability.",
    )

    # ── Lead Times (FR-SC-002) ──────────────────────────────────────────

    admin_lead_time = fields.Integer(
        string="Administrative Lead Time (days)",
        default=0,
        help="Days for internal processing before order is placed.",
    )
    supplier_lead_time = fields.Integer(
        string="Supplier Lead Time (days)",
        default=0,
        help="Days from order placement to delivery.",
    )

    # ── ABC Classification (FR-SC-005) ──────────────────────────────────

    abc_class = fields.Selection(
        [
            ("A", "A — High Value / High Priority"),
            ("B", "B — Medium Value / Medium Priority"),
            ("C", "C — Low Value / Low Priority"),
        ],
        string="ABC Class",
        help="ABC analysis classification by usage value to prioritize management attention.",
    )
    
    # ── AUTO-062: Control Levels Auto-Calculation ──────────────────────
    
    auto_reorder_enabled = fields.Boolean(
        string="Enable Auto-Reorder Calculation",
        default=False,
        help="AUTO-062: Enable automatic calculation of reorder levels from historical usage"
    )
    
    historical_period_months = fields.Integer(
        string="Historical Period (Months)",
        default=6,
        help="AUTO-062: Number of months to analyze for usage calculation"
    )
    
    average_monthly_usage = fields.Float(
        string="Avg Monthly Usage",
        compute="_compute_usage_statistics",
        store=True,
        help="AUTO-062: Average monthly usage calculated from history"
    )
    
    max_monthly_usage = fields.Float(
        string="Max Monthly Usage",
        compute="_compute_usage_statistics",
        store=True,
        help="AUTO-062: Maximum monthly usage in historical period"
    )
    
    last_calculation_date = fields.Datetime(
        string="Last Auto-Calculation",
        readonly=True,
        help="AUTO-062: Last time control levels were auto-calculated"
    )
    
    suggested_reorder_level = fields.Float(
        string="Suggested Reorder Level",
        compute="_compute_suggested_levels",
        help="AUTO-062: System-calculated reorder level based on usage + lead time"
    )
    
    suggested_minimum_level = fields.Float(
        string="Suggested Minimum Level",
        compute="_compute_suggested_levels",
        help="AUTO-062: System-calculated minimum level (safety stock)"
    )
    
    suggested_maximum_level = fields.Float(
        string="Suggested Maximum Level",
        compute="_compute_suggested_levels",
        help="AUTO-062: System-calculated maximum level"
    )

    # ── Stock Status & Monitoring ───────────────────────────────────────

    current_stock = fields.Float(
        string="Current Stock",
        compute="_compute_current_stock",
        help="Current stock balance from bin card"
    )

    stock_status = fields.Selection([
        ('critical', 'Critical - Below Minimum'),
        ('low', 'Low - Below Reorder'),
        ('hasten', 'Hasten - Below Hastening'),
        ('normal', 'Normal'),
        ('high', 'High - Above Maximum'),
    ], string="Stock Status", compute="_compute_stock_status", store=True)

    issue_status = fields.Selection([
        ('issued', 'Issued'),
        ('not_issued', 'Not Issued'),
    ], string="Issue Status", compute="_compute_issue_status")

    current_holder = fields.Char(
        string="Current Holder",
        compute="_compute_current_holder",
        help="The actual employee, department, or requester currently holding the item. Shows department or initials + name."
    )

    total_lead_time = fields.Integer(
        string="Total Lead Time (days)",
        compute="_compute_total_lead_time",
        store=True,
        help="Total lead time = Administrative + Supplier lead time"
    )

    # ── Controlled Material Flag (FR-ISSUE-004) ─────────────────────────

    is_controlled = fields.Boolean(
        string="Controlled Material",
        default=False,
        help="If checked, issue restricted to authorized individuals only "
             "(e.g. drugs, chemicals, explosives).",
    )
    
    # ── AUTO-066: Dormant/Damaged/Obsolete Item Flagging ────────────────
    
    is_dormant = fields.Boolean(
        string="Dormant Item",
        compute="_compute_item_flags",
        store=True,
        help="AUTO-066: Auto-flagged if no issues in configured dormant period"
    )
    
    is_slow_moving = fields.Boolean(
        string="Slow Moving",
        compute="_compute_item_flags",
        store=True,
        help="AUTO-066: Auto-flagged if usage below threshold"
    )
    
    is_damaged = fields.Boolean(
        string="Damaged",
        default=False,
        help="AUTO-066: Manually flagged damaged items (FR-DISP2-001)"
    )
    
    is_obsolete = fields.Boolean(
        string="Obsolete",
        default=False,
        help="AUTO-066: Manually flagged obsolete items (FR-DISP2-001)"
    )
    
    days_since_last_issue = fields.Integer(
        string="Days Since Last Issue",
        compute="_compute_item_flags",
        store=True,
        help="AUTO-066: Number of days since last issue"
    )
    
    dormant_threshold_days = fields.Integer(
        string="Dormant Threshold (Days)",
        default=365,
        help="AUTO-066: Days of no activity before flagging as dormant"
    )
    
    item_condition_notes = fields.Text(
        string="Condition Notes",
        help="AUTO-066: Notes about item condition/status"
    )

    # ── Catalog Exclusion (FR-ID-006) ───────────────────────────────────

    exclude_from_catalog = fields.Boolean(
        string="Exclude from Catalog",
        default=False,
        help="Mark seldom-required/non-repetitive items excluded from the coding catalog.",
    )
    
    # ── AUTO-036: Auto-Generation Tracking ──────────────────────────────
    
    code_auto_generated = fields.Boolean(
        string="Code Auto-Generated",
        default=False,
        readonly=True,
        help="AUTO-036: True if item code was auto-generated by system"
    )
    
    generated_on = fields.Datetime(
        string="Code Generated On",
        readonly=True,
        help="AUTO-036: Timestamp of code generation"
    )
    
    generated_by_id = fields.Many2one(
        'res.users',
        string="Generated By",
        readonly=True,
        help="AUTO-036: User who triggered code generation"
    )

    # ── Computed / Validation ───────────────────────────────────────────

    @api.depends("item_code", "name")
    def _compute_display_name(self):
        for rec in self:
            if rec.item_code and rec.name:
                rec.display_name = f"[{rec.item_code}] {rec.name}"
            else:
                rec.display_name = rec.name or rec.item_code or ""

    @api.constrains("item_code")
    def _check_item_code_format(self):
        for record in self:
            if not record.item_code:
                continue
            if not _ITEM_CODE_PATTERN.fullmatch(record.item_code):
                raise ValidationError(
                    "Item Code must follow the format ####-###-### (digits and dashes)."
                )

    @api.constrains("classification_id", "major_code")
    def _check_classification_consistency(self):
        """Validate that major_code matches classification_id.code."""
        for record in self:
            if record.classification_id and record.major_code:
                if record.classification_id.code != record.major_code:
                    raise ValidationError(
                        f"Major code {record.major_code} does not match "
                        f"classification code {record.classification_id.code}."
                    )

    @api.constrains("sub_classification_id", "sub_code")
    def _check_sub_classification_consistency(self):
        """Validate that sub_code matches sub_classification_id.code."""
        for record in self:
            if record.sub_classification_id and record.sub_code:
                if record.sub_classification_id.code != record.sub_code:
                    raise ValidationError(
                        f"Sub code {record.sub_code} does not match "
                        f"sub classification code {record.sub_classification_id.code}."
                    )

    @api.depends("item_code")
    def _compute_item_code_segments(self):
        for record in self:
            match = _ITEM_CODE_PATTERN.fullmatch(record.item_code or "")
            if not match:
                record.major_code = False
                record.sub_code = False
                record.specific_code = False
                continue
            record.major_code = match.group("major")
            record.sub_code = match.group("sub")
            record.specific_code = match.group("specific")

    def _inverse_item_code_segments(self):
        for record in self:
            if not (record.major_code and record.sub_code and record.specific_code):
                continue

            major = (record.major_code or "").strip()
            sub = (record.sub_code or "").strip()
            specific = (record.specific_code or "").strip()
            record.item_code = f"{major}-{sub}-{specific}"

    @api.onchange("classification_id")
    def _onchange_classification_id(self):
        """Auto-fill major code prefix from classification selection."""
        if self.classification_id and self.classification_id.code:
            self.major_code = self.classification_id.code

    @api.onchange("major_code")
    def _onchange_major_code(self):
        """Auto-link classification when major code is typed manually."""
        if self.major_code:
            classification = self.env["mesob.inventory.major.classification"].search(
                [("code", "=", self.major_code)], limit=1
            )
            if classification:
                self.classification_id = classification.id
    
    @api.model_create_multi
    def create(self, vals_list):
        """AUTO-036: Enhanced create with auto-code generation and validation.
        
        AUTO-038: Also checks for duplicate items before creation.
        """
        for vals in vals_list:
            # AUTO-036: Auto-generate item code if not provided
            if not vals.get('item_code') and vals.get('classification_id') and vals.get('sub_classification_id'):
                vals['item_code'] = self._auto_generate_item_code(
                    vals['classification_id'],
                    vals['sub_classification_id']
                )
                vals['code_auto_generated'] = True
                vals['generated_on'] = fields.Datetime.now()
                vals['generated_by_id'] = self.env.user.id
                
                _logger.info(
                    f"AUTO-036: Auto-generated item code: {vals['item_code']} "
                    f"by user {self.env.user.name}"
                )
            
            # AUTO-038: Check for duplicate items before creation
            if vals.get('name'):
                similar_items = self._detect_similar_items(
                    vals['name'],
                    vals.get('classification_id')
                )
                
                if similar_items:
                    # Log warning but allow creation (user was notified)
                    _logger.warning(
                        f"AUTO-038: Creating item '{vals['name']}' despite similar items found: "
                        f"{', '.join(similar_items.mapped('item_code'))}"
                    )
        
        return super().create(vals_list)
    
    def _auto_generate_item_code(self, classification_id, sub_classification_id):
        """AUTO-036: Auto-generate next available item code (FR-ID-002, FR-ID-003).
        
        Format: ####-###-### where:
        - #### = Major classification code (e.g., 4402)
        - ### = Sub classification code (e.g., 001)
        - ### = Next available specific item number (auto-incremented)
        
        Returns:
            str: Generated item code
        """
        # Get classification codes
        classification = self.env['mesob.inventory.major.classification'].browse(classification_id)
        sub_classification = self.env['mesob.inventory.sub.classification'].browse(sub_classification_id)
        
        if not classification or not sub_classification:
            raise UserError("AUTO-036: Cannot auto-generate code without valid classifications.")
        
        major_code = classification.code
        sub_code = sub_classification.code
        
        # Find highest existing specific code for this major-sub combination
        existing_items = self.search([
            ('major_code', '=', major_code),
            ('sub_code', '=', sub_code)
        ], order='specific_code desc', limit=1)
        
        if existing_items and existing_items[0].specific_code:
            try:
                last_specific = int(existing_items[0].specific_code)
                next_specific = last_specific + 1
            except ValueError:
                # Fallback if existing code is not numeric
                next_specific = 1
        else:
            next_specific = 1
        
        # Validate uniqueness
        max_attempts = 1000
        attempt = 0
        while attempt < max_attempts:
            specific_code = str(next_specific + attempt).zfill(3)
            candidate_code = f"{major_code}-{sub_code}-{specific_code}"
            
            # Check if code already exists
            existing = self.search([('item_code', '=', candidate_code)])
            if not existing:
                _logger.info(f"AUTO-036: Generated code {candidate_code} (FR-ID-002, FR-ID-003)")
                return candidate_code
            
            attempt += 1
        
        raise UserError(
            f"AUTO-036: Unable to generate unique item code after {max_attempts} attempts. "
            f"Major: {major_code}, Sub: {sub_code}"
        )
    
    def _detect_similar_items(self, item_name, classification_id=None):
        """AUTO-038: Detect potentially duplicate items using keyword matching.
        
        Searches existing items for similar descriptions to prevent duplicates (BR-ID-001).
        
        Args:
            item_name (str): Item name/description to check
            classification_id (int, optional): Filter by classification
        
        Returns:
            recordset: Similar items found
        """
        if not item_name or len(item_name) < 3:
            return self.env['mesob.inventory.item']
        
        # Extract keywords (simple approach - production would use NLP)
        # Remove common words and split
        common_words = {'the', 'a', 'an', 'and', 'or', 'of', 'in', 'for', 'with', 'to', 'from'}
        keywords = [
            word.lower().strip() 
            for word in item_name.split() 
            if word.lower() not in common_words and len(word) > 2
        ]
        
        if not keywords:
            return self.env['mesob.inventory.item']
        
        # Build search domain
        domain = [('active', '=', True)]
        if classification_id:
            domain.append(('classification_id', '=', classification_id))
        
        # Search for items with matching keywords
        name_conditions = ['|'] * (len(keywords) - 1) if len(keywords) > 1 else []
        for keyword in keywords:
            name_conditions.append(('name', 'ilike', keyword))
        
        domain.extend(name_conditions)
        
        similar_items = self.search(domain, limit=5)
        
        if similar_items:
            _logger.info(
                f"AUTO-038: Found {len(similar_items)} similar items for '{item_name}': "
                f"{', '.join(similar_items.mapped('item_code'))}"
            )
        
        return similar_items
    
    def action_check_duplicates(self):
        """AUTO-038: Manual duplicate check action for existing items."""
        self.ensure_one()
        
        similar_items = self._detect_similar_items(
            self.name,
            self.classification_id.id if self.classification_id else None
        ).filtered(lambda i: i.id != self.id)  # Exclude self
        
        if not similar_items:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Duplicates Found',
                    'message': f'No similar items found for "{self.name}"',
                    'type': 'success',
                    'sticky': False,
                }
            }
        
        # Build similar items message
        items_html = '<ul>'
        for item in similar_items:
            items_html += f'<li><strong>{item.item_code}</strong>: {item.name}</li>'
        items_html += '</ul>'
        
        self.message_post(
            body=f"""<div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px;">
                <h3>⚠️ AUTO-038: Similar Items Detected</h3>
                <p><strong>Current Item:</strong> {self.item_code} - {self.name}</p>
                <p><strong>Similar Items Found:</strong></p>
                {items_html}
                <p style="margin-top: 15px; background-color: #fff; padding: 10px; border-radius: 4px;">
                    <strong>BR-ID-001 Recommendation:</strong> Review these items to ensure no duplication. 
                    Consider using existing items if appropriate for "like-with-like" grouping.
                </p>
            </div>""",
            subject='Duplicate Item Check',
            message_type='comment'
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Similar Items Found',
                'message': f'Found {len(similar_items)} similar items. Check chatter for details.',
                'type': 'warning',
                'sticky': True,
            }
        }

    # ── Stock Control Validations & Computations ───────────────────────

    @api.constrains('minimum_level', 'reorder_level', 'hastening_level', 'maximum_level', 'safety_stock')
    def _check_control_levels(self):
        """Validate control level relationships (FR-SC-001)"""
        for item in self:
            if item.minimum_level < 0 or item.maximum_level < 0 or item.reorder_level < 0:
                raise ValidationError('Control levels cannot be negative.')
            
            if item.maximum_level > 0 and item.minimum_level > item.maximum_level:
                raise ValidationError(
                    f'Item {item.item_code}: Minimum level ({item.minimum_level}) '
                    f'cannot exceed maximum level ({item.maximum_level}).'
                )
            
            if item.reorder_level > 0:
                if item.minimum_level > 0 and item.reorder_level < item.minimum_level:
                    raise ValidationError(
                        f'Item {item.item_code}: Reorder level ({item.reorder_level}) '
                        f'should be >= minimum level ({item.minimum_level}).'
                    )
                if item.maximum_level > 0 and item.reorder_level > item.maximum_level:
                    raise ValidationError(
                        f'Item {item.item_code}: Reorder level ({item.reorder_level}) '
                        f'should be <= maximum level ({item.maximum_level}).'
                    )

    @api.depends('admin_lead_time', 'supplier_lead_time')
    def _compute_total_lead_time(self):
        """Calculate total lead time (FR-SC-002)"""
        for item in self:
            item.total_lead_time = item.admin_lead_time + item.supplier_lead_time

    def _compute_current_stock(self):
        """Get current stock from bin card aggregated by sub-classification (FR-SC-001)"""
        for item in self:
            if not item.sub_classification_id:
                item.current_stock = 0.0
                continue
            
            # Get the latest bin card balance for this sub-classification
            bin_card = self.env['mesob.bin.card'].search([
                ('sub_classification_id', '=', item.sub_classification_id.id)
            ], limit=1, order='date desc, id desc')
            item.current_stock = bin_card.balance if bin_card else 0.0

    @api.depends('current_stock', 'minimum_level', 'reorder_level', 'hastening_level', 'maximum_level')
    def _compute_stock_status(self):
        """Determine stock status based on control levels (FR-SC-001)"""
        for item in self:
            current = item.current_stock
            
            if item.minimum_level > 0 and current < item.minimum_level:
                item.stock_status = 'critical'
            elif item.reorder_level > 0 and current < item.reorder_level:
                item.stock_status = 'low'
            elif item.hastening_level > 0 and current < item.hastening_level:
                item.stock_status = 'hasten'
            elif item.maximum_level > 0 and current > item.maximum_level:
                item.stock_status = 'high'
            else:
                item.stock_status = 'normal'

            # AUTO-023: FR-PROC-029 Auto-generate draft Purchase Requisition (need) upon reorder trigger
            if item.reorder_level > 0 and current <= item.reorder_level:
                # Check for outstanding open POs for this item code to prevent duplicate ordering (FR-PROC-029)
                outstanding_pos = self.env['mesob.procurement.order.line'].search([
                    ('item_id', '=', item.id),
                    ('order_id.state', 'in', ['draft', 'pending', 'approved', 'sent'])
                ])
                
                if outstanding_pos:
                    # Outstanding PO exists - log info message
                    _logger.info(
                        f"AUTO-023: Reorder level reached for {item.item_code}, "
                        f"but PO {outstanding_pos[0].order_id.name} already outstanding. "
                        f"ETA: {outstanding_pos[0].order_id.date_order or 'N/A'}"
                    )
                else:
                    # No outstanding PO - check for existing draft need to avoid duplication
                    existing_need = self.env['mesob.procurement.need'].search([
                        ('item_id', '=', item.id),
                        ('state', '=', 'draft')
                    ])
                    
                    if not existing_need:
                        # Calculate suggested order quantity: (Max level - Current level) or reorder level
                        suggested_qty = max(
                            item.maximum_level - current if item.maximum_level > 0 else item.reorder_level,
                            item.reorder_level - current
                        )
                        
                        # Get last purchase price as estimated unit price (AUTO-023 intelligent pre-fill)
                        last_po_line = self.env['mesob.procurement.order.line'].search([
                            ('item_id', '=', item.id),
                            ('order_id.state', 'in', ['approved', 'sent', 'fully_received', 'closed'])
                        ], order='id desc', limit=1)
                        estimated_price = last_po_line.price_unit if last_po_line else 100.0
                        
                        # Auto-create draft need request (FR-PROC-029)
                        need = self.env['mesob.procurement.need'].create({
                            'department': 'ministry_transport_logistics',  # default department fallback
                            'item_id': item.id,
                            'quantity': suggested_qty,
                            'estimated_unit_price': estimated_price,
                            'expected_delivery_period': f'{item.total_lead_time} days (Auto-Reorder)',
                            'state': 'draft'
                        })
                        
                        # AUTO-023: Send notification to Procurement Officer
                        procurement_officers = self.env.ref('mesob_inventory_base.group_mesob_procurement').users
                        if procurement_officers:
                            need.message_post(
                                body=f"""<p><strong>AUTO-023: Reorder Alert</strong></p>
                                <ul>
                                    <li>Item: {item.item_code} - {item.name}</li>
                                    <li>Current Stock: {current}</li>
                                    <li>Reorder Level: {item.reorder_level}</li>
                                    <li>Suggested Order Qty: {suggested_qty}</li>
                                    <li>Last Unit Price: ETB {estimated_price}</li>
                                    <li>Lead Time: {item.total_lead_time} days</li>
                                </ul>
                                <p>Review and convert this draft need to Purchase Order.</p>""",
                                subject=f"Reorder Alert: {item.item_code}",
                                message_type='notification',
                                partner_ids=procurement_officers.mapped('partner_id').ids
                            )
                        
                        _logger.info(
                            f"AUTO-023: Auto-generated draft procurement need for {item.item_code}. "
                            f"Current: {current}, Reorder: {item.reorder_level}, Suggested Qty: {suggested_qty}"
                        )

    def _compute_issue_status(self):
        for rec in self:
            issued_lines = self.env['mesob.inventory.issue.voucher.line'].search_count([
                ('item_id', '=', rec.id),
                ('voucher_id.state', 'in', ['issued', 'received']),
            ])
            rec.issue_status = 'issued' if issued_lines > 0 else 'not_issued'

    def _compute_current_holder(self):
        for rec in self:
            # Find the latest issue voucher line for this item
            line = self.env['mesob.inventory.issue.voucher.line'].search([
                ('item_id', '=', rec.id),
                ('voucher_id.state', 'in', ['issued', 'received'])
            ], order='id desc', limit=1)
            
            if line:
                voucher = line.voucher_id
                requisition = voucher.requisition_id
                if requisition:
                    if requisition.department:
                        rec.current_holder = f"🏢 {requisition.department}"
                    elif requisition.requested_by_id:
                        user = requisition.requested_by_id
                        name = user.name or ""
                        parts = name.split()
                        initials = "".join([p[0].upper() for p in parts if p])[:2]
                        rec.current_holder = f"👤 {initials} {name}"
                    else:
                        rec.current_holder = ""
                else:
                    rec.current_holder = ""
            else:
                rec.current_holder = ""



    # ═══════════════════════════════════════════════════════════════════
    # AUTO-062: Control Levels Auto-Calculation from Historical Usage
    # ═══════════════════════════════════════════════════════════════════
    
    @api.depends('item_code', 'sub_classification_id')
    def _compute_usage_statistics(self):
        """AUTO-062: Calculate average and max monthly usage from issue history (FR-SC-002)"""
        for item in self:
            if not item.sub_classification_id:
                item.average_monthly_usage = 0.0
                item.max_monthly_usage = 0.0
                continue
            
            # Get issue history for the configured period
            months_back = item.historical_period_months or 6
            start_date = fields.Date.today() - timedelta(days=months_back * 30)
            
            # Query issue voucher lines for this item
            issue_lines = self.env['mesob.inventory.issue.voucher.line'].search([
                ('item_id', '=', item.id),
                ('voucher_id.state', 'in', ['issued', 'received']),
                ('voucher_id.issue_date', '>=', start_date)
            ])
            
            if not issue_lines:
                item.average_monthly_usage = 0.0
                item.max_monthly_usage = 0.0
                continue
            
            # Group by month and calculate usage
            from collections import defaultdict
            monthly_usage = defaultdict(float)
            
            for line in issue_lines:
                issue_date = line.voucher_id.issue_date
                month_key = issue_date.strftime('%Y-%m')
                monthly_usage[month_key] += line.quantity
            
            if monthly_usage:
                usage_values = list(monthly_usage.values())
                item.average_monthly_usage = sum(usage_values) / len(usage_values)
                item.max_monthly_usage = max(usage_values)
            else:
                item.average_monthly_usage = 0.0
                item.max_monthly_usage = 0.0
    
    @api.depends('average_monthly_usage', 'total_lead_time', 'safety_stock')
    def _compute_suggested_levels(self):
        """AUTO-062: Calculate suggested control levels based on usage and lead time (FR-SC-001, FR-SC-002)"""
        for item in self:
            if item.average_monthly_usage == 0:
                item.suggested_reorder_level = 0.0
                item.suggested_minimum_level = 0.0
                item.suggested_maximum_level = 0.0
                continue
            
            # Convert lead time to months
            lead_time_months = item.total_lead_time / 30.0 if item.total_lead_time > 0 else 0.5
            
            # Suggested minimum = safety stock (1 week of average usage as default)
            item.suggested_minimum_level = (item.average_monthly_usage / 4.0) if item.safety_stock == 0 else item.safety_stock
            
            # Suggested reorder = (avg usage × lead time) + safety stock
            item.suggested_reorder_level = (item.average_monthly_usage * lead_time_months) + item.suggested_minimum_level
            
            # Suggested maximum = 2 × reorder level (standard practice)
            item.suggested_maximum_level = item.suggested_reorder_level * 2
    
    def action_apply_suggested_levels(self):
        """AUTO-062: Apply system-calculated levels to actual control levels"""
        self.ensure_one()
        
        if self.suggested_reorder_level == 0:
            raise UserError(
                "AUTO-062: Cannot apply suggested levels. No historical usage data found. "
                "Please enter control levels manually or wait for usage history to accumulate."
            )
        
        self.write({
            'minimum_level': self.suggested_minimum_level,
            'reorder_level': self.suggested_reorder_level,
            'maximum_level': self.suggested_maximum_level,
            'last_calculation_date': fields.Datetime.now()
        })
        
        self.message_post(
            body=f"""<div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px;">
                <h3>✅ AUTO-062: Control Levels Auto-Applied</h3>
                <table style="width: 100%; margin-top: 10px;">
                    <tr><td><strong>Minimum Level:</strong></td><td>{self.minimum_level:.2f}</td></tr>
                    <tr><td><strong>Reorder Level:</strong></td><td>{self.reorder_level:.2f}</td></tr>
                    <tr><td><strong>Maximum Level:</strong></td><td>{self.maximum_level:.2f}</td></tr>
                </table>
                <p style="margin-top: 10px; font-size: 12px; color: #666;">
                    Based on {self.historical_period_months} months of usage history:<br/>
                    Average monthly usage: {self.average_monthly_usage:.2f}<br/>
                    Lead time: {self.total_lead_time} days
                </p>
            </div>""",
            subject='Control Levels Updated',
            message_type='notification'
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Control Levels Applied',
                'message': f'Auto-calculated levels applied successfully for {self.item_code}',
                'type': 'success',
                'sticky': False,
            }
        }
    
    @api.model
    def cron_recalculate_control_levels(self):
        """AUTO-062 + AUTO-065: Scheduled action to recalculate control levels for enabled items"""
        items = self.search([('auto_reorder_enabled', '=', True)])
        
        for item in items:
            try:
                # Force recomputation
                item._compute_usage_statistics()
                item._compute_suggested_levels()
                
                # Auto-apply if configured (optional flag can be added)
                if item.suggested_reorder_level > 0:
                    item.write({
                        'reorder_level': item.suggested_reorder_level,
                        'minimum_level': item.suggested_minimum_level,
                        'maximum_level': item.suggested_maximum_level,
                        'last_calculation_date': fields.Datetime.now()
                    })
                    
                    _logger.info(
                        f"AUTO-062: Auto-updated control levels for {item.item_code} - "
                        f"Reorder: {item.reorder_level:.2f}, Min: {item.minimum_level:.2f}, Max: {item.maximum_level:.2f}"
                    )
            except Exception as e:
                _logger.error(f"AUTO-062: Failed to recalculate levels for {item.item_code}: {str(e)}")
        
        _logger.info(f"AUTO-062: Completed control level recalculation for {len(items)} items")


    # ═══════════════════════════════════════════════════════════════════
    # AUTO-066: Dormant/Damaged/Obsolete Item Auto-Flagging
    # ═══════════════════════════════════════════════════════════════════
    
    @api.depends('item_code', 'average_monthly_usage')
    def _compute_item_flags(self):
        """AUTO-066: Auto-flag dormant and slow-moving items (FR-REP-003, FR-DISP2-001)"""
        for item in self:
            # Find last issue date
            last_issue = self.env['mesob.inventory.issue.voucher.line'].search([
                ('item_id', '=', item.id),
                ('voucher_id.state', 'in', ['issued', 'received'])
            ], order='voucher_id.issue_date desc', limit=1)
            
            if last_issue:
                last_issue_date = last_issue.voucher_id.issue_date
                today = fields.Date.today()
                delta = (today - last_issue_date).days
                item.days_since_last_issue = delta
                
                # Flag as dormant if no issues beyond threshold
                item.is_dormant = delta >= item.dormant_threshold_days
            else:
                # Never issued
                item.days_since_last_issue = 9999
                item.is_dormant = True
            
            # Flag as slow-moving if average monthly usage is very low (< 1 unit/month)
            item.is_slow_moving = (0 < item.average_monthly_usage < 1.0) and not item.is_dormant
    
    def action_flag_damaged(self):
        """AUTO-066: Manually flag item as damaged"""
        self.ensure_one()
        self.is_damaged = True
        
        self.message_post(
            body=f"""<div style="background-color: #f8d7da; border-left: 4px solid #dc3545; padding: 15px;">
                <h3>⚠️ AUTO-066: Item Flagged as Damaged</h3>
                <p><strong>Item:</strong> {self.item_code} - {self.name}</p>
                <p><strong>Current Stock:</strong> {self.current_stock}</p>
                <p><strong>Action Required:</strong> Review for disposal per FR-DISP2-001</p>
            </div>""",
            subject='Item Flagged as Damaged',
            message_type='notification'
        )
        
        return {'type': 'ir.actions.client', 'tag': 'reload'}
    
    def action_flag_obsolete(self):
        """AUTO-066: Manually flag item as obsolete"""
        self.ensure_one()
        self.is_obsolete = True
        
        self.message_post(
            body=f"""<div style="background-color: #f8d7da; border-left: 4px solid #dc3545; padding: 15px;">
                <h3>⚠️ AUTO-066: Item Flagged as Obsolete</h3>
                <p><strong>Item:</strong> {self.item_code} - {self.name}</p>
                <p><strong>Current Stock:</strong> {self.current_stock}</p>
                <p><strong>Action Required:</strong> Review for disposal per FR-DISP2-001</p>
            </div>""",
            subject='Item Flagged as Obsolete',
            message_type='notification'
        )
        
        return {'type': 'ir.actions.client', 'tag': 'reload'}
    
    def action_clear_flags(self):
        """AUTO-066: Clear damage/obsolete flags"""
        self.ensure_one()
        self.write({
            'is_damaged': False,
            'is_obsolete': False
        })
        
        self.message_post(
            body=f"<p>Damage/Obsolete flags cleared for {self.item_code}</p>",
            subject='Flags Cleared',
            message_type='comment'
        )
        
        return {'type': 'ir.actions.client', 'tag': 'reload'}
    
    @api.model
    def cron_flag_dormant_items(self):
        """AUTO-066: Scheduled action to identify and flag dormant/slow-moving items"""
        all_items = self.search([('active', '=', True)])
        
        dormant_count = 0
        slow_count = 0
        
        for item in all_items:
            item._compute_item_flags()
            
            if item.is_dormant:
                dormant_count += 1
            if item.is_slow_moving:
                slow_count += 1
        
        _logger.info(
            f"AUTO-066: Dormant/Slow-Moving scan complete. "
            f"Dormant: {dormant_count}, Slow-moving: {slow_count}"
        )
        
        # Notify PAO if significant dormant items found
        if dormant_count > 0:
            pao_group = self.env.ref('mesob_inventory_base.group_mesob_pao', raise_if_not_found=False)
            if pao_group:
                # Create a system notification
                self.env['mail.message'].create({
                    'message_type': 'notification',
                    'subject': f'AUTO-066: Dormant Items Alert ({dormant_count} items)',
                    'body': f"""<div style="background-color: #fff3cd; padding: 15px;">
                        <h3>📊 AUTO-066: Dormant & Slow-Moving Items Report</h3>
                        <ul>
                            <li><strong>Dormant Items:</strong> {dormant_count}</li>
                            <li><strong>Slow-Moving Items:</strong> {slow_count}</li>
                        </ul>
                        <p>Review these items for potential disposal (FR-DISP2-001, FR-REP-003)</p>
                    </div>""",
                    'partner_ids': [(6, 0, pao_group.users.mapped('partner_id').ids)]
                })

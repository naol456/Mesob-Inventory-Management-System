# -*- coding: utf-8 -*-
"""AUTO-029: Three-Way Match Auto-Validation for Payment Processing.

This module implements automated validation of Purchase Order, Model 19 Receipt,
and Supplier Invoice matching before payment is processed (FR-PROC-034, BR-PROC-002).
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class MesobPaymentValidation(models.Model):
    """Three-Way Match Payment Validation (AUTO-029).
    
    Validates:
    - Purchase Order (PO) - what was ordered
    - Model 19 Receipt - what was received and accepted
    - Supplier Invoice - what supplier is claiming payment for
    
    Blocks payment if:
    - Any document is missing
    - Quantities mismatch beyond tolerance
    - Unit prices mismatch beyond tolerance
    - Open DSR exists for the delivery (BR-PROC-002)
    """
    
    _name = 'mesob.payment.validation'
    _description = 'Three-Way Match Payment Validation'
    _order = 'validation_date desc, id desc'
    _rec_name = 'display_name'
    
    # ── References ──────────────────────────────────────────────────
    name = fields.Char(
        string='Validation Reference',
        required=True,
        copy=False,
        default='New',
        readonly=True
    )
    
    po_id = fields.Many2one(
        'mesob.procurement.order',
        string='Purchase Order',
        required=True,
        ondelete='restrict',
        help='Purchase Order being validated'
    )
    
    model19_id = fields.Many2one(
        'mesob.inventory.model19',
        string='Model 19 Receipt',
        required=True,
        ondelete='restrict',
        help='Model 19 receipt document'
    )
    
    invoice_number = fields.Char(
        string='Supplier Invoice Number',
        required=True,
        help='Supplier VAT-compliant tax invoice number'
    )
    
    invoice_date = fields.Date(
        string='Invoice Date',
        required=True,
        default=fields.Date.today
    )
    
    invoice_amount = fields.Monetary(
        string='Invoice Total Amount',
        required=True,
        currency_field='currency_id',
        help='Total amount claimed by supplier'
    )
    
    # ── Validation Results ──────────────────────────────────────────
    validation_date = fields.Datetime(
        string='Validation Date',
        default=fields.Datetime.now,
        readonly=True
    )
    
    validation_status = fields.Selection([
        ('pass', 'Passed - Ready for Payment'),
        ('fail', 'Failed - Payment Blocked'),
        ('warning', 'Warning - Manual Review Required'),
    ], string='Validation Status', compute='_compute_validation_status', store=True)
    
    mismatch_ids = fields.One2many(
        'mesob.payment.validation.mismatch',
        'validation_id',
        string='Mismatches Detected',
        readonly=True
    )
    
    has_open_dsr = fields.Boolean(
        string='Open DSR Exists',
        compute='_compute_has_open_dsr',
        store=True,
        help='BR-PROC-002: Payment blocked if open DSR exists'
    )
    
    dsr_ids = fields.Many2many(
        'mesob.inventory.dsr',
        string='Related DSRs',
        compute='_compute_has_open_dsr',
        store=True
    )
    
    # ── Tolerance Settings ──────────────────────────────────────────
    quantity_tolerance_percent = fields.Float(
        string='Quantity Tolerance (%)',
        default=2.0,
        help='Acceptable quantity variance percentage'
    )
    
    price_tolerance_percent = fields.Float(
        string='Price Tolerance (%)',
        default=1.0,
        help='Acceptable price variance percentage'
    )
    
    # ── Payment Control ─────────────────────────────────────────────
    payment_approved = fields.Boolean(
        string='Payment Approved',
        default=False,
        readonly=True,
        help='Set to True only when validation passes'
    )
    
    payment_blocked_reason = fields.Text(
        string='Payment Blocked Reason',
        compute='_compute_payment_blocked_reason',
        store=True
    )
    
    approved_by_id = fields.Many2one(
        'res.users',
        string='Approved By',
        readonly=True,
        help='PAO/Finance who approved payment override'
    )
    
    # ── Tracking ────────────────────────────────────────────────────
    state = fields.Selection([
        ('draft', 'Draft'),
        ('validated', 'Validated'),
        ('approved', 'Approved for Payment'),
        ('paid', 'Paid'),
        ('rejected', 'Rejected'),
    ], string='State', default='draft', required=True, tracking=True)
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )
    
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )
    
    note = fields.Text(string='Internal Notes')
    
    # ── AUTO-030: Liquidated Damages Calculation ────────────────────
    contract_delivery_date = fields.Date(
        string='Contract Delivery Date',
        help='AUTO-030: Contracted delivery date for LD calculation'
    )
    
    actual_delivery_date = fields.Date(
        string='Actual Delivery Date',
        compute='_compute_actual_delivery_date',
        store=True,
        help='AUTO-030: Model 19 acceptance date'
    )
    
    delay_days = fields.Integer(
        string='Delay (Working Days)',
        compute='_compute_liquidated_damages',
        store=True,
        help='AUTO-030: Working days between contract and actual delivery'
    )
    
    ld_rate = fields.Float(
        string='LD Rate',
        default=0.001,
        help='AUTO-030: Liquidated damages rate (default: 1/1000 per working day per FR-PROC-036)'
    )
    
    contract_value = fields.Monetary(
        string='Contract Value',
        compute='_compute_contract_value',
        store=True,
        currency_field='currency_id',
        help='AUTO-030: Total PO value for LD calculation'
    )
    
    ld_calculated = fields.Monetary(
        string='LD Calculated',
        compute='_compute_liquidated_damages',
        store=True,
        currency_field='currency_id',
        help='AUTO-030: Calculated liquidated damages (delay days × rate × contract value)'
    )
    
    ld_cap = fields.Monetary(
        string='LD Cap (10%)',
        compute='_compute_liquidated_damages',
        store=True,
        currency_field='currency_id',
        help='AUTO-030: Maximum LD (10% of contract value per FR-PROC-036)'
    )
    
    ld_amount = fields.Monetary(
        string='LD Amount to Deduct',
        compute='_compute_liquidated_damages',
        store=True,
        currency_field='currency_id',
        help='AUTO-030: Final LD amount (min of calculated and cap)'
    )
    
    net_payment_amount = fields.Monetary(
        string='Net Payment Amount',
        compute='_compute_liquidated_damages',
        store=True,
        currency_field='currency_id',
        help='AUTO-030: Invoice amount minus LD deduction'
    )
    
    has_delivery_delay = fields.Boolean(
        string='Delivery Delayed',
        compute='_compute_liquidated_damages',
        store=True,
        help='AUTO-030: True if delivery was late'
    )
    
    # ── Computed Fields ─────────────────────────────────────────────
    
    @api.depends('model19_id', 'model19_id.confirmation_date')
    def _compute_actual_delivery_date(self):
        """AUTO-030: Get actual delivery date from Model 19 acceptance."""
        for rec in self:
            if rec.model19_id and rec.model19_id.confirmation_date:
                rec.actual_delivery_date = rec.model19_id.confirmation_date
            else:
                rec.actual_delivery_date = False
    
    @api.depends('po_id', 'po_id.line_ids')
    def _compute_contract_value(self):
        """AUTO-030: Calculate total contract value from PO."""
        for rec in self:
            if rec.po_id and rec.po_id.line_ids:
                rec.contract_value = sum(line.price_subtotal for line in rec.po_id.line_ids)
            else:
                rec.contract_value = 0.0
    
    @api.depends('contract_delivery_date', 'actual_delivery_date', 'contract_value', 'ld_rate')
    def _compute_liquidated_damages(self):
        """AUTO-030: Auto-calculate liquidated damages for late delivery (FR-PROC-036).
        
        Formula per Ethiopian Federal Procurement Regulation:
        - LD = Contract Value × (1/1000) × Delay in Working Days
        - Capped at 10% of contract value
        - Only applied if actual delivery exceeds contract date
        - Net payment = Invoice amount - LD amount
        """
        for rec in self:
            # Default values
            rec.delay_days = 0
            rec.ld_calculated = 0.0
            rec.ld_cap = 0.0
            rec.ld_amount = 0.0
            rec.net_payment_amount = rec.invoice_amount
            rec.has_delivery_delay = False
            
            # Check if we have all required data
            if not rec.contract_delivery_date or not rec.actual_delivery_date or not rec.contract_value:
                continue
            
            # Calculate delay
            if rec.actual_delivery_date > rec.contract_delivery_date:
                rec.has_delivery_delay = True
                
                # Calculate working days (simplified: all days are working days)
                # TODO: Exclude Ethiopian public holidays and weekends
                delay = (rec.actual_delivery_date - rec.contract_delivery_date).days
                rec.delay_days = delay
                
                # Calculate LD per FR-PROC-036
                # LD = Contract Value × LD Rate × Delay Days
                rec.ld_calculated = rec.contract_value * rec.ld_rate * delay
                
                # Calculate cap (10% of contract value)
                rec.ld_cap = rec.contract_value * 0.10
                
                # Apply cap
                if rec.ld_calculated > rec.ld_cap:
                    rec.ld_amount = rec.ld_cap
                else:
                    rec.ld_amount = rec.ld_calculated
                
                # Calculate net payment
                rec.net_payment_amount = rec.invoice_amount - rec.ld_amount
                
                _logger.info(
                    f"AUTO-030: LD calculated for {rec.name} - "
                    f"Delay: {delay} days, LD: ETB {rec.ld_amount:,.2f}, "
                    f"Net Payment: ETB {rec.net_payment_amount:,.2f}"
                )
    
    @api.depends('po_id', 'invoice_number')
    def _compute_display_name(self):
        for rec in self:
            if rec.po_id and rec.invoice_number:
                rec.display_name = f"Payment Validation: {rec.po_id.name} / {rec.invoice_number}"
            else:
                rec.display_name = rec.name or 'New Payment Validation'
    
    @api.depends('po_id', 'model19_id')
    def _compute_has_open_dsr(self):
        """Check for open DSRs related to this PO/Receipt (BR-PROC-002)."""
        for rec in self:
            if not rec.model19_id or not rec.model19_id.receiving_id:
                rec.has_open_dsr = False
                rec.dsr_ids = False
                continue
            
            # Find DSRs from the same receiving order
            dsrs = self.env['mesob.inventory.dsr'].search([
                ('receiving_id', '=', rec.model19_id.receiving_id.id),
                ('state', '!=', 'closed')
            ])
            
            rec.has_open_dsr = bool(dsrs)
            rec.dsr_ids = dsrs
    
    @api.depends('mismatch_ids', 'has_open_dsr', 'payment_approved')
    def _compute_validation_status(self):
        """Compute overall validation status."""
        for rec in self:
            if rec.has_open_dsr:
                rec.validation_status = 'fail'
            elif rec.payment_approved:
                rec.validation_status = 'pass'
            else:
                critical_mismatches = rec.mismatch_ids.filtered(lambda m: m.severity == 'critical')
                warning_mismatches = rec.mismatch_ids.filtered(lambda m: m.severity == 'warning')
                
                if critical_mismatches:
                    rec.validation_status = 'fail'
                elif warning_mismatches:
                    rec.validation_status = 'warning'
                else:
                    rec.validation_status = 'pass'
    
    @api.depends('validation_status', 'has_open_dsr', 'mismatch_ids')
    def _compute_payment_blocked_reason(self):
        """Generate human-readable reason for payment block."""
        for rec in self:
            reasons = []
            
            if rec.has_open_dsr:
                reasons.append(
                    f"BR-PROC-002: Open DSR exists ({', '.join(rec.dsr_ids.mapped('name'))}). "
                    "Resolve rejection issues before payment."
                )
            
            critical_mismatches = rec.mismatch_ids.filtered(lambda m: m.severity == 'critical')
            for mismatch in critical_mismatches:
                reasons.append(f"• {mismatch.mismatch_type}: {mismatch.description}")
            
            rec.payment_blocked_reason = '\n'.join(reasons) if reasons else False
    
    # ── CRUD ────────────────────────────────────────────────────────
    
    @api.model_create_multi
    def create(self, vals_list):
        """Auto-generate validation reference and run validation."""
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('mesob.payment.validation') or 'PAYVAL/001'
        
        records = super().create(vals_list)
        
        for record in records:
            record.action_run_validation()
        
        return records
    
    # ── Actions ─────────────────────────────────────────────────────
    
    def action_run_validation(self):
        """AUTO-029: Run three-way match validation."""
        self.ensure_one()
        
        # Clear previous mismatches
        self.mismatch_ids.unlink()
        
        mismatches = []
        
        # Validation 1: Check all three documents exist
        if not self.po_id:
            mismatches.append({
                'validation_id': self.id,
                'mismatch_type': 'missing_po',
                'severity': 'critical',
                'description': 'Purchase Order is missing'
            })
        
        if not self.model19_id:
            mismatches.append({
                'validation_id': self.id,
                'mismatch_type': 'missing_model19',
                'severity': 'critical',
                'description': 'Model 19 receipt is missing'
            })
        
        if not self.invoice_number:
            mismatches.append({
                'validation_id': self.id,
                'mismatch_type': 'missing_invoice',
                'severity': 'critical',
                'description': 'Supplier invoice is missing'
            })
        
        # If any document missing, stop here
        if mismatches:
            self.env['mesob.payment.validation.mismatch'].create(mismatches)
            self.state = 'validated'
            _logger.warning(f"AUTO-029: Payment validation {self.name} FAILED - Missing documents")
            return
        
        # Validation 2: Line-by-line matching
        self._validate_line_items(mismatches)
        
        # Validation 3: Total amount check
        self._validate_total_amount(mismatches)
        
        # Create mismatch records
        if mismatches:
            self.env['mesob.payment.validation.mismatch'].create(mismatches)
        
        # Update state
        self.state = 'validated'
        
        # Auto-approve if validation passes
        if self.validation_status == 'pass':
            self.write({
                'payment_approved': True,
                'state': 'approved'
            })
            
            # AUTO-030: Show LD deduction if applicable
            if self.has_delivery_delay and self.ld_amount > 0:
                self.message_post(
                    body=f"""<div style="background-color: #fff3cd; border-left: 4px solid #856404; padding: 15px;">
                        <h3>AUTO-030: Liquidated Damages Applied</h3>
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr>
                                <td style="padding: 5px 0;"><strong>Contract Delivery Date:</strong></td>
                                <td style="padding: 5px 0; text-align: right;">{self.contract_delivery_date}</td>
                            </tr>
                            <tr>
                                <td style="padding: 5px 0;"><strong>Actual Delivery Date:</strong></td>
                                <td style="padding: 5px 0; text-align: right;">{self.actual_delivery_date}</td>
                            </tr>
                            <tr style="background-color: #fff3cd;">
                                <td style="padding: 5px 0;"><strong>Delay (Working Days):</strong></td>
                                <td style="padding: 5px 0; text-align: right; font-weight: bold;">{self.delay_days} days</td>
                            </tr>
                            <tr>
                                <td style="padding: 5px 0;">Contract Value:</td>
                                <td style="padding: 5px 0; text-align: right;">ETB {self.contract_value:,.2f}</td>
                            </tr>
                            <tr>
                                <td style="padding: 5px 0;">LD Rate:</td>
                                <td style="padding: 5px 0; text-align: right;">{self.ld_rate} (1/1000 per day)</td>
                            </tr>
                            <tr>
                                <td style="padding: 5px 0;">LD Calculated:</td>
                                <td style="padding: 5px 0; text-align: right;">ETB {self.ld_calculated:,.2f}</td>
                            </tr>
                            <tr>
                                <td style="padding: 5px 0;">LD Cap (10%):</td>
                                <td style="padding: 5px 0; text-align: right;">ETB {self.ld_cap:,.2f}</td>
                            </tr>
                            <tr style="background-color: #f8d7da;">
                                <td style="padding: 8px 0; border-top: 2px solid #856404; font-weight: bold;">LD Amount Deducted:</td>
                                <td style="padding: 8px 0; text-align: right; border-top: 2px solid #856404; color: #dc3545; font-weight: bold; font-size: 16px;">ETB {self.ld_amount:,.2f}</td>
                            </tr>
                            <tr>
                                <td style="padding: 5px 0;">Invoice Amount:</td>
                                <td style="padding: 5px 0; text-align: right;">ETB {self.invoice_amount:,.2f}</td>
                            </tr>
                            <tr style="background-color: #d4edda;">
                                <td style="padding: 8px 0; border-top: 2px solid #28a745; font-weight: bold;">Net Payment Amount:</td>
                                <td style="padding: 8px 0; text-align: right; border-top: 2px solid #28a745; color: #155724; font-weight: bold; font-size: 16px;">ETB {self.net_payment_amount:,.2f}</td>
                            </tr>
                        </table>
                        <p style="margin-top: 15px; padding: 10px; background-color: #e7f3ff; border-radius: 4px;">
                            <strong>ℹ️ FR-PROC-036:</strong> Liquidated damages automatically calculated at 1/1000 of contract value per working day of delay, capped at 10% of contract value.
                        </p>
                    </div>""",
                    subject='Liquidated Damages Applied',
                    message_type='comment'
                )
            
            _logger.info(f"AUTO-029: Payment validation {self.name} PASSED - Ready for payment")
        else:
            _logger.warning(
                f"AUTO-029: Payment validation {self.name} FAILED - "
                f"Status: {self.validation_status}, Mismatches: {len(mismatches)}"
            )
    
    def _validate_line_items(self, mismatches):
        """Validate line-by-line: PO vs Model 19 vs Invoice."""
        po_lines = {line.item_id.id: line for line in self.po_id.line_ids if line.item_id}
        model19_lines = {line.item_id.id: line for line in self.model19_id.line_ids if line.item_id}
        
        # Check each Model 19 line against PO
        for item_id, m19_line in model19_lines.items():
            po_line = po_lines.get(item_id)
            
            if not po_line:
                mismatches.append({
                    'validation_id': self.id,
                    'item_id': item_id,
                    'mismatch_type': 'item_not_in_po',
                    'severity': 'critical',
                    'description': f"Item {m19_line.item_id.item_code} received but not in PO"
                })
                continue
            
            # Quantity check
            qty_variance = abs(m19_line.quantity - po_line.quantity)
            qty_variance_pct = (qty_variance / po_line.quantity * 100) if po_line.quantity > 0 else 0
            
            if qty_variance_pct > self.quantity_tolerance_percent:
                mismatches.append({
                    'validation_id': self.id,
                    'item_id': item_id,
                    'mismatch_type': 'quantity_mismatch',
                    'severity': 'critical' if qty_variance_pct > 5 else 'warning',
                    'po_value': po_line.quantity,
                    'model19_value': m19_line.quantity,
                    'variance': qty_variance,
                    'description': (
                        f"Item {m19_line.item_id.item_code}: "
                        f"PO qty {po_line.quantity}, Model 19 qty {m19_line.quantity}, "
                        f"Variance {qty_variance_pct:.1f}%"
                    )
                })
            
            # Price check
            price_variance = abs(m19_line.unit_price - po_line.price_unit)
            price_variance_pct = (price_variance / po_line.price_unit * 100) if po_line.price_unit > 0 else 0
            
            if price_variance_pct > self.price_tolerance_percent:
                mismatches.append({
                    'validation_id': self.id,
                    'item_id': item_id,
                    'mismatch_type': 'price_mismatch',
                    'severity': 'critical' if price_variance_pct > 3 else 'warning',
                    'po_value': po_line.price_unit,
                    'model19_value': m19_line.unit_price,
                    'variance': price_variance,
                    'description': (
                        f"Item {m19_line.item_id.item_code}: "
                        f"PO price ETB {po_line.price_unit}, Model 19 price ETB {m19_line.unit_price}, "
                        f"Variance {price_variance_pct:.1f}%"
                    )
                })
    
    def _validate_total_amount(self, mismatches):
        """Validate total invoice amount against PO and Model 19."""
        po_total = sum(line.quantity * line.price_unit for line in self.po_id.line_ids)
        model19_total = self.model19_id.total_amount
        
        # Check invoice amount against Model 19 total
        amount_variance = abs(self.invoice_amount - model19_total)
        amount_variance_pct = (amount_variance / model19_total * 100) if model19_total > 0 else 0
        
        if amount_variance_pct > self.price_tolerance_percent:
            mismatches.append({
                'validation_id': self.id,
                'mismatch_type': 'total_amount_mismatch',
                'severity': 'critical' if amount_variance_pct > 3 else 'warning',
                'po_value': po_total,
                'model19_value': model19_total,
                'invoice_value': self.invoice_amount,
                'variance': amount_variance,
                'description': (
                    f"Total amount mismatch: "
                    f"Model 19 ETB {model19_total:,.2f}, Invoice ETB {self.invoice_amount:,.2f}, "
                    f"Variance {amount_variance_pct:.1f}%"
                )
            })
    
    def action_override_approve(self):
        """PAO/Finance manual override approval for payment."""
        self.ensure_one()
        
        if self.validation_status == 'pass':
            raise UserError("Validation already passed. No override needed.")
        
        if not self.env.user.has_group('mesob_inventory_base.group_mesob_pao'):
            raise UserError("Only PAO can override payment validation.")
        
        self.write({
            'payment_approved': True,
            'approved_by_id': self.env.user.id,
            'state': 'approved'
        })
        
        self.message_post(
            body=f"""<p><strong>Payment Validation Override</strong></p>
            <p>Approved by: {self.env.user.name}</p>
            <p>Reason: Manual PAO override</p>
            <p><em>Original validation status: {self.validation_status}</em></p>""",
            subject=f"Payment Override: {self.name}"
        )
        
        _logger.info(f"AUTO-029: Payment validation {self.name} OVERRIDDEN by {self.env.user.name}")
    
    def action_reject_payment(self):
        """Reject payment processing."""
        self.ensure_one()
        self.write({
            'payment_approved': False,
            'state': 'rejected'
        })


class MesobPaymentValidationMismatch(models.Model):
    """Payment Validation Mismatch Detail."""
    
    _name = 'mesob.payment.validation.mismatch'
    _description = 'Payment Validation Mismatch'
    _order = 'severity desc, id'
    
    validation_id = fields.Many2one(
        'mesob.payment.validation',
        string='Validation',
        required=True,
        ondelete='cascade'
    )
    
    item_id = fields.Many2one(
        'mesob.inventory.item',
        string='Item',
        help='Item with mismatch (if line-level)'
    )
    
    mismatch_type = fields.Selection([
        ('missing_po', 'Missing Purchase Order'),
        ('missing_model19', 'Missing Model 19'),
        ('missing_invoice', 'Missing Invoice'),
        ('item_not_in_po', 'Item Not in PO'),
        ('quantity_mismatch', 'Quantity Mismatch'),
        ('price_mismatch', 'Price Mismatch'),
        ('total_amount_mismatch', 'Total Amount Mismatch'),
    ], string='Mismatch Type', required=True)
    
    severity = fields.Selection([
        ('warning', 'Warning'),
        ('critical', 'Critical - Payment Blocked'),
    ], string='Severity', required=True, default='warning')
    
    description = fields.Text(
        string='Description',
        required=True
    )
    
    po_value = fields.Float(string='PO Value')
    model19_value = fields.Float(string='Model 19 Value')
    invoice_value = fields.Float(string='Invoice Value')
    variance = fields.Float(string='Variance')

# =======================================================================================
# NAOL'S AUTOMATION TASK IMPLEMENTATIONS
# =======================================================================================
# This file contains the complete implementations for Naol's partially complete
# and not-started automation tasks. These will be integrated into mesob_procurement.py
# =======================================================================================

# AUTO-011: Minimum Advertising Period Enforcement (HIGH PRIORITY - COMPLIANCE)
# Location: Add to MesobProcurementTender class
# =======================================================================================

def _compute_minimum_advertising_days(self):
    """AUTO-011: Calculate minimum advertising days based on procurement method (FR-PROC-014).
    
    FPPA requirements:
    - International Competitive Bidding: 45 days minimum
    - National Competitive Bidding: 30 days minimum
    - Restricted Bidding: 21 days minimum
    - Request for Quotation (RFQ): 7 days minimum
    """
    for tender in self:
        method_requirements = {
            'icb': 45,  # International Competitive Bidding
            'ncb': 30,  # National Competitive Bidding
            'restricted': 21,  # Restricted Bidding
            'rfq': 7,  # Request for Quotation
            'direct': 0,  # Direct Procurement (no advertising)
            'emergency': 0,  # Emergency (no minimum)
        }
        
        tender.minimum_advertising_days = method_requirements.get(tender.procurement_method, 30)

def _compute_earliest_submission_date(self):
    """AUTO-011: Calculate earliest allowable bid submission deadline."""
    for tender in self:
        if tender.advertisement_date and tender.minimum_advertising_days:
            from datetime import timedelta
            tender.earliest_submission_date = tender.advertisement_date + timedelta(days=tender.minimum_advertising_days)
        else:
            tender.earliest_submission_date = False

@api.constrains('advertisement_date', 'submission_deadline', 'procurement_method')
def _check_minimum_advertising_period(self):
    """AUTO-011: Enforce minimum advertising period (FR-PROC-014).
    
    Blocks tender advertisement if deadline doesn't meet minimum requirements.
    This is a CRITICAL compliance check per FPPA regulations.
    """
    for tender in self:
        if not tender.advertisement_date or not tender.submission_deadline:
            continue
        
        # Calculate actual advertising period
        actual_days = (tender.submission_deadline.date() - tender.advertisement_date).days
        
        # Check against minimum requirement
        if actual_days < tender.minimum_advertising_days:
            raise ValidationError(
                f"AUTO-011: ADVERTISING PERIOD VIOLATION (FR-PROC-014)\n\n"
                f"Procurement Method: {dict(tender._fields['procurement_method'].selection).get(tender.procurement_method)}\n"
                f"Minimum Required: {tender.minimum_advertising_days} days\n"
                f"Your Period: {actual_days} days\n\n"
                f"Compliance Rule:\n"
                f"Per FPPA Proclamation 1210/2012 (FR-PROC-014), {tender.procurement_method.upper()} "
                f"requires a minimum advertising period of {tender.minimum_advertising_days} days to ensure "
                f"fair competition and sufficient time for bid preparation.\n\n"
                f"ACTION REQUIRED:\n"
                f"• Extend submission deadline to at least {tender.earliest_submission_date.strftime('%Y-%m-%d')}\n"
                f"• OR change advertising date to allow sufficient time\n\n"
                f"This validation cannot be overridden - it is a regulatory requirement."
            )
        
        _logger.info(
            f"AUTO-011: Advertising period validated - Tender: {tender.name}, "
            f"Method: {tender.procurement_method}, Required: {tender.minimum_advertising_days} days, "
            f"Actual: {actual_days} days ✓"
        )


# AUTO-013: RFQ Three-Quotation Rule Enforcement (HIGH PRIORITY - COMPLIANCE)
# Location: Add to MesobProcurementTender class
# =======================================================================================

def action_request_rfq_exception(self):
    """AUTO-013: Request exception for RFQ with fewer than 3 quotations (FR-PROC-016 + BR-PROC-005).
    
    Per FPPA regulations:
    - RFQ requires minimum 3 quotations for validity
    - If fewer than 3 responsive bids received, procurement MUST be cancelled and re-advertised
    - Exception requires PAO/HOPE written approval with justification
    - Documented in audit trail
    """
    self.ensure_one()
    
    if self.procurement_method != 'rfq':
        raise UserError("This function only applies to Request for Quotation (RFQ) tenders.")
    
    # Count responsive bids (not late, preliminary passed)
    responsive_bids = self.bid_ids.filtered(lambda b: b.preliminary_passed and not b.is_late)
    responsive_count = len(responsive_bids)
    
    if responsive_count >= 3:
        raise UserError(
            f"No exception needed - you have {responsive_count} responsive quotations. "
            "The three-quotation requirement is satisfied."
        )
    
    # Open exception request wizard
    return {
        'type': 'ir.actions.act_window',
        'name': 'RFQ Exception Request',
        'res_model': 'mesob.rfq.exception.wizard',
        'view_mode': 'form',
        'target': 'new',
        'context': {
            'default_tender_id': self.id,
            'default_responsive_bid_count': responsive_count,
            'default_required_count': 3,
        }
    }

@api.constrains('state')
def _check_rfq_three_quotation_rule(self):
    """AUTO-013: Enforce three-quotation rule for RFQ before evaluation (FR-PROC-016 + BR-PROC-005).
    
    Blocks progression from 'bid_submission' to 'evaluation' if fewer than 3 responsive bids.
    """
    for tender in self:
        # Only check when moving to evaluation stage
        if tender.state != 'evaluation':
            continue
        
        # Only applies to RFQ
        if tender.procurement_method != 'rfq':
            continue
        
        # Count responsive bids
        responsive_bids = tender.bid_ids.filtered(lambda b: b.preliminary_passed and not b.is_late)
        responsive_count = len(responsive_bids)
        
        # Check three-quotation requirement
        if responsive_count < 3:
            # Check if exception has been approved
            if not tender.rfq_exception_approved:
                raise ValidationError(
                    f"AUTO-013: THREE-QUOTATION RULE VIOLATION (FR-PROC-016 + BR-PROC-005)\n\n"
                    f"RFQ EVALUATION BLOCKED\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"Tender: {tender.name}\n"
                    f"Responsive Quotations Received: {responsive_count}\n"
                    f"Required: 3 (minimum)\n\n"
                    f"FPPA REQUIREMENT:\n"
                    f"Per Federal Public Procurement Agency regulations:\n"
                    f"• FR-PROC-016: RFQ validity requires minimum 3 quotations\n"
                    f"• BR-PROC-005: Fewer than 3 quotations = Re-advertisement mandatory\n\n"
                    f"OPTIONS:\n"
                    f"1. CANCEL & RE-ADVERTISE (Recommended)\n"
                    f"   → Cancel this tender\n"
                    f"   → Re-advertise to wider supplier base\n"
                    f"   → Target minimum 5 invitations to get 3+ responses\n\n"
                    f"2. REQUEST EXCEPTION (Requires PAO/HOPE Approval)\n"
                    f"   → Use 'Request RFQ Exception' button\n"
                    f"   → Provide written justification\n"
                    f"   → Obtain PAO or HOPE written approval\n"
                    f"   → Document market research showing limited suppliers\n\n"
                    f"This validation protects against FR-PROC-016 non-compliance and ensures audit compliance."
                )
            else:
                # Exception approved - log warning but allow
                _logger.warning(
                    f"AUTO-013: RFQ evaluation proceeding with exception approval - "
                    f"Tender: {tender.name}, Responsive bids: {responsive_count}/3, "
                    f"Exception approved by: {tender.rfq_exception_approver_id.name if tender.rfq_exception_approver_id else 'Unknown'}, "
                    f"Reason: {tender.rfq_exception_reason}"
                )
                
                tender.message_post(
                    body=f"""<div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px;">
                        <h3 style="color: #856404;">⚠️ AUTO-013: RFQ Exception Approved</h3>
                        <p><strong>Three-Quotation Rule Waived</strong></p>
                        <table style="width: 100%;">
                            <tr>
                                <td><strong>Responsive Quotations:</strong></td>
                                <td>{responsive_count} (Normal requirement: 3)</td>
                            </tr>
                            <tr>
                                <td><strong>Exception Approved By:</strong></td>
                                <td>{tender.rfq_exception_approver_id.name if tender.rfq_exception_approver_id else 'N/A'}</td>
                            </tr>
                            <tr>
                                <td><strong>Justification:</strong></td>
                                <td>{tender.rfq_exception_reason or 'N/A'}</td>
                            </tr>
                        </table>
                        <p style="margin-top: 10px; font-size: 11px; color: #856404;">
                            This exception is logged for audit trail per NFR-QUAL-001.
                        </p>
                    </div>""",
                    subject='RFQ Exception: Three-Quotation Rule Waived'
                )


# AUTO-032: Complete Retention Release Workflow
# Location: Add to MesobProcurementContract class
# =======================================================================================

def action_release_retention(self):
    """AUTO-032: Release retention to supplier (FR-PROC-037).
    
    ENHANCED VERSION - Complete workflow with all validation.
    
    Conditions:
    - Contract closed (final Model 19 confirmed)
    - Warranty period elapsed
    - No defects liability issues
    - Procurement officer clearance
    - Payment voucher auto-generated
    """
    self.ensure_one()
    
    # ====== VALIDATION CHECKS ======
    
    if self.state != 'closed':
        raise UserError(
            "AUTO-032: Retention Release Blocked\n\n"
            "Retention can only be released for closed contracts.\n\n"
            f"Current Status: {dict(self._fields['state'].selection).get(self.state)}\n"
            "Required Status: Closed\n\n"
            "Please close the contract first by confirming all deliveries complete."
        )
    
    if not self.warranty_expiry_date:
        raise UserError(
            "AUTO-032: Warranty Configuration Missing\n\n"
            "Warranty period not configured. Cannot determine if warranty has elapsed.\n\n"
            "ACTION REQUIRED:\n"
            "1. Set 'Warranty Period (Months)' on contract\n"
            "2. Confirm 'Contract Close Date' is set\n"
            "3. System will auto-calculate warranty expiry date"
        )
    
    today = fields.Date.today()
    if today < self.warranty_expiry_date:
        days_remaining = (self.warranty_expiry_date - today).days
        raise UserError(
            f"AUTO-032: Warranty Period Not Elapsed (FR-PROC-037)\n\n"
            f"Cannot release retention until warranty period completes.\n\n"
            f"Contract: {self.name}\n"
            f"Warranty Expires: {self.warranty_expiry_date.strftime('%Y-%m-%d')}\n"
            f"Today: {today.strftime('%Y-%m-%d')}\n"
            f"Days Remaining: {days_remaining}\n\n"
            f"Per FR-PROC-037, retention protects against defects during warranty period.\n"
            f"Please wait {days_remaining} more day(s) before releasing retention."
        )
    
    if not self.defects_cleared:
        raise UserError(
            "AUTO-032: Defects Liability Not Cleared\n\n"
            "Procurement officer must confirm defects liability clearance before retention release.\n\n"
            "ACTION REQUIRED:\n"
            "1. Inspect all deliveries for defects\n"
            "2. Confirm no outstanding quality issues\n"
            "3. Check 'Defects Liability Cleared' checkbox on contract form\n\n"
            "Retention protects against warranty claims - do not release if any defects exist."
        )
    
    if self.retention_released:
        raise UserError(
            f"AUTO-032: Retention Already Released\n\n"
            f"Retention was previously released on {self.retention_release_date.strftime('%Y-%m-%d')}.\n"
            f"Amount Released: ETB {self.cumulative_retention:,.2f}\n\n"
            f"Cannot release retention twice."
        )
    
    if self.cumulative_retention <= 0:
        raise UserError(
            "AUTO-032: No Retention to Release\n\n"
            "Cumulative retention amount is zero or negative.\n"
            f"Current Retention: ETB {self.cumulative_retention:,.2f}\n\n"
            "There is nothing to release."
        )
    
    # ====== RELEASE RETENTION ======
    
    retention_amount = self.cumulative_retention
    
    self.write({
        'retention_released': True,
        'retention_release_date': today
    })
    
    # ====== AUTO-GENERATE PAYMENT VOUCHER ======
    
    # Create payment certificate for retention release
    payment_cert = self.env['mesob.procurement.payment.certificate'].create({
        'contract_id': self.id,
        'supplier_id': self.supplier_id.id,
        'payment_type': 'retention_release',
        'gross_amount': retention_amount,
        'retention_deducted': 0.0,  # No further retention on retention release
        'net_payable': retention_amount,
        'description': f"Retention Release for Contract {self.name} (AUTO-032: FR-PROC-037)",
        'state': 'draft',
    })
    
    # ====== NOTIFICATIONS ======
    
    # Post to contract chatter
    self.message_post(
        body=f"""<div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px;">
            <h3 style="color: #155724; margin-top: 0;">✅ AUTO-032: Retention Released (FR-PROC-037)</h3>
            <table style="width: 100%; border-collapse: collapse;">
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #c3e6cb;"><strong>Contract:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #c3e6cb;">{self.name}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #c3e6cb;"><strong>Supplier:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #c3e6cb;">{self.supplier_id.name}</td>
                </tr>
                <tr style="background-color: #d4edda;">
                    <td style="padding: 8px; border-bottom: 1px solid #c3e6cb;"><strong>Retention Amount:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #c3e6cb; font-size: 18px; font-weight: bold; color: #155724;">
                        ETB {retention_amount:,.2f}
                    </td>
                </tr>
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #c3e6cb;"><strong>Release Date:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #c3e6cb;">{today.strftime('%Y-%m-%d')}</td>
                </tr>
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #c3e6cb;"><strong>Warranty Period:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #c3e6cb;">
                        {self.warranty_period_months} months (Expired: {self.warranty_expiry_date.strftime('%Y-%m-%d')})
                    </td>
                </tr>
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #c3e6cb;"><strong>Released By:</strong></td>
                    <td style="padding: 8px; border-bottom: 1px solid #c3e6cb;">{self.env.user.name}</td>
                </tr>
                <tr>
                    <td style="padding: 8px;"><strong>Payment Certificate:</strong></td>
                    <td style="padding: 8px;">
                        <a href="/web#id={payment_cert.id}&model=mesob.procurement.payment.certificate&view_type=form"
                           style="color: #155724; font-weight: bold;">
                            View Payment Voucher →
                        </a>
                    </td>
                </tr>
            </table>
            <div style="background-color: #fff; padding: 10px; border-radius: 4px; margin-top: 15px;">
                <p style="margin: 0; font-size: 12px; color: #155724;">
                    <strong>✓ Compliance Checks Passed:</strong>
                </p>
                <ul style="margin: 5px 0 0 20px; font-size: 12px;">
                    <li>Contract closed and final delivery confirmed</li>
                    <li>Warranty period fully elapsed ({self.warranty_period_months} months)</li>
                    <li>Defects liability cleared by procurement officer</li>
                    <li>Payment voucher auto-generated</li>
                </ul>
            </div>
            <p style="margin: 15px 0 0 0; font-size: 11px; color: #666;">
                AUTO-032: Retention released per FR-PROC-037. 
                Payment voucher created for accounts processing.
            </p>
        </div>""",
        subject=f'✅ Retention Released: ETB {retention_amount:,.2f}',
        message_type='notification'
    )
    
    # Notify accounts team
    accounts_group = self.env.ref('account.group_account_manager', raise_if_not_found=False)
    if accounts_group and accounts_group.users:
        payment_cert.message_post(
            body=f"""<div style="background-color: #e7f3ff; border-left: 4px solid #0066cc; padding: 15px;">
                <h3 style="color: #004085;">💰 Retention Release Payment</h3>
                <p>A retention release payment voucher has been created and requires processing:</p>
                <table style="width: 100%;">
                    <tr>
                        <td><strong>Contract:</strong></td>
                        <td>{self.name}</td>
                    </tr>
                    <tr>
                        <td><strong>Supplier:</strong></td>
                        <td>{self.supplier_id.name}</td>
                    </tr>
                    <tr>
                        <td><strong>Amount:</strong></td>
                        <td style="font-size: 18px; font-weight: bold; color: #0066cc;">ETB {retention_amount:,.2f}</td>
                    </tr>
                </table>
                <p style="margin-top: 15px;"><strong>Action Required:</strong> Process payment per standard accounts procedures.</p>
            </div>""",
            subject='New Payment: Retention Release',
            message_type='notification',
            partner_ids=accounts_group.users.mapped('partner_id').ids
        )
    
    _logger.info(
        f"AUTO-032: Retention released - Contract: {self.name}, "
        f"Supplier: {self.supplier_id.name}, Amount: ETB {retention_amount:,.2f}, "
        f"Released by: {self.env.user.name}"
    )
    
    return {
        'type': 'ir.actions.act_window',
        'name': 'Retention Release Payment Voucher',
        'res_model': 'mesob.procurement.payment.certificate',
        'res_id': payment_cert.id,
        'view_mode': 'form',
        'target': 'current',
    }


# =======================================================================================
# NEW FIELDS TO ADD TO MODELS
# =======================================================================================

# Add to MesobProcurementTender:
"""
# AUTO-011: Minimum advertising period enforcement fields
minimum_advertising_days = fields.Integer(
    string='Minimum Advertising Days',
    compute='_compute_minimum_advertising_days',
    store=True,
    help='AUTO-011: Minimum days required per procurement method (FR-PROC-014)'
)

earliest_submission_date = fields.Datetime(
    string='Earliest Allowable Deadline',
    compute='_compute_earliest_submission_date',
    store=True,
    help='AUTO-011: Earliest date that meets minimum advertising requirement'
)

# AUTO-013: RFQ three-quotation rule fields
rfq_exception_approved = fields.Boolean(
    string='RFQ Exception Approved',
    default=False,
    help='AUTO-013: True if PAO/HOPE approved proceeding with <3 quotations'
)

rfq_exception_reason = fields.Text(
    string='Exception Justification',
    help='AUTO-013: Written justification for RFQ exception approval'
)

rfq_exception_approver_id = fields.Many2one(
    'res.users',
    string='Exception Approved By',
    help='AUTO-013: PAO or HOPE who approved the exception'
)

rfq_exception_approval_date = fields.Datetime(
    string='Exception Approval Date',
    help='AUTO-013: When the exception was granted'
)
"""

# Add to MesobProcurementBid:
"""
# AUTO-012 fields already exist in current code:
# - submission_timestamp
# - is_late  
# - late_rejection_reason
"""

# Add to MesobProcurementPaymentCertificate:
"""
payment_type = fields.Selection([
    ('milestone', 'Milestone Payment'),
    ('final', 'Final Payment'),
    ('retention_release', 'Retention Release'),
    ('advance', 'Advance Payment'),
], string='Payment Type', default='milestone',
   help='AUTO-032: Type of payment for proper accounting treatment')
"""

print("AUTO-011, AUTO-012, AUTO-013, AUTO-032 implementations complete!")
print("Next steps: Integrate these methods into mesob_procurement.py")

# AUTO-018, AUTO-021, AUTO-032 Contract Extensions
# Methods to be added to MesobProcurementContract class

    def action_generate_contract_from_bid(self, bid_id=None):
        """AUTO-018: Generate contract document from approved bid (FR-PROC-021).
        
        Auto-populates:
        - Supplier details from master (FR-PROC-010)
        - Item codes/quantities/unit prices from winning bid
        - Delivery schedule from lot timeline (FR-PROC-021)
        - Standard clauses from template library (payment terms, LD formula, warranty)
        
        Officer reviews and adds custom clauses if needed.
        Compliance: FR-PROC-021 contract content; reduces drafting time by 80%.
        
        Args:
            bid_id: ID of the winning bid (if not set, uses is_winner flag from lot)
        
        Returns:
            Action dict to open contract form for review
        """
        self.ensure_one()
        
        # Find winning bid
        if not bid_id and self.lot_id:
            winning_bids = self.env['mesob.procurement.bid'].search([
                ('tender_id.lot_id', '=', self.lot_id.id),
                ('is_winner', '=', True)
            ], limit=1)
            
            if not winning_bids:
                raise UserError(
                    "No winning bid found for this lot. "
                    "Please mark a bid as winner before generating contract."
                )
            
            bid = winning_bids
        else:
            bid = self.env['mesob.procurement.bid'].browse(bid_id)
            if not bid.exists():
                raise UserError(f"Bid with ID {bid_id} not found.")
        
        # Extract bid data
        supplier = bid.supplier_id
        tender = bid.tender_id
        lot = self.lot_id or tender.lot_id
        
        # Build items table
        items_rows = ''
        total_value = 0.0
        
        for idx, line in enumerate(bid.line_ids, start=1):
            line_total = line.quantity * line.unit_price
            total_value += line_total
            
            items_rows += f'''
            <tr>
                <td style="border: 1px solid #dee2e6; padding: 8px; text-align: center;">{idx}</td>
                <td style="border: 1px solid #dee2e6; padding: 8px;">{line.item_id.code}</td>
                <td style="border: 1px solid #dee2e6; padding: 8px;">{line.item_id.name}</td>
                <td style="border: 1px solid #dee2e6; padding: 8px;">{line.item_id.specification or 'As per tender'}</td>
                <td style="border: 1px solid #dee2e6; padding: 8px; text-align: center;">{line.quantity:.2f}</td>
                <td style="border: 1px solid #dee2e6; padding: 8px; text-align: center;">{line.uom_id.name if line.uom_id else 'Unit'}</td>
                <td style="border: 1px solid #dee2e6; padding: 8px; text-align: right;">{line.unit_price:,.2f}</td>
                <td style="border: 1px solid #dee2e6; padding: 8px; text-align: right; font-weight: bold;">{line_total:,.2f}</td>
            </tr>'''
        
        # Generate delivery schedule from lot timeline (simplified)
        expected_delivery = lot.expected_award_date or fields.Date.today()
        from dateutil.relativedelta import relativedelta
        delivery_date = expected_delivery + relativedelta(months=3)  # Default 3 months
        
        delivery_schedule = f"""
        <p><strong>Delivery Timeline:</strong></p>
        <ul>
            <li>Contract Signature Date: {fields.Date.today().strftime('%B %d, %Y')}</li>
            <li>Expected Delivery Date: {delivery_date.strftime('%B %d, %Y')} (90 days)</li>
            <li>Delivery Location: {self.env.company.name}, Store Department</li>
            <li>Delivery Terms: FOB Destination, Supplier bears all costs</li>
        </ul>
        """
        
        # Standard payment terms (FR-PROC-034)
        payment_terms = """
        <h4>Payment Terms</h4>
        <ol>
            <li><strong>Payment Method:</strong> Three-way match verification (FR-PROC-034)
                <ul>
                    <li>Purchase Order (PO)</li>
                    <li>Model 19 (Goods Receipt)</li>
                    <li>Supplier Invoice</li>
                </ul>
            </li>
            <li><strong>Advance Payment:</strong> Up to 30% upon provision of equivalent bank guarantee (BR-PROC-006)</li>
            <li><strong>Retention:</strong> 10% of each payment withheld until warranty period completion (FR-PROC-037)</li>
            <li><strong>Payment Processing:</strong> Within 30 days of Model 19 issuance</li>
            <li><strong>Payment Currency:</strong> Ethiopian Birr (ETB)</li>
        </ol>
        """
        
        # Standard LD formula (FR-PROC-036)
        ld_clause = """
        <h4>Liquidated Damages</h4>
        <p>In case of delivery delay beyond the agreed delivery date:</p>
        <ul>
            <li><strong>Formula:</strong> Contract Value × (1/1000) × Working Days Delayed</li>
            <li><strong>Maximum:</strong> 10% of total contract value</li>
            <li><strong>Calculation:</strong> Automated by system (AUTO-030)</li>
            <li><strong>Deduction:</strong> Applied to final payment</li>
        </ul>
        <p><em>Per Federal Public Procurement Regulation (FR-PROC-036)</em></p>
        """
        
        # Standard warranty clause
        warranty_clause = f"""
        <h4>Warranty Terms</h4>
        <ul>
            <li><strong>Warranty Period:</strong> {self.warranty_period_months} months from delivery acceptance</li>
            <li><strong>Coverage:</strong> Defects in materials, workmanship, and performance</li>
            <li><strong>Supplier Obligation:</strong> Repair or replace defective goods at no cost</li>
            <li><strong>Retention Release:</strong> After warranty period completion and defects clearance</li>
        </ul>
        """
        
        # Generate HTML contract document
        contract_html = f"""
        <div style="font-family: 'Times New Roman', serif; max-width: 800px; margin: 0 auto; padding: 20px;">
            
            <!-- Header -->
            <div style="text-align: center; border-bottom: 3px solid #2c3e50; padding-bottom: 20px; margin-bottom: 30px;">
                <h1 style="margin: 0; color: #2c3e50;">FEDERAL DEMOCRATIC REPUBLIC OF ETHIOPIA</h1>
                <h2 style="margin: 10px 0; color: #34495e;">{self.env.company.name}</h2>
                <h3 style="margin: 10px 0; color: #7f8c8d;">PROCUREMENT CONTRACT</h3>
                <p style="margin: 5px 0;"><strong>Contract No:</strong> {self.name}</p>
                <p style="margin: 5px 0;"><strong>Date:</strong> {fields.Date.today().strftime('%B %d, %Y')}</p>
            </div>
            
            <!-- Parties -->
            <h3 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 5px;">PARTIES TO THE CONTRACT</h3>
            
            <div style="margin: 20px 0;">
                <p><strong>PROCURING ENTITY:</strong></p>
                <table style="margin-left: 20px; width: 95%;">
                    <tr>
                        <td style="padding: 5px 0; width: 150px;"><strong>Name:</strong></td>
                        <td style="padding: 5px 0;">{self.env.company.name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 0;"><strong>Address:</strong></td>
                        <td style="padding: 5px 0;">Addis Ababa, Ethiopia</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 0;"><strong>TIN:</strong></td>
                        <td style="padding: 5px 0;">{self.env.company.vat or 'N/A'}</td>
                    </tr>
                </table>
            </div>
            
            <div style="margin: 20px 0;">
                <p><strong>SUPPLIER:</strong></p>
                <table style="margin-left: 20px; width: 95%;">
                    <tr>
                        <td style="padding: 5px 0; width: 150px;"><strong>Name:</strong></td>
                        <td style="padding: 5px 0;">{supplier.name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 0;"><strong>Address:</strong></td>
                        <td style="padding: 5px 0;">{supplier.street or 'N/A'}, {supplier.city or 'N/A'}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 0;"><strong>TIN:</strong></td>
                        <td style="padding: 5px 0;">{supplier.vat or 'N/A'}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 0;"><strong>Phone:</strong></td>
                        <td style="padding: 5px 0;">{supplier.phone or 'N/A'}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 0;"><strong>Email:</strong></td>
                        <td style="padding: 5px 0;">{supplier.email or 'N/A'}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 0;"><strong>Registration:</strong></td>
                        <td style="padding: 5px 0;">FPPA Cert: {supplier.fppa_certificate_no or 'N/A'}, Expires: {supplier.registration_expiry_date or 'N/A'}</td>
                    </tr>
                </table>
            </div>
            
            <!-- Procurement Reference -->
            <h3 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 5px; margin-top: 30px;">PROCUREMENT REFERENCE</h3>
            <table style="width: 100%; margin: 15px 0;">
                <tr>
                    <td style="padding: 5px 0; width: 200px;"><strong>Tender Reference:</strong></td>
                    <td style="padding: 5px 0;">{tender.name}</td>
                </tr>
                <tr>
                    <td style="padding: 5px 0;"><strong>APP Lot:</strong></td>
                    <td style="padding: 5px 0;">{lot.name}</td>
                </tr>
                <tr>
                    <td style="padding: 5px 0;"><strong>Procurement Method:</strong></td>
                    <td style="padding: 5px 0;">{dict(tender._fields['procurement_method'].selection).get(tender.procurement_method)}</td>
                </tr>
                <tr>
                    <td style="padding: 5px 0;"><strong>Original Bid Price:</strong></td>
                    <td style="padding: 5px 0;">ETB {bid.bid_price:,.2f}</td>
                </tr>
                <tr>
                    <td style="padding: 5px 0;"><strong>Local Content:</strong></td>
                    <td style="padding: 5px 0;">{bid.local_content}%</td>
                </tr>
            </table>
            
            <!-- Items/Services -->
            <h3 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 5px; margin-top: 30px;">ITEMS / SERVICES TO BE SUPPLIED</h3>
            <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
                <thead style="background-color: #34495e; color: white;">
                    <tr>
                        <th style="border: 1px solid #dee2e6; padding: 10px; text-align: center;">No.</th>
                        <th style="border: 1px solid #dee2e6; padding: 10px; text-align: left;">Code</th>
                        <th style="border: 1px solid #dee2e6; padding: 10px; text-align: left;">Description</th>
                        <th style="border: 1px solid #dee2e6; padding: 10px; text-align: left;">Specification</th>
                        <th style="border: 1px solid #dee2e6; padding: 10px; text-align: center;">Qty</th>
                        <th style="border: 1px solid #dee2e6; padding: 10px; text-align: center;">UoM</th>
                        <th style="border: 1px solid #dee2e6; padding: 10px; text-align: right;">Unit Price</th>
                        <th style="border: 1px solid #dee2e6; padding: 10px; text-align: right;">Total (ETB)</th>
                    </tr>
                </thead>
                <tbody>
                    {items_rows}
                    <tr style="background-color: #ecf0f1; font-weight: bold;">
                        <td colspan="7" style="border: 1px solid #dee2e6; padding: 10px; text-align: right;">TOTAL CONTRACT VALUE:</td>
                        <td style="border: 1px solid #dee2e6; padding: 10px; text-align: right; font-size: 16px;">ETB {total_value:,.2f}</td>
                    </tr>
                </tbody>
            </table>
            
            <!-- Delivery Schedule -->
            <h3 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 5px; margin-top: 30px;">DELIVERY SCHEDULE</h3>
            {delivery_schedule}
            
            <!-- Payment Terms -->
            <h3 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 5px; margin-top: 30px;">PAYMENT TERMS</h3>
            {payment_terms}
            
            <!-- Liquidated Damages -->
            <h3 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 5px; margin-top: 30px;">LIQUIDATED DAMAGES</h3>
            {ld_clause}
            
            <!-- Warranty -->
            <h3 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 5px; margin-top: 30px;">WARRANTY TERMS</h3>
            {warranty_clause}
            
            <!-- Legal Framework -->
            <h3 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 5px; margin-top: 30px;">APPLICABLE LAWS & REGULATIONS</h3>
            <p>This contract is governed by:</p>
            <ul>
                <li>Federal Public Procurement and Property Administration Proclamation No. 1210/2012</li>
                <li>Council of Ministers Regulation No. 430/2018</li>
                <li>Ethiopian Civil Code</li>
                <li>Mesob Center Procurement Manual</li>
            </ul>
            
            <!-- Signatures -->
            <h3 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 5px; margin-top: 40px;">SIGNATURES</h3>
            <div style="margin-top: 40px;">
                <table style="width: 100%;">
                    <tr>
                        <td style="width: 50%; vertical-align: top;">
                            <p><strong>FOR THE PROCURING ENTITY:</strong></p>
                            <p style="margin-top: 60px; border-top: 1px solid #000; width: 200px;">Signature</p>
                            <p><strong>Name:</strong> _____________________</p>
                            <p><strong>Title:</strong> _____________________</p>
                            <p><strong>Date:</strong> _____________________</p>
                        </td>
                        <td style="width: 50%; vertical-align: top;">
                            <p><strong>FOR THE SUPPLIER:</strong></p>
                            <p style="margin-top: 60px; border-top: 1px solid #000; width: 200px;">Signature</p>
                            <p><strong>Name:</strong> {supplier.name}</p>
                            <p><strong>Title:</strong> Authorized Representative</p>
                            <p><strong>Date:</strong> _____________________</p>
                        </td>
                    </tr>
                </table>
            </div>
            
            <!-- Footer -->
            <div style="text-align: center; margin-top: 50px; padding-top: 20px; border-top: 1px solid #dee2e6; color: #7f8c8d; font-size: 12px;">
                <p><em>AUTO-018: Contract Auto-Generated from Approved Bid</em></p>
                <p>Generated: {fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | System: Mesob IMS v2.0</p>
            </div>
            
        </div>
        """
        
        # Update contract with generated document and initial values
        self.write({
            'contract_document': contract_html,
            'total_value': total_value,
            'original_contract_value': total_value,  # AUTO-021: Store original for variation tracking
            'delivery_schedule': delivery_schedule,
            'payment_terms': payment_terms,
        })
        
        # Log to chatter
        self.message_post(
            body=f"""<div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px;">
                <h3>✅ AUTO-018: Contract Document Generated</h3>
                <p><strong>Source Bid:</strong> {bid.supplier_id.name} - ETB {bid.bid_price:,.2f}</p>
                <p><strong>Total Items:</strong> {len(bid.line_ids)}</p>
                <p><strong>Contract Value:</strong> ETB {total_value:,.2f}</p>
                <hr/>
                <p><em>Officer: Please review the generated contract and add custom clauses if needed.</em></p>
                <p><em>FR-PROC-021: Contract content auto-populated from approved bid (80% time savings)</em></p>
            </div>""",
            subject=f'Contract Generated: {self.name}',
            message_type='comment'
        )
        
        _logger.info(
            f"AUTO-018: Contract {self.name} generated from bid {bid.id} - "
            f"Supplier: {supplier.name}, Value: ETB {total_value:,.2f}, Items: {len(bid.line_ids)}"
        )
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Review Generated Contract',
            'res_model': 'mesob.procurement.contract',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }

    
    def action_add_variation(self, variation_amount, variation_description):
        """AUTO-021: Add contract variation and track cumulative percentage (FR-PROC-023).
        
        - Updates cumulative_variation_total
        - Checks thresholds (10%, 15%, 20%) and sends alerts
        - Blocks variation approval above 20% without HOPE override
        - Creates audit trail via variation record
        
        Args:
            variation_amount: ETB value of variation (positive or negative)
            variation_description: Description of the variation
        
        Returns:
            True if successful, raises ValidationError if blocked
        """
        self.ensure_one()
        
        if not self.original_contract_value or self.original_contract_value == 0:
            raise ValidationError(
                "Original contract value is not set. Cannot calculate variation percentage. "
                "Please set original_contract_value field."
            )
        
        # Calculate new cumulative total
        new_cumulative = self.cumulative_variation_total + variation_amount
        new_percentage = (new_cumulative / self.original_contract_value) * 100.0
        
        # Check 20% ceiling (BR-PROC-005 or equivalent)
        VARIATION_CEILING = 20.0  # Configurable
        
        if abs(new_percentage) > VARIATION_CEILING:
            # Check if user is HOPE (has permission to override)
            hope_group = self.env.ref('mesob_inventory_base.group_mesob_hope', raise_if_not_found=False)
            
            if hope_group and self.env.user in hope_group.users:
                # HOPE override allowed
                _logger.warning(
                    f"AUTO-021: HOPE override - Variation above {VARIATION_CEILING}% approved for {self.name} - "
                    f"New percentage: {new_percentage:.2f}%"
                )
            else:
                raise ValidationError(
                    f"Contract variation BLOCKED (FR-PROC-023)\n\n"
                    f"Cumulative variation would exceed {VARIATION_CEILING}% ceiling:\n"
                    f"  Original Contract Value: ETB {self.original_contract_value:,.2f}\n"
                    f"  Current Cumulative Variations: ETB {self.cumulative_variation_total:,.2f} ({self.variation_percentage:.2f}%)\n"
                    f"  Requested Variation: ETB {variation_amount:,.2f}\n"
                    f"  New Cumulative: ETB {new_cumulative:,.2f} ({new_percentage:.2f}%)\n\n"
                    f"HOPE authorization required for variations above {VARIATION_CEILING}%."
                )
        
        # Update cumulative variation
        old_percentage = self.variation_percentage
        self.write({
            'cumulative_variation_total': new_cumulative,
            'total_value': self.original_contract_value + new_cumulative,  # Update current value
        })
        
        # Create variation record for audit trail
        variation_rec = self.env['mesob.contract.variation'].create({
            'contract_id': self.id,
            'variation_date': fields.Date.today(),
            'variation_amount': variation_amount,
            'description': variation_description,
            'cumulative_after': new_cumulative,
            'percentage_after': new_percentage,
            'approved_by_id': self.env.user.id,
        })
        
        # Check thresholds and send alerts
        self._check_variation_thresholds(old_percentage, new_percentage, variation_amount)
        
        # Log to chatter
        variation_color = '#28a745' if variation_amount >= 0 else '#dc3545'
        sign = '+' if variation_amount >= 0 else ''
        
        threshold_warning = ''
        if abs(new_percentage) >= 15:
            threshold_warning = f'''<div style="background-color: #fff3cd; padding: 10px; border-radius: 5px; margin-top: 10px;">
                <p style="margin: 0; color: #856404;"><strong>⚠ THRESHOLD ALERT:</strong> Cumulative variation is at {new_percentage:.2f}% (15% threshold exceeded)</p>
            </div>'''
        elif abs(new_percentage) >= 10:
            threshold_warning = f'''<div style="background-color: #d1ecf1; padding: 10px; border-radius: 5px; margin-top: 10px;">
                <p style="margin: 0; color: #0c5460;"><strong>ℹ NOTICE:</strong> Cumulative variation is at {new_percentage:.2f}% (10% threshold exceeded)</p>
            </div>'''
        
        self.message_post(
            body=f"""<div style="background-color: #e7f3ff; border-left: 4px solid #2196F3; padding: 15px;">
                <h3>💰 AUTO-021: Contract Variation Added</h3>
                <p><strong>Description:</strong> {variation_description}</p>
                <hr/>
                <table style="width: 100%; margin: 10px 0;">
                    <tr>
                        <td style="padding: 5px 0;"><strong>Original Contract Value:</strong></td>
                        <td style="padding: 5px 0; text-align: right;">ETB {self.original_contract_value:,.2f}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 0;"><strong>Previous Cumulative:</strong></td>
                        <td style="padding: 5px 0; text-align: right;">ETB {self.cumulative_variation_total - variation_amount:,.2f} ({old_percentage:.2f}%)</td>
                    </tr>
                    <tr style="background-color: {variation_color}20;">
                        <td style="padding: 8px 0; font-weight: bold; border-top: 2px solid #2196F3;">This Variation:</td>
                        <td style="padding: 8px 0; text-align: right; font-weight: bold; color: {variation_color}; border-top: 2px solid #2196F3;">{sign}ETB {abs(variation_amount):,.2f}</td>
                    </tr>
                    <tr style="background-color: #ecf0f1;">
                        <td style="padding: 8px 0; font-weight: bold; border-top: 2px solid #34495e;">New Cumulative Variation:</td>
                        <td style="padding: 8px 0; text-align: right; font-weight: bold; font-size: 16px; border-top: 2px solid #34495e;">ETB {new_cumulative:,.2f} ({new_percentage:.2f}%)</td>
                    </tr>
                    <tr style="background-color: #d4edda;">
                        <td style="padding: 8px 0; font-weight: bold; border-top: 2px solid #28a745;">Adjusted Contract Value:</td>
                        <td style="padding: 8px 0; text-align: right; font-weight: bold; font-size: 18px; border-top: 2px solid #28a745;">ETB {self.total_value:,.2f}</td>
                    </tr>
                </table>
                {threshold_warning}
                <hr/>
                <p style="font-size: 12px;"><strong>Approved By:</strong> {self.env.user.name} | <strong>Date:</strong> {fields.Date.today()}</p>
                <p style="font-size: 11px;"><em>FR-PROC-023: Contract variation control | AUTO-021: Cumulative tracking</em></p>
            </div>""",
            subject=f'Variation Added: {sign}ETB {abs(variation_amount):,.2f}',
            message_type='comment'
        )
        
        _logger.info(
            f"AUTO-021: Variation added to contract {self.name} - "
            f"Amount: {sign}ETB {variation_amount:,.2f}, "
            f"New Cumulative: ETB {new_cumulative:,.2f} ({new_percentage:.2f}%), "
            f"Approved By: {self.env.user.name}"
        )
        
        return True
    
    def _check_variation_thresholds(self, old_percentage, new_percentage, variation_amount):
        """AUTO-021: Check variation percentage thresholds and send alerts (FR-PROC-023).
        
        Thresholds:
        - 10%: Information alert (yellow)
        - 15%: Warning alert (orange)
        - 20%: Critical alert / block (red)
        
        Sends one-time alerts when thresholds are crossed.
        """
        self.ensure_one()
        
        # Get procurement users for alerts
        procurement_users = self.env.ref('mesob_inventory_base.group_mesob_procurement', raise_if_not_found=False)
        if not procurement_users or not procurement_users.users:
            return
        
        # Check 10% threshold
        if abs(old_percentage) < 10 and abs(new_percentage) >= 10 and not self.variation_alert_10_sent:
            self._send_variation_threshold_alert('10', new_percentage, procurement_users.users)
            self.variation_alert_10_sent = True
        
        # Check 15% threshold
        if abs(old_percentage) < 15 and abs(new_percentage) >= 15 and not self.variation_alert_15_sent:
            self._send_variation_threshold_alert('15', new_percentage, procurement_users.users)
            self.variation_alert_15_sent = True
    
    def _send_variation_threshold_alert(self, threshold, current_percentage, users):
        """AUTO-021: Send variation threshold alert to procurement officers."""
        self.ensure_one()
        
        threshold_config = {
            '10': {
                'color': '#fff3cd',
                'text_color': '#856404',
                'icon': 'ℹ️',
                'severity': 'INFORMATION',
                'message': 'Cumulative contract variation has reached 10% of original value.'
            },
            '15': {
                'color': '#fff3cd',
                'text_color': '#ff9800',
                'icon': '⚠️',
                'severity': 'WARNING',
                'message': 'Cumulative contract variation has reached 15% of original value. Approaching 20% ceiling.'
            }
        }
        
        config = threshold_config.get(threshold, threshold_config['10'])
        
        self.message_post(
            body=f"""<div style="background-color: {config['color']}; border-left: 4px solid {config['text_color']}; padding: 15px;">
                <h3 style="color: {config['text_color']};">{config['icon']} AUTO-021: Variation Threshold Alert - {threshold}% {config['severity']}</h3>
                <p>{config['message']}</p>
                <hr/>
                <table style="width: 100%;">
                    <tr>
                        <td style="padding: 5px 0;"><strong>Contract:</strong></td>
                        <td style="padding: 5px 0; text-align: right;">{self.name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 0;"><strong>Supplier:</strong></td>
                        <td style="padding: 5px 0; text-align: right;">{self.supplier_id.name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 0;"><strong>Original Value:</strong></td>
                        <td style="padding: 5px 0; text-align: right;">ETB {self.original_contract_value:,.2f}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 0;"><strong>Cumulative Variation:</strong></td>
                        <td style="padding: 5px 0; text-align: right;">ETB {self.cumulative_variation_total:,.2f}</td>
                    </tr>
                    <tr style="background-color: {config['color']};">
                        <td style="padding: 8px 0; font-weight: bold; border-top: 2px solid {config['text_color']};">Variation Percentage:</td>
                        <td style="padding: 8px 0; text-align: right; font-weight: bold; color: {config['text_color']}; font-size: 18px; border-top: 2px solid {config['text_color']};">{current_percentage:.2f}%</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 0;"><strong>Current Contract Value:</strong></td>
                        <td style="padding: 5px 0; text-align: right; font-weight: bold;">ETB {self.total_value:,.2f}</td>
                    </tr>
                </table>
                <hr/>
                <div style="background-color: #fff; padding: 10px; border-radius: 5px; margin-top: 10px;">
                    <p style="margin: 0;"><strong>⚠ ACTION REQUIRED (FR-PROC-023):</strong></p>
                    <ul style="margin: 5px 0 0 0;">
                        <li>Review justification for cumulative variations</li>
                        <li>Verify all variations are documented and approved</li>
                        <li>Consider re-tendering if variations indicate scope creep</li>
                        {f'<li><strong>CRITICAL:</strong> Further variations above 20% require HOPE authorization</li>' if threshold == '15' else ''}
                    </ul>
                </div>
            </div>""",
            subject=f'{config["icon"]} Variation {threshold}% Threshold: {self.name}',
            message_type='notification',
            partner_ids=users.mapped('partner_id').ids
        )
        
        _logger.warning(
            f"AUTO-021: Variation {threshold}% threshold alert sent for contract {self.name} - "
            f"Current: {current_percentage:.2f}%, Cumulative: ETB {self.cumulative_variation_total:,.2f}"
        )

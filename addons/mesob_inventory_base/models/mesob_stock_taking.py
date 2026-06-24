from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class MesobStockTaking(models.Model):
    """Stock Taking event managed by Property Admin Officer (PAO) - Section 4.8.

    Enforces pre-training, logical layout sequencing, pre-numbered sheets,
    and exclusion of storekeepers from the count team (FR-ST-001 through FR-ST-009).
    """

    _name = "mesob.stock.taking"
    _description = "Stock Taking Event"
    _order = "date_start desc, id desc"

    name = fields.Char(
        string="Stock-Take Reference",
        required=True,
        copy=False,
        default="New",
    )
    pao_id = fields.Many2one(
        "res.users",
        string="Property Admin Officer (PAO)",
        required=True,
        default=lambda self: self.env.user,
        help="Supervising officer who manages stock taking (FR-ST-001).",
    )
    date_start = fields.Date(
        string="Start Date",
        required=True,
        default=fields.Date.today,
    )
    date_end = fields.Date(string="End Date")
    instructions = fields.Text(
        string="Stock-Taking Instructions",
        required=True,
        help="Instructions issued by PAO for the counting teams.",
    )
    is_pre_training_done = fields.Boolean(
        string="Pre-Stocktaking Training Performed",
        default=False,
        help="Must be checked to confirm team training was completed (FR-ST-001).",
    )
    team_member_ids = fields.Many2many(
        "res.users",
        "mesob_stock_taking_team_users_rel",
        "stock_taking_id",
        "user_id",
        string="Stock-Taking Team",
        help="Team members conducting the count. Storekeepers are strictly excluded (FR-ST-009).",
    )
    guide_storekeeper_ids = fields.Many2many(
        "res.users",
        "mesob_stock_taking_guides_users_rel",
        "stock_taking_id",
        "user_id",
        string="Storekeeper Guides / Witnesses",
        help="Storekeepers may act as guides or witnesses only (FR-ST-009).",
    )
    line_ids = fields.One2many(
        "mesob.stock.taking.line",
        "stock_taking_id",
        string="Stock taking Sheets",
    )
    
    # AUTO-057: Sheet Issuance & Return Tracking
    sheet_issuance_ids = fields.One2many(
        "mesob.stock.taking.sheet.issuance",
        "stock_taking_id",
        string="Sheet Issuances",
        help="AUTO-057: Track which sheets were issued to which recorder (FR-ST-004)"
    )
    
    total_sheets_issued = fields.Integer(
        string="Total Sheets Issued",
        compute="_compute_sheet_stats",
        help="AUTO-057: Total count sheets distributed"
    )
    
    total_sheets_returned = fields.Integer(
        string="Total Sheets Returned", 
        compute="_compute_sheet_stats",
        help="AUTO-057: Count sheets returned by recorders"
    )
    
    unreturned_sheets = fields.Integer(
        string="Unreturned Sheets",
        compute="_compute_sheet_stats",
        help="AUTO-057: Sheets not yet returned (flagged)"
    )
    
    # AUTO-058: Variance Statistics
    total_items_counted = fields.Integer(
        string="Items Counted",
        compute="_compute_variance_stats"
    )
    
    items_with_discrepancy = fields.Integer(
        string="Items with Discrepancy",
        compute="_compute_variance_stats"
    )
    
    accuracy_percentage = fields.Float(
        string="Accuracy %",
        compute="_compute_variance_stats",
        help="AUTO-058: (Items without discrepancy / Total items) × 100"
    )
    
    critical_discrepancies = fields.Integer(
        string="Critical Discrepancies (>10%)",
        compute="_compute_variance_stats"
    )
    
    medium_discrepancies = fields.Integer(
        string="Medium Discrepancies (5-10%)",
        compute="_compute_variance_stats"
    )
    
    low_discrepancies = fields.Integer(
        string="Low Discrepancies (2-5%)",
        compute="_compute_variance_stats"
    )
    
    # ADVANCED: Real-Time Progress Tracking
    total_items_in_sheets = fields.Integer(
        string="Total Items",
        compute="_compute_progress_stats",
        help="ADVANCED: Total items in count sheets"
    )
    
    items_counted_progress = fields.Integer(
        string="Items Counted",
        compute="_compute_progress_stats",
        help="ADVANCED: Number of items counted so far"
    )
    
    counting_progress_percentage = fields.Float(
        string="Progress %",
        compute="_compute_progress_stats",
        help="ADVANCED: Real-time counting progress percentage"
    )
    
    estimated_completion_time = fields.Char(
        string="Est. Completion",
        compute="_compute_progress_stats",
        help="ADVANCED: Estimated time to complete based on current pace"
    )
    
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("ongoing", "Ongoing / Counting"),
            ("completed", "Completed & Reconciled"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        required=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("mesob.stock.taking") or "New"
        return super().create(vals_list)

    @api.constrains("team_member_ids", "guide_storekeeper_ids")
    def _check_storekeeper_exclusion(self):
        """Enforces that storekeepers are strictly excluded from count teams (FR-ST-009 / BR-ST-001)."""
        for rec in self:
            storekeeper_group = self.env.ref("mesob_inventory_base.group_mesob_storekeeper")
            for member in rec.team_member_ids:
                if storekeeper_group in member.group_ids:
                    raise ValidationError(
                        f"Validation Block: User '{member.name}' is a Storekeeper and "
                        f"MUST NOT be a member of the stock-taking counting team! (FR-ST-009)"
                    )
    
    # AUTO-057: Sheet Issuance Tracking Computations
    @api.depends('sheet_issuance_ids', 'sheet_issuance_ids.is_returned')
    def _compute_sheet_stats(self):
        """AUTO-057: Compute sheet issuance statistics"""
        for rec in self:
            rec.total_sheets_issued = len(rec.sheet_issuance_ids)
            rec.total_sheets_returned = len(rec.sheet_issuance_ids.filtered(lambda s: s.is_returned))
            rec.unreturned_sheets = rec.total_sheets_issued - rec.total_sheets_returned
    
    # AUTO-058: Variance Statistics Computations
    @api.depends('line_ids', 'line_ids.is_counted', 'line_ids.discrepancy', 'line_ids.recorded_qty')
    def _compute_variance_stats(self):
        """AUTO-058: Auto-calculate variance statistics and accuracy score"""
        for rec in self:
            counted_lines = rec.line_ids.filtered(lambda l: l.is_counted)
            rec.total_items_counted = len(counted_lines)
            
            discrepancy_lines = counted_lines.filtered(lambda l: abs(l.discrepancy) > 0.01)
            rec.items_with_discrepancy = len(discrepancy_lines)
            
            # Calculate accuracy percentage
            if rec.total_items_counted > 0:
                accurate_items = rec.total_items_counted - rec.items_with_discrepancy
                rec.accuracy_percentage = (accurate_items / rec.total_items_counted) * 100
            else:
                rec.accuracy_percentage = 0.0
            
            # Categorize discrepancies by severity
            rec.critical_discrepancies = 0
            rec.medium_discrepancies = 0
            rec.low_discrepancies = 0
            
            for line in discrepancy_lines:
                if line.recorded_qty > 0:
                    variance_pct = abs(line.discrepancy / line.recorded_qty) * 100
                    if variance_pct > 10:
                        rec.critical_discrepancies += 1
                    elif variance_pct > 5:
                        rec.medium_discrepancies += 1
                    elif variance_pct > 2:
                        rec.low_discrepancies += 1
                else:
                    # Recorded qty is 0 but physical count exists = critical
                    if abs(line.discrepancy) > 0:
                        rec.critical_discrepancies += 1
    
    # ADVANCED: Real-Time Progress Dashboard
    @api.depends('line_ids', 'line_ids.is_counted', 'date_start')
    def _compute_progress_stats(self):
        """ADVANCED: Real-time counting progress tracking for dashboard"""
        from datetime import datetime, timedelta
        
        for rec in self:
            rec.total_items_in_sheets = len(rec.line_ids)
            rec.items_counted_progress = len(rec.line_ids.filtered(lambda l: l.is_counted))
            
            if rec.total_items_in_sheets > 0:
                rec.counting_progress_percentage = (rec.items_counted_progress / rec.total_items_in_sheets) * 100
            else:
                rec.counting_progress_percentage = 0.0
            
            # Estimate completion time based on current pace
            if rec.state == 'ongoing' and rec.items_counted_progress > 0:
                elapsed_time = (fields.Datetime.now() - rec.create_date).total_seconds() / 3600  # hours
                items_per_hour = rec.items_counted_progress / elapsed_time if elapsed_time > 0 else 0
                
                remaining_items = rec.total_items_in_sheets - rec.items_counted_progress
                if items_per_hour > 0:
                    remaining_hours = remaining_items / items_per_hour
                    est_completion = datetime.now() + timedelta(hours=remaining_hours)
                    rec.estimated_completion_time = est_completion.strftime('%Y-%m-%d %H:%M')
                else:
                    rec.estimated_completion_time = "Calculating..."
            else:
                rec.estimated_completion_time = "N/A"

    def action_start_stock_taking(self):
        """AUTO-056: Pre-Generate Count Sheets in Logical Storage Order (FR-ST-002).
        
        Initiates the stock-taking event with:
        - Pre-generated sheets matching physical storage layout
        - Serial numbering for accountability (FR-ST-003)
        - System book balance pre-populated
        - Logical grouping by classification and location
        """
        for rec in self:
            if rec.state != "draft":
                raise UserError("Stock-taking has already been started.")
            if not rec.is_pre_training_done:
                raise UserError("You must perform and record pre-stocktaking training before starting (FR-ST-001).")
            if not rec.team_member_ids:
                raise UserError("Please assign at least one team member to conduct the counts.")

            # Clear any existing lines
            rec.line_ids.unlink()

            # AUTO-056: Pre-generate sheets in logical order matching classifications & storage layout (FR-ST-002)
            items = self.env["mesob.inventory.item"].search([], order="classification_id, sub_classification_id, item_code")
            serial_num = 1
            
            StockMixin = self.env['mesob.stock.movement.mixin']
            
            for item in items:
                # AUTO-056: Fetch real-time system stock balance from Bin Card
                current_stock = StockMixin.get_current_stock_level(item.id, location='Main Store')
                
                self.env["mesob.stock.taking.line"].create({
                    "stock_taking_id": rec.id,
                    "serial_number": serial_num,
                    "item_id": item.id,
                    "recorded_qty": current_stock,
                    "location_label": item.sub_classification_id.name or "Store A",
                })
                serial_num += 1

            rec.state = "ongoing"
            
            # AUTO-056: Notify team members
            rec.message_post(
                body=f"""<div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px;">
                    <h3>AUTO-056: Stock Taking Initiated</h3>
                    <p><strong>Reference:</strong> {rec.name}</p>
                    <p><strong>Start Date:</strong> {rec.date_start}</p>
                    <p><strong>PAO:</strong> {rec.pao_id.name}</p>
                    <p><strong>Team Members:</strong> {', '.join(rec.team_member_ids.mapped('name'))}</p>
                    <p><strong>Count Sheets:</strong> {len(rec.line_ids)} pre-numbered sheets generated in logical storage order</p>
                    <hr/>
                    <p><em>FR-ST-002: Count sheets are pre-generated in logical storage sequence.</em></p>
                    <p><em>FR-ST-003: All sheets are pre-numbered for accountability.</em></p>
                </div>""",
                subject=f'Stock Taking Started: {rec.name}',
                message_type='notification',
                partner_ids=rec.team_member_ids.mapped('partner_id').ids
            )
            
            _logger.info(
                f"AUTO-056: Stock taking {rec.name} started - "
                f"{len(rec.line_ids)} sheets generated, "
                f"Team: {len(rec.team_member_ids)} members"
            )
        
        return True
    
    def action_export_to_excel(self):
        """ADVANCED: Export count sheets to Excel for offline counting.
        
        Generates Excel file with:
        - Pre-formatted count sheets
        - Barcode-ready format
        - Formulas for variance calculation
        - Print-ready formatting
        """
        self.ensure_one()
        
        try:
            import xlsxwriter
            from io import BytesIO
            import base64
        except ImportError:
            raise UserError("Excel export requires xlsxwriter library. Please install: pip install xlsxwriter")
        
        # Create Excel file in memory
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        
        # Define formats
        header_format = workbook.add_format({
            'bold': True,
            'font_size': 14,
            'bg_color': '#4472C4',
            'font_color': 'white',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1
        })
        
        title_format = workbook.add_format({
            'bold': True,
            'font_size': 16,
            'align': 'center'
        })
        
        cell_format = workbook.add_format({
            'border': 1,
            'align': 'left',
            'valign': 'vcenter'
        })
        
        number_format = workbook.add_format({
            'border': 1,
            'align': 'right',
            'valign': 'vcenter',
            'num_format': '#,##0.00'
        })
        
        # Create worksheet
        worksheet = workbook.add_worksheet('Stock Taking Sheet')
        worksheet.set_column('A:A', 12)  # Serial No
        worksheet.set_column('B:B', 20)  # Item Code
        worksheet.set_column('C:C', 40)  # Item Name
        worksheet.set_column('D:D', 20)  # Location
        worksheet.set_column('E:E', 15)  # System Qty
        worksheet.set_column('F:F', 15)  # Physical Qty
        worksheet.set_column('G:G', 15)  # Variance
        worksheet.set_column('H:H', 12)  # Unit
        
        # Title
        worksheet.merge_range('A1:H1', f'STOCK TAKING EVENT: {self.name}', title_format)
        worksheet.merge_range('A2:H2', f'Date: {self.date_start} | PAO: {self.pao_id.name}', cell_format)
        
        # Headers
        row = 3
        headers = ['Serial #', 'Item Code', 'Item Name', 'Location', 'System Qty', 'Physical Count', 'Variance', 'Unit']
        for col, header in enumerate(headers):
            worksheet.write(row, col, header, header_format)
        
        # Data rows
        row = 4
        for line in self.line_ids.sorted('serial_number'):
            worksheet.write(row, 0, line.serial_number, cell_format)
            worksheet.write(row, 1, line.item_code or '', cell_format)
            worksheet.write(row, 2, line.item_id.name or '', cell_format)
            worksheet.write(row, 3, line.location_label or '', cell_format)
            worksheet.write(row, 4, line.recorded_qty, number_format)
            worksheet.write(row, 5, '', number_format)  # Empty for physical count
            # Variance formula
            worksheet.write_formula(row, 6, f'=F{row+1}-E{row+1}', number_format)
            worksheet.write(row, 7, line.item_id.uom_id.name or 'Unit', cell_format)
            row += 1
        
        # Close workbook
        workbook.close()
        
        # Get file data
        output.seek(0)
        file_data = base64.b64encode(output.read())
        output.close()
        
        # Create attachment
        filename = f'Stock_Taking_{self.name.replace("/", "_")}_{fields.Date.today()}.xlsx'
        attachment = self.env['ir.attachment'].create({
            'name': filename,
            'datas': file_data,
            'res_model': self._name,
            'res_id': self.id,
            'type': 'binary',
        })
        
        self.message_post(
            body=f"""<div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px;">
                <h3>📊 Excel Export Complete</h3>
                <p><strong>File:</strong> {filename}</p>
                <p><strong>Sheets:</strong> {len(self.line_ids)} items exported</p>
                <p><em>Download the file for offline counting, then import results back into system.</em></p>
            </div>""",
            subject='Stock Taking Excel Export',
            attachment_ids=[attachment.id]
        )
        
        _logger.info(f"ADVANCED: Exported stock taking {self.name} to Excel - {len(self.line_ids)} items")
        
        # Return download action
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'self',
        }

    def action_complete_and_reconcile(self):
        """AUTO-057/058/059: Auto-Discrepancy Detection, Red-Ink Bin Card Posting, and Investigation Alerts.
        
        AUTO-057: Auto-detect and flag discrepancies (FR-ST-006)
        AUTO-058: Auto-post red-ink adjustments to Bin Cards (FR-ST-008)
        AUTO-059: Trigger investigation alerts for material discrepancies
        
        Finalizes count sheet and posts red-ink Equivalent markers on Bin Cards (FR-ST-008).
        """
        for rec in self:
            if rec.state != "ongoing":
                raise UserError("Only ongoing stock-taking events can be finalized.")

            uncounted = rec.line_ids.filtered(lambda l: not l.is_counted)
            if uncounted:
                raise UserError(
                    f"Please complete counting for all items. {len(uncounted)} lines are still uncounted."
                )

            # AUTO-057: Detect and categorize discrepancies
            discrepancy_lines = rec.line_ids.filtered(lambda l: abs(l.discrepancy) > 0.01)
            critical_discrepancies = []
            total_discrepancy_value = 0.0
            
            # Reconcile counts and update red ink indicators
            for line in rec.line_ids:
                if abs(line.discrepancy) > 0.01:
                    # AUTO-058: Record adjustment on the Bin Card with red-ink marker
                    sub_class = line.item_id.sub_classification_id
                    if sub_class:
                        bin_card = self.env["mesob.bin.card"].create({
                            "major_classification_id": sub_class.major_classification_id.id,
                            "sub_classification_id": sub_class.id,
                            "date": fields.Date.today(),
                            "reference": f"Stock-Take Adj ({rec.name})",
                            "quantity_received": line.physical_qty if line.discrepancy > 0 else 0.0,
                            "quantity_distributed": abs(line.discrepancy) if line.discrepancy < 0 else 0.0,
                            "description": f"RED INK AUDIT CHECK: {line.discrepancy_reason or 'No reason provided'} | Physical: {line.physical_qty}, Book: {line.recorded_qty}",
                            "uom_id": line.item_id.uom_id.id,
                            "transaction_type": "adjustment",
                        })
                        
                        _logger.info(
                            f"AUTO-058: Red-ink adjustment posted - "
                            f"Item: {line.item_id.item_code}, "
                            f"Discrepancy: {line.discrepancy}, "
                            f"Bin Card: {bin_card.id}"
                        )
                    
                    # AUTO-057/059: Check for material discrepancies requiring investigation
                    discrepancy_pct = (abs(line.discrepancy) / line.recorded_qty * 100) if line.recorded_qty > 0 else 100.0
                    
                    # Get item valuation for value-based threshold
                    valuation = self.env['mesob.stock.movement.mixin'].get_item_valuation(line.item_id.id)
                    discrepancy_value = abs(line.discrepancy) * valuation.get('average_cost', 0.0)
                    total_discrepancy_value += discrepancy_value
                    
                    # Material discrepancy thresholds (BR-ST-002 implied):
                    # 1. > 5% quantity variance
                    # 2. > ETB 10,000 value variance
                    # 3. Any theft/pilferage indication
                    is_material = (
                        discrepancy_pct > 5.0 or
                        discrepancy_value > 10000.0 or
                        line.discrepancy_reason == 'theft'
                    )
                    
                    if is_material:
                        critical_discrepancies.append({
                            'line': line,
                            'percentage': discrepancy_pct,
                            'value': discrepancy_value,
                        })

            rec.write({
                "state": "completed",
                "date_end": fields.Date.today(),
            })
            
            # AUTO-059: Send investigation alerts for material discrepancies
            if critical_discrepancies:
                rec._send_investigation_alerts(critical_discrepancies, total_discrepancy_value)
                rec._create_investigations(critical_discrepancies)
            
            # AUTO-057: Send completion summary
            rec.message_post(
                body=f"""<div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px;">
                    <h3>AUTO-057/058: Stock Taking Completed</h3>
                    <p><strong>Reference:</strong> {rec.name}</p>
                    <p><strong>Completion Date:</strong> {rec.date_end}</p>
                    <p><strong>Total Items Counted:</strong> {len(rec.line_ids)}</p>
                    <p><strong>Discrepancies Found:</strong> {len(discrepancy_lines)} items</p>
                    <p><strong>Total Discrepancy Value:</strong> ETB {total_discrepancy_value:,.2f}</p>
                    <p><strong>Critical Discrepancies:</strong> {len(critical_discrepancies)} requiring investigation</p>
                    <hr/>
                    <p><em>AUTO-058: Red-ink adjustments posted to Bin Cards (FR-ST-008)</em></p>
                    <p><em>AUTO-057: Discrepancy analysis completed (FR-ST-006)</em></p>
                    {'<p style="color: #dc3545;"><strong>⚠ AUTO-059: Investigation alerts sent to PAO</strong></p>' if critical_discrepancies else ''}
                </div>""",
                subject=f'Stock Taking Completed: {rec.name}',
                message_type='comment'
            )
            
            _logger.info(
                f"AUTO-057/058: Stock taking {rec.name} completed - "
                f"Discrepancies: {len(discrepancy_lines)}, "
                f"Critical: {len(critical_discrepancies)}, "
                f"Total Value: ETB {total_discrepancy_value:,.2f}"
            )
        
        return True
    
    def _send_investigation_alerts(self, critical_discrepancies, total_value):
        """AUTO-059: Investigation Alerts for Material Discrepancies.
        
        Sends alerts to PAO and relevant authorities when material discrepancies are detected.
        Includes detailed breakdown and recommended actions.
        
        Compliance: FR-ST-006, FR-ST-007 (implied investigation requirement)
        """
        self.ensure_one()
        
        # Build critical discrepancy summary
        discrepancy_html = '<table style="width: 100%; border-collapse: collapse; margin-top: 10px;">'
        discrepancy_html += '''
            <thead>
                <tr style="background-color: #dc3545; color: white;">
                    <th style="padding: 10px; text-align: left;">Item Code</th>
                    <th style="padding: 10px; text-align: right;">Book Qty</th>
                    <th style="padding: 10px; text-align: right;">Physical Qty</th>
                    <th style="padding: 10px; text-align: right;">Variance</th>
                    <th style="padding: 10px; text-align: right;">%</th>
                    <th style="padding: 10px; text-align: right;">Value</th>
                    <th style="padding: 10px; text-align: left;">Reason</th>
                </tr>
            </thead>
            <tbody>
        '''
        
        for disc in critical_discrepancies[:20]:  # Show top 20
            line = disc['line']
            discrepancy_html += f'''
                <tr style="background-color: {'#fff3cd' if disc['percentage'] > 10 else '#f8d7da'};">
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">{line.item_code}</td>
                    <td style="padding: 8px; text-align: right; border-bottom: 1px solid #ddd;">{line.recorded_qty:,.2f}</td>
                    <td style="padding: 8px; text-align: right; border-bottom: 1px solid #ddd;">{line.physical_qty:,.2f}</td>
                    <td style="padding: 8px; text-align: right; border-bottom: 1px solid #ddd; font-weight: bold; color: {'#dc3545' if line.discrepancy < 0 else '#28a745'};">{line.discrepancy:+,.2f}</td>
                    <td style="padding: 8px; text-align: right; border-bottom: 1px solid #ddd;">{disc['percentage']:.1f}%</td>
                    <td style="padding: 8px; text-align: right; border-bottom: 1px solid #ddd;">ETB {disc['value']:,.2f}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">{dict(line._fields['discrepancy_reason'].selection).get(line.discrepancy_reason, 'Not specified')}</td>
                </tr>
            '''
        
        if len(critical_discrepancies) > 20:
            discrepancy_html += f'''
                <tr>
                    <td colspan="7" style="padding: 10px; text-align: center; font-style: italic; background-color: #e7f3ff;">
                        ...and {len(critical_discrepancies) - 20} more critical discrepancies
                    </td>
                </tr>
            '''
        
        discrepancy_html += '</tbody></table>'
        
        # Determine severity level
        if total_value > 100000 or any(d['line'].discrepancy_reason == 'theft' for d in critical_discrepancies):
            severity = 'CRITICAL'
            severity_color = '#dc3545'
        elif total_value > 50000:
            severity = 'HIGH'
            severity_color = '#fd7e14'
        else:
            severity = 'MEDIUM'
            severity_color = '#ffc107'
        
        # Send alert to PAO
        pao_users = self.env.ref('mesob_inventory_base.group_mesob_pao', raise_if_not_found=False)
        if pao_users and pao_users.users:
            self.message_post(
                body=f"""<div style="background-color: #f8d7da; border-left: 4px solid #dc3545; padding: 15px;">
                    <h2 style="color: {severity_color}; margin-top: 0;">🚨 AUTO-059: MATERIAL DISCREPANCY ALERT</h2>
                    <div style="background-color: {severity_color}; color: white; padding: 10px; margin-bottom: 15px; text-align: center; font-size: 18px; font-weight: bold;">
                        SEVERITY: {severity}
                    </div>
                    
                    <h3>Stock Taking Event</h3>
                    <table style="width: 100%; margin-bottom: 15px;">
                        <tr>
                            <td style="padding: 5px; font-weight: bold; width: 200px;">Reference:</td>
                            <td style="padding: 5px;">{self.name}</td>
                        </tr>
                        <tr>
                            <td style="padding: 5px; font-weight: bold;">Completion Date:</td>
                            <td style="padding: 5px;">{self.date_end}</td>
                        </tr>
                        <tr>
                            <td style="padding: 5px; font-weight: bold;">PAO:</td>
                            <td style="padding: 5px;">{self.pao_id.name}</td>
                        </tr>
                    </table>
                    
                    <h3>Discrepancy Summary</h3>
                    <table style="width: 100%; background-color: #fff3cd; padding: 10px; margin-bottom: 15px;">
                        <tr>
                            <td style="padding: 5px; font-weight: bold;">Total Items with Discrepancies:</td>
                            <td style="padding: 5px; text-align: right;">{len(self.line_ids.filtered(lambda l: abs(l.discrepancy) > 0.01))}</td>
                        </tr>
                        <tr>
                            <td style="padding: 5px; font-weight: bold;">Material Discrepancies (Critical):</td>
                            <td style="padding: 5px; text-align: right; color: #dc3545; font-size: 16px; font-weight: bold;">{len(critical_discrepancies)}</td>
                        </tr>
                        <tr>
                            <td style="padding: 5px; font-weight: bold;">Total Discrepancy Value:</td>
                            <td style="padding: 5px; text-align: right; color: #dc3545; font-size: 16px; font-weight: bold;">ETB {total_value:,.2f}</td>
                        </tr>
                    </table>
                    
                    <h3>Critical Discrepancies Requiring Investigation</h3>
                    {discrepancy_html}
                    
                    <div style="background-color: #e7f3ff; padding: 15px; margin-top: 20px; border-radius: 5px;">
                        <h4 style="margin-top: 0;">⚠ REQUIRED ACTIONS (FR-ST-007)</h4>
                        <ol style="margin: 10px 0;">
                            <li><strong>Immediate Investigation:</strong> PAO must investigate all material discrepancies</li>
                            <li><strong>Document Review:</strong> Review bin cards, stock record cards, and transaction history</li>
                            <li><strong>Team Interview:</strong> Interview storekeepers and recent transaction parties</li>
                            <li><strong>Physical Verification:</strong> Re-verify physical counts for high-value discrepancies</li>
                            <li><strong>Report Preparation:</strong> Prepare detailed investigation report for management</li>
                            <li><strong>Corrective Action:</strong> Implement controls to prevent recurrence</li>
                        </ol>
                        <p style="margin: 10px 0 0 0;"><em>Material discrepancy thresholds: >5% quantity variance OR >ETB 10,000 value OR theft indication</em></p>
                    </div>
                    
                    <p style="margin-top: 20px;"><a href="/web#id={self.id}&model=mesob.stock.taking&view_type=form" 
                       style="background-color: #dc3545; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                       View Stock Taking Event →
                    </a></p>
                </div>""",
                subject=f'🚨 URGENT: Material Discrepancy Alert - {self.name}',
                message_type='notification',
                partner_ids=pao_users.users.mapped('partner_id').ids
            )
            
            _logger.warning(
                f"AUTO-059: Material discrepancy alert sent - "
                f"Stock Taking: {self.name}, "
                f"Critical Items: {len(critical_discrepancies)}, "
                f"Total Value: ETB {total_value:,.2f}, "
                f"Severity: {severity}"
            )

    # ── Role-Based Access Control (UI Level) ────────────────────────

    @api.model
    def get_view(self, view_id=None, view_type="form", **options):
        """Apply role-based UI controls for Stock Taking.
        
        Both PAO and Stock Clerk can create stock taking events.
        PAO supervises, Stock Clerk conducts counts.
        """
        result = super(MesobStockTaking, self).get_view(view_id, view_type, **options)
        
        # Import lxml for XML manipulation
        from lxml import etree
        
        # Check user roles
        is_pao = self.env.user.has_group("mesob_inventory_base.group_mesob_pao")
        is_stock_clerk = self.env.user.has_group("mesob_inventory_base.group_mesob_stock_clerk")
        
        # Both roles have full access - no restrictions needed currently
        # This method is here for future enhancements if needed
        # (e.g., state-based field visibility based on role)
        
        return result


class MesobStockTakingLine(models.Model):
    """Pre-numbered count sheet lines - FR-ST-002/006."""

    _name = "mesob.stock.taking.line"
    _description = "Stock Taking count Line"
    _order = "serial_number asc"

    stock_taking_id = fields.Many2one(
        "mesob.stock.taking",
        string="Stock-Taking Event",
        required=True,
        ondelete="cascade",
    )
    serial_number = fields.Integer(string="Sheet Serial No.", required=True)
    item_id = fields.Many2one("mesob.inventory.item", string="Catalogued Item", required=True)
    item_code = fields.Char(related="item_id.item_code", string="Item Code", readonly=True)
    location_label = fields.Char(string="Storage Location / Shelf")
    
    recorded_qty = fields.Float(string="System Book Balance", readonly=True)
    physical_qty = fields.Float(string="Physical Count", default=0.0)
    discrepancy = fields.Float(
        string="Discrepancy (Qty)",
        compute="_compute_discrepancy",
        store=True,
    )
    is_counted = fields.Boolean(
        string="Counted (Sticker Attached)",
        default=False,
        help="Colored-sticker counting marker is placed (FR-ST-005).",
    )
    discrepancy_reason = fields.Selection(
        [
            ("posting_error", "Posting Error - Incorrect Record"),
            ("counting_error", "Counting Error - Recount Needed"),
            ("damaged", "Damaged Items"),
            ("shortage", "Unexplained Shortage / Pilferage"),
            ("overage", "Unrecorded Overage"),
            ("theft", "Theft Suspected"),
            ("expired", "Expired / Obsolete"),
        ],
        string="Reason for Discrepancy",
        help="AUTO-059: PAO investigation reason (FR-ST-007)"
    )
    corrective_action = fields.Text(
        string="Corrective Action",
        help="AUTO-059: Documented action by PAO (FR-ST-007)"
    )
    
    # AUTO-058: Variance Classification
    variance_percentage = fields.Float(
        string="Variance %",
        compute="_compute_variance_classification",
        store=True,
        help="AUTO-058: (Discrepancy / Recorded) × 100"
    )
    
    variance_severity = fields.Selection([
        ('none', 'No Variance'),
        ('low', 'Low (2-5%)'),
        ('medium', 'Medium (5-10%)'),
        ('critical', 'Critical (>10%)'),
    ], string="Severity", compute="_compute_variance_classification", store=True,
       help="AUTO-058: Auto-categorized severity level")
    
    # ADVANCED: Value-based severity
    discrepancy_value = fields.Float(
        string="Discrepancy Value (ETB)",
        compute="_compute_variance_classification",
        store=True,
        help="ADVANCED: Financial impact of discrepancy"
    )
    
    value_severity = fields.Selection([
        ('low', 'Low (<ETB 1,000)'),
        ('medium', 'Medium (ETB 1,000-10,000)'),
        ('high', 'High (ETB 10,000-50,000)'),
        ('critical', 'Critical (>ETB 50,000)'),
    ], string="Value Severity", compute="_compute_variance_classification", store=True,
       help="ADVANCED: Severity based on financial value")
    
    combined_severity_score = fields.Integer(
        string="Risk Score",
        compute="_compute_variance_classification",
        store=True,
        help="ADVANCED: Combined risk score (0-100) considering both % and value"
    )
    
    requires_investigation = fields.Boolean(
        string="Requires Investigation",
        compute="_compute_variance_classification",
        store=True,
        help="AUTO-059: Flagged if variance > 2% tolerance or value > ETB 10,000"
    )
    
    investigation_status = fields.Selection([
        ('pending', 'Pending Investigation'),
        ('in_progress', 'Under Investigation'),
        ('resolved', 'Resolved'),
    ], string="Investigation Status", default='pending',
       help="AUTO-059: PAO investigation workflow status")
    
    investigated_by_id = fields.Many2one(
        'res.users',
        string="Investigated By",
        help="AUTO-059: PAO who investigated the discrepancy"
    )
    
    investigation_date = fields.Date(
        string="Investigation Date",
        help="AUTO-059: Date of PAO investigation"
    )
    notes = fields.Text(string="Witness/Team Notes")

    @api.depends("recorded_qty", "physical_qty")
    def _compute_discrepancy(self):
        for line in self:
            line.discrepancy = line.physical_qty - line.recorded_qty
    
    # AUTO-058/059: Variance Classification and Investigation Flagging
    @api.depends('discrepancy', 'recorded_qty', 'item_id')
    def _compute_variance_classification(self):
        """AUTO-058: Auto-calculate variance % and severity; AUTO-059: Flag for investigation
        
        ADVANCED: Now includes value-based severity for smarter prioritization!
        """
        for line in self:
            # Calculate percentage variance
            if line.recorded_qty > 0:
                line.variance_percentage = abs(line.discrepancy / line.recorded_qty) * 100
            else:
                # If recorded is 0 but physical count exists, treat as critical
                line.variance_percentage = 100.0 if abs(line.discrepancy) > 0 else 0.0
            
            # ADVANCED: Calculate financial impact (discrepancy value in ETB)
            item_cost = 0.0
            if line.item_id:
                # Get average cost from valuation
                valuation = self.env['mesob.stock.movement.mixin'].get_item_valuation(line.item_id.id)
                item_cost = valuation.get('average_cost', 0.0)
            
            line.discrepancy_value = abs(line.discrepancy) * item_cost
            
            # Calculate percentage severity score (0-40 points)
            if line.variance_percentage == 0:
                pct_score = 0
            elif line.variance_percentage > 10:
                pct_score = 40
            elif line.variance_percentage > 5:
                pct_score = 30
            elif line.variance_percentage > 2:
                pct_score = 20
            else:
                pct_score = 10
            
            # Calculate value severity score (0-60 points)
            if line.discrepancy_value > 50000:
                value_score = 60
                line.value_severity = 'critical'
            elif line.discrepancy_value > 10000:
                value_score = 45
                line.value_severity = 'high'
            elif line.discrepancy_value > 1000:
                value_score = 30
                line.value_severity = 'medium'
            else:
                value_score = 10
                line.value_severity = 'low'
            
            # Combined risk score (0-100)
            line.combined_severity_score = min(pct_score + value_score, 100)
            
            # AUTO-058: Categorize percentage-based severity
            if line.variance_percentage == 0:
                line.variance_severity = 'none'
            elif line.variance_percentage <= 5:
                line.variance_severity = 'low'
            elif line.variance_percentage <= 10:
                line.variance_severity = 'medium'
            else:
                line.variance_severity = 'critical'
            
            # AUTO-059: Flag for investigation based on EITHER percentage OR value
            # Material discrepancy if: >2% variance OR >ETB 10,000 value OR risk score >50
            line.requires_investigation = (
                line.variance_percentage > 2.0 or 
                line.discrepancy_value > 10000 or
                line.combined_severity_score > 50
            )

    @api.onchange("physical_qty")
    def _onchange_physical_qty(self):
        """Auto-mark counted with sticker upon physical qty entry (FR-ST-005)."""
        if self.physical_qty > 0.0 or self.is_counted:
            self.is_counted = True
    
    # AUTO-059: Discrepancy Investigation Actions
    def action_investigate(self):
        """AUTO-059: Start PAO investigation workflow"""
        self.ensure_one()
        self.write({
            'investigation_status': 'in_progress',
            'investigated_by_id': self.env.user.id,
            'investigation_date': fields.Date.today()
        })
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Investigate Discrepancy',
            'res_model': 'mesob.stock.taking.line',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_resolve_investigation(self):
        """AUTO-059: Complete investigation and approve corrective action"""
        self.ensure_one()
        
        if not self.discrepancy_reason or not self.corrective_action:
            raise UserError(
                "AUTO-059: Please provide both Reason and Corrective Action "
                "before resolving the investigation (FR-ST-007)"
            )
        
        self.investigation_status = 'resolved'
        
        # AUTO-059: Auto-create stock adjustment posting if approved
        if self.discrepancy_reason != 'counting_error':  # Don't adjust for counting errors
            sub_class = self.item_id.sub_classification_id
            if sub_class:
                self.env["mesob.bin.card"].create({
                    "major_classification_id": sub_class.major_classification_id.id,
                    "sub_classification_id": sub_class.id,
                    "date": fields.Date.today(),
                    "reference": f"Stock Taking Adjustment - {self.stock_taking_id.name}",
                    "quantity_received": self.discrepancy if self.discrepancy > 0 else 0,
                    "quantity_issued": abs(self.discrepancy) if self.discrepancy < 0 else 0,
                    "notes": f"AUTO-059: {self.discrepancy_reason} - {self.corrective_action}"
                })
        
        self.stock_taking_id.message_post(
            body=f"""<div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px;">
                <h3>AUTO-059: Discrepancy Resolved</h3>
                <p><strong>Item:</strong> {self.item_id.item_code} - {self.item_id.name}</p>
                <p><strong>Discrepancy:</strong> {self.discrepancy:.2f}</p>
                <p><strong>Variance:</strong> {self.variance_percentage:.1f}%</p>
                <p><strong>Reason:</strong> {dict(self._fields['discrepancy_reason'].selection).get(self.discrepancy_reason)}</p>
                <p><strong>Action:</strong> {self.corrective_action}</p>
                <p><strong>Investigated By:</strong> {self.investigated_by_id.name}</p>
            </div>""",
            subject=f'Discrepancy Resolved: {self.item_id.item_code}',
            message_type='comment'
        )
        
        return {'type': 'ir.actions.client', 'tag': 'reload'}



# ═══════════════════════════════════════════════════════════════════════
# AUTO-057: Stock Taking Sheet Issuance & Return Tracking
# ═══════════════════════════════════════════════════════════════════════

class MesobStockTakingSheetIssuance(models.Model):
    """AUTO-057: Sheet Issuance & Return Tracking with Enhanced Custody Control"""
    
    _name = "mesob.stock.taking.sheet.issuance"
    _description = "Stock Taking Sheet Issuance Record"
    _order = "issue_date desc, id desc"
    
    name = fields.Char(string="Issuance Reference", required=True, copy=False, default="New")
    stock_taking_id = fields.Many2one(
        "mesob.stock.taking",
        string="Stock Taking Event",
        required=True,
        ondelete="cascade"
    )
    sheet_numbers = fields.Char(
        string="Sheet Numbers",
        required=True,
        help="AUTO-057: Range or list of sheet serial numbers (e.g., '1-50' or '1,5,10')"
    )
    recorder_id = fields.Many2one(
        "res.users",
        string="Recorder",
        required=True,
        help="AUTO-057: Team member who received these sheets"
    )
    issue_date = fields.Datetime(
        string="Issued At",
        default=fields.Datetime.now,
        required=True,
        help="AUTO-057: Timestamp when sheets were issued"
    )
    return_date = fields.Datetime(
        string="Returned At",
        help="AUTO-057: Timestamp when sheets were returned"
    )
    is_returned = fields.Boolean(
        string="Returned",
        compute="_compute_return_status",
        store=True,
        help="AUTO-057: True when sheets have been returned"
    )
    hours_held = fields.Float(
        string="Hours Held",
        compute="_compute_hours_held",
        help="AUTO-057: Duration sheets were held by recorder"
    )
    
    # ADVANCED: Digital Signature & Enhanced Tracking
    issuer_signature = fields.Binary(
        string="Issuer Signature",
        help="ADVANCED: Digital signature of PAO/issuer"
    )
    recorder_signature_issue = fields.Binary(
        string="Recorder Signature (Issue)",
        help="ADVANCED: Recorder signature upon receiving sheets"
    )
    recorder_signature_return = fields.Binary(
        string="Recorder Signature (Return)",
        help="ADVANCED: Recorder signature upon returning sheets"
    )
    
    # ADVANCED: Notification tracking
    reminder_sent_count = fields.Integer(
        string="Reminders Sent",
        default=0,
        help="ADVANCED: Number of reminder notifications sent"
    )
    last_reminder_date = fields.Datetime(
        string="Last Reminder",
        help="ADVANCED: When last reminder was sent"
    )
    
    # ADVANCED: Geolocation tracking
    issue_location_lat = fields.Float(string="Issue Location (Lat)", digits=(10, 7))
    issue_location_lng = fields.Float(string="Issue Location (Lng)", digits=(10, 7))
    return_location_lat = fields.Float(string="Return Location (Lat)", digits=(10, 7))
    return_location_lng = fields.Float(string="Return Location (Lng)", digits=(10, 7))
    
    notes = fields.Text(string="Notes")
    
    @api.depends('return_date')
    def _compute_return_status(self):
        """AUTO-057: Check if sheets are returned"""
        for rec in self:
            rec.is_returned = bool(rec.return_date)
    
    @api.depends('issue_date', 'return_date')
    def _compute_hours_held(self):
        """AUTO-057: Calculate custody duration"""
        for rec in self:
            if rec.return_date:
                delta = rec.return_date - rec.issue_date
                rec.hours_held = delta.total_seconds() / 3600
            elif rec.issue_date:
                # Still held
                now = fields.Datetime.now()
                delta = now - rec.issue_date
                rec.hours_held = delta.total_seconds() / 3600
            else:
                rec.hours_held = 0.0
    
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("mesob.stock.taking.sheet.issuance") or "New"
        return super().create(vals_list)
    
    def action_return_sheets(self):
        """AUTO-057: Mark sheets as returned"""
        for rec in self:
            if rec.is_returned:
                raise UserError(f"Sheets {rec.sheet_numbers} have already been returned.")
            
            rec.return_date = fields.Datetime.now()
            
            rec.message_post(
                body=f"""<div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px;">
                    <h3>✅ Sheets Returned</h3>
                    <p><strong>Sheets:</strong> {rec.sheet_numbers}</p>
                    <p><strong>Recorder:</strong> {rec.recorder_id.name}</p>
                    <p><strong>Duration Held:</strong> {rec.hours_held:.1f} hours</p>
                    <p><strong>Returned:</strong> {rec.return_date.strftime('%Y-%m-%d %H:%M')}</p>
                </div>""",
                subject='Sheets Returned'
            )
    
    # ADVANCED: Automated reminder system
    @api.model
    def cron_send_unreturned_reminders(self):
        """ADVANCED: Send reminders for unreturned sheets (AUTO-057 Enhanced).
        
        Escalating reminder schedule:
        - After 4 hours: First reminder
        - After 8 hours: Second reminder (escalate to PAO)
        - After 12 hours: Final warning (escalate to management)
        
        Runs hourly during working hours.
        """
        from datetime import timedelta
        
        now = fields.Datetime.now()
        cutoff_4h = now - timedelta(hours=4)
        cutoff_8h = now - timedelta(hours=8)
        cutoff_12h = now - timedelta(hours=12)
        
        # Find unreturned sheets
        unreturned = self.search([
            ('return_date', '=', False),
            ('issue_date', '<', cutoff_4h),
        ])
        
        for record in unreturned:
            hours_held = record.hours_held
            
            # Determine escalation level
            if hours_held >= 12 and record.reminder_sent_count < 3:
                # Final warning - escalate to management
                record._send_reminder('critical')
            elif hours_held >= 8 and record.reminder_sent_count < 2:
                # Second reminder - escalate to PAO
                record._send_reminder('urgent')
            elif hours_held >= 4 and record.reminder_sent_count < 1:
                # First reminder - friendly
                record._send_reminder('normal')
        
        _logger.info(f"ADVANCED AUTO-057: Processed unreturned sheet reminders for {len(unreturned)} records")
        return True
    
    def _send_reminder(self, severity='normal'):
        """ADVANCED: Send reminder notification via email and chatter"""
        self.ensure_one()
        
        severity_config = {
            'normal': {
                'color': '#ffc107',
                'icon': '⏰',
                'title': 'Reminder: Please Return Count Sheets',
                'recipients': [self.recorder_id.partner_id.id],
            },
            'urgent': {
                'color': '#fd7e14',
                'icon': '⚠️',
                'title': 'URGENT: Count Sheets Overdue',
                'recipients': [self.recorder_id.partner_id.id] + self.stock_taking_id.pao_id.partner_id.ids,
            },
            'critical': {
                'color': '#dc3545',
                'icon': '🚨',
                'title': 'CRITICAL: Count Sheets Severely Overdue',
                'recipients': [self.recorder_id.partner_id.id] + self.stock_taking_id.pao_id.partner_id.ids,
            },
        }
        
        config = severity_config.get(severity, severity_config['normal'])
        
        self.message_post(
            body=f"""<div style="background-color: #fff3cd; border-left: 4px solid {config['color']}; padding: 15px;">
                <h3 style="color: {config['color']};">{config['icon']} {config['title']}</h3>
                <p><strong>Recorder:</strong> {self.recorder_id.name}</p>
                <p><strong>Sheets:</strong> {self.sheet_numbers}</p>
                <p><strong>Issued:</strong> {self.issue_date.strftime('%Y-%m-%d %H:%M')}</p>
                <p><strong>Duration:</strong> {self.hours_held:.1f} hours</p>
                <hr/>
                <p><strong>ACTION REQUIRED:</strong> Please return the count sheets immediately to complete stock-taking.</p>
                <p><em>Stock Taking Event: {self.stock_taking_id.name}</em></p>
            </div>""",
            subject=config['title'],
            message_type='notification',
            partner_ids=config['recipients']
        )
        
        self.write({
            'reminder_sent_count': self.reminder_sent_count + 1,
            'last_reminder_date': fields.Datetime.now(),
        })
        
        _logger.info(
            f"ADVANCED AUTO-057: Sent {severity} reminder to {self.recorder_id.name} - "
            f"Sheets: {self.sheet_numbers}, Hours: {self.hours_held:.1f}"
        )



    def _create_investigations(self, critical_discrepancies):
        """AUTO-059: Auto-create formal investigation records for material discrepancies.
        
        Creates structured investigation workflow for each critical discrepancy:
        - Assigns to PAO as lead investigator
        - Sets target completion based on severity
        - Links to stock taking line for traceability
        
        Args:
            critical_discrepancies: List of dicts with 'line', 'percentage', 'value' keys
        """
        self.ensure_one()
        
        Investigation = self.env['mesob.stock.discrepancy.investigation']
        
        created_investigations = []
        for disc in critical_discrepancies:
            line = disc['line']
            
            # Create investigation
            investigation = Investigation.create({
                'stock_taking_id': self.id,
                'stock_taking_line_id': line.id,
                'assigned_to_id': self.pao_id.id,  # Assign to stock taking PAO
            })
            
            created_investigations.append(investigation)
            
            # Update stock taking line status
            line.write({
                'investigation_status': 'pending',
                'requires_investigation': True
            })
        
        # Send summary notification
        if created_investigations:
            self.message_post(
                body=f"""<div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px;">
                    <h3>🔍 AUTO-059: Investigations Auto-Created</h3>
                    <p><strong>Stock Taking:</strong> {self.name}</p>
                    <p><strong>Investigations Created:</strong> {len(created_investigations)}</p>
                    <p><strong>Assigned To:</strong> {self.pao_id.name}</p>
                    <hr/>
                    <p><em>Material discrepancies require formal investigation per FR-ST-006.</em></p>
                    <p><strong>Investigation References:</strong></p>
                    <ul>
                        {''.join(f'<li>{inv.name} - {inv.item_code} (ETB {inv.discrepancy_value:,.2f})</li>' for inv in created_investigations[:10])}
                        {f'<li><em>...and {len(created_investigations) - 10} more</em></li>' if len(created_investigations) > 10 else ''}
                    </ul>
                </div>""",
                subject=f'AUTO-059: {len(created_investigations)} Investigations Created'
            )
            
            _logger.info(
                f"AUTO-059: Created {len(created_investigations)} investigations for stock taking {self.name}"
            )
        
        return created_investigations

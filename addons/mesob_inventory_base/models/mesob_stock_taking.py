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
            ("damaged", "Damaged Items"),
            ("shortage", "Unexplained Shortage"),
            ("overage", "Unrecorded Overage"),
            ("wrong_quality", "Inferior Quality / Expired"),
            ("theft", "Pilferage / Theft"),
        ],
        string="Reason for Discrepancy",
    )
    corrective_action = fields.Text(string="Proposed Corrective Action")
    notes = fields.Text(string="Witness/Team Notes")

    @api.depends("recorded_qty", "physical_qty")
    def _compute_discrepancy(self):
        for line in self:
            line.discrepancy = line.physical_qty - line.recorded_qty

    @api.onchange("physical_qty")
    def _onchange_physical_qty(self):
        """Auto-mark counted with sticker upon physical qty entry (FR-ST-005)."""
        if self.physical_qty > 0.0 or self.is_counted:
            self.is_counted = True

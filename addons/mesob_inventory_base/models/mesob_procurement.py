from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
import datetime
import logging

_logger = logging.getLogger(__name__)


class MesobProcurementPlan(models.Model):
    """Annual Procurement Plan (APP) - FR-PROC-001."""

    _name = "mesob.procurement.plan"
    _description = "Annual Procurement Plan"
    _order = "fiscal_year desc, id desc"

    name = fields.Char(
        string="APP Reference",
        required=True,
        copy=False,
        default="New",
    )
    fiscal_year = fields.Char(
        string="Ethiopian Fiscal Year",
        required=True,
        placeholder="e.g., 2018 E.C.",
    )
    planning_type = fields.Selection(
        [("standard", "Standard / Planned"), ("emergency", "Emergency")],
        string="Planning Type",
        default="standard",
        required=True,
    )
    execution_type = fields.Selection(
        [("domestic", "Domestic Only"), ("international", "International / Both")],
        string="Execution Type",
        default="domestic",
        required=True,
    )
    procurement_stream = fields.Selection(
        [
            ("goods", "Goods"),
            ("works", "Works"),
            ("services", "Non-Consulting Services"),
            ("consultancy", "Consultancy Services"),
        ],
        string="Procurement Stream",
        default="goods",
        required=True,
    )
    rejection_comment = fields.Text(string="Rejection Comments")
    lot_ids = fields.One2many(
        "mesob.procurement.plan.lot",
        "plan_id",
        string="Procurement Lots",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("puh_approved", "PUH Approved"),
            ("pec_approved", "PEC Approved"),
            ("hope_approved", "HOPE Approved (Published)"),
            ("rejected", "Rejected"),
        ],
        string="Status",
        default="draft",
        required=True,
        tracking=True,
    )
    
    # AUTO-004: Approval workflow tracking fields
    submitted_date = fields.Datetime(
        string="Submitted Date",
        readonly=True,
        help="Date when APP was submitted for approval"
    )
    puh_approval_date = fields.Datetime(
        string="PUH Approval Date",
        readonly=True
    )
    pec_approval_date = fields.Datetime(
        string="PEC Approval Date",
        readonly=True
    )
    hope_approval_date = fields.Datetime(
        string="HOPE Approval Date",
        readonly=True
    )
    
    approval_sla_status = fields.Selection([
        ('on_time', 'On Time'),
        ('warning', 'Approaching Deadline'),
        ('overdue', 'Overdue'),
    ], string='Approval SLA Status', compute='_compute_approval_sla', store=True)
    
    days_in_approval = fields.Integer(
        string='Days in Approval',
        compute='_compute_approval_sla',
        store=True,
        help='Number of days since submission'
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = f"APP/{vals.get('fiscal_year', 'FY')}/{self.env['ir.sequence'].next_by_code('mesob.procurement.plan') or '001'}"
        return super().create(vals_list)
    
    @api.depends('submitted_date', 'state')
    def _compute_approval_sla(self):
        """AUTO-004: Compute approval SLA status and days in approval."""
        for rec in self:
            if not rec.submitted_date or rec.state in ('draft', 'hope_approved', 'rejected'):
                rec.approval_sla_status = 'on_time'
                rec.days_in_approval = 0
                continue
            
            # Calculate days since submission
            now = fields.Datetime.now()
            days_diff = (now - rec.submitted_date).days
            rec.days_in_approval = days_diff
            
            # SLA thresholds (configurable)
            warning_days = 5  # Yellow alert at 5 days
            overdue_days = 7  # Red alert at 7 days
            
            if days_diff >= overdue_days:
                rec.approval_sla_status = 'overdue'
            elif days_diff >= warning_days:
                rec.approval_sla_status = 'warning'
            else:
                rec.approval_sla_status = 'on_time'

    def action_submit_for_approval(self):
        """AUTO-004: Submit APP for approval workflow (initiates auto-routing)."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError("Only draft plans can be submitted.")
            if not rec.lot_ids:
                raise UserError("Please add at least one lot before submitting.")
            
            rec.write({
                'submitted_date': fields.Datetime.now(),
                'state': 'draft'  # Remains draft until PUH approves
            })
            
            # AUTO-004: Auto-route to PUH with notification
            rec._send_approval_notification('puh')
            
            _logger.info(f"AUTO-004: APP {rec.name} submitted for approval")
        
        return True

    def action_puh_approve(self):
        """AUTO-004: PUH approves and auto-routes to PEC."""
        for rec in self:
            if rec.state not in ("draft", "rejected"):
                raise UserError("Only draft or rejected plans can be approved by PUH.")
            
            rec.write({
                'state': 'puh_approved',
                'puh_approval_date': fields.Datetime.now()
            })
            
            # AUTO-004: Auto-route to PEC with notification
            rec._send_approval_notification('pec')
            
            _logger.info(f"AUTO-004: APP {rec.name} approved by PUH, routed to PEC")
        
        return True

    def action_pec_approve(self):
        """AUTO-004: PEC approves and auto-routes to HOPE."""
        for rec in self:
            if rec.state != "puh_approved":
                raise UserError("The plan must be approved by PUH first.")
            
            rec.write({
                'state': 'pec_approved',
                'pec_approval_date': fields.Datetime.now()
            })
            
            # AUTO-004: Auto-route to HOPE with notification
            rec._send_approval_notification('hope')
            
            _logger.info(f"AUTO-004: APP {rec.name} approved by PEC, routed to HOPE")
        
        return True

    def action_hope_approve(self):
        """AUTO-004: HOPE gives final authorization and publishes APP (FR-PROC-005)."""
        for rec in self:
            if rec.state != "pec_approved":
                raise UserError("The plan must be approved by PEC first.")
            
            rec.write({
                'state': 'hope_approved',
                'hope_approval_date': fields.Datetime.now()
            })
            
            # Route lots to correct execution workflow (FR-PROC-006)
            for lot in rec.lot_ids:
                if lot.mechanism == "bidding":
                    lot.state = "tender"
                elif lot.mechanism == "shopping":
                    lot.state = "rfq"
                else:
                    lot.state = "approved"
            
            # AUTO-004: Send publication notification to all stakeholders
            rec._send_publication_notification()
            
            _logger.info(f"AUTO-004: APP {rec.name} approved by HOPE and published")
        
        return True
                    lot.state = "rfq"
                else:
                    lot.state = "approved"
        return True

    def action_reject(self, comment):
        """Reject and return to preceding actor with mandatory comments."""
        for rec in self:
            if not comment:
                raise UserError("Mandatory comment required for rejection.")
            rec.write({
                "state": "rejected",
                "rejection_comment": comment,
            })
        return True

    def action_auto_generate_lots(self):
        """Auto-Lotting by Sub-Classification.
        Groups locked needs without lot_id by their sub-classification and generates Lots.
        """
        for plan in self:
            # 1. Search for locked needs that do not have a lot assigned yet and are valid (have item_id or sub_classification_id)
            needs = self.env["mesob.procurement.need"].search([
                ("state", "=", "locked"),
                ("lot_id", "=", False),
                "|",
                ("item_id", "!=", False),
                ("sub_classification_id", "!=", False)
            ])
            if not needs:
                raise UserError("No valid locked department needs available for automatic consolidation. Please make sure you have submitted, reviewed, and locked some valid Need Requests first.")

            # 2. Defensive fallback: Ensure all needs have sub_classification_id populated from item_id if empty
            for need in needs:
                if need.item_id and not need.sub_classification_id:
                    need.write({
                        "sub_classification_id": need.item_id.sub_classification_id.id,
                        "major_classification_id": need.item_id.classification_id.id,
                    })

            # Re-fetch/re-filter needs that actually have sub_classification_id populated now
            needs_with_sub = needs.filtered(lambda n: n.sub_classification_id)
            if not needs_with_sub:
                raise UserError("No locked department needs with a valid Sub-Classification are available for automatic consolidation.")

            # 3. Group them by Sub-Classification
            sub_classes = needs_with_sub.mapped("sub_classification_id")
            lot_count = len(plan.lot_ids) + 1

            for sub_class in sub_classes:
                # Filter needs belonging to this specific sub-classification
                sub_class_needs = needs_with_sub.filtered(lambda n: n.sub_classification_id == sub_class)
                total_budget = sum(sub_class_needs.mapped("total_price"))

                # 4. Check if there's already an existing lot in this APP for the same sub-classification
                existing_lot = plan.lot_ids.filtered(lambda l: l.sub_classification_id == sub_class)
                if existing_lot:
                    # Update budget of the existing lot and link the needs to it
                    existing_lot[0].write({
                        "budget": existing_lot[0].budget + total_budget
                    })
                    sub_class_needs.write({"lot_id": existing_lot[0].id})
                else:
                    # Create a new Lot and assign it
                    lot = self.env["mesob.procurement.plan.lot"].create({
                        "plan_id": plan.id,
                        "name": f"Lot {lot_count}: {sub_class.name}",
                        "category": "equipment" if sub_class.is_fixed_asset else "supplies",
                        "budget": total_budget,
                        "sub_classification_id": sub_class.id,
                    })
                    sub_class_needs.write({"lot_id": lot.id})
                    lot_count += 1
        return True
    
    def _send_approval_notification(self, approver_role):
        """AUTO-004: Send notification to next approver in workflow.
        
        Args:
            approver_role: 'puh', 'pec', or 'hope'
        """
        self.ensure_one()
        
        # Map roles to user groups (configure these group external IDs)
        role_group_map = {
            'puh': 'mesob_inventory_base.group_mesob_procurement_officer',  # Adjust as needed
            'pec': 'mesob_inventory_base.group_mesob_pao',
            'hope': 'mesob_inventory_base.group_mesob_pao',  # HOPE typically PAO or higher
        }
        
        group_xml_id = role_group_map.get(approver_role)
        if not group_xml_id:
            return
        
        approver_group = self.env.ref(group_xml_id, raise_if_not_found=False)
        if not approver_group or not approver_group.users:
            _logger.warning(f"AUTO-004: No users found for approver role {approver_role}")
            return
        
        role_names = {'puh': 'Procurement Unit Head', 'pec': 'Procurement Endorsing Committee', 'hope': 'Head of Public Body'}
        role_name = role_names.get(approver_role, approver_role.upper())
        
        # Build lots summary
        lots_summary = '<ul>'
        for lot in self.lot_ids:
            lots_summary += f'<li>{lot.name}: ETB {lot.budget:,.2f} ({lot.mechanism})</li>'
        lots_summary += '</ul>'
        
        # SLA status indicator
        sla_color = {'on_time': 'green', 'warning': 'orange', 'overdue': 'red'}[self.approval_sla_status]
        
        self.message_post(
            body=f"""<div style="border-left: 4px solid {sla_color}; padding-left: 15px;">
                <h3>APP Approval Required: {role_name}</h3>
                <p><strong>APP Reference:</strong> {self.name}</p>
                <p><strong>Fiscal Year:</strong> {self.fiscal_year}</p>
                <p><strong>Days in Approval:</strong> <span style="color: {sla_color}; font-weight: bold;">{self.days_in_approval} days</span></p>
                <p><strong>Total Lots:</strong> {len(self.lot_ids)}</p>
                <p><strong>Total Budget:</strong> ETB {sum(self.lot_ids.mapped('budget')):,.2f}</p>
                <hr/>
                <h4>Lots Summary:</h4>
                {lots_summary}
                <hr/>
                <p><em>Please review and approve this Annual Procurement Plan.</em></p>
                <p><a href="/web#id={self.id}&model=mesob.procurement.plan&view_type=form" 
                   style="background-color: #007bff; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                   Review APP →
                </a></p>
            </div>""",
            subject=f'APP Approval Required: {self.name} ({role_name})',
            message_type='notification',
            partner_ids=approver_group.users.mapped('partner_id').ids
        )
        
        _logger.info(f"AUTO-004: Notification sent to {len(approver_group.users)} {role_name} users")
    
    def _send_publication_notification(self):
        """AUTO-004: Send APP publication notification to all stakeholders."""
        self.ensure_one()
        
        # Notify all procurement users and department heads
        procurement_users = self.env.ref('mesob_inventory_base.group_mesob_procurement_officer', raise_if_not_found=False)
        
        if procurement_users and procurement_users.users:
            self.message_post(
                body=f"""<div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px;">
                    <h2 style="color: #155724;">✅ APP Published & Approved</h2>
                    <p><strong>APP Reference:</strong> {self.name}</p>
                    <p><strong>Fiscal Year:</strong> {self.fiscal_year}</p>
                    <p><strong>Approval Date:</strong> {self.hope_approval_date}</p>
                    <p><strong>Total Lots:</strong> {len(self.lot_ids)}</p>
                    <p><strong>Total Budget:</strong> ETB {sum(self.lot_ids.mapped('budget')):,.2f}</p>
                    <hr/>
                    <p><em>This APP has been approved by HOPE and is now published for execution.</em></p>
                    <p><em>Lots have been auto-routed to appropriate execution workflows.</em></p>
                </div>""",
                subject=f'APP Published: {self.name}',
                message_type='notification',
                partner_ids=procurement_users.users.mapped('partner_id').ids
            )


class MesobProcurementPlanLot(models.Model):
    """Procurement Lot inside APP - FR-PROC-004."""

    _name = "mesob.procurement.plan.lot"
    _description = "Procurement Lot"

    plan_id = fields.Many2one(
        "mesob.procurement.plan",
        string="Annual Plan",
        required=True,
        ondelete="cascade",
    )
    name = fields.Char(string="Lot Name / No.", required=True)
    category = fields.Selection(
        [
            ("supplies", "Supplies / Raw Materials"),
            ("equipment", "Office Equipment / IT"),
            ("fixed_assets", "Fixed Assets"),
            ("other", "Other"),
        ],
        string="Category",
        default="supplies",
        required=True,
    )
    sub_classification_id = fields.Many2one(
        "mesob.inventory.sub.classification",
        string="Linked Sub Classification",
        help="Linked sub-classification for automated stock integration.",
    )
    mechanism = fields.Selection(
        [
            ("bidding", "Tender / Bidding"),
            ("shopping", "Shopping / RFQ"),
            ("direct", "Direct (Single-Source)"),
        ],
        string="Procurement Mechanism",
        default="shopping",
        required=True,
    )
    
    # AUTO-006: Suggested mechanism based on thresholds
    suggested_mechanism = fields.Selection(
        [
            ("bidding", "Tender / Bidding"),
            ("shopping", "Shopping / RFQ"),
            ("direct", "Direct (Single-Source)"),
        ],
        string="Suggested Mechanism",
        compute='_compute_suggested_mechanism',
        store=True,
        help="AUTO-006: System-suggested procurement method based on estimated value thresholds"
    )
    
    mechanism_override_reason = fields.Text(
        string="Method Override Reason",
        help="Mandatory if selected mechanism differs from suggested mechanism"
    )
    
    budget = fields.Float(string="Distributed Budget", required=True)
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("approved", "Approved"),
            ("tender", "Tender Prepared"),
            ("rfq", "RFQ Pending"),
            ("closed", "Closed"),
        ],
        string="Lot Status",
        default="draft",
    )
    need_ids = fields.One2many(
        "mesob.procurement.need",
        "lot_id",
        string="Consolidated Needs",
    )
    
    @api.depends('budget')
    def _compute_suggested_mechanism(self):
        """AUTO-006: Suggest procurement mechanism based on threshold rules (FR-PROC-007, FR-PROC-008)."""
        # TODO: Make these thresholds configurable via system parameters
        # Ethiopian procurement thresholds (example values - adjust per FPPA regulations)
        ICB_THRESHOLD = 10000000.0  # ETB 10M+ requires International Competitive Bidding
        NCB_THRESHOLD = 5000000.0   # ETB 5M-10M requires National Competitive Bidding
        RFQ_THRESHOLD = 500000.0    # ETB 500K-5M allows Shopping/RFQ
        # Below 500K can use Shopping/RFQ
        
        for lot in self:
            if lot.budget >= ICB_THRESHOLD:
                lot.suggested_mechanism = 'bidding'  # ICB
            elif lot.budget >= NCB_THRESHOLD:
                lot.suggested_mechanism = 'bidding'  # NCB
            elif lot.budget >= RFQ_THRESHOLD:
                lot.suggested_mechanism = 'shopping'  # RFQ/Shopping
            else:
                lot.suggested_mechanism = 'shopping'  # Shopping
    
    @api.constrains('mechanism', 'suggested_mechanism', 'mechanism_override_reason')
    def _check_mechanism_override(self):
        """AUTO-006: Require justification if mechanism differs from suggestion."""
        for lot in self:
            if lot.mechanism != lot.suggested_mechanism:
                if lot.mechanism == 'direct' and not lot.mechanism_override_reason:
                    raise ValidationError(
                        f"Lot {lot.name}: Direct/Single-Source procurement requires "
                        "documented justification in 'Method Override Reason' field (FR-PROC-007)."
                    )
                elif not lot.mechanism_override_reason:
                    raise ValidationError(
                        f"Lot {lot.name}: Selected mechanism '{lot.mechanism}' differs from "
                        f"suggested '{lot.suggested_mechanism}'. Please provide override reason."
                    )
    
    @api.onchange('budget')
    def _onchange_budget(self):
        """AUTO-006: Auto-suggest mechanism when budget changes."""
        if self.budget and not self.mechanism_override_reason:
            # Auto-set mechanism to match suggestion if no override reason exists
            if self.suggested_mechanism:
                self.mechanism = self.suggested_mechanism
    
    def action_generate_purchase_order(self):
        """AUTO-022: Auto-generate draft Purchase Order from approved lot.
        
        Creates a draft PO with:
        - Item codes/quantities from consolidated needs
        - Unit prices from approved bid/contract or last PO
        - Delivery location from store master
        - Supplier from winning bid or lot settings
        
        Officer reviews and submits for approval workflow (FR-PROC-026).
        """
        self.ensure_one()
        
        if self.state not in ('approved', 'tender', 'rfq'):
            raise UserError("Only approved lots can generate Purchase Orders.")
        
        if not self.need_ids:
            raise UserError(f"Lot {self.name} has no consolidated needs. Cannot generate PO.")
        
        # Find winning bid/contract for this lot
        winning_bid = None
        if self.mechanism == 'bidding':
            tender = self.env['mesob.procurement.tender'].search([
                ('lot_id', '=', self.id),
                ('state', '=', 'evaluated')
            ], limit=1)
            if tender:
                winning_bid = tender.bid_ids.filtered(lambda b: b.is_winner).sorted('evaluated_price')[:1]
        
        # Prepare PO values
        po_vals = {
            'plan_lot_id': self.id,
            'date_order': fields.Date.today(),
            'state': 'draft',
            'line_ids': [],
        }
        
        # Set supplier from winning bid if available
        if winning_bid and winning_bid.supplier_id:
            po_vals['supplier_id'] = winning_bid.supplier_id.id
        else:
            # Must have a supplier - raise error
            raise UserError(
                f"Cannot generate PO for Lot {self.name}: No supplier assigned.\n"
                "Please either:\n"
                "1. Award a bid from tender evaluation, or\n"
                "2. Manually select a supplier after PO generation."
            )
        
        # Group needs by item to avoid duplicate lines
        items_dict = {}
        for need in self.need_ids:
            if not need.item_id:
                continue
            
            item_id = need.item_id.id
            if item_id not in items_dict:
                items_dict[item_id] = {
                    'item': need.item_id,
                    'quantity': 0.0,
                    'unit_price': need.estimated_unit_price or 0.0,
                    'major_classification_id': need.major_classification_id.id if need.major_classification_id else False,
                    'sub_classification_id': need.sub_classification_id.id if need.sub_classification_id else False,
                }
            
            items_dict[item_id]['quantity'] += need.quantity
            
            # Use highest price as default (officer can adjust)
            if need.estimated_unit_price > items_dict[item_id]['unit_price']:
                items_dict[item_id]['unit_price'] = need.estimated_unit_price
        
        if not items_dict:
            raise UserError(f"Lot {self.name} has no items with catalogued item codes. Cannot generate PO.")
        
        # Create PO lines
        for item_data in items_dict.values():
            item = item_data['item']
            quantity = item_data['quantity']
            unit_price = item_data['unit_price']
            
            # Override price from winning bid if available
            if winning_bid and winning_bid.line_ids:
                bid_line = winning_bid.line_ids.filtered(lambda l: l.item_id == item)
                if bid_line:
                    unit_price = bid_line[0].unit_price
            
            po_vals['line_ids'].append((0, 0, {
                'item_id': item.id,
                'major_classification_id': item_data['major_classification_id'],
                'sub_classification_id': item_data['sub_classification_id'],
                'quantity': quantity,
                'price_unit': unit_price,
                'description': item.name,
            }))
        
        # Create the PO
        po = self.env['mesob.procurement.order'].create(po_vals)
        
        # Update lot state
        self.write({'state': 'closed'})
        
        # Calculate total PO value for logging
        total_value = sum(line[2]['quantity'] * line[2]['price_unit'] for line in po_vals['line_ids'])
        
        # Log action
        _logger.info(
            f"AUTO-022: PO {po.name} auto-generated from Lot {self.name} - "
            f"{len(po_vals['line_ids'])} items, Total: ETB {total_value:,.2f}"
        )
        
        # Send notification to Procurement Officer
        procurement_users = self.env.ref('mesob_inventory_base.group_mesob_procurement_officer', raise_if_not_found=False)
        if procurement_users and procurement_users.users:
            self.plan_id.message_post(
                body=f"""<div style="background-color: #d1ecf1; border-left: 4px solid #0c5460; padding: 15px;">
                    <h3>AUTO-022: Draft PO Generated</h3>
                    <p><strong>PO Reference:</strong> {po.name}</p>
                    <p><strong>Source Lot:</strong> {self.name}</p>
                    <p><strong>Supplier:</strong> {po.supplier_id.name if po.supplier_id else 'Not assigned'}</p>
                    <p><strong>Items:</strong> {len(po.line_ids)}</p>
                    <p><strong>Estimated Total:</strong> ETB {total_value:,.2f}</p>
                    <hr/>
                    <p><em>Please review item quantities, unit prices, and supplier details before submitting for approval.</em></p>
                    <p><a href="/web#id={po.id}&model=mesob.procurement.order&view_type=form" 
                       style="background-color: #17a2b8; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                       Review PO →
                    </a></p>
                </div>""",
                subject=f'Draft PO Ready for Review: {po.name}',
                message_type='notification',
                partner_ids=procurement_users.users.mapped('partner_id').ids
            )
        
        return {
            'name': 'Purchase Order',
            'type': 'ir.actions.act_window',
            'res_model': 'mesob.procurement.order',
            'res_id': po.id,
            'view_mode': 'form',
            'target': 'current',
        }


class MesobProcurementNeed(models.Model):
    """Departmental Needs Collection - FR-PROC-002."""

    _name = "mesob.procurement.need"
    _description = "Departmental Need Request"

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
    )
    item_id = fields.Many2one(
        "mesob.inventory.item",
        string="Catalogued Stock Item",
        required=False,
        help="Optional if item is not yet coded or will be auto-generated.",
    )
    major_classification_id = fields.Many2one(
        "mesob.inventory.major.classification",
        string="Major Classification",
        help="Major classification code (e.g., 4402) for non-coded / auto-generated items.",
    )
    sub_classification_id = fields.Many2one(
        "mesob.inventory.sub.classification",
        string="Sub Classification",
        help="Sub classification code (e.g., 001) for non-coded / auto-generated items.",
    )
    item_code = fields.Char(
        string="Item Code",
        compute="_compute_item_code",
        store=True,
        readonly=True,
    )
    quantity = fields.Float(string="Quantity Requested", required=True, default=1.0)
    estimated_unit_price = fields.Float(string="Estimated Unit Price", required=True)
    total_price = fields.Float(
        string="Estimated Total Price",
        compute="_compute_total_price",
        store=True,
    )
    expected_delivery_period = fields.Char(
        string="Expected Delivery Period",
        required=True,
        placeholder="e.g. Q1 / Sene 2018",
    )
    reviewer_id = fields.Many2one("res.users", string="Reviewer", readonly=True)
    review_timestamp = fields.Datetime(string="Review Timestamp", readonly=True)
    lot_id = fields.Many2one(
        "mesob.procurement.plan.lot",
        string="Assigned APP Lot",
        help="Lot assigned by Senior Procurement Officer (FR-PROC-004).",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("reviewed", "Reviewed"),
            ("locked", "Locked (Immutable)"),
        ],
        string="Status",
        default="draft",
        required=True,
    )

    @api.onchange("item_id")
    def _onchange_item_id(self):
        """Auto-populate classifications when selecting a catalogued item."""
        if self.item_id:
            self.major_classification_id = self.item_id.classification_id
            self.sub_classification_id = self.item_id.sub_classification_id

    @api.constrains("item_id", "major_classification_id", "sub_classification_id")
    def _check_required_classifications(self):
        for rec in self:
            if not rec.item_id and (not rec.major_classification_id or not rec.sub_classification_id):
                raise ValidationError("You must either select a Catalogued Item or specify both Major and Sub Classifications.")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("item_id"):
                item = self.env["mesob.inventory.item"].browse(vals["item_id"])
                if item:
                    vals["major_classification_id"] = item.classification_id.id
                    vals["sub_classification_id"] = item.sub_classification_id.id
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("item_id"):
            item = self.env["mesob.inventory.item"].browse(vals["item_id"])
            if item:
                vals["major_classification_id"] = item.classification_id.id
                vals["sub_classification_id"] = item.sub_classification_id.id
        return super().write(vals)

    @api.depends("item_id", "major_classification_id", "sub_classification_id")
    def _compute_item_code(self):
        for rec in self:
            if rec.item_id:
                rec.item_code = rec.item_id.item_code
            elif rec.major_classification_id and rec.sub_classification_id:
                rec.item_code = f"{rec.major_classification_id.code}-{rec.sub_classification_id.code}-XXX"
            else:
                rec.item_code = False

    @api.depends("quantity", "estimated_unit_price")
    def _compute_total_price(self):
        for rec in self:
            rec.total_price = rec.quantity * rec.estimated_unit_price

    def action_submit(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError("Only draft needs can be submitted.")
            rec.state = "submitted"
        return True

    def action_review(self):
        """Reviewer workflow (FR-PROC-003)."""
        for rec in self:
            if rec.state != "submitted":
                raise UserError("Only submitted needs can be reviewed.")
            rec.write({
                "state": "reviewed",
                "reviewer_id": self.env.user.id,
                "review_timestamp": fields.Datetime.now(),
            })
        return True

    def action_lock(self):
        """Lock need to make it immutable."""
        for rec in self:
            if rec.state != "reviewed":
                raise UserError("Only reviewed needs can be locked.")
            rec.state = "locked"
        return True


class MesobProcurementTender(models.Model):
    """Bidding and Tender Management - FR-PROC-013."""

    _name = "mesob.procurement.tender"
    _description = "Procurement Tender"
    _order = "id desc"

    name = fields.Char(
        string="Tender Reference",
        required=True,
        copy=False,
        default="New",
    )
    lot_id = fields.Many2one(
        "mesob.procurement.plan.lot",
        string="Source APP Lot",
        required=True,
        domain=[("mechanism", "=", "bidding")],
    )
    technical_specifications = fields.Text(
        string="Technical Specifications",
        required=True,
        help="FR-PROC-009 quality performance characteristics (brandless).",
    )
    spec_status = fields.Selection(
        [("draft", "Draft"), ("approved", "Approved")],
        string="Specification Status",
        default="draft",
        required=True,
    )
    advertisement_date = fields.Date(string="Advertisement Date")
    submission_deadline = fields.Datetime(string="Submission Deadline")
    opening_minutes = fields.Text(string="Bid Opening Minutes (FR-PROC-015)")
    opening_signatures = fields.Text(string="Opening Committee Signatures")
    bid_ids = fields.One2many(
        "mesob.procurement.bid",
        "tender_id",
        string="Submitted Bids",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("spec_approved", "Spec Approved"),
            ("advertised", "Advertised"),
            ("opened", "Bids Opened"),
            ("evaluated", "Evaluated"),
            ("closed", "Closed"),
        ],
        string="Status",
        default="draft",
        required=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = f"TEN/{self.env['ir.sequence'].next_by_code('mesob.procurement.tender') or '001'}"
        return super().create(vals_list)

    def action_approve_spec(self):
        """Technical specifications sign-off status approved (FR-PROC-009)."""
        for rec in self:
            rec.write({
                "spec_status": "approved",
                "state": "spec_approved",
            })
        return True

    def action_advertise(self):
        for rec in self:
            if rec.spec_status != "approved":
                raise UserError("Cannot advertise until Technical Specifications are approved (FR-PROC-013).")
            if not rec.advertisement_date or not rec.submission_deadline:
                raise UserError("Please set advertisement date and submission deadline first.")
            rec.state = "advertised"
        return True

    def action_open_bids(self):
        """Record public bid opening minutes and validate timestamps (FR-PROC-015)."""
        for rec in self:
            if rec.state != "advertised":
                raise UserError("Bids can only be opened after the tender is advertised.")
            rec.state = "opened"
        return True

    def action_evaluate(self):
        """Trigger bid evaluation ranking and preference calculations (FR-PROC-017, FR-PROC-018)."""
        for rec in self:
            if rec.state != "opened":
                raise UserError("Bids must be opened before evaluation.")

            # Filter responsive / preliminary passed bids
            responsive_bids = rec.bid_ids.filtered(lambda b: b.preliminary_passed)
            if not responsive_bids:
                raise UserError("There are no responsive/preliminary passed bids to evaluate.")

            # Compute adjusted evaluated price & ranking
            for bid in responsive_bids:
                preference_factor = 1.0
                if bid.local_content >= 70.0:
                    preference_factor = 1.0 - 0.135  # 13.5% domestic preference (FR-PROC-018)
                elif 40.0 <= bid.local_content < 70.0:
                    preference_factor = 1.0 - 0.11   # 11% domestic preference
                
                bid.evaluated_price = bid.bid_price * preference_factor

            # Perform ranking (ascending evaluated price)
            ranked_bids = sorted(responsive_bids, key=lambda b: b.evaluated_price)
            for rank, bid in enumerate(ranked_bids, start=1):
                bid.ranking = rank

            rec.state = "evaluated"
        return True


class MesobProcurementBid(models.Model):
    """Supplier Bid submission inside Tender - FR-PROC-017."""

    _name = "mesob.procurement.bid"
    _description = "Procurement Bid Submission"

    tender_id = fields.Many2one("mesob.procurement.tender", string="Tender", required=True, ondelete="cascade")
    supplier_id = fields.Many2one(
        "res.partner",
        string="Supplier",
        required=True,
        domain=[("fppa_blacklisted", "=", False)],
    )
    bid_price = fields.Float(string="Original Bid Price (ETB)", required=True)
    local_content = fields.Float(
        string="Local Content (%)",
        default=0.0,
        help="Percentage of local material/manufacturing content.",
    )
    
    # AUTO-015: Domestic preference calculation fields
    preference_percentage = fields.Float(
        string="Preference Margin (%)",
        compute='_compute_domestic_preference',
        store=True,
        help="AUTO-015: Domestic preference margin per BR-PROC-003 (13.5% for ≥70% local, 11% for 40-70% local)"
    )
    preference_amount = fields.Float(
        string="Preference Amount (ETB)",
        compute='_compute_domestic_preference',
        store=True,
        help="AUTO-015: Preference amount deducted for ranking purposes only"
    )
    
    preliminary_passed = fields.Boolean(
        string="Administrative Passed",
        default=True,
        help="Checked bid completeness, security validity & eligibility.",
    )
    technical_score = fields.Float(string="Technical Score", default=0.0)
    financial_score = fields.Float(string="Financial Score", default=0.0)
    evaluated_price = fields.Float(
        string="Evaluated Price (ETB)",
        compute='_compute_domestic_preference',
        store=True,
        readonly=True,
        help="AUTO-015: Adjusted price applying domestic preference for ranking (FR-PROC-018 + BR-PROC-003). Contract uses original bid_price.",
    )
    ranking = fields.Integer(string="Rank", readonly=True)
    is_winner = fields.Boolean(string="Winning Bid", default=False, help="Marked as winning bid after evaluation")
    
    line_ids = fields.One2many(
        'mesob.procurement.bid.line',
        'bid_id',
        string='Bid Lines',
        help='Individual items quoted in this bid'
    )
    
    @api.depends('bid_price', 'local_content')
    def _compute_domestic_preference(self):
        """AUTO-015: Auto-calculate domestic preference per BR-PROC-003.
        
        Ethiopian Federal Procurement Regulation:
        - ≥70% local content → 13.5% preference margin
        - 40-70% local content → 11% preference margin
        - <40% or foreign → 0% preference
        
        Evaluated price = bid_price - (bid_price × preference_percentage)
        
        Note: Preference is for ranking ONLY. Contract and payment use original bid_price (FR-PROC-018).
        """
        for bid in self:
            # Determine preference percentage based on local content (BR-PROC-003)
            if bid.local_content >= 70.0:
                bid.preference_percentage = 13.5
            elif bid.local_content >= 40.0:
                bid.preference_percentage = 11.0
            else:
                bid.preference_percentage = 0.0
            
            # Calculate preference amount
            bid.preference_amount = bid.bid_price * (bid.preference_percentage / 100.0)
            
            # Calculate evaluated price for ranking
            bid.evaluated_price = bid.bid_price - bid.preference_amount
            
            _logger.info(
                f"AUTO-015: Bid {bid.id} preference calculation - "
                f"Local Content: {bid.local_content}%, "
                f"Preference: {bid.preference_percentage}%, "
                f"Original Price: ETB {bid.bid_price:,.2f}, "
                f"Evaluated Price: ETB {bid.evaluated_price:,.2f}"
            )
    
    def action_generate_preference_worksheet(self):
        """AUTO-015: Generate domestic preference calculation worksheet for audit trail (FR-PROC-018)."""
        self.ensure_one()
        
        worksheet_html = f"""
        <div style="font-family: Arial, sans-serif; padding: 20px;">
            <h2 style="text-align: center;">Domestic Preference Calculation Worksheet</h2>
            <p style="text-align: center;"><em>Federal Procurement Regulation BR-PROC-003</em></p>
            <hr/>
            
            <table style="width: 100%; border-collapse: collapse; margin-top: 20px;">
                <tr style="background-color: #f0f0f0;">
                    <th style="border: 1px solid #ddd; padding: 8px; text-align: left;">Item</th>
                    <th style="border: 1px solid #ddd; padding: 8px; text-align: right;">Value</th>
                </tr>
                <tr>
                    <td style="border: 1px solid #ddd; padding: 8px;">Tender Reference</td>
                    <td style="border: 1px solid #ddd; padding: 8px; text-align: right;">{self.tender_id.name}</td>
                </tr>
                <tr>
                    <td style="border: 1px solid #ddd; padding: 8px;">Supplier Name</td>
                    <td style="border: 1px solid #ddd; padding: 8px; text-align: right;">{self.supplier_id.name}</td>
                </tr>
                <tr>
                    <td style="border: 1px solid #ddd; padding: 8px;">Local Content (%)</td>
                    <td style="border: 1px solid #ddd; padding: 8px; text-align: right; font-weight: bold;">{self.local_content}%</td>
                </tr>
                <tr style="background-color: #fff3cd;">
                    <td style="border: 1px solid #ddd; padding: 8px;">Applicable Preference Margin</td>
                    <td style="border: 1px solid #ddd; padding: 8px; text-align: right; font-weight: bold;">{self.preference_percentage}%</td>
                </tr>
                <tr>
                    <td style="border: 1px solid #ddd; padding: 8px;">Original Bid Price (ETB)</td>
                    <td style="border: 1px solid #ddd; padding: 8px; text-align: right;">{self.bid_price:,.2f}</td>
                </tr>
                <tr>
                    <td style="border: 1px solid #ddd; padding: 8px;">Preference Deduction (ETB)</td>
                    <td style="border: 1px solid #ddd; padding: 8px; text-align: right;">({self.preference_amount:,.2f})</td>
                </tr>
                <tr style="background-color: #d4edda;">
                    <td style="border: 1px solid #ddd; padding: 8px; font-weight: bold;">Evaluated Price for Ranking (ETB)</td>
                    <td style="border: 1px solid #ddd; padding: 8px; text-align: right; font-weight: bold;">{self.evaluated_price:,.2f}</td>
                </tr>
            </table>
            
            <div style="margin-top: 30px; padding: 15px; background-color: #e7f3ff; border-left: 4px solid #2196F3;">
                <h4 style="margin-top: 0;">Preference Calculation Rules (BR-PROC-003):</h4>
                <ul>
                    <li><strong>≥70% local content:</strong> 13.5% preference margin</li>
                    <li><strong>40-70% local content:</strong> 11% preference margin</li>
                    <li><strong>&lt;40% local content:</strong> 0% preference (no margin)</li>
                </ul>
                <p style="margin-bottom: 0;"><strong>Note:</strong> Preference is applied for <em>ranking purposes only</em>. Contract value and payments use the <strong>original bid price</strong> (FR-PROC-018).</p>
            </div>
            
            <div style="margin-top: 20px;">
                <p><strong>Generated:</strong> {fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p><strong>System:</strong> AUTO-015 Domestic Preference Calculation Engine</p>
            </div>
        </div>
        """
        
        # Post to tender chatter for audit trail
        self.tender_id.message_post(
            body=worksheet_html,
            subject=f'Domestic Preference Worksheet: {self.supplier_id.name}',
            message_type='comment'
        )
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Preference Calculation Worksheet',
            'res_model': 'mesob.procurement.tender',
            'res_id': self.tender_id.id,
            'view_mode': 'form',
            'target': 'current',
        }

    @api.constrains("supplier_id")
    def _check_supplier_status(self):
        for rec in self:
            if rec.supplier_id.fppa_blacklisted:
                raise ValidationError(f"Supplier {rec.supplier_id.name} is blacklisted and cannot participate (FR-PROC-012).")


class MesobProcurementBidLine(models.Model):
    """Individual item lines within a bid submission."""
    
    _name = "mesob.procurement.bid.line"
    _description = "Bid Line Item"
    
    bid_id = fields.Many2one('mesob.procurement.bid', string='Bid', required=True, ondelete='cascade')
    item_id = fields.Many2one('mesob.inventory.item', string='Item', required=True)
    quantity = fields.Float(string='Quantity', required=True, default=1.0)
    unit_price = fields.Float(string='Unit Price (ETB)', required=True)
    total_price = fields.Float(string='Total Price (ETB)', compute='_compute_total_price', store=True)
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure')
    
    @api.depends('quantity', 'unit_price')
    def _compute_total_price(self):
        for line in self:
            line.total_price = line.quantity * line.unit_price


class MesobProcurementContract(models.Model):
    """Contract Formation & Management - FR-PROC-021."""

    _name = "mesob.procurement.contract"
    _description = "Procurement Contract"
    _order = "id desc"

    name = fields.Char(string="Contract Number", required=True, copy=False)
    supplier_id = fields.Many2one(
        "res.partner",
        string="Supplier",
        required=True,
        domain=[("fppa_blacklisted", "=", False)],
    )
    lot_id = fields.Many2one("mesob.procurement.plan.lot", string="APP Lot Reference", required=True)
    total_value = fields.Float(string="Total Contract Value (ETB)", required=True)
    delivery_schedule = fields.Text(string="Delivery Schedule")
    payment_terms = fields.Text(string="Payment Terms")
    
    # ── AUTO-019: Performance Security & Guarantees ────────────────
    performance_security_recorded = fields.Boolean(
        string="Performance Security Recorded",
        default=False,
    )
    performance_security_details = fields.Text(string="Performance Security Details")
    performance_security_amount = fields.Float(
        string="Performance Security Amount (ETB)",
        help="AUTO-019: Typically 5-10% of contract value"
    )
    performance_security_expiry = fields.Date(
        string="Performance Security Expiry Date",
        help="AUTO-019: Alert will be sent 30/15/7 days before expiry"
    )
    performance_security_alert_sent = fields.Selection([
        ('none', 'No Alert Sent'),
        ('30days', '30 Days Alert Sent'),
        ('15days', '15 Days Alert Sent'),
        ('7days', '7 Days Alert Sent'),
        ('expired', 'Expiry Alert Sent'),
    ], string='Security Alert Status', default='none')
    
    advance_payment = fields.Float(
        string="Advance Payment (%)",
        default=0.0,
        help="Capped at maximum 30% for goods (BR-PROC-006).",
    )
    advance_payment_guarantee = fields.Boolean(
        string="Advance Payment Guarantee Recorded",
        default=False,
    )
    advance_payment_guarantee_amount = fields.Float(
        string="Advance Payment Guarantee Amount (ETB)",
        compute='_compute_advance_payment_guarantee_amount',
        store=True,
        help="AUTO-019: Must equal advance payment amount"
    )
    advance_payment_guarantee_expiry = fields.Date(
        string="Advance Payment Guarantee Expiry",
        help="AUTO-019: Alert will be sent before expiry"
    )
    advance_payment_guarantee_alert_sent = fields.Selection([
        ('none', 'No Alert Sent'),
        ('30days', '30 Days Alert Sent'),
        ('15days', '15 Days Alert Sent'),
        ('7days', '7 Days Alert Sent'),
        ('expired', 'Expiry Alert Sent'),
    ], string='Guarantee Alert Status', default='none')
    
    # ── AUTO-020: Delivery Milestones ──────────────────────────────
    milestone_ids = fields.One2many(
        'mesob.contract.milestone',
        'contract_id',
        string='Delivery Milestones',
        help='AUTO-020: Auto-tracked delivery milestones'
    )
    
    # ── AUTO-031: Price Adjustment ──────────────────────────────────
    has_price_adjustment = fields.Boolean(
        string="Price Adjustment Clause",
        default=False,
        help="AUTO-031: Contract allows price adjustments per FR-PROC-035"
    )
    base_price_indices = fields.Text(
        string="Base Price Indices",
        help="AUTO-031: JSON format: {fuel: 100, steel: 150, labor: 120}"
    )
    price_adjustment_formula = fields.Text(
        string="Price Adjustment Formula",
        help="AUTO-031: e.g., 40% fuel + 30% steel + 30% labor"
    )
    
    # ── AUTO-032: Retention & Warranty ─────────────────────────────
    retention_percentage = fields.Float(
        string="Retention Percentage (%)",
        default=10.0,
        help="AUTO-032: Holdback per payment (max 10% per FR-PROC-037)"
    )
    cumulative_retention = fields.Float(
        string="Cumulative Retention Held (ETB)",
        default=0.0,
        readonly=True,
        help="AUTO-032: Total retention held from payments"
    )
    retention_released = fields.Boolean(
        string="Retention Released",
        default=False,
        help="AUTO-032: True when retention released to supplier"
    )
    retention_release_date = fields.Date(
        string="Retention Release Date",
        readonly=True,
        help="AUTO-032: Date retention was released"
    )
    warranty_period_months = fields.Integer(
        string="Warranty Period (Months)",
        default=12,
        help="AUTO-032: Defects liability period"
    )
    warranty_expiry_date = fields.Date(
        string="Warranty Expiry Date",
        compute='_compute_warranty_expiry',
        store=True,
        help="AUTO-032: Contract close date + warranty months"
    )
    defects_cleared = fields.Boolean(
        string="Defects Liability Cleared",
        default=False,
        help="AUTO-032: Procurement officer confirms no defects"
    )
    
    cumulative_variation_total = fields.Float(
        string="Cumulative Variations Total (ETB)",
        default=0.0,
    )
    
    contract_sign_date = fields.Date(
        string="Contract Signature Date",
        help="Date contract was signed"
    )
    contract_close_date = fields.Date(
        string="Contract Close Date",
        help="Date final delivery completed"
    )
    
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("signed", "Signed"),
            ("variation", "In Variation / Amendment"),
            ("closed", "Closed"),
        ],
        string="Contract Status",
        default="draft",
        required=True,
    )

    @api.depends('advance_payment', 'total_value')
    def _compute_advance_payment_guarantee_amount(self):
        """AUTO-019: Calculate required advance payment guarantee amount."""
        for rec in self:
            if rec.advance_payment > 0:
                rec.advance_payment_guarantee_amount = rec.total_value * (rec.advance_payment / 100.0)
            else:
                rec.advance_payment_guarantee_amount = 0.0
    
    @api.depends('contract_close_date', 'warranty_period_months')
    def _compute_warranty_expiry(self):
        """AUTO-032: Calculate warranty expiry date."""
        for rec in self:
            if rec.contract_close_date and rec.warranty_period_months:
                from dateutil.relativedelta import relativedelta
                rec.warranty_expiry_date = rec.contract_close_date + relativedelta(months=rec.warranty_period_months)
            else:
                rec.warranty_expiry_date = False
    
    @api.constrains("advance_payment", "advance_payment_guarantee")
    def _check_advance_payment_rules(self):
        for rec in self:
            if rec.advance_payment > 30.0:
                raise ValidationError("Advance payment cannot exceed 30% of contract value for goods contracts (BR-PROC-006).")
            if rec.advance_payment > 0.0 and not rec.advance_payment_guarantee:
                raise ValidationError("Advance payment is blocked until an advance payment guarantee of equivalent value is recorded (FR-PROC-022).")

    def action_sign_contract(self):
        """Sign contract validation (FR-PROC-021)."""
        for rec in self:
            # Check complaints during standstill (FR-PROC-020)
            open_complaints = self.env["mesob.procurement.complaint"].search([
                ("lot_id", "=", rec.lot_id.id),
                ("state", "=", "open")
            ])
            if open_complaints:
                raise UserError("Contract signature is blocked. There is an active open complaint registered during the standstill period (FR-PROC-020).")
            
            # Check performance security
            if rec.total_value >= 500000.0 and not rec.performance_security_recorded:
                raise UserError("Performance security must be recorded for contracts of ETB 500,000 or above before signature (FR-PROC-021).")
            
            rec.state = "signed"
        return True
    
    @api.model
    def _cron_check_guarantee_expiry(self):
        """AUTO-019: Scheduled job to check performance security & advance payment guarantee expiry.
        
        Runs daily to send alerts at 30, 15, 7 days before expiry (FR-PROC-022).
        Blocks payments if guarantees expire before delivery complete.
        """
        today = fields.Date.today()
        from datetime import timedelta
        
        active_contracts = self.search([
            ('state', 'in', ['signed', 'variation']),
        ])
        
        for contract in active_contracts:
            # Check Performance Security expiry
            if contract.performance_security_recorded and contract.performance_security_expiry:
                days_until_expiry = (contract.performance_security_expiry - today).days
                
                if days_until_expiry <= 0 and contract.performance_security_alert_sent != 'expired':
                    contract._send_security_expiry_alert('expired', days_until_expiry)
                    contract.performance_security_alert_sent = 'expired'
                elif days_until_expiry <= 7 and contract.performance_security_alert_sent not in ['7days', 'expired']:
                    contract._send_security_expiry_alert('7days', days_until_expiry)
                    contract.performance_security_alert_sent = '7days'
                elif days_until_expiry <= 15 and contract.performance_security_alert_sent not in ['15days', '7days', 'expired']:
                    contract._send_security_expiry_alert('15days', days_until_expiry)
                    contract.performance_security_alert_sent = '15days'
                elif days_until_expiry <= 30 and contract.performance_security_alert_sent == 'none':
                    contract._send_security_expiry_alert('30days', days_until_expiry)
                    contract.performance_security_alert_sent = '30days'
            
            # Check Advance Payment Guarantee expiry
            if contract.advance_payment_guarantee and contract.advance_payment_guarantee_expiry:
                days_until_expiry = (contract.advance_payment_guarantee_expiry - today).days
                
                if days_until_expiry <= 0 and contract.advance_payment_guarantee_alert_sent != 'expired':
                    contract._send_guarantee_expiry_alert('expired', days_until_expiry)
                    contract.advance_payment_guarantee_alert_sent = 'expired'
                elif days_until_expiry <= 7 and contract.advance_payment_guarantee_alert_sent not in ['7days', 'expired']:
                    contract._send_guarantee_expiry_alert('7days', days_until_expiry)
                    contract.advance_payment_guarantee_alert_sent = '7days'
                elif days_until_expiry <= 15 and contract.advance_payment_guarantee_alert_sent not in ['15days', '7days', 'expired']:
                    contract._send_guarantee_expiry_alert('15days', days_until_expiry)
                    contract.advance_payment_guarantee_alert_sent = '15days'
                elif days_until_expiry <= 30 and contract.advance_payment_guarantee_alert_sent == 'none':
                    contract._send_guarantee_expiry_alert('30days', days_until_expiry)
                    contract.advance_payment_guarantee_alert_sent = '30days'
        
        _logger.info(f"AUTO-019: Guarantee expiry check completed - {len(active_contracts)} contracts scanned")
    
    def _send_security_expiry_alert(self, alert_type, days_remaining):
        """AUTO-019: Send performance security expiry alert."""
        self.ensure_one()
        
        alert_colors = {
            '30days': ('#fff3cd', '#856404', '⚠️', 'WARNING'),
            '15days': ('#fff3cd', '#ff9800', '⚠️', 'URGENT'),
            '7days': ('#f8d7da', '#dc3545', '🚨', 'CRITICAL'),
            'expired': ('#f8d7da', '#721c24', '❌', 'EXPIRED'),
        }
        
        bg_color, text_color, icon, severity = alert_colors.get(alert_type, alert_colors['30days'])
        days_text = f"{days_remaining} days" if days_remaining > 0 else "EXPIRED"
        
        procurement_users = self.env.ref('mesob_inventory_base.group_mesob_procurement_officer', raise_if_not_found=False)
        
        if procurement_users and procurement_users.users:
            self.message_post(
                body=f"""<div style="background-color: {bg_color}; border-left: 4px solid {text_color}; padding: 15px;">
                    <h3 style="color: {text_color}; margin-top: 0;">{icon} AUTO-019: Performance Security {severity}</h3>
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
                            <td style="padding: 5px 0;"><strong>Security Amount:</strong></td>
                            <td style="padding: 5px 0; text-align: right;">ETB {self.performance_security_amount:,.2f}</td>
                        </tr>
                        <tr style="background-color: {bg_color};">
                            <td style="padding: 5px 0;"><strong>Expiry Date:</strong></td>
                            <td style="padding: 5px 0; text-align: right; font-weight: bold;">{self.performance_security_expiry}</td>
                        </tr>
                        <tr>
                            <td style="padding: 5px 0;"><strong>Days Remaining:</strong></td>
                            <td style="padding: 5px 0; text-align: right; color: {text_color}; font-weight: bold; font-size: 18px;">{days_text}</td>
                        </tr>
                    </table>
                    <div style="background-color: #fff; padding: 10px; border-radius: 4px; margin-top: 15px;">
                        <p style="margin: 0;"><strong>⚠️ ACTION REQUIRED (FR-PROC-022):</strong></p>
                        <p style="margin: 5px 0 0 0;">Contact supplier to renew performance security before expiry or risk will not be covered.</p>
                    </div>
                </div>""",
                subject=f'{icon} {severity}: Performance Security Expiry - {self.name}',
                message_type='notification',
                partner_ids=procurement_users.users.mapped('partner_id').ids
            )
    
    def _send_guarantee_expiry_alert(self, alert_type, days_remaining):
        """AUTO-019: Send advance payment guarantee expiry alert."""
        self.ensure_one()
        
        alert_colors = {
            '30days': ('#fff3cd', '#856404', '⚠️', 'WARNING'),
            '15days': ('#fff3cd', '#ff9800', '⚠️', 'URGENT'),
            '7days': ('#f8d7da', '#dc3545', '🚨', 'CRITICAL'),
            'expired': ('#f8d7da', '#721c24', '❌', 'EXPIRED - PAYMENT BLOCKED'),
        }
        
        bg_color, text_color, icon, severity = alert_colors.get(alert_type, alert_colors['30days'])
        days_text = f"{days_remaining} days" if days_remaining > 0 else "EXPIRED"
        
        procurement_users = self.env.ref('mesob_inventory_base.group_mesob_procurement_officer', raise_if_not_found=False)
        
        if procurement_users and procurement_users.users:
            self.message_post(
                body=f"""<div style="background-color: {bg_color}; border-left: 4px solid {text_color}; padding: 15px;">
                    <h3 style="color: {text_color}; margin-top: 0;">{icon} AUTO-019: Advance Payment Guarantee {severity}</h3>
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
                            <td style="padding: 5px 0;"><strong>Guarantee Amount:</strong></td>
                            <td style="padding: 5px 0; text-align: right;">ETB {self.advance_payment_guarantee_amount:,.2f}</td>
                        </tr>
                        <tr style="background-color: {bg_color};">
                            <td style="padding: 5px 0;"><strong>Expiry Date:</strong></td>
                            <td style="padding: 5px 0; text-align: right; font-weight: bold;">{self.advance_payment_guarantee_expiry}</td>
                        </tr>
                        <tr>
                            <td style="padding: 5px 0;"><strong>Days Remaining:</strong></td>
                            <td style="padding: 5px 0; text-align: right; color: {text_color}; font-weight: bold; font-size: 18px;">{days_text}</td>
                        </tr>
                    </table>
                    <div style="background-color: #f8d7da; padding: 10px; border-radius: 4px; margin-top: 15px;">
                        <p style="margin: 0;"><strong>🚨 CRITICAL (BR-PROC-006, FR-PROC-022):</strong></p>
                        <p style="margin: 5px 0 0 0;">Advance payment is BLOCKED if guarantee expires! Contact supplier immediately for renewal.</p>
                    </div>
                </div>""",
                subject=f'{icon} {severity}: Advance Payment Guarantee - {self.name}',
                message_type='notification',
                partner_ids=procurement_users.users.mapped('partner_id').ids
            )
    
    def action_release_retention(self):
        """AUTO-032: Release retention to supplier (FR-PROC-037).
        
        Conditions:
        - Contract closed (final Model 19 confirmed)
        - Warranty period elapsed
        - No defects liability issues
        - Procurement officer clearance
        """
        self.ensure_one()
        
        # Validation checks
        if self.state != 'closed':
            raise UserError("Retention can only be released for closed contracts.")
        
        if not self.warranty_expiry_date:
            raise UserError("Warranty period not configured. Cannot determine if warranty has elapsed.")
        
        if fields.Date.today() < self.warranty_expiry_date:
            raise UserError(
                f"Warranty period has not elapsed yet. "
                f"Warranty expires on {self.warranty_expiry_date}. "
                f"Cannot release retention until warranty period complete."
            )
        
        if not self.defects_cleared:
            raise UserError(
                "Procurement officer must confirm defects liability clearance before retention release. "
                "Please check 'Defects Liability Cleared' field."
            )
        
        if self.retention_released:
            raise UserError("Retention has already been released.")
        
        if self.cumulative_retention <= 0:
            raise UserError("No retention amount to release.")
        
        # Release retention
        self.write({
            'retention_released': True,
            'retention_release_date': fields.Date.today()
        })
        
        # Log to chatter
        self.message_post(
            body=f"""<div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px;">
                <h3 style="color: #155724;">✅ AUTO-032: Retention Released</h3>
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
                        <td style="padding: 5px 0;"><strong>Retention Amount:</strong></td>
                        <td style="padding: 5px 0; text-align: right; font-weight: bold; color: #28a745; font-size: 18px;">ETB {self.cumulative_retention:,.2f}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 0;"><strong>Release Date:</strong></td>
                        <td style="padding: 5px 0; text-align: right;">{self.retention_release_date}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 0;"><strong>Warranty Expiry:</strong></td>
                        <td style="padding: 5px 0; text-align: right;">{self.warranty_expiry_date}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 0;"><strong>Released By:</strong></td>
                        <td style="padding: 5px 0; text-align: right;">{self.env.user.name}</td>
                    </tr>
                </table>
                <div style="background-color: #fff; padding: 10px; border-radius: 4px; margin-top: 15px;">
                    <p style="margin: 0;"><strong>✓ Conditions Met (FR-PROC-037):</strong></p>
                    <ul style="margin: 5px 0 0 0;">
                        <li>Contract closed with final Model 19 confirmed</li>
                        <li>Warranty period ({self.warranty_period_months} months) elapsed</li>
                        <li>Defects liability clearance confirmed</li>
                        <li>Procurement officer approval obtained</li>
                    </ul>
                </div>
            </div>""",
            subject=f'Retention Released: ETB {self.cumulative_retention:,.2f}',
            message_type='comment'
        )
        
        _logger.info(
            f"AUTO-032: Retention released for contract {self.name} - "
            f"Amount: ETB {self.cumulative_retention:,.2f}, Supplier: {self.supplier_id.name}"
        )
        
        return True


class MesobContractMilestone(models.Model):
    """AUTO-020: Contract Delivery Milestone Tracking.
    
    Auto-tracks delivery milestones from contract schedule.
    Sends alerts 14, 7, 3 days before due date.
    Flags overdue milestones with days-late counter.
    """
    
    _name = 'mesob.contract.milestone'
    _description = 'Contract Delivery Milestone'
    _order = 'due_date asc, id'
    
    contract_id = fields.Many2one(
        'mesob.procurement.contract',
        string='Contract',
        required=True,
        ondelete='cascade'
    )
    
    name = fields.Char(
        string='Milestone Description',
        required=True,
        help='e.g., "First Batch Delivery - 100 units"'
    )
    
    due_date = fields.Date(
        string='Due Date',
        required=True,
        help='Contract delivery deadline'
    )
    
    actual_date = fields.Date(
        string='Actual Delivery Date',
        help='Actual date items were received (Model 19 date)'
    )
    
    status = fields.Selection([
        ('upcoming', 'Upcoming'),
        ('approaching', 'Approaching (14 days)'),
        ('urgent', 'Urgent (7 days)'),
        ('critical', 'Critical (3 days)'),
        ('overdue', 'Overdue'),
        ('completed', 'Completed'),
    ], string='Status', compute='_compute_status', store=True)
    
    days_until_due = fields.Integer(
        string='Days Until Due',
        compute='_compute_status',
        store=True,
        help='Negative if overdue'
    )
    
    alert_14days_sent = fields.Boolean(string='14-Day Alert Sent', default=False)
    alert_7days_sent = fields.Boolean(string='7-Day Alert Sent', default=False)
    alert_3days_sent = fields.Boolean(string='3-Day Alert Sent', default=False)
    alert_overdue_sent = fields.Boolean(string='Overdue Alert Sent', default=False)
    
    notes = fields.Text(string='Notes')
    
    @api.depends('due_date', 'actual_date')
    def _compute_status(self):
        """AUTO-020: Compute milestone status and days until due."""
        today = fields.Date.today()
        
        for milestone in self:
            if milestone.actual_date:
                milestone.status = 'completed'
                milestone.days_until_due = 0
                continue
            
            if not milestone.due_date:
                milestone.status = 'upcoming'
                milestone.days_until_due = 999
                continue
            
            days_diff = (milestone.due_date - today).days
            milestone.days_until_due = days_diff
            
            if days_diff < 0:
                milestone.status = 'overdue'
            elif days_diff <= 3:
                milestone.status = 'critical'
            elif days_diff <= 7:
                milestone.status = 'urgent'
            elif days_diff <= 14:
                milestone.status = 'approaching'
            else:
                milestone.status = 'upcoming'
    
    @api.model
    def _cron_check_milestone_alerts(self):
        """AUTO-020: Scheduled job to check milestones and send alerts.
        
        Runs daily to send alerts at 14, 7, 3 days before due date.
        Flags overdue milestones with escalation.
        """
        today = fields.Date.today()
        
        upcoming_milestones = self.search([
            ('actual_date', '=', False),  # Not completed yet
        ])
        
        for milestone in upcoming_milestones:
            days_until = milestone.days_until_due
            
            # Overdue alert
            if days_until < 0 and not milestone.alert_overdue_sent:
                milestone._send_milestone_alert('overdue', days_until)
                milestone.alert_overdue_sent = True
            
            # 3-day alert
            elif days_until <= 3 and days_until >= 0 and not milestone.alert_3days_sent:
                milestone._send_milestone_alert('3days', days_until)
                milestone.alert_3days_sent = True
            
            # 7-day alert
            elif days_until <= 7 and days_until > 3 and not milestone.alert_7days_sent:
                milestone._send_milestone_alert('7days', days_until)
                milestone.alert_7days_sent = True
            
            # 14-day alert
            elif days_until <= 14 and days_until > 7 and not milestone.alert_14days_sent:
                milestone._send_milestone_alert('14days', days_until)
                milestone.alert_14days_sent = True
        
        _logger.info(f"AUTO-020: Milestone alert check completed - {len(upcoming_milestones)} milestones scanned")
    
    def _send_milestone_alert(self, alert_type, days_until):
        """AUTO-020: Send milestone delivery alert."""
        self.ensure_one()
        
        alert_configs = {
            '14days': ('#d1ecf1', '#0c5460', '📅', 'REMINDER', 'Delivery due in 14 days'),
            '7days': ('#fff3cd', '#856404', '⚠️', 'WARNING', 'Delivery due in 7 days'),
            '3days': ('#f8d7da', '#dc3545', '🚨', 'URGENT', 'Delivery due in 3 days'),
            'overdue': ('#f8d7da', '#721c24', '❌', 'OVERDUE', f'Delivery {abs(days_until)} days late'),
        }
        
        bg_color, text_color, icon, severity, message = alert_configs.get(alert_type, alert_configs['14days'])
        
        # Send to procurement officer and supplier (if email available)
        procurement_users = self.env.ref('mesob_inventory_base.group_mesob_procurement_officer', raise_if_not_found=False)
        
        recipients = []
        if procurement_users and procurement_users.users:
            recipients.extend(procurement_users.users.mapped('partner_id').ids)
        
        # Add supplier if email available
        if self.contract_id.supplier_id.email:
            recipients.append(self.contract_id.supplier_id.id)
        
        if recipients:
            self.contract_id.message_post(
                body=f"""<div style="background-color: {bg_color}; border-left: 4px solid {text_color}; padding: 15px;">
                    <h3 style="color: {text_color}; margin-top: 0;">{icon} AUTO-020: Delivery Milestone {severity}</h3>
                    <table style="width: 100%;">
                        <tr>
                            <td style="padding: 5px 0;"><strong>Contract:</strong></td>
                            <td style="padding: 5px 0; text-align: right;">{self.contract_id.name}</td>
                        </tr>
                        <tr>
                            <td style="padding: 5px 0;"><strong>Supplier:</strong></td>
                            <td style="padding: 5px 0; text-align: right;">{self.contract_id.supplier_id.name}</td>
                        </tr>
                        <tr>
                            <td style="padding: 5px 0;"><strong>Milestone:</strong></td>
                            <td style="padding: 5px 0; text-align: right;">{self.name}</td>
                        </tr>
                        <tr style="background-color: {bg_color};">
                            <td style="padding: 5px 0;"><strong>Due Date:</strong></td>
                            <td style="padding: 5px 0; text-align: right; font-weight: bold;">{self.due_date}</td>
                        </tr>
                        <tr>
                            <td style="padding: 5px 0;"><strong>Status:</strong></td>
                            <td style="padding: 5px 0; text-align: right; color: {text_color}; font-weight: bold;">{message}</td>
                        </tr>
                    </table>
                    <div style="background-color: #fff; padding: 10px; border-radius: 4px; margin-top: 15px;">
                        <p style="margin: 0;"><strong>FR-PROC-024: Delivery Tracking</strong></p>
                        <p style="margin: 5px 0 0 0;">Please ensure timely delivery per contract schedule. Delays may trigger liquidated damages (AUTO-024).</p>
                    </div>
                </div>""",
                subject=f'{icon} {severity}: Delivery Milestone - {self.name}',
                message_type='notification',
                partner_ids=recipients
            )
        
        _logger.info(f"AUTO-020: {severity} alert sent for milestone {self.name}")
    
    def action_mark_completed(self):
        """Mark milestone as completed with actual delivery date."""
        self.ensure_one()
        
        if self.actual_date:
            raise UserError("Milestone is already marked as completed.")
        
        self.actual_date = fields.Date.today()
        
        self.contract_id.message_post(
            body=f"""<div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px;">
                <h3 style="color: #155724;">✅ Milestone Completed</h3>
                <p><strong>Milestone:</strong> {self.name}</p>
                <p><strong>Due Date:</strong> {self.due_date}</p>
                <p><strong>Actual Date:</strong> {self.actual_date}</p>
                <p><strong>Days {'Early' if self.days_until_due > 0 else 'Late'}:</strong> {abs(self.days_until_due)}</p>
            </div>""",
            subject=f'Milestone Completed: {self.name}'
        )
        
        return True


class MesobProcurementOrder(models.Model):
    """Standard Purchase Order mapped to APP and Contracts - FR-PROC-026."""

    _name = "mesob.procurement.order"
    _description = "Purchase Order"
    _inherit = ["mail.thread"]
    _order = "date_order desc, id desc"

    name = fields.Char(
        string="PO Reference",
        required=True,
        copy=False,
        default="New",
        readonly=True,
    )
    plan_lot_id = fields.Many2one("mesob.procurement.plan.lot", string="APP Lot Reference", required=True)
    contract_id = fields.Many2one("mesob.procurement.contract", string="Contract Link")
    supplier_id = fields.Many2one(
        "res.partner",
        string="Supplier",
        required=True,
        domain=[("is_blacklisted", "=", False)],
        tracking=True,
    )
    date_order = fields.Date(string="Order Date", default=fields.Date.today, required=True)

    @api.onchange("plan_lot_id")
    def _onchange_plan_lot_id(self):
        """Auto-populate PO lines from the consolidated needs of the selected APP Lot (Section 4.13.G)."""
        if self.plan_lot_id:
            new_lines = []
            for need in self.plan_lot_id.need_ids:
                line_vals = {
                    "item_id": need.item_id.id if need.item_id else False,
                    "major_classification_id": need.major_classification_id.id if need.major_classification_id else False,
                    "sub_classification_id": need.sub_classification_id.id if need.sub_classification_id else False,
                    "quantity": need.quantity,
                    "price_unit": need.estimated_unit_price,
                    "description": need.item_id.name if need.item_id else f"{need.major_classification_id.name or ''} {need.sub_classification_id.name or ''}",
                }
                new_lines.append((0, 0, line_vals))
            self.line_ids = new_lines
    inspection_type = fields.Selection(
        [
            ("storekeeper", "Storekeeper (Simple Items)"),
            ("technical", "Technical Staff (Technical Items)"),
            ("independent", "Independent / Supplier-site"),
        ],
        string="Inspection Type",
        default="storekeeper",
        required=True,
        help="Assign inspection type for receiving team (FR-PROC-031).",
    )
    line_ids = fields.One2many(
        "mesob.procurement.order.line",
        "order_id",
        string="Purchase Order Lines",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("pending", "Pending Approval"),
            ("approved", "Approved"),
            ("sent", "Sent to Supplier"),
            ("partially_received", "Partially Received"),
            ("fully_received", "Fully Received"),
            ("closed", "Closed"),
            ("cancelled", "Cancelled"),
        ],
        string="Status",
        default="draft",
        required=True,
        tracking=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = f"PO/{self.env['ir.sequence'].next_by_code('mesob.procurement.order') or '001'}"
        return super().create(vals_list)

    @api.constrains("supplier_id")
    def _check_supplier_validity(self):
        for rec in self:
            print(f"\n\nDEBUG: Checking supplier {rec.supplier_id.name}, fppa_blacklisted: {rec.supplier_id.fppa_blacklisted}\n\n")
            if rec.supplier_id.fppa_blacklisted:
                raise ValidationError(f"Hard-Stop: Supplier '{rec.supplier_id.name}' is currently blacklisted! (FR-PROC-012)")
            if rec.supplier_id.registration_expiry_date and rec.supplier_id.registration_expiry_date < fields.Date.today():
                raise ValidationError(f"Hard-Stop: Supplier '{rec.supplier_id.name}' registration license has expired! (FR-PROC-012)")

    def action_submit(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError("Only draft Purchase Orders can be submitted.")
            rec.state = "pending"

    def action_approve(self):
        """Authorize the Purchase Order.
        
        AUTO-025: Enhanced with automatic receiving handoff notification.
        AUTO-026: Enhanced with automatic inspection type assignment.
        """
        for rec in self:
            if rec.state != "pending":
                raise UserError("Only pending Purchase Orders can be approved.")
            
            # Check Surplus block business rule (BR-PROC-008 / AC-PROC-006)
            for line in rec.line_ids:
                if line.item_id.is_surplus:
                    raise UserError(f"Approval Blocked: Stock item code '{line.item_id.item_code}' is currently flagged as surplus in the Disposal system! (BR-PROC-008)")

            rec.state = "approved"
            
            # AUTO-026: Auto-assign inspection type based on item classifications
            rec._auto_assign_inspection_type()
            
            # AUTO-025: Notify Storekeeper of expected delivery
            rec._send_receiving_handoff_notification()
        
        return True
    
    def _auto_assign_inspection_type(self):
        """AUTO-026: Auto-assign inspection type based on item classification (FR-PROC-031).
        
        Classification-based inspection rules:
        - 4401-4403 (office supplies, stationery, cleaning) → Storekeeper inspection
        - 4405 (fuel), 4411 (drugs/chemicals) → Technical staff inspection
        - 4413 (vehicles), 4414 (equipment) → User technical staff + Storekeeper
        - Default → Storekeeper inspection
        
        Officer can override with documented reason.
        """
        self.ensure_one()
        
        # Analyze items in PO to determine inspection type
        major_codes = []
        for line in self.line_ids:
            if line.item_id and line.item_id.classification_id:
                code = line.item_id.classification_id.code
                if code and code not in major_codes:
                    major_codes.append(code)
        
        if not major_codes:
            self.inspection_type = 'storekeeper'
            return
        
        # Apply classification-based rules (FR-PROC-031)
        requires_technical = False
        requires_independent = False
        
        for code in major_codes:
            # Fuel, drugs, chemicals require technical inspection
            if code in ['4405', '4411']:
                requires_technical = True
            
            # Vehicles, heavy equipment require independent/user technical staff
            elif code in ['4413', '4414']:
                requires_independent = True
        
        # Assign inspection type based on highest requirement
        if requires_independent:
            self.inspection_type = 'independent'
            _logger.info(f"AUTO-026: PO {self.name} assigned 'independent' inspection (vehicles/equipment)")
        elif requires_technical:
            self.inspection_type = 'technical'
            _logger.info(f"AUTO-026: PO {self.name} assigned 'technical' inspection (fuel/chemicals)")
        else:
            self.inspection_type = 'storekeeper'
            _logger.info(f"AUTO-026: PO {self.name} assigned 'storekeeper' inspection (standard supplies)")
        
        # Log assignment to chatter
        inspection_reason = {
            'independent': 'Contains vehicles (4413) or heavy equipment (4414)',
            'technical': 'Contains fuel (4405) or drugs/chemicals (4411)',
            'storekeeper': 'Standard office supplies and materials'
        }
        
        self.message_post(
            body=f"""<div style="background-color: #e7f3ff; border-left: 4px solid #2196F3; padding: 15px;">
                <h4>AUTO-026: Inspection Type Auto-Assigned</h4>
                <p><strong>Inspection Type:</strong> {dict(self._fields['inspection_type'].selection).get(self.inspection_type)}</p>
                <p><strong>Reason:</strong> {inspection_reason.get(self.inspection_type)}</p>
                <p><strong>Item Classifications:</strong> {', '.join(major_codes)}</p>
                <p><em>Officer can override this assignment with documented reason if needed (FR-PROC-031).</em></p>
            </div>""",
            subject='Inspection Type Auto-Assigned',
            message_type='comment'
        )
    
    def _send_receiving_handoff_notification(self):
        """AUTO-025: Notify Storekeeper of expected delivery (FR-PROC-030).
        
        Sends comprehensive notification with:
        - Expected items (codes, descriptions, quantities)
        - Supplier name and contact info
        - Expected delivery date
        - Assigned inspection type
        - Preparation checklist
        
        Enables proactive receiving area preparation.
        """
        self.ensure_one()
        
        # Build items table
        items_html = '<table style="width: 100%; border-collapse: collapse; margin: 15px 0;">'
        items_html += '''<thead style="background-color: #f8f9fa;">
            <tr>
                <th style="border: 1px solid #dee2e6; padding: 8px; text-align: left;">Item Code</th>
                <th style="border: 1px solid #dee2e6; padding: 8px; text-align: left;">Description</th>
                <th style="border: 1px solid #dee2e6; padding: 8px; text-align: right;">Quantity</th>
                <th style="border: 1px solid #dee2e6; padding: 8px; text-align: left;">Unit</th>
            </tr>
        </thead><tbody>'''
        
        for line in self.line_ids:
            items_html += f'''<tr>
                <td style="border: 1px solid #dee2e6; padding: 8px;"><strong>{line.item_id.item_code if line.item_id else 'N/A'}</strong></td>
                <td style="border: 1px solid #dee2e6; padding: 8px;">{line.description or (line.item_id.name if line.item_id else 'N/A')}</td>
                <td style="border: 1px solid #dee2e6; padding: 8px; text-align: right;">{line.quantity:.0f}</td>
                <td style="border: 1px solid #dee2e6; padding: 8px;">{line.item_id.uom_id.name if line.item_id and line.item_id.uom_id else 'units'}</td>
            </tr>'''
        
        items_html += '</tbody></table>'
        
        # Calculate expected delivery date (PO date + 30 days lead time)
        from datetime import timedelta
        expected_date = self.date_order + timedelta(days=30) if self.date_order else fields.Date.today()
        
        # Inspection type label
        inspection_label = dict(self._fields['inspection_type'].selection).get(self.inspection_type, 'Storekeeper')
        
        # Build checklist based on inspection type
        if self.inspection_type == 'technical':
            checklist = '''
                <li>✓ Coordinate with technical staff for inspection</li>
                <li>✓ Prepare specialized testing equipment if needed</li>
                <li>✓ Review technical specifications from PO</li>
                <li>✓ Prepare receiving area with safety precautions</li>
                <li>✓ Ensure proper storage conditions are ready</li>
            '''
        elif self.inspection_type == 'independent':
            checklist = '''
                <li>✓ Coordinate with user department technical staff</li>
                <li>✓ Schedule inspection appointment with supplier if needed</li>
                <li>✓ Prepare vehicle/equipment inspection checklist</li>
                <li>✓ Ensure adequate receiving space</li>
                <li>✓ Review contract specifications</li>
            '''
        else:
            checklist = '''
                <li>✓ Prepare receiving inspection checklist (FR-REC-003)</li>
                <li>✓ Clear receiving area for incoming delivery</li>
                <li>✓ Ensure adequate storage space is available</li>
                <li>✓ Review PO specifications</li>
                <li>✓ Prepare Model 19 forms (will be auto-generated)</li>
            '''
        
        # Send notification to Storekeeper group
        storekeeper_users = self.env.ref('mesob_inventory_base.group_mesob_storekeeper', raise_if_not_found=False)
        
        if storekeeper_users and storekeeper_users.users:
            self.message_post(
                body=f"""<div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px;">
                    <h2 style="margin-top: 0;">📦 AUTO-025: Expected Delivery Notification</h2>
                    
                    <div style="background-color: #fff; padding: 15px; border-radius: 4px; margin: 15px 0;">
                        <h3 style="margin-top: 0; color: #856404;">Purchase Order Details</h3>
                        <table style="width: 100%;">
                            <tr>
                                <td style="padding: 5px 0;"><strong>PO Reference:</strong></td>
                                <td style="padding: 5px 0;">{self.name}</td>
                            </tr>
                            <tr>
                                <td style="padding: 5px 0;"><strong>Supplier:</strong></td>
                                <td style="padding: 5px 0;">{self.supplier_id.name}</td>
                            </tr>
                            <tr>
                                <td style="padding: 5px 0;"><strong>Supplier Contact:</strong></td>
                                <td style="padding: 5px 0;">{self.supplier_id.phone or 'N/A'} / {self.supplier_id.email or 'N/A'}</td>
                            </tr>
                            <tr>
                                <td style="padding: 5px 0;"><strong>PO Date:</strong></td>
                                <td style="padding: 5px 0;">{self.date_order}</td>
                            </tr>
                            <tr style="background-color: #fff3cd;">
                                <td style="padding: 5px 0;"><strong>Expected Delivery:</strong></td>
                                <td style="padding: 5px 0; font-weight: bold;">{expected_date}</td>
                            </tr>
                            <tr>
                                <td style="padding: 5px 0;"><strong>Inspection Type:</strong></td>
                                <td style="padding: 5px 0;"><span style="background-color: #17a2b8; color: white; padding: 3px 10px; border-radius: 3px;">{inspection_label}</span></td>
                            </tr>
                        </table>
                    </div>
                    
                    <h3 style="color: #856404;">Expected Items</h3>
                    {items_html}
                    
                    <div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px; margin-top: 20px;">
                        <h3 style="margin-top: 0; color: #155724;">📋 Preparation Checklist</h3>
                        <ul style="margin: 0;">
                            {checklist}
                        </ul>
                    </div>
                    
                    <div style="margin-top: 20px; padding: 15px; background-color: #e7f3ff; border-radius: 4px;">
                        <p style="margin: 0;"><strong>ℹ️ Note:</strong> Model 19 (Goods Received Note) will be auto-generated after successful inspection (AUTO-027).</p>
                    </div>
                    
                    <p style="margin-top: 20px;">
                        <a href="/web#id={self.id}&model=mesob.procurement.order&view_type=form" 
                           style="background-color: #ffc107; color: #000; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                           📋 View Full PO →
                        </a>
                    </p>
                </div>""",
                subject=f'Expected Delivery: PO {self.name} from {self.supplier_id.name}',
                message_type='notification',
                partner_ids=storekeeper_users.users.mapped('partner_id').ids
            )
            
            _logger.info(
                f"AUTO-025: Receiving handoff notification sent to {len(storekeeper_users.users)} Storekeeper users - "
                f"PO {self.name}, {len(self.line_ids)} items, Expected: {expected_date}"
            )
        else:
            _logger.warning("AUTO-025: No Storekeeper users found for receiving notification")
    
    @api.model
    def _cron_check_overdue_pos(self):
        """AUTO-024: Scheduled job to check for overdue POs and send escalation alerts.
        
        Runs daily to check all approved/sent POs for overdue deliveries.
        Escalation schedule:
        - Day 1 overdue: Supplier reminder (if email available)
        - Day 3 overdue: Procurement Officer alert
        - Day 7 overdue: PAO/HOPE escalation with liquidated damages recommendation
        
        Called by scheduled action (cron job).
        """
        today = fields.Date.today()
        
        # Find all POs that are approved or sent but not fully received
        overdue_pos = self.search([
            ('state', 'in', ['approved', 'sent', 'partially_received']),
            ('date_order', '!=', False)
        ])
        
        for po in overdue_pos:
            # Calculate expected delivery date (PO date + 30 days)
            from datetime import timedelta
            expected_date = po.date_order + timedelta(days=30)
            
            if expected_date >= today:
                continue  # Not overdue yet
            
            days_overdue = (today - expected_date).days
            
            if days_overdue == 1:
                # Day 1: Send reminder to supplier
                po._send_supplier_overdue_reminder(days_overdue)
            
            elif days_overdue == 3:
                # Day 3: Alert Procurement Officer
                po._send_procurement_overdue_alert(days_overdue)
            
            elif days_overdue == 7:
                # Day 7: Escalate to PAO/HOPE with LD recommendation
                po._send_pao_overdue_escalation(days_overdue)
            
            elif days_overdue > 7 and days_overdue % 7 == 0:
                # Every 7 days after: Continue escalation
                po._send_pao_overdue_escalation(days_overdue)
        
        _logger.info(f"AUTO-024: Overdue PO check completed - {len(overdue_pos)} POs scanned")
    
    def _send_supplier_overdue_reminder(self, days_overdue):
        """AUTO-024: Send overdue delivery reminder to supplier (Day 1)."""
        self.ensure_one()
        
        if not self.supplier_id.email:
            _logger.warning(f"AUTO-024: Cannot send supplier reminder for PO {self.name} - no email for {self.supplier_id.name}")
            return
        
        # Log to PO chatter
        self.message_post(
            body=f"""<div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px;">
                <h4>⏰ AUTO-024: Overdue Delivery Reminder Sent</h4>
                <p><strong>Days Overdue:</strong> {days_overdue} day(s)</p>
                <p><strong>Supplier:</strong> {self.supplier_id.name}</p>
                <p><strong>Email:</strong> {self.supplier_id.email}</p>
                <p><em>Automated reminder sent to supplier requesting delivery status update.</em></p>
            </div>""",
            subject=f'Overdue Delivery Reminder Sent: Day {days_overdue}',
            message_type='comment'
        )
        
        _logger.info(f"AUTO-024: Day 1 supplier reminder sent for PO {self.name}")
    
    def _send_procurement_overdue_alert(self, days_overdue):
        """AUTO-024: Alert Procurement Officer of overdue delivery (Day 3)."""
        self.ensure_one()
        
        procurement_users = self.env.ref('mesob_inventory_base.group_mesob_procurement_officer', raise_if_not_found=False)
        
        if procurement_users and procurement_users.users:
            self.message_post(
                body=f"""<div style="background-color: #fff3cd; border-left: 4px solid #ff9800; padding: 15px;">
                    <h3>⚠️ AUTO-024: Overdue PO Alert</h3>
                    <p><strong>PO Reference:</strong> {self.name}</p>
                    <p><strong>Supplier:</strong> {self.supplier_id.name}</p>
                    <p><strong>PO Date:</strong> {self.date_order}</p>
                    <p><strong>Days Overdue:</strong> <span style="color: #ff9800; font-weight: bold; font-size: 18px;">{days_overdue} days</span></p>
                    <hr/>
                    <h4>Recommended Actions:</h4>
                    <ul>
                        <li>Contact supplier for delivery status update</li>
                        <li>Request revised delivery schedule</li>
                        <li>Document supplier response</li>
                        <li>Consider escalation if no response</li>
                    </ul>
                    <p style="margin-top: 15px;">
                        <a href="/web#id={self.id}&model=mesob.procurement.order&view_type=form" 
                           style="background-color: #ff9800; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                           Review PO →
                        </a>
                    </p>
                </div>""",
                subject=f'OVERDUE: PO {self.name} - {days_overdue} days late',
                message_type='notification',
                partner_ids=procurement_users.users.mapped('partner_id').ids
            )
            
            _logger.info(f"AUTO-024: Day 3 procurement alert sent for PO {self.name}")
    
    def _send_pao_overdue_escalation(self, days_overdue):
        """AUTO-024: Escalate to PAO/HOPE with liquidated damages recommendation (Day 7+)."""
        self.ensure_one()
        
        # Calculate potential liquidated damages (1/1000 per working day, max 10%)
        # Simplified: assume all days are working days
        contract_value = sum(line.price_subtotal for line in self.line_ids)
        ld_rate = 0.001  # 1/1000 per day per FR-PROC-036
        ld_amount = contract_value * ld_rate * days_overdue
        ld_cap = contract_value * 0.10  # 10% cap
        
        if ld_amount > ld_cap:
            ld_amount = ld_cap
        
        pao_users = self.env.ref('mesob_inventory_base.group_mesob_pao', raise_if_not_found=False)
        
        if pao_users and pao_users.users:
            self.message_post(
                body=f"""<div style="background-color: #f8d7da; border-left: 4px solid #dc3545; padding: 15px;">
                    <h2 style="color: #721c24; margin-top: 0;">🚨 AUTO-024: CRITICAL - Overdue PO Escalation</h2>
                    
                    <div style="background-color: #fff; padding: 15px; border-radius: 4px; margin: 15px 0;">
                        <table style="width: 100%;">
                            <tr>
                                <td style="padding: 5px 0;"><strong>PO Reference:</strong></td>
                                <td style="padding: 5px 0;">{self.name}</td>
                            </tr>
                            <tr>
                                <td style="padding: 5px 0;"><strong>Supplier:</strong></td>
                                <td style="padding: 5px 0;">{self.supplier_id.name}</td>
                            </tr>
                            <tr>
                                <td style="padding: 5px 0;"><strong>PO Date:</strong></td>
                                <td style="padding: 5px 0;">{self.date_order}</td>
                            </tr>
                            <tr style="background-color: #f8d7da;">
                                <td style="padding: 5px 0;"><strong>Days Overdue:</strong></td>
                                <td style="padding: 5px 0; font-weight: bold; color: #dc3545; font-size: 20px;">{days_overdue} days</td>
                            </tr>
                            <tr>
                                <td style="padding: 5px 0;"><strong>Contract Value:</strong></td>
                                <td style="padding: 5px 0;">ETB {contract_value:,.2f}</td>
                            </tr>
                        </table>
                    </div>
                    
                    <div style="background-color: #fff3cd; border-left: 4px solid #856404; padding: 15px; margin: 15px 0;">
                        <h4 style="margin-top: 0; color: #856404;">💰 Liquidated Damages Calculation (FR-PROC-036)</h4>
                        <table style="width: 100%;">
                            <tr>
                                <td style="padding: 3px 0;">LD Rate:</td>
                                <td style="padding: 3px 0; text-align: right;">1/1000 per working day</td>
                            </tr>
                            <tr>
                                <td style="padding: 3px 0;">Delay Period:</td>
                                <td style="padding: 3px 0; text-align: right;">{days_overdue} days</td>
                            </tr>
                            <tr>
                                <td style="padding: 3px 0;">Calculated LD:</td>
                                <td style="padding: 3px 0; text-align: right;">ETB {contract_value * ld_rate * days_overdue:,.2f}</td>
                            </tr>
                            <tr>
                                <td style="padding: 3px 0;">LD Cap (10%):</td>
                                <td style="padding: 3px 0; text-align: right;">ETB {ld_cap:,.2f}</td>
                            </tr>
                            <tr style="background-color: #fff; font-weight: bold;">
                                <td style="padding: 8px 0; border-top: 2px solid #856404;">Recommended LD:</td>
                                <td style="padding: 8px 0; text-align: right; border-top: 2px solid #856404; color: #dc3545; font-size: 16px;">ETB {ld_amount:,.2f}</td>
                            </tr>
                        </table>
                    </div>
                    
                    <div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px;">
                        <h4 style="margin-top: 0; color: #155724;">📋 Recommended Actions</h4>
                        <ol style="margin: 0;">
                            <li><strong>Issue formal notice</strong> to supplier citing contract breach</li>
                            <li><strong>Document all communications</strong> regarding delivery delay</li>
                            <li><strong>Assess liquidated damages</strong> per FR-PROC-036</li>
                            <li><strong>Consider contract termination</strong> if delay continues</li>
                            <li><strong>Initiate alternative procurement</strong> if critical items</li>
                        </ol>
                    </div>
                    
                    <p style="margin-top: 20px;">
                        <a href="/web#id={self.id}&model=mesob.procurement.order&view_type=form" 
                           style="background-color: #dc3545; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                           🚨 REVIEW URGENT →
                        </a>
                    </p>
                </div>""",
                subject=f'🚨 CRITICAL: PO {self.name} - {days_overdue} days overdue - LD Recommended',
                message_type='notification',
                partner_ids=pao_users.users.mapped('partner_id').ids
            )
            
            _logger.info(
                f"AUTO-024: Day {days_overdue} PAO escalation sent for PO {self.name} - "
                f"LD Recommendation: ETB {ld_amount:,.2f}"
            )


class MesobProcurementOrderLine(models.Model):
    """Line item in Purchase Order - FR-PROC-026."""

    _name = "mesob.procurement.order.line"
    _description = "Purchase Order Line"

    order_id = fields.Many2one("mesob.procurement.order", string="Purchase Order", ondelete="cascade")
    item_id = fields.Many2one("mesob.inventory.item", string="Catalogued Item", required=False)
    major_classification_id = fields.Many2one(
        "mesob.inventory.major.classification",
        string="Major Classification",
    )
    sub_classification_id = fields.Many2one(
        "mesob.inventory.sub.classification",
        string="Sub Classification",
    )
    auto_generate_items = fields.Boolean(
        string="Auto-Generate Items",
        default=False,
    )
    description = fields.Char(string="Description")
    quantity = fields.Float(string="Quantity", required=True, default=1.0)
    qty_received = fields.Float(string="Received Qty", compute="_compute_received_qty", store=True)
    price_unit = fields.Float(string="Unit Price (ETB)", required=True)
    price_subtotal = fields.Float(string="Subtotal", compute="_compute_subtotal", store=True)

    @api.onchange("item_id")
    def _onchange_item_id(self):
        """Auto-populate classifications when selecting a catalogued item on PO line."""
        if self.item_id:
            self.major_classification_id = self.item_id.classification_id
            self.sub_classification_id = self.item_id.sub_classification_id

    @api.depends("quantity", "price_unit")
    def _compute_subtotal(self):
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit

    @api.depends("order_id.name", "item_id")
    def _compute_received_qty(self):
        for line in self:
            if not line.order_id or not line.order_id.name or not line.item_id:
                line.qty_received = 0.0
                continue
            # Query accepted Model 19 quantities received under this PO reference
            domain = [
                ("model19_id.receiving_id.purchase_order_ref", "=", line.order_id.name),
                ("item_id", "=", line.item_id.id),
                ("model19_id.state", "in", ("confirmed", "distributed", "done")),
            ]
            receipt_lines = self.env["mesob.inventory.model19.line"].search(domain)
            line.qty_received = sum(receipt_lines.mapped("quantity"))


class MesobProcurementPaymentCertificate(models.Model):
    """Three-Way Match payment validation & processing - FR-PROC-034."""

    _name = "mesob.procurement.payment.certificate"
    _description = "Procurement Payment Certificate"
    _order = "id desc"

    name = fields.Char(string="Certificate Number", required=True, copy=False, default="New")
    order_id = fields.Many2one("mesob.procurement.order", string="Purchase Order", required=True)
    supplier_id = fields.Many2one(related="order_id.supplier_id", string="Supplier", readonly=True, store=True)
    amount_gross = fields.Float(string="Gross Amount (ETB)", required=True)
    
    # Matching Checks
    has_invoice = fields.Boolean(string="VAT Compliant Invoice Verified", default=False)
    has_model19 = fields.Boolean(string="Model 19 Receipt Verified", default=False)
    has_po = fields.Boolean(string="Approved PO Verified", default=False)
    
    # Calculations
    days_delay = fields.Integer(string="Days of Delay", default=0)
    penalty_rate = fields.Float(string="Daily Penalty Rate (%)", default=0.1)  # Default: 1/1000 = 0.1% per day
    liquidated_damages = fields.Float(
        string="Liquidated Damages (ETB)",
        compute="_compute_liquidated_damages",
        store=True,
    )
    retention_percent = fields.Float(string="Retention Percentage (%)", default=5.0)
    retention_amount = fields.Float(
        string="Retention Held (ETB)",
        compute="_compute_retention_amount",
        store=True,
    )
    net_payable = fields.Float(
        string="Net Payable Amount (ETB)",
        compute="_compute_net_payable",
        store=True,
    )
    state = fields.Selection(
        [("draft", "Draft"), ("approved", "Approved by PAO Finance")],
        string="Status",
        default="draft",
        required=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = f"PAY/{self.env['ir.sequence'].next_by_code('mesob.procurement.payment.certificate') or '001'}"
        return super().create(vals_list)

    @api.depends("amount_gross", "days_delay", "penalty_rate")
    def _compute_liquidated_damages(self):
        for rec in self:
            # default: 1/1000 of contract value per working day (capped at 10% of total)
            damage = rec.amount_gross * (rec.penalty_rate / 100.0) * rec.days_delay
            max_penalty = rec.amount_gross * 0.10
            rec.liquidated_damages = min(damage, max_penalty)

    @api.depends("amount_gross", "retention_percent")
    def _compute_retention_amount(self):
        for rec in self:
            rec.retention_amount = rec.amount_gross * (rec.retention_percent / 100.0)

    @api.depends("amount_gross", "liquidated_damages", "retention_amount")
    def _compute_net_payable(self):
        for rec in self:
            rec.net_payable = rec.amount_gross - rec.liquidated_damages - rec.retention_amount

    def action_approve(self):
        """Enforces three-way match hard-blocking before payment processing (FR-PROC-034)."""
        for rec in self:
            if not (rec.has_invoice and rec.has_model19 and rec.has_po):
                raise UserError("Three-Way Match Failed! Payment is strictly blocked unless Approved PO, Model 19 Acceptance Receipt, and VAT Compliant Invoice are all verified (FR-PROC-034).")
            rec.state = "approved"
        return True


class MesobProcurementComplaint(models.Model):
    """Complaints and Appeals Register - FR-PROC-038."""

    _name = "mesob.procurement.complaint"
    _description = "Procurement Complaints Register"
    _order = "date_filed desc, id desc"

    name = fields.Char(string="Complaint ID", required=True, copy=False, default="New")
    complainant_name = fields.Char(string="Complainant Name", required=True)
    lot_id = fields.Many2one("mesob.procurement.plan.lot", string="Subject APP Lot", required=True)
    date_filed = fields.Date(string="Date Filed", default=fields.Date.today, required=True)
    nature = fields.Selection(
        [
            ("bidding", "Bidding Irregularity"),
            ("specification", "Specification Dispute"),
            ("award", "Award Challenge"),
            ("contract", "Contract Dispute"),
        ],
        string="Nature of Complaint",
        required=True,
    )
    details = fields.Text(string="Complaint Details", required=True)
    action_taken = fields.Text(string="Response Action Taken")
    resolution = fields.Text(string="Resolution Outcome")
    state = fields.Selection(
        [("open", "Open / Standstill Block"), ("resolved", "Resolved")],
        string="Status",
        default="open",
        required=True,
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = f"COM/{self.env['ir.sequence'].next_by_code('mesob.procurement.complaint') or '001'}"
        return super().create(vals_list)

    def action_resolve(self):
        for rec in self:
            if not rec.resolution:
                raise UserError("Please document the resolution outcome first.")
            rec.state = "resolved"
        return True

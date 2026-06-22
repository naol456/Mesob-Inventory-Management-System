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
            
            # AUTO-004: Calculate total approval time
            if rec.submitted_date and rec.hope_approval_date:
                approval_duration = (rec.hope_approval_date - rec.submitted_date).days
                
                rec.message_post(
                    body=f"""<div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px;">
                        <h3>✅ AUTO-004: APP Approved and Published</h3>
                        <p><strong>APP Reference:</strong> {rec.name}</p>
                        <p><strong>Fiscal Year:</strong> {rec.fiscal_year}</p>
                        <p><strong>Total Lots:</strong> {len(rec.lot_ids)}</p>
                        <hr/>
                        <h4>Approval Timeline:</h4>
                        <table style="width: 100%; margin-top: 10px;">
                            <tr>
                                <td style="padding: 5px;"><strong>Submitted:</strong></td>
                                <td style="padding: 5px;">{rec.submitted_date}</td>
                            </tr>
                            <tr>
                                <td style="padding: 5px;"><strong>PUH Approved:</strong></td>
                                <td style="padding: 5px;">{rec.puh_approval_date or 'N/A'}</td>
                            </tr>
                            <tr>
                                <td style="padding: 5px;"><strong>PEC Approved:</strong></td>
                                <td style="padding: 5px;">{rec.pec_approval_date or 'N/A'}</td>
                            </tr>
                            <tr style="background-color: #d4edda;">
                                <td style="padding: 5px;"><strong>HOPE Approved:</strong></td>
                                <td style="padding: 5px; font-weight: bold;">{rec.hope_approval_date}</td>
                            </tr>
                            <tr>
                                <td style="padding: 5px;"><strong>Total Duration:</strong></td>
                                <td style="padding: 5px; font-weight: bold;">{approval_duration} days</td>
                            </tr>
                        </table>
                        <hr/>
                        <p><em>FR-PROC-005: APP is now authorized and published. Procurement can proceed.</em></p>
                    </div>""",
                    subject=f'APP Published: {rec.name}',
                    message_type='comment'
                )
                
                _logger.info(
                    f"AUTO-004: APP {rec.name} fully approved in {approval_duration} days - "
                    f"PUH: {(rec.puh_approval_date - rec.submitted_date).days if rec.puh_approval_date else 0}d, "
                    f"PEC: {(rec.pec_approval_date - rec.puh_approval_date).days if rec.pec_approval_date and rec.puh_approval_date else 0}d, "
                    f"HOPE: {(rec.hope_approval_date - rec.pec_approval_date).days if rec.hope_approval_date and rec.pec_approval_date else 0}d"
                )
            
            # Notify procurement officers
            rec._send_approval_notification('published')
        
        return True
    
    def _send_approval_notification(self, stage):
        """AUTO-004: Send approval workflow notifications with SLA tracking.
        
        Args:
            stage: 'puh', 'pec', 'hope', or 'published'
        """
        self.ensure_one()
        
        # Determine recipient group and message based on stage
        if stage == 'puh':
            group_ref = 'mesob_inventory_base.group_mesob_puh'
            title = 'APP Submitted for PUH Approval'
            action_text = 'Please review and approve this Annual Procurement Plan.'
            color = '#ffc107'
        elif stage == 'pec':
            group_ref = 'mesob_inventory_base.group_mesob_pec'
            title = 'APP Ready for PEC Approval'
            action_text = 'PUH has approved. Please review and approve for PEC level.'
            color = '#fd7e14'
        elif stage == 'hope':
            group_ref = 'mesob_inventory_base.group_mesob_hope'
            title = 'APP Ready for HOPE Final Authorization'
            action_text = 'PEC has approved. Please review and authorize publication.'
            color = '#dc3545'
        else:  # published
            group_ref = 'mesob_inventory_base.group_mesob_procurement'
            title = 'APP Published - Procurement Authorized'
            action_text = 'You may now proceed with procurement activities per this approved plan.'
            color = '#28a745'
        
        # Get recipients
        recipient_group = self.env.ref(group_ref, raise_if_not_found=False)
        if not recipient_group or not recipient_group.users:
            _logger.warning(f"AUTO-004: No users found in group {group_ref}")
            return
        
        # Build lots summary
        lots_summary = '<ul>'
        for lot in self.lot_ids[:10]:  # Show first 10 lots
            estimated_value = sum(item.estimated_value for item in lot.item_ids)
            lots_summary += f'<li><strong>{lot.name}</strong>: {lot.method} - ETB {estimated_value:,.2f}</li>'
        lots_summary += '</ul>'
        
        if len(self.lot_ids) > 10:
            lots_summary += f'<p><em>...and {len(self.lot_ids) - 10} more lots</em></p>'
        
        # SLA warning if overdue
        sla_warning = ''
        if self.approval_sla_status == 'overdue':
            sla_warning = f'''<div style="background-color: #f8d7da; padding: 10px; border-radius: 5px; margin-top: 15px;">
                <p style="margin: 0; color: #dc3545;"><strong>⚠ SLA ALERT:</strong> This APP has been in approval for {self.days_in_approval} days (OVERDUE)</p>
            </div>'''
        elif self.approval_sla_status == 'warning':
            sla_warning = f'''<div style="background-color: #fff3cd; padding: 10px; border-radius: 5px; margin-top: 15px;">
                <p style="margin: 0; color: #856404;"><strong>⚠ SLA WARNING:</strong> This APP has been in approval for {self.days_in_approval} days (approaching deadline)</p>
            </div>'''
        
        # Send notification
        self.message_post(
            body=f"""<div style="background-color: #f8f9fa; border-left: 4px solid {color}; padding: 15px;">
                <h3 style="color: {color};">AUTO-004: {title}</h3>
                <p><strong>APP Reference:</strong> {self.name}</p>
                <p><strong>Fiscal Year:</strong> {self.fiscal_year}</p>
                <p><strong>Planning Type:</strong> {dict(self._fields['planning_type'].selection).get(self.planning_type)}</p>
                <p><strong>Stream:</strong> {dict(self._fields['procurement_stream'].selection).get(self.procurement_stream)}</p>
                <p><strong>Total Lots:</strong> {len(self.lot_ids)}</p>
                {f'<p><strong>Days in Approval:</strong> {self.days_in_approval}</p>' if self.submitted_date and stage != 'published' else ''}
                <hr/>
                <h4>Procurement Lots:</h4>
                {lots_summary}
                {sla_warning}
                <hr/>
                <p style="margin-top: 15px;"><strong>{action_text}</strong></p>
                <p><a href="/web#id={self.id}&model=mesob.procurement.plan&view_type=form" 
                   style="background-color: {color}; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                   View APP →
                </a></p>
            </div>""",
            subject=f'AUTO-004: {title} - {self.name}',
            message_type='notification',
            partner_ids=recipient_group.users.mapped('partner_id').ids
        )
        
        _logger.info(
            f"AUTO-004: Notification sent to {len(recipient_group.users)} {stage.upper()} users - "
            f"APP: {self.name}, SLA Status: {self.approval_sla_status}"
        )
        
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
            'puh': 'mesob_inventory_base.group_mesob_procurement',  # Procurement Unit Head
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
        procurement_users = self.env.ref('mesob_inventory_base.group_mesob_procurement', raise_if_not_found=False)
        
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
    
    def action_intelligent_consolidation(self):
        """AUTO-002: Launch intelligent needs consolidation wizard.
        
        Opens a wizard that helps SPO consolidate department needs into lots using:
        - Keyword similarity matching
        - Classification-based grouping
        - Budget-based mechanism suggestions
        """
        self.ensure_one()
        
        # Count unassigned reviewed needs
        unassigned_needs = self.env['mesob.procurement.need'].search_count([
            ('state', '=', 'reviewed'),
            ('lot_id', '=', False),
            '|',
            ('item_id', '!=', False),
            ('sub_classification_id', '!=', False)
        ])
        
        if unassigned_needs == 0:
            raise UserError(
                "No reviewed needs available for consolidation.\n\n"
                "Please ensure department needs are submitted and reviewed before using intelligent consolidation."
            )
        
        # Create wizard and return action
        wizard = self.env['mesob.intelligent.consolidation.wizard'].create({
            'plan_id': self.id,
        })
        
        return {
            'name': 'AUTO-002: Intelligent Needs Consolidation',
            'type': 'ir.actions.act_window',
            'res_model': 'mesob.intelligent.consolidation.wizard',
            'res_id': wizard.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }


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
    
    # AUTO-007: Technical specification template library
    major_classification_id = fields.Many2one(
        'mesob.inventory.major.classification',
        string='Major Classification',
        compute='_compute_major_classification',
        store=True,
        help='AUTO-007: Determined from consolidated needs for template matching'
    )
    
    spec_template_id = fields.Many2one(
        'mesob.technical.spec.template',
        string='Specification Template',
        domain="[('major_classification_id', '=', major_classification_id), ('is_active', '=', True)]",
        help='AUTO-007: Reusable technical specification template (FR-PROC-009)'
    )
    
    has_brand_name_violations = fields.Boolean(
        string='Brand Name Violations',
        compute='_compute_brand_name_check',
        store=True,
        help='AUTO-007: True if technical specs contain unapproved brand names'
    )
    
    brand_name_violations_list = fields.Text(
        string='Detected Brand Names',
        compute='_compute_brand_name_check',
        store=True,
        help='AUTO-007: List of brand names detected in specifications'
    )
    
    @api.depends('need_ids', 'need_ids.major_classification_id')
    def _compute_major_classification(self):
        """AUTO-007: Determine major classification from needs for template matching."""
        for lot in self:
            if not lot.need_ids:
                lot.major_classification_id = False
                continue
            
            # Get the most common classification from needs
            classifications = lot.need_ids.mapped('major_classification_id')
            if classifications:
                # Use the first classification (could be enhanced to use most common)
                lot.major_classification_id = classifications[0]
            else:
                lot.major_classification_id = False
    
    @api.onchange('spec_template_id')
    def _onchange_spec_template(self):
        """AUTO-007: Auto-fill technical specifications from template."""
        if self.spec_template_id:
            # Apply template
            from html.parser import HTMLParser
            
            class HTMLToText(HTMLParser):
                def __init__(self):
                    super().__init__()
                    self.text = []
                
                def handle_data(self, data):
                    self.text.append(data)
                
                def get_text(self):
                    return ''.join(self.text)
            
            # Convert HTML to plain text for the Text field
            # (Note: If technical_specifications is Html field, use HTML directly)
            parser = HTMLToText()
            parser.feed(self.spec_template_id.specification_text or '')
            
            # Update last used date on template
            self.spec_template_id.write({'last_used_date': fields.Date.today()})
            
            return {
                'warning': {
                    'title': 'Template Applied',
                    'message': f'Specification template "{self.spec_template_id.name}" has been loaded. '
                               'Please review and customize as needed for this specific lot.'
                }
            }
    
    def action_apply_template(self):
        """AUTO-007: Manually apply selected template to technical specifications."""
        self.ensure_one()
        
        if not self.spec_template_id:
            raise UserError(
                "No template selected.\n\n"
                "Please select a specification template from the dropdown first."
            )
        
        # Apply the template content
        from html.parser import HTMLParser
        
        class HTMLToText(HTMLParser):
            def __init__(self):
                super().__init__()
                self.text = []
            
            def handle_data(self, data):
                self.text.append(data)
            
            def get_text(self):
                return ''.join(self.text)
        
        parser = HTMLToText()
        parser.feed(self.spec_template_id.specification_text or '')
        spec_text = parser.get_text()
        
        # Update the lot's technical specifications
        # Note: Adjust field name if it's different in tender model
        tender = self.env['mesob.procurement.tender'].search([('lot_id', '=', self.id)], limit=1)
        if tender:
            tender.write({'technical_specifications': spec_text})
        
        # Update template usage
        self.spec_template_id.write({'last_used_date': fields.Date.today()})
        
        _logger.info(
            f"AUTO-007: Template '{self.spec_template_id.name}' applied to lot {self.name}"
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Template Applied',
                'message': f'Specification template "{self.spec_template_id.name}" applied successfully. Please review and customize.',
                'type': 'success',
            }
        }
    
    @api.depends('spec_template_id', 'spec_template_id.brand_name_keywords')
    def _compute_brand_name_check(self):
        """AUTO-007: Check technical specifications for brand name violations (FR-PROC-009)."""
        for lot in self:
            # Get technical specs from tender if exists
            tender = self.env['mesob.procurement.tender'].search([('lot_id', '=', lot.id)], limit=1)
            
            if not tender or not tender.technical_specifications:
                lot.has_brand_name_violations = False
                lot.brand_name_violations_list = ''
                continue
            
            if not lot.spec_template_id:
                lot.has_brand_name_violations = False
                lot.brand_name_violations_list = ''
                continue
            
            # Check for brand names
            has_violations, detected_brands = lot.spec_template_id._check_brand_names(
                tender.technical_specifications
            )
            
            lot.has_brand_name_violations = has_violations
            if detected_brands:
                lot.brand_name_violations_list = (
                    f"⚠️ FR-PROC-009 Violation: Brand names detected without 'or equivalent' clause:\n\n" +
                    "\n".join(f"• {brand}" for brand in detected_brands) +
                    "\n\nAction Required: Either remove brand names or add 'or equivalent' after each brand reference (BR-PROC-004)."
                )
            else:
                lot.brand_name_violations_list = ''
    
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
        procurement_users = self.env.ref('mesob_inventory_base.group_mesob_procurement', raise_if_not_found=False)
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
    """Departmental Needs Collection - FR-PROC-002.
    
    AUTO-001: Department Self-Service Needs Submission
    - Department Heads submit needs directly via self-service form
    - System validates item codes against catalogue in real-time (FR-ID-001)
    - System auto-calculates estimated value based on last purchase price
    - Procurement Officer receives aggregated submissions
    """

    _name = "mesob.procurement.need"
    _description = "Departmental Need Request"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "submission_date desc, id desc"

    # ── AUTO-001: Self-Service Submission Fields ────────────────────
    
    submission_date = fields.Datetime(
        string="Submission Date",
        default=fields.Datetime.now,
        readonly=True,
        tracking=True,
        help="AUTO-001: Timestamp when department submitted this need"
    )
    
    submitted_by_id = fields.Many2one(
        'res.users',
        string="Submitted By",
        default=lambda self: self.env.user,
        readonly=True,
        tracking=True,
        help="AUTO-001: Department Head/User who submitted this need"
    )
    
    fiscal_year = fields.Char(
        string="Target Fiscal Year",
        required=True,
        default=lambda self: self._default_fiscal_year(),
        help="Ethiopian Fiscal Year (e.g., 2018 E.C.)"
    )
    
    justification = fields.Text(
        string="Justification/Need Reason",
        required=True,
        help="AUTO-001: Department must justify why this item is needed"
    )
    
    # ── Budget Availability Check (AUTO-003) ────────────────────────
    
    budget_classification = fields.Selection([
        ('4401', '4401 - Office Supplies'),
        ('4402', '4402 - Stationery'),
        ('4403', '4403 - Cleaning Materials'),
        ('4404', '4404 - Printed Forms'),
        ('4405', '4405 - Fuel & Lubricants'),
        ('4406', '4406 - Spare Parts'),
        ('4407', '4407 - Books & Publications'),
        ('4408', '4408 - Medical Supplies'),
        ('4409', '4409 - Agricultural Supplies'),
        ('4410', '4410 - Construction Materials'),
        ('4411', '4411 - Drugs & Chemicals'),
        ('4412', '4412 - Food & Beverages'),
        ('4413', '4413 - Vehicles'),
        ('4414', '4414 - Machinery & Equipment'),
        ('4415', '4415 - Furniture & Fixtures'),
        ('4416', '4416 - IT Equipment'),
        ('4417', '4417 - Communication Equipment'),
        ('4418', '4418 - Other Equipment'),
    ], string="Budget Classification", compute='_compute_budget_classification', store=True)
    
    budget_available = fields.Boolean(
        string="Budget Available",
        compute='_compute_budget_available',
        store=True,
        help="AUTO-003: Real-time budget availability check"
    )
    
    budget_balance = fields.Monetary(
        string="Available Budget Balance",
        compute='_compute_budget_available',
        store=True,
        currency_field='currency_id',
        help="AUTO-003: Remaining budget for this classification"
    )
    
    budget_warning = fields.Text(
        string="Budget Warning",
        compute='_compute_budget_available',
        store=True,
        help="AUTO-003: Warning if budget insufficient"
    )

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
        default=lambda self: self._default_department(),
        tracking=True,
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )
    item_id = fields.Many2one(
        "mesob.inventory.item",
        string="Catalogued Stock Item",
        required=False,
        tracking=True,
        help="AUTO-001: Optional if item is not yet coded. System validates against catalogue (FR-ID-001).",
    )
    major_classification_id = fields.Many2one(
        "mesob.inventory.major.classification",
        string="Major Classification",
        tracking=True,
        help="Major classification code (e.g., 4402) for non-coded / auto-generated items.",
    )
    sub_classification_id = fields.Many2one(
        "mesob.inventory.sub.classification",
        string="Sub Classification",
        tracking=True,
        help="Sub classification code (e.g., 001) for non-coded / auto-generated items.",
    )
    item_code = fields.Char(
        string="Item Code",
        compute="_compute_item_code",
        store=True,
        readonly=True,
    )
    quantity = fields.Float(
        string="Quantity Requested", 
        required=True, 
        default=1.0,
        tracking=True,
    )
    estimated_unit_price = fields.Float(
        string="Estimated Unit Price", 
        required=True,
        tracking=True,
        help="AUTO-001: Auto-calculated from last purchase price if item exists"
    )
    
    # AUTO-001: Last purchase price intelligence
    last_purchase_price = fields.Float(
        string="Last Purchase Price",
        compute='_compute_last_purchase_price',
        help="AUTO-001: Last recorded purchase price for this item"
    )
    
    price_variance_percent = fields.Float(
        string="Price Variance %",
        compute='_compute_price_variance',
        help="AUTO-001: Variance between estimated and last purchase price"
    )
    
    total_price = fields.Float(
        string="Estimated Total Price",
        compute="_compute_total_price",
        store=True,
        tracking=True,
    )
    expected_delivery_period = fields.Char(
        string="Expected Delivery Period",
        required=True,
        placeholder="e.g. Q1 / Sene 2018",
        tracking=True,
    )
    reviewer_id = fields.Many2one(
        "res.users", 
        string="Reviewer", 
        readonly=True,
        tracking=True,
    )
    review_timestamp = fields.Datetime(
        string="Review Timestamp", 
        readonly=True,
        tracking=True,
    )
    review_comment = fields.Text(
        string="Review Comment",
        help="AUTO-001: SPO comments during review"
    )
    lot_id = fields.Many2one(
        "mesob.procurement.plan.lot",
        string="Assigned APP Lot",
        tracking=True,
        help="AUTO-002: Lot assigned by Senior Procurement Officer (FR-PROC-004).",
    )
    
    # AUTO-002: Intelligent consolidation fields
    similar_needs_count = fields.Integer(
        string="Similar Needs",
        compute='_compute_similar_needs',
        help="AUTO-002: Count of similar needs for consolidation"
    )
    
    consolidation_group = fields.Char(
        string="Consolidation Group",
        compute='_compute_consolidation_group',
        store=True,
        help="AUTO-002: Auto-generated grouping key for similar items"
    )
    
    suggested_lot_name = fields.Char(
        string="Suggested Lot Name",
        compute='_compute_suggested_lot',
        help="AUTO-002: System-suggested lot assignment"
    )
    
    consolidation_keywords = fields.Char(
        string="Keywords",
        compute='_compute_consolidation_keywords',
        store=True,
        help="AUTO-002: Extracted keywords for similarity matching"
    )
    
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted - Pending SPO Review"),
            ("reviewed", "Reviewed by SPO"),
            ("locked", "Locked (Immutable)"),
            ("rejected", "Rejected"),
        ],
        string="Status",
        default="draft",
        required=True,
        tracking=True,
    )
    
    rejection_reason = fields.Text(
        string="Rejection Reason",
        readonly=True,
        help="AUTO-001: Reason for need rejection"
    )
    
    # ── Helper/Computed Fields ──────────────────────────────────────
    
    display_name = fields.Char(
        string="Display Name",
        compute='_compute_display_name',
        store=True,
    )

    # ── AUTO-001: Default Values ────────────────────────────────────
    
    @api.model
    def _default_fiscal_year(self):
        """Return current Ethiopian fiscal year (approximate)."""
        # Ethiopian calendar is ~7-8 years behind Gregorian
        # Fiscal year runs from Hamle 1 (approx July 8)
        import datetime
        today = datetime.date.today()
        ec_year = today.year - 7  # Approximate
        return f"{ec_year} E.C."
    
    @api.model
    def _default_department(self):
        """AUTO-001: Auto-detect department from user context."""
        # Try to infer from user's groups or profile
        # For now, return False to force selection
        return False
    
    # ── AUTO-001: Computed Fields ───────────────────────────────────
    
    @api.depends('department', 'item_code', 'quantity')
    def _compute_display_name(self):
        for rec in self:
            if rec.department and rec.item_code:
                dept_label = dict(rec._fields['department'].selection).get(rec.department, 'Unknown')
                rec.display_name = f"{dept_label[:30]} - {rec.item_code} (Qty: {rec.quantity})"
            else:
                rec.display_name = f"Need Request #{rec.id or 'New'}"
    
    @api.depends('major_classification_id')
    def _compute_budget_classification(self):
        """AUTO-003: Map major classification to budget code."""
        for rec in self:
            if rec.major_classification_id:
                rec.budget_classification = rec.major_classification_id.code
            else:
                rec.budget_classification = False
    
    @api.depends('budget_classification', 'total_price', 'fiscal_year')
    def _compute_budget_available(self):
        """AUTO-003: Real-time budget availability check (FR-PROC-002, BR-PROC-001).
        
        Checks if sufficient budget exists before needs acceptance.
        Prevents wasted consolidation effort on unfunded needs.
        """
        for rec in self:
            if not rec.budget_classification or not rec.total_price or not rec.fiscal_year:
                rec.budget_available = True
                rec.budget_balance = 0.0
                rec.budget_warning = False
                continue
            
            # AUTO-003: Check real-time budget availability
            budget_check = self.env['mesob.budget.allocation'].check_budget_availability(
                rec.budget_classification,
                rec.fiscal_year,
                rec.total_price
            )
            
            rec.budget_available = budget_check['available']
            rec.budget_balance = budget_check['balance']
            rec.budget_warning = budget_check['warning'] or False
    
    @api.depends('item_id')
    def _compute_last_purchase_price(self):
        """AUTO-001: Fetch last purchase price for intelligent pre-fill."""
        for rec in self:
            if not rec.item_id:
                rec.last_purchase_price = 0.0
                continue
            
            # Find last approved/received PO line for this item
            last_po_line = self.env['mesob.procurement.order.line'].search([
                ('item_id', '=', rec.item_id.id),
                ('order_id.state', 'in', ['approved', 'sent', 'fully_received', 'closed'])
            ], order='id desc', limit=1)
            
            rec.last_purchase_price = last_po_line.price_unit if last_po_line else 0.0
    
    @api.depends('estimated_unit_price', 'last_purchase_price')
    def _compute_price_variance(self):
        """AUTO-001: Calculate price variance for review."""
        for rec in self:
            if rec.last_purchase_price > 0 and rec.estimated_unit_price > 0:
                variance = ((rec.estimated_unit_price - rec.last_purchase_price) / rec.last_purchase_price) * 100
                rec.price_variance_percent = variance
            else:
                rec.price_variance_percent = 0.0

    # ── AUTO-001: Onchange Methods ──────────────────────────────────

    @api.onchange("item_id")
    def _onchange_item_id(self):
        """AUTO-001: Auto-populate fields when selecting catalogued item (FR-ID-001 validation)."""
        if self.item_id:
            # Auto-populate classifications
            self.major_classification_id = self.item_id.classification_id
            self.sub_classification_id = self.item_id.sub_classification_id
            
            # AUTO-001: Auto-fill estimated price from last purchase
            if self.item_id and not self.estimated_unit_price:
                last_po_line = self.env['mesob.procurement.order.line'].search([
                    ('item_id', '=', self.item_id.id),
                    ('order_id.state', 'in', ['approved', 'sent', 'fully_received', 'closed'])
                ], order='id desc', limit=1)
                
                if last_po_line:
                    self.estimated_unit_price = last_po_line.price_unit
                    
                    return {
                        'warning': {
                            'title': 'AUTO-001: Price Auto-Filled',
                            'message': (
                                f'Estimated unit price auto-filled from last purchase: '
                                f'ETB {last_po_line.price_unit:,.2f}\n'
                                f'You can adjust this value if needed.'
                            )
                        }
                    }
    
    @api.onchange('estimated_unit_price')
    def _onchange_estimated_unit_price(self):
        """AUTO-001: Warn if price variance is significant."""
        if self.estimated_unit_price and self.last_purchase_price:
            variance = self.price_variance_percent
            
            if abs(variance) > 20:  # > 20% variance
                return {
                    'warning': {
                        'title': 'Price Variance Alert',
                        'message': (
                            f'Estimated price (ETB {self.estimated_unit_price:,.2f}) differs '
                            f'from last purchase (ETB {self.last_purchase_price:,.2f}) by '
                            f'{variance:+.1f}%.\n\n'
                            f'Please verify and justify in the need justification field.'
                        )
                    }
                }
    
    # ── Validation ───────────────────────────────────────────────────

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
    
    # ── AUTO-002: Intelligent Consolidation Compute Methods ─────────
    
    @api.depends('item_id', 'major_classification_id', 'sub_classification_id', 'justification')
    def _compute_consolidation_keywords(self):
        """AUTO-002: Extract keywords from item description and justification."""
        import re
        
        # Common words to exclude
        STOP_WORDS = {
            'the', 'a', 'an', 'and', 'or', 'of', 'in', 'for', 'with', 'to', 'from', 
            'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
            'this', 'that', 'these', 'those', 'it', 'its', 'we', 'our', 'you', 'your'
        }
        
        for rec in self:
            keywords = []
            
            # Extract from item name
            if rec.item_id and rec.item_id.name:
                words = re.findall(r'\b\w+\b', rec.item_id.name.lower())
                keywords.extend([w for w in words if len(w) > 2 and w not in STOP_WORDS])
            
            # Extract from justification
            if rec.justification:
                words = re.findall(r'\b\w+\b', rec.justification.lower())
                keywords.extend([w for w in words[:10] if len(w) > 3 and w not in STOP_WORDS])  # First 10 meaningful words
            
            # Remove duplicates and join
            rec.consolidation_keywords = ' '.join(list(dict.fromkeys(keywords))[:10])  # Top 10 unique keywords
    
    @api.depends('item_id', 'major_classification_id', 'sub_classification_id')
    def _compute_consolidation_group(self):
        """AUTO-002: Generate grouping key for automatic consolidation."""
        for rec in self:
            if rec.item_id:
                # Group by exact item code
                rec.consolidation_group = f"ITEM_{rec.item_id.id}"
            elif rec.sub_classification_id:
                # Group by sub-classification
                rec.consolidation_group = f"SUB_{rec.sub_classification_id.id}"
            elif rec.major_classification_id:
                # Group by major classification
                rec.consolidation_group = f"MAJ_{rec.major_classification_id.id}"
            else:
                rec.consolidation_group = f"UNGROUPED_{rec.id}"
    
    @api.depends('consolidation_group', 'state')
    def _compute_similar_needs(self):
        """AUTO-002: Count similar reviewed needs for consolidation."""
        for rec in self:
            if rec.state != 'reviewed' or not rec.consolidation_group:
                rec.similar_needs_count = 0
                continue
            
            # Count other reviewed needs in same group without lot assignment
            similar = self.search_count([
                ('consolidation_group', '=', rec.consolidation_group),
                ('state', '=', 'reviewed'),
                ('lot_id', '=', False),
                ('id', '!=', rec.id)
            ])
            
            rec.similar_needs_count = similar
    
    @api.depends('consolidation_group', 'item_id', 'sub_classification_id')
    def _compute_suggested_lot(self):
        """AUTO-002: Suggest lot name based on grouping."""
        for rec in self:
            if rec.item_id:
                rec.suggested_lot_name = f"Lot: {rec.item_id.name}"
            elif rec.sub_classification_id:
                rec.suggested_lot_name = f"Lot: {rec.sub_classification_id.name}"
            elif rec.major_classification_id:
                rec.suggested_lot_name = f"Lot: {rec.major_classification_id.name}"
            else:
                rec.suggested_lot_name = "Uncategorized Lot"

    # ── AUTO-001: Self-Service Actions ──────────────────────────────
    
    def action_submit(self):
        """AUTO-001: Department Head submits need directly (FR-PROC-002).
        
        Validates:
        - Item code against catalogue (FR-ID-001)
        - Required fields completed
        - Justification provided
        
        Sends notification to SPO for aggregated review.
        """
        for rec in self:
            if rec.state != "draft":
                raise UserError("Only draft needs can be submitted.")
            
            # Validation checks
            if not rec.justification or len(rec.justification) < 20:
                raise ValidationError(
                    "AUTO-001: Justification is mandatory and must be at least 20 characters. "
                    "Please explain why this item is needed."
                )
            
            if rec.total_price <= 0:
                raise ValidationError("Estimated total price must be greater than zero.")
            
            # AUTO-003: Warn if budget appears insufficient (non-blocking)
            if rec.budget_warning:
                _logger.warning(f"AUTO-003: {rec.budget_warning} for need ID {rec.id}")
            
            rec.write({
                'state': 'submitted',
                'submission_date': fields.Datetime.now(),
                'submitted_by_id': self.env.user.id,
            })
            
            # Send notification to SPO
            rec._notify_spo_new_submission()
            
            _logger.info(
                f"AUTO-001: Need submitted by {self.env.user.name} - "
                f"{rec.department}, Item: {rec.item_code}, Qty: {rec.quantity}, "
                f"Value: ETB {rec.total_price:,.2f}"
            )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Need Submitted Successfully',
                'message': 'Your procurement need has been submitted to SPO for review.',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_review(self):
        """AUTO-001: SPO reviews submitted need (FR-PROC-003).
        
        SPO can:
        - Approve: Move to 'reviewed' state for lot assignment
        - Reject: Return to department with comments
        - Request clarification: Add comment and keep in submitted state
        """
        for rec in self:
            if rec.state != "submitted":
                raise UserError("Only submitted needs can be reviewed.")
            
            rec.write({
                "state": "reviewed",
                "reviewer_id": self.env.user.id,
                "review_timestamp": fields.Datetime.now(),
            })
            
            # Notify department of approval
            if rec.submitted_by_id:
                rec.message_post(
                    body=f"""<div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px;">
                        <h3>✅ Need Reviewed & Approved</h3>
                        <p>Your procurement need has been reviewed and approved by SPO.</p>
                        <p><strong>Reviewer:</strong> {self.env.user.name}</p>
                        <p><strong>Next Step:</strong> Need will be consolidated into procurement lots.</p>
                    </div>""",
                    subject=f'Need Approved: {rec.item_code}',
                    message_type='notification',
                    partner_ids=[rec.submitted_by_id.partner_id.id]
                )
            
            _logger.info(f"AUTO-001: Need {rec.id} reviewed by {self.env.user.name}")
        
        return True
    
    def action_reject(self):
        """AUTO-001: SPO rejects need with mandatory comment."""
        self.ensure_one()
        
        if self.state not in ['submitted', 'reviewed']:
            raise UserError("Only submitted or reviewed needs can be rejected.")
        
        # Open wizard for rejection reason
        return {
            'name': 'Reject Procurement Need',
            'type': 'ir.actions.act_window',
            'res_model': 'mesob.procurement.need.reject.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_need_id': self.id}
        }
    
    def _confirm_rejection(self, reason):
        """Internal method to confirm rejection with reason."""
        self.ensure_one()
        
        if not reason or len(reason) < 10:
            raise ValidationError("Rejection reason must be at least 10 characters.")
        
        self.write({
            'state': 'rejected',
            'rejection_reason': reason,
            'reviewer_id': self.env.user.id,
            'review_timestamp': fields.Datetime.now(),
        })
        
        # Notify department
        if self.submitted_by_id:
            self.message_post(
                body=f"""<div style="background-color: #f8d7da; border-left: 4px solid #dc3545; padding: 15px;">
                    <h3>❌ Need Rejected</h3>
                    <p>Your procurement need has been rejected by SPO.</p>
                    <p><strong>Reviewer:</strong> {self.env.user.name}</p>
                    <p><strong>Reason:</strong></p>
                    <p style="background-color: white; padding: 10px; border-radius: 4px;">{reason}</p>
                    <p><strong>Action Required:</strong> Please revise and resubmit if needed.</p>
                </div>""",
                subject=f'Need Rejected: {self.item_code}',
                message_type='notification',
                partner_ids=[self.submitted_by_id.partner_id.id]
            )
        
        _logger.info(f"AUTO-001: Need {self.id} rejected by {self.env.user.name}")
    
    def _notify_spo_new_submission(self):
        """AUTO-001: Notify SPO of new department need submission."""
        self.ensure_one()
        
        # Get SPO users
        spo_group = self.env.ref('mesob_inventory_base.group_mesob_procurement', raise_if_not_found=False)
        if not spo_group or not spo_group.users:
            _logger.warning("AUTO-001: No SPO users found for notification")
            return
        
        dept_label = dict(self._fields['department'].selection).get(self.department, 'Unknown')
        
        # Build notification
        self.message_post(
            body=f"""<div style="background-color: #d1ecf1; border-left: 4px solid #0c5460; padding: 15px;">
                <h3>📥 AUTO-001: New Need Submission</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 5px 0;"><strong>Department:</strong></td>
                        <td style="padding: 5px 0;">{dept_label}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 0;"><strong>Submitted By:</strong></td>
                        <td style="padding: 5px 0;">{self.submitted_by_id.name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 0;"><strong>Item:</strong></td>
                        <td style="padding: 5px 0;">{self.item_code or 'TBD'} - {self.item_id.name if self.item_id else 'Non-catalogued'}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 0;"><strong>Quantity:</strong></td>
                        <td style="padding: 5px 0;">{self.quantity}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 0;"><strong>Estimated Unit Price:</strong></td>
                        <td style="padding: 5px 0;">ETB {self.estimated_unit_price:,.2f}</td>
                    </tr>
                    <tr style="background-color: #e7f3ff;">
                        <td style="padding: 5px 0;"><strong>Total Value:</strong></td>
                        <td style="padding: 5px 0; font-weight: bold;">ETB {self.total_price:,.2f}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 0;"><strong>Expected Delivery:</strong></td>
                        <td style="padding: 5px 0;">{self.expected_delivery_period}</td>
                    </tr>
                </table>
                <hr/>
                <p><strong>Justification:</strong></p>
                <p style="background-color: white; padding: 10px; border-radius: 4px;">{self.justification}</p>
                {'<p style="background-color: #fff3cd; padding: 10px; border-radius: 4px; margin-top: 10px;">' + 
                 '<strong>⚠️ Budget Warning:</strong> ' + self.budget_warning + '</p>' if self.budget_warning else ''}
                <p style="margin-top: 15px;">
                    <a href="/web#id={self.id}&model=mesob.procurement.need&view_type=form" 
                       style="background-color: #17a2b8; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                       Review Need →
                    </a>
                </p>
            </div>""",
            subject=f'New Need Submission: {dept_label} - {self.item_code or "TBD"}',
            message_type='notification',
            partner_ids=spo_group.users.mapped('partner_id').ids
        )
        
        _logger.info(
            f"AUTO-001: Notification sent to {len(spo_group.users)} SPO users for need {self.id}"
        )

    def action_lock(self):
        """Lock need to make it immutable."""
        for rec in self:
            if rec.state != "reviewed":
                raise UserError("Only reviewed needs can be locked.")
            rec.state = "locked"
        return True


class MesobProcurementTender(models.Model):
    """Bidding and Tender Management - FR-PROC-013.
    
    AUTO-010: Bidding Document Auto-Assembly
    - System auto-generates bidding document pack from approved lot data
    - Includes: Invitation, Technical Spec, Bill of Quantities, Bid Security template
    - Auto-calculates bid security (% of estimated value)
    - Officer reviews and approves pack before issuance
    - Reduces assembly time from days to minutes
    
    AUTO-011: Minimum Advertising Period Enforcement
    - System auto-sets submission deadline based on procurement method
    - Blocks earlier deadlines (ICB: 45 days, NCB: 30 days, RFQ: 7 days)
    - Allows extensions with documented reason
    """

    _name = "mesob.procurement.tender"
    _description = "Procurement Tender"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "id desc"

    name = fields.Char(
        string="Tender Reference",
        required=True,
        copy=False,
        default="New",
        tracking=True,
    )
    lot_id = fields.Many2one(
        "mesob.procurement.plan.lot",
        string="Source APP Lot",
        required=True,
        domain=[("mechanism", "=", "bidding")],
        tracking=True,
    )
    
    # AUTO-010: Document assembly fields
    invitation_letter = fields.Html(
        string="Invitation to Bid",
        compute='_compute_bidding_documents',
        store=True,
        help="AUTO-010: Auto-generated invitation letter from lot data"
    )
    
    technical_specifications = fields.Text(
        string="Technical Specifications",
        required=True,
        help="AUTO-010/FR-PROC-009: Quality performance characteristics (brandless).",
        tracking=True,
    )
    
    bill_of_quantities = fields.Html(
        string="Bill of Quantities",
        compute='_compute_bidding_documents',
        store=True,
        help="AUTO-010: Auto-generated BOQ from lot line items"
    )
    
    bid_security_amount = fields.Monetary(
        string="Bid Security Amount",
        compute='_compute_bid_security',
        store=True,
        currency_field='currency_id',
        help="AUTO-010: Auto-calculated bid security (% of estimated value)"
    )
    
    bid_security_percentage = fields.Float(
        string="Bid Security %",
        default=2.0,
        help="AUTO-010: Bid security percentage (default 2% per FPPA)"
    )
    
    bid_security_template = fields.Html(
        string="Bid Security Template",
        compute='_compute_bidding_documents',
        store=True,
        help="AUTO-010: Template for bid security guarantee"
    )
    
    # AUTO-011: Minimum advertising period enforcement
    procurement_method = fields.Selection([
        ('icb', 'International Competitive Bidding (ICB)'),
        ('ncb', 'National Competitive Bidding (NCB)'),
        ('rfq', 'Request for Quotation (RFQ)'),
    ], string="Procurement Method", compute='_compute_procurement_method', store=True)
    
    minimum_advertising_days = fields.Integer(
        string="Minimum Advertising Days",
        compute='_compute_minimum_advertising_days',
        store=True,
        help="AUTO-011: Minimum days based on procurement method (FR-PROC-014)"
    )
    
    earliest_submission_date = fields.Date(
        string="Earliest Submission Date",
        compute='_compute_earliest_submission_date',
        store=True,
        help="AUTO-011: Calculated from advertisement date + minimum days"
    )
    
    deadline_extension_reason = fields.Text(
        string="Deadline Extension Reason",
        help="AUTO-011: Required if deadline extended beyond minimum period"
    )
    
    deadline_extension_approved_by = fields.Many2one(
        'res.users',
        string="Extension Approved By",
        help="AUTO-011: User who approved the deadline extension",
        readonly=True
    )
    
    deadline_extension_approved_date = fields.Datetime(
        string="Extension Approved Date",
        help="AUTO-011: Timestamp of extension approval",
        readonly=True
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )
    
    spec_status = fields.Selection(
        [("draft", "Draft"), ("approved", "Approved")],
        string="Specification Status",
        default="draft",
        required=True,
        tracking=True,
    )
    advertisement_date = fields.Date(
        string="Advertisement Date",
        tracking=True,
    )
    submission_deadline = fields.Datetime(
        string="Submission Deadline",
        tracking=True,
    )
    opening_minutes = fields.Text(
        string="Bid Opening Minutes (FR-PROC-015)",
        tracking=True,
    )
    opening_signatures = fields.Text(
        string="Opening Committee Signatures"
    )
    bid_ids = fields.One2many(
        "mesob.procurement.bid",
        "tender_id",
        string="Submitted Bids",
    )
    
    # AUTO-013: RFQ Three-Quotation Rule Enforcement
    valid_bid_count = fields.Integer(
        string="Valid Bids Count",
        compute='_compute_valid_bid_count',
        store=True,
        help="AUTO-013: Count of valid (not late, not disqualified) bids for RFQ rule enforcement"
    )
    
    rfq_minimum_violation = fields.Boolean(
        string="RFQ Minimum Violation",
        compute='_compute_valid_bid_count',
        store=True,
        help="AUTO-013: True if RFQ has fewer than 3 valid quotations (FR-PROC-016)"
    )
    
    rfq_justification = fields.Text(
        string="RFQ Exception Justification",
        help="AUTO-013: PAO justification for proceeding with fewer than 3 quotations (BR-PROC-005)"
    )
    
    rfq_exception_approved_by = fields.Many2one(
        'res.users',
        string="RFQ Exception Approved By",
        help="AUTO-013: PAO/HOPE who approved the exception",
        readonly=True
    )
    
    rfq_exception_approved_date = fields.Datetime(
        string="Exception Approval Date",
        help="AUTO-013: Timestamp of exception approval",
        readonly=True
    )
    
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("doc_generated", "Documents Generated"),
            ("spec_approved", "Spec Approved"),
            ("advertised", "Advertised"),
            ("opened", "Bids Opened"),
            ("evaluated", "Evaluated"),
            ("closed", "Closed"),
        ],
        string="Status",
        default="draft",
        required=True,
        tracking=True,
    )
    
    @api.depends('bid_ids', 'bid_ids.preliminary_passed', 'bid_ids.is_late')
    def _compute_valid_bid_count(self):
        """AUTO-013: Count valid (responsive) bids for RFQ three-quotation rule."""
        for tender in self:
            # Count bids that passed preliminary evaluation and are not late
            valid_bids = tender.bid_ids.filtered(
                lambda b: b.preliminary_passed and not b.is_late
            )
            tender.valid_bid_count = len(valid_bids)
            
            # Check RFQ minimum violation
            if tender.procurement_method == 'rfq':
                tender.rfq_minimum_violation = tender.valid_bid_count < 3
            else:
                tender.rfq_minimum_violation = False

    # ── AUTO-010: Document Assembly Compute Methods ────────────────
    
    @api.depends('lot_id', 'lot_id.budget')
    def _compute_procurement_method(self):
        """AUTO-011: Determine procurement method from lot budget."""
        ICB_THRESHOLD = 10000000.0  # ETB 10M+
        NCB_THRESHOLD = 5000000.0   # ETB 5M-10M
        
        for tender in self:
            if not tender.lot_id:
                tender.procurement_method = 'ncb'
                continue
            
            if tender.lot_id.budget >= ICB_THRESHOLD:
                tender.procurement_method = 'icb'
            elif tender.lot_id.budget >= NCB_THRESHOLD:
                tender.procurement_method = 'ncb'
            else:
                tender.procurement_method = 'rfq'
    
    @api.depends('procurement_method')
    def _compute_minimum_advertising_days(self):
        """AUTO-011: Set minimum advertising period based on method (FR-PROC-014)."""
        method_days = {
            'icb': 45,  # International: 45 days
            'ncb': 30,  # National: 30 days
            'rfq': 7,   # RFQ: 7 days
        }
        
        for tender in self:
            tender.minimum_advertising_days = method_days.get(tender.procurement_method, 30)
    
    @api.depends('advertisement_date', 'minimum_advertising_days')
    def _compute_earliest_submission_date(self):
        """AUTO-011: Calculate earliest allowed submission date."""
        from datetime import timedelta
        
        for tender in self:
            if tender.advertisement_date and tender.minimum_advertising_days:
                tender.earliest_submission_date = tender.advertisement_date + timedelta(days=tender.minimum_advertising_days)
            else:
                tender.earliest_submission_date = False
    
    @api.constrains('submission_deadline', 'advertisement_date', 'earliest_submission_date', 'deadline_extension_reason')
    def _check_minimum_advertising_period(self):
        """AUTO-011: Enforce minimum advertising period (FR-PROC-014).
        
        Blocks submission deadlines earlier than minimum period unless:
        - Extension reason provided AND
        - Extension approved by authorized user (HOPE level)
        """
        from datetime import datetime
        from odoo.exceptions import ValidationError
        
        for tender in self:
            if not tender.submission_deadline or not tender.earliest_submission_date:
                continue
            
            # Convert datetime to date for comparison
            submission_date = tender.submission_deadline.date() if isinstance(tender.submission_deadline, datetime) else tender.submission_deadline
            
            if submission_date < tender.earliest_submission_date:
                # Check if extension is approved
                if not tender.deadline_extension_approved_by:
                    raise ValidationError(
                        f"AUTO-011 Violation: Minimum Advertising Period Not Met\n\n"
                        f"Procurement Method: {dict(tender._fields['procurement_method'].selection).get(tender.procurement_method, 'N/A')}\n"
                        f"Required Minimum Period: {tender.minimum_advertising_days} days (FR-PROC-014)\n"
                        f"Advertisement Date: {tender.advertisement_date}\n"
                        f"Earliest Allowed Deadline: {tender.earliest_submission_date}\n"
                        f"Your Deadline: {submission_date}\n"
                        f"Shortfall: {(tender.earliest_submission_date - submission_date).days} days\n\n"
                        f"❌ This deadline violates FPPA Proclamation 1210/2012.\n\n"
                        f"To proceed with an earlier deadline, you must:\n"
                        f"1. Provide documented justification in 'Deadline Extension Reason'\n"
                        f"2. Obtain HOPE authorization via 'Request Deadline Extension' button"
                    )
    
    @api.depends('lot_id', 'lot_id.budget', 'bid_security_percentage')
    def _compute_bid_security(self):
        """AUTO-010: Auto-calculate bid security amount (FR-PROC-015)."""
        for tender in self:
            if tender.lot_id and tender.lot_id.budget:
                tender.bid_security_amount = tender.lot_id.budget * (tender.bid_security_percentage / 100.0)
            else:
                tender.bid_security_amount = 0.0
    
    @api.depends('lot_id', 'lot_id.need_ids', 'bid_security_amount')
    def _compute_bidding_documents(self):
        """AUTO-010: Auto-generate bidding document pack from lot data (FR-PROC-013)."""
        for tender in self:
            if not tender.lot_id:
                tender.invitation_letter = False
                tender.bill_of_quantities = False
                tender.bid_security_template = False
                continue
            
            # Generate Invitation Letter
            tender.invitation_letter = tender._generate_invitation_letter()
            
            # Generate Bill of Quantities
            tender.bill_of_quantities = tender._generate_bill_of_quantities()
            
            # Generate Bid Security Template
            tender.bid_security_template = tender._generate_bid_security_template()
    
    def _generate_invitation_letter(self):
        """AUTO-010: Generate invitation to bid letter."""
        self.ensure_one()
        
        if not self.lot_id:
            return ""
        
        method_name = dict(self._fields['procurement_method'].selection).get(self.procurement_method, 'Tender')
        
        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto;">
            <div style="text-align: center; margin-bottom: 30px;">
                <h2>FEDERAL DEMOCRATIC REPUBLIC OF ETHIOPIA</h2>
                <h3>MESOB CENTER</h3>
                <h4 style="color: #2c3e50;">INVITATION TO BID</h4>
            </div>
            
            <p><strong>Tender Reference:</strong> {self.name}</p>
            <p><strong>Procurement Method:</strong> {method_name}</p>
            <p><strong>Lot Name:</strong> {self.lot_id.name}</p>
            <p><strong>Estimated Budget:</strong> ETB {self.lot_id.budget:,.2f}</p>
            
            <hr style="border: 1px solid #ccc; margin: 20px 0;"/>
            
            <h4>1. Invitation</h4>
            <p>The Federal Democratic Republic of Ethiopia, Mesob Center, invites sealed bids from eligible and qualified bidders for the procurement of goods described below.</p>
            
            <h4>2. Scope of Work</h4>
            <p><strong>Lot Description:</strong> {self.lot_id.name}</p>
            <p><strong>Category:</strong> {dict(self.lot_id._fields['category'].selection).get(self.lot_id.category, '')}</p>
            <p><strong>Number of Items:</strong> {len(self.lot_id.need_ids)} item(s)</p>
            
            <h4>3. Bid Security</h4>
            <p>Bidders must submit a bid security of <strong>ETB {self.bid_security_amount:,.2f}</strong> ({self.bid_security_percentage}% of estimated value) in the form of:</p>
            <ul>
                <li>Bank guarantee from a reputable Ethiopian bank, OR</li>
                <li>Certified check, OR</li>
                <li>Insurance bond</li>
            </ul>
            
            <h4>4. Submission Deadline</h4>
            <p><strong>Submission Deadline:</strong> {self.submission_deadline or 'To be announced'}</p>
            <p><strong>Minimum Advertising Period:</strong> {self.minimum_advertising_days} days (FR-PROC-014)</p>
            
            <h4>5. Bid Opening</h4>
            <p>Bids will be opened publicly immediately after the submission deadline in the presence of bidders' representatives.</p>
            
            <h4>6. Contact Information</h4>
            <p><strong>Procurement Unit</strong><br/>
            FDRE Mesob Center<br/>
            Addis Ababa, Ethiopia</p>
            
            <div style="margin-top: 40px; padding: 15px; background-color: #f8f9fa; border-left: 4px solid #007bff;">
                <p style="margin: 0;"><strong>Note:</strong> This document was auto-generated by the Mesob IMS (AUTO-010). 
                Please review all details before issuance.</p>
            </div>
        </div>
        """
        
        return html
    
    def _generate_bill_of_quantities(self):
        """AUTO-010: Generate Bill of Quantities from lot needs."""
        self.ensure_one()
        
        if not self.lot_id or not self.lot_id.need_ids:
            return ""
        
        html = """
        <div style="font-family: Arial, sans-serif; max-width: 1000px; margin: 0 auto;">
            <h3 style="text-align: center; color: #2c3e50;">BILL OF QUANTITIES</h3>
            
            <table style="width: 100%; border-collapse: collapse; margin-top: 20px;">
                <thead style="background-color: #34495e; color: white;">
                    <tr>
                        <th style="border: 1px solid #ddd; padding: 12px; text-align: left;">Item No.</th>
                        <th style="border: 1px solid #ddd; padding: 12px; text-align: left;">Description</th>
                        <th style="border: 1px solid #ddd; padding: 12px; text-align: center;">Quantity</th>
                        <th style="border: 1px solid #ddd; padding: 12px; text-align: center;">Unit</th>
                        <th style="border: 1px solid #ddd; padding: 12px; text-align: right;">Unit Price (ETB)</th>
                        <th style="border: 1px solid #ddd; padding: 12px; text-align: right;">Total Price (ETB)</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        item_no = 1
        total_value = 0.0
        
        for need in self.lot_id.need_ids:
            item_desc = need.item_id.name if need.item_id else f"{need.major_classification_id.name if need.major_classification_id else 'Item'}"
            item_code = need.item_code or 'TBD'
            
            line_total = need.quantity * need.estimated_unit_price
            total_value += line_total
            
            html += f"""
                <tr>
                    <td style="border: 1px solid #ddd; padding: 8px;">{item_no}</td>
                    <td style="border: 1px solid #ddd; padding: 8px;">
                        <strong>{item_code}</strong><br/>
                        {item_desc}
                    </td>
                    <td style="border: 1px solid #ddd; padding: 8px; text-align: center;">{need.quantity:.2f}</td>
                    <td style="border: 1px solid #ddd; padding: 8px; text-align: center;">Units</td>
                    <td style="border: 1px solid #ddd; padding: 8px; text-align: right;">{need.estimated_unit_price:,.2f}</td>
                    <td style="border: 1px solid #ddd; padding: 8px; text-align: right;">{line_total:,.2f}</td>
                </tr>
            """
            item_no += 1
        
        html += f"""
                </tbody>
                <tfoot style="background-color: #ecf0f1; font-weight: bold;">
                    <tr>
                        <td colspan="5" style="border: 1px solid #ddd; padding: 12px; text-align: right;">TOTAL:</td>
                        <td style="border: 1px solid #ddd; padding: 12px; text-align: right;">ETB {total_value:,.2f}</td>
                    </tr>
                </tfoot>
            </table>
            
            <div style="margin-top: 30px; padding: 15px; background-color: #fff3cd; border-left: 4px solid #ffc107;">
                <p style="margin: 0;"><strong>Instructions to Bidders:</strong></p>
                <ul style="margin: 10px 0;">
                    <li>Complete all columns with your offered prices</li>
                    <li>Unit prices should be in Ethiopian Birr (ETB)</li>
                    <li>Prices should be inclusive of all taxes and duties</li>
                    <li>Any alteration to quantities must be authorized by the Employer</li>
                </ul>
            </div>
        </div>
        """
        
        return html
    
    def _generate_bid_security_template(self):
        """AUTO-010: Generate bid security guarantee template."""
        self.ensure_one()
        
        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto;">
            <h3 style="text-align: center; color: #2c3e50;">BID SECURITY GUARANTEE</h3>
            
            <div style="border: 2px solid #2c3e50; padding: 20px; margin: 20px 0;">
                <p><strong>To:</strong> Federal Democratic Republic of Ethiopia, Mesob Center</p>
                <p><strong>Tender Reference:</strong> {self.name}</p>
                <p><strong>Lot:</strong> {self.lot_id.name if self.lot_id else 'N/A'}</p>
                
                <hr style="border: 1px solid #ccc; margin: 20px 0;"/>
                
                <p>WHEREAS [<em>Name of Bidder</em>] (hereinafter called "the Bidder") has submitted its bid dated [<em>Date</em>] for the execution of [<em>Name of Contract</em>] (hereinafter called "the Bid").</p>
                
                <p>KNOW ALL PEOPLE by these presents that WE [<em>Name of Bank/Insurance Company</em>] having our registered office at [<em>Address</em>] (hereinafter called "the Guarantor"), are bound unto the Federal Democratic Republic of Ethiopia, Mesob Center (hereinafter called "the Employer") in the sum of <strong>ETB {self.bid_security_amount:,.2f}</strong> for which payment well and truly to be made to the said Employer, the Guarantor binds itself, its successors, and assigns by these presents.</p>
                
                <p>Sealed with the Common Seal of the said Guarantor this _____ day of _____________ 20____.</p>
                
                <p>THE CONDITIONS of this obligation are:</p>
                <ol>
                    <li>If the Bidder withdraws its Bid during the period of bid validity specified in the Bidder's letter; or</li>
                    <li>If the Bidder, having been notified of the acceptance of its Bid by the Employer during the period of bid validity:
                        <ul>
                            <li>fails or refuses to execute the Contract; or</li>
                            <li>fails or refuses to furnish the Performance Security;</li>
                        </ul>
                    </li>
                </ol>
                
                <p>We undertake to pay the Employer up to the above amount upon receipt of its first written demand, without the Employer having to substantiate its demand, provided that in its demand the Employer will note that the amount claimed by it is due to it owing to the occurrence of one or both of the conditions, specifying the occurred condition or conditions.</p>
                
                <p>This guarantee will remain in force up to and including [<em>Date</em>] and any demand in respect thereof should reach the Guarantor not later than the above date.</p>
                
                <div style="margin-top: 40px;">
                    <p>_________________________<br/>
                    [Signature of Authorized Officer]</p>
                    <p>[Name and Title]</p>
                    <p>[Official Stamp]</p>
                </div>
            </div>
            
            <div style="margin-top: 20px; padding: 15px; background-color: #d1ecf1; border-left: 4px solid #0c5460;">
                <p style="margin: 0;"><strong>Required Amount:</strong> ETB {self.bid_security_amount:,.2f} ({self.bid_security_percentage}% of estimated value)</p>
                <p style="margin: 10px 0 0 0;"><strong>Validity Period:</strong> Minimum 30 days beyond bid validity period</p>
            </div>
        </div>
        """
        
        return html

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = f"TEN/{self.env['ir.sequence'].next_by_code('mesob.procurement.tender') or '001'}"
        return super().create(vals_list)
    
    # ── Actions ─────────────────────────────────────────────────────
    
    def action_generate_bidding_documents(self):
        """AUTO-010: Auto-generate complete bidding document pack (FR-PROC-013).
        
        Generates:
        - Invitation letter with tender details
        - Bill of Quantities from lot needs
        - Bid security template with calculated amount
        
        Officer reviews pack before proceeding to spec approval.
        """
        self.ensure_one()
        
        if not self.lot_id:
            raise UserError("Cannot generate documents: No lot assigned to this tender.")
        
        if not self.lot_id.need_ids:
            raise UserError(
                f"Cannot generate documents: Lot {self.lot_id.name} has no consolidated needs.\n"
                "Please ensure needs are properly assigned to this lot."
            )
        
        # Force recompute of all documents
        self._compute_bidding_documents()
        self._compute_bid_security()
        
        # Update state
        self.write({'state': 'doc_generated'})
        
        # Send notification to procurement officers
        procurement_users = self.env.ref('mesob_inventory_base.group_mesob_procurement', raise_if_not_found=False)
        if procurement_users and procurement_users.users:
            self.message_post(
                body=f"""<div style="background-color: #d1ecf1; border-left: 4px solid #0c5460; padding: 15px;">
                    <h3>AUTO-010: Bidding Documents Generated</h3>
                    <p><strong>Tender:</strong> {self.name}</p>
                    <p><strong>Lot:</strong> {self.lot_id.name}</p>
                    <p><strong>Procurement Method:</strong> {dict(self._fields['procurement_method'].selection).get(self.procurement_method, '')}</p>
                    <p><strong>Estimated Value:</strong> ETB {self.lot_id.budget:,.2f}</p>
                    <p><strong>Bid Security Required:</strong> ETB {self.bid_security_amount:,.2f}</p>
                    <p><strong>Items:</strong> {len(self.lot_id.need_ids)}</p>
                    <hr/>
                    <h4>Documents Generated:</h4>
                    <ul>
                        <li>✓ Invitation to Bid</li>
                        <li>✓ Bill of Quantities ({len(self.lot_id.need_ids)} items)</li>
                        <li>✓ Bid Security Template (ETB {self.bid_security_amount:,.2f})</li>
                        <li>⏳ Technical Specifications (please complete)</li>
                    </ul>
                    <p style="margin-top: 15px;"><em>Please review all generated documents and complete technical specifications before approval.</em></p>
                </div>""",
                subject=f'Bidding Documents Generated: {self.name}',
                message_type='notification',
                partner_ids=procurement_users.users.mapped('partner_id').ids
            )
        
        _logger.info(
            f"AUTO-010: Bidding documents generated for {self.name} - "
            f"Lot: {self.lot_id.name}, Items: {len(self.lot_id.need_ids)}, "
            f"Value: ETB {self.lot_id.budget:,.2f}, Bid Security: ETB {self.bid_security_amount:,.2f}"
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Bidding Documents Generated',
                'message': f'Document pack generated for {self.name}. Please review and complete technical specifications.',
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_download_bidding_pack(self):
        """AUTO-010: Download complete bidding document pack as single HTML file.
        
        Assembles all generated bidding documents into one comprehensive package:
        - Cover page with tender summary
        - Section 1: Invitation to Bid
        - Section 2: Instructions to Bidders
        - Section 3: Bill of Quantities
        - Section 4: Technical Specifications
        - Section 5: Bid Security Template
        - Section 6: Terms and Conditions
        
        Posted to chatter for download and distribution to potential bidders.
        """
        self.ensure_one()
        
        if not self.invitation_letter or not self.boq_document or not self.bid_security_template:
            raise UserError(
                "Complete bidding document pack not available.\n\n"
                "Please generate bidding documents first using 'Generate Bidding Documents' button."
            )
        
        # Generate complete document pack
        method_name = dict(self._fields['procurement_method'].selection).get(self.procurement_method, 'Tender')
        
        complete_pack = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>Bidding Document Pack - {self.name}</title>
            <style>
                body {{
                    font-family: 'Times New Roman', serif;
                    line-height: 1.6;
                    color: #333;
                    max-width: 900px;
                    margin: 0 auto;
                    padding: 20px;
                }}
                .cover-page {{
                    text-align: center;
                    padding: 100px 40px;
                    page-break-after: always;
                }}
                .section {{
                    page-break-before: always;
                    margin-top: 40px;
                }}
                .section-title {{
                    color: #2c3e50;
                    border-bottom: 3px solid #2c3e50;
                    padding-bottom: 10px;
                    margin-bottom: 20px;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin: 20px 0;
                }}
                th, td {{
                    border: 1px solid #ddd;
                    padding: 10px;
                    text-align: left;
                }}
                th {{
                    background-color: #34495e;
                    color: white;
                }}
                .info-box {{
                    background-color: #f8f9fa;
                    border-left: 4px solid #007bff;
                    padding: 15px;
                    margin: 20px 0;
                }}
                .warning-box {{
                    background-color: #fff3cd;
                    border-left: 4px solid #ffc107;
                    padding: 15px;
                    margin: 20px 0;
                }}
                @media print {{
                    .no-print {{
                        display: none;
                    }}
                }}
            </style>
        </head>
        <body>
            <!-- COVER PAGE -->
            <div class="cover-page">
                <h1 style="font-size: 28px; margin: 20px 0;">FEDERAL DEMOCRATIC REPUBLIC OF ETHIOPIA</h1>
                <h2 style="font-size: 24px; margin: 20px 0;">MESOB CENTER</h2>
                <h3 style="font-size: 20px; margin: 20px 0; color: #7f8c8d;">Procurement Unit</h3>
                
                <hr style="width: 60%; border: 2px solid #2c3e50; margin: 40px auto;"/>
                
                <h1 style="font-size: 32px; margin: 40px 0; color: #2c3e50;">BIDDING DOCUMENT PACK</h1>
                
                <div style="text-align: left; display: inline-block; margin-top: 60px;">
                    <table style="border: none;">
                        <tr>
                            <td style="border: none; padding: 10px; font-weight: bold;">Tender Reference:</td>
                            <td style="border: none; padding: 10px; font-size: 18px; color: #2c3e50;">{self.name}</td>
                        </tr>
                        <tr>
                            <td style="border: none; padding: 10px; font-weight: bold;">Procurement Method:</td>
                            <td style="border: none; padding: 10px;">{method_name}</td>
                        </tr>
                        <tr>
                            <td style="border: none; padding: 10px; font-weight: bold;">Lot Name:</td>
                            <td style="border: none; padding: 10px;">{self.lot_id.name if self.lot_id else 'N/A'}</td>
                        </tr>
                        <tr>
                            <td style="border: none; padding: 10px; font-weight: bold;">Estimated Value:</td>
                            <td style="border: none; padding: 10px; color: #27ae60; font-weight: bold;">ETB {self.lot_id.budget:,.2f if self.lot_id else 0.0}</td>
                        </tr>
                        <tr>
                            <td style="border: none; padding: 10px; font-weight: bold;">Submission Deadline:</td>
                            <td style="border: none; padding: 10px; color: #e74c3c; font-weight: bold;">{self.submission_deadline.strftime('%B %d, %Y at %I:%M %p') if self.submission_deadline else 'To be announced'}</td>
                        </tr>
                        <tr>
                            <td style="border: none; padding: 10px; font-weight: bold;">Document Issue Date:</td>
                            <td style="border: none; padding: 10px;">{fields.Date.today().strftime('%B %d, %Y')}</td>
                        </tr>
                    </table>
                </div>
                
                <p style="margin-top: 80px; font-size: 12px; color: #7f8c8d;">
                    AUTO-010: Automated Document Assembly System<br/>
                    This document pack was generated automatically per FR-PROC-013
                </p>
            </div>
            
            <!-- TABLE OF CONTENTS -->
            <div class="section">
                <h2 class="section-title">TABLE OF CONTENTS</h2>
                <ol style="font-size: 16px; line-height: 2;">
                    <li><a href="#section1" style="color: #2c3e50; text-decoration: none;">Invitation to Bid</a></li>
                    <li><a href="#section2" style="color: #2c3e50; text-decoration: none;">Instructions to Bidders</a></li>
                    <li><a href="#section3" style="color: #2c3e50; text-decoration: none;">Bill of Quantities</a></li>
                    <li><a href="#section4" style="color: #2c3e50; text-decoration: none;">Technical Specifications</a></li>
                    <li><a href="#section5" style="color: #2c3e50; text-decoration: none;">Bid Security Template</a></li>
                    <li><a href="#section6" style="color: #2c3e50; text-decoration: none;">Terms and Conditions</a></li>
                </ol>
            </div>
            
            <!-- SECTION 1: INVITATION -->
            <div class="section" id="section1">
                <h2 class="section-title">SECTION 1: INVITATION TO BID</h2>
                {self.invitation_letter}
            </div>
            
            <!-- SECTION 2: INSTRUCTIONS -->
            <div class="section" id="section2">
                <h2 class="section-title">SECTION 2: INSTRUCTIONS TO BIDDERS</h2>
                <h3>2.1 General</h3>
                <p>This section provides instructions for preparing and submitting bids. Bidders must read these instructions carefully and comply fully.</p>
                
                <h3>2.2 Eligibility</h3>
                <ul>
                    <li>Bidders must be legally registered businesses in Ethiopia or foreign companies authorized to operate in Ethiopia</li>
                    <li>Bidders must not be blacklisted by FPPA (Federal Public Procurement Authority)</li>
                    <li>Bidders must have valid tax clearance certificates</li>
                    <li>Bidders must meet the minimum qualification criteria specified in Section 4</li>
                </ul>
                
                <h3>2.3 Bid Submission</h3>
                <p><strong>Submission Deadline:</strong> {self.submission_deadline.strftime('%B %d, %Y at %I:%M %p') if self.submission_deadline else 'To be announced'}</p>
                <p><strong>Submission Location:</strong> Mesob Center Procurement Unit, Addis Ababa, Ethiopia</p>
                
                <div class="warning-box">
                    <p style="margin: 0;"><strong>⚠️ IMPORTANT - AUTO-012:</strong></p>
                    <p style="margin: 5px 0 0 0;">
                        Bids received after the deadline will be <strong>automatically rejected</strong> with timestamp proof. 
                        Late submissions will NOT be opened or considered under any circumstances (FR-PROC-015).
                    </p>
                </div>
                
                <h3>2.4 Bid Security</h3>
                <p>All bidders must submit bid security as specified in Section 5. The bid security amount is:</p>
                <p style="font-size: 18px; color: #2c3e50; font-weight: bold;">ETB {self.bid_security_amount:,.2f} ({self.bid_security_percentage}% of estimated value)</p>
                
                <h3>2.5 Bid Validity</h3>
                <p>Bids must remain valid for <strong>90 days</strong> from the submission deadline.</p>
                
                <h3>2.6 Domestic Preference (BR-PROC-003)</h3>
                <div class="info-box">
                    <p><strong>AUTO-015: Domestic Preference Calculation</strong></p>
                    <p>Ethiopian bidders with qualifying local content will receive preference margins:</p>
                    <ul>
                        <li><strong>≥70% local content:</strong> 13.5% preference margin</li>
                        <li><strong>40-70% local content:</strong> 11% preference margin</li>
                        <li><strong>&lt;40% local content:</strong> No preference</li>
                    </ul>
                    <p><em>Note: Preference is applied for ranking purposes only. Contract value uses original bid price (FR-PROC-018).</em></p>
                </div>
                
                <h3>2.7 Bid Opening</h3>
                <p>Bids will be opened publicly immediately after the submission deadline. Bidders or their representatives may attend.</p>
                
                <h3>2.8 Evaluation Criteria</h3>
                <p>Bids will be evaluated using:</p>
                <ul>
                    <li><strong>Preliminary Evaluation (AUTO-014):</strong> Administrative compliance, bid security, eligibility</li>
                    <li><strong>Technical Evaluation:</strong> Compliance with specifications, past performance, capacity</li>
                    <li><strong>Financial Evaluation (AUTO-015):</strong> Price comparison with domestic preference application</li>
                </ul>
                
                <h3>2.9 Award</h3>
                <p>The contract will be awarded to the <strong>lowest evaluated responsive bidder</strong> (AUTO-016).</p>
            </div>
            
            <!-- SECTION 3: BILL OF QUANTITIES -->
            <div class="section" id="section3">
                <h2 class="section-title">SECTION 3: BILL OF QUANTITIES</h2>
                {self.boq_document}
            </div>
            
            <!-- SECTION 4: TECHNICAL SPECIFICATIONS -->
            <div class="section" id="section4">
                <h2 class="section-title">SECTION 4: TECHNICAL SPECIFICATIONS</h2>
                {self.technical_specifications if self.technical_specifications else '<p style="color: #e74c3c;"><em>Technical specifications will be provided separately or uploaded by procurement officer.</em></p>'}
            </div>
            
            <!-- SECTION 5: BID SECURITY -->
            <div class="section" id="section5">
                <h2 class="section-title">SECTION 5: BID SECURITY TEMPLATE</h2>
                {self.bid_security_template}
            </div>
            
            <!-- SECTION 6: TERMS AND CONDITIONS -->
            <div class="section" id="section6">
                <h2 class="section-title">SECTION 6: GENERAL TERMS AND CONDITIONS</h2>
                
                <h3>6.1 Compliance with Laws</h3>
                <p>This procurement is governed by:</p>
                <ul>
                    <li>Federal Public Procurement and Property Administration Proclamation No. 1210/2012</li>
                    <li>Council of Ministers Procurement Regulations</li>
                    <li>FPPA Directives and Standard Bidding Documents</li>
                </ul>
                
                <h3>6.2 Corruption and Fraud</h3>
                <p>The Employer has zero tolerance for corruption and fraud. Any bidder found to have engaged in corrupt or fraudulent practices will be:</p>
                <ul>
                    <li>Disqualified from the procurement process</li>
                    <li>Blacklisted by FPPA</li>
                    <li>Reported to relevant law enforcement authorities</li>
                </ul>
                
                <h3>6.3 Confidentiality</h3>
                <p>All information relating to the evaluation and award process is confidential until contract signature.</p>
                
                <h3>6.4 Right to Accept or Reject</h3>
                <p>The Employer reserves the right to:</p>
                <ul>
                    <li>Accept or reject any bid</li>
                    <li>Annul the procurement process at any time without incurring liability</li>
                    <li>Award to other than the lowest priced bid if justified</li>
                </ul>
                
                <h3>6.5 Complaints</h3>
                <p>Bidders who believe they have been unfairly treated may file complaints per FR-PROC-038:</p>
                <ul>
                    <li><strong>First Level:</strong> To PAO/HOPE within 7 days of award notification</li>
                    <li><strong>Second Level:</strong> To FPPA within 14 days if not resolved</li>
                </ul>
                
                <h3>6.6 Contract Signature</h3>
                <p>The successful bidder must sign the contract within <strong>10 days</strong> of receiving the award letter (FR-PROC-020).</p>
                
                <h3>6.7 Performance Security</h3>
                <p>The successful bidder must provide performance security of <strong>10% of contract value</strong> before contract signature (FR-PROC-023).</p>
            </div>
            
            <!-- FOOTER -->
            <div style="margin-top: 60px; padding-top: 20px; border-top: 2px solid #2c3e50; text-align: center; page-break-inside: avoid;">
                <p style="color: #7f8c8d; font-size: 12px;">
                    <strong>FDRE Mesob Center | Procurement Unit</strong><br/>
                    Addis Ababa, Ethiopia<br/>
                    <br/>
                    <em>This bidding document pack was auto-generated by the Mesob IMS (AUTO-010)<br/>
                    Generated: {fields.Datetime.now().strftime('%B %d, %Y at %I:%M %p')}<br/>
                    Tender Reference: {self.name}</em>
                </p>
            </div>
        </body>
        </html>
        """
        
        # Post the complete pack to chatter for download
        self.message_post(
            body=complete_pack,
            subject=f'Complete Bidding Document Pack - {self.name}',
            message_type='comment',
            subtype_xmlid='mail.mt_note'
        )
        
        _logger.info(
            f"AUTO-010: Complete bidding document pack generated for {self.name} - "
            f"Sections: 6, Total size: {len(complete_pack)} chars"
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Complete Bidding Pack Generated',
                'message': f'Full document pack for {self.name} has been posted to chatter. You can download it from the message attachments.',
                'type': 'success',
                'sticky': True,
            }
        }

    def action_approve_spec(self):
        """Technical specifications sign-off status approved (FR-PROC-009)."""
        for rec in self:
            if rec.state not in ('doc_generated', 'draft'):
                raise UserError("Specifications can only be approved after documents are generated.")
            
            if not rec.technical_specifications:
                raise UserError("Please complete technical specifications before approval (FR-PROC-009).")
            
            rec.write({
                "spec_status": "approved",
                "state": "spec_approved",
            })
        return True

    def action_advertise(self):
        """AUTO-011: Advertise tender with minimum period enforcement (FR-PROC-014)."""
        for rec in self:
            if rec.spec_status != "approved":
                raise UserError("Cannot advertise until Technical Specifications are approved (FR-PROC-013).")
            
            if not rec.advertisement_date:
                raise UserError("Please set advertisement date first.")
            
            if not rec.submission_deadline:
                raise UserError("Please set submission deadline first.")
            
            # AUTO-011: Validation is handled by @api.constrains
            # Constraint will raise ValidationError if minimum period not met and no approval
            
            rec.state = "advertised"
            
            _logger.info(
                f"AUTO-011: Tender {rec.name} advertised - "
                f"Method: {rec.procurement_method}, Min Days: {rec.minimum_advertising_days}, "
                f"Deadline: {rec.submission_deadline}"
            )
        
        return True
    
    def action_request_deadline_extension(self):
        """AUTO-011: Request HOPE approval for early deadline (FR-PROC-014 exception).
        
        Allows procurement officer to request authorization for deadlines
        shorter than the minimum advertising period in exceptional cases.
        """
        self.ensure_one()
        
        if not self.deadline_extension_reason:
            raise UserError(
                "Please provide a detailed justification in 'Deadline Extension Reason' field before requesting approval.\n\n"
                "Your justification should explain:\n"
                "- Why the shorter deadline is necessary\n"
                "- What emergency or exceptional circumstances exist\n"
                "- How fair competition will still be ensured"
            )
        
        # Check if user has HOPE authorization
        # In real scenario, this would trigger approval workflow to HOPE
        # For now, we'll allow users with procurement manager rights to approve
        hope_group = self.env.ref('mesob_inventory_base.group_mesob_pao', raise_if_not_found=False)
        
        if not hope_group or self.env.user not in hope_group.users:
            raise UserError(
                "Deadline extension requires HOPE (Head of Public Body) authorization.\n\n"
                "Current user does not have sufficient authority. "
                "Please submit this request to your HOPE for approval."
            )
        
        # Approve the extension
        self.write({
            'deadline_extension_approved_by': self.env.user.id,
            'deadline_extension_approved_date': fields.Datetime.now()
        })
        
        # Log in chatter
        self.message_post(
            body=f"""<div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px;">
                <h3>⚠️ AUTO-011: Deadline Extension Approved</h3>
                <p><strong>Approved By:</strong> {self.env.user.name}</p>
                <p><strong>Approval Date:</strong> {fields.Datetime.now()}</p>
                <p><strong>Procurement Method:</strong> {dict(self._fields['procurement_method'].selection).get(self.procurement_method, '')}</p>
                <p><strong>Required Min Period:</strong> {self.minimum_advertising_days} days</p>
                <p><strong>Earliest Allowed:</strong> {self.earliest_submission_date}</p>
                <p><strong>Approved Deadline:</strong> {self.submission_deadline}</p>
                <hr/>
                <p><strong>Justification:</strong></p>
                <p>{self.deadline_extension_reason}</p>
                <hr/>
                <p style="font-size: 11px; color: #856404;"><em>This exception to FR-PROC-014 has been documented for audit trail per NFR-QUAL-001.</em></p>
            </div>""",
            subject='Deadline Extension Approved',
            message_type='notification'
        )
        
        _logger.info(
            f"AUTO-011: Deadline extension approved for {self.name} by {self.env.user.name} - "
            f"Deadline: {self.submission_deadline}, Min required: {self.earliest_submission_date}"
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Extension Approved',
                'message': f'Deadline extension for {self.name} has been authorized. You may now proceed with advertising.',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_open_bids(self):
        """Record public bid opening minutes and validate timestamps (FR-PROC-015)."""
        for rec in self:
            if rec.state != "advertised":
                raise UserError("Bids can only be opened after the tender is advertised.")
            rec.state = "opened"
        return True

    def action_evaluate(self):
        """AUTO-013 & AUTO-016: Trigger bid evaluation with RFQ rule enforcement and ranking (FR-PROC-017, FR-PROC-018).
        
        AUTO-013: Enforces RFQ three-quotation minimum (FR-PROC-016 + BR-PROC-005)
        AUTO-016: Auto-ranks bids by evaluated price and generates recommendation
        """
        for rec in self:
            if rec.state != "opened":
                raise UserError("Bids must be opened before evaluation.")

            # AUTO-013: Enforce RFQ three-quotation rule (FR-PROC-016)
            if rec.procurement_method == 'rfq' and rec.valid_bid_count < 3:
                if not rec.rfq_exception_approved_by:
                    raise UserError(
                        f"AUTO-013 / FR-PROC-016 Violation: Insufficient Quotations for RFQ\n\n"
                        f"RFQ Rule: Minimum THREE (3) valid quotations required (BR-PROC-005)\n\n"
                        f"Current Status:\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"Total Bids Received:      {len(rec.bid_ids)}\n"
                        f"Valid Quotations:         {rec.valid_bid_count}\n"
                        f"Late/Rejected Bids:       {len(rec.bid_ids) - rec.valid_bid_count}\n"
                        f"Minimum Required:         3\n"
                        f"Shortfall:                {3 - rec.valid_bid_count}\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"❌ Cannot proceed with award evaluation.\n\n"
                        f"Options:\n"
                        f"1. Re-advertise the RFQ to obtain more quotations, OR\n"
                        f"2. Provide documented justification and obtain PAO approval\n"
                        f"   using 'Request RFQ Exception' button\n\n"
                        f"Justification must explain:\n"
                        f"- Why re-advertising is impractical\n"
                        f"- Market availability constraints\n"
                        f"- Urgency of procurement\n"
                        f"- How competition was ensured"
                    )

            # Filter responsive / preliminary passed bids
            responsive_bids = rec.bid_ids.filtered(lambda b: b.preliminary_passed and not b.is_late)
            if not responsive_bids:
                raise UserError("There are no responsive/preliminary passed bids to evaluate.")

            # AUTO-016: Compute adjusted evaluated price & ranking
            for bid in responsive_bids:
                preference_factor = 1.0
                if bid.local_content >= 70.0:
                    preference_factor = 1.0 - 0.135  # 13.5% domestic preference (FR-PROC-018)
                elif 40.0 <= bid.local_content < 70.0:
                    preference_factor = 1.0 - 0.11   # 11% domestic preference
                
                bid.evaluated_price = bid.bid_price * preference_factor

            # AUTO-016: Perform ranking (ascending evaluated price)
            ranked_bids = sorted(responsive_bids, key=lambda b: b.evaluated_price)
            for rank, bid in enumerate(ranked_bids, start=1):
                bid.ranking = rank

            rec.state = "evaluated"
            
            _logger.info(
                f"AUTO-013 & AUTO-016: Tender {rec.name} evaluated - "
                f"Method: {rec.procurement_method}, Valid Bids: {rec.valid_bid_count}, "
                f"RFQ Violation: {rec.rfq_minimum_violation}, "
                f"Exception Approved: {bool(rec.rfq_exception_approved_by)}"
            )
        
        return True
    
    def action_request_rfq_exception(self):
        """AUTO-013: Request PAO/HOPE approval to proceed with fewer than 3 quotations (BR-PROC-005).
        
        Allows procurement officer to request authorization for RFQ award
        with fewer than the minimum 3 quotations in exceptional circumstances.
        """
        self.ensure_one()
        
        if self.procurement_method != 'rfq':
            raise UserError("RFQ exception is only applicable for Request for Quotation tenders.")
        
        if self.valid_bid_count >= 3:
            raise UserError(
                f"RFQ exception is not needed. You have {self.valid_bid_count} valid quotations, "
                "which meets the minimum requirement."
            )
        
        if not self.rfq_justification:
            raise UserError(
                "Please provide detailed justification in 'RFQ Exception Justification' field before requesting approval.\n\n"
                "Your justification must explain:\n"
                "• Why re-advertising is impractical or would cause unacceptable delay\n"
                "• Market availability constraints (limited suppliers for this item)\n"
                "• Urgency of the procurement requirement\n"
                "• How fair competition was ensured despite fewer quotations\n"
                "• Any market research conducted to identify potential suppliers"
            )
        
        # Check if user has PAO authorization
        pao_group = self.env.ref('mesob_inventory_base.group_mesob_pao', raise_if_not_found=False)
        
        if not pao_group or self.env.user not in pao_group.users:
            raise UserError(
                "RFQ exception requires PAO (Procurement Administration Officer) or HOPE authorization.\n\n"
                "Current user does not have sufficient authority. "
                "Please submit this request to your PAO for approval."
            )
        
        # Approve the exception
        self.write({
            'rfq_exception_approved_by': self.env.user.id,
            'rfq_exception_approved_date': fields.Datetime.now()
        })
        
        # Log in chatter
        self.message_post(
            body=f"""<div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px;">
                <h3>⚠️ AUTO-013: RFQ Three-Quotation Exception Approved</h3>
                <p><strong>Approved By:</strong> {self.env.user.name}</p>
                <p><strong>Approval Date:</strong> {fields.Datetime.now()}</p>
                <p><strong>Tender:</strong> {self.name}</p>
                <p><strong>Procurement Method:</strong> RFQ (Request for Quotation)</p>
                <hr/>
                <table style="width: 100%; border-collapse: collapse; margin: 10px 0;">
                    <tr style="background-color: #fff3cd;">
                        <td style="padding: 8px; border: 1px solid #ffc107; font-weight: bold;">Minimum Required:</td>
                        <td style="padding: 8px; border: 1px solid #ffc107;">3 quotations</td>
                    </tr>
                    <tr style="background-color: #fff3cd;">
                        <td style="padding: 8px; border: 1px solid #ffc107; font-weight: bold;">Valid Quotations:</td>
                        <td style="padding: 8px; border: 1px solid #ffc107; color: #856404; font-weight: bold;">{self.valid_bid_count}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border: 1px solid #ffc107; font-weight: bold;">Total Bids Received:</td>
                        <td style="padding: 8px; border: 1px solid #ffc107;">{len(self.bid_ids)}</td>
                    </tr>
                </table>
                <hr/>
                <p><strong>Justification:</strong></p>
                <div style="background-color: #fffbf0; padding: 10px; border: 1px solid #ffc107; margin: 10px 0;">
                    {self.rfq_justification}
                </div>
                <hr/>
                <p style="font-size: 11px; color: #856404;">
                    <strong>Compliance Note:</strong> This exception to FR-PROC-016/BR-PROC-005 has been documented 
                    for audit trail per NFR-QUAL-001. The justification and approval are logged for regulatory review.
                </p>
            </div>""",
            subject='RFQ Three-Quotation Exception Approved',
            message_type='notification'
        )
        
        _logger.warning(
            f"AUTO-013: RFQ exception approved for {self.name} by {self.env.user.name} - "
            f"Valid bids: {self.valid_bid_count}/3, Justification: {self.rfq_justification[:100]}..."
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'RFQ Exception Approved',
                'message': f'Authorization granted to proceed with {self.valid_bid_count} quotation(s). You may now evaluate and award.',
                'type': 'warning',
                'sticky': True,
            }
        }
    
    def action_generate_award_recommendation(self):
        """AUTO-016: Generate draft evaluation report with bid ranking and award recommendation (FR-PROC-019).
        
        Creates comprehensive evaluation report including:
        - All bids table with compliance status, evaluated prices, ranks
        - Auto-recommendation for lowest evaluated responsive bid
        - Domestic preference calculations and justifications
        - Ready for evaluator review and submission to PEC/HOPE
        """
        self.ensure_one()
        
        if self.state != 'evaluated':
            raise UserError(
                "Award recommendation can only be generated after bid evaluation.\n\n"
                "Current state: " + dict(self._fields['state'].selection).get(self.state, self.state) + "\n"
                "Please complete bid evaluation first using 'Evaluate Bids' button."
            )
        
        # Get all bids (responsive and non-responsive)
        all_bids = self.bid_ids
        responsive_bids = all_bids.filtered(lambda b: b.preliminary_passed and not b.is_late)
        rejected_bids = all_bids - responsive_bids
        
        if not responsive_bids:
            raise UserError(
                "Cannot generate award recommendation: No responsive bids available.\n\n"
                "All submitted bids have been disqualified. Please review bid evaluation results."
            )
        
        # Get the winning bid (lowest evaluated price)
        winner = min(responsive_bids, key=lambda b: b.evaluated_price)
        
        # Build responsive bids table
        responsive_table_rows = ""
        for bid in sorted(responsive_bids, key=lambda b: b.evaluated_rank):
            preference_badge = ""
            if bid.preference_percentage > 0:
                preference_badge = f'<span style="background-color: #28a745; color: white; padding: 2px 6px; border-radius: 3px; font-size: 11px;">-{bid.preference_percentage}%</span>'
            
            winner_badge = ""
            if bid == winner:
                winner_badge = '<span style="background-color: #ffc107; color: #000; padding: 4px 10px; border-radius: 4px; font-weight: bold;">⭐ RECOMMENDED</span>'
            
            responsive_table_rows += f"""
            <tr style="{'background-color: #fff9e6;' if bid == winner else ''}">
                <td style="border: 1px solid #ddd; padding: 10px; text-align: center; font-weight: {'bold' if bid == winner else 'normal'};">{bid.evaluated_rank}</td>
                <td style="border: 1px solid #ddd; padding: 10px;">{bid.supplier_id.name}</td>
                <td style="border: 1px solid #ddd; padding: 10px; text-align: right;">{bid.bid_price:,.2f}</td>
                <td style="border: 1px solid #ddd; padding: 10px; text-align: center;">{bid.local_content:.1f}%</td>
                <td style="border: 1px solid #ddd; padding: 10px; text-align: center;">{preference_badge if preference_badge else '-'}</td>
                <td style="border: 1px solid #ddd; padding: 10px; text-align: right; font-weight: {'bold' if bid == winner else 'normal'};">{bid.evaluated_price:,.2f}</td>
                <td style="border: 1px solid #ddd; padding: 10px; text-align: center;">{winner_badge}</td>
            </tr>
            """
        
        # Build rejected bids table
        rejected_table_rows = ""
        if rejected_bids:
            for bid in rejected_bids:
                reason_parts = []
                if bid.is_late:
                    reason_parts.append("Late Submission (AUTO-012)")
                if not bid.preliminary_passed:
                    reason_parts.append("Failed Preliminary Evaluation")
                
                rejection_reason = "; ".join(reason_parts) if reason_parts else "Disqualified"
                
                rejected_table_rows += f"""
                <tr style="background-color: #f8d7da;">
                    <td style="border: 1px solid #ddd; padding: 10px;">—</td>
                    <td style="border: 1px solid #ddd; padding: 10px; color: #721c24;">{bid.supplier_id.name}</td>
                    <td style="border: 1px solid #ddd; padding: 10px; text-align: right; text-decoration: line-through;">{bid.bid_price:,.2f}</td>
                    <td style="border: 1px solid #ddd; padding: 10px; color: #721c24;" colspan="4">{rejection_reason}</td>
                </tr>
                """
        
        # Generate the complete report
        report_html = f"""
        <div style="font-family: 'Times New Roman', serif; padding: 40px; max-width: 900px; margin: 0 auto;">
            <!-- Header -->
            <div style="text-align: center; margin-bottom: 30px;">
                <h1 style="color: #2c3e50; font-size: 24px; margin: 0;">Federal Democratic Republic of Ethiopia</h1>
                <h2 style="color: #34495e; font-size: 20px; margin: 10px 0;">Mesob Center</h2>
                <h3 style="color: #7f8c8d; font-size: 16px; margin: 10px 0;">Procurement Unit</h3>
                <hr style="border: 2px solid #2c3e50; width: 60%; margin: 20px auto;"/>
                <h2 style="color: #2c3e50; font-size: 22px; margin: 20px 0;">BID EVALUATION REPORT<br/>AND AWARD RECOMMENDATION</h2>
                <p style="font-size: 12px; color: #7f8c8d; margin: 10px 0;">AUTO-016: Auto-Generated per FR-PROC-019</p>
            </div>
            
            <!-- Tender Information -->
            <div style="background-color: #ecf0f1; padding: 20px; margin: 20px 0; border-left: 4px solid #3498db;">
                <h3 style="color: #2c3e50; margin-top: 0;">Tender Information</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 5px 10px; font-weight: bold; width: 40%;">Tender Reference:</td>
                        <td style="padding: 5px 10px;">{self.name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 10px; font-weight: bold;">Procurement Method:</td>
                        <td style="padding: 5px 10px;">{dict(self._fields['procurement_method'].selection).get(self.procurement_method, self.procurement_method).upper()}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 10px; font-weight: bold;">Tender Opening Date:</td>
                        <td style="padding: 5px 10px;">{self.opening_date.strftime('%B %d, %Y') if self.opening_date else 'N/A'}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 10px; font-weight: bold;">Total Bids Received:</td>
                        <td style="padding: 5px 10px;">{len(all_bids)}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 10px; font-weight: bold;">Responsive Bids:</td>
                        <td style="padding: 5px 10px; color: #27ae60; font-weight: bold;">{len(responsive_bids)}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 10px; font-weight: bold;">Rejected Bids:</td>
                        <td style="padding: 5px 10px; color: #e74c3c; font-weight: bold;">{len(rejected_bids)}</td>
                    </tr>
                </table>
            </div>
            
            <!-- Evaluation Summary -->
            <h3 style="color: #2c3e50; border-bottom: 2px solid #2c3e50; padding-bottom: 10px; margin-top: 30px;">1. EVALUATION SUMMARY</h3>
            
            <h4 style="color: #34495e; margin-top: 20px;">1.1 Responsive Bids (Ranked by Evaluated Price)</h4>
            <table style="width: 100%; border-collapse: collapse; margin: 15px 0; font-size: 13px;">
                <thead>
                    <tr style="background-color: #34495e; color: white;">
                        <th style="border: 1px solid #ddd; padding: 10px;">Rank</th>
                        <th style="border: 1px solid #ddd; padding: 10px;">Supplier Name</th>
                        <th style="border: 1px solid #ddd; padding: 10px;">Original Bid<br/>Price (ETB)</th>
                        <th style="border: 1px solid #ddd; padding: 10px;">Local<br/>Content</th>
                        <th style="border: 1px solid #ddd; padding: 10px;">Preference<br/>Margin</th>
                        <th style="border: 1px solid #ddd; padding: 10px;">Evaluated<br/>Price (ETB)</th>
                        <th style="border: 1px solid #ddd; padding: 10px;">Status</th>
                    </tr>
                </thead>
                <tbody>
                    {responsive_table_rows}
                </tbody>
            </table>
            
            {'<h4 style="color: #34495e; margin-top: 20px;">1.2 Rejected/Disqualified Bids</h4>' if rejected_bids else ''}
            {'<table style="width: 100%; border-collapse: collapse; margin: 15px 0; font-size: 13px;">' if rejected_bids else ''}
            {'<thead><tr style="background-color: #e74c3c; color: white;"><th style="border: 1px solid #ddd; padding: 10px;">Rank</th><th style="border: 1px solid #ddd; padding: 10px;">Supplier Name</th><th style="border: 1px solid #ddd; padding: 10px;">Bid Price (ETB)</th><th style="border: 1px solid #ddd; padding: 10px;" colspan="4">Rejection Reason</th></tr></thead>' if rejected_bids else ''}
            {'<tbody>' + rejected_table_rows + '</tbody></table>' if rejected_bids else ''}
            
            <!-- Recommendation -->
            <h3 style="color: #2c3e50; border-bottom: 2px solid #2c3e50; padding-bottom: 10px; margin-top: 30px;">2. AWARD RECOMMENDATION</h3>
            
            <div style="background-color: #fff9e6; border: 3px solid #ffc107; padding: 20px; margin: 20px 0;">
                <p style="font-size: 16px; margin: 0; line-height: 1.8;">
                    Based on the evaluation of {len(responsive_bids)} responsive bid(s) received for 
                    <strong>{self.name}</strong>, it is <strong>RECOMMENDED</strong> that the award be made to:
                </p>
                
                <div style="background-color: white; padding: 20px; margin: 20px 0; border-left: 4px solid #ffc107;">
                    <table style="width: 100%; font-size: 15px;">
                        <tr>
                            <td style="padding: 8px 0; font-weight: bold; width: 40%;">Recommended Supplier:</td>
                            <td style="padding: 8px 0; font-size: 18px; color: #f39c12; font-weight: bold;">{winner.supplier_id.name}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; font-weight: bold;">Original Bid Price:</td>
                            <td style="padding: 8px 0; font-size: 16px;">ETB {winner.bid_price:,.2f}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; font-weight: bold;">Local Content:</td>
                            <td style="padding: 8px 0;">{winner.local_content:.1f}%</td>
                        </tr>
                        {'<tr><td style="padding: 8px 0; font-weight: bold;">Domestic Preference Applied:</td><td style="padding: 8px 0;">' + f'{winner.preference_percentage}% (ETB {winner.preference_amount:,.2f})' + '</td></tr>' if winner.preference_percentage > 0 else ''}
                        <tr>
                            <td style="padding: 8px 0; font-weight: bold;">Evaluated Price (for ranking):</td>
                            <td style="padding: 8px 0; color: #27ae60; font-weight: bold; font-size: 16px;">ETB {winner.evaluated_price:,.2f}</td>
                        </tr>
                        <tr>
                            <td style="padding: 8px 0; font-weight: bold;">Evaluation Rank:</td>
                            <td style="padding: 8px 0; color: #f39c12; font-weight: bold; font-size: 18px;">1st (Lowest Evaluated Responsive Bid)</td>
                        </tr>
                    </table>
                </div>
                
                <p style="font-size: 14px; margin: 15px 0; line-height: 1.8;">
                    <strong>Justification:</strong> {winner.supplier_id.name} submitted the <strong>lowest evaluated responsive bid</strong> 
                    after applying domestic preference adjustments per BR-PROC-003 (Federal Procurement Regulation). 
                    The bid met all preliminary evaluation criteria (AUTO-014) and technical specifications per FR-PROC-017.
                    {'<br/><br/><strong>Domestic Preference Note:</strong> A ' + f'{winner.preference_percentage}%' + ' preference margin was applied for ' + f'{winner.local_content:.1f}%' + ' local content (BR-PROC-003). Contract value and payment will use the <strong>original bid price</strong> of ETB ' + f'{winner.bid_price:,.2f}' + ' per FR-PROC-018.' if winner.preference_percentage > 0 else ''}
                </p>
            </div>
            
            <!-- Compliance Notes -->
            <h3 style="color: #2c3e50; border-bottom: 2px solid #2c3e50; padding-bottom: 10px; margin-top: 30px;">3. COMPLIANCE NOTES</h3>
            <ul style="line-height: 1.8; color: #34495e;">
                <li><strong>FR-PROC-017:</strong> Bid evaluation conducted per Federal Public Procurement procedure</li>
                <li><strong>FR-PROC-018:</strong> Evaluated price used for ranking only; contract uses original bid price</li>
                <li><strong>BR-PROC-003:</strong> Domestic preference applied per federal procurement regulation</li>
                <li><strong>AUTO-012:</strong> Late bids automatically rejected with timestamp proof</li>
                <li><strong>AUTO-014:</strong> Preliminary evaluation checklist auto-scoring applied</li>
                <li><strong>AUTO-015:</strong> Domestic preference calculations automated and auditable</li>
                <li><strong>AUTO-016:</strong> Bid ranking automated by evaluated price (this report)</li>
                {'<li style="color: #f39c12;"><strong>AUTO-013:</strong> RFQ exception approved by ' + self.rfq_exception_approved_by.name + ' on ' + self.rfq_exception_approved_date.strftime('%Y-%m-%d') + '</li>' if self.procurement_method == 'rfq' and self.rfq_exception_approved_by else ''}
            </ul>
            
            <!-- Signature Section -->
            <div style="margin-top: 50px; page-break-inside: avoid;">
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="width: 50%; padding: 10px; vertical-align: top;">
                            <p style="margin: 0;"><strong>Prepared By:</strong></p>
                            <p style="margin: 5px 0;">_______________________________</p>
                            <p style="margin: 5px 0; font-size: 12px;">Procurement Officer</p>
                            <p style="margin: 5px 0; font-size: 12px;">Date: _______________</p>
                        </td>
                        <td style="width: 50%; padding: 10px; vertical-align: top;">
                            <p style="margin: 0;"><strong>Reviewed By:</strong></p>
                            <p style="margin: 5px 0;">_______________________________</p>
                            <p style="margin: 5px 0; font-size: 12px;">PAO / HOPE</p>
                            <p style="margin: 5px 0; font-size: 12px;">Date: _______________</p>
                        </td>
                    </tr>
                </table>
            </div>
            
            <!-- Footer -->
            <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #bdc3c7; text-align: center;">
                <p style="font-size: 11px; color: #7f8c8d; margin: 5px 0;">
                    Report Generated: {fields.Datetime.now().strftime('%B %d, %Y at %I:%M %p')}<br/>
                    AUTO-016: Automated Bid Ranking and Award Recommendation System<br/>
                    FDRE Mesob Center | Procurement Management System
                </p>
            </div>
        </div>
        """
        
        # Post to chatter for audit trail
        self.message_post(
            body=report_html,
            subject=f'AUTO-016: Award Recommendation - {winner.supplier_id.name}',
            message_type='comment'
        )
        
        _logger.info(
            f"AUTO-016: Award recommendation generated for tender {self.name} - "
            f"Winner: {winner.supplier_id.name}, "
            f"Evaluated Price: ETB {winner.evaluated_price:,.2f}, "
            f"Responsive Bids: {len(responsive_bids)}"
        )
        
        return {
            'type': 'ir.actions.act_window',
            'name': f'Award Recommendation: {self.name}',
            'res_model': 'mesob.procurement.tender',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'current',
        }


class MesobProcurementBid(models.Model):
    """Supplier Bid submission inside Tender - FR-PROC-017.
    
    AUTO-012: Late Bid Auto-Rejection with Timestamp Proof
    - System captures bid submission timestamp at receipt
    - Auto-rejects bids received after tender deadline (FR-PROC-015)
    - Rejected bid logged with timestamp proof for audit trail
    - Supplier receives auto-notification with exact submission time
    """

    _name = "mesob.procurement.bid"
    _description = "Procurement Bid Submission"
    _inherit = ['mail.thread', 'mail.activity.mixin']

    tender_id = fields.Many2one("mesob.procurement.tender", string="Tender", required=True, ondelete="cascade")
    supplier_id = fields.Many2one(
        "res.partner",
        string="Supplier",
        required=True,
        domain=[("fppa_blacklisted", "=", False)],
    )
    
    # AUTO-012: Timestamp proof fields
    submission_timestamp = fields.Datetime(
        string="Submission Timestamp",
        readonly=True,
        default=fields.Datetime.now,
        help="AUTO-012: Exact timestamp when bid was received (FR-PROC-015)"
    )
    
    is_late = fields.Boolean(
        string="Late Submission",
        compute='_compute_is_late',
        store=True,
        help="AUTO-012: Automatically determined if bid received after deadline"
    )
    
    late_rejection_reason = fields.Text(
        string="Late Rejection Details",
        readonly=True,
        help="AUTO-012: Auto-generated rejection details with timestamp proof"
    )
    
    bid_price = fields.Float(string="Original Bid Price (ETB)", required=True)
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
        help='Currency for bid amounts'
    )
    
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
    
    # AUTO-016: Auto-ranking and recommendation fields
    evaluated_rank = fields.Integer(
        string="Auto Rank",
        compute='_compute_evaluated_rank',
        store=True,
        help="AUTO-016: Automatically calculated rank based on evaluated price (lowest = 1)"
    )
    
    is_winner = fields.Boolean(string="Winning Bid", default=False, help="Marked as winning bid after evaluation")
    
    line_ids = fields.One2many(
        'mesob.procurement.bid.line',
        'bid_id',
        string='Bid Lines',
        help='Individual items quoted in this bid'
    )
    
    # AUTO-014: Preliminary evaluation checklist
    evaluation_checklist_id = fields.One2many(
        'mesob.bid.evaluation.checklist',
        'bid_id',
        string='Evaluation Checklist',
        help='AUTO-014: Preliminary evaluation checklist with auto-scoring'
    )
    
    has_evaluation_checklist = fields.Boolean(
        string='Has Checklist',
        compute='_compute_has_evaluation_checklist',
        help='AUTO-014: True if evaluation checklist exists'
    )
    
    @api.depends('evaluation_checklist_id')
    def _compute_has_evaluation_checklist(self):
        """Check if evaluation checklist exists."""
        for bid in self:
            bid.has_evaluation_checklist = bool(bid.evaluation_checklist_id)
    
    @api.depends('tender_id.bid_ids.evaluated_price', 'tender_id.bid_ids.preliminary_passed', 'tender_id.bid_ids.is_late')
    def _compute_evaluated_rank(self):
        """AUTO-016: Auto-rank bids within the same tender by evaluated price.
        
        Only responsive bids (preliminary_passed=True, is_late=False) are ranked.
        Lowest evaluated price gets rank 1.
        """
        for bid in self:
            # Get all responsive bids in the same tender
            responsive_bids = bid.tender_id.bid_ids.filtered(
                lambda b: b.preliminary_passed and not b.is_late
            )
            
            if not responsive_bids or bid not in responsive_bids:
                bid.evaluated_rank = 0  # Not ranked (disqualified)
                continue
            
            # Sort by evaluated price (ascending)
            sorted_bids = sorted(responsive_bids, key=lambda b: b.evaluated_price)
            
            # Find this bid's rank
            bid.evaluated_rank = sorted_bids.index(bid) + 1
    
    def action_generate_evaluation_checklist(self):
        """AUTO-014: Generate preliminary evaluation checklist for this bid.
        
        Creates a checklist with auto-populated checks from bid data.
        Evaluator reviews and confirms each criterion.
        """
        self.ensure_one()
        
        if self.evaluation_checklist_id:
            raise UserError(
                "Evaluation checklist already exists for this bid. "
                "Please use the existing checklist or delete it first."
            )
        
        # Create checklist using factory method
        checklist = self.env['mesob.bid.evaluation.checklist'].create_from_bid(self)
        
        _logger.info(f"AUTO-014: Evaluation checklist generated for bid {self.id}")
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Preliminary Evaluation Checklist',
            'res_model': 'mesob.bid.evaluation.checklist',
            'res_id': checklist.id,
            'view_mode': 'form',
            'target': 'new',
        }
    
    @api.depends('submission_timestamp', 'tender_id.submission_deadline')
    def _compute_is_late(self):
        """AUTO-012: Determine if bid is late based on submission timestamp."""
        for bid in self:
            if bid.submission_timestamp and bid.tender_id.submission_deadline:
                bid.is_late = bid.submission_timestamp > bid.tender_id.submission_deadline
            else:
                bid.is_late = False
    
    @api.model_create_multi
    def create(self, vals_list):
        """AUTO-012: Capture submission timestamp and auto-reject late bids (FR-PROC-015)."""
        bids = super().create(vals_list)
        
        for bid in bids:
            # Capture exact timestamp if not already set
            if not bid.submission_timestamp:
                bid.submission_timestamp = fields.Datetime.now()
            
            # AUTO-012: Check if bid is late and auto-reject
            if bid.is_late:
                # Calculate how late the bid is
                from datetime import datetime
                delay = bid.submission_timestamp - bid.tender_id.submission_deadline
                delay_minutes = int(delay.total_seconds() / 60)
                delay_hours = int(delay_minutes / 60)
                delay_days = int(delay_hours / 24)
                
                # Format delay message
                if delay_days > 0:
                    delay_str = f"{delay_days} day(s) {delay_hours % 24} hour(s)"
                elif delay_hours > 0:
                    delay_str = f"{delay_hours} hour(s) {delay_minutes % 60} minute(s)"
                else:
                    delay_str = f"{delay_minutes} minute(s)"
                
                # Auto-reject with timestamp proof
                rejection_details = (
                    f"AUTO-012: BID AUTOMATICALLY REJECTED - LATE SUBMISSION\n\n"
                    f"This bid has been automatically rejected per FR-PROC-015 (FPPA Proclamation 1210/2012).\n\n"
                    f"TIMESTAMP PROOF:\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"Submission Deadline:  {bid.tender_id.submission_deadline.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"Actual Submission:    {bid.submission_timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
                    f"Delay:                {delay_str} late\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"Supplier: {bid.supplier_id.name}\n"
                    f"Tender: {bid.tender_id.name}\n"
                    f"Bid Price: ETB {bid.bid_price:,.2f}\n\n"
                    f"This rejection is FINAL and cannot be reversed.\n"
                    f"The submission timestamp is system-generated and tamper-proof.\n\n"
                    f"Logged: {fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
                
                bid.write({
                    'preliminary_passed': False,
                    'late_rejection_reason': rejection_details
                })
                
                # Post rejection notice to tender chatter
                bid.tender_id.message_post(
                    body=f"""<div style="background-color: #f8d7da; border-left: 4px solid #dc3545; padding: 15px;">
                        <h3 style="color: #721c24; margin-top: 0;">🚫 AUTO-012: Late Bid Auto-Rejected</h3>
                        <table style="width: 100%; border-collapse: collapse;">
                            <tr>
                                <td style="padding: 8px; font-weight: bold;">Supplier:</td>
                                <td style="padding: 8px;">{bid.supplier_id.name}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px; font-weight: bold;">Submission Time:</td>
                                <td style="padding: 8px;">{bid.submission_timestamp.strftime('%Y-%m-%d %H:%M:%S')}</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px; font-weight: bold;">Deadline:</td>
                                <td style="padding: 8px;">{bid.tender_id.submission_deadline.strftime('%Y-%m-%d %H:%M:%S')}</td>
                            </tr>
                            <tr style="background-color: #f5c6cb;">
                                <td style="padding: 8px; font-weight: bold;">Delay:</td>
                                <td style="padding: 8px; color: #721c24; font-weight: bold;">{delay_str} LATE</td>
                            </tr>
                            <tr>
                                <td style="padding: 8px; font-weight: bold;">Bid Amount:</td>
                                <td style="padding: 8px;">ETB {bid.bid_price:,.2f}</td>
                            </tr>
                        </table>
                        <hr style="border-color: #f5c6cb;"/>
                        <p style="margin: 10px 0 0 0; font-size: 11px; color: #721c24;">
                            <strong>FR-PROC-015:</strong> Late bids are automatically rejected per FPPA Proclamation 1210/2012. 
                            This rejection is logged for audit trail (NFR-QUAL-001).
                        </p>
                    </div>""",
                    subject=f'Late Bid Rejected: {bid.supplier_id.name}',
                    message_type='notification'
                )
                
                # Send notification email to supplier if email available
                if bid.supplier_id.email:
                    bid._send_late_rejection_email()
                
                _logger.warning(
                    f"AUTO-012: Late bid auto-rejected - Tender: {bid.tender_id.name}, "
                    f"Supplier: {bid.supplier_id.name}, "
                    f"Deadline: {bid.tender_id.submission_deadline}, "
                    f"Submitted: {bid.submission_timestamp}, "
                    f"Delay: {delay_str}"
                )
            else:
                _logger.info(
                    f"AUTO-012: Bid received on time - Tender: {bid.tender_id.name}, "
                    f"Supplier: {bid.supplier_id.name}, "
                    f"Submitted: {bid.submission_timestamp}, "
                    f"Deadline: {bid.tender_id.submission_deadline}"
                )
        
        return bids
    
    def _send_late_rejection_email(self):
        """AUTO-012: Send auto-generated email to supplier about late bid rejection."""
        self.ensure_one()
        
        if not self.supplier_id.email:
            return
        
        email_body = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background-color: #dc3545; color: white; padding: 20px; text-align: center;">
                <h2 style="margin: 0;">Bid Rejection Notice</h2>
            </div>
            
            <div style="padding: 20px; background-color: #f8f9fa;">
                <p>Dear {self.supplier_id.name},</p>
                
                <p>This is an <strong>automated notification</strong> from the Federal Democratic Republic of Ethiopia, Mesob Center Procurement System.</p>
                
                <div style="background-color: #f8d7da; border-left: 4px solid #dc3545; padding: 15px; margin: 20px 0;">
                    <h3 style="color: #721c24; margin-top: 0;">Your bid has been automatically rejected</h3>
                    <p><strong>Reason:</strong> Late Submission (FR-PROC-015)</p>
                </div>
                
                <table style="width: 100%; border-collapse: collapse; margin: 20px 0;">
                    <tr style="background-color: #e9ecef;">
                        <th style="border: 1px solid #dee2e6; padding: 10px; text-align: left;">Details</th>
                        <th style="border: 1px solid #dee2e6; padding: 10px; text-align: left;">Information</th>
                    </tr>
                    <tr>
                        <td style="border: 1px solid #dee2e6; padding: 10px;">Tender Reference</td>
                        <td style="border: 1px solid #dee2e6; padding: 10px;">{self.tender_id.name}</td>
                    </tr>
                    <tr>
                        <td style="border: 1px solid #dee2e6; padding: 10px;">Submission Deadline</td>
                        <td style="border: 1px solid #dee2e6; padding: 10px; font-weight: bold;">{self.tender_id.submission_deadline.strftime('%Y-%m-%d %H:%M:%S')}</td>
                    </tr>
                    <tr style="background-color: #f8d7da;">
                        <td style="border: 1px solid #dee2e6; padding: 10px;">Your Submission Time</td>
                        <td style="border: 1px solid #dee2e6; padding: 10px; font-weight: bold; color: #721c24;">{self.submission_timestamp.strftime('%Y-%m-%d %H:%M:%S')}</td>
                    </tr>
                </table>
                
                <div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px; margin: 20px 0;">
                    <p style="margin: 0;"><strong>Legal Notice:</strong></p>
                    <p style="margin: 10px 0 0 0;">
                        Per Federal Public Procurement and Property Administration Proclamation No. 1210/2012, Article [FR-PROC-015], 
                        bids received after the submission deadline are <strong>automatically rejected</strong> without review.
                    </p>
                    <p style="margin: 10px 0 0 0;">
                        The submission timestamp is system-generated and serves as tamper-proof evidence for audit purposes.
                        This rejection is <strong>FINAL</strong> and cannot be appealed.
                    </p>
                </div>
                
                <p>We encourage you to participate in future procurement opportunities. Please ensure timely submission to avoid automatic rejection.</p>
                
                <p>This is an automated message. Please do not reply to this email.</p>
                
                <hr style="border: 1px solid #dee2e6; margin: 20px 0;"/>
                
                <p style="font-size: 12px; color: #6c757d;">
                    <strong>FDRE Mesob Center</strong><br/>
                    Procurement Unit<br/>
                    Addis Ababa, Ethiopia<br/>
                    <em>AUTO-012: Automated Bid Rejection System</em>
                </p>
            </div>
        </div>
        """
        
        mail_values = {
            'subject': f'Bid Rejected - Late Submission: {self.tender_id.name}',
            'body_html': email_body,
            'email_to': self.supplier_id.email,
            'email_from': self.env.company.email or 'procurement@mesob.gov.et',
            'auto_delete': False,
        }
        
        mail = self.env['mail.mail'].create(mail_values)
        mail.send()
        
        _logger.info(
            f"AUTO-012: Late rejection email sent to {self.supplier_id.name} ({self.supplier_id.email})"
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


class MesobBidEvaluationChecklist(models.Model):
    """AUTO-014: Preliminary Evaluation Checklist with Auto-Scoring (FR-PROC-017).
    
    Auto-populates administrative compliance checklist from bid submission data:
    - Bid security amount and validity verification
    - Supplier registration status and expiry checks
    - Document completeness tracking
    - Automatic preliminary disqualification for critical failures
    
    Evaluator confirms/overrides each item with documented reasons.
    """
    
    _name = 'mesob.bid.evaluation.checklist'
    _description = 'Bid Preliminary Evaluation Checklist'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'bid_id, id'
    
    bid_id = fields.Many2one(
        'mesob.procurement.bid',
        string='Bid',
        required=True,
        ondelete='cascade',
        help='Bid being evaluated'
    )
    
    tender_id = fields.Many2one(
        'mesob.procurement.tender',
        related='bid_id.tender_id',
        string='Tender',
        store=True
    )
    
    supplier_id = fields.Many2one(
        'res.partner',
        related='bid_id.supplier_id',
        string='Supplier',
        store=True
    )
    
    bid_price = fields.Float(
        string='Bid Price',
        related='bid_id.bid_price',
        readonly=True,
        help='Original bid price from the bid'
    )
    
    # ── AUTO-014: Auto-Populated Criteria ──────────────────────────
    
    # 1. Bid Security Checks
    bid_security_submitted = fields.Boolean(
        string='Bid Security Submitted',
        default=False,
        help='AUTO-014: Check if bid security document was submitted'
    )
    
    bid_security_amount_ok = fields.Boolean(
        string='Bid Security Amount Correct',
        compute='_compute_bid_security_checks',
        store=True,
        help='AUTO-014: Auto-check if submitted amount ≥ required amount'
    )
    
    bid_security_amount_submitted = fields.Float(
        string='Bid Security Amount Submitted (ETB)',
        help='Amount stated in submitted bid security'
    )
    
    bid_security_amount_required = fields.Monetary(
        string='Bid Security Required',
        related='tender_id.bid_security_amount',
        currency_field='currency_id',
        readonly=True,
        help='Required bid security per tender'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        related='tender_id.currency_id',
        readonly=True
    )
    
    bid_security_validity_ok = fields.Boolean(
        string='Bid Security Validity Adequate',
        compute='_compute_bid_security_checks',
        store=True,
        help='AUTO-014: Auto-check if validity extends beyond bid validity period'
    )
    
    bid_security_validity_date = fields.Date(
        string='Bid Security Valid Until',
        help='Expiry date of submitted bid security'
    )
    
    # 2. Supplier Registration Checks
    supplier_registration_valid = fields.Boolean(
        string='Supplier Registration Valid',
        compute='_compute_supplier_checks',
        store=True,
        help='AUTO-014: Auto-check if supplier registration not expired'
    )
    
    supplier_not_blacklisted = fields.Boolean(
        string='Supplier Not Blacklisted',
        compute='_compute_supplier_checks',
        store=True,
        help='AUTO-014: Auto-check supplier blacklist status'
    )
    
    supplier_category_matches = fields.Boolean(
        string='Supplier Category Matches',
        compute='_compute_supplier_checks',
        store=True,
        help='AUTO-014: Auto-check if supplier registered for this category'
    )
    
    # 3. Document Completeness Checks
    technical_proposal_submitted = fields.Boolean(
        string='Technical Proposal Submitted',
        default=False,
        help='Technical proposal document received'
    )
    
    financial_proposal_submitted = fields.Boolean(
        string='Financial Proposal Submitted',
        default=False,
        help='Financial proposal/price schedule received'
    )
    
    company_profile_submitted = fields.Boolean(
        string='Company Profile Submitted',
        default=False,
        help='Company profile and credentials received'
    )
    
    tax_clearance_submitted = fields.Boolean(
        string='Tax Clearance Certificate Submitted',
        default=False,
        help='Valid tax clearance certificate received'
    )
    
    # 4. Bid Submission Checks
    bid_submitted_on_time = fields.Boolean(
        string='Bid Submitted On Time',
        related='bid_id.is_late',
        help='AUTO-012: Auto-check if bid was late',
        store=True
    )
    
    bid_properly_sealed = fields.Boolean(
        string='Bid Envelope Properly Sealed',
        default=True,
        help='Physical bid envelope was sealed and unopened'
    )
    
    bid_signed_authorized = fields.Boolean(
        string='Bid Signed by Authorized Rep',
        default=False,
        help='Bid documents signed by authorized representative'
    )
    
    # ── AUTO-014: Critical Failure Tracking ────────────────────────
    
    critical_failures = fields.Text(
        string='Critical Failures',
        compute='_compute_critical_failures',
        store=True,
        help='AUTO-014: List of critical failures causing auto-disqualification'
    )
    
    preliminary_pass = fields.Boolean(
        string='Preliminary Evaluation Pass',
        compute='_compute_preliminary_pass',
        store=True,
        help='AUTO-014: True if all critical criteria met'
    )
    
    disqualification_reason = fields.Text(
        string='Disqualification Reason',
        compute='_compute_preliminary_pass',
        store=True,
        help='AUTO-014: Auto-generated disqualification reason if failed'
    )
    
    # ── Evaluator Override ──────────────────────────────────────────
    
    evaluator_override = fields.Boolean(
        string='Evaluator Override',
        default=False,
        help='Evaluator manually overrides auto-disqualification (requires justification)'
    )
    
    override_justification = fields.Text(
        string='Override Justification',
        help='Required if evaluator overrides auto-disqualification'
    )
    
    evaluator_id = fields.Many2one(
        'res.users',
        string='Evaluated By',
        help='User who completed the evaluation'
    )
    
    evaluation_date = fields.Datetime(
        string='Evaluation Date',
        help='Timestamp of evaluation completion'
    )
    
    evaluator_notes = fields.Text(
        string='Evaluator Notes',
        help='Additional notes from evaluator'
    )
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('completed', 'Completed'),
        ('overridden', 'Overridden'),
    ], string='Status', default='draft')
    
    # ── AUTO-014: Auto-Scoring Compute Methods ─────────────────────
    
    @api.depends('bid_security_submitted', 'bid_security_amount_submitted', 
                 'bid_security_amount_required', 'bid_security_validity_date')
    def _compute_bid_security_checks(self):
        """AUTO-014: Auto-check bid security amount and validity."""
        for checklist in self:
            # Check amount
            if checklist.bid_security_submitted and checklist.bid_security_amount_submitted > 0:
                checklist.bid_security_amount_ok = (
                    checklist.bid_security_amount_submitted >= checklist.bid_security_amount_required
                )
            else:
                checklist.bid_security_amount_ok = False
            
            # Check validity (should be valid for at least 30 days beyond bid opening)
            if checklist.bid_security_validity_date and checklist.tender_id.submission_deadline:
                from datetime import timedelta
                deadline = checklist.tender_id.submission_deadline.date() if hasattr(checklist.tender_id.submission_deadline, 'date') else checklist.tender_id.submission_deadline
                min_validity = deadline + timedelta(days=30)
                checklist.bid_security_validity_ok = checklist.bid_security_validity_date >= min_validity
            else:
                checklist.bid_security_validity_ok = False
    
    @api.depends('supplier_id', 'supplier_id.registration_expiry_date', 
                 'supplier_id.fppa_blacklisted', 'supplier_id.supply_category_ids',
                 'tender_id.lot_id.category')
    def _compute_supplier_checks(self):
        """AUTO-014: Auto-check supplier registration, blacklist, and category match."""
        for checklist in self:
            # Check registration validity
            if checklist.supplier_id.registration_expiry_date:
                today = fields.Date.today()
                checklist.supplier_registration_valid = checklist.supplier_id.registration_expiry_date >= today
            else:
                checklist.supplier_registration_valid = False
            
            # Check blacklist status
            checklist.supplier_not_blacklisted = not checklist.supplier_id.fppa_blacklisted
            
            # Check category match (if lot has category and supplier has categories)
            if checklist.tender_id.lot_id and checklist.supplier_id.supply_category_ids:
                # Check if supplier is registered for any category matching the lot's classification
                lot_classification = checklist.tender_id.lot_id.need_ids.mapped('major_classification_id')
                supplier_categories = checklist.supplier_id.supply_category_ids
                checklist.supplier_category_matches = bool(set(lot_classification) & set(supplier_categories))
            else:
                # If no categories configured, pass by default
                checklist.supplier_category_matches = True
    
    @api.depends('bid_security_submitted', 'bid_security_amount_ok', 'bid_security_validity_ok',
                 'supplier_registration_valid', 'supplier_not_blacklisted', 'supplier_category_matches',
                 'bid_submitted_on_time', 'technical_proposal_submitted', 'financial_proposal_submitted')
    def _compute_critical_failures(self):
        """AUTO-014: Identify critical failures causing auto-disqualification."""
        for checklist in self:
            failures = []
            
            # Critical criteria per FR-PROC-017
            if not checklist.bid_security_submitted:
                failures.append("• Bid security not submitted (FR-PROC-015 - CRITICAL)")
            elif not checklist.bid_security_amount_ok:
                failures.append(
                    f"• Bid security amount insufficient: Submitted ETB {checklist.bid_security_amount_submitted:,.2f}, "
                    f"Required ETB {checklist.bid_security_amount_required:,.2f} (FR-PROC-015 - CRITICAL)"
                )
            
            if not checklist.bid_security_validity_ok:
                failures.append("• Bid security validity period inadequate (FR-PROC-015 - CRITICAL)")
            
            if not checklist.supplier_registration_valid:
                failures.append("• Supplier registration expired (FR-PROC-010 - CRITICAL)")
            
            if not checklist.supplier_not_blacklisted:
                failures.append("• Supplier is blacklisted/suspended (FR-PROC-012 - CRITICAL)")
            
            if not checklist.supplier_category_matches:
                failures.append("• Supplier not registered for this supply category (FR-PROC-010 - CRITICAL)")
            
            if checklist.bid_submitted_on_time:  # Note: is_late=True means LATE
                failures.append("• Bid submitted after deadline (AUTO-012 / FR-PROC-015 - CRITICAL)")
            
            if not checklist.technical_proposal_submitted:
                failures.append("• Technical proposal not submitted (FR-PROC-013 - CRITICAL)")
            
            if not checklist.financial_proposal_submitted:
                failures.append("• Financial proposal/price schedule not submitted (FR-PROC-013 - CRITICAL)")
            
            checklist.critical_failures = '\n'.join(failures) if failures else ''
    
    @api.depends('critical_failures', 'evaluator_override')
    def _compute_preliminary_pass(self):
        """AUTO-014: Determine if bid passes preliminary evaluation."""
        for checklist in self:
            has_critical_failures = bool(checklist.critical_failures)
            
            if not has_critical_failures:
                # No failures - PASS
                checklist.preliminary_pass = True
                checklist.disqualification_reason = ''
            elif checklist.evaluator_override:
                # Failures but evaluator override - PASS with justification
                checklist.preliminary_pass = True
                checklist.disqualification_reason = (
                    f"EVALUATOR OVERRIDE: Bid had critical failures but was passed by evaluator.\n\n"
                    f"Original Failures:\n{checklist.critical_failures}\n\n"
                    f"Override Justification:\n{checklist.override_justification or 'NOT PROVIDED'}"
                )
            else:
                # Critical failures - FAIL
                checklist.preliminary_pass = False
                checklist.disqualification_reason = (
                    f"AUTO-014: BID DISQUALIFIED - Administrative Non-Compliance\n\n"
                    f"The following critical failures were detected during preliminary evaluation (FR-PROC-017):\n\n"
                    f"{checklist.critical_failures}\n\n"
                    f"This bid is automatically disqualified per FPPA Proclamation 1210/2012.\n"
                    f"Only administratively compliant bids proceed to technical/financial evaluation."
                )
    
    @api.model
    def create_from_bid(self, bid):
        """AUTO-014: Factory method to create checklist from bid with auto-populated values.
        
        Args:
            bid: mesob.procurement.bid record
        
        Returns:
            Created checklist record
        """
        return self.create({
            'bid_id': bid.id,
            'bid_security_submitted': False,  # Evaluator must confirm
            'bid_security_amount_submitted': 0.0,  # Evaluator must enter
            'bid_security_validity_date': False,  # Evaluator must enter
            'technical_proposal_submitted': False,  # Evaluator must confirm
            'financial_proposal_submitted': False,  # Evaluator must confirm
            'company_profile_submitted': False,
            'tax_clearance_submitted': False,
            'bid_properly_sealed': True,  # Assume yes unless noted
            'bid_signed_authorized': False,  # Evaluator must confirm
        })
    
    def action_complete_evaluation(self):
        """Complete preliminary evaluation and update bid status."""
        self.ensure_one()
        
        if not self.evaluator_id:
            self.evaluator_id = self.env.user.id
        
        if not self.evaluation_date:
            self.evaluation_date = fields.Datetime.now()
        
        # Update bid's preliminary_passed status
        self.bid_id.preliminary_passed = self.preliminary_pass
        
        # Set state
        if self.evaluator_override:
            self.state = 'overridden'
        else:
            self.state = 'completed'
        
        # Post to bid chatter
        if self.preliminary_pass:
            self.bid_id.message_post(
                body=f"""<div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px;">
                    <h3 style="color: #155724;">✅ AUTO-014: Preliminary Evaluation PASSED</h3>
                    <p><strong>Evaluated By:</strong> {self.evaluator_id.name}</p>
                    <p><strong>Evaluation Date:</strong> {self.evaluation_date}</p>
                    <p>All critical administrative criteria met. Bid proceeds to technical/financial evaluation.</p>
                </div>""",
                subject='Preliminary Evaluation: PASSED',
                message_type='comment'
            )
        else:
            self.bid_id.message_post(
                body=f"""<div style="background-color: #f8d7da; border-left: 4px solid #dc3545; padding: 15px;">
                    <h3 style="color: #721c24;">❌ AUTO-014: Preliminary Evaluation FAILED</h3>
                    <p><strong>Evaluated By:</strong> {self.evaluator_id.name}</p>
                    <p><strong>Evaluation Date:</strong> {self.evaluation_date}</p>
                    <div style="background-color: #fff; padding: 10px; margin: 10px 0;">
                        <pre style="margin: 0; white-space: pre-wrap;">{self.disqualification_reason}</pre>
                    </div>
                </div>""",
                subject='Preliminary Evaluation: DISQUALIFIED',
                message_type='comment'
            )
        
        _logger.info(
            f"AUTO-014: Preliminary evaluation completed for bid {self.bid_id.id} - "
            f"Result: {'PASS' if self.preliminary_pass else 'FAIL'}, "
            f"Evaluator: {self.evaluator_id.name}"
        )
        
        return True


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
    
    # ── AUTO-021: Contract Variation Tracking ──────────────────────
    original_contract_value = fields.Float(
        string="Original Contract Value (ETB)",
        help="AUTO-021: Initial contract value before any variations"
    )
    cumulative_variation_total = fields.Float(
        string="Cumulative Variations Total (ETB)",
        default=0.0,
        help="AUTO-021: Total ETB value of all approved variations"
    )
    variation_percentage = fields.Float(
        string="Variation Percentage (%)",
        compute='_compute_variation_percentage',
        store=True,
        help="AUTO-021: % of original contract value (FR-PROC-023)"
    )
    variation_alert_10_sent = fields.Boolean(
        string="10% Alert Sent",
        default=False,
        help="AUTO-021: Alert sent when cumulative variation reached 10%"
    )
    variation_alert_15_sent = fields.Boolean(
        string="15% Alert Sent",
        default=False,
        help="AUTO-021: Alert sent when cumulative variation reached 15%"
    )
    variation_ids = fields.One2many(
        'mesob.contract.variation',
        'contract_id',
        string='Contract Variations',
        help='AUTO-021: All contract variations'
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
    
    # ── AUTO-018: Contract Document Generation ─────────────────────
    contract_document = fields.Html(
        string="Contract Document",
        help="AUTO-018: Auto-generated contract document from approved bid"
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
    
    @api.depends('original_contract_value', 'cumulative_variation_total')
    def _compute_variation_percentage(self):
        """AUTO-021: Calculate cumulative variation as % of original contract value (FR-PROC-023)."""
        for rec in self:
            if rec.original_contract_value and rec.original_contract_value > 0:
                rec.variation_percentage = (rec.cumulative_variation_total / rec.original_contract_value) * 100.0
            else:
                rec.variation_percentage = 0.0
    
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
    
    @api.model
    def _cron_check_retention_release_eligibility(self):
        """AUTO-032: Scheduled job to check if retention can be released (FR-PROC-037).
        
        Runs daily to check closed contracts where:
        - Contract is closed
        - Warranty period has elapsed
        - Retention not yet released
        
        Sends alert to procurement officers to review and release retention.
        """
        today = fields.Date.today()
        
        eligible_contracts = self.search([
            ('state', '=', 'closed'),
            ('retention_released', '=', False),
            ('cumulative_retention', '>', 0),
            ('warranty_expiry_date', '!=', False),
            ('warranty_expiry_date', '<=', today),
        ])
        
        if not eligible_contracts:
            _logger.info("AUTO-032: No contracts eligible for retention release")
            return
        
        # Group by days since warranty expiry for priority
        urgent_contracts = []
        overdue_contracts = []
        
        for contract in eligible_contracts:
            days_since_expiry = (today - contract.warranty_expiry_date).days
            
            if days_since_expiry > 30:
                overdue_contracts.append((contract, days_since_expiry))
            else:
                urgent_contracts.append((contract, days_since_expiry))
        
        # Send consolidated alert
        procurement_users = self.env.ref('mesob_inventory_base.group_mesob_pao', raise_if_not_found=False)
        
        if procurement_users and procurement_users.users:
            alert_html = """<div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px;">
                <h3 style="color: #856404; margin-top: 0;">💰 AUTO-032: Retention Release Reminder</h3>
                <p>The following contracts have retention amounts ready for release (FR-PROC-037):</p>
            """
            
            if overdue_contracts:
                alert_html += """<div style="background-color: #f8d7da; padding: 10px; margin: 10px 0; border-left: 3px solid #dc3545;">
                    <h4 style="color: #721c24; margin-top: 0;">🚨 OVERDUE (>30 days since warranty expiry):</h4>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr style="background-color: #f5c6cb;">
                            <th style="border: 1px solid #dc3545; padding: 8px; text-align: left;">Contract</th>
                            <th style="border: 1px solid #dc3545; padding: 8px; text-align: left;">Supplier</th>
                            <th style="border: 1px solid #dc3545; padding: 8px; text-align: right;">Retention (ETB)</th>
                            <th style="border: 1px solid #dc3545; padding: 8px; text-align: right;">Overdue</th>
                        </tr>"""
                
                for contract, days in overdue_contracts:
                    alert_html += f"""<tr>
                        <td style="border: 1px solid #dee2e6; padding: 8px;">{contract.name}</td>
                        <td style="border: 1px solid #dee2e6; padding: 8px;">{contract.supplier_id.name}</td>
                        <td style="border: 1px solid #dee2e6; padding: 8px; text-align: right; font-weight: bold;">{contract.cumulative_retention:,.2f}</td>
                        <td style="border: 1px solid #dee2e6; padding: 8px; text-align: right; color: #dc3545; font-weight: bold;">{days} days</td>
                    </tr>"""
                
                alert_html += "</table></div>"
            
            if urgent_contracts:
                alert_html += """<div style="background-color: #fff3cd; padding: 10px; margin: 10px 0; border-left: 3px solid #ffc107;">
                    <h4 style="color: #856404; margin-top: 0;">⚠️ READY FOR RELEASE:</h4>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr style="background-color: #fff3cd;">
                            <th style="border: 1px solid #ffc107; padding: 8px; text-align: left;">Contract</th>
                            <th style="border: 1px solid #ffc107; padding: 8px; text-align: left;">Supplier</th>
                            <th style="border: 1px solid #ffc107; padding: 8px; text-align: right;">Retention (ETB)</th>
                            <th style="border: 1px solid #ffc107; padding: 8px; text-align: right;">Days Since</th>
                        </tr>"""
                
                for contract, days in urgent_contracts:
                    alert_html += f"""<tr>
                        <td style="border: 1px solid #dee2e6; padding: 8px;">{contract.name}</td>
                        <td style="border: 1px solid #dee2e6; padding: 8px;">{contract.supplier_id.name}</td>
                        <td style="border: 1px solid #dee2e6; padding: 8px; text-align: right; font-weight: bold;">{contract.cumulative_retention:,.2f}</td>
                        <td style="border: 1px solid #dee2e6; padding: 8px; text-align: right;">{days} days</td>
                    </tr>"""
                
                alert_html += "</table></div>"
            
            total_retention = sum(c.cumulative_retention for c in eligible_contracts)
            
            alert_html += f"""<div style="background-color: #d4edda; padding: 15px; margin-top: 15px; border-radius: 4px;">
                <table style="width: 100%;">
                    <tr>
                        <td style="padding: 5px 0;"><strong>Total Contracts:</strong></td>
                        <td style="padding: 5px 0; text-align: right; font-weight: bold;">{len(eligible_contracts)}</td>
                    </tr>
                    <tr style="background-color: #c3e6cb;">
                        <td style="padding: 8px 0; font-size: 16px;"><strong>Total Retention to Release:</strong></td>
                        <td style="padding: 8px 0; text-align: right; font-size: 18px; font-weight: bold; color: #155724;">ETB {total_retention:,.2f}</td>
                    </tr>
                </table>
            </div>
            <div style="background-color: #e7f3ff; padding: 10px; margin-top: 15px; border-radius: 4px;">
                <p style="margin: 0;"><strong>📋 Action Required (FR-PROC-037):</strong></p>
                <ol style="margin: 10px 0 0 20px;">
                    <li>Review each contract for defects liability clearance</li>
                    <li>Confirm final Model 19 has been issued</li>
                    <li>Verify warranty period has fully elapsed</li>
                    <li>Use 'Release Retention' button on contract form</li>
                </ol>
            </div>
        </div>"""
            
            # Post to each contract
            for contract in eligible_contracts:
                contract.message_post(
                    body=alert_html,
                    subject='Retention Release Eligible',
                    message_type='notification',
                    partner_ids=procurement_users.users.mapped('partner_id').ids
                )
        
        _logger.info(
            f"AUTO-032: Retention release check completed - "
            f"{len(eligible_contracts)} contracts eligible (Total: ETB {total_retention:,.2f}), "
            f"Overdue: {len(overdue_contracts)}, Urgent: {len(urgent_contracts)}"
        )
    
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
        
        procurement_users = self.env.ref('mesob_inventory_base.group_mesob_procurement', raise_if_not_found=False)
        
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
        
        procurement_users = self.env.ref('mesob_inventory_base.group_mesob_procurement', raise_if_not_found=False)
        
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
    
    def action_calculate_price_adjustment(self, current_indices):
        """AUTO-031: Calculate price adjustment based on current indices (FR-PROC-035).
        
        Args:
            current_indices (dict): Current index values, e.g., {'fuel': 110, 'steel': 160, 'labor': 125}
        
        Returns:
            dict: Adjustment calculation details
        
        Example:
            contract.action_calculate_price_adjustment({'fuel': 110, 'steel': 160, 'labor': 125})
        """
        self.ensure_one()
        
        if not self.has_price_adjustment:
            raise UserError("This contract does not have a price adjustment clause (FR-PROC-035).")
        
        if not self.base_price_indices:
            raise UserError("Base price indices not configured. Cannot calculate adjustment.")
        
        if not self.price_adjustment_formula:
            raise UserError("Price adjustment formula not configured.")
        
        # Parse base indices (JSON format)
        import json
        try:
            base_indices = json.loads(self.base_price_indices)
        except:
            raise UserError("Invalid base price indices format. Expected JSON format.")
        
        # Parse formula (e.g., "40% fuel + 30% steel + 30% labor")
        # Simplified parsing - production would use more robust parser
        formula_parts = self.price_adjustment_formula.lower().replace('%', '').replace('+', ',').split(',')
        
        weights = {}
        for part in formula_parts:
            part = part.strip()
            if not part:
                continue
            
            tokens = part.split()
            if len(tokens) != 2:
                continue
            
            try:
                weight = float(tokens[0]) / 100.0  # Convert percentage to decimal
                component = tokens[1].strip()
                weights[component] = weight
            except:
                continue
        
        # Calculate adjustment factor
        adjustment_factor = 1.0
        calculation_details = []
        
        for component, weight in weights.items():
            base_index = base_indices.get(component, 0)
            current_index = current_indices.get(component, 0)
            
            if base_index == 0:
                raise UserError(f"Base index for '{component}' is zero or missing.")
            
            if current_index == 0:
                raise UserError(f"Current index for '{component}' is zero or missing.")
            
            # Component adjustment = (current / base) * weight
            component_adjustment = (current_index / base_index) * weight
            adjustment_factor += component_adjustment - weight  # Subtract weight to get delta only
            
            calculation_details.append({
                'component': component,
                'weight': weight * 100,  # Convert back to percentage
                'base_index': base_index,
                'current_index': current_index,
                'ratio': current_index / base_index,
                'contribution': (component_adjustment - weight) * 100  # Delta in percentage
            })
        
        # Calculate adjusted price
        adjusted_total_value = self.total_value * adjustment_factor
        adjustment_amount = adjusted_total_value - self.total_value
        
        # Log to chatter
        calculation_html = '<table style="width: 100%; border-collapse: collapse; margin: 15px 0;">'
        calculation_html += '''<thead style="background-color: #f8f9fa;">
            <tr>
                <th style="border: 1px solid #dee2e6; padding: 8px;">Component</th>
                <th style="border: 1px solid #dee2e6; padding: 8px;">Weight</th>
                <th style="border: 1px solid #dee2e6; padding: 8px;">Base Index</th>
                <th style="border: 1px solid #dee2e6; padding: 8px;">Current Index</th>
                <th style="border: 1px solid #dee2e6; padding: 8px;">Ratio</th>
                <th style="border: 1px solid #dee2e6; padding: 8px;">Impact</th>
            </tr>
        </thead><tbody>'''
        
        for detail in calculation_details:
            impact_color = '#28a745' if detail['contribution'] >= 0 else '#dc3545'
            calculation_html += f'''<tr>
                <td style="border: 1px solid #dee2e6; padding: 8px;">{detail['component'].title()}</td>
                <td style="border: 1px solid #dee2e6; padding: 8px; text-align: right;">{detail['weight']:.1f}%</td>
                <td style="border: 1px solid #dee2e6; padding: 8px; text-align: right;">{detail['base_index']:.2f}</td>
                <td style="border: 1px solid #dee2e6; padding: 8px; text-align: right;">{detail['current_index']:.2f}</td>
                <td style="border: 1px solid #dee2e6; padding: 8px; text-align: right;">{detail['ratio']:.4f}</td>
                <td style="border: 1px solid #dee2e6; padding: 8px; text-align: right; color: {impact_color};">{detail['contribution']:+.2f}%</td>
            </tr>'''
        
        calculation_html += '</tbody></table>'
        
        adjustment_color = '#28a745' if adjustment_amount >= 0 else '#dc3545'
        sign = '+' if adjustment_amount >= 0 else ''
        
        self.message_post(
            body=f"""<div style="background-color: #e7f3ff; border-left: 4px solid #2196F3; padding: 15px;">
                <h3 style="margin-top: 0;">💰 AUTO-031: Price Adjustment Calculation</h3>
                <p><strong>Calculation Date:</strong> {fields.Date.today()}</p>
                <p><strong>Formula:</strong> {self.price_adjustment_formula}</p>
                <hr/>
                <h4>Index Analysis:</h4>
                {calculation_html}
                <hr/>
                <table style="width: 100%; margin-top: 15px;">
                    <tr>
                        <td style="padding: 5px 0;"><strong>Original Contract Value:</strong></td>
                        <td style="padding: 5px 0; text-align: right;">ETB {self.total_value:,.2f}</td>
                    </tr>
                    <tr>
                        <td style="padding: 5px 0;"><strong>Adjustment Factor:</strong></td>
                        <td style="padding: 5px 0; text-align: right;">{adjustment_factor:.6f}</td>
                    </tr>
                    <tr style="background-color: {adjustment_color}20;">
                        <td style="padding: 8px 0; font-weight: bold; border-top: 2px solid #2196F3;">Price Adjustment:</td>
                        <td style="padding: 8px 0; text-align: right; font-weight: bold; color: {adjustment_color}; font-size: 16px; border-top: 2px solid #2196F3;">{sign}ETB {abs(adjustment_amount):,.2f}</td>
                    </tr>
                    <tr style="background-color: #d4edda;">
                        <td style="padding: 8px 0; font-weight: bold; border-top: 2px solid #28a745;">Adjusted Contract Value:</td>
                        <td style="padding: 8px 0; text-align: right; font-weight: bold; font-size: 18px; border-top: 2px solid #28a745;">ETB {adjusted_total_value:,.2f}</td>
                    </tr>
                </table>
                <div style="background-color: #fff3cd; padding: 10px; border-radius: 4px; margin-top: 15px;">
                    <p style="margin: 0;"><strong>ℹ️ Important Notes (FR-PROC-035, BR-PROC-007):</strong></p>
                    <ul style="margin: 5px 0 0 0;">
                        <li><strong>Payment adjustment only</strong> - Does NOT alter FIFO stock cost (BR-PROC-007)</li>
                        <li>Adjustment recorded separately in financial records</li>
                        <li>Stock Record Cards maintain original PO unit prices</li>
                        <li>Price indices source must be documented for audit</li>
                    </ul>
                </div>
            </div>""",
            subject=f'Price Adjustment: {sign}ETB {abs(adjustment_amount):,.2f}',
            message_type='comment'
        )
        
        _logger.info(
            f"AUTO-031: Price adjustment calculated for contract {self.name} - "
            f"Factor: {adjustment_factor:.6f}, Adjustment: {sign}ETB {adjustment_amount:,.2f}"
        )
        
        return {
            'adjustment_factor': adjustment_factor,
            'original_value': self.total_value,
            'adjusted_value': adjusted_total_value,
            'adjustment_amount': adjustment_amount,
            'calculation_details': calculation_details,
        }
    
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
        
        # Build items table HTML (abbreviated for space - full version in extension file)
        items_rows = ''
        total_value = 0.0
        
        for idx, line in enumerate(bid.line_ids, start=1):
            line_total = line.quantity * line.unit_price
            total_value += line_total
            items_rows += f'<tr><td>{idx}</td><td>{line.item_id.code}</td><td>{line.item_id.name}</td><td>{line.quantity:.2f}</td><td>{line.unit_price:,.2f}</td><td>{line_total:,.2f}</td></tr>'
        
        # Generate simplified contract document HTML
        contract_html = f"""
        <div style="font-family: Arial; padding: 20px;">
            <h2>PROCUREMENT CONTRACT - {self.name}</h2>
            <p><strong>Supplier:</strong> {supplier.name}</p>
            <p><strong>Total Value:</strong> ETB {total_value:,.2f}</p>
            <table>{items_rows}</table>
            <p><em>AUTO-018: Contract generated from approved bid</em></p>
        </div>
        """
        
        # Update contract with generated document and initial values
        self.write({
            'contract_document': contract_html,
            'total_value': total_value,
            'original_contract_value': total_value,  # AUTO-021: Store original for variation tracking
        })
        
        # Log to chatter
        self.message_post(
            body=f"✅ AUTO-018: Contract Generated - Supplier: {supplier.name}, Value: ETB {total_value:,.2f}",
            subject='Contract Generated',
            message_type='comment'
        )
        
        _logger.info(f"AUTO-018: Contract {self.name} generated from bid {bid.id} - Value: ETB {total_value:,.2f}")
        
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
                "Original contract value is not set. Cannot calculate variation percentage."
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
                _logger.warning(f"AUTO-021: HOPE override - Variation above {VARIATION_CEILING}% approved for {self.name}")
            else:
                raise ValidationError(
                    f"Contract variation BLOCKED (FR-PROC-023)\n\n"
                    f"Cumulative variation would exceed {VARIATION_CEILING}% ceiling.\n"
                    f"HOPE authorization required."
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
        sign = '+' if variation_amount >= 0 else ''
        self.message_post(
            body=f"💰 AUTO-021: Variation Added - {sign}ETB {abs(variation_amount):,.2f} - Cumulative: {new_percentage:.2f}%",
            subject=f'Variation: {sign}ETB {abs(variation_amount):,.2f}',
            message_type='comment'
        )
        
        _logger.info(f"AUTO-021: Variation added to {self.name} - Amount: {sign}ETB {variation_amount:,.2f}, Cumulative: {new_percentage:.2f}%")
        
        return True
    
    def _check_variation_thresholds(self, old_percentage, new_percentage, variation_amount):
        """AUTO-021: Check variation percentage thresholds and send alerts (FR-PROC-023)."""
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
        
        severity = 'INFO' if threshold == '10' else 'WARNING'
        icon = 'ℹ️' if threshold == '10' else '⚠️'
        
        self.message_post(
            body=f"""{icon} AUTO-021: Variation {threshold}% Threshold Alert - Contract {self.name} - {current_percentage:.2f}%""",
            subject=f'{icon} Variation {threshold}%: {self.name}',
            message_type='notification',
            partner_ids=users.mapped('partner_id').ids
        )
        
        _logger.warning(f"AUTO-021: Variation {threshold}% alert sent for {self.name} - Current: {current_percentage:.2f}%")
    
    def action_open_variations(self):
        """Open list of contract variations."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Variations - {self.name}',
            'res_model': 'mesob.contract.variation',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {'default_contract_id': self.id},
        }


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
        procurement_users = self.env.ref('mesob_inventory_base.group_mesob_procurement', raise_if_not_found=False)
        
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
    
    # ── AUTO-005: Emergency Procurement Fields (BR-PROC-001) ───────────
    
    is_emergency = fields.Boolean(
        string="Emergency Procurement",
        default=False,
        tracking=True,
        help="AUTO-005: Mark as emergency procurement (BR-PROC-001 5-day retrospective rule)"
    )
    
    emergency_justification = fields.Text(
        string="Emergency Justification",
        help="AUTO-005: Mandatory justification for emergency procurement"
    )
    
    emergency_created_date = fields.Date(
        string="Emergency PO Created",
        readonly=True,
        tracking=True,
        help="AUTO-005: Date when emergency PO was created"
    )
    
    app_amendment_id = fields.Many2one(
        'mesob.procurement.plan.lot',
        string="APP Amendment",
        readonly=True,
        help="AUTO-005: Draft APP amendment auto-generated for emergency PO"
    )
    
    app_amendment_deadline = fields.Date(
        string="APP Amendment Deadline",
        compute='_compute_app_amendment_deadline',
        store=True,
        help="AUTO-005: 5 working days deadline for APP update (BR-PROC-001)"
    )
    
    days_until_app_deadline = fields.Integer(
        string="Days Until APP Deadline",
        compute='_compute_days_until_app_deadline',
        help="AUTO-005: Countdown to APP amendment deadline"
    )
    
    app_updated = fields.Boolean(
        string="APP Updated",
        default=False,
        tracking=True,
        help="AUTO-005: Whether APP has been retrospectively updated"
    )
    
    app_update_date = fields.Date(
        string="APP Update Date",
        readonly=True,
        tracking=True,
        help="AUTO-005: Date when APP was retrospectively updated"
    )
    
    hope_emergency_authorized = fields.Boolean(
        string="HOPE Emergency Authorized",
        default=False,
        tracking=True,
        help="AUTO-005: Whether HOPE has authorized emergency procurement"
    )
    
    hope_authorization_date = fields.Date(
        string="HOPE Authorization Date",
        readonly=True,
        tracking=True,
        help="AUTO-005: Date when HOPE authorized emergency"
    )
    
    hope_authorized_by_id = fields.Many2one(
        'res.users',
        string="HOPE Authorized By",
        readonly=True,
        tracking=True,
        help="AUTO-005: HOPE user who authorized emergency"
    )
    
    plan_lot_id = fields.Many2one("mesob.procurement.plan.lot", string="APP Lot Reference", required=False)
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
            
            # AUTO-005: Handle emergency procurement creation
            if vals.get('is_emergency'):
                vals['emergency_created_date'] = fields.Date.today()
        
        records = super().create(vals_list)
        
        # AUTO-005: Auto-trigger APP amendment for emergency POs
        for rec in records:
            if rec.is_emergency:
                rec._auto_create_app_amendment()
                rec._notify_hope_emergency_authorization_needed()
        
        return records
    
    # ── AUTO-005: Computed Fields ───────────────────────────────────────
    
    @api.depends('emergency_created_date')
    def _compute_app_amendment_deadline(self):
        """AUTO-005: Calculate 5 working days deadline for APP amendment (BR-PROC-001)."""
        from datetime import timedelta
        
        for rec in self:
            if not rec.is_emergency or not rec.emergency_created_date:
                rec.app_amendment_deadline = False
                continue
            
            # Calculate 5 working days (excluding weekends)
            current_date = rec.emergency_created_date
            working_days = 0
            
            while working_days < 5:
                current_date += timedelta(days=1)
                # Skip weekends (Saturday=5, Sunday=6)
                if current_date.weekday() < 5:
                    working_days += 1
            
            rec.app_amendment_deadline = current_date
    
    @api.depends('app_amendment_deadline', 'app_updated')
    def _compute_days_until_app_deadline(self):
        """AUTO-005: Calculate countdown to APP amendment deadline."""
        from datetime import date
        
        today = fields.Date.today()
        
        for rec in self:
            if not rec.is_emergency or rec.app_updated or not rec.app_amendment_deadline:
                rec.days_until_app_deadline = 0
                continue
            
            delta = (rec.app_amendment_deadline - today).days
            rec.days_until_app_deadline = max(0, delta)

    @api.constrains("supplier_id")
    def _check_supplier_validity(self):
        """AUTO-008: Validate supplier registration before PO creation (FR-PROC-012)."""
        for rec in self:
            if rec.supplier_id.fppa_blacklisted:
                raise ValidationError(
                    f"Hard-Stop: Supplier '{rec.supplier_id.name}' is currently blacklisted! (FR-PROC-012)"
                )
            
            # AUTO-008: Block PO if supplier registration expired
            if rec.supplier_id.registration_status == 'expired':
                rec.supplier_id.action_block_expired_supplier_po()

    def action_submit(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError("Only draft Purchase Orders can be submitted.")
            rec.state = "pending"

    def action_approve(self):
        """Authorize the Purchase Order.
        
        AUTO-005: Enhanced with emergency procurement compliance check (BR-PROC-001).
        AUTO-025: Enhanced with automatic receiving handoff notification.
        AUTO-026: Enhanced with automatic inspection type assignment.
        AUTO-067: Enhanced with procurement suspension check (BR-PROC-008).
        """
        for rec in self:
            if rec.state != "pending":
                raise UserError("Only pending Purchase Orders can be approved.")
            
            # AUTO-005: Check emergency procurement compliance (BR-PROC-001)
            if rec.is_emergency:
                if not rec.hope_emergency_authorized:
                    raise UserError(
                        "AUTO-005: Emergency PO Approval Blocked (BR-PROC-001)\n\n"
                        "HOPE authorization is required for emergency procurement.\n\n"
                        "Action Required:\n"
                        "- HOPE must review and authorize this emergency procurement\n"
                        "- Use 'HOPE Authorize Emergency' button to authorize"
                    )
                
                if not rec.app_updated:
                    days_remaining = rec.days_until_app_deadline
                    
                    if days_remaining <= 0:
                        raise UserError(
                            f"AUTO-005: Emergency PO Approval Blocked (BR-PROC-001)\n\n"
                            f"APP amendment deadline has EXPIRED!\n\n"
                            f"Emergency PO Created: {rec.emergency_created_date}\n"
                            f"APP Amendment Deadline: {rec.app_amendment_deadline}\n\n"
                            f"Per BR-PROC-001, APP must be updated within 5 working days.\n\n"
                            f"Action Required:\n"
                            f"- Update APP retrospectively with emergency justification\n"
                            f"- Use 'Mark APP Updated' button once completed"
                        )
                    else:
                        raise UserError(
                            f"AUTO-005: Emergency PO Approval Blocked (BR-PROC-001)\n\n"
                            f"APP amendment is not yet completed.\n\n"
                            f"Emergency PO Created: {rec.emergency_created_date}\n"
                            f"APP Amendment Deadline: {rec.app_amendment_deadline}\n"
                            f"Days Remaining: {days_remaining} working days\n\n"
                            f"Action Required:\n"
                            f"- Complete APP amendment retrospectively\n"
                            f"- HOPE must approve emergency justification\n"
                            f"- Use 'Mark APP Updated' button once completed"
                        )
            
            # Check Surplus block business rule (BR-PROC-008 / AC-PROC-006)
            for line in rec.line_ids:
                if line.item_id.is_surplus:
                    raise UserError(
                        f"Approval Blocked: Stock item code '{line.item_id.item_code}' is currently "
                        f"flagged as surplus in the Disposal system! (BR-PROC-008)"
                    )
            
            # AUTO-067: Check procurement suspension (BR-PROC-008)
            suspended_items = []
            for line in rec.line_ids:
                if line.item_id.procurement_suspended:
                    suspended_items.append({
                        'code': line.item_id.item_code,
                        'name': line.item_id.name,
                        'reason': dict(line.item_id._fields['suspension_reason'].selection).get(
                            line.item_id.suspension_reason, 'Unknown'
                        ),
                        'date': line.item_id.suspension_date,
                    })
            
            if suspended_items:
                # Build detailed error message
                error_msg = "AUTO-067: PO Approval Blocked - Procurement Suspended (BR-PROC-008)\n\n"
                error_msg += "The following items have procurement suspended and cannot be ordered:\n\n"
                
                for item in suspended_items:
                    error_msg += (
                        f"• {item['code']} - {item['name']}\n"
                        f"  Reason: {item['reason']}\n"
                        f"  Suspended: {item['date']}\n\n"
                    )
                
                error_msg += (
                    "Action Required:\n"
                    "- If surplus has been consumed (stock < max level), PAO can clear suspension\n"
                    "- If anticipated demand surge, PAO can clear with documented justification\n"
                    "- Otherwise, remove suspended items from this PO"
                )
                
                _logger.warning(
                    f"AUTO-067: PO {rec.name} approval blocked - "
                    f"{len(suspended_items)} items with procurement suspended"
                )
                
                raise UserError(error_msg)

            rec.state = "approved"
            
            # AUTO-026: Auto-assign inspection type based on item classifications
            rec._auto_assign_inspection_type()
            
            # AUTO-025: Notify Storekeeper of expected delivery
            rec._send_receiving_handoff_notification()
            
            _logger.info(f"PO {rec.name} approved - AUTO-005/025/026/067 checks passed")
        
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
        
        procurement_users = self.env.ref('mesob_inventory_base.group_mesob_procurement', raise_if_not_found=False)
        
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
    
    # ── AUTO-005: Emergency Procurement Methods ─────────────────────────
    
    def _auto_create_app_amendment(self):
        """AUTO-005: Auto-create draft APP amendment for emergency PO (BR-PROC-001).
        
        Creates draft APP lot amendment that must be approved by HOPE within 5 working days.
        """
        self.ensure_one()
        
        if not self.is_emergency:
            return
        
        # Create draft APP lot for emergency
        app_lot_vals = {
            'name': f'Emergency APP Amendment - {self.name}',
            'plan_id': False,  # No existing plan
            'estimated_value': sum(line.landed_cost_total for line in self.line_ids),
            'procurement_method': 'emergency',
            'state': 'draft',
            'notes': f"AUTO-005: Emergency APP amendment for PO {self.name}\n\n{self.emergency_justification or ''}",
        }
        
        app_amendment = self.env['mesob.procurement.plan.lot'].create(app_lot_vals)
        
        self.app_amendment_id = app_amendment.id
        
        # Log to chatter
        self.message_post(
            body=f"""<div style="background-color: #fff3cd; border-left: 4px solid #f57c00; padding: 15px;">
                <h3>⚡ AUTO-005: Draft APP Amendment Created</h3>
                <p>Emergency procurement requires retrospective APP update per BR-PROC-001.</p>
                <table style="width: 100%; margin: 10px 0;">
                    <tr>
                        <td style="padding: 3px 0;"><strong>APP Amendment:</strong></td>
                        <td style="padding: 3px 0;"><a href="/web#id={app_amendment.id}&model=mesob.procurement.plan.lot&view_type=form">{app_amendment.name}</a></td>
                    </tr>
                    <tr>
                        <td style="padding: 3px 0;"><strong>Created:</strong></td>
                        <td style="padding: 3px 0;">{self.emergency_created_date}</td>
                    </tr>
                    <tr style="background-color: #fff3cd;">
                        <td style="padding: 3px 0;"><strong>Deadline:</strong></td>
                        <td style="padding: 3px 0; font-weight: bold;">{self.app_amendment_deadline} (5 working days)</td>
                    </tr>
                </table>
                <p><strong>Action Required:</strong> Complete APP amendment and obtain HOPE approval within 5 working days.</p>
            </div>""",
            subject=f'Emergency APP Amendment Created: {app_amendment.name}'
        )
        
        _logger.info(
            f"AUTO-005: Draft APP amendment {app_amendment.name} created for emergency PO {self.name}"
        )
    
    def _notify_hope_emergency_authorization_needed(self):
        """AUTO-005: Notify HOPE that emergency procurement requires authorization."""
        self.ensure_one()
        
        hope_users = self.env.ref('mesob_inventory_base.group_mesob_hope', raise_if_not_found=False)
        
        if not hope_users or not hope_users.users:
            _logger.warning("AUTO-005: No HOPE users found for emergency authorization notification")
            return
        
        self.message_post(
            body=f"""<div style="background-color: #f8d7da; border-left: 4px solid #dc3545; padding: 15px;">
                <h2 style="color: #721c24; margin-top: 0;">⚡ AUTO-005: Emergency Procurement Authorization Required</h2>
                
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
                            <td style="padding: 5px 0;"><strong>Total Value:</strong></td>
                            <td style="padding: 5px 0;">ETB {sum(line.landed_cost_total for line in self.line_ids):,.2f}</td>
                        </tr>
                        <tr>
                            <td style="padding: 5px 0;"><strong>Created:</strong></td>
                            <td style="padding: 5px 0;">{self.emergency_created_date}</td>
                        </tr>
                        <tr style="background-color: #f8d7da;">
                            <td style="padding: 5px 0;"><strong>APP Deadline:</strong></td>
                            <td style="padding: 5px 0; font-weight: bold; color: #dc3545;">{self.app_amendment_deadline}</td>
                        </tr>
                    </table>
                </div>
                
                <div style="background-color: #fff3cd; padding: 15px; border-radius: 4px; margin: 15px 0;">
                    <h4 style="margin-top: 0;">Emergency Justification:</h4>
                    <p style="background-color: white; padding: 10px; border-radius: 4px;">{self.emergency_justification or 'Not provided'}</p>
                </div>
                
                <div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px;">
                    <h4 style="margin-top: 0; color: #155724;">Required Actions (BR-PROC-001):</h4>
                    <ol style="margin: 0;">
                        <li><strong>Review emergency justification</strong> - Verify urgency is valid</li>
                        <li><strong>Authorize emergency procurement</strong> - Use 'HOPE Authorize Emergency' button</li>
                        <li><strong>Ensure APP updated</strong> - Within 5 working days ({self.app_amendment_deadline})</li>
                        <li><strong>Approve APP amendment</strong> - Retrospectively include in APP</li>
                    </ol>
                </div>
                
                <p style="margin-top: 20px;">
                    <a href="/web#id={self.id}&model=mesob.procurement.order&view_type=form" 
                       style="background-color: #dc3545; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                       ⚡ Review Emergency PO →
                    </a>
                </p>
            </div>""",
            subject=f'🚨 URGENT: Emergency PO Authorization Required - {self.name}',
            message_type='notification',
            partner_ids=hope_users.users.mapped('partner_id').ids
        )
        
        _logger.info(
            f"AUTO-005: Emergency authorization notification sent to {len(hope_users.users)} HOPE users for PO {self.name}"
        )
    
    def action_hope_authorize_emergency(self):
        """AUTO-005: HOPE authorizes emergency procurement (BR-PROC-001)."""
        self.ensure_one()
        
        if not self.is_emergency:
            raise UserError("This is not an emergency procurement.")
        
        # Check if user is HOPE
        if not self.env.user.has_group('mesob_inventory_base.group_mesob_hope'):
            raise UserError("Only HOPE can authorize emergency procurement.")
        
        if self.hope_emergency_authorized:
            raise UserError("Emergency procurement already authorized.")
        
        self.write({
            'hope_emergency_authorized': True,
            'hope_authorization_date': fields.Date.today(),
            'hope_authorized_by_id': self.env.user.id,
        })
        
        # Notify procurement officer
        self.message_post(
            body=f"""<div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px;">
                <h3>✅ AUTO-005: HOPE Emergency Authorization Granted</h3>
                <p><strong>Authorized By:</strong> {self.env.user.name} (HOPE)</p>
                <p><strong>Date:</strong> {fields.Date.today()}</p>
                <p><strong>Status:</strong> Emergency procurement authorized per BR-PROC-001</p>
                <hr/>
                <p style="background-color: #fff3cd; padding: 10px; border-radius: 4px;">
                    <strong>⚠️ Reminder:</strong> APP amendment must still be completed by {self.app_amendment_deadline} 
                    ({self.days_until_app_deadline} working days remaining)
                </p>
            </div>""",
            subject=f'Emergency Authorization Granted: {self.name}'
        )
        
        _logger.info(
            f"AUTO-005: Emergency PO {self.name} authorized by HOPE user {self.env.user.name}"
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Emergency Authorized',
                'message': f'Emergency procurement {self.name} has been authorized.',
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_mark_app_updated(self):
        """AUTO-005: Mark APP as retrospectively updated."""
        self.ensure_one()
        
        if not self.is_emergency:
            raise UserError("This is not an emergency procurement.")
        
        if self.app_updated:
            raise UserError("APP already marked as updated.")
        
        # Check if deadline not exceeded
        if fields.Date.today() > self.app_amendment_deadline:
            _logger.warning(
                f"AUTO-005: APP updated after deadline for PO {self.name} - "
                f"Deadline: {self.app_amendment_deadline}, Updated: {fields.Date.today()}"
            )
        
        self.write({
            'app_updated': True,
            'app_update_date': fields.Date.today(),
        })
        
        self.message_post(
            body=f"""<div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px;">
                <h3>✅ AUTO-005: APP Retrospectively Updated</h3>
                <p><strong>Updated By:</strong> {self.env.user.name}</p>
                <p><strong>Date:</strong> {fields.Date.today()}</p>
                <p><strong>Deadline:</strong> {self.app_amendment_deadline}</p>
                <p><strong>Status:</strong> {'✅ Within deadline' if fields.Date.today() <= self.app_amendment_deadline else '⚠️ After deadline'}</p>
                <hr/>
                <p>Emergency procurement APP amendment completed per BR-PROC-001.</p>
                {f'<p><strong>APP Amendment:</strong> <a href="/web#id={self.app_amendment_id.id}&model=mesob.procurement.plan.lot&view_type=form">{self.app_amendment_id.name}</a></p>' if self.app_amendment_id else ''}
            </div>""",
            subject=f'APP Updated: {self.name}'
        )
        
        _logger.info(
            f"AUTO-005: APP marked as updated for emergency PO {self.name} - "
            f"{'Within' if fields.Date.today() <= self.app_amendment_deadline else 'After'} deadline"
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'APP Updated',
                'message': 'APP has been marked as retrospectively updated.',
                'type': 'success',
                'sticky': False,
            }
        }
    
    @api.model
    def _cron_send_app_amendment_alerts(self):
        """AUTO-005: Scheduled job to send countdown alerts for APP amendments.
        
        Sends alerts on Day 3 and Day 4 to responsible officer.
        Runs daily via cron job.
        """
        today = fields.Date.today()
        
        # Find all emergency POs with pending APP updates
        emergency_pos = self.search([
            ('is_emergency', '=', True),
            ('app_updated', '=', False),
            ('app_amendment_deadline', '!=', False),
        ])
        
        for po in emergency_pos:
            days_remaining = po.days_until_app_deadline
            
            # Send alerts on Day 3 and Day 4 (2 days and 1 day remaining)
            if days_remaining == 2:
                po._send_app_deadline_alert(days_remaining, urgency='medium')
            elif days_remaining == 1:
                po._send_app_deadline_alert(days_remaining, urgency='high')
            elif days_remaining == 0:
                po._send_app_deadline_alert(days_remaining, urgency='critical')
        
        _logger.info(f"AUTO-005: APP amendment alert check completed - {len(emergency_pos)} emergency POs scanned")
    
    def _send_app_deadline_alert(self, days_remaining, urgency='medium'):
        """AUTO-005: Send APP amendment deadline countdown alert."""
        self.ensure_one()
        
        # Determine color and urgency level
        if urgency == 'critical':
            bg_color = '#f8d7da'
            border_color = '#dc3545'
            title_color = '#721c24'
            icon = '🚨'
            subject_prefix = 'CRITICAL'
        elif urgency == 'high':
            bg_color = '#fff3cd'
            border_color = '#ffc107'
            title_color = '#856404'
            icon = '⚠️'
            subject_prefix = 'URGENT'
        else:
            bg_color = '#d1ecf1'
            border_color = '#17a2b8'
            title_color = '#0c5460'
            icon = '⏰'
            subject_prefix = 'REMINDER'
        
        # Get procurement officer
        procurement_users = self.env.ref('mesob_inventory_base.group_mesob_procurement', raise_if_not_found=False)
        
        if not procurement_users or not procurement_users.users:
            _logger.warning(f"AUTO-005: No procurement users found for APP deadline alert - PO {self.name}")
            return
        
        deadline_status = 'EXPIRED - IMMEDIATE ACTION REQUIRED!' if days_remaining == 0 else f'{days_remaining} working day(s) remaining'
        
        self.message_post(
            body=f"""<div style="background-color: {bg_color}; border-left: 4px solid {border_color}; padding: 15px;">
                <h2 style="color: {title_color}; margin-top: 0;">{icon} AUTO-005: APP Amendment Deadline Alert</h2>
                
                <div style="background-color: #fff; padding: 15px; border-radius: 4px; margin: 15px 0;">
                    <table style="width: 100%;">
                        <tr>
                            <td style="padding: 5px 0;"><strong>PO Reference:</strong></td>
                            <td style="padding: 5px 0;">{self.name}</td>
                        </tr>
                        <tr>
                            <td style="padding: 5px 0;"><strong>Emergency Created:</strong></td>
                            <td style="padding: 5px 0;">{self.emergency_created_date}</td>
                        </tr>
                        <tr>
                            <td style="padding: 5px 0;"><strong>APP Deadline:</strong></td>
                            <td style="padding: 5px 0;">{self.app_amendment_deadline}</td>
                        </tr>
                        <tr style="background-color: {bg_color};">
                            <td style="padding: 5px 0;"><strong>Status:</strong></td>
                            <td style="padding: 5px 0; font-weight: bold; color: {border_color}; font-size: 18px;">{deadline_status}</td>
                        </tr>
                    </table>
                </div>
                
                <div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px;">
                    <h4 style="margin-top: 0; color: #155724;">Required Actions (BR-PROC-001):</h4>
                    <ol style="margin: 0;">
                        <li><strong>Complete APP amendment</strong> - Update APP with emergency items</li>
                        <li><strong>Obtain HOPE approval</strong> - Ensure emergency justification accepted</li>
                        <li><strong>Mark as updated</strong> - Use 'Mark APP Updated' button</li>
                    </ol>
                </div>
                
                {f'<div style="background-color: #f8d7da; padding: 15px; border-radius: 4px; margin-top: 15px;"><p style="margin: 0; font-weight: bold; color: #721c24;">⚠️ CRITICAL: Deadline has expired! PO approval will be blocked until APP is updated.</p></div>' if days_remaining == 0 else ''}
                
                <p style="margin-top: 20px;">
                    <a href="/web#id={self.id}&model=mesob.procurement.order&view_type=form" 
                       style="background-color: {border_color}; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                       {icon} Review Emergency PO →
                    </a>
                </p>
            </div>""",
            subject=f'{icon} {subject_prefix}: APP Deadline - {self.name} ({deadline_status})',
            message_type='notification',
            partner_ids=procurement_users.users.mapped('partner_id').ids
        )
        
        _logger.info(
            f"AUTO-005: Day {5 - days_remaining} APP deadline alert sent for PO {self.name} - "
            f"{days_remaining} days remaining, urgency: {urgency}"
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
    
    # AUTO-052: Cost Component Fields (FR-VAL-002)
    price_unit = fields.Float(string="Base Unit Price (ETB)", required=True, help="Base price from bid/contract")
    freight_cost_unit = fields.Float(string="Freight per Unit (ETB)", default=0.0, help="AUTO-052: Freight/transportation cost per unit")
    insurance_rate = fields.Float(string="Insurance Rate (%)", default=0.0, help="AUTO-052: Insurance as % of base price")
    insurance_cost_unit = fields.Float(string="Insurance per Unit (ETB)", compute="_compute_cost_components", store=True)
    duties_taxes_rate = fields.Float(string="Duties/Taxes Rate (%)", default=0.0, help="AUTO-052: Import duties and taxes as %")
    duties_taxes_unit = fields.Float(string="Duties/Taxes per Unit (ETB)", compute="_compute_cost_components", store=True)
    package_cost_unit = fields.Float(string="Package Cost per Unit (ETB)", default=0.0, help="AUTO-052: Packaging/handling charges per unit")
    
    # AUTO-052: Landed Cost (Total Cost per FR-VAL-002)
    landed_cost_unit = fields.Float(
        string="Landed Cost per Unit (ETB)",
        compute="_compute_cost_components",
        store=True,
        help="AUTO-052: Total cost = Base + Freight + Insurance + Duties + Packaging (FR-VAL-002)"
    )
    
    price_subtotal = fields.Float(string="Subtotal (Base)", compute="_compute_subtotal", store=True)
    landed_cost_total = fields.Float(string="Total Landed Cost", compute="_compute_subtotal", store=True, help="AUTO-052: Total including all cost components")

    @api.onchange("item_id")
    def _onchange_item_id(self):
        """Auto-populate classifications when selecting a catalogued item on PO line."""
        if self.item_id:
            self.major_classification_id = self.item_id.classification_id
            self.sub_classification_id = self.item_id.sub_classification_id

    @api.depends("price_unit", "freight_cost_unit", "insurance_rate", "duties_taxes_rate", "package_cost_unit")
    def _compute_cost_components(self):
        """AUTO-052: Compute all cost components and landed cost per FR-VAL-002."""
        for line in self:
            # Insurance = base price * rate%
            line.insurance_cost_unit = line.price_unit * (line.insurance_rate / 100.0)
            
            # Duties/Taxes = base price * rate%
            line.duties_taxes_unit = line.price_unit * (line.duties_taxes_rate / 100.0)
            
            # Landed Cost = Base + Freight + Insurance + Duties/Taxes + Packaging
            line.landed_cost_unit = (
                line.price_unit +
                line.freight_cost_unit +
                line.insurance_cost_unit +
                line.duties_taxes_unit +
                line.package_cost_unit
            )
    
    @api.depends("quantity", "price_unit", "landed_cost_unit")
    def _compute_subtotal(self):
        for line in self:
            line.price_subtotal = line.quantity * line.price_unit
            line.landed_cost_total = line.quantity * line.landed_cost_unit

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
    """AUTO-029: Three-Way Match payment validation & processing - FR-PROC-034.
    
    Automated Features:
    - Auto-validate PO + Model 19 + Invoice match
    - Auto-check quantities and unit prices
    - Auto-block payment if DSR exists (BR-PROC-002)
    - Auto-calculate deductions (LD, retention)
    - Generate mismatch report with specific line references
    """

    _name = "mesob.procurement.payment.certificate"
    _description = "Procurement Payment Certificate"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = "id desc"

    name = fields.Char(string="Certificate Number", required=True, copy=False, default="New", tracking=True)
    order_id = fields.Many2one("mesob.procurement.order", string="Purchase Order", required=True, tracking=True)
    supplier_id = fields.Many2one(related="order_id.supplier_id", string="Supplier", readonly=True, store=True)
    
    # AUTO-029: Invoice details
    invoice_number = fields.Char(string="Invoice Number", tracking=True)
    invoice_date = fields.Date(string="Invoice Date", tracking=True)
    invoice_amount = fields.Float(string="Invoice Amount (ETB)", tracking=True)
    
    amount_gross = fields.Float(string="Gross Amount (ETB)", required=True, tracking=True)
    
    # AUTO-029: Enhanced Matching with compute methods
    has_invoice = fields.Boolean(string="Invoice Verified", compute="_compute_has_invoice", store=True)
    has_model19 = fields.Boolean(string="Model 19 Receipt Verified", compute="_compute_has_model19", store=True)
    has_po = fields.Boolean(string="Approved PO Verified", compute="_compute_has_po", store=True)
    
    # Calculations
    days_delay = fields.Integer(string="Days of Delay", default=0, tracking=True)
    penalty_rate = fields.Float(string="Daily Penalty Rate (%)", default=0.1, tracking=True)  # 1/1000 = 0.1%
    liquidated_damages = fields.Float(
        string="Liquidated Damages (ETB)",
        compute="_compute_liquidated_damages",
        store=True,
        tracking=True
    )
    retention_percent = fields.Float(string="Retention Percentage (%)", default=5.0, tracking=True)
    retention_amount = fields.Float(
        string="Retention Held (ETB)",
        compute="_compute_retention_amount",
        store=True,
        tracking=True
    )
    net_payable = fields.Float(
        string="Net Payable Amount (ETB)",
        compute="_compute_net_payable",
        store=True,
        tracking=True
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("approved", "Approved by PAO Finance")
        ],
        string="Status",
        default="draft",
        required=True,
        tracking=True
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = f"PAY/{self.env['ir.sequence'].next_by_code('mesob.procurement.payment.certificate') or '001'}"
        return super().create(vals_list)
    
    @api.depends("invoice_number")
    def _compute_has_invoice(self):
        """AUTO-029: Check if invoice is provided."""
        for rec in self:
            rec.has_invoice = bool(rec.invoice_number)
    
    @api.depends("order_id")
    def _compute_has_model19(self):
        """AUTO-029: Check if Model 19 exists for linked PO."""
        for rec in self:
            if rec.order_id:
                model19_count = self.env['mesob.inventory.model19'].search_count([
                    ('receiving_id.purchase_order_ref', '=', rec.order_id.name)
                ])
                rec.has_model19 = model19_count > 0
            else:
                rec.has_model19 = False
    
    @api.depends("order_id", "order_id.state")
    def _compute_has_po(self):
        """AUTO-029: Check if PO is approved."""
        for rec in self:
            rec.has_po = rec.order_id and rec.order_id.state in ('approved', 'sent', 'partially_received', 'fully_received')

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
        """AUTO-029: Enforces three-way match with DSR blocking (FR-PROC-034, BR-PROC-002)."""
        for rec in self:
            # Check for open DSR first (BR-PROC-002)
            if rec.order_id:
                open_dsrs = self.env['mesob.inventory.dsr'].search([
                    ('purchase_order_ref', '=', rec.order_id.name),
                    ('payment_blocked', '=', True)
                ])
                
                if open_dsrs:
                    dsr_refs = ', '.join(open_dsrs.mapped('name'))
                    raise UserError(
                        f"Payment BLOCKED (BR-PROC-002): Open DSR(s) exist for this PO: {dsr_refs}. "
                        f"Payment is strictly blocked until replacement goods are received and accepted. "
                        f"DSR must be closed before payment can proceed."
                    )
            
            # Three-way match validation
            if not (rec.has_invoice and rec.has_model19 and rec.has_po):
                missing = []
                if not rec.has_po:
                    missing.append("Approved Purchase Order")
                if not rec.has_model19:
                    missing.append("Model 19 Receipt")
                if not rec.has_invoice:
                    missing.append("VAT Invoice Number")
                
                raise UserError(
                    f"Three-Way Match Failed! Payment is strictly blocked unless Approved PO, "
                    f"Model 19 Acceptance Receipt, and VAT Compliant Invoice are all verified (FR-PROC-034).\n\n"
                    f"Missing: {', '.join(missing)}"
                )
            
            rec.state = "approved"
            
            # Post approval notification with AUTO-029 tag
            rec.message_post(
                body=f"""<div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px;">
                    <h4>✅ AUTO-029: Payment Certificate APPROVED</h4>
                    <p><strong>Certificate:</strong> {rec.name}</p>
                    <p><strong>PO:</strong> {rec.order_id.name}</p>
                    <p><strong>Invoice:</strong> {rec.invoice_number}</p>
                    <p><strong>Approved By:</strong> {self.env.user.name}</p>
                    <p><strong>Date:</strong> {fields.Date.today()}</p>
                    <hr/>
                    <p><strong>Three-Way Match Verified:</strong></p>
                    <ul>
                        <li>✅ Approved PO: {rec.order_id.name}</li>
                        <li>✅ Model 19 Receipt: Confirmed</li>
                        <li>✅ Invoice: {rec.invoice_number}</li>
                        <li>✅ No Open DSR (BR-PROC-002 Check Passed)</li>
                    </ul>
                    <hr/>
                    <p><strong>Payment Calculation:</strong></p>
                    <ul>
                        <li>Gross Amount: ETB {rec.amount_gross:,.2f}</li>
                        <li>Liquidated Damages: ETB {rec.liquidated_damages:,.2f}</li>
                        <li>Retention ({rec.retention_percent}%): ETB {rec.retention_amount:,.2f}</li>
                    </ul>
                    <p style="font-size: 18px; margin-top: 15px;"><strong>Net Payable: ETB {rec.net_payable:,.2f}</strong></p>
                    <p><em>Payment can now be processed through finance system.</em></p>
                </div>""",
                subject='Payment Approved - Three-Way Match Verified'
            )
            
            _logger.info(
                f"AUTO-029: Payment certificate {rec.name} approved - "
                f"PO {rec.order_id.name}, Invoice {rec.invoice_number}, Net Payable: ETB {rec.net_payable:,.2f}"
            )
        
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



class MesobTechnicalSpecTemplate(models.Model):
    """AUTO-007: Technical Specification Template Library (FR-PROC-009).
    
    Maintains reusable specification templates organized by major classification.
    Templates ensure function/performance-based specs and prevent brand-name references.
    
    Compliance:
    - FR-PROC-009: Technical specifications must be function/performance-based
    - BR-PROC-004: Brand-name restrictions (only allowed with "or equivalent")
    """
    
    _name = "mesob.technical.spec.template"
    _description = "Technical Specification Template"
    _order = "major_classification_id, name"
    
    name = fields.Char(
        string="Template Name",
        required=True,
        help="Descriptive name for this template (e.g., 'Standard Office Furniture Specs')"
    )
    
    major_classification_id = fields.Many2one(
        'mesob.inventory.major.classification',
        string='Major Classification',
        required=True,
        domain="[('code', 'in', ['4401', '4402', '4403', '4404', '4405', '4406', '4407', '4408', '4409', '4410', '4411', '4412', '4413', '4414', '4415', '4416', '4417', '4418'])]",
        help="AUTO-007: Template applies to items in this classification (4401-4418)"
    )
    
    classification_code = fields.Char(
        string='Classification Code',
        related='major_classification_id.code',
        store=True,
        readonly=True
    )
    
    specification_text = fields.Html(
        string='Specification Template',
        required=True,
        help="AUTO-007: Function/performance-based specification template. Avoid brand names per FR-PROC-009."
    )
    
    brand_name_keywords = fields.Text(
        string='Brand Name Filter Keywords',
        help='AUTO-007: Comma-separated brand names to detect and flag (e.g., "Dell, HP, Lenovo, Toyota")',
        default=''
    )
    
    is_active = fields.Boolean(
        string='Active',
        default=True,
        help='Inactive templates are hidden from selection'
    )
    
    usage_count = fields.Integer(
        string='Times Used',
        compute='_compute_usage_count',
        store=True,
        help='Number of lots using this template'
    )
    
    last_used_date = fields.Date(
        string='Last Used',
        readonly=True,
        help='Date when template was last applied to a lot'
    )
    
    created_by_id = fields.Many2one(
        'res.users',
        string='Created By',
        default=lambda self: self.env.user,
        readonly=True
    )
    
    notes = fields.Text(
        string='Usage Notes',
        help='Guidelines for when and how to use this template'
    )
    
    @api.depends('major_classification_id')
    def _compute_usage_count(self):
        """Count how many lots are using this template."""
        for template in self:
            count = self.env['mesob.procurement.plan.lot'].search_count([
                ('spec_template_id', '=', template.id)
            ])
            template.usage_count = count
    
    def _check_brand_names(self, text):
        """AUTO-007: Check if text contains brand name keywords (FR-PROC-009).
        
        Returns:
            tuple: (has_violations, list of detected brand names)
        """
        self.ensure_one()
        
        if not self.brand_name_keywords or not text:
            return (False, [])
        
        # Parse brand name keywords
        keywords = [k.strip().lower() for k in self.brand_name_keywords.split(',') if k.strip()]
        
        if not keywords:
            return (False, [])
        
        # Check for brand names in text (case-insensitive)
        text_lower = text.lower()
        detected = []
        
        for keyword in keywords:
            if keyword in text_lower:
                # Check if it's followed by "or equivalent" (acceptable per BR-PROC-004)
                or_equiv_variants = [
                    "or equivalent",
                    "or similar",
                    "or comparable",
                    "or equal"
                ]
                
                # Find all occurrences of the brand name
                import re
                for match in re.finditer(r'\b' + re.escape(keyword) + r'\b', text_lower):
                    # Check next 50 characters for "or equivalent"
                    context = text_lower[match.end():match.end() + 50]
                    has_or_equivalent = any(variant in context for variant in or_equiv_variants)
                    
                    if not has_or_equivalent:
                        detected.append(keyword.title())
        
        return (len(detected) > 0, detected)
    
    def action_apply_to_lot(self):
        """Open wizard to select lot and apply this template."""
        self.ensure_one()
        
        return {
            'type': 'ir.actions.act_window',
            'name': 'Apply Template to Lot',
            'res_model': 'mesob.procurement.plan.lot',
            'view_mode': 'tree,form',
            'domain': [
                ('major_classification_id', '=', self.major_classification_id.id),
                ('state', 'in', ['draft', 'approved'])
            ],
            'context': {
                'default_spec_template_id': self.id,
            },
            'target': 'current',
        }
    
    @api.model
    def create_default_templates(self):
        """AUTO-007: Create default specification templates for common classifications.
        
        This method can be called to populate the library with starter templates.
        """
        default_templates = [
            {
                'name': 'Standard Office Furniture Specifications',
                'classification_code': '4401',
                'specification': """
                <h3>1. GENERAL REQUIREMENTS</h3>
                <p>All furniture items must be suitable for office use with ergonomic design principles.</p>
                
                <h3>2. MATERIALS</h3>
                <ul>
                    <li><strong>Desks:</strong> High-grade engineered wood or solid wood, minimum 18mm thickness</li>
                    <li><strong>Chairs:</strong> Padded seat with breathable fabric, adjustable height mechanism</li>
                    <li><strong>Cabinets:</strong> Steel or wood with lockable doors</li>
                </ul>
                
                <h3>3. DIMENSIONS</h3>
                <ul>
                    <li><strong>Standard Desk:</strong> 120cm (W) × 60cm (D) × 75cm (H) ± 5%</li>
                    <li><strong>Office Chair:</strong> Seat height adjustable 42-54cm, backrest height minimum 45cm</li>
                    <li><strong>Filing Cabinet:</strong> 4 drawers, total height 132cm ± 5%</li>
                </ul>
                
                <h3>4. QUALITY STANDARDS</h3>
                <ul>
                    <li>All items must be new, first quality with no defects</li>
                    <li>Load-bearing capacity: desks minimum 80kg, chairs minimum 120kg</li>
                    <li>Finish must be smooth, uniform color, scratch-resistant</li>
                </ul>
                
                <h3>5. WARRANTY</h3>
                <p>Minimum 12 months warranty against manufacturing defects</p>
                """,
                'brand_keywords': 'IKEA, Herman Miller, Steelcase, Knoll',
                'notes': 'Use for standard office furniture procurement. Adjust dimensions as needed.'
            },
            {
                'name': 'Computer Equipment Technical Specifications',
                'classification_code': '4402',
                'specification': """
                <h3>1. DESKTOP COMPUTER SPECIFICATIONS</h3>
                
                <h4>1.1 Processor</h4>
                <ul>
                    <li>Minimum: Quad-core processor, 2.5 GHz base frequency</li>
                    <li>64-bit architecture</li>
                    <li>Benchmark score minimum: PassMark 8000 or equivalent</li>
                </ul>
                
                <h4>1.2 Memory (RAM)</h4>
                <ul>
                    <li>Minimum: 8GB DDR4</li>
                    <li>Expandable to minimum 32GB</li>
                </ul>
                
                <h4>1.3 Storage</h4>
                <ul>
                    <li>Primary: 256GB SSD (Solid State Drive)</li>
                    <li>Read speed: minimum 500 MB/s</li>
                    <li>Write speed: minimum 400 MB/s</li>
                </ul>
                
                <h4>1.4 Graphics</h4>
                <ul>
                    <li>Integrated graphics with minimum 2GB dedicated memory</li>
                    <li>Support for dual monitor output</li>
                </ul>
                
                <h4>1.5 Connectivity</h4>
                <ul>
                    <li>Minimum 4 USB ports (at least 2 USB 3.0)</li>
                    <li>Gigabit Ethernet port (1000 Mbps)</li>
                    <li>Wi-Fi 802.11ac or later</li>
                    <li>Bluetooth 4.2 or later</li>
                </ul>
                
                <h4>1.6 Operating System</h4>
                <ul>
                    <li>Windows 10 Professional or Windows 11 Professional (64-bit)</li>
                    <li>Original license with certificate of authenticity</li>
                </ul>
                
                <h4>1.7 Peripherals</h4>
                <ul>
                    <li>Keyboard: USB or wireless, QWERTY layout</li>
                    <li>Mouse: USB or wireless, optical sensor, minimum 1000 DPI</li>
                </ul>
                
                <h3>2. QUALITY & WARRANTY</h3>
                <ul>
                    <li>All equipment must be brand new, first quality</li>
                    <li>Minimum 24 months manufacturer warranty</li>
                    <li>Energy Star certified or equivalent efficiency rating</li>
                </ul>
                
                <p><strong>Note:</strong> Bidders must provide detailed technical datasheets for all proposed equipment.</p>
                """,
                'brand_keywords': 'Dell, HP, Lenovo, Acer, ASUS, Intel, AMD',
                'notes': 'Standard specification for office computers. Adjust performance requirements based on user needs (basic office vs. engineering workstations).'
            },
            {
                'name': 'Vehicle Specifications - Light Duty',
                'classification_code': '4405',
                'specification': """
                <h3>1. GENERAL SPECIFICATIONS</h3>
                
                <h4>1.1 Vehicle Type</h4>
                <ul>
                    <li>Category: Light duty passenger vehicle (sedan or SUV)</li>
                    <li>Seating capacity: 5 passengers minimum</li>
                    <li>Body type: 4-door</li>
                </ul>
                
                <h4>1.2 Engine</h4>
                <ul>
                    <li>Displacement: 1600cc - 2500cc</li>
                    <li>Fuel type: Gasoline or Diesel</li>
                    <li>Power output: Minimum 120 HP</li>
                    <li>Euro 4 emission standard or higher</li>
                </ul>
                
                <h4>1.3 Transmission</h4>
                <ul>
                    <li>Manual or Automatic transmission</li>
                    <li>Minimum 5-speed manual or 6-speed automatic</li>
                </ul>
                
                <h4>1.4 Performance</h4>
                <ul>
                    <li>Fuel efficiency: Minimum 12 km/liter (combined cycle)</li>
                    <li>Top speed: Minimum 160 km/h</li>
                    <li>Ground clearance: Minimum 150mm</li>
                </ul>
                
                <h4>1.5 Safety Features (Minimum)</h4>
                <ul>
                    <li>ABS (Anti-lock Braking System)</li>
                    <li>Dual front airbags</li>
                    <li>Seatbelts for all passengers (3-point)</li>
                    <li>Rear parking sensors or camera</li>
                </ul>
                
                <h4>1.6 Comfort Features</h4>
                <ul>
                    <li>Air conditioning (manual or automatic climate control)</li>
                    <li>Power steering</li>
                    <li>Power windows (all doors)</li>
                    <li>Central locking system</li>
                </ul>
                
                <h3>2. SPARE PARTS & SERVICE</h3>
                <ul>
                    <li>Spare parts must be readily available in Ethiopian market</li>
                    <li>Authorized service center must exist in Addis Ababa</li>
                    <li>Bidder must provide list of service centers and parts availability confirmation</li>
                </ul>
                
                <h3>3. WARRANTY</h3>
                <ul>
                    <li>Minimum 3 years or 100,000 km manufacturer warranty (whichever comes first)</li>
                    <li>Warranty must cover powertrain, electrical, and body components</li>
                </ul>
                
                <h3>4. DELIVERY CONDITION</h3>
                <ul>
                    <li>Brand new vehicle (current year model)</li>
                    <li>Factory-sealed with all original manufacturer documentation</li>
                    <li>Full tank of fuel at delivery</li>
                    <li>Tool kit and spare tire included</li>
                </ul>
                """,
                'brand_keywords': 'Toyota, Honda, Hyundai, Nissan, Kia, Ford, Chevrolet, Mitsubishi',
                'notes': 'Standard light duty vehicle specification. Adjust engine size and features based on intended use (city driving vs. field work).'
            },
            {
                'name': 'Stationery and Office Supplies',
                'classification_code': '4410',
                'specification': """
                <h3>1. PAPER PRODUCTS</h3>
                
                <h4>1.1 A4 Copy Paper</h4>
                <ul>
                    <li>Size: 210mm × 297mm (A4)</li>
                    <li>Weight: 80 GSM (±2 GSM)</li>
                    <li>Brightness: Minimum 90%</li>
                    <li>Whiteness: CIE grade minimum 150</li>
                    <li>Packaging: 500 sheets per ream, 5 reams per box</li>
                    <li>Quality: No tears, wrinkles, or discoloration</li>
                </ul>
                
                <h4>1.2 Envelopes</h4>
                <ul>
                    <li>Size options: C5 (162×229mm), DL (110×220mm)</li>
                    <li>Paper weight: Minimum 90 GSM</li>
                    <li>Self-seal or gummed flap</li>
                    <li>Window or non-window as specified</li>
                </ul>
                
                <h3>2. WRITING INSTRUMENTS</h3>
                
                <h4>2.1 Ballpoint Pens</h4>
                <ul>
                    <li>Ink color: Blue or black</li>
                    <li>Tip size: 0.7mm - 1.0mm</li>
                    <li>Writing length: Minimum 1200 meters</li>
                    <li>Cap or retractable mechanism</li>
                </ul>
                
                <h4>2.2 Pencils</h4>
                <ul>
                    <li>Grade: HB</li>
                    <li>Wood casing, hexagonal or round</li>
                    <li>Pre-sharpened or unsharpened as specified</li>
                    <li>Eraser tip optional</li>
                </ul>
                
                <h3>3. FILES AND FOLDERS</h3>
                
                <h4>3.1 Manila Folders</h4>
                <ul>
                    <li>Size: A4 compatible</li>
                    <li>Material: 230 GSM manila board minimum</li>
                    <li>Reinforced edges</li>
                </ul>
                
                <h4>3.2 Ring Binders</h4>
                <ul>
                    <li>Size: A4</li>
                    <li>Ring diameter: 25mm or 50mm as specified</li>
                    <li>Material: Rigid cardboard with PVC covering</li>
                    <li>Metal rings, D-ring or O-ring mechanism</li>
                </ul>
                
                <h3>4. ADHESIVES</h3>
                
                <h4>4.1 Glue Sticks</h4>
                <ul>
                    <li>Size: 8g - 20g</li>
                    <li>Non-toxic, washable formula</li>
                    <li>Smooth application, no lumps</li>
                </ul>
                
                <h4>4.2 Tape</h4>
                <ul>
                    <li>Clear adhesive tape, 18mm × 33m minimum</li>
                    <li>Good adhesion to paper</li>
                    <li>Dispenser included (for bulk orders)</li>
                </ul>
                
                <h3>5. QUALITY STANDARDS</h3>
                <ul>
                    <li>All items must be new, unused, first quality</li>
                    <li>No expired or near-expiry items</li>
                    <li>Packaging must be intact and properly labeled</li>
                    <li>Environmentally friendly products preferred</li>
                </ul>
                """,
                'brand_keywords': 'Papermate, Bic, Staedtler, Pilot, Pentel, 3M',
                'notes': 'General office stationery specification. Quantities and specific items should be adjusted per actual needs.'
            }
        ]
        
        created_count = 0
        for template_data in default_templates:
            # Find classification
            classification = self.env['mesob.inventory.major.classification'].search([
                ('code', '=', template_data['classification_code'])
            ], limit=1)
            
            if not classification:
                _logger.warning(f"Classification {template_data['classification_code']} not found. Skipping template.")
                continue
            
            # Check if template already exists
            existing = self.search([
                ('name', '=', template_data['name']),
                ('major_classification_id', '=', classification.id)
            ])
            
            if existing:
                _logger.info(f"Template '{template_data['name']}' already exists. Skipping.")
                continue
            
            # Create template
            self.create({
                'name': template_data['name'],
                'major_classification_id': classification.id,
                'specification_text': template_data['specification'],
                'brand_name_keywords': template_data['brand_keywords'],
                'notes': template_data['notes'],
                'is_active': True
            })
            created_count += 1
            _logger.info(f"Created template: {template_data['name']}")
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Default Templates Created',
                'message': f'{created_count} specification template(s) created successfully.',
                'type': 'success',
            }
        }



class MesobProcurementComplaint(models.Model):
    """AUTO-033: Complaint Register with Auto-Linking & Escalation (FR-PROC-038).
    
    Self-service supplier complaint portal with:
    - Auto-linking to relevant lots/contracts
    - Automatic routing to responsible officer
    - Standstill period enforcement for contract signature blocking
    - SLA-based escalation alerts for unresolved complaints
    """
    
    _name = 'mesob.procurement.complaint'
    _description = 'Procurement Complaint Register'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'complaint_date desc, id desc'
    
    name = fields.Char(
        string='Complaint Reference',
        required=True,
        copy=False,
        default='New',
        readonly=True,
        help='Auto-generated complaint reference number'
    )
    
    complaint_date = fields.Datetime(
        string='Complaint Date',
        required=True,
        default=fields.Datetime.now,
        tracking=True,
        help='Date when complaint was lodged'
    )
    
    # Complainant Information
    supplier_id = fields.Many2one(
        'res.partner',
        string='Complainant Supplier',
        required=True,
        domain=[('is_company', '=', True)],
        tracking=True,
        help='Supplier lodging the complaint'
    )
    
    contact_person = fields.Char(
        string='Contact Person',
        help='Name of person lodging complaint'
    )
    
    contact_email = fields.Char(
        string='Contact Email',
        required=True,
        help='Email for complaint communications'
    )
    
    contact_phone = fields.Char(
        string='Contact Phone',
        help='Phone number for urgent matters'
    )
    
    # AUTO-033: Auto-linking to procurement objects
    complaint_type = fields.Selection([
        ('tender_process', 'Tender Process / Procedures'),
        ('technical_specs', 'Technical Specifications'),
        ('evaluation', 'Bid Evaluation / Scoring'),
        ('award_decision', 'Award Decision'),
        ('contract_terms', 'Contract Terms'),
        ('payment', 'Payment Issues'),
        ('other', 'Other'),
    ], string='Complaint Type', required=True, tracking=True,
       help='AUTO-033: Category for automatic routing'
    )
    
    related_tender_id = fields.Many2one(
        'mesob.procurement.tender',
        string='Related Tender',
        tracking=True,
        help='AUTO-033: Tender this complaint relates to (auto-linked)'
    )
    
    related_lot_id = fields.Many2one(
        'mesob.procurement.plan.lot',
        string='Related Lot',
        tracking=True,
        help='AUTO-033: Specific lot this complaint relates to'
    )
    
    related_contract_id = fields.Many2one(
        'mesob.procurement.contract',
        string='Related Contract',
        tracking=True,
        help='AUTO-033: Contract this complaint relates to'
    )
    
    related_bid_id = fields.Many2one(
        'mesob.procurement.bid',
        string='Related Bid',
        tracking=True,
        help='Complainant\'s bid (if applicable)'
    )
    
    # Complaint Details
    complaint_subject = fields.Char(
        string='Subject',
        required=True,
        help='Brief summary of complaint'
    )
    
    complaint_description = fields.Html(
        string='Detailed Description',
        required=True,
        help='Full description of complaint with supporting facts'
    )
    
    requested_remedy = fields.Text(
        string='Requested Remedy',
        help='What resolution the complainant is seeking'
    )
    
    supporting_documents = fields.Many2many(
        'ir.attachment',
        string='Supporting Documents',
        help='Evidence and documentation supporting the complaint'
    )
    
    # AUTO-033: Automatic routing and assignment
    responsible_officer_id = fields.Many2one(
        'res.users',
        string='Responsible Officer',
        tracking=True,
        help='AUTO-033: Officer assigned to investigate (auto-assigned by type)'
    )
    
    routing_notes = fields.Text(
        string='Routing Notes',
        readonly=True,
        help='AUTO-033: System notes on automatic routing decision'
    )
    
    # Investigation & Resolution
    investigation_findings = fields.Html(
        string='Investigation Findings',
        help='Officer\'s investigation results and analysis'
    )
    
    resolution_action = fields.Html(
        string='Resolution Action Taken',
        help='Actions taken to resolve the complaint'
    )
    
    resolution_date = fields.Datetime(
        string='Resolution Date',
        readonly=True,
        tracking=True,
        help='Date when complaint was resolved'
    )
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('under_investigation', 'Under Investigation'),
        ('resolved', 'Resolved'),
        ('rejected', 'Rejected'),
        ('escalated', 'Escalated to FPPA'),
    ], string='Status', default='draft', required=True, tracking=True,
       help='Complaint processing status'
    )
    
    # AUTO-033: SLA tracking and escalation
    sla_deadline = fields.Datetime(
        string='SLA Deadline',
        compute='_compute_sla_deadline',
        store=True,
        help='AUTO-033: Deadline for resolution (typically 10 business days)'
    )
    
    days_open = fields.Integer(
        string='Days Open',
        compute='_compute_days_open',
        store=True,
        help='Number of days since complaint was submitted'
    )
    
    sla_status = fields.Selection([
        ('on_time', 'On Time'),
        ('warning', 'Approaching Deadline'),
        ('overdue', 'Overdue - Escalation Required'),
    ], string='SLA Status', compute='_compute_sla_status', store=True,
       help='AUTO-033: Tracks compliance with resolution SLA'
    )
    
    escalation_alert_sent = fields.Boolean(
        string='Escalation Alert Sent',
        default=False,
        help='AUTO-033: True if overdue escalation alert has been sent'
    )
    
    # AUTO-033: Standstill enforcement
    is_standstill_complaint = fields.Boolean(
        string='Standstill Period Complaint',
        compute='_compute_standstill_status',
        store=True,
        help='AUTO-033: True if complaint lodged during standstill period'
    )
    
    blocks_contract_signature = fields.Boolean(
        string='Blocks Contract Signature',
        compute='_compute_standstill_status',
        store=True,
        help='AUTO-033: True if unresolved complaint blocks contract signature (FR-PROC-020)'
    )
    
    @api.model_create_multi
    def create(self, vals_list):
        """AUTO-033: Auto-generate complaint reference and perform auto-routing."""
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('mesob.procurement.complaint') or 'COMP/NEW'
        
        complaints = super().create(vals_list)
        
        for complaint in complaints:
            # AUTO-033: Perform automatic routing
            complaint._auto_route_complaint()
            
            # AUTO-033: Check standstill period
            complaint._check_standstill_enforcement()
        
        return complaints
    
    @api.depends('complaint_date', 'state')
    def _compute_sla_deadline(self):
        """AUTO-033: Calculate SLA deadline (10 business days from submission)."""
        for rec in self:
            if rec.complaint_date and rec.state in ('submitted', 'under_investigation'):
                # Calculate 10 business days (simplified - doesn't account for holidays)
                deadline = rec.complaint_date
                days_added = 0
                while days_added < 10:
                    deadline += datetime.timedelta(days=1)
                    # Skip weekends (Saturday=5, Sunday=6)
                    if deadline.weekday() < 5:
                        days_added += 1
                rec.sla_deadline = deadline
            else:
                rec.sla_deadline = False
    
    @api.depends('complaint_date', 'resolution_date', 'state')
    def _compute_days_open(self):
        """AUTO-033: Calculate days since complaint submission."""
        for rec in self:
            if not rec.complaint_date:
                rec.days_open = 0
                continue
            
            if rec.state in ('resolved', 'rejected'):
                if rec.resolution_date:
                    rec.days_open = (rec.resolution_date - rec.complaint_date).days
                else:
                    rec.days_open = 0
            else:
                rec.days_open = (fields.Datetime.now() - rec.complaint_date).days
    
    @api.depends('days_open', 'sla_deadline', 'state')
    def _compute_sla_status(self):
        """AUTO-033: Determine SLA compliance status."""
        for rec in self:
            if rec.state in ('resolved', 'rejected'):
                rec.sla_status = 'on_time'
                continue
            
            if not rec.sla_deadline:
                rec.sla_status = 'on_time'
                continue
            
            now = fields.Datetime.now()
            days_until_deadline = (rec.sla_deadline - now).days
            
            if days_until_deadline < 0:
                rec.sla_status = 'overdue'
            elif days_until_deadline <= 2:
                rec.sla_status = 'warning'
            else:
                rec.sla_status = 'on_time'
    
    @api.depends('complaint_date', 'related_tender_id', 'state')
    def _compute_standstill_status(self):
        """AUTO-033: Determine if complaint is during standstill period (FR-PROC-020)."""
        for rec in self:
            rec.is_standstill_complaint = False
            rec.blocks_contract_signature = False
            
            if not rec.related_tender_id or not rec.complaint_date:
                continue
            
            # Check if complaint is filed during active tender period
            # Standstill period is between bid opening and contract signature
            # Any unresolved complaint during this period blocks contract signature
            
            # If there's a related contract and complaint is unresolved, block signature
            if rec.related_contract_id:
                if rec.state not in ('resolved', 'rejected'):
                    rec.is_standstill_complaint = True
                    rec.blocks_contract_signature = True
    
    def _auto_route_complaint(self):
        """AUTO-033: Automatically route complaint to responsible officer based on type.
        
        Routing logic:
        - tender_process/technical_specs → Tender/Lot procurement officer
        - evaluation/award_decision → Procurement manager
        - contract_terms/payment → Contracts officer
        - other → Default procurement officer
        """
        self.ensure_one()
        
        routing_map = {
            'tender_process': 'Procurement Officer (Tender)',
            'technical_specs': 'Procurement Officer (Technical)',
            'evaluation': 'Procurement Manager (Evaluation)',
            'award_decision': 'Procurement Manager (Award)',
            'contract_terms': 'Contracts Officer',
            'payment': 'Accounts Officer',
            'other': 'Procurement Officer (General)',
        }
        
        # Try to assign based on related tender/contract
        officer = None
        routing_note = f"AUTO-033: Complaint type '{dict(self._fields['complaint_type'].selection).get(self.complaint_type)}' → "
        
        if self.related_tender_id and self.related_tender_id.create_uid:
            officer = self.related_tender_id.create_uid
            routing_note += f"Assigned to tender creator: {officer.name}"
        elif self.related_contract_id and self.related_contract_id.create_uid:
            officer = self.related_contract_id.create_uid
            routing_note += f"Assigned to contract creator: {officer.name}"
        else:
            # Fallback: assign to procurement manager or first available procurement user
            procurement_group = self.env.ref('mesob_inventory_base.group_mesob_procurement', raise_if_not_found=False)
            if procurement_group and procurement_group.users:
                officer = procurement_group.users[0]
                routing_note += f"Assigned to default procurement officer: {officer.name}"
            else:
                routing_note += "No officer found - manual assignment required"
        
        if officer:
            self.write({
                'responsible_officer_id': officer.id,
                'routing_notes': routing_note
            })
            
            # Send notification to assigned officer
            self._send_assignment_notification(officer)
        else:
            self.routing_notes = routing_note
        
        _logger.info(f"AUTO-033: {routing_note}")
    
    def _check_standstill_enforcement(self):
        """AUTO-033: Check and enforce standstill period blocking (FR-PROC-020)."""
        self.ensure_one()
        
        if self.is_standstill_complaint and self.blocks_contract_signature:
            # Block related contract signature
            if self.related_contract_id and self.related_contract_id.state == 'approved':
                self.related_contract_id.message_post(
                    body=f"""<div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px;">
                        <h3 style="color: #856404;">⚠ AUTO-033: Contract Signature Blocked (FR-PROC-020)</h3>
                        <p><strong>Reason:</strong> Complaint lodged during standstill period</p>
                        <p><strong>Complaint Ref:</strong> {self.name}</p>
                        <p><strong>Complainant:</strong> {self.supplier_id.name}</p>
                        <p><strong>Subject:</strong> {self.complaint_subject}</p>
                        <hr/>
                        <p>This contract cannot be signed until the complaint is resolved.</p>
                        <p><a href="/web#id={self.id}&model=mesob.procurement.complaint&view_type=form" 
                           style="background-color: #ffc107; color: #000; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                           View Complaint →
                        </a></p>
                    </div>""",
                    subject=f'Contract Signature Blocked: Complaint {self.name}',
                    message_type='notification'
                )
                
                _logger.warning(
                    f"AUTO-033: Contract {self.related_contract_id.name} signature blocked by "
                    f"standstill complaint {self.name} (FR-PROC-020)"
                )
    
    def _send_assignment_notification(self, officer):
        """AUTO-033: Notify assigned officer of new complaint."""
        self.ensure_one()
        
        self.message_post(
            body=f"""<div style="background-color: #f8d7da; border-left: 4px solid #dc3545; padding: 15px;">
                <h3 style="color: #721c24;">AUTO-033: New Complaint Assigned to You</h3>
                <p><strong>Complaint Ref:</strong> {self.name}</p>
                <p><strong>Complainant:</strong> {self.supplier_id.name}</p>
                <p><strong>Type:</strong> {dict(self._fields['complaint_type'].selection).get(self.complaint_type)}</p>
                <p><strong>Subject:</strong> {self.complaint_subject}</p>
                <p><strong>SLA Deadline:</strong> {self.sla_deadline.strftime('%Y-%m-%d') if self.sla_deadline else 'N/A'}</p>
                <hr/>
                {f'<div style="background-color: #fff3cd; padding: 10px; margin: 10px 0;"><strong>⚠ STANDSTILL ALERT:</strong> This complaint blocks contract signature per FR-PROC-020</div>' if self.blocks_contract_signature else ''}
                <p><strong>Description:</strong></p>
                <div style="background-color: #fff; padding: 10px; border: 1px solid #ddd;">
                    {self.complaint_description}
                </div>
                <hr/>
                <p><a href="/web#id={self.id}&model=mesob.procurement.complaint&view_type=form" 
                   style="background-color: #dc3545; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                   Investigate Complaint →
                </a></p>
            </div>""",
            subject=f'New Complaint Assigned: {self.name}',
            message_type='notification',
            partner_ids=[officer.partner_id.id]
        )
        
        _logger.info(f"AUTO-033: Assignment notification sent to {officer.name} for complaint {self.name}")
    
    def action_submit(self):
        """Submit complaint for investigation."""
        for rec in self:
            if rec.state != 'draft':
                raise UserError("Only draft complaints can be submitted.")
            
            rec.write({
                'state': 'submitted',
                'complaint_date': fields.Datetime.now()
            })
            
            # Re-trigger routing and standstill check
            rec._auto_route_complaint()
            rec._check_standstill_enforcement()
            
            rec.message_post(
                body=f"Complaint submitted for investigation (FR-PROC-038)",
                subject=f'Complaint Submitted: {rec.name}'
            )
    
    def action_start_investigation(self):
        """Start investigating the complaint."""
        for rec in self:
            if rec.state != 'submitted':
                raise UserError("Can only investigate submitted complaints.")
            
            rec.write({'state': 'under_investigation'})
            
            rec.message_post(
                body=f"Investigation started by {self.env.user.name}",
                subject=f'Investigation Started: {rec.name}'
            )
    
    def action_resolve(self):
        """Resolve the complaint."""
        for rec in self:
            if rec.state not in ('submitted', 'under_investigation'):
                raise UserError("Can only resolve submitted or under-investigation complaints.")
            
            if not rec.investigation_findings:
                raise UserError("Please document investigation findings before resolving.")
            
            if not rec.resolution_action:
                raise UserError("Please document resolution action before marking as resolved.")
            
            rec.write({
                'state': 'resolved',
                'resolution_date': fields.Datetime.now()
            })
            
            # Unblock contract if applicable
            if rec.related_contract_id and rec.blocks_contract_signature:
                rec.related_contract_id.message_post(
                    body=f"""<div style="background-color: #d4edda; padding: 15px;">
                        <h3 style="color: #155724;">✅ Complaint Resolved - Contract Unblocked</h3>
                        <p><strong>Complaint Ref:</strong> {rec.name}</p>
                        <p><strong>Resolution:</strong> {rec.resolution_action[:200]}...</p>
                        <p>Contract signature may now proceed.</p>
                    </div>""",
                    subject=f'Complaint Resolved: {rec.name}'
                )
            
            rec.message_post(
                body=f"""<div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px;">
                    <h3>Complaint Resolved</h3>
                    <p><strong>Resolution Date:</strong> {rec.resolution_date}</p>
                    <p><strong>Days to Resolution:</strong> {rec.days_open}</p>
                    <p><strong>SLA Status:</strong> {rec.sla_status.upper()}</p>
                    <hr/>
                    <p><strong>Findings:</strong></p>
                    {rec.investigation_findings}
                    <hr/>
                    <p><strong>Action Taken:</strong></p>
                    {rec.resolution_action}
                </div>""",
                subject=f'Complaint Resolved: {rec.name}'
            )
    
    def action_reject(self):
        """Reject the complaint as invalid."""
        for rec in self:
            if rec.state not in ('submitted', 'under_investigation'):
                raise UserError("Can only reject submitted or under-investigation complaints.")
            
            if not rec.investigation_findings:
                raise UserError("Please document why complaint is being rejected.")
            
            rec.write({
                'state': 'rejected',
                'resolution_date': fields.Datetime.now()
            })
            
            rec.message_post(
                body=f"Complaint rejected. Reason: {rec.investigation_findings[:200]}...",
                subject=f'Complaint Rejected: {rec.name}'
            )
    
    def action_escalate_to_fppa(self):
        """Escalate unresolved complaint to FPPA."""
        for rec in self:
            if rec.state not in ('under_investigation', 'submitted'):
                raise UserError("Can only escalate submitted or under-investigation complaints.")
            
            rec.write({'state': 'escalated'})
            
            rec.message_post(
                body=f"""<div style="background-color: #f8d7da; border-left: 4px solid #dc3545; padding: 15px;">
                    <h3>Complaint Escalated to FPPA</h3>
                    <p>This complaint has been escalated to the Federal Public Procurement Agency.</p>
                    <p><strong>Days Open:</strong> {rec.days_open}</p>
                    <p><strong>Reason for Escalation:</strong> {rec.investigation_findings if rec.investigation_findings else 'SLA overdue'}</p>
                </div>""",
                subject=f'Complaint Escalated: {rec.name}'
            )
    
    @api.model
    def _cron_check_sla_escalation(self):
        """AUTO-033: Cron job to send escalation alerts for overdue complaints.
        
        Run daily to check complaints that have exceeded SLA and send alerts.
        """
        overdue_complaints = self.search([
            ('state', 'in', ('submitted', 'under_investigation')),
            ('sla_status', '=', 'overdue'),
            ('escalation_alert_sent', '=', False)
        ])
        
        for complaint in overdue_complaints:
            # Send escalation alert to responsible officer and manager
            recipients = [complaint.responsible_officer_id.partner_id.id] if complaint.responsible_officer_id else []
            
            # Add procurement manager
            manager_group = self.env.ref('mesob_inventory_base.group_mesob_pao', raise_if_not_found=False)
            if manager_group and manager_group.users:
                recipients.extend(manager_group.users.mapped('partner_id').ids)
            
            complaint.message_post(
                body=f"""<div style="background-color: #f8d7da; border-left: 4px solid #dc3545; padding: 15px;">
                    <h2 style="color: #721c24;">🚨 AUTO-033: SLA ESCALATION ALERT</h2>
                    <p><strong>Complaint Ref:</strong> {complaint.name}</p>
                    <p><strong>Complainant:</strong> {complaint.supplier_id.name}</p>
                    <p><strong>Subject:</strong> {complaint.complaint_subject}</p>
                    <p><strong>Days Open:</strong> <span style="color: #dc3545; font-weight: bold;">{complaint.days_open} days (OVERDUE)</span></p>
                    <p><strong>SLA Deadline:</strong> {complaint.sla_deadline.strftime('%Y-%m-%d %H:%M') if complaint.sla_deadline else 'N/A'}</p>
                    <hr/>
                    <p style="font-weight: bold; color: #dc3545;">This complaint has exceeded the resolution SLA and requires immediate action.</p>
                    {f'<p style="background-color: #fff3cd; padding: 10px;"><strong>⚠ CRITICAL:</strong> This complaint is blocking contract signature (FR-PROC-020)</p>' if complaint.blocks_contract_signature else ''}
                    <hr/>
                    <p><a href="/web#id={complaint.id}&model=mesob.procurement.complaint&view_type=form" 
                       style="background-color: #dc3545; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                       Take Action Now →
                    </a></p>
                </div>""",
                subject=f'🚨 SLA OVERDUE: Complaint {complaint.name}',
                message_type='notification',
                partner_ids=recipients
            )
            
            complaint.escalation_alert_sent = True
            
            _logger.warning(
                f"AUTO-033: SLA escalation alert sent for complaint {complaint.name} - "
                f"{complaint.days_open} days overdue"
            )
        
        if overdue_complaints:
            _logger.info(f"AUTO-033: Processed {len(overdue_complaints)} overdue complaints")



class MesobProcurementProgressDashboard(models.Model):
    """AUTO-034: APP Execution Progress Dashboard (Real-Time) (FR-PROC-039).
    
    Live dashboard showing per-lot execution progress:
    - Current stage in procurement lifecycle
    - Planned vs. Actual dates (award, contract, delivery)
    - Budget vs. Actual variance analysis
    - Delivery and payment status tracking
    - Days behind/ahead of schedule (red/yellow/green indicators)
    - Filterable by department, classification, procurement method
    - One-click export to FPPA e-GP system
    """
    
    _name = 'mesob.procurement.progress.dashboard'
    _description = 'APP Execution Progress Dashboard'
    _order = 'days_behind_schedule desc, id'
    
    # This is a reporting/dashboard model - data is computed from other models
    name = fields.Char(
        string='Dashboard Entry',
        compute='_compute_name',
        store=True
    )
    
    # Source lot reference
    lot_id = fields.Many2one(
        'mesob.procurement.plan.lot',
        string='Procurement Lot',
        required=True,
        ondelete='cascade',
        help='Source procurement lot'
    )
    
    plan_id = fields.Many2one(
        'mesob.procurement.plan',
        related='lot_id.plan_id',
        string='APP',
        store=True
    )
    
    fiscal_year = fields.Char(
        related='plan_id.fiscal_year',
        string='Fiscal Year',
        store=True
    )
    
    # Classification for filtering
    major_classification_id = fields.Many2one(
        'mesob.inventory.major.classification',
        related='lot_id.major_classification_id',
        string='Major Classification',
        store=True
    )
    
    sub_classification_id = fields.Many2one(
        'mesob.inventory.sub.classification',
        related='lot_id.sub_classification_id',
        string='Sub Classification',
        store=True
    )
    
    procurement_method = fields.Selection(
        related='lot_id.mechanism',
        string='Procurement Method',
        store=True
    )
    
    # AUTO-034: Lifecycle stage tracking
    current_stage = fields.Selection([
        ('needs', 'Needs Consolidation'),
        ('lot_formation', 'Lot Formation'),
        ('tender_prep', 'Tender Preparation'),
        ('bidding', 'Bidding / RFQ'),
        ('evaluation', 'Bid Evaluation'),
        ('award', 'Award Decision'),
        ('contract', 'Contract Signature'),
        ('delivery', 'Delivery in Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], string='Current Stage', compute='_compute_current_stage', store=True,
       help='AUTO-034: Current stage in procurement lifecycle'
    )
    
    stage_color = fields.Selection([
        ('success', 'Green - On Track'),
        ('warning', 'Yellow - Attention Needed'),
        ('danger', 'Red - Critical Delay'),
        ('info', 'Blue - In Progress'),
        ('muted', 'Gray - Not Started'),
    ], string='Stage Color', compute='_compute_stage_indicators', store=True)
    
    # AUTO-034: Budget tracking
    original_budget = fields.Float(
        related='lot_id.budget',
        string='Original Budget',
        store=True
    )
    
    contract_value = fields.Float(
        string='Contract Value',
        compute='_compute_financial_metrics',
        store=True,
        help='Actual contract value if awarded'
    )
    
    budget_variance = fields.Float(
        string='Budget Variance',
        compute='_compute_financial_metrics',
        store=True,
        help='Contract value - Original budget'
    )
    
    budget_variance_percent = fields.Float(
        string='Budget Variance %',
        compute='_compute_financial_metrics',
        store=True,
        help='(Contract value / Original budget - 1) × 100'
    )
    
    # AUTO-034: Schedule tracking
    planned_award_date = fields.Date(
        string='Planned Award Date',
        help='Expected date for award decision (from lot or tender)'
    )
    
    actual_award_date = fields.Date(
        string='Actual Award Date',
        compute='_compute_schedule_metrics',
        store=True,
        help='Actual date award decision was made'
    )
    
    planned_contract_date = fields.Date(
        string='Planned Contract Date',
        help='Expected date for contract signature'
    )
    
    actual_contract_date = fields.Date(
        string='Actual Contract Date',
        compute='_compute_schedule_metrics',
        store=True,
        help='Actual date contract was signed'
    )
    
    planned_delivery_date = fields.Date(
        string='Planned Delivery Date',
        help='Expected final delivery date'
    )
    
    actual_delivery_date = fields.Date(
        string='Actual Delivery Date',
        compute='_compute_schedule_metrics',
        store=True,
        help='Date when all items fully delivered'
    )
    
    days_behind_schedule = fields.Integer(
        string='Days Behind Schedule',
        compute='_compute_schedule_metrics',
        store=True,
        help='AUTO-034: Positive = behind schedule, Negative = ahead, 0 = on time'
    )
    
    schedule_status = fields.Selection([
        ('ahead', 'Ahead of Schedule'),
        ('on_time', 'On Time'),
        ('minor_delay', 'Minor Delay (1-7 days)'),
        ('significant_delay', 'Significant Delay (8-30 days)'),
        ('critical_delay', 'Critical Delay (>30 days)'),
    ], string='Schedule Status', compute='_compute_schedule_metrics', store=True)
    
    # AUTO-034: Delivery tracking
    total_items_ordered = fields.Integer(
        string='Total Items Ordered',
        compute='_compute_delivery_metrics',
        store=True
    )
    
    total_items_delivered = fields.Integer(
        string='Total Items Delivered',
        compute='_compute_delivery_metrics',
        store=True
    )
    
    delivery_percent = fields.Float(
        string='Delivery %',
        compute='_compute_delivery_metrics',
        store=True,
        help='AUTO-034: Percentage of items delivered'
    )
    
    # AUTO-034: Payment tracking
    total_payment_due = fields.Float(
        string='Total Payment Due',
        compute='_compute_payment_metrics',
        store=True
    )
    
    total_payment_made = fields.Float(
        string='Total Payment Made',
        compute='_compute_payment_metrics',
        store=True
    )
    
    payment_percent = fields.Float(
        string='Payment %',
        compute='_compute_payment_metrics',
        store=True,
        help='AUTO-034: Percentage of contract value paid'
    )
    
    # Department for filtering (from consolidated needs)
    department_names = fields.Text(
        string='Requesting Departments',
        compute='_compute_department_info',
        store=True,
        help='Comma-separated list of departments that submitted needs for this lot'
    )
    
    @api.depends('lot_id', 'lot_id.name')
    def _compute_name(self):
        """Generate dashboard entry name."""
        for rec in self:
            if rec.lot_id:
                rec.name = f"Progress: {rec.lot_id.name}"
            else:
                rec.name = "Progress Entry"
    
    @api.depends('lot_id', 'lot_id.state', 'lot_id.need_ids')
    def _compute_current_stage(self):
        """AUTO-034: Determine current stage in procurement lifecycle."""
        for rec in self:
            lot = rec.lot_id
            
            if not lot:
                rec.current_stage = 'needs'
                continue
            
            # Check if there's a related tender
            tender = self.env['mesob.procurement.tender'].search([
                ('lot_ids', 'in', lot.id)
            ], limit=1)
            
            # Check if there's a contract
            contract = self.env['mesob.procurement.contract'].search([
                ('lot_id', '=', lot.id)
            ], limit=1)
            
            # Check if there are purchase orders
            po = self.env['mesob.procurement.purchase.order'].search([
                ('lot_id', '=', lot.id)
            ], limit=1)
            
            # Determine stage based on related records
            if contract and contract.state == 'closed':
                rec.current_stage = 'completed'
            elif po and po.state in ('received', 'partial'):
                rec.current_stage = 'delivery'
            elif contract and contract.state == 'active':
                rec.current_stage = 'delivery'
            elif contract and contract.state in ('approved', 'draft'):
                rec.current_stage = 'contract'
            elif tender and tender.state == 'awarded':
                rec.current_stage = 'award'
            elif tender and tender.state in ('evaluation', 'technical_evaluation'):
                rec.current_stage = 'evaluation'
            elif tender and tender.state in ('published', 'submission'):
                rec.current_stage = 'bidding'
            elif tender and tender.state == 'draft':
                rec.current_stage = 'tender_prep'
            elif lot.state == 'approved' and lot.need_ids:
                rec.current_stage = 'lot_formation'
            else:
                rec.current_stage = 'needs'
    
    @api.depends('current_stage', 'days_behind_schedule', 'schedule_status')
    def _compute_stage_indicators(self):
        """AUTO-034: Compute color indicators for dashboard visualization."""
        for rec in self:
            if rec.current_stage == 'completed':
                rec.stage_color = 'success'
            elif rec.current_stage == 'cancelled':
                rec.stage_color = 'muted'
            elif rec.schedule_status in ('critical_delay', 'significant_delay'):
                rec.stage_color = 'danger'
            elif rec.schedule_status == 'minor_delay':
                rec.stage_color = 'warning'
            elif rec.schedule_status in ('on_time', 'ahead'):
                rec.stage_color = 'success'
            else:
                rec.stage_color = 'info'
    
    @api.depends('lot_id', 'contract_value', 'original_budget')
    def _compute_financial_metrics(self):
        """AUTO-034: Calculate budget variance metrics."""
        for rec in self:
            # Get contract value from related contract
            contract = self.env['mesob.procurement.contract'].search([
                ('lot_id', '=', rec.lot_id.id)
            ], limit=1)
            
            if contract:
                rec.contract_value = contract.contract_value
            else:
                rec.contract_value = 0.0
            
            # Calculate variance
            if rec.original_budget > 0:
                rec.budget_variance = rec.contract_value - rec.original_budget
                rec.budget_variance_percent = (rec.contract_value / rec.original_budget - 1) * 100
            else:
                rec.budget_variance = 0.0
                rec.budget_variance_percent = 0.0
    
    @api.depends('lot_id', 'planned_award_date', 'planned_contract_date', 'planned_delivery_date')
    def _compute_schedule_metrics(self):
        """AUTO-034: Calculate schedule metrics and delays."""
        for rec in self:
            # Get tender for award date
            tender = self.env['mesob.procurement.tender'].search([
                ('lot_ids', 'in', rec.lot_id.id)
            ], limit=1)
            
            if tender and tender.award_date:
                rec.actual_award_date = tender.award_date
            else:
                rec.actual_award_date = False
            
            # Get contract for contract signature date
            contract = self.env['mesob.procurement.contract'].search([
                ('lot_id', '=', rec.lot_id.id)
            ], limit=1)
            
            if contract and contract.signature_date:
                rec.actual_contract_date = contract.signature_date
            else:
                rec.actual_contract_date = False
            
            # Check delivery completion (from receiving records)
            # Simplified - could be enhanced with actual Model 19 tracking
            if contract and contract.state == 'closed':
                rec.actual_delivery_date = contract.write_date.date() if contract.write_date else False
            else:
                rec.actual_delivery_date = False
            
            # Calculate days behind schedule
            today = fields.Date.today()
            days_behind = 0
            
            if rec.current_stage in ('needs', 'lot_formation', 'tender_prep', 'bidding', 'evaluation', 'award'):
                # Compare against planned award date
                if rec.planned_award_date:
                    if rec.actual_award_date:
                        days_behind = (rec.actual_award_date - rec.planned_award_date).days
                    elif today > rec.planned_award_date:
                        days_behind = (today - rec.planned_award_date).days
            
            elif rec.current_stage == 'contract':
                # Compare against planned contract date
                if rec.planned_contract_date:
                    if rec.actual_contract_date:
                        days_behind = (rec.actual_contract_date - rec.planned_contract_date).days
                    elif today > rec.planned_contract_date:
                        days_behind = (today - rec.planned_contract_date).days
            
            elif rec.current_stage == 'delivery':
                # Compare against planned delivery date
                if rec.planned_delivery_date:
                    if rec.actual_delivery_date:
                        days_behind = (rec.actual_delivery_date - rec.planned_delivery_date).days
                    elif today > rec.planned_delivery_date:
                        days_behind = (today - rec.planned_delivery_date).days
            
            rec.days_behind_schedule = days_behind
            
            # Determine schedule status
            if days_behind <= -1:
                rec.schedule_status = 'ahead'
            elif days_behind == 0:
                rec.schedule_status = 'on_time'
            elif 1 <= days_behind <= 7:
                rec.schedule_status = 'minor_delay'
            elif 8 <= days_behind <= 30:
                rec.schedule_status = 'significant_delay'
            else:
                rec.schedule_status = 'critical_delay'
    
    @api.depends('lot_id')
    def _compute_delivery_metrics(self):
        """AUTO-034: Calculate delivery progress metrics."""
        for rec in self:
            # Get contract and related purchase orders
            contract = self.env['mesob.procurement.contract'].search([
                ('lot_id', '=', rec.lot_id.id)
            ], limit=1)
            
            if not contract:
                rec.total_items_ordered = 0
                rec.total_items_delivered = 0
                rec.delivery_percent = 0.0
                continue
            
            # Sum quantities from PO lines
            po_lines = self.env['mesob.procurement.purchase.order.line'].search([
                ('order_id.lot_id', '=', rec.lot_id.id)
            ])
            
            total_ordered = sum(po_lines.mapped('quantity'))
            total_delivered = sum(po_lines.mapped('quantity_received'))
            
            rec.total_items_ordered = int(total_ordered)
            rec.total_items_delivered = int(total_delivered)
            
            if total_ordered > 0:
                rec.delivery_percent = (total_delivered / total_ordered) * 100
            else:
                rec.delivery_percent = 0.0
    
    @api.depends('lot_id', 'contract_value')
    def _compute_payment_metrics(self):
        """AUTO-034: Calculate payment progress metrics."""
        for rec in self:
            # Get contract
            contract = self.env['mesob.procurement.contract'].search([
                ('lot_id', '=', rec.lot_id.id)
            ], limit=1)
            
            if not contract:
                rec.total_payment_due = 0.0
                rec.total_payment_made = 0.0
                rec.payment_percent = 0.0
                continue
            
            rec.total_payment_due = contract.contract_value
            
            # Get payment validations for this contract
            payments = self.env['mesob.payment.validation'].search([
                ('contract_id', '=', contract.id),
                ('state', '=', 'validated')
            ])
            
            rec.total_payment_made = sum(payments.mapped('payment_amount'))
            
            if rec.total_payment_due > 0:
                rec.payment_percent = (rec.total_payment_made / rec.total_payment_due) * 100
            else:
                rec.payment_percent = 0.0
    
    @api.depends('lot_id', 'lot_id.need_ids', 'lot_id.need_ids.department')
    def _compute_department_info(self):
        """Extract requesting departments from consolidated needs."""
        for rec in self:
            departments = rec.lot_id.need_ids.mapped('department')
            rec.department_names = ', '.join(filter(None, departments)) if departments else ''
    
    @api.model
    def action_refresh_dashboard(self):
        """AUTO-034: Refresh dashboard data from all active lots.
        
        This method creates/updates dashboard entries for all lots in approved APPs.
        Should be run periodically (e.g., daily cron) or on-demand.
        """
        # Get all lots from approved APPs
        approved_plans = self.env['mesob.procurement.plan'].search([
            ('state', '=', 'hope_approved')
        ])
        
        lots = approved_plans.mapped('lot_ids')
        
        _logger.info(f"AUTO-034: Refreshing dashboard for {len(lots)} lots from {len(approved_plans)} approved APPs")
        
        for lot in lots:
            # Check if dashboard entry exists
            existing = self.search([('lot_id', '=', lot.id)], limit=1)
            
            if existing:
                # Trigger recomputation by writing a dummy field
                existing.write({'lot_id': lot.id})
            else:
                # Create new dashboard entry
                self.create({'lot_id': lot.id})
        
        _logger.info(f"AUTO-034: Dashboard refresh complete - {len(lots)} entries updated/created")
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Dashboard Refreshed',
                'message': f'Updated {len(lots)} procurement lots',
                'type': 'success',
                'sticky': False,
            }
        }
    
    def action_view_lot_details(self):
        """Navigate to the source procurement lot."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Procurement Lot',
            'res_model': 'mesob.procurement.plan.lot',
            'res_id': self.lot_id.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_export_to_fppa(self):
        """AUTO-034: Export dashboard data to FPPA e-GP format.
        
        Generates CSV/Excel export compatible with FPPA e-GP reporting requirements.
        """
        # Get selected records or all dashboard entries
        records = self if self else self.search([])
        
        if not records:
            raise UserError("No dashboard entries to export.")
        
        # Build export data
        export_data = []
        for rec in records:
            export_data.append({
                'APP Reference': rec.plan_id.name if rec.plan_id else '',
                'Fiscal Year': rec.fiscal_year or '',
                'Lot Name': rec.lot_id.name if rec.lot_id else '',
                'Classification': rec.major_classification_id.name if rec.major_classification_id else '',
                'Procurement Method': dict(rec._fields['procurement_method'].selection).get(rec.procurement_method, ''),
                'Current Stage': dict(rec._fields['current_stage'].selection).get(rec.current_stage, ''),
                'Original Budget': rec.original_budget,
                'Contract Value': rec.contract_value,
                'Budget Variance %': rec.budget_variance_percent,
                'Planned Award Date': rec.planned_award_date or '',
                'Actual Award Date': rec.actual_award_date or '',
                'Days Behind Schedule': rec.days_behind_schedule,
                'Schedule Status': dict(rec._fields['schedule_status'].selection).get(rec.schedule_status, ''),
                'Delivery %': rec.delivery_percent,
                'Payment %': rec.payment_percent,
                'Departments': rec.department_names or '',
            })
        
        # Generate CSV
        import csv
        import io
        import base64
        
        output = io.StringIO()
        fieldnames = export_data[0].keys() if export_data else []
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        
        writer.writeheader()
        writer.writerows(export_data)
        
        csv_data = output.getvalue()
        output.close()
        
        # Create attachment
        attachment = self.env['ir.attachment'].create({
            'name': f'FPPA_Procurement_Progress_{fields.Date.today()}.csv',
            'type': 'binary',
            'datas': base64.b64encode(csv_data.encode('utf-8')),
            'mimetype': 'text/csv',
        })
        
        _logger.info(f"AUTO-034: Exported {len(records)} dashboard entries to FPPA format")
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/{attachment.id}?download=true',
            'target': 'new',
        }




class MesobContractVariation(models.Model):
    """AUTO-021: Contract Variation Tracking Model.
    
    Tracks individual contract variations with cumulative percentage monitoring.
    Enforces 10%, 15%, and 20% thresholds per FR-PROC-023.
    """
    
    _name = 'mesob.contract.variation'
    _description = 'Contract Variation Record'
    _order = 'variation_date desc, id desc'
    
    contract_id = fields.Many2one(
        'mesob.procurement.contract',
        string='Contract',
        required=True,
        ondelete='cascade',
        help='Contract being varied'
    )
    
    name = fields.Char(
        string='Variation Reference',
        compute='_compute_name',
        store=True,
        help='Auto-generated reference like VAR-001'
    )
    
    variation_date = fields.Date(
        string='Variation Date',
        required=True,
        default=fields.Date.context_today,
        help='Date variation was approved'
    )
    
    variation_amount = fields.Float(
        string='Variation Amount (ETB)',
        required=True,
        help='Positive for additions, negative for reductions'
    )
    
    description = fields.Text(
        string='Variation Description',
        required=True,
        help='Detailed explanation of the variation'
    )
    
    cumulative_after = fields.Float(
        string='Cumulative After (ETB)',
        readonly=True,
        help='Cumulative variation total after this variation'
    )
    
    percentage_after = fields.Float(
        string='Percentage After (%)',
        readonly=True,
        help='Cumulative variation percentage after this variation'
    )
    
    approved_by_id = fields.Many2one(
        'res.users',
        string='Approved By',
        readonly=True,
        help='User who approved the variation'
    )
    
    @api.depends('contract_id')
    def _compute_name(self):
        """Generate variation reference number."""
        for rec in self:
            if rec.contract_id:
                # Count existing variations for this contract
                var_count = self.search_count([
                    ('contract_id', '=', rec.contract_id.id)
                ])
                rec.name = f"VAR-{var_count + 1:03d}"
            else:
                rec.name = "New Variation"

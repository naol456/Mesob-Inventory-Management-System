from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class MesobStockHandover(models.Model):
    """Stocks Handing/Taking-Over custody transfer - Section 4.9.

    Triggered by storekeeper transfer, duty travel, training, medical leave,
    promotion, or retirement. Formulates official certificate and counted sheet lines
    in presence of competent witness, distributed in triplicate (FR-HO-001/002/003).
    """

    _name = "mesob.stock.handover"
    _description = "Storekeeper Stock Handover"
    _order = "date desc, id desc"

    name = fields.Char(
        string="Handover Reference",
        required=True,
        copy=False,
        default="New",
    )
    trigger_event = fields.Selection(
        [
            ("leave", "Annual/Sick Leave"),
            ("retirement", "Retirement"),
            ("duty_travel", "Duty Travel outside station"),
            ("training", "Training outside station"),
            ("promotion", "Promotion"),
            ("transfer", "Transfer to another branch"),
            ("medical", "Medical Treatment"),
        ],
        string="Triggering Status Change",
        required=True,
        help="The official reasons trigger custody transfers (FR-HO-001).",
    )
    outgoing_storekeeper_id = fields.Many2one(
        "res.users",
        string="Outgoing Storekeeper (Custodian)",
        required=True,
        help="Outgoing storekeeper transferring custody (FR-HO-002).",
    )
    incoming_storekeeper_id = fields.Many2one(
        "res.users",
        string="Incoming Storekeeper (Receiver)",
        required=True,
        help="Incoming storekeeper taking custody (FR-HO-002).",
    )
    witness_id = fields.Many2one(
        "res.users",
        string="Competent Witness / PAO",
        required=True,
        help="Witness who oversees the custody count and signs off (FR-HO-002).",
    )
    date = fields.Date(
        string="Handover Date",
        required=True,
        default=fields.Date.today,
    )
    certificate = fields.Text(
        string="Handover Custody Certificate",
        help="Official custody transfer statement signed in presence of the witness.",
    )
    line_ids = fields.One2many(
        "mesob.stock.handover.line",
        "handover_id",
        string="Handover Count Sheet",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("counting", "Physical Counting"),
            ("signed", "Witness Signed"),
            ("done", "Custody Transferred"),
        ],
        string="Status",
        default="draft",
        required=True,
    )
    
    # AUTO-060: Handover Trigger Auto-Detection
    auto_triggered = fields.Boolean(
        string="Auto-Triggered",
        default=False,
        readonly=True,
        help="AUTO-060: True if handover was auto-triggered by system"
    )
    
    trigger_source = fields.Char(
        string="Trigger Source",
        readonly=True,
        help="AUTO-060: HR event or status change that triggered handover"
    )
    
    # AUTO-061: Certificate Auto-Generation
    certificate_generated = fields.Boolean(
        string="Certificate Auto-Generated",
        default=False,
        readonly=True,
        help="AUTO-061: True if certificate was auto-generated"
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("mesob.stock.handover") or "New"
        return super().create(vals_list)

    @api.constrains("outgoing_storekeeper_id", "incoming_storekeeper_id", "witness_id")
    def _check_distinct_participants(self):
        for rec in self:
            if rec.outgoing_storekeeper_id == rec.incoming_storekeeper_id:
                raise ValidationError("Outgoing and Incoming storekeepers must be distinct individuals.")
            if rec.witness_id in (rec.outgoing_storekeeper_id, rec.incoming_storekeeper_id):
                raise ValidationError("The witness must be an independent participant and cannot be a storekeeper.")

    def action_start_counting(self):
        """Pre-populates the handover count sheet with current system balances (FR-HO-002)."""
        for rec in self:
            if rec.state != "draft":
                raise UserError("Custody counting has already been initiated.")
            
            # Clear lines
            rec.line_ids.unlink()

            # Prepopulate lines
            items = self.env["mesob.inventory.item"].search([])
            for item in items:
                item._compute_current_stock()
                self.env["mesob.stock.handover.line"].create({
                    "handover_id": rec.id,
                    "item_id": item.id,
                    "system_qty": item.current_stock,
                    "counted_qty": item.current_stock,  # Default to matching
                })
            
            # Generate default certificate template text
            rec.certificate = (
                f"I, {rec.outgoing_storekeeper_id.name}, hereby hand over absolute custody of "
                f"the stock items listed below to the incoming storekeeper, {rec.incoming_storekeeper_id.name}, "
                f"under the supervision and witnessing of {rec.witness_id.name} on {rec.date} "
                f"due to triggering status change: '{dict(rec._fields['trigger_event'].selection).get(rec.trigger_event)}'."
            )
            rec.state = "counting"
        return True

    def action_sign_handover(self):
        """Witness and both storekeepers confirm and sign off (FR-HO-002)."""
        for rec in self:
            if rec.state != "counting":
                raise UserError("Only active counts can be signed.")
            rec.state = "signed"
        return True

    def action_finalize_handover(self):
        """Finalizes handover custody and closes the record (FR-HO-003)."""
        for rec in self:
            if rec.state != "signed":
                raise UserError("Handover must be signed by all parties before completion.")
            rec.state = "done"
        return True

    # ── Role-Based Access Control (UI Level) ────────────────────────

    @api.model
    def get_view(self, view_id=None, view_type="form", **options):
        """Apply role-based UI controls for Stock Handovers.
        
        Both PAO and Storekeepers can create and manage handovers.
        PAO acts as witness, Storekeepers transfer custody.
        """
        result = super(MesobStockHandover, self).get_view(view_id, view_type, **options)
        
        # Import lxml for XML manipulation
        from lxml import etree
        
        # Check user roles
        is_pao = self.env.user.has_group("mesob_inventory_base.group_mesob_pao")
        is_storekeeper = self.env.user.has_group("mesob_inventory_base.group_mesob_storekeeper")
        
        # Both roles have full access - no restrictions needed currently
        # This method is here for future enhancements if needed
        # (e.g., restrict editing based on user's role in the handover)
        
        return result


class MesobStockHandoverLine(models.Model):
    """Line item in Handover custody count sheet - FR-HO-002."""

    _name = "mesob.stock.handover.line"
    _description = "Stock Handover Line"

    handover_id = fields.Many2one(
        "mesob.stock.handover",
        string="Handover Event",
        required=True,
        ondelete="cascade",
    )
    item_id = fields.Many2one("mesob.inventory.item", string="Catalogued Item", required=True)
    item_code = fields.Char(related="item_id.item_code", string="Item Code", readonly=True)
    system_qty = fields.Float(string="System Balance", readonly=True)
    counted_qty = fields.Float(string="Physical Counted", required=True, default=0.0)
    discrepancy = fields.Float(
        string="Discrepancy",
        compute="_compute_discrepancy",
        store=True,
    )

    @api.depends("system_qty", "counted_qty")
    def _compute_discrepancy(self):
        for line in self:
            line.discrepancy = line.counted_qty - line.system_qty


    # ═══════════════════════════════════════════════════════════════════
    # AUTO-060: Handover Trigger Auto-Detection
    # AUTO-061: Handover Certificate Auto-Generation
    # ═══════════════════════════════════════════════════════════════════
    
    @api.model
    def auto_trigger_handover(self, storekeeper_id, trigger_event, trigger_source, incoming_storekeeper_id=None):
        """AUTO-060: Auto-create handover when storekeeper status changes (FR-HO-001)
        
        Args:
            storekeeper_id: ID of outgoing storekeeper
            trigger_event: One of the trigger_event selection values
            trigger_source: Description of HR event
            incoming_storekeeper_id: Optional ID of incoming storekeeper (if known)
        
        Returns:
            Created handover record
        """
        storekeeper = self.env['res.users'].browse(storekeeper_id)
        
        # Find PAO to act as witness
        pao_group = self.env.ref('mesob_inventory_base.group_mesob_pao', raise_if_not_found=False)
        pao = pao_group.users[0] if pao_group and pao_group.users else self.env.user
        
        # If no incoming storekeeper specified, leave for manual assignment
        if not incoming_storekeeper_id:
            # Find another storekeeper from the group
            storekeeper_group = self.env.ref('mesob_inventory_base.group_mesob_storekeeper', raise_if_not_found=False)
            if storekeeper_group:
                other_storekeepers = storekeeper_group.users.filtered(lambda u: u.id != storekeeper_id)
                incoming_storekeeper_id = other_storekeepers[0].id if other_storekeepers else storekeeper_id
            else:
                incoming_storekeeper_id = storekeeper_id
        
        # Create handover record
        handover = self.create({
            'trigger_event': trigger_event,
            'outgoing_storekeeper_id': storekeeper_id,
            'incoming_storekeeper_id': incoming_storekeeper_id,
            'witness_id': pao.id,
            'date': fields.Date.today(),
            'auto_triggered': True,
            'trigger_source': trigger_source,
        })
        
        # AUTO-061: Auto-generate certificate
        handover.action_generate_certificate()
        
        # Notify all participants
        handover.message_post(
            body=f"""<div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px;">
                <h3>🔔 AUTO-060: Handover Auto-Triggered</h3>
                <p><strong>Trigger Event:</strong> {dict(handover._fields['trigger_event'].selection).get(trigger_event)}</p>
                <p><strong>Trigger Source:</strong> {trigger_source}</p>
                <p><strong>Outgoing Storekeeper:</strong> {storekeeper.name}</p>
                <p><strong>Action Required:</strong> Complete physical count and sign handover certificate</p>
                <hr/>
                <p><em>FR-HO-001: Mandatory handover stock-taking triggered by status change</em></p>
            </div>""",
            subject=f'Handover Required: {storekeeper.name}',
            message_type='notification',
            partner_ids=(storekeeper.partner_id + pao.partner_id).ids
        )
        
        _logger.info(
            f"AUTO-060: Auto-triggered handover {handover.name} for {storekeeper.name} - "
            f"Event: {trigger_event}, Source: {trigger_source}"
        )
        
        return handover
    
    def action_generate_certificate(self):
        """AUTO-061: Auto-generate handover certificate (FR-HO-003)"""
        self.ensure_one()
        
        trigger_desc = dict(self._fields['trigger_event'].selection).get(self.trigger_event, 'Status Change')
        
        certificate_text = f"""
HANDOVER CERTIFICATE
Stock Custody Transfer

Reference: {self.name}
Date: {self.date}

I, {self.outgoing_storekeeper_id.name}, hereby hand over absolute custody of all stock items 
under my care to {self.incoming_storekeeper_id.name}, effective {self.date}.

TRIGGER EVENT: {trigger_desc}
{f'SOURCE: {self.trigger_source}' if self.trigger_source else ''}

This handover is conducted in the presence of {self.witness_id.name} (PAO/Witness), 
who supervises the physical count and verifies the accuracy of this transfer.

Both parties confirm:
1. Physical stock count has been completed
2. All discrepancies have been documented
3. Count sheets are attached and signed
4. Custody responsibility transfers upon signature

DISTRIBUTION (FR-HO-003):
- Original: PAO/Property Administration
- Duplicate: Incoming Storekeeper
- Triplicate: Outgoing Storekeeper

────────────────────────────────────────────────────────

SIGNATURES:

Outgoing Storekeeper: {self.outgoing_storekeeper_id.name}
Signature: __________________ Date: __________

Incoming Storekeeper: {self.incoming_storekeeper_id.name}
Signature: __________________ Date: __________

Witness (PAO): {self.witness_id.name}
Signature: __________________ Date: __________

────────────────────────────────────────────────────────
Federal Democratic Republic of Ethiopia
Mesob Center - Stock Management System
Auto-Generated Certificate (AUTO-061)
"""
        
        self.write({
            'certificate': certificate_text,
            'certificate_generated': True
        })
        
        self.message_post(
            body="<p>AUTO-061: Handover certificate auto-generated and ready for signatures</p>",
            subject='Certificate Generated',
            message_type='comment'
        )
        
        return True

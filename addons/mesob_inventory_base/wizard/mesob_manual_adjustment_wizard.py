"""AUTO-050: Manual Stock Adjustment Wizard.

This wizard allows Storekeeper to create manual stock adjustments
that require PAO approval before posting. Ensures audit trail and
prevents unauthorized stock changes.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class MesobManualAdjustmentWizard(models.TransientModel):
    """Wizard for creating manual stock adjustments with PAO approval workflow."""
    
    _name = "mesob.manual.adjustment.wizard"
    _description = "Manual Stock Adjustment Wizard"
    
    sub_classification_id = fields.Many2one(
        "mesob.inventory.sub.classification",
        string="Sub Classification",
        required=True,
        help="Sub-classification to adjust",
    )
    
    major_classification_id = fields.Many2one(
        "mesob.inventory.major.classification",
        string="Major Classification",
        related="sub_classification_id.major_classification_id",
        readonly=True,
    )
    
    location = fields.Char(
        string="Location",
        required=True,
        default="Main Store",
        help="Storage location",
    )
    
    current_balance = fields.Float(
        string="Current Balance",
        compute="_compute_current_balance",
        help="Current stock balance from Bin Card",
    )
    
    physical_count = fields.Float(
        string="Physical Count",
        required=True,
        digits="Product Unit of Measure",
        help="Actual quantity counted during physical stock take",
    )
    
    adjustment_quantity = fields.Float(
        string="Adjustment Quantity",
        compute="_compute_adjustment_quantity",
        store=True,
        help="Difference between physical count and system balance",
    )
    
    adjustment_type = fields.Selection(
        [
            ("increase", "Stock Increase"),
            ("decrease", "Stock Decrease"),
        ],
        string="Adjustment Type",
        compute="_compute_adjustment_type",
        store=True,
    )
    
    uom_id = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
        required=True,
        help="Unit of measure for this adjustment",
    )
    
    adjustment_reason = fields.Text(
        string="Adjustment Reason",
        required=True,
        help=(
            "Required: Explain why this adjustment is necessary.\n"
            "Examples: Physical count discrepancy, damage, theft, data entry error, etc."
        ),
    )
    
    supporting_document = fields.Char(
        string="Supporting Document Reference",
        help="Reference to stock take report, memo, or other supporting document",
    )
    
    date = fields.Date(
        string="Adjustment Date",
        required=True,
        default=fields.Date.today,
    )
    
    @api.depends("sub_classification_id", "location")
    def _compute_current_balance(self):
        """Get current stock balance from latest Bin Card entry."""
        for record in self:
            if not record.sub_classification_id or not record.location:
                record.current_balance = 0.0
                continue
            
            BinCard = self.env["mesob.bin.card"]
            latest_entry = BinCard.search(
                [
                    ("sub_classification_id", "=", record.sub_classification_id.id),
                    ("location", "=", record.location),
                ],
                order="date desc, id desc",
                limit=1,
            )
            
            record.current_balance = latest_entry.balance if latest_entry else 0.0
    
    @api.depends("current_balance", "physical_count")
    def _compute_adjustment_quantity(self):
        """Calculate adjustment quantity (positive or negative)."""
        for record in self:
            record.adjustment_quantity = record.physical_count - record.current_balance
    
    @api.depends("adjustment_quantity")
    def _compute_adjustment_type(self):
        """Determine if this is an increase or decrease."""
        for record in self:
            if record.adjustment_quantity > 0:
                record.adjustment_type = "increase"
            elif record.adjustment_quantity < 0:
                record.adjustment_type = "decrease"
            else:
                record.adjustment_type = False
    
    @api.constrains("adjustment_reason")
    def _check_adjustment_reason(self):
        """Ensure adjustment reason is meaningful."""
        for record in self:
            if not record.adjustment_reason or not record.adjustment_reason.strip():
                raise ValidationError(_("Adjustment reason cannot be empty."))
            
            if len(record.adjustment_reason.strip()) < 20:
                raise ValidationError(
                    _("Adjustment reason is too short. "
                      "Please provide a detailed explanation (minimum 20 characters).")
                )
    
    @api.constrains("physical_count")
    def _check_physical_count(self):
        """Ensure physical count is not negative."""
        for record in self:
            if record.physical_count < 0:
                raise ValidationError(_("Physical count cannot be negative."))
    
    def action_create_adjustment(self):
        """Create manual adjustment entry in Bin Card (requires PAO approval)."""
        self.ensure_one()
        
        # Verify Storekeeper role
        if not self.env.user.has_group("mesob_inventory_base.group_mesob_storekeeper"):
            raise UserError(
                _("Only Storekeepers can create manual stock adjustments.")
            )
        
        # Check if adjustment is needed
        if abs(self.adjustment_quantity) < 0.01:
            raise UserError(
                _(f"No adjustment needed. Physical count ({self.physical_count}) "
                  f"matches system balance ({self.current_balance}).")
            )
        
        # Create Bin Card entry in draft state (requires PAO approval)
        BinCard = self.env["mesob.bin.card"]
        
        bin_card_vals = {
            "major_classification_id": self.major_classification_id.id,
            "sub_classification_id": self.sub_classification_id.id,
            "location": self.location,
            "date": self.date,
            "transaction_type": "adjustment",
            "reference": f"Manual Adjustment - Physical Count",
            "description": f"AUTO-050: Manual adjustment created via wizard\n{self.adjustment_reason}",
            "quantity_received": self.adjustment_quantity if self.adjustment_quantity > 0 else 0.0,
            "quantity_distributed": abs(self.adjustment_quantity) if self.adjustment_quantity < 0 else 0.0,
            "uom_id": self.uom_id.id,
            "received_by_id": self.env.user.id,
            "state": "draft",  # Requires PAO approval
            "adjustment_reason": self.adjustment_reason,
            "supporting_document": self.supporting_document,
        }
        
        bin_card = BinCard.create(bin_card_vals)
        
        # Task 7: Send activity notification to PAO for approval
        pao_group = self.env.ref('mesob_inventory_base.group_mesob_pao', raise_if_not_found=False)
        if pao_group and pao_group.users:
            bin_card._schedule_activity(
                activity_code='mesob_activity_manual_adjustment_approval',
                user_ids=pao_group.users.ids,
                summary=_('Manual Stock Adjustment Approval Required'),
                note=_(
                    '<p><strong>Item:</strong> %s</p>'
                    '<p><strong>Location:</strong> %s</p>'
                    '<p><strong>Current Balance:</strong> %s</p>'
                    '<p><strong>Physical Count:</strong> %s</p>'
                    '<p><strong>Adjustment:</strong> %+.2f</p>'
                    '<p><strong>Reason:</strong> %s</p>'
                ) % (
                    self.sub_classification_id.name,
                    self.location,
                    self.current_balance,
                    self.physical_count,
                    self.adjustment_quantity,
                    self.adjustment_reason or 'Not specified',
                ),
            )
        
        # Post message to chatter
        bin_card.message_post(
            body=_(
                f"<b>Manual Adjustment Created (Awaiting PAO Approval)</b><br/>"
                f"<b>Created by:</b> {self.env.user.name}<br/>"
                f"<b>Current Balance:</b> {self.current_balance}<br/>"
                f"<b>Physical Count:</b> {self.physical_count}<br/>"
                f"<b>Adjustment:</b> {self.adjustment_quantity:+.2f}<br/>"
                f"<b>Reason:</b> {self.adjustment_reason}"
            ),
            subject="Manual Adjustment Pending Approval",
        )
        
        return {
            "type": "ir.actions.act_window",
            "name": "Manual Adjustment Created",
            "res_model": "mesob.bin.card",
            "res_id": bin_card.id,
            "view_mode": "form",
            "target": "current",
        }

"""AUTO-038: Duplicate Item Detection Wizard.

This wizard shows similar items when creating a new item,
allowing the user to use an existing item or proceed with creation.
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError


class MesobDuplicateItemWizard(models.TransientModel):
    """Wizard to show duplicate items and let user decide."""
    
    _name = "mesob.duplicate.item.wizard"
    _description = "Duplicate Item Detection Wizard"
    
    item_name = fields.Char(
        string="New Item Name",
        required=True,
        readonly=True,
    )
    
    classification_id = fields.Many2one(
        "mesob.inventory.major.classification",
        string="Classification",
        readonly=True,
    )
    
    similar_item_ids = fields.Many2many(
        "mesob.inventory.item",
        string="Similar Items Found",
        readonly=True,
        help="Items with similar names in the same classification",
    )
    
    similar_item_count = fields.Integer(
        string="Similar Items Count",
        compute="_compute_similar_item_count",
    )
    
    user_decision = fields.Selection(
        [
            ("use_existing", "Use Existing Item"),
            ("create_new", "Create New Item Anyway"),
        ],
        string="Decision",
        required=True,
        default="use_existing",
    )
    
    selected_item_id = fields.Many2one(
        "mesob.inventory.item",
        string="Select Existing Item to Use",
        domain="[('id', 'in', similar_item_ids)]",
    )
    
    @api.depends("similar_item_ids")
    def _compute_similar_item_count(self):
        """Count similar items."""
        for record in self:
            record.similar_item_count = len(record.similar_item_ids)
    
    def action_confirm(self):
        """User confirms their decision."""
        self.ensure_one()
        
        if self.user_decision == "use_existing":
            if not self.selected_item_id:
                raise UserError(
                    _("Please select an existing item to use, or choose 'Create New Item Anyway'.")
                )
            
            # Return the selected existing item
            return {
                "type": "ir.actions.act_window",
                "name": "Existing Item",
                "res_model": "mesob.inventory.item",
                "res_id": self.selected_item_id.id,
                "view_mode": "form",
                "target": "current",
            }
        
        else:  # create_new
            # User chose to create new item despite duplicates
            # Return to the form to proceed with creation
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Proceed with Creation",
                    "message": "You can now save the new item. The system will log this as a potential duplicate.",
                    "type": "warning",
                    "sticky": False,
                },
            }

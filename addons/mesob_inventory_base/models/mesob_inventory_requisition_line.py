from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class MesobInventoryRequisitionLine(models.Model):
    """Individual line item on a Stores Requisition (Model 20).

    Each line references an inventory item and specifies the quantity
    requested along with the unit of measure.
    """

    _name = "mesob.inventory.requisition.line"
    _description = "Stores Requisition Line"

    requisition_id = fields.Many2one(
        "mesob.inventory.requisition",
        required=True,
        ondelete="cascade",
    )
    
    # Classification fields for item selection
    major_classification_id = fields.Many2one(
        "mesob.inventory.major.classification",
        string="Major Classification",
        help="Filter items by major classification",
    )
    sub_classification_id = fields.Many2one(
        "mesob.inventory.sub.classification",
        string="Sub Classification",
        help="Filter items by sub classification",
    )
    
    item_id = fields.Many2one(
        "mesob.inventory.item",
        string="Item",
        help="Select specific item, or use Major/Sub classification to request by category.",
    )
    quantity = fields.Float(
        string="Quantity Requested",
        required=True,
        default=1.0,
    )
    uom_id = fields.Many2one(
        "uom.uom",
        string="Unit of Measure",
        help="Unit of measure for this requisition line.",
    )
    note = fields.Char(string="Remarks")

    @api.onchange("major_classification_id")
    def _onchange_major_classification(self):
        """Filter sub-classifications and items when major changes."""
        # Clear sub and item if they don't match new major
        if self.sub_classification_id and self.major_classification_id:
            if self.sub_classification_id.major_classification_id != self.major_classification_id:
                self.sub_classification_id = False
        
        # Clear item if it doesn't match new major
        if self.item_id and self.major_classification_id:
            if self.item_id.classification_id != self.major_classification_id:
                self.item_id = False
        
        # Return domains for filtering
        result = {'domain': {}}
        
        if self.major_classification_id:
            # Filter subs by major
            result['domain']['sub_classification_id'] = [
                ('major_classification_id', '=', self.major_classification_id.id),
                ('active', '=', True)
            ]
            # Filter items by major
            result['domain']['item_id'] = [
                ('classification_id', '=', self.major_classification_id.id),
                ('active', '=', True)
            ]
        else:
            result['domain']['sub_classification_id'] = [('id', '=', False)]
            result['domain']['item_id'] = []
        
        return result

    @api.onchange("sub_classification_id")
    def _onchange_sub_classification(self):
        """Filter items when sub-classification changes."""
        # Clear item if it doesn't match sub
        if self.item_id and self.sub_classification_id:
            if self.item_id.sub_classification_id != self.sub_classification_id:
                self.item_id = False
        
        # Return domain for item filtering
        if self.sub_classification_id:
            return {
                'domain': {
                    'item_id': [
                        ('sub_classification_id', '=', self.sub_classification_id.id),
                        ('active', '=', True)
                    ]
                }
            }
        elif self.major_classification_id:
            # Only major selected, filter by major
            return {
                'domain': {
                    'item_id': [
                        ('classification_id', '=', self.major_classification_id.id),
                        ('active', '=', True)
                    ]
                }
            }
        else:
            return {'domain': {'item_id': []}}

    @api.onchange("item_id")
    def _onchange_item_id(self):
        """Auto-fill UoM from item."""
        if self.item_id:
            if self.item_id.uom_id:
                self.uom_id = self.item_id.uom_id

    @api.constrains('item_id', 'major_classification_id', 'sub_classification_id')
    def _check_item_or_classification(self):
        """Ensure either item or classifications are provided."""
        for line in self:
            if not line.item_id and not line.major_classification_id:
                raise ValidationError(
                    "Please select either a specific Item OR a Major Classification."
                )

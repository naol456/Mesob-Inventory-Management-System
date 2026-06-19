from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class MesobInventoryRequisitionLine(models.Model):
    """Individual line item on a Stores Requisition (Model 20).

    Each line references an inventory item and specifies the quantity
    requested along with the unit of measure.
    
    AUTO-042: Enhanced with intelligent pre-fill:
    - Displays real-time stock availability when selecting items
    - Pre-fills last issued quantity for same item/department
    - Suggests order quantity based on usage patterns
    - Alerts if item is controlled (FR-ISSUE-004)
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
        help="AUTO-042: Select specific item with real-time stock display.",
    )
    
    # AUTO-042: Stock availability display
    current_stock = fields.Float(
        string="Current Stock",
        compute='_compute_current_stock',
        help="AUTO-042: Real-time stock on hand"
    )
    
    stock_status = fields.Selection([
        ('critical', '🔴 Critical - Below Minimum'),
        ('low', '🟠 Low - Below Reorder'),
        ('normal', '🟢 Normal'),
        ('out_of_stock', '⛔ Out of Stock'),
    ], string="Stock Status", compute='_compute_current_stock')
    
    # AUTO-042: Last issued quantity intelligence
    last_issued_quantity = fields.Float(
        string="Last Issued Qty",
        compute='_compute_last_issued_quantity',
        help="AUTO-042: Last issued quantity for this item to your department"
    )
    
    suggested_quantity = fields.Float(
        string="Suggested Qty",
        compute='_compute_suggested_quantity',
        help="AUTO-042: Suggested order quantity based on usage patterns"
    )
    
    is_controlled_item = fields.Boolean(
        string="Controlled",
        related='item_id.is_controlled',
        help="FR-ISSUE-004: Restricted to authorized individuals only"
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

    # ── AUTO-042: Computed Fields ───────────────────────────────────────
    
    @api.depends('item_id')
    def _compute_current_stock(self):
        """AUTO-042: Display real-time stock availability."""
        for line in self:
            if not line.item_id or not line.item_id.sub_classification_id:
                line.current_stock = 0.0
                line.stock_status = 'out_of_stock'
                continue
            
            # Get latest bin card balance
            bin_card = self.env['mesob.bin.card'].search([
                ('sub_classification_id', '=', line.item_id.sub_classification_id.id),
                ('location', '=', 'Main Store')
            ], order='date desc, id desc', limit=1)
            
            line.current_stock = bin_card.balance if bin_card else 0.0
            
            # Determine status
            if line.current_stock <= 0:
                line.stock_status = 'out_of_stock'
            elif line.item_id.minimum_level > 0 and line.current_stock < line.item_id.minimum_level:
                line.stock_status = 'critical'
            elif line.item_id.reorder_level > 0 and line.current_stock < line.item_id.reorder_level:
                line.stock_status = 'low'
            else:
                line.stock_status = 'normal'
    
    @api.depends('item_id', 'requisition_id.department')
    def _compute_last_issued_quantity(self):
        """AUTO-042: Pre-fill last issued quantity for same item/department."""
        for line in self:
            if not line.item_id or not line.requisition_id.department:
                line.last_issued_quantity = 0.0
                continue
            
            # Find last issued voucher for this item to this department
            last_issue = self.env['mesob.inventory.issue.voucher'].search([
                ('state', 'in', ['issued', 'received']),
                ('requisition_id.department', '=', line.requisition_id.department),
                ('line_ids.item_id', '=', line.item_id.id)
            ], order='issue_date desc', limit=1)
            
            if last_issue:
                # Get quantity from matching line
                issue_line = last_issue.line_ids.filtered(lambda l: l.item_id == line.item_id)
                line.last_issued_quantity = sum(issue_line.mapped('quantity_issued'))
            else:
                line.last_issued_quantity = 0.0
    
    @api.depends('item_id', 'last_issued_quantity', 'current_stock')
    def _compute_suggested_quantity(self):
        """AUTO-042: Suggest order quantity based on usage patterns."""
        for line in self:
            if not line.item_id:
                line.suggested_quantity = 1.0
                continue
            
            # Strategy: Suggest last issued quantity if available, otherwise 1.0
            if line.last_issued_quantity > 0:
                # Cap suggestion at current stock to prevent over-ordering
                if line.current_stock > 0:
                    line.suggested_quantity = min(line.last_issued_quantity, line.current_stock)
                else:
                    line.suggested_quantity = line.last_issued_quantity
            else:
                line.suggested_quantity = 1.0
    
    # ── Onchange Methods ─────────────────────────────────────────────────
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
        """AUTO-042: Auto-fill UoM and suggest quantity from item with alerts."""
        if self.item_id:
            # Auto-fill UoM
            if self.item_id.uom_id:
                self.uom_id = self.item_id.uom_id
            
            # AUTO-042: Pre-fill quantity suggestion
            if self.suggested_quantity > 0 and not self.quantity or self.quantity == 1.0:
                self.quantity = self.suggested_quantity
            
            # AUTO-042: Alert if controlled item
            if self.item_id.is_controlled:
                return {
                    'warning': {
                        'title': 'FR-ISSUE-004: Controlled Material',
                        'message': (
                            f'{self.item_id.item_code} - {self.item_id.name}\n\n'
                            f'This is a controlled material (e.g., drugs, chemicals, explosives).\n'
                            f'Issue is restricted to authorized individuals only.\n\n'
                            f'Ensure you have proper authorization before submitting this requisition.'
                        )
                    }
                }
            
            # AUTO-042: Alert if out of stock
            if self.stock_status == 'out_of_stock':
                return {
                    'warning': {
                        'title': 'Stock Unavailable',
                        'message': (
                            f'{self.item_id.item_code} - {self.item_id.name}\n\n'
                            f'Current Stock: {self.current_stock:.0f}\n'
                            f'Status: Out of Stock\n\n'
                            f'This requisition may need to wait for new stock delivery.'
                        )
                    }
                }
            
            # AUTO-042: Info message if pre-filled quantity
            if self.last_issued_quantity > 0:
                return {
                    'warning': {
                        'title': 'AUTO-042: Quantity Pre-filled',
                        'message': (
                            f'Quantity auto-filled based on last issued amount: {self.last_issued_quantity:.0f}\n'
                            f'Current Stock Available: {self.current_stock:.0f}\n\n'
                            f'You can adjust this quantity if needed.'
                        ),
                        'type': 'info'
                    }
                }

    @api.constrains('item_id', 'major_classification_id', 'sub_classification_id')
    def _check_item_or_classification(self):
        """Ensure either item or classifications are provided."""
        for line in self:
            if not line.item_id and not line.major_classification_id:
                raise ValidationError(
                    "Please select either a specific Item OR a Major Classification."
                )

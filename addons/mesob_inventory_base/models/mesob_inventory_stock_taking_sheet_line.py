# -*- coding: utf-8 -*-
"""
Mesob Inventory Stock Taking Sheet Line (SRS 4.8)
FR-ST-005, FR-ST-006, FR-ST-007: Individual item counts with discrepancy tracking
"""

from odoo import models, fields, api, _


class MesobInventoryStockTakingSheetLine(models.Model):
    """
    FR-ST-005: Colored-sticker marking (counted marker)
    FR-ST-006: Compare physical counts vs records
    FR-ST-007: Capture discrepancy reasons and corrective actions
    """
    _name = 'mesob.inventory.stock.taking.sheet.line'
    _description = 'Stock Taking Sheet Line'
    _order = 'sheet_id, item_id'

    sheet_id = fields.Many2one('mesob.inventory.stock.taking.sheet', string='Sheet',
                              required=True, ondelete='cascade')
    event_id = fields.Many2one(related='sheet_id.event_id', string='Event', store=True)
    item_id = fields.Many2one('mesob.inventory.item', string='Item', required=True)
    item_code = fields.Char(related='item_id.item_code', string='Item Code', store=True)
    item_name = fields.Char(related='item_id.name', string='Item Name', store=True)
    classification_code = fields.Char(related='item_id.classification_id.code', string='Classification', store=True)
    location_id = fields.Many2one('stock.location', string='Location', required=True)
    
    # Expected Quantities (from records)
    expected_quantity = fields.Float(string='Expected Quantity', digits=(16, 2),
                                    help='Quantity from bin card/stock record')
    bin_card_balance = fields.Float(string='Bin Card Balance', digits=(16, 2))
    stock_record_balance = fields.Float(string='Stock Record Balance', digits=(16, 2))
    
    # FR-ST-005: Counted Marker (colored-sticker equivalent)
    is_counted = fields.Boolean(string='Counted', default=False,
                                help='Mark as counted to prevent double counting')
    counted_quantity = fields.Float(string='Counted Quantity', digits=(16, 2))
    counted_date = fields.Datetime(string='Counted Date/Time')
    counted_by_id = fields.Many2one('res.users', string='Counted By')
    
    # FR-ST-006: Discrepancy Calculation
    discrepancy_quantity = fields.Float(string='Discrepancy', compute='_compute_discrepancy',
                                       store=True, digits=(16, 2))
    has_discrepancy = fields.Boolean(string='Has Discrepancy', compute='_compute_discrepancy',
                                    store=True)
    discrepancy_type = fields.Selection([
        ('none', 'No Discrepancy'),
        ('shortage', 'Shortage'),
        ('overage', 'Overage')
    ], string='Discrepancy Type', compute='_compute_discrepancy', store=True)
    discrepancy_percentage = fields.Float(string='Discrepancy %', compute='_compute_discrepancy',
                                         store=True, digits=(5, 2))
    
    # FR-ST-007: Discrepancy Reasons and Corrective Actions
    discrepancy_reason = fields.Selection([
        ('counting_error', 'Counting Error'),
        ('record_error', 'Recording Error'),
        ('theft', 'Theft/Loss'),
        ('damage', 'Damage/Spoilage'),
        ('evaporation', 'Evaporation/Shrinkage'),
        ('unauthorized_issue', 'Unauthorized Issue'),
        ('receiving_error', 'Receiving Error'),
        ('other', 'Other')
    ], string='Discrepancy Reason')
    reason_notes = fields.Text(string='Reason Details')
    corrective_action = fields.Text(string='Corrective Action')
    action_responsible_id = fields.Many2one('res.users', string='Action Responsible')
    action_deadline = fields.Date(string='Action Deadline')
    action_completed = fields.Boolean(string='Action Completed')
    
    # UOM
    uom_id = fields.Many2one(related='item_id.uom_id', string='Unit of Measure', store=True)
    
    # Notes
    notes = fields.Text(string='Notes')
    
    # Company
    company_id = fields.Many2one(related='sheet_id.company_id', store=True)

    @api.depends('expected_quantity', 'counted_quantity', 'is_counted')
    def _compute_discrepancy(self):
        for line in self:
            if line.is_counted:
                # Calculate discrepancy
                line.discrepancy_quantity = line.counted_quantity - line.expected_quantity
                
                # Determine if there's a discrepancy (allow small rounding differences)
                if abs(line.discrepancy_quantity) < 0.01:
                    line.has_discrepancy = False
                    line.discrepancy_type = 'none'
                    line.discrepancy_percentage = 0.0
                else:
                    line.has_discrepancy = True
                    if line.discrepancy_quantity > 0:
                        line.discrepancy_type = 'overage'
                    else:
                        line.discrepancy_type = 'shortage'
                    
                    # Calculate percentage
                    if line.expected_quantity != 0:
                        line.discrepancy_percentage = (line.discrepancy_quantity / line.expected_quantity) * 100
                    else:
                        line.discrepancy_percentage = 100.0 if line.counted_quantity > 0 else 0.0
            else:
                line.discrepancy_quantity = 0.0
                line.has_discrepancy = False
                line.discrepancy_type = 'none'
                line.discrepancy_percentage = 0.0

    def action_mark_counted(self):
        """Mark item as counted (colored-sticker equivalent)"""
        self.ensure_one()
        self.write({
            'is_counted': True,
            'counted_date': fields.Datetime.now(),
            'counted_by_id': self.env.user.id
        })

    def action_record_count(self):
        """Open wizard to record count"""
        self.ensure_one()
        return {
            'name': _('Record Count'),
            'type': 'ir.actions.act_window',
            'res_model': 'mesob.inventory.stock.taking.sheet.line',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': {'form_view_initial_mode': 'edit'}
        }

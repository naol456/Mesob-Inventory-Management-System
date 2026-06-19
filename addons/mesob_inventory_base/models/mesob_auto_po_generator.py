# -*- coding: utf-8 -*-
"""AUTO-022: Auto-PO Generation from Approved Lot.
AUTO-023: Reorder-Level Auto-Requisition.

Compliance: FR-PROC-026, FR-PROC-029, FR-SC-003
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class MesobAutoPOGenerator(models.AbstractModel):
    """AUTO-022 & AUTO-023: Automated PO and Requisition Generation."""
    
    _name = 'mesob.auto.po.generator'
    _description = 'Automated PO Generation Helper'
    
    @api.model
    def generate_po_from_lot(self, lot_id):
        """AUTO-022: Generate PO from approved APP lot.
        
        Args:
            lot_id: mesob.procurement.plan.lot ID
        
        Returns:
            PO record or False
        """
        lot = self.env['mesob.procurement.plan.lot'].browse(lot_id)
        
        if not lot.exists():
            return False
        
        # TODO: Implement when procurement.order model exists
        _logger.info(f"AUTO-022: PO generation requested for lot {lot.name}")
        return False
    
    @api.model
    def check_reorder_levels_and_generate_requisitions(self):
        """AUTO-023: Check all items at/below reorder level and auto-generate requisitions.
        
        Compliance: FR-SC-003, FR-PROC-029
        Scheduled to run daily via cron.
        """
        ReorderAlert = self.env['mesob.stock.reorder.alert']
        StockMixin = self.env['mesob.stock.movement.mixin']
        Item = self.env['mesob.inventory.item']
        
        items_needing_reorder = []
        
        # Get all items with reorder levels configured
        items = Item.search([('reorder_level', '>', 0)])
        
        for item in items:
            current_stock = StockMixin.get_current_stock_level(item.id)
            
            if current_stock <= item.reorder_level:
                # Check for existing open PO or requisition
                # TODO: Check open POs when model exists
                
                # Check for pending requisitions
                pending_req = self.env['mesob.inventory.requisition.line'].search([
                    ('item_id', '=', item.id),
                    ('requisition_id.state', 'in', ['draft', 'submitted', 'approved']),
                ], limit=1)
                
                if not pending_req:
                    items_needing_reorder.append({
                        'item': item,
                        'current_stock': current_stock,
                        'reorder_level': item.reorder_level,
                        'shortfall': item.reorder_level - current_stock,
                    })
        
        # Generate requisitions for items needing reorder
        requisitions_created = []
        for item_data in items_needing_reorder:
            item = item_data['item']
            
            # Calculate suggested order quantity
            suggested_qty = max(
                item.max_stock_level - item_data['current_stock'],
                item.reorder_quantity or (item.max_stock_level - item.reorder_level)
            ) if item.max_stock_level > 0 else item.reorder_quantity or 100
            
            # Create draft requisition
            requisition = self.env['mesob.inventory.requisition'].create({
                'issue_mode': 'replacement',
                'department': 'ministry_transport_logistics',  # TODO: Configure default
                'notes': f"AUTO-023: Auto-generated reorder requisition\n"
                        f"Current stock: {item_data['current_stock']}\n"
                        f"Reorder level: {item_data['reorder_level']}\n"
                        f"Suggested order: {suggested_qty}",
            })
            
            # Add line
            self.env['mesob.inventory.requisition.line'].create({
                'requisition_id': requisition.id,
                'item_id': item.id,
                'quantity_requested': suggested_qty,
                'justification': f"Stock level ({item_data['current_stock']}) at or below reorder point ({item_data['reorder_level']})",
            })
            
            requisitions_created.append(requisition)
            
            _logger.info(
                f"AUTO-023: Auto-generated requisition {requisition.name} for "
                f"item {item.name} (stock: {item_data['current_stock']}, "
                f"reorder: {item_data['reorder_level']})"
            )
        
        # Notify procurement officers
        if requisitions_created:
            procurement_users = self.env.ref(
                'mesob_inventory_base.group_mesob_procurement',
                raise_if_not_found=False
            )
            
            if procurement_users and procurement_users.users:
                # Send summary notification
                summary_html = f"""<div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px;">
                    <h3>🔔 AUTO-023: Reorder Alert</h3>
                    <p><strong>Generated Requisitions:</strong> {len(requisitions_created)}</p>
                    <p><strong>Date:</strong> {fields.Date.today()}</p>
                    <hr/>
                    <h4>Items Requiring Reorder:</h4>
                    <ul>
                """
                
                for req in requisitions_created[:10]:  # Show first 10
                    summary_html += f"<li>{req.name}: {len(req.line_ids)} items</li>"
                
                if len(requisitions_created) > 10:
                    summary_html += f"<li><em>...and {len(requisitions_created) - 10} more</em></li>"
                
                summary_html += """
                    </ul>
                    <p><em>Please review and process these auto-generated reorder requisitions.</em></p>
                </div>"""
                
                # Post to procurement channel or first requisition
                requisitions_created[0].message_post(
                    body=summary_html,
                    subject='AUTO-023: Reorder Requisitions Generated',
                    message_type='notification',
                    partner_ids=procurement_users.users.mapped('partner_id').ids
                )
        
        return {
            'items_checked': len(items),
            'items_needing_reorder': len(items_needing_reorder),
            'requisitions_created': len(requisitions_created),
            'requisition_ids': [r.id for r in requisitions_created],
        }


class MesobStockReorderAlert(models.Model):
    """Enhanced with AUTO-023 integration."""
    
    _inherit = 'mesob.stock.reorder.alert'
    
    auto_generated = fields.Boolean(
        string='Auto-Generated',
        default=False,
        readonly=True,
        help='AUTO-023: Indicates this was auto-generated by reorder system'
    )

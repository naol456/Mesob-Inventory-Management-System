# -*- coding: utf-8 -*-
"""AUTO-049: Real-Time Bin Card & Stock Record Card Updates.

Mixin model that provides automated stock movement recording functionality.
Any model that triggers stock movements can inherit this mixin to automatically
update Bin Cards and Stock Record Cards in real-time.

Triggers:
- Model 19 (Receiving) creation → Auto-debit Bin Card & Stock Record
- Model 22 (Issue Voucher) creation → Auto-credit Bin Card & Stock Record
- Stock adjustments → Auto-update both cards
- Transfers → Auto-update source and destination locations

Compliance:
- FR-RECARD-001: Bin Card maintenance
- FR-RECARD-002: Stock Record Card maintenance
- FR-VAL-001: FIFO valuation
- NFR-QUAL-001: Real-time accuracy
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class MesobStockMovementMixin(models.AbstractModel):
    """AUTO-049: Mixin for automated stock movement recording."""
    
    _name = 'mesob.stock.movement.mixin'
    _description = 'Stock Movement Automation Mixin'
    
    # Track if stock movements have been posted
    stock_movements_posted = fields.Boolean(
        string='Stock Movements Posted',
        default=False,
        readonly=True,
        help='AUTO-049: Indicates if Bin Card and Stock Record Card have been updated'
    )
    
    stock_movement_ids = fields.Many2many(
        'mesob.bin.card',
        string='Related Bin Card Entries',
        readonly=True,
        help='AUTO-049: Bin Card entries created by this document'
    )
    
    stock_record_ids = fields.Many2many(
        'mesob.stock.record.card',
        string='Related Stock Record Entries',
        readonly=True,
        help='AUTO-049: Stock Record Card entries created by this document'
    )
    
    def _prepare_bin_card_values(self, item, quantity, transaction_type, reference=None):
        """Prepare values for Bin Card entry creation.
        
        Args:
            item: mesob.inventory.item record
            quantity: float (positive for receipt, negative for issue)
            transaction_type: str ('receipt', 'issue', 'adjustment', 'transfer')
            reference: str (optional document reference)
        
        Returns:
            dict: Values for Bin Card creation
        """
        self.ensure_one()
        
        return {
            'major_classification_id': item.classification_id.id,
            'sub_classification_id': item.sub_classification_id.id,
            'location': 'Main Store',  # TODO: Make location configurable
            'date': fields.Date.today(),
            'transaction_type': transaction_type,
            'reference': reference or self.name if hasattr(self, 'name') else '',
            'description': f'Auto-posted from {self._description}: {reference or ""}',
            'quantity_received': quantity if transaction_type == 'receipt' else 0.0,
            'quantity_distributed': abs(quantity) if transaction_type == 'issue' else 0.0,
            'uom_id': item.uom_id.id,
            'received_by_id': self.env.user.id,
        }
    
    def _prepare_stock_record_values(self, item, quantity, transaction_type, unit_cost=0.0, reference=None):
        """Prepare values for Stock Record Card entry creation.
        
        Args:
            item: mesob.inventory.item record
            quantity: float (positive for receipt, negative for issue)
            transaction_type: str ('receipt', 'issue', 'adjustment', 'return')
            unit_cost: float (cost per unit for receipts)
            reference: str (optional document reference)
        
        Returns:
            dict: Values for Stock Record Card creation
        """
        self.ensure_one()
        
        return {
            'item_id': item.id,
            'date': fields.Date.today(),
            'transaction_type': transaction_type,
            'reference': reference or self.name if hasattr(self, 'name') else '',
            'description': f'Auto-posted from {self._description}: {reference or ""}',
            'quantity_in': quantity if transaction_type == 'receipt' else 0.0,
            'quantity_out': abs(quantity) if transaction_type == 'issue' else 0.0,
            'uom_id': item.uom_id.id,
            'unit_cost': unit_cost,
            'source_document': f'{self._name},{self.id}',
            'created_by_id': self.env.user.id,
        }
    
    def action_post_stock_movements(self, movements_data):
        """AUTO-049: Post stock movements to Bin Card and Stock Record Card.
        
        Args:
            movements_data: list of dicts with keys:
                - item_id: int (item ID)
                - quantity: float (positive for receipt, negative for issue)
                - transaction_type: str ('receipt', 'issue', 'adjustment', 'transfer')
                - unit_cost: float (optional, for receipts)
                - reference: str (optional)
        
        Returns:
            dict: Created bin card and stock record entries
        """
        self.ensure_one()
        
        if self.stock_movements_posted:
            raise UserError(
                _("Stock movements have already been posted for this document.\n"
                  "Cannot post movements twice to prevent duplicate entries.")
            )
        
        BinCard = self.env['mesob.bin.card']
        StockRecord = self.env['mesob.stock.record.card']
        Item = self.env['mesob.inventory.item']
        
        bin_cards_created = BinCard
        stock_records_created = StockRecord
        
        for movement in movements_data:
            item = Item.browse(movement['item_id'])
            
            if not item.exists():
                raise ValidationError(_(f"Item with ID {movement['item_id']} does not exist."))
            
            # Create Bin Card entry
            bin_card_vals = self._prepare_bin_card_values(
                item=item,
                quantity=movement['quantity'],
                transaction_type=movement['transaction_type'],
                reference=movement.get('reference')
            )
            bin_card = BinCard.create(bin_card_vals)
            bin_cards_created |= bin_card
            
            # Create Stock Record Card entry
            stock_record_vals = self._prepare_stock_record_values(
                item=item,
                quantity=movement['quantity'],
                transaction_type=movement['transaction_type'],
                unit_cost=movement.get('unit_cost', 0.0),
                reference=movement.get('reference')
            )
            stock_record = StockRecord.create(stock_record_vals)
            stock_records_created |= stock_record
            
            # AUTO-051: FIFO Layer Management
            if movement['transaction_type'] == 'receipt' and movement['quantity'] > 0:
                stock_record.action_create_fifo_layers()
            elif movement['transaction_type'] == 'issue' and movement['quantity'] < 0:
                stock_record.action_consume_fifo()
            
            _logger.info(
                f"AUTO-049: Stock movement posted - "
                f"Item: {item.name}, "
                f"Qty: {movement['quantity']}, "
                f"Type: {movement['transaction_type']}, "
                f"Doc: {self._name},{self.id}"
            )
        
        # Mark movements as posted
        self.write({
            'stock_movements_posted': True,
            'stock_movement_ids': [(6, 0, bin_cards_created.ids)],
            'stock_record_ids': [(6, 0, stock_records_created.ids)],
        })
        
        return {
            'bin_cards': bin_cards_created,
            'stock_records': stock_records_created,
        }
    
    def action_reverse_stock_movements(self):
        """Reverse posted stock movements (for cancellations/rejections)."""
        self.ensure_one()
        
        if not self.stock_movements_posted:
            raise UserError(_("No stock movements to reverse for this document."))
        
        # Create reversal entries
        reversal_data = []
        
        for stock_record in self.stock_record_ids:
            reversal_data.append({
                'item_id': stock_record.item_id.id,
                'quantity': -stock_record.quantity_in if stock_record.quantity_in > 0 else stock_record.quantity_out,
                'transaction_type': 'adjustment',
                'unit_cost': stock_record.unit_cost,
                'reference': f'REVERSAL: {stock_record.reference}',
            })
        
        # Post reversals
        self.action_post_stock_movements(reversal_data)
        
        _logger.info(f"AUTO-049: Stock movements reversed for {self._name},{self.id}")
    
    @api.model
    def get_current_stock_level(self, item_id, location='Main Store'):
        """AUTO-049: Get current stock level for an item from latest Bin Card.
        
        Args:
            item_id: int (item ID)
            location: str (storage location)
        
        Returns:
            float: Current stock balance
        """
        Item = self.env['mesob.inventory.item']
        item = Item.browse(item_id)
        
        if not item.exists():
            return 0.0
        
        # Get latest bin card entry for this sub-classification
        BinCard = self.env['mesob.bin.card']
        latest_entry = BinCard.search([
            ('sub_classification_id', '=', item.sub_classification_id.id),
            ('location', '=', location),
        ], order='date desc, id desc', limit=1)
        
        return latest_entry.balance if latest_entry else 0.0
    
    @api.model
    def get_item_valuation(self, item_id):
        """AUTO-049: Get current valuation for an item from Stock Record Card.
        
        Args:
            item_id: int (item ID)
        
        Returns:
            dict: {
                'quantity': float,
                'value': float,
                'average_cost': float
            }
        """
        StockRecord = self.env['mesob.stock.record.card']
        latest_record = StockRecord.search([
            ('item_id', '=', item_id),
        ], order='date desc, id desc', limit=1)
        
        if not latest_record:
            return {'quantity': 0.0, 'value': 0.0, 'average_cost': 0.0}
        
        return {
            'quantity': latest_record.quantity_balance,
            'value': latest_record.balance_value,
            'average_cost': latest_record.average_cost,
        }


class MesobStockMovementHelper(models.AbstractModel):
    """Helper methods for stock movement operations."""
    
    _name = 'mesob.stock.movement.helper'
    _description = 'Stock Movement Helper Methods'
    
    @api.model
    def check_stock_availability(self, item_id, required_quantity, location='Main Store'):
        """Check if sufficient stock is available for issue.
        
        Returns:
            dict: {
                'available': bool,
                'current_stock': float,
                'shortfall': float,
                'message': str
            }
        """
        current_stock = self.env['mesob.stock.movement.mixin'].get_current_stock_level(
            item_id, location
        )
        
        shortfall = max(0.0, required_quantity - current_stock)
        
        return {
            'available': current_stock >= required_quantity,
            'current_stock': current_stock,
            'shortfall': shortfall,
            'message': f"Stock available: {current_stock}, Required: {required_quantity}, Shortfall: {shortfall}" if shortfall > 0 else "Sufficient stock available"
        }
    
    @api.model
    def get_pending_requisitions_for_item(self, item_id):
        """Get pending requisitions for an item (for stock allocation planning).
        
        Returns:
            recordset: Pending requisition lines
        """
        RequisitionLine = self.env['mesob.inventory.requisition.line']
        return RequisitionLine.search([
            ('item_id', '=', item_id),
            ('requisition_id.state', 'in', ['draft', 'submitted', 'approved']),
        ])
    
    @api.model
    def get_expected_delivery_date(self, item_id):
        """Get expected delivery date from open PO for an item.
        
        Returns:
            date or None
        """
        # TODO: Implement when PO model is available
        return None

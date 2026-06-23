# -*- coding: utf-8 -*-
"""AUTO-051: FIFO Batch Auto-Tracking & Issue Costing.

Maintains FIFO batch queue per item for accurate stock valuation (FR-VAL-001).
On issue, system auto-consumes oldest batch first and computes weighted average
cost if issue spans multiple batches.
"""

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError, UserError
import logging

_logger = logging.getLogger(__name__)


class MesobStockFifoBatch(models.Model):
    """AUTO-051: FIFO Batch Tracking for Stock Valuation (FR-VAL-001).
    
    Each receipt creates a new batch with its landed cost.
    Issues consume from oldest batches first (FIFO principle).
    """
    
    _name = 'mesob.stock.fifo.batch'
    _description = 'FIFO Stock Batch'
    _order = 'receipt_date, id'
    
    # ── Batch Identification ───────────────────────────────────────
    name = fields.Char(
        string='Batch Reference',
        required=True,
        index=True,
        help='Unique batch identifier (e.g., Model 19 reference + line)'
    )
    
    item_id = fields.Many2one(
        'mesob.inventory.item',
        string='Item',
        required=True,
        index=True,
        ondelete='restrict',
        help='Stock item this batch belongs to'
    )
    
    # ── Receipt Information ────────────────────────────────────────
    receipt_date = fields.Date(
        string='Receipt Date',
        required=True,
        index=True,
        help='Date when batch was received (for FIFO ordering)'
    )
    
    source_document = fields.Char(
        string='Source Document',
        required=True,
        help='Model 19 reference or other receipt document'
    )
    
    model19_id = fields.Many2one(
        'mesob.inventory.model19',
        string='Model 19 Receipt',
        ondelete='set null',
        help='Link to Model 19 if available'
    )
    
    # ── Quantity Tracking ──────────────────────────────────────────
    quantity_received = fields.Float(
        string='Quantity Received',
        required=True,
        digits='Product Unit of Measure',
        help='Original quantity received in this batch'
    )
    
    quantity_remaining = fields.Float(
        string='Quantity Remaining',
        required=True,
        digits='Product Unit of Measure',
        help='Current quantity available in this batch (consumed via FIFO)'
    )
    
    quantity_consumed = fields.Float(
        string='Quantity Consumed',
        compute='_compute_quantity_consumed',
        store=True,
        digits='Product Unit of Measure',
        help='Total quantity issued from this batch'
    )
    
    # ── Cost Information ───────────────────────────────────────────
    unit_cost = fields.Monetary(
        string='Unit Cost (Landed)',
        required=True,
        currency_field='currency_id',
        help='AUTO-052: Landed cost per unit (includes freight, insurance, duties)'
    )
    
    total_cost = fields.Monetary(
        string='Total Batch Cost',
        compute='_compute_total_cost',
        store=True,
        currency_field='currency_id',
        help='Total value of remaining quantity in batch'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
        required=True
    )
    
    # ── Status ─────────────────────────────────────────────────────
    state = fields.Selection([
        ('active', 'Active'),
        ('depleted', 'Depleted'),
        ('cancelled', 'Cancelled'),
    ], string='Status', default='active', required=True, index=True)
    
    # ── Issue History ──────────────────────────────────────────────
    consumption_ids = fields.One2many(
        'mesob.stock.fifo.consumption',
        'batch_id',
        string='Consumption History',
        help='History of issues from this batch'
    )
    
    # ── Computed Fields ────────────────────────────────────────────
    
    @api.depends('quantity_received', 'quantity_remaining')
    def _compute_quantity_consumed(self):
        """Calculate consumed quantity."""
        for batch in self:
            batch.quantity_consumed = batch.quantity_received - batch.quantity_remaining
    
    @api.depends('quantity_remaining', 'unit_cost')
    def _compute_total_cost(self):
        """Calculate total value of remaining quantity."""
        for batch in self:
            batch.total_cost = batch.quantity_remaining * batch.unit_cost
    
    # ── Constraints ────────────────────────────────────────────────
    
    @api.constrains('quantity_remaining', 'quantity_received')
    def _check_quantity_remaining(self):
        """Ensure remaining quantity doesn't exceed received quantity."""
        for batch in self:
            if batch.quantity_remaining < 0:
                raise ValidationError(
                    f"Batch {batch.name}: Remaining quantity cannot be negative. "
                    f"Remaining: {batch.quantity_remaining}"
                )
            if batch.quantity_remaining > batch.quantity_received:
                raise ValidationError(
                    f"Batch {batch.name}: Remaining quantity ({batch.quantity_remaining}) "
                    f"cannot exceed received quantity ({batch.quantity_received})"
                )
    
    # ── FIFO Consumption Logic ────────────────────────────────────
    
    @api.model
    def consume_fifo(self, item_id, quantity_needed, issue_reference):
        """AUTO-051: Consume quantity from oldest batches first (FIFO).
        
        Args:
            item_id: ID of item to consume
            quantity_needed: Total quantity to issue
            issue_reference: Model 22 or other issue document reference
            
        Returns:
            dict: {
                'consumed': list of dicts with batch consumption details,
                'total_cost': weighted average cost of issued quantity,
                'unit_cost': weighted average unit cost
            }
        """
        if quantity_needed <= 0:
            raise UserError("Quantity to consume must be positive.")
        
        # Get active batches for this item, ordered by receipt date (FIFO)
        batches = self.search([
            ('item_id', '=', item_id),
            ('state', '=', 'active'),
            ('quantity_remaining', '>', 0)
        ], order='receipt_date, id')
        
        if not batches:
            raise UserError(
                f"AUTO-051: No FIFO batches available for item ID {item_id}. "
                "Cannot perform FIFO costing."
            )
        
        # Check if sufficient stock available
        total_available = sum(batches.mapped('quantity_remaining'))
        if total_available < quantity_needed:
            raise UserError(
                f"AUTO-051: Insufficient stock for FIFO consumption. "
                f"Requested: {quantity_needed}, Available: {total_available}"
            )
        
        # Consume from batches (FIFO)
        consumed_details = []
        remaining_to_consume = quantity_needed
        total_cost = 0.0
        
        Consumption = self.env['mesob.stock.fifo.consumption']
        
        for batch in batches:
            if remaining_to_consume <= 0:
                break
            
            # Determine how much to consume from this batch
            consumed_qty = min(batch.quantity_remaining, remaining_to_consume)
            consumed_cost = consumed_qty * batch.unit_cost
            
            # Record consumption
            consumption = Consumption.create({
                'batch_id': batch.id,
                'issue_reference': issue_reference,
                'quantity_consumed': consumed_qty,
                'unit_cost': batch.unit_cost,
                'total_cost': consumed_cost,
            })
            
            # Update batch remaining quantity
            batch.write({
                'quantity_remaining': batch.quantity_remaining - consumed_qty
            })
            
            # Mark batch as depleted if fully consumed
            if batch.quantity_remaining == 0:
                batch.state = 'depleted'
            
            # Track consumption details
            consumed_details.append({
                'batch_id': batch.id,
                'batch_name': batch.name,
                'receipt_date': batch.receipt_date,
                'quantity': consumed_qty,
                'unit_cost': batch.unit_cost,
                'total_cost': consumed_cost,
            })
            
            total_cost += consumed_cost
            remaining_to_consume -= consumed_qty
            
            _logger.info(
                f"AUTO-051: Consumed {consumed_qty} from batch {batch.name} "
                f"(Receipt: {batch.receipt_date}, Unit Cost: ETB {batch.unit_cost:,.2f})"
            )
        
        # Calculate weighted average unit cost
        weighted_avg_unit_cost = total_cost / quantity_needed if quantity_needed > 0 else 0.0
        
        _logger.info(
            f"AUTO-051: FIFO consumption complete for item ID {item_id} - "
            f"Qty: {quantity_needed}, Total Cost: ETB {total_cost:,.2f}, "
            f"Weighted Avg Unit Cost: ETB {weighted_avg_unit_cost:,.2f}, "
            f"Batches consumed: {len(consumed_details)}"
        )
        
        return {
            'consumed': consumed_details,
            'total_cost': total_cost,
            'unit_cost': weighted_avg_unit_cost,
        }
    
    @api.model
    def create_batch(self, item_id, receipt_date, quantity, unit_cost, source_document, model19_id=None):
        """AUTO-051: Create new FIFO batch for received goods.
        
        Called automatically when Model 19 is confirmed.
        """
        batch_name = f"{source_document}/BATCH/{self.env['ir.sequence'].next_by_code('mesob.fifo.batch') or '001'}"
        
        batch = self.create({
            'name': batch_name,
            'item_id': item_id,
            'receipt_date': receipt_date,
            'source_document': source_document,
            'model19_id': model19_id,
            'quantity_received': quantity,
            'quantity_remaining': quantity,
            'unit_cost': unit_cost,
            'state': 'active',
        })
        
        _logger.info(
            f"AUTO-051: Created FIFO batch {batch_name} - "
            f"Item ID: {item_id}, Qty: {quantity}, Unit Cost: ETB {unit_cost:,.2f}"
        )
        
        return batch


class MesobStockFifoConsumption(models.Model):
    """AUTO-051: FIFO Consumption History.
    
    Tracks each issue transaction and which batch it consumed from.
    """
    
    _name = 'mesob.stock.fifo.consumption'
    _description = 'FIFO Batch Consumption Record'
    _order = 'consumption_date desc, id desc'
    
    batch_id = fields.Many2one(
        'mesob.stock.fifo.batch',
        string='FIFO Batch',
        required=True,
        ondelete='cascade',
        index=True
    )
    
    item_id = fields.Many2one(
        'mesob.inventory.item',
        related='batch_id.item_id',
        string='Item',
        store=True,
        readonly=True
    )
    
    consumption_date = fields.Datetime(
        string='Consumption Date',
        default=fields.Datetime.now,
        required=True
    )
    
    issue_reference = fields.Char(
        string='Issue Reference',
        required=True,
        help='Model 22 or other issue document reference'
    )
    
    quantity_consumed = fields.Float(
        string='Quantity Consumed',
        required=True,
        digits='Product Unit of Measure'
    )
    
    unit_cost = fields.Monetary(
        string='Unit Cost',
        required=True,
        currency_field='currency_id',
        help='Unit cost from the batch at time of consumption'
    )
    
    total_cost = fields.Monetary(
        string='Total Cost',
        required=True,
        currency_field='currency_id',
        help='Total cost of this consumption (qty × unit cost)'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
        required=True
    )

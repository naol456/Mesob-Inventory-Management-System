from odoo import api, fields, models, tools


class MesobInventoryStockValuation(models.Model):
    """Stock Valuation Report by Classification.
    
    Provides FIFO-based stock valuation aggregated by major classification
    for accounting reconciliation and reporting (SRS 4.6 FR-VAL-004).
    """
    
    _name = "mesob.inventory.stock.valuation"
    _description = "Stock Valuation by Classification"
    _auto = False  # This is a SQL view, not a regular table
    _order = "classification_id, item_id"
    
    # ── Dimensions ──────────────────────────────────────────────────
    
    classification_id = fields.Many2one(
        "mesob.inventory.major.classification",
        string="Major Classification",
        readonly=True,
    )
    
    classification_code = fields.Char(
        string="Classification Code",
        readonly=True,
    )
    
    item_id = fields.Many2one(
        "mesob.inventory.item",
        string="Item",
        readonly=True,
    )
    
    item_code = fields.Char(
        string="Item Code",
        readonly=True,
    )
    
    item_name = fields.Char(
        string="Item Name",
        readonly=True,
    )
    
    # ── Measures ────────────────────────────────────────────────────
    
    total_quantity = fields.Float(
        string="Total Quantity",
        readonly=True,
        help="Total quantity in stock (from FIFO layers)",
    )
    
    total_value = fields.Monetary(
        string="Total Value",
        readonly=True,
        currency_field='currency_id',
        help="Total value using FIFO costing",
    )
    
    average_unit_cost = fields.Monetary(
        string="Average Unit Cost",
        readonly=True,
        currency_field='currency_id',
        help="Weighted average unit cost",
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        readonly=True,
    )
    
    has_estimated_cost = fields.Boolean(
        string="Has Estimated Cost",
        readonly=True,
        help="True if any FIFO layer has estimated (not actual) cost",
    )
    
    # ── SQL View Definition ─────────────────────────────────────────
    
    def init(self):
        """Create SQL view for stock valuation reporting."""
        tools.drop_view_if_exists(self.env.cr, self._table)
        
        query = """
            CREATE OR REPLACE VIEW mesob_inventory_stock_valuation AS (
                SELECT
                    ROW_NUMBER() OVER (ORDER BY item.classification_id, item.id) AS id,
                    item.classification_id AS classification_id,
                    class.code AS classification_code,
                    item.id AS item_id,
                    item.item_code AS item_code,
                    item.name AS item_name,
                    COALESCE(SUM(fifo.remaining_quantity), 0) AS total_quantity,
                    COALESCE(SUM(fifo.remaining_quantity * fifo.unit_price), 0) AS total_value,
                    CASE 
                        WHEN COALESCE(SUM(fifo.remaining_quantity), 0) > 0 
                        THEN COALESCE(SUM(fifo.remaining_quantity * fifo.unit_price), 0) / 
                             COALESCE(SUM(fifo.remaining_quantity), 1)
                        ELSE 0
                    END AS average_unit_cost,
                    item.currency_id AS currency_id,
                    COALESCE(MAX(CASE WHEN fifo.is_estimated_cost THEN 1 ELSE 0 END), 0)::boolean AS has_estimated_cost
                FROM
                    mesob_inventory_item item
                    LEFT JOIN mesob_inventory_major_classification class 
                        ON item.classification_id = class.id
                    LEFT JOIN mesob_inventory_fifo_layer fifo 
                        ON item.id = fifo.item_id 
                        AND fifo.remaining_quantity > 0
                GROUP BY
                    item.id,
                    item.classification_id,
                    class.code,
                    item.item_code,
                    item.name,
                    item.currency_id
            )
        """
        self.env.cr.execute(query)


class MesobInventoryStockValuationSummary(models.Model):
    """Stock Valuation Summary by Classification.
    
    Aggregated view for control account reconciliation (SRS 4.6 FR-VAL-004).
    """
    
    _name = "mesob.inventory.stock.valuation.summary"
    _description = "Stock Valuation Summary by Classification"
    _auto = False
    _order = "classification_code"
    
    classification_id = fields.Many2one(
        "mesob.inventory.major.classification",
        string="Major Classification",
        readonly=True,
    )
    
    classification_code = fields.Char(
        string="Classification Code",
        readonly=True,
    )
    
    classification_name = fields.Char(
        string="Classification Name",
        readonly=True,
    )
    
    item_count = fields.Integer(
        string="Number of Items",
        readonly=True,
    )
    
    total_quantity = fields.Float(
        string="Total Quantity",
        readonly=True,
    )
    
    total_value = fields.Monetary(
        string="Total Value",
        readonly=True,
        currency_field='currency_id',
        help="Control account value for this classification",
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        readonly=True,
    )
    
    def init(self):
        """Create SQL view for classification-level valuation summary."""
        tools.drop_view_if_exists(self.env.cr, self._table)
        
        query = """
            CREATE OR REPLACE VIEW mesob_inventory_stock_valuation_summary AS (
                SELECT
                    class.id AS id,
                    class.id AS classification_id,
                    class.code AS classification_code,
                    class.name AS classification_name,
                    COUNT(DISTINCT item.id) AS item_count,
                    COALESCE(SUM(fifo.remaining_quantity), 0) AS total_quantity,
                    COALESCE(SUM(fifo.remaining_quantity * fifo.unit_price), 0) AS total_value,
                    company.currency_id AS currency_id
                FROM
                    mesob_inventory_major_classification class
                    LEFT JOIN mesob_inventory_item item 
                        ON class.id = item.classification_id
                    LEFT JOIN mesob_inventory_fifo_layer fifo 
                        ON item.id = fifo.item_id 
                        AND fifo.remaining_quantity > 0
                    CROSS JOIN res_company company
                WHERE
                    company.id = (SELECT id FROM res_company LIMIT 1)
                GROUP BY
                    class.id,
                    class.code,
                    class.name,
                    company.currency_id
            )
        """
        self.env.cr.execute(query)

# models/mesob_stock_taking.py
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


# ─────────────────────────────────────────────
# 4.8  Stock Taking & Discrepancy Handling
# ─────────────────────────────────────────────

class MesobStockTaking(models.Model):
    _name = 'mesob.stock.taking'
    _description = 'Mesob Stock Taking'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'

    name = fields.Char(string='Reference', required=True, copy=False,
                       readonly=True, default=lambda self: _('New'))
    date = fields.Date(string='Taking Date', required=True,
                       default=fields.Date.today)
    responsible_id = fields.Many2one('res.users', string='Responsible (PAO)',
                                     required=True,
                                     default=lambda self: self.env.user)
    state = fields.Selection([
        ('draft',       'Draft'),
        ('in_progress', 'In Progress'),
        ('done',        'Done'),
        ('cancel',      'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    taking_type = fields.Selection([
        ('regular',  'Regular Stock Taking'),
        ('handover', 'Handover / Takeover'),
    ], string='Type', default='regular', required=True)

    # FR-ST-001 – PAO instructions / training recorded
    instructions = fields.Text(string='PAO Instructions')
    training_done = fields.Boolean(string='Pre-stocktaking Training Performed')

    # FR-ST-003 – scheduling
    start_time = fields.Datetime(string='Planned Start')
    end_time   = fields.Datetime(string='Planned End')

    note = fields.Text(string='Notes')
    line_ids = fields.One2many('mesob.stock.taking.line', 'taking_id',
                               string='Stock Taking Lines')

    # FR-ST-009 – team members (storekeepers excluded) and guides
    team_ids  = fields.Many2many('res.users', 'mesob_taking_team_rel',
                                 'taking_id', 'user_id',
                                 string='Stock Taking Team')
    guide_ids = fields.Many2many('res.users', 'mesob_taking_guide_rel',
                                 'taking_id', 'user_id',
                                 string='Storekeeper Guides / Witnesses')

    # ── computed summary ──────────────────────
    total_lines       = fields.Integer(compute='_compute_summary', store=True)
    discrepancy_count = fields.Integer(compute='_compute_summary', store=True)

    @api.depends('line_ids', 'line_ids.difference')
    def _compute_summary(self):
        for rec in self:
            rec.total_lines = len(rec.line_ids)
            rec.discrepancy_count = len(
                rec.line_ids.filtered(lambda l: l.difference != 0)
            )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('mesob.stock.taking')
                    or _('New')
                )
        return super().create(vals_list)

    def action_start_taking(self):
        # FR-ST-009 – enforce storekeeper exclusion from team
        for rec in self:
            if rec.team_ids:
                storekeeper_group = self.env.ref(
                    'stock.group_stock_user', raise_if_not_found=False)
                if storekeeper_group:
                    # get users in the storekeeper group directly from the group
                    storekeeper_users = storekeeper_group.users
                    # PAO (responsible) is allowed — only block pure storekeepers
                    blocked = rec.team_ids & storekeeper_users
                    blocked = blocked.filtered(
                        lambda u: u != rec.responsible_id
                    )
                    if blocked:
                        names = ', '.join(blocked.mapped('name'))
                        raise ValidationError(_(
                            'FR-ST-009: The following users are Storekeepers '
                            'and cannot be Stock Taking team members: %s\n\n'
                            'Move them to "Storekeeper Guides / Witnesses" instead.'
                        ) % names)
        self.write({'state': 'in_progress'})

    def action_complete(self):
        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancel'})


class MesobStockTakingLine(models.Model):
    _name = 'mesob.stock.taking.line'
    _description = 'Stock Taking Line'

    taking_id    = fields.Many2one('mesob.stock.taking', ondelete='cascade')
    product_id   = fields.Many2one('product.product', string='Product',
                                   required=True)
    location_id  = fields.Many2one('stock.location', string='Location')
    uom_id       = fields.Many2one('uom.uom', string='UoM',
                                   related='product_id.uom_id', store=True)

    theoretical_qty = fields.Float(string='Theoretical Qty',
                                   digits='Product Unit of Measure',
                                   readonly=True)
    counted_qty     = fields.Float(string='Counted Qty',
                                   digits='Product Unit of Measure')
    difference      = fields.Float(string='Difference',
                                   compute='_compute_difference', store=True,
                                   digits='Product Unit of Measure')

    # FR-ST-005 – counted marker
    is_counted          = fields.Boolean(string='Counted (Sticker)')
    discrepancy_reason  = fields.Text(string='Discrepancy Reason / Action')

    @api.depends('theoretical_qty', 'counted_qty')
    def _compute_difference(self):
        for line in self:
            line.difference = line.counted_qty - line.theoretical_qty

    @api.onchange('product_id', 'location_id')
    def _onchange_product_location(self):
        """Auto-fill theoretical_qty from current stock on hand."""
        for line in self:
            if line.product_id:
                domain = [
                    ('product_id', '=', line.product_id.id),
                    ('location_id.usage', '=', 'internal'),
                ]
                if line.location_id:
                    domain = [
                        ('product_id', '=', line.product_id.id),
                        ('location_id', '=', line.location_id.id),
                    ]
                quants = self.env['stock.quant'].search(domain)
                line.theoretical_qty = sum(quants.mapped('quantity'))
            else:
                line.theoretical_qty = 0.0


# ─────────────────────────────────────────────
# 4.9  Stocks Handover / Takeover
# ─────────────────────────────────────────────

class MesobStockHandover(models.Model):
    _name = 'mesob.stock.handover'
    _description = 'Stock Handover / Takeover'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name desc'

    name = fields.Char(string='Certificate No.', required=True, copy=False,
                       readonly=True, default=lambda self: _('New'))

    # FR-HO-001 – trigger reason
    trigger_reason = fields.Selection([
        ('leave',      'Leave / Retirement'),
        ('travel',     'Duty Travel'),
        ('training',   'Training Outside Station'),
        ('promotion',  'Promotion'),
        ('transfer',   'Transfer'),
        ('medical',    'Medical Treatment'),
        ('other',      'Other'),
    ], string='Trigger Reason', required=True)

    date = fields.Date(string='Handover Date', required=True,
                       default=fields.Date.today)

    # FR-HO-002 – outgoing / incoming / witness
    outgoing_storekeeper_id = fields.Many2one(
        'res.users', string='Outgoing Storekeeper', required=True)
    incoming_storekeeper_id = fields.Many2one(
        'res.users', string='Incoming Storekeeper', required=True)
    witness_id = fields.Many2one(
        'res.users', string='Competent Witness', required=True)
    pao_id = fields.Many2one(
        'res.users', string='PAO', required=True,
        default=lambda self: self.env.user)

    state = fields.Selection([
        ('draft',    'Draft'),
        ('in_progress', 'In Progress'),
        ('certified', 'Certified'),
        ('cancel',   'Cancelled'),
    ], string='Status', default='draft', tracking=True)

    # linked stock taking
    stock_taking_id = fields.Many2one(
        'mesob.stock.taking', string='Stock Taking Sheet',
        domain=[('taking_type', '=', 'handover')])

    note = fields.Text(string='Notes')

    # FR-HO-003 – copy distribution tracking
    pao_copy_sent         = fields.Boolean(string='Original sent to PAO')
    incoming_copy_sent    = fields.Boolean(string='Duplicate sent to Incoming SK')
    outgoing_copy_sent    = fields.Boolean(string='Triplicate sent to Outgoing SK')

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = (
                    self.env['ir.sequence'].next_by_code('mesob.stock.handover')
                    or _('New')
                )
        return super().create(vals_list)

    @api.constrains('outgoing_storekeeper_id', 'incoming_storekeeper_id',
                    'witness_id')
    def _check_distinct_users(self):
        for rec in self:
            if rec.outgoing_storekeeper_id == rec.incoming_storekeeper_id:
                raise ValidationError(
                    _('Outgoing and Incoming Storekeeper must be different people.')
                )

    def action_start(self):
        self.write({'state': 'in_progress'})

    def action_certify(self):
        # FR-HO-002 – require stock taking to be done
        if self.stock_taking_id and self.stock_taking_id.state != 'done':
            raise ValidationError(
                _('The linked Stock Taking must be completed before certifying.')
            )
        self.write({'state': 'certified'})

    def action_cancel(self):
        self.write({'state': 'cancel'})


# ─────────────────────────────────────────────
# 4.10  Stock Control (Replenishment & Levels)
# ─────────────────────────────────────────────

class MesobStockControl(models.Model):
    _name = 'mesob.stock.control'
    _description = 'Stock Control Levels'
    _inherit = ['mail.thread']

    product_id  = fields.Many2one('product.product', string='Product',
                                  required=True, index=True)
    location_id = fields.Many2one('stock.location', string='Location')

    # FR-SC-001 – control levels
    min_qty      = fields.Float(string='Minimum Qty')
    reorder_qty  = fields.Float(string='Reorder Level')
    hastening_qty = fields.Float(string='Hastening Level')
    max_qty      = fields.Float(string='Maximum Qty')
    safety_stock = fields.Float(string='Safety Stock')

    # FR-SC-002 – lead times
    admin_lead_time     = fields.Integer(string='Admin Lead Time (days)')
    supplier_lead_time  = fields.Integer(string='Supplier Lead Time (days)')
    total_lead_time     = fields.Integer(string='Total Lead Time (days)',
                                         compute='_compute_lead_time', store=True)

    # FR-SC-005 – ABC classification
    abc_class = fields.Selection([
        ('a', 'A – High Value'),
        ('b', 'B – Medium Value'),
        ('c', 'C – Low Value'),
    ], string='ABC Class')

    # FR-SC-004 – last review
    last_review_date = fields.Date(string='Last Review Date')
    next_review_date = fields.Date(string='Next Review Date')
    review_frequency = fields.Selection([
        ('weekly',    'Weekly'),
        ('monthly',   'Monthly'),
        ('quarterly', 'Quarterly'),
    ], string='Review Frequency', default='monthly')

    # computed current stock
    qty_on_hand = fields.Float(string='Qty On Hand',
                               compute='_compute_qty_on_hand')
    alert_level = fields.Selection([
        ('ok',       'OK'),
        ('reorder',  'Reorder Required'),
        ('hastening','Hastening Required'),
        ('critical', 'Below Minimum'),
    ], string='Alert', compute='_compute_alert_level', store=True)

    note = fields.Text(string='Notes')

    @api.depends('admin_lead_time', 'supplier_lead_time')
    def _compute_lead_time(self):
        for rec in self:
            rec.total_lead_time = (rec.admin_lead_time or 0) + (
                rec.supplier_lead_time or 0)

    def _compute_qty_on_hand(self):
        for rec in self:
            domain = [('product_id', '=', rec.product_id.id),
                      ('state', '=', 'done')]
            if rec.location_id:
                domain += [('location_dest_id', '=', rec.location_id.id)]
            rec.qty_on_hand = rec.product_id.qty_available if rec.product_id else 0.0

    @api.depends('qty_on_hand', 'min_qty', 'reorder_qty', 'hastening_qty')
    def _compute_alert_level(self):
        for rec in self:
            qty = rec.product_id.qty_available if rec.product_id else 0.0
            if qty <= rec.min_qty:
                rec.alert_level = 'critical'
            elif qty <= rec.hastening_qty:
                rec.alert_level = 'hastening'
            elif qty <= rec.reorder_qty:
                rec.alert_level = 'reorder'
            else:
                rec.alert_level = 'ok'


# ─────────────────────────────────────────────
# 4.7  Reporting – Discrepancy & Dormant
# ─────────────────────────────────────────────

class MesobStockReport(models.Model):
    """Read-only reporting model — aggregates stock taking discrepancies."""
    _name = 'mesob.stock.report'
    _description = 'Stock Taking Report'
    _auto = False          # no DB table; backed by a SQL view
    _order = 'taking_date desc'

    taking_id    = fields.Many2one('mesob.stock.taking', string='Stock Taking',
                                   readonly=True)
    taking_date  = fields.Date(string='Date', readonly=True)
    taking_name  = fields.Char(string='Reference', readonly=True)
    taking_state = fields.Char(string='Status', readonly=True)
    taking_type  = fields.Char(string='Type', readonly=True)
    product_id   = fields.Many2one('product.product', string='Product',
                                   readonly=True)
    location_id  = fields.Many2one('stock.location', string='Location',
                                   readonly=True)
    theoretical_qty = fields.Float(string='Theoretical Qty', readonly=True)
    counted_qty     = fields.Float(string='Counted Qty', readonly=True)
    difference      = fields.Float(string='Difference', readonly=True)
    discrepancy_reason = fields.Text(string='Reason', readonly=True)

    def init(self):
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW mesob_stock_report AS (
                SELECT
                    l.id                    AS id,
                    st.id                   AS taking_id,
                    st.date                 AS taking_date,
                    st.name                 AS taking_name,
                    st.state                AS taking_state,
                    st.taking_type          AS taking_type,
                    l.product_id            AS product_id,
                    l.location_id           AS location_id,
                    l.theoretical_qty       AS theoretical_qty,
                    l.counted_qty           AS counted_qty,
                    l.difference            AS difference,
                    l.discrepancy_reason    AS discrepancy_reason
                FROM mesob_stock_taking_line l
                JOIN mesob_stock_taking st ON st.id = l.taking_id
            )
        """)

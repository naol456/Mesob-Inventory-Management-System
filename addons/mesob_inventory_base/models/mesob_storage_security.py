from odoo import api, fields, models
from odoo.exceptions import ValidationError
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)


class MesobStoragePlan(models.Model):
    """Storage Organization and Layout Artifact - FR-STOR-001/002.

    Supports labeling of stocks, shelves, and documenting physical layout plan.
    """

    _name = "mesob.storage.plan"
    _description = "Warehouse Storage Plan"
    _order = "id desc"

    name = fields.Char(string="Storage Plan / Layout Title", required=True)
    description = fields.Text(string="Layout Description")
    aisles = fields.Char(string="Aisles Configuration", help="Aisles mapping, e.g. Aisle A-H")
    gates_count = fields.Integer(string="Number of Gates/Exits", default=2)
    layout_file = fields.Binary(string="Layout Document/Plan", help="Physical schematic or floor plan document.")
    state = fields.Selection(
        [("draft", "Draft"), ("approved", "Approved by PAO")],
        string="Status",
        default="draft",
        required=True,
    )
    
    # AUTO-068: Bin Location Tracking
    bin_location_ids = fields.One2many(
        "mesob.storage.bin.location",
        "storage_plan_id",
        string="Bin Locations",
        help="AUTO-068: Individual bin/shelf locations within this storage plan"
    )
    
    total_bins = fields.Integer(
        string="Total Bins",
        compute="_compute_bin_stats",
        help="AUTO-068: Total bin locations defined"
    )
    
    occupied_bins = fields.Integer(
        string="Occupied Bins",
        compute="_compute_bin_stats",
        help="AUTO-068: Bins with items assigned"
    )
    
    occupancy_percentage = fields.Float(
        string="Occupancy %",
        compute="_compute_bin_stats",
        help="AUTO-068: Percentage of bins with items"
    )
    
    @api.depends('bin_location_ids', 'bin_location_ids.item_ids')
    def _compute_bin_stats(self):
        """AUTO-068: Compute bin occupation statistics"""
        for rec in self:
            rec.total_bins = len(rec.bin_location_ids)
            rec.occupied_bins = len(rec.bin_location_ids.filtered(lambda b: b.item_ids))
            if rec.total_bins > 0:
                rec.occupancy_percentage = (rec.occupied_bins / rec.total_bins) * 100
            else:
                rec.occupancy_percentage = 0.0

    def action_approve(self):
        for rec in self:
            rec.state = "approved"


class MesobStorageBinLocation(models.Model):
    """AUTO-068: Bin/Shelf Location Tracking within Storage Plans - FR-STOR-002.
    
    Enables digital warehouse mapping, optimal bin assignment, and pick list generation.
    Each bin can hold multiple items with capacity tracking.
    """
    
    _name = "mesob.storage.bin.location"
    _description = "Storage Bin / Shelf Location"
    _order = "aisle, shelf, level"
    
    name = fields.Char(
        string="Bin Code",
        required=True,
        help="AUTO-068: Unique bin identifier (e.g., A-01-3 = Aisle A, Shelf 1, Level 3)"
    )
    
    storage_plan_id = fields.Many2one(
        "mesob.storage.plan",
        string="Storage Plan",
        required=True,
        ondelete="cascade",
        help="Parent storage plan"
    )
    
    aisle = fields.Char(
        string="Aisle",
        required=True,
        help="Warehouse aisle (e.g., A, B, C)"
    )
    
    shelf = fields.Char(
        string="Shelf",
        required=True,
        help="Shelf number within aisle (e.g., 01, 02, 03)"
    )
    
    level = fields.Char(
        string="Level",
        help="Vertical level on shelf (e.g., 1=ground, 2=middle, 3=top)"
    )
    
    item_ids = fields.Many2many(
        "mesob.inventory.item",
        "mesob_bin_item_rel",
        "bin_id",
        "item_id",
        string="Items Stored",
        help="AUTO-068: Items assigned to this bin location"
    )
    
    capacity_cubic_meters = fields.Float(
        string="Capacity (m³)",
        help="Total storage capacity of this bin in cubic meters"
    )
    
    occupied_capacity = fields.Float(
        string="Occupied (m³)",
        compute="_compute_occupied_capacity",
        help="AUTO-068: Space occupied by current items"
    )
    
    available_capacity = fields.Float(
        string="Available (m³)",
        compute="_compute_occupied_capacity",
        help="AUTO-068: Remaining available space"
    )
    
    capacity_percentage = fields.Float(
        string="Occupancy %",
        compute="_compute_occupied_capacity",
        help="AUTO-068: Percentage of capacity used"
    )
    
    zone = fields.Selection([
        ('receiving', 'Receiving Zone'),
        ('storage', 'Storage Zone'),
        ('picking', 'Picking/Issue Zone'),
        ('quarantine', 'Quarantine Zone'),
    ], string="Zone", default='storage',
       help="AUTO-068: Functional zone for optimal placement")
    
    is_fast_moving = fields.Boolean(
        string="Fast-Moving Area",
        help="AUTO-068: Designate for high-velocity items (near issue area)"
    )
    
    notes = fields.Text(string="Location Notes")
    
    @api.depends('item_ids', 'capacity_cubic_meters')
    def _compute_occupied_capacity(self):
        """AUTO-068: Calculate space utilization"""
        for rec in self:
            # Simplified: assume 0.01 m³ per unit (configurable per item in future)
            # Get current stock for all items in this bin
            total_qty = 0.0
            for item in rec.item_ids:
                # Use current_stock computed field instead of quantity_on_hand
                total_qty += item.current_stock
            
            rec.occupied_capacity = total_qty * 0.01  # Placeholder calculation
            rec.available_capacity = rec.capacity_cubic_meters - rec.occupied_capacity
            
            if rec.capacity_cubic_meters > 0:
                rec.capacity_percentage = (rec.occupied_capacity / rec.capacity_cubic_meters) * 100
            else:
                rec.capacity_percentage = 0.0
    
    def get_optimal_bin_for_item(self, item):
        """AUTO-068: Suggest optimal bin location for incoming item.
        
        Criteria:
        1. Group by classification (FR-STOR-001)
        2. Available capacity
        3. Fast-moving items near picking zone
        4. FIFO accessibility
        
        Args:
            item: mesob.inventory.item record
            
        Returns:
            mesob.storage.bin.location record or False
        """
        # Get item's classification for grouping
        classification = item.sub_classification_id or item.classification_id
        
        # Check if item is fast-moving (issued frequently)
        usage_mixin = self.env['mesob.stock.movement.mixin']
        issue_count = len(usage_mixin._get_issue_history(item.id, months=3))
        is_fast = issue_count > 10  # More than 10 issues in 3 months = fast-moving
        
        # Search for optimal bin
        domain = [('available_capacity', '>', 0)]
        if is_fast:
            domain.append(('is_fast_moving', '=', True))
        
        bins = self.search(domain, order='available_capacity desc')
        
        # Prefer bins with similar classification items (grouping)
        for bin_loc in bins:
            if any(i.sub_classification_id == classification or i.classification_id == classification 
                   for i in bin_loc.item_ids):
                return bin_loc
        
        # Fallback: return bin with most available space
        return bins[0] if bins else False
    
    def generate_pick_list(self, item_ids):
        """AUTO-068: Generate pick list showing bin locations for item picking.
        
        Displays bin locations to storekeeper for efficient picking during issue.
        
        Args:
            item_ids: List of item IDs to pick
            
        Returns:
            List of dicts with item and location info
        """
        pick_list = []
        for item_id in item_ids:
            item = self.env['mesob.inventory.item'].browse(item_id)
            bins = self.search([('item_ids', 'in', [item_id])])
            
            for bin_loc in bins:
                pick_list.append({
                    'item_code': item.item_code,
                    'item_name': item.name,
                    'bin_code': bin_loc.name,
                    'aisle': bin_loc.aisle,
                    'shelf': bin_loc.shelf,
                    'level': bin_loc.level,
                    'zone': dict(bin_loc._fields['zone'].selection).get(bin_loc.zone, 'Storage'),
                    'quantity_in_bin': item.current_stock,  # Use current_stock computed field
                })
        
        # Sort by aisle and shelf for logical picking sequence
        pick_list.sort(key=lambda x: (x['aisle'], x['shelf'], x['level'] or ''))
        
        return pick_list


class MesobStorageKeyRegister(models.Model):
    """Key Custody Register with Tamper-evident logging - FR-STOR-003 / NFR-SEC-003."""

    _name = "mesob.storage.key.register"
    _description = "Warehouse Key Custody Register"
    _order = "collected_at desc, id desc"

    name = fields.Char(string="Transaction ID", required=True, copy=False, default="New")
    key_id = fields.Char(string="Key ID / Label", required=True)
    collected_by_id = fields.Many2one("res.users", string="Collected By", required=True)
    collected_at = fields.Datetime(string="Collected Timestamp", default=fields.Datetime.now, required=True)
    deposited_at = fields.Datetime(string="Deposited Timestamp")
    notes = fields.Text(string="Remarks")
    
    # AUTO-069: Key Custody Auto-Logging enhancements
    is_returned = fields.Boolean(
        string="Returned",
        compute="_compute_is_returned",
        store=True,
        help="AUTO-069: True when key has been deposited back"
    )
    
    hours_held = fields.Float(
        string="Hours Held",
        compute="_compute_hours_held",
        help="AUTO-069: Duration key was held"
    )
    
    overdue = fields.Boolean(
        string="Overdue",
        compute="_compute_overdue",
        store=True,
        help="AUTO-069: Flagged if not returned within working hours"
    )
    
    @api.depends('deposited_at')
    def _compute_is_returned(self):
        """AUTO-069: Check if key is returned"""
        for rec in self:
            rec.is_returned = bool(rec.deposited_at)
    
    @api.depends('collected_at', 'deposited_at')
    def _compute_hours_held(self):
        """AUTO-069: Calculate how long key was held"""
        for rec in self:
            if rec.deposited_at:
                delta = rec.deposited_at - rec.collected_at
                rec.hours_held = delta.total_seconds() / 3600
            else:
                # Still held
                now = fields.Datetime.now()
                delta = now - rec.collected_at
                rec.hours_held = delta.total_seconds() / 3600
    
    @api.depends('is_returned', 'hours_held')
    def _compute_overdue(self):
        """AUTO-069: Flag if key not returned within 10 hours (working day)"""
        for rec in self:
            rec.overdue = not rec.is_returned and rec.hours_held > 10

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("mesob.storage.key.register") or "New"
        return super().create(vals_list)

    def action_deposit_keys(self):
        for rec in self:
            rec.deposited_at = fields.Datetime.now()
    
    @api.model
    def cron_check_overdue_keys(self):
        """AUTO-069: Check for overdue keys and alert PAO (FR-STOR-003).
        
        Scheduled to run hourly during working hours.
        Sends alerts to PAO for keys not returned within working day.
        """
        overdue_records = self.search([
            ('deposited_at', '=', False),
            ('collected_at', '<', fields.Datetime.now()),
        ])
        
        overdue_now = overdue_records.filtered(lambda r: r.hours_held > 10)
        
        if not overdue_now:
            _logger.info("AUTO-069: No overdue keys found")
            return
        
        # Group by key_id for summary
        key_groups = {}
        for rec in overdue_now:
            if rec.key_id not in key_groups:
                key_groups[rec.key_id] = []
            key_groups[rec.key_id].append(rec)
        
        # Build alert message
        alert_html = '<table style="width: 100%; border-collapse: collapse; margin-top: 10px;">'
        alert_html += '''
            <thead>
                <tr style="background-color: #dc3545; color: white;">
                    <th style="padding: 10px; text-align: left;">Key ID</th>
                    <th style="padding: 10px; text-align: left;">Collected By</th>
                    <th style="padding: 10px; text-align: left;">Collected At</th>
                    <th style="padding: 10px; text-align: right;">Hours Held</th>
                    <th style="padding: 10px; text-align: left;">Notes</th>
                </tr>
            </thead>
            <tbody>
        '''
        
        for key_id, records in key_groups.items():
            for rec in records:
                alert_html += f'''
                    <tr style="background-color: #f8d7da;">
                        <td style="padding: 8px; border-bottom: 1px solid #ddd; font-weight: bold;">{key_id}</td>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">{rec.collected_by_id.name}</td>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">{rec.collected_at.strftime('%Y-%m-%d %H:%M')}</td>
                        <td style="padding: 8px; text-align: right; border-bottom: 1px solid #ddd; color: #dc3545; font-weight: bold;">{rec.hours_held:.1f}h</td>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">{rec.notes or 'N/A'}</td>
                    </tr>
                '''
        
        alert_html += '</tbody></table>'
        
        # Send alert to PAO
        pao_group = self.env.ref('mesob_inventory_base.group_mesob_pao', raise_if_not_found=False)
        if pao_group and pao_group.users:
            # Post to the first overdue record (representative)
            overdue_now[0].message_post(
                body=f"""<div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px;">
                    <h2 style="color: #856404; margin-top: 0;">⚠ AUTO-069: OVERDUE KEY CUSTODY ALERT</h2>
                    
                    <p style="font-size: 16px; margin: 10px 0;">
                        <strong>{len(overdue_now)}</strong> warehouse key(s) have not been returned within the working day threshold (10 hours).
                    </p>
                    
                    <h3>Overdue Key Details</h3>
                    {alert_html}
                    
                    <div style="background-color: #e7f3ff; padding: 15px; margin-top: 20px; border-radius: 5px;">
                        <h4 style="margin-top: 0;">📋 REQUIRED ACTIONS (FR-STOR-003)</h4>
                        <ol style="margin: 10px 0;">
                            <li><strong>Immediate Contact:</strong> Contact key holders to verify status</li>
                            <li><strong>Security Check:</strong> Verify warehouse security and access</li>
                            <li><strong>Key Retrieval:</strong> Arrange immediate key return if holder is off-site</li>
                            <li><strong>Incident Report:</strong> Document reason for extended custody</li>
                            <li><strong>Policy Review:</strong> Review and reinforce key custody policy with staff</li>
                        </ol>
                        <p style="margin: 10px 0 0 0;"><em>Key custody threshold: 10 hours (one working day)</em></p>
                    </div>
                    
                    <p style="margin-top: 20px;">
                        <a href="/web#model=mesob.storage.key.register&view_type=list" 
                           style="background-color: #ffc107; color: #212529; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                           View Key Register →
                        </a>
                    </p>
                </div>""",
                subject=f'⚠ Overdue Key Alert: {len(overdue_now)} Key(s) Not Returned',
                message_type='notification',
                partner_ids=pao_group.users.mapped('partner_id').ids
            )
        
        _logger.warning(
            f"AUTO-069: Overdue key alert sent - "
            f"{len(overdue_now)} keys overdue, "
            f"Keys: {', '.join(key_groups.keys())}"
        )
        
        return True


class MesobStorageVisitorLog(models.Model):
    """Visitor Access Logs - FR-STOR-004."""

    _name = "mesob.storage.visitor.log"
    _description = "Warehouse Visitor Log"
    _order = "entry_time desc"

    name = fields.Char(string="Log Reference", required=True, copy=False, default="New")
    visitor_name = fields.Char(string="Visitor Name", required=True)
    organization = fields.Char(string="Organization / Institution")
    purpose = fields.Text(string="Purpose of Visit", required=True)
    entry_time = fields.Datetime(string="Entry Timestamp", default=fields.Datetime.now, required=True)
    exit_time = fields.Datetime(string="Exit Timestamp")
    security_escort_id = fields.Many2one("res.users", string="Security Officer / Escort")
    
    # AUTO-070: Access Control Enhancement
    visit_duration_hours = fields.Float(
        string="Duration (Hours)",
        compute="_compute_visit_duration",
        help="AUTO-070: Time spent in warehouse"
    )
    
    is_after_hours = fields.Boolean(
        string="After-Hours Visit",
        compute="_compute_after_hours",
        store=True,
        help="AUTO-070: Flagged if entry outside working hours (8 AM - 5 PM)"
    )
    
    visit_type = fields.Selection([
        ('routine', 'Routine Inspection'),
        ('audit', 'Audit Visit'),
        ('delivery', 'Delivery/Supplier'),
        ('maintenance', 'Maintenance'),
        ('other', 'Other'),
    ], string="Visit Type", default='routine',
       help="AUTO-070: Categorize visitor type")
    
    items_accessed = fields.Many2many(
        "mesob.inventory.item",
        "mesob_visitor_item_rel",
        "visitor_log_id",
        "item_id",
        string="Items Accessed/Viewed",
        help="AUTO-070: Track which items were accessed during visit"
    )
    
    notes = fields.Text(string="Visit Notes / Observations")
    
    @api.depends('entry_time', 'exit_time')
    def _compute_visit_duration(self):
        """AUTO-070: Calculate visit duration"""
        for rec in self:
            if rec.exit_time:
                delta = rec.exit_time - rec.entry_time
                rec.visit_duration_hours = delta.total_seconds() / 3600
            else:
                # Still visiting
                now = fields.Datetime.now()
                delta = now - rec.entry_time
                rec.visit_duration_hours = delta.total_seconds() / 3600
    
    @api.depends('entry_time')
    def _compute_after_hours(self):
        """AUTO-070: Flag after-hours access (outside 8 AM - 5 PM)"""
        for rec in self:
            if rec.entry_time:
                hour = rec.entry_time.hour
                # After hours: before 8 AM or after 5 PM
                rec.is_after_hours = hour < 8 or hour >= 17
            else:
                rec.is_after_hours = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("mesob.storage.visitor.log") or "New"
        return super().create(vals_list)

    def action_exit(self):
        for rec in self:
            rec.exit_time = fields.Datetime.now()
    
    @api.model
    def get_visitor_frequency_report(self, days=30):
        """AUTO-070: Analyze visitor frequency patterns.
        
        Generates report showing:
        - Most frequent visitors
        - After-hours access events
        - Unusual access patterns
        
        Args:
            days: Analysis period in days (default: 30)
            
        Returns:
            Dict with frequency analysis
        """
        cutoff_date = fields.Datetime.now() - timedelta(days=days)
        
        logs = self.search([
            ('entry_time', '>=', cutoff_date)
        ])
        
        # Frequency analysis
        visitor_counts = {}
        after_hours_count = 0
        
        for log in logs:
            visitor_counts[log.visitor_name] = visitor_counts.get(log.visitor_name, 0) + 1
            if log.is_after_hours:
                after_hours_count += 1
        
        # Sort by frequency
        sorted_visitors = sorted(visitor_counts.items(), key=lambda x: x[1], reverse=True)
        
        return {
            'period_days': days,
            'total_visits': len(logs),
            'unique_visitors': len(visitor_counts),
            'after_hours_visits': after_hours_count,
            'top_visitors': sorted_visitors[:10],
            'average_visits_per_day': len(logs) / days if days > 0 else 0,
        }
    
    @api.model
    def cron_generate_access_report(self):
        """AUTO-070: Generate weekly access control report for PAO (FR-STOR-004).
        
        Reports on:
        - After-hours access events
        - High-frequency visitors
        - Unauthorized access attempts (to be logged via separate mechanism)
        """
        # Get weekly report
        report = self.get_visitor_frequency_report(days=7)
        
        # Get after-hours visits details
        cutoff_date = fields.Datetime.now() - timedelta(days=7)
        after_hours_visits = self.search([
            ('entry_time', '>=', cutoff_date),
            ('is_after_hours', '=', True)
        ], order='entry_time desc')
        
        # Build after-hours details table
        after_hours_html = ''
        if after_hours_visits:
            after_hours_html = '<table style="width: 100%; border-collapse: collapse; margin-top: 10px;">'
            after_hours_html += '''
                <thead>
                    <tr style="background-color: #fd7e14; color: white;">
                        <th style="padding: 10px; text-align: left;">Visitor</th>
                        <th style="padding: 10px; text-align: left;">Organization</th>
                        <th style="padding: 10px; text-align: left;">Entry Time</th>
                        <th style="padding: 10px; text-align: left;">Purpose</th>
                        <th style="padding: 10px; text-align: left;">Escort</th>
                    </tr>
                </thead>
                <tbody>
            '''
            
            for visit in after_hours_visits[:20]:  # Show top 20
                after_hours_html += f'''
                    <tr style="background-color: #fff3cd;">
                        <td style="padding: 8px; border-bottom: 1px solid #ddd; font-weight: bold;">{visit.visitor_name}</td>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">{visit.organization or 'N/A'}</td>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">{visit.entry_time.strftime('%Y-%m-%d %H:%M')}</td>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">{visit.purpose[:50]}...</td>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">{visit.security_escort_id.name if visit.security_escort_id else 'None'}</td>
                    </tr>
                '''
            
            after_hours_html += '</tbody></table>'
        else:
            after_hours_html = '<p style="color: #28a745; font-weight: bold;">✓ No after-hours access events recorded this week</p>'
        
        # Build frequent visitors table
        frequent_html = '<table style="width: 100%; border-collapse: collapse; margin-top: 10px;">'
        frequent_html += '''
            <thead>
                <tr style="background-color: #007bff; color: white;">
                    <th style="padding: 10px; text-align: left;">Visitor Name</th>
                    <th style="padding: 10px; text-align: right;">Visit Count</th>
                </tr>
            </thead>
            <tbody>
        '''
        
        for visitor, count in report['top_visitors'][:10]:
            frequent_html += f'''
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">{visitor}</td>
                    <td style="padding: 8px; text-align: right; border-bottom: 1px solid #ddd;">{count}</td>
                </tr>
            '''
        
        frequent_html += '</tbody></table>'
        
        # Send report to PAO
        pao_group = self.env.ref('mesob_inventory_base.group_mesob_pao', raise_if_not_found=False)
        if pao_group and pao_group.users:
            # Create a mail.message or use the first visit record as anchor
            anchor_visit = after_hours_visits[0] if after_hours_visits else self.search([], limit=1)
            
            if anchor_visit:
                anchor_visit.message_post(
                    body=f"""<div style="background-color: #e7f3ff; border-left: 4px solid #007bff; padding: 15px;">
                        <h2 style="color: #004085; margin-top: 0;">📊 AUTO-070: WEEKLY ACCESS CONTROL REPORT</h2>
                        
                        <h3>Summary (Past 7 Days)</h3>
                        <table style="width: 100%; background-color: white; padding: 10px; margin-bottom: 15px;">
                            <tr>
                                <td style="padding: 5px; font-weight: bold; width: 250px;">Total Visits:</td>
                                <td style="padding: 5px;">{report['total_visits']}</td>
                            </tr>
                            <tr>
                                <td style="padding: 5px; font-weight: bold;">Unique Visitors:</td>
                                <td style="padding: 5px;">{report['unique_visitors']}</td>
                            </tr>
                            <tr>
                                <td style="padding: 5px; font-weight: bold;">After-Hours Visits:</td>
                                <td style="padding: 5px; {'color: #dc3545; font-weight: bold;' if report['after_hours_visits'] > 0 else 'color: #28a745;'}">{report['after_hours_visits']}</td>
                            </tr>
                            <tr>
                                <td style="padding: 5px; font-weight: bold;">Average Visits/Day:</td>
                                <td style="padding: 5px;">{report['average_visits_per_day']:.1f}</td>
                            </tr>
                        </table>
                        
                        <h3>{'⚠ ' if report['after_hours_visits'] > 0 else ''}After-Hours Access Events</h3>
                        {after_hours_html}
                        
                        <h3>Most Frequent Visitors</h3>
                        {frequent_html}
                        
                        <div style="background-color: #fff3cd; padding: 15px; margin-top: 20px; border-radius: 5px;">
                            <h4 style="margin-top: 0;">📋 SECURITY RECOMMENDATIONS (FR-STOR-004)</h4>
                            <ul style="margin: 10px 0;">
                                <li>Review after-hours access events and verify authorization</li>
                                <li>Ensure all after-hours visitors had proper escort</li>
                                <li>Investigate any unusual visitor patterns or frequencies</li>
                                <li>Verify visitor log completeness (entry/exit timestamps)</li>
                                <li>Review and update access control policies as needed</li>
                            </ul>
                        </div>
                        
                        <p style="margin-top: 20px;">
                            <a href="/web#model=mesob.storage.visitor.log&view_type=list" 
                               style="background-color: #007bff; color: white; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                               View Visitor Logs →
                            </a>
                        </p>
                    </div>""",
                    subject=f'📊 Weekly Access Control Report - {after_hours_visits[0].entry_time.strftime("%Y-%m-%d") if after_hours_visits else ""}',
                    message_type='notification',
                    partner_ids=pao_group.users.mapped('partner_id').ids
                )
        
        _logger.info(
            f"AUTO-070: Weekly access report generated - "
            f"Total: {report['total_visits']}, "
            f"After-hours: {report['after_hours_visits']}, "
            f"Unique: {report['unique_visitors']}"
        )
        
        return True


class MesobStorageSafetyChecklist(models.Model):
    """Safety and Fire Precaution Compliance Checklist - FR-STOR-005/006."""

    _name = "mesob.storage.safety.checklist"
    _description = "Warehouse Safety Checklist"
    _order = "date desc, id desc"

    name = fields.Char(string="Checklist Reference", required=True, copy=False, default="New")
    inspector_id = fields.Many2one("res.users", string="Inspector / Officer", default=lambda self: self.env.user, required=True)
    date = fields.Date(string="Inspection Date", default=fields.Date.today, required=True)
    
    has_fire_extinguishers_checked = fields.Boolean(string="Fire Extinguishers Checked & Serviced (FR-STOR-005)", default=False)
    has_ppe_available = fields.Boolean(string="PPE Available & Utilized (FR-STOR-006)", default=False)
    has_first_aid_kit = fields.Boolean(string="First Aid Kit Fully Stocked", default=False)
    has_emergency_exits_clear = fields.Boolean(string="Emergency Communication & Exits Clear", default=False)
    
    # AUTO-071: Enhanced safety tracking
    inspection_type = fields.Selection([
        ('fire_extinguisher', 'Fire Extinguisher Check'),
        ('ppe', 'PPE Compliance Check'),
        ('first_aid', 'First Aid Kit Check'),
        ('emergency_drill', 'Emergency Exit Drill'),
        ('comprehensive', 'Comprehensive Safety Inspection'),
    ], string="Inspection Type", required=True, default='comprehensive',
       help="AUTO-071: Type of safety inspection")
    
    is_overdue = fields.Boolean(
        string="Overdue Inspection",
        compute="_compute_overdue",
        help="AUTO-071: Flagged if inspection type is overdue based on schedule"
    )
    
    next_inspection_date = fields.Date(
        string="Next Inspection Due",
        compute="_compute_next_inspection",
        help="AUTO-071: Calculated next inspection date based on type"
    )
    
    compliance_score = fields.Float(
        string="Compliance %",
        compute="_compute_compliance_score",
        help="AUTO-071: Percentage of checks passed"
    )
    
    remarks = fields.Text(string="Inspection Observations")
    
    # Detailed checklist items
    fire_extinguisher_count = fields.Integer(
        string="Extinguishers Checked",
        help="Number of fire extinguishers inspected"
    )
    fire_extinguisher_expired = fields.Integer(
        string="Extinguishers Expired",
        help="Number requiring service/recharge"
    )
    
    ppe_items_checked = fields.Text(
        string="PPE Items Checked",
        help="List: helmets, gloves, boots, masks, etc."
    )
    ppe_items_missing = fields.Text(
        string="PPE Items Missing/Inadequate",
        help="Items needing replacement"
    )
    
    first_aid_expiry_items = fields.Text(
        string="Expired First Aid Items",
        help="Medications or supplies past expiry"
    )
    
    emergency_exit_obstructions = fields.Text(
        string="Exit Obstructions Noted",
        help="Any blockages or access issues"
    )
    
    @api.depends('inspection_type', 'date')
    def _compute_next_inspection(self):
        """AUTO-071: Calculate next inspection date based on schedule.
        
        Schedule (FR-STOR-005/006):
        - Fire extinguisher: Monthly
        - PPE: Weekly
        - First aid: Monthly
        - Emergency drill: Quarterly
        - Comprehensive: Monthly
        """
        for rec in self:
            if not rec.date:
                rec.next_inspection_date = False
                continue
            
            schedule_days = {
                'fire_extinguisher': 30,  # Monthly
                'ppe': 7,                  # Weekly
                'first_aid': 30,           # Monthly
                'emergency_drill': 90,     # Quarterly
                'comprehensive': 30,        # Monthly
            }
            
            days = schedule_days.get(rec.inspection_type, 30)
            rec.next_inspection_date = rec.date + timedelta(days=days)
    
    @api.depends('inspection_type', 'date')
    def _compute_overdue(self):
        """AUTO-071: Check if this inspection type is overdue"""
        for rec in self:
            if not rec.date or not rec.inspection_type:
                rec.is_overdue = False
                continue
            
            # Find last inspection of this type before this one
            last_inspection = self.search([
                ('inspection_type', '=', rec.inspection_type),
                ('date', '<', rec.date),
                ('id', '!=', rec.id),
            ], order='date desc', limit=1)
            
            if last_inspection and last_inspection.next_inspection_date:
                # Overdue if current date is past next_inspection_date
                rec.is_overdue = rec.date > last_inspection.next_inspection_date
            else:
                rec.is_overdue = False
    
    @api.depends('has_fire_extinguishers_checked', 'has_ppe_available', 
                 'has_first_aid_kit', 'has_emergency_exits_clear')
    def _compute_compliance_score(self):
        """AUTO-071: Calculate compliance percentage"""
        for rec in self:
            total_checks = 4
            passed_checks = sum([
                rec.has_fire_extinguishers_checked,
                rec.has_ppe_available,
                rec.has_first_aid_kit,
                rec.has_emergency_exits_clear,
            ])
            rec.compliance_score = (passed_checks / total_checks) * 100 if total_checks > 0 else 0.0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = self.env["ir.sequence"].next_by_code("mesob.storage.safety.checklist") or "New"
        return super().create(vals_list)
    
    @api.model
    def cron_safety_inspection_reminders(self):
        """AUTO-071: Send reminders for overdue safety inspections (FR-STOR-005/006).
        
        Checks inspection schedules and alerts PAO/Storekeeper about overdue items:
        - Fire extinguisher: Monthly
        - PPE: Weekly
        - First aid: Monthly
        - Emergency drill: Quarterly
        
        Runs daily to check compliance.
        """
        today = fields.Date.today()
        
        inspection_types = {
            'fire_extinguisher': {'name': 'Fire Extinguisher Check', 'days': 30, 'priority': 'high'},
            'ppe': {'name': 'PPE Compliance Check', 'days': 7, 'priority': 'medium'},
            'first_aid': {'name': 'First Aid Kit Check', 'days': 30, 'priority': 'high'},
            'emergency_drill': {'name': 'Emergency Exit Drill', 'days': 90, 'priority': 'medium'},
        }
        
        overdue_inspections = []
        
        for inspection_type, config in inspection_types.items():
            # Find last inspection of this type
            last_inspection = self.search([
                ('inspection_type', '=', inspection_type),
            ], order='date desc', limit=1)
            
            if last_inspection:
                days_since = (today - last_inspection.date).days
                if days_since > config['days']:
                    overdue_inspections.append({
                        'type': inspection_type,
                        'name': config['name'],
                        'days_overdue': days_since - config['days'],
                        'last_date': last_inspection.date,
                        'priority': config['priority'],
                        'frequency': f"Every {config['days']} days",
                    })
            else:
                # Never inspected
                overdue_inspections.append({
                    'type': inspection_type,
                    'name': config['name'],
                    'days_overdue': 'Never performed',
                    'last_date': False,
                    'priority': config['priority'],
                    'frequency': f"Every {config['days']} days",
                })
        
        if not overdue_inspections:
            _logger.info("AUTO-071: All safety inspections are up to date")
            return True
        
        # Build overdue table
        overdue_html = '<table style="width: 100%; border-collapse: collapse; margin-top: 10px;">'
        overdue_html += '''
            <thead>
                <tr style="background-color: #dc3545; color: white;">
                    <th style="padding: 10px; text-align: left;">Inspection Type</th>
                    <th style="padding: 10px; text-align: left;">Frequency</th>
                    <th style="padding: 10px; text-align: left;">Last Performed</th>
                    <th style="padding: 10px; text-align: left;">Days Overdue</th>
                    <th style="padding: 10px; text-align: left;">Priority</th>
                </tr>
            </thead>
            <tbody>
        '''
        
        for inspection in overdue_inspections:
            priority_color = '#dc3545' if inspection['priority'] == 'high' else '#ffc107'
            overdue_html += f'''
                <tr style="background-color: #f8d7da;">
                    <td style="padding: 8px; border-bottom: 1px solid #ddd; font-weight: bold;">{inspection['name']}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">{inspection['frequency']}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd;">{inspection['last_date'] or 'Never'}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd; color: #dc3545; font-weight: bold;">{inspection['days_overdue']}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #ddd; color: {priority_color}; font-weight: bold; text-transform: uppercase;">{inspection['priority']}</td>
                </tr>
            '''
        
        overdue_html += '</tbody></table>'
        
        # Send alert to PAO and Storekeepers
        pao_group = self.env.ref('mesob_inventory_base.group_mesob_pao', raise_if_not_found=False)
        storekeeper_group = self.env.ref('mesob_inventory_base.group_mesob_storekeeper', raise_if_not_found=False)
        
        recipients = []
        if pao_group:
            recipients.extend(pao_group.users.mapped('partner_id').ids)
        if storekeeper_group:
            recipients.extend(storekeeper_group.users.mapped('partner_id').ids)
        
        recipients = list(set(recipients))  # Remove duplicates
        
        if recipients:
            # Use first inspection record as anchor, or create a generic record
            anchor = self.search([], limit=1)
            
            if anchor:
                anchor.message_post(
                    body=f"""<div style="background-color: #fff3cd; border-left: 4px solid #ffc107; padding: 15px;">
                        <h2 style="color: #856404; margin-top: 0;">⚠ AUTO-071: SAFETY INSPECTION REMINDERS</h2>
                        
                        <p style="font-size: 16px; margin: 10px 0;">
                            <strong>{len(overdue_inspections)}</strong> safety inspection(s) are overdue or have never been performed.
                        </p>
                        
                        <h3>Overdue Inspections</h3>
                        {overdue_html}
                        
                        <div style="background-color: #e7f3ff; padding: 15px; margin-top: 20px; border-radius: 5px;">
                            <h4 style="margin-top: 0;">📋 REQUIRED ACTIONS (FR-STOR-005/006)</h4>
                            <h5 style="margin-top: 10px;">Fire Extinguisher Check (Monthly):</h5>
                            <ul style="margin: 5px 0;">
                                <li>Inspect all fire extinguishers for pressure and condition</li>
                                <li>Verify expiry dates and service tags</li>
                                <li>Test accessibility and mounting</li>
                                <li>Schedule recharge/replacement for expired units</li>
                            </ul>
                            
                            <h5 style="margin-top: 10px;">PPE Compliance Check (Weekly):</h5>
                            <ul style="margin: 5px 0;">
                                <li>Verify availability of helmets, gloves, safety boots, masks</li>
                                <li>Check condition of existing PPE equipment</li>
                                <li>Ensure storekeepers are using required PPE</li>
                                <li>Order replacements for worn or damaged items</li>
                            </ul>
                            
                            <h5 style="margin-top: 10px;">First Aid Kit Check (Monthly):</h5>
                            <ul style="margin: 5px 0;">
                                <li>Inspect first aid supplies for completeness</li>
                                <li>Check medication expiry dates</li>
                                <li>Verify bandages, antiseptics, and emergency supplies</li>
                                <li>Restock expired or used items</li>
                            </ul>
                            
                            <h5 style="margin-top: 10px;">Emergency Exit Drill (Quarterly):</h5>
                            <ul style="margin: 5px 0;">
                                <li>Conduct emergency evacuation drill</li>
                                <li>Test emergency communication systems</li>
                                <li>Verify all exits are clear and accessible</li>
                                <li>Document drill results and response times</li>
                            </ul>
                        </div>
                        
                        <div style="background-color: #f8d7da; padding: 15px; margin-top: 15px; border-radius: 5px;">
                            <p style="margin: 0; font-weight: bold; color: #721c24;">
                                🚨 COMPLIANCE ALERT: Safety inspections are mandatory under FR-STOR-005 and FR-STOR-006.
                                Non-compliance may result in safety hazards and regulatory violations.
                            </p>
                        </div>
                        
                        <p style="margin-top: 20px;">
                            <a href="/web#model=mesob.storage.safety.checklist&view_type=form&view_mode=form" 
                               style="background-color: #ffc107; color: #212529; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold;">
                               Perform Safety Inspection →
                            </a>
                        </p>
                    </div>""",
                    subject=f'⚠ Safety Inspection Reminder: {len(overdue_inspections)} Overdue',
                    message_type='notification',
                    partner_ids=recipients
                )
        
        _logger.warning(
            f"AUTO-071: Safety inspection reminders sent - "
            f"{len(overdue_inspections)} overdue inspections"
        )
        
        return True

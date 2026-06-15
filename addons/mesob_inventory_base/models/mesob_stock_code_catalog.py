"""AUTO-037: Stock Code List Auto-Publication & Version Control.

Maintains live stock code list with version control and change tracking (FR-ID-004, FR-ID-005).
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class MesobStockCodeCatalog(models.Model):
    """AUTO-037: Stock Code Catalog Version Control (FR-ID-004, FR-ID-005)."""
    
    _name = 'mesob.stock.code.catalog'
    _description = 'Stock Code Catalog Version'
    _order = 'version_number desc, id desc'
    _rec_name = 'version_name'
    
    version_name = fields.Char(
        string='Version Name',
        required=True,
        help='e.g., "2026 Annual Amendment v1.0"'
    )
    
    version_number = fields.Char(
        string='Version Number',
        required=True,
        copy=False,
        default='1.0.0',
        help='Semantic version: major.minor.patch'
    )
    
    effective_date = fields.Date(
        string='Effective Date',
        required=True,
        default=fields.Date.today,
        help='Date this catalog version becomes effective'
    )
    
    publication_date = fields.Datetime(
        string='Publication Date',
        readonly=True,
        help='AUTO-037: Timestamp of catalog publication'
    )
    
    published_by_id = fields.Many2one(
        'res.users',
        string='Published By',
        readonly=True
    )
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('superseded', 'Superseded'),
    ], string='Status', default='draft', required=True, tracking=True)
    
    total_items = fields.Integer(
        string='Total Items',
        compute='_compute_statistics',
        store=True,
        help='Total number of items in catalog'
    )
    
    new_codes = fields.Integer(
        string='New Codes',
        help='Number of new codes in this version'
    )
    
    retired_codes = fields.Integer(
        string='Retired Codes',
        help='Number of codes retired in this version'
    )
    
    change_log = fields.Html(
        string='Change Log',
        help='AUTO-037: Detailed list of changes (new, modified, retired codes)'
    )
    
    notes = fields.Text(string='Publication Notes')
    
    # ── Computed Methods ────────────────────────────────────────────────
    
    @api.depends('state')
    def _compute_statistics(self):
        """Compute current item count."""
        for catalog in self:
            if catalog.state == 'published':
                catalog.total_items = self.env['mesob.inventory.item'].search_count([
                    ('active', '=', True)
                ])
            else:
                catalog.total_items = 0
    
    # ── Actions ─────────────────────────────────────────────────────────
    
    def action_publish_catalog(self):
        """AUTO-037: Publish catalog version and notify users (FR-ID-004, FR-ID-005)."""
        self.ensure_one()
        
        if self.state != 'draft':
            raise UserError("Only draft catalogs can be published.")
        
        # Supersede previous published version
        previous_published = self.search([
            ('state', '=', 'published'),
            ('id', '!=', self.id)
        ])
        if previous_published:
            previous_published.write({'state': 'superseded'})
        
        # Generate change log
        change_log = self._generate_change_log()
        
        # Publish
        self.write({
            'state': 'published',
            'publication_date': fields.Datetime.now(),
            'published_by_id': self.env.user.id,
            'change_log': change_log,
        })
        
        # Notify all authorized users
        self._send_publication_notification()
        
        _logger.info(
            f"AUTO-037: Stock code catalog {self.version_name} (v{self.version_number}) published "
            f"by {self.env.user.name}"
        )
        
        return True
    
    def _generate_change_log(self):
        """AUTO-037: Generate change log comparing to last published version."""
        # Get last published version
        last_version = self.search([
            ('state', 'in', ['published', 'superseded']),
            ('id', '!=', self.id)
        ], order='publication_date desc', limit=1)
        
        if not last_version or not last_version.publication_date:
            # First publication - list all current items
            all_items = self.env['mesob.inventory.item'].search([
                ('active', '=', True)
            ], order='item_code')
            
            self.new_codes = len(all_items)
            self.retired_codes = 0
            
            change_log_html = '<div style="padding: 15px;">'
            change_log_html += '<h3 style="color: #28a745;">📝 Initial Catalog Publication</h3>'
            change_log_html += f'<p><strong>Total Items:</strong> {len(all_items)}</p>'
            change_log_html += '<p><em>This is the first published version of the stock code catalog.</em></p>'
            change_log_html += '</div>'
            
            return change_log_html
        
        # Compare with last version
        current_items = self.env['mesob.inventory.item'].search([
            ('active', '=', True)
        ])
        
        # Items created/modified since last publication
        new_items = current_items.filtered(
            lambda i: not i.create_date or i.create_date > last_version.publication_date
        )
        
        # Items with auto-generated codes (new)
        auto_generated_items = current_items.filtered(lambda i: i.code_auto_generated)
        
        self.new_codes = len(new_items)
        self.retired_codes = 0  # Would need inactive items tracking
        
        # Build change log HTML
        change_log_html = '<div style="padding: 15px;">'
        change_log_html += f'<h3>📝 Changes in Version {self.version_number}</h3>'
        change_log_html += f'<p><strong>Effective Date:</strong> {self.effective_date}</p>'
        change_log_html += f'<p><strong>Previous Version:</strong> {last_version.version_number} (published {last_version.publication_date.date()})</p>'
        change_log_html += '<hr/>'
        
        # New codes section
        if new_items:
            change_log_html += f'<h4 style="color: #28a745;">✨ New Codes ({len(new_items)})</h4>'
            change_log_html += '<table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">'
            change_log_html += '''<thead style="background-color: #f8f9fa;">
                <tr>
                    <th style="border: 1px solid #dee2e6; padding: 8px;">Item Code</th>
                    <th style="border: 1px solid #dee2e6; padding: 8px;">Description</th>
                    <th style="border: 1px solid #dee2e6; padding: 8px;">Classification</th>
                </tr>
            </thead><tbody>'''
            
            for item in new_items[:50]:  # Limit to first 50
                change_log_html += f'''<tr>
                    <td style="border: 1px solid #dee2e6; padding: 8px;"><strong>{item.item_code}</strong></td>
                    <td style="border: 1px solid #dee2e6; padding: 8px;">{item.name}</td>
                    <td style="border: 1px solid #dee2e6; padding: 8px;">{item.classification_id.name if item.classification_id else 'N/A'}</td>
                </tr>'''
            
            if len(new_items) > 50:
                change_log_html += f'''<tr>
                    <td colspan="3" style="border: 1px solid #dee2e6; padding: 8px; text-align: center; font-style: italic;">
                        ... and {len(new_items) - 50} more new codes
                    </td>
                </tr>'''
            
            change_log_html += '</tbody></table>'
        else:
            change_log_html += '<p><em>No new codes in this version.</em></p>'
        
        change_log_html += '<hr/>'
        change_log_html += f'<p><strong>Total Active Items:</strong> {len(current_items)}</p>'
        change_log_html += '</div>'
        
        return change_log_html
    
    def _send_publication_notification(self):
        """AUTO-037: Send catalog publication notification to all users (FR-ID-004)."""
        self.ensure_one()
        
        # Send to all inventory users
        all_users = self.env['res.users'].search([('active', '=', True)])
        
        if all_users:
            self.message_post(
                body=f"""<div style="background-color: #d1ecf1; border-left: 4px solid #0c5460; padding: 15px;">
                    <h2 style="margin-top: 0;">📚 AUTO-037: Stock Code Catalog Published</h2>
                    <table style="width: 100%; margin: 15px 0;">
                        <tr>
                            <td style="padding: 5px 0;"><strong>Version:</strong></td>
                            <td style="padding: 5px 0;">{self.version_number}</td>
                        </tr>
                        <tr>
                            <td style="padding: 5px 0;"><strong>Version Name:</strong></td>
                            <td style="padding: 5px 0;">{self.version_name}</td>
                        </tr>
                        <tr>
                            <td style="padding: 5px 0;"><strong>Effective Date:</strong></td>
                            <td style="padding: 5px 0; font-weight: bold;">{self.effective_date}</td>
                        </tr>
                        <tr>
                            <td style="padding: 5px 0;"><strong>Total Items:</strong></td>
                            <td style="padding: 5px 0;">{self.total_items}</td>
                        </tr>
                        <tr>
                            <td style="padding: 5px 0;"><strong>New Codes:</strong></td>
                            <td style="padding: 5px 0; color: #28a745; font-weight: bold;">{self.new_codes}</td>
                        </tr>
                    </table>
                    <div style="background-color: #fff3cd; padding: 10px; border-radius: 4px; margin: 15px 0;">
                        <p style="margin: 0;"><strong>ℹ️ Important (FR-ID-004, FR-ID-005):</strong></p>
                        <ul style="margin: 5px 0 0 0;">
                            <li>New stock code catalog version is now effective</li>
                            <li>All users can access live catalog at any time</li>
                            <li>Historical versions retained for audit (NFR-QUAL-001)</li>
                            <li>Review change log for new/modified codes</li>
                        </ul>
                    </div>
                    {self.change_log if self.change_log else ''}
                    <p style="margin-top: 15px;">
                        <a href="/web#id={self.id}&model=mesob.stock.code.catalog&view_type=form" 
                           style="background-color: #0c5460; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                           📖 View Full Catalog →
                        </a>
                    </p>
                </div>""",
                subject=f'New Stock Code Catalog: {self.version_name} (v{self.version_number})',
                message_type='notification',
                partner_ids=all_users.mapped('partner_id').ids
            )
        
        _logger.info(
            f"AUTO-037: Catalog publication notification sent to {len(all_users)} users"
        )
    
    def action_view_catalog_items(self):
        """View all active items in this catalog."""
        self.ensure_one()
        
        return {
            'name': f'Stock Code Catalog: {self.version_name}',
            'type': 'ir.actions.act_window',
            'res_model': 'mesob.inventory.item',
            'view_mode': 'list,form',
            'domain': [('active', '=', True)],
            'context': {'default_active': True},
        }

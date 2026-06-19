# -*- coding: utf-8 -*-
"""AUTO-037: Stock Code List Auto-Publication & Version Control.

Automatically publishes and maintains versioned stock code catalogs per FR-ID-004, FR-ID-005.
Enables annual amendments with proper version tracking and distribution.

Compliance: FR-ID-004, FR-ID-005, NFR-QUAL-001
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging
from datetime import date

_logger = logging.getLogger(__name__)


class MesobStockCodeCatalogPublication(models.Model):
    """AUTO-037: Stock Code Catalog Publication with Version Control."""
    
    _name = 'mesob.stock.code.catalog.publication'
    _description = 'Stock Code Catalog Publication'
    _order = 'publication_date desc, version desc'
    _rec_name = 'display_name'
    
    # ── Version Control ─────────────────────────────────────────────
    
    name = fields.Char(
        string='Publication Name',
        required=True,
        default=lambda self: f"Stock Code Catalog {fields.Date.today().year}",
        help='AUTO-037: Name of this catalog publication'
    )
    
    version = fields.Char(
        string='Version',
        required=True,
        copy=False,
        default='1.0',
        help='AUTO-037: Version number (e.g., 1.0, 1.1, 2.0)'
    )
    
    display_name = fields.Char(
        string='Display Name',
        compute='_compute_display_name',
        store=True
    )
    
    publication_date = fields.Date(
        string='Publication Date',
        required=True,
        default=fields.Date.today,
        help='FR-ID-005: Date of catalog publication'
    )
    
    fiscal_year = fields.Char(
        string='Fiscal Year',
        required=True,
        default=lambda self: self._default_fiscal_year(),
        help='FR-ID-005: Ethiopian fiscal year (e.g., 2016 E.C.)'
    )
    
    state = fields.Selection([
        ('draft', 'Draft'),
        ('published', 'Published'),
        ('amended', 'Amended'),
        ('superseded', 'Superseded'),
    ], string='State', default='draft', tracking=True)
    
    # ── Content ─────────────────────────────────────────────────────
    
    item_count = fields.Integer(
        string='Item Count',
        compute='_compute_item_statistics',
        store=True,
        help='Total items in this catalog'
    )
    
    classification_count = fields.Integer(
        string='Classification Count',
        compute='_compute_item_statistics',
        store=True,
        help='Number of major classifications'
    )
    
    new_items_count = fields.Integer(
        string='New Items',
        default=0,
        help='Items added since last version'
    )
    
    amended_items_count = fields.Integer(
        string='Amended Items',
        default=0,
        help='Items modified since last version'
    )
    
    excluded_items_count = fields.Integer(
        string='Excluded Items',
        default=0,
        help='FR-ID-006: Seldom-required items excluded from catalog'
    )
    
    # ── Previous Version Tracking ───────────────────────────────────
    
    previous_version_id = fields.Many2one(
        'mesob.stock.code.catalog.publication',
        string='Previous Version',
        readonly=True,
        help='AUTO-037: Link to superseded version'
    )
    
    amendment_notes = fields.Text(
        string='Amendment Notes',
        help='FR-ID-005: Description of changes in this version'
    )
    
    # ── Distribution Tracking ───────────────────────────────────────
    
    distributed_to = fields.Text(
        string='Distributed To',
        help='FR-ID-004: Record of departments/units who received catalog'
    )
    
    distribution_date = fields.Date(
        string='Distribution Date',
        help='AUTO-037: Date when catalog was distributed'
    )
    
    # ── Audit Trail ─────────────────────────────────────────────────
    
    published_by_id = fields.Many2one(
        'res.users',
        string='Published By',
        readonly=True,
        help='User who published this catalog'
    )
    
    approved_by_id = fields.Many2one(
        'res.users',
        string='Approved By',
        help='PAO or authorized approver'
    )
    
    # ── Computed Fields ─────────────────────────────────────────────
    
    @api.depends('name', 'version')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"{rec.name} v{rec.version}"
    
    @api.depends('state')
    def _compute_item_statistics(self):
        """Calculate catalog statistics from active items."""
        Item = self.env['mesob.inventory.item']
        
        for rec in self:
            # Count active items (excluding those marked for exclusion per FR-ID-006)
            active_items = Item.search([
                ('active', '=', True),
                ('exclude_from_catalog', '=', False)
            ])
            
            rec.item_count = len(active_items)
            rec.classification_count = len(active_items.mapped('classification_id'))
            rec.excluded_items_count = Item.search_count([
                ('active', '=', True),
                ('exclude_from_catalog', '=', True)
            ])
    
    @api.model
    def _default_fiscal_year(self):
        """Calculate Ethiopian fiscal year."""
        today = date.today()
        # Ethiopian fiscal year starts July 8 (Gregorian)
        if today.month < 7 or (today.month == 7 and today.day < 8):
            ec_year = today.year - 8  # Before July 8
        else:
            ec_year = today.year - 7  # After July 8
        return f"{ec_year} E.C."
    
    # ── Constraints ─────────────────────────────────────────────────
    
    _sql_constraints = [
        ('version_unique', 'UNIQUE(version, fiscal_year)',
         'AUTO-037: Version must be unique per fiscal year.')
    ]
    
    @api.constrains('version')
    def _check_version_format(self):
        """Validate version number format (e.g., 1.0, 1.1, 2.0)."""
        import re
        version_pattern = re.compile(r'^\d+\.\d+$')
        
        for rec in self:
            if not version_pattern.match(rec.version):
                raise ValidationError(
                    _("AUTO-037: Version must follow format X.Y (e.g., 1.0, 1.1, 2.0)")
                )
    
    # ── Actions ─────────────────────────────────────────────────────
    
    def action_generate_catalog(self):
        """AUTO-037: Generate catalog content from current item master."""
        self.ensure_one()
        
        if self.state != 'draft':
            raise UserError(_("Only draft catalogs can be regenerated."))
        
        # Recalculate statistics
        self._compute_item_statistics()
        
        # Compare with previous version if exists
        if self.previous_version_id:
            self._calculate_amendments()
        
        _logger.info(
            f"AUTO-037: Catalog {self.display_name} generated - "
            f"Items: {self.item_count}, Classifications: {self.classification_count}"
        )
        
        self.message_post(
            body=f"""<div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px;">
                <h3>✅ AUTO-037: Catalog Generated</h3>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 8px; font-weight: bold;">Version:</td>
                        <td style="padding: 8px;">{self.version}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; font-weight: bold;">Fiscal Year:</td>
                        <td style="padding: 8px;">{self.fiscal_year}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; font-weight: bold;">Total Items:</td>
                        <td style="padding: 8px;">{self.item_count}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; font-weight: bold;">Classifications:</td>
                        <td style="padding: 8px;">{self.classification_count}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; font-weight: bold;">Excluded Items:</td>
                        <td style="padding: 8px;">{self.excluded_items_count} (FR-ID-006)</td>
                    </tr>
                    {f'''<tr style="background-color: #fff3cd;">
                        <td style="padding: 8px; font-weight: bold;">New Items:</td>
                        <td style="padding: 8px;">{self.new_items_count}</td>
                    </tr>
                    <tr style="background-color: #fff3cd;">
                        <td style="padding: 8px; font-weight: bold;">Amended Items:</td>
                        <td style="padding: 8px;">{self.amended_items_count}</td>
                    </tr>''' if self.previous_version_id else ''}
                </table>
                <p style="margin-top: 15px;"><em>Compliance: FR-ID-004, FR-ID-005</em></p>
            </div>""",
            subject='Catalog Generated',
            message_type='comment'
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Catalog Generated',
                'message': f'Version {self.version} - {self.item_count} items',
                'type': 'success',
                'sticky': False,
            }
        }
    
    def _calculate_amendments(self):
        """Calculate changes since previous version."""
        self.ensure_one()
        
        if not self.previous_version_id:
            return
        
        # Get snapshot date of previous version
        prev_date = self.previous_version_id.publication_date
        
        # Count new items created after previous publication
        Item = self.env['mesob.inventory.item']
        new_items = Item.search([
            ('create_date', '>', prev_date),
            ('active', '=', True),
            ('exclude_from_catalog', '=', False)
        ])
        self.new_items_count = len(new_items)
        
        # Count amended items (modified after previous publication)
        amended_items = Item.search([
            ('write_date', '>', prev_date),
            ('create_date', '<=', prev_date),
            ('active', '=', True),
            ('exclude_from_catalog', '=', False)
        ])
        self.amended_items_count = len(amended_items)
        
        _logger.info(
            f"AUTO-037: Amendments calculated - New: {self.new_items_count}, "
            f"Amended: {self.amended_items_count}"
        )
    
    def action_publish(self):
        """AUTO-037: Publish catalog and distribute (FR-ID-004)."""
        self.ensure_one()
        
        if self.state != 'draft':
            raise UserError(_("Only draft catalogs can be published."))
        
        if not self.approved_by_id:
            raise UserError(_("Catalog must be approved before publication."))
        
        # Mark previous version as superseded
        if self.previous_version_id and self.previous_version_id.state == 'published':
            self.previous_version_id.state = 'superseded'
        
        self.write({
            'state': 'published',
            'published_by_id': self.env.user.id,
            'publication_date': fields.Date.today(),
        })
        
        # AUTO-037: Send distribution notifications
        self._auto_distribute_catalog()
        
        _logger.info(
            f"AUTO-037: Catalog {self.display_name} published by {self.env.user.name}"
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Catalog Published',
                'message': f'{self.display_name} published successfully',
                'type': 'success',
                'sticky': True,
            }
        }
    
    def _auto_distribute_catalog(self):
        """AUTO-037: Auto-distribute catalog to relevant departments (FR-ID-004)."""
        self.ensure_one()
        
        # Get relevant user groups for distribution
        groups_to_notify = [
            'mesob_inventory_base.group_mesob_pao',
            'mesob_inventory_base.group_mesob_storekeeper',
            'mesob_inventory_base.group_mesob_procurement',
            'mesob_inventory_base.group_mesob_accounts',
        ]
        
        recipient_users = self.env['res.users']
        for group_xml_id in groups_to_notify:
            try:
                group = self.env.ref(group_xml_id)
                recipient_users |= group.users
            except ValueError:
                continue
        
        if not recipient_users:
            _logger.warning(
                f"AUTO-037: No users found for catalog distribution {self.display_name}"
            )
            return
        
        # Send notification
        self.message_post(
            body=f"""<div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px;">
                <h2 style="margin: 0;">📚 AUTO-037: Stock Code Catalog Published</h2>
            </div>
            <div style="background-color: #f8f9fa; padding: 20px; margin-top: 10px;">
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 10px; font-weight: bold;">Catalog:</td>
                        <td style="padding: 10px;">{self.display_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; font-weight: bold;">Version:</td>
                        <td style="padding: 10px;">{self.version}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; font-weight: bold;">Fiscal Year:</td>
                        <td style="padding: 10px;">{self.fiscal_year}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; font-weight: bold;">Publication Date:</td>
                        <td style="padding: 10px;">{self.publication_date}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; font-weight: bold;">Total Items:</td>
                        <td style="padding: 10px;">{self.item_count}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; font-weight: bold;">New Items:</td>
                        <td style="padding: 10px;">{self.new_items_count}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px; font-weight: bold;">Amended Items:</td>
                        <td style="padding: 10px;">{self.amended_items_count}</td>
                    </tr>
                </table>
                {f'''<div style="background-color: #fff3cd; padding: 15px; margin-top: 15px; border-radius: 4px;">
                    <h4 style="margin-top: 0;">📝 Amendment Notes:</h4>
                    <p>{self.amendment_notes}</p>
                </div>''' if self.amendment_notes else ''}
                <div style="background-color: #e7f3ff; padding: 15px; margin-top: 15px; border-radius: 4px;">
                    <p style="margin: 0;"><strong>📋 Action Required:</strong></p>
                    <ul style="margin: 10px 0;">
                        <li>Review the updated stock code catalog</li>
                        <li>Update your department records accordingly</li>
                        <li>Use the new codes for all requisitions and procurement</li>
                    </ul>
                </div>
                <p style="margin-top: 15px;"><em>Compliance: FR-ID-004 (Catalog Distribution), FR-ID-005 (Version Control)</em></p>
            </div>""",
            subject=f'Stock Code Catalog Published: {self.display_name}',
            message_type='notification',
            partner_ids=recipient_users.mapped('partner_id').ids
        )
        
        self.write({
            'distribution_date': fields.Date.today(),
            'distributed_to': f"Auto-distributed to {len(recipient_users)} users: "
                             f"{', '.join(recipient_users.mapped('name')[:5])}{'...' if len(recipient_users) > 5 else ''}"
        })
        
        _logger.info(
            f"AUTO-037: Catalog {self.display_name} distributed to {len(recipient_users)} users"
        )
    
    def action_create_amendment(self):
        """AUTO-037: Create new version as amendment to this catalog (FR-ID-005)."""
        self.ensure_one()
        
        if self.state != 'published':
            raise UserError(_("Only published catalogs can be amended."))
        
        # Calculate next version number
        version_parts = self.version.split('.')
        major = int(version_parts[0])
        minor = int(version_parts[1]) if len(version_parts) > 1 else 0
        
        # Check if it's annual (new fiscal year) or mid-year amendment
        current_fy = self._default_fiscal_year()
        if current_fy != self.fiscal_year:
            # New fiscal year - increment major version
            new_version = f"{major + 1}.0"
        else:
            # Mid-year amendment - increment minor version
            new_version = f"{major}.{minor + 1}"
        
        # Create new draft version
        new_catalog = self.copy(default={
            'version': new_version,
            'fiscal_year': current_fy,
            'state': 'draft',
            'previous_version_id': self.id,
            'publication_date': fields.Date.today(),
            'published_by_id': False,
            'approved_by_id': False,
            'distribution_date': False,
            'distributed_to': False,
            'new_items_count': 0,
            'amended_items_count': 0,
        })
        
        # Mark current as amended
        self.state = 'amended'
        
        _logger.info(
            f"AUTO-037: Amendment created - {self.display_name} → {new_catalog.display_name}"
        )
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mesob.stock.code.catalog.publication',
            'res_id': new_catalog.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    def action_print_catalog(self):
        """Generate PDF catalog report."""
        self.ensure_one()
        # TODO: Implement PDF report generation
        raise UserError(_("PDF catalog export coming soon. Use web view for now."))

"""AUTO-037: Stock Code List Auto-Publication & Version Control.

Maintains live stock code list with version control and change tracking (FR-ID-004, FR-ID-005).
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging
import io
import base64
from datetime import datetime

_logger = logging.getLogger(__name__)


class MesobStockCodeCatalog(models.Model):
    """AUTO-037: Stock Code Catalog Version Control (FR-ID-004, FR-ID-005)."""
    
    _name = 'mesob.stock.code.catalog'
    _description = 'Stock Code Catalog Version'
    _inherit = ['mail.thread', 'mail.activity.mixin']
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
    
    # ═══════════════════════════════════════════════════════════════════════
    # ADVANCED AUTO-037: Code Management & Utilities
    # ═══════════════════════════════════════════════════════════════════════
    
    reserved_codes_ids = fields.One2many(
        'mesob.reserved.code',
        'catalog_id',
        string='Reserved Codes',
        help='ADVANCED: Codes reserved for future use'
    )
    
    export_file = fields.Binary(
        string='Exported Catalog',
        readonly=True,
        help='ADVANCED: Excel export of catalog'
    )
    
    export_filename = fields.Char(
        string='Export Filename',
        readonly=True
    )
    
    import_file = fields.Binary(
        string='Import File',
        help='ADVANCED: Upload Excel/CSV to bulk import codes'
    )
    
    import_filename = fields.Char(string='Import Filename')
    
    migration_log = fields.Html(
        string='Migration Log',
        readonly=True,
        help='ADVANCED: Log of code migrations and transformations'
    )
    
    code_availability_check = fields.Text(
        string='Code Availability',
        compute='_compute_code_availability',
        help='ADVANCED: Check which codes are available for use'
    )
    
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
    
    # ═══════════════════════════════════════════════════════════════════════
    # ADVANCED AUTO-037: Code Availability & Management
    # ═══════════════════════════════════════════════════════════════════════
    
    @api.depends('state')
    def _compute_code_availability(self):
        """ADVANCED AUTO-037: Check code availability in each classification."""
        for catalog in self:
            if catalog.state != 'published':
                catalog.code_availability_check = 'Publish catalog to check availability'
                continue
            
            availability_report = []
            classifications = self.env['mesob.inventory.major.classification'].search([])
            
            for classification in classifications:
                items_in_class = self.env['mesob.inventory.item'].search_count([
                    ('classification_id', '=', classification.id),
                    ('active', '=', True)
                ])
                
                # Max items per classification: 999 sub-classifications × 999 specific codes = ~1M codes
                # Simplified: assume 999 codes per sub-classification
                max_codes = 999000
                availability_pct = (items_in_class / max_codes) * 100 if max_codes > 0 else 0
                
                status = '✅ Available' if availability_pct < 50 else '⚠️ 50%+ Used' if availability_pct < 80 else '🚨 80%+ Used'
                
                availability_report.append(
                    f"{classification.code} ({classification.name}): {items_in_class} codes used ({availability_pct:.2f}%) - {status}"
                )
            
            catalog.code_availability_check = '\n'.join(availability_report)
    
    def action_check_code(self, code_to_check):
        """ADVANCED AUTO-037: Check if a specific code is available.
        
        Args:
            code_to_check: String in format ####-###-###
            
        Returns:
            Dict with availability info
        """
        self.ensure_one()
        
        # Check format
        import re
        if not re.match(r'^\d{4}-\d{3}-\d{3}$', code_to_check):
            raise UserError(f"Invalid code format: {code_to_check}. Expected: ####-###-###")
        
        # Check if code exists
        existing_item = self.env['mesob.inventory.item'].search([
            ('item_code', '=', code_to_check),
            ('active', '=', True)
        ], limit=1)
        
        # Check if code is reserved
        reserved = self.env['mesob.reserved.code'].search([
            ('code', '=', code_to_check),
            ('catalog_id', '=', self.id),
            ('released', '=', False)
        ], limit=1)
        
        if existing_item:
            return {
                'available': False,
                'status': 'in_use',
                'message': f"Code {code_to_check} is already in use by: {existing_item.name}",
                'item_id': existing_item.id,
            }
        elif reserved:
            return {
                'available': False,
                'status': 'reserved',
                'message': f"Code {code_to_check} is reserved for: {reserved.purpose}",
                'reserved_by': reserved.reserved_by_id.name,
                'reserved_until': reserved.reserved_until,
            }
        else:
            return {
                'available': True,
                'status': 'available',
                'message': f"Code {code_to_check} is available for use",
            }
    
    def action_reserve_codes(self, code_range_start, code_range_end, purpose, reserved_until=None):
        """ADVANCED AUTO-037: Reserve a range of codes for future use.
        
        Args:
            code_range_start: Starting code (e.g., '4401-001-001')
            code_range_end: Ending code (e.g., '4401-001-050')
            purpose: Reason for reservation
            reserved_until: Optional expiry date
            
        Returns:
            List of created reservation records
        """
        self.ensure_one()
        
        # Parse codes
        import re
        match_start = re.match(r'^(\d{4})-(\d{3})-(\d{3})$', code_range_start)
        match_end = re.match(r'^(\d{4})-(\d{3})-(\d{3})$', code_range_end)
        
        if not match_start or not match_end:
            raise UserError("Invalid code format. Expected: ####-###-###")
        
        # Ensure same major and sub codes
        if match_start.group(1) != match_end.group(1) or match_start.group(2) != match_end.group(2):
            raise UserError("Code range must be within same sub-classification")
        
        major = match_start.group(1)
        sub = match_start.group(2)
        specific_start = int(match_start.group(3))
        specific_end = int(match_end.group(3))
        
        if specific_start > specific_end:
            raise UserError("Start code must be less than or equal to end code")
        
        # Create reservations
        reserved_codes = []
        for specific in range(specific_start, specific_end + 1):
            code = f"{major}-{sub}-{specific:03d}"
            
            # Check if already reserved or in use
            check_result = self.action_check_code(code)
            if check_result['available']:
                reservation = self.env['mesob.reserved.code'].create({
                    'catalog_id': self.id,
                    'code': code,
                    'purpose': purpose,
                    'reserved_by_id': self.env.user.id,
                    'reserved_until': reserved_until,
                })
                reserved_codes.append(reservation)
        
        _logger.info(
            f"AUTO-037: Reserved {len(reserved_codes)} codes from {code_range_start} to {code_range_end} "
            f"for: {purpose}"
        )
        
        return reserved_codes
    
    def action_bulk_generate_codes(self, classification_id, sub_classification_id, count, prefix_name):
        """ADVANCED AUTO-037: Bulk generate item codes with template data.
        
        Args:
            classification_id: Major classification ID
            sub_classification_id: Sub-classification ID
            count: Number of codes to generate
            prefix_name: Name prefix for generated items
            
        Returns:
            List of created item records
        """
        self.ensure_one()
        
        if count > 100:
            raise UserError("Maximum 100 codes can be generated at once")
        
        classification = self.env['mesob.inventory.major.classification'].browse(classification_id)
        sub_classification = self.env['mesob.inventory.sub.classification'].browse(sub_classification_id)
        
        if not classification or not sub_classification:
            raise UserError("Invalid classification or sub-classification")
        
        created_items = []
        for i in range(count):
            # Auto-generate next code
            item = self.env['mesob.inventory.item'].create({
                'classification_id': classification_id,
                'sub_classification_id': sub_classification_id,
                'name': f"{prefix_name} {i+1}",
                'active': True,
            })
            created_items.append(item)
        
        _logger.info(
            f"AUTO-037: Bulk generated {count} item codes in "
            f"{classification.name} / {sub_classification.name}"
        )
        
        return created_items
    
    def action_export_catalog(self):
        """ADVANCED AUTO-037: Export catalog to Excel for offline use.
        
        Returns Excel file with:
        - All active items
        - Classifications
        - Reserved codes
        - Change history
        """
        self.ensure_one()
        
        try:
            from xlsxwriter import Workbook
        except ImportError:
            raise UserError("xlsxwriter library not installed. Run: pip install xlsxwriter")
        
        # Create Excel file in memory
        output = io.BytesIO()
        workbook = Workbook(output, {'in_memory': True})
        
        # Sheet 1: Active Items
        worksheet1 = workbook.add_worksheet('Active Items')
        bold = workbook.add_format({'bold': True, 'bg_color': '#D9E1F2'})
        
        # Headers
        headers = ['Item Code', 'Name (English)', 'Name (Amharic)', 'Classification', 'Sub-Classification', 'ABC Class', 'Current Stock']
        for col, header in enumerate(headers):
            worksheet1.write(0, col, header, bold)
        
        # Data
        items = self.env['mesob.inventory.item'].search([('active', '=', True)], order='item_code')
        for row, item in enumerate(items, start=1):
            worksheet1.write(row, 0, item.item_code or '')
            worksheet1.write(row, 1, item.name or '')
            worksheet1.write(row, 2, item.name_am or '')
            worksheet1.write(row, 3, item.classification_id.name if item.classification_id else '')
            worksheet1.write(row, 4, item.sub_classification_id.name if item.sub_classification_id else '')
            worksheet1.write(row, 5, item.abc_class or '')
            worksheet1.write(row, 6, item.current_stock or 0)
        
        # Sheet 2: Reserved Codes
        worksheet2 = workbook.add_worksheet('Reserved Codes')
        headers2 = ['Code', 'Purpose', 'Reserved By', 'Reserved Until', 'Status']
        for col, header in enumerate(headers2):
            worksheet2.write(0, col, header, bold)
        
        reserved = self.env['mesob.reserved.code'].search([('catalog_id', '=', self.id)])
        for row, res in enumerate(reserved, start=1):
            worksheet2.write(row, 0, res.code or '')
            worksheet2.write(row, 1, res.purpose or '')
            worksheet2.write(row, 2, res.reserved_by_id.name if res.reserved_by_id else '')
            worksheet2.write(row, 3, str(res.reserved_until) if res.reserved_until else '')
            worksheet2.write(row, 4, 'Released' if res.released else 'Active')
        
        # Sheet 3: Catalog Info
        worksheet3 = workbook.add_worksheet('Catalog Info')
        info_data = [
            ['Version Name', self.version_name],
            ['Version Number', self.version_number],
            ['Effective Date', str(self.effective_date)],
            ['Publication Date', str(self.publication_date) if self.publication_date else ''],
            ['Published By', self.published_by_id.name if self.published_by_id else ''],
            ['Total Items', str(self.total_items)],
            ['New Codes', str(self.new_codes)],
            ['Retired Codes', str(self.retired_codes)],
        ]
        for row, (label, value) in enumerate(info_data):
            worksheet3.write(row, 0, label, bold)
            worksheet3.write(row, 1, value)
        
        workbook.close()
        output.seek(0)
        
        # Save to record
        filename = f"Stock_Catalog_{self.version_number}_{datetime.now().strftime('%Y%m%d')}.xlsx"
        self.write({
            'export_file': base64.b64encode(output.read()),
            'export_filename': filename,
        })
        
        _logger.info(f"AUTO-037: Catalog {self.version_name} exported to Excel")
        
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/mesob.stock.code.catalog/{self.id}/export_file/{filename}?download=true',
            'target': 'self',
        }
    
    def action_import_catalog(self):
        """ADVANCED AUTO-037: Import items from Excel/CSV file.
        
        Expected format:
        - Column A: Item Code (####-###-###)
        - Column B: Name (English)
        - Column C: Name (Amharic)
        - Column D: Classification Code
        - Column E: Sub-Classification Code
        """
        self.ensure_one()
        
        if not self.import_file:
            raise UserError("Please upload an import file first")
        
        try:
            import openpyxl
        except ImportError:
            raise UserError("openpyxl library not installed. Run: pip install openpyxl")
        
        # Decode file
        file_data = base64.b64decode(self.import_file)
        file_obj = io.BytesIO(file_data)
        
        # Load workbook
        workbook = openpyxl.load_workbook(file_obj)
        sheet = workbook.active
        
        created_count = 0
        skipped_count = 0
        errors = []
        
        # Process rows (skip header)
        for row_num, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):
            if not row[0]:  # Skip empty rows
                continue
            
            item_code = str(row[0]).strip()
            name = str(row[1]).strip() if row[1] else ''
            name_am = str(row[2]).strip() if len(row) > 2 and row[2] else ''
            
            # Check if code already exists
            existing = self.env['mesob.inventory.item'].search([('item_code', '=', item_code)], limit=1)
            if existing:
                skipped_count += 1
                continue
            
            try:
                # Create item
                self.env['mesob.inventory.item'].create({
                    'item_code': item_code,
                    'name': name,
                    'name_am': name_am,
                    'active': True,
                })
                created_count += 1
            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")
        
        # Build migration log
        migration_html = f"""<div style="padding: 15px;">
            <h3>📥 Catalog Import Results</h3>
            <p><strong>Import Date:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p><strong>Imported By:</strong> {self.env.user.name}</p>
            <table style="width: 100%; margin: 15px 0;">
                <tr>
                    <td><strong>Created:</strong></td>
                    <td style="color: #28a745; font-weight: bold;">{created_count} items</td>
                </tr>
                <tr>
                    <td><strong>Skipped (duplicates):</strong></td>
                    <td style="color: #ffc107;">{skipped_count} items</td>
                </tr>
                <tr>
                    <td><strong>Errors:</strong></td>
                    <td style="color: #dc3545;">{len(errors)} items</td>
                </tr>
            </table>
        """
        
        if errors:
            migration_html += '<h4 style="color: #dc3545;">Import Errors:</h4><ul>'
            for error in errors[:20]:  # Show first 20 errors
                migration_html += f'<li>{error}</li>'
            if len(errors) > 20:
                migration_html += f'<li><em>...and {len(errors) - 20} more errors</em></li>'
            migration_html += '</ul>'
        
        migration_html += '</div>'
        
        self.write({'migration_log': migration_html})
        
        _logger.info(
            f"AUTO-037: Import complete - Created: {created_count}, "
            f"Skipped: {skipped_count}, Errors: {len(errors)}"
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Import Complete',
                'message': f'Created {created_count} items, skipped {skipped_count} duplicates, {len(errors)} errors',
                'type': 'success' if len(errors) == 0 else 'warning',
                'sticky': False,
            }
        }


class MesobReservedCode(models.Model):
    """ADVANCED AUTO-037: Reserved Code Management.
    
    Allows reserving codes for future use (planning, bulk operations, migrations).
    """
    
    _name = 'mesob.reserved.code'
    _description = 'Reserved Item Code'
    _order = 'code'
    
    catalog_id = fields.Many2one(
        'mesob.stock.code.catalog',
        string='Catalog Version',
        required=True,
        ondelete='cascade'
    )
    
    code = fields.Char(
        string='Reserved Code',
        required=True,
        help='Code reserved in format ####-###-###'
    )
    
    purpose = fields.Text(
        string='Purpose',
        required=True,
        help='Reason for reservation'
    )
    
    reserved_by_id = fields.Many2one(
        'res.users',
        string='Reserved By',
        default=lambda self: self.env.user,
        required=True
    )
    
    reserved_date = fields.Date(
        string='Reserved Date',
        default=fields.Date.today,
        required=True
    )
    
    reserved_until = fields.Date(
        string='Reserved Until',
        help='Expiry date for reservation (optional)'
    )
    
    released = fields.Boolean(
        string='Released',
        default=False,
        help='True when code is released for general use'
    )
    
    released_date = fields.Date(
        string='Released Date',
        readonly=True
    )
    
    notes = fields.Text(string='Notes')
    
    @api.constrains('code')
    def _check_code_format(self):
        """Validate code format."""
        import re
        for rec in self:
            if not re.match(r'^\d{4}-\d{3}-\d{3}$', rec.code):
                raise ValidationError(f"Invalid code format: {rec.code}. Expected: ####-###-###")
    
    def action_release_code(self):
        """Release reserved code for general use."""
        self.ensure_one()
        
        if self.released:
            raise UserError("This code has already been released")
        
        self.write({
            'released': True,
            'released_date': fields.Date.today(),
        })
        
        _logger.info(f"AUTO-037: Reserved code {self.code} released by {self.env.user.name}")
        
        return True
    
    @api.model
    def cron_expire_reservations(self):
        """ADVANCED AUTO-037: Automatically release expired reservations.
        
        Runs daily to check for expired reservations.
        """
        today = fields.Date.today()
        
        expired = self.search([
            ('reserved_until', '<', today),
            ('reserved_until', '!=', False),
            ('released', '=', False),
        ])
        
        if expired:
            expired.write({
                'released': True,
                'released_date': today,
            })
            
            _logger.info(f"AUTO-037: Auto-released {len(expired)} expired code reservations")
        
        return True

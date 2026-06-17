# -*- coding: utf-8 -*-
"""AUTO-002: Intelligent Needs Consolidation Wizard.

Helps SPO consolidate department needs into lots using:
- Keyword matching for similar items
- Auto-grouping by classification
- Budget threshold-based mechanism suggestions
- Visual grouping interface
"""

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
import logging

_logger = logging.getLogger(__name__)


class MesobIntelligentConsolidationWizard(models.TransientModel):
    """AUTO-002: Intelligent consolidation wizard for SPO."""
    
    _name = 'mesob.intelligent.consolidation.wizard'
    _description = 'Intelligent Needs Consolidation Wizard'
    
    plan_id = fields.Many2one(
        'mesob.procurement.plan',
        string='Annual Procurement Plan',
        required=True,
        readonly=True
    )
    
    consolidation_strategy = fields.Selection([
        ('by_item', 'By Exact Item Code'),
        ('by_sub_class', 'By Sub-Classification'),
        ('by_major_class', 'By Major Classification'),
        ('by_keywords', 'By Keyword Similarity (Intelligent)'),
    ], string='Consolidation Strategy', default='by_sub_class', required=True)
    
    keyword_threshold = fields.Integer(
        string='Keyword Match Threshold (%)',
        default=60,
        help='Minimum percentage of matching keywords to group items (for keyword strategy)'
    )
    
    group_preview_ids = fields.One2many(
        'mesob.consolidation.group.preview',
        'wizard_id',
        string='Consolidation Preview',
        help='Preview of how needs will be grouped into lots'
    )
    
    total_needs = fields.Integer(
        string='Total Needs',
        compute='_compute_statistics'
    )
    
    total_groups = fields.Integer(
        string='Suggested Lots',
        compute='_compute_statistics'
    )
    
    total_budget = fields.Monetary(
        string='Total Budget',
        compute='_compute_statistics',
        currency_field='currency_id'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )
    
    @api.depends('group_preview_ids')
    def _compute_statistics(self):
        """Compute preview statistics."""
        for wizard in self:
            wizard.total_needs = sum(wizard.group_preview_ids.mapped('need_count'))
            wizard.total_groups = len(wizard.group_preview_ids)
            wizard.total_budget = sum(wizard.group_preview_ids.mapped('total_budget'))
    
    def action_preview_consolidation(self):
        """AUTO-002: Generate consolidation preview based on selected strategy."""
        self.ensure_one()
        
        # Clear existing preview
        self.group_preview_ids.unlink()
        
        # Get reviewed needs without lot assignment
        needs = self.env['mesob.procurement.need'].search([
            ('state', '=', 'reviewed'),
            ('lot_id', '=', False),
            '|',
            ('item_id', '!=', False),
            ('sub_classification_id', '!=', False)
        ])
        
        if not needs:
            raise UserError(
                "No reviewed needs available for consolidation.\n"
                "Please ensure needs are reviewed before attempting consolidation."
            )
        
        # Apply consolidation strategy
        if self.consolidation_strategy == 'by_item':
            groups = self._group_by_item(needs)
        elif self.consolidation_strategy == 'by_sub_class':
            groups = self._group_by_sub_classification(needs)
        elif self.consolidation_strategy == 'by_major_class':
            groups = self._group_by_major_classification(needs)
        else:  # by_keywords
            groups = self._group_by_keywords(needs)
        
        # Create preview records
        for group_key, group_needs in groups.items():
            self._create_preview_group(group_key, group_needs)
        
        _logger.info(
            f"AUTO-002: Consolidation preview generated - "
            f"Strategy: {self.consolidation_strategy}, "
            f"Needs: {len(needs)}, Groups: {len(groups)}"
        )
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mesob.intelligent.consolidation.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
    
    def _group_by_item(self, needs):
        """Group needs by exact item code."""
        groups = {}
        for need in needs:
            if need.item_id:
                key = f"ITEM_{need.item_id.id}"
                if key not in groups:
                    groups[key] = self.env['mesob.procurement.need']
                groups[key] |= need
        return groups
    
    def _group_by_sub_classification(self, needs):
        """Group needs by sub-classification."""
        groups = {}
        for need in needs:
            if need.sub_classification_id:
                key = f"SUB_{need.sub_classification_id.id}"
                if key not in groups:
                    groups[key] = self.env['mesob.procurement.need']
                groups[key] |= need
        return groups
    
    def _group_by_major_classification(self, needs):
        """Group needs by major classification."""
        groups = {}
        for need in needs:
            if need.major_classification_id:
                key = f"MAJ_{need.major_classification_id.id}"
                if key not in groups:
                    groups[key] = self.env['mesob.procurement.need']
                groups[key] |= need
        return groups
    
    def _group_by_keywords(self, needs):
        """AUTO-002: Intelligent grouping by keyword similarity."""
        from difflib import SequenceMatcher
        
        groups = {}
        processed = set()
        
        for need in needs:
            if need.id in processed:
                continue
            
            # Start new group with this need
            group_key = f"KW_{need.id}"
            groups[group_key] = self.env['mesob.procurement.need']
            groups[group_key] |= need
            processed.add(need.id)
            
            # Find similar needs
            for other_need in needs:
                if other_need.id in processed:
                    continue
                
                # Check classification match first
                if need.major_classification_id != other_need.major_classification_id:
                    continue
                
                # Calculate keyword similarity
                similarity = self._calculate_keyword_similarity(
                    need.consolidation_keywords,
                    other_need.consolidation_keywords
                )
                
                if similarity >= (self.keyword_threshold / 100.0):
                    groups[group_key] |= other_need
                    processed.add(other_need.id)
        
        return groups
    
    def _calculate_keyword_similarity(self, keywords1, keywords2):
        """Calculate similarity ratio between two keyword strings."""
        if not keywords1 or not keywords2:
            return 0.0
        
        from difflib import SequenceMatcher
        return SequenceMatcher(None, keywords1, keywords2).ratio()
    
    def _create_preview_group(self, group_key, group_needs):
        """Create preview record for a consolidation group."""
        # Determine group name
        first_need = group_needs[0]
        if first_need.item_id:
            group_name = first_need.item_id.name
        elif first_need.sub_classification_id:
            group_name = first_need.sub_classification_id.name
        elif first_need.major_classification_id:
            group_name = first_need.major_classification_id.name
        else:
            group_name = "Uncategorized Group"
        
        # Calculate totals
        total_budget = sum(group_needs.mapped('total_price'))
        
        # Suggest procurement mechanism based on budget (AUTO-006 logic)
        if total_budget >= 10000000.0:
            suggested_mechanism = 'bidding'
        elif total_budget >= 5000000.0:
            suggested_mechanism = 'bidding'
        elif total_budget >= 500000.0:
            suggested_mechanism = 'shopping'
        else:
            suggested_mechanism = 'shopping'
        
        self.env['mesob.consolidation.group.preview'].create({
            'wizard_id': self.id,
            'group_key': group_key,
            'suggested_lot_name': f"Lot: {group_name}",
            'need_ids': [(6, 0, group_needs.ids)],
            'need_count': len(group_needs),
            'total_budget': total_budget,
            'suggested_mechanism': suggested_mechanism,
        })
    
    def action_confirm_consolidation(self):
        """AUTO-002: Create lots from consolidation preview."""
        self.ensure_one()
        
        if not self.group_preview_ids:
            raise UserError("No consolidation preview available. Please generate preview first.")
        
        lot_count = len(self.plan_id.lot_ids) + 1
        created_lots = self.env['mesob.procurement.plan.lot']
        
        for group in self.group_preview_ids:
            if not group.include_in_consolidation:
                continue
            
            # Create lot
            lot = self.env['mesob.procurement.plan.lot'].create({
                'plan_id': self.plan_id.id,
                'name': group.suggested_lot_name or f"Lot {lot_count}",
                'category': 'supplies',  # Default
                'budget': group.total_budget,
                'mechanism': group.suggested_mechanism,
                'sub_classification_id': group.need_ids[0].sub_classification_id.id if group.need_ids and group.need_ids[0].sub_classification_id else False,
            })
            
            # Assign needs to lot
            group.need_ids.write({'lot_id': lot.id})
            
            created_lots |= lot
            lot_count += 1
            
            _logger.info(
                f"AUTO-002: Lot created - {lot.name}, "
                f"Needs: {len(group.need_ids)}, Budget: ETB {group.total_budget:,.2f}"
            )
        
        # Send notification
        self.plan_id.message_post(
            body=f"""<div style="background-color: #d4edda; border-left: 4px solid #28a745; padding: 15px;">
                <h3>AUTO-002: Intelligent Consolidation Complete</h3>
                <p><strong>Strategy:</strong> {dict(self._fields['consolidation_strategy'].selection).get(self.consolidation_strategy, '')}</p>
                <p><strong>Lots Created:</strong> {len(created_lots)}</p>
                <p><strong>Total Budget:</strong> ETB {sum(created_lots.mapped('budget')):,.2f}</p>
                <p><strong>Needs Consolidated:</strong> {sum(created_lots.mapped('need_ids').mapped(lambda n: 1))}</p>
                <hr/>
                <h4>Created Lots:</h4>
                <ul>
                    {''.join([f'<li>{lot.name}: ETB {lot.budget:,.2f} ({lot.mechanism})</li>' for lot in created_lots])}
                </ul>
            </div>""",
            subject='Intelligent Consolidation Complete',
            message_type='comment'
        )
        
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Consolidation Complete',
                'message': f'{len(created_lots)} lots created successfully.',
                'type': 'success',
                'sticky': False,
            }
        }


class MesobConsolidationGroupPreview(models.TransientModel):
    """Preview of a consolidation group."""
    
    _name = 'mesob.consolidation.group.preview'
    _description = 'Consolidation Group Preview'
    _order = 'total_budget desc'
    
    wizard_id = fields.Many2one(
        'mesob.intelligent.consolidation.wizard',
        required=True,
        ondelete='cascade'
    )
    
    group_key = fields.Char(string='Group Key', required=True)
    
    suggested_lot_name = fields.Char(
        string='Suggested Lot Name',
        required=True
    )
    
    need_ids = fields.Many2many(
        'mesob.procurement.need',
        string='Needs in Group'
    )
    
    need_count = fields.Integer(string='Need Count')
    
    total_budget = fields.Monetary(
        string='Total Budget',
        currency_field='currency_id'
    )
    
    suggested_mechanism = fields.Selection([
        ('bidding', 'Tender / Bidding'),
        ('shopping', 'Shopping / RFQ'),
        ('direct', 'Direct (Single-Source)'),
    ], string='Suggested Mechanism')
    
    include_in_consolidation = fields.Boolean(
        string='Include',
        default=True,
        help='Include this group in final consolidation'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        default=lambda self: self.env.company.currency_id
    )

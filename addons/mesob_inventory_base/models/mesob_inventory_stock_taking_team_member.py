# -*- coding: utf-8 -*-
"""
Mesob Inventory Stock Taking Team Member (SRS 4.8)
FR-ST-009: Manages team members with storekeeper exclusion rules
"""

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class MesobInventoryStockTakingTeamMember(models.Model):
    """
    FR-ST-009: Stock taking team members
    Ensures storekeepers are excluded from counter/recorder/team_head roles
    """
    _name = 'mesob.inventory.stock.taking.team.member'
    _description = 'Stock Taking Team Member'
    _order = 'role, user_id'

    event_id = fields.Many2one('mesob.inventory.stock.taking.event', string='Stock Taking Event',
                              required=True, ondelete='cascade')
    user_id = fields.Many2one('res.users', string='Team Member', required=True)
    role = fields.Selection([
        ('team_head', 'Team Head'),
        ('counter', 'Counter'),
        ('recorder', 'Recorder'),
        ('witness', 'Witness'),
        ('guide', 'Guide (Storekeeper)')
    ], string='Role', required=True)
    signature_date = fields.Datetime(string='Signature Date/Time')
    notes = fields.Text(string='Notes')
    
    # Computed field to check if user is storekeeper
    is_storekeeper = fields.Boolean(string='Is Storekeeper', compute='_compute_is_storekeeper', store=True)

    @api.depends('user_id')
    def _compute_is_storekeeper(self):
        storekeeper_group = self.env.ref('mesob_inventory_base.group_mesob_storekeeper', raise_if_not_found=False)
        for member in self:
            if member.user_id and storekeeper_group:
                member.is_storekeeper = storekeeper_group in member.user_id.groups_id
            else:
                member.is_storekeeper = False

    @api.constrains('user_id', 'role')
    def _check_storekeeper_role(self):
        """
        FR-ST-009: Ensure storekeepers are excluded from being stock-taking team members
        (except as guides/witnessed participants)
        """
        storekeeper_group = self.env.ref('mesob_inventory_base.group_mesob_storekeeper', raise_if_not_found=False)
        if not storekeeper_group:
            return
        
        for member in self:
            if member.user_id and storekeeper_group in member.user_id.groups_id:
                if member.role in ['team_head', 'counter', 'recorder', 'witness']:
                    raise ValidationError(_(
                        'Storekeepers cannot be assigned as Team Head, Counter, Recorder, or Witness. '
                        'They can only participate as Guides. '
                        'User "%s" is a storekeeper.'
                    ) % member.user_id.name)

    @api.constrains('user_id', 'event_id')
    def _check_unique_user_per_event(self):
        """Ensure a user is not added multiple times to the same event"""
        for member in self:
            duplicate = self.search([
                ('event_id', '=', member.event_id.id),
                ('user_id', '=', member.user_id.id),
                ('id', '!=', member.id)
            ], limit=1)
            if duplicate:
                raise ValidationError(_(
                    'User "%s" is already a team member for this stock taking event.'
                ) % member.user_id.name)

    def action_sign(self):
        """Record signature date/time"""
        self.ensure_one()
        self.signature_date = fields.Datetime.now()

# -*- coding: utf-8 -*-
"""
Task 7: Push Notification System - User Preferences
====================================================

Allows users to configure which notifications they want to receive.
Default: All notifications enabled (opt-out model).
"""

from odoo import api, models, fields, _


class MesobNotificationPreference(models.Model):
    """
    User notification preferences.
    Controls which activity types trigger notifications for each user.
    """
    _name = 'mesob.notification.preference'
    _description = 'Notification Preference'
    _rec_name = 'user_id'

    user_id = fields.Many2one(
        'res.users',
        string='User',
        required=True,
        ondelete='cascade',
        default=lambda self: self.env.user,
        help='User whose preferences these are'
    )
    
    activity_type_code = fields.Selection([
        ('mesob_activity_requisition_approval', 'Requisition Approvals'),
        ('mesob_activity_po_approval', 'Purchase Order Approvals'),
        ('mesob_activity_gate_pass_authorization', 'Gate Pass Authorizations'),
        ('mesob_activity_reorder_alert', 'Stock Reorder Alerts'),
        ('mesob_activity_po_overdue', 'Overdue PO Alerts'),
        ('mesob_activity_manual_adjustment_approval', 'Manual Adjustment Approvals'),
    ], string='Notification Type', required=True, help='Type of notification')
    
    enabled = fields.Boolean(
        string='Enabled',
        default=True,
        help='Enable/disable this notification type'
    )
    
    _sql_constraints = [
        ('user_activity_unique', 'UNIQUE(user_id, activity_type_code)',
         'Each user can only have one preference per notification type!')
    ]

    @api.model
    def get_user_preference(self, user_id, activity_type_code):
        """
        Get user preference for a specific notification type.
        
        Args:
            user_id: User ID
            activity_type_code: Activity type code
            
        Returns:
            bool: True if enabled (default), False if disabled
        """
        preference = self.search([
            ('user_id', '=', user_id),
            ('activity_type_code', '=', activity_type_code),
        ], limit=1)
        
        return preference.enabled if preference else True

    @api.model
    def set_user_preference(self, user_id, activity_type_code, enabled):
        """
        Set user preference for a specific notification type.
        
        Args:
            user_id: User ID
            activity_type_code: Activity type code
            enabled: True to enable, False to disable
        """
        preference = self.search([
            ('user_id', '=', user_id),
            ('activity_type_code', '=', activity_type_code),
        ], limit=1)
        
        if preference:
            preference.enabled = enabled
        else:
            self.create({
                'user_id': user_id,
                'activity_type_code': activity_type_code,
                'enabled': enabled,
            })

    @api.model
    def initialize_user_preferences(self, user_id):
        """
        Initialize default preferences for a new user.
        Called when a new user is created.
        
        Args:
            user_id: User ID
        """
        activity_types = dict(self._fields['activity_type_code'].selection)
        
        for code in activity_types.keys():
            if not self.search([('user_id', '=', user_id), ('activity_type_code', '=', code)]):
                self.create({
                    'user_id': user_id,
                    'activity_type_code': code,
                    'enabled': True,
                })

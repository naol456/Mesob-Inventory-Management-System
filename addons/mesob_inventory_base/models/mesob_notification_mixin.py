# -*- coding: utf-8 -*-
"""
Task 7: Push Notification System
=================================

Notification mixin for Mesob Inventory Management System.
Provides unified notification methods using Odoo's Activity system.

Activities appear in:
- Activity menu (top right bell icon)
- Activity sidebar on records
- Email notifications (if configured)
"""

from odoo import api, models, fields, _
import logging

_logger = logging.getLogger(__name__)


class MesobNotificationMixin(models.AbstractModel):
    """
    Mixin to provide notification capabilities to models.
    Uses Odoo's built-in Activity system for real-time notifications.
    """
    _name = 'mesob.notification.mixin'
    _description = 'Mesob Notification Mixin'

    def _get_activity_type(self, activity_code):
        """
        Get or create activity type by XML ID.
        
        Activity types defined in data file:
        - mesob_activity_requisition_approval
        - mesob_activity_po_approval
        - mesob_activity_gate_pass_authorization
        - mesob_activity_reorder_alert
        - mesob_activity_po_overdue
        - mesob_activity_manual_adjustment_approval
        """
        try:
            return self.env.ref(f'mesob_inventory_base.{activity_code}')
        except ValueError:
            # Fallback to generic TODO activity
            _logger.warning(f"Activity type {activity_code} not found, using fallback")
            return self.env.ref('mail.mail_activity_data_todo')

    def _schedule_activity(self, activity_code, user_ids=None, summary=None, note=None, date_deadline=None):
        """
        Schedule an activity (notification) for users.
        
        Args:
            activity_code: Activity type XML ID (without module prefix)
            user_ids: List of user IDs to notify (default: PAO users)
            summary: Activity summary/title
            note: Detailed note (HTML supported)
            date_deadline: Due date (default: today)
        """
        self.ensure_one()
        
        if not user_ids:
            # Default to PAO users
            pao_group = self.env.ref('mesob_inventory_base.group_mesob_pao', raise_if_not_found=False)
            if pao_group and pao_group.users:
                user_ids = pao_group.users.ids
            else:
                _logger.warning("No PAO users found for notification")
                return

        activity_type = self._get_activity_type(activity_code)
        
        if not date_deadline:
            date_deadline = fields.Date.today()

        # Schedule activity for each user
        for user_id in user_ids:
            # Check user notification preferences
            if self._should_send_notification(user_id, activity_code):
                try:
                    self.activity_schedule(
                        activity_type_id=activity_type.id,
                        user_id=user_id,
                        summary=summary or activity_type.name,
                        note=note,
                        date_deadline=date_deadline,
                    )
                    _logger.info(f"Activity scheduled for user {user_id}: {summary}")
                except Exception as e:
                    _logger.error(f"Failed to schedule activity for user {user_id}: {e}")

    def _should_send_notification(self, user_id, activity_code):
        """
        Check if user wants to receive this type of notification.
        Based on user's notification preferences.
        
        Args:
            user_id: User ID
            activity_code: Activity type code
            
        Returns:
            bool: True if notification should be sent
        """
        Preference = self.env['mesob.notification.preference'].sudo()
        
        # Check if user has specific preference
        preference = Preference.search([
            ('user_id', '=', user_id),
            ('activity_type_code', '=', activity_code),
        ], limit=1)
        
        if preference:
            return preference.enabled
        
        # Default: send all notifications (opt-out model)
        return True

    def _notify_requisition_approval(self, requisition):
        """Notify PAO of new requisition requiring approval."""
        pao_group = self.env.ref('mesob_inventory_base.group_mesob_pao', raise_if_not_found=False)
        if pao_group and pao_group.users:
            requisition._schedule_activity(
                activity_code='mesob_activity_requisition_approval',
                user_ids=pao_group.users.ids,
                summary=_('Requisition Approval Required: %s') % requisition.name,
                note=_(
                    '<p><strong>Department:</strong> %s</p>'
                    '<p><strong>Requested by:</strong> %s</p>'
                    '<p><strong>Items:</strong> %d</p>'
                    '<p><strong>Purpose:</strong> %s</p>'
                ) % (
                    requisition.department_id.name,
                    requisition.requester_id.name,
                    len(requisition.line_ids),
                    requisition.purpose or 'Not specified',
                ),
            )

    def _notify_po_approval(self, po):
        """Notify HOPE of PO requiring approval."""
        # Get HOPE users (assuming PAO for now, adjust as needed)
        hope_group = self.env.ref('mesob_inventory_base.group_mesob_pao', raise_if_not_found=False)
        if hope_group and hope_group.users:
            po._schedule_activity(
                activity_code='mesob_activity_po_approval',
                user_ids=hope_group.users.ids,
                summary=_('PO Approval Required: %s') % po.name,
                note=_(
                    '<p><strong>Supplier:</strong> %s</p>'
                    '<p><strong>Amount:</strong> %s</p>'
                    '<p><strong>Items:</strong> %d</p>'
                ) % (
                    po.supplier_id.name if hasattr(po, 'supplier_id') else 'N/A',
                    po.total_amount if hasattr(po, 'total_amount') else 'N/A',
                    len(po.line_ids) if hasattr(po, 'line_ids') else 0,
                ),
            )

    def _notify_gate_pass_authorization(self, gate_pass):
        """Notify PAO of Gate Pass requiring authorization."""
        pao_group = self.env.ref('mesob_inventory_base.group_mesob_pao', raise_if_not_found=False)
        if pao_group and pao_group.users:
            gate_pass._schedule_activity(
                activity_code='mesob_activity_gate_pass_authorization',
                user_ids=pao_group.users.ids,
                summary=_('Gate Pass Authorization Required: %s') % gate_pass.name,
                note=_(
                    '<p><strong>Receiver:</strong> %s</p>'
                    '<p><strong>Destination:</strong> %s</p>'
                    '<p><strong>Items:</strong> %d</p>'
                ) % (
                    gate_pass.receiver_name,
                    gate_pass.destination,
                    len(gate_pass.line_ids),
                ),
            )

    def _notify_security_gate_pass_dispatch(self, gate_pass):
        """Notify Security of authorized Gate Pass ready for dispatch."""
        security_group = self.env.ref('mesob_inventory_base.group_mesob_security_guard', raise_if_not_found=False)
        if security_group and security_group.users:
            gate_pass._schedule_activity(
                activity_code='mesob_activity_gate_pass_authorization',  # Reuse same activity type
                user_ids=security_group.users.ids,
                summary=_('Gate Pass Ready for Dispatch: %s') % gate_pass.name,
                note=_(
                    '<p><strong>Status:</strong> Authorized - Ready to Dispatch</p>'
                    '<p><strong>Receiver:</strong> %s</p>'
                    '<p><strong>Destination:</strong> %s</p>'
                ) % (
                    gate_pass.receiver_name,
                    gate_pass.destination,
                ),
            )

    def _notify_reorder_alert(self, alert):
        """Notify Procurement of reorder alert."""
        procurement_group = self.env.ref('mesob_inventory_base.group_mesob_procurement', raise_if_not_found=False)
        if procurement_group and procurement_group.users:
            alert._schedule_activity(
                activity_code='mesob_activity_reorder_alert',
                user_ids=procurement_group.users.ids,
                summary=_('Stock Reorder Alert: %s') % alert.item_id.name,
                note=_(
                    '<p><strong>Item:</strong> %s</p>'
                    '<p><strong>Current Stock:</strong> %s</p>'
                    '<p><strong>Reorder Level:</strong> %s</p>'
                    '<p><strong>Suggested Order Qty:</strong> %s</p>'
                ) % (
                    alert.item_id.name,
                    alert.current_quantity,
                    alert.reorder_level,
                    alert.suggested_order_quantity,
                ),
            )

    def _notify_po_overdue(self, po):
        """Notify Procurement Officer of overdue PO."""
        procurement_group = self.env.ref('mesob_inventory_base.group_mesob_procurement', raise_if_not_found=False)
        if procurement_group and procurement_group.users:
            po._schedule_activity(
                activity_code='mesob_activity_po_overdue',
                user_ids=procurement_group.users.ids,
                summary=_('Overdue PO: %s') % po.name,
                note=_(
                    '<p><strong>Supplier:</strong> %s</p>'
                    '<p><strong>Expected Date:</strong> %s</p>'
                    '<p><strong>Days Overdue:</strong> %s</p>'
                ) % (
                    po.supplier_id.name if hasattr(po, 'supplier_id') else 'N/A',
                    po.expected_date if hasattr(po, 'expected_date') else 'N/A',
                    (fields.Date.today() - po.expected_date).days if hasattr(po, 'expected_date') and po.expected_date else 'N/A',
                ),
            )

    def _notify_manual_adjustment_approval(self, bin_card):
        """Notify PAO of manual stock adjustment requiring approval."""
        pao_group = self.env.ref('mesob_inventory_base.group_mesob_pao', raise_if_not_found=False)
        if pao_group and pao_group.users:
            bin_card._schedule_activity(
                activity_code='mesob_activity_manual_adjustment_approval',
                user_ids=pao_group.users.ids,
                summary=_('Manual Stock Adjustment Approval Required'),
                note=_(
                    '<p><strong>Item:</strong> %s</p>'
                    '<p><strong>Adjustment:</strong> %s</p>'
                    '<p><strong>Reason:</strong> %s</p>'
                ) % (
                    bin_card.item_id.name,
                    bin_card.quantity,
                    bin_card.adjustment_reason or 'Not specified',
                ),
            )

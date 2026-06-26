# -*- coding: utf-8 -*-
"""
Auto-Registration Hooks for Asset Register

Automatically registers items to the Asset Register when:
1. New item is created
2. Item is issued to a user
3. Item is received
"""
from odoo import models, api


class MesobInventoryItemAutoRegister(models.Model):
    """Extend Inventory Item to auto-register to Asset Register"""
    _inherit = 'mesob.inventory.item'
    
    @api.model_create_multi
    def create(self, vals_list):
        """Auto-register new items to Asset Register"""
        items = super().create(vals_list)
        
        # Auto-register each new item
        AssetRegister = self.env['mesob.asset.dashboard']
        for item in items:
            AssetRegister._auto_register_item(item.id)
        
        return items


class MesobInventoryIssueVoucherAutoRegister(models.Model):
    """Extend Issue Voucher to auto-register items when issued"""
    _inherit = 'mesob.inventory.issue.voucher'
    
    def action_issue(self):
        """Auto-register items when issued"""
        result = super().action_issue()
        
        # Auto-register all items in this voucher
        AssetRegister = self.env['mesob.asset.dashboard']
        for line in self.line_ids:
            AssetRegister._auto_register_item(line.item_id.id)
        
        return result


class MesobInventoryReceivingAutoRegister(models.Model):
    """Extend Receiving to auto-register items when received"""
    _inherit = 'mesob.inventory.receiving'
    
    def action_accept(self):
        """Auto-register items when received and accepted"""
        result = super().action_accept()
        
        # Auto-register all items in this receiving
        AssetRegister = self.env['mesob.asset.dashboard']
        for line in self.line_ids:
            if line.sub_classification_id and line.sub_classification_id.item_ids:
                for item in line.sub_classification_id.item_ids:
                    AssetRegister._auto_register_item(item.id)
        
        return result

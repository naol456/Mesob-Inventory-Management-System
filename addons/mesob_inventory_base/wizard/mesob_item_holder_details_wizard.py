# -*- coding: utf-8 -*-
from odoo import api, fields, models


class MesobItemHolderDetailsWizard(models.TransientModel):
    """Wizard to display item holder and classification details"""
    _name = 'mesob.item.holder.details.wizard'
    _description = 'Item Holder Details'

    item_id = fields.Many2one('mesob.inventory.item', string='Item', required=True)
    
    # Requisition Information
    requested_by = fields.Char(string='Requested By', readonly=True)
    department = fields.Char(string='Department', readonly=True)
    
    # Classification Information
    major_classification = fields.Char(string='Major Classification', readonly=True)
    sub_classification = fields.Char(string='Sub Classification', readonly=True)
    major_code = fields.Char(string='Major Code', readonly=True)
    sub_code = fields.Char(string='Sub Code', readonly=True)
    specific_code = fields.Char(string='Specific Code', readonly=True)
    full_item_code = fields.Char(string='Full Item Code', readonly=True)

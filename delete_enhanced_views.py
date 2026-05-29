#!/usr/bin/env python3
"""
Script to delete enhanced views from Odoo database
Run with: docker-compose exec odoo python3 /mnt/extra-addons/delete_enhanced_views.py
"""

import xmlrpc.client

# Odoo connection details
url = 'http://localhost:8069'
db = 'odoo'
username = 'admin'
password = 'admin'  # Change if different

# Connect to Odoo
common = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/common')
uid = common.authenticate(db, username, password, {})

if uid:
    models = xmlrpc.client.ServerProxy(f'{url}/xmlrpc/2/object')
    
    # Delete enhanced views
    view_names = [
        'mesob.inventory.issue.voucher.form.enhanced',
        'mesob.inventory.requisition.form.enhanced',
        'mesob.inventory.receiving.form.enhanced',
    ]
    
    for view_name in view_names:
        view_ids = models.execute_kw(db, uid, password,
            'ir.ui.view', 'search',
            [[['name', '=', view_name]]])
        
        if view_ids:
            models.execute_kw(db, uid, password,
                'ir.ui.view', 'unlink',
                [view_ids])
            print(f"✓ Deleted view: {view_name}")
        else:
            print(f"- View not found: {view_name}")
    
    print("\n✓ Done! Now try upgrading the module.")
else:
    print("✗ Authentication failed. Check username/password.")

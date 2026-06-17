#!/usr/bin/env python3
"""
Clear Odoo Web Assets Cache
Run this with: python clear_odoo_cache.py --database YOUR_DB_NAME
"""

import sys
import argparse

# Add Odoo to path
sys.path.insert(0, r'C:\Program Files\Odoo 19.0.20260218\server')

import odoo
from odoo import api, SUPERUSER_ID

def clear_assets_cache(db_name):
    """Clear web assets cache from Odoo database"""
    
    odoo.tools.config.parse_config(['-d', db_name, '--no-http'])
    
    with odoo.api.Environment.manage():
        registry = odoo.registry(db_name)
        with registry.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            
            # Clear compiled assets
            attachments = env['ir.attachment'].search([
                '|', '|',
                ('res_model', '=', 'ir.ui.view'),
                ('name', 'ilike', 'web_assets%'),
                ('name', 'ilike', 'web.assets%'),
            ])
            
            count = len(attachments)
            if attachments:
                attachments.unlink()
                print(f"✓ Cleared {count} cached asset attachments")
            else:
                print("✓ No cached assets found")
            
            # Clear QWeb cache
            env['ir.qweb'].clear_caches()
            print("✓ Cleared QWeb caches")
            
            # Clear model caches  
            env.registry.clear_caches()
            print("✓ Cleared registry caches")
            
            cr.commit()
            print(f"\n✓ Cache cleared successfully for database: {db_name}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Clear Odoo assets cache')
    parser.add_argument('--database', '-d', required=True, help='Database name')
    args = parser.parse_args()
    
    try:
        clear_assets_cache(args.database)
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)

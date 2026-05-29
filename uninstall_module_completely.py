#!/usr/bin/env python3
"""
Complete module uninstallation script
This removes ALL traces of the module from the database
"""

import psycopg2
import sys

# Database connection
conn = psycopg2.connect(
    host="localhost",
    port="5432",
    database="mesob",
    user="odoo",
    password="odoo"
)

try:
    cur = conn.cursor()
    
    print("🔍 Finding all views related to mesob_inventory_base...")
    
    # Find all views from this module
    cur.execute("""
        SELECT v.id, v.name, v.model
        FROM ir_ui_view v
        JOIN ir_model_data d ON d.res_id = v.id AND d.model = 'ir.ui.view'
        WHERE d.module = 'mesob_inventory_base'
        ORDER BY v.id;
    """)
    
    views = cur.fetchall()
    print(f"Found {len(views)} views:")
    for view_id, name, model in views:
        print(f"  - View {view_id}: {name} ({model})")
    
    # Delete all views
    if views:
        view_ids = [v[0] for v in views]
        cur.execute(f"DELETE FROM ir_ui_view WHERE id IN ({','.join(map(str, view_ids))})")
        print(f"✓ Deleted {len(views)} views")
    
    # Delete all model data entries
    cur.execute("DELETE FROM ir_model_data WHERE module = 'mesob_inventory_base'")
    deleted_data = cur.rowcount
    print(f"✓ Deleted {deleted_data} model data entries")
    
    # Set module to uninstalled
    cur.execute("""
        UPDATE ir_module_module 
        SET state = 'uninstalled' 
        WHERE name = 'mesob_inventory_base'
    """)
    print("✓ Set module state to 'uninstalled'")
    
    # Commit changes
    conn.commit()
    print("\n✅ Module completely removed from database!")
    print("Now you can do a fresh install from Odoo UI")
    
except Exception as e:
    conn.rollback()
    print(f"❌ Error: {e}")
    sys.exit(1)
finally:
    cur.close()
    conn.close()

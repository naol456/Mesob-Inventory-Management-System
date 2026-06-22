#!/usr/bin/env python3
"""
Script to add the missing requester_role column to mesob_inventory_requisition table.
This is needed when a stored computed field is added to the model but the database
schema hasn't been updated yet.
"""

import psycopg2
from psycopg2 import sql

# Database connection parameters
DB_HOST = 'localhost'
DB_PORT = '5432'
DB_NAME = 'MESOB_PRO'
DB_USER = 'odoo'
DB_PASSWORD = 'odoo'  # Update this with your actual password

def add_requester_role_column():
    """Add requester_role column if it doesn't exist."""
    try:
        # Connect to the database
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        conn.autocommit = True
        cursor = conn.cursor()
        
        # Check if column exists
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='mesob_inventory_requisition' 
            AND column_name='requester_role'
        """)
        
        if cursor.fetchone():
            print("✓ Column 'requester_role' already exists.")
            return
        
        # Add the column
        print("Adding 'requester_role' column...")
        cursor.execute("""
            ALTER TABLE mesob_inventory_requisition 
            ADD COLUMN requester_role VARCHAR;
        """)
        
        # Set default value for existing records
        print("Setting default values for existing records...")
        cursor.execute("""
            UPDATE mesob_inventory_requisition 
            SET requester_role = 'staff' 
            WHERE requester_role IS NULL;
        """)
        
        print("✓ Column added successfully!")
        print("✓ Default values set for existing records.")
        print("\nNext steps:")
        print("1. Restart your Odoo server")
        print("2. Upgrade the mesob_inventory_base module")
        print("3. The computed values will be recalculated automatically")
        
    except psycopg2.Error as e:
        print(f"✗ Database error: {e}")
        print("\nPlease check:")
        print("- Database credentials are correct")
        print("- PostgreSQL server is running")
        print("- You have permission to alter the table")
        
    finally:
        if 'conn' in locals():
            cursor.close()
            conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("Adding requester_role column to mesob_inventory_requisition")
    print("=" * 60)
    print()
    add_requester_role_column()

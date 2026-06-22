# -*- coding: utf-8 -*-
"""
Migration script for Mesob Inventory Base v19.0.1.6.0
AUTO-009: Add supplier performance scoring fields to res.partner

This pre-migration script adds new columns to res_partner table before
the module update loads the new model definitions.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Add new columns for AUTO-009 supplier performance scoring."""
    
    _logger.info("AUTO-009 Migration: Adding supplier performance fields to res_partner")
    
    # List of new columns to add
    new_columns = [
        ('on_time_delivery_rate', 'NUMERIC'),
        ('dsr_rejection_rate', 'NUMERIC'),
        ('complaint_count', 'INTEGER'),
        ('total_pos_count', 'INTEGER'),
        ('performance_rating', 'VARCHAR'),
        ('last_score_update', 'TIMESTAMP'),
    ]
    
    for column_name, column_type in new_columns:
        # Check if column already exists
        cr.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='res_partner' 
            AND column_name=%s
        """, (column_name,))
        
        if not cr.fetchone():
            # Column doesn't exist, add it
            _logger.info(f"  Adding column: {column_name} ({column_type})")
            
            if column_type == 'NUMERIC':
                cr.execute(f"""
                    ALTER TABLE res_partner 
                    ADD COLUMN {column_name} NUMERIC DEFAULT 0.0
                """)
            elif column_type == 'INTEGER':
                cr.execute(f"""
                    ALTER TABLE res_partner 
                    ADD COLUMN {column_name} INTEGER DEFAULT 0
                """)
            elif column_type == 'VARCHAR':
                cr.execute(f"""
                    ALTER TABLE res_partner 
                    ADD COLUMN {column_name} VARCHAR
                """)
            elif column_type == 'TIMESTAMP':
                cr.execute(f"""
                    ALTER TABLE res_partner 
                    ADD COLUMN {column_name} TIMESTAMP
                """)
        else:
            _logger.info(f"  Column {column_name} already exists, skipping")
    
    _logger.info("AUTO-009 Migration: Supplier performance fields added successfully")

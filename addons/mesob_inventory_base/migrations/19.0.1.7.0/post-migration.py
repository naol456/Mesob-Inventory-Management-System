# -*- coding: utf-8 -*-
"""Migration script to remove duplicate procurement lots."""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    """Remove duplicate procurement plan lots keeping only the oldest one."""
    _logger.info("Starting migration: Removing duplicate procurement plan lots")
    
    # Find and delete duplicate lots, keeping only the first (oldest) one for each (plan_id, name) combination
    cr.execute("""
        DELETE FROM mesob_procurement_plan_lot
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM mesob_procurement_plan_lot
            GROUP BY plan_id, name
        )
    """)
    
    deleted_count = cr.rowcount
    _logger.info(f"Migration complete: Removed {deleted_count} duplicate procurement plan lots")

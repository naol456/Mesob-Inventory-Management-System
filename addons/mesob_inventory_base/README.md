# Mesob Inventory Management System

**Version:** 19.0.1.11.0  
**Odoo Version:** 19.0  
**License:** LGPL-3

## Overview

Complete inventory management system for Mesob One-Stop Service implementing all features from the Software Requirements Specification (SRS).

## Features Implemented

- ✅ 4.1 Stock Identification (Classification & Coding)
- ✅ 4.2 Receiving & Inspection
- ✅ 4.3 Issue of Stocks
- ✅ 4.4 Dispatch Outside Organization (Gate Pass)
- ✅ 4.5 Stock Records (Bin Cards & Stock Record Cards)
- ✅ 4.6 Stock Accounting & Valuation (FIFO)
- ✅ 4.7 Reporting
- ✅ 4.8 Stock Taking & Discrepancy Handling
- ✅ 4.9 Stocks Handing/Taking-Over

## Installation

1. Copy this module to your Odoo addons directory
2. Restart Odoo server
3. Update Apps List
4. Install "Mesob Inventory Base"

## Upgrade

```bash
cd "C:\Program Files\Odoo 19.0.20260218\server"
python odoo-bin -d your_database -u mesob_inventory_base --stop-after-init
```

## Access Handover Feature

The handover feature can be accessed via:
- Direct URL: `http://localhost:8069/web#action=mesob_inventory_base.action_mesob_handover_event`
- Search: Type "Storekeeper Handovers" in Odoo search

To enable the menu item, uncomment the menu in `views/mesob_inventory_menus.xml` (line 158) and restart the server.

## User Roles

- **PAO (Property Administration Officer):** Full access
- **Storekeeper:** Daily operations
- **Stock Clerk:** Stock records maintenance
- **Requester:** Create requisitions

## Documentation

- **SRS:** `material/srs.md` - Software Requirements Specification

## Support

For issues or questions, contact Mesob Center IT Support.

---

**Author:** Mesob Center  
**Date:** May 2026

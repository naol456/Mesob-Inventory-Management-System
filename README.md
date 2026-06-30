# Mesob Inventory Management System (Odoo 19)

This repository contains **custom addons** for an FDRE-compliant inventory management system built on Odoo 19.

## Repo layout
- `addons/`: custom Odoo modules (loaded via `--addons-path`)
- `specs/`: tracked project specs/checklists (FDRE-first)
- `docs/`: untracked working documents (ignored by `.gitignore` per project rule)
- `tools/`: helper scripts

## Workflow
See `specs/Development-Workflow-Notion.md`.


## Test/Demo Accounts

**⚠️ SECURITY WARNING: FOR DEVELOPMENT/TESTING ONLY ⚠️**

Demo accounts are available in the demo data. These accounts **MUST BE DISABLED OR DELETED** before production deployment.

**NEVER use these credentials in a production environment.**

For production deployment instructions, see [deployment/README.md](deployment/README.md)





<!-- if you want to run it with XML auto-reload for development -->

<!-- python odoo-19/odoo-bin -c odoo.conf --dev=xml

 -->

 <!-- to run and upgrade at same time -->

 <!-- python odoo-19/odoo-bin -c odoo.conf -u mesob_inventory_base -d mesob_inventory -->




# Mesob Inventory Management System (Odoo 19)

This repository contains **custom addons** for an FDRE-compliant inventory management system built on Odoo 19.

## Repo layout
- `addons/`: custom Odoo modules (loaded via `--addons-path`)
- `specs/`: tracked project specs/checklists (FDRE-first)
- `docs/`: untracked working documents (ignored by `.gitignore` per project rule)
- `tools/`: helper scripts

## Workflow
See `specs/Development-Workflow-Notion.md`.


MESOB INVENTORY TEST ACCOUNTS
==============================

PAO Account:
  Email: pao@mesob.local
  Password: Pao123
  

Storekeeper Account:
  Email: store@mesob.local
  Password: Store123
  

Stock Clerk Account:
  Email: clerk@mesob.local
  Password: Clerk123
  

Regular User Account:
  Email: user@mesob.local
  Password: User123





<!-- if you want to run it with XML auto-reload for development -->

<!-- python odoo-19/odoo-bin -c odoo.conf --dev=xml

 -->

 <!-- to run and upgrade at same time -->

 <!-- python odoo-19/odoo-bin -c odoo.conf -u mesob_inventory_base -d mesob_inventory -->




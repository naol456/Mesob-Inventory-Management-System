# Issue of Stocks - Architecture Overview

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     User Interface Layer                     │
├─────────────────────────────────────────────────────────────┤
│  Requisition Views  │  Issue Voucher Views  │  Receipt Wizard│
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Business Logic Layer                      │
├─────────────────────────────────────────────────────────────┤
│  Requisition Model  │  Issue Voucher Model  │  Receipt Wizard│
│  - Workflow         │  - Stock Validation   │  - Verification│
│  - Approval         │  - Picking Creation   │  - Confirmation│
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Integration Layer                         │
├─────────────────────────────────────────────────────────────┤
│  Stock Module       │  Mail Module          │  Security      │
│  - stock.picking    │  - mail.thread        │  - Groups      │
│  - stock.move       │  - mail.activity      │  - Rules       │
│  - stock.quant      │  - Audit Trail        │  - Access      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Data Layer                              │
├─────────────────────────────────────────────────────────────┤
│  Requisition Table  │  Issue Voucher Table  │  Item Table    │
│  - Header           │  - Header             │  - Master Data │
│  - Lines            │  - Lines              │  - Product Link│
└─────────────────────────────────────────────────────────────┘
```

## Data Model

```
mesob_inventory_item
├── item_code (PK)
├── is_controlled
└── product_id (FK) ──────┐
                          │
mesob_inventory_requisition    │
├── id (PK)                    │
├── state                      │
└── issue_voucher_ids ─────┐   │
                           │   │
mesob_inventory_issue_voucher  │
├── id (PK)                │   │
├── requisition_id (FK) ───┘   │
├── picking_id (FK) ───────────┼──┐
└── line_ids ──────────────┐   │  │
                           │   │  │
mesob_inventory_issue_voucher_line
├── id (PK)                │   │  │
├── voucher_id (FK) ───────┘   │  │
└── item_id (FK) ──────────────┘  │
                                  │
stock_picking                     │
├── id (PK) ──────────────────────┘
└── move_ids
```

## Workflow States

```
Requisition:  draft → submitted → approved → issued → received
                 ↓         ↓
              cancelled  rejected

Issue Voucher: draft → issued → received
                 ↓
              cancelled
```

## Security Model

```
PAO (Property Admin Officer)
├── Approve/Reject Requisitions
├── Full Access to All Records
└── Override Capabilities

Storekeeper
├── View Approved Requisitions
├── Create Issue Vouchers
└── Issue Materials

Stock Clerk
├── View All Records
└── Post to Stock Records

Department User
├── Create Own Requisitions
├── View Own Requisitions
└── Confirm Receipt
```

{
    "name": "Mesob Inventory Management System",
    "version": "19.0.1.5.0",
    "category": "Inventory/Inventory",
    "summary": "FDRE Mesob Center - Complete inventory management system with "
               "classifications (4401–4418), requisitions, receiving, inspection, "
               "Model 19, DSR, Gate Pass & Dispatch Control.",
    "description": """
        Mesob Inventory Management System
        ==================================
        
        Complete inventory management solution for FDRE Mesob Center
        
        Features:
        ---------
        * Item Master with Major/Sub Classifications (4401-4418)
        * Store Requisition (Model 20)
        * Receiving & Inspection Voucher
        * Issue Voucher (Model 19)
        * Daily Stock Register (DSR)
        * Gate Pass & Dispatch Control
        * Bin Card & Stock Record Card
        * Reorder Alert System
        * FDRE-compliant stock control
        * Four-copy document distribution
        
        Developed for FDRE Mesob Center
        Federal Democratic Republic of Ethiopia
    """,
    "author": "FDRE Mesob Center",
    "website": "https://id.gov.et",
    "license": "LGPL-3",
    "depends": ["stock", "mail"],
    "data": [
        # Security (load first)
        "security/mesob_inventory_groups.xml",
        "security/ir.model.access.csv",
        "security/mesob_inventory_record_rules.xml",
        "security/mesob_gate_pass_rules.xml",
        # Seed / reference data
        "data/mesob_major_classification_data.xml",
        "data/mesob_requisition_sequence.xml",
        "data/mesob_receiving_sequence.xml",
        "data/mesob_issue_voucher_sequence.xml",
        "data/mesob_gate_pass_sequence.xml",
        "data/mesob_reorder_alert_sequence.xml",
        # Company data
        "data/mesob_company_data.xml",
        # Assets (Modern UI Styles)
        "views/mesob_inventory_assets.xml",
        # Custom Login Layout
        "views/mesob_login_template.xml",
        # Views (Base)
        "views/mesob_inventory_major_classification_views.xml",
        "views/mesob_inventory_sub_classification_views.xml",
        "views/mesob_inventory_item_views.xml",
        "views/mesob_inventory_requisition_views.xml",
        "views/mesob_inventory_receiving_views.xml",
        "views/mesob_inventory_receiving_views_simplified.xml",
        "views/mesob_inventory_model19_views.xml",
        "views/mesob_inventory_dsr_views.xml",
        "views/mesob_inventory_issue_voucher_views.xml",
        "views/mesob_gate_pass_views.xml",
        "views/mesob_bin_card_views.xml",
        "views/mesob_stock_record_card_views.xml",
        "views/mesob_stock_reorder_alert_views.xml",
        # Menus
        "views/mesob_inventory_menus.xml",
        # Wizards
        "wizard/mesob_inventory_issue_receipt_wizard_views.xml",
        "wizard/mesob_abc_classification_wizard_views.xml",
        # Reports
        "reports/mesob_gate_pass_report.xml",
    ],
    "demo": [],
    "installable": True,
    "application": True,
}

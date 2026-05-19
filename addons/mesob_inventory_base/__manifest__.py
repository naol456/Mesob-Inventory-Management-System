{
    "name": "Mesob Inventory Base",
    "version": "19.0.1.3.0",
    "category": "Inventory",
    "summary": "Foundation module for Mesob One-Stop Service inventory management — "
               "item master, classifications (4401–4418), requisitions (Model 20), "
               "receiving & inspection, Model 19, DSR, Gate Pass & Dispatch Control, "
               "and FDRE-compliant stock control parameters.",
    "author": "Mesob Center",
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
        # Assets (Modern UI Styles)
        "views/mesob_inventory_assets.xml",
        # Views (Base)
        "views/mesob_inventory_major_classification_views.xml",
        "views/mesob_inventory_item_views.xml",
        "views/mesob_inventory_requisition_views.xml",
        "views/mesob_inventory_receiving_views.xml",
        "views/mesob_inventory_receiving_views_simplified.xml",
        "views/mesob_inventory_model19_views.xml",
        "views/mesob_inventory_dsr_views.xml",
        "views/mesob_inventory_issue_voucher_views.xml",
        "views/mesob_gate_pass_views.xml",
        # Enhanced Views
        "views/mesob_inventory_requisition_views_enhanced.xml",
        "views/mesob_inventory_issue_voucher_views_enhanced.xml",
        "views/mesob_inventory_receiving_views_enhanced.xml",
        # Menus
        "views/mesob_inventory_menus.xml",
        # Wizards
        "wizard/mesob_inventory_issue_receipt_wizard_views.xml",
        # Reports
        "reports/mesob_gate_pass_report.xml",
    ],
    "demo": [],
    "installable": True,
    "application": True,
}

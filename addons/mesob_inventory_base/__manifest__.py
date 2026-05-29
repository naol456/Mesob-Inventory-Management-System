{
    "name": "Mesob Inventory Base",
    "version": "19.0.1.11.0",
    "category": "Inventory",
    "summary": "Foundation module for Mesob One-Stop Service inventory management — "
               "item master, classifications (4401–4418), requisitions (Model 20), "
               "receiving & inspection, Model 19, DSR, "
               "Bin Cards, Stock Record Cards with FIFO valuation, "
               "Stock Accounting & Valuation Reports, "
               "Reporting (Movement, Dormant Stock, Fiscal Year End), "
               "Stock Taking & Discrepancy Handling, "
               "Storekeeper Handover & Taking-Over, "
               "and FDRE-compliant stock control parameters.",
    "author": "Mesob Center",
    "license": "LGPL-3",
    "depends": ["stock"],
    "data": [
        # Security Groups (load first - no model dependencies)
        "security/mesob_inventory_groups.xml",
        # Seed / reference data
        "data/mesob_major_classification_data.xml",
        "data/mesob_requisition_sequence.xml",
        "data/mesob_receiving_sequence.xml",
        "data/mesob_stock_taking_sequence.xml",
        "data/mesob_handover_sequence.xml",
        # Assets (Modern UI Styles)
        "views/mesob_inventory_assets.xml",
        # Views (Base)
        "views/mesob_inventory_major_classification_views.xml",
        "views/mesob_inventory_item_views.xml",
        "views/mesob_inventory_requisition_views.xml",
        "views/mesob_inventory_receiving_views.xml",
        "views/mesob_inventory_model19_views.xml",
        "views/mesob_inventory_dsr_views.xml",
        # Stock Records (Bin Card & Stock Record Card)
        "views/mesob_inventory_bin_card_views.xml",
        "views/mesob_inventory_stock_record_card_views.xml",
        # Stock Valuation Reports (SRS 4.6)
        "views/mesob_inventory_stock_valuation_views.xml",
        # Stock Valuation Security (loaded after views to ensure models exist)
        "security/mesob_stock_valuation_security.xml",
        # Reporting (SRS 4.7)
        "views/mesob_inventory_reports_views.xml",
        # Stock Taking (SRS 4.8)
        "views/mesob_inventory_stock_taking_event_views.xml",
        "views/mesob_inventory_stock_taking_sheet_views.xml",
        # Handover (SRS 4.9)
        "views/mesob_inventory_handover_views.xml",
        # Enhanced Views
        "views/mesob_inventory_item_views_enhanced.xml",
        "views/mesob_inventory_requisition_views_enhanced.xml",
        "views/mesob_inventory_receiving_views_enhanced.xml",
        "views/mesob_inventory_dsr_views_enhanced.xml",
        "views/mesob_inventory_model19_views_enhanced.xml",
        # Dashboard
        "views/mesob_inventory_dashboard.xml",
        # Menus
        "views/mesob_inventory_menus.xml",
        # Security (loaded after views to ensure models exist)
        "security/ir.model.access.csv",
        "security/mesob_inventory_record_rules.xml",
        # Reports Security (loaded after menus to ensure actions exist)
        "security/mesob_reports_security.xml",
        # Stock Taking Security (loaded after menus to ensure actions exist)
        "security/mesob_stock_taking_security.xml",
        # Handover Security (loaded after menus to ensure actions exist)
        "security/mesob_handover_security.xml",
        # Wizards
        "wizard/mesob_inventory_issue_receipt_wizard_views.xml",
    ],
    "demo": [],
    "installable": True,
    "application": True,
}

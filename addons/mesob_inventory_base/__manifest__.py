{
    "name": "Mesob Inventory Management System",
    "version": "19.0.1.7.0",
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
    "website": "https://mesobcenter.et",
    "license": "LGPL-3",
    "depends": ["stock", "mail"],
    "data": [
        # Security (load first)
        "security/mesob_inventory_groups.xml",
        "security/ir.model.access.csv",
        "security/mesob_inventory_record_rules.xml",
        "security/mesob_gate_pass_rules.xml",
        # Root Menu
        "views/mesob_inventory_root_menu.xml",
        # Seed / reference data
        "data/mesob_major_classification_data.xml",
        "data/mesob_department_data.xml",
        "data/mesob_requisition_sequence.xml",
        "data/mesob_receiving_sequence.xml",
        "data/mesob_issue_voucher_sequence.xml",
        "data/mesob_gate_pass_sequence.xml",
        "data/mesob_reorder_alert_sequence.xml",
        "data/mesob_procurement_sequences.xml",
        # Company data
        "data/mesob_company_data.xml",
        # Views (Base)
        "views/mesob_inventory_major_classification_views.xml",
        "views/mesob_inventory_sub_classification_views.xml",
        "views/mesob_department_views.xml",
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
        "views/mesob_procurement_views.xml",
        "views/mesob_supplier_views.xml",
        "views/mesob_stock_taking_handover_views.xml",
        "views/mesob_storage_security_views.xml",
        "views/mesob_inventory_dashboard_views.xml",
        "views/mesob_analytics_dashboard_views.xml",
        "views/mesob_asset_dashboard_views.xml",
        "views/mesob_asset_map_dashboard.xml",
        # Login customization
        "views/mesob_login_template.xml",
        # Menus
        "views/mesob_inventory_menus.xml",
        # Wizards
        "wizard/mesob_inventory_issue_receipt_wizard_views.xml",
        "wizard/mesob_abc_classification_wizard_views.xml",
        "wizard/mesob_item_holder_details_wizard_view.xml",
        # Reports
        "reports/mesob_gate_pass_report.xml",
    ],
    "demo": [],
    "assets": {
        "web.assets_backend": [
            "mesob_inventory_base/static/src/scss/variables.scss",
            "mesob_inventory_base/static/src/scss/glass_theme.scss",
            "mesob_inventory_base/static/src/scss/buttons.scss",
            "mesob_inventory_base/static/src/scss/forms.scss",
            "mesob_inventory_base/static/src/scss/lists.scss",
            "mesob_inventory_base/static/src/scss/kanban.scss",
            "mesob_inventory_base/static/src/scss/modals.scss",
            "mesob_inventory_base/static/src/scss/navbar.scss",
            "mesob_inventory_base/static/src/scss/analytics_menu.scss",
            "mesob_inventory_base/static/src/scss/stock_records_premium.scss",
            "mesob_inventory_base/static/src/scss/procurement_premium.scss",
            "mesob_inventory_base/static/src/scss/asset_dashboard_premium.scss",
            "mesob_inventory_base/static/src/scss/asset_map_dashboard.scss",
            "mesob_inventory_base/static/src/js/navbar_sidebar.js",
            "mesob_inventory_base/static/src/js/analytics_menu.js",
            "mesob_inventory_base/static/src/xml/apps_sidebar.xml",
        ],
        "web.assets_frontend": [
            "mesob_inventory_base/static/src/scss/mesob_login.scss",
        ],
        "web.assets_backend_lazy": [
            "mesob_inventory_base/static/src/js/canvas_text.js",
        ],
    },
    "installable": True,
    "application": True,
}

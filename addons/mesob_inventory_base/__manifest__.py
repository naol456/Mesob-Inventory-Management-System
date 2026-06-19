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
        # Root Menu
        "views/mesob_inventory_root_menu.xml",
        # Seed / reference data
        "data/mesob_major_classification_data.xml",
        "data/mesob_requisition_sequence.xml",
        "data/mesob_receiving_sequence.xml",
        "data/mesob_issue_voucher_sequence.xml",
        "data/mesob_gate_pass_sequence.xml",
        "data/mesob_reorder_alert_sequence.xml",
        "data/mesob_procurement_sequences.xml",
        "data/mesob_payment_validation_sequence.xml",
        "data/mesob_catalog_publication_sequence.xml",
        "data/mesob_overdue_po_cron.xml",
        "data/mesob_auto_reorder_cron.xml",
        "data/mesob_notification_activity_types.xml",  # Task 7: Activity types for notifications
        "data/mesob_dashboard_kpi_cron.xml",  # Task 12: KPI refresh cron
        # Company data
        "data/mesob_company_data.xml",
        # Views (Base)
        "views/mesob_inventory_major_classification_views.xml",
        "views/mesob_inventory_sub_classification_views.xml",
        "views/mesob_inventory_item_views.xml",
        # TODO: Fix stock code catalog views - has validation issues
        # "views/mesob_stock_code_catalog_views.xml",
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
        # Menus (must be loaded before views that reference menu parents)
        "views/mesob_inventory_menus.xml",
        "views/mesob_budget_views.xml",
        "views/mesob_procurement_views.xml",
        # TODO: Fix stock code catalog publication views - model not loaded
        # "views/mesob_stock_code_catalog_publication_views.xml",
        "views/mesob_stock_taking_handover_views.xml",
        "views/mesob_storage_security_views.xml",
        "views/mesob_inventory_dashboard_views.xml",
        "views/mesob_dashboard_enhanced_views.xml",  # Task 12: Enhanced dashboards
        # Login customization
        "views/mesob_login_template.xml",
        # Wizards
        "wizard/mesob_inventory_issue_receipt_wizard_views.xml",
        "wizard/mesob_abc_classification_wizard_views.xml",
        # TODO: Fix wizard views - models not loaded
        # "wizard/mesob_fiscal_year_valuation_wizard_views.xml",
        # "wizard/mesob_requisition_stock_alert_wizard_views.xml",
        "wizard/mesob_procurement_need_reject_wizard_views.xml",
        "wizard/mesob_intelligent_consolidation_wizard_views.xml",
        "wizard/mesob_gate_pass_override_wizard_views.xml",  # AUTO-046
        "wizard/mesob_manual_adjustment_wizard_views.xml",  # AUTO-050
        "wizard/mesob_duplicate_item_wizard_views.xml",  # AUTO-038
        "wizard/mesob_quarterly_movement_report_wizard_views.xml",  # AUTO-054
        "wizard/mesob_gate_pass_extend_wizard_views.xml",  # AUTO-048
        "wizard/mesob_barcode_scanner_wizard_views.xml",  # Task 9
        # Notification preferences (Task 7)
        "views/mesob_notification_preference_views.xml",
        # Digital Signatures (Task 11)
        "views/mesob_digital_signature_views.xml",
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
            "mesob_inventory_base/static/src/js/navbar_sidebar.js",
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

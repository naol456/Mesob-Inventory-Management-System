{
    "name": "Mesob Inventory Base",
    "version": "19.0.1.2.0",
    "category": "Inventory",
    "summary": "Foundation module for Mesob One-Stop Service inventory management — "
               "item master, classifications (4401–4418), requisitions (Model 20), "
               "receiving & inspection, Model 19, DSR, "
               "and FDRE-compliant stock control parameters.",
    "author": "Mesob Center",
    "license": "LGPL-3",
    "depends": ["stock"],
    "data": [
        # Security (load first)
        "security/mesob_inventory_groups.xml",
        "security/ir.model.access.csv",
        # Seed / reference data
        "data/mesob_major_classification_data.xml",
        "data/mesob_requisition_sequence.xml",
        "data/mesob_receiving_sequence.xml",
        # Views
        "views/mesob_inventory_major_classification_views.xml",
        "views/mesob_inventory_item_views.xml",
        "views/mesob_inventory_requisition_views.xml",
        "views/mesob_inventory_receiving_views.xml",
        "views/mesob_inventory_model19_views.xml",
        "views/mesob_inventory_dsr_views.xml",
        "views/mesob_inventory_menus.xml",
    ],
    "demo": [],
    "installable": True,
    "application": True,
}

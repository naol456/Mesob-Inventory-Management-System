{
    'name': 'Mesob Stock Taking',
    'version': '2.0',
    'category': 'Inventory',
    'summary': 'Stock Taking, Handover, Control & Reporting for Mesob',
    'description': '''
        Implements SRS Sections 4.7–4.10:
        - 4.7  Reporting (Discrepancy Report, Pivot, Graph)
        - 4.8  Stock Taking & Discrepancy Handling
        - 4.9  Stocks Handover / Takeover Certificate
        - 4.10 Stock Control Levels & Alerts (ABC, Min/Max/Reorder)
    ''',
    'author': 'Martha Tesema',
    'license': 'LGPL-3',
    'depends': ['stock', 'mail', 'mesob_inventory_base'],
    'data': [
        'security/ir.model.access.csv',
        'data/sequence.xml',
        'views/mesob_stock_taking_views.xml',
    ],
    'installable': True,
    'application': False,
}

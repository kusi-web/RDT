{
    'name': 'Stock Removal Transfer',
    'version': '1.0',
    'category': 'Inventory',
    'summary': 'Automatic transfer of products based on removal date',
    'depends': ['stock'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_cron_data.xml',
        'views/stock_warehouse_views.xml',
        'views/stock_lot_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}

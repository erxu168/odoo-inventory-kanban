{
    'name': 'Mobile Physical Inventory',
    'version': '19.0.1.0.0',
    'category': 'Inventory',
    'summary': 'Mobile-friendly UI for Physical Inventory (Stock Adjustment)',
    'description': """
        Enhances the Physical Inventory screen with a responsive, 
        mobile-friendly interface for easy use on smartphones and tablets.
        Features include:
        - Large touch-friendly buttons
        - Card-based product layout
        - Easy quantity input with +/- controls
        - Barcode scanning support
        - Search/filter by product or location
    """,
    'author': 'Custom',
    'depends': ['stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/mobile_inventory_views.xml',
        'views/mobile_inventory_menus.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'mobile_physical_inventory/static/src/css/mobile_inventory.css',
            'mobile_physical_inventory/static/src/xml/mobile_inventory.xml',
            'mobile_physical_inventory/static/src/js/mobile_inventory.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}

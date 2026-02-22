# -*- coding: utf-8 -*-
{
    'name': 'Inventory Kanban Count — Custom Kanban View',
    'version': '19.0.1.0.0',
    'summary': 'Replaces the default inventory adjustment list with a fast kanban counting interface',
    'description': """
        Version 1 — Custom Kanban View (js_class approach)
        ===================================================
        Extends the standard stock.inventory (Physical Inventory) with a custom
        OWL Kanban view. Items appear as kanban cards in two columns (To Count / Counted).
        Tapping the count field slides up a numpad drawer for fast data entry.

        Approach: Inherits OWL KanbanController + KanbanRecord. Registered via js_class
        on the kanban arch. This is the lightest customization path.
    """,
    'category': 'Inventory',
    'author': 'Custom Dev',
    'depends': ['stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/inventory_kanban_view.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'inventory_kanban_count/static/src/scss/kanban_count.scss',
            'inventory_kanban_count/static/src/xml/kanban_count_card.xml',
            'inventory_kanban_count/static/src/xml/numpad_drawer.xml',
            'inventory_kanban_count/static/src/js/numpad_drawer.js',
            'inventory_kanban_count/static/src/js/kanban_count_record.js',
            'inventory_kanban_count/static/src/js/kanban_count_controller.js',
            'inventory_kanban_count/static/src/js/kanban_count_renderer.js',
            'inventory_kanban_count/static/src/js/kanban_count_view.js',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}

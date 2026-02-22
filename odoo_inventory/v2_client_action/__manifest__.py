# -*- coding: utf-8 -*-
{
    'name': 'Inventory Count Client Action',
    'version': '19.0.1.0.0',
    'summary': 'Full-screen client action for inventory counting with kanban + numpad',
    'description': """
        Version 2 — Client Action (full OWL control)
        =============================================
        A completely custom client action registered in ir.actions.client.
        The entire UI is a single OWL component that:
        - Loads stock.quant records via ORM service
        - Renders the two-column kanban board
        - Handles the numpad drawer natively (no KanbanRecord inheritance)
        - Writes counts back via RPC
        - Validates the inventory session

        Approach: Maximum flexibility. No dependency on Odoo's KanbanView.
        Full control over layout, state, and UX flow.
    """,
    'category': 'Inventory',
    'author': 'Custom Dev',
    'depends': ['stock'],
    'data': [
        'security/ir.model.access.csv',
        'views/client_action.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'inventory_count_action/static/src/scss/inventory_count.scss',
            'inventory_count_action/static/src/xml/inventory_count_app.xml',
            'inventory_count_action/static/src/js/inventory_count_app.js',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}

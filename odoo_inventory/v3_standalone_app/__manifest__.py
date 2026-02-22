# -*- coding: utf-8 -*-
{
    'name': 'Inventory Count — Standalone Mobile App',
    'version': '19.0.1.0.0',
    'summary': 'Dedicated mobile-first inventory counting PWA, separate from the Odoo web client',
    'description': """
        Version 3 — Standalone OWL Application
        =======================================
        A completely standalone OWL app served at /inventory-count.
        Follows the same pattern as Odoo's self-order app (pos_self_order module).

        - Served by a dedicated controller at /inventory-count
        - Has its own asset bundle (not web.assets_backend)
        - Bootstraps its own OWL environment via mountComponent
        - Communicates with Odoo backend via JSON-RPC
        - PWA-ready: full-screen, mobile-first, installable
        - Works offline with service worker caching (optional)

        Use case: tablet or phone mounted in the warehouse, used exclusively
        for inventory counting without the full Odoo web client overhead.
    """,
    'category': 'Inventory',
    'author': 'Custom Dev',
    'depends': ['stock', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/standalone_templates.xml',
    ],
    'assets': {
        # Standalone bundle — separate from backend, like pos_self_order
        'inventory_count_standalone.assets': [
            # OWL + Odoo core (minimum required)
            ('include', 'web._assets_helpers'),
            'web/static/src/libs/owl/owl.js',
            'web/static/src/env.js',
            'web/static/src/session.js',
            # Our standalone app
            'inventory_count_standalone/static/src/scss/standalone.scss',
            'inventory_count_standalone/static/src/xml/standalone_app.xml',
            'inventory_count_standalone/static/src/js/standalone_service.js',
            'inventory_count_standalone/static/src/js/standalone_app.js',
            'inventory_count_standalone/static/src/js/standalone_main.js',
        ],
    },
    'installable': True,
    'application': True,  # Shows as standalone app in Odoo home
    'license': 'LGPL-3',
}

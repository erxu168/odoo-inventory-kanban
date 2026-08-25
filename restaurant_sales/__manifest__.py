{
    'name': 'Restaurant Daily Sales',
    'version': '19.0.1.0.0',
    'category': 'Sales',
    'summary': 'Daily sales close-out per outlet: POS reconciliation, cash variance and manager sign-off',
    'description': """
Restaurant Daily Sales
======================

One record per outlet per business day. The entry pulls its figures straight
from Point of Sale and asks the closing staff to declare what they actually
counted, so every shortage or overage is visible and explained before a
manager signs it off.

Features
--------
* Automatic nightly draft entry for every outlet (configurable business-day
  cutoff, so a shift that runs past midnight still lands on the right day).
* POS reconciliation per payment method: expected vs. counted, with the
  difference highlighted.
* Cash variance tolerance per outlet; an explanation is mandatory above it.
* Off-POS revenue channels (delivery platforms, catering, events) with
  commission and net payout.
* Draft -> Submitted -> Approved workflow with chatter, activities and
  record rules per outlet.
* Pivot / graph reporting on revenue, variance and channel mix.
""",
    'author': 'Krawings',
    'license': 'LGPL-3',
    'depends': ['base', 'mail', 'point_of_sale'],
    'data': [
        'security/security_groups.xml',
        'security/ir.model.access.csv',
        'security/record_rules.xml',
        'data/sales_channel_data.xml',
        'data/cron_jobs.xml',
        'views/pos_config_views.xml',
        'views/sales_channel_views.xml',
        'views/sales_entry_views.xml',
        'views/dashboard_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'restaurant_sales/static/src/css/sales.css',
        ],
    },
    'installable': True,
    'application': True,
}

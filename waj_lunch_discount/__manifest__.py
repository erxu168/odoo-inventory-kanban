{
    'name': 'WAJ Lunch Hour Discounts',
    'version': '19.0.1.0.0',
    'category': 'Sales/Point of Sale',
    'summary': 'Time-limited pricelist rules: discount dishes on given weekdays and hours (e.g. Mon-Fri 12:00-16:00)',
    'description': """
        Adds a "Limit to days & hours" option on pricelist rules so a discount can
        apply only during a time window, e.g. a lunch deal on all dishes from
        Monday to Friday between 12:00 and 16:00.

        The window is enforced both in the backend (sales orders, quotations,
        product price computation) and in the Point of Sale, where the check is
        done locally against the rule's timezone so no page reload is needed
        when lunch time starts or ends.
    """,
    'author': 'WAJ',
    'license': 'LGPL-3',
    'depends': ['product', 'point_of_sale'],
    'data': [
        'views/product_pricelist_item_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'waj_lunch_discount/static/src/app/models/product_pricelist.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}

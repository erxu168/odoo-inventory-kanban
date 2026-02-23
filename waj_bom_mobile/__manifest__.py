{
    'name': 'WAJ BoM Mobile Fix',
    'version': '19.0.1.0.0',
    'summary': 'Improves Bill of Materials readability on mobile screens',
    'category': 'Manufacturing',
    'author': 'WAJ',
    'depends': ['mrp'],
    'data': [
        'views/mrp_bom_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'waj_bom_mobile/static/src/css/bom_mobile.css',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}

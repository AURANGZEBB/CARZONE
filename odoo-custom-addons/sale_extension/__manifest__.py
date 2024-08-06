# -*- coding: utf-8 -*-

{
    'name': 'Sale Extension',
    'category': 'sale',
    'version': '15.0.1.0.1',
    'author': 'Sapna Verma',
    'company': '',
    'maintainer': 'Sapna Verma',
    'website': '',
    'summary': 'Sale Extension',
    'images': [],
    'description': "Sale Extension",
    'depends': ['project', 'base', 'account', 'customization_carzone', 'sale', 'job_card_extension'],
    'data': [
        'security/ir.model.access.csv',
        'views/sale_order_views.xml',
        'views/sale_estimate_report_view.xml',
        'wizard/sale_report_views.xml',
    ],
    'demo': [],
    'license': 'AGPL-3',
    'installable': True,
    'application': False,
    'auto_install': False,
}

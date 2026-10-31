{
    'name': 'Brightloop Subscription',
    'version': '17.0.1.0.0',
    'summary': 'Subscription management',
    'category': 'Sales',
    'depends': ['base', 'mail', 'contacts', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'views/plan_views.xml',
        'views/subscription_views.xml',
        'data/cron.xml',
    ],
    'installable': True,
    'application': True,
}

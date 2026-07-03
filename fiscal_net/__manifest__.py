# -*- coding: utf-8 -*-
{
    'name': 'Fiscal Cash Register Integration (Romania)',
    'summary': 'Connect Odoo POS to Fiscal Cash Registers (FiscalNet.ro)',
    'description': """
Fiscal Cash Register Integration
================================
Professional Odoo bridge for physical fiscal printers using the FiscalNet.ro driver.
Automates receipt printing, Z-reports, and legal cash book reporting for Romanian businesses.

Key features:
* Support for Datecs, Daisy, Olivetti, Tremol, and more.
* Automated fiscal receipt printing after sale.
* Z-Report and Cash Book (Registrul de Casă) generation.
* Cash-in/Cash-out operation management.
    """,
    'author': "Franchise Tech",
    'website': "https://franchisetech.ro/",
    'category': 'Localization/Romania',
    'version': '19.0.1.0.0',
    'depends': ['point_of_sale', 'stock', 'purchase', 'mrp'],
    'external_dependencies': {
        'python': ['requests'],
    },
    'sequence': 1,
    'data': [
        'security/ir.model.access.csv',
        'views/pos_config_view.xml',
        'views/fiscal_operation_log_views.xml',
        'views/payment_method_form.xml',
        'views/product_view.xml',
        'views/cashbook_report.xml',
        'views/register_report_menu.xml',
        'views/tax_menu.xml',
        'views/management_report_template.xml',
        'views/report_saledetails_inherit.xml',
        'wizard/management_report_wizard_views.xml',
    ],
    'assets': {
        'point_of_sale._assets_pos': [
            'fiscal_net/static/src/css/pos.css',
            'fiscal_net/static/src/js/models.esm.js',
            'fiscal_net/static/src/js/pos_fiscal_operations.js',
            'fiscal_net/static/src/js/cashin_cashout.js',
            'fiscal_net/static/src/js/opening_balance.js',
            'fiscal_net/static/src/js/closingPopup.js',
            'fiscal_net/static/src/js/payment_screen.js',
            'fiscal_net/static/src/js/pos_franchise_tech_title.js',
            'fiscal_net/static/src/xml/navbar_logo.xml',
            'fiscal_net/static/src/xml/pos.xml',
            'fiscal_net/static/src/xml/closing_tab.xml',
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': True,
    'price': 199.0,
    'currency': 'EUR',
    'license': 'LGPL-3',
    'images': [
        'static/description/main_screenshot.png',
        'static/description/banner.png',
        'static/description/payment_setup.png',
        'static/description/tax_setup.png',
        'static/description/cash_operations.png',
        'static/description/accounting_report.png',
        'static/description/sgr.png',
    ],
    'post_init_hook': 'post_init_hook',
}

# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class PosConfig(models.Model):
    _inherit = 'pos.config'

    fiscal_printer_enabled = fields.Boolean(
        string='Enable Fiscal Printer',
        default=True,
        help='Enable fiscal printer integration for cash operations'
    )
    use_romanian_format = fields.Boolean(
        string='Use Romanian Cash Register Format',
        help='Enable Romanian Registrul de Casa format for reports',
        default=False
    )
    fiscal_printer_output_dir = fields.Char(
        string='Fiscal Files Directory',
        default='/tmp/fiscal',
        help='Directory where fiscal operation files will be saved'
    )
    # New fields for FiscalNet API integration
    fiscal_integration_method = fields.Selection([
        ('local_file', 'Local File'),
        ('api_integration', 'FiscalNet API')
    ], string='Fiscal Integration Method', default='local_file',
        help='Choose between local file download or direct API integration with FiscalNet')
    fiscal_os_type = fields.Selection([
        ('windows', 'Windows'),
        ('android', 'Android')
    ], string='FiscalNet OS Type', default='windows',
        help='Specify the operating system where FiscalNet driver is running')

    fiscal_api_endpoint = fields.Char(
        string='FiscalNet API Endpoint',
        default='http://localhost:65400/api/Receipt',
        help='FiscalNet API endpoint URL (e.g., http://localhost:65400/api/Receipt)'
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to initialize fiscal settings from company"""
        records = super().create(vals_list)

        # Initialize fiscal settings from company if not provided
        company = self.env.company
        for record in records:
            if not record.fiscal_integration_method:
                record.fiscal_integration_method = company.fiscal_integration_method or 'local_file'
            if not record.fiscal_os_type:
                record.fiscal_os_type = company.fiscal_os_type or 'android'
            if not record.fiscal_api_endpoint:
                record.fiscal_api_endpoint = company.fiscal_api_endpoint or 'http://localhost:65400/api/Receipt'

        return records

    def ensure_cash_payment_method(self):
        """Ensure that the POS configuration has at least one cash payment method"""
        self.ensure_one()

        # Check if we already have cash payment methods
        cash_payment_methods = self.payment_method_ids.filtered('is_cash_count')
        if cash_payment_methods:
            return cash_payment_methods[0]  # Return the first cash payment method

        # Create a cash payment method if none exists
        cash_journal = self.env['account.journal'].search([
            ('type', '=', 'cash'),
            ('company_id', '=', self.company_id.id)
        ], limit=1)

        if not cash_journal:
            # Create a cash journal if none exists
            cash_journal = self.env['account.journal'].create({
                'name': 'Cash',
                'type': 'cash',
                'company_id': self.company_id.id,
                'code': 'CASH',
            })

        # Create cash payment method
        cash_payment_method = self.env['pos.payment.method'].create({
            'name': 'Cash',
            'journal_id': cash_journal.id,
            'is_cash_count': True,
            'company_id': self.company_id.id,
        })

        # Add to POS configuration
        self.payment_method_ids = [(4, cash_payment_method.id)]

        return cash_payment_method

    @api.model
    def _get_fiscal_integration_method(self):
        """Get fiscal integration method from config parameter"""
        return self.env['ir.config_parameter'].sudo().get_param(
            'fiscal_net.fiscal_integration_method', 'local_file'
        )

    @api.model
    def _get_fiscal_os_type(self):
        """Get fiscal OS type from config parameter"""
        return self.env['ir.config_parameter'].sudo().get_param(
            'fiscal_net.fiscal_os_type', 'android'
        )

    @api.model
    def _get_fiscal_api_endpoint(self):
        """Get fiscal API endpoint from config parameter"""
        return self.env['ir.config_parameter'].sudo().get_param(
            'fiscal_net.fiscal_api_endpoint', 'http://localhost:65400/api/Receipt'
        )

    def action_save(self):
        """Enhanced save action with user feedback"""
        self.ensure_one()

        # Validate fiscal settings
        if self.fiscal_integration_method == 'api_integration' and not self.fiscal_api_endpoint:
            raise UserError("Fiscal API endpoint is required when using API integration method.")

        if self.fiscal_integration_method == 'local_file' and not self.fiscal_printer_output_dir:
            raise UserError("Fiscal printer output directory is required when using local file method.")

        # Save the record
        self.write({})

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Configuration Saved',
                'message': 'Fiscal cash register configuration has been saved successfully!',
                'type': 'success',
                'sticky': False,
            }
        }




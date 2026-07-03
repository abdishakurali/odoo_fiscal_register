# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError
from datetime import datetime, date

class ManagementReportWizard(models.TransientModel):
    _name = 'management.report.wizard'
    _description = 'Asistent Raport de Gestiune'

    date_from = fields.Date(
        string='Data de la',
        required=True,
        default=lambda self: date.today().replace(day=1)
    )
    date_to = fields.Date(
        string='Data până la',
        required=True,
        default=fields.Date.today
    )
    company_id = fields.Many2one(
        'res.company',
        string='Companie',
        required=True,
        default=lambda self: self.env.company
    )

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for record in self:
            if record.date_from > record.date_to:
                raise UserError(_('Data de la trebuie să fie înainte de Data până la.'))

    def action_generate_report(self):
        """Generează raportul de gestiune"""
        self.ensure_one()
        
        # Prepare data for the report
        data = {
            'date_from': self.date_from,
            'date_to': self.date_to,
        }
        
        # Return the report action
        return {
            'type': 'ir.actions.report',
            'report_name': 'fiscal_net.management_report_template',
            'report_type': 'qweb-pdf',
            'data': data,
            'context': {
                'active_model': 'res.company',
                'active_ids': [self.company_id.id],
            }
        }

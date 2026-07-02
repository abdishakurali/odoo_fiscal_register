import logging
from odoo import models, api, fields, _
from odoo.tools import float_is_zero

_logger = logging.getLogger(__name__)

class ReportSaleDetails(models.AbstractModel):
    _inherit = 'report.point_of_sale.report_saledetails'

    @api.model
    def get_sale_details(self, date_start=False, date_stop=False, config_ids=False, session_ids=False, **kwargs):
        result = super().get_sale_details(date_start, date_stop, config_ids, session_ids, **kwargs)

        def _fmt(amount):
            try:
                return f"{float(amount):,.2f} RON"
            except Exception:
                return "0.00 RON"

        # Always inject safe defaults so the template never sees undefined variables,
        # even when no session is found (e.g. session still open during closing flow).
        result.setdefault('opening_balance_fmt', '0.00 RON')
        result.setdefault('total_incasari_fmt', '0.00 RON')
        result.setdefault('total_plati_fmt', '0.00 RON')
        result.setdefault('sold_final_fmt', '0.00 RON')
        result.setdefault('current_date', fields.Date.context_today(self))

        try:
            if session_ids:
                sessions = self.env['pos.session'].browse(session_ids)
            else:
                sessions = self.env['pos.session'].search([
                    ('config_id', 'in', config_ids or []),
                    ('start_at', '>=', date_start),
                    ('start_at', '<=', date_stop),
                ], order='id desc', limit=1)

            if not sessions:
                return result

            session = sessions[0]

            previous_session = self.env['pos.session'].search([
                ('config_id', '=', session.config_id.id),
                ('id', '<', session.id),
                ('state', '=', 'closed'),
            ], order='id desc', limit=1)

            # cash_register_balance_end_real was removed in Odoo 17+
            opening_balance = getattr(previous_session, 'cash_register_balance_end_real', 0.0) if previous_session else 0.0

            try:
                cash_moves = self.env['account.bank.statement.line'].search([
                    ('pos_session_id', '=', session.id)
                ], order='create_date asc')
            except Exception:
                cash_moves = self.env['account.bank.statement.line'].browse()

            total_incasari = sum(m.amount for m in cash_moves if m.amount > 0)
            total_plati = sum(abs(m.amount) for m in cash_moves if m.amount < 0)
            sold_final = opening_balance + total_incasari - total_plati

            payments = result.get('payments', [])
            for payment in payments:
                if payment.get('cash', False):
                    payment['cash_moves'] = []
                    for move in cash_moves:
                        payment['cash_moves'].append({
                            'name': move.payment_ref or move.name or '',
                            'amount': move.amount,
                            'amount_fmt': _fmt(move.amount),
                            'amount_abs_fmt': _fmt(abs(move.amount)),
                            'reason': move.payment_ref or move.name or '',
                        })

            result.update({
                'opening_balance': opening_balance,
                'opening_balance_fmt': _fmt(opening_balance),
                'total_incasari': total_incasari,
                'total_incasari_fmt': _fmt(total_incasari),
                'total_plati': total_plati,
                'total_plati_fmt': _fmt(total_plati),
                'sold_final_fmt': _fmt(sold_final),
                'current_date': fields.Date.context_today(self),
                'payments': payments,
            })

        except Exception:
            _logger.exception("ReportStandard: error building Romanian cash register data")

        return result

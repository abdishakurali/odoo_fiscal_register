from odoo import models, api, fields, _
from odoo.tools import float_is_zero

class ReportSaleDetails(models.AbstractModel):
    _inherit = 'report.point_of_sale.report_saledetails'

    @api.model
    def get_sale_details(self, date_start=False, date_stop=False, config_ids=False, session_ids=False, **kwargs):
        # Get the base report data
        result = super().get_sale_details(date_start, date_stop, config_ids, session_ids, **kwargs)

        if session_ids:
            sessions = self.env['pos.session'].browse(session_ids)
        else:
            sessions = self.env['pos.session'].search([
                ('config_id', 'in', config_ids),
                ('start_at', '>=', date_start),
                ('start_at', '<=', date_stop),
                ('state', 'in', ['closed'])
            ])

        if not sessions:
            return result

        # We'll focus on the first session as Romanian cash register is per session
        session = sessions[0]
        company = session.config_id.company_id

        # Get the opening balance from the previous session
        previous_session = self.env['pos.session'].search([
            ('config_id', '=', session.config_id.id),
            ('id', '<', session.id),
            ('state', '=', 'closed')
        ], limit=1)

        # cash_register_balance_end_real was removed/renamed in Odoo 17+; fall back to 0.
        opening_balance = getattr(previous_session, 'cash_register_balance_end_real', 0.0) if previous_session else 0.0

        # Get all cash movements for this session.
        # In Odoo 17+ the pos_session_id field on account.bank.statement.line may not
        # exist; fall back to an empty recordset so the report still renders.
        try:
            cash_moves = self.env['account.bank.statement.line'].search([
                ('pos_session_id', '=', session.id)
            ], order='create_date asc')
        except Exception:
            cash_moves = self.env['account.bank.statement.line']

        # Calculate totals
        total_incasari = sum(move.amount for move in cash_moves if move.amount > 0)
        total_plati = sum(abs(move.amount) for move in cash_moves if move.amount < 0)

        # Get payment totals from orders
        orders = session.order_ids
        total_paid = sum(order.amount_paid for order in orders)
        total_returned = sum(order.amount_return for order in orders)

        def _fmt(amount):
            try:
                return f"{float(amount):,.2f} RON"
            except Exception:
                return f"0.00 RON"

        # Find the cash payment method and update its cash_moves
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

        sold_final = opening_balance + total_incasari - total_plati

        # Add values to the report — amounts are pre-formatted so the template
        # does not need to call a Python callable (avoids safe_eval restrictions).
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
            'products': result.get('products', []),
            'products_info': result.get('products_info', {}),
            'refund_products': result.get('refund_products', []),
            'refund_info': result.get('refund_info', {}),
            'refund_taxes': result.get('refund_taxes', []),
            'refund_taxes_info': result.get('refund_taxes_info', {})
        })

        return result

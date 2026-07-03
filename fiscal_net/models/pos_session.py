# -*- coding: utf-8 -*-
from odoo import models, api, fields
import logging
import os
from datetime import datetime

_logger = logging.getLogger(__name__)

class PosSession(models.Model):
    _inherit = 'pos.session'

    def action_print_romanian_cash_register(self):
        """Action to print Romanian Cash Register report"""
        return self.env.ref('fiscal_net.action_report_pos_romanian_cash_register').report_action(self)

    def action_generate_register_report(self):
        """Action to generate Registrul De Casa report"""
        return self.env.ref('fiscal_net.report_cash_book_action').report_action(self)

    @api.model
    def ensure_fiscal_directory(self):
        """Ensure the fiscal files directory exists"""
        config = self.config_id
        if config.fiscal_printer_enabled and config.fiscal_printer_output_dir:
            os.makedirs(config.fiscal_printer_output_dir, exist_ok=True)
            return True
        return False

    def _validate_session(self, balancing_account=False, amount_to_balance=0, bank_payment_method_diffs=None):
        res = super(PosSession, self)._validate_session(balancing_account, amount_to_balance, bank_payment_method_diffs)
        if self.config_id.fiscal_printer_enabled:
            try:
                self.ensure_fiscal_directory()
                _logger.info('Fiscal directory checked for session %s', self.name)
            except Exception as e:
                _logger.error('Failed to ensure fiscal directory: %s', str(e))
        return res

    def _get_report_values(self, docids, data=None):
        result = super()._get_report_values(docids, data)
        if not docids:
            return result
        if not isinstance(docids, (list, tuple)) or len(docids) == 0:
            return result

        session = self.browse(docids[0])
        cash_payment_methods = session.payment_method_ids.filtered(lambda pm: pm.is_cash_count)
        payments_data = []

        for payment_method in cash_payment_methods:
            opening_balance = session.cash_register_balance_start
            payment_data = {
                'name': payment_method.name,
                'is_cash_count': True,
                'opening_balance': opening_balance,
                'money_counted': session.cash_register_balance_end_real,
                'cash_moves': [],
                'cash_in_total': 0.0,
                'cash_out_total': 0.0,
                'final_count': session.cash_register_balance_end,
                'money_difference': session.cash_register_difference,
                'final_balance': session.cash_register_balance_end
            }

            statement_lines = session.statement_line_ids.filtered(
                lambda line: line.payment_method_id == payment_method
            ).sorted('date')

            cash_in_count = 0
            cash_out_count = 0

            for line in statement_lines:
                if line.amount != 0:
                    if line.amount > 0:
                        cash_in_count += 1
                        doc_number = f"CHI{str(cash_in_count).zfill(4)}"
                        move_name = line.payment_ref or f"Incasare {doc_number}"
                    else:
                        cash_out_count += 1
                        doc_number = f"CHO{str(cash_out_count).zfill(4)}"
                        move_name = line.payment_ref or f"Plata {doc_number}"

                    move_data = {
                        'id': line.id,
                        'date': line.date,
                        'name': move_name,
                        'document_ref': doc_number,
                        'amount': abs(line.amount),
                        'type': 'in' if line.amount > 0 else 'out',
                        'reason': line.narration or line.payment_ref or ''
                    }
                    payment_data['cash_moves'].append(move_data)

                    if line.amount > 0:
                        payment_data['cash_in_total'] += line.amount
                    else:
                        payment_data['cash_out_total'] += abs(line.amount)

            cash_payments = self.env['pos.payment'].search([
                ('session_id', '=', session.id),
                ('payment_method_id', '=', payment_method.id)
            ]).sorted('payment_date')

            for payment in cash_payments:
                if payment.amount != 0:
                    cash_in_count += 1
                    doc_number = f"CHI{str(cash_in_count).zfill(4)}"
                    payment_data['cash_moves'].append({
                        'id': payment.id,
                        'date': payment.payment_date,
                        'name': f"Incasare {payment.pos_order_id.name}",
                        'document_ref': doc_number,
                        'amount': abs(payment.amount),
                        'type': 'in' if payment.amount > 0 else 'out',
                        'reason': payment.pos_order_id.note or ''
                    })
                    if payment.amount > 0:
                        payment_data['cash_in_total'] += payment.amount
                    else:
                        payment_data['cash_out_total'] += abs(payment.amount)

            payment_data['cash_moves'] = sorted(
                payment_data['cash_moves'],
                key=lambda x: (x['date'], x['id'])
            )
            payments_data.append(payment_data)

        result.update({
            'payments': payments_data,
            'date_start': session.start_at,
            'date_stop': session.stop_at or fields.Datetime.now(),
            'state': session.state,
            'company': session.company_id,
            'session_name': session.name,
            'nbr_orders': len(session.order_ids),
            'opening_note': session.opening_notes,
            'closing_note': session.closing_notes,
            'currency': {
                'symbol': session.currency_id.symbol,
                'position': session.currency_id.position,
                'precision': session.currency_id.decimal_places,
                'total_paid': sum(session.order_ids.mapped('amount_total'))
            }
        })
        return result


class POSSessionCashBook(models.AbstractModel):
    _name = 'report.fiscal_net.report_cash_book_view_template'
    _description = 'Cash Book Report'

    @api.model
    def _get_report_values(self, docids, data=None):
        """Get cash register data for the report"""
        session = self.env['pos.session'].browse(docids[0])
        if not session:
            return {}

        cash_transactions = []
        cash_statements = session.statement_line_ids.filtered(lambda l: l.journal_id.type == 'cash')
        running_balance = session.cash_register_balance_start or 0.0
        initial_balance = running_balance

        cash_transactions.append({
            'type': 'initial',
            'date': session.start_at,
            'reference': 'SOLD INITIAL',
            'description': f'Report / Sold ziua precedenta {session.start_at.strftime("%d-%m-%Y") if session.start_at else ""}',
            'amount_in': 0.0,
            'amount_out': 0.0,
            'balance': running_balance
        })

        for line in cash_statements.sorted('date'):
            if line.amount > 0:
                running_balance += line.amount
                cash_transactions.append({
                    'type': 'cash_in',
                    'date': line.date,
                    'reference': line.ref or '',
                    'description': line.payment_ref or line.narration or 'Incasare',
                    'amount_in': line.amount,
                    'amount_out': 0.0,
                })
            else:
                running_balance += line.amount
                cash_transactions.append({
                    'type': 'cash_out',
                    'date': line.date,
                    'reference': line.ref or '',
                    'description': line.payment_ref or line.narration or 'Plata',
                    'amount_in': 0.0,
                    'amount_out': abs(line.amount),
                })

        for order in session.order_ids:
            for payment in order.payment_ids:
                if payment.payment_method_id.type == 'cash':
                    cash_transactions.append({
                        'date': payment.payment_date,
                        'type': 'pos_cash_order',
                        'reference': order.name,
                        'description': f"Cash sale - {order.name}",
                        'amount_in': payment.amount,
                        'amount_out': 0.0,
                    })

        total_cash_in = sum(t['amount_in'] for t in cash_transactions if t['type'] in ['cash_in', 'pos_cash_order'])
        total_cash_out = sum(t['amount_out'] for t in cash_transactions if t['type'] == 'cash_out')
        final_balance = initial_balance + total_cash_in - total_cash_out

        cash_transactions.append({
            'type': 'final',
            'date': session.stop_at or fields.Datetime.now(),
            'reference': 'SOLD FINAL',
            'description': f'Sold Final ziua {(session.stop_at or fields.Datetime.now()).strftime("%d-%m-%Y")}',
            'amount_in': 0.0,
            'amount_out': 0.0,
            'balance': final_balance
        })

        return {
            'doc_ids': docids,
            'doc_model': 'pos.session',
            'docs': [session],
            'session': session,
            'company': session.config_id.company_id,
            'cash_transactions': cash_transactions,
            'total_cash_in': total_cash_in,
            'total_cash_out': total_cash_out,
            'initial_balance': initial_balance,
            'final_balance': final_balance,
            'date_start': session.start_at,
            'date_end': session.stop_at or fields.Datetime.now(),
        }

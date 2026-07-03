# -*- coding: utf-8 -*-
from odoo import models, api
from datetime import datetime, date, time, timedelta
from collections import defaultdict
import logging

_logger = logging.getLogger(__name__)

# ── Shared date-format constants ───────────────────────────────────────────────
_DT_FMT = '%d.%m.%Y\n%H:%M:%S'   # shown in Data column (white-space:pre-wrap)
_D_FMT  = '%d.%m.%Y'


class ManagementReport(models.AbstractModel):
    _name = 'report.fiscal_net.management_report_template'
    _description = 'Raport de Gestiune'

    # ── Entry point ───────────────────────────────────────────────────────────

    @api.model
    def _get_report_values(self, docids, data=None):
        company = (
            self.env['res.company'].browse(docids[0])
            if docids else self.env.company
        )

        date_from = data.get('date_from') if data else None
        date_to   = data.get('date_to')   if data else None

        if isinstance(date_from, str):
            date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
        if isinstance(date_to, str):
            date_to = datetime.strptime(date_to, '%Y-%m-%d').date()

        if not date_from or not date_to:
            today     = date.today()
            date_from = today.replace(day=1)
            date_to   = today

        all_tax_rates = self._get_system_tax_rates()
        report_data   = self._build_report(company, date_from, date_to)

        pos_config = self.env['pos.config'].search([('active', '=', True)], limit=1)

        _logger.info(
            'Raport Gestiune %s: %d tranzactii, %s -> %s',
            company.name, len(report_data['transactions']), date_from, date_to,
        )

        return {
            'doc_ids':         docids,
            'doc_model':       'res.company',
            'docs':            [company],
            'company':         company,
            'date_from':       date_from,
            'date_to':         date_to,
            'report_data':     report_data,
            'user':            self.env.user,
            'generated_date':  datetime.now(),
            'pos_config_name': pos_config.name if pos_config else 'N/A',
            'all_tax_rates':   all_tax_rates,
        }

    # ── Orchestrator ──────────────────────────────────────────────────────────

    def _build_report(self, company, date_from, date_to):
        rows = []

        # 1. Incoming supplier receipts — ONE row per stock.picking (NIR)
        rows.extend(self._nir_rows(company, date_from, date_to))

        # 2. Daily POS aggregates — ONE row per calendar day (Raport Z)
        rows.extend(self._raport_z_rows(company, date_from, date_to))

        # 3. Manufacturing — ONE Bon de consum + ONE PV per MO
        rows.extend(self._manufacturing_rows(company, date_from, date_to))

        # Sort by internal key (datetime, priority) then strip it before rendering
        rows.sort(key=lambda r: r['_sort_key'])
        for r in rows:
            r.pop('_sort_key')

        totals        = self._calculate_totals(rows)
        initial_stock = self._initial_stock_value(company, date_from)
        final_stock   = self._final_stock_value(company)

        return {
            'transactions':  rows,
            'totals':        totals,
            'stock_summary': {
                'initial_stock':     initial_stock,
                'final_stock':       final_stock,
                **self._stock_footer(company, final_stock),
            },
        }

    # ── Stock valuation ───────────────────────────────────────────────────────

    def _initial_stock_value(self, company, date_from):
        """
        Sum all stock.valuation.layer entries posted BEFORE the period start.
        Falls back to zero if the module is not installed.
        """
        try:
            cutoff = datetime.combine(date_from, time.min)
            layers = self.env['stock.valuation.layer'].search([
                ('company_id', '=', company.id),
                ('create_date', '<', cutoff),
            ])
            return max(sum(l.value for l in layers), 0.0)
        except Exception:
            return 0.0

    def _final_stock_value(self, company):
        quants = self.env['stock.quant'].search([
            ('company_id', '=', company.id),
            ('location_id.usage', '=', 'internal'),
        ])
        return max(
            sum(q.quantity * (q.product_id.standard_price or 0.0) for q in quants),
            0.0,
        )

    def _stock_footer(self, company, final_stock):
        """Compute VAT on final stock, purchase price, and markup."""
        quants = self.env['stock.quant'].search([
            ('company_id', '=', company.id),
            ('location_id.usage', '=', 'internal'),
        ])
        vat_total = 0.0
        for q in quants:
            if not q.product_id.standard_price:
                continue
            val   = q.quantity * q.product_id.standard_price
            taxes = q.product_id.taxes_id.filtered(lambda t: t.amount_type == 'percent')
            if taxes:
                vat_total += val * taxes[0].amount / 100.0

        # Assume an average 20 % retail markup for purchase-price back-calculation
        purchase_price = round(final_stock / 1.20, 2) if final_stock else 0.0
        markup         = round(final_stock - purchase_price, 2)

        return {
            'stock_value':       final_stock,
            'vat_value':         round(vat_total, 2),
            'purchase_price':    purchase_price,
            'commercial_markup': markup,
        }

    # ── NIR rows (one per incoming picking, all moves aggregated) ─────────────

    def _nir_rows(self, company, date_from, date_to):
        rows = []
        dt_from = datetime.combine(date_from, time.min)
        dt_to   = datetime.combine(date_to,   time.max)

        receipts = self.env['stock.picking'].search([
            ('company_id', '=', company.id),
            ('date_done', '>=', dt_from),
            ('date_done', '<=', dt_to),
            ('picking_type_code', '=', 'incoming'),
            ('state', '=', 'done'),
        ], order='date_done asc')

        for receipt in receipts:
            partner_name = self._partner_name(
                receipt.partner_id,
                getattr(receipt, 'purchase_id', None) and receipt.purchase_id.partner_id or None,
            )

            total   = 0.0
            vat_acc = defaultdict(float)
            for move in receipt.move_ids:
                if move.product_id.type != 'product' or move.state != 'done':
                    continue
                amt = move.product_qty * (move.product_id.standard_price or 0.0)
                total += amt
                for k, v in self._vat_amounts(move.product_id, amt).items():
                    vat_acc[k] += v

            if total == 0.0:
                continue

            done_dt = receipt.date_done  # aware datetime from Odoo
            rows.append({
                # priority 1 → NIR appears after Raport Z (priority 0) on same day
                '_sort_key':   (done_dt, 1),
                'document':    'NIR',
                'date':        done_dt.strftime(_DT_FMT),
                'description': 'Furnizor: %s' % partner_name,
                'intrari':     round(total, 2),
                'iesiri':      0.0,
                'discount':    0.0,
                **{k: round(v, 2) for k, v in vat_acc.items()},
            })

        return rows

    # ── Raport Z rows (one per calendar day, all POS orders aggregated) ───────

    def _raport_z_rows(self, company, date_from, date_to):
        dt_from = datetime.combine(date_from, time.min)
        dt_to   = datetime.combine(date_to,   time.max)

        pos_orders = self.env['pos.order'].search([
            ('company_id', '=', company.id),
            ('date_order', '>=', dt_from),
            ('date_order', '<=', dt_to),
            ('state', 'in', ['paid', 'done', 'invoiced']),
        ], order='date_order asc')

        # Aggregate by calendar day (server local date)
        daily = defaultdict(lambda: {
            'total':    0.0,
            'discount': 0.0,
            'vat':      defaultdict(float),
        })

        for order in pos_orders:
            day = order.date_order.date()
            daily[day]['total']    += order.amount_total
            daily[day]['discount'] += getattr(order, 'amount_discount', 0.0)
            for line in order.lines:
                key = self._vat_key_for_taxes(line.tax_ids)
                daily[day]['vat'][key] += line.price_subtotal

        rows = []
        for day in sorted(daily.keys()):
            d = daily[day]
            # Use midnight so Raport Z sorts FIRST within the day (priority 0)
            sort_dt = datetime.combine(day, time.min)
            rows.append({
                '_sort_key':   (sort_dt, 0),
                'document':    'Raport Z',
                'date':        day.strftime(_D_FMT) + '\n12:00:00',
                'description': 'Valoare vanzare (Bon fiscal) - Raport Z',
                'intrari':     0.0,
                'iesiri':      round(d['total'], 2),
                'discount':    round(d['discount'], 2),
                **{k: round(v, 2) for k, v in d['vat'].items()},
            })

        return rows

    # ── Manufacturing rows (Bon de consum + PV per MO, paired by sequence) ────

    def _manufacturing_rows(self, company, date_from, date_to):
        rows = []
        dt_from = datetime.combine(date_from, time.min)
        dt_to   = datetime.combine(date_to,   time.max)

        try:
            mos = self.env['mrp.production'].search([
                ('company_id', '=', company.id),
                ('date_start', '>=', dt_from),
                ('date_start', '<=', dt_to),
                ('state', 'in', ['done', 'to_close']),
            ], order='date_start asc')
        except Exception:
            _logger.warning('mrp.production not available or query failed')
            return rows

        for mo in mos:
            # Extract the short numeric suffix, e.g. "WH/MO/00412" → "412"
            mo_seq = mo.name.rsplit('/', 1)[-1].lstrip('0') or mo.name

            # MO start datetime (Odoo stores as UTC datetime)
            mo_dt = mo.date_start or mo.date_planned_start
            if not mo_dt:
                mo_dt = dt_from
            mo_date_str = mo_dt.strftime(_D_FMT) if hasattr(mo_dt, 'strftime') else str(mo_dt)

            # Both Bon de consum and PV share end-of-day sort so they appear
            # AFTER Raport Z (priority 0) and NIR (priority 1) on the same day.
            sort_dt = datetime.combine(mo_dt.date(), time(23, 59, 59))

            # ── Bon de consum: aggregate raw material cost ─────────────────
            raw_total = 0.0
            raw_vat   = defaultdict(float)
            for move in mo.move_raw_ids:
                if move.state != 'done':
                    continue
                amt = move.product_uom_qty * (move.product_id.standard_price or 0.0)
                raw_total += amt
                for k, v in self._vat_amounts(move.product_id, amt).items():
                    raw_vat[k] += v

            if raw_total > 0:
                rows.append({
                    '_sort_key':   (sort_dt, 2),  # Bon de consum before PV
                    'document':    'Bon de consum nr. %s' % mo_seq,
                    'date':        mo_dt.strftime(_DT_FMT),
                    'description': 'RETETA, PERIOADA: %s - %s' % (mo_date_str, mo_date_str),
                    'intrari':     0.0,
                    'iesiri':      round(raw_total, 2),
                    'discount':    0.0,
                    **{k: round(v, 2) for k, v in raw_vat.items()},
                })

            # ── PV: aggregate finished-goods value ─────────────────────────
            fin_total = 0.0
            fin_vat   = defaultdict(float)
            for move in mo.move_finished_ids:
                if move.state != 'done':
                    continue
                amt = move.product_uom_qty * (move.product_id.standard_price or 0.0)
                fin_total += amt
                for k, v in self._vat_amounts(move.product_id, amt).items():
                    fin_vat[k] += v

            if fin_total > 0:
                rows.append({
                    '_sort_key':   (sort_dt, 3),  # PV after Bon de consum
                    'document':    'PV nr. %s' % mo_seq,
                    'date':        mo_dt.strftime(_DT_FMT),
                    'description': 'RETETA: Bon de consum %s/%s' % (mo_seq, mo_date_str),
                    'intrari':     round(fin_total, 2),
                    'iesiri':      0.0,
                    'discount':    0.0,
                    **{k: round(v, 2) for k, v in fin_vat.items()},
                })

        return rows

    # ── VAT helpers ───────────────────────────────────────────────────────────

    def _vat_key_for_taxes(self, tax_ids):
        """'vat_24', 'vat_9', 'vat_0' … derived from the first % tax on the line."""
        pct = tax_ids.filtered(lambda t: t.amount_type == 'percent')
        return ('vat_%d' % int(pct[0].amount)) if pct else 'vat_0'

    def _vat_amounts(self, product, amount):
        """Return {'vat_N': amount} keyed by the product's first sales tax rate."""
        if not product or not amount:
            return {'vat_0': 0.0}
        taxes = product.taxes_id.filtered(lambda t: t.amount_type == 'percent')
        if taxes:
            return {'vat_%d' % int(taxes[0].amount): amount}
        return {'vat_0': amount}

    def _get_system_tax_rates(self):
        """
        Return deduplicated account.tax records used on active saleable products,
        sorted highest-rate first (matches the column order in the screenshot).
        """
        products = self.env['product.template'].search([
            ('active', '=', True),
            ('sale_ok', '=', True),
        ])
        all_taxes = products.mapped('taxes_id').filtered(
            lambda t: t.amount_type == 'percent' and t.type_tax_use == 'sale'
        )
        seen, result = set(), []
        for tax in sorted(all_taxes, key=lambda t: t.amount, reverse=True):
            if tax.amount not in seen:
                seen.add(tax.amount)
                result.append(tax)
        return result

    # ── Totals ────────────────────────────────────────────────────────────────

    def _calculate_totals(self, rows):
        totals = {'intrari': 0.0, 'iesiri': 0.0, 'discount': 0.0}
        for r in rows:
            totals['intrari']  += r.get('intrari',  0.0)
            totals['iesiri']   += r.get('iesiri',   0.0)
            totals['discount'] += r.get('discount', 0.0)
            for k, v in r.items():
                if k.startswith('vat_'):
                    totals[k] = totals.get(k, 0.0) + v
        return {k: round(v, 2) for k, v in totals.items()}

    # ── Partner name resolution ───────────────────────────────────────────────

    def _partner_name(self, *partners):
        """Walk the partner chain and return the first non-empty name."""
        for p in partners:
            if p and getattr(p, 'name', None):
                return p.name
        return 'Necunoscut'

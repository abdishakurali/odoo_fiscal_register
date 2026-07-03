# models/payment_method.py
from odoo import models, fields, api


class PaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    payment_type_code = fields.Integer(
        string="Payment Type Code",
        help="Code to identify the payment type in the fiscal operations."
    )
    is_card = fields.Boolean(
        string="Is Card",
        default=False,
        help="To identify the card payment in the fiscal operations."
    )

    @api.model
    def _load_pos_data_fields(self, config_id):
        """Add custom fields to POS payment method data (Odoo 19 API)."""
        fields = super()._load_pos_data_fields(config_id)
        fields += ['payment_type_code', 'is_card']
        return fields


class AccountTax(models.Model):
    _inherit = 'account.tax'

    vat_group_code = fields.Integer(
        string="VAT Group Code",
        help="Code for categorizing VAT groups for fiscal purposes."
    )

    @api.model
    def _load_pos_data_fields(self, config_id):
        """Add custom fields to POS tax data (Odoo 19 API)."""
        fields = super()._load_pos_data_fields(config_id)
        fields += ['vat_group_code']
        return fields

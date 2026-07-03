# -*- coding: utf-8 -*-

from odoo import models, fields, api


class ProductProduct(models.Model):
    _inherit = "product.product"

    @api.model
    def _load_pos_data_fields(self, config_id):
        """Add SGR fields to POS product data (Odoo 19 API)."""
        fields_list = super()._load_pos_data_fields(config_id)
        fields_list += ['sgr_product_id', 'sgr_qty', 'is_sgr']
        return fields_list


class ProductTemplate(models.Model):
    _inherit = "product.template"


    sgr_product_id = fields.Many2one("product.product", check_company=False, default=False)
    sgr_percent = fields.Float(default=0.0)
    sgr_qty = fields.Float(default=1.0)
    is_sgr = fields.Boolean(string="Are SGR", help="If checked, automatically creates and sets the SGR product", default=False)

    # Document smart button fields
    fiscal_operations_count = fields.Integer(string="Fiscal Operations", compute="_compute_fiscal_operations_count")
    pos_orders_count = fields.Integer(string="POS Orders", compute="_compute_pos_orders_count")


    @api.onchange('is_sgr')
    def _onchange_is_sgr(self):
        """Handle SGR checkbox changes - works on first click"""
        if self.is_sgr:
            # Always create/update SGR product when checked
            # Use sudo() to bypass multi-company security checks for category access
            self.sudo()._create_or_update_sgr_product()
        else:
            # Clear the SGR product when unchecked
            self.sgr_product_id = False

    @api.onchange('available_in_pos')
    def _onchange_available_in_pos(self):
        """Ensure products available in POS are active by default"""
        if self.available_in_pos and not self.active:
            self.active = True

    def _create_or_update_sgr_product(self):
        """Create or update the SGR product with specified parameters"""
        import logging
        _logger = logging.getLogger(__name__)

        # Get current active company
        current_company = self.env.company

        # Find 0% tax for sales in current company
        zero_tax = self.env['account.tax'].search([
            ('amount', '=', 0.0),
            ('amount_type', '=', 'percent'),
            ('type_tax_use', '=', 'sale'),
            ('company_id', 'in', [False, current_company.id])
        ], limit=1)

        # Look for existing SGR product in current company FIRST
        existing_sgr = self.env['product.product'].search([
            ('name', '=', 'SGR'),
            ('company_id', '=', current_company.id)
        ], limit=1)

        # If not found in current company, look for shared SGR (no company assigned)
        if not existing_sgr:
            existing_sgr = self.env['product.product'].search([
                ('name', '=', 'SGR'),
                ('company_id', '=', False)
            ], limit=1)

        if existing_sgr:
            # Use existing SGR product and ensure it has correct settings
            self.sgr_product_id = existing_sgr.id
            update_vals = {
                'available_in_pos': True,
                'active': True,  # Products available in POS must be active
                'categ_id': self.env.ref('product.product_category_all', raise_if_not_found=False) and self.env.ref('product.product_category_all').id or self.env['product.category'].search([], order='id asc', limit=1).id
            }


            existing_sgr.write(update_vals)
            _logger.info(f"Using existing SGR product with ID {existing_sgr.id} for company {current_company.name}")
        else:
            # Create new SGR product
            # IMPORTANT: Always assign current active company to SGR product
            sgr_product_vals = {
                'name': 'SGR',
                'type': 'service',
                'list_price': 0.5,
                'available_in_pos': True,
                'active': True,
            'categ_id': (self.env.ref('product.product_category_all', raise_if_not_found=False) and self.env.ref('product.product_category_all').id) or self.env['product.category'].search([], order='id asc', limit=1).id,

            }

            if zero_tax:
                sgr_product_vals['taxes_id'] = [(6, 0, [zero_tax.id])]

            # Create SGR product
            # Use sudo() for elevated permissions
            sgr_product = self.env['product.product'].sudo().create(sgr_product_vals)


            self.sgr_product_id = sgr_product.id
            _logger.info(f"Successfully created SGR product with ID {sgr_product.id}")


    def write(self, vals):
        """Override write to ensure POS products are active"""
        # If available_in_pos is being set to True, ensure product is active
        if 'available_in_pos' in vals and vals['available_in_pos']:
            if 'active' not in vals:
                vals['active'] = True

        # NOTE: SGR product creation is ONLY triggered by onchange('is_sgr')
        # We do NOT auto-create SGR during write() to avoid category assignment issues

        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        """Override create to ensure POS products are active and no default category"""
        for vals in vals_list:
            # If available_in_pos is being set to True, ensure product is active
            if 'available_in_pos' in vals and vals['available_in_pos']:
                if 'active' not in vals:
                    vals['active'] = True

            # Ensure no default category unless explicitly provided

        records = super().create(vals_list)

        # NOTE: SGR product creation is ONLY triggered by onchange('is_sgr')
        # We do NOT auto-create SGR during create() to avoid:
        # 1. Creating SGR products blindly
        # 2. Automatic category assignment from last created category
        # 3. Cross-company category assignment
        # User MUST explicitly check the "Are SGR" checkbox in UI

        return records

    @api.depends('product_variant_ids')
    def _compute_fiscal_operations_count(self):
        """Compute fiscal operations count for smart button"""
        for record in self:
            if hasattr(self.env['pos.order'], 'search'):
                orders = self.env['pos.order'].search([
                    ('lines.product_id', 'in', record.product_variant_ids.ids)
                ])
                record.fiscal_operations_count = len(orders)
            else:
                record.fiscal_operations_count = 0

    @api.depends('product_variant_ids')
    def _compute_pos_orders_count(self):
        """Compute POS orders count for smart button"""
        for record in self:
            if hasattr(self.env['pos.order'], 'search'):
                orders = self.env['pos.order'].search([
                    ('lines.product_id', 'in', record.product_variant_ids.ids)
                ])
                record.pos_orders_count = len(orders)
            else:
                record.pos_orders_count = 0

    def action_view_fiscal_operations(self):
        """Action to view fiscal operations for this product"""
        self.ensure_one()
        return {
            'name': 'Fiscal Operations',
            'type': 'ir.actions.act_window',
            'res_model': 'pos.order',
            'view_mode': 'list,form',
            'domain': [('lines.product_id', 'in', self.product_variant_ids.ids)],
            'context': {'search_default_product_id': self.id},
        }

    def action_view_pos_orders(self):
        """Action to view POS orders for this product"""
        self.ensure_one()
        return {
            'name': 'POS Orders',
            'type': 'ir.actions.act_window',
            'res_model': 'pos.order',
            'view_mode': 'list,form',
            'domain': [('lines.product_id', 'in', self.product_variant_ids.ids)],
            'context': {'search_default_product_id': self.id},
        }

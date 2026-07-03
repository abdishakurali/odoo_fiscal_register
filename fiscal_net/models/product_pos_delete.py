# -*- coding: utf-8 -*-
from odoo import api, models, _
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    """Override to make POS session check company-aware"""
    _inherit = 'product.template'

    @api.ondelete(at_uninstall=False)
    def _unlink_except_open_session(self):
        """
        Override to check only POS sessions in the SAME company as the product.
        
        Original Odoo checks ALL sessions across ALL companies, which prevents
        deleting products even when sessions are open in OTHER companies.
        """
        product_ctx = dict(self.env.context or {}, active_test=False)
        
        # Check if any of the products being deleted are available in POS
        if self.with_context(product_ctx).search_count([('id', 'in', self.ids), ('available_in_pos', '=', True)]):
            # Get company IDs for products being deleted
            product_companies = self.mapped('company_id')
            
            # If products have no company, check all sessions (safe fallback)
            if not product_companies:
                if self.env['pos.session'].sudo().search_count([('state', '!=', 'closed')]):
                    raise UserError(
                        _(
                            "To delete a product, make sure all point of sale sessions are closed.\n\n"
                            "Deleting a product available in a session would be like attempting to snatch a hamburger from a customer's hand mid-bite; chaos will ensue as ketchup and mayo go flying everywhere!",
                        ),
                    )
            else:
                # Check only sessions in the SAME companies as the products
                company_names = ', '.join(product_companies.mapped('name'))
                open_sessions = self.env['pos.session'].sudo().search_count([
                    ('state', '!=', 'closed'),
                    ('company_id', 'in', product_companies.ids)
                ])
                
                if open_sessions:
                    raise UserError(
                        _(
                            "To delete a product, make sure all point of sale sessions in company '%s' are closed.\n\n"
                            "Deleting a product available in a session would be like attempting to snatch a hamburger from a customer's hand mid-bite; chaos will ensue as ketchup and mayo go flying everywhere!",
                            company_names
                        ),
                    )
                else:
                    _logger.info(f"Product deletion allowed - no open sessions in company '{company_names}'")


class ProductProduct(models.Model):
    """Override to make POS session check company-aware"""
    _inherit = 'product.product'

    @api.ondelete(at_uninstall=False)
    def _unlink_except_active_pos_session(self):
        """
        Override to check only POS sessions in the SAME company as the product.
        
        Original Odoo checks ALL sessions across ALL companies, which prevents
        deleting products even when sessions are open in OTHER companies.
        """
        product_ctx = dict(self.env.context or {}, active_test=False)
        
        # Get company IDs for products being deleted
        product_companies = self.mapped('company_id')
        
        # If products have no company, check all sessions (safe fallback)
        if not product_companies:
            if self.env['pos.session'].sudo().search_count([('state', '!=', 'closed')]):
                if self.with_context(product_ctx).search_count([('id', 'in', self.ids), ('product_tmpl_id.available_in_pos', '=', True)]):
                    raise UserError(
                        _(
                            "To delete a product, make sure all point of sale sessions are closed.\n\n"
                            "Deleting a product available in a session would be like attempting to snatch a hamburger from a customer's hand mid-bite; chaos will ensue as ketchup and mayo go flying everywhere!",
                        ),
                    )
        else:
            # Check only sessions in the SAME companies as the products
            company_names = ', '.join(product_companies.mapped('name'))
            open_sessions = self.env['pos.session'].sudo().search_count([
                ('state', '!=', 'closed'),
                ('company_id', 'in', product_companies.ids)
            ])
            
            if open_sessions:
                if self.with_context(product_ctx).search_count([('id', 'in', self.ids), ('product_tmpl_id.available_in_pos', '=', True)]):
                    raise UserError(
                        _(
                            "To delete a product, make sure all point of sale sessions in company '%s' are closed.\n\n"
                            "Deleting a product available in a session would be like attempting to snatch a hamburger from a customer's hand mid-bite; chaos will ensue as ketchup and mayo go flying everywhere!",
                            company_names
                        ),
                    )
            else:
                _logger.info(f"Product deletion allowed - no open sessions in company '{company_names}'")


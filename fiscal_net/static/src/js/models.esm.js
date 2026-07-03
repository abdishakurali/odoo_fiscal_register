/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { PosStore } from "@point_of_sale/app/services/pos_store";

patch(PosStore.prototype, {
    async addLineToCurrentOrder(vals, opts = {}, configure = true) {
        const result = await super.addLineToCurrentOrder(vals, opts, configure);

        try {
            const productTemplate = vals.product_tmpl_id;
            if (!productTemplate || opts.is_sgr_product) {
                return result;
            }

            const product = productTemplate.product_variant_ids?.[0] || vals.product_id;
            if (!product) {
                return result;
            }

            const sgrProductId = product.sgr_product_id;
            if (!sgrProductId) {
                return result;
            }

            const sgrProduct = this.models["product.product"].getBy("id", sgrProductId.id || sgrProductId);
            if (sgrProduct && sgrProduct.product_tmpl_id) {
                await super.addLineToCurrentOrder(
                    { product_tmpl_id: sgrProduct.product_tmpl_id },
                    {
                        quantity: product.sgr_qty || 1,
                        is_sgr_product: true,
                    },
                    false
                );
            }
        } catch (error) {
            console.warn("Error adding SGR product:", error);
        }

        return result;
    },
});

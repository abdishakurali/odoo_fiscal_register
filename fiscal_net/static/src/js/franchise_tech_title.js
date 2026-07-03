/** @odoo-module **/

import { WebClient } from "@web/webclient/webclient";
import { patch } from "@web/core/utils/patch";

patch(WebClient.prototype, {
    setup() {
        super.setup();
        // Set the window title to "Franchise Tech"
        this.title.setParts({ zopenerp: "Franchise Tech" });
    }
});

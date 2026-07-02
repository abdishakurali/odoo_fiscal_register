/** @odoo-module */
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

function get_line_attributes(line) {
    const unit = line.product_id?.uom_id?.name || "buc";

    // unit price with tax before discount (Odoo 19: unitPrices.no_discount_total_included)
    const unitPriceWithTax = line.unitPrices?.no_discount_total_included || line.price_unit || 0;
    const priceWithTax = Math.round(unitPriceWithTax * 100);
    const quantity = Math.round((line.qty || 0) * 1000);

    // Get VAT group from product taxes
    let vatGroup = 1;
    const taxes = line.tax_ids;
    if (taxes && taxes.length > 0) {
        const tax = taxes[0];
        vatGroup = tax.vat_group_code || 1;
    }
    return [line.full_product_name, priceWithTax, quantity, unit, vatGroup];
}

function addFiscalSection(order, fileName) {
    const lines = [];

    try {
        const isRefundOrder = order.lines.some((line) => line.refunded_orderline_id);
        if (isRefundOrder) {
            lines.push(`VB^${fileName.replace(".txt", "")}^BON FISCAL RETUR`);
        }

        // Customer CUI/VAT — from partner record or order note (pattern: "CUI:XXXXXXXX")
        let rawCui = order.partner?.vat || "";
        if (!rawCui && order.note) {
            const m = order.note.match(/\bCUI[:\s]+([RO0-9][\s0-9]*)/i);
            if (m) rawCui = m[1];
        }
        if (rawCui) {
            const cleanVat = rawCui.replace(/\s+/g, "").replace(/^RO/i, "").replace(/[^0-9]/g, "");
            if (cleanVat) lines.push(`CF^${cleanVat}`);
        }

        // Categorise order lines into three buckets:
        //  - regularLines : positive-price, non-SGR products
        //  - sgrLines     : bottle-deposit (is_sgr flag)
        //  - discountLines: negative-price lines created by POS global-discount feature
        //
        // FiscalNet rejects negative prices in S^ commands ("Pretul nu poate fi negativ").
        // Global-discount lines are converted to a DV^ command on the subtotal instead.
        const regularLines = [];
        const sgrLines = [];
        const discountLines = [];

        order.lines.forEach((line) => {
            const unitPrice = line.unitPrices?.no_discount_total_included ?? line.price_unit ?? 0;
            if (line.product_id?.is_sgr) {
                sgrLines.push(line);
            } else if (unitPrice < 0) {
                discountLines.push(line);
            } else {
                regularLines.push(line);
            }
        });

        // Helper: emit one S^ (sale) or VS^ (return) line, with optional DP^/DV^ for
        // line-level percentage discounts.
        const emitLine = (line) => {
            const isRefund = !!line.refunded_orderline_id;
            const a = get_line_attributes(line);
            if (!isRefund) {
                lines.push(`S^${a[0]}^${a[1]}^${a[2]}^${a[3]}^${a[4]}^1`);
                if (line.discount > 0) {
                    lines.push(`DP^${Math.round(line.discount * 100)}`);
                    const dv = Math.round(
                        (line.unitPrices?.no_discount_total_included || line.price_unit || 0) *
                            line.qty *
                            (line.discount / 100) *
                            100
                    );
                    lines.push(`DV^${dv}`);
                }
            } else {
                lines.push(
                    `VS^${a[0]}^${Math.abs(a[1])}^${Math.abs(a[2])}^${a[3]}^${a[4]}^1`
                );
            }
        };

        // 1. Regular product lines
        regularLines.forEach(emitLine);

        // 2. SGR bottle-deposit lines — placed before the discount checkpoint so the
        //    receipt total stays aligned with the Odoo order total.
        sgrLines.forEach(emitLine);

        // 3. Global discount: aggregate all negative-price discount lines into one
        //    ST^ + DV^ pair applied to the running subtotal.
        if (discountLines.length > 0) {
            const totalDiscountCents = discountLines.reduce((sum, line) => {
                const p = Math.abs(
                    line.unitPrices?.no_discount_total_included ?? line.price_unit ?? 0
                );
                return sum + Math.round(p * Math.abs(line.qty || 1) * 100);
            }, 0);
            if (totalDiscountCents > 0) {
                lines.push(`ST^`);
                lines.push(`DV^${totalDiscountCents}`);
            }
        }

        lines.push(`ST^0`);

        order.payment_ids.forEach((payment) => {
            const paymentType = payment.payment_method_id?.payment_type_code || 9;
            const amountInCents = Math.round(payment.amount * 100);
            const adjustedAmount = isRefundOrder ? Math.abs(amountInCents) : amountInCents;
            lines.push(`P^${paymentType}^${adjustedAmount}`);
        });

        return lines.join("\n");
    } catch (error) {
        console.error("Error generating fiscal section:", error);
        return lines.join("\n");
    }
}

const createDownload = (content, fileName) => {
    const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
    try {
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement("a");
        link.href = url;
        link.setAttribute("download", fileName);
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);
    } catch (error) {
        console.error("Download error:", error);
    }
};

patch(PaymentScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.orm = useService("orm");
        this.dialog = useService("dialog");

        if (this.pos && this.pos.config) {
            console.log("=== FISCAL CASH REGISTER DEBUG ===");
            console.log("Fiscal Integration Method:", this.pos.config.fiscal_integration_method);
            console.log("Fiscal OS Type:", this.pos.config.fiscal_os_type);
            console.log("Fiscal API Endpoint:", this.pos.config.fiscal_api_endpoint);
            console.log("Fiscal Printer Enabled:", this.pos.config.fiscal_printer_enabled);
            console.log("=== END FISCAL DEBUG ===");
        }
    },

    getFiscalSettings() {
        const posConfig = this.pos?.config;
        if (!posConfig) {
            return {
                integrationMethod: "local_file",
                osType: "windows",
                apiEndpoint: "http://localhost:65400/api/Receipt",
                printerEnabled: true,
                useRomanianFormat: false,
                outputDir: "/tmp/fiscal",
            };
        }
        return {
            integrationMethod: posConfig.fiscal_integration_method || "local_file",
            osType: posConfig.fiscal_os_type || "windows",
            apiEndpoint:
                posConfig.fiscal_api_endpoint || "http://localhost:65400/api/Receipt",
            printerEnabled: posConfig.fiscal_printer_enabled !== false,
            useRomanianFormat: posConfig.use_romanian_format || false,
            outputDir: posConfig.fiscal_printer_output_dir || "/tmp/fiscal",
        };
    },

    async createAndSaveFiscalFile(order) {
        console.log("createAndSaveFiscalFile called with order:", order.name);
        const fileName = `bon_${(order.name || "order").replace(/[^a-z0-9]/gi, "_")}.txt`;
        const fiscalSettings = this.getFiscalSettings();
        const content = addFiscalSection(order, fileName);
        const { integrationMethod, apiEndpoint, osType } = fiscalSettings;

        if (integrationMethod === "api_integration") {
            try {
                const apiResult = await this.sendFiscalReceiptToApi(content, osType, apiEndpoint);
                return apiResult;
            } catch (error) {
                console.error("API integration failed:", error);
                return { success: false, message: "API integration failed: " + error.message };
            }
        } else {
            createDownload(content, fileName);
            return { success: true, message: "Local file created successfully" };
        }
    },

    async sendFiscalReceiptToApi(content, osType, apiEndpoint) {
        try {
            const commands = content.split("\n").filter((cmd) => cmd.trim() !== "");
            const finalApiEndpoint =
                apiEndpoint ||
                this.pos.config.fiscal_api_endpoint ||
                "http://localhost:65400/api/Receipt";

            const result = await this.sendReceiptToFiscalNet(commands, finalApiEndpoint);

            if (result && result.success !== false) {
                return {
                    success: true,
                    message: "FiscalNet API call completed successfully",
                    raw_response: result,
                };
            } else {
                const errorMessage =
                    result?.message || result?.error || "Unknown error occurred";
                this.env.services.notification.add(errorMessage, {
                    type: "danger",
                    sticky: true,
                });
                return { success: false, message: errorMessage };
            }
        } catch (error) {
            let errorMessage = error.message || "Unknown error occurred";
            this.env.services.notification.add(errorMessage, {
                type: "danger",
                sticky: true,
            });
            this.dialog.add(AlertDialog, {
                title: "FiscalNet API Error",
                body: errorMessage,
            });
            return { success: false, message: errorMessage };
        }
    },

    async sendReceiptToFiscalNet(commands, apiEndpoint) {
        try {
            const xhr_result = await this.sendViaXHR(apiEndpoint, commands);
            return xhr_result;
        } catch (xhrError) {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 10000);

            const response = await fetch(apiEndpoint, {
                method: "POST",
                mode: "cors",
                cache: "no-cache",
                headers: {
                    Accept: "application/json",
                    "Content-Type": "application/json",
                },
                body: JSON.stringify(commands),
                signal: controller.signal,
            });

            clearTimeout(timeoutId);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            return await response.json();
        }
    },

    async sendViaXHR(apiEndpoint, commands) {
        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            xhr.open("POST", apiEndpoint, true);
            xhr.setRequestHeader("Content-Type", "application/json");
            xhr.setRequestHeader("Accept", "application/json");
            xhr.timeout = 10000;

            xhr.onreadystatechange = function () {
                if (xhr.readyState === 4) {
                    if (xhr.status >= 200 && xhr.status < 300) {
                        try {
                            resolve(JSON.parse(xhr.responseText));
                        } catch (e) {
                            resolve({ success: true, message: "Response received" });
                        }
                    } else {
                        reject(new Error(`XHR Error: ${xhr.status} - ${xhr.statusText}`));
                    }
                }
            };
            xhr.onerror = () => reject(new Error("XHR Network Error"));
            xhr.ontimeout = () => reject(new Error("XHR Timeout"));
            xhr.send(JSON.stringify(commands));
        });
    },

    async validateOrder(isForceValidate) {
        try {
            const order = this.currentOrder;

            // Handle card POS terminal notification
            const cardPaymentLine = order.payment_ids.find(
                (line) => line.payment_method_id && line.payment_method_id.is_card
            );

            if (cardPaymentLine) {
                const amountInCents = Math.round(cardPaymentLine.amount * 100);
                const command = `POS^${amountInCents}`;
                const fileName = `POS^VALOARE^${amountInCents}.txt`;
                const posConfig = this.pos.config;
                const integrationMethod = posConfig.fiscal_integration_method || "local_file";
                const osType = posConfig.fiscal_os_type || "windows";

                if (integrationMethod === "api_integration") {
                    const apiEndpoint =
                        posConfig.fiscal_api_endpoint || "http://localhost:65400/api/Receipt";
                    await this.sendFiscalReceiptToApi(command, osType, apiEndpoint);
                } else {
                    createDownload(command, fileName);
                }
            }

            // Process fiscal receipt BEFORE order validation
            const fiscalResult = await this.createAndSaveFiscalFile(order);

            if (fiscalResult && fiscalResult.success === false) {
                console.log("Fiscal processing failed, stopping order validation");
                return;
            }

            await super.validateOrder(...arguments);
        } catch (error) {
            console.error("validateOrder error:", error);
            await super.validateOrder(...arguments);
        }
    },
});

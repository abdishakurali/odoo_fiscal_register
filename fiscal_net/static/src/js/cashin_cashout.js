/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { CashMovePopup } from "@point_of_sale/app/components/popups/cash_move_popup/cash_move_popup";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { useService } from "@web/core/utils/hooks";

patch(CashMovePopup.prototype, {
    setup() {
        super.setup(...arguments);
        this.dialog = this.dialog || useService("dialog");
    },

    async confirm() {
        const amount = parseFloat(this.state.amount) || 0;
        const type = this.state.type;

        if (amount) {
            const lines = [];
            const fileName = type === "in" ? "bon_cashIn.txt" : "bon_cashOut.txt";
            const valuePrefix = type === "in" ? "I^" : "O^";
            const command = `${valuePrefix}${Math.round(amount * 100)}`;
            lines.push(command);

            const posConfig = this.pos.config;

            if (!posConfig) {
                console.error("POS Config not available");
            } else {
                const integrationMethod = posConfig.fiscal_integration_method || "local_file";
                const osType = posConfig.fiscal_os_type || "windows";
                const apiEndpoint =
                    posConfig.fiscal_api_endpoint || "http://localhost:65400/api/Receipt";

                console.log("Cash Operation - Integration Method:", integrationMethod);

                if (integrationMethod === "api_integration") {
                    console.log("Using API Integration for cash operation");
                    await this.sendCashOperationToApi(command, osType, type, apiEndpoint);
                } else {
                    console.log("Using Local File Mode for cash operation");
                    const blob = new Blob([lines], { type: "text/plain;charset=utf-8" });
                    try {
                        const url = URL.createObjectURL(blob);
                        const link = document.createElement("a");
                        link.href = url;
                        link.download = fileName;
                        document.body.appendChild(link);
                        link.click();
                        document.body.removeChild(link);
                        URL.revokeObjectURL(url);
                    } catch (error) {
                        console.error("Error saving file:", error);
                    }
                }
            }
        }

        await super.confirm(...arguments);
    },

    async sendCashOperationToApi(command, osType, operationType, apiEndpoint) {
        try {
            const commands = [command];
            const result = await this.sendReceiptToFiscalNet(commands, apiEndpoint);

            if (result && result.success !== false) {
                console.log(`Cash ${operationType} sent successfully to FiscalNet API`);
            } else {
                const errorMessage =
                    result?.message ||
                    result?.error ||
                    `Failed to send cash ${operationType} operation to API`;
                const detailedError = `FiscalNet API Error:\n${errorMessage}`;
                try {
                    this.notification.add(detailedError, { type: "danger", sticky: true });
                } catch (e) {
                    console.error("Notification error:", e);
                }
                this.dialog.add(AlertDialog, {
                    title: "FiscalNet API Error",
                    body: detailedError,
                });
            }
        } catch (error) {
            console.error("Browser-side API integration error:", error);
            let errorMessage = error.message || "Unknown error occurred";
            try {
                this.notification.add(errorMessage, { type: "danger", sticky: true });
            } catch (e) {
                console.error("Notification error:", e);
            }
            this.dialog.add(AlertDialog, {
                title: "FiscalNet API Error",
                body: errorMessage,
            });
        }
    },

    async sendReceiptToFiscalNet(commands, apiEndpoint) {
        const response = await fetch(apiEndpoint, {
            method: "POST",
            headers: {
                Accept: "application/json",
                "Content-Type": "application/json",
            },
            body: JSON.stringify(commands),
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        return await response.json();
    },
});

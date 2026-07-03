/** @odoo-module */

import { patch } from "@web/core/utils/patch";
import { OpeningControlPopup } from "@point_of_sale/app/components/popups/opening_control_popup/opening_control_popup";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { parseFloat } from "@web/views/fields/parsers";

patch(OpeningControlPopup.prototype, {
    async confirm() {
        const cleanValue = String(this.state.openingCash)
            .replace(/\./g, "")
            .replace(/,/g, ".")
            .replace(/[^\d.-]/g, "");
        const openingBalance = parseFloat(cleanValue) || 0;

        const command = `I^${Math.round(openingBalance * 100)}`;
        const fileName = "bon_openingBalance.txt";

        const posConfig = this.pos.config;
        if (!posConfig) {
            console.error("POS Config not available");
        } else {
            const integrationMethod = posConfig.fiscal_integration_method || "local_file";
            const apiEndpoint =
                posConfig.fiscal_api_endpoint || "http://localhost:65400/api/Receipt";

            console.log("Opening Balance - Integration Method:", integrationMethod);
            console.log("Opening Balance - Command:", command);

            if (integrationMethod === "api_integration") {
                console.log("Using API Integration for opening balance");
                await this.sendOpeningBalanceToApi(command, apiEndpoint);
            } else {
                console.log("Using Local File Mode for opening balance");
                const blob = new Blob([command], { type: "text/plain;charset=utf-8" });
                try {
                    if (window.navigator && window.navigator.msSaveOrOpenBlob) {
                        window.navigator.msSaveOrOpenBlob(blob, fileName);
                    } else {
                        const url = window.URL.createObjectURL(blob);
                        const link = document.createElement("a");
                        link.href = url;
                        link.setAttribute("download", fileName);
                        document.body.appendChild(link);
                        link.click();
                        document.body.removeChild(link);
                        window.URL.revokeObjectURL(url);
                    }
                } catch (error) {
                    console.error("Error saving file:", error);
                }
            }
        }

        await super.confirm(...arguments);
    },

    async sendOpeningBalanceToApi(command, apiEndpoint) {
        const commands = [command];
        console.log("Opening Balance API - Commands:", commands);
        console.log("Opening Balance API - Endpoint:", apiEndpoint);

        try {
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

            const responseData = await response.json();
            console.log("Opening Balance API response:", responseData);

            if (!responseData || responseData.success === false) {
                const errorMessage =
                    responseData?.message ||
                    responseData?.error ||
                    "Failed to send opening balance to API";
                console.error("FiscalNet API Error for opening balance:", errorMessage);
            }
        } catch (error) {
            console.error("Opening Balance API error:", error);
            // Non-blocking: log error but don't prevent session opening
        }
    },
});

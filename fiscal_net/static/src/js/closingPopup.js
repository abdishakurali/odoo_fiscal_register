/** @odoo-module */

import { ClosePosPopup } from "@point_of_sale/app/components/popups/closing_popup/closing_popup";
import { patch } from "@web/core/utils/patch";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";

patch(ClosePosPopup.prototype, {
    async cashinoutreport() {
        return this.report.doAction("fiscal_net.report_cash_book_action", [
            this.pos.session.id,
        ]);
    },

    async fiscalnetreport() {
        const closingBalance =
            this.state.payments[this.props.default_cash_details.id]?.counted || "0.00";
        const fileName = `bon_z_report.txt`;
        const command = `Z^${closingBalance}`;

        const posConfig = this.pos.config;
        if (!posConfig) {
            console.error("POS Config not available");
            return;
        }

        const integrationMethod = posConfig.fiscal_integration_method || "local_file";
        const osType = posConfig.fiscal_os_type || "windows";
        const apiEndpoint =
            posConfig.fiscal_api_endpoint || "http://localhost:65400/api/Receipt";

        console.log("Z Report - Integration Method:", integrationMethod);

        if (integrationMethod === "api_integration") {
            console.log("Using API Integration for Z report");
            await this.sendZReportToApi(command, osType, apiEndpoint);
        } else {
            console.log("Using Local File Mode for Z report");
            const blob = new Blob([[command]], { type: "text/plain;charset=utf-8" });
            try {
                if (window.navigator && window.navigator.msSaveOrOpenBlob) {
                    window.navigator.msSaveOrOpenBlob(blob, fileName);
                    return;
                }
                const url = window.URL.createObjectURL(blob);
                const link = document.createElement("a");
                link.href = url;
                link.setAttribute("download", fileName);
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
                window.URL.revokeObjectURL(url);
            } catch (error) {
                console.error("Error saving file:", error);
            }
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

    async sendZReportToApi(command, osType, apiEndpoint) {
        try {
            const commands = [command];
            const result = await this.sendReceiptToFiscalNet(commands, apiEndpoint);

            if (result && result.success !== false) {
                console.log("Z Report sent successfully to FiscalNet API");
            } else {
                const errorMessage = result?.message || "Failed to send Z Report to API";
                const detailedError = `FiscalNet API Error:\n${errorMessage}`;
                try {
                    this.env.services.notification.add(detailedError, {
                        type: "danger",
                        sticky: true,
                    });
                } catch (e) {
                    console.error("Notification error:", e);
                }
                this.dialog.add(AlertDialog, {
                    title: "FiscalNet API Error",
                    body: detailedError,
                });
            }
        } catch (error) {
            console.error("Z Report API error:", error);
            const errorMessage = `API Integration Error:\n${error.message || "Unknown error"}`;
            try {
                this.env.services.notification.add(errorMessage, {
                    type: "danger",
                    sticky: true,
                });
            } catch (e) {
                console.error("Notification error:", e);
            }
            this.dialog.add(AlertDialog, {
                title: "API Integration Error",
                body: errorMessage,
            });
        }
    },
});

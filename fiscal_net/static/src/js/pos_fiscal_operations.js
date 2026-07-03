/** @odoo-module */
import { PaymentScreen } from "@point_of_sale/app/screens/payment_screen/payment_screen";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

/**
 * Handles fiscal operations command generation and file creation
 */
class FiscalOperations {
    static formatAmount(amount) {
        return Math.round(amount * 100);
    }

    static createCashInCommand(amount) {
        const amountInCents = this.formatAmount(amount);
        return `I^${amountInCents}\n`;
    }

    static createCashOutCommand(amount) {
        const amountInCents = this.formatAmount(amount);
        return `O^${amountInCents}\n`;
    }

    static createDrawerCommand() {
        return "DS^\n";
    }

    static async createFiscalFile(content, fileName) {
        const blob = new Blob([content], { type: "text/plain;charset=utf-8" });

        return new Promise((resolve, reject) => {
            try {
                const url = window.URL.createObjectURL(blob);
                const link = document.createElement("a");
                link.href = url;
                link.setAttribute("download", fileName);
                document.body.appendChild(link);
                link.click();

                setTimeout(() => {
                    document.body.removeChild(link);
                    window.URL.revokeObjectURL(url);
                    resolve();
                }, 100);
            } catch (error) {
                reject(new Error(`Could not create fiscal file: ${error.message}`));
            }
        });
    }
}

patch(PaymentScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.notification = useService("notification");
    },

    async _onClickOpenCashbox() {
        try {
            await super._onClickOpenCashbox(...arguments);
            const fileName = `drawer_${Date.now()}.txt`;
            const command = FiscalOperations.createDrawerCommand();
            await FiscalOperations.createFiscalFile(command, fileName);
            this.notification.add("Drawer opening command sent", {
                type: "success",
                sticky: false,
            });
        } catch (error) {
            console.error("Drawer operation error:", error);
            this.notification.add(`Failed to open drawer: ${error.message}`, {
                type: "danger",
                sticky: true,
            });
        }
    },
});

export { FiscalOperations };

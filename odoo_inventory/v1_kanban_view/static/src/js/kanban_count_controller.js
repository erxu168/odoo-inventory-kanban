/** @odoo-module **/
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { useService } from "@web/core/utils/hooks";
import { useState } from "@odoo/owl";

/**
 * KanbanCountController
 * Extends the standard KanbanController to add:
 * - Progress bar (counted / total)
 * - Save all button that validates the inventory
 */
export class KanbanCountController extends KanbanController {
    setup() {
        super.setup();
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.actionService = useService("action");
    }

    get progressStats() {
        const records = this.model.root.records || [];
        const total = records.length;
        const counted = records.filter(r => r.data.inventory_quantity_set).length;
        const pct = total ? Math.round((counted / total) * 100) : 0;
        return { total, counted, pending: total - counted, pct };
    }

    async onValidateInventory() {
        try {
            // Calls Odoo's built-in inventory validation
            await this.orm.call("stock.quant", "action_apply_inventory", [[]]);
            this.notification.add("Inventory validated successfully!", { type: "success" });
            await this.model.load();
        } catch (e) {
            this.notification.add("Validation failed. Check all items are counted.", {
                type: "danger",
            });
        }
    }
}

/** @odoo-module **/
import { Component, useState, useRef, useExternalListener } from "@odoo/owl";
import { KanbanRecord } from "@web/views/kanban/kanban_record";
import { NumpadDrawer } from "./numpad_drawer";
import { useService } from "@web/core/utils/hooks";

/**
 * KanbanCountRecord
 * Replaces the standard KanbanRecord for inventory counting.
 * Each card shows product info + a tappable count field.
 * Tapping the field opens the NumpadDrawer.
 */
export class KanbanCountRecord extends KanbanRecord {
    static template = "inventory_kanban_count.KanbanCountCard";
    static components = { ...KanbanRecord.components, NumpadDrawer };

    setup() {
        super.setup();
        this.state = useState({
            drawerOpen: false,
        });
        this.orm = useService("orm");
        this.notification = useService("notification");
    }

    // ── Computed getters ─────────────────────────────────

    get productName() {
        return this.props.record.data.product_id?.[1] || "—";
    }

    get locationName() {
        return this.props.record.data.location_id?.[1] || "—";
    }

    get expectedQty() {
        return this.props.record.data.quantity || 0;
    }

    get countedQty() {
        return this.props.record.data.inventory_quantity || 0;
    }

    get isCounted() {
        return this.props.record.data.inventory_quantity_set;
    }

    get uom() {
        return this.props.record.data.product_uom_id?.[1] || "";
    }

    get diffState() {
        return this.props.record.data.inventory_diff_state || "pending";
    }

    get diffValue() {
        return this.props.record.data.inventory_diff || 0;
    }

    get diffFormatted() {
        if (!this.isCounted) return null;
        const d = this.diffValue;
        if (Math.abs(d) < 0.005) return null;
        return d > 0 ? `+${d.toFixed(2)}` : d.toFixed(2);
    }

    get stripeClass() {
        const map = {
            pending: "stripe-pending",
            match: "stripe-match",
            over: "stripe-over",
            short: "stripe-short",
        };
        return map[this.diffState] || "stripe-pending";
    }

    get chipClass() {
        const map = {
            pending: "chip-pending",
            match: "chip-match",
            over: "chip-over",
            short: "chip-short",
        };
        return map[this.diffState] || "chip-pending";
    }

    get chipLabel() {
        const map = {
            pending: "Pending",
            match: "✓ Match",
            over: `+${this.diffValue.toFixed(2)} over`,
            short: `${this.diffValue.toFixed(2)} short`,
        };
        return map[this.diffState] || "Pending";
    }

    // ── Handlers ─────────────────────────────────────────

    openDrawer() {
        this.state.drawerOpen = true;
    }

    closeDrawer() {
        this.state.drawerOpen = false;
    }

    async onConfirm(qty) {
        const id = this.props.record.resId;
        try {
            await this.orm.call("stock.quant", "action_set_inventory_quantity", [[id], qty]);
            await this.props.record.load();
            this.closeDrawer();
            const diff = qty - this.expectedQty;
            const diffStr = Math.abs(diff) < 0.005
                ? "✓ Match"
                : diff > 0
                    ? `+${diff.toFixed(2)} over`
                    : `${Math.abs(diff).toFixed(2)} short`;
            this.notification.add(`${this.productName} — ${diffStr}`, {
                type: Math.abs(diff) < 0.005 ? "success" : "warning",
                sticky: false,
            });
        } catch (e) {
            this.notification.add("Failed to save count. Please retry.", { type: "danger" });
        }
    }

    async onSetMatch() {
        await this.onConfirm(this.expectedQty);
    }

    onSkip() {
        this.closeDrawer();
        this.notification.add(`Skipped — ${this.productName}`, {
            type: "warning",
            sticky: false,
        });
    }
}

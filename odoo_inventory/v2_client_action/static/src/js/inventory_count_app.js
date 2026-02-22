/** @odoo-module **/

import { Component, useState, onWillStart, onMounted } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

// ────────────────────────────────────────────────────────────
// NumpadDrawer sub-component
// ────────────────────────────────────────────────────────────
class NumpadDrawer extends Component {
    static template = "inventory_count_action.NumpadDrawer";
    static props = {
        item: Object,
        onConfirm: Function,
        onSkip: Function,
        onClose: Function,
    };

    setup() {
        this.state = useState({
            inputStr: this.props.item.inventory_quantity_set
                ? this.props.item.inventory_quantity.toFixed(2)
                : "",
        });
    }

    get isEmpty() { return !this.state.inputStr; }
    get uom()     { return this.props.item.uom_name || ""; }
    get expected(){ return this.props.item.quantity || 0; }

    get diff() {
        if (!this.state.inputStr) return null;
        return parseFloat(this.state.inputStr) - this.expected;
    }

    get diffFormatted() {
        if (this.diff === null) return "—";
        if (Math.abs(this.diff) < 0.005) return "±0";
        return this.diff > 0 ? `+${this.diff.toFixed(2)}` : this.diff.toFixed(2);
    }

    get diffClass() {
        if (this.diff === null) return "none";
        if (Math.abs(this.diff) < 0.005) return "zero";
        return this.diff > 0 ? "pos" : "neg";
    }

    get quickSets() {
        const exp = this.expected;
        return [
            { label: `✓ Match (${exp.toFixed(2)})`, value: exp.toFixed(2), cls: "match" },
            { label: "0.00", value: "0.00", cls: "" },
            { label: "Clear", value: "", cls: "clear" },
        ];
    }

    onKey(char) {
        if (char === "." && this.state.inputStr.includes(".")) return;
        if (this.state.inputStr.length >= 8) return;
        if (char === "." && !this.state.inputStr) this.state.inputStr = "0";
        if (char !== "." && this.state.inputStr === "0") this.state.inputStr = "";
        this.state.inputStr += char;
    }

    onDelete() { this.state.inputStr = this.state.inputStr.slice(0, -1); }
    onQuickSet(val) { this.state.inputStr = val; }

    async onConfirm() {
        if (!this.state.inputStr) return;
        await this.props.onConfirm(parseFloat(this.state.inputStr));
    }
}

// ────────────────────────────────────────────────────────────
// InventoryCountApp — main client action component
// ────────────────────────────────────────────────────────────
export class InventoryCountApp extends Component {
    static template = "inventory_count_action.InventoryCountApp";
    static components = { NumpadDrawer };
    static props = { action: Object, actionType: String };

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");

        this.state = useState({
            items: [],           // stock.quant records
            loading: true,
            activeItemId: null,  // which card has drawer open
            filter: "all",       // all | todo | done
            searchQuery: "",
        });

        onWillStart(async () => {
            await this.loadItems();
        });
    }

    // ── Data loading ──────────────────────────────────────

    async loadItems() {
        this.state.loading = true;
        const records = await this.orm.searchRead(
            "stock.quant",
            [["location_id.usage", "=", "internal"]],
            [
                "id",
                "product_id",
                "location_id",
                "lot_id",
                "quantity",
                "inventory_quantity",
                "inventory_quantity_set",
                "product_uom_id",
            ],
            { limit: 200 }
        );
        // Normalise
        this.state.items = records.map(r => ({
            ...r,
            product_name: r.product_id[1],
            location_name: r.location_id[1],
            lot_name: r.lot_id ? r.lot_id[1] : null,
            uom_name: r.product_uom_id ? r.product_uom_id[1] : "",
        }));
        this.state.loading = false;
    }

    // ── Derived state ─────────────────────────────────────

    get filteredItems() {
        let items = this.state.items;
        if (this.state.searchQuery) {
            const q = this.state.searchQuery.toLowerCase();
            items = items.filter(i =>
                i.product_name.toLowerCase().includes(q) ||
                i.location_name.toLowerCase().includes(q)
            );
        }
        if (this.state.filter === "todo") return items.filter(i => !i.inventory_quantity_set);
        if (this.state.filter === "done") return items.filter(i => i.inventory_quantity_set);
        return items;
    }

    get todoItems() { return this.filteredItems.filter(i => !i.inventory_quantity_set); }
    get doneItems()  { return this.filteredItems.filter(i => i.inventory_quantity_set); }

    get progress() {
        const total = this.state.items.length;
        const counted = this.state.items.filter(i => i.inventory_quantity_set).length;
        return {
            total,
            counted,
            pending: total - counted,
            pct: total ? Math.round((counted / total) * 100) : 0,
        };
    }

    get activeItem() {
        return this.state.items.find(i => i.id === this.state.activeItemId) || null;
    }

    getDiffState(item) {
        if (!item.inventory_quantity_set) return "pending";
        const diff = item.inventory_quantity - item.quantity;
        if (Math.abs(diff) < 0.005) return "match";
        return diff > 0 ? "over" : "short";
    }

    getDiffLabel(item) {
        const state = this.getDiffState(item);
        if (state === "pending") return "Pending";
        if (state === "match")   return "✓ Match";
        const diff = item.inventory_quantity - item.quantity;
        return diff > 0 ? `+${diff.toFixed(2)} over` : `${Math.abs(diff).toFixed(2)} short`;
    }

    // ── Handlers ─────────────────────────────────────────

    openDrawer(itemId) {
        this.state.activeItemId = itemId;
    }

    closeDrawer() {
        this.state.activeItemId = null;
    }

    async onConfirmCount(qty) {
        const item = this.activeItem;
        if (!item) return;
        try {
            await this.orm.write("stock.quant", [item.id], {
                inventory_quantity: qty,
                inventory_quantity_set: true,
            });
            // Update local state instantly (optimistic UI)
            item.inventory_quantity = qty;
            item.inventory_quantity_set = true;
            this.closeDrawer();

            const diff = qty - item.quantity;
            const msg = Math.abs(diff) < 0.005
                ? `${item.product_name} — ✓ Match`
                : diff > 0
                    ? `${item.product_name} — +${diff.toFixed(2)} over`
                    : `${item.product_name} — ${Math.abs(diff).toFixed(2)} short`;

            this.notification.add(msg, {
                type: Math.abs(diff) < 0.005 ? "success" : "warning",
            });
        } catch (e) {
            this.notification.add("Failed to save count", { type: "danger" });
        }
    }

    async onSetMatch(item) {
        await this.orm.write("stock.quant", [item.id], {
            inventory_quantity: item.quantity,
            inventory_quantity_set: true,
        });
        item.inventory_quantity = item.quantity;
        item.inventory_quantity_set = true;
        this.notification.add(`${item.product_name} — ✓ Match`, { type: "success" });
    }

    onSkip() {
        const item = this.activeItem;
        this.notification.add(`Skipped — ${item?.product_name || "item"}`, { type: "warning" });
        this.closeDrawer();
    }

    async onValidate() {
        try {
            await this.orm.call("stock.quant", "action_apply_inventory", [[]]);
            this.notification.add("✓ Inventory validated!", { type: "success" });
            await this.loadItems();
        } catch (e) {
            this.notification.add("Validation failed", { type: "danger" });
        }
    }

    onSearchInput(ev) {
        this.state.searchQuery = ev.target.value;
    }

    setFilter(f) {
        this.state.filter = f;
    }
}

// Register as client action
registry.category("actions").add("inventory_count_action", InventoryCountApp);

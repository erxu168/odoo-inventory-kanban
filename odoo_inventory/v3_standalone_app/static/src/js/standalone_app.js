/** @odoo-module **/
/**
 * standalone_app.js
 * Root OWL component for the standalone inventory count app.
 * Bootstrapped by standalone_main.js via owl.mount().
 */

import { Component, useState, onWillStart } from "@odoo/owl";
import { InventoryService } from "./standalone_service";

// ────────────────────────────────────────────────────────────────
// Numpad Drawer
// ────────────────────────────────────────────────────────────────
class NumpadDrawer extends Component {
    static template = "inventory_count_standalone.NumpadDrawer";
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
            saving: false,
        });
    }

    get isEmpty()   { return !this.state.inputStr; }
    get uom()       { return this.props.item.uom_name || ""; }
    get expected()  { return this.props.item.quantity || 0; }

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
        if (!this.state.inputStr || this.state.saving) return;
        this.state.saving = true;
        await this.props.onConfirm(parseFloat(this.state.inputStr));
        this.state.saving = false;
    }
}

// ────────────────────────────────────────────────────────────────
// Toast notification (standalone, no Odoo notification service)
// ────────────────────────────────────────────────────────────────
class Toast extends Component {
    static template = "inventory_count_standalone.Toast";
    static props = { message: String, type: String };
}

// ────────────────────────────────────────────────────────────────
// Main App
// ────────────────────────────────────────────────────────────────
export class InventoryCountStandaloneApp extends Component {
    static template = "inventory_count_standalone.App";
    static components = { NumpadDrawer, Toast };

    setup() {
        this.state = useState({
            items: [],
            loading: true,
            error: null,
            activeItemId: null,
            searchQuery: "",
            filter: "all",        // all | todo | done
            toast: null,          // { message, type }
            validating: false,
            locations: [],
            selectedLocationId: null,
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    // ── Data ──────────────────────────────────────────────

    async loadData() {
        this.state.loading = true;
        this.state.error = null;
        try {
            const [items, locations] = await Promise.all([
                InventoryService.getItems(this.state.selectedLocationId),
                InventoryService.getLocations(),
            ]);
            this.state.items = items.map(r => ({
                ...r,
                product_name: Array.isArray(r.product_id) ? r.product_id[1] : r.product_id,
                location_name: Array.isArray(r.location_id) ? r.location_id[1] : r.location_id,
                lot_name: r.lot_id ? (Array.isArray(r.lot_id) ? r.lot_id[1] : r.lot_id) : null,
                uom_name: r.product_uom_id ? (Array.isArray(r.product_uom_id) ? r.product_uom_id[1] : r.product_uom_id) : "",
            }));
            this.state.locations = locations;
        } catch (e) {
            this.state.error = e.message || "Failed to load inventory data";
        }
        this.state.loading = false;
    }

    // ── Computed ──────────────────────────────────────────

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
        const s = this.getDiffState(item);
        if (s === "pending") return "Pending";
        if (s === "match")   return "✓ Match";
        const diff = item.inventory_quantity - item.quantity;
        return diff > 0 ? `+${diff.toFixed(2)} over` : `${Math.abs(diff).toFixed(2)} short`;
    }

    // ── Handlers ─────────────────────────────────────────

    openDrawer(id) { this.state.activeItemId = id; }
    closeDrawer()  { this.state.activeItemId = null; }

    async onConfirmCount(qty) {
        const item = this.activeItem;
        if (!item) return;
        try {
            const result = await InventoryService.setCount(item.id, qty);
            // Optimistic update
            item.inventory_quantity = result.inventory_quantity;
            item.inventory_quantity_set = true;
            this.closeDrawer();
            const diff = qty - item.quantity;
            const msg = Math.abs(diff) < 0.005
                ? `${item.product_name.split(",")[0]} — ✓ Match`
                : diff > 0
                    ? `${item.product_name.split(",")[0]} — +${diff.toFixed(2)} over`
                    : `${item.product_name.split(",")[0]} — ${Math.abs(diff).toFixed(2)} short`;
            this.showToast(msg, Math.abs(diff) < 0.005 ? "success" : "warning");
        } catch (e) {
            this.showToast("Failed to save. Check connection.", "error");
        }
    }

    async onSetMatch(item, ev) {
        ev.stopPropagation();
        try {
            await InventoryService.setCount(item.id, item.quantity);
            item.inventory_quantity = item.quantity;
            item.inventory_quantity_set = true;
            this.showToast(`${item.product_name.split(",")[0]} — ✓ Match`, "success");
        } catch (e) {
            this.showToast("Failed to save", "error");
        }
    }

    onSkip() {
        const item = this.activeItem;
        this.showToast(`Skipped — ${item?.product_name?.split(",")[0] || ""}`, "warning");
        this.closeDrawer();
    }

    async onValidate() {
        if (!confirm("Validate inventory and apply all adjustments?")) return;
        this.state.validating = true;
        try {
            await InventoryService.validate();
            this.showToast("✓ Inventory validated!", "success");
            await this.loadData();
        } catch (e) {
            this.showToast("Validation failed: " + e.message, "error");
        }
        this.state.validating = false;
    }

    onSearch(ev) { this.state.searchQuery = ev.target.value; }
    setFilter(f) { this.state.filter = f; }

    onLocationChange(ev) {
        const val = ev.target.value;
        this.state.selectedLocationId = val ? parseInt(val) : null;
        this.loadData();
    }

    // ── Toast ─────────────────────────────────────────────

    showToast(message, type = "success") {
        this.state.toast = { message, type };
        clearTimeout(this._toastTimer);
        this._toastTimer = setTimeout(() => { this.state.toast = null; }, 2500);
    }
}

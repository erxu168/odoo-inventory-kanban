/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, useState, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

// ============================================================
//  Mobile Physical Inventory - OWL Component
// ============================================================

/**
 * JSON-RPC helper for calling custom Odoo controller routes.
 * The `rpc` service is not available in standalone client actions
 * in Odoo 17+ / 19, so we use fetch directly.
 */
async function jsonRpc(route, params = {}) {
    const response = await fetch(route, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jsonrpc: "2.0", method: "call", params }),
    });
    const data = await response.json();
    if (data.error) {
        throw new Error(data.error.data?.message || data.error.message || "RPC Error");
    }
    return data.result;
}

class MobilePhysicalInventory extends Component {
    static template = "mobile_physical_inventory.App";

    setup() {
        // Use `orm` service for model reads; use jsonRpc() for custom routes
        this.orm = useService("orm");
        this.notification = useService("notification");

        this.state = useState({
            quants: [],
            locations: [],
            loading: false,
            searchText: "",
            selectedLocation: "",
            totalCount: 0,
            countedItems: 0,
            diffItems: 0,
            hasMore: false,
            offset: 0,
            limit: 20,
            showModal: false,
            showApplyBanner: false,
            newEntry: {
                location_id: "",
                productSearch: "",
                product_id: null,
                quantity: 0,
            },
            productSuggestions: [],
        });

        this._searchDebounce = null;
        this._productSearchDebounce = null;

        onMounted(() => {
            this._unlockScroll();
            this.loadLocations();
            this.loadQuants(true);
        });
    }

    // ---- Scroll unlock: walk up the DOM and remove any overflow:hidden ----
    _unlockScroll() {
        // Walk up from our root element and fix every ancestor that clips scroll
        let el = this.__owl__.bdom.el;
        while (el && el !== document.body) {
            const style = window.getComputedStyle(el);
            const overflow = style.overflow + style.overflowY + style.overflowX;
            if (overflow.includes("hidden") || overflow.includes("clip")) {
                el.style.setProperty("overflow", "visible", "important");
                el.style.setProperty("overflow-y", "visible", "important");
                el.style.setProperty("height", "auto", "important");
                el.style.setProperty("min-height", "0", "important");
                el.style.setProperty("max-height", "none", "important");
                el.style.setProperty("display", "block", "important");
            }
            el = el.parentElement;
        }
        // Make html + body scrollable
        document.documentElement.style.setProperty("overflow-y", "auto", "important");
        document.documentElement.style.setProperty("height", "auto", "important");
        document.body.style.setProperty("overflow-y", "auto", "important");
        document.body.style.setProperty("height", "auto", "important");
    }

    // ---- Data Loading ----

    async loadLocations() {
        try {
            const locations = await jsonRpc("/mobile_inventory/get_locations", {});
            this.state.locations = locations;
        } catch (e) {
            this.showToast("Failed to load locations", "error");
        }
    }

    async loadQuants(reset = false) {
        if (reset) {
            this.state.offset = 0;
            this.state.quants = [];
        }
        this.state.loading = true;
        try {
            const result = await jsonRpc("/mobile_inventory/get_quants", {
                location_id: this.state.selectedLocation || null,
                search: this.state.searchText,
                offset: this.state.offset,
                limit: this.state.limit,
            });
            const newQuants = result.quants.map(q => ({ ...q, modified: false }));
            this.state.quants = reset ? newQuants : [...this.state.quants, ...newQuants];
            this.state.totalCount = result.total;
            this.state.hasMore = (this.state.offset + this.state.limit) < result.total;
            this.updateStats();
        } catch (e) {
            this.showToast("Failed to load inventory data", "error");
        }
        this.state.loading = false;
    }

    async loadMore() {
        this.state.offset += this.state.limit;
        await this.loadQuants(false);
    }

    async refreshData() {
        await this.loadQuants(true);
        this.showToast("Refreshed!", "success");
    }

    // ---- Stats ----

    updateStats() {
        let counted = 0;
        let diff = 0;
        for (const q of this.state.quants) {
            if (q.inventory_quantity !== null && q.inventory_quantity !== undefined) {
                counted++;
            }
            if (q.inventory_diff_quantity && q.inventory_diff_quantity !== 0) {
                diff++;
            }
        }
        this.state.countedItems = counted;
        this.state.diffItems = diff;
    }

    // ---- Search / Filter ----

    onSearchInput() {
        clearTimeout(this._searchDebounce);
        this._searchDebounce = setTimeout(() => {
            this.loadQuants(true);
        }, 500);
    }

    onLocationChange(ev) {
        this.state.selectedLocation = ev.target.value ? parseInt(ev.target.value) : "";
        this.loadQuants(true);
    }

    // ---- Quantity Controls ----

    async adjustQty(quant, delta) {
        const newQty = Math.max(0, (parseFloat(quant.inventory_quantity) || 0) + delta);
        await this.saveQty(quant, newQty);
    }

    async onQtyChange(quant, ev) {
        const val = parseFloat(ev.target.value);
        if (!isNaN(val) && val >= 0) {
            await this.saveQty(quant, val);
        }
    }

    selectAll(ev) {
        ev.target.select();
    }

    async saveQty(quant, qty) {
        try {
            const result = await jsonRpc("/mobile_inventory/set_quantity", {
                quant_id: quant.id,
                quantity: qty,
            });
            if (result.success) {
                quant.inventory_quantity = result.inventory_quantity;
                quant.inventory_diff_quantity = result.inventory_diff_quantity;
                quant.modified = true;
                this.updateStats();
            } else {
                this.showToast("Error saving: " + (result.error || "Unknown error"), "error");
            }
        } catch (e) {
            this.showToast("Error saving quantity", "error");
        }
    }

    // ---- Apply All ----

    showApplyConfirm() {
        this.state.showApplyBanner = !this.state.showApplyBanner;
    }

    hideApplyBanner() {
        this.state.showApplyBanner = false;
    }

    async applyAll() {
        this.state.showApplyBanner = false;
        this.state.loading = true;
        try {
            const result = await jsonRpc("/mobile_inventory/apply_all", {
                location_id: this.state.selectedLocation || null,
            });
            if (result.success) {
                this.showToast("Inventory adjustments applied!", "success");
                await this.loadQuants(true);
            } else {
                this.showToast("Error: " + (result.error || "Could not apply"), "error");
            }
        } catch (e) {
            this.showToast("Error applying adjustments", "error");
        }
        this.state.loading = false;
    }

    // ---- Add Modal ----

    showAddModal() {
        this.state.newEntry = {
            location_id: this.state.selectedLocation || "",
            productSearch: "",
            product_id: null,
            quantity: 0,
        };
        this.state.productSuggestions = [];
        this.state.showModal = true;
    }

    hideModal() {
        this.state.showModal = false;
        this.state.productSuggestions = [];
    }

    hideModalOnOverlay(ev) {
        if (ev.target === ev.currentTarget) {
            this.hideModal();
        }
    }

    async onProductSearch() {
        clearTimeout(this._productSearchDebounce);
        const q = this.state.newEntry.productSearch;
        if (q.length < 2) {
            this.state.productSuggestions = [];
            return;
        }
        this._productSearchDebounce = setTimeout(async () => {
            try {
                const results = await this.orm.searchRead(
                    "product.product",
                    [["active", "=", true], ["name", "ilike", q]],
                    ["id", "display_name", "default_code"],
                    { limit: 10 }
                );
                this.state.productSuggestions = results;
            } catch (e) {
                // silently ignore search errors
            }
        }, 350);
    }

    selectProduct(prod) {
        this.state.newEntry.product_id = prod.id;
        this.state.newEntry.productSearch = prod.display_name;
        this.state.productSuggestions = [];
    }

    async saveNewEntry() {
        const entry = this.state.newEntry;
        if (!entry.location_id) {
            this.showToast("Please select a location", "error");
            return;
        }
        if (!entry.product_id) {
            this.showToast("Please select a product", "error");
            return;
        }
        try {
            const result = await jsonRpc("/mobile_inventory/create_quant", {
                product_id: entry.product_id,
                location_id: entry.location_id,
                quantity: parseFloat(entry.quantity) || 0,
            });
            if (result.success) {
                this.showToast("Product added to inventory!", "success");
                this.hideModal();
                await this.loadQuants(true);
            } else {
                this.showToast("Error: " + (result.error || "Failed to add"), "error");
            }
        } catch (e) {
            this.showToast("Error adding product", "error");
        }
    }

    // ---- Helpers ----

    formatQty(qty) {
        if (qty === null || qty === undefined) return "0";
        const n = parseFloat(qty);
        return isNaN(n) ? "0" : (Number.isInteger(n) ? n.toString() : n.toFixed(2).replace(/\.?0+$/, ""));
    }

    getDiffClass(quant) {
        if (!quant.inventory_diff_quantity || quant.inventory_diff_quantity === 0) return "";
        return quant.inventory_diff_quantity > 0 ? "has-diff-positive" : "has-diff-negative";
    }

    showToast(message, type = "") {
        const toast = document.createElement("div");
        toast.className = `mpi-toast ${type}`;
        toast.textContent = message;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 3000);
    }
}

// Register as client action
registry.category("actions").add("mobile_physical_inventory", MobilePhysicalInventory);

/**
 * standalone_service.js
 * Lightweight JSON-RPC client for the standalone inventory count app.
 * Does NOT depend on @web/core — works in the standalone bundle.
 */

/**
 * Low-level JSON-RPC call to an Odoo controller route.
 */
async function jsonRpc(route, params = {}) {
    const response = await fetch(route, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        },
        body: JSON.stringify({
            jsonrpc: "2.0",
            method: "call",
            id: Math.floor(Math.random() * 1e9),
            params,
        }),
    });

    if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const data = await response.json();
    if (data.error) {
        throw new Error(data.error.data?.message || data.error.message || "RPC Error");
    }
    return data.result;
}

/**
 * InventoryService — wraps all /inventory-count/* routes.
 */
export const InventoryService = {
    async getItems(locationId = null) {
        return jsonRpc("/inventory-count/items", { location_id: locationId });
    },

    async setCount(quantId, qty) {
        return jsonRpc("/inventory-count/set_count", { quant_id: quantId, qty });
    },

    async validate() {
        return jsonRpc("/inventory-count/validate", {});
    },

    async getLocations() {
        return jsonRpc("/inventory-count/locations", {});
    },
};

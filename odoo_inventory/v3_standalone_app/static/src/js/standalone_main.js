/**
 * standalone_main.js
 * Entry point for the standalone inventory count app.
 * Mounts the OWL app into #inventory_count_root after DOM is ready.
 *
 * Mirrors the pattern from pos_self_order/static/src/main.js
 */

import { whenReady, mount } from "@odoo/owl";
import { InventoryCountStandaloneApp } from "./standalone_app";

// Make all templates available (registered via QWeb template injection)
import "@odoo/owl";

whenReady(() => {
    const root = document.getElementById("inventory_count_root");
    if (!root) {
        console.error("[InventoryCount] Mount point #inventory_count_root not found.");
        return;
    }

    mount(InventoryCountStandaloneApp, root, {
        // OWL environment — minimal config for standalone
        env: {
            debug: (new URLSearchParams(window.location.search)).get("debug") === "1",
        },
        dev: false,
    });

    console.info("[InventoryCount] Standalone app mounted.");
});

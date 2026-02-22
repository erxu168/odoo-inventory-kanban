# Odoo 19 — Physical Inventory Kanban Count
## Three Implementation Approaches

---

## Overview

This package contains three Odoo 19 modules that implement the same UX design:
a two-column kanban board for physical inventory counting, with a slide-up numpad
drawer triggered by tapping any item's count field.

All three versions share the same UX design but differ in architecture, flexibility, and complexity.

---

## Version 1 — `inventory_kanban_count`
### Custom Kanban View (`js_class` approach)

**Complexity:** ★★☆☆☆ Low  
**Flexibility:** ★★★☆☆ Medium  
**Odoo Integration:** Highest — stays inside the standard `stock.quant` kanban view

### How it works
- Extends `stock.quant` with computed fields (`inventory_diff`, `inventory_diff_state`)
- Registers a new kanban view arch with `js_class="inventory_kanban_count"`
- OWL components inherit from `KanbanController`, `KanbanRenderer`, and `KanbanRecord`
- The `NumpadDrawer` component is injected inside each card
- Counts are saved via `orm.call("stock.quant", "action_set_inventory_quantity")`

### File structure
```
inventory_kanban_count/
├── __manifest__.py
├── __init__.py
├── models/
│   └── stock_inventory_line.py     ← Extends stock.quant
├── views/
│   └── inventory_kanban_view.xml   ← View arch + menu
├── security/
│   └── ir.model.access.csv
└── static/src/
    ├── js/
    │   ├── numpad_drawer.js            ← Slide-up numpad component
    │   ├── kanban_count_record.js      ← Custom KanbanRecord
    │   ├── kanban_count_renderer.js    ← Custom KanbanRenderer
    │   ├── kanban_count_controller.js  ← Custom KanbanController
    │   └── kanban_count_view.js        ← View registry registration
    ├── xml/
    │   ├── numpad_drawer.xml           ← Numpad QWeb template
    │   └── kanban_count_card.xml       ← Card QWeb template
    └── scss/
        └── kanban_count.scss
```

### When to use
- You want the feature accessible from standard Inventory menus
- You want Odoo's search/filter/group_by to still work
- You are extending, not replacing, the inventory workflow

---

## Version 2 — `inventory_count_action`
### Client Action (Full OWL control)

**Complexity:** ★★★☆☆ Medium  
**Flexibility:** ★★★★☆ High  
**Odoo Integration:** Medium — registered as `ir.actions.client`, accessible from menu

### How it works
- A single OWL component (`InventoryCountApp`) acts as the entire UI
- Registered in `registry.category("actions")` under `"inventory_count_action"`
- An `ir.actions.client` record with `tag="inventory_count_action"` wires it to a menu
- Data is loaded on mount via `useService("orm").searchRead()`
- Counts are saved via `useService("orm").write()`
- Validates via `orm.call("stock.quant", "action_apply_inventory")`
- Sub-components: `NumpadDrawer`, rendered conditionally when `activeItemId` is set

### File structure
```
inventory_count_action/
├── __manifest__.py
├── __init__.py
├── views/
│   └── client_action.xml           ← ir.actions.client + menu
├── security/
│   └── ir.model.access.csv
└── static/src/
    ├── js/
    │   └── inventory_count_app.js  ← Full app + NumpadDrawer component
    ├── xml/
    │   └── inventory_count_app.xml ← All QWeb templates
    └── scss/
        └── inventory_count.scss
```

### When to use
- You want full control over the UI without being constrained by Kanban view architecture
- You want to add features like location filtering, offline queuing, or custom workflows
- You are comfortable owning the full data loading and state management

---

## Version 3 — `inventory_count_standalone`
### Standalone OWL Application

**Complexity:** ★★★★☆ High  
**Flexibility:** ★★★★★ Maximum  
**Odoo Integration:** Lowest — separate URL, separate asset bundle, like POS self-order

### How it works
- Served at `/inventory-count` by `controllers/main.py`
- Has its own asset bundle `inventory_count_standalone.assets` (not `web.assets_backend`)
- OWL is bootstrapped via `mount(InventoryCountStandaloneApp, root)` in `standalone_main.js`
- Communicates with Odoo via a lightweight `InventoryService` (plain `fetch` JSON-RPC)
- Custom controller routes: `/inventory-count/items`, `/inventory-count/set_count`, `/inventory-count/validate`
- Includes simulated status bar, location filter dropdown, toast notifications (no Odoo services)
- Clock ticks in real-time (JS `setInterval`)
- Designed for a dedicated tablet or phone mounted in the warehouse

### File structure
```
inventory_count_standalone/
├── __manifest__.py
├── __init__.py
├── controllers/
│   ├── __init__.py
│   └── main.py                     ← HTTP routes + JSON-RPC handlers
├── views/
│   └── standalone_templates.xml    ← Shell HTML template
├── security/
│   └── ir.model.access.csv
└── static/src/
    ├── js/
    │   ├── standalone_service.js   ← Lightweight JSON-RPC client
    │   ├── standalone_app.js       ← Main OWL component + NumpadDrawer
    │   └── standalone_main.js      ← Bootstrap: mount() into #root
    ├── xml/
    │   └── standalone_app.xml      ← All QWeb templates
    └── scss/
        └── standalone.scss
```

### When to use
- Dedicated warehouse tablet/phone — no need for the full Odoo web client
- You want PWA installability (`manifest.json`, service worker)
- You want complete isolation from the Odoo backend JS framework
- You want the fastest possible load time on mobile hardware

---

## Installation

### Prerequisites
- Odoo 19.0
- Python 3.10+
- `stock` module installed

### Steps

1. Copy the module folder(s) into your Odoo addons path:
   ```bash
   cp -r inventory_kanban_count /path/to/odoo/addons/
   cp -r inventory_count_action /path/to/odoo/addons/
   cp -r inventory_count_standalone /path/to/odoo/addons/
   ```

2. Restart Odoo and update the app list:
   ```bash
   ./odoo-bin -c odoo.conf -u all
   ```
   Or from Settings → Apps → Update Apps List

3. Install the desired module(s):
   - V1: Search "Inventory Kanban Count"
   - V2: Search "Inventory Count Client Action"
   - V3: Search "Inventory Count Standalone"

4. Access:
   - V1 & V2: Inventory → Operations → Physical Inventory (Kanban) / (Pro)
   - V3: Navigate to `https://your-odoo.com/inventory-count`

---

## UX Features (all versions)

| Feature | V1 | V2 | V3 |
|---|---|---|---|
| Two-column kanban board | ✓ | ✓ | ✓ |
| Tap-to-open numpad drawer | ✓ | ✓ | ✓ |
| Live diff calculation | ✓ | ✓ | ✓ |
| "✓ Match" one-tap shortcut | ✓ | ✓ | ✓ |
| Coloured status stripes | ✓ | ✓ | ✓ |
| Progress bar | ✓ | ✓ | ✓ |
| Skip / requeue item | ✓ | ✓ | ✓ |
| Search filter | — | ✓ | ✓ |
| All / To Count / Done tabs | — | ✓ | ✓ |
| Location filter | — | — | ✓ |
| Toast notifications | Odoo service | Odoo service | Custom |
| Validate inventory | ✓ | ✓ | ✓ |
| Offline-ready | — | — | Extendable |
| PWA installable | — | — | ✓ |
| Mobile full-screen | — | — | ✓ |

---

## Development Notes

### OWL Patterns Used
- `useState` — reactive local component state
- `onWillStart` — async data loading before first render
- `useService("orm")` — Odoo ORM service (V1, V2 only)
- `useService("notification")` — Odoo notification service (V1, V2 only)
- Conditional rendering with `t-if`
- List rendering with `t-foreach`
- Event binding with `t-on-click` and `.bind` for method references

### Extending the modules
- Add barcode scanning: hook into `BarcodeScanner` service (V1/V2) or Web Barcode API (V3)
- Add lot/serial tracking: extend the card template to show lot selection
- Add image preview: extend `stock.quant` to include `product_id.image_128`
- Offline support for V3: add a Service Worker + IndexedDB sync queue

---

## Compatibility
- Odoo 19.0 ✓
- Odoo 18.0 — likely compatible with minor adjustments to `stock.quant` field names
- Odoo 17.0 — compatible; `inventory_quantity_set` field exists from v17
- Odoo 16.0 and below — uses different inventory model (`stock.inventory`), significant changes needed

---

## License
LGPL-3

/** @odoo-module **/
import { registry } from "@web/core/registry";
import { kanbanView } from "@web/views/kanban/kanban_view";
import { KanbanCountController } from "./kanban_count_controller";
import { KanbanCountRenderer } from "./kanban_count_renderer";

/**
 * inventory_kanban_count view
 * Registered as js_class="inventory_kanban_count" in the XML arch.
 * Inherits everything from the standard kanban view, swapping
 * Controller and Renderer for our custom versions.
 */
export const inventoryKanbanCountView = {
    ...kanbanView,
    Controller: KanbanCountController,
    Renderer: KanbanCountRenderer,
    display: {
        ...kanbanView.display,
    },
};

registry.category("views").add("inventory_kanban_count", inventoryKanbanCountView);

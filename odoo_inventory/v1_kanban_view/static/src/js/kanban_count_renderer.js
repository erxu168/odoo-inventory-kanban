/** @odoo-module **/
import { KanbanRenderer } from "@web/views/kanban/kanban_renderer";
import { KanbanCountRecord } from "./kanban_count_record";

/**
 * KanbanCountRenderer
 * Swaps the default KanbanRecord for KanbanCountRecord,
 * and renders a two-column layout: "To Count" | "Counted"
 */
export class KanbanCountRenderer extends KanbanRenderer {
    static components = {
        ...KanbanRenderer.components,
        KanbanRecord: KanbanCountRecord,
    };

    /**
     * Override to split records into two explicit columns
     * instead of using Odoo's group_by mechanism for display.
     */
    get todoRecords() {
        return (this.props.list?.records || []).filter(
            r => !r.data.inventory_quantity_set
        );
    }

    get doneRecords() {
        return (this.props.list?.records || []).filter(
            r => r.data.inventory_quantity_set
        );
    }
}

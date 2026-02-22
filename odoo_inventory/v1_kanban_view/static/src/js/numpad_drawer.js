/** @odoo-module **/
import { Component, useState, useRef, onMounted } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

/**
 * NumpadDrawer
 * A slide-up bottom sheet with a numeric keypad.
 * Emits: confirm(qty), skip(), close()
 */
export class NumpadDrawer extends Component {
    static template = "inventory_kanban_count.NumpadDrawer";
    static props = {
        record: { type: Object },
        onConfirm: { type: Function },
        onSkip: { type: Function },
        onClose: { type: Function },
    };

    setup() {
        this.state = useState({
            inputStr: "",
            isOpen: false,
        });
        this.notification = useService("notification");

        // Open with animation on mount
        onMounted(() => {
            requestAnimationFrame(() => {
                this.state.isOpen = true;
                // Pre-fill if already counted
                if (this.props.record.data.inventory_quantity_set) {
                    this.state.inputStr = this.props.record.data.inventory_quantity.toFixed(2);
                }
            });
        });
    }

    // ── Computed ──────────────────────────────────────────

    get displayValue() {
        return this.state.inputStr || "";
    }

    get isEmpty() {
        return !this.state.inputStr;
    }

    get expectedQty() {
        return this.props.record.data.quantity;
    }

    get expectedQtyFormatted() {
        const uom = this.props.record.data.product_uom_id?.[1] || "";
        return `${this.expectedQty.toFixed(2)} ${uom}`;
    }

    get diff() {
        if (!this.state.inputStr) return null;
        return parseFloat(this.state.inputStr) - this.expectedQty;
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

    get confirmEnabled() {
        return !!this.state.inputStr;
    }

    get quickSets() {
        const exp = this.expectedQty;
        const sets = [
            { label: `✓ Match (${exp.toFixed(2)})`, value: exp.toFixed(2), cls: "match" },
        ];
        const floor = Math.floor(exp);
        if (floor !== exp && floor >= 0) {
            sets.push({ label: floor.toFixed(2), value: floor.toFixed(2), cls: "" });
        }
        sets.push({ label: "0.00", value: "0.00", cls: "" });
        sets.push({ label: "Clear", value: "", cls: "clear" });
        return sets;
    }

    // ── Numpad handlers ───────────────────────────────────

    onKey(char) {
        if (char === "." && this.state.inputStr.includes(".")) return;
        if (this.state.inputStr.length >= 8) return;
        if (char === "." && !this.state.inputStr) this.state.inputStr = "0";
        if (char !== "." && this.state.inputStr === "0") this.state.inputStr = "";
        this.state.inputStr += char;
    }

    onDelete() {
        this.state.inputStr = this.state.inputStr.slice(0, -1);
    }

    onQuickSet(value) {
        this.state.inputStr = value;
    }

    // ── Actions ───────────────────────────────────────────

    async onConfirm() {
        if (!this.confirmEnabled) return;
        await this.props.onConfirm(parseFloat(this.state.inputStr));
    }

    onSkip() {
        this.props.onSkip();
    }

    onClose() {
        this.state.isOpen = false;
        setTimeout(() => this.props.onClose(), 300);
    }
}

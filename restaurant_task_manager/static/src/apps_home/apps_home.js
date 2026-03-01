/** @odoo-module **/
import { Component } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class AppsHome extends Component {
    static template = "restaurant_task_manager.AppsHome";
    static props = ["*"];

    setup() {
        this.menuService = useService("menu");
    }

    get apps() {
        return this.menuService.getApps();
    }

    onAppClick(app) {
        this.menuService.selectMenu(app);
    }
}

registry.category("actions").add("apps_home", AppsHome);

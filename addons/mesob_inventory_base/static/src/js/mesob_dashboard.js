/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component } from "@odoo/owl";

class MesobInventoryDashboard extends Component {
    static template = "mesob_inventory_base.Dashboard";
}

registry.category("actions").add("mesob_inventory_dashboard", MesobInventoryDashboard);

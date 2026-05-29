/** @odoo-module **/

import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class MesobInventoryDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        
        this.state = useState({
            stats: {
                pendingRequisitions: 0,
                pendingIssues: 0,
                lowStockItems: 0,
                pendingGatePasses: 0,
                totalItems: 0,
                monthlyIssues: 0,
            },
            recentActivity: [],
            lowStockItems: [],
            loading: true,
        });

        onWillStart(async () => {
            await this.loadDashboardData();
        });
    }

    async loadDashboardData() {
        try {
            // Load statistics
            const [
                pendingRequisitions,
                pendingIssues,
                lowStockItems,
                pendingGatePasses,
                totalItems,
            ] = await Promise.all([
                this.orm.searchCount("mesob.inventory.requisition", [["state", "=", "draft"]]),
                this.orm.searchCount("mesob.inventory.issue.voucher", [["state", "=", "draft"]]),
                this.orm.searchCount("mesob.inventory.item", [["quantity_on_hand", "<", "reorder_level"]]),
                this.orm.searchCount("mesob.gate.pass", [["state", "=", "draft"]]),
                this.orm.searchCount("mesob.inventory.item", []),
            ]);

            this.state.stats = {
                pendingRequisitions,
                pendingIssues,
                lowStockItems,
                pendingGatePasses,
                totalItems,
                monthlyIssues: 0, // TODO: Calculate from current month
            };

            // Load recent activity
            const recentRequisitions = await this.orm.searchRead(
                "mesob.inventory.requisition",
                [],
                ["name", "requesting_department", "state", "create_date"],
                { limit: 5, order: "create_date desc" }
            );

            this.state.recentActivity = recentRequisitions;

            // Load low stock items
            const lowStock = await this.orm.searchRead(
                "mesob.inventory.item",
                [["quantity_on_hand", "<", "reorder_level"]],
                ["name", "quantity_on_hand", "reorder_level", "uom_id"],
                { limit: 10 }
            );

            this.state.lowStockItems = lowStock;
            this.state.loading = false;
        } catch (error) {
            console.error("Error loading dashboard data:", error);
            this.state.loading = false;
        }
    }

    openRequisitions() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "mesob.inventory.requisition",
            views: [[false, "list"], [false, "form"]],
            domain: [["state", "=", "draft"]],
            name: "Pending Requisitions",
        });
    }

    openIssueVouchers() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "mesob.inventory.issue.voucher",
            views: [[false, "list"], [false, "form"]],
            domain: [["state", "=", "draft"]],
            name: "Pending Issue Vouchers",
        });
    }

    openLowStock() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "mesob.inventory.item",
            views: [[false, "list"], [false, "form"]],
            domain: [["quantity_on_hand", "<", "reorder_level"]],
            name: "Low Stock Items",
        });
    }

    openGatePasses() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "mesob.gate.pass",
            views: [[false, "list"], [false, "form"]],
            domain: [["state", "=", "draft"]],
            name: "Pending Gate Passes",
        });
    }

    openAllItems() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "mesob.inventory.item",
            views: [[false, "list"], [false, "form"]],
            name: "All Inventory Items",
        });
    }

    getStateColor(state) {
        const colors = {
            draft: "warning",
            confirmed: "info",
            approved: "success",
            issued: "primary",
            received: "success",
            cancelled: "danger",
        };
        return colors[state] || "secondary";
    }

    getStateBadgeClass(state) {
        return `badge bg-${this.getStateColor(state)}`;
    }

    formatDate(dateString) {
        if (!dateString) return "";
        const date = new Date(dateString);
        return date.toLocaleDateString();
    }
}

MesobInventoryDashboard.template = "mesob_inventory_base.Dashboard";

registry.category("actions").add("mesob_inventory_dashboard", MesobInventoryDashboard);

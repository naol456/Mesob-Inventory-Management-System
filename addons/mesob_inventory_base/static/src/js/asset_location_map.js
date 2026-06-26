/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class AssetLocationMap extends Component {
    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            loading: true,
            total_assets: 0,
            main_store: 0,
            departments: {},
            state_counts: {},
        });

        onWillStart(async () => {
            await this.loadData();
        });
    }

    async loadData() {
        try {
            const data = await this.orm.call(
                "mesob.asset.dashboard",
                "get_asset_map_data",
                []
            );
            
            this.state.total_assets = data.total_assets;
            this.state.main_store = data.main_store_count;
            this.state.departments = data.department_counts;
            this.state.state_counts = data.state_counts;
            this.state.loading = false;
        } catch (error) {
            console.error("Failed to load asset map data:", error);
            this.state.loading = false;
        }
    }

    getDeptCount(deptName) {
        return this.state.departments[deptName] || 0;
    }

    async openLocation(location) {
        let domain = [];
        if (location === 'main_store') {
            domain = [['asset_state', '=', 'in_stock']];
        } else if (location === 'all') {
            domain = [];
        } else {
            // It's a state filter
            domain = [['asset_state', '=', location]];
        }
        
        await this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'mesob.asset.dashboard',
            view_mode: 'list,form',
            views: [[false, 'list'], [false, 'form']],
            domain: domain,
            name: `Assets - ${location}`,
        });
    }

    async openDepartment(deptName) {
        await this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: 'mesob.asset.dashboard',
            view_mode: 'list,form',
            views: [[false, 'list'], [false, 'form']],
            domain: [['using_department_id.name', '=', deptName]],
            name: `Assets - ${deptName}`,
        });
    }
}

AssetLocationMap.template = "mesob_inventory_base.AssetLocationMapTemplate";

registry.category("actions").add("mesob_asset_location_map", AssetLocationMap);

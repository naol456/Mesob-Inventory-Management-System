/** @odoo-module **/

import { NavBar } from "@web/webclient/navbar/navbar";
import { patch } from "@web/core/utils/patch";

/**
 * Patch NavBar to organize overflow menu items hierarchically
 * Parent menus show submenus on hover instead of flat list
 */
patch(NavBar.prototype, {
    
    /**
     * After mounting, reorganize the "More" menu
     */
    setup() {
        super.setup();
        
        // Wait for DOM to be ready
        setTimeout(() => {
            this.organizeMoreMenu();
        }, 1000);
    },
    
    /**
     * Reorganize overflow menu items into hierarchical structure
     */
    organizeMoreMenu() {
        // Find the "More" dropdown menu
        const moreMenu = document.querySelector('.o_menu_sections .o-dropdown--menu');
        if (!moreMenu) {
            console.log('Mesob Menu: More menu not found');
            return;
        }
        
        console.log('Mesob Menu: Organizing hierarchical menu...');
        
        // Parent menus that should have submenus
        const parentMenuConfig = [
            {
                name: 'Stock-Taking & Handovers',
                children: ['Physical Stock Taking', 'Storekeeper Handovers']
            },
            {
                name: 'Master Data',
                children: ['Major Classifications', 'Sub Classifications', 'Departments']
            },
            {
                name: 'Storage, Safety & Security',
                children: ['Layout Plans', 'Key Custody Ledger', 'Visitor Logbook', 'Safety & Fire Inspections']
            }
        ];
        
        // Get all menu items
        const allItems = Array.from(moreMenu.querySelectorAll('.dropdown-item'));
        console.log('Mesob Menu: Found', allItems.length, 'menu items');
        
        parentMenuConfig.forEach(config => {
            // Find parent item
            const parentItem = allItems.find(item => 
                item.textContent.trim() === config.name
            );
            
            if (!parentItem) {
                console.log('Mesob Menu: Parent not found:', config.name);
                return;
            }
            
            console.log('Mesob Menu: Processing parent:', config.name);
            
            // Mark as having submenu
            parentItem.classList.add('has-submenu');
            parentItem.setAttribute('data-has-submenu', 'true');
            
            // Prevent default click action on parent
            parentItem.style.pointerEvents = 'auto';
            parentItem.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
            });
            
            // Create submenu container
            let submenu = parentItem.querySelector('.dropdown-submenu');
            if (!submenu) {
                submenu = document.createElement('div');
                submenu.className = 'dropdown-submenu';
                parentItem.appendChild(submenu);
            }
            
            // Move child items into submenu
            let foundChildren = 0;
            config.children.forEach(childName => {
                const childItem = allItems.find(item => 
                    item.textContent.trim() === childName
                );
                
                if (childItem && childItem !== parentItem) {
                    // Clone and add to submenu
                    const clonedChild = childItem.cloneNode(true);
                    clonedChild.style.display = 'block';
                    submenu.appendChild(clonedChild);
                    
                    // Hide original
                    childItem.style.display = 'none';
                    foundChildren++;
                }
            });
            
            console.log('Mesob Menu: Added', foundChildren, 'children to', config.name);
        });
        
        console.log('Mesob Menu: Organization complete');
    }
    
});

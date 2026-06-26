/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { NavBar } from "@web/webclient/navbar/navbar";

/**
 * Analytics & BI Menu - Multi-Column Layout Enhancement
 * Patches the NavBar component to apply grid layout to Analytics submenu items
 */

patch(NavBar.prototype, {
    /**
     * Apply multi-column grid layout to Analytics & BI submenu
     */
    setup() {
        super.setup(...arguments);
        
        // Wait for DOM to be ready
        this.env.bus.addEventListener("DOM_UPDATED", () => {
            this._applyAnalyticsMenuGridLayout();
        });
    },
    
    /**
     * Apply grid layout to Analytics & BI submenu items
     */
    _applyAnalyticsMenuGridLayout() {
        // Find the Analytics & BI menu and its submenu container
        const analyticsMenus = document.querySelectorAll('[data-menu-xmlid*="menu_analytics"], [data-section="analytics"]');
        
        analyticsMenus.forEach(menu => {
            const dropdown = menu.querySelector('.dropdown-menu');
            if (dropdown && !dropdown.classList.contains('analytics-grid-applied')) {
                // Apply grid layout class
                dropdown.classList.add('analytics-grid-layout', 'analytics-grid-applied');
                
                // Count items to determine optimal columns
                const items = dropdown.querySelectorAll('.dropdown-item, .o-dropdown-item');
                const itemCount = items.length;
                
                // Set grid columns based on item count
                if (itemCount >= 6) {
                    dropdown.classList.add('grid-cols-3');
                } else if (itemCount >= 4) {
                    dropdown.classList.add('grid-cols-2');
                }
                
                // Add hover effect enhancement
                items.forEach(item => {
                    if (!item.classList.contains('analytics-item-enhanced')) {
                        item.classList.add('analytics-menu-item', 'analytics-item-enhanced');
                    }
                });
            }
        });
    },
});

// Alternative approach: Direct DOM manipulation after page load
document.addEventListener('DOMContentLoaded', function() {
    // Use MutationObserver to catch dynamically loaded menus
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            mutation.addedNodes.forEach((node) => {
                if (node.nodeType === 1) { // Element node
                    applyAnalyticsGridLayout(node);
                }
            });
        });
    });
    
    // Start observing
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
    
    // Initial application
    applyAnalyticsGridLayout(document.body);
});

/**
 * Apply grid layout to analytics menu items
 * @param {Element} container - Container element to search within
 */
function applyAnalyticsGridLayout(container) {
    // Target Analytics & BI submenu specifically
    const selectors = [
        '[data-menu-xmlid="mesob_inventory_base.menu_mesob_analytics_bi"]',
        '.o_menu_sections [data-section*="analytic"]',
        '#menu_mesob_analytics_bi',
    ];
    
    selectors.forEach(selector => {
        const menus = container.querySelectorAll ? container.querySelectorAll(selector) : [];
        
        menus.forEach(menu => {
            // Find dropdown menu
            let dropdown = menu.querySelector('.dropdown-menu');
            if (!dropdown && menu.classList.contains('dropdown-menu')) {
                dropdown = menu;
            }
            
            if (dropdown && !dropdown.classList.contains('analytics-grid-applied')) {
                // Apply grid classes
                dropdown.classList.add('analytics-grid-layout', 'analytics-grid-applied');
                
                // Get all menu items
                const items = dropdown.querySelectorAll('.dropdown-item, .o-dropdown-item, a[role="menuitem"]');
                
                if (items.length > 0) {
                    // Determine column count
                    const cols = items.length >= 6 ? 3 : items.length >= 4 ? 2 : 1;
                    dropdown.style.display = 'grid';
                    dropdown.style.gridTemplateColumns = `repeat(${cols}, 1fr)`;
                    dropdown.style.gap = '12px';
                    dropdown.style.padding = '16px';
                    dropdown.style.minWidth = cols > 1 ? '650px' : '280px';
                    
                    // Style individual items
                    items.forEach(item => {
                        if (!item.classList.contains('analytics-item-styled')) {
                            item.style.padding = '14px 18px';
                            item.style.borderRadius = '8px';
                            item.style.background = 'rgba(212, 175, 55, 0.1)';
                            item.style.border = '1px solid rgba(212, 175, 55, 0.3)';
                            item.style.transition = 'all 0.25s ease';
                            item.classList.add('analytics-item-styled');
                            
                            // Add hover effect
                            item.addEventListener('mouseenter', function() {
                                this.style.background = 'rgba(212, 175, 55, 0.25)';
                                this.style.transform = 'translateY(-2px)';
                                this.style.boxShadow = '0 4px 8px rgba(212, 175, 55, 0.2)';
                            });
                            
                            item.addEventListener('mouseleave', function() {
                                this.style.background = 'rgba(212, 175, 55, 0.1)';
                                this.style.transform = 'translateY(0)';
                                this.style.boxShadow = 'none';
                            });
                        }
                    });
                }
            }
        });
    });
}

// Handle responsive resizing
window.addEventListener('resize', debounce(function() {
    const analyticsMenus = document.querySelectorAll('.analytics-grid-layout');
    analyticsMenus.forEach(dropdown => {
        const items = dropdown.querySelectorAll('.dropdown-item, .o-dropdown-item, a[role="menuitem"]');
        const width = window.innerWidth;
        
        let cols = 1;
        if (width > 1024 && items.length >= 6) {
            cols = 3;
        } else if (width > 768 && items.length >= 4) {
            cols = 2;
        }
        
        dropdown.style.gridTemplateColumns = `repeat(${cols}, 1fr)`;
        dropdown.style.minWidth = cols > 1 ? (cols === 3 ? '650px' : '450px') : '280px';
    });
}, 250));

/**
 * Debounce utility function
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

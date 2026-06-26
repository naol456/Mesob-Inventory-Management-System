/** @odoo-module **/

/**
 * Analytics & BI Menu - Horizontal Top Bar Layout
 * Ensures Analytics menu items appear as horizontal tabs in the navigation bar
 */

document.addEventListener('DOMContentLoaded', function() {
    // Apply horizontal layout to Analytics menu items
    applyHorizontalAnalyticsLayout();
    
    // Use MutationObserver to catch dynamically loaded menus
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            mutation.addedNodes.forEach((node) => {
                if (node.nodeType === 1) { // Element node
                    applyHorizontalAnalyticsLayout();
                }
            });
        });
    });
    
    // Start observing
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
});

/**
 * Apply horizontal layout styling to analytics menu items
 */
function applyHorizontalAnalyticsLayout() {
    // Target Analytics & BI menu items in the navbar
    const selectors = [
        '[data-menu-xmlid*="menu_analytics_"]',
        '.o_menu_sections button[data-menu-xmlid*="menu_analytics"]',
        '.o_menu_sections a[data-menu-xmlid*="menu_analytics"]',
    ];
    
    selectors.forEach(selector => {
        const menuItems = document.querySelectorAll(selector);
        
        menuItems.forEach(item => {
            if (!item.classList.contains('analytics-horizontal-styled')) {
                // Apply horizontal tab styling
                item.style.display = 'inline-flex';
                item.style.alignItems = 'center';
                item.style.padding = '8px 16px';
                item.style.margin = '0 2px';
                item.style.borderRadius = '6px';
                item.style.transition = 'all 0.25s ease';
                item.style.whiteSpace = 'nowrap';
                item.classList.add('analytics-horizontal-styled', 'analytics-menu-tab');
                
                // Add hover effects
                item.addEventListener('mouseenter', function() {
                    this.style.background = 'rgba(212, 175, 55, 0.25)';
                    this.style.borderColor = 'rgba(212, 175, 55, 0.4)';
                    this.style.transform = 'translateY(-1px)';
                });
                
                item.addEventListener('mouseleave', function() {
                    if (!this.classList.contains('active')) {
                        this.style.background = 'transparent';
                        this.style.transform = 'translateY(0)';
                    }
                });
                
                // Mark active state
                item.addEventListener('click', function() {
                    // Remove active from siblings
                    const siblings = document.querySelectorAll('.analytics-menu-tab');
                    siblings.forEach(sibling => {
                        sibling.classList.remove('active');
                        sibling.style.background = 'transparent';
                        sibling.style.fontWeight = '500';
                    });
                    
                    // Add active to clicked item
                    this.classList.add('active');
                    this.style.background = 'rgba(212, 175, 55, 0.35)';
                    this.style.fontWeight = '600';
                });
            }
        });
    });
    
    // Ensure menu sections container is horizontal
    const menuSections = document.querySelector('.o_menu_sections');
    if (menuSections && menuSections.querySelector('[data-menu-xmlid*="menu_analytics_"]')) {
        if (!menuSections.classList.contains('analytics-horizontal-container')) {
            menuSections.style.display = 'flex';
            menuSections.style.flexWrap = 'wrap';
            menuSections.style.alignItems = 'center';
            menuSections.style.gap = '4px';
            menuSections.classList.add('analytics-horizontal-container');
        }
    }
}

// Handle responsive behavior
window.addEventListener('resize', debounce(function() {
    const width = window.innerWidth;
    const menuItems = document.querySelectorAll('.analytics-menu-tab');
    
    if (width < 768) {
        // Mobile: Stack vertically
        menuItems.forEach(item => {
            item.style.display = 'flex';
            item.style.width = '100%';
            item.style.justifyContent = 'flex-start';
            item.style.padding = '10px 14px';
        });
        
        const menuSections = document.querySelector('.o_menu_sections');
        if (menuSections) {
            menuSections.style.flexDirection = 'column';
            menuSections.style.alignItems = 'stretch';
        }
    } else {
        // Desktop/Tablet: Horizontal
        menuItems.forEach(item => {
            item.style.display = 'inline-flex';
            item.style.width = 'auto';
            item.style.padding = width < 992 ? '6px 10px' : '8px 16px';
        });
        
        const menuSections = document.querySelector('.o_menu_sections');
        if (menuSections) {
            menuSections.style.flexDirection = 'row';
            menuSections.style.alignItems = 'center';
        }
    }
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

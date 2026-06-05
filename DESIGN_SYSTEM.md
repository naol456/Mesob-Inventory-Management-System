# Mesob Inventory Management System - Design System

## Overview
Professional UI design system that complements Odoo 19's default theme without conflicts.

## Color Palette

### Primary Colors
- **Primary Purple**: `#714B67` - Matches Odoo's default purple theme
- **Primary Hover**: `#5a3b52` - Darker shade for interactions
- **Primary Light**: `#f3f0f5` - Subtle background tints

### Status Colors
- **Success Green**: `#10b981` with light variant `#d1fae5`
- **Warning Amber**: `#f59e0b` with light variant `#fef3c7`
- **Danger Red**: `#ef4444` with light variant `#fee2e2`
- **Info Blue**: `#3b82f6` with light variant `#dbeafe`

### Neutral Grays
Professional gray scale from `50` (lightest) to `900` (darkest)
- Background: `#f9fafb` (gray-50)
- Borders: `#e5e7eb` (gray-200)
- Text: `#111827` (gray-900)
- Muted text: `#6b7280` (gray-500)

## Typography
- Uses Odoo's default font stack
- Semantic sizing through CSS variables
- Consistent weight hierarchy (400, 500, 600, 700)

## Components

### Classification Cards (`.mesob_classification_card`)
Modern kanban cards with:
- Clean white background
- Subtle shadows with hover effects
- Emoji icons for visual identity
- Badge indicators for counts
- Responsive footer actions

**Usage**: Major/Sub Classification kanban views

### Government Headers (`.mesob_gov_header`)
Professional document headers with:
- Purple gradient background
- White text with proper contrast
- Centered alignment
- Consistent spacing

**Usage**: Gate Pass, DSR, Model 19 forms

### Utility Classes
- `.mesob_card_*`: Card component parts (header, content, title, subtitle, badge, footer)
- `.mesob_flex*`: Flexbox utilities
- `.mesob_text_*`: Typography utilities

## Design Principles

1. **Harmony**: Complements Odoo's default theme, doesn't fight it
2. **Clarity**: Semantic class names, easy to understand
3. **Consistency**: Reusable components, predictable patterns
4. **Accessibility**: Proper contrast ratios, keyboard navigation
5. **Responsiveness**: Mobile-first approach with breakpoints
6. **Performance**: Minimal CSS, no conflicts, fast loading

## No Conflicts Guarantee
- No `!important` overrides (except where necessary for white text on colored backgrounds)
- No inline styles (all moved to CSS classes)
- No color overlaps (white backgrounds have proper colored text)
- No theme clashes (uses Odoo's color scheme as base)

## Browser Support
- Modern browsers (Chrome, Firefox, Edge, Safari)
- Progressive enhancement approach
- Print styles included

## Maintenance
All styles in single file: `static/src/scss/mesob_inventory.scss`
Loaded via: `views/mesob_inventory_assets.xml`

## Migration Notes
Replaced 2,890 lines of custom theme code with 318 lines of professional, maintainable CSS.

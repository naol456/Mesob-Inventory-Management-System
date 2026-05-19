# Mesob Inventory UI - Quick Reference Guide

## 🎨 CSS Classes Reference

### Layout Classes

```scss
.mesob_card                    // Modern card container
.mesob_kpi_card               // KPI metric card
.mesob_info_cards             // Grid container for info cards
.mesob_approval_flow          // Workflow visualization container
.mesob_approval_step          // Individual workflow step
.mesob_flow_arrow             // Arrow between workflow steps
.mesob_modern_header          // Enhanced header section
.mesob_modern_list            // Enhanced table/list styling
.mesob_form_title             // Enhanced form title
.mesob_section_title          // Section header styling
```

### State Classes

```scss
.mesob_approval_step.active      // Current workflow step
.mesob_approval_step.completed   // Completed workflow step
```

### Utility Classes

```scss
.mesob_text_muted             // Muted text color
.mesob_text_primary           // Primary brand color
.mesob_text_success           // Success color
.mesob_text_warning           // Warning color
.mesob_text_danger            // Danger color
.mesob_stock_indicator        // Stock level indicator
.mesob_abc_indicator          // ABC classification display
```

## 🎯 Common Patterns

### Info Cards Grid

```xml
<div class="row mesob_info_cards">
    <div class="col-md-3">
        <div class="mesob_card text-center">
            <i class="fa fa-icon fa-2x text-primary mb-2"/>
            <div class="fw-bold"><field name="field_name" readonly="1"/></div>
            <small class="text-muted">Label</small>
        </div>
    </div>
    <!-- Repeat for other cards -->
</div>
```

### Workflow Visualization

```xml
<div class="mesob_approval_flow">
    <div t-att-class="'mesob_approval_step ' + ('completed' if state in ['state1', 'state2'] else 'active' if state == 'draft' else '')">
        <i class="fa fa-icon fa-2x mb-2"/>
        <div class="fw-bold">Step Name</div>
        <small class="text-muted">Description</small>
    </div>
    <div class="mesob_flow_arrow">
        <i class="fa fa-arrow-right fa-2x"/>
    </div>
    <!-- Repeat for other steps -->
</div>
```

### Enhanced Title with Badge

```xml
<h1 class="mesob_form_title">
    <field name="name" readonly="1"/>
    <span t-if="state == 'draft'" class="badge badge-info ms-3">Draft</span>
    <span t-if="state == 'approved'" class="badge badge-success ms-3">Approved</span>
</h1>
```

### Alert Box

```xml
<div class="alert alert-info" role="alert">
    <i class="fa fa-info-circle"/> 
    <strong>Title:</strong> Message content here.
</div>
```

### Section with Title

```xml
<div class="mesob_card">
    <h4 class="mesob_section_title">
        <i class="fa fa-icon"/> Section Title
    </h4>
    <!-- Content here -->
</div>
```

## 🎨 Color Variables

```scss
// Primary Colors
var(--mesob-primary)           // #2563eb
var(--mesob-primary-dark)      // #1e40af
var(--mesob-primary-light)     // #3b82f6
var(--mesob-primary-subtle)    // #eff6ff

// Status Colors
var(--mesob-success)           // #10b981
var(--mesob-success-light)     // #d1fae5
var(--mesob-warning)           // #f59e0b
var(--mesob-warning-light)     // #fef3c7
var(--mesob-danger)            // #ef4444
var(--mesob-danger-light)      // #fee2e2
var(--mesob-info)              // #3b82f6
var(--mesob-info-light)        // #dbeafe

// Neutral Colors
var(--mesob-gray-50)           // #f9fafb
var(--mesob-gray-100)          // #f3f4f6
var(--mesob-gray-200)          // #e5e7eb
var(--mesob-gray-300)          // #d1d5db
var(--mesob-gray-500)          // #6b7280
var(--mesob-gray-700)          // #374151
var(--mesob-gray-900)          // #111827

// Spacing
var(--mesob-radius-sm)         // 6px
var(--mesob-radius-md)         // 8px
var(--mesob-radius-lg)         // 12px

// Shadows
var(--mesob-shadow-sm)         // Subtle shadow
var(--mesob-shadow-md)         // Medium shadow
var(--mesob-shadow-lg)         // Large shadow
var(--mesob-shadow-xl)         // Extra large shadow
```

## 📋 Badge Styles

```xml
<!-- Status Badges -->
<span class="badge badge-info">Info</span>
<span class="badge badge-primary">Primary</span>
<span class="badge badge-success">Success</span>
<span class="badge badge-warning">Warning</span>
<span class="badge badge-danger">Danger</span>
<span class="badge badge-secondary">Secondary</span>
<span class="badge badge-dark">Dark</span>

<!-- Pill Badges -->
<span class="badge badge-pill badge-success">Pill Badge</span>
```

## 🔘 Button Styles

```xml
<!-- Primary Action -->
<button class="btn-primary">Primary Action</button>

<!-- Success Action -->
<button class="btn-success">Approve</button>

<!-- Danger Action -->
<button class="btn-danger">Reject</button>

<!-- Stat Button -->
<button class="oe_stat_button" type="object" name="action_name" icon="fa-icon">
    <div class="o_stat_info">
        <span class="o_stat_value">123</span>
        <span class="o_stat_text">Label</span>
    </div>
</button>
```

## 📊 List View Decorations

```xml
<list class="mesob_modern_list"
      decoration-info="state == 'draft'"
      decoration-warning="state == 'submitted'"
      decoration-success="state == 'approved'"
      decoration-danger="state == 'rejected'"
      decoration-muted="state == 'cancelled'">
    <!-- Fields here -->
</list>
```

## 🎴 Kanban Card Template

```xml
<kanban class="mesob_item_kanban">
    <field name="name"/>
    <field name="state"/>
    <templates>
        <t t-name="kanban-box">
            <div class="oe_kanban_card mesob_kanban_record">
                <div class="oe_kanban_content">
                    <div class="o_kanban_record_top mb-2">
                        <div class="o_kanban_record_headings">
                            <strong class="o_kanban_record_title">
                                <field name="name"/>
                            </strong>
                        </div>
                        <span class="badge badge-info">Badge</span>
                    </div>
                    <div class="o_kanban_record_body">
                        <!-- Card content -->
                    </div>
                </div>
            </div>
        </t>
    </templates>
</kanban>
```

## 🎯 Icons Reference

Common FontAwesome icons used:

```
fa-cubes              // Inventory items
fa-file-text-o        // Documents/requisitions
fa-truck              // Shipping/receiving
fa-building           // Department/supplier
fa-user               // User/person
fa-calendar           // Dates
fa-check-circle       // Success/approved
fa-times-circle       // Rejected/cancelled
fa-exclamation-triangle // Warnings/DSR
fa-search             // Inspection
fa-shield             // Controlled items
fa-exchange           // Stock moves
fa-clock-o            // Pending/waiting
fa-paper-plane        // Submitted
fa-pencil             // Draft/edit
fa-undo               // Return
fa-files-o            // Copy distribution
fa-info-circle        // Information
```

## 📱 Responsive Classes

```xml
<!-- Bootstrap Grid -->
<div class="row">
    <div class="col-md-3 col-sm-6 col-12">
        <!-- Content -->
    </div>
</div>

<!-- Visibility -->
<div class="d-none d-md-block">Desktop only</div>
<div class="d-md-none">Mobile only</div>
```

## 🎨 Form Enhancement Pattern

```xml
<record id="view_model_form_enhanced" model="ir.ui.view">
    <field name="name">model.form.enhanced</field>
    <field name="model">your.model</field>
    <field name="inherit_id" ref="view_model_form"/>
    <field name="arch" type="xml">
        
        <!-- Add workflow visualization -->
        <xpath expr="//sheet/div[@class='oe_title']" position="before">
            <div class="mesob_approval_flow">
                <!-- Workflow steps -->
            </div>
        </xpath>

        <!-- Enhance title -->
        <xpath expr="//div[@class='oe_title']/h1" position="replace">
            <h1 class="mesob_form_title">
                <field name="name" readonly="1"/>
                <span class="badge badge-info ms-3">Status</span>
            </h1>
        </xpath>

        <!-- Add info cards -->
        <xpath expr="//group[1]" position="before">
            <div class="row mesob_info_cards">
                <!-- Info cards -->
            </div>
        </xpath>

        <!-- Hide original groups -->
        <xpath expr="//group[1]" position="attributes">
            <attribute name="invisible">1</attribute>
        </xpath>

    </field>
</record>
```

## 🔍 Testing Checklist

- [ ] Desktop view (> 992px)
- [ ] Tablet view (768px - 992px)
- [ ] Mobile view (< 768px)
- [ ] List view styling
- [ ] Form view styling
- [ ] Kanban view styling
- [ ] Button hover states
- [ ] Badge colors
- [ ] Workflow visualization
- [ ] Info cards display
- [ ] Print layout
- [ ] Dark mode (if applicable)

## 📝 Common Customizations

### Change Primary Color

```scss
// In mesob_inventory_modern.scss
:root {
    --mesob-primary: #your-color;
    --mesob-primary-dark: #darker-shade;
    --mesob-primary-light: #lighter-shade;
    --mesob-primary-subtle: #very-light-shade;
}
```

### Add Custom Card Style

```scss
// In mesob_inventory_components.scss
.mesob_custom_card {
    background: white;
    border-radius: var(--mesob-radius-lg);
    padding: 24px;
    box-shadow: var(--mesob-shadow-md);
    border: 1px solid var(--mesob-gray-200);
}
```

### Create Custom Badge

```scss
.badge-custom {
    background: var(--mesob-custom-light);
    color: var(--mesob-custom);
    font-weight: 600;
    padding: 6px 12px;
    border-radius: 12px;
}
```

---

**Quick Tip**: Use browser DevTools to inspect elements and see which classes are applied. All custom classes start with `mesob_` prefix.

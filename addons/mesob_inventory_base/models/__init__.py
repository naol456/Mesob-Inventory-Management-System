# ═══════════════════════════════════════════════════════════
# MIXINS (must be loaded FIRST - other models inherit from them)
# ═══════════════════════════════════════════════════════════
from . import mesob_notification_mixin  # Task 7: Notification system
from . import mesob_signable_mixin  # Task 11: Digital signatures
from . import mesob_stock_movement_mixin  # Stock movement tracking

# ═══════════════════════════════════════════════════════════
# CORE MODELS (Base classifications and items)
# ═══════════════════════════════════════════════════════════
from . import mesob_inventory_major_classification
from . import mesob_inventory_sub_classification
from . import mesob_item_code_sequence
from . import mesob_inventory_item
from . import mesob_stock_code_catalog
from . import mesob_stock_code_catalog_publication

# ═══════════════════════════════════════════════════════════
# DOCUMENT MODELS (Requisition, Receiving, Model 19, etc.)
# ═══════════════════════════════════════════════════════════
from . import mesob_inventory_requisition
from . import mesob_inventory_requisition_line
from . import mesob_inventory_receiving
from . import mesob_inventory_receiving_line
from . import mesob_inventory_model19
from . import mesob_inventory_model19_line
from . import mesob_inventory_dsr
from . import mesob_inventory_dsr_line
from . import mesob_inventory_issue_voucher
from . import mesob_gate_pass
from . import mesob_gate_pass_line

# ═══════════════════════════════════════════════════════════
# STOCK TRACKING (Bin Card, Record Card, Reorder)
# ═══════════════════════════════════════════════════════════
from . import mesob_bin_card
from . import mesob_stock_record_card
from . import mesob_stock_reorder_alert
from . import mesob_auto_po_generator  # MUST be after mesob_stock_reorder_alert (inherits from it)

# ═══════════════════════════════════════════════════════════
# PROCUREMENT & BUDGET
# ═══════════════════════════════════════════════════════════
from . import res_partner
from . import mesob_budget
from . import mesob_procurement
from . import mesob_payment_validation

# ═══════════════════════════════════════════════════════════
# AUTOMATION CALCULATION ENGINES
# ═══════════════════════════════════════════════════════════
# AUTO-009, 015, 030, 031, 035, 055: Lelisa's Automation Calculation Engines
from . import mesob_domestic_preference_calc
from . import mesob_liquidated_damages_calc
from . import mesob_price_adjustment_calc
from . import mesob_procurement_stock_reconciliation
from . import mesob_stock_accuracy_scorecard

# ═══════════════════════════════════════════════════════════
# STOCK TAKING & HANDOVER (Section 4.8)
# ═══════════════════════════════════════════════════════════
from . import mesob_stock_taking
from . import mesob_stock_handover

# ═══════════════════════════════════════════════════════════
# INVESTIGATION WORKFLOW (TEMPORARILY DISABLED FOR MODULE ACTIVATION)
# ═══════════════════════════════════════════════════════════
# AUTO-059: Stock Discrepancy Investigation Workflow
# from . import mesob_stock_discrepancy_investigation  # TODO: Re-enable after module loads

# ═══════════════════════════════════════════════════════════
# ADDITIONAL FEATURES (Task 7, 11, 12)
# ═══════════════════════════════════════════════════════════
from . import mesob_notification_preference  # Task 7: User notification preferences
from . import mesob_digital_signature  # Task 11: Digital signature records
from . import mesob_dashboard_kpi  # Task 12: Dashboard KPIs
# from . import mesob_contract_extensions  # TODO: Fix - invalid Python syntax (methods without class)
from . import mesob_storage_security  # Storage security tracking

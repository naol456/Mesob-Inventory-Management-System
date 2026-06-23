from . import mesob_inventory_major_classification
from . import mesob_inventory_sub_classification
from . import mesob_item_code_sequence
from . import mesob_inventory_item
from . import mesob_stock_code_catalog
from . import mesob_stock_code_catalog_publication
from . import mesob_stock_movement_mixin
from . import mesob_digital_signature  # Must be imported before signable_mixin
from . import mesob_notification_mixin  # Must be imported before models that inherit from it
from . import mesob_signable_mixin  # Must be imported before models that inherit from it
from . import mesob_notification_preference  # User notification preferences
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
from . import mesob_bin_card
from . import mesob_stock_record_card
from . import mesob_stock_reorder_alert
from . import mesob_stock_taking  # Stock taking events and sheets (Section 4.8)
from . import mesob_stock_handover  # Stock handover/takeover custody transfers (Section 4.9)
from . import mesob_auto_po_generator  # MUST be after mesob_stock_reorder_alert (inherits from it)
from . import res_partner
from . import mesob_budget
from . import mesob_procurement
from . import mesob_payment_validation
from . import mesob_complaint_portal  # AUTO-033: Self-service supplier complaint portal
from . import mesob_stock_fifo_batch  # AUTO-051: FIFO batch tracking for accurate stock valuation

# AUTO-009, 015, 030, 031, 035, 055: Lelisa's Automation Calculation Engines
from . import mesob_domestic_preference_calc
from . import mesob_liquidated_damages_calc
from . import mesob_price_adjustment_calc
from . import mesob_procurement_stock_reconciliation
from . import mesob_stock_accuracy_scorecard

# Additional modules
from . import mesob_contract_extensions  # Contract amendments and variations
from . import mesob_dashboard_kpi  # Dashboard KPI tracking
from . import mesob_storage_security  # Storage and security management

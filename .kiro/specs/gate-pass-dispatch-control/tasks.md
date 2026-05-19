# Implementation Plan: Gate Pass & Dispatch Control

## Overview

This implementation plan creates the Gate Pass & Dispatch Control module for the Mesob Inventory Management System. The module enforces FDRE-compliant material dispatch authorization, requiring PAO written authority for any materials leaving the compound. It integrates with the existing Issue Voucher (Model 22) workflow and implements three-copy distribution tracking for security control.

**Technology Stack:** Python (Odoo 19), PostgreSQL, XML views

## Tasks

- [x] 1. Set up module structure and core models
  - Create `models/mesob_gate_pass.py` with core Gate Pass model
  - Create `models/mesob_gate_pass_line.py` with line item model
  - Update `models/__init__.py` to import new models
  - Define all fields per design specification (name, state, dispatch_date, authorization fields, dispatch details, copy distribution flags)
  - Add mail.thread and mail.activity.mixin inheritance for audit trail
  - Set up model ordering by dispatch_date desc
  - _Requirements: 1.1, 1.3, 1.4, 1.5, 10.6_

- [ ] 2. Implement sequence generation and data integrity
  - [x] 2.1 Create sequence configuration in `data/mesob_gate_pass_sequence.xml`
    - Define sequence with code `mesob.gate.pass`
    - Set prefix format `GP/%(year)s/`
    - Configure padding to 4 digits with yearly reset
    - _Requirements: 1.1, 13.1, 13.2, 13.3, 13.4, 13.5_
  
  - [ ] 2.2 Implement auto-generation in model create method
    - Override `create()` to auto-assign sequence number
    - Ensure uniqueness constraint on name field
    - _Requirements: 1.1, 18.1_
  
  - [ ]* 2.3 Write property test for sequence uniqueness
    - **Property 1: Sequence Number Uniqueness and Format**
    - **Validates: Requirements 1.1, 13.1, 13.2, 13.3, 13.5, 18.1**
  
  - [ ]* 2.4 Write property test for sequence year reset
    - **Property 23: Sequence Counter Year Reset**
    - **Validates: Requirements 13.4**

- [ ] 3. Implement authorization document validation
  - [ ] 3.1 Add XOR constraint on authorization documents
    - Create `@api.constrains` method for `issue_voucher_id` and `written_authorization`
    - Enforce exactly one authorization method (not both, not neither)
    - Provide clear error messages
    - _Requirements: 1.5, 3.4, 3.5, 3.6, 18.5_
  
  - [ ] 3.2 Implement Issue Voucher validation method
    - Create `_validate_prerequisite_documents()` method
    - Verify Issue Voucher exists and is in valid state ("issued" or "received")
    - Verify Issue Voucher is properly signed
    - _Requirements: 2.3, 3.1, 3.2, 3.3, 18.2_
  
  - [ ]* 3.3 Write property test for authorization XOR constraint
    - **Property 2: Authorization Document XOR Constraint**
    - **Validates: Requirements 1.5, 3.4, 3.5, 3.6, 18.5**
  
  - [ ]* 3.4 Write property test for authorization prerequisite validation
    - **Property 7: Authorization Prerequisite Validation**
    - **Validates: Requirements 2.3, 3.1, 3.2, 3.3, 18.2**

- [ ] 4. Implement state machine and workflow
  - [ ] 4.1 Define state selection field
    - Add Selection field with states: draft, authorized, dispatched, cancelled
    - Set default to "draft"
    - Enable tracking for audit trail
    - _Requirements: 1.4, 6.1, 6.2_
  
  - [ ] 4.2 Implement PAO authorization action
    - Create `action_authorize()` method
    - Verify user has PAO role (`group_mesob_pao`)
    - Verify state is "draft"
    - Validate prerequisite documents
    - Validate required dispatch details
    - Set authorized_by_id and authorized_on
    - Transition state to "authorized"
    - Post audit message to chatter
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 6.2_
  
  - [ ] 4.3 Implement security guard dispatch action
    - Create `action_dispatch()` method
    - Verify user has Security Guard role (`group_mesob_security_guard`)
    - Verify state is "authorized"
    - Verify PAO authorization exists
    - Set all three copy distribution flags to TRUE
    - Set security_verified_by_id and security_verified_on
    - Transition state to "dispatched"
    - Post audit message to chatter
    - Update linked Issue Voucher if applicable
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 5.1, 5.2, 5.3, 5.4, 5.5, 8.4, 8.5_
  
  - [ ] 4.4 Implement cancellation action
    - Create `action_cancel()` method
    - Verify state is "draft" or "authorized" (not "dispatched")
    - Transition state to "cancelled"
    - Post audit message with cancellation reason
    - _Requirements: 6.4, 6.5, 16.1, 16.2, 16.3, 16.4, 16.6_
  
  - [ ] 4.5 Implement reset to draft action
    - Create `action_reset_to_draft()` method
    - Allow reset from "cancelled" state only
    - Transition state to "draft"
    - _Requirements: 6.6, 16.5_
  
  - [ ]* 4.6 Write property test for initial state
    - **Property 3: Initial State is Draft**
    - **Validates: Requirements 1.4, 6.1**
  
  - [ ]* 4.7 Write property test for state transition validity
    - **Property 12: State Transition Validity**
    - **Validates: Requirements 6.2, 6.3, 6.4, 6.5**
  
  - [ ]* 4.8 Write property test for PAO authorization invariant
    - **Property 6: PAO Authorization Invariant**
    - **Validates: Requirements 2.1, 2.2, 2.4, 2.5, 4.3**
  
  - [ ]* 4.9 Write property test for security guard dispatch invariant
    - **Property 9: Security Guard Dispatch Invariant**
    - **Validates: Requirements 4.1, 4.2, 4.4, 4.5**
  
  - [ ]* 4.10 Write property test for three-copy distribution
    - **Property 10: Three-Copy Distribution Completeness**
    - **Validates: Requirements 4.6, 5.1, 5.2, 5.3, 5.4**

- [ ] 5. Checkpoint - Ensure core workflow tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Implement immutability and security controls
  - [ ] 6.1 Override write() method for immutability
    - Prevent modification of dispatched Gate Passes
    - Allow only internal notes field for dispatched records
    - Raise UserError with clear message for unauthorized modifications
    - _Requirements: 7.1, 7.2, 7.3, 7.4_
  
  - [ ] 6.2 Implement role-based access checks
    - Create `_check_pao_role()` method
    - Create `_check_security_role()` method
    - Raise AccessError for unauthorized users
    - _Requirements: 2.7, 4.8, 12.4, 19.1_
  
  - [ ]* 6.3 Write property test for immutability after dispatch
    - **Property 14: Immutability After Dispatch**
    - **Validates: Requirements 7.1, 7.2, 7.3**
  
  - [ ]* 6.4 Write property test for non-PAO authorization rejection
    - **Property 8: Non-PAO Authorization Rejection**
    - **Validates: Requirements 2.7, 12.4, 19.1**
  
  - [ ]* 6.5 Write property test for non-security-guard dispatch rejection
    - **Property 11: Non-Security-Guard Dispatch Rejection**
    - **Validates: Requirements 4.8**

- [ ] 7. Implement line item model and validation
  - [ ] 7.1 Create Gate Pass Line model
    - Define all fields (gate_pass_id, item_id, description, quantity, uom_id, serial_numbers, remarks)
    - Add Many2one relation to parent Gate Pass
    - Add Many2one relation to inventory item
    - Set up cascade delete on parent deletion
    - _Requirements: 1.3, 11.1, 18.6_
  
  - [ ] 7.2 Implement line item validation
    - Add constraint for positive quantity
    - Validate item_id references valid inventory item
    - Require serial_numbers for serialized items
    - Default uom_id from item master if not specified
    - _Requirements: 11.2, 11.3, 11.4, 11.5, 11.6, 18.3, 18.4_
  
  - [ ] 7.3 Implement parent-level line validation
    - Add constraint on Gate Pass to require at least one line item
    - Validate all line items before authorization
    - _Requirements: 1.3, 11.5_
  
  - [ ]* 7.4 Write property test for line item requirements
    - **Property 4: Line Item Requirements**
    - **Validates: Requirements 1.3, 11.1, 11.2, 11.5, 11.6, 18.4**
  
  - [ ]* 7.5 Write property test for UOM defaulting
    - **Property 20: Line Item UOM Defaulting**
    - **Validates: Requirements 11.3**
  
  - [ ]* 7.6 Write property test for serialized item serial number requirement
    - **Property 21: Serialized Item Serial Number Requirement**
    - **Validates: Requirements 11.4**
  
  - [ ]* 7.7 Write property test for foreign key integrity
    - **Property 31: Foreign Key Integrity**
    - **Validates: Requirements 18.3**
  
  - [ ]* 7.8 Write property test for cascade delete
    - **Property 32: Cascade Delete Line Items**
    - **Validates: Requirements 18.6**

- [ ] 8. Implement Issue Voucher integration
  - [ ] 8.1 Create method to create Gate Pass from Issue Voucher
    - Implement `create_from_issue_voucher()` method
    - Validate Issue Voucher state and signatures
    - Auto-populate destination from Issue Voucher
    - Copy all line items with matching quantities and UOMs
    - Link Gate Pass to Issue Voucher
    - _Requirements: 1.2, 8.1, 8.2, 8.3_
  
  - [ ] 8.2 Add uniqueness constraint for Issue Voucher link
    - Prevent multiple Gate Passes for same Issue Voucher
    - Raise ValidationError with clear message
    - _Requirements: 8.6_
  
  - [ ] 8.3 Implement Issue Voucher update on dispatch
    - Update Issue Voucher dispatch status when Gate Pass dispatched
    - Set dispatch_date on Issue Voucher
    - _Requirements: 8.4, 8.5_
  
  - [ ]* 8.4 Write property test for Issue Voucher line copy completeness
    - **Property 5: Issue Voucher Line Copy Completeness**
    - **Validates: Requirements 1.2, 8.2, 8.3**
  
  - [ ]* 8.5 Write property test for Issue Voucher link and update
    - **Property 15: Issue Voucher Link and Update**
    - **Validates: Requirements 8.1, 8.4, 8.5**
  
  - [ ]* 8.6 Write property test for Issue Voucher uniqueness
    - **Property 16: Issue Voucher Uniqueness**
    - **Validates: Requirements 8.6**

- [ ] 9. Implement dispatch details validation
  - [ ] 9.1 Add validation for required dispatch details
    - Create `_validate_dispatch_details()` method
    - Verify destination, receiver_name, receiver_organization are provided
    - Call validation before authorization
    - _Requirements: 9.1, 9.2, 9.3, 9.6_
  
  - [ ] 9.2 Add optional vehicle and driver fields validation
    - Validate vehicle_plate, driver_name, driver_license if provided
    - _Requirements: 9.4, 9.5_
  
  - [ ]* 9.3 Write property test for required dispatch details
    - **Property 17: Required Dispatch Details Validation**
    - **Validates: Requirements 9.1, 9.2, 9.3, 9.6**

- [ ] 10. Checkpoint - Ensure business logic tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 11. Implement audit trail and tracking
  - [ ] 11.1 Configure field tracking
    - Enable tracking=True on all critical fields (state, authorized_by_id, security_verified_by_id, etc.)
    - Ensure mail.thread inheritance is working
    - _Requirements: 10.6_
  
  - [ ] 11.2 Implement audit logging for state transitions
    - Post chatter messages on create, authorize, dispatch, cancel actions
    - Include user, timestamp, and action details
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_
  
  - [ ] 11.3 Prevent audit trail deletion
    - Configure mail.message to prevent deletion for Gate Pass records
    - _Requirements: 10.7_
  
  - [ ]* 11.4 Write property test for audit trail completeness
    - **Property 18: Audit Trail Completeness**
    - **Validates: Requirements 2.6, 4.7, 10.1, 10.2, 10.3, 10.4, 10.5**
  
  - [ ]* 11.5 Write property test for audit trail immutability
    - **Property 19: Audit Trail Immutability**
    - **Validates: Requirements 10.7**

- [ ] 12. Implement security groups and access rights
  - [x] 12.1 Create access rights in `security/ir.model.access.csv`
    - Define access for PAO group (read, write, create, unlink)
    - Define access for Storekeeper group (read, write, create)
    - Define access for Security Guard group (read, write)
    - Define line item access for all groups
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6_
  
  - [x] 12.2 Create record rules in `security/mesob_gate_pass_rules.xml`
    - Create rule for PAO authorization (state=draft)
    - Create rule for Security Guard dispatch (state=authorized)
    - Restrict visibility based on roles
    - _Requirements: 12.1, 12.2, 12.3_
  
  - [ ]* 12.3 Write property test for role-based access control
    - **Property 22: Role-Based Access Control**
    - **Validates: Requirements 12.1, 12.2, 12.3, 12.5, 12.6**

- [ ] 13. Create form view for Gate Pass
  - [x] 13.1 Create `views/mesob_gate_pass_views.xml`
    - Design form view with header (state, buttons)
    - Add authorization section (Issue Voucher link, written authorization)
    - Add dispatch details section (destination, receiver, vehicle, driver)
    - Add line items notebook page with tree view
    - Add copy distribution section (readonly flags)
    - Add chatter (mail.thread)
    - _Requirements: 1.1, 1.2, 1.3, 1.5, 9.1, 9.2, 9.3, 9.4, 9.5_
  
  - [ ] 13.2 Add state-based field visibility and readonly
    - Make fields readonly when state="dispatched"
    - Show authorization buttons only in "draft" state
    - Show dispatch button only in "authorized" state
    - Show cancel button in "draft" and "authorized" states
    - _Requirements: 7.1, 7.2_
  
  - [ ] 13.3 Add smart buttons for related records
    - Add smart button to view linked Issue Voucher
    - Add smart button to view audit trail
    - _Requirements: 8.1_

- [ ] 14. Create tree and search views
  - [ ] 14.1 Create tree view for Gate Pass list
    - Display name, dispatch_date, destination, receiver_organization, state
    - Add color coding by state (draft=blue, authorized=orange, dispatched=green, cancelled=red)
    - _Requirements: 15.1, 15.2_
  
  - [ ] 14.2 Create search view with filters
    - Add filter by state (draft, authorized, dispatched, cancelled)
    - Add filter by dispatch date range
    - Add search by sequence number, destination, receiver organization
    - Add group by state, dispatch_date, authorized_by_id
    - _Requirements: 15.1, 15.2, 15.3, 15.4, 15.5_
  
  - [ ]* 14.3 Write property test for search and filter correctness
    - **Property 25: Search and Filter Correctness**
    - **Validates: Requirements 15.1, 15.2, 15.3, 15.4, 15.5**

- [ ] 15. Create menu items and actions
  - [ ] 15.1 Create window action for Gate Pass
    - Define action in `views/mesob_gate_pass_views.xml`
    - Set default view mode (tree, form)
    - Set default filter (pending authorization)
  
  - [x] 15.2 Add menu items in `views/mesob_inventory_menus.xml`
    - Add "Gate Pass" menu under "Dispatch" section
    - Add submenu for "Pending Authorization" (PAO view)
    - Add submenu for "Pending Dispatch" (Security Guard view)
    - Add submenu for "All Gate Passes"

- [ ] 16. Implement Gate Pass report (PDF)
  - [x] 16.1 Create report template in `reports/mesob_gate_pass_report.xml`
    - Design QWeb template for printable Gate Pass
    - Include header with sequence number, date, state
    - Include authorization section (Issue Voucher or written authorization)
    - Include dispatch details (destination, receiver, vehicle, driver)
    - Include line items table (item, description, quantity, UOM)
    - Include authorization signature section (PAO name and date)
    - Include copy type indicator (Original, Duplicate, Triplicate)
    - Include footer with security verification details
    - _Requirements: 14.1, 14.2, 14.3, 14.4, 14.5_
  
  - [ ] 16.2 Create report action
    - Define report action in XML
    - Link to QWeb template
    - Enable multi-copy printing (3 copies with different labels)
    - _Requirements: 14.1, 14.5_
  
  - [ ]* 16.3 Write property test for report content completeness
    - **Property 24: Report Content Completeness**
    - **Validates: Requirements 14.2, 14.3, 14.4, 14.5**

- [ ] 17. Implement error handling
  - [ ] 17.1 Add error handling for authorization failures
    - Raise AccessError for non-PAO users
    - Raise ValidationError for missing prerequisite documents
    - Raise ValidationError for invalid Issue Voucher state
    - _Requirements: 19.1, 19.2, 19.3_
  
  - [ ] 17.2 Add error handling for dispatch failures
    - Raise AccessError for non-security-guard users
    - Raise UserError for unauthorized Gate Pass
    - _Requirements: 19.1, 19.4_
  
  - [ ] 17.3 Add error handling for cancellation failures
    - Raise UserError for dispatched Gate Pass
    - _Requirements: 19.5_
  
  - [ ] 17.4 Add error handling for validation failures
    - Raise ValidationError for missing dispatch details
    - Raise ValidationError for duplicate Issue Voucher link
    - _Requirements: 19.6_
  
  - [ ]* 17.5 Write property test for error message clarity
    - **Property 33: Error Message Clarity**
    - **Validates: Requirements 19.2, 19.3, 19.4, 19.5, 19.6**

- [ ] 18. Checkpoint - Ensure UI and error handling tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 19. Add database indexes for performance
  - [ ] 19.1 Add indexes in model definition
    - Add index on state field
    - Add index on dispatch_date field
    - Add index on issue_voucher_id field
    - Add index on authorized_by_id field
    - Add index on gate_pass_id in line items
    - Add index on item_id in line items
    - _Requirements: 20.1, 20.2, 20.3, 20.4, 20.5, 20.6_
  
  - [ ]* 19.2 Write property test for performance - Gate Pass creation
    - **Property 27: Performance - Gate Pass Creation**
    - **Validates: Requirements 17.1**
  
  - [ ]* 19.3 Write property test for performance - search results
    - **Property 28: Performance - Search Results**
    - **Validates: Requirements 15.6, 17.2**
  
  - [ ]* 19.4 Write property test for performance - report generation
    - **Property 29: Performance - Report Generation**
    - **Validates: Requirements 14.6, 17.3**
  
  - [ ]* 19.5 Write property test for performance - audit trail query
    - **Property 30: Performance - Audit Trail Query**
    - **Validates: Requirements 17.4**

- [x] 20. Update module manifest
  - [x] 20.1 Update `__manifest__.py`
    - Add new model files to imports
    - Add new view files to data list
    - Add security files to data list
    - Add sequence file to data list
    - Add report files to data list
    - Update module version
    - Update module description

- [ ] 21. Write integration tests
  - [ ]* 21.1 Write integration test for end-to-end workflow
    - Test complete flow: create → authorize → dispatch
    - Verify all state transitions
    - Verify audit trail entries
    - Verify Issue Voucher updates
  
  - [ ]* 21.2 Write integration test for Issue Voucher integration
    - Create Issue Voucher with multiple lines
    - Create Gate Pass from Issue Voucher
    - Verify line items copied correctly
    - Verify Issue Voucher updated after dispatch
  
  - [ ]* 21.3 Write integration test for security roles
    - Test PAO authorization workflow
    - Test Security Guard dispatch workflow
    - Test access control enforcement
  
  - [ ]* 21.4 Write integration test for cancellation workflow
    - Test cancellation from draft state
    - Test cancellation from authorized state
    - Test prevention of cancellation from dispatched state
    - Test reset to draft after cancellation

- [ ] 22. Write unit tests for edge cases
  - [ ]* 22.1 Write unit test for XOR constraint violation
    - Test with both Issue Voucher and written authorization
    - Test with neither Issue Voucher nor written authorization
  
  - [ ]* 22.2 Write unit test for duplicate Issue Voucher link
    - Create Gate Pass from Issue Voucher
    - Attempt to create second Gate Pass from same Issue Voucher
    - Verify ValidationError raised
  
  - [ ]* 22.3 Write unit test for immutability enforcement
    - Dispatch Gate Pass
    - Attempt to modify critical fields
    - Verify UserError raised
  
  - [ ]* 22.4 Write unit test for line item validation
    - Test zero quantity rejection
    - Test negative quantity rejection
    - Test missing item_id rejection
    - Test serialized item without serial numbers

- [ ] 23. Final checkpoint - Complete system integration test
  - Run all unit tests, property tests, and integration tests
  - Verify all requirements covered
  - Test complete workflow with all roles (PAO, Storekeeper, Security Guard)
  - Verify audit trail completeness
  - Verify report generation
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 24. Documentation and deployment preparation
  - [ ] 24.1 Create user documentation
    - Document Gate Pass creation workflow
    - Document PAO authorization process
    - Document Security Guard dispatch process
    - Document cancellation and correction workflows
  
  - [ ] 24.2 Create training materials
    - Create quick reference guide for Storekeepers
    - Create quick reference guide for PAO
    - Create quick reference guide for Security Guards
  
  - [ ] 24.3 Prepare deployment checklist
    - Verify all dependencies installed
    - Verify security groups configured
    - Verify sequence configured
    - Verify access rights configured
    - Plan user training sessions

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at key milestones
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- Integration tests validate end-to-end workflows across multiple components
- All code should follow Odoo 19 best practices and conventions
- Use existing Mesob Inventory Base module patterns for consistency
- Ensure all user-facing messages are clear and actionable

# Requirements Document: Gate Pass & Dispatch Control

## Introduction

The Gate Pass & Dispatch Control module implements FDRE-compliant material dispatch authorization for the Mesob Inventory Management System. This module enforces Property Administration Officer (PAO) written authority requirements for any materials leaving the compound, integrates with the existing Issue Voucher (Model 22) workflow, and implements three-copy distribution tracking for security control. The Gate Pass serves as the sole written authority for material movement outside the organization, ensuring proper custody chain and preventing unauthorized removal of government property.

## Glossary

- **Gate_Pass_System**: The software module that manages Gate Pass creation, authorization, and dispatch
- **PAO**: Property Administration Officer who authorizes material dispatch
- **Storekeeper**: User who creates Gate Pass documents and manages materials
- **Security_Guard**: Gate personnel who verify Gate Pass and release materials
- **Issue_Voucher**: Model 22 document authorizing material issue to departments
- **Authorization_Document**: Either an Issue Voucher or written authorization reference
- **Three_Copy_Distribution**: Original (receiver), Duplicate (storekeeper), Triplicate (security)
- **Dispatch**: Act of releasing materials through gate for external delivery
- **Gate_Pass_Record**: A single Gate Pass document in the system

## Requirements

### Requirement 1: Gate Pass Creation

**User Story:** As a storekeeper, I want to create Gate Pass documents for material dispatch, so that I can obtain proper authorization before materials leave the compound.

#### Acceptance Criteria

1. WHEN a storekeeper creates a Gate Pass, THE Gate_Pass_System SHALL generate a unique sequence number in format GP/YYYY/####
2. WHEN a storekeeper creates a Gate Pass from an Issue Voucher, THE Gate_Pass_System SHALL auto-populate line items from the Issue Voucher
3. WHEN a storekeeper creates a Gate Pass, THE Gate_Pass_System SHALL require at least one line item with positive quantity
4. WHEN a storekeeper creates a Gate Pass, THE Gate_Pass_System SHALL initialize the state to "draft"
5. WHEN a storekeeper creates a Gate Pass, THE Gate_Pass_System SHALL require either an Issue Voucher link OR written authorization reference

### Requirement 2: PAO Authorization

**User Story:** As a PAO, I want to authorize Gate Pass documents, so that I can control which materials are permitted to leave the compound.

#### Acceptance Criteria

1. WHEN a PAO authorizes a Gate Pass, THE Gate_Pass_System SHALL verify the user has PAO role
2. WHEN a PAO authorizes a Gate Pass, THE Gate_Pass_System SHALL verify the Gate Pass is in "draft" state
3. WHEN a PAO authorizes a Gate Pass, THE Gate_Pass_System SHALL verify prerequisite authorization documents exist
4. WHEN a PAO authorizes a Gate Pass, THE Gate_Pass_System SHALL transition the state to "authorized"
5. WHEN a PAO authorizes a Gate Pass, THE Gate_Pass_System SHALL record the authorizing PAO user ID and timestamp
6. WHEN a PAO authorizes a Gate Pass, THE Gate_Pass_System SHALL post an audit message to the chatter
7. IF a non-PAO user attempts to authorize a Gate Pass, THEN THE Gate_Pass_System SHALL reject the action with an access error

### Requirement 3: Authorization Document Validation

**User Story:** As a system administrator, I want to enforce authorization document requirements, so that no Gate Pass can be created without proper authority.

#### Acceptance Criteria

1. WHEN a Gate Pass has an Issue Voucher link, THE Gate_Pass_System SHALL verify the Issue Voucher exists
2. WHEN a Gate Pass has an Issue Voucher link, THE Gate_Pass_System SHALL verify the Issue Voucher state is "issued" or "received"
3. WHEN a Gate Pass has an Issue Voucher link, THE Gate_Pass_System SHALL verify the Issue Voucher is properly signed
4. WHEN a Gate Pass is submitted for authorization, THE Gate_Pass_System SHALL verify exactly one authorization method is provided
5. IF a Gate Pass has both Issue Voucher and written authorization, THEN THE Gate_Pass_System SHALL reject the Gate Pass with a validation error
6. IF a Gate Pass has neither Issue Voucher nor written authorization, THEN THE Gate_Pass_System SHALL reject the Gate Pass with a validation error

### Requirement 4: Security Gate Verification and Dispatch

**User Story:** As a security guard, I want to verify and dispatch materials at the gate, so that I can ensure only authorized materials leave the compound.

#### Acceptance Criteria

1. WHEN a security guard dispatches a Gate Pass, THE Gate_Pass_System SHALL verify the user has Security Guard role
2. WHEN a security guard dispatches a Gate Pass, THE Gate_Pass_System SHALL verify the Gate Pass is in "authorized" state
3. WHEN a security guard dispatches a Gate Pass, THE Gate_Pass_System SHALL verify PAO authorization exists
4. WHEN a security guard dispatches a Gate Pass, THE Gate_Pass_System SHALL transition the state to "dispatched"
5. WHEN a security guard dispatches a Gate Pass, THE Gate_Pass_System SHALL record the security guard user ID and timestamp
6. WHEN a security guard dispatches a Gate Pass, THE Gate_Pass_System SHALL set all three copy distribution flags to TRUE
7. WHEN a security guard dispatches a Gate Pass, THE Gate_Pass_System SHALL post an audit message to the chatter
8. IF a non-security-guard user attempts to dispatch a Gate Pass, THEN THE Gate_Pass_System SHALL reject the action with an access error

### Requirement 5: Three-Copy Distribution Tracking

**User Story:** As a PAO, I want to track the distribution of all three Gate Pass copies, so that I can ensure proper custody chain and security control.

#### Acceptance Criteria

1. WHEN a Gate Pass is dispatched, THE Gate_Pass_System SHALL mark the original copy as distributed to receiver
2. WHEN a Gate Pass is dispatched, THE Gate_Pass_System SHALL mark the duplicate copy as retained by storekeeper
3. WHEN a Gate Pass is dispatched, THE Gate_Pass_System SHALL mark the triplicate copy as retained by security
4. WHEN a Gate Pass is in "dispatched" state, THE Gate_Pass_System SHALL display all three distribution flags as TRUE
5. THE Gate_Pass_System SHALL log copy distribution in the audit trail

### Requirement 6: State Machine Workflow

**User Story:** As a system administrator, I want to enforce proper state transitions, so that Gate Pass workflow follows FDRE compliance rules.

#### Acceptance Criteria

1. WHEN a Gate Pass is created, THE Gate_Pass_System SHALL set the initial state to "draft"
2. WHEN a Gate Pass transitions from "draft" to "authorized", THE Gate_Pass_System SHALL verify PAO authorization
3. WHEN a Gate Pass transitions from "authorized" to "dispatched", THE Gate_Pass_System SHALL verify security guard verification
4. WHEN a Gate Pass is in "draft" or "authorized" state, THE Gate_Pass_System SHALL allow cancellation
5. IF a Gate Pass is in "dispatched" state, THEN THE Gate_Pass_System SHALL prevent cancellation
6. WHEN a Gate Pass is cancelled, THE Gate_Pass_System SHALL allow reset to "draft" for corrections

### Requirement 7: Immutability After Dispatch

**User Story:** As a PAO, I want dispatched Gate Pass records to be immutable, so that audit trails cannot be tampered with.

#### Acceptance Criteria

1. WHEN a Gate Pass is in "dispatched" state, THE Gate_Pass_System SHALL prevent modification of all critical fields
2. WHEN a Gate Pass is in "dispatched" state, THE Gate_Pass_System SHALL allow modification of internal notes only
3. IF a user attempts to modify a dispatched Gate Pass, THEN THE Gate_Pass_System SHALL reject the modification with an error message
4. WHEN a Gate Pass is dispatched, THE Gate_Pass_System SHALL preserve all field values in the audit trail

### Requirement 8: Issue Voucher Integration

**User Story:** As a storekeeper, I want to create Gate Passes from Issue Vouchers, so that I can streamline the dispatch workflow.

#### Acceptance Criteria

1. WHEN a storekeeper creates a Gate Pass from an Issue Voucher, THE Gate_Pass_System SHALL link the Gate Pass to the Issue Voucher
2. WHEN a storekeeper creates a Gate Pass from an Issue Voucher, THE Gate_Pass_System SHALL copy all line items from the Issue Voucher
3. WHEN a storekeeper creates a Gate Pass from an Issue Voucher, THE Gate_Pass_System SHALL copy item descriptions, quantities, and units of measure
4. WHEN a Gate Pass is dispatched, THE Gate_Pass_System SHALL update the linked Issue Voucher dispatch status
5. WHEN a Gate Pass is dispatched, THE Gate_Pass_System SHALL record the dispatch date on the linked Issue Voucher
6. IF an Issue Voucher already has a Gate Pass, THEN THE Gate_Pass_System SHALL prevent creation of duplicate Gate Passes

### Requirement 9: Dispatch Details Validation

**User Story:** As a PAO, I want to ensure all dispatch details are complete, so that I can verify the legitimacy of material movement.

#### Acceptance Criteria

1. WHEN a Gate Pass is submitted for authorization, THE Gate_Pass_System SHALL verify destination is provided
2. WHEN a Gate Pass is submitted for authorization, THE Gate_Pass_System SHALL verify receiver name is provided
3. WHEN a Gate Pass is submitted for authorization, THE Gate_Pass_System SHALL verify receiver organization is provided
4. WHEN a Gate Pass includes vehicle transport, THE Gate_Pass_System SHALL record vehicle plate number
5. WHEN a Gate Pass includes vehicle transport, THE Gate_Pass_System SHALL record driver name and license number
6. IF required dispatch details are missing, THEN THE Gate_Pass_System SHALL reject authorization with a validation error

### Requirement 10: Audit Trail and Tracking

**User Story:** As a PAO, I want complete audit trails for all Gate Pass activities, so that I can review material movement history and ensure compliance.

#### Acceptance Criteria

1. WHEN a Gate Pass is created, THE Gate_Pass_System SHALL log the creation event with user and timestamp
2. WHEN a Gate Pass is authorized, THE Gate_Pass_System SHALL log the authorization event with PAO user and timestamp
3. WHEN a Gate Pass is dispatched, THE Gate_Pass_System SHALL log the dispatch event with security guard user and timestamp
4. WHEN a Gate Pass state changes, THE Gate_Pass_System SHALL post a message to the chatter
5. WHEN a Gate Pass is cancelled, THE Gate_Pass_System SHALL log the cancellation event with reason
6. THE Gate_Pass_System SHALL track all field changes using Odoo mail.thread functionality
7. THE Gate_Pass_System SHALL prevent deletion of audit trail messages

### Requirement 11: Line Item Management

**User Story:** As a storekeeper, I want to manage line items on Gate Passes, so that I can accurately document materials being dispatched.

#### Acceptance Criteria

1. WHEN a storekeeper adds a line item, THE Gate_Pass_System SHALL require an inventory item reference
2. WHEN a storekeeper adds a line item, THE Gate_Pass_System SHALL require a positive quantity
3. WHEN a storekeeper adds a line item, THE Gate_Pass_System SHALL default the unit of measure from the item master
4. WHEN a line item references a serialized item, THE Gate_Pass_System SHALL require serial numbers
5. WHEN a Gate Pass is saved, THE Gate_Pass_System SHALL verify at least one line item exists
6. IF a line item has zero or negative quantity, THEN THE Gate_Pass_System SHALL reject the line item with a validation error

### Requirement 12: Role-Based Access Control

**User Story:** As a system administrator, I want to enforce role-based access control, so that only authorized users can perform specific Gate Pass operations.

#### Acceptance Criteria

1. THE Gate_Pass_System SHALL allow PAO users to read, write, create, and authorize Gate Passes
2. THE Gate_Pass_System SHALL allow Storekeeper users to read, write, and create Gate Passes
3. THE Gate_Pass_System SHALL allow Security Guard users to read and dispatch Gate Passes
4. THE Gate_Pass_System SHALL prevent Storekeeper users from authorizing Gate Passes
5. THE Gate_Pass_System SHALL prevent Security Guard users from creating or authorizing Gate Passes
6. THE Gate_Pass_System SHALL prevent non-PAO users from deleting Gate Passes

### Requirement 13: Sequence Number Generation

**User Story:** As a storekeeper, I want Gate Passes to have unique sequential numbers, so that I can reference and track them easily.

#### Acceptance Criteria

1. WHEN a Gate Pass is created, THE Gate_Pass_System SHALL generate a unique sequence number
2. THE Gate_Pass_System SHALL format sequence numbers as GP/YYYY/#### where YYYY is the current year
3. THE Gate_Pass_System SHALL increment the sequence number for each new Gate Pass
4. THE Gate_Pass_System SHALL reset the sequence counter at the start of each year
5. THE Gate_Pass_System SHALL ensure sequence numbers are unique across all Gate Passes

### Requirement 14: Report Generation

**User Story:** As a storekeeper, I want to print Gate Pass documents, so that I can provide physical copies to receiver, storekeeper, and security.

#### Acceptance Criteria

1. WHEN a storekeeper prints a Gate Pass, THE Gate_Pass_System SHALL generate a PDF report
2. WHEN a Gate Pass is printed, THE Gate_Pass_System SHALL include all line items with descriptions and quantities
3. WHEN a Gate Pass is printed, THE Gate_Pass_System SHALL include dispatch details (destination, receiver, vehicle)
4. WHEN a Gate Pass is printed, THE Gate_Pass_System SHALL include authorization details (PAO name and date)
5. WHEN a Gate Pass is printed, THE Gate_Pass_System SHALL indicate copy type (Original, Duplicate, or Triplicate)
6. WHEN a Gate Pass is printed, THE Gate_Pass_System SHALL complete report generation within 5 seconds

### Requirement 15: Search and Filtering

**User Story:** As a PAO, I want to search and filter Gate Passes, so that I can quickly find specific records for review.

#### Acceptance Criteria

1. THE Gate_Pass_System SHALL allow users to search Gate Passes by sequence number
2. THE Gate_Pass_System SHALL allow users to filter Gate Passes by state
3. THE Gate_Pass_System SHALL allow users to filter Gate Passes by dispatch date range
4. THE Gate_Pass_System SHALL allow users to filter Gate Passes by destination
5. THE Gate_Pass_System SHALL allow users to filter Gate Passes by receiver organization
6. THE Gate_Pass_System SHALL display search results within 1 second for up to 1000 records

### Requirement 16: Cancellation Workflow

**User Story:** As a storekeeper, I want to cancel incorrect Gate Passes, so that I can correct errors before dispatch.

#### Acceptance Criteria

1. WHEN a Gate Pass is in "draft" state, THE Gate_Pass_System SHALL allow cancellation
2. WHEN a Gate Pass is in "authorized" state, THE Gate_Pass_System SHALL allow cancellation
3. IF a Gate Pass is in "dispatched" state, THEN THE Gate_Pass_System SHALL prevent cancellation
4. WHEN a Gate Pass is cancelled, THE Gate_Pass_System SHALL require a cancellation reason
5. WHEN a Gate Pass is cancelled, THE Gate_Pass_System SHALL allow reset to "draft" for corrections
6. WHEN a Gate Pass is cancelled, THE Gate_Pass_System SHALL log the cancellation in the audit trail

### Requirement 17: Performance Requirements

**User Story:** As a system administrator, I want the Gate Pass system to perform efficiently, so that users can complete their work without delays.

#### Acceptance Criteria

1. WHEN a Gate Pass is created from an Issue Voucher, THE Gate_Pass_System SHALL complete the operation within 2 seconds for up to 100 line items
2. WHEN a user queries pending Gate Passes, THE Gate_Pass_System SHALL return results within 1 second for up to 1000 records
3. WHEN a user generates a Gate Pass report, THE Gate_Pass_System SHALL complete PDF generation within 5 seconds
4. WHEN a user queries audit trail history, THE Gate_Pass_System SHALL return results within 3 seconds for up to 10,000 records

### Requirement 18: Data Integrity

**User Story:** As a system administrator, I want to ensure data integrity, so that Gate Pass records are accurate and consistent.

#### Acceptance Criteria

1. THE Gate_Pass_System SHALL enforce unique sequence numbers across all Gate Passes
2. THE Gate_Pass_System SHALL enforce foreign key constraints for Issue Voucher links
3. THE Gate_Pass_System SHALL enforce foreign key constraints for inventory item references
4. THE Gate_Pass_System SHALL enforce positive quantity constraints on line items
5. THE Gate_Pass_System SHALL enforce XOR constraint on authorization documents
6. THE Gate_Pass_System SHALL cascade delete line items when parent Gate Pass is deleted

### Requirement 19: Error Handling

**User Story:** As a user, I want clear error messages when operations fail, so that I can understand and correct problems.

#### Acceptance Criteria

1. IF a non-PAO user attempts authorization, THEN THE Gate_Pass_System SHALL display an access error message
2. IF prerequisite documents are missing, THEN THE Gate_Pass_System SHALL display a validation error with required documents
3. IF an Issue Voucher is not properly signed, THEN THE Gate_Pass_System SHALL display a validation error with Issue Voucher state
4. IF a user attempts to dispatch without authorization, THEN THE Gate_Pass_System SHALL display an error with required state
5. IF a user attempts to cancel after dispatch, THEN THE Gate_Pass_System SHALL display an error explaining immutability
6. IF required dispatch details are missing, THEN THE Gate_Pass_System SHALL display a validation error listing missing fields

### Requirement 20: Database Indexing

**User Story:** As a system administrator, I want proper database indexing, so that queries perform efficiently as data volume grows.

#### Acceptance Criteria

1. THE Gate_Pass_System SHALL create an index on the state field
2. THE Gate_Pass_System SHALL create an index on the dispatch_date field
3. THE Gate_Pass_System SHALL create an index on the issue_voucher_id field
4. THE Gate_Pass_System SHALL create an index on the authorized_by_id field
5. THE Gate_Pass_System SHALL create an index on the gate_pass_id field in line items table
6. THE Gate_Pass_System SHALL create an index on the item_id field in line items table

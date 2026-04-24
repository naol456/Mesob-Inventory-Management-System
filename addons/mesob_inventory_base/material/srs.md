 PDF To Markdown Converter
Debug View
Result View
IEEE Software Requirements Specification Template
Copyright © 202 6 MESOB Center. All rights reserved.
Software Requirements
Specification
for
Inventory Management
System
Version 1.

Prepared by Group I

Mesob Center (HQ)

March 2026/Megabit 2018

Software Requirements Specification for Inventory Management System Page ii
Table of Contents

Introduction Contents
1.1 Purpose
1.2 Document Conventions
1.3 Intended Audience and Reading Suggestions..............................................................................
1.4 Product Scope
1.5 References
Overall Description
2.1 Product Perspective
2.2 Product Functions
2.3 User Classes and Characteristics
2.4 Operating Environment
2.5 Design and Implementation Constraints
2.6 User Documentation
2.7 Assumptions and Dependencies
External Interface Requirements
3.1 User Interfaces
3.2 Hardware Interfaces
3.3 Software Interfaces
3.4 Communications Interfaces
System Features
4.1 Stock Identification (Classification & Coding)
4.2 Receiving & Inspection
4.3 Issue of Stocks
4.4 Dispatch Outside Organization (Gate Pass)
4.5 Stock Records (Bin Cards & Stock Record Cards)
4.6 Stock Accounting & Valuation (FIFO)
4.7 Reporting
4.8 Stock Taking & Discrepancy Handling
4.9 Stocks Handing/Taking-Over
4.10 Stock Control (Replenishment & Levels)....................................................................................
4.11 Disposal
4.12 Storage, Safety, and Security
Other Nonfunctional Requirements
5.1 Performance Requirements
5.2 Safety Requirements
5.3 Security Requirements
5.4 Software Quality Attributes
5.5 Business Rules
Other Requirements
Appendix B: Analysis Models
Appendix C:To Be Determined List
Appendix D: Requirements Traceability
Appendix E:Organization-Specific Inputs
Software Requirements Specification for Inventory Management System Page iii

Revision History

Name Date Reason For Changes Version
1. Introduction
1.1 Purpose
This Software Requirements Specification (SRS) defines requirements for an ERP custom module
for Mesob One-Stop Service that implements standardized public-sector stock (inventory)
management operating procedures.
Where organization-specific values or policies are missing or ambiguous, this SRS records them in
Appendix C (To Be Determined) instead of assuming.

1.2 Document Conventions
Requirement keywords: “shall” = mandatory; “should” = recommended; “may” = optional.
Traceability: Each functional requirement has an ID like FR-ISSUE-001.
Business rules: Organizational rules and controls are tagged BR-*.
ERP alignment: When an ERP capability is referenced, it is described at the business level (not
by undocumented internal implementation).
1.3 Intended Audience and Reading Suggestions..............................................................................
Public body management / PAO: Read Sections 1–2, then Section 4 (features) and 5.
(Business Rules).
Storekeepers / stock clerks: Read Section 4 (features) and Appendix A (Glossary).
Developers / implementers: Read Sections 2–6, then Appendix B.
Testers / auditors: Focus on Section 4 acceptance criteria and Section 5 (NFRs + business
rules).
1.4 Product Scope
The module shall support end-to-end stock management for items temporarily kept in stores until
needed, including:

Stock identification (classification + coding)
Receiving and inspection
Issue and dispatch
Stock records, accounting (FIFO valuation), and reporting
Stock taking, discrepancy handling, stock control, disposal linkage, and storage requirements
Fixed asset tracking with custody management
Digital request/approval workflows
HR integration for employee data
The module is a custom ERP module that configures and extends standard inventory processes to
meet Mesob One-Stop Service operating procedures and internal controls.
1.5 References
IEEE SRS Guideline
Mesob One-Stop Service Internal Standards
Ethiopian Government Asset Management Guidelines
2. Overall Description
2.1 Product Perspective
This module is an extension within an ERP environment. It shall use the ERP inventory capabilities
as the operational base while enforcing Mesob One-Stop Service business rules and internal
controls for stock management.
Key perspective decisions:

Business rules : Defined in this SRS and governed by Mesob One-Stop Service.
ERP capability constraint : The solution shall use standard ERP inventory/accounting
capabilities where possible; when multiple options exist, choose the option that best satisfies
the requirements in this SRS.
Ambiguity rule : If a required policy value is not defined, record it as TBD and require an
explicit decision.
2.2 Product Functions
At a high level, the system shall:

Maintain stock master data with standardized classification/coding scheme.
Support receiving with inspection and acceptance/rejection handling.
Support issuing to departments and dispatch outside with Gate Pass authority.
Maintain bin cards and stock record cards, including quantity and value.
Value stock using FIFO and produce annual and periodic reports.
Conduct stock taking with controlled sheets, discrepancy investigation, and handover/takeover
stock taking.
Support stock control parameters (min/max/reorder/hastening, safety stock) and regular review.
Record and flag dormant/slow moving, damaged/obsolete items; support disposal workflow
linkage (per the organization’s disposal policy; see TBD).
Enforce storage organization, safety, and security expectations.
2.3 User Classes and Characteristics
Property Administration Officer (PAO) : supervisory user; approves requisitions; oversees
compliance; manages stock taking; ensures records and processes.
Storekeeper : custody user; receives/inspects; issues; maintains bin cards; controls access and
storage housekeeping.
Stock clerk : records user; posts stock movements; maintains stock record cards (quantity +
value); prepares reports.
Procurement officer : ensures goods accepted meet purchase order specs; manages specialized
tests/inspections.
Department requisitioner/receiver : creates requisitions; receives and inspects delivered
items.
Security officer/guard : retains Gate Pass copy for dispatch control.
2.4 Operating Environment
ERP environment with inventory and accounting capabilities enabled.
Multi-step routes and storage locations may be enabled when needed by routing
requirements.
Organization context assumptions for initial rollout:
Headquarters (HQ) implementation first, with expected expansion to multiple branches.
Initial deployment is local (localhost) in the target environment.
2.5 Design and Implementation Constraints
Must adhere to the organization’s stock management procedures and internal control
requirements.
Must adhere to supported ERP behaviors and configuration constraints.
Costing/valuation must comply with FIFO valuation for stock accounting.
Change authority: business rule changes shall be controlled via governance (role-based
configuration management and audit trails).
2.6 User Documentation
User guide for PAO, storekeeper, stock clerk.
Form usage guide for Model 19, Model 20, Model 22, DSR, Gate Pass, Stock Taking Sheet,
Handover certificate.
2.7 Assumptions and Dependencies
MESOB HR System API is available and documented
Barcode/QR scanning hardware will be provided
Users have basic computer literacy
Internet connectivity available
Disposal procedures exist (details TBD)
Purchase orders and packing slips available for receiving
3. External Interface Requirements
3.1 User Interfaces
The module shall provide UI for:

Maintaining classification codes and item codes (####-###-###).
Receiving workflow: inspection results, Model 19 creation and distribution.
Rejection workflow: DSR creation and distribution.
Issue workflow: Model 20 approval, Model 22 issuance, receiving confirmation.
Dispatch workflow: Gate Pass creation with copy distribution.
Records screens: bin card view (quantity) and stock record card view (quantity + value).
Reporting screens: fiscal year ending balances per 4401–4418; quarterly movement;
discrepancy and dormant stock reports.
Stock taking screens: create serially numbered stock taking sheets, print, capture counts, record
discrepancies, sign-offs.
Storage compliance checklist (labels, arrangement, security key register references) where
feasible.
(TBD: exact ERP UI placements and menus.)
3.2 Hardware Interfaces
None required beyond standard server/client devices.

3.3 Software Interfaces
ERP Inventory capabilities (stock operations, locations, routes).
ERP Accounting capabilities (inventory valuation review/entries).
(TBD: integration boundaries between inventory and accounting configuration in the target
deployment.)
3.4 Communications Interfaces
None required beyond standard ERP web access.

4. System Features
4.1 Stock Identification (Classification & Coding)
4.1.1. Description
Implement standardized stock identification by classification and coding to avoid
ambiguous naming and enable reporting and control.
Priority : High
4.1.2. Stimulus/Response Sequences:
▪ Stimulus: Stock clerk creates/updates a stock item master.
▪ Response: System validates classification + code format uniqueness and publishes
updated code list/version.
4.1.3. Dependencies
ERP product master data must support storing item code and classification.
4.1.4. Functional Requirements
▪ FR-ID-001 The system shall support major stock classifications per chart of accounts
codes 4401 through 4418.
▪ FR-ID-002 The system shall support a 10-digit code format ####-###-### where:
first 4 digits = major classification;
next 3 digits = sub-class (001–999);
last 3 digits = specific item (001–999).
▪ FR-ID-003 The system shall prevent assigning multiple codes to the same stock item
(no alternative codes once coded).
▪ FR-ID-004 The system shall support maintaining and distributing a stock code list to
relevant units.
▪ FR-ID-005 The system shall support annual publication of coding amendments and
maintain version history.
▪ FR-ID-006 The system shall allow excluding seldom-required/non-repetitive items
from the coding catalog.
4.1.5. Business Rules
▪ BR-ID-001 Classification shall be simple, understandable, and group like-with-like.
4.1.6. Acceptance Criteria
▪ Given a major classification 4402, the system can create item code 4402- 001 - 001 and
prevent duplicates.
4.2 Receiving & Inspection
4.2.1. Description
Support receiving from outside suppliers, donors, and returns from user departments, with
inspection, acceptance, and rejection flows.
Priority : High
4.2.2. Stimulus/Response Sequences:
▪ Stimulus: Goods arrive at store.
▪ Response: System records inspection/acceptance; generates Model 19 for accepted
items or DSR for rejected items; tracks copy distribution.
4.2.3. Dependencies
▪ Purchase/packing documents exist as referenced inputs.
▪ ERP stock receipt operations and locations are available.
4.2.4. Functional Requirements
▪ FR-REC-001 The system shall require a recorded authority (preferably written) before
completing receipt of stock/fixed asset.
▪ FR-REC-002 The system shall enforce that items are not put to use before receiving is
fully completed.
▪ FR-REC-003 The system shall support receiving steps: unloading check,
unpack/inspect vs packing slip and purchase order, then acceptance.
▪ FR-REC-004 The system shall support inspection assignment: storekeeper for simple
items; user technical staff for technical items; independent/supplier-site inspection
where applicable.
▪ FR-REC-005 The system shall generate Model 19 (Receipt for articles/property) only
for accepted items.
▪ FR-REC-006 The system shall support Model 19 four-copy distribution tracking:
Accounts Unit (original with supplier invoice), Stock clerk (duplicate)
Supplier/deliverer (triplicate), Storekeeper (book copy).
▪ FR-REC-007 The system shall support returns to store from user departments for new
supplies by generating Model 19, and mark that no payment will be effected (accounts
copy retained with pad).
▪ FR-REC-008 The system shall support rejection returns using DSR in four copies with
distribution tracking: Supplier (original accompanies goods), Accounts/finance
(duplicate), Procurement officer (triplicate), Storekeeper (book copy).
▪ FR-REC-009 The system shall support recording discrepancies and their type
(damaged/shortage/overage/not right quality) on the DSR.
▪.
4.2.5. Acceptance Criteria
▪ If inspection fails, the system prevents completion of receipt and requires DSR +
return workflow.
4.3 Issue of Stocks
4.3.1. Description
Issue stocks to user departments and dispatch outside with Gate Pass control.
Priority : High
4.3.2. Stimulus/Response Sequences:
▪ Stimulus: User department requests items.
▪ Response: System enforces approved Model 20 before issuing; generates Model 22;
records department receipt confirmation.
4.3.3. Dependencies
▪ User roles/permissions for PAO, storekeeper, stock clerk.
4.3.4. Functional Requirements
▪ FR-ISSUE-001 The system shall support issue scheduling modes: imprest basis,
replacement issue, and non-stock issue.
▪ FR-ISSUE-002 The system shall require Model 20 (Stores Requisition) raised by user
department and approved by PAO before issue.
▪ FR-ISSUE-003 The system shall allow storekeeper to maintain an authorization file of
approvers and specimen signatures.
▪ FR-ISSUE-004 The system shall support restricting issue of controlled materials (e.g.,
drugs/chemicals/explosives) to authorized individuals.
▪ FR-ISSUE-005 Upon issue, the system shall generate Model 22 in three copies and
track distribution: original + requisition to stock clerk for posting, duplicate to
requesting department, triplicate retained by storekeeper.
▪ FR-ISSUE-006 The system shall record receipt confirmation by ordering department
(count + inspection vs requisition and approval).
4.4 Dispatch Outside Organization (Gate Pass)
4.4.1. Description
Control movement of materials leaving the compound through PAO authority and Gate
Pass distribution.
Priority : High
4.4.2. Stimulus/Response Sequences:
▪ Stimulus: Materials are to be moved outside the compound.
▪ Response: System requires PAO authority + prerequisite documents; generates Gate
Pass copies and records distribution.
4.4.3. Dependencies
▪ Security role/user exists to receive Gate Pass copy.
4.4.4. Functional Requirements
▪ FR-DISP-001 The system shall require PAO written authority for any material leaving
the compound.
▪ FR-DISP-002 The system shall treat Gate Pass as the only written authority for
movement outside.
▪ FR-DISP-003 The system shall allow Gate Pass creation only after a duly signed
Model 22 or written authorization.
▪ FR-DISP-004 Gate Pass shall be generated in three copies and distribution tracked:
original accompanies materials to receiver, duplicate to storekeeper, triplicate to
security officer/guard
4.5 Stock Records (Bin Cards & Stock Record Cards)
4.5.1. Description
Maintain quantity and value records to enable control, reconciliation, and reporting.
Priority : High
4.5.2. Stimulus/Response Sequences:
▪ Stimulus: Receipt, issue, adjustment, or stock-take posting occurs.
▪ Response: System updates bin card and stock record card views for the item and
preserves audit trail.
4.5.3. Dependencies
▪ Underlying stock moves are available in the ERP.
4.5.4. Functional Requirements
▪ FR-RECARD-001 The system shall support Bin Card per item, showing quantity
received, issued, and balance; maintained by storekeeper.
▪ FR-RECARD-002 The system shall support Stock Record Card per item, maintained
by stock clerk, including quantity, unit price, total value for receipts/issues/balance.
▪ FR-RECARD-003 Stock Record Cards shall be organized by classification/coding
4.6 Stock Accounting & Valuation (FIFO)
4.5.5. Description
Provide FIFO-based stock costing and valuation consistent with the organization’s stock
accounting requirements, and align with ERP inventory valuation capabilities.
Priority : High
4.5.6. Stimulus/Response Sequences:
▪ Stimulus: A stock issue is posted or fiscal year end valuation is requested.
▪ Response: System computes issue costs and ending valuations using FIFO; provides
totals by major classification for reporting/reconciliation.
4.5.7. Dependencies
▪ ERP inventory valuation configuration supports FIFO valuation.
4.5.8. Functional Requirements
▪ FR-VAL-001 The system shall value stock using FIFO for costing of issues and
ending balance valuation.
▪ FR-VAL-002 The system shall include in cost: price minus discounts plus freight,
insurance, duties/taxes, and package charges as applicable.
▪ FR-VAL-003 If stock value cannot be determined, the system shall support recording
an estimated value based on identical/similar goods value at acquisition time.
▪ FR-VAL-004 The system shall support control accounts per classification and a main
stock account total; and support monthly reconciliation that main account equals the
sum of control accounts.
4.7 Reporting
4.7.1. Description
Provide periodic and fiscal-year-end reporting required for stock accounting, control, and
provisioning decisions.
Priority : High
4.7.2. Stimulus/Response Sequences:
▪ Stimulus: Accounts unit requests fiscal year end values; management requests
quarterly movement.
▪ Response: System generates required reports grouped by classification and item.
4.7.3. Dependencies
▪ Classification/coding is configured.
▪ FIFO valuation data is available.
4.7.4. Functional Requirements
▪ FR-REP-001 At fiscal year end, the system shall produce a report of ending stock
value totals by major classification (4401–4418) for the accounts unit.
▪ FR-REP-002 The system shall support quarterly movement reports per stock item to
identify dead/slow moving items and support provisioning decisions.
▪ FR-REP-003 The system shall support reporting existence of dormant/slow-moving
stocks, inferior qualities, and record accuracy.
4.8 Stock Taking & Discrepancy Handling
4.7.5. Description
Support end-to-end stock taking: preparation, controlled counting, discrepancy
identification, and documented corrective actions.
Priority : High
4.7.6. Stimulus/Response Sequences:
▪ Stimulus: PAO initiates stock taking event.
▪ Response: System issues pre-numbered sheets, captures counts, compares to records,
and produces discrepancy list with reasons/actions.
4.7.7. Dependencies
▪ Item master + locations/storage layout are set up.
4.7.8. Functional Requirements
▪ FR-ST-001 The system shall support PAO issuance of stock-taking instructions and
recording that pre-stocktaking training was performed.
▪ FR-ST-002 The system shall generate serially numbered stock-taking sheets prepared
in advance and pre-typed in logical order matching storage layout and records.
▪ FR-ST-003 The system shall support scheduling per management decision (dates,
stores per day, start/end times, breaks).
▪ FR-ST-004 The system shall require issuance of stock-taking sheets to recorder against
signature and return completed sheets to team head.
▪ FR-ST-005 The system shall support recording colored-sticker marking to prevent
double counting (at minimum: a “counted” marker per item/location).
▪ FR-ST-006 The system shall support comparison of physical counts vs bin cards and
stock records and produce a discrepancy list.
▪ FR-ST-007 The system shall support capturing discrepancy reasons and corrective
actions.
▪ FR-ST-008 The system shall support noting and dating bin cards in red-ink equivalent
(audit marker) when checked.
▪ FR-ST-009 The system shall ensure storekeepers are excluded from being stock-taking
team members, but can be recorded as guides/witnessed participants.
4.9 Stocks Handing/Taking-Over
4.9.1. Description
Support mandatory handover stock taking when storekeeper role changes or absence
triggers custody transfer.
Priority : High
4.9.2. Stimulus/Response Sequences:
▪ Stimulus: Storekeeper change event occurs (transfer/leave/etc.).
▪ Response: System initiates handover stock taking; generates certificate and copy
distribution records.
4.9.3. Dependencies
▪ HR or administration can trigger/record the storekeeper status change event.
4.9.4. Functional Requirements
▪ FR-HO-001 The system shall support a handover stock-taking workflow triggered by
storekeeper status changes (leave/retirement, duty travel, training outside station,
promotion, transfer, medical treatment).
▪ FR-HO-002 The system shall require incoming and outgoing storekeepers to conduct
stock-taking in presence of a competent witness, with signatures.
▪ FR-HO-003 The system shall generate a handover certificate and stock-taking sheets
in triplicate distribution: PAO (original), incoming storekeeper (duplicate), outgoing
storekeeper (triplicate).
4.10 Stock Control (Replenishment & Levels)....................................................................................
4.10.1. Description
Support control levels, lead times, and alerts to prevent stock-outs and overstock, and to
prioritize management attention.
Priority : Medium
4.10.2. Stimulus/Response Sequences:
▪ Stimulus: Stock on hand changes or periodic review is performed.
▪ Response: System alerts at reorder/hastening thresholds and supports
review/adjustment and ABC classification.
4.10.3. Dependencies
▪ Historical movement data is available.
4.10.4. Functional Requirements
▪ FR-SC-001 The system shall allow maintaining control levels per item: minimum,
reorder, hastening, maximum, and safety stock.
▪ FR-SC-002 The system shall support lead time modeling with administrative lead time
and supplier lead time.
▪ FR-SC-003 When stock reaches reorder level, the system shall prompt ordering action
and require checking for outstanding deliveries.
▪ FR-SC-004 The system shall support periodic review of levels
(weekly/monthly/quarterly) and allow adjustments.
▪ FR-SC-005 The system shall support ABC analysis classification by usage to prioritize
attention (A/B/C groups).
4.11 Disposal
4.11.1. Description
Support identification and controlled tracking of disposal candidates with audit trail;
detailed disposal workflow follows the organization’s disposal policy (out of scope for this
module until provided).
Priority : Medium
4.11.2. Stimulus/Response Sequences:
▪ Stimulus: Item is identified as unwanted/surplus/unserviceable.
▪ Response: System records candidate and routes for disposal process per referenced
policy (TBD).
4.11.3. Dependencies
▪ Disposal policy/procedure details are provided and agreed.
4.11.4. Functional Requirements
▪ FR-DISP2-001 The system shall support identifying unwanted and surplus property
and generating disposal candidates list.
▪ FR-DISP2-002 The system shall record that disposal procedures follow the
organization’s disposal policy (details TBD) and maintain audit trail of PAO
responsibility.
4.12 Storage, Safety, and Security
4.12.1. Description
Support storage arrangement, safety, and security recordkeeping required by
organizational standards (labels, plans, key custody, access control, safety checklists)
Priority : Medium
4.12.2. Stimulus/Response Sequences:
▪ Stimulus: Storage plan is updated; keys are issued/returned; periodic safety/security
checks occur.
▪ Response: System records plan versions, key custody events, visitor/access logs, and
checklist outcomes
4.12.3. Dependencies
▪ User roles/permissions for store management and security.
4.12.4. Functional Requirements
▪ FR-STOR-001 The system shall support labeling of stocks and shelves and storing by
classes.
▪ FR-STOR-002 The system shall support recording storage plan elements
(receiving/issuing areas, aisles, gates) as a documented artifact.
▪ FR-STOR-003 The system shall support recording key custody register events (who
collected/deposited keys, timestamps, key IDs).
▪ FR-STOR-004 The system shall support recording access control rules and visitor logs
where required.
▪ FR-STOR-005 The system shall support recording fire precautions compliance
checklist items.
▪ FR-STOR-006 The system shall support recording safety measures (PPE availability,
first aid kit, emergency communication readiness) as checklist/audit records.
5. Other Nonfunctional Requirements
5.1 Performance Requirements
NFR-PERF-001 The system shall generate fiscal year end valuation reports (by 4401–4418)
within an acceptable time for the organization’s stock volume. (TBD: SLA)
5.2 Safety Requirements
NFR-SAFE-001 The system shall support storage safety compliance recording as required by
organizational standards (training, PPE, emergency equipment).
5.3 Security Requirements
NFR-SEC-001 Only authorized users shall approve requisitions (PAO) and issue controlled
materials.
NFR-SEC-002 Gate Pass records shall be immutable after dispatch (except via controlled
correction workflow) to preserve auditability.
NFR-SEC-003 Key custody register records shall be tamper-evident (audit trail).
5.4 Software Quality Attributes
NFR-QUAL-001 Auditability: All receipt/issue/valuation/stock-taking actions shall be
traceable to user, date/time, and source documents.
NFR-QUAL-002 Usability: Forms-based workflows shall mirror the organization’s standard
operating sequence to reduce training burden.
NFR-QUAL-003 Maintainability: Classification codes and stock levels shall be configurable
within controlled governance.
5.5 Business Rules
BR-VAL-001 FIFO valuation shall be used for stock valuation.
BR-DISP-001 Gate Pass is the only authority for movement outside compound.
BR-ST-001 Storekeepers shall not be members of stock-taking teams.
BR-COD-001 Major classifications shall follow 4401–4418 chart-of-accounts mapping.
6. Other Requirements
Training support: the system should support exporting training materials and printable forms.
Localization: UI and outputs shall support English and Amharic.
Appendix A: Glossary
PAO: Property Administration Officer.
Stock: items not immediately consumed, temporarily kept in store until needed.
Storekeeper: custodian responsible for receipt/inspection/issue/custody.
Stock clerk: responsible for stock movement records and reports.
FIFO: First In First Out valuation method.
DSR: Damage/Shortage Report.
Gate Pass: written authority for materials leaving compound.
Appendix B: Analysis Models
(TBD) Process flow diagrams (Receiving, Issue, Stock Taking) and data model mapping to ERP
entities.

Appendix C:To Be Determined List
TBD-001 ERP edition and hosting/deployment model (on-prem/managed hosting/etc.).
TBD-002 Exact Ethiopian Calendar (EC) fiscal year end date and reporting calendar alignment.
TBD-003 Disposal procedure details and required forms/approvals.
TBD-004 Exact definition of fixed asset vs supplies thresholds in your implementation context.
TBD-005 Whether bilingual UI/output (English/Amharic) is required. (Confirmed: Both)
TBD-006 Exact performance SLAs and expected transaction volumes.
Appendix D: Requirements Traceability
This appendix defines how requirements are traced within the organization.

Each functional requirement (FR-) and business rule (BR-) shall be traceable to: a business
owner (process owner), an implemented ERP configuration/customization artifact, and
verification evidence (test case, UAT sign-off, or audit checklist record).
(TBD: define the organization’s official process owners and artifact repository locations.)
Appendix E: Organization-Specific Inputs (Captured)
Organization: Mesob One-Stop Service.
Rollout context: HQ first; expanding to multiple branches.
Current operating mode (as-is): Paper-based.
Deployment (initial): Localhost.
Languages: English and Amharic.
Integrations desired (TBD scope/phase): HR (employee list only), barcode scanner, printers,
and email/SMS notifications (allowed).
Data migration approach: Opening balances + historical transactions.
This is a offline tool, your data stays locally and is not send to any server!
Feedback & Bug Reports
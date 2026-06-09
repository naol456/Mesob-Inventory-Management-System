## **Software Requirements Specification** 

## **for Inventory Management System** 

**Version 2.0** 

**Prepared by Group I** 

**Mesob Center (HQ)** 

**June 2026 / Sene 2018** 

_**Copyright © 2026 MESOB Center. All rights reserved.**_ 

_**Software Requirements Specification for Inventory Management System**_ 

_**Page ii**_ 

## **Table of Contents** 

## Contents 

|Contents|Contents|
|---|---|
|**1.** **Introduction ..............................................................................................................................1**||
|1.1|Purpose........................................................................................................................................ 1|
|1.2|Document Conventions............................................................................................................... 1|
|1.3|Intended Audience and Reading Suggestions.............................................................................. 1|
|1.4|Product Scope.............................................................................................................................. 1|
|1.5|References................................................................................................................................... 2|
|**2.** **Overall Description ..................................................................................................................2**||
|2.1|Product Perspective..................................................................................................................... 2|
|2.2|Product Functions........................................................................................................................ 2|
|2.3|User Classes and Characteristics................................................................................................. 2|
|2.4|Operating Environment............................................................................................................... 3|
|2.5|Design and Implementation Constraints...................................................................................... 3|
|2.6|User Documentation.................................................................................................................... 3|
|2.7|Assumptions and Dependencies.................................................................................................. 3|
|**3.** **External Interface Requirements ...........................................................................................3**||
|3.1|User Interfaces............................................................................................................................. 3|
|3.2|Hardware Interfaces..................................................................................................................... 4|
|3.3|Software Interfaces...................................................................................................................... 4|
|3.4|Communications Interfaces......................................................................................................... 4|
|**4.** **System Features .......................................................................................................................4**||
|4.1|Stock Identification (Classification & Coding)........................................................................... 4|
|4.2|Receiving & Inspection............................................................................................................... 5|
|4.3|Issue of Stocks............................................................................................................................. 6|
|4.4|Dispatch Outside Organization (Gate Pass)................................................................................ 6|
|4.5|Stock Records (Bin Cards & Stock Record Cards)..................................................................... 7|
|4.6|Stock Accounting & Valuation (FIFO)....................................................................................... 7|
|4.7|Reporting..................................................................................................................................... 7|
|4.8|Stock Taking & Discrepancy Handling....................................................................................... 8|
|4.9|Stocks Handing/Taking-Over...................................................................................................... 8|
|4.10|Stock Control (Replenishment & Levels).................................................................................... 9|
|4.11|Disposal....................................................................................................................................... 9|
|4.12|Storage, Safety, and Security..................................................................................................... 10|
|4.13|Procurement|
|**5.** **Other Nonfunctional Requirements .....................................................................................18**||
|5.1|Performance Requirements........................................................................................................ 18|
|5.2|Safety Requirements.................................................................................................................. 18|
|5.3|Security Requirements............................................................................................................... 18|
|5.4|Software Quality Attributes....................................................................................................... 18|
|5.5|Business Rules........................................................................................................................... 19|
|**6.** **Other Requirements ..............................................................................................................19**||



**Appendix B: Analysis Models .....................................................................................................12 Appendix C:To Be Determined List ...........................................................................................12 Appendix D: Requirements Traceability ..................................................................................12 Appendix E:Organization-Specific Inputs ................................................................................12** 

_**Software Requirements Specification for Inventory Management System**_ 

_**Page iii**_ 

## **Revision History** 

|**Name**|**Date**|**Reason For Changes**|**Version**|
|---|---|---|---|
|Group I|March<br>2026|Initial release: Sections 4.1 Stock Identification<br>through 4.12 Storage, Safety and Security.<br>Covers the full stock management lifecycle per<br>MoFED Stock Management Manual (May<br>2010).|1.0|
|Group I|June<br>2026|Added Section 4.13 Procurement: 42 functional<br>requirements, 8 business rules, 6 acceptance<br>criteria, and a full integration cross-reference<br>matrix spanning all 12 existing sections. Based<br>on FPPA Federal Government Procurement<br>Execution Manual (Hidar 2018 E.C.) and<br>Proclamation 1210/2012.|2.0|
|||||
|||||
|||||



_**Software Requirements Specification for Inventory Management System**_ 

_**Page 1**_ 

## **1. Introduction** 

## **1.1 Purpose** 

This Software Requirements Specification (SRS) defines requirements for an ERP custom module for Mesob One-Stop Service that implements standardized public-sector stock (inventory) management operating procedures. 

Where organization-specific values or policies are missing or ambiguous, this SRS records them in Appendix C (To Be Determined) instead of assuming. 

## **1.2 Document Conventions** 

- Requirement keywords: “shall” = mandatory; “should” = recommended; “may” = optional. 

- Traceability: Each functional requirement has an ID like FR-ISSUE-001. 

- Business rules: Organizational rules and controls are tagged BR-*. 

- ERP alignment: When an ERP capability is referenced, it is described at the business level (not by undocumented internal implementation). 

## **1.3 Intended Audience and Reading Suggestions** 

- Public body management / PAO: Read Sections 1–2, then Section 4 (features) and 5.5 (Business Rules). 

- Storekeepers / stock clerks: Read Section 4 (features) and Appendix A (Glossary). 

- Developers / implementers: Read Sections 2–6, then Appendix B. 

- Testers / auditors: Focus on Section 4 acceptance criteria and Section 5 (NFRs + business rules). 

## **1.4 Product Scope** 

The module shall support end-to-end stock management for items temporarily kept in stores until needed, including: 

- Stock identification (classification + coding) 

- Receiving and inspection 

- Issue and dispatch 

- Stock records, accounting (FIFO valuation), and reporting 

- Stock taking, discrepancy handling, stock control, disposal linkage, and storage requirements 

- Fixed asset tracking with custody management 

- Digital request/approval workflows 

- HR integration for employee data 

The module is a custom ERP module that configures and extends standard inventory processes to meet Mesob One-Stop Service operating procedures and internal controls. 

_**Software Requirements Specification for Inventory Management System**_ 

_**Page 2**_ 

## **1.5 References** 

- IEEE SRS Guideline 

- Mesob One-Stop Service Internal Standards 

- Ethiopian Government Asset Management Guidelines 

## **2. Overall Description** 

## **2.1 Product Perspective** 

This module is an extension within an ERP environment. It shall use the ERP inventory capabilities as the operational base while enforcing Mesob One-Stop Service business rules and internal controls for stock management. 

Key perspective decisions: 

- **Business rules** : Defined in this SRS and governed by Mesob One-Stop Service. 

- **ERP capability constraint** : The solution shall use standard ERP inventory/accounting capabilities where possible; when multiple options exist, choose the option that best satisfies the requirements in this SRS. 

- **Ambiguity rule** : If a required policy value is not defined, record it as TBD and require an explicit decision. 

## **2.2 Product Functions** 

At a high level, the system shall: 

- Maintain stock master data with standardized classification/coding scheme. 

- Support receiving with inspection and acceptance/rejection handling. 

- Support issuing to departments and dispatch outside with Gate Pass authority. 

- Maintain bin cards and stock record cards, including quantity and value. 

- Value stock using FIFO and produce annual and periodic reports. 

- Conduct stock taking with controlled sheets, discrepancy investigation, and handover/takeover stock taking. 

- Support stock control parameters (min/max/reorder/hastening, safety stock) and regular review. 

- • Record and flag dormant/slow moving, damaged/obsolete items; support disposal workflow linkage (per the organization’s disposal policy; see TBD). 

- Enforce storage organization, safety, and security expectations. 

## **2.3 User Classes and Characteristics** 

- **Property Administration Officer (PAO)** : supervisory user; approves requisitions; oversees compliance; manages stock taking; ensures records and processes. 

- **Storekeeper** : custody user; receives/inspects; issues; maintains bin cards; controls access and storage housekeeping. 

- **Stock clerk** : records user; posts stock movements; maintains stock record cards (quantity + value); prepares reports. 

- **Procurement officer** : ensures goods accepted meet purchase order specs; manages specialized tests/inspections. 

_**Software Requirements Specification for Inventory Management System**_ 

_**Page 3**_ 

- **Department requisitioner/receiver** : creates requisitions; receives and inspects delivered items. 

- **Security officer/guard** : retains Gate Pass copy for dispatch control. 

## **2.4 Operating Environment** 

- ERP environment with inventory and accounting capabilities enabled. 

- Multi-step routes and storage locations may be enabled when needed by routing requirements. 

- Organization context assumptions for initial rollout: 

- Headquarters (HQ) implementation first, with expected expansion to multiple branches. 

- Initial deployment is local (localhost) in the target environment. 

## **2.5 Design and Implementation Constraints** 

- Must adhere to the organization’s stock management procedures and internal control requirements. 

- Must adhere to supported ERP behaviors and configuration constraints. 

- Costing/valuation must comply with FIFO valuation for stock accounting. 

- Change authority: business rule changes shall be controlled via governance (role-based configuration management and audit trails). 

## **2.6 User Documentation** 

- User guide for PAO, storekeeper, stock clerk. 

- Form usage guide for Model 19, Model 20, Model 22, DSR, Gate Pass, Stock Taking Sheet, Handover certificate. 

## **2.7 Assumptions and Dependencies** 

- MESOB HR System API is available and documented 

- Barcode/QR scanning hardware will be provided 

- Users have basic computer literacy 

- Internet connectivity available 

- Disposal procedures exist (details TBD) 

- Purchase orders and packing slips available for receiving 

## **3. External Interface Requirements** 

## **3.1 User Interfaces** 

The module shall provide UI for: 

- Maintaining classification codes and item codes (####-###-###). 

- Receiving workflow: inspection results, Model 19 creation and distribution. 

- Rejection workflow: DSR creation and distribution. 

- Issue workflow: Model 20 approval, Model 22 issuance, receiving confirmation. 

_**Software Requirements Specification for Inventory Management System**_ 

_**Page 4**_ 

- Dispatch workflow: Gate Pass creation with copy distribution. 

- Records screens: bin card view (quantity) and stock record card view (quantity + value). 

- Reporting screens: fiscal year ending balances per 4401–4418; quarterly movement; discrepancy and dormant stock reports. 

- Stock taking screens: create serially numbered stock taking sheets, print, capture counts, record discrepancies, sign-offs. 

- Storage compliance checklist (labels, arrangement, security key register references) where feasible. 

(TBD: exact ERP UI placements and menus.) 

## **3.2 Hardware Interfaces** 

None required beyond standard server/client devices. 

## **3.3 Software Interfaces** 

- ERP Inventory capabilities (stock operations, locations, routes). 

- ERP Accounting capabilities (inventory valuation review/entries). 

(TBD: integration boundaries between inventory and accounting configuration in the target deployment.) 

## **3.4 Communications Interfaces** 

None required beyond standard ERP web access. 

## **4. System Features** 

## **4.1 Stock Identification (Classification & Coding)** 

## **4.1.1. Description** 

Implement standardized stock identification by classification and coding to avoid ambiguous naming and enable reporting and control. 

      - **Priority** : High 

- **4.1.2. Stimulus/Response Sequences:** 

   - Stimulus: Stock clerk creates/updates a stock item master. 

   - Response: System validates classification + code format uniqueness and publishes updated code list/version. 

## **4.1.3. Dependencies** 

ERP product master data must support storing item code and classification. 

- **4.1.4. Functional Requirements** 

   - FR-ID-001 The system shall support major stock classifications per chart of accounts codes 4401 through 4418. 

   - FR-ID-002 The system shall support a 10-digit code format ####-###-### where: first 4 digits = major classification; next 3 digits = sub-class (001–999); 

      - last 3 digits = specific item (001–999). 

_**Software Requirements Specification for Inventory Management System**_ 

_**Page 5**_ 

   - FR-ID-003 The system shall prevent assigning multiple codes to the same stock item (no alternative codes once coded). 

   - FR-ID-004 The system shall support maintaining and distributing a stock code list to relevant units. 

   - FR-ID-005 The system shall support annual publication of coding amendments and maintain version history. 

   - FR-ID-006 The system shall allow excluding seldom-required/non-repetitive items from the coding catalog. 

- **4.1.5. Business Rules** 

   - BR-ID-001 Classification shall be simple, understandable, and group like-with-like. 

- **4.1.6. Acceptance Criteria** 

   - Given a major classification 4402, the system can create item code 4402-001-001 and prevent duplicates. 

## **4.2 Receiving & Inspection** 

- **4.2.1. Description** 

Support receiving from outside suppliers, donors, and returns from user departments, with inspection, acceptance, and rejection flows. 

**Priority** : High 

- **4.2.2. Stimulus/Response Sequences:** 

   - Stimulus: Goods arrive at store. 

   - Response: System records inspection/acceptance; generates Model 19 for accepted items or DSR for rejected items; tracks copy distribution. 

- **4.2.3. Dependencies** 

   - Purchase/packing documents exist as referenced inputs. 

   - ERP stock receipt operations and locations are available. 

- **4.2.4. Functional Requirements** 

   - FR-REC-001 The system shall require a recorded authority (preferably written) before completing receipt of stock/fixed asset. 

   - FR-REC-002 The system shall enforce that items are not put to use before receiving is fully completed. 

   - FR-REC-003 The system shall support receiving steps: unloading check, unpack/inspect vs packing slip and purchase order, then acceptance. 

   - FR-REC-004 The system shall support inspection assignment: storekeeper for simple items; user technical staff for technical items; independent/supplier-site inspection where applicable. 

   - FR-REC-005 The system shall generate Model 19 (Receipt for articles/property) only for accepted items. 

   - FR-REC-006 The system shall support Model 19 four-copy distribution tracking: Accounts Unit (original with supplier invoice), Stock clerk (duplicate) Supplier/deliverer (triplicate), Storekeeper (book copy). 

   - FR-REC-007 The system shall support returns to store from user departments for new supplies by generating Model 19, and mark that no payment will be effected (accounts copy retained with pad). 

   - FR-REC-008 The system shall support rejection returns using DSR in four copies with distribution tracking: Supplier (original accompanies goods), Accounts/finance (duplicate), Procurement officer (triplicate), Storekeeper (book copy). 

   - FR-REC-009 The system shall support recording discrepancies and their type (damaged/shortage/overage/not right quality) on the DSR. 

   - 

## **4.2.5. Acceptance Criteria** 

_**Page 6**_ 

_**Software Requirements Specification for Inventory Management System**_ 

- If inspection fails, the system prevents completion of receipt and requires DSR + return workflow. 

## **4.3 Issue of Stocks** 

## **4.3.1. Description** 

Issue stocks to user departments and dispatch outside with Gate Pass control. **Priority** : High 

## **4.3.2. Stimulus/Response Sequences:** 

   - Stimulus: User department requests items. 

   - Response: System enforces approved Model 20 before issuing; generates Model 22; records department receipt confirmation. 

- **4.3.3. Dependencies** 

   - User roles/permissions for PAO, storekeeper, stock clerk. 

- **4.3.4. Functional Requirements** 

   - FR-ISSUE-001 The system shall support issue scheduling modes: imprest basis, replacement issue, and non-stock issue. 

   - FR-ISSUE-002 The system shall require Model 20 (Stores Requisition) raised by user department and approved by PAO before issue. 

   - FR-ISSUE-003 The system shall allow storekeeper to maintain an authorization file of approvers and specimen signatures. 

   - FR-ISSUE-004 The system shall support restricting issue of controlled materials (e.g., drugs/chemicals/explosives) to authorized individuals. 

   - FR-ISSUE-005 Upon issue, the system shall generate Model 22 in three copies and track distribution: original + requisition to stock clerk for posting, duplicate to requesting department, triplicate retained by storekeeper. 

   - FR-ISSUE-006 The system shall record receipt confirmation by ordering department (count + inspection vs requisition and approval). 

## **4.4 Dispatch Outside Organization (Gate Pass)** 

## **4.4.1. Description** 

Control movement of materials leaving the compound through PAO authority and Gate Pass distribution. 

**Priority** : High 

- **4.4.2. Stimulus/Response Sequences:** 

   - Stimulus: Materials are to be moved outside the compound. 

   - Response: System requires PAO authority + prerequisite documents; generates Gate Pass copies and records distribution. 

- **4.4.3. Dependencies** 

   - Security role/user exists to receive Gate Pass copy. 

- **4.4.4. Functional Requirements** 

   - FR-DISP-001 The system shall require PAO written authority for any material leaving the compound. 

   - FR-DISP-002 The system shall treat Gate Pass as the only written authority for movement outside. 

   - FR-DISP-003 The system shall allow Gate Pass creation only after a duly signed Model 22 or written authorization. 

   - FR-DISP-004 Gate Pass shall be generated in three copies and distribution tracked: original accompanies materials to receiver, duplicate to storekeeper, triplicate to security officer/guard 

_**Software Requirements Specification for Inventory Management System**_ 

_**Page 7**_ 

## **4.5 Stock Records (Bin Cards & Stock Record Cards)** 

## **4.5.1. Description** 

Maintain quantity and value records to enable control, reconciliation, and reporting. **Priority** : High 

- **4.5.2. Stimulus/Response Sequences:** 

   - Stimulus: Receipt, issue, adjustment, or stock-take posting occurs. 

   - Response: System updates bin card and stock record card views for the item and preserves audit trail. 

- **4.5.3. Dependencies** 

   - Underlying stock moves are available in the ERP. 

- **4.5.4. Functional Requirements** 

   - FR-RECARD-001 The system shall support Bin Card per item, showing quantity received, issued, and balance; maintained by storekeeper. 

   - FR-RECARD-002 The system shall support Stock Record Card per item, maintained by stock clerk, including quantity, unit price, total value for receipts/issues/balance. 

   - FR-RECARD-003 Stock Record Cards shall be organized by classification/coding 

## **4.6 Stock Accounting & Valuation (FIFO)** 

## **4.5.5. Description** 

Provide FIFO-based stock costing and valuation consistent with the organization’s stock accounting requirements, and align with ERP inventory valuation capabilities. **Priority** : High 

- **4.5.6. Stimulus/Response Sequences:** 

   - Stimulus: A stock issue is posted or fiscal year end valuation is requested. 

   - Response: System computes issue costs and ending valuations using FIFO; provides totals by major classification for reporting/reconciliation. 

- **4.5.7. Dependencies** 

   - ERP inventory valuation configuration supports FIFO valuation. 

- **4.5.8. Functional Requirements** 

   - FR-VAL-001 The system shall value stock using FIFO for costing of issues and ending balance valuation. 

   - FR-VAL-002 The system shall include in cost: price minus discounts plus freight, insurance, duties/taxes, and package charges as applicable. 

   - FR-VAL-003 If stock value cannot be determined, the system shall support recording an estimated value based on identical/similar goods value at acquisition time. 

   - FR-VAL-004 The system shall support control accounts per classification and a main stock account total; and support monthly reconciliation that main account equals the sum of control accounts. 

## **4.7 Reporting** 

## **4.7.1. Description** 

Provide periodic and fiscal-year-end reporting required for stock accounting, control, and provisioning decisions. 

**Priority** : High 

## **4.7.2. Stimulus/Response Sequences:** 

- Stimulus: Accounts unit requests fiscal year end values; management requests quarterly movement. 

- Response: System generates required reports grouped by classification and item. 

_**Software Requirements Specification for Inventory Management System**_ 

_**Page 8**_ 

## **4.7.3. Dependencies** 

   - Classification/coding is configured. 

   - FIFO valuation data is available. 

- **4.7.4. Functional Requirements** 

   - FR-REP-001 At fiscal year end, the system shall produce a report of ending stock value totals by major classification (4401–4418) for the accounts unit. 

   - FR-REP-002 The system shall support quarterly movement reports per stock item to identify dead/slow moving items and support provisioning decisions. 

   - FR-REP-003 The system shall support reporting existence of dormant/slow-moving stocks, inferior qualities, and record accuracy. 

## **4.8 Stock Taking & Discrepancy Handling** 

## **4.7.5. Description** 

Support end-to-end stock taking: preparation, controlled counting, discrepancy identification, and documented corrective actions. 

**Priority** : High 

## **4.7.6. Stimulus/Response Sequences:** 

   - Stimulus: PAO initiates stock taking event. 

   - Response: System issues pre-numbered sheets, captures counts, compares to records, and produces discrepancy list with reasons/actions. 

- **4.7.7. Dependencies** 

   - Item master + locations/storage layout are set up. 

- **4.7.8. Functional Requirements** 

   - FR-ST-001 The system shall support PAO issuance of stock-taking instructions and recording that pre-stocktaking training was performed. 

   - FR-ST-002 The system shall generate serially numbered stock-taking sheets prepared in advance and pre-typed in logical order matching storage layout and records. 

   - FR-ST-003 The system shall support scheduling per management decision (dates, stores per day, start/end times, breaks). 

   - FR-ST-004 The system shall require issuance of stock-taking sheets to recorder against signature and return completed sheets to team head. 

   - FR-ST-005 The system shall support recording colored-sticker marking to prevent double counting (at minimum: a “counted” marker per item/location). 

   - FR-ST-006 The system shall support comparison of physical counts vs bin cards and stock records and produce a discrepancy list. 

   - FR-ST-007 The system shall support capturing discrepancy reasons and corrective actions. 

   - FR-ST-008 The system shall support noting and dating bin cards in red-ink equivalent (audit marker) when checked. 

   - FR-ST-009 The system shall ensure storekeepers are excluded from being stock-taking team members, but can be recorded as guides/witnessed participants. 

## **4.9 Stocks Handing/Taking-Over** 

## **4.9.1. Description** 

Support mandatory handover stock taking when storekeeper role changes or absence triggers custody transfer. 

**Priority** : High 

- **4.9.2. Stimulus/Response Sequences:** 

   - Stimulus: Storekeeper change event occurs (transfer/leave/etc.). 

_**Page 9**_ 

_**Software Requirements Specification for Inventory Management System**_ 

- Response: System initiates handover stock taking; generates certificate and copy distribution records. 

## **4.9.3. Dependencies** 

   - HR or administration can trigger/record the storekeeper status change event. 

- **4.9.4. Functional Requirements** 

   - FR-HO-001 The system shall support a handover stock-taking workflow triggered by storekeeper status changes (leave/retirement, duty travel, training outside station, promotion, transfer, medical treatment). 

   - FR-HO-002 The system shall require incoming and outgoing storekeepers to conduct stock-taking in presence of a competent witness, with signatures. 

   - FR-HO-003 The system shall generate a handover certificate and stock-taking sheets in triplicate distribution: PAO (original), incoming storekeeper (duplicate), outgoing storekeeper (triplicate). 

## **4.10 Stock Control (Replenishment & Levels)** 

## **4.10.1. Description** 

Support control levels, lead times, and alerts to prevent stock-outs and overstock, and to prioritize management attention. 

**Priority** : Medium 

## **4.10.2. Stimulus/Response Sequences:** 

   - Stimulus: Stock on hand changes or periodic review is performed. 

   - Response: System alerts at reorder/hastening thresholds and supports review/adjustment and ABC classification. 

- **4.10.3. Dependencies** 

   - Historical movement data is available. 

- **4.10.4. Functional Requirements** 

   - FR-SC-001 The system shall allow maintaining control levels per item: minimum, reorder, hastening, maximum, and safety stock. 

   - FR-SC-002 The system shall support lead time modeling with administrative lead time and supplier lead time. 

   - FR-SC-003 When stock reaches reorder level, the system shall prompt ordering action and require checking for outstanding deliveries. 

   - FR-SC-004 The system shall support periodic review of levels (weekly/monthly/quarterly) and allow adjustments. 

   - FR-SC-005 The system shall support ABC analysis classification by usage to prioritize attention (A/B/C groups). 

## **4.11 Disposal** 

## **4.11.1. Description** 

Support identification and controlled tracking of disposal candidates with audit trail; detailed disposal workflow follows the organization’s disposal policy (out of scope for this module until provided). 

**Priority** : Medium 

## **4.11.2. Stimulus/Response Sequences:** 

- Stimulus: Item is identified as unwanted/surplus/unserviceable. 

_**Software Requirements Specification for Inventory Management System**_ 

_**Page 10**_ 

- Response: System records candidate and routes for disposal process per referenced policy (TBD). 

## **4.11.3. Dependencies** 

   - Disposal policy/procedure details are provided and agreed. 

- **4.11.4. Functional Requirements** 

   - FR-DISP2-001 The system shall support identifying unwanted and surplus property and generating disposal candidates list. 

   - FR-DISP2-002 The system shall record that disposal procedures follow the organization’s disposal policy (details TBD) and maintain audit trail of PAO responsibility. 

## **4.12 Storage, Safety, and Security** 

## **4.12.1. Description** 

Support storage arrangement, safety, and security recordkeeping required by organizational standards (labels, plans, key custody, access control, safety checklists) **Priority** : Medium 

- **4.12.2. Stimulus/Response Sequences:** 

   - Stimulus: Storage plan is updated; keys are issued/returned; periodic safety/security checks occur. 

   - Response: System records plan versions, key custody events, visitor/access logs, and checklist outcomes 

- **4.12.3. Dependencies** 

   - User roles/permissions for store management and security. 

- **4.12.4. Functional Requirements** 

   - FR-STOR-001 The system shall support labeling of stocks and shelves and storing by classes. 

   - FR-STOR-002 The system shall support recording storage plan elements (receiving/issuing areas, aisles, gates) as a documented artifact. 

   - FR-STOR-003 The system shall support recording key custody register events (who collected/deposited keys, timestamps, key IDs). 

   - FR-STOR-004 The system shall support recording access control rules and visitor logs where required. 

   - FR-STOR-005 The system shall support recording fire precautions compliance checklist items. 

   - FR-STOR-006 The system shall support recording safety measures (PPE availability, first aid kit, emergency communication readiness) as checklist/audit records. 

## **4.13 Procurement** 

## **4.1.7. Description** 

This section specifies the end-to-end Procurement subsystem of the Inventory Management System for Mesob One-Stop Service. Procurement is the upstream engine that authorises and drives every goods flow into the store. It is therefore deeply integrated with: Stock Identification (4.1 — item codes and classification govern all procurement documents), Receiving & Inspection (4.2 — the approved Purchase Order is the mandatory written authority for FR-REC-001 and the procurement DSR-return loop closes through FR-REC-008), Stock Records (4.5 — every accepted PO receipt triggers a debit posting on the Bin Card and Stock Record Card), Stock Valuation (4.6 — the agreed PO unit price seeded into FR-VAL-001 FIFO costing), Stock Control (4.10 — the 

_**Software Requirements Specification for Inventory Management System**_ 

_**Page 11**_ 

reorder-level trigger in FR-SC-003 automatically creates a draft Purchase Requisition here), Stock Reporting (4.7 — procurement data feeds spend and supplier-performance reports), and Disposal (4.11 — contract close-out and surplus identification are crossreported). Compliance is governed exclusively by: the Ethiopian Federal Government Stock Management Manual (MoFED, May 2010) for store-side procedures; and the Ethiopian Federal Government Procurement Execution Manual (FPPA, Hidar 2018 E.C.) and Proclamation 1210/2012 for the procurement process. 

Priority: High 

## **4.1.8. Stimulus/Response Sequences** 

- Stimulus 1 (Planned): Fiscal year begins → Procurement Unit Head initiates Annual Procurement Plan (APP); departmental need submissions are collected, consolidated, lotted, and approved through the PUH → PEC → HOPE hierarchy before publication. Stimulus 2 (Triggered): Stock on hand for a catalogued item (FR-ID-001) falls to reorder level (FR-SC-003) → system auto-generates a draft Purchase Requisition linked to the item code, standard supplier, and last-approved unit price → Procurement Officer reviews and converts to a formal PO under an APP lot. 

Stimulus 3 (Delivery): Supplier delivers goods against an open PO → Procurement Officer verifies delivery against PO, assigns inspection type, and hands over to Receiving & Inspection (4.2); Model 19 returned to Procurement closes the receipt confirmation → three-way match (PO + Model 19 + supplier invoice) gates payment. 

## **4.1.9. Dependencies** 

Odoo Purchase module (multi-step approval), Account module (budget lines per classification 4401–4418), and Inventory module (receipt confirmation, stock moves). Stock Identification (4.1) codes and classification must be fully configured before any procurement document references an item. Receiving & Inspection (4.2) is the direct downstream consumer of every approved PO. Stock Control (4.10) reorder events feed Procurement with automated requisitions. Disposal (4.11) surplus data feeds back to Procurement to prevent over-ordering. 

- **4.1.10. Functional Requirements** 

## **A.  Annual Procurement Plan (APP) and Needs Management** 

- FR-PROC-001  The system shall allow the Procurement Unit Head (PUH) to initiate an Annual Procurement Plan (APP) for each Ethiopian fiscal year, recording: planning type, execution type, budget year, procurement stream, unit-price updates, allowed item sources (domestic / international), and plan schedule. The APP references stock classification codes (FR-ID-001) so that every planned item is already catalogued before procurement commences. 

- FR-PROC-002  The system shall support departmental Needs Collection (NC): user departments submit procurement needs identifying the stock item code (from the 4401–4418 hierarchy per FR-ID-001), quantity, estimated unit price, and expected delivery period. The system shall validate that the submitted item code exists in the stock catalogue (FR-ID-001 to FR-ID-006) and reject submissions for uncatalogued items. 

- FR-PROC-003  The system shall support a Needs Reviewer (NSR) workflow: reviewing submitted needs, updating or removing individual items, locking approved needs (making them immutable), and forwarding consolidated departmental needs to the Senior Procurement Officer (SPO) for organisational-level review or returning them for correction. Locked needs shall be traceable to the reviewer and timestamp. 

- FR-PROC-004  The system shall support needs consolidation and lotting by the SPO: auto-consolidation of identical item codes across departments (same 10-digit code per FR-ID-002), manual merge of functionally similar items, definition of procurement category, assignment of procurement mechanism per lot, budget distribution per lot, and generation of an Individual Procurement Plan (IPP) per lot. Lot definitions shall remain linked to their source need lines for full traceability. 

_**Software Requirements Specification for Inventory Management System**_ 

_**Page 12**_ 

- FR-PROC-005  The system shall enforce the APP multi-level approval workflow before publication: PUH approval → Procurement Endorsing Committee (PEC) approval → Head of Public Body (HOPE) final authorisation. Any rejection at any level shall return the plan to the immediately preceding actor with mandatory comments. Post-publication revisions shall require explicit HOPE authorisation with a documented reason. 

- FR-PROC-006  The system shall publish the approved APP and automatically route each lot to the correct execution workflow: lots with mechanism ‘bidding’ are routed to the Tender Management workflow (FR-PROC-013); lots with mechanism ‘shopping’ are routed to the RFQ workflow (FR-PROC-016). Emergency procurements not on the APP shall require HOPE authorisation and a retrospective APP update. 

## **B.  Procurement Method Selection and Specification** 

- FR-PROC-007  The system shall support the following procurement methods as defined by FPPA Proclamation 1210/2012, selectable per lot based on estimated value and item characteristics: (i) Open International Competitive Bidding (ICB) — all domestic and international suppliers; (ii) National Competitive Bidding (NCB) — all registered Ethiopian suppliers; (iii) Request for Quotation / Shopping — minimum three independent quotations from registered suppliers, for low-value standard goods; (iv) Direct (Single-Source) Procurement — legally defined exceptional circumstances only, requires documented justification, PEC and HOPE approval. 

- FR-PROC-008  The system shall enforce procurement method selection rules based on configured monetary thresholds: a lot whose estimated value exceeds the configured NCB ceiling shall not permit selection of RFQ or Direct method without HOPEauthorised override. The system shall log every method-selection decision with the selecting user and timestamp. 

- FR-PROC-009  The system shall support technical specification preparation as a prerequisite before a lot is advertised: recording quality characteristics, dimensions, production methods, performance requirements, and standards — ensuring specifications are function/performance-based and do not reference specific brands. The specification record shall carry a sign-off status (Draft / Approved) and block lot advertisement until status is Approved. 

## **C.  Supplier Registration and Qualification** 

- FR-PROC-010  The system shall maintain a vendor/supplier master register aligned with the Federal Procurement Suppliers’ Registration and Recognition framework (Proclamation 1210/2012, Article 22). Each supplier record shall capture: legal registration number, tax identification (TIN), supply category (matching stock classification 4401–4418 from FR-ID-001), contact details, registration expiry date, blacklist / suspension status, and a running performance score aggregated from delivery history. The supplier master is the sole authoritative source for all procurement documents. 

- FR-PROC-011  The system shall support a supplier prequalification workflow for high-value or technically complex procurements: issuing prequalification documents, scoring applicants on financial capacity, technical experience, key personnel, and equipment, generating a ranked shortlist, and recording PEC review of the shortlist before the main bidding stage opens. 

- FR-PROC-012  The system shall block creation or approval of any Purchase Order, RFQ award, or contract where the selected supplier is flagged as blacklisted, suspended, or has an expired registration. The system shall surface a hard-stop alert naming the specific flag. An override shall require a written PAO-level justification recorded in the audit trail. 

- **D.  Bidding and Tender Management** 

- FR-PROC-013  The system shall support preparation and issuance of Bidding Documents per lot, containing at minimum: invitation to bid, instructions to bidders, 

_**Software Requirements Specification for Inventory Management System**_ 

_**Page 13**_ 

bid data sheet, technical specifications (from FR-PROC-009), bill of quantities / schedule of requirements, bid form, price schedule, and bid security form. The system shall enforce that the specification status is Approved (FR-PROC-009) before the bidding document set is finalised. 

- FR-PROC-014  The system shall record bid advertisement details (publication date, medium, submission deadline) and enforce minimum advertising periods per FPPA thresholds. It shall track bid document issuances to individual bidders, record all bidder queries with timestamps, and capture official addenda with evidence of distribution to all registered bidders before the submission deadline. 

- FR-PROC-015  The system shall support bid receipt and public bid opening: recording each bid received with exact timestamp (late bids auto-rejected and logged), bid security amount and validity period, and generating a Bid Opening Record signed by all opening-committee members. Bid opening minutes shall be available to all registered bidders through the system. 

- FR-PROC-016  For RFQ / Shopping lots, the system shall support: issuing an RFQ to a minimum of three independent registered suppliers (FR-PROC-010), recording at least three valid quotations, and enforcing selection of the lowest technically acceptable and responsive quotation. Lots with fewer than three quotations shall be blocked from award unless a PAO records a documented justification (BR-PROC005). 

- **E.  Bid Evaluation** 

- FR-PROC-017  The system shall support a two-stage bid evaluation workflow: (i) Preliminary / Administrative evaluation — checking bid completeness, bid security validity, and eligibility; bids failing this stage are disqualified with recorded reasons. (ii) Technical and financial evaluation — scoring responsive bids against specification criteria using a configurable scoring framework (technical merit, delivery period, aftersales support, and other criteria defined per lot in the bidding document). 

- FR-PROC-018  The system shall apply the Ethiopian domestic preference margin during financial evaluation per FPPA Proclamation 1210/2012, Article 27(4): 13.5% price preference for Ethiopian bidders with ≥70% local content; 11% preference for 40–70% local content. The adjusted evaluated price (bid price minus preference) is used for ranking only; the actual contract and all payment documents use the original bid price without the preference deduction (BR-PROC-003). 

- FR-PROC-019  The system shall produce a Bid Evaluation Report per lot, listing: all bids received, compliance status, evaluated scores / prices, domestic-preference calculations, ranking, and the recommended awardee with justification. This report shall be routed to PEC and HOPE for award approval through the same approval hierarchy as the APP (FR-PROC-005). 

- FR-PROC-020  The system shall support Notification of Award (NoA) issuance and enforce a standstill period before contract signature, during which the complaints register (FR-PROC-037) is open. The system shall block contract generation until the standstill period expires or all lodged complaints are resolved. 

## **F.  Contract Formation and Management** 

- FR-PROC-021  The system shall generate a contract document from the approved bid evaluation result, capturing: contract number, supplier (from FR-PROC-010 master), lot reference (from APP), item codes and descriptions (FR-ID-001), unit prices, total contract value, delivery schedule linked to PO delivery lines, payment terms, applicable law, and dispute-resolution clause. Contracts valued at or above the configured performance-security threshold shall block signature until a performance security record is entered (FR-PROC-022). 

- FR-PROC-022  The system shall record performance security and advance payment guarantee instruments: type (bank guarantee, insurance bond), issuing institution, instrument number, amount, validity period, and release conditions. Advance payment shall not exceed 30% of contract value for goods contracts (BR-PROC-006); advance 

_**Software Requirements Specification for Inventory Management System**_ 

_**Page 14**_ 

payment shall be blocked until an advance payment guarantee of equivalent value is recorded. Performance security release shall only be recorded after satisfactory final delivery and acceptance are confirmed (Model 19 in FR-REC-005). 

- FR-PROC-023  The system shall support contract variation (amendment) management: each variation order records the trigger, nature, justification, and financial impact; variations that increase contract value or materially alter scope shall require re-approval through the same PEC → HOPE hierarchy. The system shall track the cumulative variation total and alert when it approaches or exceeds the regulatory threshold. 

- FR-PROC-024  The system shall track contract delivery milestones against the contractual schedule and flag overdue deliveries to the Procurement Officer. Delivery progress data shall be visible to the Receiving team (4.2) as context when processing incoming goods. Overdue flags shall also surface in the procurement monitoring dashboard (FR-PROC-038). 

- FR-PROC-025  The system shall support contract closure: recording the final delivery acceptance date, linking to the Model 19 completion record from Section 4.2 (FRREC-005), releasing retention and performance security, and marking the contract as Closed. Closed contracts shall be read-only except for audit annotations. Closure data feeds the Supplier Performance Report (FR-PROC-040) and the Disposal surplus identification workflow (4.11). 

- **G.  Purchase Order Management** 

- FR-PROC-026  The system shall support creation of Purchase Orders (POs) from approved APP lots. Each PO shall reference: APP lot number, contract (if applicable), supplier (FR-PROC-010), stock item codes (FR-ID-001 through FR-ID-002), quantities, agreed unit prices (which become the FIFO cost basis per FR-VAL-001), delivery location, and required delivery date aligned to the APP schedule. POs may also be created from framework agreement call-offs. 

- FR-PROC-027  The system shall enforce a PO approval workflow: Procurement Officer prepares → PAO reviews and approves → HOPE final authorisation for POs above the configured value threshold. An approved PO is immutable; all amendments go through the contract variation process (FR-PROC-023). The approved PO is transmitted to the supplier and simultaneously made available to the Receiving & Inspection module (4.2) as the written authority required by FR-REC-001. 

- FR-PROC-028  The system shall track PO status through its full lifecycle: Draft → Pending Approval → Approved → Sent to Supplier → Partially Received → Fully Received → Closed / Cancelled. Status transitions shall be automatic where possible (e.g., status changes to Partially Received upon first Model 19 link from Section 4.2). Overdue POs shall be surfaced in the procurement monitoring dashboard (FR-PROC038). 

- FR-PROC-029  When the system detects a stock item at or below its reorder level (FRSC-003), it shall automatically generate a draft Purchase Requisition linked to the item’s 10-digit code (FR-ID-002), standard supplier, and last approved unit price. The system shall first check for any outstanding open PO or contract delivery for the same item before raising the requisition, preventing duplicate ordering. The Procurement Officer reviews and converts the requisition to a formal PO under the appropriate APP lot. 

## **H.  Goods Receipt Confirmation (Integration with Section 4.2)** 

- FR-PROC-030  Upon goods arrival, the system shall expose the relevant approved PO to the Receiving team (Section 4.2) as the mandatory written authority required by FRREC-001. The Procurement Officer shall confirm that the delivery matches the PO in item code (FR-ID-001), description, quantity, and delivery terms before the Storekeeper proceeds with the physical inspection workflow (FR-REC-003 through FR-REC-009). 

_**Software Requirements Specification for Inventory Management System**_ 

_**Page 15**_ 

- FR-PROC-031  The Procurement Officer shall record the assigned inspection type for each delivery on the PO delivery record — aligning with FR-REC-004: storekeeper inspection for simple standard items; user technical staff for technical items; independent or supplier-site inspection where the contract specifies it. This assignment shall be visible to the Receiving team before inspection commences. 

- FR-PROC-032  When items are rejected during inspection (FR-REC-008 DSR raised), the system shall automatically notify the Procurement Officer and open a supplierreturn workflow: issuing a formal rejection notice referencing the DSR, recording the supplier’s response and replacement timeline, updating the PO delivery status to Partially Received or Pending Replacement, and tracking until replacement goods are received and accepted (new Model 19 created via FR-REC-005). 

- FR-PROC-033  When the Receiving team issues a Model 19 for accepted goods (FRREC-005), the system shall automatically: (i) update the PO delivery status; (ii) trigger a debit entry on the relevant Bin Card (FR-RECARD-001) and Stock Record Card (FR-RECARD-002) at the PO unit price; (iii) provide the Model 19 reference to the payment workflow as one leg of the three-way match (FR-PROC-034). This closes the loop between procurement, receiving, and stock records. 

## **I.  Payment Processing** 

- FR-PROC-034  The system shall enforce a three-way match before any payment is processed: (i) approved Purchase Order (FR-PROC-026/027), (ii) Model 19 acceptance receipt from Section 4.2 (FR-REC-005), and (iii) supplier’s VATcompliant tax invoice. Payment shall be hard-blocked if any leg is missing, if quantities or unit prices are mismatched, or if a DSR (FR-REC-008/FR-PROC-032) is still open for the delivery (BR-PROC-002). 

- FR-PROC-035  The system shall support price adjustment calculation for contracts with adjustable price provisions: applying the Adjustable vs. Non-Adjustable price distinction per the contract record (FR-PROC-021), computing adjustments using the formula (base price, weighting factors, and current index values), and generating an adjusted payment certificate for PAO finance approval. The adjusted payment certificate value shall not be used to update the FIFO unit cost in stock records (FRVAL-001) — the original PO price remains the cost basis. 

- FR-PROC-036  The system shall compute and apply liquidated damages for late delivery: days of delay times the per-day penalty rate stipulated in the contract (default: 1/1000 of contract value per working day), deducting the amount from the payment certificate. The system shall cap total deductions at the maximum penalty allowed by the contract and record all deduction calculations transparently on the payment certificate. 

- FR-PROC-037  The system shall track and enforce retention holdbacks: computing the retention deduction per payment certificate (up to 10% until release conditions met per FR-PROC-025 contract closure), maintaining the retention account balance per contract, and releasing retention only after the Procurement Officer records a warranty/defects-liability clearance linked to the contract closure record (FR-PROC025). 

## **J.  Complaints and Appeals** 

- FR-PROC-038  The system shall maintain a formal procurement complaints register: recording each complaint with date, complainant name, subject lot or contract reference, nature of complaint (bidding irregularity / specification dispute / award challenge / contract dispute), response actions taken with timestamps, and final resolution outcome. Complaints filed during the standstill period (FR-PROC-020) shall automatically block contract signature until resolved or the statutory review period lapses. 

## **K.  Procurement Monitoring, Reporting, and Audit Readiness** 

- FR-PROC-039  The system shall produce an APP Execution Progress Report showing per lot: planned vs. actual procurement stage, planned vs. actual award date, contract 

_**Page 16**_ 

_**Software Requirements Specification for Inventory Management System**_ 

value vs. original estimate, delivery status, and payment status. This report shall integrate with the Stock Reporting module (4.7 FR-REP-002) so that spend data and stock movement data are visible in a unified view. The report shall support electronic submission to the FPPA e-GP system. 

- FR-PROC-040  The system shall produce a Supplier Performance Report per supplier per period: number of POs issued, on-time delivery rate, DSR rejection rate (from FRREC-008 and FR-PROC-032), complaint history (FR-PROC-038), and overall performance rating. This report feeds directly into future bid evaluation scoring (FRPROC-017) and supplier qualification decisions (FR-PROC-010), closing the supplierperformance feedback loop. 

- FR-PROC-041  The system shall maintain a complete, timestamped, and tamperevident procurement file per lot including: APP approval decision, specification, bidding documents, bid opening record, evaluation report, contract and all variation orders, PO records, Model 19 receipts (from FR-REC-005), payment certificates, DSRs (from FR-REC-008), and complaints. All file entries shall be traceable to the creating/approving user, date, and time to support FPPA audit readiness (NFR-QUAL001 extended to procurement domain). 

- FR-PROC-042  The system shall generate a Procurement-to-Stock reconciliation report that matches every closed PO to its Model 19 receipts, the resulting Bin Card debits (FR-RECARD-001), Stock Record Card entries (FR-RECARD-002), and payment records. Any PO line with a quantity gap between ordered, received, and stocked shall be flagged for PAO investigation — directly supporting the stock discrepancy management in Stock Taking (4.8 FR-ST-006 and FR-ST-007). 

## **4.1.11. Business Rules** 

- BR-PROC-001  No procurement expenditure shall be initiated without a corresponding approved APP lot; emergency procurements require explicit HOPE authorisation and a retrospective APP update within 5 working days. 

- BR-PROC-002  Payment to a supplier shall not be processed unless a valid Model 19 acceptance receipt (FR-REC-005) is linked, confirming goods have been inspected and accepted in store. Open DSRs (FR-REC-008) on any line of the delivery also block payment. 

- BR-PROC-003  Domestic preference adjustments (13.5% for ≥70% local content; 11% for 40–70%) apply to the evaluated price for ranking only; contracts and payment documents use the original bid price. 

- BR-PROC-004  Direct (single-source) procurement shall be used only under legally defined exceptional circumstances; each use shall be documented, approved by PEC and HOPE, and reported to FPPA where required. 

- BR-PROC-005  A minimum of three independent valid quotations from registered suppliers (FR-PROC-010) is required for every RFQ / Shopping lot; fewer than three requires a PAO-recorded documented justification. 

- BR-PROC-006  Advance payment shall not exceed 30% of contract value for goods contracts and shall only be made after an advance payment guarantee of equivalent value is recorded and verified in the system. 

- BR-PROC-007  The PO unit price for each item code (FR-ID-001) becomes the FIFO cost seed for that receipt batch in Stock Records (FR-VAL-001, FR-VAL-002). Priceadjustment amounts (FR-PROC-035) shall not alter the stock record cost; they are financial adjustments only. 

- BR-PROC-008  Any stock item identified as surplus during Disposal review (4.11 FRDISP2-001) shall trigger a procurement suspension flag for that item code, preventing new POs for the same item from being approved until the surplus is consumed or disposed of. 

## **4.1.12. Acceptance Criteria** 

- AC-PROC-001  Given an approved NCB lot with estimated value above the RFQ threshold, the system shall route it to the tendering workflow, block PO creation 

_**Software Requirements Specification for Inventory Management System**_ 

_**Page 17**_ 

      - without a signed contract or HOPE-authorised purchase authority, and hard-block payment unless Model 19 is linked. 

   - AC-PROC-002  Given three bids where Bidder A (70% local content) bids ETB 900,000,000, Bidder B (40% local content) bids ETB 840,000,000, and Bidder C (foreign) bids ETB 750,000,000, the system shall compute adjusted prices of ETB 778,500,000, ETB 747,600,000, and ETB 750,000,000 respectively, rank Bidder B first, and award the contract at the actual price of ETB 840,000,000. 

   - AC-PROC-003  Given a stock item at its reorder level with no open PO for that item code, the system shall generate a draft Purchase Requisition automatically, without waiting for manual intervention. 

   - AC-PROC-004  Given a PO delivery where the supplier delivers 80 units against a PO for 100 units, the system shall set PO status to Partially Received, expose the outstanding 20 units as a pending balance, and allow the Receiving team to issue a partial Model 19 for 80 units that triggers Bin Card and Stock Record Card debits for exactly 80 units at the PO unit price. 

   - AC-PROC-005  Given a contract for ETB 4,000,000 with 18-working-day delivery, and actual delivery on day 19, the system shall compute a liquidated damage of ETB 4,000 (4,000,000 × 1/1000 × 1 day), deduct it from the payment certificate, and show net payable of ETB 3,996,000. 

   - AC-PROC-006  Given a stock item identified as surplus in the Disposal workflow (FR-DISP2-001), the system shall flag that item code and prevent approval of a new PO for it until the PAO explicitly clears the surplus flag with a documented reason. 

- **4.1.13. Integration Cross-Reference Matrix** 

   - The table below summarises how Section 4.13 Procurement integrates with every other section of this SRS. A bidirectional arrow (⇄) indicates data flows in both directions; a right arrow (→) indicates Procurement is the producer; a left arrow (←) indicates the other section is the producer. 

   - 4.1 Stock Identification ← 4.13: All procurement documents (need submissions FRPROC-002, PO FR-PROC-026, contracts FR-PROC-021) reference the 10-digit item code (FR-ID-001/002). Procurement must not create documents for uncatalogued items. Standardisation outcomes from procurement usage feed coding amendments (FR-ID-005). 

   - 4.2 Receiving & Inspection ⇄ 4.13: Approved PO (FR-PROC-027) is the written authority for FR-REC-001. Inspection type assignment (FR-PROC-031) aligns with FR-REC-004. Model 19 (FR-REC-005) closes the procurement receipt confirmation (FR-PROC-033) and gates payment (FR-PROC-034). DSR from FR-REC-008 triggers the supplier-return workflow (FR-PROC-032). 

   - 4.3 Issue of Stocks ← 4.13: Procurement ensures items are in store before user departments can requisition. Fast-moving items identified through issue patterns (FRISSUE-001 imprest schedules) inform reorder levels and procurement frequency in FR-SC-001/003. 

   - 4.5 Stock Records ← 4.13: Model 19 receipt (FR-REC-005) triggers Bin Card debit (FR-RECARD-001) and Stock Record Card debit (FR-RECARD-002) at the PO unit price seeded from FR-PROC-026. FR-PROC-042 reconciliation report validates stock record debits match PO received quantities. 

   - 4.6 Stock Valuation ⇄ 4.13: PO unit price (FR-PROC-026) is the cost seed for FIFO batches (FR-VAL-001/002). Price adjustment amounts (FR-PROC-035) are financialonly and do not alter stock cost. FR-PROC-042 flags any cost discrepancy between PO price and posted receipt value. 

   - 4.7 Stock Reporting ← 4.13: APP Execution Progress Report (FR-PROC-039) integrates with FR-REP-002 quarterly movement reports to provide a unified spendand-movement view. Supplier Performance Report (FR-PROC-040) informs dead/slow-moving stock analysis (FR-REP-003). 

_**Software Requirements Specification for Inventory Management System**_ 

_**Page 18**_ 

- 4.8 Stock Taking & Discrepancy Handling ⇄ 4.13: FR-PROC-042 reconciliation flags procurement-to-stock gaps that feed the discrepancy list (FR-ST-006/007). Stocktaking shortfalls may reveal supplier short-delivery not caught at receiving, triggering a retrospective supplier claim through the procurement complaints register (FR-PROC038). 

- 4.10 Stock Control → 4.13: Reorder level trigger (FR-SC-003) auto-generates a draft Purchase Requisition in Procurement (FR-PROC-029). Lead-time modelling (FR-SC002) informs the delivery schedule on POs (FR-PROC-026). ABC analysis (FR-SC005) prioritises Procurement attention on A-class items. 

- 4.11 Disposal ⇄ 4.13: Surplus identification (FR-DISP2-001) raises a procurement suspension flag for that item code (BR-PROC-008), blocking new PO approvals. Contract close-out (FR-PROC-025) records surplus assets for potential disposal. Disposal proceeds reduce net procurement cost in management reporting. 

- 4.12 Storage, Safety, and Security ← 4.13: Delivery of goods on a PO must be directed to the designated receiving/storage area (FR-STOR-002 storage plan). Hazardous goods procured under specific item codes must carry procurement-level safety classification that aligns with FR-STOR-005/006 storage safety checklists. 

## **5. Other Nonfunctional Requirements** 

## **5.1 Performance Requirements** 

- NFR-PERF-001 The system shall generate fiscal year end valuation reports (by 4401–4418) within an acceptable time for the organization’s stock volume. (TBD: SLA) 

## **5.2 Safety Requirements** 

- NFR-SAFE-001 The system shall support storage safety compliance recording as required by organizational standards (training, PPE, emergency equipment). 

## **5.3 Security Requirements** 

- NFR-SEC-001 Only authorized users shall approve requisitions (PAO) and issue controlled materials. 

- NFR-SEC-002 Gate Pass records shall be immutable after dispatch (except via controlled correction workflow) to preserve auditability. 

- NFR-SEC-003 Key custody register records shall be tamper-evident (audit trail). 

## **5.4 Software Quality Attributes** 

- NFR-QUAL-001 Auditability: All receipt/issue/valuation/stock-taking actions shall be traceable to user, date/time, and source documents. 

- NFR-QUAL-002 Usability: Forms-based workflows shall mirror the organization’s standard operating sequence to reduce training burden. 

- NFR-QUAL-003 Maintainability: Classification codes and stock levels shall be configurable within controlled governance. 

_**Page 19**_ 

_**Software Requirements Specification for Inventory Management System**_ 

## **5.5 Business Rules** 

- BR-VAL-001 FIFO valuation shall be used for stock valuation. 

- BR-DISP-001 Gate Pass is the only authority for movement outside compound. 

- BR-ST-001 Storekeepers shall not be members of stock-taking teams. 

- BR-COD-001 Major classifications shall follow 4401–4418 chart-of-accounts mapping. 

## **6. Other Requirements** 

- Training support: the system should support exporting training materials and printable forms. 

- • Localization: UI and outputs shall support English and Amharic. 

_**Software Requirements Specification for Inventory Management System**_ 

_**Page 20**_ 

## **Appendix A: Glossary** 

- PAO: Property Administration Officer. 

- Stock: items not immediately consumed, temporarily kept in store until needed. 

- Storekeeper: custodian responsible for receipt/inspection/issue/custody. 

- Stock clerk: responsible for stock movement records and reports. 

- FIFO: First In First Out valuation method. 

- DSR: Damage/Shortage Report. 

- Gate Pass: written authority for materials leaving compound. 

## **Appendix B: Analysis Models** 

(TBD) Process flow diagrams (Receiving, Issue, Stock Taking) and data model mapping to ERP entities. 

## **Appendix C: To Be Determined List** 

- TBD-001 ERP edition and hosting/deployment model (on-prem/managed hosting/etc.). 

- TBD-002 Exact Ethiopian Calendar (EC) fiscal year end date and reporting calendar alignment. 

- TBD-003 Disposal procedure details and required forms/approvals. 

- TBD-004 Exact definition of fixed asset vs supplies thresholds in your implementation context. 

- TBD-005 Whether bilingual UI/output (English/Amharic) is required. (Confirmed: Both) 

- TBD-006 Exact performance SLAs and expected transaction volumes. 

## **Appendix D: Requirements Traceability (Internal)** 

This appendix defines how requirements are traced within the organization. 

- Each functional requirement (FR-*) and business rule (BR-*) shall be traceable to: a business owner (process owner), an implemented ERP configuration/customization artifact, and verification evidence (test case, UAT sign-off, or audit checklist record). 

- (TBD: define the organization’s official process owners and artifact repository locations.) 

## **Appendix E: Organization-Specific Inputs (Captured)** 

- Organization: Mesob One-Stop Service. 

- Rollout context: HQ first; expanding to multiple branches. 

- Current operating mode (as-is): Paper-based. 

- Deployment: To be decided. 

- Languages: English and Amharic. 

- Integrations desired (TBD scope/phase): HR (employee list only), barcode scanner, printers, and email/SMS notifications (allowed). 

- Data migration approach: Opening balances + historical transactions. 


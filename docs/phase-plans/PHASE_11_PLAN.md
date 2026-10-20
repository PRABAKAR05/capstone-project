# Phase 11 Plan — Revision 2
## Insurance Module & Hospital Operations Analytics Dashboard

**Document:** `docs/phase-plans/PHASE_11_PLAN.md`  
**Phase:** 11 — Insurance Module & Hospital Operations Analytics Dashboard  
**Status:** Proposal for Owner Review — NOT APPROVED FOR IMPLEMENTATION  
**Date:** 2026-10-16  

> [!IMPORTANT]
> **PROPOSAL ONLY — NO IMPLEMENTATION AUTHORIZED**  
> In accordance with CareBridge AI project governance, this document is an architectural specification recording owner design choices. No database migrations, backend endpoints, analytics calculators, or UI components will be written until the owner explicitly authorizes Phase 11 implementation. Capstone research assets on CSCM-IoMT remain strictly protected and isolated.

---

## 1. Selected Design Decisions Recorded

| Decision | Selected Option | Recorded Design Specification |
|---|---|---|
| **1. Insurance Workflow** | **Option A** | Deterministic rule engine evaluates synthetic policy rules, coverage limits, co-pay ratios, pre-existing-condition exclusions, and consultation/procedure costs. Results are strictly explainable estimates, not insurer decisions. |
| **2. Operations Analytics** | **Option A** | Server-side SQL aggregations with a bounded, in-memory time-window cache for OPD volume, doctor utilization, and average wait time. Raw patient-level rows are never sent for client-side aggregation. |
| **3. Patient Visibility & Privacy** | **Option A** | Role-partitioned views. Patients see only their own permitted policy, pre-authorization, and co-pay estimate information. Operational KPIs are limited to authorized administrative roles (`hospital_admin`). |

*Note: These are design choices only. They do not constitute approval to implement Phase 11.*

---

## 2. Objectives

1. Provide an explainable, deterministic insurance-estimation workflow for demonstration using synthetic policy data.
2. Give authorized hospital administrators an operational dashboard based on server-side aggregate queries.
3. Enforce hospital tenancy, role permissions, and patient-level access on every read and write.
4. Make uncertainty, missing policy data, and exclusions visible instead of implying guaranteed coverage.
5. Preserve all CSCM-IoMT research assets and keep the CSCM service outside this phase's scope.

---

## 3. Scope and Planned Capabilities

### 3.1 Insurance Workflow — Deterministic Estimates
- Model synthetic insurance policies, coverage categories, limits, co-pay ratios, exclusions, and relevant consultation/procedure cost inputs.
- Evaluate only explicit, versioned rules and fields. Do not use an LLM to decide coverage.
- Return an explainable result containing:
  - Estimate status (e.g., `estimate_available`, `insufficient_information`, or `review_required`);
  - Input fields and policy-rule version used;
  - Applicable limit, co-pay calculation, and matched exclusion where relevant;
  - Assumptions, missing information, and calculation breakdown;
  - Calculation timestamp.
- Support administrative tracking of pre-authorization/claim status only to the extent supported by the approved schema and current roles.
- Keep any coverage estimate distinct from insurer adjudication or a confirmed authorization.
- Use synthetic policies and costs for demos, tests, and fixtures. Do not send real patient/insurance data to Groq or another external model.

### 3.2 Operations Analytics — Server-Side Aggregation and Cache
- Proposed initial KPIs:
  - **OPD volume** over a selected time window;
  - **Doctor utilization**, with the denominator and appointment statuses explicitly defined;
  - **Average wait time**, only where reliable check-in/consultation timestamps exist.
- Requirements:
  - Aggregate in SQL on the server; do not fetch patient-level lists to the browser for client-side aggregation.
  - Apply hospital/tenant filters and authorization before returning aggregates.
  - Use a bounded, in-memory time-window cache only as a performance optimization. Define TTL, maximum size, cache key dimensions (including hospital and time window), and invalidation/expiry behavior.
  - Do not promise sub-50-ms responses until measured under a documented workload. Report measured latency and test conditions rather than treating it as a guaranteed target.
  - If source timestamps or status data are absent or unreliable, mark the KPI unavailable or define a transparent fallback; do not invent values.

### 3.3 Role-Partitioned Visibility
- Patients can access only their own authorized policy and estimate/pre-authorization information.
- Caregivers can access patient insurance information only when a valid, current patient-account linkage explicitly permits it and the existing authorization model supports that scope.
- Operational KPIs are available only to explicitly authorized hospital administrative roles. Doctor views, if added, must be separately scoped and justified.
- Receptionists and other staff receive only the minimum information needed for their approved workflow.
- Never expose cross-hospital aggregates, policy identifiers, patient names, or other identifying details in general operational dashboards.
- Enforce permissions on the backend and in database RLS; hiding a UI element is not an authorization control.

---

## 4. Implementation Stages (After Explicit Approval)

1. **Stage 0 — Read-Only Integration Audit**:
   - Inspect existing Phase 2 tenant/RLS model and Phase 3–10 schemas, routes, authorization helpers, appointment statuses, and timestamps.
   - Identify exact role names and existing insurance-related fields, if any.
   - Confirm aggregation definitions and whether source data supports wait-time/utilization calculations.
   - Check current migrations and repository working tree before proposing new files.
   - *Stop condition*: If an existing API, schema, or permission model conflicts with this plan, document the mismatch and submit a separate change proposal for owner approval. Do not silently broaden scope.
2. **Stage 1 — Detailed Schema and Rule Specification**:
   - Propose additive, tenant-safe schema changes only if necessary.
   - Define policy-rule versioning, supported inputs, currency/rounding rules, missing-data behavior, and calculation examples.
   - Define KPI formulas, appointment-status inclusion, time zones, cache boundaries, and access matrix.
   - Include migration rollback notes. No destructive migrations, resets, or data deletion without separate explicit approval.
3. **Stage 2 — Backend Insurance Rules**:
   - Implement a deterministic, unit-testable calculation service using synthetic fixtures.
   - Validate input ranges and policy applicability.
   - Return explanations and explicit estimate/review statuses.
   - Add server-side authentication, role checks, tenant constraints, RLS, and audit events that contain no PHI or policy secrets.
   - Do not guarantee coverage or automatically approve/deny an insurer claim.
4. **Stage 3 — Backend Analytics**:
   - Implement tenant-scoped SQL aggregate queries and a bounded time-window cache.
   - Define cache TTL, keying, isolation, expiry/invalidation, and fallback behavior.
   - Add pagination or bounded time windows where applicable; avoid raw patient-level payloads.
   - Instrument safe aggregate latency measurements without logging PHI.
5. **Stage 4 — Frontend Role-Based Workspaces**:
   - Patient insurance view: own policy summary, estimate breakdown, exclusions/unknowns, and status.
   - Authorized staff view: permitted policy/pre-authorization tracking and required follow-up.
   - Administrative analytics dashboard: aggregate KPIs only, with filters and definitions.
   - Show calculation time, rule version, caveats, and unavailable-data states.
   - Ensure responsive layout and accessible loading/error/empty states.
6. **Stage 5 — Security and Regression Validation**:
   - Test tenant isolation and role enforcement for every endpoint.
   - Test patient A cannot read patient B's policies or estimates; caregiver access is rechecked dynamically.
   - Test cache keys cannot mix hospitals, roles, or time windows.
   - Test exclusions, limits, co-pay math, rounding, missing data, invalid inputs, and rule-version reproducibility.
   - Test analytics against known synthetic fixtures, including timezone boundaries and cancelled/no-show appointments.
   - Run Phase 3–10 regression suites and frontend lint/build.
   - Verify no real patient/insurance data is sent to external LLMs and no PHI is written to audit/application logs.
   - Verify CSCM research files, checkpoints, datasets, and evaluation scripts remain unchanged.
7. **Stage 6 — Report and Stop**:
   - Record files changed, migrations, routes, UI, tests actually run, outcomes, warnings, and known limitations in `docs/phase-reports/PHASE_11_REPORT.md`.
   - Clearly distinguish executed test results from planned tests.
   - Stop after reporting. Do not begin Phase 12 or any other phase without separate authorization.

---

## 5. Conceptual Data and API Design (Subject to Read-Only Audit)

*Exact names and shapes must be confirmed against the current repository before implementation. These are conceptual resources, not authorization to create them.*

### Insurance Concepts
- Policy and coverage rules with tenant ownership, effective dates, version, limits, co-pay ratio, and exclusions.
- Estimate request inputs tied to an allowed consultation/procedure cost and policy reference.
- Estimate result with rule version, itemized calculation, status, assumptions, and timestamp.
- Optional pre-authorization/claim tracking status with actor and timestamp; distinguish hospital-entered status from insurer-confirmed status.

### Analytics Concepts
- Server-side aggregate endpoint(s) for OPD volume, doctor utilization, and average wait time.
- Explicit time-window filters and authorized hospital scope.
- Aggregate-only response schema; no patient-level rows.
- Cache metadata must not expose sensitive identifiers.

---

## 6. Safety, Privacy, and Security Requirements

- **Informational Estimates Only**: Estimates are informational aids, not financial guarantees, insurer decisions, or a substitute for insurer confirmation.
- **No Autonomous Decisions**: No autonomous claim approval, claim denial, clinical decisions, or consequential financial actions.
- **No Unfounded Inferences**: Do not infer policy terms that are absent or ambiguous. Return `insufficient_information` or `review_required`.
- **Synthetic Data Boundary**: Use synthetic data for demonstrations and tests. No real PHI or identifiable insurance documents sent to Groq/external models.
- **Server-Side Credentials**: Keep credentials server-side; never expose Supabase service-role keys or other secrets to the browser.
- **Server-Side Authorization & RLS**: Use server-side authorization and tenant-safe database constraints/RLS. Revalidate access for each request.
- **Zero-PHI Audit Trail**: Audit logs must be PHI-free and avoid policy numbers, document text, names, and sensitive calculation inputs.
- **Cache Isolation**: Avoid cache leakage across hospitals, patients, roles, or time windows.
- **Non-Destructive Database Operations**: No destructive database operations without separate explicit approval.

---

## 7. Acceptance Criteria (AC-11.1 to AC-11.15)

| Criteria ID | Requirement | Verification Method |
|---|---|---|
| **AC-11.1** | **Deterministic Rule Engine** | Uses deterministic, versioned rules producing reproducible outputs for identical inputs and rule versions. |
| **AC-11.2** | **Coverage & Calculation Unit Tests** | Coverage limits, co-pay math, exclusions, rounding, and missing-data cases have dedicated unit tests. |
| **AC-11.3** | **Uncertainty Transparency** | Ambiguous or incomplete policy data produces explicit review/insufficient-information state, never guessed results. |
| **AC-11.4** | **Informational Estimate Labeling** | UI explicitly labels outputs as estimates and never promises insurer approval or guaranteed coverage. |
| **AC-11.5** | **No Autonomous Claim Actions** | No claim is automatically approved or denied by the system. |
| **AC-11.6** | **Patient Privacy Boundary** | Patients can access only their own authorized insurance information. |
| **AC-11.7** | **Caregiver Relationship Validation** | Caregiver access is allowed only through a currently valid, explicitly scoped relationship. |
| **AC-11.8** | **Authorized Administrative KPIs** | Administrative KPIs are backend-authorized and tenant-scoped; raw patient lists are never sent for client-side aggregation. |
| **AC-11.9** | **Documented KPI Formulas** | OPD volume, doctor utilization, and average wait-time formulas are documented and validated against synthetic fixtures. |
| **AC-11.10** | **Tenant-Safe Cache Boundaries** | Cache entries cannot cross tenant or time-window boundaries; expiry/invalidation and size limits are verified. |
| **AC-11.11** | **Zero-PHI Audit Logging** | Audit and application logs contain no PHI or sensitive policy/document contents. |
| **AC-11.12** | **Full Regression Stability** | Phase 3–10 regressions, backend tests, frontend lint, and production build pass cleanly. |
| **AC-11.13** | **Zero External PHI Transmission** | No real patient or insurance data is sent to Groq or another external model. |
| **AC-11.14** | **CSCM-IoMT Research Preservation** | CSCM-IoMT source, checkpoints, datasets, configuration, and evaluation scripts remain 100% unchanged. |
| **AC-11.15** | **Implementation Reporting & Stop Gate** | Complete Phase 11 implementation report is written, and work stops for owner review before Phase 12. |

---

## 8. Explicit Exclusions

- No implementation until the owner explicitly approves Phase 11.
- No automatic insurer adjudication, guaranteed coverage, or financial commitment.
- No AI/LLM-based insurance decisioning.
- No real patient/insurance data sent to external LLMs.
- No client-side aggregation over patient-level resource lists.
- No new roles or permission expansions without owner review.
- No changes to CSCM-IoMT research assets, including source code, checkpoints, datasets, training/evaluation scripts, or model configuration.
- No destructive migrations, resets, or deletion of existing data without separate explicit approval.

---

## 9. Owner Approval Gate

**Current State: REVISION 2 RECORDED — AWAITING FORMAL IMPLEMENTATION APPROVAL.**

Confirmed design choices:
- **Decision 1 (Insurance Workflow)**: **Option A** — Deterministic policy rules and explainable coverage/co-pay estimates using synthetic data.
- **Decision 2 (Operations Analytics)**: **Option A** — Server-side SQL aggregations and a bounded in-memory cache for OPD volume, doctor utilization, and average wait time.
- **Decision 3 (Patient Privacy)**: **Option A** — Patients see their own authorized insurance information; operational KPIs are restricted to authorized administrators.

In accordance with CareBridge AI governance:
- **No implementation code, migrations, or endpoints will be created** until formal owner authorization is received (e.g., `"Approve Phase 11"`).
- **CSCM-IoMT Research Assets** remain 100% protected and isolated across `src/`, `models/`, and `data/`.

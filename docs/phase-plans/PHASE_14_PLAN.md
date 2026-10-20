# Phase 14 Plan — Revision 8
## Final Capstone Packaging, Database Seeding, Public Demo Mode & Comprehensive Visual QA Audit

**Document:** `docs/phase-plans/PHASE_14_PLAN.md`  
**Phase:** 14 — Final Capstone Packaging, Visual Verification & Release Assessment  
**Status:** Proposal for Owner Review — Final Corrections Incorporated  
**Date:** 2026-10-16  

> [!IMPORTANT]
> **PROPOSAL ONLY — NO IMPLEMENTATION AUTHORIZED**  
> In accordance with CareBridge AI critical governance rules, this document is an architectural planning proposal submitted for owner review. 
> - **Zero Code/Database Changes Authorized:** No application code, database schemas, migrations, seed data, environment files, or documentation files other than this plan may be modified.
> - **Zero File Churn:** No deleting, moving, renaming, or overwriting of existing repository files.
> - **Strict Research Preservation Mandate:** All CSCM-IoMT research assets across `src/`, `models/`, and `data/` remain strictly immutable, isolated, and read-only.
> - **Evidentiary Integrity & Targets to Verify:** The 17-table inventory, 17,727 CSCM files, and 128 tests are treated as **targets to verify dynamically at runtime**, not pre-confirmed facts. Tests and screenshots will only be reported as passed after actual execution.

---

## 1. Corrections Incorporated in Revision 8

In response to the latest owner review, Revision 8 embeds the following primary governance corrections:

| Issue Area | Required Governance Correction Incorporated |
|---|---|
| **1. Genuine PostgreSQL Isolation for Recovery Testing** | • **Strictly forbids SQLite:** SQLite is insufficient to validate PostgreSQL-specific types (`UUID`, `JSONB`, `TIMESTAMPTZ`), custom ENUMs, check constraints, sequences, and foreign-key cascade behaviors.<br>• Snapshot recovery is tested against a **genuinely isolated PostgreSQL sandbox** (e.g. `CREATE SCHEMA recovery_sandbox_temp;` within PostgreSQL or a disposable test database) before touching the target database.<br>• Drops the sandbox cleanly (`DROP SCHEMA recovery_sandbox_temp CASCADE;`) upon verification.<br>• Automated rollback procedure **never** executes `DROP TABLE` or `TRUNCATE` against live database tables. Rollback is surgical, deleting only synthetic records (`SYN-` prefix / deterministic UUIDs). |
| **2. Schema-Aware & Tenant-Consistent Synthetic Seeding** | • The 15-record requirement is made **strictly schema-aware**:<br>&nbsp;&nbsp;- Respects table foreign keys and multi-tenant isolation: all child records (`departments`, `doctors`, `patients`, `appointments`, `documents`, `prescriptions`, `claims`) share the exact same `hospital_id` as their parent tenant.<br>&nbsp;&nbsp;- Strictly adheres to database status constraints and ENUMs (e.g. appointments: `scheduled`, `confirmed`, `completed`; care tasks: `open`, `in_progress`, `completed`; claims: `pre_auth`, `submitted`, `adjudicated`; adherence: `taken`, `missed`, `skipped`).<br>&nbsp;&nbsp;- Synthetic users, doctors, and patients are properly cross-linked across the clinical event lifecycle.<br>• Tables referencing `auth.users` (`profiles`, `doctors`) provision test identities safely via Supabase Auth Admin API (`supabase.auth.admin.createUser`) using synthetic emails (`syn.doctor@example.com`, etc.) without bypassing or weakening RLS. |
| **3. Targets to Verify vs. Confirmed Facts** | • The stated counts (17 tables, 17,727 CSCM research files, 128 regression tests) are explicitly designated as **targets to verify dynamically at runtime**, not hardcoded facts.<br>• Dynamic inspection scripts will discover and record actual numbers in the final implementation report. |
| **4. Honest Reporting & Decoupling Release from Blockers** | • Every acceptance criterion (AC-14.1 through AC-14.14) must be reported individually in the final report as `PASS`, `FAIL`, `BLOCKED`, or `NOT TESTED`.<br>• If browser automation CLI, database permissions, or external APIs block testing, report the blocker with root-cause analysis; **Phase 14 completion will not be declared while mandatory checks remain blocked or failing.** |
| **5. Demo Role Quick-Select Security** | • Quick-select buttons on `/login` act strictly as client-side credential pre-fillers for evaluation, submitting real synthetic credentials to the backend auth endpoint.<br>• No client privilege escalation; server-side JWT signature verification and role guards (`require_role`) remain 100% active. |
| **6. Real Browser Execution & Evidence Catalog** | • Probes Microsoft Edge CLI (`msedge.exe`) for real browser execution; captures desktop and mobile screenshots; reports `BLOCKED` if unavailable rather than generating mock evidence. |
| **7. CSCM Research Immutability Protocol** | • Automated pre- and post-implementation SHA-256 verification of all research files in `src/`, `models/`, and `data/`.<br>• Immediate stop upon any mismatch without automated file overwriting or restoration. |

---

## 2. Database Seeding & Verifiable PostgreSQL Recovery Architecture

### 2.1 Target Environment Verification
Before any database write operations:
1. **Target Project Confirmation**: The harness will query and display the active database host and project reference from `DATABASE_URL` (masking sensitive credentials) to confirm it is the dedicated test environment (`vmuzexvtbodnkzhfitzf.supabase.co`).
2. **Mandatory Owner Confirmation**: Requires explicit owner confirmation of the target database environment before executing any write script.

### 2.2 Verifiable Schema & Data Snapshot
An automated backup script (`carebridge/backend/supabase/backup_pre_phase14.py`) will be executed prior to any seed operations:
1. Connects via `psycopg2` with `autocommit=False`.
2. Dumps the complete row contents and schema metadata of all public tables into structured JSON backup fixtures:
   `carebridge/backend/supabase/backups/snapshot_YYYYMMDD_HHMMSS/`
3. Captures sequence states, table definitions, foreign-key constraints, and row checksums.
4. Generates a self-contained SQL verification snapshot (`snapshot_data.sql`).

### 2.3 Pre-Reliance Recovery Verification (Isolated PostgreSQL Test Sandbox)
To guarantee that the recovery procedure is fully verifiable and executable before relying on it:
1. **PostgreSQL-Specific Sandbox**: A dedicated recovery verification script (`carebridge/backend/supabase/verify_recovery_postgres.py`) will test restoration against an isolated PostgreSQL schema (e.g. `CREATE SCHEMA recovery_sandbox_temp;` within the test database or a disposable test database).
2. **PostgreSQL Feature Validation**: Validates PostgreSQL-specific types (`UUID`, `JSONB`, `TIMESTAMPTZ`), custom ENUM types, sequences, check constraints, foreign-key cascade behaviors, and transaction boundaries. SQLite is explicitly prohibited for this check.
3. **Parity Check**: Verifies that the restored dataset achieves 100% row-count and column-checksum parity with the captured snapshot.
4. **Clean Teardown**: Drops the sandbox schema cleanly (`DROP SCHEMA recovery_sandbox_temp CASCADE;`) upon verification.

### 2.4 Non-Destructive Emergency Rollback Protocol
To protect pre-existing records and eliminate risk to the database:
1. **No Destructive Drops/Truncates**: The automated rollback procedure **will never** execute `DROP TABLE`, `TRUNCATE`, or blanket deletes on live database tables.
2. **Surgical Rollback**: In the event of a seeding failure, constraint violation, or owner request, the rollback script (`carebridge/backend/supabase/rollback_phase14.py`) executes within a managed `BEGIN ... COMMIT` transaction:
   - Deletes strictly records with identifiable synthetic markers (`SYN-` prefix or deterministic Phase 14 UUIDs `11111111-0001-...`).
   - Asserts that all pre-existing rows (baseline counts verified dynamically) remain 100% intact and unaltered.
   - If any anomaly is detected, executes `ROLLBACK;` and alerts the owner.
3. **Manual Approval for Full Snapshot Restores**: Any full schema-level restore requiring table replacement is classified as a high-risk operation requiring explicit manual authorization from the project owner.

### 2.5 Transactional Seeding Protocol
All seed inserts will be executed via a managed Python script (`seed_15_records.py`) enforcing strict transactional boundaries:
```python
conn = pool.getconn()
conn.autocommit = False
cur = conn.cursor()
try:
    cur.execute("BEGIN;")
    # 1. Verify parent hospitals exist
    # 2. Insert identifiable synthetic records with ON CONFLICT (id) DO NOTHING
    # 3. Verify row counts and foreign keys
    cur.execute("COMMIT;")
except Exception as e:
    cur.execute("ROLLBACK;")
    logger.error(f"Seeding failed, rolled back cleanly: {e}")
    raise
```

---

## 3. Schema-Aware Synthetic Seeding & Multi-Tenant Consistency

### 3.1 Consistent Definition of Targets
- **Mandatory Target**: Every applicable table must contain at least **15 identifiable, specifically tagged synthetic records** (using deterministic UUIDs `11111111-0001-...` through `11111111-0015-...` and naming prefixes `SYN-`).
- **Optional Stretch Targets**: Listed in parentheses below as optional upper bounds for rich demo workflows, **not mandatory minimums**.
- **Existing Rows**: Pre-existing rows from earlier test runs are counted separately and never conflated with newly seeded identifiable synthetic records.

### 3.2 Safe Auth API Integration for `auth.users`
- For tables referencing `auth.users` (specifically `public.profiles`, which cascades to `doctors`), synthetic accounts will be provisioned via the official Supabase Auth Admin API (`supabase.auth.admin.createUser`) using synthetic emails (`syn.doctor@example.com`, `syn.patient@example.com`, etc.).
- This pattern satisfies the hard foreign key `profiles.id REFERENCES auth.users(id)` cleanly and safely without bypassing or weakening Row-Level Security (RLS).
- No mock credentials will use real emails or passwords.

### 3.3 Multi-Tenant Consistency & Status Constraints
To ensure all synthetic data is valid, meaningful, and schema-compliant:
1. **Tenant Boundary Coherence**:
   - All synthetic child entities (`departments`, `doctors`, `patients`, `appointments`, `documents`, `care_tasks`, `prescriptions`, `policies`, `claims`) inherit and strictly share the exact `hospital_id` of their parent hospital tenant.
   - A synthetic patient in `SYN-HOSP-01` is exclusively assigned to doctors, appointments, and prescriptions belonging to `SYN-HOSP-01`.
2. **Schema-Valid Status Constraints**:
   - `appointments`: Allowed statuses strictly conform to `scheduled`, `confirmed`, `in_progress`, `completed`, `cancelled`, `no_show`.
   - `care_tasks`: Allowed statuses strictly conform to `open`, `in_progress`, `completed`, `cancelled`.
   - `clinical_conflicts`: Allowed statuses strictly conform to `detected`, `acknowledged`, `resolved`, `dismissed`.
   - `prescriptions`: Allowed statuses strictly conform to `draft`, `active`, `dispensed`, `cancelled`.
   - `medication_adherence_logs`: Allowed statuses strictly conform to `taken`, `missed`, `skipped`.
   - `insurance_claims`: Allowed statuses strictly conform to `pre_auth`, `submitted`, `approved`, `rejected`, `appealed`.
3. **Clinical Plausibility**:
   - Synthetic documents, lab values, and diagnoses represent realistic clinical scenarios (e.g. hypertension, type 2 diabetes, elevated HbA1c) rather than random characters.

### 3.4 Table Inventory & Identity Strategy (Targets to Verify Dynamically)

*Note: Baseline row counts are targets to verify dynamically upon execution.*

| # | Table Name | Baseline Target to Verify | Mandatory Target (Identifiable Synthetic) | Optional Stretch Target | Key Constraints & Foreign Keys | Identity & Auth Strategy |
|---|---|---|---|---|---|---|
| **1** | `hospitals` | ~2 | **15** | (15) | PK `id` (UUID). Unique `slug`. | Root tenant table. Seed 15 synthetic branches (`SYN-HOSP-01` to `SYN-HOSP-15`). |
| **2** | `departments` | ~4 | **15** | (20) | `hospital_id REFERENCES hospitals(id)` | Seed 15 specialized medical departments across synthetic hospitals. |
| **3** | `profiles` | ~7 | **15** | (25) | `id REFERENCES auth.users(id)` | **Auth Dependency**: Seed 15 synthetic test users in `auth.users` via Supabase Auth Admin API with synthetic emails (`doc.syn1@example.com`, etc.) to satisfy FK without weakening RLS. |
| **4** | `doctors` | ~1 | **15** | (18) | `profile_id REFERENCES profiles(id)` | Links 15 synthetic physician profiles to specialized departments. |
| **5** | `patients` | ~3 | **15** | (25) | Unique `(hospital_id, mrn)` | Seed 15 synthetic patients with unique MRNs (`SYN-MRN-001` to `SYN-MRN-015`). |
| **6** | `patient_accounts` | ~1 | **15** | (20) | `(hospital_id, patient_id)`, `user_id` | Links 15 synthetic patient accounts with primary/caregiver relationship roles. |
| **7** | `appointments` | ~2 | **15** | (30) | `patient_id`, `doctor_id`, `department_id` | 15 synthetic appointments with verified statuses (`scheduled`, `confirmed`, `completed`). |
| **8** | `clinical_documents` | ~5 | **15** | (20) | `patient_id REFERENCES patients(id)` | 15 synthetic lab reports, scans, and discharge summaries. |
| **9** | `extracted_entities` | ~24 | **15** | (60) | `document_id REFERENCES clinical_documents` | 15+ synthetic structured clinical biomarkers and diagnoses. |
| **10** | `clinical_conflicts` | ~0 | **15** | (18) | `patient_id REFERENCES patients(id)` | 15 synthetic clinical conflict records (drug-drug, duplicate therapy). |
| **11** | `clinical_conflict_sources` | ~0 | **15** | (25) | Junction: `conflict_id`, `document_id`, `entity_id` | **Junction Table**: 15 junction links binding conflicts to backing evidence entities. |
| **12** | `care_tasks` | ~46 | **15** | (55) | `patient_id`, `encounter_id` | Verify $\ge 15$ identifiable synthetic care tasks exist. |
| **13** | `prescriptions` | ~64 | **15** | (70) | `patient_id`, `encounter_id` | Verify $\ge 15$ identifiable synthetic tamper-evident e-prescriptions. |
| **14** | `prescription_items` | ~82 | **15** | (90) | `prescription_id REFERENCES prescriptions` | Verify $\ge 15$ identifiable synthetic prescription medication items. |
| **15** | `medication_adherence_logs` | ~9 | **15** | (30) | `prescription_item_id`, `patient_id` | 15 synthetic adherence logs (`taken`, `missed`, `skipped`). |
| **16** | `patient_insurance_policies` | ~1 | **15** | (18) | `patient_id REFERENCES patients(id)` | 15 synthetic health insurance policies with coverage caps and copay terms. |
| **17** | `insurance_claims` | ~7 | **15** | (25) | `policy_id`, `patient_id`, `appointment_id` | 15 synthetic claims across pre-auth, submitted, and adjudicated statuses. |

*Documented Exception*: Audit log events (`logs/audit.jsonl`) are managed as append-only structured JSONL streams rather than a database table to preserve tamper resistance and zero database overhead.

---

## 4. Public Demo Mode & Authentication Security

### 4.1 Demo Role Quick-Select Security
- **Strict Server-Side Authentication**: The demo role quick-select on the login page (`/login`) is strictly a **credential helper for evaluation**. Clicking a demo persona (e.g. "Doctor") pre-fills verified synthetic test credentials and submits them to the backend authentication endpoint (`/api/v1/auth/login` or Supabase Auth).
- **No Client Privilege Escalation**: A role selector can never grant privileges by itself. All permissions are verified on the server via cryptographic JWT signature verification and enforced at the API route level (`require_role(...)`).
- **RLS Continuity**: Supabase Row-Level Security remains active at all times. Unauthenticated visitors can never query protected tables directly.

### 4.2 Public Pages vs. Protected Gating
1. **Public Pages (Unauthenticated)**:
   - Landing page (`/`): High-level overview, live architecture metrics, "Explore Demo", "Sign In".
   - Guided Demo (`/demo`): Read-only interactive showcase with synthetic charts and simulated workflows.
   - Public Prescription Verification (`/verify-prescription/[hash]`): Verifies prescription hash with zero patient PHI.
2. **Protected Actions Interception & Return URL**:
   - Clicking any action requiring authorization (e.g. "Book Appointment", "Issue Prescription", "Upload Document") triggers an interception modal: *"Authentication required to access clinical workflows"*.
   - Routes visitor to `/login?returnUrl=/doctor` (or target route).
   - Post-login: Routes to `returnUrl` if authorized for the user's role; otherwise routes to the default authorized workspace (`/portal`).

---

## 5. Live Browser Execution & Visual QA Protocol

### 5.1 Browser Automation Availability Check
Before attempting visual QA, the test harness will probe browser availability:
1. Probe for Microsoft Edge CLI at `C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`.
2. Probe for alternative headless Chromium/Chrome executables.
3. If headless browser automation is unavailable or fails execution:
   - The harness will explicitly report `BLOCKED` or `NOT TESTED` for visual screenshot capture.
   - **No mock screenshots or fake success claims will be generated.**

### 5.2 Route-by-Route Visual Inspection Checklist
When browser automation is verified, desktop (1280x800) and mobile (375x667) screenshots will be captured into `docs/phase-reports/phase-14-evidence/`:
- [ ] `/`: Public landing page with dual CTAs (Desktop & Mobile).
- [ ] `/demo`: Guided demo tour with synthetic disclaimer badge (Desktop & Mobile).
- [ ] `/login`: Authentication page with demo quick-select pills.
- [ ] `/login` (Error): Invalid credentials error banner.
- [ ] `/portal`: Patient dashboard (Upcoming visits, medical summary).
- [ ] `/portal/book`: 3-step appointment booking wizard.
- [ ] `/portal/caregivers`: Caregiver verification desk.
- [ ] `/portal/documents`: Patient document history.
- [ ] `/receptionist`: Real-time OPD check-in queue.
- [ ] `/receptionist/verify-caregivers`: Caregiver KYC desk.
- [ ] `/doctor`: Doctor workstation with **CSCM-IoMT Monitor Card**.
- [ ] `/doctor/documents/[id]`: Medical document viewer & OCR entities.
- [ ] `/tasks`: Priority care coordination task board.
- [ ] `/admin`: Hospital analytics dashboard (OPD metrics, claim status).
- [ ] `/verify-prescription/[hash]`: Public prescription verification.
- [ ] `/_not-found`: Clean 404 error page.

---

## 6. End-to-End Business Workflow Execution Protocol

Workflows will be executed against verified repository API schemas and supported transitions:
1. **Patient Booking**: Alice Vance schedules Cardiology appointment $\rightarrow$ persisted in `appointments` with status `scheduled`.
2. **Receptionist Check-In**: Receptionist updates appointment status from `scheduled` to `confirmed` (in queue).
3. **Caregiver Access Control**: Proxy caregiver requests dependent access $\rightarrow$ blocked (`403`) until KYC approved by receptionist.
4. **Doctor Document OCR**: Upload lab report PDF $\rightarrow$ magic bytes validated $\rightarrow$ Groq Llama-3.3-70B extracts biomarkers $\rightarrow$ saved to `extracted_entities`.
5. **Clinical Conflict Review**: Conflict engine evaluates entities $\rightarrow$ flags unaddressed high glucose $\rightarrow$ recorded in `clinical_conflicts`.
6. **E-Prescription & Public Verification**: Physician issues prescription $\rightarrow$ SHA-256 hash computed $\rightarrow$ public verification endpoint returns authentic badge without patient PHI.
7. **Care Task Lifecycle**: Biomedical staff claims IoMT alert task $\rightarrow$ records resolution notes $\rightarrow$ transitions to `completed`.
8. **Insurance Pre-Authorization**: Deterministic rule engine calculates coverage and copay $\rightarrow$ persisted in `insurance_claims`.
9. **CSCM-IoMT Telemetry Evaluation**:
   - Baseline stream: Status displays *"No anomaly detected by current model"*.
   - Coordinated FDIA attack simulation: Triggers *"Cross-sensor inconsistency detected (Suspected FDIA)"* ($\text{prob} \ge 0.85$) $\rightarrow$ automated care task generated with 15-minute cooldown.
10. **Conversational AI Guardrails**: Patient asks medical question $\rightarrow$ helpful advice with disclaimer $\rightarrow$ dosage change request receives hard clinical refusal (`"I cannot recommend specific drug dosages..."`).

---

## 7. CSCM Research Immutability & Failure Protocol

- **Pre-Execution Baseline Check**: Dynamically verify all CSCM research assets in `src/`, `models/`, and `data/` against `research_comprehensive_baseline_hashes.json`. The target count (~17,727 files) is verified dynamically at execution time.
- **Strict Failure Protocol**: If **ANY** file hash mismatch or missing file is detected:
  1. Execution **STOPS IMMEDIATELY**.
  2. The exact mismatched file path and hash are reported in the failure log.
  3. **No automatic file overwriting, deletion, or restoration will be performed.**
- **Post-Execution Baseline Check**: Verify 100% hash parity after all packaging and seeding steps.

---

## 8. Clinical Safety Disclaimers & Operational Disclosures

In accordance with medical software ethics:
1. **Academic Demonstration Only**: All clinical workflows (prescriptions, conflict detection, IoMT alerts) operate strictly with synthetic data.
2. **Simulated Findings Labeled**: All simulated IoMT attacks and clinical conflict alerts are clearly labeled as *"Simulated Evaluation Data"*.
3. **Regulatory Disclosure**: The documentation and final report explicitly state that CareBridge AI is an academic capstone software implementation and research prototype, not certified under FDA 510(k), CDSCO, HIPAA Security Rule, or SOC 2 Type II audits.

---

## 9. Measurable Acceptance Criteria & Completion Gate

### 9.1 Individual Status Reporting Rule
Every acceptance criterion will be evaluated and reported with an explicit individual status in `docs/phase-reports/PHASE_14_REPORT.md`:
- `PASS`: Requirement independently executed, verified, and meeting all defined constraints.
- `FAIL`: Execution attempted but failed to meet defined constraints or assertions.
- `BLOCKED`: Pre-condition unmet, environment unavailable (e.g. browser CLI, network rate limit), or external dependency down.
- `NOT TESTED`: Check was not executed during this run.

### 9.2 Acceptance Criteria Matrix

| Criteria ID | Target Requirement | Verification Method | Pass / Completion Rule |
|---|---|---|---|
| **AC-14.1** | **Dynamic Schema Inventory** | Reflection script dynamically inspects `information_schema.tables`, logging actual tables, constraints, and RLS state (target: ~17 tables to verify). | PASS if all tables audited; BLOCKED if DB connection fails. |
| **AC-14.2** | **Schema-Aware 15 Synthetic Records Per Table** | SQL query asserts $\ge 15$ specifically tagged synthetic records exist in every applicable base table, with cross-tenant `hospital_id` coherence and schema-valid enum statuses. | PASS if $\ge 15$ valid synthetic records per table; FAIL if $< 15$ or broken constraints. |
| **AC-14.3** | **Isolated PostgreSQL Recovery & Idempotence** | Snapshot restore verified on isolated PostgreSQL sandbox schema; seed script executed twice asserting 0 duplicate key errors. | PASS if PostgreSQL recovery and idempotence verified; FAIL if errors occur. |
| **AC-14.4** | **Foreign-Key & Tenant Integrity** | Automated script verifies all child records reference valid parent rows within the same `hospital_id`. | PASS if zero orphans; FAIL if broken FKs. |
| **AC-14.5** | **Live Service Startup** | Backend (`/health`) and Frontend (`/`) return HTTP 200 on ports 8000 and 3000. | PASS if HTTP 200; BLOCKED if ports unavailable. |
| **AC-14.6** | **Public Landing Page & Demo Mode** | Headless browser confirms `/` and `/demo` render without login; "Explore Demo" and "Sign In" verified clickable. | PASS if rendered; BLOCKED if browser unavailable. |
| **AC-14.7** | **Protected Feature Gating & Return URL** | Unauthenticated click on protected actions triggers redirect to `/login?returnUrl=...`, returning after auth. | PASS if gated; FAIL if unauthenticated bypass occurs. |
| **AC-14.8** | **Post-Login Role-Based Routing** | Logins for `doctor`, `receptionist`, `patient`, and `admin` route to their respective authorized portals. | PASS if correct routing; FAIL if misrouted. |
| **AC-14.9** | **Visual Screenshot Evidence Catalog** | Headless Edge captures desktop and mobile screenshots across all routes in `docs/phase-reports/phase-14-evidence/`. | PASS if captured; BLOCKED if browser CLI unavailable. |
| **AC-14.10** | **Interactive UI Inspection** | Forms, dialogs, check-in buttons, and OCR triggers tested for responsive layout and error-free network calls. | PASS if interactive; BLOCKED if frontend down. |
| **AC-14.11** | **Backend Authorization & RLS Enforcement** | Pen-test suite confirms unauthenticated calls receive `401` and cross-role calls receive `403 Forbidden`. | PASS if barriers hold; FAIL if IDOR succeeds. |
| **AC-14.12** | **Secrets & PHI Hygiene Scan** | Automated repository scanner traverses all files and asserts zero exposed API keys or real patient PHI. | PASS if zero findings; FAIL if secrets found. |
| **AC-14.13** | **Unified System Regression Suite** | Target to verify: 100% pass across all discovered backend test files (~11 files, ~128 tests) and Next.js build. | PASS if all pass; report exact FAIL or BLOCKED per test. |
| **AC-14.14** | **CSCM Research Immutability** | Dynamic SHA-256 baseline verification confirms all research files (~17,727 files) across `src/`, `models/`, and `data/` remain 100% unmodified; stops on mismatch. | PASS if 100% match; STOP & REPORT if mismatch. |

### 9.3 Release Decoupling & Completion Gate Rule
**Strict Gate**: CareBridge AI Phase 14 will **NOT** be declared complete while any mandatory acceptance criteria are in a `FAIL` or `BLOCKED` state.
- If external factors (e.g. browser driver failure, API rate-limiting, or permission constraints) block testing, the exact blocker, diagnostic context, and mitigation plan will be documented in `docs/phase-reports/PHASE_14_REPORT.md`.
- Release sign-off requires all mandatory criteria to achieve verified `PASS` status.

---

## 10. Stopping for Owner Review & Execution Authorization

This document represents Revision 8 of the Phase 14 proposal incorporating all requested corrections.

In strict adherence to critical governance instructions:
- **No application code, database schemas, migrations, seed data, or environment files have been modified.**
- **No files have been deleted, moved, or renamed.**
- **Research assets remain 100% untouched.**

**Implementation will begin upon your explicit confirmation of this Revision 8 plan.**

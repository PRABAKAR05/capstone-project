# Phase 13 Plan — Revision 2
## Security Hardening, Multi-Portal E2E Journey Validation & Comprehensive System Verification

**Document:** `docs/phase-plans/PHASE_13_PLAN.md`  
**Phase:** 13 — Security Hardening & End-to-End Testing  
**Status:** Completed & Verified  
**Date:** 2026-10-16  

> [!NOTE]
> **PHASE 13 IMPLEMENTED & VERIFIED**  
> Formal owner approval received. All security audits, rate-limiting implementations, multi-portal persona validations, and multi-phase regressions have been executed and verified. See `docs/phase-reports/PHASE_13_REPORT.md` for full test metrics, the vulnerability & risk register, and research asset preservation audit.
> 
> **Strict Research Preservation Mandate:** 100% of 17,727 capstone research assets in `src/`, `models/`, and `data/` verified identical to baseline hashes with zero modifications.

---

## 1. Selected Design Decisions Proposed for Owner Review

| Decision Area | Proposed Option | Recorded Design Specification |
|---|---|---|
| **1. Security Audit & Pen-Test Harness** | **Option A (Comprehensive In-Process Security Suite)** | Automated attack harness validating cryptographic JWT manipulation (`alg="none"`, expired tokens, tampered signatures), horizontal/vertical privilege escalation (IDOR), cross-tenant isolation, and SQL/header injection across 100% of existing API routes. |
| **2. Multi-Portal End-to-End Validation** | **Option A (Full Persona Multi-Hop Journeys)** | Automated synthetic lifecycle journeys spanning all 5 system personas (`patient`, `caregiver`, `receptionist`, `doctor`, `hospital_admin`), validating transactional handoffs across booking, check-in, conflict resolution, e-prescribing, and IoMT telemetry using synthetic accounts in a controlled test environment. |
| **3. Input Validation & Abuse Defense** | **Option A (Audit-First Verification with Documented In-Memory Bounds)** | Audit existing input controls first (magic bytes, path traversal checks, prompt injection shields). For rate-limiting, audit/implement in-process sliding-window throttling with transparent documentation that in-memory limits are process-local and do not sync across distributed worker instances without an external cache like Redis. |

---

## 2. Incorporation of Pre-Approval Safeguards

In response to the preliminary review, the following 7 safeguards are explicitly embedded into the Phase 13 specification:

### 2.1 Research Asset Preservation Baseline (`src/`, `models/`, `data/`)
- Pre-audit SHA-256 baseline hashes will be verified before any testing begins.
- Coverage includes all files in `src/`, `models/`, and `data/` (including processed normalization files, sample `.h5` validation sets, model weights, and pipeline scripts).
- Automated tests will assert that 100% of hashes remain identical after Phase 13 execution.

### 2.2 Audit-First Approach — No Unapproved Out-of-Scope Code Churn
- Existing security controls will be audited and tested first rather than prematurely rewriting middleware:
  - File signature & size validation (`validate_file_signature` in `app.documents.storage`) already enforces 10 MB caps, filename sanitization, and `%PDF` / `\x89PNG` / `\xff\xd8\xff` binary magic-byte checks.
  - Path traversal checks in `read_document_file` already enforce base-directory containment.
  - Conversational safeguards in `app.chat.service` already enforce dosage refusal and emergency escalation.
- Any defect discovered during auditing that requires code changes outside test creation or minor defensive bug fixes must be recorded in the vulnerability register and proposed separately before modifying core services.

### 2.3 Transparent In-Memory Rate-Limiting Limitations
- If an in-memory rate limiter is audited or added for sensitive endpoints (e.g., login, chat, telemetry simulation), its architectural boundary will be explicitly documented:
  - *Limitation Disclosure*: In-memory counters are local to a single Python process/worker. They are not synchronized across multiple ASGI workers (e.g., multi-process Uvicorn/Gunicorn) or distributed container instances behind a load balancer. Production distributed deployment would require an external state store (such as Redis or Memcached).

### 2.4 Protection of Production & Sensitive Data
- Penetration tests and end-to-end user journeys will be executed strictly using synthetic seed accounts, synthetic medical documents, and generated IoMT signals.
- All testing operates against the designated development/test tenant database (`11111111-1111-1111-1111-111111111111` and `22222222-2222-2222-2222-222222222222`). Zero live or identifiable human subject data is touched.

### 2.5 Verification of Existing APIs and Infrastructure Reality
- All test fixtures and assertions must match actual repository components:
  - Verified User Roles: `hospital_admin`, `doctor`, `nurse`, `receptionist`, `lab_technician`, `patient` (from `app.core.security` and `0001_phase2_schema.sql`).
  - Verified API Routers in `main.py`: `/organizations`, `/doctors`, `/patients`, `/caregivers`, `/appointments`, `/agent`, `/documents`, `/conflicts`, `/care-tasks`, `/prescriptions`, `/chat`, `/insurance`, `/analytics`, `/cscm`.
  - Verified Existing Test Files:
    - `test_phase2_security.py`
    - `test_phase3_workflows.py`
    - `test_phase5_agent.py`
    - `test_phase6_documents.py`
    - `test_phase7_conflicts.py`
    - `test_phase8_care_tasks.py`
    - `test_phase9_prescriptions.py`
    - `test_phase10_conversational.py`
    - `test_phase11_insurance_analytics.py`
    - `test_phase12_cscm_integration.py`
    *(Note: Phase 4 is the Next.js frontend UI and has no standalone Python backend test file; its routes are verified via Next.js build and type checking).*

### 2.6 Consistent Unified Regression Definition (Phases 2–13)
- The final regression suite will systematically execute all existing backend test suites **plus Phase 13's new security and E2E suite**:
  `test_phase2_security.py`, `test_phase3_workflows.py`, `test_phase5_agent.py`, `test_phase6_documents.py`, `test_phase7_conflicts.py`, `test_phase8_care_tasks.py`, `test_phase9_prescriptions.py`, `test_phase10_conversational.py`, `test_phase11_insurance_analytics.py`, `test_phase12_cscm_integration.py`, and `test_phase13_security_e2e.py`.

### 2.7 Honest Vulnerability & Production Readiness Reporting
- The final report will record:
  - Severity classification (Critical, High, Medium, Low, Informational).
  - Concrete evidentiary reproduction steps.
  - Remediation status (Remediated, Mitigated, or Unresolved/Deferred).
  - Explicit disclosure of residual operational risks.
- **Passing tests alone will not be claimed as proof of production readiness.** The report will clearly separate test results from real-world clinical deployment prerequisites (such as SOC 2 / HIPAA compliance audits, distributed rate limiting, and hardware medical device certification).

---

## 3. Scope and Planned Capabilities

### 3.1 Security Audit & Access Control Verification
- **Cryptographic JWT Validation**:
  - Test prohibited algorithms (`alg: none`, `HS384` where `HS256` expected, invalid public keys).
  - Test token signature tampering, expired lifetimes (`exp`), and incorrect audience (`aud="authenticated"`).
- **Role Permissions & Privilege Escalation**:
  - Horizontal Privilege Escalation: Patient A attempting to access Patient B's appointments, documents, or prescriptions (`403/404`).
  - Vertical Privilege Escalation: Non-physician roles (`patient`, `receptionist`) attempting to sign consultation notes, issue e-prescriptions, adjudicate claims, or stream IoMT telemetry (`403 Forbidden`).
- **Multi-Tenant Row-Level Security (RLS)**:
  - Verify that Hospital 1 callers are blocked from reading or mutating Hospital 2 data across all tables.
- **Insecure Direct Object Reference (IDOR)**:
  - Systematic probing of all UUID-parameterized endpoints with foreign tenant resource IDs.

### 3.2 Secrets, Privacy & Secure Error Handling
- **Repository Secrets Hygiene**:
  - Regex scan across repository commits and files for hardcoded API keys (`GROQ_API_KEY`, Supabase service role keys, DB passwords).
  - Verify `.env` is gitignored and only `.env.example` is committed.
- **Zero-PHI Audit Trail Audit**:
  - Inspect `logs/audit.jsonl` output across all workflows to confirm zero patient names, medical histories, diagnoses, or raw vitals appear in log entries.
- **RFC 7807 Error Response Sanitization**:
  - Verify that server error responses return standard RFC 7807 problem details without leaking Python tracebacks, database schema names, or raw SQL queries.

### 3.3 Input Security, File Uploads & AI Safety
- **Document Upload Validation Audit**:
  - Verify existing `validate_file_signature` in `app.documents.storage` correctly rejects empty files, oversized files (>10 MB), invalid file extensions, and corrupted magic bytes.
  - Verify path traversal rejection in `read_document_file`.
- **Conversational Assistant & Prompt Injection Defense**:
  - Adversarial jailbreak testing: prompt injection, system prompt extraction, role usurpation.
  - Verify strict refusal of dosage calculations and medication modifications.
  - Verify emergency escalation triggering on acute symptom keywords.
- **API Throttling & Rate Limiting**:
  - Audit existing request volume handling and document in-memory process-local limitations.

### 3.4 Multi-Portal End-to-End Persona Journey Testing
Execute synthetic programmatic multi-hop workflows:
1. **Patient Journey**: Registration -> OPD booking -> Caregiver delegation -> Document upload -> Chat inquiry -> E-prescription view -> Insurance estimate.
2. **Caregiver Journey**: Delegation invite acceptance -> Linked patient appointment & prescription view.
3. **Receptionist Journey**: Daily appointment roster -> Patient check-in -> Caregiver credential verification.
4. **Doctor Workstation Journey**: Roster inspection -> Consultation launch -> Document review -> Conflict reconciliation -> Consultation sign-off -> E-prescription signing -> Bedside IoMT telemetry monitoring.
5. **Hospital Administrator Journey**: Operational KPI analytics (OPD volume, doctor utilization) -> Audit trail inspection -> Doctor roster management.

---

## 4. Acceptance Criteria (AC-13.1 to AC-13.14)

- **AC-13.1 (Cryptographic JWT Validation)**: Rejects tokens with `alg="none"`, tampered signatures, or expired lifetimes with `401 Unauthorized`.
- **AC-13.2 (Horizontal Privilege Barrier)**: Patients cannot view, modify, or delete another patient's medical records, documents, or prescriptions (`403/404`).
- **AC-13.3 (Vertical Privilege Barrier)**: Non-physician roles (`patient`, `receptionist`) cannot sign consultation notes, issue e-prescriptions, adjudicate claims, or query IoMT telemetry feeds (`403 Forbidden`).
- **AC-13.4 (Multi-Tenant Isolation Integrity)**: Hospital 1 callers are completely isolated from Hospital 2 resources across all endpoints and database tables.
- **AC-13.5 (Zero-PHI Audit Trail)**: Audit logs contain exclusively pseudonymized target IDs, actor roles, timestamps, and resource actions; zero patient names or clinical diagnoses.
- **AC-13.6 (Sanitized RFC 7807 Errors)**: Backend exceptions return structured RFC 7807 problem details with zero Python tracebacks or database schema details.
- **AC-13.7 (Secrets Hygiene)**: Automated scanning confirms zero committed credentials or API keys in git history or repository source code.
- **AC-13.8 (File Upload Validation & Path Traversal Defense)**: Document upload endpoint rejects executable files, mismatched MIME types, oversized files (>10 MB), and path traversal payloads.
- **AC-13.9 (Prompt Injection & Medical Safety Defense)**: Conversational assistant refuses jailbreak prompts, declines dosage alteration requests, and triggers emergency escalation on critical symptom inputs.
- **AC-13.10 (Rate-Limiting Behavior & Boundary Documentation)**: Sensitive endpoints handle burst traffic gracefully, and in-memory process-local limitations are documented transparently.
- **AC-13.11 (Full Multi-Portal E2E Persona Journeys)**: Automated test simulates complete journeys across Patient, Caregiver, Receptionist, Doctor, and Admin roles without workflow breakage.
- **AC-13.12 (Unified Regression Pass Across Phases 2–13)**: 100% test pass rate across all test suites (`test_phase2` through `test_phase13`).
- **AC-13.13 (CSCM-IoMT Research Preservation)**: Exact SHA-256 hashes of all files in `models/`, `data/`, and `src/` verified 100% identical.
- **AC-13.14 (Vulnerability & Risk Register)**: Comprehensive documentation of all audit findings, applied mitigations, and honest disclosure of residual operational risks without unwarranted production readiness claims.

---

## 5. Phased Execution Roadmap (After Formal Owner Approval)

1. **Stage 13.1 — Pre-Audit SHA-256 Research Baseline**:
   - Re-verify SHA-256 baseline hashes across `models/`, `data/`, and `src/` before running any test harness.
2. **Stage 13.2 — Secrets Hygiene & Static Security Audit**:
   - Scan codebase for exposed API keys and verify environment configuration separation.
3. **Stage 13.3 — Security Control Audit & Defensive Verification**:
   - Audit existing file upload validation (`validate_file_signature`), storage path containment, error sanitization, and in-memory rate-limiting behavior.
4. **Stage 13.4 — Multi-Portal End-to-End Test Harness**:
   - Create synthetic multi-hop persona journey tests in `carebridge/backend/tests/test_phase13_security_e2e.py`.
5. **Stage 13.5 — Adversarial Pen-Testing & Abuse Verification**:
   - Execute token tampering, privilege escalation, cross-tenant penetration, and prompt-injection attack test cases.
6. **Stage 13.6 — Full Unified Regression Run (Phases 2–13)**:
   - Run complete backend test suite across all 11 test files and record empirical execution timings.
7. **Stage 13.7 — Frontend Build & Route Verification**:
   - Execute `npm run build` to verify zero TypeScript errors across all 16 frontend routes.
8. **Stage 13.8 — Phase 13 Report & Vulnerability Register**:
   - Author `docs/phase-reports/PHASE_13_REPORT.md` documenting verified findings, resolved defects, and residual risk disclosures for owner review.

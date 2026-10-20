# Phase 10 Plan — Revision 2
## Conversational AI & Optional Voice Assistant

**Document:** `docs/phase-plans/PHASE_10_PLAN.md`  
**Phase:** 10 — Conversational AI & Optional Voice Assistant  
**Status:** Revision 2 — Owner Design Choices Recorded; Pending Formal Approval  
**Date:** 2026-10-15  

> [!IMPORTANT]
> **PROPOSAL ONLY — NO IMPLEMENTATION AUTHORIZED**  
> In accordance with project governance, this document is a formal specification recording owner design choices. No database migrations, backend endpoints, conversational agent handlers, speech models, or frontend chat widgets will be written until the owner explicitly authorizes Phase 10 implementation. CSCM-IoMT research assets remain strictly protected.

---

## 1. Executive Summary

Phase 10 introduces a safe, hospital-aware **Conversational Assistant** to CareBridge AI at **₹0 operational cost**. The system enables patients, caregivers, and clinical staff to navigate existing hospital workflows through intuitive natural language interaction.

The conversational assistant is architected not as an autonomous clinical entity, but as an **operational co-pilot and navigation layer** that reuses existing authenticated Phase 3–9 APIs and database constraints. The system starts with text chat; speech-to-text and voice capabilities are evaluated only after the text experience satisfies all safety, grounding, and security benchmarks.

---

## 2. Owner Decisions Recorded

| Decision | Approved Design Choice | Specification Details |
|---|---|---|
| **Decision 1: Execution & Tool Orchestration** | **Option A: Server-Side Tool Calling with Re-Verification** | The assistant runs server-side on FastAPI using Groq function calling with synthetic test data. Every tool call strictly re-evaluates the user's JWT, role, patient link in `patient_accounts`, and hospital tenant isolation before executing service functions. Consequential operations (booking, cancellation) require explicit client confirmation. |
| **Decision 2: Voice Strategy & Evaluation** | **Option A: Browser-Native Web Speech API with Synthetic Benchmark** | Reuses zero-cost browser-native SpeechRecognition and SpeechSynthesis APIs for voice interaction, accompanied by an offline benchmark evaluating transcription accuracy, noise resilience, latency, and mixed Tamil-English phrasing using synthetic audio test scripts. |
| **Decision 3: Safety Guardrails & Emergency Escalation** | **Option A: Deterministic Rule-Based Interceptor + Prompt Boundary** | Hardcoded regex/keyword safety filter intercepts acute emergency symptoms immediately with Indian helpline guidance (`112`, `108`, `102`) prior to model invocation without LLM latency; ambiguous medication queries strictly refuse to guess dosages and route to qualified clinical staff. |

---

## 3. Scope and Planned Capabilities

| Component | Planned Capability | Security & Authorization Boundary |
|---|---|---|
| **Patient Chat** | Answers common hospital operational questions, department hours, insurance desk locations, and explains next steps in clear, empathetic language. | Accessible to `patient` and `caregiver` roles. Excludes internal clinical notes and staff administrative logs. |
| **Appointment Assistant** | Assists in discovering doctors by specialty, checking real-time slot availability, and booking or canceling appointments. | Reuses authorized Phase 3 endpoints. Strict confirmation step required before executing cancellations or bookings. |
| **Document Assistant** | Explains document processing status (`pending`, `completed`, `failed`) and summarizes verified extracted entities with explicit page/source citations. | Patient only views verified documents linked to their own account. Never exposes unverified or rejected entities without disclaimer. |
| **Care Coordination** | Surfacing patient-actionable care plan tasks, discharge follow-ups, and pending instructions permitted by user role. | Excludes internal hospital-staff task notes (Phase 8 data masking preserved). |
| **Prescription Assistant** | Explains status of existing digital prescriptions (`prescribed`, `ready_for_pickup`, `dispensed`), directions, and adherence schedule. | **NEVER prescribes, alters dosage, or discontinues medication.** Refers clinical concerns directly to treating doctor. |
| **Staff Assistant** | Helps doctors, nurses, and receptionists find unclaimed tasks, look up hospital operational metrics, and review schedule overviews. | Strictly restricted to hospital staff roles (`doctor`, `nurse`, `receptionist`, `hospital_admin`). Tenant isolated. |
| **Optional Voice** | Browser-native voice input/output evaluated on latency, accent tolerance, and medical term recognition. | Evaluated only after text chat passes all security checks. |
| **Evaluation Dashboard** | Measures answer grounding, tool-call accuracy, refusal behavior, and regression stability. | Automated test suite and metrics reporter. |

---

## 4. Implementation Stages

1. **Stage 10.1 — Read-Only Audit and Interface Alignment**:
   - Inspect existing Phase 3–9 APIs (`/appointments`, `/doctors`, `/documents`, `/conflicts`, `/care-tasks`, `/prescriptions`).
   - Catalog exact parameter schemas, role permissions, and tenant filters to ensure conversational tools mirror backend signatures 1:1.
2. **Stage 10.2 — Conversation Backend Architecture**:
   - Design conversation request/response schemas, session tracking, input token limits, timeout budgets, and structured response models.
   - Secure all Groq API calls server-side; zero API keys or service credentials in browser code.
3. **Stage 10.3 — Secure Tool Registry & Tenancy Enforcement**:
   - Implement tool wrappers for doctor discovery, slot lookup, appointment operations, document queries, and prescription status.
   - Every tool call re-checks `context.user_id`, `context.role`, `context.hospital_id`, and `public.patient_accounts` linkage.
4. **Stage 10.4 — Grounding Engine & Safety Escalation**:
   - Ground responses in authoritative database records and verified hospital documentation.
   - Detect emergency medical keywords and immediately surface Indian emergency response numbers (`112`, `108`, `102`).
   - For ambiguous clinical or medication queries, explicitly state lack of authority and direct user to clinic desk or emergency services.
5. **Stage 10.5 — Responsive Frontend Chat Experience**:
   - Build a responsive chat interface (`carebridge/frontend/components/chat/conversational-drawer.tsx` or widget).
   - Support conversation history, loading indicators, source reference badges, and explicit confirmation dialogs for write actions.
6. **Stage 10.6 — Optional Voice Prototype & Evaluation**:
   - Integrate Web Speech API with fallback controls.
   - Benchmark synthetic medical speech scripts for transcription accuracy, noise resilience, and mixed Tamil-English phrasing.
7. **Stage 10.7 — Automated Evaluation & Regression Suite**:
   - Comprehensive test suite in `carebridge/backend/tests/test_phase10_conversational.py` verifying tool authorization, prompt-injection defense, cross-tenant isolation, emergency escalation, and zero-PHI audit logging.
   - Regression validation across Phase 6 (documents), Phase 7 (conflicts), Phase 8 (care tasks), and Phase 9 (prescriptions).
8. **Stage 10.8 — Implementation Report & Governance Stop**:
   - Document all verification results, known limitations, and CSCM preservation checks in `docs/phase-reports/PHASE_10_REPORT.md` and stop for owner review.

---

## 5. Safety, Privacy & Security Architecture

### 5.1 Clinical Non-Maleficence Invariants
- **No Autonomous Clinical Decisions**: The assistant is strictly prohibited from formulating medical diagnoses, prescribing drugs, adjusting dosages, or discontinuing medications.
- **Strict Grounding**: The assistant must not guess, extrapolate, or hallucinate clinical information. If data is absent or pending clinician verification, it must explicitly state that the record is unverified or unavailable.
- **Emergency Escalation Protocol**: Inputs mentioning severe acute symptoms (e.g., acute chest pain, severe dyspnea, sudden paralysis, heavy uncontrolled bleeding) trigger an immediate, high-priority emergency banner directing the user to call `112` / `108` or proceed to the nearest emergency department.

### 5.2 Privacy & Prompt-Injection Defenses
- **Zero Real PHI to External Models**: Groq integration is tested strictly using synthetic clinical records and test fixtures.
- **Untrusted Input Sanitization**: User messages and document text are treated strictly as untrusted data inputs, never as executable instructions or tool-routing directives.
- **Zero-PHI Audit Trail**: Conversation events (`CHAT_SESSION_STARTED`, `TOOL_EXECUTED`, `EMERGENCY_ESCALATION_TRIGGERED`) are logged to `audit.jsonl` with pseudonymous user IDs, event codes, and timestamps; zero message bodies or patient names in logs.

### 5.3 CSCM-IoMT Research Preservation Invariants
- **Preserved Title**: *Coordinated Multi-Channel False Data Injection Attack Detection Using Physiology-Aware Cross-Sensor Consistency Modeling in IoMT*.
- **Strict Isolation**: No modifications, deletions, or retraining across `src/`, `models/`, `data/`, or research scripts.

---

## 6. Acceptance Criteria (AC-10.1 to AC-10.12)

| Criteria ID | Requirement | Verification Method |
|---|---|---|
| **AC-10.1** | **Authenticated Chat & Role Scoping** | Validates JWT; routes capabilities strictly matching user's authenticated role. |
| **AC-10.2** | **Grounded Operational Responses** | Answers reflect verified hospital data without fabricating doctors, slots, or records. |
| **AC-10.3** | **Tool Execution Authorization Barrier** | Tool execution validates backend permissions; cross-tenant calls return HTTP 404/403. |
| **AC-10.4** | **Safe Action Confirmations** | Consequential actions (booking, cancellation) require explicit client confirmation. |
| **AC-10.5** | **Staff-Note Data Masking** | Internal clinical observations and staff-only tasks are never disclosed to patients. |
| **AC-10.6** | **Zero Clinical Guesswork** | Ambiguous prescription or dosage questions refuse to speculate and route to physician. |
| **AC-10.7** | **Prompt-Injection & Tenancy Resilience** | Adversarial injection attempts fail to alter system instructions or access other hospitals. |
| **AC-10.8** | **Zero-PHI Audit Logging** | Application logs in `audit.jsonl` record only event codes and pseudonyms; zero message text. |
| **AC-10.9** | **Full Regression Stability** | Regression suites for Phases 6, 7, 8, and 9 pass with 100% success rate. |
| **AC-10.10** | **Voice Modality Governance** | Voice remains optional and gated behind empirical benchmark criteria. |
| **AC-10.11** | **CSCM Research Preservation** | Zero modifications to CSCM-IoMT codebase, checkpoints, datasets, or evaluation scripts. |
| **AC-10.12** | **Implementation Reporting** | Delivers complete `docs/phase-reports/PHASE_10_REPORT.md` documenting verified metrics. |

---

## 7. Cost & Technology Stack

- **Cost Target**: **₹0 operational cost** using open-source tools, browser-native Web Speech API, and free-tier Groq API.
- **Backend**: FastAPI, Python 3.13, Pydantic, existing PostgreSQL database pool.
- **Frontend**: Next.js 16 (Turbopack), React 19, TypeScript, Tailwind CSS, Lucide Icons.
- **Security**: PostgreSQL Row-Level Security, JWT authentication, Zero-PHI structured logging.

---

## 8. Governance and Approval Gate

**Current State: REVISION 2 RECORDED — AWAITING FORMAL IMPLEMENTATION APPROVAL.**

All owner design choices have been formally recorded into Section 2 of this plan:
1. **Decision 1 (Execution & Tool Orchestration)**: **Option A** — Server-Side Tool Calling with Re-Verification
2. **Decision 2 (Voice Strategy & Evaluation)**: **Option A** — Browser-Native Web Speech API with Synthetic Benchmark
3. **Decision 3 (Safety Guardrails & Emergency Escalation)**: **Option A** — Deterministic Rule-Based Interceptor + Prompt Boundary

In accordance with CareBridge AI governance:
- **No implementation code, endpoints, or UI will be written** until formal owner authorization is received (e.g., `"Approve Phase 10"`).
- **CSCM-IoMT Research Assets** remain 100% protected and isolated in `src/`, `models/`, and `data/`.


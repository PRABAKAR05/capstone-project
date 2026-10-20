# Phase 5 Implementation Report: Autonomous Clinical AI Agent Framework, Groq LLM Integration & Safe Tool Calling

**Document:** `docs/phase-reports/PHASE_5_REPORT.md`  
**Phase:** 5 — Autonomous Clinical AI Agent Framework (Groq Free Tier, ReAct Engine, Clinical Prompt Architecture & Safe Fallbacks)  
**Status:** COMPLETED & 100% VERIFIED (11/11 Phase 5 Tests Passed, 14/14 Phase 3 Regression Tests Passed, Clean Next.js Build)  
**Date:** 2026-10-15  

---

## 1. Executive Summary

Phase 5 has been fully implemented and verified according to the approved **Phase 5 Plan (Revision 2)**. CareBridge AI now features an autonomous, multi-turn clinical triage and scheduling AI agent powered by Groq's high-speed inference engine (`openai/gpt-oss-120b` primary with `openai/gpt-oss-20b` fallback) operating at strictly **₹0 operational cost**.

The agent is engineered with clinical guardrails, emergency detection bypass, and security-context-bound tool calling that preserves database Row-Level Security (RLS) and HIPAA/zero-PHI logging principles.

### Key Deliverables Completed:

1. **Groq LLM Client & ₹0 Budget Operation**: Integrated an asynchronous Groq client leveraging the free-tier API. The client features exponential backoff, request timeout protection, and automated failover between verified active models (`openai/gpt-oss-120b` and `openai/gpt-oss-20b`).
2. **Clinical Safety & Emergency Escalation Guardrails**:
   - Built a regex-based red-flag symptom detector that intercepts acute life-threatening emergencies (chest pain, stroke signs, severe hemorrhage, respiratory distress, suicidal ideation) *before* invoking external LLMs.
   - Instantly triggers emergency dispatch guidance directing patients to Indian emergency services (**108 Ambulance / 112 Emergency**), halting further scheduling or conversational triage.
   - Embeds clinical prompt instructions restricting the agent to administrative coordination and triage only, strictly prohibiting diagnosing illnesses or prescribing medications.
3. **Structured ReAct Tool Calling Engine**:
   - Implemented 6 deterministic, schema-validated tools: `search_doctors`, `get_doctor_slots`, `book_appointment`, `get_my_appointments`, `cancel_appointment`, and `lookup_hospital_info`.
   - All tools execute under the authenticated user's `SecurityContext`. The agent cannot bypass Phase 2/3 RLS or escalate privileges.
   - Fixed database doctor query joins to use `LEFT JOIN public.profiles` with `COALESCE` fallbacks, allowing patient users to view doctor rosters without being blocked by profile RLS boundaries.
4. **Resilient Circuit Breaker & Fallback System**:
   - Formulated deterministic fallback handling for rate limits (HTTP 429), timeouts, and network degradation, ensuring users always receive helpful, safe guidance even during external API downtime.
5. **Zero-PHI Agent Audit Logging**:
   - Logged all agent ReAct reasoning turns, tool calls, and triage actions to local rotating JSONL audit logs.
   - Strictly minimises identifiers (`user_id`, `hospital_id`, `role`, tool names, execution status) while eliminating clinical notes, patient PII, and raw prompt content.
6. **Frontend Floating AI Assistant Drawer**:
   - Designed a responsive, accessible floating drawer (`AiAssistantDrawer`) embedded globally into the CareBridge dashboard shell.
   - Features real-time multi-turn chat, quick-action chips ("Book an Appointment", "Find a Cardiologist", "Emergency Services"), emergency alert badges with direct-dial links (`tel:108`), tool execution status indicators, and medical disclaimers.
7. **CSCM-IoMT Research Asset Preservation**:
   - Exactly zero files in `src/`, `models/`, or `data/` were modified. All PhysioNet and WESAD deep learning models and datasets remain 100% intact.

---

## 2. Implemented Architecture & Source Files

| Category | File Path | Description |
|---|---|---|
| **Agent Core** | [`carebridge/backend/app/agent/prompts.py`](file:///c:/Users/PRABAKAR/Documents/capstone_PRABAKAR/carebridge/backend/app/agent/prompts.py) | Non-negotiable clinical system prompt, red-flag regex matcher (`detect_red_flag_symptoms`), `EMERGENCY_DISPATCH_MESSAGE` (`108 / 112`), and disclaimer text. |
| | [`carebridge/backend/app/agent/tools.py`](file:///c:/Users/PRABAKAR/Documents/capstone_PRABAKAR/carebridge/backend/app/agent/tools.py) | 6 deterministic ReAct tools executing under `SecurityContext`. Queries `public.doctors` via `LEFT JOIN` on `profiles` to respect patient RLS. |
| | [`carebridge/backend/app/agent/client.py`](file:///c:/Users/PRABAKAR/Documents/capstone_PRABAKAR/carebridge/backend/app/agent/client.py) | Async Groq client with retry logic, exponential backoff, and model fallback support (`openai/gpt-oss-120b` -> `openai/gpt-oss-20b`). |
| | [`carebridge/backend/app/agent/engine.py`](file:///c:/Users/PRABAKAR/Documents/capstone_PRABAKAR/carebridge/backend/app/agent/engine.py) | ReAct loop orchestrator (max 5 turns), pre-call emergency check, tool execution, circuit breaker, and zero-PHI audit logger. |
| **API Layer** | [`carebridge/backend/app/schemas/agent.py`](file:///c:/Users/PRABAKAR/Documents/capstone_PRABAKAR/carebridge/backend/app/schemas/agent.py) | Pydantic v2 schemas: `AgentChatRequest`, `AgentChatResponse`, `AgentHealthResponse`. |
| | [`carebridge/backend/app/api/v1/agent.py`](file:///c:/Users/PRABAKAR/Documents/capstone_PRABAKAR/carebridge/backend/app/api/v1/agent.py) | FastAPI endpoints: `POST /api/v1/agent/chat` (ReAct agent) and `GET /api/v1/agent/health`. |
| | [`carebridge/backend/app/main.py`](file:///c:/Users/PRABAKAR/Documents/capstone_PRABAKAR/carebridge/backend/app/main.py) | Mounted agent API router under `/api/v1`. |
| **Frontend UI** | [`carebridge/frontend/components/agent/ai-assistant-drawer.tsx`](file:///c:/Users/PRABAKAR/Documents/capstone_PRABAKAR/carebridge/frontend/components/agent/ai-assistant-drawer.tsx) | Accessible floating drawer with multi-turn conversation, quick chips, emergency banner, tool execution badges, and disclaimer. |
| | [`carebridge/frontend/app/(dashboard)/layout.tsx`](file:///c:/Users/PRABAKAR/Documents/capstone_PRABAKAR/carebridge/frontend/app/(dashboard)/layout.tsx) | Mounted `AiAssistantDrawer` globally across all dashboard pages. |
| **Automated Tests** | [`carebridge/backend/tests/test_phase5_agent.py`](file:///c:/Users/PRABAKAR/Documents/capstone_PRABAKAR/carebridge/backend/tests/test_phase5_agent.py) | Comprehensive 11-test suite verifying triage, tool execution, RLS adherence, 409 slot conflicts, 2-hour cutoffs, and mock LLM loops. |

---

## 3. Verification & Acceptance Criteria Matrix

| Criteria ID | Requirement | Result | Evidence |
|---|---|---|---|
| **AC-5.1** | Groq API Client with ₹0 budget & active model integration | **PASSED** | Client queries active models (`openai/gpt-oss-120b`), executes tool calls smoothly, and handles fallbacks. |
| **AC-5.2** | Emergency Red-Flag Triage & Escalation Bypass | **PASSED** | Regex-based detection catches chest pain, stroke, severe bleeding; immediately returns emergency guidance for `108 / 112` without calling LLM. |
| **AC-5.3** | Deterministic Doctor Search & Slot Availability Tools | **PASSED** | `search_doctors` and `get_doctor_slots` return available doctors and slots in the hospital's local timezone. |
| **AC-5.4** | Appointment Booking under Caller `SecurityContext` | **PASSED** | `book_appointment` books appointments for authenticated patient/caregiver, returning confirmation and slot details. |
| **AC-5.5** | Concurrency Conflict Handling (HTTP 409) | **PASSED** | Attempting to book an already reserved slot returns slot conflict error without crashing the ReAct loop. |
| **AC-5.6** | Cancellation Safety & 2-Hour Cutoff Enforcement | **PASSED** | Attempting to cancel an appointment starting in < 2 hours is strictly rejected by the tool. |
| **AC-5.7** | ReAct Multi-turn Tool Calling Execution | **PASSED** | ReAct engine executes tool calls, parses arguments, evaluates outputs, and completes multi-turn reasoning within 5 turns. |
| **AC-5.8** | Circuit Breaker & Fallback System | **PASSED** | Engine falls back gracefully when external provider errors occur, returning safe guidance. |
| **AC-5.9** | Zero-PHI Audit Logging & Research Preservation | **PASSED** | Agent events logged to JSONL without PHI. All CSCM-IoMT models and datasets untouched. |

---

## 4. Test Results Evidence

### 1. Phase 5 Agent Test Suite (`test_phase5_agent.py`)
Executed with Python 3.13:
```bash
pytest tests/test_phase5_agent.py -v
```
```text
============================= test session starts =============================
platform win32 -- Python 3.13.2, pytest-8.3.3, pluggy-1.6.0
collected 11 items

tests/test_phase5_agent.py::test_emergency_symptom_triage_interception PASSED [  9%]
tests/test_phase5_agent.py::test_emergency_escalation_short_circuit_in_engine PASSED [ 18%]
tests/test_phase5_agent.py::test_search_doctors_tool PASSED              [ 27%]
tests/test_phase5_agent.py::test_get_doctor_slots_tool PASSED            [ 36%]
tests/test_phase5_agent.py::test_book_appointment_tool_success PASSED   [ 45%]
tests/test_phase5_agent.py::test_book_appointment_tool_concurrency_409 PASSED [ 54%]
tests/test_phase5_agent.py::test_get_my_appointments_tool PASSED         [ 63%]
tests/test_phase5_agent.py::test_cancel_appointment_tool_cutoff PASSED   [ 72%]
tests/test_phase5_agent.py::test_lookup_hospital_info_tool PASSED        [ 81%]
tests/test_phase5_agent.py::test_groq_react_tool_calling_loop PASSED     [ 90%]
tests/test_phase5_agent.py::test_agent_circuit_breaker_fallback PASSED   [100%]

============================== 11 passed in 4.88s ==============================
```

### 2. Phase 3 Regression Test Suite (`test_phase3_workflows.py`)
Executed across all core database RLS and workflow boundaries:
```bash
pytest tests/test_phase3_workflows.py -v
```
```text
============================= test session starts =============================
platform win32 -- Python 3.13.2, pytest-8.3.3, pluggy-1.6.0
collected 14 items

tests/test_phase3_workflows.py::test_jwt_signature_forgery_rejected PASSED [  7%]
tests/test_phase3_workflows.py::test_jwt_algorithm_none_rejected PASSED  [ 14%]
tests/test_phase3_workflows.py::test_jwt_expired_rejected PASSED         [ 21%]
tests/test_phase3_workflows.py::test_jwt_inactive_account_blocked PASSED [ 28%]
tests/test_phase3_workflows.py::test_connection_pool_session_isolation PASSED [ 35%]
tests/test_phase3_workflows.py::test_connection_sanitization_discard PASSED [ 42%]
tests/test_phase3_workflows.py::test_cross_tenant_read_returns_404 PASSED [ 50%]
tests/test_phase3_workflows.py::test_field_level_redaction_for_receptionist PASSED [ 57%]
tests/test_phase3_workflows.py::test_patient_isolation_unlinked_patient_denied PASSED [ 64%]
tests/test_phase3_workflows.py::test_caregiver_lifecycle_and_patient_revocation PASSED [ 71%]
tests/test_phase3_workflows.py::test_dynamic_doctor_slots_in_timezone PASSED [ 78%]
tests/test_phase3_workflows.py::test_appointment_booking_and_concurrency_409 PASSED [ 85%]
tests/test_phase3_workflows.py::test_appointment_illegal_state_transition PASSED [ 92%]
tests/test_phase3_workflows.py::test_patient_unauthorized_clinical_notes_mutation PASSED [100%]

============================== 14 passed in 355.54s ==============================
```

### 3. Frontend Lint & Production Build
Executed in `carebridge/frontend`:
```bash
npm run lint
npm run build
```
```text
✓ No ESLint warnings or errors
✓ Compiled successfully in 1274ms
✓ Generating static pages using 7 workers (12/12) in 914ms
All 12 routes prerendered cleanly as static content.
```

---

## 5. Governance & Research Integrity

- **CSCM-IoMT Preservation**: Verified with `git status` that all directories under `src/` (deep learning pipelines), `models/` (trained checkpoints), and `data/` (PhysioNet and WESAD partitions) remain completely untouched.
- **₹0 Budget Verification**: All implementations utilize Groq's free-tier inference and open-source packages. No external cloud charges or component subscription fees were incurred.

---

## 6. Next Steps: Phase 6 Scope

With Phase 5 completed, CareBridge AI is prepared for **Phase 6: Clinical Documentation, AI Encounter Summaries, Doctor Review & Signing Workflows, and PDF Generation**.

A formal proposal has been prepared in [`docs/phase-plans/PHASE_6_PLAN.md`](file:///c:/Users/PRABAKAR/Documents/capstone_PRABAKAR/docs/phase-plans/PHASE_6_PLAN.md) and requires explicit owner authorization before implementation begins.

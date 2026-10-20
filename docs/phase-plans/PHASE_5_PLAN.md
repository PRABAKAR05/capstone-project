# Phase 5 Plan: Autonomous Clinical AI Agent Framework, Groq LLM Integration & Safe Tool Calling

**Document:** `docs/phase-plans/PHASE_5_PLAN.md`  
**Phase:** 5 — Autonomous Clinical AI Agent Framework (Groq Free Tier, ReAct Engine, Clinical Prompt Architecture & Safe Fallbacks)  
**Status:** Revision 2 — Owner Design Choices Recorded; Pending Formal Approval  
**Author:** Antigravity Pairing Assistant  
**Date:** 2026-10-15  

---

> [!IMPORTANT]
> **PROPOSAL ONLY — NO IMPLEMENTATION AUTHORIZED**  
> In accordance with project governance, this document is a formal specification submitted for owner review. No backend, frontend, database, or agent implementation code will be written until the owner explicitly authorizes Phase 5. CSCM-IoMT research assets remain strictly protected.

---

## 1. Executive Summary & Objectives

Phase 5 introduces the autonomous AI core of CareBridge AI. The goal is to build an intelligent, multi-turn clinical triage and scheduling agent that operates within strict medical safety guardrails, utilizes structured tool calling to interact with Phase 3 hospital workflows, and incurs **₹0 operational cost** by leveraging **Groq's high-speed free tier** (`llama-3.3-70b-versatile` / `llama-3.1-8b-instant`).

### Core Objectives:
1. **₹0 Budget Clinical LLM Integration**: Implement a resilient client for the Groq Cloud API with automatic rate-limit backoff, request queuing, and model-agnostic abstraction.
2. **Clinical Safety & Emergency Escalation Guardrails**: Embed non-negotiable prompt instructions ensuring the AI operates strictly as an administrative and triage coordinator—never providing independent medical diagnoses or prescribing treatments. Automatically detect life-threatening red-flag symptoms and trigger instant emergency escalation protocols.
3. **Structured ReAct Tool Calling Engine**: Equip the agent with deterministic tools (`search_doctors`, `get_available_slots`, `book_appointment`, `cancel_appointment`, `get_patient_appointments`) that execute under the caller's verified `SecurityContext`. The agent cannot bypass Phase 2/3 RLS or role permissions.
4. **Resilient Circuit Breaker & Fallback System**: Provide deterministic, rule-based fallback responses when Groq rate limits are encountered or network connectivity is degraded.
5. **Zero-PHI Agent Audit Trail**: Log all agent decisions, tool invocations, and escalation events in rotating zero-PHI JSONL audit files without exposing patient PII or clinical notes to external providers unnecessarily.
6. **Preservation of Capstone Research**: Zero modifications to CSCM-IoMT attack detection datasets, neural models, or evaluation scripts.

---

## 2. Technical Architecture

### 2.1 LLM Provider Strategy (₹0 Budget)
- **Primary Model**: `llama-3.3-70b-versatile` on Groq Cloud Free Tier (high reasoning capability for clinical intent understanding and tool selection).
- **Fallback / Low-Latency Model**: `llama-3.1-8b-instant` on Groq Cloud Free Tier (used during high traffic or rate-limiting events).
- **Environment Variable**: `GROQ_API_KEY` (configured server-side in backend environment `.env`, strictly kept out of source control and never exposed to browser).

### 2.2 ReAct Engine & Tool Execution Flow

```
                      +---------------------------------------+
                      |           Authenticated User          |
                      |   (Patient / Caregiver / Reception)   |
                      +-------------------+-------------------+
                                          |
                                          | User Query + JWT
                                          v
                      +-------------------+-------------------+
                      |      FastAPI /api/v1/agent/chat       |
                      |   - Verifies JWT & SecurityContext    |
                      +-------------------+-------------------+
                                          |
                                          v
                      +-------------------+-------------------+
                      |     Clinical Safety Triage Filter     |
                      |  - Scans for Red-Flag Symptoms        |
                      +---------+-------------------+---------+
                                |                   |
                      [Emergency Detected]    [Standard Clinical/Admin Query]
                                |                   |
                                v                   v
                     +----------+-------+   +-------+---------------+
                     | Immediate 108/112|   | Groq ReAct Engine     |
                     | Emergency Notice |   | (Llama-3.3-70b)       |
                     +------------------+   +-------+---------------+
                                                    |
                                            [Requires Tool Call?]
                                                    |
                                         +----------+----------+
                                         | Yes                 | No
                                         v                     v
                               +---------+---------+   +-------+-------+
                               | Authenticated     |   | Final Natural |
                               | Tool Runner       |   | Language      |
                               | (Executes under   |   | Response      |
                               |  user Context)    |   +-------+-------+
                               +---------+---------+           |
                                         |                     |
                                         +----------->---------+
                                                               |
                                                               v
                                                    +----------+-------+
                                                    | Zero-PHI Audit   |
                                                    | Log Entry        |
                                                    +------------------+
```

### 2.3 Agent Tool Registry

Every tool is bound to the active request's `SecurityContext`:
1. `search_doctors(department_name: Optional[str], specialty: Optional[str])`:
   - Returns verified doctor profiles for the caller's hospital tenant.
2. `get_doctor_slots(doctor_id: UUID, slot_date: str)`:
   - Queries available 30-minute slots in the hospital's local timezone (`Asia/Kolkata`).
3. `book_appointment_slot(patient_id: UUID, doctor_id: UUID, scheduled_at: str, reason: str)`:
   - Enforces patient/caregiver identity validation. Fails with HTTP 409 if double-booked.
4. `get_my_appointments()`:
   - Lists appointments belonging strictly to the authenticated patient or verified caregiver ward.
5. `cancel_my_appointment(appointment_id: UUID, reason: str)`:
   - Enforces the 2-hour cutoff rule.

### 2.4 Clinical Safety & Red-Flag Detection

The system prompt and triage filter enforce strict clinical boundaries:
- **Red-Flag Keywords**: Chest pain, crushing pressure, sudden numbness or facial drooping, severe shortness of breath, anaphylaxis (throat swelling), uncontrolled hemorrhage, active suicidal ideation.
- **Action**: Bypasses general chat, returns an immediate high-priority emergency banner with local emergency services guidance (`108 / 112` for India, and `911` only in international contexts), advising immediate emergency room presentation.
- **Conservative Assessment Caveat**: Emergency keyword matching alone cannot definitively rule out an emergency. The system is intentionally conservative and clearly states it cannot provide definitive clinical diagnosis.
- **Disclaimer Invariant**: Every conversational turn concludes with the non-intrusive standard disclaimer:  
  *“CareBridge AI provides operational assistance and clinical triage navigation. For medical emergencies, contact emergency services immediately.”*

---

## 3. Proposed Implementation Scope

### Step 1: Core AI Architecture (`carebridge/backend/app/agent/`)
- `client.py`: Async Groq API client with exponential backoff, rate-limit retry (`tenacity`), and token accounting.
- `prompts.py`: Clinical system prompt templates, safety rules, red-flag taxonomies, and output format schemas.
- `tools.py`: Tool definitions with Pydantic argument schemas and backend workflow mappings.
- `engine.py`: ReAct loop executing tool calls iteratively up to a configurable maximum (default: 5 turns) with error handling.

### Step 2: Agent API Endpoints (`carebridge/backend/app/api/v1/agent.py`)
- `POST /api/v1/agent/chat`: Authenticated standard JSON multi-turn conversation endpoint (SSE streaming deferred to future phase).
- `GET /api/v1/agent/health`: Health probe reporting Groq API connectivity and rate-limit latency.

### Step 3: Frontend AI Assistant Interface
- Floating clinical assistant drawer accessible across all portals.
- Quick action pills: *"Book appointment with Cardiology"*, *"Check my upcoming visits"*, *"Cancel tomorrow's appointment"*.
- Emergency banner styling for red-flag triage detections.

### Step 4: Automated Test Suite (`tests/test_phase5_agent.py`)
- Test red-flag symptom detection and emergency dispatch response.
- Test structured tool calling with mocked Groq responses before depending on live API.
- Test permission boundary: patient cannot use agent to view another patient's records.
- Test 409 double-booking handling within the agent loop.
- Test Groq API failure and graceful rule-based fallback.

---

## 4. Acceptance Criteria

| ID | Criterion | Target Requirement |
|---|---|---|
| **AC-5.1** | **₹0 Budget Compliance** | Strictly uses Groq Cloud Free Tier (`llama-3.3-70b-versatile` / `llama-3.1-8b-instant`); zero paid subscriptions. |
| **AC-5.2** | **Red-Flag Emergency Escalation** | Queries indicating emergent symptoms trigger instant emergency guidance (`108 / 112`); agent refuses to delay patient for booking. |
| **AC-5.3** | **Bounded Scope & No Medical Advice** | Agent clearly disclaims diagnostic authority and redirects clinical symptom inquiries to scheduling a doctor consultation. |
| **AC-5.4** | **Authenticated Tool Execution** | All tool calls pass caller's `SecurityContext`; unauthorized operations return clean error messages without system crashes. |
| **AC-5.5** | **Double-Booking & Conflict Handling** | Agent gracefully handles 409 slot conflicts by offering alternative slots on the same day. |
| **AC-5.6** | **2-Hour Cancellation Rule** | Agent enforces 2-hour cutoff when attempting appointment cancellation via conversation. |
| **AC-5.7** | **Zero-PHI Audit Trail** | Agent conversations and tool invocations logged with pseudonymized patient identifiers and zero PHI. |
| **AC-5.8** | **Circuit Breaker / Fallback** | When Groq API is unreachable or rate-limited, agent gracefully degrades to guided rule-based form links. |
| **AC-5.9** | **CSCM Research Preservation** | Zero modifications to CSCM-IoMT models, datasets, or evaluation code in `src/`, `models/`, or `data/`. |

---

## 5. Owner Decisions Recorded — Revision 2

The owner has confirmed the following design choices. These choices update the proposal only and do not authorize implementation:

1. **Groq API Key Provisioning**: The owner will configure `GROQ_API_KEY` server-side in the backend environment. The key will strictly remain out of source control and will never be exposed to the browser.
2. **Emergency Numbers**: Emergency guidance will prioritize `108 / 112` for the India/Asia-Kolkata deployment context, referencing `911` only in international contexts.
3. **Chat Response Mode**: Standard JSON responses will be used for the initial Phase 5 release. Server-Sent Events (SSE) token streaming is deferred to a subsequent phase.

### Updated Implementation Constraints
- **Test with Mocked LLM First**: Unit and integration test suites will mock Groq responses to guarantee test reliability and prevent burning free-tier rate limits during automated testing.
- **Server-Side API Key Isolation**: All Groq API calls originate strictly from the FastAPI backend; the frontend never interacts directly with Groq.
- **Conservative Emergency Assessment**: Rule-based red-flag detection is paired with explicit system-level prompts, ensuring the assistant never claims to definitively rule out emergencies.
- **₹0 Budget Resilience**: Groq free tier terms and rate limits can vary; the fallback circuit breaker must be robust and deterministic.

---

## 6. Owner Approval Gate

**Current State:** PENDING — NO IMPLEMENTATION AUTHORIZED.

The owner must separately and explicitly approve this Phase 5 Revision 2 proposal before any Phase 5 code, database, backend, frontend, or agent implementation changes are made. Approval of design choices alone is not implementation approval.

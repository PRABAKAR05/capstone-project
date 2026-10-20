# Phase 8 Plan — Revision 2
## Care Coordination Workflows & Multi-Disciplinary Task Engine

**Document:** `docs/phase-plans/PHASE_8_PLAN.md`  
**Phase:** 8 — Care Coordination Workflows & Multi-Disciplinary Task Engine  
**Status:** Revision 2 — Owner Design Choices Recorded; Pending Formal Approval  
**Date:** 2026-10-15  

> [!IMPORTANT]
> **PROPOSAL ONLY — NO IMPLEMENTATION AUTHORIZED**  
> In accordance with project governance, this document is a formal specification submitted for owner review. No database migrations, backend endpoints, frontend components, or automation triggers will be written until the owner explicitly authorizes Phase 8. CSCM-IoMT research assets remain strictly protected.

---

## 1. Executive Summary

In high-volume hospital environments, care coordination breakdowns represent a primary driver of preventable readmissions, treatment delays, and adverse events. Following consultations, discharges, or document conflict detections, clinical teams require a centralized, multi-disciplinary task engine to coordinate follow-ups, post-discharge checks, specialist referrals, and caregiver communications.

In Phase 8, CareBridge AI introduces an enterprise **Care Coordination & Multi-Disciplinary Task Engine** operating at **₹0 operational cost**. The engine connects doctors, nurses, case managers, receptionists, and patients through synchronized, role-based care tasks, automated clinical event triggers, and audit-compliant task resolution lifecycles.

---

## 2. Owner Decisions Recorded

| Decision Area | Approved Design Choice |
|---|---|
| **Task Generation Triggers** | **Hybrid Event-Driven & Manual**: Automatically generate care tasks on key clinical events (e.g., consultation completion requiring follow-up, high-priority document conflict detected in Phase 7), while allowing clinicians and staff to manually create bespoke coordination tasks. |
| **Claiming & Concurrency Model** | **Soft-Lock Claim Model**: Any authorized staff member within the assigned role (e.g., Any Nurse or Any Case Manager) can claim an open pool task. Once claimed, the task is marked as assigned to that individual, while clinical supervisors maintain reassignment authority. |
| **Patient Portal Visibility** | **Patient Action Items Only**: Filter the patient view to show only patient-actionable items (e.g., *"Schedule 2-week post-op ultrasound"*, *"Pick up cardiac medications"*). Internal operational tasks (e.g., *"Review prior authorization with insurance"*, *"Nurse vitals cross-check"*) remain strictly internal to hospital staff. |

---

## 3. Database Schema & Relational Integrity

### 3.1 `public.care_tasks`
Stores multi-disciplinary care tasks, priorities, lifecycle states, and role assignments.

```sql
CREATE TABLE IF NOT EXISTS public.care_tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hospital_id UUID NOT NULL REFERENCES public.hospitals(id) ON DELETE CASCADE,
    patient_id UUID NOT NULL,
    encounter_id UUID REFERENCES public.appointments(id) ON DELETE SET NULL,
    task_type TEXT NOT NULL CHECK (task_type IN (
        'discharge_follow_up',
        'post_op_check',
        'medication_reconciliation',
        'specialist_referral',
        'lab_review',
        'patient_outreach',
        'caregiver_briefing',
        'other'
    )),
    priority TEXT NOT NULL CHECK (priority IN ('urgent', 'high', 'routine', 'low')),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN (
        'pending',
        'claimed',
        'in_progress',
        'completed',
        'cancelled'
    )),
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    patient_instructions TEXT,  -- Patient-friendly actionable phrasing (NULL if internal only)
    assigned_role TEXT NOT NULL CHECK (assigned_role IN ('doctor', 'nurse', 'case_manager', 'receptionist', 'any_staff')),
    assigned_to UUID REFERENCES auth.users(id) ON DELETE SET NULL,
    due_date TIMESTAMPTZ,
    completed_by UUID REFERENCES auth.users(id),
    completed_at TIMESTAMPTZ,
    completion_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT fk_care_tasks_patient FOREIGN KEY (hospital_id, patient_id)
        REFERENCES public.patients(hospital_id, id) ON DELETE RESTRICT,
    CONSTRAINT uq_care_tasks_tenant_id UNIQUE (hospital_id, id)
);

CREATE INDEX IF NOT EXISTS idx_care_tasks_tenant_patient 
    ON public.care_tasks(hospital_id, patient_id);
CREATE INDEX IF NOT EXISTS idx_care_tasks_tenant_status 
    ON public.care_tasks(hospital_id, status);
CREATE INDEX IF NOT EXISTS idx_care_tasks_tenant_role 
    ON public.care_tasks(hospital_id, assigned_role);
CREATE INDEX IF NOT EXISTS idx_care_tasks_tenant_assigned_to 
    ON public.care_tasks(hospital_id, assigned_to);
```

### 3.2 Non-Cascading Retention & Relational Integrity
- **Patient Preservation**: `ON DELETE RESTRICT` ensures task history and clinical care records cannot be accidentally deleted or orphaned.
- **Encounter Association**: `ON DELETE SET NULL` on `encounter_id` preserves longitudinal task records even if a linked appointment record is rescheduled, cancelled, or archived.
- **Audit Retention**: Minimum 90-day retention for completed and cancelled tasks.

### 3.3 Row-Level Security (RLS) Policies
- **SELECT**:
  - Hospital Staff (`is_hospital_staff(hospital_id)`): View all tasks within their hospital tenant.
  - Patients & Caregivers (`has_patient_access(hospital_id, patient_id)`): View only tasks for their linked patient where `patient_instructions IS NOT NULL`. Internal clinical notes (`completion_notes`, `description`) are masked at the API layer.
- **INSERT**: Authenticated hospital staff only.
- **UPDATE**: Authenticated hospital staff only (claiming, completing, reassigning). Patients and caregivers have zero update authority (HTTP 403).

---

## 4. API Specification

| Method | Endpoint | Authorized Roles | Description |
|---|---|---|---|
| `POST` | `/api/v1/care-tasks` | `doctor`, `nurse`, `case_manager`, `receptionist`, `hospital_admin` | Create a new manual care coordination task. |
| `GET` | `/api/v1/care-tasks` | All authenticated roles | Query tasks (filterable by `patient_id`, `status`, `assigned_role`, `assigned_to`, `priority`). Patient callers receive sanitized view. |
| `GET` | `/api/v1/care-tasks/{id}` | All authenticated roles | Get single task detail. Role-based masking applied. |
| `POST` | `/api/v1/care-tasks/{id}/claim` | `doctor`, `nurse`, `case_manager`, `receptionist`, `hospital_admin` | Claim an open task for the authenticated staff user (soft-lock model). |
| `POST` | `/api/v1/care-tasks/{id}/complete` | `doctor`, `nurse`, `case_manager`, `receptionist`, `hospital_admin` | Mark task completed with mandatory resolution notes ($\ge 10$ chars). |
| `POST` | `/api/v1/care-tasks/{id}/cancel` | `doctor`, `hospital_admin` | Cancel a task with documented cancellation rationale. |
| `GET` | `/api/v1/care-tasks/notifications/pending-counts` | `doctor`, `nurse`, `case_manager`, `receptionist`, `hospital_admin` | Returns count of urgent/high priority pending tasks for staff workstation badges. |

---

## 5. Frontend User Interface Components

### 5.1 Hospital Staff: Multi-Disciplinary Task Board
- **Unified Task Queue**: Filterable by "My Tasks", "Team Pool", "Urgent", and "Due Today".
- **One-Click Action Controls**:
  - "Claim Task" for pool tasks matching the user's role.
  - "Mark Complete" modal with mandatory resolution notes.
  - Quick-link to linked patient chart, appointment, or document intelligence viewer.
- **Workstation Attention Badges**: Real-time counter of pending urgent tasks in top navigation and sidebar.

### 5.2 Patient Health Portal: Actionable "Care Plan & Next Steps"
- **Patient Next Steps Card**: Displays clearly worded action items (e.g., *"Schedule follow-up appointment with Dr. Evelyn Reed within 10 days"*).
- **Zero Staff Clutter**: Internal checklists, staff assignment details, and operational notes are hidden.
- **Interactive Checkoff for Patient Tasks**: If a task has a patient action (e.g., booking a visit), completing the action automatically updates or notifies the care team.

---

## 6. Zero-PHI Audit Trail

Audit logs (`audit.jsonl`) will record:
- `event_type`: `TASK_CREATED`, `TASK_CLAIMED`, `TASK_COMPLETED`, `TASK_CANCELLED`.
- `actor_id` & `actor_role`: Pseudonymized ID and staff role.
- `hospital_id`: Tenant identifier.
- `target_resource`: `care_task`.
- `target_id`: Pseudonymized task ID.
- Zero patient medical details, free-text completion notes, or PII written to log streams.

---

## 7. Acceptance Criteria (AC-8.1 to AC-8.12)

| Criteria ID | Requirement | Verification Method |
|---|---|---|
| **AC-8.1** | **Task Creation & Role Routing** | Staff can create tasks routed to specific roles (`nurse`, `case_manager`, `doctor`). |
| **AC-8.2** | **Automated Trigger on Event** | Document conflicts or consultation completions successfully trigger automated follow-up tasks. |
| **AC-8.3** | **Staff Claiming Workflow** | Staff can claim open pool tasks; claimed tasks update `status = 'claimed'` and assign user ID. |
| **AC-8.4** | **Mandatory Resolution Notes** | Completing a task requires meaningful resolution notes ($\ge 10$ characters). |
| **AC-8.5** | **Patient Role Read-Only Restriction** | Patients view only patient-actionable items; attempts to claim or complete return HTTP 403. |
| **AC-8.6** | **Patient Data Masking** | Internal clinical notes and staff descriptions are masked (`None`) in patient API responses. |
| **AC-8.7** | **Non-Cascading Retention** | Deletion of linked encounters retains care tasks with `ON DELETE SET NULL`. |
| **AC-8.8** | **Patient ON DELETE RESTRICT** | Patient records cannot be deleted while active care tasks exist. |
| **AC-8.9** | **Tenant Isolation** | Cross-tenant task queries return HTTP 404 or empty list. |
| **AC-8.10** | **Zero-PHI Audit Logging** | Audit log entries record event codes and pseudonyms; zero patient PII or notes. |
| **AC-8.11** | **Doctor Workstation Pending Badge** | Real-time pending task counter displays correctly in staff header/dashboard. |
| **AC-8.12** | **CSCM Research Preservation** | Zero modifications to CSCM-IoMT models, scripts, or datasets. |

---

## 8. Governance and Approval Gate

**Current State: PENDING — NO IMPLEMENTATION AUTHORIZED.**

The owner's design decisions have been recorded in this Revision 2 specification:
1. **Hybrid Event-Driven & Manual Generation**: Automated task creation on clinical triggers alongside manual authoring.
2. **Soft-Lock Claim Model**: Team pool claiming with supervisor reassignment capability.
3. **Patient Action Items Only**: Selective visibility filtering out internal operational notes.

Before database migrations, backend task routers, or frontend components are implemented, the owner must explicitly approve **Phase 8 Plan Revision 2**.

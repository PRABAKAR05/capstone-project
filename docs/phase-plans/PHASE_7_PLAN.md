# Phase 7 Plan — Revision 2
## Clinical Document Conflict Checker & Multi-Encounter Reconciler

**Document:** `docs/phase-plans/PHASE_7_PLAN.md`  
**Phase:** 7 — Clinical Document Conflict Checker & Multi-Encounter Reconciler  
**Status:** Revision 2 — Owner Design Choices Recorded; Pending Formal Approval  
**Date:** 2026-10-15  

> [!IMPORTANT]
> **PROPOSAL ONLY — NO IMPLEMENTATION AUTHORIZED**  
> This document is a formal specification submitted for owner review. No database migrations, backend conflict analyzers, API endpoints, or frontend views may begin until the owner explicitly approves this revision. CSCM-IoMT research assets remain strictly protected.

---

## 1. Executive Summary

When a patient presents records from multiple healthcare encounters—such as outside hospital discharge summaries, specialist consultation notes, pharmacy slips, and historical lab panels—clinical inconsistencies frequently emerge. These discrepancies include duplicate therapeutic classes, medication-allergy conflicts, conflicting diagnoses, and divergent lab baselines.

In Phase 7, CareBridge AI introduces a secure, deterministic **Clinical Document Conflict Checker & Reconciler** operating at **₹0 operational cost**. The system analyzes verified and pending clinical entities across all patient records to detect potential safety discrepancies, provides an advisory clinician-in-the-loop review workflow, and presents patient-friendly alerts.

---

## 2. Owner Decisions Recorded

| Decision Area | Approved Design Choice |
|---|---|
| **High-Severity Conflicts** | Display an urgent alert modal requiring documented clinician acknowledgement with recorded clinical rationale. **Do not automatically block emergency clinical workflows.** |
| **Detection Approach** | Use deterministic, explainable rules backed by a maintained clinical knowledge dictionary. Allow optional Groq assistance **strictly for synthetic-data testing** until clinical reliability and privacy boundaries are separately reviewed. **Never treat an LLM output as verified clinical advice.** |
| **Patient Visibility** | Show carefully worded, patient-friendly alerts for relevant conflicts (e.g., *"Your doctor is reviewing potential medication interactions"*). Keep detailed pharmacologic reasoning, clinical notes, and resolution controls strictly restricted to authorized clinicians. |

---

## 3. Clinical Safety & Medical Governance Invariants

### 3.1 Advisory Decision Support Only (No Autonomous Order Alterations)
- The conflict checker functions strictly as an **advisory clinical decision support (CDS) tool**.
- It **never** cancels prescriptions, modifies dosages, updates allergy lists, or alters medical records autonomously.
- **No One-Click Discontinue Action**: The system will **not** provide a one-click *"Discontinue Redundant Drug"* button that directly mutates orders. Any prescription change requires a separate, explicit, clinician-controlled workflow through the doctor's standard order interface.

### 3.2 Validated Clinical Knowledge Base
- Drug-drug interactions, duplicate therapeutic classes, and drug-allergy cross-reactivities (e.g., penicillins vs. cephalosporins, multiple ACE inhibitors, NSAIDs + anticoagulants) must be evaluated against a **deterministic, structured clinical knowledge dictionary**.
- The system will **never rely on an LLM alone** to determine drug safety, contraindications, or allergy cross-reactivity.

### 3.3 Temporal, Status & Verification Awareness
- **Medication Status**: Only medications marked as *active* or lacking explicit discontinuation timestamps are flagged as active duplicate therapy candidates. Historical or completed courses (e.g., a 7-day antibiotic course from three months prior) are evaluated strictly for historical allergy/adverse-reaction context, not active duplication.
- **Document Verification Status**: Entities originating from *verified* documents carry higher evidential weight. Conflicts involving *unverified / pending* extractions are explicitly annotated as *provisional findings* awaiting source-document sign-off.
- **Encounter Dates**: Clinical conflicts preserve source encounter dates, allowing clinicians to distinguish outdated outside declarations from recent internal findings.

### 3.4 Review Priority vs. Clinical Risk
- Severities (`high`, `moderate`, `low`) represent **review priorities** for clinician workflow triage, **not a guaranteed assessment of absolute clinical risk**.
- An urgent priority alert flags potential severe harm (e.g., anaphylaxis risk or major bleeding interaction) demanding immediate clinician acknowledgement before discharge.

---

## 4. Database Schema & Relational Integrity

To avoid integrity loss from untyped UUID arrays, Phase 7 uses proper relational link tables and foreign keys with non-cascading preservation rules.

### 4.1 `public.clinical_conflicts`
Stores the high-level clinical conflict alert.

```sql
CREATE TABLE IF NOT EXISTS public.clinical_conflicts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hospital_id UUID NOT NULL REFERENCES public.hospitals(id) ON DELETE CASCADE,
    patient_id UUID NOT NULL REFERENCES public.patients(id) ON DELETE RESTRICT,
    conflict_type TEXT NOT NULL CHECK (conflict_type IN (
        'drug_allergy',
        'duplicate_therapy',
        'drug_drug_interaction',
        'diagnostic_discrepancy',
        'temporal_inconsistency',
        'other'
    )),
    review_priority TEXT NOT NULL CHECK (review_priority IN ('high', 'moderate', 'low')),
    title TEXT NOT NULL,
    clinical_summary TEXT NOT NULL,
    patient_friendly_summary TEXT NOT NULL,
    resolution_status TEXT NOT NULL DEFAULT 'unresolved' CHECK (resolution_status IN (
        'unresolved',
        'acknowledged_with_rationale',
        'resolved_via_order_change'
    )),
    acknowledged_by UUID REFERENCES auth.users(id),
    acknowledged_at TIMESTAMPTZ,
    clinician_rationale TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT uq_clinical_conflicts_tenant_id UNIQUE (hospital_id, id)
);

CREATE INDEX IF NOT EXISTS idx_clinical_conflicts_tenant_patient 
    ON public.clinical_conflicts(hospital_id, patient_id);
CREATE INDEX IF NOT EXISTS idx_clinical_conflicts_tenant_status 
    ON public.clinical_conflicts(hospital_id, resolution_status);
```

### 4.2 `public.clinical_conflict_sources` (Relational Integrity Table)
Links conflicts directly to underlying `clinical_documents` and `extracted_entities` using explicit foreign keys.

```sql
CREATE TABLE IF NOT EXISTS public.clinical_conflict_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hospital_id UUID NOT NULL REFERENCES public.hospitals(id) ON DELETE CASCADE,
    conflict_id UUID NOT NULL REFERENCES public.clinical_conflicts(id) ON DELETE CASCADE,
    document_id UUID REFERENCES public.clinical_documents(id) ON DELETE SET NULL,
    entity_id UUID REFERENCES public.extracted_entities(id) ON DELETE SET NULL,
    role_in_conflict TEXT NOT NULL CHECK (role_in_conflict IN (
        'prescribed_medication',
        'documented_allergy',
        'interacting_medication',
        'conflicting_diagnosis',
        'baseline_evidence'
    )),
    citation_text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT uq_clinical_conflict_sources_tenant UNIQUE (hospital_id, id)
);

CREATE INDEX IF NOT EXISTS idx_conflict_sources_conflict 
    ON public.clinical_conflict_sources(hospital_id, conflict_id);
CREATE INDEX IF NOT EXISTS idx_conflict_sources_entity 
    ON public.clinical_conflict_sources(hospital_id, entity_id);
```

### 4.3 Auditability & Non-Cascading Retention
- Patient records use `ON DELETE RESTRICT` on `clinical_conflicts`. Conflict histories are clinical safety records and must **not** be silently deleted if an associated patient or user record is modified.
- Deleting an individual uploaded document or entity uses `ON DELETE SET NULL` in `clinical_conflict_sources`, preserving the historical conflict record and its textual citation for medical auditability.
- Resolved and acknowledged conflicts are retained for a minimum 90-day active audit period (consistent with project audit standards).

### 4.4 Row-Level Security (RLS) Policies
- **SELECT**:
  - Clinicians: Authorized to view all conflicts within their hospital tenant (`is_hospital_staff(hospital_id)`).
  - Patients & Caregivers: Authorized to view only conflicts for their linked patient (`has_patient_access(hospital_id, patient_id)`). Database queries mask detailed clinical pharmacology notes from patient views.
- **INSERT**: Restricted strictly to server-side scan processes and authenticated hospital staff.
- **UPDATE (Acknowledgement & Resolution)**:
  - Strictly restricted to authenticated doctors and clinical administrators (`is_hospital_staff(hospital_id)` with `doctor` or `hospital_admin` role).
  - Patients and caregivers are **never** permitted to update `resolution_status`, acknowledge conflicts, or alter clinical rationale.

---

## 5. API Specification

| Method | Endpoint | Authorized Roles | Description |
|---|---|---|---|
| `POST` | `/api/v1/conflicts/scan/{patient_id}` | `doctor`, `hospital_admin` | Triggers deterministic conflict scan across verified and pending records for a patient. |
| `GET` | `/api/v1/conflicts` | `doctor`, `hospital_admin`, `patient`, `caregiver` | Lists conflicts for an authorized patient. Patient callers receive sanitized `patient_friendly_summary`. |
| `GET` | `/api/v1/conflicts/{id}` | `doctor`, `hospital_admin`, `patient`, `caregiver` | Retrieves full conflict record with relational source document citations. |
| `POST` | `/api/v1/conflicts/{id}/acknowledge` | `doctor`, `hospital_admin` | Clinician documents clinical rationale and acknowledges conflict without blocking emergency care. |
| `GET` | `/api/v1/conflicts/notifications/counts` | `doctor`, `hospital_admin` | Returns unacknowledged urgent and moderate conflict counts for the doctor workstation queue. |

---

## 6. Frontend User Interface Components

### 6.1 Doctor Workstation: Urgent Alert & Acknowledgement Modal
- **Urgent Notification Banner**: Displayed at the top of the Doctor Workstation when a patient in the clinic queue has unacknowledged high-priority conflicts.
- **Side-by-Side Reconciliation Modal**:
  - Displays the conflicting findings side-by-side with document names, dates, and verification status.
  - Shows maintained clinical cross-reference rule citations (e.g., *"Penicillin cross-sensitivity with Cephalosporins (approx. 2-5%)"*).
  - Prompts the physician for **Documented Clinical Rationale** (mandatory textarea, minimum 10 characters).
  - Action button: *"Acknowledge & Proceed with Documented Rationale"*.
  - Explicit warning text: *"This action acknowledges the advisory alert. Any medication discontinuations or modifications must be ordered through the standard prescription order workflow."*

### 6.2 Patient Portal: Friendly Safety Advisory Pill
- Displayed in the patient's Clinical Records tab (`/portal/documents`) and Health Portal (`/portal`).
- Uses calm, patient-friendly phrasing (e.g., *"Your doctor is currently reviewing potential medication interactions between your past records and recent prescriptions."*).
- Hides clinical pharmacology codes, drug interaction matrices, and clinician rationale fields.
- Provides zero mutation controls to patients.

---

## 7. Zero-PHI Audit Trail

Audit logs will record the minimum necessary information:
- `event_type`: `CONFLICT_SCAN_EXECUTED`, `CONFLICT_ACKNOWLEDGED`, `CONFLICT_RESOLVED_ORDER_CHANGE`.
- `actor_id` & `actor_role`: Pseudonymized ID and role.
- `hospital_id`: Tenant identifier.
- `target_resource`: `clinical_conflict`.
- `target_id`: Pseudonymized conflict ID.
- `resolution_action`: `acknowledged_with_rationale` or `order_change`.
- Zero clinical text, drug names, patient PII, or free-text rationale logged to audit files.

---

## 8. Acceptance Criteria

| Criteria ID | Requirement | Verification Method |
|---|---|---|
| **AC-7.1** | **Deterministic Drug-Allergy Matching** | Detects prescribed medications violating documented allergies using the clinical knowledge dictionary (e.g., Amoxicillin vs. Penicillin). |
| **AC-7.2** | **Duplicate Therapy Class Detection** | Detects concurrent active medications sharing identical therapeutic classes (e.g., dual ACE inhibitors, dual statins). |
| **AC-7.3** | **Review Priority Stratification** | Accurately assigns `high`, `moderate`, and `low` review priorities based on clinical rule severity definitions. |
| **AC-7.4** | **No Autonomous Record Mutation** | Conflict engine never cancels orders or modifies patient records autonomously. |
| **AC-7.5** | **No One-Click Discontinue Action** | Verification verifies UI does not offer direct one-click prescription cancellation. |
| **AC-7.6** | **Documented Clinician Acknowledgement** | Clinicians must supply meaningful clinical rationale to transition status to `acknowledged_with_rationale`. |
| **AC-7.7** | **Emergency Workflow Preservation** | Emergency appointments and encounters can proceed with documented clinician acknowledgement. |
| **AC-7.8** | **Patient Role Read-Only Restriction** | Patients and caregivers can view patient-friendly summaries; attempts to resolve or mutate return HTTP 403. |
| **AC-7.9** | **Relational Source Integrity** | Conflicts reference sources via `public.clinical_conflict_sources` with foreign keys, preventing orphan references. |
| **AC-7.10** | **Non-Cascading Conflict Retention** | Deletion of source documents retains conflict records with `ON DELETE SET NULL` on citations. |
| **AC-7.11** | **Tenant & Patient RLS Isolation** | Cross-tenant conflict queries return HTTP 404. Unlinked patient conflict queries return HTTP 404. |
| **AC-7.12** | **Zero-PHI Audit Logging** | Audit logs contain pseudonymous IDs and action codes; zero medication names or notes recorded. |
| **AC-7.13** | **Synthetic-Only AI Testing Boundary** | Groq assistance is tested exclusively with synthetic clinical data; zero real patient identifiable text processed. |
| **AC-7.14** | **CSCM Research Preservation** | Zero modifications to CSCM-IoMT models, datasets, or evaluation scripts. |

---

## 9. Governance and Approval Gate

**Current State: PENDING — NO IMPLEMENTATION AUTHORIZED.**

The owner has provided explicit design decisions and safety requirements for Phase 7. Those choices are recorded in this Revision 2 specification.

Before any database migrations, conflict analyzers, API endpoints, or frontend views are written, the owner must explicitly approve **Phase 7 Plan Revision 2**.

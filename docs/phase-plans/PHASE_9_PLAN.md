# Phase 9 Plan — Revision 3
## Prescription Intelligence, Digital Generation & Adherence Tracker

**Document:** `docs/phase-plans/PHASE_9_PLAN.md`  
**Phase:** 9 — Prescription Intelligence, Digital Generation & Adherence Tracker  
**Status:** Revision 3 — Safety Architecture & CSCM-IoMT Preservation Integrated; Pending Formal Approval  
**Date:** 2026-10-15  

> [!IMPORTANT]
> **PROPOSAL ONLY — NO IMPLEMENTATION AUTHORIZED**  
> In accordance with project governance, this document is a formal specification recording owner design choices and safety review requirements. No database migrations, backend endpoints, prescription generators, or frontend adherence views will be written until the owner explicitly authorizes Phase 9 implementation. CSCM-IoMT research assets remain strictly protected.

---

## 1. Executive Summary

Medication errors, illegible scrips, unmonitored drug interactions, and poor patient compliance remain significant hazards in outpatient and inpatient care. Phase 9 introduces **Prescription Intelligence** to CareBridge AI at **₹0 operational cost**.

The system enables physicians to author structured, safety-checked e-prescriptions, generates tamper-evident digital prescription records with verifiable QR codes / HMAC signatures, tracks pharmacy dispensing status, and provides an interactive daily medication adherence schedule for patients and caregivers.

---

## 2. Owner Decisions Recorded

| Decision | Approved Design Choice | Specification Details |
|---|---|---|
| **Decision 1: Verification & Tamper-Proofing** | **Option A: Cryptographic HMAC-SHA256 & Verifiable QR Payload** | Each digital prescription generates an HMAC-SHA256 signature using a versioned secret key. QR code and verification URL allow instant offline/online authenticity validation with zero PII exposure. |
| **Decision 2: Patient Adherence Tracking** | **Option A: Interactive Daily Dose Schedule & Adherence Logging** | Automated daily intervals (morning, afternoon, evening, bedtime); interactive "Mark Taken" / "Skip" checkoffs for patients and caregivers; calculates 30-day compliance percentages visible to physicians. |
| **Decision 3: Pharmacy Fulfillment Lifecycle** | **Option A: Full Dispensing Lifecycle** | Full multi-stage lifecycle: `prescribed` -> `ready_for_pickup` -> `dispensed` -> `completed` (or `discontinued`), tracking dispensing staff, timestamps, and batch/lot notes. |

---

## 3. Safety Review & Architecture Specifications

### 3.1 Cryptographic HMAC Key Rotation & Secure Public Verification
- **Secret Key Management & Rotation**:
  - Signs canonical payload using `PRESCRIPTION_SIGNING_SECRET` from environment.
  - The verification hash incorporates a key ID prefix (e.g., `v1:<hex_hmac>`) allowing seamless key rotation without invalidating historic active prescriptions.
  - Canonical payload format:
    ```json
    {
      "prescription_id": "<uuid>",
      "hospital_id": "<uuid>",
      "patient_id": "<uuid>",
      "doctor_id": "<uuid>",
      "issued_at": "<iso8601>",
      "items_hash": "<sha256_of_sorted_items>"
    }
    ```
- **Zero-PII Public Verification Endpoint (`GET /api/v1/prescriptions/verify/{verification_hash}`)**:
  - Designed for public pharmacist QR-scanning and third-party verification without login.
  - **Zero Patient Identifiable Information**: Exposes absolutely NO patient name, gender, age, diagnosis text, or clinical notes.
  - Returns only: verification status (`valid`, `expired`, `tampered`), issuing hospital ID and name, issuing doctor ID/name, issuance timestamp, validity expiration timestamp, prescription status, total item count, and cryptographic items hash for verification.

### 3.2 Dose-Scheduling & Adherence Scoring Engine
- **Deterministic Frequency-to-Interval Mapping**:
  - `'Once daily'` / `'QD'` &rarr; `08:00` (Morning)
  - `'Twice daily'` / `'BID'` &rarr; `08:00`, `20:00` (Morning, Evening)
  - `'Three times daily'` / `'TID'` &rarr; `08:00`, `14:00`, `20:00` (Morning, Afternoon, Evening)
  - `'Four times daily'` / `'QID'` &rarr; `08:00`, `12:00`, `16:00`, `20:00`
  - `'Every 8 hours'` &rarr; `06:00`, `14:00`, `22:00`
  - `'Bedtime'` / `'QHS'` &rarr; `21:00`
  - `'As needed'` / `'PRN'` &rarr; Ad-hoc logging only (excluded from scheduled adherence denominator).
- **Adherence Score Formula**:
  - Evaluation Window: Rolling 30 days prior to $T_{now}$ (or from prescription start date if $< 30$ days).
  - Scheduled Doses $S$: Total doses scheduled strictly $\le T_{now}$. Future doses are strictly excluded from the denominator.
  - Adherent Doses $C$: Doses logged with status `'taken'` or `'late'`.
  - **Adherence Rate (%)**:
    $$\text{Adherence Rate} = \begin{cases} 100.0\%, & \text{if } S = 0 \\ \frac{C}{S} \times 100\%, & \text{if } S > 0 \end{cases}$$
  - **Dose Status Rules**:
    - `'taken'`: Dose recorded within $\pm 2$ hours of scheduled time.
    - `'late'`: Dose recorded $> 2$ hours after scheduled time but on the same calendar day.
    - `'skipped'`: Explicitly marked skipped by patient/caregiver (counts against score as $C=0$).
    - `'missed'`: Scheduled dose unlogged after $> 24$ hours past scheduled time (counts against score as $C=0$).

### 3.3 Pharmacy Role Permissions & Finite State Machine (FSM)
- **Status State Machine**:
  ```mermaid
  stateDiagram-v2
      [*] --> prescribed: Doctor Authors & Signs
      prescribed --> ready_for_pickup: Pharmacist / Staff Prepares
      ready_for_pickup --> dispensed: Pharmacist Dispenses
      dispensed --> completed: Duration Expires / Doctor Signs Off
      prescribed --> discontinued: Doctor Discontinues
      ready_for_pickup --> discontinued: Doctor Discontinues
      dispensed --> [*]
      completed --> [*]
      discontinued --> [*]
  ```
- **Permission Matrix**:
  - `prescribed` &rarr; `ready_for_pickup`: Allowed for `doctor`, `receptionist` (pharmacy tech), `hospital_admin`.
  - `ready_for_pickup` &rarr; `dispensed`: Allowed for `doctor`, `receptionist`, `hospital_admin`. Requires recording `dispensed_by`, `dispensed_at`, and optional `batch_number`/`lot_number`.
  - Any state &rarr; `discontinued`: **Restricted exclusively to `doctor`**. Requires documented clinical rationale ($\ge 10$ characters).
  - Patient / Caregiver: **Strictly READ-ONLY**. Any mutation attempt on prescription headers, items, or status returns `HTTP 403 Forbidden`.

### 3.4 Tenant Isolation & Audit-History Protections
- **Relational Integrity**:
  - `public.prescriptions` references `public.patients(hospital_id, id)` with `ON DELETE RESTRICT`. Patient records cannot be deleted while active or historical prescriptions exist.
  - `public.prescription_items` references `public.prescriptions(hospital_id, id)` with `ON DELETE CASCADE`.
  - `public.medication_adherence_logs` references `public.patients(hospital_id, id)` with `ON DELETE RESTRICT` and `public.prescription_items(hospital_id, id)` with `ON DELETE CASCADE`.
- **Row-Level Security (RLS)**:
  - Strict tenant filtering on `hospital_id = auth.jwt() ->> 'hospital_id'`.
  - Patients can only select their own prescriptions where `patient_id = auth.uid()` or via caregiver link.
- **Zero-PHI Audit Trail**:
  - All prescription actions log structured events to `audit.jsonl` containing only `{event_type, timestamp, hospital_id, prescription_id, user_id}`.
  - Absolutely NO drug names, dosages, clinical notes, or patient names in application log files.

### 3.5 CSCM-IoMT Research Preservation Invariants
- **Preserved Research Title**: *Coordinated Multi-Channel False Data Injection Attack Detection Using Physiology-Aware Cross-Sensor Consistency Modeling in IoMT*.
- **Strict Isolation**: No files in `src/`, `models/`, or `data/` will be modified, moved, deleted, retrained, or replaced.
- **Independence**: The CareBridge AI clinical platform remains completely independent and decoupled from the CSCM research assets.

---

## 4. Database Schema Specification

### 4.1 `public.prescriptions`
```sql
CREATE TABLE IF NOT EXISTS public.prescriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hospital_id UUID NOT NULL REFERENCES public.hospitals(id) ON DELETE CASCADE,
    patient_id UUID NOT NULL,
    doctor_id UUID NOT NULL REFERENCES auth.users(id),
    encounter_id UUID REFERENCES public.appointments(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'prescribed' CHECK (status IN (
        'prescribed',
        'ready_for_pickup',
        'dispensed',
        'completed',
        'discontinued'
    )),
    diagnosis_context TEXT,
    notes TEXT,
    discontinuation_rationale TEXT,
    verification_hash TEXT NOT NULL,  -- Format: "v1:<hex_hmac_sha256>"
    issued_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    valid_until TIMESTAMPTZ NOT NULL,
    dispensed_by UUID REFERENCES auth.users(id),
    dispensed_at TIMESTAMPTZ,
    dispensing_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT fk_prescriptions_patient FOREIGN KEY (hospital_id, patient_id)
        REFERENCES public.patients(hospital_id, id) ON DELETE RESTRICT,
    CONSTRAINT uq_prescriptions_tenant_id UNIQUE (hospital_id, id)
);

CREATE INDEX IF NOT EXISTS idx_prescriptions_tenant_patient 
    ON public.prescriptions(hospital_id, patient_id);
CREATE INDEX IF NOT EXISTS idx_prescriptions_tenant_status 
    ON public.prescriptions(hospital_id, status);
CREATE INDEX IF NOT EXISTS idx_prescriptions_doctor 
    ON public.prescriptions(doctor_id);
CREATE INDEX IF NOT EXISTS idx_prescriptions_verification_hash
    ON public.prescriptions(verification_hash);
```

### 4.2 `public.prescription_items`
```sql
CREATE TABLE IF NOT EXISTS public.prescription_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hospital_id UUID NOT NULL REFERENCES public.hospitals(id) ON DELETE CASCADE,
    prescription_id UUID NOT NULL,
    drug_name TEXT NOT NULL,
    therapeutic_class TEXT,
    dosage TEXT NOT NULL,
    route TEXT NOT NULL DEFAULT 'oral',
    frequency TEXT NOT NULL,        -- e.g., 'Once daily', 'Twice daily', 'Every 8 hours'
    duration_days INTEGER NOT NULL,
    instructions TEXT NOT NULL,     -- e.g., 'Take with food after meals'
    refills_remaining INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT fk_prescription_items_parent FOREIGN KEY (hospital_id, prescription_id)
        REFERENCES public.prescriptions(hospital_id, id) ON DELETE CASCADE,
    CONSTRAINT uq_prescription_items_tenant UNIQUE (hospital_id, id)
);

CREATE INDEX IF NOT EXISTS idx_prescription_items_parent 
    ON public.prescription_items(hospital_id, prescription_id);
```

### 4.3 `public.medication_adherence_logs`
```sql
CREATE TABLE IF NOT EXISTS public.medication_adherence_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    hospital_id UUID NOT NULL REFERENCES public.hospitals(id) ON DELETE CASCADE,
    patient_id UUID NOT NULL,
    prescription_item_id UUID NOT NULL,
    scheduled_time TIMESTAMPTZ NOT NULL,
    taken_at TIMESTAMPTZ,
    status TEXT NOT NULL CHECK (status IN ('taken', 'skipped', 'late', 'missed')),
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT timezone('utc'::text, now()),
    CONSTRAINT fk_adherence_patient FOREIGN KEY (hospital_id, patient_id)
        REFERENCES public.patients(hospital_id, id) ON DELETE RESTRICT,
    CONSTRAINT fk_adherence_item FOREIGN KEY (hospital_id, prescription_item_id)
        REFERENCES public.prescription_items(hospital_id, id) ON DELETE CASCADE,
    CONSTRAINT uq_adherence_tenant UNIQUE (hospital_id, id)
);

CREATE INDEX IF NOT EXISTS idx_adherence_patient_time 
    ON public.medication_adherence_logs(hospital_id, patient_id, scheduled_time);
```

---

## 5. API Specification

| Method | Endpoint | Authorized Roles | Description |
|---|---|---|---|
| `POST` | `/api/v1/prescriptions` | `doctor` | Author structured e-prescription with pre-issuance Phase 7 safety checks. |
| `GET` | `/api/v1/prescriptions` | All authenticated roles | Query prescriptions (patients view own records; doctors view hospital records). |
| `GET` | `/api/v1/prescriptions/{id}` | All authenticated roles | Retrieve prescription with line items, dispensing status, and QR payload. |
| `GET` | `/api/v1/prescriptions/verify/{verification_hash}` | Public / Authenticated | Zero-PII public verification of prescription authenticity and validity. |
| `POST` | `/api/v1/prescriptions/{id}/dispense` | `doctor`, `receptionist`, `hospital_admin` | Transition status to `ready_for_pickup` or `dispensed` with optional lot notes. |
| `POST` | `/api/v1/prescriptions/{id}/discontinue` | `doctor` | Discontinue prescription with mandatory documented clinical rationale. |
| `GET` | `/api/v1/prescriptions/adherence/{patient_id}` | `patient`, `caregiver`, `doctor`, `hospital_admin` | Get calculated 30-day adherence rate, score badge, and scheduled doses. |
| `POST` | `/api/v1/prescriptions/adherence/log` | `patient`, `caregiver` | Log a dose as `taken` or `skipped`. |

---

## 6. Acceptance Criteria (AC-9.1 to AC-9.12)

| Criteria ID | Requirement | Verification Method |
|---|---|---|
| **AC-9.1** | **Structured E-Prescription Creation** | Doctors can author multi-item prescriptions with dosage, frequency, and instructions. |
| **AC-9.2** | **Pre-Issuance Safety Check** | Automatically runs deterministic Phase 7 knowledge base checks before saving prescription. |
| **AC-9.3** | **Cryptographic Tamper-Proof Signature** | Generates verifiable `v1:<hmac>` signature validating canonical prescription payload. |
| **AC-9.4** | **Zero-PII Public Verification Endpoint** | Allows verification of signature and validity without compromising patient PII. |
| **AC-9.5** | **Pharmacy Dispensing Lifecycle** | Authorized staff can transition status to `dispensed` with recorded timestamps and notes. |
| **AC-9.6** | **Physician-Only Discontinuation** | Only authorized doctors can discontinue active prescriptions with documented rationale. |
| **AC-9.7** | **Interactive Adherence Tracking** | Patients and caregivers can log doses (`taken`, `skipped`); calculates compliance score. |
| **AC-9.8** | **Patient Role Mutation Barrier** | Patients attempting to author prescriptions or dispense receive HTTP 403 Forbidden. |
| **AC-9.9** | **Tenant Isolation & RLS** | Cross-tenant prescription queries return HTTP 404 or empty list. |
| **AC-9.10** | **Non-Cascading Deletion** | Patient records protected with `ON DELETE RESTRICT`; prescriptions remain auditable. |
| **AC-9.11** | **Zero-PHI Audit Logging** | Audit trail logs event codes and pseudonyms; zero drug names or dosage text in audit file. |
| **AC-9.12** | **CSCM Research Preservation** | Zero modifications to CSCM-IoMT models, scripts, or datasets. |

---

## 7. Governance and Approval Gate

**Current State: REVISION 3 RECORDED — AWAITING FORMAL OWNER APPROVAL.**

All safety recommendations and CSCM-IoMT research preservation requirements have been fully codified into Revision 3:
1. **Cryptographic HMAC Key Rotation & Zero-PII Public Verification**: Key ID prefix (`v1:`) and public verification endpoint with strict PII removal.
2. **Dose-Scheduling & Adherence Scoring Engine**: Deterministic schedule mapping and mathematical adherence formula.
3. **Pharmacy FSM & Permissions**: Strict role boundaries and physician-only discontinuation with mandatory rationale.
4. **Tenant Isolation & Audit Retention**: Composite tenant keys, `ON DELETE RESTRICT` on patients, and zero-PHI structured logging.
5. **CSCM-IoMT Research Preservation**: Permanent preservation of *Coordinated Multi-Channel False Data Injection Attack Detection Using Physiology-Aware Cross-Sensor Consistency Modeling in IoMT*.

> **NO IMPLEMENTATION AUTHORIZED** until the owner provides explicit approval (e.g., *"Approve Phase 9"* or *"Approve"*). Upon approval, implementation will proceed through the standard verified lifecycle: SQL migrations, backend API endpoints, pre-issuance safety checks, frontend views, automated test suites, and the Phase 9 Implementation Report.

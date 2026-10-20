# Phase 6 Plan — Revision 2
## Document Intelligence: OCR, Clinical Entity Extraction & Clinician Verification

**Document:** `docs/phase-plans/PHASE_6_PLAN.md`  
**Phase:** 6 — Document Intelligence  
**Status:** Revision 2 — Owner Design Choices Recorded; Pending Formal Approval  
**Date:** 2026-10-15

> **PROPOSAL ONLY — NO IMPLEMENTATION AUTHORIZED**
>
> This document is a revised specification for owner review. No database migrations, backend endpoints, frontend components, or AI extraction implementation may begin until the owner explicitly approves this revision. CSCM-IoMT research assets must remain untouched.

---

## 1. Executive Summary

CareBridge AI will introduce a secure document intelligence pipeline for clinical PDFs and images. It will extract document text, identify structured clinical entities, and provide a clinician verification workflow.

The system will support:

- Private Supabase Storage for uploaded documents.
- Local PDF text extraction and optional Tesseract OCR.
- Groq-powered structured extraction tested exclusively with synthetic clinical data in this phase.
- Human review before extracted information can become part of an authoritative clinical record.
- Hospital-level tenant isolation and role-based access.
- Doctor workstation notifications for newly uploaded documents.
- Zero-PHI application audit logs.
- Complete preservation of CSCM-IoMT research assets.

**Budget objective:** ₹0 for development using available free tiers and open-source tools. This is a target, not a guarantee of future operating costs.

## 2. Owner Decisions Recorded

| Decision | Approved design choice |
|---|---|
| Document storage | Private Supabase Storage bucket named `clinical-documents` |
| OCR strategy | Local PDF extraction, with optional local Tesseract OCR |
| Doctor notification | Unread-document task badge |
| Groq privacy approach | Synthetic data only for AI tests |

These are design decisions only. They do not authorize implementation.

## 3. Technical Architecture

### 3.1 Document ingestion

1. An authenticated user selects a document and its type.
2. The backend validates authorization, file size, file signature, allowed format, and content.
3. The original document is uploaded to the private Supabase Storage bucket.
4. A database record is created with an initial processing status.
5. Local text extraction is attempted.
6. If a scanned document lacks a usable text layer, optional Tesseract OCR is used.
7. Extracted text is processed by the structured extraction pipeline using synthetic clinical data in AI tests.
8. Extracted entities are stored in a pending-review state.
9. An unread-document task appears for the appropriate authorized doctor or clinical workflow.
10. A clinician reviews the source document and extracted fields, makes corrections if necessary, and records a verification decision.

Processing failures must not create verified entities or partially update authoritative clinical records.

### 3.2 Extraction tools

- `pypdf` for digital PDF text extraction.
- `pdfplumber` when additional PDF text-layout extraction is needed.
- Optional Tesseract OCR for scanned PDFs and images.
- Pydantic schemas for validating structured model output.
- The existing Groq client for controlled extraction tests using synthetic data.

**Privacy boundary:** No real patient documents or identifiable clinical text may be sent to Groq during Phase 6. Processing real patient data through an external model is outside this phase and requires a separate review of applicable privacy obligations, provider terms, data retention, and security controls.

### 3.3 Clinical entities

The extraction schema will support:

- Diagnoses and clinical conditions.
- Medications, including drug name, dosage, frequency, route, and duration.
- Laboratory results, including values, units, reference ranges, and abnormal flags.
- Vital signs.
- Allergies and adverse reactions.
- Document metadata, including report date and facility information where available.

The system must preserve source-document references and page references for extracted fields wherever available. Missing or ambiguous values must remain explicitly unknown rather than being guessed.

Model-generated confidence scores must not be treated as proof of clinical correctness.

## 4. Database Schema and Tenant Security

### 4.1 `public.clinical_documents`

Proposed fields:

- `id`
- `hospital_id`
- `patient_id`
- `uploaded_by`
- `document_type`
- `file_name`
- `mime_type`
- `file_size_bytes`
- `storage_path`
- `ocr_status`
- `raw_text`
- `error_code`
- `created_at`
- `updated_at`

Processing states: `pending`, `processing`, `completed`, and `failed`.

The original document must remain in private storage. Storage paths and download access must be protected by server-side authorization.

### 4.2 `public.extracted_entities`

Proposed fields:

- `id`
- `hospital_id`
- `document_id`
- `patient_id`
- `entity_category`
- `extracted_data`
- `confidence_score`
- `verification_status`
- `verified_by`
- `verified_at`
- `doctor_notes`
- `created_at`
- `updated_at`

Review states: `pending`, `verified`, `rejected`, and `edited`.

Document processing status and entity verification status must remain separate.

### 4.3 Database invariants

- Use composite foreign keys or equivalent database constraints to prevent mismatched hospital, patient, and document IDs.
- Enable Row-Level Security (RLS) on both tables.
- Enforce tenant isolation in database policies and server-side queries.
- Patients and verified caregivers may view only documents belonging to patients they are authorized to access.
- Patients and caregivers cannot edit extracted entities or verify clinical records.
- Receptionists receive only the permissions required for their operational duties.
- Doctors may review and verify documents within their authorized hospital and patient scope.
- Hospital administrators may manage access and operational workflows but do not automatically receive clinical sign-off authority.
- Do not expose Supabase service-role credentials to the browser.

RLS must be tested independently of frontend restrictions.

## 5. API Specification

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/v1/documents/upload` | Validate and upload a document |
| GET | `/api/v1/documents` | List authorized documents |
| GET | `/api/v1/documents/{id}` | Retrieve authorized metadata and permitted extracted text |
| GET | `/api/v1/documents/{id}/entities` | Retrieve extracted entities and review status |
| POST | `/api/v1/documents/{id}/verify` | Verify, edit, or reject extracted entities |
| GET | `/api/v1/documents/{id}/download` | Authorize and stream the original document |

Every endpoint must enforce authentication, tenant isolation, patient/caregiver authorization, and role-specific permissions.

Cross-tenant or unauthorized resource access should return a consistent not-found response where appropriate.

Verification requests must validate each field, record the reviewer and timestamp, and preserve the distinction between extracted and verified information.

## 6. Frontend Components

### 6.1 Document Upload Center

Proposed path: `carebridge/frontend/components/documents/document-upload-modal.tsx`

Features:

- Drag-and-drop and file-picker upload.
- PDF, PNG, and JPEG support.
- A maximum file size of 10 MB.
- Document classification.
- Clear upload and processing status.
- Accessible validation and error messages.

Client-side validation improves usability but does not replace backend validation.

### 6.2 Doctor Document Review

Proposed path: `carebridge/frontend/app/(dashboard)/doctor/documents/[id]/page.tsx`

Features:

- Original document preview beside extracted fields.
- Categorized views for diagnoses, medications, laboratory results, vitals, and allergies.
- Source and page references where available.
- Inline correction of extracted values.
- Verification, rejection, and missing-item workflows.
- Reviewer confirmation before verification is recorded.

Unverified data must be visually distinguished from verified records.

### 6.3 Patient Document Timeline

Proposed path: `carebridge/frontend/app/(dashboard)/portal/documents/page.tsx`

Features:

- Authorized document list.
- Upload and processing status.
- Available verified-document information.
- Secure document viewing and downloading.

Patient and caregiver permissions must be checked by the backend for every request.

### 6.4 Doctor Notification Badge

An unread-document task badge will appear in the doctor workstation queue when an authorized patient or caregiver uploads a relevant document.

- Notifications must be scoped to the appropriate hospital and authorized care workflow.
- The badge must not expose document contents or unnecessary sensitive information.
- Read/unread status must be stored and updated securely.
- Failed extraction must remain visible as a processing issue rather than being represented as a completed review.

## 7. File and AI Security

- Validate actual file signatures, not only extensions or browser-provided MIME types.
- Reject unsupported, oversized, malformed, or suspicious files.
- Generate storage object names on the server.
- Keep the storage bucket private.
- Protect against malicious document content and unsafe PDF/image parsing.
- Treat extracted document text as untrusted input.
- Prevent document-embedded instructions from changing system instructions or invoking agent tools.
- Never allow document content to bypass authorization or trigger clinical actions.
- Never automatically create or update an active diagnosis, prescription, or other authoritative clinical record from unverified extraction.
- Avoid logging raw document text, OCR buffers, extracted clinical entities, access tokens, or signed download URLs.
- Return safe error messages without exposing internal details.

## 8. Zero-PHI Audit Trail

Audit events will record the minimum information needed for accountability, such as:

- Event type.
- Timestamp.
- Hospital and actor references, using the existing audit conventions.
- Document reference or pseudonymous identifier.
- Processing outcome.
- Verification action and reviewer reference.

Audit logs must not contain clinical text, extracted values, patient names, raw prompts, or document contents.

The document database and private storage are still sensitive-data systems even when audit logs contain no PHI.

## 9. Acceptance Criteria

| ID | Requirement | Verification |
|---|---|---|
| AC-6.1 | Secure upload | PDF, PNG, and JPEG files up to 10 MB accepted; invalid files rejected |
| AC-6.2 | Digital PDF extraction | Text extracted locally without external LLM processing |
| AC-6.3 | Scanned document OCR | Optional Tesseract fallback tested using synthetic documents |
| AC-6.4 | Structured extraction | Pydantic validation rejects malformed model output |
| AC-6.5 | Human review | Extracted entities remain pending until authorized verification |
| AC-6.6 | Tenant isolation | Cross-hospital and unauthorized patient access denied |
| AC-6.7 | Role enforcement | Patients, caregivers, receptionists, doctors, and administrators receive only permitted access |
| AC-6.8 | Clinical provenance | Extracted fields preserve source and page references where available |
| AC-6.9 | No automatic clinical mutation | Unverified extraction never updates authoritative clinical records |
| AC-6.10 | Private storage | Unauthorized access to document objects is denied |
| AC-6.11 | Notifications | Authorized doctor queue displays unread-document tasks |
| AC-6.12 | Zero-PHI logging | Application and audit logs exclude document content and extracted clinical values |
| AC-6.13 | Failure handling | Invalid files, OCR failures, timeouts, and invalid model responses fail safely |
| AC-6.14 | Prompt-injection resistance | Embedded document instructions cannot bypass safeguards or trigger unauthorized tools |
| AC-6.15 | Research preservation | No unauthorized changes to CSCM-IoMT source, models, datasets, or evaluation assets |

## 10. Testing Strategy

- Unit tests for file validation, text extraction, OCR fallback, schema validation, and status transitions.
- API tests for upload, listing, download, extraction, verification, and notification behavior.
- RLS tests for cross-tenant access and patient/caregiver isolation.
- Role-based tests for verification permissions.
- Synthetic-document tests for extraction accuracy and provenance.
- Failure tests for malformed files, OCR errors, provider rate limits, timeouts, and invalid structured output.
- Security tests for malicious file handling and document prompt injection.
- Frontend lint and production build.
- Regression tests for existing Phase 3 workflows and Phase 5 agent behavior.
- Verification that CSCM-IoMT research assets remain untouched.

Actual results must be reported only after the corresponding tests have been run.

## 11. Scope Boundaries

Phase 6 does not authorize:

- Processing real patient documents through Groq.
- Automatic diagnosis or prescription creation.
- Automatic modification of clinical records.
- Autonomous medication decisions.
- Changes to CSCM-IoMT model training, checkpoints, datasets, or evaluation pipelines.
- Destructive database migrations or data deletion without separate explicit authorization.

Any newly discovered backend defect that requires changes outside the approved scope must be documented in a separate proposal and submitted for approval.

## 12. Governance and Approval Gate

**Current status: PENDING — NO IMPLEMENTATION AUTHORIZED.**

The owner has supplied design choices for storage, OCR, notifications, and synthetic-only AI testing. Those choices are recorded in this revision and do not constitute implementation approval.

Before proceeding, the owner must explicitly approve **Phase 6 Plan Revision 2**.

After approval, implementation must follow the project's phase governance: implement only the approved scope, run and report actual tests, preserve uncommitted work and CSCM research assets, document results in `docs/phase-reports/PHASE_6_REPORT.md`, and stop before proposing or implementing the next phase.

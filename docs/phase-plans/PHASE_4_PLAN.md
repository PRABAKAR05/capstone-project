# Phase 4 Plan: Design System & Responsive Hospital Web Application

**Document:** `docs/phase-plans/PHASE_4_PLAN.md`  
**Phase:** 4 — Design System & Responsive Hospital Web Application (Next.js 16, React 19, Tailwind CSS v4, Lucide React)  
**Status:** Proposal (Revision 3) — Pending Owner Formal Review and Approval  
**Budget:** ₹0 (100% Free & Open Source, zero paid services or libraries)  
**Date:** 2026-10-15  

---

## 1. Executive Summary & Objectives

Phase 4 establishes the user-facing web tier for **CareBridge AI**. Building directly upon the verified Phase 2 Supabase schema and Phase 3 FastAPI API layer, Phase 4 delivers a clinical-grade, accessible, and responsive hospital operations and patient engagement web portal.

### Core Objectives:
1. **Design System & Accessible Primitives**: Implement a cohesive clinical design system in `carebridge/frontend` utilizing Next.js 16 (App Router), React 19, Tailwind CSS v4, and Lucide React icons, adhering to WCAG 2.1 AA accessibility guidelines.
2. **Role-Adaptive Application Shell**: Deploy a dynamic navigation shell with persistent hospital tenant awareness (`hospitals.name`), department context, user role badge, and hospital timezone display (`Asia/Kolkata`).
3. **Four Dedicated Role Portals**:
   - **Patient & Caregiver Portal**: Demographics view, dynamic timezone-aware appointment booking wizard (with real-time conflict handling), appointment cancellation, and caregiver linking/revocation management.
   - **Doctor & Clinical Workstation**: Daily patient roster, status tracking (`scheduled` -> `confirmed` -> `in_progress` -> `completed`), and authorized clinical note documentation.
   - **Reception & Check-in Desk**: Fast Patient Master Index (PMI) search (with demographic-only field redaction), patient check-in, and caregiver evidence verification workflow.
   - **Hospital Administrator Portal**: Department listings, doctor roster, and real-time operational capacity metrics.
4. **Security & Privacy by Design**:
   - **Cryptographic JWT Transport & Zero-Trust Client**: The frontend forwards the Supabase session JWT to FastAPI. Frontend role selection is never trusted as authorization; the backend derives identity and privileges directly from the token and database.
   - **Zero-PHI Frontend Logging**: Strict prohibition of patient names, MRNs, phone numbers, or clinical notes in browser console logs.
   - **RFC 7807 Error Interceptor**: Centralized HTTP client mapping backend Problem Details (e.g., 409 Conflict for double-booking, 422 for illegal state transitions, 403 for unauthorized note updates) into intuitive UI alerts.
   - **Anti-Enumeration Handling**: Seamless presentation of HTTP 404 responses without leaking existence of cross-tenant entities.
   - **Real-Time Caregiver Revocation Enforcement**: Immediate access cutoff upon revocation, verified against active sessions.
5. **Pre-Integration Read-Only Verification**: Explicit inspection of Phase 3 routes, schemas, and policies before integrating frontend code, with a strict prohibition against silent backend modifications.
6. **Research Asset Preservation**: CSCM model checkpoints, training scripts, and HDF5 datasets remain strictly isolated and untouched.

---

## 2. Technology Stack & Directory Structure

### 2.1 Approved Stack
- **Framework**: Next.js 16.4.0 (App Router, Turbopack, React 19 Server & Client Components)
- **Styling**: Tailwind CSS v4 with modern CSS variables for semantic theme tokens
- **Icons**: `lucide-react`
- **Utilities**: `clsx`, `tailwind-merge` (for standard `cn()` class merging)
- **Authentication & Backend API**: Supabase Browser Client (`@supabase/supabase-js`) + native `fetch` wrapper targeting FastAPI backend (`http://localhost:8000/api/v1`)
- **Cost**: **₹0.00** — zero proprietary component subscriptions, zero paid icon kits.

### 2.2 Target Frontend Directory Layout (`carebridge/frontend/`)
```
carebridge/frontend/
├── app/
│   ├── (auth)/
│   │   └── login/
│   │       └── page.tsx              # Synthetic demo credentials & Supabase Auth login
│   ├── (dashboard)/
│   │   ├── layout.tsx                # Role-adaptive shell (Sidebar, Navbar, Tenant Header)
│   │   ├── page.tsx                  # Role-based dashboard redirector
│   │   ├── admin/
│   │   │   └── page.tsx              # Hospital operations & doctor roster
│   │   ├── doctor/
│   │   │   └── page.tsx              # Doctor clinical queue & consultation room
│   │   ├── receptionist/
│   │   │   ├── page.tsx              # Reception desk, PMI search & check-in
│   │   │   └── verify-caregivers/
│   │   │       └── page.tsx          # Caregiver evidence inspection & verification
│   │   └── portal/
│   │       ├── page.tsx              # Patient home, profile & quick actions
│   │       ├── book/
│   │       │   └── page.tsx          # 3-Step appointment booking wizard
│   │       └── caregivers/
│   │           └── page.tsx          # Linked caregivers & patient-owned revocation
│   ├── globals.css                   # Semantic clinical theme variables & Tailwind setup
│   └── layout.tsx                    # Root layout with Toast & Context providers
├── components/
│   ├── ui/                           # Accessible design system primitives
│   │   ├── button.tsx
│   │   ├── card.tsx
│   │   ├── badge.tsx
│   │   ├── input.tsx
│   │   ├── select.tsx
│   │   ├── dialog.tsx
│   │   ├── table.tsx
│   │   ├── tabs.tsx
│   │   ├── alert.tsx
│   │   └── skeleton.tsx
│   ├── shell/                        # Application layout components
│   │   ├── sidebar.tsx
│   │   ├── navbar.tsx
│   │   └── tenant-header.tsx
│   ├── appointments/                 # Feature-specific components
│   │   ├── slot-picker.tsx           # Dynamic timezone slot selector
│   │   ├── appointment-card.tsx      # Status badge & lifecycle actions
│   │   └── cancel-modal.tsx          # Reason input & 2-hr cutoff warning
│   └── patients/
│       ├── pmi-search-bar.tsx
│       └── caregiver-request-form.tsx
└── lib/
    ├── api.ts                        # Centralized backend client with RFC 7807 handler
    ├── auth.ts                       # Supabase session manager & role claims
    ├── timezone.ts                   # Date/time formatting in Asia/Kolkata
    └── utils.ts                      # Class merging (`cn`) & string sanitizers
```

---

## 3. Core Architecture, Verification Boundaries & Security Invariants

### 3.1 Pre-Integration Backend Inspection & Prohibition on Silent Backend Changes
1. **Design vs. Verified Runtime Distinction**:
   - The security mechanisms described in this proposal represent intended behavioral specifications. They do not constitute evidence that the backend implements them without flaw until formally inspected.
   - **Mandatory Step 0**: Prior to implementing frontend components, the agent must perform a **read-only inspection** of all existing Phase 3 FastAPI routes (`app/api/v1/`), dependency authenticators (`app/core/security.py`), response models (`app/schemas/`), and database Row Level Security policies.
2. **Strict Prohibition Against Silent Backend Modifications**:
   - The agent is **strictly prohibited from silently modifying Phase 3 backend application code, SQL schemas, or triggers** to accommodate frontend features or resolve interface mismatches.
   - If a schema discrepancy, missing endpoint, or backend defect is discovered during frontend integration, the agent must:
     1. Stop immediately.
     2. Document the issue clearly in an issue log.
     3. Submit a formal revision proposal for owner review and approval before touching any backend files.

### 3.2 Authentication Integration & Zero-Trust Token Flow
1. **Supabase Session Management**:
   - The browser application initializes `@supabase/supabase-js` using standard public environment variables: `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY`.
   - Upon authentication, Supabase Auth issues a cryptographically signed JWT access token (`session.access_token`).
2. **FastAPI Authorization Header**:
   - In `lib/api.ts`, all HTTP requests to the backend (`http://localhost:8000/api/v1`) attach the token:
     `Authorization: Bearer ${session.access_token}`
3. **Zero Trust in Frontend-Selected Roles**:
   - The frontend never transmits a role header, query parameter, or payload field to claim privileges.
   - Any role selector or tab in the UI acts strictly as a **view mode switch**.
   - **Backend is the Sole Authority**: FastAPI independently extracts the `sub` claim from the cryptographically verified JWT, checks `public.profiles` for `role`, `hospital_id`, and `is_active`, and enforces database Row Level Security.
   - If a patient or unauthorized user selects an administrative or clinical view, all resulting API calls are rejected with HTTP 403 Forbidden or HTTP 404 Not Found.

### 3.3 Safe Demonstration Accounts & Zero Credential Exposure
1. **Configured Synthetic Accounts Only**:
   - Demonstration buttons pre-fill email addresses for the synthetic test accounts defined in the Phase 2 database seed:
     - Hospital Administrator: `admin1@aegis.example.com`
     - Attending Cardiologist: `doc1@aegis.example.com`
     - Front Desk Receptionist: `rec1@aegis.example.com`
     - Authoritative Patient: `patuser1@example.com`
     - Linked Dependent Caregiver: `caregiver@example.com`
2. **Prohibition on Hardcoded Passwords or Secret Keys**:
   - Demonstration login helpers must **never** assume accounts authenticate without configured credentials.
   - Passwords, service-role keys, or privileged tokens must **never** be embedded, committed, or exposed in frontend source code, client-side bundles, or repository files.
   - The demonstration interface pre-fills only the synthetic identifier (email), requiring the password to be entered or read securely from local, git-ignored developer environment variables (`.env.local`).
3. **Zero Secret Key Exposure**:
   - `SUPABASE_SERVICE_ROLE_KEY` is strictly confined to `carebridge/backend/.env`. It is **never** bundled, referenced, or exposed in frontend source files or environment variables.
   - Only `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY` are accessible to the browser client.
4. **No Real Patient Data**:
   - All demonstration data, names, phone numbers, and emergency contacts are 100% fictional.

### 3.4 Clinical Note Authorization & Assigned Doctor Enforcement
1. **Defense-in-Depth UI Presentation**:
   - The doctor consultation interface displays the `clinical_notes` editor as active only when the authenticated user's ID matches the assigned doctor (`appointment.doctor_id`).
   - If viewed by a non-assigned clinician or staff member, notes are presented in read-only mode with an informative badge.
2. **Backend Enforcement Guarantee**:
   - UI disabling is purely an ergonomics feature; **the true security boundary is enforced at the API**:
     - `PATCH /api/v1/appointments/{id}/status` verifies that the caller is `hospital_admin` or the specifically assigned doctor.
     - Any direct API mutation of `clinical_notes` by patients, receptionists, or unauthorized staff raises **HTTP 403 Forbidden** (`"Unauthorized: Only the assigned doctor or hospital administrator can write clinical notes"`).
   - The frontend catches this 403 response, presents an RFC 7807 error banner, and rolls back any optimistic local edits.

### 3.5 Caregiver Revocation & Active Session Invalidation
1. **Real-Time Database Verification**:
   - Caregiver authorization is not baked into a static JWT; it depends on a live database relationship in `public.patient_accounts`.
   - When a patient executes `PATCH /api/v1/patient-accounts/{id}/revoke`, the record status is immediately set to `'revoked'`.
2. **Immediate Access Cutoff for Active Sessions**:
   - Even if a revoked caregiver holds an active, unexpired Supabase login session, their subsequent API calls to `/api/v1/patients/{patient_id}` or appointment scheduling endpoints trigger `has_patient_access()` on the backend.
   - Because `has_patient_access()` requires `status = 'verified'`, the query immediately returns 0 rows, and the API returns **HTTP 404 Not Found** (anti-enumeration).
3. **Frontend Invalidation Handling**:
   - When the caregiver portal encounters an HTTP 404 for a previously accessible dependent, the UI immediately clears the dependent from active view, updates the dependent list, and informs the user that authorization is no longer valid.

---

## 4. Clinical Design System & Semantic Color Tokens

CareBridge AI adopts an accessible, high-contrast clinical theme designed for high-stress healthcare environments:

### 4.1 Color Palette & Theme Tokens
| Token | Light Value | Purpose / Meaning |
|---|---|---|
| `bg-primary` | `oklch(0.48 0.15 240)` (Deep Medical Blue) | Primary brand actions, active navigation, key CTAs |
| `bg-secondary` | `oklch(0.96 0.02 240)` (Soft Slate Gray) | Secondary buttons, subtle card headers |
| `accent-teal` | `oklch(0.60 0.14 190)` (Clinical Teal) | Medical confirmations, verified caregiver badges |
| `status-success` | `oklch(0.62 0.17 145)` (Forest Emerald) | Completed appointments, active accounts |
| `status-warning` | `oklch(0.75 0.18 75)` (Amber Warning) | Pending verification, 2-hour cancellation notice |
| `status-danger` | `oklch(0.55 0.22 25)` (Crimson Red) | Cancelled slots, 409 conflict, unauthorized attempts |
| `surface-card` | `#FFFFFF` with border `oklch(0.92 0.01 240)` | High-density clinical card containers |

### 4.2 Typography & Accessibility (WCAG 2.1 AA)
- High contrast ratio: Minimum 4.5:1 for body copy and 3:1 for large text.
- Focus visible rings on all interactive elements (`focus-visible:ring-2 focus-visible:ring-primary`).
- Semantic HTML tags (`<nav>`, `<main>`, `<article>`, `<header>`, `<table>`) with ARIA attributes (`aria-expanded`, `aria-haspopup`, `aria-busy`).

---

## 5. Role-Adaptive Application Portals

### 5.1 Patient & Caregiver Portal
- **Demographics & Records Overview**:
  - Displays authoritative PMI fields (MRN, Full Name, DOB, Blood Group, Emergency Contact).
  - Explicit notification if viewing as a verified caregiver for a dependent.
- **Dynamic 3-Step Appointment Booking Wizard**:
  - **Step 1: Department & Specialist Selection**: Filters active doctors by department and specialization.
  - **Step 2: Timezone-Aware Slot Selection**:
    - Fetches live slots from `/api/v1/doctors/{id}/slots?slot_date=YYYY-MM-DD`.
    - Explicitly displays slots in `Asia/Kolkata` with clear morning/afternoon partitioning.
    - Disabled slots for already booked intervals.
  - **Step 3: Review & Confirmation**:
    - Displays consultation fee, reason for visit prompt.
    - Handles concurrency: If another user books the slot concurrently, catches HTTP 409 Conflict and prompts user to pick an alternate available slot immediately without losing wizard progress.
- **Appointment Management**:
  - View upcoming appointments with live status badge (`scheduled`, `confirmed`).
  - Cancel appointment button enabled only if >2 hours before start time. Opens modal requiring `cancellation_reason`.
- **Caregiver Linking & Revocation Manager**:
  - Submit link request with standardized evidence type (`legal_guardianship_order`, `power_of_attorney`, etc.) and authority name.
  - View all active caregiver links.
  - **1-Click Patient-Owned Revocation**: Red "Revoke Access" button allows the patient to instantly terminate caregiver privileges.

### 5.2 Reception & Check-in Desk
- **Patient Master Index (PMI) Search**:
  - Real-time search by MRN or patient name.
  - Displays demographic details only (phone, emergency contact). Medical history and confidential notes remain redacted in compliance with Phase 3 field-level security.
- **Appointment Queue & Rapid Check-In**:
  - Daily schedule view for the hospital.
  - One-click check-in button executing transition `scheduled` -> `confirmed`.
- **Caregiver Verification Desk**:
  - Listing of all `pending_verification` caregiver requests for the hospital.
  - Displays submitted evidence reference number and issuing authority.
  - Self-approval protection: Verifier cannot approve their own requests.
  - Staff selects verification method (`in_person_inspection`, `notarized_consent_verified`) and confirms link.

### 5.3 Doctor Clinical Workstation
- **Active Consultation Queue**:
  - Chronological list of confirmed patients for the day.
  - Quick action: "Start Consultation" (transitions status to `in_progress`).
- **Clinical Consultation View**:
  - Patient banner with age, gender, blood group, and reason for visit.
  - Authorized `clinical_notes` documentation field (only editable by assigned doctor or admin; backend rejects unauthorized edits with 403).
  - Final action: "Complete Consultation" (transitions status to terminal `completed`).

### 5.4 Hospital Administrator View
- **Operational Metrics**:
  - Total active departments, doctors on duty, and daily appointment distribution.
  - Hospital metadata view showing configured timezone (`Asia/Kolkata`) and license parameters.

---

## 6. Frontend Security, Session & Privacy Invariants

1. **Zero-PHI Console Invariant**:
   - `lib/api.ts` must never log request or response payloads containing patient names, medical notes, or contact info to `console.log` or `console.error`.
   - Logging in development is restricted to HTTP method, endpoint route, status code, and sanitized error code.
2. **RFC 7807 Centralized Error Handling**:
   - Backend returns structured errors (`title`, `status`, `detail`).
   - The frontend error boundary and toast notifications parse `detail` directly into contextual alerts (e.g., *"This doctor is already booked for the selected time slot. Please choose another slot."* for 409 Conflict).
3. **Anti-Enumeration Integrity**:
   - When the backend returns HTTP 404 for cross-tenant resources, the frontend displays a standard *"Record not found"* notice, ensuring no confirmation of existence in other hospitals.
4. **Timezone Determinism**:
   - All appointment timestamps are formatted using the hospital's authoritative timezone (`Asia/Kolkata`) to prevent user confusion across different travel or client device settings.

---

## 7. Acceptance Criteria

| # | Acceptance Criterion | Verification Method |
|---|---------------------|---------------------|
| **AC 4.1** | Clean Next.js 16 build with 0 TypeScript/ESLint errors | `npm run build` exits 0 with all routes generated |
| **AC 4.2** | Responsive design across desktop, tablet, and mobile | Viewport testing at 1440px, 768px, and 375px |
| **AC 4.3** | Interactive Appointment Booking Wizard with live dynamic slots | Successfully books slot against Phase 3 FastAPI backend |
| **AC 4.4** | Real-time 409 Conflict UI handling | Attempting duplicate booking displays slot collision alert without data loss |
| **AC 4.5** | Real-time caregiver revocation cutoff | Revoking link immediately cuts off caregiver queries (404) even with active session |
| **AC 4.6** | Receptionist PMI view enforces field-level redaction | Verified clinical notes are hidden in receptionist UI and redacted by backend |
| **AC 4.7** | Doctor clinical note backend authorization | Non-assigned doctors/patients cannot write notes; backend enforces 403 |
| **AC 4.8** | Synthetic demonstration accounts only | No real PII, service-role keys, or production data exposed |
| **AC 4.9** | Zero hardcoded credentials in repository | Codebase audit verifies no embedded passwords or privileged keys |
| **AC 4.10** | Pre-integration verification without backend tampering | Read-only inspection completed; zero unauthorized Phase 3 backend modifications |
| **AC 4.11** | Zero-PHI frontend logging | Console audit confirms no patient identifiers emitted |
| **AC 4.12** | CSCM research assets remain unmodified | Git diff confirms `src/`, `models/`, and datasets untouched |

---

## 8. Implementation Workflow (Upon Approval)

1. **Step 0: Pre-Integration Inspection**: Execute read-only inspection of Phase 3 API routes, schemas, and RLS policies. Formally record verification findings. Strictly zero modifications to Phase 3 backend code.
2. **Step 1: UI Primitives & Theme Tokens**: Setup `globals.css` with semantic clinical variables, install accessible primitives (`button`, `card`, `dialog`, `badge`, `table`, `input`, `select`, `tabs`, `alert`).
3. **Step 2: API Client & Auth Context**: Implement `lib/api.ts` with RFC 7807 interception and Supabase token injection.
4. **Step 3: Core Shell & Navigation**: Implement `Sidebar`, `Navbar`, and `TenantHeader` with role switching.
5. **Step 4: Role Portals**: Implement Patient Booking Wizard, Caregiver Management, Doctor Roster, Receptionist PMI desk.
6. **Step 5: Verification & Build**: Run `npm run build` and end-to-end browser walkthrough.
7. **Step 6: Phase 4 Implementation Report**: Compile evidence and await review before Phase 5.

---

> [!IMPORTANT]
> **Owner Review Gate**: Implementation of Phase 4 is pending formal user review and approval. No frontend application code, UI components, or configuration files will be modified until explicit authorization is granted.

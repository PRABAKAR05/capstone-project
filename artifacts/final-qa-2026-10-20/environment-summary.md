# CareBridge AI — Target Environment & Architecture Summary

**Evaluation Date**: 2026-10-20  
**Environment**: Production Demonstration & Final End-to-End QA Validation  
**Target Cluster**: Supabase Cloud PostgreSQL 15 (`db.vmuzexvtbodnkzhfitzf.supabase.co:5432`)  

---

## 1. Operating System & Runtime Environments

| Component | Specification | Description |
|:---|:---|:---|
| **Host Operating System** | Windows 11 Enterprise (x86_64) | Shell: Windows PowerShell 5.1 / PowerShell 7 |
| **Python Runtime** | Python 3.13.2 (64-bit) | Located at `C:\Users\PRABAKAR\AppData\Local\Programs\Python\Python313\python.exe` |
| **Node.js Runtime** | Node.js v20+ | Next.js 16.4.0 with Turbopack Bundler |
| **React Framework** | React 19.3.0 / React-DOM 19.3.0 | Client/Server Components with Tailwind CSS v4 |
| **Browser Engine** | Playwright Chromium v1248 | Automated headless browser validation |

---

## 2. Service Architecture & Network Topology

| Service | Protocol / Binding | Port | Primary Responsibilities |
|:---|:---|:---:|:---|
| **CareBridge Backend** | HTTP / REST / RFC 7807 | `8000` | FastAPI 0.12.0 core services, JWT cryptography, RBAC/RLS boundary enforcement, clinical conflict engine, prescription QR verification, CSCM integration |
| **CareBridge Frontend** | HTTP / Next.js Server | `3000` | Next.js 16.4.0 Turbopack application, responsive multi-role clinical workstation, zero-PHI client telemetry, patient portal |
| **Database Cluster** | PostgreSQL 15 / TLS | `5432` | Managed Supabase PostgreSQL with `pgcrypto` (`extensions.crypt`), Row-Level Security, multi-tenant schemas (`public`, `auth`, `carebridge_internal`) |

---

## 3. Hospital Multi-Tenant Topography

The environment is strictly partitioned into two production hospital tenants to prove cross-tenant isolation and strict multi-tenancy:

1. **Hospital 1 (Primary Hub)**:
   - **ID**: `11111111-1111-1111-1111-111111111111`
   - **Name**: Aegis Metro General Hospital
   - **Slug**: `aegis-metro`
   - **Timezone**: `Asia/Kolkata`
   - **Assigned Synthetic Personas**: `CB-ADMIN-01..03`, `CB-DOCTOR-01..03`, `CB-NURSE-01..03`, `CB-LAB-01..03`, `CB-PATIENT-01..03`
   - **Clinical Data**: 12 inpatient ward patients, clinical documents, active HbA1c diagnostic conflict, care tasks, prescriptions.

2. **Hospital 2 (Secondary Peer)**:
   - **ID**: `22222222-2222-2222-2222-222222222222`
   - **Name**: St. Jude Regional Infirmary
   - **Slug**: `st-jude-metro`
   - **Timezone**: `Asia/Kolkata`
   - **Assigned Synthetic Personas**: `CB-ADMIN-04`, `CB-DOCTOR-04`, `CB-NURSE-04`, `CB-LAB-04`, `CB-PATIENT-04`
   - **Purpose**: Validates cross-tenant boundaries (cross-tenant 404/403 barrier enforcement).

---

## 4. Role Governance & RBAC Lifecycle

| Role | Status | Description | Workstation Route |
|:---|:---:|:---|:---:|
| **Hospital Admin** | **ACTIVE** | Operational analytics, doctor roster, system governance | `/admin` |
| **Doctor** | **ACTIVE** | Clinical consultations, notes recording, conflict reconciliation | `/doctor` |
| **Nurse** | **ACTIVE** | Patient intake, rapid OPD check-in, care tasks coordination | `/nurse`, `/tasks` |
| **Lab Technician** | **ACTIVE** | Specimen accessioning, demographics-masked verification | `/lab` |
| **Patient** | **ACTIVE** | Personal health records, 3-step appointment booking | `/portal`, `/portal/book` |
| **Receptionist** | **RETIRED** | Permanently decommissioned; role barred with 403, UI route with 404 | `/receptionist` (404) |
| **Caregiver** | **RETIRED** | Permanently decommissioned; role barred with 403, UI route with 404 | `/portal/caregivers` (404) |

---

## 5. CSCM-IoMT Protected Research Assets

- **Total Research Files**: 17,727 files (`src/`, `models/`, `data/`)
- **Parity Status**: 100% SHA-256 bit-for-bit immutable match against `research_comprehensive_baseline_hashes.json`. Zero mutations.
- **Historical Audit Log**: 48 historical receptionist audit events in `carebridge/backend/logs/audit.jsonl` verified 100% line-by-line identical.

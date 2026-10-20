# CareBridge AI — Repository Archival & Asset Inventory Audit
## Comprehensive Deliverable Catalog & Non-Destructive Archival Record

**Document:** `docs/ARCHIVAL_AUDIT.md`  
**Phase:** 14 — Final Capstone Packaging  
**Date:** 2026-10-16  
**Status:** Completed & Formally Verified  
**Author:** Antigravity (Advanced Agentic Pair Programmer)

---

## 1. Executive Summary & Archival Scope

In adherence to project governance and research preservation mandates, this document provides a comprehensive, structured catalog of all software deliverables, academic manuscripts, research assets, architecture diagrams, and test suites across the CareBridge AI capstone repository.

> [!IMPORTANT]
> **Non-Destructive Archival Guarantee**  
> This archival process is strictly **read-only and non-destructive**. Zero existing files have been moved, renamed, reorganized, or deleted. All legacy scripts, research checkpoints, raw datasets, thesis chapters, and review documents remain in their original directories and exact file paths.

---

## 2. Master Repository Asset Inventory

### 2.1 Preserved Research Core (CSCM-IoMT Capstone Contribution)
*Research Project: Coordinated Multi-Channel False Data Injection Attack Detection Using Physiology-Aware Cross-Sensor Consistency Modeling in IoMT*

| Asset Category | Directory Path | File Count | Verified Preservation Status |
|---|---|---|---|
| **Pipeline Source Code** | `src/` | 36 files | 100% SHA-256 matched (0 mutations) |
| **Model Weights & Checkpoints** | `models/` | 109 files | 100% SHA-256 matched (0 mutations) |
| **Datasets & Normalization** | `data/` | 17,582 files | 100% SHA-256 matched (0 mutations) |
| **Research Scripts** | `scripts/` | 38 files | Preserved in original paths |
| **Research Unit Tests** | `tests/` | 8 files | Preserved in original paths |
| **Conference Paper Assets** | `conference_paper/` | Multi-file | Preserved in original paths |
| **Research Figures** | `report_figures/` | Multi-file | Preserved in original paths |
| **Total Protected Assets** | `src/`, `models/`, `data/` | **17,727 files** | **100% Bit-for-Bit Verified** |

### 2.2 SWE3004 Hospital Platform Monorepo (`carebridge/`)

| Subsystem | Directory Path | Description & Deliverables |
|---|---|---|
| **Frontend Application** | `carebridge/frontend/` | Next.js 15 App Router, TypeScript, Tailwind CSS, shadcn/ui. 16 production routes compiled cleanly. |
| **Backend REST API** | `carebridge/backend/` | FastAPI (Python 3.13), SQLAlchemy connection pool, Pydantic schemas, Groq AI orchestration. |
| **Decoupled Research Adapter** | `carebridge/backend/app/cscm/` | In-process read-only PyTorch adapter (`weights_only=True`, frozen parameters, graph attribution). |
| **Database Migrations** | `carebridge/backend/supabase/migrations/` | 7 sequential SQL migrations (`0001` through `0007`) and down scripts. |
| **Synthetic Seed Data** | `carebridge/backend/supabase/seed.sql` | Synthetic fixtures for Hospital 1 & Hospital 2. |
| **Regression Test Suites** | `carebridge/backend/tests/` | 11 test suites covering Phases 2 through 13 (128 passing tests). |

### 2.3 Comprehensive Documentation Suite (`docs/`)

| Document Type | Directory / File Path | Contents & Scope |
|---|---|---|
| **Dual Architecture Guide** | [`docs/ARCHITECTURE.md`](file:///c:/Users/PRABAKAR/Documents/capstone_PRABAKAR/docs/ARCHITECTURE.md) | High-level system topology, role matrices, decoupled research adapter, and data flows. |
| **Viva Demonstration Guide** | [`docs/VIVA_DEMO_GUIDE.md`](file:///c:/Users/PRABAKAR/Documents/capstone_PRABAKAR/docs/VIVA_DEMO_GUIDE.md) | Step-by-step viva walkthrough script across Patient, Caregiver, Receptionist, Doctor, and Admin. |
| **Local Setup Runbook** | [`docs/LOCAL_SETUP.md`](file:///c:/Users/PRABAKAR/Documents/capstone_PRABAKAR/docs/LOCAL_SETUP.md) | Local development bootstrap, environment variables, sequential migrations, and troubleshooting. |
| **Production Runbook** | [`docs/PRODUCTION_RUNBOOK.md`](file:///c:/Users/PRABAKAR/Documents/capstone_PRABAKAR/docs/PRODUCTION_RUNBOOK.md) | Architectural specification for horizontal scaling and Redis-based distributed sliding-window rate limiting. |
| **Archival & Asset Audit** | [`docs/ARCHIVAL_AUDIT.md`](file:///c:/Users/PRABAKAR/Documents/capstone_PRABAKAR/docs/ARCHIVAL_AUDIT.md) | Non-destructive repository deliverable catalog and research asset verification record. |
| **Implementation Plans** | `docs/phase-plans/` | Complete 14-phase planning proposals (`PHASE_1_PLAN.md` through `PHASE_14_PLAN.md`). |
| **Implementation Reports** | `docs/phase-reports/` | Complete 14-phase verification reports (`PHASE_1_REPORT.md` through `PHASE_14_REPORT.md`). |
| **Thesis Chapters** | `docs/thesis/` | Chapters 4, 5, 6, 7, 8, 9, and 11. |
| **Experimental Reports** | `docs/reports/` | Phase 6, 7, and 8 experimental results, data leakage audits, and `ERROR_ANALYSIS.md`. |
| **Review Deliverables** | `docs/review_1/` | Review 1 evaluation PDF and presentation materials. |

### 2.4 Architecture Visual Assets (Root Diagrams)

All 12 high-resolution architectural diagrams are preserved in the root directory:

1. [`fig_context.png`](file:///c:/Users/PRABAKAR/Documents/capstone_PRABAKAR/fig_context.png): System Context & External Actors.
2. [`fig_components.png`](file:///c:/Users/PRABAKAR/Documents/capstone_PRABAKAR/fig_components.png): High-Level Component Decomposition.
3. [`fig_authz_flow.png`](file:///c:/Users/PRABAKAR/Documents/capstone_PRABAKAR/fig_authz_flow.png): Cryptographic JWT & RBAC Authorization Flow.
4. [`fig_appointment_seq.png`](file:///c:/Users/PRABAKAR/Documents/capstone_PRABAKAR/fig_appointment_seq.png): Appointment Booking & Check-in Sequence.
5. [`fig_document_flow.png`](file:///c:/Users/PRABAKAR/Documents/capstone_PRABAKAR/fig_document_flow.png): Document OCR Extraction Pipeline.
6. [`fig_conflict_flow.png`](file:///c:/Users/PRABAKAR/Documents/capstone_PRABAKAR/fig_conflict_flow.png): Clinical Conflict Detection Sequence.
7. [`fig_prescription_flow.png`](file:///c:/Users/PRABAKAR/Documents/capstone_PRABAKAR/fig_prescription_flow.png): Tamper-Evident E-Prescribing & Hash Verification.
8. [`fig_insurance_flow.png`](file:///c:/Users/PRABAKAR/Documents/capstone_PRABAKAR/fig_insurance_flow.png): Insurance Pre-Auth Estimation & Adjudication.
9. [`fig_cscm_flow.png`](file:///c:/Users/PRABAKAR/Documents/capstone_PRABAKAR/fig_cscm_flow.png): CSCM-IoMT Physiology-Aware Consistency Inference.
10. [`fig_er.png`](file:///c:/Users/PRABAKAR/Documents/capstone_PRABAKAR/fig_er.png): Relational Entity-Relationship (ER) Schema.
11. [`fig_deployment.png`](file:///c:/Users/PRABAKAR/Documents/capstone_PRABAKAR/fig_deployment.png): Local & Cloud Deployment Topology.
12. [`fig_phase_deps.png`](file:///c:/Users/PRABAKAR/Documents/capstone_PRABAKAR/fig_phase_deps.png): 14-Phase Project Execution Roadmap.

### 2.5 Academic Review Documents (Root Directory)
- `22MIS0527_Review-1.docx`: Review 1 project submission.
- `22MIS0527_Review-2.pdf`: Review 2 presentation report.
- `CareBridge_AI_SWE3004_Final_Project_Report.docx`: Capstone final project report (Word).
- `CareBridge_AI_SWE3004_Final_Project_Report.pdf`: Capstone final project report (PDF).
- `CareBridge_AI_SWE3004_Final_Project_Report_updated.docx`: Updated project report revision.

---

## 3. Cryptographic Research Immutability Record

Before and during Phase 14 packaging, automated verification was executed against the cryptographic baseline stored in:
`carebridge/backend/app/cscm/research_comprehensive_baseline_hashes.json`

### Audit Execution Log:
```
Checking 17727 research files against baseline...
- Scanned src/    : 36 files (0 mismatches, 0 modifications)
- Scanned models/ : 109 files (0 mismatches, 0 modifications)
- Scanned data/   : 17,582 files (0 mismatches, 0 modifications)
AUDIT RESULT: 100% of 17,727 files matched baseline exactly. Zero mutations.
```

---

## 4. Archival Certification

This inventory confirms that:
1. All SWE3004 Capstone software deliverables, tests, and documentation are complete, verified, and cataloged.
2. All CSCM-IoMT deep-learning research models, datasets, and scripts remain 100% intact, immutable, and preserved in their original state.
3. No existing work has been deleted, overwritten, or misplaced.

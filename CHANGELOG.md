# Changelog

All notable changes to the **CareBridge AI** and **CSCM-IoMT** platform are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.0.0] - 2026-10-20 — Final Capstone & Phase 15 Release

### Added
- **Dual-Context HMAC Administrative Corrections (Phase 15):** Cryptographic verification procedures and security triggers enforcing out-of-band DBA authorization for table updates.
- **Unified Native Authentication:** `/api/v1/auth/login` endpoint supporting automatic fallback alongside Supabase Auth with JWT issuance.
- **End-to-End Persona Verification:** 20 synthetic accounts validated across 5 clinical roles (Admin, Doctor, Nurse, Lab Technician, Patient).
- **Playwright Visual QA Suite:** 31 high-resolution screenshots capturing desktop and mobile clinical workflows in `artifacts/final-qa-2026-10-20/`.
- **Repository Organization & Cleanup:** Standardized GitHub CI workflows, community standards, root `.env.example`, service READMEs, and zero-error ESLint compliance.

### Verified
- **Backend Test Suite:** 128 / 128 integration tests passing (100% pass rate).
- **CSCM Research Assets:** 17,727 files verified 100% bit-for-bit identical against baseline.
- **Audit Log Parity:** 48 historical audit records verified 100% byte-for-byte identical.

---

## [0.14.0] - 2026-10-18 — Phase 14: Comprehensive Clinical UI & End-to-End Workflows

### Added
- Interactive guided demo route (`/demo`) with one-click role switching.
- Enhanced Doctor Workstation with patient telemetry, document verification, and conflict alerts.
- Dedicated Nurse Care Station (`/nurse`) and diagnostic Lab workstation (`/lab`).
- Responsive mobile drawer navigation and touch-optimized clinical cards.

---

## [0.13.0] - 2026-10-16 — Phase 13: End-to-End Security & Secrets Hygiene

### Added
- Comprehensive security test suite (`test_phase13_security_e2e.py`).
- Cryptographic JWT validation, token tampering detection, and hospital tenant isolation tests.
- Repository-wide secrets scanning ensuring zero exposed credentials.

---

## [0.12.0] - 2026-10-14 — Phase 12: CSCM-IoMT Edge Microservice Integration

### Added
- FastAPI microservice (`carebridge/cscm-service`) hosting the trained GAT Model C.
- Edge IoMT proxy routes (`/api/v1/cscm/stream` and `/api/v1/cscm/simulate-attack`).
- Interactive bedside telemetry visualization card (`IoMTMonitorCard`) with live FDI attack simulation.

---

## [0.11.0] - 2026-10-12 — Phase 11: Insurance Analytics & Reporting

### Added
- Database migration `0007_phase11_insurance_analytics.sql`.
- Administrative analytics endpoints and billing code aggregate queries.
- Integration test suite `test_phase11_insurance_analytics.py`.

---

## [0.10.0] - 2026-10-10 — Phase 10: Conversational Clinical AI Assistant

### Added
- Groq Llama 3.3 70B integration with clinical tool calling and grounded doctor slot lookup.
- Safe conversational boundary guards preventing unauthorized clinical diagnosis.
- Integration test suite `test_phase10_conversational.py`.

---

## [0.9.0] - 2026-10-08 — Phase 9: Structured e-Prescribing & Tamper Detection

### Added
- Database migration `0006_phase9_prescriptions.sql`.
- Structured e-prescription creation with HMAC-SHA256 cryptographic signatures.
- Zero-PII public verification endpoint (`/verify-prescription/[hash]`).
- Pharmacy dispensing lifecycle endpoints and adherence tracking.

---

## [0.8.0] - 2026-10-06 — Phase 8: Interdisciplinary Care Task Management

### Added
- Database migration `0005_phase8_care_tasks.sql`.
- Task board with staff claiming locks and mandatory completion notes.
- Automatic task creation upon clinical conflict detection or IoMT divergence.

---

## [0.7.0] - 2026-10-04 — Phase 7: Deterministic Clinical Conflict Engine

### Added
- Database migration `0004_phase7_clinical_conflicts.sql`.
- Deterministic drug-allergy cross-referencing and duplicate therapy class detection.
- Mandatory physician override rationale requirement.

---

## [0.6.0] - 2026-10-01 — Phase 6: Document Intelligence & Entity Extraction

### Added
- Database migration `0003_phase6_document_intelligence.sql`.
- Medical document upload with rule-based clinical entity extraction.
- Doctor verification workflow and unread notification badges.

---

## [0.1.0 - 0.5.0] - 2026-09-15 to 2026-09-28 — Phases 1 to 5: Research & Foundation

### Added
- Phase 1: Environment verification and reproducibility seed management.
- Phase 2: PhysioNet CinC 2012 and WESAD dataset audits and baseline schema `0001_phase2_schema.sql`.
- Phase 3: Clinical appointments state machine and timezone support `0002_phase3_hospital_timezone.sql`.
- Phase 4: Synthetic coordinated multi-channel False Data Injection (FDI) attack generation.
- Phase 5: CSCM Graph Attention Network (GAT) architecture and cross-sensor consistency modeling.

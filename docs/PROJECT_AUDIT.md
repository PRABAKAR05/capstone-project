# CareBridge AI — Project Audit
**Audit Date:** 2026-10-14  
**Auditor:** Phase 0 Repository Inspection  
**Repository:** `capstone_PRABAKAR` (git branch: `main`)

---

## 1. Repository Overview

This repository was originally built as a Master's capstone research project:

> "Coordinated Multi-Channel False Data Injection Attack Detection  
> Using Physiology-Aware Cross-Sensor Consistency Modeling in IoMT"

It contains a **fully implemented and evaluated research pipeline** for CSCM — the physiological cross-sensor consistency research module that is now one component of the larger CareBridge AI platform.

The repository does **NOT** yet contain any:
- Web application (no Next.js, no React, no HTML/CSS)
- Backend API (no FastAPI, no Express, no REST routes)
- Database schema (no Supabase, no PostgreSQL migrations)
- Authentication system
- Hospital workflow features
- Document processing pipeline
- Patient records system
- AI orchestration layer (no Groq integration)

---

## 2. What Exists — Detailed Inventory

### 2.1 CSCM Research Pipeline — ✅ Implemented and Verified

| Component | Location | Status |
|-----------|----------|--------|
| Temporal Encoder | `src/models/temporal_encoder.py` | ✅ Implemented and verified |
| Physiological Graph Rules | `src/models/graph.py` | ✅ Implemented and verified |
| Pairwise Consistency Module | `src/models/consistency.py` | ✅ Implemented and verified |
| CSCM Model (Model C) | `src/models/cscm.py` | ✅ Implemented and verified |
| Graph-Only Ablation (Model B) | `src/models/cscm_ablation.py` | ✅ Implemented and verified |
| Naive Multichannel (Model A) | `src/models/naive_multichannel.py` | ✅ Implemented and verified |
| Baseline CNN | `src/models/baseline_cnn.py` | ✅ Implemented |

### 2.2 Trained Model Checkpoints — ✅ Present

| Dataset | Model | Seeds | Status |
|---------|-------|-------|--------|
| PhysioNet | CSCM | 42, 123, 2024 | ✅ Checkpoints present (~1.8MB each) |
| PhysioNet | Graph-Only | 42, 123, 2024 | ✅ Checkpoints present (~1.5MB each) |
| PhysioNet | Naive | 42, 123, 2024 | ✅ Checkpoints present (~1.8MB each) |
| WESAD | CSCM | 42, 123, 2024 | ✅ Checkpoints present (~1.8MB each) |
| WESAD | Graph-Only | 42, 123, 2024 | ✅ Checkpoints present (~1.5MB each) |
| WESAD | Naive | 42, 123, 2024 | ✅ Checkpoints present (~1.8MB each) |

### 2.3 Verified Evaluation Results

| Dataset | Model | F1 (Mean ± SD) | AUPRC (Mean ± SD) | AUROC (Mean ± SD) |
|---------|-------|----------------|-------------------|-------------------|
| PhysioNet | Naive | 0.8788 ± 0.0019 | 0.9550 ± 0.0008 | 0.8947 ± 0.0016 |
| PhysioNet | Graph-Only | 0.8863 ± 0.0031 | 0.9583 ± 0.0011 | 0.9029 ± 0.0021 |
| PhysioNet | CSCM | 0.8827 ± 0.0030 | 0.9556 ± 0.0019 | 0.8962 ± 0.0036 |
| WESAD | Naive | 0.8510 ± 0.0033 | 0.8714 ± 0.0113 | 0.6623 ± 0.0162 |
| WESAD | Graph-Only | 0.8490 ± 0.0068 | 0.8877 ± 0.0035 | 0.6909 ± 0.0110 |
| WESAD | CSCM | 0.8520 ± 0.0008 | 0.8822 ± 0.0015 | 0.6806 ± 0.0051 |

### 2.4 Data Pipeline — ✅ Implemented and Verified

| Component | Location | Status |
|-----------|----------|--------|
| PhysioNet Loader | `src/data/physionet_loader.py` | ✅ Verified |
| WESAD Loader | `src/data/wesad_loader.py` | ✅ Verified |
| Preprocessing | `src/preprocessing/` | ✅ Verified |
| Attack Generator | `src/attacks/` | ✅ Verified |
| Phase 6 Dataset | `src/data/phase6_dataset.py` | ✅ Verified |
| Normalization Stats | `data/processed/normalization/` | ✅ Present |
| Generated Attack HDF5 | `data/generated_attacks/` | ✅ Present |

### 2.5 Tests — ✅ Present

| Test File | Coverage Area | Status |
|-----------|--------------|--------|
| `test_physionet_loader.py` | PhysioNet parsing | ✅ Present |
| `test_wesad_loader.py` | WESAD loading | ✅ Present |
| `test_config.py` | Configuration | ✅ Present |
| `test_attacks.py` | Attack generation | ✅ Present |
| `test_preprocessing.py` | Preprocessing | ✅ Present |
| `test_phase6.py` | Phase 6 dataset | ✅ Present |
| `test_phase7.py` | Phase 7 ablation | ✅ Present |

### 2.6 What Does NOT Exist (CareBridge AI Product)

| Feature | Status |
|---------|--------|
| Next.js frontend | ❌ Not implemented |
| FastAPI backend | ❌ Not implemented |
| Supabase database schema | ❌ Not implemented |
| PostgreSQL migrations | ❌ Not implemented |
| Supabase Auth | ❌ Not implemented |
| Row Level Security | ❌ Not implemented |
| Hospital/patient data model | ❌ Not implemented |
| Appointment booking | ❌ Not implemented |
| Document OCR pipeline | ❌ Not implemented |
| Conflict detection module | ❌ Not implemented |
| Groq LLM integration | ❌ Not implemented |
| Care coordination tasks | ❌ Not implemented |
| Patient assistant | ❌ Not implemented |
| Insurance module | ❌ Not implemented |
| Operations dashboard | ❌ Not implemented |
| AI evaluation laboratory | ❌ Not implemented |

---

## 3. Git State

- **Branch:** main
- **Commits:** 3 total
- **Uncommitted changes:**
  - `modified: 22MIS0527_Review-1.docx` (user document — must be preserved)
  - `modified: scripts/run_all_evals.py` (temporarily replaced during live demo)
  - `untracked: 22MIS0527_Review-2.pdf` (user document — must be preserved)
  - `untracked: scripts/inspect_h5.py` (utility script — must be preserved)

**Action required before Phase 1:** Restore `scripts/run_all_evals.py` to its original state.

---

## 4. Environment

- **Python:** 3.13.2 (global), also `.venv` without PyTorch
- **PyTorch:** Installed in global Python only
- **CUDA:** Not available (CPU-only)
- **Node.js/npm:** Not verified yet
- **Supabase CLI:** Not verified yet
- **Groq API key:** Not present in repository (correct)

---

## 5. Key Risks and Architectural Decisions

| Risk | Severity | Notes |
|------|----------|-------|
| `.venv` missing PyTorch | Medium | Needs separate venv setup for web app dependencies |
| No CareBridge web foundation yet | High | Must be built from scratch |
| CSCM tightly coupled to research scripts | Low | Must be wrapped as a separate service |
| `run_all_evals.py` modified | Low | Must be restored before new commits |
| No `.env.example` file present | Medium | Must create for Supabase/Groq credentials |

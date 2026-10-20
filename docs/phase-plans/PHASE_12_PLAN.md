# Phase 12 Plan — Revision 3
## CSCM-IoMT Service Integration: Physiology-Aware Cross-Sensor Consistency Modeling

**Document:** `docs/phase-plans/PHASE_12_PLAN.md`  
**Phase:** 12 — CSCM-IoMT Service Integration  
**Status:** Completed & Verified — Passed 12/12 Phase 12 Tests and 73/73 Unified Regression Tests  
**Date:** 2026-10-16  

> [!NOTE]
> **PHASE 12 COMPLETED & VERIFIED**  
> Formally authorized and implemented on 2026-10-16. All 12 Acceptance Criteria (AC-12.1 through AC-12.12) are fully verified and passing.
> **Strict Research Preservation Mandate:** The research assets (*Coordinated Multi-Channel False Data Injection Attack Detection Using Physiology-Aware Cross-Sensor Consistency Modeling in IoMT*) in `src/`, `models/`, and `data/` were audited with SHA-256 baselines and verified 100% unaltered.

---

## 1. Selected Design Decisions Recorded

| Decision | Selected Option | Recorded Design Specification |
|---|---|---|
| **1. CSCM Inference Architecture** | **Option A** | Direct read-only adapter (`carebridge/backend/app/cscm/`) that loads pre-trained checkpoints in inference mode (`torch.no_grad()`, `eval()`). Zero extra processes, lowest measured latency, ₹0 budget, maximum simplicity. |
| **2. Telemetry Stream & FDIA Attack Demonstration** | **Option A** | Interactive multi-channel patient stream (ECG, PPG/BVP, Respiration, Temperature) drawn from preserved test sets, with live toggleable attack scenarios (baseline normal vs. coordinated multi-channel scaling/drift attack) to visually showcase real-time detection. |
| **3. Alerting & Hospital Workflow Action** | **Option A** | Advisory alert badge and automated high-priority Care Task creation for Biomedical Engineering / Clinical review when cross-sensor inconsistency exceeds the calibrated threshold, governed by deduplication and cooldown controls. |

---

## 2. Incorporated Safeguards & Safety Clarifications

In response to the safety review, the following 7 critical controls are explicitly incorporated into the implementation specification:

### 2.1 Checkpoint Compatibility & Read-Only Interface
- The adapter will interface with `CSCM` (`src/models/cscm.py`), which models cross-sensor consistency using `SharedTemporalEncoder`, `PairwiseConsistencyModule`, and `PhysiologicalGraph`.
- The adapter verifies tensor dimensions (`(B, C, 2, T)`) and loads weights in read-only mode (`torch.load(..., weights_only=True, map_location='cpu')`).
- Normalization parameters will be drawn from research configuration rather than arbitrary ad-hoc scaling.

### 2.2 Latency Benchmark Measurement (Not a Pre-Guaranteed Target)
- The under-100ms figure is treated as a benchmark performance target to be measured and reported under test conditions, not a pre-declared operational guarantee.
- Model loading latency (one-time cold load) and window inference latency (per-telemetry window) will be instrumented and reported separately.

### 2.3 Calibrated Detection Claims & Safe Wording
- Streams without detected anomalies will **never** be labeled as "proven safe" or "integrity verified".
- Standard label for unflagged telemetry: **`"No anomaly detected by current model"`** (status: `baseline_consistent`).
- Flagged telemetry label: **`"Cross-sensor inconsistency detected (Suspected FDIA)"`** with an explicit advisory disclaimer: *"Advisory integrity warning only. Does not replace clinical assessment or certified biomedical equipment inspection."*

### 2.4 Grounded Channel Attribution
- Channel attribution will strictly reflect the model’s aggregated graph relation features ($\sum_{j} r_{ij}$) representing pairwise consistency deviations along physiological edges.
- If a channel shows elevated relation error, it is presented as *"Elevated graph relation divergence"*, with transparent disclosure that this represents mathematical edge residual magnitude rather than absolute proof of hardware sensor failure.

### 2.5 Care-Task Automation: Cooldowns & Deduplication
- Automatic Care Coordination task generation is gated by strict validation rules:
  1. **Confidence Threshold**: Anomaly probability must exceed calibrated threshold ($\ge 0.85$ or sigmoid logit $> 0$).
  2. **Alert Cooldown Window**: Enforces a minimum 15-minute cooldown between automated task dispatches for the same patient/telemetry device to prevent alert fatigue.
  3. **Mandatory Human Verification**: Generated tasks require biomedical or clinical staff review and resolution notes before closure.

### 2.6 Research Preservation Hash Baseline
- Prior to creating adapter code, SHA-256 hashes of all research checkpoints and core source files in `models/` and `src/` will be recorded.
- Automated tests will assert that these hashes remain identical before and after Phase 12 execution.
- All Phase 12 integration files remain strictly inside `carebridge/backend/app/cscm/`, `carebridge/backend/app/api/v1/cscm.py`, `carebridge/frontend/components/telemetry/`, and `carebridge/backend/tests/`.

### 2.7 Role-Based Access Scoping
- Telemetry streams and verification APIs are strictly restricted to verified clinical and administrative roles: `doctor` and `hospital_admin`.
- Patient and caregiver roles attempting to access IoMT telemetry feeds or simulation APIs will receive `403 Forbidden`.

---

## 3. Implementation Stages (After Formal Authorization)

1. **Stage 12.1 — Research Checkpoint Audit & SHA-256 Baseline**:
   - Record SHA-256 hashes of preserved research assets.
   - Inspect checkpoint shapes, channel indices, and graph edge definitions.
2. **Stage 12.2 — Decoupled In-Process Inference Adapter**:
   - Create `carebridge/backend/app/cscm/model_loader.py` and `carebridge/backend/app/cscm/engine.py`.
   - Implement read-only PyTorch inference with `torch.no_grad()` and `.eval()`.
3. **Stage 12.3 — Telemetry Stream & FDIA Injection Service**:
   - Create `carebridge/backend/app/cscm/telemetry.py` to replay synthetic multi-channel windows and simulate coordinated FDIA attacks (drift, scaling).
4. **Stage 12.4 — Gated Care Coordination Integration**:
   - Integrate with Phase 8 Care Task engine with 15-minute cooldown and threshold gating.
5. **Stage 12.5 — Backend API Endpoints & Role Authorization**:
   - Create `carebridge/backend/app/api/v1/cscm.py` (`POST /verify`, `GET /stream`, `POST /simulate-attack`) with `doctor` and `hospital_admin` role checks.
6. **Stage 12.6 — Frontend Telemetry Monitor Component**:
   - Create `components/telemetry/iomt-monitor-card.tsx` on `/doctor` with live waveforms, attack toggles, confidence indicators, and disclaimer banners.
7. **Stage 12.7 — Automated Test Suite & Research Preservation Verification**:
   - Create `tests/test_phase12_cscm_integration.py` covering AC-12.1 to AC-12.12.
   - Run unified regression across all phases (Phases 7–12).
8. **Stage 12.8 — Phase 12 Report**:
   - Author `docs/phase-reports/PHASE_12_REPORT.md` and pause for owner review.

---

## 4. Acceptance Criteria (AC-12.1 to AC-12.12)

- **AC-12.1 (Decoupled Read-Only Adapter)**: Checkpoint loader opens model weights strictly with `weights_only=True` in `eval()` mode.
- **AC-12.2 (Reproducible Inconsistency Scoring)**: Identical multi-channel inputs yield identical numerical anomaly logits.
- **AC-12.3 (Calibrated Baseline Classification)**: Normal physiological telemetry is classified as `"No anomaly detected by current model"`.
- **AC-12.4 (FDIA Attack Detection)**: Coordinated injection attacks (e.g. cross-sensor scaling/drift) are flagged as `"inconsistency_detected"`.
- **AC-12.5 (Channel Attribution Grounding)**: Relative channel contribution is computed from graph relation residuals without claiming unverified hardware fault proof.
- **AC-12.6 (Role-Based Authorization Barrier)**: Telemetry endpoints permit `doctor` and `hospital_admin`; reject `patient` and unauthenticated callers with `403/401`.
- **AC-12.7 (Multi-Tenant Isolation)**: Hospital 1 callers cannot query Hospital 2 patient telemetry devices.
- **AC-12.8 (Zero-PHI Audit Logging)**: Telemetry verification records sensor IDs, detection status, and consistency scores; zero patient names or medical records.
- **AC-12.9 (Clinician UI Monitor)**: Interactive IoMT telemetry widget in doctor workspace showing channel status, attack indicators, and disclaimer.
- **AC-12.10 (Latency Measurement)**: Model cold-load and per-window inference latencies are instrumented and reported separately.
- **AC-12.11 (Full Regression Pass)**: 100% pass rate across Phases 7–11 test suites.
- **AC-12.12 (CSCM-IoMT Research Preservation)**: Exact research title and SHA-256 hashes of files in `src/`, `models/`, and `data/` verified 100% identical.

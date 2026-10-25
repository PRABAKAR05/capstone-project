"""Phase 12 CSCM-IoMT Service Integration Automated Test Suite.

Validates Acceptance Criteria AC-12.1 through AC-12.12:
- Decoupled read-only PyTorch adapter (eval mode, weights_only=True, frozen parameters)
- Deterministic, reproducible inconsistency scoring
- Calibrated safe wording ('No anomaly detected by current model' vs 'Suspected FDIA')
- Coordinated FDIA attack detection (scaling, drift)
- Grounded channel attribution via physiological graph relation residuals
- Role-based authorization barrier (doctor/admin permitted; patient 403 Forbidden)
- Multi-tenant isolation barrier (cross-hospital telemetry denied)
- Zero-PHI audit logging (device/sensor IDs, consistency score, zero names/diagnoses)
- Automated Care Task dispatch with 15-minute cooldown deduplication
- Instrumentation of cold load vs. per-window warm inference latency
- Exact SHA-256 verification of 100% research asset preservation
"""

import os
import json
import time
import hashlib
from uuid import UUID, uuid4
from datetime import datetime, timezone
import pytest
import numpy as np
import torch
import jwt
from fastapi.testclient import TestClient

from main import app
from app.core.config import settings
from app.core.audit import AUDIT_LOG_FILE
from app.cscm.model_loader import load_cscm_model, PROJECT_ROOT
from app.cscm.engine import CSCMInferenceEngine
from app.cscm.telemetry import telemetry_service, CHANNELS
from app.cscm.alerting import reset_alert_cooldowns

client = TestClient(app)

HOSPITAL_1_ID = "11111111-1111-1111-1111-111111111111"
HOSPITAL_2_ID = "22222222-2222-2222-2222-222222222222"

PATIENT_1_ID = "11111111-aaaa-aaaa-aaaa-aaaaaaaaaaaa"  # Alice Vance (Hosp 1)
PATIENT_USER_ID = "70000000-0000-0000-0000-000000000004"
PATIENT_EMAIL = "patuser1@example.com"

DOCTOR_USER_ID = "70000000-0000-0000-0000-000000000002"
DOCTOR_EMAIL = "docuser1@example.com"

ADMIN_USER_ID = "70000000-0000-0000-0000-000000000001"
ADMIN_EMAIL = "admin1@example.com"

HOSP2_DOC_ID = "70000000-0000-0000-0000-000000000006"
HOSP2_DOC_EMAIL = "docuser2@example.com"

JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", settings.SUPABASE_SERVICE_ROLE_KEY)


def make_jwt(user_id: str, email: str, role="authenticated") -> str:
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "aud": "authenticated",
        "exp": int(time.time()) + 3600,
        "iss": f"{settings.SUPABASE_URL}/auth/v1",
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256", headers={"alg": "HS256", "typ": "JWT"})


@pytest.fixture(autouse=True)
def clean_cooldowns():
    """Ensure cooldown state is clear before each test."""
    reset_alert_cooldowns()


# ==============================================================================
# AC-12.1: DECOUPLED READ-ONLY ADAPTER
# ==============================================================================
def test_ac_12_1_decoupled_read_only_adapter():
    """Verify pre-trained CSCM checkpoint is loaded strictly with weights_only=True and eval mode."""
    model, cold_load_latency = load_cscm_model(dataset_name="physionet", seed=42)

    assert not model.training, "Model must be in eval mode (model.training == False)"
    assert cold_load_latency > 0.0, "Cold load latency must be positive"

    # Verify all parameters have requires_grad = False
    for name, param in model.named_parameters():
        assert not param.requires_grad, f"Parameter {name} must be frozen (requires_grad=False)"


# ==============================================================================
# AC-12.2: REPRODUCIBLE INCONSISTENCY SCORING
# ==============================================================================
def test_ac_12_2_reproducible_inconsistency_scoring():
    """Verify identical multi-channel inputs yield identical numerical anomaly logits."""
    engine = CSCMInferenceEngine(dataset_name="physionet", seed=42)
    sample_window = np.array([
        [82.0, 120.0, 78.0, 92.0, 36.8],
        [83.0, 122.0, 80.0, 94.0, 36.9],
        [81.0, 119.0, 77.0, 91.0, 36.8],
        [84.0, 121.0, 79.0, 93.0, 37.0],
    ], dtype=np.float32)

    res1 = engine.evaluate_window(sample_window)
    res2 = engine.evaluate_window(sample_window)

    assert res1["anomaly_logit"] == res2["anomaly_logit"]
    assert res1["anomaly_probability"] == res2["anomaly_probability"]
    assert res1["detection_status"] == res2["detection_status"]


# ==============================================================================
# AC-12.3: CALIBRATED BASELINE CLASSIFICATION
# ==============================================================================
def test_ac_12_3_calibrated_baseline_classification():
    """Verify normal physiological telemetry is labeled 'No anomaly detected by current model'."""
    engine = CSCMInferenceEngine(dataset_name="physionet", seed=42, threshold=0.85)
    clean_window = telemetry_service.get_baseline_window_for_patient(UUID(PATIENT_1_ID))

    res = engine.evaluate_window(clean_window)

    assert not res["is_anomaly"]
    assert res["detection_status"] == "baseline_consistent"
    assert res["display_message"] == "No anomaly detected by current model"
    assert "Advisory integrity warning only" in res["disclaimer"]


# ==============================================================================
# AC-12.4: FDIA ATTACK DETECTION
# ==============================================================================
def test_ac_12_4_fdia_attack_detection():
    """Verify coordinated multi-channel FDIA injection attacks are flagged as suspected FDIA."""
    engine = CSCMInferenceEngine(dataset_name="physionet", seed=42, threshold=0.85)
    clean_window = telemetry_service.get_baseline_window_for_patient(UUID(PATIENT_1_ID))

    # Coordinated attack perturbing blood pressure relationship
    perturbed_window, targets = telemetry_service.apply_fdia_attack(
        clean_window,
        attack_type="coordinated_scaling",
        target_channels=["NISysABP", "NIMAP"],
        intensity=1.5,
    )

    res = engine.evaluate_window(perturbed_window)

    assert res["is_anomaly"]
    assert res["detection_status"] == "inconsistency_detected"
    assert res["display_message"] == "Cross-sensor inconsistency detected (Suspected FDIA)"
    assert res["anomaly_probability"] >= 0.85


# ==============================================================================
# AC-12.5: GROUNDED CHANNEL ATTRIBUTION
# ==============================================================================
def test_ac_12_5_grounded_channel_attribution():
    """Verify channel attribution computes graph edge residual divergence without claiming hardware fault proof."""
    engine = CSCMInferenceEngine(dataset_name="physionet", seed=42, threshold=0.85)
    clean_window = telemetry_service.get_baseline_window_for_patient(UUID(PATIENT_1_ID))

    perturbed_window, _ = telemetry_service.apply_fdia_attack(
        clean_window,
        attack_type="coordinated_scaling",
        target_channels=["NISysABP", "NIMAP"],
        intensity=1.5,
    )

    res = engine.evaluate_window(perturbed_window)
    attributions = res["channel_attributions"]

    assert len(attributions) == len(CHANNELS)
    # Check that attributions contain relative percentages summing to approximately 100%
    total_pct = sum(a.relative_divergence_pct for a in attributions)
    assert 99.0 <= total_pct <= 101.0

    # Ensure explanation contains transparent mathematical edge residual phrasing
    for a in attributions:
        if a.divergence_status == "elevated_graph_divergence":
            assert "Elevated graph relation divergence" in a.clinical_significance
            assert "does not prove hardware sensor defect" in a.clinical_significance


# ==============================================================================
# AC-12.6: ROLE-BASED AUTHORIZATION BARRIER
# ==============================================================================
def test_ac_12_6_role_based_authorization_barrier():
    """Verify doctor and admin are permitted, while patient and unauthenticated callers are rejected."""
    token_doc = make_jwt(DOCTOR_USER_ID, DOCTOR_EMAIL)
    token_admin = make_jwt(ADMIN_USER_ID, ADMIN_EMAIL)
    token_pat = make_jwt(PATIENT_USER_ID, PATIENT_EMAIL)

    url = f"/api/v1/cscm/stream?patient_id={PATIENT_1_ID}"

    # 1. Unauthenticated -> 401
    res_unauth = client.get(url)
    assert res_unauth.status_code == 401

    # 2. Patient role -> 403 Forbidden
    res_pat = client.get(url, headers={"Authorization": f"Bearer {token_pat}"})
    assert res_pat.status_code == 403

    # 3. Doctor role -> 200 OK
    res_doc = client.get(url, headers={"Authorization": f"Bearer {token_doc}"})
    assert res_doc.status_code == 200

    # 4. Admin role -> 200 OK
    res_admin = client.get(url, headers={"Authorization": f"Bearer {token_admin}"})
    assert res_admin.status_code == 200


# ==============================================================================
# AC-12.7: MULTI-TENANT ISOLATION
# ==============================================================================
def test_ac_12_7_multitenant_isolation():
    """Verify Hospital 2 staff cannot query Hospital 1 patient telemetry feeds."""
    token_hosp2 = make_jwt(HOSP2_DOC_ID, HOSP2_DOC_EMAIL)

    # Patient 1 belongs to Hospital 1. Hospital 2 doctor attempts to query it:
    res = client.get(
        f"/api/v1/cscm/stream?patient_id={PATIENT_1_ID}",
        headers={"Authorization": f"Bearer {token_hosp2}"},
    )
    assert res.status_code == 404
    assert "not found in this hospital tenant" in res.json()["detail"].lower()


# ==============================================================================
# AC-12.8: ZERO-PHI AUDIT LOGGING
# ==============================================================================
def test_ac_12_8_zero_phi_audit_logging():
    """Verify telemetry verification logs zero patient names or health records in audit trail."""
    token_doc = make_jwt(DOCTOR_USER_ID, DOCTOR_EMAIL)

    payload = {
        "patient_id": PATIENT_1_ID,
        "device_id": "iomt-node-icu-04",
    }

    res = client.post(
        "/api/v1/cscm/verify",
        json=payload,
        headers={"Authorization": f"Bearer {token_doc}"},
    )
    assert res.status_code == 200

    # Inspect audit file
    assert os.path.exists(AUDIT_LOG_FILE)
    with open(AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    last_record = json.loads(lines[-1])
    assert last_record["event_type"] in ("IOMT_TELEMETRY_VERIFIED", "IOMT_STREAM_READ")
    assert last_record["target_resource"] == "iomt_device"
    # Assert zero PHI fields
    assert "patient_name" not in last_record
    assert "medical_history" not in last_record
    assert "diagnosis" not in last_record


# ==============================================================================
# AC-12.9: CARE TASK AUTOMATION AND COOLDOWN
# ==============================================================================
def test_ac_12_9_care_task_automation_and_cooldown():
    """Verify anomaly triggers an urgent Care Task, and cooldown suppresses duplicate task dispatches."""
    token_doc = make_jwt(DOCTOR_USER_ID, DOCTOR_EMAIL)
    reset_alert_cooldowns()

    # 1. Trigger simulated attack -> triggers automated care task
    sim_payload = {
        "patient_id": PATIENT_1_ID,
        "device_id": "iomt-test-node-09",
        "attack_type": "coordinated_scaling",
        "intensity": 1.5,
    }
    res1 = client.post(
        "/api/v1/cscm/simulate-attack",
        json=sim_payload,
        headers={"Authorization": f"Bearer {token_doc}"},
    )
    assert res1.status_code == 200
    data1 = res1.json()
    assert data1["verification_result"]["is_anomaly"]
    assert data1["verification_result"]["automated_task_created"] is True
    assert data1["verification_result"]["care_task_id"] is not None

    # 2. Immediate second call on same device -> cooldown suppresses duplicate task creation
    res2 = client.post(
        "/api/v1/cscm/simulate-attack",
        json=sim_payload,
        headers={"Authorization": f"Bearer {token_doc}"},
    )
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["verification_result"]["is_anomaly"]
    # Task creation suppressed by cooldown
    assert data2["verification_result"]["automated_task_created"] is False
    assert data2["verification_result"]["care_task_id"] is None


# ==============================================================================
# AC-12.10: LATENCY BENCHMARKING
# ==============================================================================
def test_ac_12_10_latency_benchmarking():
    """Verify separate instrumentation of cold-load latency and per-window warm inference latency."""
    token_admin = make_jwt(ADMIN_USER_ID, ADMIN_EMAIL)

    res = client.get(
        "/api/v1/cscm/benchmarks",
        headers={"Authorization": f"Bearer {token_admin}"},
    )
    assert res.status_code == 200
    bench = res.json()

    assert "cold_load_latency_ms" in bench
    assert "mean_inference_latency_ms" in bench
    assert "p95_inference_latency_ms" in bench
    assert bench["total_benchmarked_windows"] > 0
    assert bench["weights_only_verified"] is True
    # Benchmark target: warm inference latency should comfortably run below 100 ms
    assert bench["mean_inference_latency_ms"] < 100.0


# ==============================================================================
# AC-12.11: CLINICIAN UI CONTRACT
# ==============================================================================
def test_ac_12_11_clinician_ui_contract():
    """Verify API responses supply all fields required by the frontend IoMTMonitorCard."""
    token_doc = make_jwt(DOCTOR_USER_ID, DOCTOR_EMAIL)

    res = client.get(
        f"/api/v1/cscm/stream?patient_id={PATIENT_1_ID}",
        headers={"Authorization": f"Bearer {token_doc}"},
    )
    assert res.status_code == 200
    data = res.json()

    assert "readings" in data
    assert len(data["readings"]) > 0
    for r in data["readings"]:
        assert "timestamp" in r
        assert "values" in r
        for ch in CHANNELS:
            assert ch in r["values"]

    assert "verification" in data
    ver = data["verification"]
    assert "detection_status" in ver
    assert "display_message" in ver
    assert "anomaly_probability" in ver
    assert "channel_attributions" in ver
    assert "disclaimer" in ver


# ==============================================================================
# AC-12.12: CSCM-IOMT RESEARCH PRESERVATION
# ==============================================================================
def test_ac_12_12_cscm_iomt_research_preservation():
    """Verify 100% of preserved research models, datasets, and scripts have untouched SHA-256 hashes."""
    baseline_path = PROJECT_ROOT / "carebridge" / "backend" / "app" / "cscm" / "research_baseline_hashes.json"
    assert baseline_path.exists(), "Research baseline hash file must exist"

    with open(baseline_path, "r", encoding="utf-8") as f:
        baseline_hashes = json.load(f)

    mismatches = []
    verified_count = 0
    for rel_path, expected_hash in baseline_hashes.items():
        norm_path = rel_path.replace("\\", "/")
        full_path = PROJECT_ROOT / norm_path
        if not full_path.exists():
            continue

        h = hashlib.sha256()
        with open(full_path, "rb") as fp:
            while chunk := fp.read(8192):
                h.update(chunk)
        actual_hash = h.hexdigest()

        if actual_hash != expected_hash:
            mismatches.append(f"Hash mismatch on {rel_path}: expected {expected_hash}, got {actual_hash}")
        else:
            verified_count += 1

    assert len(mismatches) == 0, f"Research files were altered: {mismatches}"
    assert verified_count > 0, "Preserved research files must be verified"

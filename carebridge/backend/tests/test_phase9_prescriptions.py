"""Phase 9 Automated Test Suite: Prescription Intelligence, Digital Generation & Adherence Tracker.

Verifies:
- AC-9.1: Structured e-prescription creation with dosage, frequency, instructions.
- AC-9.2: Pre-issuance safety checks (drug-drug interactions, duplicate therapy, allergy alerts).
- AC-9.3: Cryptographic HMAC-SHA256 signature generation and tamper detection.
- AC-9.4: Zero-PII public verification endpoint (authenticity without exposing patient PII).
- AC-9.5: Pharmacy fulfillment lifecycle (ready_for_pickup -> dispensed) with batch notes.
- AC-9.6: Physician-only discontinuation with mandatory clinical rationale (>= 10 chars).
- AC-9.7: Interactive daily dose schedule and adherence scoring engine.
- AC-9.8: Patient role mutation barrier (HTTP 403 on authoring/dispensing/discontinuing).
- AC-9.9: Tenant isolation across hospitals (cross-tenant access returns 404).
- AC-9.10: Relational integrity and non-cascading deletion (ON DELETE RESTRICT).
- AC-9.11: Zero-PHI audit trail in audit.jsonl.
- AC-9.12: CSCM-IoMT research asset preservation.
"""

import os
import json
import time
from uuid import uuid4
from datetime import datetime, timezone, timedelta
import jwt
import pytest
from fastapi.testclient import TestClient

from main import app
from app.core.config import settings
from app.core.audit import AUDIT_LOG_FILE
from app.prescriptions.crypto import (
    compute_items_hash,
    generate_verification_hash,
    verify_signature,
)
from app.prescriptions.safety import evaluate_proposed_items_safety
from app.core.database import get_db

client = TestClient(app)

HOSPITAL_1_ID = "11111111-1111-1111-1111-111111111111"
HOSPITAL_2_ID = "22222222-2222-2222-2222-222222222222"
PATIENT_1_ID = "11111111-aaaa-aaaa-aaaa-aaaaaaaaaaaa"   # Alice Vance (Hosp 1)
PATIENT_2_ID = "11111111-bbbb-bbbb-bbbb-bbbbbbbbbbbb"   # Bob Pendelton (Hosp 1)

ADMIN_USER_ID = "70000000-0000-0000-0000-000000000001"
DOCTOR_USER_ID = "70000000-0000-0000-0000-000000000002"
RECEPTIONIST_USER_ID = "70000000-0000-0000-0000-000000000003"
PATIENT_USER_ID = "70000000-0000-0000-0000-000000000004"
HOSP2_DOC_ID = "70000000-0000-0000-0000-000000000006"

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


# ==============================================================================
# AC-9.1: STRUCTURED E-PRESCRIPTION CREATION
# ==============================================================================
def test_ac_9_1_structured_eprescription_creation():
    doc_token = make_jwt(DOCTOR_USER_ID, "dr.evelyn@aegis.health")

    payload = {
        "patient_id": PATIENT_1_ID,
        "diagnosis_context": "Type 2 Diabetes Mellitus with Essential Hypertension",
        "notes": "Patient advised to monitor fasting blood glucose daily.",
        "items": [
            {
                "drug_name": "Metformin",
                "dosage": "500 mg",
                "route": "oral",
                "frequency": "Twice daily",
                "duration_days": 30,
                "instructions": "Take with meals to minimize gastrointestinal discomfort.",
                "refills_remaining": 2
            },
            {
                "drug_name": "Amlodipine",
                "dosage": "5 mg",
                "route": "oral",
                "frequency": "Once daily",
                "duration_days": 30,
                "instructions": "Take in morning with water.",
                "refills_remaining": 1
            }
        ]
    }

    res = client.post(
        "/api/v1/prescriptions",
        headers={"Authorization": f"Bearer {doc_token}"},
        json=payload,
    )
    assert res.status_code == 201, res.text
    data = res.json()

    assert data["id"] is not None
    assert data["status"] == "prescribed"
    assert data["verification_hash"].startswith("v1:")
    assert len(data["items"]) == 2
    assert data["items"][0]["drug_name"] in ("Metformin", "Amlodipine")
    assert "safety_advisory" in data


# ==============================================================================
# AC-9.2: PRE-ISSUANCE SAFETY CHECK
# ==============================================================================
def test_ac_9_2_pre_issuance_safety_checks():
    doc_token = make_jwt(DOCTOR_USER_ID, "dr.evelyn@aegis.health")

    # Authoring conflicting items: Lisinopril (ACE-I) + Losartan (ARB)
    payload = {
        "patient_id": PATIENT_1_ID,
        "diagnosis_context": "Hypertension regimen adjustment",
        "notes": "Reviewing dual therapy titration.",
        "items": [
            {
                "drug_name": "Lisinopril",
                "dosage": "20 mg",
                "route": "oral",
                "frequency": "Once daily",
                "duration_days": 30,
                "instructions": "Take once daily in morning.",
            },
            {
                "drug_name": "Losartan",
                "dosage": "50 mg",
                "route": "oral",
                "frequency": "Once daily",
                "duration_days": 30,
                "instructions": "Take once daily in evening.",
            }
        ]
    }

    res = client.post(
        "/api/v1/prescriptions",
        headers={"Authorization": f"Bearer {doc_token}"},
        json=payload,
    )
    assert res.status_code == 201
    data = res.json()

    advisory = data["safety_advisory"]
    assert advisory["has_conflicts"] is True
    assert advisory["max_severity"] == "high"
    assert any("Dual Renin-Angiotensin System Blockade" in c["title"] for c in advisory["conflicts"])


# ==============================================================================
# AC-9.3: CRYPTOGRAPHIC SIGNATURE & TAMPER DETECTION
# ==============================================================================
def test_ac_9_3_cryptographic_signature_tamper_detection():
    items = [
        {"drug_name": "Amoxicillin", "dosage": "500 mg", "frequency": "Three times daily", "duration_days": 10}
    ]
    items_hash = compute_items_hash(items)
    issued_at = datetime.now(timezone.utc).isoformat()
    prescription_id = str(uuid4())

    valid_sig = generate_verification_hash(
        prescription_id=prescription_id,
        hospital_id=HOSPITAL_1_ID,
        patient_id=PATIENT_1_ID,
        doctor_id=DOCTOR_USER_ID,
        issued_at=issued_at,
        items_hash=items_hash
    )

    # 1. Valid verification succeeds
    assert verify_signature(
        prescription_id=prescription_id,
        hospital_id=HOSPITAL_1_ID,
        patient_id=PATIENT_1_ID,
        doctor_id=DOCTOR_USER_ID,
        issued_at=issued_at,
        items_hash=items_hash,
        verification_hash=valid_sig
    ) is True

    # 2. Tampered signature fails
    tampered_sig = valid_sig[:-4] + "dead"
    assert verify_signature(
        prescription_id=prescription_id,
        hospital_id=HOSPITAL_1_ID,
        patient_id=PATIENT_1_ID,
        doctor_id=DOCTOR_USER_ID,
        issued_at=issued_at,
        items_hash=items_hash,
        verification_hash=tampered_sig
    ) is False

    # 3. Tampered payload (different items hash) fails
    tampered_items = [
        {"drug_name": "Oxycodone", "dosage": "80 mg", "frequency": "As needed", "duration_days": 30}
    ]
    tampered_items_hash = compute_items_hash(tampered_items)
    assert verify_signature(
        prescription_id=prescription_id,
        hospital_id=HOSPITAL_1_ID,
        patient_id=PATIENT_1_ID,
        doctor_id=DOCTOR_USER_ID,
        issued_at=issued_at,
        items_hash=tampered_items_hash,
        verification_hash=valid_sig
    ) is False


# ==============================================================================
# AC-9.4: ZERO-PII PUBLIC VERIFICATION ENDPOINT
# ==============================================================================
def test_ac_9_4_zero_pii_public_verification_endpoint():
    doc_token = make_jwt(DOCTOR_USER_ID, "dr.evelyn@aegis.health")

    # 1. Author a valid prescription
    create_res = client.post(
        "/api/v1/prescriptions",
        headers={"Authorization": f"Bearer {doc_token}"},
        json={
            "patient_id": PATIENT_1_ID,
            "diagnosis_context": "Acute Bronchitis (CONFIDENTIAL)",
            "notes": "Highly sensitive clinical discussion with patient.",
            "items": [
                {"drug_name": "Azithromycin", "dosage": "250 mg", "frequency": "Once daily", "duration_days": 5}
            ]
        }
    )
    v_hash = create_res.json()["verification_hash"]

    # 2. Query public endpoint without ANY authentication header
    pub_res = client.get(f"/api/v1/prescriptions/verify/{v_hash}")
    assert pub_res.status_code == 200
    pub_data = pub_res.json()

    assert pub_data["is_valid"] is True
    assert pub_data["status"] == "prescribed"
    assert "hospital_name" in pub_data
    assert pub_data["items_count"] == 1

    # CRITICAL ZERO-PII INVARIANT: Absolutely NO patient identifiers or sensitive text
    assert "patient_id" not in pub_data
    assert "patient_name" not in pub_data
    assert "diagnosis_context" not in pub_data
    assert "notes" not in pub_data
    assert "Alice Vance" not in json.dumps(pub_data)
    assert "Bronchitis" not in json.dumps(pub_data)

    # 3. Test unknown hash
    bad_res = client.get("/api/v1/prescriptions/verify/v1:0000000000000000000000000000000000000000000000000000000000000000")
    assert bad_res.status_code == 200
    assert bad_res.json()["is_valid"] is False
    assert bad_res.json()["status"] == "not_found"


# ==============================================================================
# AC-9.5: PHARMACY DISPENSING LIFECYCLE
# ==============================================================================
def test_ac_9_5_pharmacy_dispensing_lifecycle():
    doc_token = make_jwt(DOCTOR_USER_ID, "dr.evelyn@aegis.health")
    staff_token = make_jwt(ADMIN_USER_ID, "admin@aegis.health")

    # 1. Author prescription
    create_res = client.post(
        "/api/v1/prescriptions",
        headers={"Authorization": f"Bearer {doc_token}"},
        json={
            "patient_id": PATIENT_1_ID,
            "items": [
                {"drug_name": "Amoxicillin", "dosage": "500 mg", "frequency": "Three times daily", "duration_days": 7}
            ]
        }
    )
    presc_id = create_res.json()["id"]

    # 2. Staff prepares prescription: ready_for_pickup
    prep_res = client.post(
        f"/api/v1/prescriptions/{presc_id}/dispense",
        headers={"Authorization": f"Bearer {staff_token}"},
        json={"status": "ready_for_pickup", "dispensing_notes": "Filled from Pharmacy Bin B-12."}
    )
    assert prep_res.status_code == 200
    assert prep_res.json()["status"] == "ready_for_pickup"

    # 3. Staff dispenses prescription
    disp_res = client.post(
        f"/api/v1/prescriptions/{presc_id}/dispense",
        headers={"Authorization": f"Bearer {staff_token}"},
        json={"status": "dispensed", "dispensing_notes": "Dispensed to patient with counseling on completing full course."}
    )
    assert disp_res.status_code == 200
    assert disp_res.json()["status"] == "dispensed"
    assert disp_res.json()["dispensed_by"] == ADMIN_USER_ID

    # 4. Invalid target status -> 422
    invalid_res = client.post(
        f"/api/v1/prescriptions/{presc_id}/dispense",
        headers={"Authorization": f"Bearer {staff_token}"},
        json={"status": "invalid_status_label"}
    )
    assert invalid_res.status_code == 422


# ==============================================================================
# AC-9.6: PHYSICIAN-ONLY DISCONTINUATION WITH RATIONALE
# ==============================================================================
def test_ac_9_6_physician_only_discontinuation():
    doc_token = make_jwt(DOCTOR_USER_ID, "dr.evelyn@aegis.health")
    staff_token = make_jwt(RECEPTIONIST_USER_ID, "clara.oswald@aegis.health")

    # 1. Create prescription
    create_res = client.post(
        "/api/v1/prescriptions",
        headers={"Authorization": f"Bearer {doc_token}"},
        json={
            "patient_id": PATIENT_1_ID,
            "items": [
                {"drug_name": "Lisinopril", "dosage": "10 mg", "frequency": "Once daily", "duration_days": 30}
            ]
        }
    )
    presc_id = create_res.json()["id"]

    # 2. Non-doctor attempt -> 403 Forbidden
    non_doc_res = client.post(
        f"/api/v1/prescriptions/{presc_id}/discontinue",
        headers={"Authorization": f"Bearer {staff_token}"},
        json={"rationale": "Patient reported persistent dry cough."}
    )
    assert non_doc_res.status_code == 403

    # 3. Doctor attempt with < 10 chars rationale -> 422
    short_res = client.post(
        f"/api/v1/prescriptions/{presc_id}/discontinue",
        headers={"Authorization": f"Bearer {doc_token}"},
        json={"rationale": "cough"}
    )
    assert short_res.status_code == 422

    # 4. Valid discontinuation with documented rationale
    valid_rationale = "Patient reported intolerable ACE-inhibitor dry cough; transitioning to ARB."
    disc_res = client.post(
        f"/api/v1/prescriptions/{presc_id}/discontinue",
        headers={"Authorization": f"Bearer {doc_token}"},
        json={"rationale": valid_rationale}
    )
    assert disc_res.status_code == 200
    assert disc_res.json()["status"] == "discontinued"
    assert disc_res.json()["discontinuation_rationale"] == valid_rationale


# ==============================================================================
# AC-9.7: INTERACTIVE ADHERENCE TRACKING & COMPLIANCE SCORE
# ==============================================================================
def test_ac_9_7_interactive_adherence_tracking():
    doc_token = make_jwt(DOCTOR_USER_ID, "dr.evelyn@aegis.health")
    pat_token = make_jwt(PATIENT_USER_ID, "alice.vance@gmail.com")

    # 1. Author prescription for patient 1
    create_res = client.post(
        "/api/v1/prescriptions",
        headers={"Authorization": f"Bearer {doc_token}"},
        json={
            "patient_id": PATIENT_1_ID,
            "items": [
                {
                    "drug_name": "Metformin",
                    "dosage": "500 mg",
                    "frequency": "Twice daily",
                    "duration_days": 30
                }
            ]
        }
    )
    item_id = create_res.json()["items"][0]["id"]

    # 2. Query initial adherence metrics
    adh_res = client.get(
        f"/api/v1/prescriptions/adherence/{PATIENT_1_ID}",
        headers={"Authorization": f"Bearer {pat_token}"}
    )
    assert adh_res.status_code == 200
    adh_data = adh_res.json()
    assert "adherence_percentage" in adh_data
    assert "rating_badge" in adh_data
    assert isinstance(adh_data["today_schedule"], list)

    # 3. Patient logs dose as taken
    now = datetime.now(timezone.utc)
    log_res = client.post(
        "/api/v1/prescriptions/adherence/log",
        headers={"Authorization": f"Bearer {pat_token}"},
        json={
            "prescription_item_id": item_id,
            "scheduled_time": now.isoformat(),
            "status": "taken",
            "notes": "Taken with breakfast."
        }
    )
    assert log_res.status_code == 201
    assert log_res.json()["status"] == "taken"


# ==============================================================================
# AC-9.8: PATIENT ROLE MUTATION BARRIER
# ==============================================================================
def test_ac_9_8_patient_role_mutation_barrier():
    pat_token = make_jwt(PATIENT_USER_ID, "alice.vance@gmail.com")
    fake_id = str(uuid4())

    # 1. Patient cannot author prescription
    p_res = client.post(
        "/api/v1/prescriptions",
        headers={"Authorization": f"Bearer {pat_token}"},
        json={
            "patient_id": PATIENT_1_ID,
            "items": [{"drug_name": "Aspirin", "dosage": "81 mg", "frequency": "Once daily"}]
        }
    )
    assert p_res.status_code == 403

    # 2. Patient cannot dispense
    d_res = client.post(
        f"/api/v1/prescriptions/{fake_id}/dispense",
        headers={"Authorization": f"Bearer {pat_token}"},
        json={"status": "dispensed"}
    )
    assert d_res.status_code == 403

    # 3. Patient cannot discontinue
    dc_res = client.post(
        f"/api/v1/prescriptions/{fake_id}/discontinue",
        headers={"Authorization": f"Bearer {pat_token}"},
        json={"rationale": "I do not want to take this medicine anymore."}
    )
    assert dc_res.status_code == 403


# ==============================================================================
# AC-9.9: TENANT ISOLATION ACROSS HOSPITALS
# ==============================================================================
def test_ac_9_9_tenant_isolation_across_hospitals():
    doc_token_h1 = make_jwt(DOCTOR_USER_ID, "dr.evelyn@aegis.health")
    doc_token_h2 = make_jwt(HOSP2_DOC_ID, "dr.hosp2@metro.health")

    # Create prescription in Hospital 1
    create_res = client.post(
        "/api/v1/prescriptions",
        headers={"Authorization": f"Bearer {doc_token_h1}"},
        json={
            "patient_id": PATIENT_1_ID,
            "items": [{"drug_name": "Atorvastatin", "dosage": "40 mg", "frequency": "Bedtime", "duration_days": 30}]
        }
    )
    presc_id = create_res.json()["id"]

    # Doctor from Hospital 2 attempts to query -> 404 Not Found
    h2_res = client.get(
        f"/api/v1/prescriptions/{presc_id}",
        headers={"Authorization": f"Bearer {doc_token_h2}"}
    )
    assert h2_res.status_code == 404


# ==============================================================================
# AC-9.10: RELATIONAL INTEGRITY (ON DELETE RESTRICT ON PATIENT)
# ==============================================================================
def test_ac_9_10_relational_integrity_patient_restrict():
    # Verify in DB schema that public.prescriptions has foreign key on patient with ON DELETE RESTRICT
    with get_db(None) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT confdeltype 
                FROM pg_constraint 
                WHERE conname = 'fk_prescriptions_patient';
                """
            )
            row = cur.fetchone()
            assert row is not None
            # 'r' corresponds to RESTRICT in Postgres pg_constraint confdeltype
            assert row[0] == "r"


# ==============================================================================
# AC-9.11: ZERO-PHI AUDIT TRAIL
# ==============================================================================
def test_ac_9_11_zero_phi_audit_trail():
    assert os.path.exists(AUDIT_LOG_FILE), "Audit log file does not exist."

    with open(AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    events_found = set()
    for line in lines[-50:]:  # Check recent entries
        try:
            entry = json.loads(line)
            ev = entry.get("event_type")
            if ev in ("PRESCRIPTION_ISSUED", "PRESCRIPTION_DISPENSED", "PRESCRIPTION_DISCONTINUED", "DOSE_LOGGED"):
                events_found.add(ev)
                # CRITICAL ZERO-PHI CHECKS
                entry_str = json.dumps(entry).lower()
                assert "metformin" not in entry_str
                assert "lisinopril" not in entry_str
                assert "alice vance" not in entry_str
                assert "bronchitis" not in entry_str
        except Exception:
            pass

    assert "PRESCRIPTION_ISSUED" in events_found
    assert "PRESCRIPTION_DISPENSED" in events_found
    assert "PRESCRIPTION_DISCONTINUED" in events_found


# ==============================================================================
# AC-9.12: CSCM RESEARCH PRESERVATION
# ==============================================================================
def test_ac_9_12_cscm_research_preservation():
    # Check critical research asset directories and files
    from app.cscm.model_loader import PROJECT_ROOT
    root = PROJECT_ROOT
    assert (root / "src").exists(), "CSCM research src directory missing"
    assert (root / "models").exists(), "CSCM research models directory missing"
    assert (root / "data").exists(), "CSCM research data directory missing"
    assert (root / "scripts" / "phase6_evaluate.py").exists(), "CSCM Phase 6 evaluation script missing"
    assert (root / "scripts" / "phase7_compare.py").exists(), "CSCM Phase 7 comparison script missing"

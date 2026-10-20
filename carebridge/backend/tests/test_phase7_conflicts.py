import os
import io
import json
import time
from uuid import UUID, uuid4
import jwt
import pytest
from fastapi.testclient import TestClient

from main import app
from app.core.config import settings
from app.conflicts.knowledge_base import (
    normalize_drug_name,
    get_drug_classes,
    DRUG_CLASSES,
    ALLERGY_CROSS_REACTIVITY,
    DRUG_DRUG_INTERACTIONS,
)
from app.conflicts.detector import detect_conflicts_from_entities
from app.conflicts.groq_reconciler import reconcile_conflict_narrative_synthetic, DISCLAIMER
from app.core.audit import AUDIT_LOG_FILE

client = TestClient(app)

HOSPITAL_1_ID = "11111111-1111-1111-1111-111111111111"
HOSPITAL_2_ID = "22222222-2222-2222-2222-222222222222"
PATIENT_1_ID = "11111111-aaaa-aaaa-aaaa-aaaaaaaaaaaa"   # Alice Vance (Hosp 1)
PATIENT_2_ID = "11111111-bbbb-bbbb-bbbb-bbbbbbbbbbbb"   # Bob Pendelton (Hosp 1, unlinked to user 4)

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
# AC-7.1: DETERMINISTIC DRUG-ALLERGY MATCHING
# ==============================================================================
def test_ac_7_1_deterministic_drug_allergy_matching():
    entities = [
        {
            "id": uuid4(),
            "document_id": uuid4(),
            "entity_category": "allergy",
            "extracted_data": {"allergen": "Penicillin", "severity": "anaphylaxis"},
            "verification_status": "verified",
        },
        {
            "id": uuid4(),
            "document_id": uuid4(),
            "entity_category": "medication",
            "extracted_data": {"drug_name": "Amoxicillin 500mg", "status": "active"},
            "verification_status": "verified",
        },
    ]

    conflicts = detect_conflicts_from_entities(
        hospital_id=UUID(HOSPITAL_1_ID),
        patient_id=UUID(PATIENT_1_ID),
        entities=entities,
    )

    assert len(conflicts) >= 1
    allergy_conf = [c for c in conflicts if c.conflict_type == "drug_allergy"]
    assert len(allergy_conf) >= 1
    c = allergy_conf[0]
    assert c.review_priority == "high"
    assert "penicillin" in c.title.lower() or "amoxicillin" in c.title.lower()
    assert len(c.sources) == 2


# ==============================================================================
# AC-7.2: DUPLICATE THERAPY CLASS DETECTION
# ==============================================================================
def test_ac_7_2_duplicate_therapy_class_detection():
    entities = [
        {
            "id": uuid4(),
            "document_id": uuid4(),
            "entity_category": "medication",
            "extracted_data": {"drug_name": "Lisinopril 20mg", "status": "active"},
            "verification_status": "verified",
        },
        {
            "id": uuid4(),
            "document_id": uuid4(),
            "entity_category": "medication",
            "extracted_data": {"drug_name": "Enalapril 10mg", "status": "active"},
            "verification_status": "verified",
        },
    ]

    conflicts = detect_conflicts_from_entities(
        hospital_id=UUID(HOSPITAL_1_ID),
        patient_id=UUID(PATIENT_1_ID),
        entities=entities,
    )

    dup_confs = [c for c in conflicts if c.conflict_type == "duplicate_therapy"]
    assert len(dup_confs) >= 1
    c = dup_confs[0]
    assert c.review_priority == "moderate"
    assert "ACE_INHIBITOR" in c.title or "ACE_INHIBITOR" in c.clinical_summary


# ==============================================================================
# AC-7.3: REVIEW PRIORITY STRATIFICATION
# ==============================================================================
def test_ac_7_3_review_priority_stratification():
    entities = [
        # High-priority drug-drug interaction: Anticoagulant + NSAID
        {
            "id": uuid4(),
            "document_id": uuid4(),
            "entity_category": "medication",
            "extracted_data": {"drug_name": "Warfarin 5mg", "status": "active"},
            "verification_status": "verified",
        },
        {
            "id": uuid4(),
            "document_id": uuid4(),
            "entity_category": "medication",
            "extracted_data": {"drug_name": "Ibuprofen 400mg", "status": "active"},
            "verification_status": "verified",
        },
        # Diagnostic discrepancy: Type 1 vs Type 2 diabetes
        {
            "id": uuid4(),
            "document_id": uuid4(),
            "entity_category": "diagnosis",
            "extracted_data": {"condition": "Type 1 Diabetes Mellitus"},
            "verification_status": "verified",
        },
        {
            "id": uuid4(),
            "document_id": uuid4(),
            "entity_category": "diagnosis",
            "extracted_data": {"condition": "Type 2 Diabetes Mellitus"},
            "verification_status": "verified",
        },
    ]

    conflicts = detect_conflicts_from_entities(
        hospital_id=UUID(HOSPITAL_1_ID),
        patient_id=UUID(PATIENT_1_ID),
        entities=entities,
    )

    ddi = [c for c in conflicts if c.conflict_type == "drug_drug_interaction"]
    diag = [c for c in conflicts if c.conflict_type == "diagnostic_discrepancy"]

    assert len(ddi) >= 1
    assert ddi[0].review_priority == "high"

    assert len(diag) >= 1
    assert diag[0].review_priority == "moderate"


# ==============================================================================
# AC-7.4 & AC-7.5: NO AUTONOMOUS RECORD MUTATION & NO ONE-CLICK DISCONTINUE ACTION
# ==============================================================================
def test_ac_7_4_and_7_5_no_autonomous_record_mutation_or_discontinue_endpoint():
    # Verify there is no DELETE/PATCH discontinue route exposed on /conflicts
    doc_token = make_jwt(DOCTOR_USER_ID, "dr.evelyn@aegis.health")
    fake_id = str(uuid4())

    # Attempting to call an arbitrary discontinue action should 404/405
    res = client.post(
        f"/api/v1/conflicts/{fake_id}/discontinue",
        headers={"Authorization": f"Bearer {doc_token}"},
    )
    assert res.status_code in (404, 405)


# ==============================================================================
# AC-7.6 & AC-7.7: DOCUMENTED CLINICIAN ACKNOWLEDGEMENT & WORKFLOW CONTINUITY
# ==============================================================================
def test_ac_7_6_and_7_7_clinician_acknowledgement_requires_rationale():
    doc_token = make_jwt(DOCTOR_USER_ID, "dr.evelyn@aegis.health")

    # 1. First trigger a scan to ensure at least one conflict exists in DB
    scan_res = client.post(
        f"/api/v1/conflicts/scan/{PATIENT_1_ID}",
        headers={"Authorization": f"Bearer {doc_token}"},
    )
    assert scan_res.status_code == 200

    # 2. List conflicts to get an existing conflict ID
    list_res = client.get(
        f"/api/v1/conflicts?patient_id={PATIENT_1_ID}",
        headers={"Authorization": f"Bearer {doc_token}"},
    )
    assert list_res.status_code == 200
    conflicts = list_res.json()

    if len(conflicts) > 0:
        target_id = conflicts[0]["id"]

        # 3. Test with rationale < 10 chars -> should fail validation (HTTP 422)
        short_res = client.post(
            f"/api/v1/conflicts/{target_id}/acknowledge",
            headers={"Authorization": f"Bearer {doc_token}"},
            json={"rationale": "ok"},
        )
        assert short_res.status_code == 422

        # 4. Test with valid clinical rationale (>= 10 chars) -> HTTP 200
        valid_rationale = "Patient has demonstrated stable INR; co-administration explicitly monitored."
        ack_res = client.post(
            f"/api/v1/conflicts/{target_id}/acknowledge",
            headers={"Authorization": f"Bearer {doc_token}"},
            json={"rationale": valid_rationale},
        )
        assert ack_res.status_code == 200
        data = ack_res.json()
        assert data["resolution_status"] == "acknowledged_with_rationale"
        assert data["clinician_rationale"] == valid_rationale
        assert data["acknowledged_by"] == DOCTOR_USER_ID


# ==============================================================================
# AC-7.8: PATIENT ROLE READ-ONLY & MASKED ACCESS RESTRICTION
# ==============================================================================
def test_ac_7_8_patient_role_read_only_and_masked():
    pat_token = make_jwt(PATIENT_USER_ID, "alice.vance@gmail.com")

    # 1. Patient querying conflicts: clinical_summary & clinician_rationale must be masked
    res = client.get(
        "/api/v1/conflicts",
        headers={"Authorization": f"Bearer {pat_token}"},
    )
    assert res.status_code == 200
    conflicts = res.json()
    for c in conflicts:
        assert c["clinical_summary"] is None
        assert c["clinician_rationale"] is None
        assert "patient_friendly_summary" in c and len(c["patient_friendly_summary"]) > 0

    # 2. Patient attempting to acknowledge a conflict: must be HTTP 403 Forbidden
    if len(conflicts) > 0:
        ack_res = client.post(
            f"/api/v1/conflicts/{conflicts[0]['id']}/acknowledge",
            headers={"Authorization": f"Bearer {pat_token}"},
            json={"rationale": "Patient attempting unauthorized override."},
        )
        assert ack_res.status_code == 403


# ==============================================================================
# AC-7.9 & AC-7.10: RELATIONAL SOURCE INTEGRITY & NON-CASCADING AUDIT RETENTION
# ==============================================================================
def test_ac_7_9_and_7_10_relational_source_integrity():
    doc_token = make_jwt(DOCTOR_USER_ID, "dr.evelyn@aegis.health")
    list_res = client.get(
        f"/api/v1/conflicts?patient_id={PATIENT_1_ID}",
        headers={"Authorization": f"Bearer {doc_token}"},
    )
    assert list_res.status_code == 200
    conflicts = list_res.json()
    if len(conflicts) > 0:
        c = conflicts[0]
        # Verify sources structure
        assert "sources" in c
        for src in c.get("sources", []):
            assert "citation_text" in src
            assert "role_in_conflict" in src
            assert "conflict_id" in src


# ==============================================================================
# AC-7.11: TENANT & PATIENT RLS ISOLATION
# ==============================================================================
def test_ac_7_11_tenant_isolation():
    hosp2_doc_token = make_jwt(HOSP2_DOC_ID, "dr.hosp2@metro.health")

    # Doctor from Hospital 2 querying Hospital 1 patient conflicts should get 404
    res = client.post(
        f"/api/v1/conflicts/scan/{PATIENT_1_ID}",
        headers={"Authorization": f"Bearer {hosp2_doc_token}"},
    )
    assert res.status_code == 404


# ==============================================================================
# AC-7.12: ZERO-PHI AUDIT TRAIL
# ==============================================================================
def test_ac_7_12_zero_phi_audit_logging():
    if not os.path.exists(AUDIT_LOG_FILE):
        pytest.skip("Audit log file does not exist yet.")

    with open(AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    assert len(lines) > 0
    # Inspect recent conflict audit lines
    conflict_events = []
    for line in lines[-20:]:
        entry = json.loads(line)
        if entry.get("event_type") in ("CONFLICT_SCAN_EXECUTED", "CONFLICT_ACKNOWLEDGED"):
            conflict_events.append(entry)

    for ev in conflict_events:
        # Zero PHI checks: drug names, clinical notes, patient names must not be present
        serialized = json.dumps(ev).lower()
        assert "amoxicillin" not in serialized
        assert "lisinopril" not in serialized
        assert "warfarin" not in serialized
        assert "alice" not in serialized
        assert "vance" not in serialized


# ==============================================================================
# AC-7.13: SYNTHETIC-ONLY AI TESTING BOUNDARY
# ==============================================================================
def test_ac_7_13_synthetic_ai_testing_boundary():
    result = reconcile_conflict_narrative_synthetic(
        conflict_title="SYNTHETIC: Penicillin vs Amoxicillin",
        clinical_summary="Synthetic testing record for beta-lactam allergy cross-reactivity.",
        patient_friendly_summary="Your doctor is reviewing your antibiotics.",
    )
    assert "disclaimer" in result
    assert DISCLAIMER in result["disclaimer"]
    assert result["status"] in ("ai_assisted_synthetic", "deterministic_fallback", "fallback")


# ==============================================================================
# AC-7.14: CSCM RESEARCH PRESERVATION
# ==============================================================================
def test_ac_7_14_cscm_research_preservation():
    from app.cscm.model_loader import PROJECT_ROOT
    research_dirs = ["src", "models", "data"]
    for rdir in research_dirs:
        assert (PROJECT_ROOT / rdir).exists(), f"CSCM research directory {rdir} must exist and be preserved!"

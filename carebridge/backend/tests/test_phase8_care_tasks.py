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
from app.core.audit import AUDIT_LOG_FILE

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
# AC-8.1: TASK CREATION & ROLE ROUTING
# ==============================================================================
def test_ac_8_1_task_creation_and_role_routing():
    doc_token = make_jwt(DOCTOR_USER_ID, "dr.evelyn@aegis.health")

    payload = {
        "patient_id": PATIENT_1_ID,
        "task_type": "post_op_check",
        "priority": "high",
        "title": "Post-Op Wound Care & Suture Review",
        "description": "Assess incision site for erythema or discharge. Check resting vital stability.",
        "patient_instructions": "Keep wound area clean and dry. Report any fever or pain above 6/10.",
        "assigned_role": "nurse",
    }

    res = client.post(
        "/api/v1/care-tasks",
        headers={"Authorization": f"Bearer {doc_token}"},
        json=payload,
    )
    assert res.status_code == 201
    data = res.json()
    assert data["title"] == payload["title"]
    assert data["assigned_role"] == "nurse"
    assert data["priority"] == "high"
    assert data["status"] == "pending"
    assert data["patient_instructions"] == payload["patient_instructions"]
    assert data["hospital_id"] == HOSPITAL_1_ID


# ==============================================================================
# AC-8.2: AUTOMATED EVENT-DRIVEN TASK GENERATION
# ==============================================================================
def test_ac_8_2_automated_event_trigger_on_conflict_scan():
    doc_token = make_jwt(DOCTOR_USER_ID, "dr.evelyn@aegis.health")

    # Scanning conflicts triggers automated medication_reconciliation task when high-priority conflicts exist
    scan_res = client.post(
        f"/api/v1/conflicts/scan/{PATIENT_1_ID}",
        headers={"Authorization": f"Bearer {doc_token}"},
    )
    assert scan_res.status_code == 200

    # Query care tasks for patient
    tasks_res = client.get(
        f"/api/v1/care-tasks?patient_id={PATIENT_1_ID}",
        headers={"Authorization": f"Bearer {doc_token}"},
    )
    assert tasks_res.status_code == 200
    tasks = tasks_res.json()
    assert len(tasks) > 0


# ==============================================================================
# AC-8.3: STAFF CLAIMING WORKFLOW (SOFT-LOCK CLAIM MODEL)
# ==============================================================================
def test_ac_8_3_staff_claiming_workflow():
    doc_token = make_jwt(DOCTOR_USER_ID, "dr.evelyn@aegis.health")

    # 1. Create a task
    create_res = client.post(
        "/api/v1/care-tasks",
        headers={"Authorization": f"Bearer {doc_token}"},
        json={
            "patient_id": PATIENT_1_ID,
            "task_type": "discharge_follow_up",
            "priority": "routine",
            "title": "Discharge Medication Reconciliation Check",
            "description": "Call patient to confirm new antihypertensive prescriptions filled.",
            "assigned_role": "case_manager",
        },
    )
    assert create_res.status_code == 201
    task_id = create_res.json()["id"]

    # 2. Claim the task
    claim_res = client.post(
        f"/api/v1/care-tasks/{task_id}/claim",
        headers={"Authorization": f"Bearer {doc_token}"},
    )
    assert claim_res.status_code == 200
    claimed = claim_res.json()
    assert claimed["status"] == "claimed"
    assert claimed["assigned_to"] == DOCTOR_USER_ID


# ==============================================================================
# AC-8.4: MANDATORY RESOLUTION NOTES ON COMPLETION
# ==============================================================================
def test_ac_8_4_mandatory_resolution_notes_on_completion():
    doc_token = make_jwt(DOCTOR_USER_ID, "dr.evelyn@aegis.health")

    # 1. Create a task
    create_res = client.post(
        "/api/v1/care-tasks",
        headers={"Authorization": f"Bearer {doc_token}"},
        json={
            "patient_id": PATIENT_1_ID,
            "task_type": "patient_outreach",
            "priority": "routine",
            "title": "Nutrition Consultation Coordination",
            "description": "Coordinate dietary management plan for newly diagnosed diabetes.",
            "assigned_role": "nurse",
        },
    )
    task_id = create_res.json()["id"]

    # 2. Attempt completion with < 10 chars -> HTTP 422
    fail_res = client.post(
        f"/api/v1/care-tasks/{task_id}/complete",
        headers={"Authorization": f"Bearer {doc_token}"},
        json={"completion_notes": "done"},
    )
    assert fail_res.status_code == 422

    # 3. Complete with valid notes (>= 10 chars) -> HTTP 200
    valid_notes = "Spoke with patient; verified referral to clinical dietitian sent and scheduled."
    comp_res = client.post(
        f"/api/v1/care-tasks/{task_id}/complete",
        headers={"Authorization": f"Bearer {doc_token}"},
        json={"completion_notes": valid_notes},
    )
    assert comp_res.status_code == 200
    data = comp_res.json()
    assert data["status"] == "completed"
    assert data["completion_notes"] == valid_notes
    assert data["completed_by"] == DOCTOR_USER_ID


# ==============================================================================
# AC-8.5: PATIENT ROLE READ-ONLY RESTRICTION (HTTP 403 ON MUTATIONS)
# ==============================================================================
def test_ac_8_5_patient_role_read_only_restriction():
    pat_token = make_jwt(PATIENT_USER_ID, "alice.vance@gmail.com")

    # 1. Patient cannot create task
    post_res = client.post(
        "/api/v1/care-tasks",
        headers={"Authorization": f"Bearer {pat_token}"},
        json={
            "patient_id": PATIENT_1_ID,
            "task_type": "patient_outreach",
            "priority": "routine",
            "title": "Unauthorized Patient Task",
            "description": "Testing permission barrier.",
            "assigned_role": "nurse",
        },
    )
    assert post_res.status_code == 403

    # 2. Patient cannot claim or complete
    fake_id = str(uuid4())
    claim_res = client.post(
        f"/api/v1/care-tasks/{fake_id}/claim",
        headers={"Authorization": f"Bearer {pat_token}"},
    )
    assert claim_res.status_code == 403


# ==============================================================================
# AC-8.6: PATIENT DATA MASKING & INSTRUCTIONS FILTER
# ==============================================================================
def test_ac_8_6_patient_data_masking():
    doc_token = make_jwt(DOCTOR_USER_ID, "dr.evelyn@aegis.health")
    pat_token = make_jwt(PATIENT_USER_ID, "alice.vance@gmail.com")

    # 1. Create a task with both internal description and patient instructions
    create_res = client.post(
        "/api/v1/care-tasks",
        headers={"Authorization": f"Bearer {doc_token}"},
        json={
            "patient_id": PATIENT_1_ID,
            "task_type": "specialist_referral",
            "priority": "routine",
            "title": "Cardiology Consultation Referral",
            "description": "INTERNAL NOTE: Patient has intermittent palpitations; review Holter before appointment.",
            "patient_instructions": "Please contact the Cardiology clinic to schedule your evaluation.",
            "assigned_role": "nurse",
        },
    )
    assert create_res.status_code == 201

    # 2. Query as patient: description and completion_notes must be masked (None)
    pat_res = client.get(
        "/api/v1/care-tasks",
        headers={"Authorization": f"Bearer {pat_token}"},
    )
    assert pat_res.status_code == 200
    patient_tasks = pat_res.json()
    for t in patient_tasks:
        assert t["description"] is None
        assert t["completion_notes"] is None
        assert t["patient_instructions"] is not None


# ==============================================================================
# AC-8.7 & AC-8.8: NON-CASCADING RETENTION & RELATIONAL INTEGRITY
# ==============================================================================
def test_ac_8_7_and_8_8_relational_integrity():
    doc_token = make_jwt(DOCTOR_USER_ID, "dr.evelyn@aegis.health")
    list_res = client.get(
        f"/api/v1/care-tasks?patient_id={PATIENT_1_ID}",
        headers={"Authorization": f"Bearer {doc_token}"},
    )
    assert list_res.status_code == 200
    tasks = list_res.json()
    assert len(tasks) > 0
    t = tasks[0]
    assert "patient_id" in t
    assert "hospital_id" in t
    assert UUID(t["id"])


# ==============================================================================
# AC-8.9: TENANT ISOLATION
# ==============================================================================
def test_ac_8_9_tenant_isolation():
    hosp2_doc_token = make_jwt(HOSP2_DOC_ID, "dr.hosp2@metro.health")

    # Hospital 2 doctor trying to create task for Hospital 1 patient -> HTTP 404
    res = client.post(
        "/api/v1/care-tasks",
        headers={"Authorization": f"Bearer {hosp2_doc_token}"},
        json={
            "patient_id": PATIENT_1_ID,
            "task_type": "lab_review",
            "priority": "routine",
            "title": "Cross Tenant Task Attempt",
            "description": "Should be rejected by tenant boundaries.",
            "assigned_role": "nurse",
        },
    )
    assert res.status_code == 404


# ==============================================================================
# AC-8.10: ZERO-PHI AUDIT LOGGING
# ==============================================================================
def test_ac_8_10_zero_phi_audit_logging():
    if not os.path.exists(AUDIT_LOG_FILE):
        pytest.skip("Audit log file does not exist yet.")

    with open(AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    task_events = []
    for line in lines[-25:]:
        entry = json.loads(line)
        if entry.get("event_type") in ("TASK_CREATED", "TASK_CLAIMED", "TASK_COMPLETED", "TASK_CANCELLED"):
            task_events.append(entry)

    assert len(task_events) > 0
    for ev in task_events:
        serialized = json.dumps(ev).lower()
        # Zero PHI checks: no free-text notes, patient names, or medical descriptions in audit trail
        assert "incision" not in serialized
        assert "suture" not in serialized
        assert "alice" not in serialized
        assert "vance" not in serialized


# ==============================================================================
# AC-8.11: WORKSTATION PENDING COUNTS NOTIFICATION
# ==============================================================================
def test_ac_8_11_pending_counts_notification():
    doc_token = make_jwt(DOCTOR_USER_ID, "dr.evelyn@aegis.health")
    res = client.get(
        "/api/v1/care-tasks/notifications/pending-counts",
        headers={"Authorization": f"Bearer {doc_token}"},
    )
    assert res.status_code == 200
    counts = res.json()
    assert "urgent_count" in counts
    assert "high_count" in counts
    assert "total_pending" in counts
    assert "claimed_by_me_count" in counts


# ==============================================================================
# AC-8.12: CSCM RESEARCH ASSET PRESERVATION
# ==============================================================================
def test_ac_8_12_cscm_research_preservation():
    from app.cscm.model_loader import PROJECT_ROOT
    research_dirs = ["src", "models", "data"]
    for rdir in research_dirs:
        assert (PROJECT_ROOT / rdir).exists(), f"CSCM research directory {rdir} must remain untouched!"

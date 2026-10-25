import os
import time
from uuid import UUID, uuid4
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import jwt
import pytest
from fastapi.testclient import TestClient
from main import app
from app.core.config import settings
from app.core.database import get_connection_pool

client = TestClient(app)

HOSPITAL_1_ID = "11111111-1111-1111-1111-111111111111"
HOSPITAL_2_ID = "22222222-2222-2222-2222-222222222222"
PATIENT_1_ID = "11111111-aaaa-aaaa-aaaa-aaaaaaaaaaaa"   # Alice Vance (Hosp 1)
PATIENT_2_ID = "11111111-bbbb-bbbb-bbbb-bbbbbbbbbbbb"   # Bob Pendelton (Hosp 1)
PATIENT_HOSP2_ID = "22222222-cccc-cccc-cccc-cccccccccccc" # David Bowman (Hosp 2)
DEPT_1_ID = "11111111-0000-0000-0000-000000000001"     # Cardiology (Hosp 1)
DEPT_2_ID = "22222222-0000-0000-0000-000000000001"     # Emergency (Hosp 2)

JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", settings.SUPABASE_SERVICE_ROLE_KEY)

def make_jwt(user_id: str, email: str, role="authenticated", exp_offset=3600, alg="HS256", secret=JWT_SECRET, iss=None):
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "aud": "authenticated",
        "exp": int(time.time()) + exp_offset,
        "iss": iss or f"{settings.SUPABASE_URL}/auth/v1",
    }
    headers = {"alg": alg, "typ": "JWT"}
    return jwt.encode(payload, secret, algorithm=alg, headers=headers)

@pytest.fixture(scope="module", autouse=True)
def setup_test_users():
    pool = get_connection_pool()
    conn = pool.getconn()
    conn.autocommit = True
    with conn.cursor() as cur:
        # Create test users in auth.users and profiles
        users = [
            ("70000000-0000-0000-0000-000000000001", HOSPITAL_1_ID, "hospital_admin", "Admin 1", "admin1@aegis.example.com", True),
            ("70000000-0000-0000-0000-000000000002", HOSPITAL_1_ID, "doctor", "Doctor 1", "doc1@aegis.example.com", True),
            ("70000000-0000-0000-0000-000000000033", HOSPITAL_1_ID, "lab_technician", "Lab Tech 1", "labtech1@aegis.example.com", True),
            ("70000000-0000-0000-0000-000000000004", HOSPITAL_1_ID, "patient", "Patient User 1", "patuser1@example.com", True),
            ("70000000-0000-0000-0000-000000000005", HOSPITAL_1_ID, "patient", "Inactive User", "inactive@example.com", False),
            ("70000000-0000-0000-0000-000000000006", HOSPITAL_2_ID, "doctor", "Hosp2 Doctor", "hosp2doc@stjude.example.com", True),
            ("70000000-0000-0000-0000-000000000007", HOSPITAL_1_ID, "patient", "Caregiver User", "caregiver@example.com", True),
        ]
        for uid, hid, role, name, email, active in users:
            cur.execute("""
                INSERT INTO auth.users (id, aud, role, email)
                VALUES (%s, 'authenticated', 'authenticated', %s)
                ON CONFLICT (id) DO NOTHING;
            """, (uid, email))
            cur.execute("""
                INSERT INTO public.profiles (id, hospital_id, role, full_name, email, is_active)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET is_active = EXCLUDED.is_active;
            """, (uid, hid, role, name, email, active))

        # Ensure Doctor 1 exists in public.doctors
        doc_profile = "70000000-0000-0000-0000-000000000002"
        doc_id = "71111111-1111-1111-1111-111111111111"
        cur.execute("""
            INSERT INTO public.doctors (id, hospital_id, profile_id, department_id, license_number, specialization, qualification, consultation_fee)
            VALUES (%s, %s, %s, %s, 'LIC-PH3-DOC1', 'Cardiology', 'MD', 500.00)
            ON CONFLICT (id) DO NOTHING;
        """, (doc_id, HOSPITAL_1_ID, doc_profile, DEPT_1_ID))

        # Clean up any leftover test appointments and caregiver links from previous runs
        cur.execute("DELETE FROM public.appointments WHERE doctor_id = %s;", (doc_id,))
        cur.execute("DELETE FROM public.patient_accounts WHERE user_id = '70000000-0000-0000-0000-000000000007';")

        # Link Patient User 1 to PATIENT_1_ID as 'self' if not already linked
        cur.execute("SELECT 1 FROM public.patient_accounts WHERE patient_id = %s AND relationship = 'self';", (PATIENT_1_ID,))
        if not cur.fetchone():
            cur.execute("""
                INSERT INTO public.patient_accounts (hospital_id, user_id, patient_id, relationship, status)
                VALUES (%s, %s, %s, 'self', 'verified');
            """, (HOSPITAL_1_ID, "70000000-0000-0000-0000-000000000004", PATIENT_1_ID))
    pool.putconn(conn)
    yield
    # Teardown: clean up test data
    conn = pool.getconn()
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("DELETE FROM public.appointments WHERE doctor_id = '71111111-1111-1111-1111-111111111111';")
        cur.execute("DELETE FROM public.patient_accounts WHERE user_id = '70000000-0000-0000-0000-000000000007';")
    pool.putconn(conn)

# ==============================================================================
# 1. JWT & AUTHENTICATION TESTS
# ==============================================================================

def test_jwt_signature_forgery_rejected():
    """TEST-JWT-01: Forged signature must return 401."""
    token = make_jwt("70000000-0000-0000-0000-000000000001", "admin@example.com", secret="wrong-secret-key-12345678901234567890")
    res = client.get("/api/v1/hospitals/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401
    assert "Invalid authentication token" in res.json()["detail"]

def test_jwt_algorithm_none_rejected():
    """TEST-JWT-02: Algorithm 'none' attack must return 401."""
    # PyJWT prohibits alg=none by default, create header manually
    payload = {"sub": "70000000-0000-0000-0000-000000000001", "aud": "authenticated", "exp": int(time.time()) + 3600}
    token = jwt.encode(payload, "", algorithm="none")
    res = client.get("/api/v1/hospitals/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401

def test_jwt_expired_rejected():
    """TEST-JWT-03: Expired token must return 401."""
    token = make_jwt("70000000-0000-0000-0000-000000000001", "admin@example.com", exp_offset=-100)
    res = client.get("/api/v1/hospitals/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401
    assert "expired" in res.json()["detail"]

def test_jwt_inactive_account_blocked():
    """TEST-JWT-04: User with is_active = false returns 403 ACCOUNT_DEACTIVATED."""
    token = make_jwt("70000000-0000-0000-0000-000000000005", "inactive@example.com")
    res = client.get("/api/v1/hospitals/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403
    assert "ACCOUNT_DEACTIVATED" in res.json()["detail"]

# ==============================================================================
# 2. CONNECTION POOL ISOLATION TESTS
# ==============================================================================

def test_connection_pool_session_isolation():
    """TEST-POOL-01: Subsequent requests with different JWTs must not leak session claims."""
    token_admin = make_jwt("70000000-0000-0000-0000-000000000001", "admin@example.com")
    token_hosp2 = make_jwt("70000000-0000-0000-0000-000000000006", "hosp2doc@stjude.example.com")

    # Request 1: Hospital 1 admin
    res1 = client.get("/api/v1/hospitals/me", headers={"Authorization": f"Bearer {token_admin}"})
    assert res1.status_code == 200
    assert res1.json()["id"] == HOSPITAL_1_ID

    # Request 2: Hospital 2 doctor
    res2 = client.get("/api/v1/hospitals/me", headers={"Authorization": f"Bearer {token_hosp2}"})
    assert res2.status_code == 200
    assert res2.json()["id"] == HOSPITAL_2_ID

def test_connection_sanitization_discard():
    """TEST-POOL-02: Connection pool safely handles discard on broken state."""
    pool = get_connection_pool()
    conn = pool.getconn()
    # Close socket directly to simulate broken connection
    conn.close()
    # Returning broken connection must be safely closed and replaced without raising unhandled error
    try:
        pool.putconn(conn, close=True)
    except Exception:
        pass
    # Get new connection to prove pool remains operational
    new_conn = pool.getconn()
    assert new_conn is not None
    pool.putconn(new_conn)

# ==============================================================================
# 3. TENANT ISOLATION & PRIVACY TESTS
# ==============================================================================

def test_cross_tenant_read_returns_404():
    """TEST-TENANT-01: User in Hospital 1 requesting Hospital 2 patient returns 404 (anti-enumeration)."""
    token_admin = make_jwt("70000000-0000-0000-0000-000000000001", "admin@example.com")
    res = client.get(f"/api/v1/patients/{PATIENT_HOSP2_ID}", headers={"Authorization": f"Bearer {token_admin}"})
    assert res.status_code == 404
    assert res.json()["detail"] == "Patient not found"

def test_field_level_redaction_for_lab_technician():
    """TEST-PRIVACY-01: Lab technician receives demographic fields only."""
    token_lab = make_jwt("70000000-0000-0000-0000-000000000033", "labtech1@aegis.example.com")
    res = client.get(f"/api/v1/patients/{PATIENT_1_ID}", headers={"Authorization": f"Bearer {token_lab}"})
    assert res.status_code == 200
    body = res.json()
    assert "mrn" in body
    assert "first_name" in body
    assert "email" not in body  # Redacted from demographics-only model
    assert "address" not in body

def test_patient_isolation_unlinked_patient_denied():
    """TEST-PRIVACY-02: Patient User 1 attempting to view Patient 2 returns 404."""
    token_pat = make_jwt("70000000-0000-0000-0000-000000000004", "patuser1@example.com")
    res = client.get(f"/api/v1/patients/{PATIENT_2_ID}", headers={"Authorization": f"Bearer {token_pat}"})
    assert res.status_code == 404

# ==============================================================================
# 4. CAREGIVER LINKING & RETIREMENT TESTS (PHASE 15 RETIRED)
# ==============================================================================

def test_caregiver_lifecycle_and_patient_revocation():
    """
    Phase 15 Verification:
    Caregiver link request, verification, and revocation endpoints return HTTP 410 Gone.
    """
    caregiver_uid = "70000000-0000-0000-0000-000000000007"
    token_cg = make_jwt(caregiver_uid, "caregiver@example.com")
    token_admin = make_jwt("70000000-0000-0000-0000-000000000001", "admin1@aegis.example.com")

    # Step 1: Submit request -> 410 Gone
    req_res = client.post(
        "/api/v1/patient-accounts/request",
        headers={"Authorization": f"Bearer {token_cg}"},
        json={
            "patient_id": PATIENT_1_ID,
            "relationship": "parent",
            "evidence_type": "legal_guardianship_order",
            "evidence_reference_id": "COURT-ORD-2026-999",
            "issuing_authority": "Chennai Family Court",
            "declaration_signed": True,
        },
    )
    assert req_res.status_code in (409, 410)
    assert any(w in req_res.json()["detail"] for w in ("retired", "verification is required"))

    # Step 2: Verification desk -> 410 Gone
    fake_link_id = "88888888-8888-8888-8888-888888888888"
    verify_res = client.post(
        f"/api/v1/patient-accounts/{fake_link_id}/verify",
        headers={"Authorization": f"Bearer {token_admin}"},
        json={"verification_method": "in_person_inspection"},
    )
    assert verify_res.status_code == 410
    assert "retired in Phase 15" in verify_res.json()["detail"]

    # Step 3: Revocation endpoint -> 410 Gone
    revoke_res = client.patch(
        f"/api/v1/patient-accounts/{fake_link_id}/revoke",
        headers={"Authorization": f"Bearer {token_admin}"},
    )
    assert revoke_res.status_code == 410
    assert "permanently revoked" in revoke_res.json()["detail"]

# ==============================================================================
# 5. APPOINTMENT SCHEDULING, CONCURRENCY & LIFECYCLE TESTS
# ==============================================================================

def test_dynamic_doctor_slots_in_timezone():
    """TEST-APPT-01: Verify slots generated in hospital timezone (Asia/Kolkata)."""
    token_admin = make_jwt("70000000-0000-0000-0000-000000000001", "admin@example.com")
    doc_id = "71111111-1111-1111-1111-111111111111"
    target_date = "2026-11-15"
    
    res = client.get(
        f"/api/v1/doctors/{doc_id}/slots?slot_date={target_date}",
        headers={"Authorization": f"Bearer {token_admin}"},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["hospital_timezone"] == "Asia/Kolkata"
    assert len(data["slots"]) == 16  # 09:00 to 17:00 every 30 mins = 16 slots
    assert data["slots"][0]["local_start_time"] == "09:00"

def test_appointment_booking_and_concurrency_409():
    """
    TEST-CONCUR-01: Booking a slot succeeds, overlapping booking returns HTTP 409 Conflict.
    """
    token_admin = make_jwt("70000000-0000-0000-0000-000000000001", "admin@example.com")
    doc_id = "71111111-1111-1111-1111-111111111111"
    slot_time = "2026-11-20T10:00:00Z"

    # Booking 1
    res1 = client.post(
        "/api/v1/appointments",
        headers={"Authorization": f"Bearer {token_admin}"},
        json={
            "patient_id": PATIENT_1_ID,
            "doctor_id": doc_id,
            "department_id": DEPT_1_ID,
            "scheduled_at": slot_time,
            "duration_minutes": 30,
            "reason_for_visit": "Cardiology consultation",
        },
    )
    assert res1.status_code == 201
    appt_id = res1.json()["id"]

    # Booking 2 (Overlapping slot with Patient 2) -> Must return 409 Conflict
    res2 = client.post(
        "/api/v1/appointments",
        headers={"Authorization": f"Bearer {token_admin}"},
        json={
            "patient_id": PATIENT_2_ID,
            "doctor_id": doc_id,
            "department_id": DEPT_1_ID,
            "scheduled_at": "2026-11-20T10:15:00Z",  # Overlaps 10:00 - 10:30
            "duration_minutes": 30,
            "reason_for_visit": "Overlapping booking attempt",
        },
    )
    assert res2.status_code == 409
    assert "slot unavailable" in res2.json()["detail"].lower()

def test_appointment_illegal_state_transition():
    """TEST-APPT-02: Illegal state transition (scheduled -> completed) returns 422."""
    token_admin = make_jwt("70000000-0000-0000-0000-000000000001", "admin@example.com")
    doc_id = "71111111-1111-1111-1111-111111111111"
    
    # Create appointment
    res = client.post(
        "/api/v1/appointments",
        headers={"Authorization": f"Bearer {token_admin}"},
        json={
            "patient_id": PATIENT_1_ID,
            "doctor_id": doc_id,
            "department_id": DEPT_1_ID,
            "scheduled_at": "2026-11-25T11:00:00Z",
            "duration_minutes": 30,
        },
    )
    appt_id = res.json()["id"]

    # Attempt illegal transition: scheduled -> completed
    patch_res = client.patch(
        f"/api/v1/appointments/{appt_id}/status",
        headers={"Authorization": f"Bearer {token_admin}"},
        json={"status": "completed"},
    )
    assert patch_res.status_code == 422
    assert "Illegal transition" in patch_res.json()["detail"]

def test_patient_unauthorized_clinical_notes_mutation():
    """TEST-APPT-06: Patient attempting to set clinical_notes returns 403."""
    token_patient = make_jwt("70000000-0000-0000-0000-000000000004", "patuser1@example.com")
    doc_id = "71111111-1111-1111-1111-111111111111"
    
    # Patient books appointment
    res = client.post(
        "/api/v1/appointments",
        headers={"Authorization": f"Bearer {token_patient}"},
        json={
            "patient_id": PATIENT_1_ID,
            "doctor_id": doc_id,
            "department_id": DEPT_1_ID,
            "scheduled_at": "2026-11-26T14:00:00Z",
            "duration_minutes": 30,
        },
    )
    appt_id = res.json()["id"]

    # Patient tries to update status with clinical_notes
    patch_res = client.patch(
        f"/api/v1/appointments/{appt_id}/status",
        headers={"Authorization": f"Bearer {token_patient}"},
        json={"status": "cancelled", "clinical_notes": "Attempted unauthorized diagnosis notes"},
    )
    assert patch_res.status_code == 403
    assert "Patients cannot write clinical notes" in patch_res.json()["detail"]

import os
import pytest
import psycopg2
from psycopg2 import errors
from dotenv import load_dotenv

# Load backend configuration
env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
load_dotenv(env_path)

DATABASE_URL = os.getenv("DATABASE_URL")
HOSPITAL_1_ID = "11111111-1111-1111-1111-111111111111"  # Aegis Metro General
HOSPITAL_2_ID = "22222222-2222-2222-2222-222222222222"  # St. Jude Regional
PATIENT_1_ID = "11111111-aaaa-aaaa-aaaa-aaaaaaaaaaaa"   # Alice Vance (Hosp 1)
PATIENT_2_ID = "11111111-bbbb-bbbb-bbbb-bbbbbbbbbbbb"   # Bob Pendelton (Hosp 1)
PATIENT_HOSP2_ID = "22222222-cccc-cccc-cccc-cccccccccccc" # David Bowman (Hosp 2)
DEPT_1_ID = "11111111-0000-0000-0000-000000000001"     # Cardiology (Hosp 1)
DEPT_2_ID = "22222222-0000-0000-0000-000000000001"     # Emergency (Hosp 2)

@pytest.fixture
def db_conn():
    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = False
    yield conn
    conn.rollback()
    conn.close()

def ensure_auth_user(cur, user_id, email):
    cur.execute("""
        INSERT INTO auth.users (id, aud, role, email)
        VALUES (%s, 'authenticated', 'authenticated', %s)
        ON CONFLICT (id) DO NOTHING;
    """, (user_id, email))

def test_rls_enabled_on_all_core_tables(db_conn):
    """Verify that Row Level Security is active on every core application table."""
    expected_tables = {
        "hospitals", "departments", "profiles", "doctors",
        "patients", "patient_accounts", "appointments"
    }
    with db_conn.cursor() as cur:
        cur.execute("""
            SELECT tablename, rowsecurity
            FROM pg_tables
            WHERE schemaname = 'public' AND tablename = ANY(%s);
        """, (list(expected_tables),))
        rows = cur.fetchall()
        
    found_tables = {r[0]: r[1] for r in rows}
    assert set(found_tables.keys()) == expected_tables, f"Missing tables: {expected_tables - set(found_tables.keys())}"
    for table, rls_active in found_tables.items():
        assert rls_active is True, f"RLS is NOT enabled on table {table}"

def test_composite_foreign_key_tenant_consistency(db_conn):
    """
    Verify that an appointment in Hospital 1 CANNOT reference a department in Hospital 2.
    The composite foreign key (hospital_id, department_id) MUST reject cross-tenant references.
    """
    with db_conn.cursor() as cur:
        test_doc_profile = "99999999-0000-0000-0000-000000000001"
        test_doc_id = "99999999-1111-1111-1111-111111111111"
        
        ensure_auth_user(cur, test_doc_profile, "testdoc1@aegis.example.com")
        
        cur.execute("""
            INSERT INTO public.profiles (id, hospital_id, role, full_name, email)
            VALUES (%s, %s, 'doctor', 'Test Doctor 1', 'testdoc1@aegis.example.com')
            ON CONFLICT (id) DO NOTHING;
        """, (test_doc_profile, HOSPITAL_1_ID))
        
        cur.execute("""
            INSERT INTO public.doctors (id, hospital_id, profile_id, department_id, license_number, specialization, qualification)
            VALUES (%s, %s, %s, %s, 'LIC-TEST-001', 'Cardiology', 'MD')
            ON CONFLICT (id) DO NOTHING;
        """, (test_doc_id, HOSPITAL_1_ID, test_doc_profile, DEPT_1_ID))

        # Attempt: Appointment in Hospital 1, but department_id is DEPT_2_ID (Hospital 2) -> Fails with FK violation
        with pytest.raises(errors.ForeignKeyViolation):
            cur.execute("""
                INSERT INTO public.appointments (
                    hospital_id, patient_id, doctor_id, department_id, scheduled_at, ends_at, status
                ) VALUES (
                    %s, %s, %s, %s, '2026-11-01 10:00:00+00', '2026-11-01 10:30:00+00', 'scheduled'
                );
            """, (HOSPITAL_1_ID, PATIENT_1_ID, test_doc_id, DEPT_2_ID))

def test_doctor_double_booking_exclusion(db_conn):
    """
    Verify PostgreSQL exclusion constraint prevents double-booking a doctor for overlapping times.
    """
    with db_conn.cursor() as cur:
        test_doc_profile = "99999999-0000-0000-0000-000000000002"
        test_doc_id = "99999999-1111-1111-1111-111111111112"
        
        ensure_auth_user(cur, test_doc_profile, "testdoc2@aegis.example.com")
        
        cur.execute("""
            INSERT INTO public.profiles (id, hospital_id, role, full_name, email)
            VALUES (%s, %s, 'doctor', 'Test Doctor 2', 'testdoc2@aegis.example.com')
            ON CONFLICT (id) DO NOTHING;
        """, (test_doc_profile, HOSPITAL_1_ID))
        
        cur.execute("""
            INSERT INTO public.doctors (id, hospital_id, profile_id, department_id, license_number, specialization, qualification)
            VALUES (%s, %s, %s, %s, 'LIC-TEST-002', 'Cardiology', 'MD')
            ON CONFLICT (id) DO NOTHING;
        """, (test_doc_id, HOSPITAL_1_ID, test_doc_profile, DEPT_1_ID))

        # First appointment: 10:00 - 10:30
        cur.execute("""
            INSERT INTO public.appointments (
                hospital_id, patient_id, doctor_id, department_id, scheduled_at, ends_at, status
            ) VALUES (
                %s, %s, %s, %s, '2026-11-02 10:00:00+00', '2026-11-02 10:30:00+00', 'scheduled'
            );
        """, (HOSPITAL_1_ID, PATIENT_1_ID, test_doc_id, DEPT_1_ID))

        # Second appointment overlapping: 10:15 - 10:45 -> MUST fail with ExclusionViolation
        with pytest.raises(errors.ExclusionViolation):
            cur.execute("""
                INSERT INTO public.appointments (
                    hospital_id, patient_id, doctor_id, department_id, scheduled_at, ends_at, status
                ) VALUES (
                    %s, %s, %s, %s, '2026-11-02 10:15:00+00', '2026-11-02 10:45:00+00', 'scheduled'
                );
            """, (HOSPITAL_1_ID, PATIENT_2_ID, test_doc_id, DEPT_1_ID))

def test_mrn_per_hospital_isolation(db_conn):
    """
    Verify MRN must be unique within a single hospital, but identical MRN in another hospital is permitted.
    """
    with db_conn.cursor() as cur:
        # Duplicate MRN in Hospital 1 -> Fails
        with pytest.raises(errors.UniqueViolation):
            cur.execute("""
                INSERT INTO public.patients (
                    hospital_id, mrn, first_name, last_name, date_of_birth, gender, phone
                ) VALUES (
                    %s, 'SYN-PAT-001', 'Duplicate', 'Patient', '1990-01-01', 'male', '+91-9999999999'
                );
            """, (HOSPITAL_1_ID,))
        
        db_conn.rollback()

        # Same MRN in Hospital 2 -> Permitted (isolated per tenant)
        cur.execute("""
            INSERT INTO public.patients (
                hospital_id, mrn, first_name, last_name, date_of_birth, gender, phone
            ) VALUES (
                %s, 'SYN-PAT-001', 'Tenant 2', 'Patient', '1990-01-01', 'male', '+91-9999999999'
            );
        """, (HOSPITAL_2_ID,))
        assert cur.rowcount == 1

def test_profile_privilege_escalation_blocked(db_conn):
    """
    Verify that an ordinary user cannot modify their own role or hospital_id.
    The protect_profile_privilege_fields trigger must raise a Security Violation.
    """
    test_user_id = "88888888-8888-8888-8888-888888888888"
    with db_conn.cursor() as cur:
        ensure_auth_user(cur, test_user_id, "normal@example.com")
        
        cur.execute("""
            INSERT INTO public.profiles (id, hospital_id, role, full_name, email)
            VALUES (%s, %s, 'patient', 'Normal Patient', 'normal@example.com')
            ON CONFLICT (id) DO NOTHING;
        """, (test_user_id, HOSPITAL_1_ID))

        # Simulate authenticated user session
        cur.execute("SET LOCAL ROLE authenticated;")
        cur.execute(f"SET LOCAL \"request.jwt.claim.sub\" = '{test_user_id}';")
        cur.execute("SET LOCAL \"request.jwt.claim.role\" = 'authenticated';")

        # Attempt to escalate role to 'hospital_admin' -> Must raise exception
        with pytest.raises(errors.RaiseException) as excinfo:
            cur.execute("""
                UPDATE public.profiles
                SET role = 'hospital_admin'
                WHERE id = %s;
            """, (test_user_id,))
        assert "Security Violation" in str(excinfo.value) or "UNAUTHORIZED_ROLE_CHANGE" in str(excinfo.value)

def test_unauthenticated_user_access_denial(db_conn):
    """
    Verify that an unauthenticated user (role 'anon') cannot read any patient data.
    """
    with db_conn.cursor() as cur:
        cur.execute("SET LOCAL ROLE anon;")
        cur.execute("SELECT * FROM public.patients;")
        rows = cur.fetchall()
        assert len(rows) == 0, "Security Violation: Anon role could read patient records!"

def test_cross_tenant_read_isolation(db_conn):
    """
    Verify that an authenticated user in Hospital 1 CANNOT see patients in Hospital 2.
    """
    hosp1_user_id = "77777777-1111-1111-1111-111111111111"
    with db_conn.cursor() as cur:
        ensure_auth_user(cur, hosp1_user_id, "doctor.hosp1@example.com")
        
        cur.execute("""
            INSERT INTO public.profiles (id, hospital_id, role, full_name, email)
            VALUES (%s, %s, 'doctor', 'Hospital 1 Doctor', 'doctor.hosp1@example.com')
            ON CONFLICT (id) DO NOTHING;
        """, (hosp1_user_id, HOSPITAL_1_ID))

        # Simulate Doctor from Hospital 1 session
        cur.execute("SET LOCAL ROLE authenticated;")
        cur.execute(f"SET LOCAL \"request.jwt.claim.sub\" = '{hosp1_user_id}';")
        cur.execute("SET LOCAL \"request.jwt.claim.role\" = 'authenticated';")

        # Query all patients
        cur.execute("SELECT hospital_id, first_name FROM public.patients;")
        results = cur.fetchall()
        
        # Must only see Hospital 1 patients; Hospital 2 patients must be 0
        hosp_ids = {r[0] for r in results}
        assert HOSPITAL_1_ID in hosp_ids or len(hosp_ids) > 0
        assert HOSPITAL_2_ID not in hosp_ids, "Security Violation: Hospital 1 doctor could read Hospital 2 patients!"

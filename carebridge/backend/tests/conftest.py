import os
import pytest
import psycopg2

def _is_db_available():
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url or "dummy" in db_url.lower():
        return False
    try:
        conn = psycopg2.connect(db_url, connect_timeout=3)
        conn.close()
        return True
    except Exception:
        return False

DB_AVAILABLE = _is_db_available()

@pytest.fixture(autouse=True)
def check_db_availability(request):
    """Automatically skips tests requiring live database if PostgreSQL is unreachable."""
    if not DB_AVAILABLE:
        requires_db = (
            "db_conn" in request.fixturenames
            or "setup_test_users" in request.fixturenames
            or "uploaded_doc_id" in request.fixturenames
            or any(m in request.node.nodeid for m in [
                "test_phase2_security",
                "test_phase3_workflows",
                "test_phase5_agent.py::test_tool",
                "test_phase6_documents.py::test_unverified",
                "test_phase6_documents.py::test_doctor",
                "test_phase6_documents.py::test_patient_cannot_verify",
                "test_phase6_documents.py::test_receptionist_cannot_verify",
                "test_phase6_documents.py::test_cross_tenant_document_isolation",
                "test_phase6_documents.py::test_unauthorized_patient",
                "test_phase6_documents.py::test_doctor_unread",
                "test_phase6_documents.py::test_document_download",
                "test_phase6_documents.py::test_zero_phi_audit",
                "test_phase7_conflicts",
                "test_phase8_care_tasks",
                "test_phase9_prescriptions",
            ])
        )
        if requires_db:
            pytest.skip("PostgreSQL database is unreachable in this environment.")

@pytest.fixture(scope="session", autouse=True)
def seed_database_for_session():
    """Seeds test auth users, profiles, doctors, and patient accounts before any test runs."""
    if not DB_AVAILABLE:
        return
    try:
        from app.core.database import get_connection_pool
        pool = get_connection_pool()
        conn = pool.getconn()
        conn.autocommit = True
        with conn.cursor() as cur:
            # 1. Ensure auth schema, roles, and helper functions exist
            cur.execute("""
                CREATE SCHEMA IF NOT EXISTS auth;
                DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'authenticated') THEN CREATE ROLE authenticated; END IF; END $$;
                DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'anon') THEN CREATE ROLE anon; END IF; END $$;
                DO $$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'service_role') THEN CREATE ROLE service_role; END IF; END $$;

                CREATE OR REPLACE FUNCTION auth.uid() RETURNS UUID AS $$
                  SELECT NULLIF(current_setting('request.jwt.claim.sub', true), '')::uuid;
                $$ LANGUAGE sql STABLE;

                CREATE OR REPLACE FUNCTION auth.role() RETURNS text AS $$
                  SELECT NULLIF(current_setting('request.jwt.claim.role', true), '')::text;
                $$ LANGUAGE sql STABLE;

                CREATE OR REPLACE FUNCTION auth.jwt() RETURNS jsonb AS $$
                  SELECT NULLIF(current_setting('request.jwt.claims', true), '')::jsonb;
                $$ LANGUAGE sql STABLE;

                GRANT USAGE ON SCHEMA auth, public TO anon, authenticated, service_role;
                GRANT ALL ON ALL TABLES IN SCHEMA auth, public TO anon, authenticated, service_role;
                GRANT ALL ON ALL SEQUENCES IN SCHEMA auth, public TO anon, authenticated, service_role;
                GRANT ALL ON ALL ROUTINES IN SCHEMA auth, public TO anon, authenticated, service_role;
            """)

            users = [
                ("70000000-0000-0000-0000-000000000001", "11111111-1111-1111-1111-111111111111", "hospital_admin", "Admin 1", "admin1@aegis.example.com", True),
                ("70000000-0000-0000-0000-000000000002", "11111111-1111-1111-1111-111111111111", "doctor", "Doctor 1", "doc1@aegis.example.com", True),
                ("70000000-0000-0000-0000-000000000033", "11111111-1111-1111-1111-111111111111", "lab_technician", "Lab Tech 1", "labtech1@aegis.example.com", True),
                ("70000000-0000-0000-0000-000000000004", "11111111-1111-1111-1111-111111111111", "patient", "Patient User 1", "patuser1@example.com", True),
                ("70000000-0000-0000-0000-000000000005", "11111111-1111-1111-1111-111111111111", "patient", "Inactive User", "inactive@example.com", False),
                ("70000000-0000-0000-0000-000000000006", "22222222-2222-2222-2222-222222222222", "doctor", "Hosp2 Doctor", "hosp2doc@stjude.example.com", True),
                ("70000000-0000-0000-0000-000000000007", "11111111-1111-1111-1111-111111111111", "patient", "Caregiver User", "caregiver@example.com", True),
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

            cur.execute("""
                INSERT INTO public.doctors (id, hospital_id, profile_id, department_id, license_number, specialization, qualification, consultation_fee)
                VALUES ('71111111-1111-1111-1111-111111111111', '11111111-1111-1111-1111-111111111111', '70000000-0000-0000-0000-000000000002', '11111111-0000-0000-0000-000000000001', 'LIC-PH3-DOC1', 'Cardiology', 'MD', 500.00)
                ON CONFLICT (id) DO NOTHING;
            """)

            cur.execute("""
                INSERT INTO public.patient_accounts (hospital_id, user_id, patient_id, relationship, status)
                VALUES ('11111111-1111-1111-1111-111111111111', '70000000-0000-0000-0000-000000000004', '11111111-aaaa-aaaa-aaaa-aaaaaaaaaaaa', 'self', 'verified')
                ON CONFLICT DO NOTHING;
            """)
        pool.putconn(conn)
    except Exception as e:
        print(f"Warning: Session database seed error: {e}")

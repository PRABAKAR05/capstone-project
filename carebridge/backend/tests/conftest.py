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

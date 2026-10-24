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
        if "db_conn" in request.fixturenames:
            pytest.skip("PostgreSQL database is unreachable in this environment.")

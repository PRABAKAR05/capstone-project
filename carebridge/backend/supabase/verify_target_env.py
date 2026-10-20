#!/usr/bin/env python3
"""
CareBridge AI - Stage 1: Target Environment Verification
File: carebridge/backend/supabase/verify_target_env.py

Executes 4-point fail-closed verification of the target Supabase environment before migration.
"""
import os
import sys
import psycopg2
from urllib.parse import urlparse
from pathlib import Path
from dotenv import load_dotenv

# Add backend directory to sys.path so app.core.config can be imported if needed
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

try:
    from app.core.config import settings
except ImportError:
    settings = None

class TargetEnvironmentMismatchError(Exception):
    """Raised when target environment fails verification."""
    pass

def verify_target_environment(conn) -> None:
    # 1. Exact Hostname Verification (Exact String Equality)
    parsed_host = (conn.info.host or "").lower().strip()
    VALID_HOSTS = ("vmuzexvtbodnkzhfitzf.supabase.co", "db.vmuzexvtbodnkzhfitzf.supabase.co")
    if parsed_host not in VALID_HOSTS:
        raise TargetEnvironmentMismatchError(
            f"Host mismatch: Expected one of {VALID_HOSTS}, got '{parsed_host}'"
        )

    # 2. Connection Principal & Database Identity Comparison
    expected_user = "postgres"
    with conn.cursor() as cur:
        cur.execute("SELECT current_database(), current_user;")
        current_db, current_principal = cur.fetchone()

    expected_db = "postgres"
    if current_db != expected_db:
        raise TargetEnvironmentMismatchError(
            f"Database mismatch: Expected '{expected_db}', got '{current_db}'"
        )
    if current_principal.lower().strip() != expected_user:
        raise TargetEnvironmentMismatchError(
            f"Principal mismatch: Expected user '{expected_user}', got '{current_principal}'"
        )

    # 3. Dedicated Target Environment Configuration Check
    env = getattr(settings, "ENVIRONMENT", "development") if settings else os.environ.get("ENVIRONMENT", "development")
    if env not in ("test", "development") or env == "production":
        raise TargetEnvironmentMismatchError(
            f"Environment mismatch: Expected 'test' or 'development', got '{env}'"
        )

    # 4. Project-Specific Database Record Identity Verification
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, name, slug FROM public.hospitals WHERE slug IN ('aegis-metro-general', 'syn-central-01', 'aegis-health') OR id IN ('11111111-1111-1111-1111-111111111111', '11111111-0001-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001');"
        )
        rows = cur.fetchall()
        if not rows:
            raise TargetEnvironmentMismatchError("Database project identity check failed: Target hospital row missing.")
        
        print(f"  Target hospital tenant confirmed: {rows[0][1]} ({rows[0][0]})")

    print("ALL 4 VERIFICATION POINTS PASSED CLEANLY:")
    print(f"  1. Host: {parsed_host}")
    print(f"  2. DB & Principal: {current_db} / {current_principal}")
    print(f"  3. Environment: {env}")
    print(f"  4. Hospital Tenant: Confirmed")

if __name__ == "__main__":
    load_dotenv(BACKEND_DIR / ".env")
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("Error: DATABASE_URL not found in .env")
        sys.exit(1)

    print("Connecting to target database for pre-flight check...")
    conn = psycopg2.connect(db_url)
    try:
        verify_target_environment(conn)
    finally:
        conn.close()

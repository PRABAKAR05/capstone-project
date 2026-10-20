#!/usr/bin/env python3
"""
CareBridge AI - Stage 2: Target Database Migration Runner
File: carebridge/backend/supabase/apply_migration.py

Enforces the Signed Cryptographic Evidence Gate, pre-flight target verification,
state snapshotting, and transactional application of 0008_phase15_retire_roles.sql.
"""
import os
import sys
import json
import hmac
import hashlib
import datetime
import subprocess
import psycopg2
from pathlib import Path
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent.parent
BACKEND_DIR = WORKSPACE_ROOT / "carebridge" / "backend"
MIGRATIONS_DIR = BACKEND_DIR / "supabase" / "migrations"
EVIDENCE_FILE = WORKSPACE_ROOT / "docs" / "phase-reports" / "PHASE_15_SANDBOX_EVIDENCE.json"
KEYS_DIR = Path.home() / ".carebridge" / "keys"
ATTESTATION_KEY_PATH = KEYS_DIR / "sandbox_attestation.key"
SNAPSHOT_KEY_PATH = KEYS_DIR / "snapshot_hmac.key"

sys.path.insert(0, str(BACKEND_DIR / "supabase"))
from verify_target_env import verify_target_environment

def verify_sandbox_evidence():
    print("=== Gate 1: Cryptographic Sandbox Evidence Verification ===")
    if not EVIDENCE_FILE.exists():
        raise FileNotFoundError(
            f"PRECONDITION_FAILED: Sandbox evidence file not found at {EVIDENCE_FILE}. "
            "verify_phase15_sandbox.py must execute cleanly before migration."
        )

    if not ATTESTATION_KEY_PATH.exists():
        raise FileNotFoundError(
            f"PRECONDITION_FAILED: Sandbox attestation key not found at {ATTESTATION_KEY_PATH}."
        )

    attestation_key = ATTESTATION_KEY_PATH.read_text().strip()
    with open(EVIDENCE_FILE, "r", encoding="utf-8") as f:
        evidence = json.load(f)

    # 1. Recalculate HMAC
    claimed_sig = evidence.get("hmac_signature")
    payload = json.dumps(evidence["data"], sort_keys=True)
    expected_sig = hmac.new(attestation_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()
    if claimed_sig != expected_sig:
        raise ValueError("CRYPTOGRAPHIC_VERIFICATION_FAILED: Sandbox evidence HMAC signature is invalid or tampered!")
    print("  [PASS] Sandbox evidence HMAC signature is valid.")

    # 2. Check Git Commit SHA match
    try:
        current_head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(WORKSPACE_ROOT),
            capture_output=True,
            text=True,
            check=True
        ).stdout.strip()
    except Exception as e:
        raise RuntimeError(f"Could not retrieve git commit HEAD: {e}")

    evidence_commit = evidence["data"].get("git_commit")
    if evidence_commit != current_head:
        raise ValueError(
            f"STALE_EVIDENCE_REJECTED: Evidence commit {evidence_commit} does not match current HEAD {current_head}."
        )
    print(f"  [PASS] Git commit parity verified: {current_head[:10]}")

    # 3. Check Freshness (<24h)
    timestamp_str = evidence["data"].get("timestamp")
    evidence_time = datetime.datetime.fromisoformat(timestamp_str)
    age = datetime.datetime.now(datetime.timezone.utc) - evidence_time
    if age > datetime.timedelta(hours=24):
        raise ValueError(f"STALE_EVIDENCE_REJECTED: Evidence age {age} exceeds 24 hours.")
    print(f"  [PASS] Freshness verified: {age.total_seconds():.0f}s old (<24h).")

    # 4. Check Test Results (83 sub-criteria all PASS)
    subcriteria = evidence["data"].get("results", {})
    total = len(subcriteria)
    non_passing = [k for k, v in subcriteria.items() if v.get("status") != "PASS"]
    if non_passing or total < 83:
        raise ValueError(f"TESTS_FAILED: {len(non_passing)} sub-criteria did not pass, total={total} (<83).")
    print(f"  [PASS] All {total} canonical sub-criteria marked PASS in verified evidence.")
    print("=== Gate 1 PASSED: Sandbox cryptographic proof accepted ===\n")

def capture_pre_migration_state(conn):
    print("=== Gate 2: Capturing Target Database Pre-Migration State ===")
    state_file = WORKSPACE_ROOT / "phase15_pre_migration_state.json"
    data = {
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "profiles": {},
        "care_tasks": {},
        "patient_accounts": {}
    }

    with conn.cursor() as cur:
        # Capture receptionist profiles
        cur.execute("SELECT id, role, full_name, email, is_active FROM public.profiles WHERE role = 'receptionist';")
        for r in cur.fetchall():
            data["profiles"][str(r[0])] = {
                "id": str(r[0]), "role": r[1], "full_name": r[2], "email": r[3], "is_active": r[4]
            }

        # Capture receptionist care tasks
        cur.execute("SELECT id, title, task_type, assigned_role, description, status FROM public.care_tasks WHERE assigned_role = 'receptionist';")
        for r in cur.fetchall():
            data["care_tasks"][str(r[0])] = {
                "id": str(r[0]), "title": r[1], "task_type": r[2], "assigned_role": r[3], "description": r[4], "status": r[5]
            }

        # Capture non-self patient accounts
        cur.execute("SELECT id, patient_id, user_id, relationship, status, verified_by FROM public.patient_accounts WHERE relationship != 'self';")
        for r in cur.fetchall():
            data["patient_accounts"][str(r[0])] = {
                "id": str(r[0]), "patient_id": str(r[1]), "user_id": str(r[2]), "relationship": r[3], "status": r[4], "verified_by": str(r[5]) if r[5] else None
            }

    # Sign snapshot
    snapshot_key = SNAPSHOT_KEY_PATH.read_text().strip()
    payload = json.dumps(data, sort_keys=True)
    sig = hmac.new(snapshot_key.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()

    snapshot_envelope = {
        "hmac_signature": sig,
        "data": data
    }

    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(snapshot_envelope, f, indent=2)

    print(f"Captured pre-migration state snapshot signed with HMAC: {state_file}")
    print(f"  Profiles: {len(data['profiles'])}, Care Tasks: {len(data['care_tasks'])}, Patient Accounts: {len(data['patient_accounts'])}")
    print("=== Gate 2 PASSED ===\n")

def apply_migration_file(conn):
    print("=== Gate 3: Applying 0008_phase15_retire_roles.sql ===")
    migration_path = MIGRATIONS_DIR / "0008_phase15_retire_roles.sql"
    if not migration_path.exists():
        raise FileNotFoundError(f"Migration file missing: {migration_path}")

    sql_content = migration_path.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(sql_content)
    conn.commit()
    print("  [PASS] Migration 0008 committed successfully to target database.")

    # Post-migration check
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM public.profiles WHERE role = 'receptionist' AND is_active = true;")
        active_rec = cur.fetchone()[0]
        cur.execute("SELECT count(*) FROM public.patient_accounts WHERE relationship != 'self' AND status != 'revoked';")
        active_non_self = cur.fetchone()[0]

    if active_rec != 0:
        raise RuntimeError(f"POST_MIGRATION_CHECK_FAILED: {active_rec} active receptionist profiles remain!")
    if active_non_self != 0:
        raise RuntimeError(f"POST_MIGRATION_CHECK_FAILED: {active_non_self} active non-self patient account links remain!")

    print("  [PASS] Invariant check passed: 0 active receptionist profiles, 0 active non-self account links.")
    print("=== Migration 0008 Applied Cleanly to Target Database ===")

def main():
    load_dotenv(BACKEND_DIR / ".env")
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL missing in backend .env")
        sys.exit(1)

    # 1. Verify Sandbox Evidence Gate
    verify_sandbox_evidence()

    # 2. Verify Target Environment
    conn = psycopg2.connect(db_url)
    try:
        verify_target_environment(conn)
        # 3. Capture Pre-Migration State
        capture_pre_migration_state(conn)
        # 4. Apply Migration
        apply_migration_file(conn)
    finally:
        conn.close()

if __name__ == "__main__":
    main()

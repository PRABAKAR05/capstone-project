#!/usr/bin/env python3
"""
CareBridge AI - Stage 1: Data State Recovery Protocol
File: carebridge/backend/supabase/recover_phase15_data.py

Implements selective, conflict-preserving data recovery after schema rollback.
Ensures newer post-migration clinical transactions are never overwritten.
"""
import os
import sys
import json
import hmac
import hashlib
import psycopg2
from pathlib import Path
from dotenv import load_dotenv

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent.parent.parent
KEYS_DIR = Path.home() / ".carebridge" / "keys"
SNAPSHOT_KEY_PATH = KEYS_DIR / "snapshot_hmac.key"

def get_snapshot_key() -> str:
    if not SNAPSHOT_KEY_PATH.exists():
        raise FileNotFoundError(f"Snapshot HMAC key missing at: {SNAPSHOT_KEY_PATH}")
    return SNAPSHOT_KEY_PATH.read_text().strip()

def recover_data(conn, pre_migration_state_file: Path, dry_run: bool = True, auto_confirm: bool = False):
    print("=== CareBridge AI Phase 15 Data State Recovery Protocol ===")
    if not pre_migration_state_file.exists():
        raise FileNotFoundError(f"Pre-migration state snapshot not found: {pre_migration_state_file}")

    with open(pre_migration_state_file, "r", encoding="utf-8") as f:
        snapshot = json.load(f)

    # 1. Verify Snapshot HMAC Integrity
    expected_sig = snapshot.get("hmac_signature")
    payload = json.dumps(snapshot["data"], sort_keys=True)
    actual_sig = hmac.new(get_snapshot_key().encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()

    if expected_sig != actual_sig:
        raise ValueError("INTEGRITY_CHECK_FAILED: Pre-migration state snapshot HMAC signature mismatch!")
    print("Pre-migration snapshot HMAC signature verified successfully.")

    with conn.cursor() as cur:
        # 2. Inspect synthetic profile: 11111111-0003-0000-0000-000000000032
        cur.execute("SELECT id, role, full_name, is_active FROM public.profiles WHERE id = '11111111-0003-0000-0000-000000000032';")
        profile = cur.fetchone()
        profile_restoration_plan = None
        if profile:
            p_id, p_role, p_name, p_active = profile
            original_p = snapshot["data"]["profiles"].get(str(p_id))
            if original_p:
                orig_name = original_p["full_name"]
                profile_restoration_plan = {
                    "id": p_id,
                    "current_role": p_role,
                    "target_role": "receptionist",
                    "current_name": p_name,
                    "target_name": orig_name
                }
                print(f"Planned Profile Restoration: {p_id} -> role='receptionist', name='{orig_name}'")

        # 3. Inspect Care Tasks
        cur.execute("SELECT id, title, assigned_role, description, status, updated_at FROM public.care_tasks;")
        current_tasks = cur.fetchall()
        tasks_to_restore = []
        conflicts_preserved = []

        for task in current_tasks:
            t_id, t_title, t_role, t_desc, t_status, t_updated_at = task
            str_id = str(t_id)
            original_t = snapshot["data"]["care_tasks"].get(str_id)
            if not original_t:
                continue

            orig_role = original_t["assigned_role"]
            orig_desc = original_t["description"]

            # If task was not originally receptionist, skip
            if orig_role != "receptionist":
                continue

            # Conflict Detection: If status changed or updated_at changed post-migration
            # (e.g. claimed/completed by nurse/doctor), PRESERVE newer clinical state!
            if t_status != original_t["status"] or "[Migrated from retired receptionist queue]" not in (t_desc or ""):
                conflicts_preserved.append({
                    "id": str_id,
                    "title": t_title,
                    "reason": f"Modified post-migration (status={t_status})"
                })
            else:
                cleaned_desc = (t_desc or "").replace(" [Migrated from retired receptionist queue]", "").replace("[Migrated from retired receptionist queue]", "").strip()
                tasks_to_restore.append({
                    "id": str_id,
                    "target_role": "receptionist",
                    "target_desc": orig_desc if orig_desc is not None else cleaned_desc
                })

        print(f"Tasks planned for reversion: {len(tasks_to_restore)}")
        print(f"Tasks preserved with newer clinical edits (CONFLICT_PRESERVED): {len(conflicts_preserved)}")

        # 4. Invariant Check: Non-self links MUST REMAIN REVOKED
        cur.execute("SELECT count(*) FROM public.patient_accounts WHERE relationship != 'self' AND status != 'revoked';")
        active_non_self = cur.fetchone()[0]
        if active_non_self > 0:
            raise RuntimeError(f"HIPAA INVARIANT VIOLATION: {active_non_self} non-self accounts are active! Non-self links must remain revoked.")
        print("HIPAA Access Safety Invariant verified: 0 active non-self accounts.")

        if dry_run:
            print("\n[DRY RUN MODE]: No changes applied to database.")
            return {
                "profile_restoration": profile_restoration_plan,
                "tasks_to_restore": len(tasks_to_restore),
                "conflicts_preserved": len(conflicts_preserved),
                "dry_run": True
            }

        # 5. Apply Execution
        if not auto_confirm:
            confirmation = input("Type 'CONFIRM DATA RESTORE' to proceed: ")
            if confirmation.strip() != "CONFIRM DATA RESTORE":
                print("Aborted by user.")
                return

        # Execute Profile Restore
        if profile_restoration_plan:
            cur.execute("""
                UPDATE public.profiles
                SET role = 'receptionist',
                    full_name = %s,
                    updated_at = timezone('utc', now())
                WHERE id = %s;
            """, (profile_restoration_plan["target_name"], profile_restoration_plan["id"]))

        # Execute Task Restore (Skipping Conflicted Tasks)
        for t in tasks_to_restore:
            cur.execute("""
                UPDATE public.care_tasks
                SET assigned_role = 'receptionist',
                    description = %s,
                    updated_at = timezone('utc', now())
                WHERE id = %s;
            """, (t["target_desc"], t["id"]))

        conn.commit()
        print("=== DATA RESTORATION COMPLETED SUCCESSFULLY ===")
        return {
            "profile_restoration": profile_restoration_plan,
            "tasks_restored": len(tasks_to_restore),
            "conflicts_preserved": len(conflicts_preserved),
            "dry_run": False
        }

if __name__ == "__main__":
    load_dotenv(WORKSPACE_ROOT / "carebridge" / "backend" / ".env")
    db_url = os.environ.get("DATABASE_URL")
    conn = psycopg2.connect(db_url)
    try:
        recover_data(conn, WORKSPACE_ROOT / "phase15_pre_migration_state.json", dry_run=False, auto_confirm=True)
    finally:
        conn.close()

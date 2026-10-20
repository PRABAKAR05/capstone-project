#!/usr/bin/env python3
"""
Phase 15 Baseline Capture Script
Captures pre-execution baseline snapshots and git diff patch:
1. PHASE_15_AFFECTED_FILES.json
2. pre_phase15_uncommitted_<timestamp>.patch
3. phase15_file_baselines/ with exact snapshots and SHA-256 hashes
"""
import os
import sys
import json
import shutil
import hashlib
import datetime
import subprocess
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent

AFFECTED_FILES = [
    # Backend Core & Schemas
    "carebridge/backend/app/core/security.py",
    "carebridge/backend/app/schemas/care_task.py",
    "carebridge/backend/app/schemas/caregiver.py",
    "carebridge/backend/app/schemas/conflict.py",
    "carebridge/backend/main.py",
    # Backend API Endpoints
    "carebridge/backend/app/api/v1/caregiver.py",
    "carebridge/backend/app/api/v1/appointments.py",
    "carebridge/backend/app/api/v1/patients.py",
    "carebridge/backend/app/api/v1/documents.py",
    "carebridge/backend/app/api/v1/conflicts.py",
    "carebridge/backend/app/api/v1/care_tasks.py",
    "carebridge/backend/app/api/v1/prescriptions.py",
    "carebridge/backend/app/api/v1/insurance.py",
    "carebridge/backend/app/api/v1/chat/tools.py",
    "carebridge/backend/app/api/v1/chat/engine.py",
    # Supabase / DB Seed
    "carebridge/backend/supabase/seed_15_records.py",
    # Frontend Core & Shell
    "carebridge/frontend/lib/auth-context.tsx",
    "carebridge/frontend/components/shell/sidebar.tsx",
    "carebridge/frontend/components/shell/tenant-header.tsx",
    "carebridge/frontend/components/prescriptions/prescription-detail-modal.tsx",
    # Frontend Pages
    "carebridge/frontend/app/demo/page.tsx",
    "carebridge/frontend/app/(dashboard)/page.tsx",
    "carebridge/frontend/app/(dashboard)/tasks/page.tsx",
    "carebridge/frontend/app/(dashboard)/receptionist/page.tsx",
    "carebridge/frontend/app/(dashboard)/receptionist/verify-caregivers/page.tsx",
    "carebridge/frontend/app/(dashboard)/portal/caregivers/page.tsx",
]

def compute_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def record_baseline():
    timestamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    baselines_dir = WORKSPACE_ROOT / "phase15_file_baselines"
    baselines_dir.mkdir(parents=True, exist_ok=True)

    print(f"=== Recording Phase 15 Baseline State ===")
    print(f"Timestamp: {timestamp}")
    print(f"Target Baselines Directory: {baselines_dir}")

    # 1. Capture git diff patch for pre-existing uncommitted changes
    patch_filename = f"pre_phase15_uncommitted_{timestamp}.patch"
    patch_path = WORKSPACE_ROOT / patch_filename
    try:
        git_diff_result = subprocess.run(
            ["git", "diff", "HEAD"],
            cwd=str(WORKSPACE_ROOT),
            capture_output=True,
            text=True,
            check=True
        )
        with open(patch_path, "w", encoding="utf-8") as pf:
            pf.write(git_diff_result.stdout)
        print(f"Captured uncommitted worktree patch: {patch_filename} ({len(git_diff_result.stdout)} bytes)")
    except Exception as e:
        print(f"Warning: Could not capture git diff patch: {e}")

    # 2. Capture snapshots and calculate SHA-256 for affected files
    manifest = {
        "timestamp": timestamp,
        "workspace_root": str(WORKSPACE_ROOT),
        "uncommitted_patch": patch_filename,
        "files_count": len(AFFECTED_FILES),
        "files": {}
    }

    for rel_path in AFFECTED_FILES:
        src_path = WORKSPACE_ROOT / rel_path
        if not src_path.exists():
            print(f"Notice: File {rel_path} does not exist yet; will be recorded as pending creation.")
            manifest["files"][rel_path] = {
                "exists": False,
                "sha256": None,
                "snapshot": None
            }
            continue

        sha256_hash = compute_sha256(src_path)
        safe_rel_name = rel_path.replace("/", "__").replace("\\", "__")
        snapshot_file = baselines_dir / f"{safe_rel_name}.snapshot"
        shutil.copy2(src_path, snapshot_file)

        manifest["files"][rel_path] = {
            "exists": True,
            "sha256": sha256_hash,
            "bytes": src_path.stat().st_size,
            "snapshot": str(snapshot_file.relative_to(WORKSPACE_ROOT))
        }
        print(f"  Captured: {rel_path:60} (SHA256: {sha256_hash[:12]}...)")

    # 3. Write PHASE_15_AFFECTED_FILES.json
    manifest_path = WORKSPACE_ROOT / "PHASE_15_AFFECTED_FILES.json"
    with open(manifest_path, "w", encoding="utf-8") as mf:
        json.dump(manifest, mf, indent=2)

    print(f"\nBaseline capture complete! Manifest saved to: {manifest_path}")

if __name__ == "__main__":
    record_baseline()

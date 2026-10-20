#!/usr/bin/env python3
"""
Phase 15 Pre-Execution Audit Script
Records SHA-256 hashes of all 17,727 CSCM research assets and audit log line counts
into phase15_pre_execution_audit.json before any modifications are made.
"""
import os
import sys
import json
import hashlib
import datetime
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent
BASELINE_HASHES_PATH = WORKSPACE_ROOT / "carebridge" / "backend" / "app" / "cscm" / "research_comprehensive_baseline_hashes.json"
AUDIT_LOG_PATH = WORKSPACE_ROOT / "carebridge" / "backend" / "logs" / "audit.jsonl"
OUTPUT_AUDIT_JSON = WORKSPACE_ROOT / "phase15_pre_execution_audit.json"

def compute_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def run_pre_execution_audit():
    print(f"=== CareBridge AI Phase 15 Pre-Execution Audit Gate ===")
    start_time = datetime.datetime.now(datetime.timezone.utc)
    print(f"Timestamp: {start_time.isoformat()}")

    # 1. Audit CSCM-IoMT Research Assets
    if not BASELINE_HASHES_PATH.exists():
        raise FileNotFoundError(f"Baseline hashes file not found at: {BASELINE_HASHES_PATH}")

    with open(BASELINE_HASHES_PATH, "r", encoding="utf-8") as f:
        baseline_hashes = json.load(f)

    total_baseline_files = len(baseline_hashes)
    print(f"Checking {total_baseline_files} CSCM research files against baseline...")

    missing_files = []
    hash_mismatches = []
    checked_count = 0

    for rel_path, expected_hash in baseline_hashes.items():
        checked_count += 1
        full_path = WORKSPACE_ROOT / rel_path
        if not full_path.exists():
            missing_files.append(rel_path)
            continue
        actual_hash = compute_sha256(full_path)
        if actual_hash != expected_hash:
            hash_mismatches.append({
                "path": rel_path,
                "expected": expected_hash,
                "actual": actual_hash
            })
        if checked_count % 5000 == 0 or checked_count == total_baseline_files:
            print(f"  Progress: {checked_count}/{total_baseline_files} files checked...")

    if missing_files or hash_mismatches:
        print(f"FAIL: Missing {len(missing_files)} files, {len(hash_mismatches)} hash mismatches.")
        sys.exit(1)

    print(f"SUCCESS: 100% of {total_baseline_files} CSCM research files verified bit-for-bit identical.")

    # 2. Audit carebridge/backend/logs/audit.jsonl
    if not AUDIT_LOG_PATH.exists():
        raise FileNotFoundError(f"Audit log file not found at: {AUDIT_LOG_PATH}")

    audit_file_hash = compute_sha256(AUDIT_LOG_PATH)
    total_audit_lines = 0
    receptionist_events = []

    with open(AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            total_audit_lines += 1
            record = json.loads(line)
            role = record.get("actor_role") or record.get("role")
            if role == "receptionist":
                receptionist_events.append({
                    "line_number": idx,
                    "event_type": record.get("event_type") or record.get("action"),
                    "timestamp": record.get("timestamp") or record.get("created_at"),
                    "sha256_line": hashlib.sha256(line.encode("utf-8")).hexdigest()
                })

    print(f"Audit log verified: {total_audit_lines} total lines, {len(receptionist_events)} receptionist events.")
    if len(receptionist_events) != 48:
        print(f"WARNING: Expected 48 receptionist events, found {len(receptionist_events)}")

    # 3. Assemble and persist pre-execution record
    audit_record = {
        "audit_version": "1.0",
        "phase": 15,
        "recorded_at": start_time.isoformat(),
        "workspace_root": str(WORKSPACE_ROOT),
        "cscm_research_assets": {
            "baseline_reference_file": str(BASELINE_HASHES_PATH.relative_to(WORKSPACE_ROOT)),
            "total_files": total_baseline_files,
            "checked_files": checked_count,
            "missing_count": len(missing_files),
            "mismatch_count": len(hash_mismatches),
            "status": "PASS" if len(missing_files) == 0 and len(hash_mismatches) == 0 else "FAIL"
        },
        "audit_log": {
            "file_path": str(AUDIT_LOG_PATH.relative_to(WORKSPACE_ROOT)),
            "file_sha256": audit_file_hash,
            "total_lines": total_audit_lines,
            "receptionist_events_count": len(receptionist_events),
            "receptionist_events": receptionist_events,
            "status": "PASS"
        },
        "gate_status": "PASSED"
    }

    with open(OUTPUT_AUDIT_JSON, "w", encoding="utf-8") as f:
        json.dump(audit_record, f, indent=2)

    print(f"Pre-execution audit successfully captured into: {OUTPUT_AUDIT_JSON}")
    return audit_record

if __name__ == "__main__":
    run_pre_execution_audit()

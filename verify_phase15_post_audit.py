#!/usr/bin/env python3
"""
Phase 15 Post-Execution Audit Verification Script
Validates 100% hash parity across all 17,727 CSCM research files and
100% byte-for-byte and line-by-line identity of the 48 historical receptionist audit events.
"""
import os
import sys
import json
import hashlib
from pathlib import Path

WORKSPACE_ROOT = Path(__file__).resolve().parent
PRE_AUDIT_JSON = WORKSPACE_ROOT / "phase15_pre_execution_audit.json"
AUDIT_LOG_PATH = WORKSPACE_ROOT / "carebridge" / "backend" / "logs" / "audit.jsonl"
BASELINE_HASHES_PATH = WORKSPACE_ROOT / "carebridge" / "backend" / "app" / "cscm" / "research_comprehensive_baseline_hashes.json"

def compute_sha256(file_path: Path) -> str:
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def verify_post_audit():
    print("=== CareBridge AI Phase 15 Post-Execution Audit Gate ===")
    if not PRE_AUDIT_JSON.exists():
        print(f"ERROR: Pre-execution audit file {PRE_AUDIT_JSON} not found!")
        sys.exit(1)

    with open(PRE_AUDIT_JSON, "r", encoding="utf-8") as f:
        pre_audit = json.load(f)

    # 1. Verify CSCM-IoMT Research Assets
    with open(BASELINE_HASHES_PATH, "r", encoding="utf-8") as f:
        baseline_hashes = json.load(f)

    total_files = len(baseline_hashes)
    print(f"Checking {total_files} CSCM research files for post-execution parity...")
    mismatches = []
    missing = []
    for rel_path, expected_hash in baseline_hashes.items():
        fp = WORKSPACE_ROOT / rel_path
        if not fp.exists():
            missing.append(rel_path)
            continue
        actual_hash = compute_sha256(fp)
        if actual_hash != expected_hash:
            mismatches.append({"path": rel_path, "expected": expected_hash, "actual": actual_hash})

    if missing or mismatches:
        print(f"FAILED: Found {len(missing)} missing files and {len(mismatches)} hash mismatches in CSCM assets!")
        sys.exit(1)
    print(f"AC-15.11 PASS: 100% of {total_files} CSCM research files matched baseline exactly. Zero mutations.")

    # 2. Verify audit.jsonl historical receptionist entries
    if not AUDIT_LOG_PATH.exists():
        print(f"ERROR: Audit log file {AUDIT_LOG_PATH} missing!")
        sys.exit(1)

    pre_receptionist_events = pre_audit["audit_log"]["receptionist_events"]
    receptionist_events_by_line = {e["line_number"]: e for e in pre_receptionist_events}

    post_receptionist_count = 0
    corrupted_lines = []

    with open(AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            record = json.loads(line)
            role = record.get("actor_role") or record.get("role")
            if role == "receptionist":
                post_receptionist_count += 1
                if idx in receptionist_events_by_line:
                    expected_line_hash = receptionist_events_by_line[idx]["sha256_line"]
                    actual_line_hash = hashlib.sha256(line.encode("utf-8")).hexdigest()
                    if expected_line_hash != actual_line_hash:
                        corrupted_lines.append(idx)

    if corrupted_lines or post_receptionist_count != len(pre_receptionist_events):
        print(f"FAILED: Receptionist events modified or count changed! Expected {len(pre_receptionist_events)}, found {post_receptionist_count}. Corrupted lines: {corrupted_lines}")
        sys.exit(1)

    print(f"AC-15.10 PASS: All {post_receptionist_count} historical receptionist audit records verified 100% byte-for-byte identical.")
    print("=== POST-EXECUTION AUDIT GATE PASSED CLEANLY ===")

if __name__ == "__main__":
    verify_post_audit()

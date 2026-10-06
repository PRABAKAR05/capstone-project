"""
scripts/audit_datasets.py
==========================
CSCM-IoMT Phase 2 — Complete Dataset Audit

Audits both datasets and produces structured reports:
    results/dataset_audit/physionet_audit.json
    results/dataset_audit/physionet_audit.md
    results/dataset_audit/wesad_audit.json
    results/dataset_audit/wesad_audit.md
    results/dataset_audit/combined_audit.md

Usage::

    # Full audit (default)
    python scripts/audit_datasets.py

    # Sample audit (first N records/subjects)
    python scripts/audit_datasets.py --sample 2

    # Dataset-specific
    python scripts/audit_datasets.py --physionet-only
    python scripts/audit_datasets.py --wesad-only

    # Help
    python scripts/audit_datasets.py --help

IMPORTANT:
    This script is READ-ONLY with respect to raw datasets.
    It will never modify, rename, or delete raw dataset files.
"""

from __future__ import annotations

import argparse
import gc
import json
import math
import os
import stat
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# -----------------------------------------------------------------------
# Ensure project root is on the path
# -----------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tqdm import tqdm

from src.data.physionet_loader import (
    parse_record,
    summarize_parameters,
    is_valid_record_file,
    classify_parameter,
)
from src.data.wesad_loader import (
    load_subject_pkl,
    validate_subject,
    check_subject_files,
    CHEST_RATE_HZ,
    LABEL_NAMES,
)
from src.utils.config import (
    find_project_root,
    resolve_dataset_paths,
    get_physionet_set_a_records,
    get_wesad_subject_dirs,
    load_physionet_config,
    load_wesad_config,
)
from src.utils.logging import get_logger, setup_logging

logger = get_logger(__name__)


# -----------------------------------------------------------------------
# Read-only safety check
# -----------------------------------------------------------------------

def _snapshot_dir_mtimes(directory: Path) -> dict[str, float]:
    """
    Record modification times for all files in a directory tree.
    Used for pre/post comparison to detect inadvertent writes.
    """
    mtimes: dict[str, float] = {}
    if not directory.exists():
        return mtimes
    try:
        for f in directory.rglob("*"):
            if f.is_file():
                mtimes[str(f)] = f.stat().st_mtime
    except Exception:
        pass
    return mtimes


def _verify_no_modifications(before: dict[str, float], directory: Path) -> list[str]:
    """Return list of files that were modified, created, or deleted."""
    violations: list[str] = []
    if not directory.exists():
        return violations

    after: dict[str, float] = {}
    try:
        for f in directory.rglob("*"):
            if f.is_file():
                after[str(f)] = f.stat().st_mtime
    except Exception:
        return violations

    # New files (created during audit)
    new_files = set(after.keys()) - set(before.keys())
    for f in new_files:
        violations.append(f"NEW FILE created in raw dir: {f}")

    # Modified files
    for f, mtime in after.items():
        if f in before and not math.isclose(mtime, before[f], abs_tol=1.0):
            violations.append(f"FILE MODIFIED: {f}")

    # Deleted files
    deleted = set(before.keys()) - set(after.keys())
    for f in deleted:
        violations.append(f"FILE DELETED: {f}")

    return violations


# -----------------------------------------------------------------------
# PhysioNet Audit
# -----------------------------------------------------------------------

def audit_physionet(
    paths: dict[str, Any],
    sample_n: Optional[int] = None,
    pn_config: Optional[dict] = None,
) -> dict[str, Any]:
    """
    Audit all PhysioNet Set-A records.

    Parameters
    ----------
    paths : dict
        Resolved paths from resolve_dataset_paths().
    sample_n : int, optional
        If set, audit only the first N records.
    pn_config : dict, optional
        PhysioNet configuration dict.

    Returns
    -------
    dict
        Full audit result with per-record and aggregate statistics.
    """
    set_a_dir: Path = paths["physionet"]["set_a"]
    outcomes_a_path: Path = paths["physionet"].get("outcomes_a")
    is_sample = sample_n is not None

    audit: dict[str, Any] = {
        "dataset": "physionet",
        "audit_type": "sample" if is_sample else "full",
        "sample_n": sample_n,
        "set_a_dir": str(set_a_dir),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "files_found": 0,
        "valid_record_files": 0,
        "invalid_files": [],
        "records": {},          # record_id → summary
        "parameters": {},       # param_name → aggregate stats
        "errors": [],
        "warnings": [],
        "outcomes": {},
    }

    # ----------------------------------------------------------------
    # File discovery
    # ----------------------------------------------------------------
    logger.info("Scanning PhysioNet Set-A directory: %s", set_a_dir)
    all_files = sorted(set_a_dir.iterdir()) if set_a_dir.exists() else []
    audit["files_found"] = sum(1 for f in all_files if f.is_file())

    valid_records: list[Path] = []
    for f in all_files:
        if not f.is_file():
            continue
        if is_valid_record_file(f):
            valid_records.append(f)
        else:
            audit["invalid_files"].append({
                "name": f.name,
                "size_bytes": f.stat().st_size,
                "reason": "Does not match expected header 'Time,Parameter,Value'",
            })

    audit["valid_record_files"] = len(valid_records)
    logger.info("Found %d valid record files.", len(valid_records))

    # Apply sample limit
    if is_sample:
        valid_records = valid_records[:sample_n]
        audit["warnings"].append(
            f"SAMPLE AUDIT: Processing only {len(valid_records)} of "
            f"{audit['valid_record_files']} records. "
            f"Results are NOT representative of the full dataset."
        )

    # ----------------------------------------------------------------
    # Per-parameter aggregate accumulators
    # ----------------------------------------------------------------
    param_records_present: dict[str, int] = defaultdict(int)
    param_total_obs: dict[str, int] = defaultdict(int)
    param_sentinel_count: dict[str, int] = defaultdict(int)
    param_invalid_count: dict[str, int] = defaultdict(int)
    param_obs_per_record: dict[str, list[int]] = defaultdict(list)
    param_categories: dict[str, str] = {}
    total_record_count = len(valid_records)

    # ----------------------------------------------------------------
    # Parse records
    # ----------------------------------------------------------------
    parse_errors_total = 0
    parse_warnings_total = 0

    for rec_path in tqdm(valid_records, desc="PhysioNet: Auditing records", unit="rec"):
        try:
            rec = parse_record(rec_path)
        except ValueError as exc:
            audit["errors"].append({
                "file": rec_path.name,
                "error_type": "ValueError",
                "message": str(exc),
            })
            parse_errors_total += 1
            continue
        except OSError as exc:
            audit["errors"].append({
                "file": rec_path.name,
                "error_type": "OSError",
                "message": str(exc),
            })
            parse_errors_total += 1
            continue
        except Exception as exc:
            audit["errors"].append({
                "file": rec_path.name,
                "error_type": type(exc).__name__,
                "message": str(exc),
            })
            parse_errors_total += 1
            continue

        # Per-record parse errors/warnings
        if rec["parse_errors"]:
            parse_errors_total += len(rec["parse_errors"])
            for err in rec["parse_errors"]:
                audit["warnings"].append(
                    f"Record {rec.get('record_id', rec_path.name)}: {err}"
                )
        if rec["time_errors"]:
            parse_warnings_total += len(rec["time_errors"])

        # Store compact per-record summary
        rid = rec.get("record_id") or rec_path.stem
        audit["records"][str(rid)] = {
            "file": rec_path.name,
            "record_id": rec.get("record_id"),
            "raw_observations": rec["raw_observations"],
            "unique_params": rec["unique_params"],
            "earliest_time_min": rec.get("earliest_time_min"),
            "latest_time_min": rec.get("latest_time_min"),
            "duration_hours": rec.get("duration_hours"),
            "sentinel_count": rec["sentinel_count"],
            "invalid_count": rec["invalid_count"],
            "metadata": rec["metadata"],
            "has_errors": bool(rec["parse_errors"]),
        }

        # Aggregate per-parameter statistics
        param_summary = summarize_parameters(rec)
        for param, stats in param_summary.items():
            param_records_present[param] += 1
            obs = stats["obs_count"]
            param_total_obs[param] += obs
            param_sentinel_count[param] += stats["sentinel_count"]
            param_invalid_count[param] += stats["invalid_count"]
            param_obs_per_record[param].append(obs)
            if param not in param_categories:
                param_categories[param] = stats["category"]

    # ----------------------------------------------------------------
    # Compute aggregate parameter statistics
    # ----------------------------------------------------------------
    for param in sorted(param_records_present.keys()):
        records_present = param_records_present[param]
        coverage_pct = (records_present / total_record_count * 100) if total_record_count > 0 else 0
        obs_list = param_obs_per_record[param]

        median_obs = sorted(obs_list)[len(obs_list) // 2] if obs_list else None
        min_obs = min(obs_list) if obs_list else None
        max_obs = max(obs_list) if obs_list else None

        audit["parameters"][param] = {
            "category": param_categories.get(param, "unknown"),
            "records_present": records_present,
            "coverage_percent": round(coverage_pct, 2),
            "total_observations": param_total_obs[param],
            "median_obs_per_record": median_obs,
            "min_obs_per_record": min_obs,
            "max_obs_per_record": max_obs,
            "sentinel_count": param_sentinel_count[param],
            "invalid_count": param_invalid_count[param],
            "high_coverage": coverage_pct >= 70.0,
        }

    # ----------------------------------------------------------------
    # Outcomes-A inspection
    # ----------------------------------------------------------------
    if outcomes_a_path and outcomes_a_path.exists():
        try:
            import csv as csv_mod
            rows = 0
            columns = None
            with open(outcomes_a_path, "r", encoding="utf-8") as fh:
                reader = csv_mod.DictReader(fh)
                columns = reader.fieldnames
                for row in reader:
                    rows += 1
            audit["outcomes"] = {
                "outcomes_a_path": str(outcomes_a_path),
                "columns": list(columns) if columns else [],
                "row_count": rows,
                "note": (
                    "Outcomes are auxiliary metadata. "
                    "In-hospital death labels are NOT used as FDI attack labels."
                ),
            }
        except Exception as exc:
            audit["outcomes"]["error"] = str(exc)
    else:
        audit["outcomes"]["note"] = "Outcomes-a.txt not found or not accessible."

    # ----------------------------------------------------------------
    # Summary
    # ----------------------------------------------------------------
    audit["summary"] = {
        "total_files_found": audit["files_found"],
        "valid_record_files": audit["valid_record_files"],
        "records_processed": len(audit["records"]),
        "records_failed": parse_errors_total,
        "unique_parameters": len(audit["parameters"]),
        "total_parse_errors": parse_errors_total,
        "high_coverage_params": [
            p for p, s in audit["parameters"].items() if s["high_coverage"]
            and s["category"] in ("physiological", "clinical_score", "laboratory")
        ],
        "physiological_params": [
            p for p, s in audit["parameters"].items() if s["category"] == "physiological"
        ],
        "metadata_params": [
            p for p, s in audit["parameters"].items() if s["category"] == "metadata"
        ],
        "laboratory_params": [
            p for p, s in audit["parameters"].items() if s["category"] == "laboratory"
        ],
        "unknown_params": [
            p for p, s in audit["parameters"].items() if s["category"] == "unknown"
        ],
    }

    return audit


# -----------------------------------------------------------------------
# WESAD Audit
# -----------------------------------------------------------------------

def audit_wesad(
    paths: dict[str, Any],
    sample_n: Optional[int] = None,
    wesad_config: Optional[dict] = None,
) -> dict[str, Any]:
    """
    Audit all WESAD subjects (S2–S17) one at a time.

    CRITICAL: Subjects are loaded and released ONE AT A TIME to avoid
    OOM errors with 15× ~930 MB pkl files.

    Parameters
    ----------
    paths : dict
        Resolved paths from resolve_dataset_paths().
    sample_n : int, optional
        If set, audit only the first N subjects.
    wesad_config : dict, optional
        WESAD configuration dict.

    Returns
    -------
    dict
        Full audit result.
    """
    wesad_root: Path = paths["wesad"]["root"]
    available_subjects: list[str] = paths["wesad"].get("available_subjects", [])
    absent_subjects: list[str] = paths["wesad"].get("absent_subjects", [])
    is_sample = sample_n is not None

    audit: dict[str, Any] = {
        "dataset": "wesad",
        "audit_type": "sample" if is_sample else "full",
        "sample_n": sample_n,
        "wesad_root": str(wesad_root),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "expected_subjects": available_subjects,
        "absent_subjects": {
            "ids": absent_subjects,
            "reason": "Sensor malfunction during data collection (per WESAD readme)",
        },
        "subjects": {},
        "modality_aggregate": {},
        "errors": [],
        "warnings": [],
    }

    # Apply sample limit
    subjects_to_audit = available_subjects
    if is_sample:
        subjects_to_audit = available_subjects[:sample_n]
        audit["warnings"].append(
            f"SAMPLE AUDIT: Processing only {len(subjects_to_audit)} of "
            f"{len(available_subjects)} subjects. "
            f"Results are NOT representative of all subjects."
        )

    # ----------------------------------------------------------------
    # Subject-level audit (one at a time)
    # ----------------------------------------------------------------
    subject_dirs = get_wesad_subject_dirs(paths)
    loaded_count = 0
    failed_count = 0

    # Aggregate modality stats across subjects
    modality_presence: dict[str, dict[str, int]] = {
        "chest": defaultdict(int),
        "wrist": defaultdict(int),
    }

    for subj_id in tqdm(subjects_to_audit, desc="WESAD: Auditing subjects", unit="subj"):
        subj_dir = subject_dirs.get(subj_id, wesad_root / subj_id)

        # File integrity check (read-only)
        file_check = check_subject_files(subj_dir, subj_id)

        subj_entry: dict[str, Any] = {
            "subject_id": subj_id,
            "directory": str(subj_dir),
            "dir_exists": file_check["subject_dir_exists"],
            "files": {
                k: {"exists": v["exists"], "path": str(v["path"])}
                for k, v in file_check.items()
                if isinstance(v, dict) and "exists" in v
            },
            "missing_files": file_check["missing_files"],
            "pkl_size_mb": None,
            "validation": None,
            "errors": [],
            "warnings": [],
        }

        # Check PKL size
        pkl_info = file_check.get("pkl", {})
        if pkl_info.get("exists") and pkl_info.get("size_bytes"):
            subj_entry["pkl_size_mb"] = round(pkl_info["size_bytes"] / 1e6, 1)

        # Directory missing
        if not file_check["subject_dir_exists"]:
            msg = f"Subject {subj_id}: Directory not found: {subj_dir}"
            audit["errors"].append({"subject": subj_id, "error_type": "DirectoryNotFound", "message": msg})
            subj_entry["errors"].append(msg)
            audit["subjects"][subj_id] = subj_entry
            failed_count += 1
            continue

        # PKL missing
        if not pkl_info.get("exists"):
            msg = f"Subject {subj_id}: PKL file not found in {subj_dir}"
            audit["errors"].append({"subject": subj_id, "error_type": "PKLNotFound", "message": msg})
            subj_entry["errors"].append(msg)
            audit["subjects"][subj_id] = subj_entry
            failed_count += 1
            continue

        # Load and validate
        data = None
        try:
            data = load_subject_pkl(subj_dir, subj_id)
            validation = validate_subject(subj_id, data)
            subj_entry["validation"] = _serialize_validation(validation)

            # Propagate errors/warnings
            subj_entry["errors"].extend(validation.get("errors", []))
            subj_entry["warnings"].extend(validation.get("warnings", []))

            if not validation.get("is_valid"):
                audit["warnings"].append(
                    f"Subject {subj_id} validation failed: "
                    f"{validation.get('errors', [])}"
                )

            # Track modality presence
            for mod in (validation.get("chest") or {}).keys():
                modality_presence["chest"][mod] += 1
            for mod in (validation.get("wrist") or {}).keys():
                modality_presence["wrist"][mod] += 1

            loaded_count += 1

        except FileNotFoundError as exc:
            msg = str(exc)
            audit["errors"].append({"subject": subj_id, "error_type": "FileNotFound", "message": msg})
            subj_entry["errors"].append(msg)
            failed_count += 1
        except MemoryError as exc:
            msg = f"MemoryError loading {subj_id}: {exc}"
            audit["errors"].append({"subject": subj_id, "error_type": "MemoryError", "message": msg})
            subj_entry["errors"].append(msg)
            failed_count += 1
        except Exception as exc:
            msg = f"{type(exc).__name__}: {exc}"
            audit["errors"].append({"subject": subj_id, "error_type": type(exc).__name__, "message": msg})
            subj_entry["errors"].append(msg)
            failed_count += 1
        finally:
            # CRITICAL: Release memory before moving to next subject
            if data is not None:
                del data
                gc.collect()

        audit["subjects"][subj_id] = subj_entry

    # ----------------------------------------------------------------
    # Aggregate modality statistics
    # ----------------------------------------------------------------
    for device, mods in modality_presence.items():
        audit["modality_aggregate"][device] = {
            mod: {
                "subjects_present": cnt,
                "subjects_processed": len(subjects_to_audit),
                "coverage_percent": round(cnt / len(subjects_to_audit) * 100, 1)
                if subjects_to_audit else 0,
            }
            for mod, cnt in sorted(mods.items())
        }

    # ----------------------------------------------------------------
    # Summary
    # ----------------------------------------------------------------
    audit["summary"] = {
        "subjects_expected": len(available_subjects),
        "subjects_audited": len(subjects_to_audit),
        "subjects_loaded_successfully": loaded_count,
        "subjects_failed": failed_count,
        "total_errors": len(audit["errors"]),
        "total_warnings": len(audit["warnings"]),
        "chest_modalities_found": sorted(modality_presence["chest"].keys()),
        "wrist_modalities_found": sorted(modality_presence["wrist"].keys()),
    }

    return audit


def _serialize_validation(validation: dict) -> dict:
    """Convert a validation dict to JSON-serializable form."""
    result = {}
    for k, v in validation.items():
        if isinstance(v, dict):
            result[k] = _serialize_validation(v)
        elif isinstance(v, list):
            result[k] = [
                _serialize_validation(i) if isinstance(i, dict) else
                (list(i) if isinstance(i, (tuple,)) else i)
                for i in v
            ]
        elif isinstance(v, (int, float, str, bool)) or v is None:
            result[k] = v
        else:
            result[k] = str(v)
    return result


# -----------------------------------------------------------------------
# JSON / Markdown writers
# -----------------------------------------------------------------------

def write_json(data: dict, path: Path) -> None:
    """Write data as indented JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, default=_json_default)
    logger.info("Written: %s", path)


def _json_default(obj):
    """JSON serialization fallback."""
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, (set, frozenset)):
        return sorted(obj)
    return str(obj)


def write_physionet_md(audit: dict, path: Path) -> None:
    """Write PhysioNet audit as Markdown report."""
    is_sample = audit.get("audit_type") == "sample"
    summary = audit.get("summary", {})
    params = audit.get("parameters", {})
    records = audit.get("records", {})
    errors = audit.get("errors", [])
    warnings = audit.get("warnings", [])
    outcomes = audit.get("outcomes", {})

    # Compute record observation stats
    obs_counts = [r["raw_observations"] for r in records.values() if r.get("raw_observations")]
    durations = [r["duration_hours"] for r in records.values() if r.get("duration_hours") is not None]

    lines = [
        "# PhysioNet/CinC Challenge 2012 — Dataset Audit Report",
        "",
    ]
    if is_sample:
        lines += [
            "> ⚠️ **SAMPLE AUDIT** — Results based on "
            f"{audit.get('sample_n')} records only. "
            "Not representative of the full dataset.",
            "",
        ]
    lines += [
        f"**Generated**: {audit.get('timestamp_utc')}",
        f"**Source**: `{audit.get('set_a_dir')}`",
        f"**Audit type**: {audit.get('audit_type', 'full').upper()}",
        "",
        "---",
        "",
        "## Executive Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Files found in Set-A | {summary.get('total_files_found', 'N/A')} |",
        f"| Valid record files | {summary.get('valid_record_files', 'N/A')} |",
        f"| Records successfully parsed | {summary.get('records_processed', 'N/A')} |",
        f"| Records with parse errors | {summary.get('records_failed', 'N/A')} |",
        f"| Unique parameters discovered | {summary.get('unique_parameters', 'N/A')} |",
        f"| Physiological parameters | {len(summary.get('physiological_params', []))} |",
        f"| Laboratory parameters | {len(summary.get('laboratory_params', []))} |",
        f"| Metadata fields | {len(summary.get('metadata_params', []))} |",
        f"| Unknown parameters | {len(summary.get('unknown_params', []))} |",
        "",
    ]

    # Record observation statistics
    if obs_counts:
        lines += [
            "## Record Observation Statistics",
            "",
            "| Metric | Value |",
            "|--------|-------|",
            f"| Min observations per record | {min(obs_counts)} |",
            f"| Max observations per record | {max(obs_counts)} |",
            f"| Median observations per record | {sorted(obs_counts)[len(obs_counts)//2]} |",
        ]
        if durations:
            lines += [
                f"| Min record duration (hours) | {min(durations):.2f} |",
                f"| Max record duration (hours) | {max(durations):.2f} |",
                f"| Median record duration (hours) | {sorted(durations)[len(durations)//2]:.2f} |",
            ]
        lines.append("")

    # Parameter coverage table
    lines += [
        "## Parameter Coverage",
        "",
        "> Coverage% = fraction of parsed records containing the parameter.",
        "> Sentinel = PhysioNet's -1 marker for unavailable measurements.",
        "> Category: **P**=physiological, **L**=laboratory, **C**=clinical score, **M**=metadata, **?**=unknown",
        "",
        "| Parameter | Category | Records Present | Coverage% | Total Obs | Median Obs/Record | Sentinel Count | Invalid Count |",
        "|-----------|----------|-----------------|-----------|-----------|-------------------|----------------|---------------|",
    ]
    cat_abbrev = {
        "physiological": "P",
        "laboratory": "L",
        "clinical_score": "C",
        "metadata": "M",
        "unknown": "?",
    }
    for param, s in sorted(params.items(), key=lambda x: -x[1]["coverage_percent"]):
        cat = cat_abbrev.get(s["category"], "?")
        high = " ⬆️" if s["high_coverage"] else ""
        lines.append(
            f"| {param} | {cat}{high} | {s['records_present']} | "
            f"{s['coverage_percent']:.1f}% | {s['total_observations']} | "
            f"{s.get('median_obs_per_record', 'N/A')} | "
            f"{s['sentinel_count']} | {s['invalid_count']} |"
        )
    lines.append("")

    # Candidate channels
    high_cov_phys = [p for p, s in params.items()
                     if s["category"] == "physiological" and s["high_coverage"]]
    low_cov_phys = [p for p, s in params.items()
                    if s["category"] == "physiological" and not s["high_coverage"]]
    lines += [
        "## Candidate Physiological Channels",
        "",
        "> **AUDIT OBSERVATION** (not a final research design decision).",
        "",
        "### High-Coverage Candidates (>=70% records)",
        "",
    ]
    if high_cov_phys:
        for p in sorted(high_cov_phys):
            lines.append(f"- `{p}` — {params[p]['coverage_percent']:.1f}% record coverage")
    else:
        lines.append("_None found above threshold._")
    lines += [
        "",
        "### Lower-Coverage Candidates (<70% records)",
        "",
    ]
    if low_cov_phys:
        for p in sorted(low_cov_phys):
            lines.append(f"- `{p}` — {params[p]['coverage_percent']:.1f}% record coverage")
    else:
        lines.append("_None._")

    # Outcomes
    if outcomes:
        lines += [
            "",
            "## Outcomes-A",
            "",
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Path | `{outcomes.get('outcomes_a_path', 'N/A')}` |",
            f"| Columns | {', '.join(outcomes.get('columns', []))} |",
            f"| Rows | {outcomes.get('row_count', 'N/A')} |",
            "",
            f"> {outcomes.get('note', '')}",
        ]

    # Errors
    lines += ["", "## Errors and Warnings", ""]
    if errors:
        lines.append(f"**{len(errors)} errors encountered:**")
        for err in errors[:20]:  # Limit display
            lines.append(f"- `{err.get('file', '?')}`: {err.get('message', '?')}")
        if len(errors) > 20:
            lines.append(f"  _(and {len(errors)-20} more — see physionet_audit.json)_")
    else:
        lines.append("[PASS] No critical errors.")
    if warnings:
        lines += ["", f"**{min(len(warnings), 10)} of {len(warnings)} warnings:**"]
        for w in warnings[:10]:
            lines.append(f"- {w}")

    # Unrecognized files
    invalid_files = audit.get("invalid_files", [])
    if invalid_files:
        lines += [
            "",
            "## Unrecognized Files",
            "",
            "The following files did not match the expected record format:",
            "",
        ]
        for f_info in invalid_files[:20]:
            lines.append(f"- `{f_info['name']}`: {f_info['reason']}")

    # Missing-value notes
    lines += [
        "",
        "## Missing Value Notes",
        "",
        "PhysioNet uses `-1` as a sentinel for unavailable measurements.",
        "This is **not** the same as an interpolated or observed zero.",
        "The sentinel counts above show how frequently this occurs per parameter.",
        "",
        "**Temporal missingness** (fraction of time-grid positions without observations)",
        "will be computed in Phase 3 after a temporal alignment strategy is chosen.",
        "It is not reported here because PhysioNet is irregularly sampled.",
    ]

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    logger.info("Written: %s", path)


def write_wesad_md(audit: dict, path: Path) -> None:
    """Write WESAD audit as Markdown report."""
    is_sample = audit.get("audit_type") == "sample"
    summary = audit.get("summary", {})
    subjects = audit.get("subjects", {})
    modalities = audit.get("modality_aggregate", {})
    errors = audit.get("errors", [])
    warnings = audit.get("warnings", [])

    lines = [
        "# WESAD — Wearable Stress and Affect Detection — Dataset Audit",
        "",
    ]
    if is_sample:
        lines += [
            "> ⚠️ **SAMPLE AUDIT** — Results based on "
            f"{audit.get('sample_n')} subjects only.",
            "",
        ]
    lines += [
        f"**Generated**: {audit.get('timestamp_utc')}",
        f"**Source**: `{audit.get('wesad_root')}`",
        f"**Audit type**: {audit.get('audit_type', 'full').upper()}",
        "",
        "---",
        "",
        "## Executive Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Expected subjects | {summary.get('subjects_expected', 'N/A')} |",
        f"| Subjects audited | {summary.get('subjects_audited', 'N/A')} |",
        f"| Successfully loaded | {summary.get('subjects_loaded_successfully', 'N/A')} |",
        f"| Failed to load | {summary.get('subjects_failed', 'N/A')} |",
        f"| Chest modalities found | {', '.join(summary.get('chest_modalities_found', []))} |",
        f"| Wrist modalities found | {', '.join(summary.get('wrist_modalities_found', []))} |",
        "",
        "**Absent subjects (S1, S12)**: Excluded per WESAD documentation due to sensor malfunction.",
        "",
        "---",
        "",
        "## Subject-Level Summary",
        "",
        "| Subject | Dir | PKL | PKL Size (MB) | Duration (s) | Chest Mods | Wrist Mods | Label Issues | Errors |",
        "|---------|-----|-----|---------------|-------------|------------|------------|--------------|--------|",
    ]

    for subj_id, s in sorted(subjects.items()):
        v = s.get("validation") or {}
        labels = v.get("labels") or {}
        dur = labels.get("duration_seconds", "N/A")
        chest_mods = ", ".join(sorted((v.get("chest") or {}).keys())) or "—"
        wrist_mods = ", ".join(sorted((v.get("wrist") or {}).keys())) or "—"
        label_warnings = len(labels.get("warnings", []))
        err_count = len(s.get("errors", []))
        dir_ok = "[PASS]" if s.get("dir_exists") else "[FAIL]"
        pkl_ok = "[PASS]" if (s.get("files", {}).get("pkl", {}).get("exists")) else "[FAIL]"
        lines.append(
            f"| {subj_id} | {dir_ok} | {pkl_ok} | "
            f"{s.get('pkl_size_mb', 'N/A')} | {dur} | "
            f"{chest_mods} | {wrist_mods} | "
            f"{label_warnings} | {err_count} |"
        )

    # Signal structure detail per modality
    lines += [
        "",
        "---",
        "",
        "## Signal Structure",
        "",
        "### Chest Modalities (RespiBAN, documented 700 Hz)",
        "",
        "| Modality | Subjects Present | Coverage% | Example Shape |",
        "|----------|-----------------|-----------|---------------|",
    ]
    chest_mods_agg = modalities.get("chest", {})
    for mod in sorted(chest_mods_agg.keys()):
        m = chest_mods_agg[mod]
        # Get example shape from first available subject
        example_shape = "N/A"
        for s_data in subjects.values():
            v = s_data.get("validation") or {}
            chest_v = v.get("chest") or {}
            if mod in chest_v and chest_v[mod].get("shape"):
                example_shape = str(chest_v[mod]["shape"])
                break
        lines.append(
            f"| {mod} | {m['subjects_present']} | "
            f"{m['coverage_percent']:.0f}% | `{example_shape}` |"
        )

    lines += [
        "",
        "### Wrist Modalities (Empatica E4)",
        "",
        "| Modality | Documented Hz | Subjects Present | Coverage% | Example Shape |",
        "|----------|---------------|-----------------|-----------|---------------|",
    ]
    wrist_hz = {"ACC": "32", "BVP": "64", "EDA": "4", "TEMP": "4"}
    wrist_mods_agg = modalities.get("wrist", {})
    for mod in sorted(wrist_mods_agg.keys()):
        m = wrist_mods_agg[mod]
        example_shape = "N/A"
        for s_data in subjects.values():
            v = s_data.get("validation") or {}
            wrist_v = v.get("wrist") or {}
            if mod in wrist_v and wrist_v[mod].get("shape"):
                example_shape = str(wrist_v[mod]["shape"])
                break
        lines.append(
            f"| {mod} | {wrist_hz.get(mod, '?')} | {m['subjects_present']} | "
            f"{m['coverage_percent']:.0f}% | `{example_shape}` |"
        )

    # Labels section
    lines += [
        "",
        "---",
        "",
        "## Label Distribution",
        "",
        "WESAD label mapping (experimental conditions — NOT cybersecurity labels):",
        "",
        "| Label | Condition | Notes |",
        "|-------|-----------|-------|",
        "| 0 | Transient | Transitional segments |",
        "| 1 | Baseline | Resting state |",
        "| 2 | Stress | TSST protocol |",
        "| 3 | Amusement | Funny video clips |",
        "| 4 | Meditation | Guided meditation |",
        "| 5,6,7 | _Ignored_ | Per WESAD documentation |",
        "",
    ]

    # Per-subject label counts
    lines += ["### Per-Subject Label Counts", ""]
    header_labels = [0, 1, 2, 3, 4, 5, 6, 7]
    header_row = "| Subject | " + " | ".join(str(l) for l in header_labels) + " | Unexpected |"
    separator = "|---------|" + "|".join(["---------"] * len(header_labels)) + "|------------|"
    lines += [header_row, separator]
    for subj_id in sorted(subjects.keys()):
        s = subjects[subj_id]
        v = s.get("validation") or {}
        label_info = v.get("labels") or {}
        counts = label_info.get("label_counts", {})
        unexpected = label_info.get("unexpected_labels", [])
        row_vals = [str(counts.get(l, 0)) for l in header_labels]
        lines.append(
            f"| {subj_id} | " + " | ".join(row_vals) +
            f" | {unexpected or '—'} |"
        )

    # NaN/Inf report
    lines += [
        "",
        "---",
        "",
        "## Data Quality — NaN and Inf",
        "",
        "| Subject | Signal | NaN Count | Inf Count | Finite% |",
        "|---------|--------|-----------|-----------|---------|",
    ]
    for subj_id in sorted(subjects.keys()):
        s = subjects[subj_id]
        v = s.get("validation") or {}
        for device in ("chest", "wrist"):
            for mod, stats in sorted((v.get(device) or {}).items()):
                if not isinstance(stats, dict):
                    continue
                nan_c = stats.get("nan_count", "N/A")
                inf_c = stats.get("inf_count", "N/A")
                fin = stats.get("finite_fraction")
                fin_str = f"{fin*100:.1f}%" if isinstance(fin, float) else "N/A"
                lines.append(
                    f"| {subj_id} | {device}/{mod} | {nan_c} | {inf_c} | {fin_str} |"
                )

    # Errors
    lines += ["", "---", "", "## Errors and Warnings", ""]
    if errors:
        lines.append(f"**{len(errors)} errors:**")
        for err in errors:
            lines.append(
                f"- `{err.get('subject', '?')}`: "
                f"[{err.get('error_type', '?')}] {err.get('message', '?')}"
            )
    else:
        lines.append("[PASS] No critical errors.")
    if warnings:
        lines += ["", f"**{len(warnings)} warnings:**"]
        for w in warnings[:15]:
            lines.append(f"- {w}")
        if len(warnings) > 15:
            lines.append(f"  _(and {len(warnings)-15} more — see wesad_audit.json)_")

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    logger.info("Written: %s", path)


def write_combined_md(
    pn_audit: Optional[dict],
    wesad_audit: Optional[dict],
    env_data: Optional[dict],
    output_path: Path,
) -> None:
    """Write the combined audit report answering all Phase 2 research questions."""
    pn_summary = (pn_audit or {}).get("summary", {})
    pn_params = (pn_audit or {}).get("parameters", {})
    ws_summary = (wesad_audit or {}).get("summary", {})
    ws_subjects = (wesad_audit or {}).get("subjects", {})
    ws_mods = (wesad_audit or {}).get("modality_aggregate", {})

    # Helper: extract stats from env_data
    py_ver = "N/A"
    torch_ver = "N/A"
    cuda = "N/A"
    gpu = "N/A"
    if env_data:
        py_info = env_data.get("python", {})
        pkg_info = env_data.get("packages", {})
        gpu_info = env_data.get("gpu", {})
        py_ver = py_info.get("python_version_short", "N/A")
        t_pkg = pkg_info.get("torch", {})
        torch_ver = t_pkg.get("version") if t_pkg.get("installed") else "not installed"
        cuda = "available" if gpu_info.get("cuda_available") else "not available"
        gpus = gpu_info.get("gpus", [])
        gpu = gpus[0]["name"] if gpus else "none"

    lines = [
        "# CSCM-IoMT — Combined Dataset Audit Report",
        "## Phase 2: Dataset Audit",
        "",
        "**Project**: Coordinated Multi-Channel False Data Injection Attack Detection",
        "Using Physiology-Aware Cross-Sensor Consistency Modeling in IoMT",
        "",
        f"**Generated**: {datetime.now(timezone.utc).isoformat()}",
        "",
        "> ⚠️ This report distinguishes **AUDIT OBSERVATIONS** from **RESEARCH DESIGN DECISIONS**.",
        "> Candidate channels and graph edges listed here are preliminary findings — not final choices.",
        "",
        "---",
        "",
        "## 1. Environment",
        "",
        f"| Property | Value |",
        f"|----------|-------|",
        f"| Python | {py_ver} |",
        f"| PyTorch | {torch_ver} |",
        f"| CUDA | {cuda} |",
        f"| GPU | {gpu} |",
        "",
        "---",
        "",
        "## 2. Project Paths",
        "",
        f"| Dataset | Configured Path |",
        f"|---------|-----------------|",
    ]
    if pn_audit:
        lines.append(f"| PhysioNet Set-A | `{pn_audit.get('set_a_dir')}` |")
    if wesad_audit:
        lines.append(f"| WESAD root | `{wesad_audit.get('wesad_root')}` |")

    lines += [
        "",
        "---",
        "",
        "## 3. PhysioNet Set-A Summary",
        "",
    ]
    if pn_audit:
        pn_records = pn_audit.get("records", {})
        obs_counts = [r.get("raw_observations", 0) for r in pn_records.values()]
        durations = [r["duration_hours"] for r in pn_records.values() if r.get("duration_hours") is not None]
        lines += [
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Valid record files | {pn_summary.get('valid_record_files', 'N/A')} |",
            f"| Records successfully parsed | {pn_summary.get('records_processed', 'N/A')} |",
            f"| Records with errors | {pn_summary.get('records_failed', 0)} |",
            f"| Unique parameters | {pn_summary.get('unique_parameters', 'N/A')} |",
            f"| Median obs per record | {sorted(obs_counts)[len(obs_counts)//2] if obs_counts else 'N/A'} |",
            f"| Median duration (hours) | {round(sorted(durations)[len(durations)//2], 2) if durations else 'N/A'} |",
        ]
    else:
        lines.append("_PhysioNet audit not run._")

    lines += [
        "",
        "---",
        "",
        "## 4. WESAD Summary",
        "",
    ]
    if wesad_audit:
        lines += [
            f"| Metric | Value |",
            f"|--------|-------|",
            f"| Expected subjects | {ws_summary.get('subjects_expected', 'N/A')} |",
            f"| Successfully loaded | {ws_summary.get('subjects_loaded_successfully', 'N/A')} |",
            f"| Failed | {ws_summary.get('subjects_failed', 0)} |",
            f"| Chest modalities | {', '.join(ws_summary.get('chest_modalities_found', []))} |",
            f"| Wrist modalities | {', '.join(ws_summary.get('wrist_modalities_found', []))} |",
            "",
            "_Absent subjects: S1, S12 — sensor malfunction per WESAD documentation._",
        ]
    else:
        lines.append("_WESAD audit not run._")

    # PhysioNet parameter coverage table (high-coverage only)
    lines += [
        "",
        "---",
        "",
        "## 5. PhysioNet Parameter Coverage",
        "",
        "> ⬆️ marks parameters with >=70% record coverage.",
        "",
        "| Parameter | Category | Coverage% | Total Obs | Sentinel Count |",
        "|-----------|----------|-----------|-----------|----------------|",
    ]
    cat_abbrev = {
        "physiological": "Physiological",
        "laboratory": "Laboratory",
        "clinical_score": "Clinical Score",
        "metadata": "Metadata",
        "unknown": "Unknown",
    }
    for param, s in sorted(pn_params.items(), key=lambda x: -x[1]["coverage_percent"]):
        high = " ⬆️" if s["high_coverage"] else ""
        lines.append(
            f"| {param} | {cat_abbrev.get(s['category'], s['category'])}{high} | "
            f"{s['coverage_percent']:.1f}% | {s['total_observations']} | {s['sentinel_count']} |"
        )

    # WESAD signal structure
    lines += [
        "",
        "---",
        "",
        "## 6. WESAD Signal Structure",
        "",
        "### Chest Modalities (RespiBAN, 700 Hz documented)",
        "",
        "| Modality | Subjects Present | Coverage% |",
        "|----------|-----------------|-----------|",
    ]
    for mod, m in sorted(ws_mods.get("chest", {}).items()):
        lines.append(f"| {mod} | {m['subjects_present']} | {m['coverage_percent']:.0f}% |")

    lines += [
        "",
        "### Wrist Modalities (Empatica E4)",
        "",
        "| Modality | Documented Hz | Subjects Present | Coverage% |",
        "|----------|---------------|-----------------|-----------|",
    ]
    wrist_hz = {"ACC": 32, "BVP": 64, "EDA": 4, "TEMP": 4}
    for mod, m in sorted(ws_mods.get("wrist", {}).items()):
        lines.append(
            f"| {mod} | {wrist_hz.get(mod, '?')} Hz | "
            f"{m['subjects_present']} | {m['coverage_percent']:.0f}% |"
        )

    # Answer all 17 Phase 2 questions
    lines += [
        "",
        "---",
        "",
        "## 7. Missing and Invalid Data Findings",
        "",
        "### PhysioNet",
        "",
        "- PhysioNet uses **-1 as a sentinel** for unavailable measurements.",
        "- Sentinel counts per parameter are tabulated in the parameter coverage table.",
        "- Laboratory parameters are typically sparse (intermittent sampling).",
        "- Absent observations for a given time-step are structurally different from sentinel -1.",
        "- Temporal missingness (grid-based) will be assessed in Phase 3 after alignment strategy is chosen.",
        "",
        "### WESAD",
        "",
        "- WESAD .pkl files contain synchronized signals.",
        "- NaN and Inf counts per modality are reported in `wesad_audit.md`.",
        "- Any NaN/Inf issues found above should be reviewed before preprocessing.",
    ]

    # Candidate channels
    high_cov_phys = [p for p, s in pn_params.items()
                     if s["category"] == "physiological" and s["high_coverage"]]
    low_cov_phys = [p for p, s in pn_params.items()
                    if s["category"] == "physiological" and not s["high_coverage"]]

    lines += [
        "",
        "---",
        "",
        "## 8. Candidate Physiological Channels",
        "",
        "> **AUDIT OBSERVATION** — not final research design decisions.",
        "> Final channel selection requires review of coverage, physiological meaning,",
        "> graph formability, and attack-generation compatibility.",
        "",
        "### PhysioNet — High-Coverage Candidates (>=70%)",
        "",
    ]
    if high_cov_phys:
        for p in sorted(high_cov_phys):
            lines.append(f"- `{p}` ({pn_params[p]['coverage_percent']:.1f}% coverage)")
    else:
        lines.append("_None found above 70% threshold (verify with full audit)._")

    lines += [
        "",
        "### PhysioNet — Lower-Coverage Physiological Parameters (<70%)",
        "",
    ]
    if low_cov_phys:
        for p in sorted(low_cov_phys):
            lines.append(f"- `{p}` ({pn_params[p]['coverage_percent']:.1f}%)")

    lines += [
        "",
        "### WESAD — Confirmed Chest Modalities",
        "",
    ]
    for mod in sorted(ws_mods.get("chest", {}).keys()):
        lines.append(f"- `{mod}` (chest, 700 Hz)")

    lines += [
        "",
        "### WESAD — Confirmed Wrist Modalities",
        "",
    ]
    for mod in sorted(ws_mods.get("wrist", {}).keys()):
        hz = wrist_hz.get(mod, "?")
        lines.append(f"- `{mod}` (wrist, {hz} Hz)")

    lines += [
        "",
        "---",
        "",
        "## 9. Candidate Cross-Sensor Relationships",
        "",
        "> **PRELIMINARY / CANDIDATE GRAPH** — Not implemented yet.",
        "> These are hypothesized relationships for subsequent analysis,",
        "> not proven clinical relationships.",
        "",
        "### PhysioNet Candidate Graph Edges",
        "",
        "| Edge | Physiological Rationale |",
        "|------|------------------------|",
        "| HR ↔ RespRate | Cardiorespiratory coupling (if both available) |",
        "| NISysABP ↔ NIDiasABP | Systolic-diastolic blood pressure relationship |",
        "| NISysABP ↔ NIMAP | MAP is derived from systolic and diastolic BP |",
        "| NIDiasABP ↔ NIMAP | See above |",
        "| HR ↔ NISysABP | Autonomic nervous system coupling |",
        "| HR ↔ Temp | Fever/thermoregulation effect on HR |",
        "",
        "> Final graph: selected after confirming availability of both edge endpoints",
        "> and sufficient temporal co-occurrence across records.",
        "",
        "### WESAD Candidate Graph Edges",
        "",
        "| Edge | Physiological Rationale |",
        "|------|------------------------|",
        "| ECG ↔ BVP (chest-wrist) | Both reflect cardiac activity at different locations |",
        "| ECG ↔ RESP | Respiratory sinus arrhythmia — HR modulated by breathing |",
        "| chest EDA ↔ wrist EDA | Both reflect electrodermal activity; device and location differ |",
        "| chest Temp ↔ wrist TEMP | Both reflect temperature; location and sensor differ |",
        "| RESP ↔ chest EDA | Respiration and sympathetic arousal co-vary during stress |",
        "",
        "> Note: Cross-location signals (e.g., chest EDA vs. wrist EDA) are different",
        "> measurements and should NOT be assumed equal.",
        "> The model should learn the relationship rather than enforce equality.",
    ]

    # Temporal alignment challenges
    lines += [
        "",
        "---",
        "",
        "## 10. Data Quality Warnings",
        "",
        "### PhysioNet",
        "",
    ]
    pn_warnings = (pn_audit or {}).get("warnings", [])
    if pn_warnings:
        for w in pn_warnings[:15]:
            lines.append(f"- {w}")
        if len(pn_warnings) > 15:
            lines.append(f"- _(and {len(pn_warnings)-15} more — see physionet_audit.json)_")
    else:
        lines.append("[PASS] No significant warnings.")

    lines += ["", "### WESAD", ""]
    ws_warnings = (wesad_audit or {}).get("warnings", [])
    if ws_warnings:
        for w in ws_warnings[:15]:
            lines.append(f"- {w}")
        if len(ws_warnings) > 15:
            lines.append(f"- _(and {len(ws_warnings)-15} more — see wesad_audit.json)_")
    else:
        lines.append("[PASS] No significant warnings.")

    lines += [
        "",
        "---",
        "",
        "## 11. Recommended Next Steps (Phase 3)",
        "",
        "### Temporal Alignment",
        "",
        "**PhysioNet**: Irregular observations → requires a temporal grid strategy.",
        "- Candidate: 1-hour grid with forward-fill and explicit missingness mask.",
        "- Configurable maximum interpolation gap (suggested: 120 minutes).",
        "- Laboratory values are sparse — treat as separate missingness class.",
        "",
        "**WESAD**: Synchronized at different rates per device.",
        "- Chest signals at 700 Hz, wrist at 4–64 Hz.",
        "- Downsampling chest or upsampling wrist → to be decided in Phase 3.",
        "- Preferred approach: decimate chest to a common rate (e.g., 4 Hz or 32 Hz).",
        "",
        "### Windowing",
        "",
        "**PhysioNet**: 1-hour windows (candidate — not validated yet).",
        "- Records span 24–49+ hours; windowing will produce multiple windows per record.",
        "",
        "**WESAD**: 60-second windows at the target rate (candidate).",
        "- At 700 Hz: 60 s = 42,000 samples per window.",
        "- After downsampling to 4 Hz: 60 s = 240 samples.",
        "",
        "### Normalization",
        "",
        "Normalization statistics **must** be computed on training subjects/records only.",
        "Validation and test data must use training statistics — never fit on them.",
        "",
        "### Missing Value Strategy",
        "",
        "**PhysioNet**:",
        "- Sentinel -1 → NaN before any numerical operations.",
        "- Short gaps: linear interpolation with missingness mask.",
        "- Long gaps (>threshold): do not interpolate — mark as missing.",
        "",
        "**WESAD**:",
        "- NaN/Inf counts confirmed above. Any found → inspect cause before imputation.",
        "",
        "### Attack Generation",
        "",
        "Attack channel combinations will be based on the final confirmed channel sets.",
        "Do not finalize attack combinations until channel selection is complete.",
    ]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    logger.info("Written: %s", output_path)


# -----------------------------------------------------------------------
# Main entry point
# -----------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="CSCM-IoMT Phase 2 — Dataset Audit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--physionet-only", action="store_true",
        help="Audit PhysioNet only (skip WESAD).",
    )
    parser.add_argument(
        "--wesad-only", action="store_true",
        help="Audit WESAD only (skip PhysioNet).",
    )
    parser.add_argument(
        "--sample", type=int, default=None, metavar="N",
        help=(
            "Audit only the first N records (PhysioNet) "
            "and/or N subjects (WESAD). "
            "SAMPLE RESULTS ARE NOT REPRESENTATIVE."
        ),
    )
    return parser.parse_args()


def main() -> int:
    """
    Run the full dataset audit.

    Returns
    -------
    int
        Exit code: 0 = success, 1 = failures detected.
    """
    args = parse_args()

    # Setup
    setup_logging()
    from src.utils.reproducibility import set_all_seeds
    set_all_seeds(42)

    project_root = find_project_root()
    paths = resolve_dataset_paths(project_root, validate=True)
    output_dir: Path = paths["outputs"]["dataset_audit"]

    logger.info("=" * 60)
    logger.info("CSCM-IoMT Phase 2 — Dataset Audit")
    logger.info("Project root: %s", project_root)
    logger.info("=" * 60)

    if args.sample:
        logger.warning(
            "SAMPLE MODE: Processing only %d records/subjects. "
            "Full audit required for final results.", args.sample
        )

    run_physionet = not args.wesad_only
    run_wesad = not args.physionet_only

    # ----------------------------------------------------------------
    # Read-only safety: snapshot raw dataset mtimes before audit
    # ----------------------------------------------------------------
    pn_dir: Path = paths["physionet"]["set_a"]
    ws_dir: Path = paths["wesad"]["root"]
    pn_snapshot_before = _snapshot_dir_mtimes(pn_dir)
    ws_snapshot_before = _snapshot_dir_mtimes(ws_dir)

    # ----------------------------------------------------------------
    # Phase 1: Collect environment
    # ----------------------------------------------------------------
    logger.info("Collecting environment information…")
    import scripts.environment_info as env_mod
    env_data = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "project_root": str(project_root),
        "system": env_mod.collect_system_info(),
        "python": env_mod.collect_python_info(),
        "packages": env_mod.collect_package_info(),
        "gpu": env_mod.collect_gpu_info(),
        "disk": env_mod.collect_disk_info(project_root),
    }
    env_mod.write_environment_json(env_data, output_dir)
    env_mod.write_environment_md(env_data, output_dir)

    pn_audit: Optional[dict] = None
    wesad_audit: Optional[dict] = None
    total_errors = 0

    # ----------------------------------------------------------------
    # Phase 2: PhysioNet audit
    # ----------------------------------------------------------------
    if run_physionet:
        logger.info("Starting PhysioNet audit…")
        t0 = time.time()
        try:
            pn_config = load_physionet_config(project_root)
            pn_audit = audit_physionet(paths, sample_n=args.sample, pn_config=pn_config)
            elapsed = time.time() - t0
            pn_audit["elapsed_seconds"] = round(elapsed, 2)
            logger.info("PhysioNet audit complete in %.1f s.", elapsed)
        except Exception as exc:
            logger.error("PhysioNet audit FAILED: %s", exc, exc_info=True)
            pn_audit = {"error": str(exc), "dataset": "physionet"}
            total_errors += 1

        # Write outputs
        if pn_audit:
            write_json(pn_audit, output_dir / "physionet_audit.json")
            write_physionet_md(pn_audit, output_dir / "physionet_audit.md")
            total_errors += len(pn_audit.get("errors", []))

    # ----------------------------------------------------------------
    # Phase 3: WESAD audit (one subject at a time)
    # ----------------------------------------------------------------
    if run_wesad:
        logger.info("Starting WESAD audit…")
        t0 = time.time()
        try:
            wesad_cfg = load_wesad_config(project_root)
            wesad_audit = audit_wesad(paths, sample_n=args.sample, wesad_config=wesad_cfg)
            elapsed = time.time() - t0
            wesad_audit["elapsed_seconds"] = round(elapsed, 2)
            logger.info("WESAD audit complete in %.1f s.", elapsed)
        except Exception as exc:
            logger.error("WESAD audit FAILED: %s", exc, exc_info=True)
            wesad_audit = {"error": str(exc), "dataset": "wesad"}
            total_errors += 1

        # Write outputs
        if wesad_audit:
            write_json(wesad_audit, output_dir / "wesad_audit.json")
            write_wesad_md(wesad_audit, output_dir / "wesad_audit.md")
            total_errors += len(wesad_audit.get("errors", []))

    # ----------------------------------------------------------------
    # Combined report
    # ----------------------------------------------------------------
    logger.info("Writing combined audit report…")
    write_combined_md(pn_audit, wesad_audit, env_data, output_dir / "combined_audit.md")

    # ----------------------------------------------------------------
    # Read-only safety: verify no raw files were modified
    # ----------------------------------------------------------------
    logger.info("Verifying raw dataset integrity (read-only check)…")
    violations: list[str] = []
    if run_physionet:
        violations.extend(_verify_no_modifications(pn_snapshot_before, pn_dir))
    if run_wesad:
        violations.extend(_verify_no_modifications(ws_snapshot_before, ws_dir))

    if violations:
        logger.error("READ-ONLY VIOLATION: Raw dataset files were modified!")
        for v in violations:
            logger.error("  VIOLATION: %s", v)
        total_errors += len(violations)

    # ----------------------------------------------------------------
    # Final summary printout
    # ----------------------------------------------------------------
    pn_sum = (pn_audit or {}).get("summary", {})
    ws_sum = (wesad_audit or {}).get("summary", {})
    py_ver = env_data["python"].get("python_version_short", "N/A")
    torch_ver = env_data["packages"].get("torch", {})
    torch_str = (
        "v" + torch_ver.get("version", "") if torch_ver.get("installed") else "not installed"
    )
    cuda_str = "available" if env_data["gpu"].get("cuda_available") else "not available"
    gpu_list = env_data["gpu"].get("gpus", [])
    gpu_str = gpu_list[0]["name"] if gpu_list else "none"

    print("\n" + "=" * 52)
    print("CSCM-IoMT PHASE 2 AUDIT COMPLETE")
    print("=" * 52)
    print(f"\nEnvironment:")
    print(f"  Python  : {py_ver}")
    print(f"  PyTorch : {torch_str}")
    print(f"  CUDA    : {cuda_str}")
    print(f"  GPU     : {gpu_str}")

    if run_physionet and pn_audit:
        print(f"\nPhysioNet:")
        print(f"  Records discovered  : {pn_sum.get('valid_record_files', 'N/A')}")
        print(f"  Records parsed      : {pn_sum.get('records_processed', 'N/A')}")
        print(f"  Records failed      : {pn_sum.get('records_failed', 0)}")
        print(f"  Unique parameters   : {pn_sum.get('unique_parameters', 'N/A')}")
        print(f"  Physiological params: {len(pn_sum.get('physiological_params', []))}")
        print(f"  High-coverage (>=70%): {len([p for p,s in pn_audit.get('parameters',{}).items() if s.get('high_coverage')])}")

    if run_wesad and wesad_audit:
        print(f"\nWESAD:")
        print(f"  Subjects expected   : {ws_sum.get('subjects_expected', 'N/A')}")
        print(f"  Subjects found      : {ws_sum.get('subjects_audited', 'N/A')}")
        print(f"  Subjects loaded     : {ws_sum.get('subjects_loaded_successfully', 'N/A')}")
        print(f"  Subjects failed     : {ws_sum.get('subjects_failed', 0)}")
        print(f"  Chest modalities    : {', '.join(ws_sum.get('chest_modalities_found', []))}")
        print(f"  Wrist modalities    : {', '.join(ws_sum.get('wrist_modalities_found', []))}")

    if violations:
        print(f"\n⛔ READ-ONLY VIOLATIONS: {len(violations)}")
        for v in violations:
            print(f"  {v}")

    print(f"\nData quality:")
    print(f"  PhysioNet warnings  : {len((pn_audit or {}).get('warnings', []))}")
    print(f"  WESAD warnings      : {len((wesad_audit or {}).get('warnings', []))}")

    print(f"\nReports written to: {output_dir}")
    print("  - environment.json / environment.md")
    if run_physionet:
        print("  - physionet_audit.json / physionet_audit.md")
    if run_wesad:
        print("  - wesad_audit.json / wesad_audit.md")
    print("  - combined_audit.md")

    # Phase 2 gate
    phase_pass = total_errors == 0
    print(f"\nPhase 2 status: {'[PASS] PASS' if phase_pass else '[FAIL] FAIL'}")
    if phase_pass:
        print("Ready for Phase 3: preprocessing design.")
    else:
        print(f"Phase 2 requires correction before proceeding. ({total_errors} error(s) detected.)")
        if args.sample:
            print("\n  NOTE: You ran a --sample audit. Run the full audit before final evaluation.")
    print("=" * 52 + "\n")

    return 0 if phase_pass else 1


if __name__ == "__main__":
    sys.exit(main())

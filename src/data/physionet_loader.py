"""
CSCM-IoMT: PhysioNet/CinC Challenge 2012 Data Loader
======================================================
Parses PhysioNet Set-A patient records in long-format CSV:
    Time,Parameter,Value

Key design decisions:
  - Records are parsed one file at a time (memory-efficient).
  - Time strings "HH:MM" are converted to elapsed minutes.
  - The sentinel value -1 is flagged but NOT silently converted to NaN
    during loading — the audit layer decides interpretation.
  - Parameter classification distinguishes metadata from physiological
    channels, laboratory values, clinical scores, and unknowns.
  - A file that does not start with 'Time,Parameter,Value' is rejected
    as a non-record file (warnings are recorded, not exceptions raised).

Usage::

    from src.data.physionet_loader import parse_record, classify_parameter

    result = parse_record(Path("set-a/132539.txt"))
    print(result["record_id"])
    print(result["parameters"].keys())
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Any, Optional

from src.utils.logging import get_logger

logger = get_logger(__name__)

# -----------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------

EXPECTED_HEADER: str = "Time,Parameter,Value"
MISSING_SENTINEL: float = -1.0  # PhysioNet uses -1 for unavailable fields

# Parameter classification lookup.
# Categories: metadata | physiological | laboratory | clinical_score | unknown
# NOTE: This is a best-effort classification based on PhysioNet documentation.
#       The audit will extend/correct this based on observed parameters.
_PARAM_CATEGORIES: dict[str, str] = {
    # ---- Metadata (patient descriptors at t=0) ----
    "RecordID":    "metadata",
    "Age":         "metadata",
    "Gender":      "metadata",
    "Height":      "metadata",
    "Weight":      "metadata",
    "ICUType":     "metadata",

    # ---- Physiological vital signs ----
    "HR":          "physiological",
    "RespRate":    "physiological",
    "SpO2":        "physiological",
    "Temp":        "physiological",
    "SysABP":      "physiological",
    "DiasABP":     "physiological",
    "MAP":         "physiological",
    "NISysABP":    "physiological",
    "NIDiasABP":   "physiological",
    "NIMAP":       "physiological",

    # ---- Laboratory values ----
    "BUN":         "laboratory",
    "Creatinine":  "laboratory",
    "Glucose":     "laboratory",
    "HCO3":        "laboratory",
    "HCT":         "laboratory",
    "Mg":          "laboratory",
    "Na":          "laboratory",
    "K":           "laboratory",
    "WBC":         "laboratory",
    "Platelets":   "laboratory",
    "Lactate":     "laboratory",
    "ALT":         "laboratory",
    "AST":         "laboratory",
    "Bilirubin":   "laboratory",
    "TroponinI":   "laboratory",
    "TroponinT":   "laboratory",
    "PaCO2":       "laboratory",
    "PaO2":        "laboratory",
    "pH":          "laboratory",
    "FiO2":        "laboratory",
    "Urine":       "laboratory",
    "Albumin":     "laboratory",
    "Cholesterol": "laboratory",

    # ---- Clinical scores ----
    "GCS":         "clinical_score",
    "MechVent":    "clinical_score",
}


# -----------------------------------------------------------------------
# Time conversion
# -----------------------------------------------------------------------

def parse_time_to_minutes(time_string: str) -> float:
    """
    Convert a PhysioNet time string to elapsed minutes.

    PhysioNet uses "HH:MM" format to represent elapsed time since
    ICU admission (not wall clock time).

    Parameters
    ----------
    time_string : str
        Time string in "HH:MM" format. Hours may exceed 23 for long ICU
        stays (e.g., "48:07").

    Returns
    -------
    float
        Elapsed time in minutes.

    Raises
    ------
    ValueError
        If the time string cannot be parsed.

    Examples
    --------
    >>> parse_time_to_minutes("00:07")
    7.0
    >>> parse_time_to_minutes("01:37")
    97.0
    >>> parse_time_to_minutes("48:00")
    2880.0
    """
    time_string = time_string.strip()
    if ":" not in time_string:
        raise ValueError(f"Invalid time format (expected HH:MM): '{time_string}'")
    parts = time_string.split(":", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid time format (expected HH:MM): '{time_string}'")
    try:
        hours = int(parts[0])
        minutes = int(parts[1])
    except ValueError as exc:
        raise ValueError(
            f"Non-integer components in time string '{time_string}': {exc}"
        ) from exc
    if minutes < 0 or minutes >= 60:
        raise ValueError(
            f"Minutes component out of range [0,59] in '{time_string}'"
        )
    if hours < 0:
        raise ValueError(f"Negative hours in time string '{time_string}'")
    return float(hours * 60 + minutes)


# -----------------------------------------------------------------------
# Parameter classification
# -----------------------------------------------------------------------

def classify_parameter(parameter_name: str) -> str:
    """
    Return the category of a PhysioNet parameter.

    Categories:
      - ``metadata``       : Patient descriptors (RecordID, Age, Gender, etc.)
      - ``physiological``  : Continuously monitored vital signs
      - ``laboratory``     : Intermittent lab results
      - ``clinical_score`` : Composite scores (GCS, MechVent)
      - ``unknown``        : Parameter not in classification table

    Parameters
    ----------
    parameter_name : str
        Parameter name as it appears in the record file.

    Returns
    -------
    str
        One of the category strings above.
    """
    return _PARAM_CATEGORIES.get(parameter_name.strip(), "unknown")


# -----------------------------------------------------------------------
# Value parsing
# -----------------------------------------------------------------------

def _safe_float(value_str: str) -> tuple[Optional[float], Optional[str]]:
    """
    Attempt to convert a value string to float.

    Returns
    -------
    tuple[Optional[float], Optional[str]]
        (float_value, error_message)
        If conversion succeeds: (float_value, None)
        If conversion fails: (None, error_message)
    """
    value_str = value_str.strip()
    try:
        return float(value_str), None
    except ValueError:
        return None, f"Non-numeric value: '{value_str}'"


def _is_sentinel(value: float) -> bool:
    """Return True if the value equals the PhysioNet missing sentinel (-1)."""
    return math.isclose(value, MISSING_SENTINEL, abs_tol=1e-9)


# -----------------------------------------------------------------------
# Record parsing
# -----------------------------------------------------------------------

def is_valid_record_file(filepath: Path) -> bool:
    """
    Check whether a file appears to be a valid PhysioNet record.

    Validation:
      1. File must exist and be a regular file.
      2. First line must be exactly 'Time,Parameter,Value'.

    Parameters
    ----------
    filepath : Path
        Path to the candidate file.

    Returns
    -------
    bool
    """
    if not filepath.is_file():
        return False
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
            first_line = fh.readline().strip()
        return first_line == EXPECTED_HEADER
    except OSError:
        return False


def parse_record(filepath: Path) -> dict[str, Any]:
    """
    Parse a single PhysioNet record file.

    The record is parsed line-by-line without loading the entire file
    into memory at once.

    Parameters
    ----------
    filepath : Path
        Absolute path to the record .txt file.

    Returns
    -------
    dict with keys:
        - ``record_id`` (int | None): RecordID from the metadata row.
        - ``filepath`` (str): Source file path.
        - ``metadata`` (dict): Patient descriptors (Age, Gender, etc.).
        - ``parameters`` (dict): Mapping of parameter name →
            list of (time_minutes, raw_value, is_sentinel, parse_error).
        - ``raw_observations`` (int): Total observation rows parsed.
        - ``sentinel_count`` (int): Total sentinel (-1) values found.
        - ``invalid_count`` (int): Total unparseable values found.
        - ``unique_params`` (int): Number of distinct parameter names.
        - ``earliest_time_min`` (float | None): Earliest time in minutes.
        - ``latest_time_min`` (float | None): Latest time in minutes.
        - ``duration_hours`` (float | None): Duration in hours.
        - ``time_errors`` (list): Rows with unparseable timestamps.
        - ``classification`` (dict): Parameter → category mapping.
        - ``parse_errors`` (list): Error messages encountered.
        - ``warnings`` (list): Non-fatal issues.

    Raises
    ------
    FileNotFoundError
        If filepath does not exist.
    ValueError
        If the file header does not match EXPECTED_HEADER.
    """
    if not filepath.exists():
        raise FileNotFoundError(f"Record file not found: {filepath}")

    result: dict[str, Any] = {
        "record_id": None,
        "filepath": str(filepath),
        "metadata": {},
        "parameters": {},       # param_name → list of (time_min, value, is_sentinel, error)
        "raw_observations": 0,
        "sentinel_count": 0,
        "invalid_count": 0,
        "unique_params": 0,
        "earliest_time_min": None,
        "latest_time_min": None,
        "duration_hours": None,
        "time_errors": [],
        "classification": {},
        "parse_errors": [],
        "warnings": [],
    }

    times: list[float] = []

    with open(filepath, "r", encoding="utf-8", errors="replace") as fh:
        reader = csv.reader(fh)

        # Validate header
        try:
            header = next(reader)
        except StopIteration:
            result["parse_errors"].append("File is empty.")
            return result

        header_str = ",".join(h.strip() for h in header)
        if header_str != EXPECTED_HEADER:
            raise ValueError(
                f"Unexpected header in {filepath}: '{header_str}' "
                f"(expected '{EXPECTED_HEADER}')"
            )

        # Parse rows
        for line_num, row in enumerate(reader, start=2):
            if not row or all(c.strip() == "" for c in row):
                continue  # Skip blank lines

            if len(row) < 3:
                result["parse_errors"].append(
                    f"Line {line_num}: expected 3 columns, got {len(row)}: {row}"
                )
                continue

            time_str = row[0].strip()
            param = row[1].strip()
            value_str = row[2].strip()

            # Parse time
            try:
                time_min = parse_time_to_minutes(time_str)
            except ValueError as exc:
                result["time_errors"].append(
                    {"line": line_num, "time_str": time_str, "error": str(exc)}
                )
                continue

            # Parse value
            float_val, val_error = _safe_float(value_str)

            if val_error:
                result["invalid_count"] += 1
                result["parse_errors"].append(
                    f"Line {line_num} [{param}]: {val_error}"
                )
                float_val = None
                is_sentinel = False
            else:
                is_sentinel = _is_sentinel(float_val)
                if is_sentinel:
                    result["sentinel_count"] += 1

            # Classify parameter
            category = classify_parameter(param)
            result["classification"][param] = category

            # Route: metadata rows (time=0, metadata category)
            if category == "metadata" and math.isclose(time_min, 0.0):
                if float_val is not None and not is_sentinel:
                    result["metadata"][param] = float_val
                    if param == "RecordID":
                        result["record_id"] = int(float_val)
                continue  # Metadata rows not stored in parameters dict

            # Store observation
            result["raw_observations"] += 1
            if param not in result["parameters"]:
                result["parameters"][param] = []
            result["parameters"][param].append(
                (time_min, float_val, is_sentinel, val_error)
            )

            if float_val is not None:
                times.append(time_min)

    # Summary statistics
    result["unique_params"] = len(result["parameters"])
    if times:
        result["earliest_time_min"] = min(times)
        result["latest_time_min"] = max(times)
        result["duration_hours"] = (max(times) - min(times)) / 60.0

    return result


# -----------------------------------------------------------------------
# Metadata extraction helper
# -----------------------------------------------------------------------

def parse_metadata(record_data: dict[str, Any]) -> dict[str, Any]:
    """
    Extract and return the metadata sub-dict from a parsed record.

    Parameters
    ----------
    record_data : dict
        Output of parse_record().

    Returns
    -------
    dict
        Patient metadata including RecordID, Age, Gender, ICUType, etc.
    """
    return dict(record_data.get("metadata", {}))


# -----------------------------------------------------------------------
# Parameter summary for audit
# -----------------------------------------------------------------------

def summarize_parameters(
    record_data: dict[str, Any]
) -> dict[str, dict[str, Any]]:
    """
    Compute per-parameter summary statistics from a parsed record.

    Parameters
    ----------
    record_data : dict
        Output of parse_record().

    Returns
    -------
    dict
        param_name →
            {obs_count, sentinel_count, invalid_count, min_time, max_time,
             category, has_valid_values}
    """
    summary: dict[str, dict[str, Any]] = {}
    for param, obs_list in record_data["parameters"].items():
        obs_count = len(obs_list)
        sentinel_count = sum(1 for _, _, is_s, _ in obs_list if is_s)
        invalid_count = sum(1 for _, v, _, _ in obs_list if v is None)
        times = [t for t, v, is_s, _ in obs_list if v is not None and not is_s]
        summary[param] = {
            "obs_count": obs_count,
            "sentinel_count": sentinel_count,
            "invalid_count": invalid_count,
            "min_time_min": min(times) if times else None,
            "max_time_min": max(times) if times else None,
            "category": record_data["classification"].get(param, "unknown"),
            "has_valid_values": (obs_count - sentinel_count - invalid_count) > 0,
        }
    return summary

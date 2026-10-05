"""
CSCM-IoMT: WESAD Dataset Loader
=================================
Loads WESAD subject .pkl files one subject at a time.

Key design decisions:
  - Each subject .pkl is loaded, inspected, and released before the next.
    (S2.pkl alone is ~930 MB — never load all subjects simultaneously.)
  - The loader verifies actual pkl structure and reports deviations from
    expected WESAD format rather than silently assuming correctness.
  - NaN and Inf counts are computed per modality.
  - Labels are validated against the documented set {0,1,2,3,4,5,6,7}.
  - Labels 5/6/7 are reported but flagged as ignored per WESAD docs.
  - The loader does NOT rename or modify any file.

Expected pkl structure (WESAD documented)::

    {
        'subject': 'S2',
        'signal': {
            'chest': {
                'ACC': np.ndarray,  # shape (N, 3) at 700 Hz
                'ECG': np.ndarray,  # shape (N, 1) at 700 Hz
                'EDA': np.ndarray,  # shape (N, 1) at 700 Hz
                'EMG': np.ndarray,  # shape (N, 1) at 700 Hz
                'RESP': np.ndarray, # shape (N, 1) at 700 Hz
                'Temp': np.ndarray, # shape (N, 1) at 700 Hz
            },
            'wrist': {
                'ACC': np.ndarray,  # shape (M, 3) at 32 Hz
                'BVP': np.ndarray,  # shape (K, 1) at 64 Hz
                'EDA': np.ndarray,  # shape (L, 1) at 4 Hz
                'TEMP': np.ndarray, # shape (L, 1) at 4 Hz
            }
        },
        'label': np.ndarray,        # shape (N,) at 700 Hz (chest rate)
    }

Notes:
  - Chest key for temperature is 'Temp' (mixed case).
  - Wrist key for temperature is 'TEMP' (all caps).
  - BVP is a blood volume pulse signal — NOT equivalent to ECG.
  - Cross-location EDA/Temp pairs are different sensor measurements.

Usage::

    from src.data.wesad_loader import load_subject_pkl, validate_subject

    subject_data = load_subject_pkl(Path("WESAD/WESAD/S2"), subject_id="S2")
    report = validate_subject("S2", subject_data)
    del subject_data  # Free ~930 MB
"""

from __future__ import annotations

import gc
import math
import pickle
from pathlib import Path
from typing import Any, Optional

import numpy as np

from src.utils.logging import get_logger

logger = get_logger(__name__)

# -----------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------

# Documented WESAD sampling rates (Hz)
CHEST_RATE_HZ: int = 700
WRIST_ACC_RATE_HZ: int = 32
WRIST_BVP_RATE_HZ: int = 64
WRIST_EDA_RATE_HZ: int = 4
WRIST_TEMP_RATE_HZ: int = 4

# Expected pkl structure
EXPECTED_TOP_KEYS: set[str] = {"subject", "signal", "label"}
EXPECTED_SIGNAL_KEYS: set[str] = {"chest", "wrist"}
EXPECTED_CHEST_KEYS: set[str] = {"ACC", "ECG", "EDA", "EMG", "RESP", "Temp"}
EXPECTED_WRIST_KEYS: set[str] = {"ACC", "BVP", "EDA", "TEMP"}

# Valid and ignored labels per WESAD documentation
VALID_LABELS: set[int] = {0, 1, 2, 3, 4}
IGNORED_LABELS: set[int] = {5, 6, 7}
LABEL_NAMES: dict[int, str] = {
    0: "transient",
    1: "baseline",
    2: "stress",
    3: "amusement",
    4: "meditation",
    5: "ignored",
    6: "ignored",
    7: "ignored",
}

# -----------------------------------------------------------------------
# File integrity check
# -----------------------------------------------------------------------

def check_subject_files(subject_dir: Path, subject_id: str) -> dict[str, Any]:
    """
    Check which expected files exist for a subject.

    Parameters
    ----------
    subject_dir : Path
        Subject directory (e.g., WESAD/WESAD/S2/).
    subject_id : str
        Subject identifier (e.g., 'S2').

    Returns
    -------
    dict
        {
            'subject_dir_exists': bool,
            'pkl': {'path': Path, 'exists': bool, 'size_bytes': int|None},
            'respiban': {'path': Path, 'exists': bool},
            'e4_zip': {'path': Path, 'exists': bool},
            'quest_csv': {'path': Path, 'exists': bool},
            'readme': {'path': Path, 'exists': bool},
            'missing_files': [str],
        }
    """
    result: dict[str, Any] = {
        "subject_dir_exists": subject_dir.exists() and subject_dir.is_dir(),
        "missing_files": [],
    }

    expected_files = {
        "pkl":       f"{subject_id}.pkl",
        "respiban":  f"{subject_id}_respiban.txt",
        "e4_zip":    f"{subject_id}_E4_Data.zip",
        "quest_csv": f"{subject_id}_quest.csv",
        "readme":    f"{subject_id}_readme.txt",
    }

    for key, fname in expected_files.items():
        fpath = subject_dir / fname
        exists = fpath.is_file()
        info: dict[str, Any] = {"path": fpath, "exists": exists}
        if key == "pkl" and exists:
            info["size_bytes"] = fpath.stat().st_size
        result[key] = info
        if not exists:
            result["missing_files"].append(fname)

    return result


# -----------------------------------------------------------------------
# PKL loading
# -----------------------------------------------------------------------

def load_subject_pkl(subject_dir: Path, subject_id: str) -> dict[str, Any]:
    """
    Load a subject's .pkl file.

    IMPORTANT: The caller is responsible for deleting the returned dict
    and calling gc.collect() after processing, to free ~1 GB of memory.

    Parameters
    ----------
    subject_dir : Path
        Directory for the subject (e.g., WESAD/WESAD/S2/).
    subject_id : str
        Subject identifier (e.g., 'S2').

    Returns
    -------
    dict
        Raw loaded pickle content. Structure is verified by validate_subject().

    Raises
    ------
    FileNotFoundError
        If the .pkl file does not exist.
    pickle.UnpicklingError
        If the .pkl file cannot be deserialized.
    MemoryError
        If there is insufficient RAM to load the file.
    """
    pkl_path = subject_dir / f"{subject_id}.pkl"
    if not pkl_path.exists():
        raise FileNotFoundError(f"PKL file not found: {pkl_path}")

    logger.info("Loading %s (%.1f MB)…", pkl_path.name, pkl_path.stat().st_size / 1e6)

    with open(pkl_path, "rb") as fh:
        data = pickle.load(fh, encoding="latin1")

    logger.info("Loaded %s successfully.", pkl_path.name)
    return data


# -----------------------------------------------------------------------
# Structure inspection
# -----------------------------------------------------------------------

def inspect_pkl_keys(data: dict) -> dict[str, Any]:
    """
    Inspect and report the top-level and nested key structure of the pkl.

    Parameters
    ----------
    data : dict
        Loaded pkl content.

    Returns
    -------
    dict
        {
            'top_level_keys': list[str],
            'missing_top_keys': list[str],
            'unexpected_top_keys': list[str],
            'signal_keys': list[str] | None,
            'chest_keys': list[str] | None,
            'wrist_keys': list[str] | None,
            'missing_chest_keys': list[str],
            'missing_wrist_keys': list[str],
        }
    """
    top_keys = set(data.keys()) if isinstance(data, dict) else set()
    missing_top = sorted(EXPECTED_TOP_KEYS - top_keys)
    unexpected_top = sorted(top_keys - EXPECTED_TOP_KEYS - IGNORED_LABELS)

    result: dict[str, Any] = {
        "top_level_keys": sorted(top_keys),
        "missing_top_keys": missing_top,
        "unexpected_top_keys": [k for k in unexpected_top if k not in ("", None)],
        "signal_keys": None,
        "chest_keys": None,
        "wrist_keys": None,
        "missing_chest_keys": [],
        "missing_wrist_keys": [],
    }

    if "signal" in data and isinstance(data["signal"], dict):
        sig = data["signal"]
        result["signal_keys"] = sorted(sig.keys())

        if "chest" in sig and isinstance(sig["chest"], dict):
            chest_keys = set(sig["chest"].keys())
            result["chest_keys"] = sorted(chest_keys)
            result["missing_chest_keys"] = sorted(EXPECTED_CHEST_KEYS - chest_keys)

        if "wrist" in sig and isinstance(sig["wrist"], dict):
            wrist_keys = set(sig["wrist"].keys())
            result["wrist_keys"] = sorted(wrist_keys)
            result["missing_wrist_keys"] = sorted(EXPECTED_WRIST_KEYS - wrist_keys)

    return result


# -----------------------------------------------------------------------
# Signal statistics
# -----------------------------------------------------------------------

def _array_stats(arr: Any, name: str) -> dict[str, Any]:
    """
    Compute statistics for a numpy array.

    Parameters
    ----------
    arr : array-like
        Signal array.
    name : str
        Signal name (for logging).

    Returns
    -------
    dict
        Shape, dtype, NaN count, Inf count, finite fraction, min, max, mean, std.
    """
    if not isinstance(arr, np.ndarray):
        try:
            arr = np.array(arr)
        except Exception as exc:
            return {
                "error": f"Cannot convert to numpy array: {exc}",
                "shape": None,
                "dtype": str(type(arr)),
            }

    shape = arr.shape
    dtype = str(arr.dtype)
    total = arr.size

    if total == 0:
        return {
            "shape": shape, "dtype": dtype, "total_elements": 0,
            "nan_count": 0, "inf_count": 0, "finite_fraction": None,
            "min": None, "max": None, "mean": None, "std": None,
        }

    # Compute stats on float-cast view to avoid integer isnan errors
    try:
        arr_f = arr.astype(float, copy=False)
        nan_count = int(np.sum(np.isnan(arr_f)))
        inf_count = int(np.sum(np.isinf(arr_f)))
        finite_mask = np.isfinite(arr_f)
        finite_fraction = float(finite_mask.sum()) / total

        if finite_mask.any():
            arr_finite = arr_f[finite_mask]
            v_min = float(np.min(arr_finite))
            v_max = float(np.max(arr_finite))
            v_mean = float(np.mean(arr_finite))
            v_std = float(np.std(arr_finite))
        else:
            v_min = v_max = v_mean = v_std = None

    except Exception as exc:
        return {
            "shape": shape, "dtype": dtype, "total_elements": total,
            "stats_error": str(exc),
        }

    return {
        "shape": list(shape),
        "dtype": dtype,
        "total_elements": total,
        "nan_count": nan_count,
        "inf_count": inf_count,
        "finite_fraction": round(finite_fraction, 6),
        "min": v_min,
        "max": v_max,
        "mean": round(v_mean, 6) if v_mean is not None else None,
        "std": round(v_std, 6) if v_std is not None else None,
    }


# -----------------------------------------------------------------------
# Label analysis
# -----------------------------------------------------------------------

def analyze_labels(label_array: Any, subject_id: str) -> dict[str, Any]:
    """
    Analyze the label array for a WESAD subject.

    Parameters
    ----------
    label_array : array-like
        Label array from data['label'].
    subject_id : str
        Subject identifier (for logging/reporting).

    Returns
    -------
    dict
        {
            'shape': list,
            'dtype': str,
            'total_samples': int,
            'duration_seconds': float,    # at 700 Hz
            'label_counts': dict[int, int],
            'valid_label_counts': dict[int, int],
            'ignored_label_counts': dict[int, int],
            'unexpected_labels': list[int],
            'warnings': list[str],
        }
    """
    result: dict[str, Any] = {
        "shape": None,
        "dtype": None,
        "total_samples": 0,
        "duration_seconds": None,
        "label_counts": {},
        "valid_label_counts": {},
        "ignored_label_counts": {},
        "unexpected_labels": [],
        "warnings": [],
    }

    if not isinstance(label_array, np.ndarray):
        try:
            label_array = np.array(label_array)
        except Exception as exc:
            result["warnings"].append(f"Cannot convert label to ndarray: {exc}")
            return result

    result["shape"] = list(label_array.shape)
    result["dtype"] = str(label_array.dtype)
    total = label_array.size
    result["total_samples"] = total
    if total > 0:
        result["duration_seconds"] = round(total / CHEST_RATE_HZ, 2)

    # Count all unique labels
    unique_labels, counts = np.unique(label_array, return_counts=True)
    for lbl, cnt in zip(unique_labels.tolist(), counts.tolist()):
        lbl_int = int(lbl)
        result["label_counts"][lbl_int] = cnt
        if lbl_int in VALID_LABELS:
            result["valid_label_counts"][lbl_int] = cnt
        elif lbl_int in IGNORED_LABELS:
            result["ignored_label_counts"][lbl_int] = cnt
        else:
            result["unexpected_labels"].append(lbl_int)

    if result["unexpected_labels"]:
        result["warnings"].append(
            f"Subject {subject_id}: Unexpected labels found: "
            f"{result['unexpected_labels']}"
        )

    if result["ignored_label_counts"]:
        result["warnings"].append(
            f"Subject {subject_id}: Labels {list(result['ignored_label_counts'].keys())} "
            f"present (will be ignored per WESAD documentation)."
        )

    return result


# -----------------------------------------------------------------------
# Main validation function
# -----------------------------------------------------------------------

def validate_subject(subject_id: str, data: dict) -> dict[str, Any]:
    """
    Perform a full structural and statistical validation of a loaded subject.

    This function does NOT modify the data in any way.

    Parameters
    ----------
    subject_id : str
        Subject identifier (e.g., 'S2').
    data : dict
        Loaded pkl content from load_subject_pkl().

    Returns
    -------
    dict
        Comprehensive validation report:
        {
            'subject_id': str,
            'subject_key_in_pkl': str | None,
            'structure': inspect_pkl_keys() output,
            'chest': {modality: _array_stats() output},
            'wrist': {modality: _array_stats() output},
            'labels': analyze_labels() output,
            'errors': list[str],
            'warnings': list[str],
            'is_valid': bool,
        }
    """
    report: dict[str, Any] = {
        "subject_id": subject_id,
        "subject_key_in_pkl": None,
        "structure": {},
        "chest": {},
        "wrist": {},
        "labels": {},
        "errors": [],
        "warnings": [],
        "is_valid": False,
    }

    if not isinstance(data, dict):
        report["errors"].append(
            f"PKL content is not a dict (got {type(data).__name__})"
        )
        return report

    # ----------------------------------------------------------------
    # Key structure
    # ----------------------------------------------------------------
    report["structure"] = inspect_pkl_keys(data)

    # Subject key
    if "subject" in data:
        report["subject_key_in_pkl"] = str(data["subject"])
        if data["subject"] != subject_id:
            report["warnings"].append(
                f"PKL subject key '{data['subject']}' does not match "
                f"expected '{subject_id}'."
            )

    # ----------------------------------------------------------------
    # Chest signals
    # ----------------------------------------------------------------
    try:
        chest = data.get("signal", {}).get("chest", {})
        for mod_name in sorted(chest.keys()):
            arr = chest[mod_name]
            report["chest"][mod_name] = _array_stats(arr, f"{subject_id}/chest/{mod_name}")
    except Exception as exc:
        report["errors"].append(f"Error reading chest signals: {exc}")

    # ----------------------------------------------------------------
    # Wrist signals
    # ----------------------------------------------------------------
    try:
        wrist = data.get("signal", {}).get("wrist", {})
        for mod_name in sorted(wrist.keys()):
            arr = wrist[mod_name]
            report["wrist"][mod_name] = _array_stats(arr, f"{subject_id}/wrist/{mod_name}")
    except Exception as exc:
        report["errors"].append(f"Error reading wrist signals: {exc}")

    # ----------------------------------------------------------------
    # Labels
    # ----------------------------------------------------------------
    if "label" in data:
        report["labels"] = analyze_labels(data["label"], subject_id)
        report["warnings"].extend(report["labels"].get("warnings", []))
    else:
        report["errors"].append("No 'label' key found in PKL.")

    # ----------------------------------------------------------------
    # Consistency checks
    # ----------------------------------------------------------------
    # Chest signal lengths should all match the label length at 700 Hz
    label_len = report["labels"].get("total_samples", None)
    for mod_name, stats in report["chest"].items():
        if stats.get("shape") is None:
            continue
        # For multi-axis signals (ACC), first dim is time
        chest_len = stats["shape"][0] if stats.get("shape") else None
        if chest_len is not None and label_len is not None:
            if chest_len != label_len:
                report["warnings"].append(
                    f"Chest {mod_name} length ({chest_len}) != label length "
                    f"({label_len}). Expected synchronization at {CHEST_RATE_HZ} Hz."
                )

    # ----------------------------------------------------------------
    # Validity determination
    # ----------------------------------------------------------------
    report["is_valid"] = len(report["errors"]) == 0

    return report

"""
tests/test_wesad_loader.py
===========================
Unit tests for the WESAD data loader.

Tests:
  - Valid PKL structure validation
  - Missing key detection
  - Label validation
  - Signal statistics computation
  - Array statistics edge cases
"""

from __future__ import annotations

import numpy as np
import pytest

from src.data.wesad_loader import (
    inspect_pkl_keys,
    validate_subject,
    analyze_labels,
    check_subject_files,
    _array_stats,
    VALID_LABELS,
    IGNORED_LABELS,
    CHEST_RATE_HZ,
)


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------

def _make_minimal_wesad_data(
    subject: str = "S2",
    n_chest: int = 70000,  # ~100 seconds at 700 Hz
    include_label: bool = True,
    label_values: list[int] | None = None,
) -> dict:
    """Create a minimal well-formed WESAD data dict for testing."""
    if label_values is None:
        label_values = [1] * n_chest  # All baseline

    data = {
        "subject": subject,
        "signal": {
            "chest": {
                "ACC": np.zeros((n_chest, 3), dtype=np.float64),
                "ECG": np.zeros((n_chest, 1), dtype=np.float64),
                "EDA": np.zeros((n_chest, 1), dtype=np.float64),
                "EMG": np.zeros((n_chest, 1), dtype=np.float64),
                "RESP": np.zeros((n_chest, 1), dtype=np.float64),
                "Temp": np.ones((n_chest, 1), dtype=np.float64) * 37.0,
            },
            "wrist": {
                "ACC": np.zeros((n_chest // 22, 3), dtype=np.float64),  # ~32 Hz
                "BVP": np.zeros((n_chest // 11, 1), dtype=np.float64),  # ~64 Hz
                "EDA": np.zeros((n_chest // 175, 1), dtype=np.float64), # ~4 Hz
                "TEMP": np.zeros((n_chest // 175, 1), dtype=np.float64),
            },
        },
        "label": np.array(label_values, dtype=np.int32),
    }
    return data


# -----------------------------------------------------------------------
# inspect_pkl_keys
# -----------------------------------------------------------------------

class TestInspectPklKeys:

    def test_complete_structure(self):
        data = _make_minimal_wesad_data()
        keys = inspect_pkl_keys(data)
        assert keys["missing_top_keys"] == []
        assert "chest" in keys.get("signal_keys", [])
        assert "wrist" in keys.get("signal_keys", [])
        assert keys["missing_chest_keys"] == []
        assert keys["missing_wrist_keys"] == []

    def test_missing_label(self):
        data = _make_minimal_wesad_data()
        del data["label"]
        keys = inspect_pkl_keys(data)
        assert "label" in keys["missing_top_keys"]

    def test_missing_chest_key(self):
        data = _make_minimal_wesad_data()
        del data["signal"]["chest"]["ECG"]
        keys = inspect_pkl_keys(data)
        assert "ECG" in keys["missing_chest_keys"]

    def test_missing_wrist_key(self):
        data = _make_minimal_wesad_data()
        del data["signal"]["wrist"]["BVP"]
        keys = inspect_pkl_keys(data)
        assert "BVP" in keys["missing_wrist_keys"]

    def test_not_dict(self):
        keys = inspect_pkl_keys("not_a_dict")
        assert keys["missing_top_keys"] == sorted({"subject", "signal", "label"})

    def test_top_keys_reported(self):
        data = _make_minimal_wesad_data()
        keys = inspect_pkl_keys(data)
        assert "subject" in keys["top_level_keys"]
        assert "signal" in keys["top_level_keys"]
        assert "label" in keys["top_level_keys"]


# -----------------------------------------------------------------------
# analyze_labels
# -----------------------------------------------------------------------

class TestAnalyzeLabels:

    def test_all_valid_labels(self):
        labels = np.array([0, 1, 2, 3, 4, 1, 2, 1], dtype=np.int32)
        result = analyze_labels(labels, "S_test")
        assert result["unexpected_labels"] == []
        assert 1 in result["valid_label_counts"]
        assert 2 in result["valid_label_counts"]

    def test_ignored_labels_flagged(self):
        labels = np.array([1, 2, 5, 6, 7, 1], dtype=np.int32)
        result = analyze_labels(labels, "S_test")
        assert 5 in result["ignored_label_counts"]
        assert 6 in result["ignored_label_counts"]
        assert 7 in result["ignored_label_counts"]
        assert len(result["warnings"]) > 0

    def test_unexpected_labels(self):
        labels = np.array([1, 2, 99, 100], dtype=np.int32)
        result = analyze_labels(labels, "S_test")
        assert 99 in result["unexpected_labels"]
        assert 100 in result["unexpected_labels"]
        assert len(result["warnings"]) > 0

    def test_duration_calculation(self):
        # 70000 samples at 700 Hz = 100 seconds
        labels = np.ones(70000, dtype=np.int32)
        result = analyze_labels(labels, "S_test")
        assert result["total_samples"] == 70000
        assert abs(result["duration_seconds"] - 100.0) < 1.0

    def test_label_counts_correct(self):
        labels = np.array([1, 1, 2, 2, 2, 3], dtype=np.int32)
        result = analyze_labels(labels, "S_test")
        assert result["label_counts"][1] == 2
        assert result["label_counts"][2] == 3
        assert result["label_counts"][3] == 1

    def test_empty_label_array(self):
        labels = np.array([], dtype=np.int32)
        result = analyze_labels(labels, "S_test")
        assert result["total_samples"] == 0
        assert result["duration_seconds"] is None or result["duration_seconds"] == 0

    def test_non_array_input(self):
        # Should not crash — should try to convert
        result = analyze_labels([1, 2, 2, 3], "S_test")
        assert result["total_samples"] == 4


# -----------------------------------------------------------------------
# _array_stats
# -----------------------------------------------------------------------

class TestArrayStats:

    def test_normal_array(self):
        arr = np.array([[1.0, 2.0, 3.0]] * 100)
        stats = _array_stats(arr, "test")
        assert stats["shape"] == [100, 3]
        assert stats["nan_count"] == 0
        assert stats["inf_count"] == 0
        assert stats["finite_fraction"] == 1.0
        assert stats["mean"] is not None

    def test_nan_detection(self):
        arr = np.array([1.0, np.nan, 3.0])
        stats = _array_stats(arr, "test")
        assert stats["nan_count"] == 1
        assert stats["finite_fraction"] < 1.0

    def test_inf_detection(self):
        arr = np.array([1.0, np.inf, -np.inf, 2.0])
        stats = _array_stats(arr, "test")
        assert stats["inf_count"] == 2

    def test_all_nan(self):
        arr = np.full((10, 1), np.nan)
        stats = _array_stats(arr, "test")
        assert stats["nan_count"] == 10
        assert stats["finite_fraction"] == 0.0
        assert stats["min"] is None
        assert stats["max"] is None

    def test_empty_array(self):
        arr = np.array([], dtype=np.float64)
        stats = _array_stats(arr, "test")
        assert stats["total_elements"] == 0

    def test_integer_array(self):
        arr = np.array([1, 2, 3, 4, 5], dtype=np.int32)
        stats = _array_stats(arr, "test")
        assert stats["nan_count"] == 0
        assert stats["total_elements"] == 5


# -----------------------------------------------------------------------
# validate_subject
# -----------------------------------------------------------------------

class TestValidateSubject:

    def test_valid_subject(self):
        data = _make_minimal_wesad_data("S2")
        report = validate_subject("S2", data)
        assert report["is_valid"] is True
        assert report["errors"] == []

    def test_subject_key_mismatch(self):
        data = _make_minimal_wesad_data("S2")
        data["subject"] = "S99"  # Wrong subject key
        report = validate_subject("S2", data)
        # Should be a warning, not an error
        assert any("S99" in w for w in report["warnings"])

    def test_missing_label_is_error(self):
        data = _make_minimal_wesad_data("S2")
        del data["label"]
        report = validate_subject("S2", data)
        assert report["is_valid"] is False
        assert any("label" in e.lower() for e in report["errors"])

    def test_chest_modalities_reported(self):
        data = _make_minimal_wesad_data("S2")
        report = validate_subject("S2", data)
        assert "ECG" in report["chest"]
        assert "EDA" in report["chest"]
        assert "RESP" in report["chest"]

    def test_wrist_modalities_reported(self):
        data = _make_minimal_wesad_data("S2")
        report = validate_subject("S2", data)
        assert "BVP" in report["wrist"]
        assert "EDA" in report["wrist"]

    def test_not_dict_is_error(self):
        report = validate_subject("S2", "not_a_dict")
        assert report["is_valid"] is False
        assert len(report["errors"]) > 0

    def test_nan_in_signal_detected(self):
        data = _make_minimal_wesad_data("S2", n_chest=700)
        data["signal"]["chest"]["ECG"][0, 0] = np.nan
        report = validate_subject("S2", data)
        ecg_stats = report["chest"].get("ECG", {})
        assert ecg_stats.get("nan_count", 0) >= 1

    def test_ignored_labels_produce_warning(self):
        n = 700
        labels = [1] * (n - 1) + [5]  # One label=5
        data = _make_minimal_wesad_data("S2", n_chest=n, label_values=labels)
        report = validate_subject("S2", data)
        # Ignored labels should produce a warning, not an error
        assert any("5" in w for w in report["warnings"])

    def test_label_stats_populated(self):
        data = _make_minimal_wesad_data("S2", n_chest=700)
        report = validate_subject("S2", data)
        label_info = report.get("labels", {})
        assert label_info.get("total_samples") == 700
        assert label_info.get("duration_seconds") is not None


# -----------------------------------------------------------------------
# check_subject_files
# -----------------------------------------------------------------------

class TestCheckSubjectFiles:

    def test_nonexistent_directory(self, tmp_path):
        fake_dir = tmp_path / "S99"
        result = check_subject_files(fake_dir, "S99")
        assert result["subject_dir_exists"] is False
        assert "S99.pkl" in result["missing_files"]

    def test_existing_directory_missing_pkl(self, tmp_path):
        subj_dir = tmp_path / "S2"
        subj_dir.mkdir()
        result = check_subject_files(subj_dir, "S2")
        assert result["subject_dir_exists"] is True
        assert "S2.pkl" in result["missing_files"]

    def test_existing_files_detected(self, tmp_path):
        subj_dir = tmp_path / "S2"
        subj_dir.mkdir()
        # Create dummy files
        for fname in ["S2.pkl", "S2_quest.csv", "S2_readme.txt"]:
            (subj_dir / fname).write_bytes(b"dummy")
        result = check_subject_files(subj_dir, "S2")
        assert result["pkl"]["exists"] is True
        assert result["quest_csv"]["exists"] is True
        assert result["readme"]["exists"] is True
        assert "S2.pkl" not in result["missing_files"]

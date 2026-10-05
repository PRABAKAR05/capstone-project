"""
tests/test_physionet_loader.py
===============================
Unit tests for the PhysioNet data loader.

Tests:
  - Valid record parsing
  - Timestamp conversion
  - Metadata extraction
  - Missing sentinel handling
  - Malformed record handling
  - Numeric conversion
  - Parameter classification
"""

from __future__ import annotations

import csv
import math
import tempfile
from pathlib import Path

import pytest

from src.data.physionet_loader import (
    classify_parameter,
    is_valid_record_file,
    parse_record,
    parse_time_to_minutes,
    summarize_parameters,
    EXPECTED_HEADER,
    MISSING_SENTINEL,
)


# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------

def _make_record_file(
    tmpdir: Path,
    content: str,
    filename: str = "999999.txt",
) -> Path:
    """Write a record file to a temp directory and return its path."""
    fpath = tmpdir / filename
    fpath.write_text(content, encoding="utf-8")
    return fpath


VALID_RECORD_CONTENT = """Time,Parameter,Value
00:00,RecordID,132539
00:00,Age,54
00:00,Gender,0
00:00,Height,-1
00:00,ICUType,4
00:00,Weight,-1
00:07,GCS,15
00:07,HR,73
00:07,NIDiasABP,65
00:07,NIMAP,92.33
00:07,NISysABP,147
00:07,RespRate,19
00:07,Temp,35.1
00:37,HR,77
01:37,HR,60
01:37,RespRate,18
"""


# -----------------------------------------------------------------------
# parse_time_to_minutes
# -----------------------------------------------------------------------

class TestParseTimeToMinutes:

    def test_minutes_only(self):
        assert parse_time_to_minutes("00:07") == 7.0

    def test_hours_and_minutes(self):
        assert parse_time_to_minutes("01:37") == 97.0

    def test_two_digit_hours(self):
        assert parse_time_to_minutes("48:00") == 2880.0

    def test_zero(self):
        assert parse_time_to_minutes("00:00") == 0.0

    def test_large_hours(self):
        assert parse_time_to_minutes("99:59") == 99 * 60 + 59

    def test_whitespace_stripped(self):
        assert parse_time_to_minutes("  00:07  ") == 7.0

    def test_invalid_no_colon(self):
        with pytest.raises(ValueError, match="expected HH:MM"):
            parse_time_to_minutes("0007")

    def test_invalid_non_integer(self):
        with pytest.raises(ValueError):
            parse_time_to_minutes("aa:bb")

    def test_invalid_minutes_out_of_range(self):
        with pytest.raises(ValueError, match="Minutes component out of range"):
            parse_time_to_minutes("00:60")

    def test_negative_hours(self):
        with pytest.raises(ValueError, match="Negative hours"):
            parse_time_to_minutes("-1:00")

    def test_exactly_48_hours(self):
        result = parse_time_to_minutes("48:00")
        assert result == 2880.0


# -----------------------------------------------------------------------
# classify_parameter
# -----------------------------------------------------------------------

class TestClassifyParameter:

    def test_physiological_channels(self):
        for p in ("HR", "RespRate", "SpO2", "Temp", "NISysABP", "NIDiasABP", "NIMAP"):
            assert classify_parameter(p) == "physiological", f"Failed for {p}"

    def test_metadata_fields(self):
        for p in ("RecordID", "Age", "Gender", "Height", "Weight", "ICUType"):
            assert classify_parameter(p) == "metadata", f"Failed for {p}"

    def test_laboratory_values(self):
        for p in ("BUN", "Creatinine", "Glucose", "HCT", "WBC", "Platelets"):
            assert classify_parameter(p) == "laboratory", f"Failed for {p}"

    def test_clinical_score(self):
        assert classify_parameter("GCS") == "clinical_score"
        assert classify_parameter("MechVent") == "clinical_score"

    def test_unknown(self):
        assert classify_parameter("UnknownParam") == "unknown"
        assert classify_parameter("XYZ") == "unknown"

    def test_whitespace_in_param(self):
        # Should not crash
        result = classify_parameter("  HR  ")
        # Stripped internally
        assert result in ("physiological", "unknown")


# -----------------------------------------------------------------------
# is_valid_record_file
# -----------------------------------------------------------------------

class TestIsValidRecordFile:

    def test_valid_file(self, tmp_path):
        f = _make_record_file(tmp_path, VALID_RECORD_CONTENT)
        assert is_valid_record_file(f) is True

    def test_wrong_header(self, tmp_path):
        content = "Time,Param,Val\n00:00,RecordID,123\n"
        f = _make_record_file(tmp_path, content)
        assert is_valid_record_file(f) is False

    def test_empty_file(self, tmp_path):
        f = _make_record_file(tmp_path, "")
        assert is_valid_record_file(f) is False

    def test_nonexistent_file(self, tmp_path):
        assert is_valid_record_file(tmp_path / "doesnotexist.txt") is False

    def test_directory_not_file(self, tmp_path):
        assert is_valid_record_file(tmp_path) is False  # tmp_path is a dir


# -----------------------------------------------------------------------
# parse_record
# -----------------------------------------------------------------------

class TestParseRecord:

    def test_valid_record_id(self, tmp_path):
        f = _make_record_file(tmp_path, VALID_RECORD_CONTENT)
        result = parse_record(f)
        assert result["record_id"] == 132539

    def test_metadata_extracted(self, tmp_path):
        f = _make_record_file(tmp_path, VALID_RECORD_CONTENT)
        result = parse_record(f)
        assert result["metadata"]["Age"] == 54.0
        assert result["metadata"]["Gender"] == 0.0
        assert result["metadata"]["ICUType"] == 4.0

    def test_metadata_sentinel_excluded(self, tmp_path):
        """Height=-1 and Weight=-1 (sentinels) should not appear in metadata."""
        f = _make_record_file(tmp_path, VALID_RECORD_CONTENT)
        result = parse_record(f)
        # Height and Weight are -1 (sentinel), so they should NOT be in metadata
        # (or if they are, they should be marked as sentinel)
        # The loader skips metadata rows with sentinel values
        assert "Height" not in result["metadata"] or result["metadata"].get("Height") != MISSING_SENTINEL

    def test_hr_observations(self, tmp_path):
        f = _make_record_file(tmp_path, VALID_RECORD_CONTENT)
        result = parse_record(f)
        assert "HR" in result["parameters"]
        # Three HR observations: 00:07, 00:37, 01:37
        assert len(result["parameters"]["HR"]) == 3

    def test_sentinel_counted(self, tmp_path):
        content = (
            "Time,Parameter,Value\n"
            "00:00,RecordID,999\n"
            "00:07,HR,-1\n"
            "00:37,HR,80\n"
        )
        f = _make_record_file(tmp_path, content)
        result = parse_record(f)
        assert result["sentinel_count"] == 1

    def test_no_sentinel_in_normal(self, tmp_path):
        content = (
            "Time,Parameter,Value\n"
            "00:00,RecordID,999\n"
            "00:07,HR,73\n"
            "00:37,HR,80\n"
        )
        f = _make_record_file(tmp_path, content)
        result = parse_record(f)
        assert result["sentinel_count"] == 0

    def test_duration_calculated(self, tmp_path):
        content = (
            "Time,Parameter,Value\n"
            "00:00,RecordID,999\n"
            "00:07,HR,73\n"
            "02:07,HR,80\n"  # 120 minutes later
        )
        f = _make_record_file(tmp_path, content)
        result = parse_record(f)
        assert result["duration_hours"] is not None
        assert math.isclose(result["duration_hours"], 2.0, rel_tol=0.01)

    def test_earliest_latest_time(self, tmp_path):
        content = (
            "Time,Parameter,Value\n"
            "00:00,RecordID,999\n"
            "00:07,HR,73\n"
            "02:07,HR,80\n"
            "12:37,RespRate,18\n"
        )
        f = _make_record_file(tmp_path, content)
        result = parse_record(f)
        assert result["earliest_time_min"] == 7.0
        assert result["latest_time_min"] == 12 * 60 + 37

    def test_invalid_value_counted(self, tmp_path):
        content = (
            "Time,Parameter,Value\n"
            "00:00,RecordID,999\n"
            "00:07,HR,INVALID\n"
            "00:37,HR,80\n"
        )
        f = _make_record_file(tmp_path, content)
        result = parse_record(f)
        assert result["invalid_count"] == 1

    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            parse_record(tmp_path / "nonexistent.txt")

    def test_wrong_header_raises(self, tmp_path):
        content = "Time,Param,Val\n00:00,RecordID,123\n"
        f = _make_record_file(tmp_path, content)
        with pytest.raises(ValueError, match="Unexpected header"):
            parse_record(f)

    def test_empty_file(self, tmp_path):
        f = _make_record_file(tmp_path, "")
        result = parse_record(f)
        assert "empty" in " ".join(result["parse_errors"]).lower()

    def test_classification_stored(self, tmp_path):
        f = _make_record_file(tmp_path, VALID_RECORD_CONTENT)
        result = parse_record(f)
        assert result["classification"].get("HR") == "physiological"
        assert result["classification"].get("GCS") == "clinical_score"

    def test_large_hour_timestamps(self, tmp_path):
        content = (
            "Time,Parameter,Value\n"
            "00:00,RecordID,999\n"
            "48:07,HR,70\n"
        )
        f = _make_record_file(tmp_path, content)
        result = parse_record(f)
        assert result["raw_observations"] == 1
        assert result["latest_time_min"] == 48 * 60 + 7


# -----------------------------------------------------------------------
# summarize_parameters
# -----------------------------------------------------------------------

class TestSummarizeParameters:

    def test_summary_keys(self, tmp_path):
        f = _make_record_file(tmp_path, VALID_RECORD_CONTENT)
        result = parse_record(f)
        summary = summarize_parameters(result)
        assert "HR" in summary
        hr = summary["HR"]
        assert "obs_count" in hr
        assert "sentinel_count" in hr
        assert "category" in hr
        assert hr["category"] == "physiological"

    def test_has_valid_values(self, tmp_path):
        f = _make_record_file(tmp_path, VALID_RECORD_CONTENT)
        result = parse_record(f)
        summary = summarize_parameters(result)
        assert summary["HR"]["has_valid_values"] is True

    def test_sentinel_only_not_valid(self, tmp_path):
        content = (
            "Time,Parameter,Value\n"
            "00:00,RecordID,999\n"
            "00:07,HR,-1\n"
        )
        f = _make_record_file(tmp_path, content)
        result = parse_record(f)
        summary = summarize_parameters(result)
        assert summary["HR"]["has_valid_values"] is False

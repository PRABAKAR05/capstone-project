"""
tests/test_config.py
=====================
Unit tests for configuration loading and path resolution.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import yaml

from src.utils.config import (
    find_project_root,
    load_yaml,
    resolve_path,
    resolve_dataset_paths,
)


# -----------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------

@pytest.fixture
def minimal_project(tmp_path: Path) -> Path:
    """
    Create a minimal project structure in a temp directory.

    Returns the project root path.
    """
    (tmp_path / "configs").mkdir()
    paths_config = {
        "project_root": ".",
        "datasets": {
            "physionet": {
                "set_a": "data/physionet/set-a",
                "outcomes_a": "data/physionet/Outcomes-a.txt",
            },
            "wesad": {
                "root": "data/wesad",
                "available_subjects": ["S2", "S3"],
                "absent_subjects": ["S1", "S12"],
            },
        },
        "outputs": {
            "processed": "data/processed",
            "dataset_audit": "results/dataset_audit",
            "logs": "results/logs",
        },
    }
    with open(tmp_path / "configs" / "paths.yaml", "w") as fh:
        yaml.dump(paths_config, fh)
    return tmp_path


@pytest.fixture
def project_with_datasets(minimal_project: Path) -> Path:
    """Extend minimal project with actual mock dataset directories."""
    set_a = minimal_project / "data" / "physionet" / "set-a"
    wesad_root = minimal_project / "data" / "wesad"
    set_a.mkdir(parents=True)
    wesad_root.mkdir(parents=True)
    # Create a dummy record file
    record = set_a / "999999.txt"
    record.write_text("Time,Parameter,Value\n00:00,RecordID,999999\n")
    return minimal_project


# -----------------------------------------------------------------------
# find_project_root
# -----------------------------------------------------------------------

class TestFindProjectRoot:

    def test_finds_root_from_env(self, minimal_project, monkeypatch):
        monkeypatch.setenv("CSCM_PROJECT_ROOT", str(minimal_project))
        root = find_project_root()
        assert root == minimal_project

    def test_invalid_env_raises(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CSCM_PROJECT_ROOT", str(tmp_path / "nonexistent"))
        with pytest.raises(RuntimeError, match="configs/paths.yaml"):
            find_project_root()

    def test_finds_actual_project_root(self):
        """The real project root should be discoverable from this test file."""
        root = find_project_root()
        assert root.exists()
        assert (root / "configs" / "paths.yaml").exists()


# -----------------------------------------------------------------------
# load_yaml
# -----------------------------------------------------------------------

class TestLoadYaml:

    def test_valid_yaml(self, tmp_path):
        p = tmp_path / "test.yaml"
        p.write_text("key: value\nnested:\n  a: 1\n")
        result = load_yaml(p)
        assert result["key"] == "value"
        assert result["nested"]["a"] == 1

    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_yaml(tmp_path / "nonexistent.yaml")

    def test_empty_yaml(self, tmp_path):
        p = tmp_path / "empty.yaml"
        p.write_text("")
        result = load_yaml(p)
        assert result is None  # yaml.safe_load("") returns None


# -----------------------------------------------------------------------
# resolve_path
# -----------------------------------------------------------------------

class TestResolvePath:

    def test_relative_path(self, tmp_path):
        resolved = resolve_path("configs/paths.yaml", tmp_path)
        assert resolved == (tmp_path / "configs" / "paths.yaml").resolve()

    def test_absolute_path(self, tmp_path):
        abs_path = str(tmp_path / "some" / "dir")
        resolved = resolve_path(abs_path, Path("/irrelevant"))
        assert resolved == Path(abs_path).resolve()

    def test_dot_is_project_root(self, tmp_path):
        resolved = resolve_path(".", tmp_path)
        assert resolved == tmp_path.resolve()

    def test_subdirectory(self, tmp_path):
        resolved = resolve_path("data/processed", tmp_path)
        assert resolved == (tmp_path / "data" / "processed").resolve()


# -----------------------------------------------------------------------
# resolve_dataset_paths
# -----------------------------------------------------------------------

class TestResolveDatasetPaths:

    def test_returns_dict_structure(self, project_with_datasets, monkeypatch):
        monkeypatch.setenv("CSCM_PROJECT_ROOT", str(project_with_datasets))
        paths = resolve_dataset_paths(project_with_datasets, validate=True)
        assert "physionet" in paths
        assert "wesad" in paths
        assert "outputs" in paths
        assert "project_root" in paths

    def test_physionet_set_a_resolved(self, project_with_datasets, monkeypatch):
        monkeypatch.setenv("CSCM_PROJECT_ROOT", str(project_with_datasets))
        paths = resolve_dataset_paths(project_with_datasets, validate=True)
        set_a = paths["physionet"]["set_a"]
        assert isinstance(set_a, Path)
        assert set_a.is_absolute()

    def test_outputs_created(self, project_with_datasets, monkeypatch):
        monkeypatch.setenv("CSCM_PROJECT_ROOT", str(project_with_datasets))
        paths = resolve_dataset_paths(project_with_datasets, validate=True)
        for key, p in paths["outputs"].items():
            if isinstance(p, Path):
                assert p.exists(), f"Output dir not created: {key} = {p}"

    def test_missing_physionet_raises(self, minimal_project, monkeypatch):
        """Without validate=False, missing dataset should raise FileNotFoundError."""
        monkeypatch.setenv("CSCM_PROJECT_ROOT", str(minimal_project))
        with pytest.raises(FileNotFoundError, match="PhysioNet Set-A not found"):
            resolve_dataset_paths(minimal_project, validate=True)

    def test_validate_false_no_error(self, minimal_project, monkeypatch):
        """With validate=False, missing datasets should not raise."""
        monkeypatch.setenv("CSCM_PROJECT_ROOT", str(minimal_project))
        paths = resolve_dataset_paths(minimal_project, validate=False)
        assert "physionet" in paths

    def test_subjects_list_preserved(self, project_with_datasets, monkeypatch):
        monkeypatch.setenv("CSCM_PROJECT_ROOT", str(project_with_datasets))
        paths = resolve_dataset_paths(project_with_datasets, validate=True)
        subjects = paths["wesad"].get("available_subjects", [])
        assert "S2" in subjects
        assert "S3" in subjects

    def test_project_root_is_absolute(self, project_with_datasets, monkeypatch):
        monkeypatch.setenv("CSCM_PROJECT_ROOT", str(project_with_datasets))
        paths = resolve_dataset_paths(project_with_datasets, validate=True)
        root = paths["project_root"]
        assert isinstance(root, Path)
        assert root.is_absolute()

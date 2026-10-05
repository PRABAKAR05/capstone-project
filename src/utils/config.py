"""
CSCM-IoMT Configuration Loader
===============================
Reads configs/paths.yaml and other YAML configs.
Resolves relative paths against the project root.
Validates that configured paths actually exist.

Usage::

    from src.utils.config import load_paths_config, resolve_dataset_paths

    paths = resolve_dataset_paths()
    print(paths["physionet"]["set_a"])  # absolute Path object

"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import yaml


# -----------------------------------------------------------------------
# Project root detection
# -----------------------------------------------------------------------

def find_project_root() -> Path:
    """
    Locate the project root directory (capstone_PRABAKAR/).

    Strategy:
      1. Check if the current working directory contains configs/paths.yaml.
      2. Walk upward from this file's location until configs/paths.yaml is found.
      3. Raise RuntimeError if not found.

    Returns
    -------
    Path
        Absolute path to the project root.

    Raises
    ------
    RuntimeError
        If the project root cannot be determined.
    """
    # Option 1: environment variable override
    env_root = os.environ.get("CSCM_PROJECT_ROOT")
    if env_root:
        p = Path(env_root).resolve()
        if (p / "configs" / "paths.yaml").exists():
            return p
        raise RuntimeError(
            f"CSCM_PROJECT_ROOT is set to '{env_root}' but "
            f"configs/paths.yaml was not found there."
        )

    # Option 2: walk upward from this file
    here = Path(__file__).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "configs" / "paths.yaml").exists():
            return candidate

    # Option 3: try current working directory
    cwd = Path.cwd().resolve()
    if (cwd / "configs" / "paths.yaml").exists():
        return cwd

    raise RuntimeError(
        "Cannot find project root. Expected to find configs/paths.yaml "
        "in or above the current directory. "
        "Set the CSCM_PROJECT_ROOT environment variable or run scripts "
        "from the capstone_PRABAKAR/ directory."
    )


# -----------------------------------------------------------------------
# YAML loading
# -----------------------------------------------------------------------

def load_yaml(config_path: Path) -> dict[str, Any]:
    """
    Load a YAML file and return its contents as a dict.

    Parameters
    ----------
    config_path : Path
        Absolute path to the YAML file.

    Returns
    -------
    dict
        Parsed YAML contents.

    Raises
    ------
    FileNotFoundError
        If the config file does not exist.
    yaml.YAMLError
        If the YAML file cannot be parsed.
    """
    if not config_path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {config_path}"
        )
    with open(config_path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def load_paths_config(project_root: Path | None = None) -> dict[str, Any]:
    """
    Load configs/paths.yaml.

    Parameters
    ----------
    project_root : Path, optional
        Project root directory. Auto-detected if not provided.

    Returns
    -------
    dict
        Raw paths configuration.
    """
    if project_root is None:
        project_root = find_project_root()
    return load_yaml(project_root / "configs" / "paths.yaml")


def load_physionet_config(project_root: Path | None = None) -> dict[str, Any]:
    """Load configs/physionet.yaml."""
    if project_root is None:
        project_root = find_project_root()
    return load_yaml(project_root / "configs" / "physionet.yaml")


def load_wesad_config(project_root: Path | None = None) -> dict[str, Any]:
    """Load configs/wesad.yaml."""
    if project_root is None:
        project_root = find_project_root()
    return load_yaml(project_root / "configs" / "wesad.yaml")


# -----------------------------------------------------------------------
# Path resolution and validation
# -----------------------------------------------------------------------

def resolve_path(raw: str, project_root: Path) -> Path:
    """
    Resolve a raw path string against the project root.

    Rules:
      - If raw is already absolute, return it directly.
      - Otherwise, resolve relative to project_root.

    Parameters
    ----------
    raw : str
        Path string from YAML config.
    project_root : Path
        Absolute project root.

    Returns
    -------
    Path
        Resolved absolute Path.
    """
    p = Path(raw)
    if p.is_absolute():
        return p.resolve()
    return (project_root / p).resolve()


def resolve_dataset_paths(
    project_root: Path | None = None,
    validate: bool = True,
) -> dict[str, Any]:
    """
    Load paths.yaml and resolve all dataset paths to absolute Path objects.

    Parameters
    ----------
    project_root : Path, optional
        Project root. Auto-detected if not provided.
    validate : bool
        If True, raise FileNotFoundError for missing required paths.

    Returns
    -------
    dict
        Resolved paths dict with structure::

            {
                "project_root": Path,
                "physionet": {
                    "set_a": Path,
                    "outcomes_a": Path,
                    ...
                },
                "wesad": {
                    "root": Path,
                    "available_subjects": [str, ...],
                },
                "outputs": {
                    "processed": Path,
                    "dataset_audit": Path,
                    ...
                },
            }

    Raises
    ------
    FileNotFoundError
        If validate=True and a required dataset path does not exist.
    RuntimeError
        If project root cannot be determined.
    """
    if project_root is None:
        project_root = find_project_root()

    raw_cfg = load_paths_config(project_root)

    # ----------------------------------------------------------------
    # PhysioNet paths
    # ----------------------------------------------------------------
    pn_cfg = raw_cfg.get("datasets", {}).get("physionet", {})
    physionet_paths: dict[str, Any] = {}
    for key, raw_value in pn_cfg.items():
        if isinstance(raw_value, str):
            physionet_paths[key] = resolve_path(raw_value, project_root)
        else:
            physionet_paths[key] = raw_value  # non-string values pass through

    # ----------------------------------------------------------------
    # WESAD paths
    # ----------------------------------------------------------------
    wesad_cfg = raw_cfg.get("datasets", {}).get("wesad", {})
    wesad_paths: dict[str, Any] = {}
    for key, raw_value in wesad_cfg.items():
        if isinstance(raw_value, str):
            wesad_paths[key] = resolve_path(raw_value, project_root)
        elif isinstance(raw_value, list):
            wesad_paths[key] = raw_value  # subject lists etc.
        else:
            wesad_paths[key] = raw_value

    # ----------------------------------------------------------------
    # Output paths — create if missing
    # ----------------------------------------------------------------
    out_cfg = raw_cfg.get("outputs", {})
    output_paths: dict[str, Any] = {}
    for key, raw_value in out_cfg.items():
        if isinstance(raw_value, str):
            p = resolve_path(raw_value, project_root)
            p.mkdir(parents=True, exist_ok=True)
            output_paths[key] = p
        else:
            output_paths[key] = raw_value

    # ----------------------------------------------------------------
    # Validation of required inputs
    # ----------------------------------------------------------------
    errors: list[str] = []
    warnings: list[str] = []

    if validate:
        # PhysioNet Set-A is required
        set_a = physionet_paths.get("set_a")
        if set_a and not set_a.exists():
            errors.append(
                f"PhysioNet Set-A not found: {set_a}\n"
                f"  Configure the correct path in configs/paths.yaml "
                f"under datasets.physionet.set_a"
            )

        # WESAD root is required
        wesad_root = wesad_paths.get("root")
        if wesad_root and not wesad_root.exists():
            errors.append(
                f"WESAD root not found: {wesad_root}\n"
                f"  Configure the correct path in configs/paths.yaml "
                f"under datasets.wesad.root"
            )

        # Outcomes-A is optional but warn if missing
        oa = physionet_paths.get("outcomes_a")
        if oa and not oa.exists():
            warnings.append(f"PhysioNet Outcomes-A not found (optional): {oa}")

        if errors:
            msg = "\n".join(["[CONFIG ERROR]"] + errors)
            raise FileNotFoundError(msg)

    # ----------------------------------------------------------------
    # Check for WESAD subject ambiguity
    # ----------------------------------------------------------------
    wesad_root = wesad_paths.get("root")
    if wesad_root and wesad_root.exists():
        discovered = sorted(
            [d.name for d in wesad_root.iterdir() if d.is_dir()]
        )
        configured = wesad_paths.get("available_subjects", [])
        extra = [s for s in discovered if s not in configured and s not in wesad_cfg.get("absent_subjects", [])]
        if extra:
            warnings.append(
                f"Discovered WESAD subject directories not in config: {extra}. "
                f"They will be ignored. Update configs/paths.yaml if intended."
            )

    return {
        "project_root": project_root,
        "physionet": physionet_paths,
        "wesad": wesad_paths,
        "outputs": output_paths,
        "_warnings": warnings,
        "_raw_config": raw_cfg,
    }


# -----------------------------------------------------------------------
# Convenience helpers
# -----------------------------------------------------------------------

def get_physionet_set_a_records(
    paths: dict[str, Any] | None = None,
) -> list[Path]:
    """
    Return sorted list of PhysioNet Set-A record files.

    A valid record file is identified by:
      1. It is a regular file.
      2. Its first line is exactly 'Time,Parameter,Value'.

    Parameters
    ----------
    paths : dict, optional
        Resolved paths dict from resolve_dataset_paths(). Auto-loaded if None.

    Returns
    -------
    list[Path]
        Sorted list of valid record file paths.
    """
    if paths is None:
        paths = resolve_dataset_paths()

    set_a_dir: Path = paths["physionet"]["set_a"]
    records = []
    for f in sorted(set_a_dir.iterdir()):
        if not f.is_file():
            continue
        try:
            with open(f, "r", encoding="utf-8", errors="replace") as fh:
                first_line = fh.readline().strip()
            if first_line == "Time,Parameter,Value":
                records.append(f)
        except OSError:
            pass  # Will be caught by audit
    return records


def get_wesad_subject_dirs(
    paths: dict[str, Any] | None = None,
) -> dict[str, Path]:
    """
    Return dict mapping subject ID to subject directory path.

    Only returns subjects listed in configs/paths.yaml available_subjects.

    Parameters
    ----------
    paths : dict, optional
        Resolved paths dict. Auto-loaded if None.

    Returns
    -------
    dict[str, Path]
        {subject_id: subject_dir_path}
    """
    if paths is None:
        paths = resolve_dataset_paths()

    wesad_root: Path = paths["wesad"]["root"]
    available: list[str] = paths["wesad"].get("available_subjects", [])

    result = {}
    for subj in available:
        subj_dir = wesad_root / subj
        result[subj] = subj_dir  # Path may not exist — caller handles that

    return result

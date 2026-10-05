"""
scripts/environment_info.py
============================
Detect and report the execution environment for CSCM-IoMT.

Outputs:
    results/dataset_audit/environment.json
    results/dataset_audit/environment.md

Usage::

    python scripts/environment_info.py
"""

from __future__ import annotations

import json
import os
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

# -----------------------------------------------------------------------
# Ensure src/ is importable when running as a script
# -----------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.utils.config import find_project_root, resolve_dataset_paths
from src.utils.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)


# -----------------------------------------------------------------------
# Collectors
# -----------------------------------------------------------------------

def collect_system_info() -> dict:
    """Collect OS, CPU, and memory information."""
    info: dict = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "operating_system": platform.system(),
        "os_version": platform.version(),
        "os_release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "architecture": platform.architecture()[0],
        "hostname": platform.node(),
    }

    # psutil — CPU + memory
    try:
        import psutil
        info["logical_cpu_count"] = psutil.cpu_count(logical=True)
        info["physical_cpu_count"] = psutil.cpu_count(logical=False)
        mem = psutil.virtual_memory()
        info["ram_total_gb"] = round(mem.total / 1e9, 2)
        info["ram_available_gb"] = round(mem.available / 1e9, 2)
        info["ram_used_percent"] = mem.percent
    except ImportError:
        info["psutil_warning"] = "psutil not available — CPU/memory info incomplete"

    return info


def collect_python_info() -> dict:
    """Collect Python runtime information."""
    return {
        "python_version": sys.version,
        "python_version_short": platform.python_version(),
        "python_executable": sys.executable,
        "python_implementation": platform.python_implementation(),
    }


def collect_package_info() -> dict:
    """Collect installed package versions relevant to the project."""
    packages = [
        "numpy", "pandas", "scipy", "sklearn", "matplotlib",
        "seaborn", "yaml", "tqdm", "psutil", "pytest",
        "torch", "torch_geometric",
    ]
    # Import names → package names for display
    import_to_display = {
        "sklearn": "scikit-learn",
        "yaml": "PyYAML",
        "torch_geometric": "torch-geometric",
    }

    info: dict = {}
    for pkg in packages:
        display_name = import_to_display.get(pkg, pkg)
        try:
            mod = __import__(pkg)
            version = getattr(mod, "__version__", "unknown")
            info[display_name] = {"installed": True, "version": version}
        except ImportError:
            info[display_name] = {"installed": False, "version": None}
    return info


def collect_gpu_info() -> dict:
    """Collect GPU and CUDA information if PyTorch is available."""
    gpu_info: dict = {
        "torch_available": False,
        "cuda_available": False,
        "cuda_version": None,
        "gpu_count": 0,
        "gpus": [],
    }
    try:
        import torch
        gpu_info["torch_available"] = True
        gpu_info["cuda_available"] = torch.cuda.is_available()
        if torch.cuda.is_available():
            gpu_info["cuda_version"] = torch.version.cuda
            gpu_info["gpu_count"] = torch.cuda.device_count()
            for i in range(torch.cuda.device_count()):
                props = torch.cuda.get_device_properties(i)
                gpu_info["gpus"].append({
                    "index": i,
                    "name": props.name,
                    "total_memory_gb": round(props.total_memory / 1e9, 2),
                    "major": props.major,
                    "minor": props.minor,
                })
    except ImportError:
        gpu_info["note"] = "PyTorch not installed — GPU info unavailable"
    return gpu_info


def collect_disk_info(project_root: Path) -> dict:
    """Collect disk space information for the project drive."""
    try:
        import psutil
        usage = psutil.disk_usage(str(project_root))
        return {
            "path": str(project_root),
            "total_gb": round(usage.total / 1e9, 2),
            "used_gb": round(usage.used / 1e9, 2),
            "free_gb": round(usage.free / 1e9, 2),
            "used_percent": usage.percent,
        }
    except ImportError:
        return {"error": "psutil not available"}
    except Exception as exc:
        return {"error": str(exc)}


# -----------------------------------------------------------------------
# Report writers
# -----------------------------------------------------------------------

def write_environment_json(env_data: dict, output_dir: Path) -> Path:
    """Write environment JSON report."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "environment.json"
    with open(json_path, "w", encoding="utf-8") as fh:
        json.dump(env_data, fh, indent=2, default=str)
    logger.info("Written: %s", json_path)
    return json_path


def write_environment_md(env_data: dict, output_dir: Path) -> Path:
    """Write human-readable environment Markdown report."""
    output_dir.mkdir(parents=True, exist_ok=True)
    md_path = output_dir / "environment.md"

    sys_info = env_data.get("system", {})
    py_info = env_data.get("python", {})
    pkg_info = env_data.get("packages", {})
    gpu_info = env_data.get("gpu", {})
    disk_info = env_data.get("disk", {})

    lines = [
        "# CSCM-IoMT: Execution Environment",
        "",
        f"**Generated**: {env_data.get('timestamp_utc', 'N/A')}",
        "",
        "---",
        "",
        "## System",
        "",
        f"| Property | Value |",
        f"|----------|-------|",
        f"| OS | {sys_info.get('operating_system', 'N/A')} {sys_info.get('os_release', '')} |",
        f"| OS Version | {sys_info.get('os_version', 'N/A')} |",
        f"| Machine | {sys_info.get('machine', 'N/A')} |",
        f"| Processor | {sys_info.get('processor', 'N/A')} |",
        f"| Architecture | {sys_info.get('architecture', 'N/A')} |",
        f"| Logical CPUs | {sys_info.get('logical_cpu_count', 'N/A')} |",
        f"| Physical CPUs | {sys_info.get('physical_cpu_count', 'N/A')} |",
        f"| RAM Total | {sys_info.get('ram_total_gb', 'N/A')} GB |",
        f"| RAM Available | {sys_info.get('ram_available_gb', 'N/A')} GB |",
        "",
        "## Python",
        "",
        f"| Property | Value |",
        f"|----------|-------|",
        f"| Version | {py_info.get('python_version_short', 'N/A')} |",
        f"| Implementation | {py_info.get('python_implementation', 'N/A')} |",
        f"| Executable | `{py_info.get('python_executable', 'N/A')}` |",
        "",
        "## Packages",
        "",
        "| Package | Installed | Version |",
        "|---------|-----------|---------|",
    ]
    for pkg_name, pkg_data in sorted(pkg_info.items()):
        installed = "✅" if pkg_data.get("installed") else "❌"
        version = pkg_data.get("version") or "—"
        lines.append(f"| {pkg_name} | {installed} | {version} |")

    lines += [
        "",
        "## GPU / CUDA",
        "",
        f"| Property | Value |",
        f"|----------|-------|",
        f"| PyTorch Available | {'Yes' if gpu_info.get('torch_available') else 'No'} |",
        f"| CUDA Available | {'Yes' if gpu_info.get('cuda_available') else 'No'} |",
        f"| CUDA Version | {gpu_info.get('cuda_version') or '—'} |",
        f"| GPU Count | {gpu_info.get('gpu_count', 0)} |",
    ]
    for g in gpu_info.get("gpus", []):
        lines.append(f"| GPU {g['index']} | {g['name']} ({g['total_memory_gb']} GB) |")

    lines += [
        "",
        "## Disk",
        "",
        f"| Property | Value |",
        f"|----------|-------|",
        f"| Project Drive | `{disk_info.get('path', 'N/A')}` |",
        f"| Total | {disk_info.get('total_gb', 'N/A')} GB |",
        f"| Used | {disk_info.get('used_gb', 'N/A')} GB ({disk_info.get('used_percent', 'N/A')}%) |",
        f"| Free | {disk_info.get('free_gb', 'N/A')} GB |",
        "",
        "---",
        "",
        "> **Note**: PyTorch and torch-geometric are model-phase dependencies.",
        "> They are not required for Phase 1 (environment setup) or Phase 2 (dataset audit).",
    ]

    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    logger.info("Written: %s", md_path)
    return md_path


# -----------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------

def main() -> None:
    project_root = find_project_root()
    paths = resolve_dataset_paths(project_root, validate=False)
    output_dir = paths["outputs"].get("dataset_audit", project_root / "results" / "dataset_audit")

    logger.info("Collecting environment information…")

    env_data = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "project_root": str(project_root),
        "system": collect_system_info(),
        "python": collect_python_info(),
        "packages": collect_package_info(),
        "gpu": collect_gpu_info(),
        "disk": collect_disk_info(project_root),
    }

    write_environment_json(env_data, output_dir)
    write_environment_md(env_data, output_dir)

    # Print summary
    sys_info = env_data["system"]
    py_info = env_data["python"]
    gpu_info = env_data["gpu"]

    print("\n" + "=" * 50)
    print("CSCM-IoMT ENVIRONMENT SUMMARY")
    print("=" * 50)
    print(f"OS         : {sys_info.get('operating_system')} {sys_info.get('os_release')}")
    print(f"Python     : {py_info.get('python_version_short')}")
    print(f"Executable : {py_info.get('python_executable')}")
    print(f"RAM        : {sys_info.get('ram_available_gb')} GB available / {sys_info.get('ram_total_gb')} GB total")
    print(f"PyTorch    : {'installed (v' + env_data['packages'].get('torch', {}).get('version', '') + ')' if env_data['packages'].get('torch', {}).get('installed') else 'NOT installed'}")
    print(f"CUDA       : {'available' if gpu_info.get('cuda_available') else 'not available'}")
    if gpu_info.get("gpus"):
        for g in gpu_info["gpus"]:
            print(f"GPU        : {g['name']} ({g['total_memory_gb']} GB)")
    print(f"\nReports -> {output_dir}")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    main()

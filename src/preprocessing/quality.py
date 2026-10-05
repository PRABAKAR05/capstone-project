"""
src/preprocessing/quality.py
============================
Handles report generation and quality metrics tracking for Phase 3 experiments.
"""

from __future__ import annotations

import json
from pathlib import Path


def append_experiment_record(record: dict, output_path: Path) -> None:
    """
    Append an experiment record to the JSON tracker.
    
    Args:
        record: Dictionary containing experiment statistics.
        output_path: Path to preprocessing_experiments.json.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    if output_path.exists():
        with open(output_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = []
        
    data.append(record)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def generate_physionet_report(stats: dict, output_path: Path) -> None:
    """Generate the PhysioNet preprocessing quality report."""
    
    md_content = f"""# PhysioNet Preprocessing Report

## 1. Input Records
- Records Processed: {stats.get('records_processed', 0)}
- Records Failed: {stats.get('records_failed', 0)}

## 2. Selected Channels
- Primary: {", ".join(stats.get('primary_channels', []))}
- Secondary: {", ".join(stats.get('secondary_channels', []))}

## 3. Temporal Grid Candidates
- Evaluated Resolutions: {", ".join(map(str, stats.get('evaluated_grids', [])))} min

## 4. Aggregation & Missingness
- Imputation Mode: {stats.get('imputation_mode', 'Unknown')}
- Max Gap Limit: {stats.get('max_imputation_gap_min', 'N/A')} min

## 5. Window Statistics
- Windows Generated: {stats.get('windows_generated', 0)}
- Usable Windows: {stats.get('usable_windows', 0)}
- Rejected Windows: {stats.get('rejected_windows', 0)}

**Rejection Reasons:**
"""
    for reason, count in stats.get('rejection_reasons', {}).items():
        md_content += f"- {reason}: {count}\n"
        
    md_content += f"""
## 6. Splits
- Train Records: {stats.get('train_records', 0)}
- Val Records: {stats.get('val_records', 0)}
- Test Records: {stats.get('test_records', 0)}

## 7. Normalization
- Method: {stats.get('normalization_method', 'N/A')}

*Generated automatically during Phase 3.*
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(md_content, encoding="utf-8")


def generate_wesad_report(stats: dict, output_path: Path) -> None:
    """Generate the WESAD preprocessing quality report."""
    
    md_content = f"""# WESAD Preprocessing Report

## 1. Input Subjects
- Subjects Processed: {stats.get('subjects_processed', 0)}
- Subjects Failed: {stats.get('subjects_failed', 0)}

## 2. Signal Modalities
- Chest: {", ".join(stats.get('chest_modalities', []))}
- Wrist: {", ".join(stats.get('wrist_modalities', []))}

## 3. Sampling Rates
- Original: Chest (700Hz), Wrist BVP (64Hz), Wrist EDA/TEMP (4Hz)
- Target Configured: {stats.get('target_rate_hz', 'Unknown')} Hz

## 4. Window Statistics
- Window Duration: {stats.get('window_size_sec', 'N/A')} sec
- Label Purity Threshold: {stats.get('purity_threshold', 'N/A')}
- Windows Generated: {stats.get('windows_generated', 0)}
- Usable Windows: {stats.get('usable_windows', 0)}
- Rejected Windows: {stats.get('rejected_windows', 0)}

**Rejection Reasons:**
"""
    for reason, count in stats.get('rejection_reasons', {}).items():
        md_content += f"- {reason}: {count}\n"
        
    md_content += f"""
## 5. Splits
- Train Subjects: {stats.get('train_subjects', 0)}
- Val Subjects: {stats.get('val_subjects', 0)}
- Test Subjects: {stats.get('test_subjects', 0)}

## 6. Normalization
- Method: {stats.get('normalization_method', 'N/A')}

*Generated automatically during Phase 3.*
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(md_content, encoding="utf-8")


def generate_summary_report(output_path: Path) -> None:
    """Generate the combined preprocessing summary."""
    md_content = """# CSCM-IoMT Preprocessing Summary

> [!NOTE]
> **AUDIT FACT**: Phase 2 established 4,000 valid PhysioNet records and 15 valid WESAD subjects with 0 NaN/Inf raw signals.

> [!NOTE]
> **PREPROCESSING EXPERIMENT**: Phase 3 evaluated multiple combinations of grid sizes, imputation rules, sampling rates, and window sizes to document empirical trade-offs.

> [!WARNING]
> **RESEARCH DESIGN DECISION**: No single configuration is declared "optimal" automatically. The final configuration for Phase 4 (FDI attacks) must be explicitly selected after reviewing these trade-offs.

Check `physionet_preprocessing.md`, `wesad_preprocessing.md`, and `preprocessing_experiments.json` for full details.
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(md_content, encoding="utf-8")

"""
src/preprocessing/splits.py
===========================
Handles Record-level (PhysioNet) and Subject-level (WESAD) train/val/test splitting.
Splits are deterministic, saved to JSON, and strictly validated to prevent leakage.
"""

from __future__ import annotations

import json
from pathlib import Path

from sklearn.model_selection import train_test_split


def generate_physionet_splits(
    record_ids: list[int | str],
    train_ratio: float,
    val_ratio: float,
    test_ratio: float,
    seed: int,
    output_path: Path,
) -> dict[str, list[str]]:
    """
    Generate and save Record-level splits for PhysioNet.

    Args:
        record_ids: List of unique RecordIDs.
        train_ratio: Fraction of records for training.
        val_ratio: Fraction of records for validation.
        test_ratio: Fraction of records for testing.
        seed: Random seed for reproducibility.
        output_path: Path to save the JSON split file.

    Returns:
        Dict with 'train', 'val', 'test' lists of RecordIDs as strings.
    """
    # Ensure probabilities sum to 1.0 (approximate is fine due to floats)
    assert abs(train_ratio + val_ratio + test_ratio - 1.0) < 1e-5, "Ratios must sum to 1.0"
    
    # Ensure string representation for consistent JSON serialization
    record_ids = sorted([str(x) for x in record_ids])
    
    # First split: Train vs Temp (Val + Test)
    train_ids, temp_ids = train_test_split(
        record_ids, 
        train_size=train_ratio, 
        random_state=seed, 
        shuffle=True
    )
    
    # Second split: Val vs Test
    val_rel_ratio = val_ratio / (val_ratio + test_ratio)
    val_ids, test_ids = train_test_split(
        temp_ids, 
        train_size=val_rel_ratio, 
        random_state=seed, 
        shuffle=True
    )
    
    # Convert back to sorted lists
    train_ids = sorted(train_ids)
    val_ids = sorted(val_ids)
    test_ids = sorted(test_ids)
    
    # Leakage check
    _validate_no_leakage(train_ids, val_ids, test_ids)
    
    split_data = {
        "dataset": "physionet",
        "seed": seed,
        "splits": {
            "train": train_ids,
            "val": val_ids,
            "test": test_ids
        }
    }
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(split_data, f, indent=2)
        
    return split_data["splits"]


def generate_wesad_splits(
    train_subjects: list[str],
    val_subjects: list[str],
    test_subjects: list[str],
    seed: int,
    output_path: Path,
) -> dict[str, list[str]]:
    """
    Save Subject-level splits for WESAD based on declarative configuration.
    
    Args:
        train_subjects: List of subject IDs for training (e.g., ["S2", "S3"]).
        val_subjects: List of subject IDs for validation.
        test_subjects: List of subject IDs for testing.
        seed: Random seed tracking.
        output_path: Path to save the JSON split file.
        
    Returns:
        Dict with 'train', 'val', 'test' lists of SubjectIDs.
    """
    train_ids = sorted([str(x) for x in train_subjects])
    val_ids = sorted([str(x) for x in val_subjects])
    test_ids = sorted([str(x) for x in test_subjects])
    
    # Leakage check
    _validate_no_leakage(train_ids, val_ids, test_ids)
    
    split_data = {
        "dataset": "wesad",
        "seed": seed,
        "splits": {
            "train": train_ids,
            "val": val_ids,
            "test": test_ids
        }
    }
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(split_data, f, indent=2)
        
    return split_data["splits"]


def _validate_no_leakage(train_ids: list[str], val_ids: list[str], test_ids: list[str]) -> None:
    """
    Strict validation to ensure there is no crossover between splits.
    Raises ValueError if any leakage is detected.
    """
    train_set = set(train_ids)
    val_set = set(val_ids)
    test_set = set(test_ids)
    
    if not train_set.isdisjoint(val_set):
        overlap = train_set.intersection(val_set)
        raise ValueError(f"LEAKAGE DETECTED: Train and Val splits overlap: {overlap}")
        
    if not train_set.isdisjoint(test_set):
        overlap = train_set.intersection(test_set)
        raise ValueError(f"LEAKAGE DETECTED: Train and Test splits overlap: {overlap}")
        
    if not val_set.isdisjoint(test_set):
        overlap = val_set.intersection(test_set)
        raise ValueError(f"LEAKAGE DETECTED: Val and Test splits overlap: {overlap}")


def load_splits(filepath: Path) -> dict[str, list[str]]:
    """
    Load a generated split JSON file.
    
    Args:
        filepath: Path to the JSON split file.
        
    Returns:
        Dict containing 'train', 'val', 'test' ID lists.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["splits"]

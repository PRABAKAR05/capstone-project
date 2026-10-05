"""
src/preprocessing/windowing.py
==============================
Handles sliding window generation, label purity validation, and channel coverage checks.
"""

from __future__ import annotations

import numpy as np


def generate_window_indices(
    total_length: int, 
    window_size: int, 
    overlap_fraction: float
) -> list[tuple[int, int]]:
    """
    Generate start and end indices for sliding windows.
    
    Args:
        total_length: Total number of samples/bins in the sequence.
        window_size: Number of samples/bins per window.
        overlap_fraction: Fraction of overlap (e.g., 0.5 for 50%).
        
    Returns:
        List of (start_idx, end_idx) tuples.
    """
    if window_size <= 0 or total_length < window_size:
        return []
        
    step_size = max(1, int(window_size * (1.0 - overlap_fraction)))
    
    indices = []
    for start in range(0, total_length - window_size + 1, step_size):
        indices.append((start, start + window_size))
        
    return indices


def check_label_purity(
    labels: np.ndarray, 
    purity_threshold: float,
    ignore_labels: list[int] | None = None
) -> dict:
    """
    Check if a window meets the required label purity.
    
    Args:
        labels: 1D numpy array of integer labels for the window.
        purity_threshold: Float between 0.0 and 1.0 (e.g., 0.8 for 80%).
        ignore_labels: List of labels to completely ignore when calculating purity 
                       (e.g., [5, 6, 7]). If all valid labels are ignored, purity fails.
                       
    Returns:
        Dict containing:
            'is_pure': bool
            'dominant_label': int or None
            'dominant_percentage': float
            'label_counts': dict
    """
    if len(labels) == 0:
        return {"is_pure": False, "dominant_label": None, "dominant_percentage": 0.0, "label_counts": {}}
        
    # Count occurrences
    unique, counts = np.unique(labels, return_counts=True)
    counts_dict = dict(zip(unique, counts))
    
    # Filter ignored labels
    if ignore_labels:
        valid_counts = {k: v for k, v in counts_dict.items() if k not in ignore_labels}
    else:
        valid_counts = counts_dict.copy()
        
    total_valid = sum(valid_counts.values())
    if total_valid == 0:
        return {"is_pure": False, "dominant_label": None, "dominant_percentage": 0.0, "label_counts": counts_dict}
        
    # Find dominant
    dominant_label = max(valid_counts.items(), key=lambda x: x[1])[0]
    dominant_count = valid_counts[dominant_label]
    dominant_percentage = dominant_count / total_valid
    
    is_pure = bool(dominant_percentage >= purity_threshold)
    
    return {
        "is_pure": is_pure,
        "dominant_label": int(dominant_label),
        "dominant_percentage": float(dominant_percentage),
        "label_counts": counts_dict
    }


def check_window_usability(
    mask: np.ndarray, 
    coverage_threshold: float,
    min_temporal_points: int
) -> dict:
    """
    Check if a window has sufficient channel coverage and temporal points.
    
    Args:
        mask: 2D boolean numpy array (time_steps, channels). True=Observed.
        coverage_threshold: Minimum fraction of non-missing values required overall.
        min_temporal_points: Minimum number of required temporal steps (already validated by grid, 
                             but good for secondary check).
                             
    Returns:
        Dict with 'usable': bool and 'reason': str (if rejected) or None.
    """
    if mask.shape[0] < min_temporal_points:
        return {"usable": False, "reason": "INSUFFICIENT_TEMPORAL_POINTS"}
        
    total_elements = mask.size
    if total_elements == 0:
        return {"usable": False, "reason": "EMPTY_WINDOW"}
        
    valid_elements = np.sum(mask)
    coverage = valid_elements / total_elements
    
    if coverage < coverage_threshold:
        return {"usable": False, "reason": "INSUFFICIENT_CHANNEL_COVERAGE"}
        
    return {"usable": True, "reason": None}

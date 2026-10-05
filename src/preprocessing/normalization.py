"""
src/preprocessing/normalization.py
==================================
Handles calculation and application of normalization statistics.
Ensures statistics are fitted ONLY on training data.
"""

from __future__ import annotations

import numpy as np


def fit_normalization(data_list: list[np.ndarray], method: str = "zscore") -> dict[str, float]:
    """
    Calculate normalization statistics over a list of arrays (e.g., all training windows for a channel).
    Ignores NaN values.
    
    Args:
        data_list: List of 1D or 2D numpy arrays representing training data for a single channel.
        method: "zscore" (mean/std) or "robust" (median/IQR).
        
    Returns:
        Dict containing the fitted statistics.
    """
    # Concatenate all valid observations across the list of arrays
    valid_data = []
    for arr in data_list:
        mask = ~np.isnan(arr)
        valid_data.append(arr[mask])
        
    if not valid_data:
        # Fallback if entirely NaN
        return {"mean": 0.0, "std": 1.0, "median": 0.0, "iqr": 1.0, "method": method}
        
    all_valid = np.concatenate(valid_data)
    if len(all_valid) == 0:
        return {"mean": 0.0, "std": 1.0, "median": 0.0, "iqr": 1.0, "method": method}
        
    stats = {"method": method}
    
    if method == "zscore":
        stats["mean"] = float(np.mean(all_valid))
        stats["std"] = float(np.std(all_valid))
        if stats["std"] < 1e-8:
            stats["std"] = 1.0
            
    elif method == "robust":
        stats["median"] = float(np.median(all_valid))
        q75, q25 = np.percentile(all_valid, [75, 25])
        iqr = float(q75 - q25)
        stats["iqr"] = iqr if iqr > 1e-8 else 1.0
        
    else:
        raise ValueError(f"Unknown normalization method: {method}")
        
    return stats


def apply_normalization(data: np.ndarray, stats: dict[str, float]) -> np.ndarray:
    """
    Apply fitted normalization statistics to an array.
    NaNs and missingness masks are completely unaffected.
    
    Args:
        data: 1D or 2D numpy array.
        stats: Dict containing fitted statistics from `fit_normalization`.
        
    Returns:
        Normalized numpy array.
    """
    normalized = data.copy()
    mask = ~np.isnan(normalized)
    
    method = stats.get("method", "zscore")
    
    if method == "zscore":
        mean = stats["mean"]
        std = stats["std"]
        normalized[mask] = (normalized[mask] - mean) / std
        
    elif method == "robust":
        median = stats["median"]
        iqr = stats["iqr"]
        normalized[mask] = (normalized[mask] - median) / iqr
        
    else:
        raise ValueError(f"Unknown normalization method: {method}")
        
    return normalized

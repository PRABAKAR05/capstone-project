"""
src/preprocessing/resampling.py
===============================
Functions for resampling and aggregation.
- PhysioNet: Median aggregation within bins.
- WESAD: SciPy-based anti-alias filtering and downsampling.
"""

from __future__ import annotations

import numpy as np
import scipy.signal as signal


def aggregate_bin(values: np.ndarray, method: str = "median") -> float:
    """
    Aggregate a set of values within a temporal bin.
    
    Args:
        values: 1D array of values.
        method: Aggregation method ("median" or "mean").
        
    Returns:
        The aggregated value, or np.nan if values is empty.
    """
    if len(values) == 0:
        return np.nan
        
    if method == "median":
        return float(np.median(values))
    elif method == "mean":
        return float(np.mean(values))
    else:
        raise ValueError(f"Unknown aggregation method: {method}")


def downsample_signal(
    data: np.ndarray, 
    orig_rate: int, 
    target_rate: int, 
    apply_anti_alias: bool = True
) -> np.ndarray:
    """
    Downsample a high-frequency signal (e.g., 700 Hz) to a lower target rate (e.g., 32 Hz).
    
    Uses `scipy.signal.resample_poly` which automatically applies a polyphase 
    anti-alias FIR filter before downsampling.
    
    Args:
        data: 1D or 2D numpy array of signal data.
        orig_rate: The original sampling rate in Hz.
        target_rate: The target sampling rate in Hz.
        apply_anti_alias: If True, uses polyphase filtering. If False, just decimates.
        
    Returns:
        Downsampled numpy array.
    """
    if orig_rate == target_rate:
        return data.copy()
        
    if orig_rate < target_rate:
        raise ValueError(
            f"downsample_signal is for downsampling only. "
            f"orig_rate={orig_rate} < target_rate={target_rate}. "
            "Upsampling requires interpolation/masking, not polyphase resampling."
        )

    if apply_anti_alias:
        # resample_poly automatically designs and applies a zero-phase FIR anti-aliasing filter
        # It is generally faster and more robust than decimate for non-integer factors
        resampled = signal.resample_poly(data, up=target_rate, down=orig_rate, axis=0)
    else:
        # Simple decimation (taking every Nth sample). Not recommended for high-freq signals.
        factor = int(orig_rate / target_rate)
        if orig_rate % target_rate != 0:
            raise ValueError("Exact integer decimation factor required without anti-aliasing.")
        resampled = data[::factor]
        
    return resampled

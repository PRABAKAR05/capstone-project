"""
src/preprocessing/missingness.py
================================
Handles Missingness Masking and Imputation (Causal and Offline).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def create_missingness_mask(data: np.ndarray) -> np.ndarray:
    """
    Create a boolean validity mask for the given data array.
    True = Valid measurement, False = NaN / Missing.
    
    Args:
        data: 1D or 2D numpy array.
        
    Returns:
        Boolean numpy array of the same shape.
    """
    return ~np.isnan(data)


def impute_missing_values(
    data: np.ndarray, 
    mode: str, 
    max_gap_steps: int = 0
) -> np.ndarray:
    """
    Impute missing values (NaN) in a 1D or 2D sequence.
    
    Args:
        data: 1D or 2D numpy array of shape (time_steps, channels).
        mode: "causal" (forward fill only) or "offline" (linear interpolation allowed).
        max_gap_steps: Maximum number of consecutive missing steps to fill.
                       If the gap is larger, it remains NaN.
                       
    Returns:
        Imputed numpy array (original array is not modified in-place).
    """
    if len(data) == 0:
        return data.copy()
        
    # Pandas provides robust limit-based ffill and interpolate
    df = pd.DataFrame(data)
    
    if mode == "causal":
        # Causal: Use only past observations. Forward fill.
        imputed_df = df.ffill(limit=max_gap_steps if max_gap_steps > 0 else None)
    elif mode == "offline":
        # Offline: Can use future observations. Linear interpolation.
        imputed_df = df.interpolate(
            method="linear", 
            limit=max_gap_steps if max_gap_steps > 0 else None,
            limit_direction="both"
        )
    else:
        raise ValueError(f"Unknown imputation mode: {mode}")
        
    return imputed_df.to_numpy()

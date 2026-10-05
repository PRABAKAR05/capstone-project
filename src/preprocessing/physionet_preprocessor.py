"""
src/preprocessing/physionet_preprocessor.py
===========================================
Handles processing a single PhysioNet record into a temporal grid, 
imputing missing values, and slicing into usable temporal windows.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .temporal_grid import generate_grid_edges, assign_to_bins
from .resampling import aggregate_bin
from .missingness import impute_missing_values, create_missingness_mask
from .windowing import generate_window_indices, check_window_usability


def parse_time_to_minutes(time_str: str) -> float:
    """Convert HH:MM string to elapsed minutes."""
    try:
        h, m = time_str.split(":")
        return int(h) * 60.0 + int(m)
    except Exception:
        return np.nan


def process_record_to_grid(
    df: pd.DataFrame,
    channels: list[str],
    grid_res_min: float,
    imputation_mode: str,
    max_gap_min: float
) -> tuple[np.ndarray, np.ndarray]:
    """
    Map raw irregular PhysioNet observations to a regular temporal grid.
    
    Args:
        df: DataFrame containing 'Time', 'Parameter', 'Value'.
        channels: List of physiological channels to extract.
        grid_res_min: Grid resolution in minutes.
        imputation_mode: "causal" (forward fill) or "offline" (interpolate).
        max_gap_min: Maximum gap duration in minutes for imputation.
        
    Returns:
        Tuple of (values, mask), both shape (num_bins, num_channels).
    """
    # 1. Parse elapsed minutes
    df = df.copy()
    if 'Time' in df.columns and df['Time'].dtype == object:
        df['elapsed_min'] = df['Time'].apply(parse_time_to_minutes)
    elif 'elapsed_min' not in df.columns:
        raise ValueError("DataFrame must contain 'Time' or 'elapsed_min'")
        
    df = df.dropna(subset=['elapsed_min', 'Value'])
    
    # 2. Convert -1 sentinels to NaN
    df['Value'] = df['Value'].replace(-1.0, np.nan)
    
    if len(df) == 0:
        return np.array([]), np.array([])
        
    start_min = 0.0
    end_min = df['elapsed_min'].max()
    
    # Generate bin edges and number of bins
    edges = generate_grid_edges(start_min, end_min, grid_res_min)
    num_bins = len(edges) - 1
    if num_bins <= 0:
        return np.array([]), np.array([])
        
    df['bin_idx'] = assign_to_bins(df['elapsed_min'].values, grid_res_min, start_min)
    df = df[(df['bin_idx'] >= 0) & (df['bin_idx'] < num_bins)]
    
    # 3. Aggregate into grid
    grid_values = np.full((num_bins, len(channels)), np.nan)
    
    for c_idx, channel in enumerate(channels):
        chan_df = df[df['Parameter'] == channel]
        
        # Group by bin_idx and aggregate via median
        grouped = chan_df.groupby('bin_idx')['Value'].median()
        for b_idx, val in grouped.items():
            grid_values[b_idx, c_idx] = val
            
    # 4. Create explicit missingness mask BEFORE imputation
    mask = create_missingness_mask(grid_values)
    
    # 5. Impute
    max_gap_steps = int(max_gap_min / grid_res_min)
    grid_values = impute_missing_values(grid_values, mode=imputation_mode, max_gap_steps=max_gap_steps)
    
    # Note: We return the original mask (indicating true observations), not the imputed mask.
    return grid_values, mask


def generate_physionet_windows(
    grid_values: np.ndarray,
    grid_mask: np.ndarray,
    window_duration_min: float,
    grid_res_min: float,
    overlap_fraction: float,
    min_temporal_points: int,
    coverage_threshold: float
) -> tuple[list[np.ndarray], list[np.ndarray], dict]:
    """
    Slice the grid into sliding windows and evaluate usability.
    
    Returns:
        List of usable value windows, list of usable mask windows, and rejection stats.
    """
    total_bins = len(grid_values)
    window_size_bins = int(window_duration_min / grid_res_min)
    
    indices = generate_window_indices(total_bins, window_size_bins, overlap_fraction)
    
    valid_values = []
    valid_masks = []
    
    stats = {
        "generated": len(indices),
        "usable": 0,
        "rejected": 0,
        "reasons": {}
    }
    
    for start, end in indices:
        w_values = grid_values[start:end]
        w_mask = grid_mask[start:end]
        
        usability = check_window_usability(w_mask, coverage_threshold, min_temporal_points)
        
        if usability["usable"]:
            valid_values.append(w_values)
            valid_masks.append(w_mask)
            stats["usable"] += 1
        else:
            stats["rejected"] += 1
            reason = usability["reason"]
            stats["reasons"][reason] = stats["reasons"].get(reason, 0) + 1
            
    return valid_values, valid_masks, stats

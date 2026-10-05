"""
src/preprocessing/temporal_grid.py
==================================
Handles generation of temporal grids and mapping of irregular timestamps to grid bins.
"""

from __future__ import annotations

import numpy as np


def generate_grid_edges(start_min: float, end_min: float, resolution_min: float) -> np.ndarray:
    """
    Generate the bin edges for a temporal grid.
    
    Args:
        start_min: The start time in minutes.
        end_min: The end time in minutes.
        resolution_min: The grid resolution (bin width) in minutes.
        
    Returns:
        A 1D numpy array of bin edges. Length is num_bins + 1.
    """
    # Use np.arange to generate edges. Add a small epsilon to end_min 
    # to ensure the last edge covers the end time.
    return np.arange(start_min, end_min + resolution_min + 1e-9, resolution_min)


def assign_to_bins(times: np.ndarray, resolution_min: float, start_min: float = 0.0) -> np.ndarray:
    """
    Map an array of irregular timestamps to integer bin indices based on the grid resolution.
    
    Args:
        times: 1D numpy array of timestamps (in minutes).
        resolution_min: The grid resolution in minutes.
        start_min: The start time (offset) in minutes. Default is 0.0.
        
    Returns:
        1D numpy array of integer bin indices.
    """
    times = np.asarray(times)
    # The index is simply the floor of the time offset divided by resolution
    bin_indices = np.floor((times - start_min) / resolution_min).astype(int)
    
    # Ensure no negative indices if times < start_min (clip to 0 or let caller handle)
    # Usually times should be >= start_min
    bin_indices = np.maximum(0, bin_indices)
    
    return bin_indices


def validate_grid_window_compatibility(
    grid_resolution_min: float, 
    window_duration_min: float, 
    min_temporal_points: int = 4
) -> bool:
    """
    Validate if a window size and grid resolution are compatible for temporal modeling.
    
    Args:
        grid_resolution_min: Grid bin width in minutes.
        window_duration_min: Total duration of the window in minutes.
        min_temporal_points: The minimum number of temporal points required in the window.
        
    Returns:
        True if the combination will yield enough temporal points, False otherwise.
    """
    expected_points = int(window_duration_min / grid_resolution_min)
    return expected_points >= min_temporal_points

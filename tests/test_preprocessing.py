"""
tests/test_preprocessing.py
===========================
Unit tests for preprocessing logic (grid, imputation, splits, windows).
"""

import numpy as np
import pytest

from src.preprocessing.missingness import impute_missing_values, create_missingness_mask
from src.preprocessing.temporal_grid import validate_grid_window_compatibility, generate_grid_edges
from src.preprocessing.windowing import check_label_purity, generate_window_indices
from src.preprocessing.splits import _validate_no_leakage


def test_imputation_causal():
    # Setup data with gaps
    data = np.array([
        [1.0, 10.0],
        [np.nan, np.nan],
        [np.nan, 30.0],
        [4.0, np.nan]
    ])
    
    # Forward fill (causal)
    imputed = impute_missing_values(data, mode="causal", max_gap_steps=2)
    
    # Column 0: 1 -> 1 -> 1 -> 4
    np.testing.assert_array_equal(imputed[:, 0], [1.0, 1.0, 1.0, 4.0])
    
    # Column 1: 10 -> 10 -> 30 -> 30
    np.testing.assert_array_equal(imputed[:, 1], [10.0, 10.0, 30.0, 30.0])


def test_imputation_causal_max_gap():
    data = np.array([
        [1.0],
        [np.nan],
        [np.nan],
        [np.nan],
        [4.0]
    ])
    
    # Limit to 2 steps. The third nan should remain nan
    imputed = impute_missing_values(data, mode="causal", max_gap_steps=2)
    
    assert imputed[0, 0] == 1.0
    assert imputed[1, 0] == 1.0
    assert imputed[2, 0] == 1.0
    assert np.isnan(imputed[3, 0])
    assert imputed[4, 0] == 4.0


def test_imputation_offline():
    data = np.array([
        [0.0],
        [np.nan],
        [20.0]
    ])
    
    # Linear interp
    imputed = impute_missing_values(data, mode="offline")
    
    assert imputed[0, 0] == 0.0
    assert imputed[1, 0] == 10.0  # Interpolated (future info used!)
    assert imputed[2, 0] == 20.0


def test_grid_compatibility():
    # 60m grid, 2h window (120m) -> 2 points
    assert not validate_grid_window_compatibility(60, 120, min_temporal_points=4)
    # 60m grid, 4h window (240m) -> 4 points
    assert validate_grid_window_compatibility(60, 240, min_temporal_points=4)
    # 30m grid, 2h window (120m) -> 4 points
    assert validate_grid_window_compatibility(30, 120, min_temporal_points=4)


def test_label_purity():
    labels = np.array([1, 1, 1, 1, 2])
    
    # 80% class 1
    res = check_label_purity(labels, purity_threshold=0.8, ignore_labels=[0, 5, 6, 7])
    assert res["is_pure"] is True
    assert res["dominant_label"] == 1
    
    # 90% threshold -> fails
    res_fail = check_label_purity(labels, purity_threshold=0.9, ignore_labels=[0, 5, 6, 7])
    assert res_fail["is_pure"] is False


def test_label_purity_with_ignore():
    labels = np.array([2, 2, 0, 0, 0]) # 0 is ignored transient
    
    # Valid labels are only the 2s. 2 out of 2 valid = 100% purity!
    res = check_label_purity(labels, purity_threshold=1.0, ignore_labels=[0, 5, 6, 7])
    assert res["is_pure"] is True
    assert res["dominant_label"] == 2


def test_leakage_validation():
    # Should pass
    _validate_no_leakage(["A", "B"], ["C"], ["D"])
    
    # Should fail due to overlap
    with pytest.raises(ValueError):
        _validate_no_leakage(["A", "B"], ["B"], ["D"])
        
    with pytest.raises(ValueError):
        _validate_no_leakage(["A", "B"], ["C"], ["A", "D"])


def test_windowing_indices():
    indices = generate_window_indices(10, 4, 0.5)
    # len=10, win=4, step=2
    # 0-4, 2-6, 4-8, 6-10
    assert indices == [(0, 4), (2, 6), (4, 8), (6, 10)]


def test_normalization_train_isolation():
    from src.preprocessing.normalization import fit_normalization
    
    # Train data: mean = 5.0, std = 2.0
    # Values: [3.0, 7.0]
    train_data = [np.array([3.0, 7.0])]
    
    # Val data: mean = 100.0, std = 0.0
    val_data = [np.array([100.0, 100.0])]
    
    # Test A: Fit on train only
    stats_train_only = fit_normalization(train_data, method="zscore")
    assert stats_train_only["mean"] == 5.0
    assert stats_train_only["std"] == 2.0
    
    # Test B: Fit on train + val (should NOT equal stats_train_only)
    stats_contaminated = fit_normalization(train_data + val_data, method="zscore")
    assert stats_contaminated["mean"] != 5.0
    assert stats_contaminated["mean"] == 52.5  # (3+7+100+100)/4
    
    # This proves the function `fit_normalization` mathematically depends ONLY 
    # on the array list passed to it. In our production path (compute_normalization.py), 
    # we explicitly only pass the `train` HDF5 group data.


def test_wesad_resample_poly_factors():
    from src.preprocessing.resampling import downsample_signal
    
    # 1. Verify exact lengths and rational factors
    # 700 Hz -> 4 Hz (ratio 175)
    data_700 = np.ones((700 * 2,))  # 2 seconds
    resampled_4_from_700 = downsample_signal(data_700, 700, 4, apply_anti_alias=True)
    assert len(resampled_4_from_700) == 8  # 4 Hz * 2 seconds
    
    # 64 Hz -> 4 Hz (ratio 16)
    data_64 = np.ones((64 * 3,)) # 3 seconds
    resampled_4_from_64 = downsample_signal(data_64, 64, 4, apply_anti_alias=True)
    assert len(resampled_4_from_64) == 12
    
    # 2. Verify anti-aliasing behavior
    # Create a 64Hz signal containing a 1Hz (survives) and 10Hz (attenuated) sine wave
    fs = 64
    t = np.arange(0, 10, 1/fs)
    f_low = 1.0  # Below 2Hz Nyquist
    f_high = 10.0 # Above 2Hz Nyquist
    
    signal_low = np.sin(2 * np.pi * f_low * t)
    signal_high = np.sin(2 * np.pi * f_high * t)
    combined = signal_low + signal_high
    
    resampled = downsample_signal(combined, 64, 4, apply_anti_alias=True)
    
    # The output length should be 4 Hz * 10 seconds = 40
    assert len(resampled) == 40
    
    # At 4 Hz target rate, Nyquist is 2 Hz. 
    # The 1 Hz component should be preserved. The 10 Hz component should be attenuated.
    # Let's verify the power of the 10 Hz component is heavily suppressed compared to the original
    # We can do a quick check: the variance of the combined signal is var(sin(1)) + var(sin(10)) ~= 0.5 + 0.5 = 1.0
    # The resampled signal should mostly just be the 1Hz signal, so its variance should be ~0.5
    assert np.var(combined) > 0.9
    assert np.var(resampled) < 0.6  # Suppressed the high frequency!


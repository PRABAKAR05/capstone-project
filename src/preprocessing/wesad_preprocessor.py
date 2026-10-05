"""
src/preprocessing/wesad_preprocessor.py
=======================================
Handles WESAD resampling, tensor alignment, and window generation.
Applies anti-alias filtering to high-frequency signals and strict nearest-neighbor
or masking for low-frequency signals and discrete labels.
"""

from __future__ import annotations

import numpy as np

from .resampling import downsample_signal
from .windowing import generate_window_indices, check_label_purity


def resample_labels(labels: np.ndarray, orig_rate: float, target_rate: float) -> np.ndarray:
    """
    Resample discrete labels using nearest neighbor to preserve class integers.
    """
    total_time = len(labels) / orig_rate
    target_len = int(total_time * target_rate)
    
    # Calculate indices in original array
    indices = np.round(np.linspace(0, len(labels) - 1, target_len)).astype(int)
    return labels[indices]


def align_low_freq_signal(
    data: np.ndarray, 
    orig_rate: float, 
    target_rate: float
) -> tuple[np.ndarray, np.ndarray]:
    """
    Align a low-frequency signal (e.g., 4 Hz) to a higher target rate (e.g., 32 Hz).
    Uses nearest-neighbor (step) interpolation to align the tensor without inventing
    frequency components, and returns a mask indicating which samples were actual 
    observations (True) vs interpolated copies (False).
    """
    if orig_rate >= target_rate:
        raise ValueError("This function is for upsampling low-freq signals only.")
        
    total_time = len(data) / orig_rate
    target_len = int(total_time * target_rate)
    
    # Nearest neighbor interpolation
    indices = np.round(np.linspace(0, len(data) - 1, target_len)).astype(int)
    aligned_data = data[indices]
    
    # Create mask: Only the exact original timestamps get True
    # We find the nearest target index for each original index
    mask = np.zeros_like(aligned_data, dtype=bool)
    true_indices = np.round(np.arange(len(data)) * (target_rate / orig_rate)).astype(int)
    # Filter out bounds
    true_indices = true_indices[true_indices < target_len]
    mask[true_indices] = True
    
    return aligned_data, mask


def process_wesad_subject(
    subject_data: dict,
    target_rate_hz: int,
    chest_mods: list[str],
    wrist_mods: list[str]
) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
    """
    Extract, resample, and align WESAD modalities into a unified tensor.
    
    Args:
        subject_data: The loaded SX.pkl data dict.
        target_rate_hz: Target sampling rate (e.g., 4, 8, 16, 32).
        chest_mods: List of chest modalities (originally 700 Hz).
        wrist_mods: List of wrist modalities (orig: BVP 64Hz, ACC 32Hz, EDA/TEMP 4Hz).
        
    Returns:
        values: shape (time, channels)
        masks: shape (time, channels)
        labels: shape (time,)
        channel_names: Ordered list of channel names in the tensor.
    """
    chest_rate = 700.0
    
    processed_channels = []
    masks_channels = []
    channel_names = []
    
    # 1. Process Chest (700 Hz)
    if 'signal' in subject_data and 'chest' in subject_data['signal']:
        for mod in chest_mods:
            if mod in subject_data['signal']['chest']:
                data = subject_data['signal']['chest'][mod]
                if data.ndim == 1:
                    data = data.reshape(-1, 1)
                
                # Downsample
                downsampled = downsample_signal(data, int(chest_rate), target_rate_hz, apply_anti_alias=True)
                
                for col in range(downsampled.shape[1]):
                    processed_channels.append(downsampled[:, col])
                    masks_channels.append(np.ones_like(downsampled[:, col], dtype=bool))
                    channel_names.append(f"chest_{mod}_{col}" if downsampled.shape[1] > 1 else f"chest_{mod}")

    # 2. Process Wrist
    if 'signal' in subject_data and 'wrist' in subject_data['signal']:
        rates = {'ACC': 32.0, 'BVP': 64.0, 'EDA': 4.0, 'TEMP': 4.0}
        for mod in wrist_mods:
            if mod in subject_data['signal']['wrist']:
                data = subject_data['signal']['wrist'][mod]
                orig_rate = rates.get(mod, 32.0)
                
                if data.ndim == 1:
                    data = data.reshape(-1, 1)
                
                if orig_rate > target_rate_hz:
                    # Downsample with anti-alias
                    aligned = downsample_signal(data, int(orig_rate), target_rate_hz, apply_anti_alias=True)
                    mask = np.ones_like(aligned, dtype=bool)
                elif orig_rate < target_rate_hz:
                    # Upsample low-freq without inventing data
                    aligned, mask = align_low_freq_signal(data, orig_rate, target_rate_hz)
                else:
                    # Same rate
                    aligned = data.copy()
                    mask = np.ones_like(aligned, dtype=bool)
                    
                for col in range(aligned.shape[1]):
                    processed_channels.append(aligned[:, col])
                    masks_channels.append(mask[:, col] if mask.ndim > 1 else mask)
                    channel_names.append(f"wrist_{mod}_{col}" if aligned.shape[1] > 1 else f"wrist_{mod}")

    # Ensure all channels have the same length (truncate to shortest due to rounding)
    min_len = min(len(c) for c in processed_channels)
    processed_channels = [c[:min_len] for c in processed_channels]
    masks_channels = [c[:min_len] for c in masks_channels]

    values = np.column_stack(processed_channels)
    masks = np.column_stack(masks_channels)
    
    # 3. Process Labels
    labels_700 = subject_data['label']
    resampled_labels = resample_labels(labels_700, chest_rate, target_rate_hz)[:min_len]
    
    return values, masks, resampled_labels, channel_names


def generate_wesad_windows(
    values: np.ndarray,
    masks: np.ndarray,
    labels: np.ndarray,
    window_duration_sec: float,
    target_rate_hz: int,
    overlap_fraction: float,
    purity_threshold: float,
    valid_labels: list[int],
    transient_label: int,
    ignore_labels: list[int]
) -> tuple[list[np.ndarray], list[np.ndarray], list[int], dict]:
    """
    Generate overlapping windows and filter by label purity.
    """
    total_len = len(values)
    window_size = int(window_duration_sec * target_rate_hz)
    
    indices = generate_window_indices(total_len, window_size, overlap_fraction)
    
    valid_v = []
    valid_m = []
    valid_l = []
    
    stats = {
        "generated": len(indices),
        "usable": 0,
        "rejected": 0,
        "reasons": {}
    }
    
    for start, end in indices:
        w_vals = values[start:end]
        w_masks = masks[start:end]
        w_labels = labels[start:end]
        
        # Purity check
        purity_info = check_label_purity(w_labels, purity_threshold, ignore_labels)
        
        if not purity_info["is_pure"]:
            stats["rejected"] += 1
            stats["reasons"]["MIXED_LABEL_WINDOW"] = stats["reasons"].get("MIXED_LABEL_WINDOW", 0) + 1
            continue
            
        dominant_label = purity_info["dominant_label"]
        
        # Check if the dominant label is transient or ignored
        if dominant_label == transient_label:
            stats["rejected"] += 1
            stats["reasons"]["TRANSIENT_EXCLUDED"] = stats["reasons"].get("TRANSIENT_EXCLUDED", 0) + 1
            continue
            
        if dominant_label not in valid_labels:
            stats["rejected"] += 1
            stats["reasons"]["INVALID_LABEL"] = stats["reasons"].get("INVALID_LABEL", 0) + 1
            continue
            
        valid_v.append(w_vals)
        valid_m.append(w_masks)
        valid_l.append(dominant_label)
        stats["usable"] += 1
        
    return valid_v, valid_m, valid_l, stats

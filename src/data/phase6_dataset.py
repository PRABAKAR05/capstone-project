import json
import logging
from typing import Dict, List, Tuple

import h5py
import numpy as np
import torch
from torch.utils.data import Dataset

logger = logging.getLogger(__name__)

class Phase6FDIDataset(Dataset):
    """
    Dataset for training Multi-Channel Models (Model B & Model C).
    Loads all channels concurrently into a single tensor per window.
    
    Inputs:
      - raw values (clean or attacked) for ALL channels.
      - apply Phase 3 training statistics (z-score) per channel.
      - NaN remains NaN -> replaced with 0.0 -> missingness mask = 1
      - observed values -> missingness mask = 0
    
    Outputs:
      - x: (C, 2, T) tensor. Dim 1: Channel 0 = normalized signal, Channel 1 = missingness indicator.
      - y: float tensor (0.0 or 1.0). 1.0 if ANY channel in this window is attacked.
      - idx: index to recover metadata.
    """
    def __init__(
        self,
        h5_path: str,
        meta_path: str,
        split: str,
        all_channels: List[str],
        norm_stats: Dict,
    ):
        self.split = split
        self.all_channels = all_channels
        
        # Load metadata and filter plausible windows
        with open(meta_path, "r") as f:
            full_meta = json.load(f)
            
        if split not in full_meta:
            raise ValueError(f"Split {split} not found in metadata.")
            
        split_meta = full_meta[split]
        
        # Filtering policy: Explicitly auditable filtering
        self.metadata = []
        valid_indices = []
        rejected_reasons = {}
        
        for i, m in enumerate(split_meta):
            if m.get("is_plausible", False):
                self.metadata.append(m)
                valid_indices.append(i)
            else:
                r = m.get("rejection_reason", "unknown")
                cat = "bound_violation" if "bound_violation" in r else ("nan_inherited" if "nan_inherited" in r else "other")
                rejected_reasons[cat] = rejected_reasons.get(cat, 0) + 1
                
        total_orig = len(split_meta)
        total_kept = len(valid_indices)
        logger.info(f"Dataset {split} (Phase 6 All Channels): Kept {total_kept}/{total_orig} windows. Rejections: {rejected_reasons}")
        
        # Load HDF5 data into memory
        with h5py.File(h5_path, "r") as f:
            grp = f[split]
            data = grp["attacked_data"][:]
            # attack_mask is True where synthetic perturbations were injected
            attack_mask = grp["attack_mask"][:]
            
        # Subset to valid windows
        data = data[valid_indices]
        attack_mask = attack_mask[valid_indices]
        
        # Primary Phase 6 label: window-level FDI detection
        # window_attack = 1 if ANY channel is attacked in the window
        # The attack_mask has shape (N, T, C). We collapse T and C.
        self.labels = np.any(attack_mask, axis=(1, 2)).astype(np.float32)
        
        # Build normalized (C, 2, T) tensors
        N, T, C = data.shape
        x_processed = np.zeros((N, C, 2, T), dtype=np.float32)
        
        for c_idx, ch_name in enumerate(all_channels):
            ch_data = data[:, :, c_idx]
            
            # Normalization
            ch_stats = norm_stats.get("statistics", {}).get(ch_name, {}).get("zscore", {})
            mean = ch_stats.get("mean", 0.0)
            std = ch_stats.get("std", 1.0)
            
            # Apply normalization: (x - mean) / std. NaNs remain NaNs.
            norm_data = (ch_data - mean) / std
            
            # Missingness mask (this is the observation mask, not the attack mask)
            missing_mask = np.isnan(norm_data).astype(np.float32)
            
            # Replace NaN with 0.0
            norm_data = np.nan_to_num(norm_data, nan=0.0)
            
            x_processed[:, c_idx, 0, :] = norm_data
            x_processed[:, c_idx, 1, :] = missing_mask
            
        self.x = x_processed
        
    def __len__(self):
        return len(self.labels)
        
    def __getitem__(self, idx) -> Tuple[torch.Tensor, torch.Tensor, int]:
        """
        Returns:
            x: (C, 2, T) tensor
            y: (1,) tensor
            idx: original valid_index to recover metadata
        """
        return torch.from_numpy(self.x[idx]), torch.tensor([self.labels[idx]]), idx

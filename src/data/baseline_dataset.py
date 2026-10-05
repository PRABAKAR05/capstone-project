import json
import logging
from typing import Dict, List, Tuple

import h5py
import numpy as np
import torch
from torch.utils.data import Dataset

logger = logging.getLogger(__name__)

class SingleChannelFDIDataset(Dataset):
    """
    Dataset for training a single-channel FDI baseline model.
    Loads data entirely into memory for speed, as datasets are small (< 50MB).
    
    Inputs:
      - raw value (clean or attacked)
      - apply Phase 3 training statistics (z-score)
      - NaN remains NaN -> replaced with 0.0 -> missingness mask = 1
      - observed values -> missingness mask = 0
    
    Outputs:
      - x: (2, T) tensor. Channel 0 = normalized signal, Channel 1 = missingness indicator.
      - y: float tensor (0.0 or 1.0). 1.0 if this specific channel is attacked in this window.
      - meta: dictionary of metadata for the window (for error analysis/filtering).
    """
    def __init__(
        self,
        h5_path: str,
        meta_path: str,
        split: str,
        channel_name: str,
        all_channels: List[str],
        norm_stats: Dict,
    ):
        self.split = split
        self.channel_name = channel_name
        self.channel_idx = all_channels.index(channel_name)
        
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
        logger.info(f"Dataset {split} '{channel_name}': Kept {total_kept}/{total_orig} windows. Rejections: {rejected_reasons}")
        
        # Load HDF5 data into memory
        with h5py.File(h5_path, "r") as f:
            grp = f[split]
            # We use 'attacked_data' because the clean baseline windows are identical to clean_data 
            # and actual attacks are present in attacked_data.
            data = grp["attacked_data"][:]
            mask = grp["attack_mask"][:]
            
        # Subset to valid windows and specific channel
        data = data[valid_indices, :, self.channel_idx]
        mask = mask[valid_indices, :, self.channel_idx]
        
        # Determine labels: attack_mask.any() for this specific channel
        self.labels = np.any(mask, axis=1).astype(np.float32)
        
        # Normalization
        ch_stats = norm_stats.get("statistics", {}).get(channel_name, {}).get("zscore", {})
        mean = ch_stats.get("mean", 0.0)
        std = ch_stats.get("std", 1.0)
        
        # Apply normalization: (x - mean) / std. NaNs remain NaNs.
        norm_data = (data - mean) / std
        
        # Missingness mask
        missing_mask = np.isnan(norm_data).astype(np.float32)
        
        # Replace NaN with 0.0
        norm_data = np.nan_to_num(norm_data, nan=0.0)
        
        # Stack into (N, 2, T)
        self.x = np.stack([norm_data, missing_mask], axis=1).astype(np.float32)
        
    def __len__(self):
        return len(self.labels)
        
    def __getitem__(self, idx) -> Tuple[torch.Tensor, torch.Tensor, int]:
        """
        Returns:
            x: (2, T) tensor
            y: (1,) tensor
            idx: original valid_index to recover metadata if needed
        """
        return torch.from_numpy(self.x[idx]), torch.tensor([self.labels[idx]]), idx


"""
scripts/compute_normalization.py
================================
Extracts and computes normalization statistics (z-score, robust) exclusively 
from the training split of the preprocessed datasets.

Reads HDF5 incrementally in chunks to prevent out-of-memory errors.
Respects observation masks (ignores imputed/missing data).
"""

import os
import json
import logging
import argparse
import numpy as np
import h5py
from pathlib import Path
from tqdm import tqdm

from src.utils.config import resolve_dataset_paths

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def load_split(split_path: Path) -> dict:
    if not split_path.exists():
        raise FileNotFoundError(f"Split file not found: {split_path}")
    with open(split_path, "r", encoding="utf-8") as f:
        return json.load(f)


def compute_chunk_statistics(
    h5_path: Path, chunk_size: int = 1000
) -> dict:
    """
    Iterate over the HDF5 train split in chunks and accumulate statistics per channel.
    """
    if not h5_path.exists():
        raise FileNotFoundError(f"HDF5 file not found: {h5_path}")

    channel_data = {}

    logging.info(f"Scanning HDF5: {h5_path.name}")
    with h5py.File(h5_path, "r") as f:
        # Data is already partitioned in the 'train' group!
        train_grp = f["train"]
        num_samples = train_grp["data"].shape[0]
        
        # Channels are stored as a comma-separated string in attrs
        channels_str = f.attrs.get("channels")
        if not channels_str:
            channels_str = f.attrs.get("channel_names", "")
            
        if isinstance(channels_str, bytes):
            channels_str = channels_str.decode("utf-8")
        channels = channels_str.split(",") if channels_str else []
        
        for c in channels:
            channel_data[c] = []

        # Iterate in chunks
        for start_idx in tqdm(range(0, num_samples, chunk_size)):
            end_idx = min(start_idx + chunk_size, num_samples)
            
            # Read chunk directly from train group
            chunk_data = train_grp["data"][start_idx:end_idx]
            chunk_obs_mask = train_grp["mask"][start_idx:end_idx]
            
            # Accumulate per channel
            for c_idx, c_name in enumerate(channels):
                c_data = chunk_data[:, :, c_idx]
                c_mask = chunk_obs_mask[:, :, c_idx]
                
                # Extract only explicitly observed values
                # True in mask means observed
                valid_values = c_data[c_mask]
                
                # Also ignore NaNs just in case
                valid_values = valid_values[~np.isnan(valid_values)]
                
                if len(valid_values) > 0:
                    channel_data[c_name].append(valid_values)

    # Compute final statistics
    stats = {}
    train_obs_counts = {}
    
    for c_name, data_list in channel_data.items():
        if not data_list:
            logging.warning(f"No valid training observations for channel {c_name}!")
            stats[c_name] = {
                "zscore": {"mean": 0.0, "std": 1.0},
                "robust": {"median": 0.0, "iqr": 1.0}
            }
            train_obs_counts[c_name] = 0
            continue
            
        all_valid = np.concatenate(data_list)
        train_obs_counts[c_name] = len(all_valid)
        
        # Z-Score
        c_mean = float(np.mean(all_valid))
        c_std = float(np.std(all_valid))
        if c_std < 1e-8:
            c_std = 1.0
            
        # Robust
        c_median = float(np.median(all_valid))
        q75, q25 = np.percentile(all_valid, [75, 25])
        c_iqr = float(q75 - q25)
        if c_iqr < 1e-8:
            c_iqr = 1.0
            
        stats[c_name] = {
            "zscore": {"mean": c_mean, "std": c_std},
            "robust": {"median": c_median, "iqr": c_iqr}
        }

    return stats, train_obs_counts, channels


def main():
    parser = argparse.ArgumentParser(description="Compute Normalization Statistics from Train Split")
    args = parser.parse_args()

    paths = resolve_dataset_paths()
    processed_dir = paths["outputs"]["processed"]
    norm_dir = processed_dir / "normalization"
    norm_dir.mkdir(parents=True, exist_ok=True)
    
    splits_dir = Path("splits")
    
    # ---------------------------------------------------------
    # 1. PhysioNet
    # ---------------------------------------------------------
    physio_split_path = splits_dir / "physionet_split.json"
    physio_h5 = processed_dir / "physionet" / "physionet_grid30_win2h_7be100f8.h5"
    
    if physio_split_path.exists() and physio_h5.exists():
        logging.info("Computing PhysioNet Normalization...")
        stats, obs_counts, channels = compute_chunk_statistics(
            h5_path=physio_h5
        )
        
        artifact = {
            "dataset": "PhysioNet",
            "preprocessing_hash": "7be100f8",
            "channels": channels,
            "training_observations_used": obs_counts,
            "statistics": stats,
            "note": "The normalization method used by subsequent experiments must be selected explicitly and recorded in the experiment configuration."
        }
        
        out_path = norm_dir / "physionet_normalization.json"
        with open(out_path, "w") as f:
            json.dump(artifact, f, indent=4)
        logging.info(f"Saved PhysioNet normalization to {out_path}")
    else:
        logging.warning("PhysioNet outputs not found, skipping...")

    # ---------------------------------------------------------
    # 2. WESAD
    # ---------------------------------------------------------
    wesad_split_path = splits_dir / "wesad_split.json"
    wesad_h5 = processed_dir / "wesad" / "wesad_rate4hz_win30s_5cbc160d.h5"
    
    if wesad_split_path.exists() and wesad_h5.exists():
        logging.info("Computing WESAD Normalization...")
        stats, obs_counts, channels = compute_chunk_statistics(
            h5_path=wesad_h5
        )
        
        artifact = {
            "dataset": "WESAD",
            "preprocessing_hash": "5cbc160d",
            "channels": channels,
            "training_observations_used": obs_counts,
            "statistics": stats,
            "note": "The normalization method used by subsequent experiments must be selected explicitly and recorded in the experiment configuration."
        }
        
        out_path = norm_dir / "wesad_normalization.json"
        with open(out_path, "w") as f:
            json.dump(artifact, f, indent=4)
        logging.info(f"Saved WESAD normalization to {out_path}")
    else:
        logging.warning("WESAD outputs not found, skipping...")

    logging.info("Normalization computation complete.")

if __name__ == "__main__":
    main()

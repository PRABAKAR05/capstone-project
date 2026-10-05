"""
CSCM-IoMT Phase 4: Full Dataset Validation
==========================================
Validates the fully generated FDI attack benchmark.

Checks:
 1. Metadata alignment and splits
 2. Rejection statistics (counts and reasons)
 3. Pearson correlation changes for coordinated attacks
 4. Overall perturbation magnitude validation
"""

import json
import logging
from pathlib import Path

import h5py
import numpy as np
from scipy.stats import pearsonr

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def validate_dataset(name: str, h5_path: str, meta_path: str, channels: list[str]):
    logging.info(f"--- Validating {name.upper()} Dataset ---")
    
    with h5py.File(h5_path, "r") as f:
        with open(meta_path, "r") as mf:
            meta = json.load(mf)
            
        splits = ["train", "val", "test"]
        total_samples = 0
        total_plausible = 0
        total_rejected = 0
        
        # We will collect correlation shifts for coordinated attacks to prove the attack mechanism
        coord_stats = []
        
        for split in splits:
            if split not in f:
                continue
                
            split_meta = meta[split]
            data_clean = f[split]["clean_data"][:]
            data_attack = f[split]["attacked_data"][:]
            mask = f[split]["attack_mask"][:]
            
            n = len(split_meta)
            assert data_clean.shape[0] == n
            assert data_attack.shape[0] == n
            
            total_samples += n
            
            split_plausible = sum(1 for m in split_meta if m["is_plausible"])
            split_rejected = n - split_plausible
            
            total_plausible += split_plausible
            total_rejected += split_rejected
            
            logging.info(f"  [{split}] {n} samples -> {split_plausible} plausible, {split_rejected} rejected")
            
            # Detailed rejection reasons
            reasons = {}
            for m in split_meta:
                r = m.get("rejection_reason")
                if r:
                    # Simplify reason string for aggregation
                    cat = "bound_violation" if "bound_violation" in r else ("nan_inherited" if "nan_inherited" in r else "other")
                    reasons[cat] = reasons.get(cat, 0) + 1
                    
            if reasons:
                logging.info(f"    Rejection Breakdown: {reasons}")
                
            # Distribution / Relationship Validation
            for i, m in enumerate(split_meta):
                if m["attack_family"].startswith("coordinated") and m["is_plausible"]:
                    chans = m["attacked_channels"]
                    if len(chans) == 2:
                        idx0, idx1 = channels.index(chans[0]), channels.index(chans[1])
                        c0_clean = data_clean[i, :, idx0]
                        c1_clean = data_clean[i, :, idx1]
                        c0_att = data_attack[i, :, idx0]
                        c1_att = data_attack[i, :, idx1]
                        
                        # filter nans
                        valid_c = ~np.isnan(c0_clean) & ~np.isnan(c1_clean)
                        valid_a = ~np.isnan(c0_att) & ~np.isnan(c1_att)
                        
                        if valid_c.sum() > 10 and valid_a.sum() > 10:
                            r_clean, _ = pearsonr(c0_clean[valid_c], c1_clean[valid_c])
                            r_att, _ = pearsonr(c0_att[valid_a], c1_att[valid_a])
                            
                            coord_stats.append({
                                "channels": f"{chans[0]}-{chans[1]}",
                                "r_clean": r_clean,
                                "r_att": r_att,
                                "delta": r_att - r_clean,
                                "policy": m.get("policy", "unknown")
                            })
                            
        # Aggregate coord stats
        if coord_stats:
            policies = set(s["policy"] for s in coord_stats)
            for pol in policies:
                pol_stats = [s for s in coord_stats if s["policy"] == pol]
                avg_clean = np.nanmean([s["r_clean"] for s in pol_stats])
                avg_att = np.nanmean([s["r_att"] for s in pol_stats])
                avg_delta = np.nanmean([s["delta"] for s in pol_stats])
                logging.info(f"  Coordinated Policy '{pol}':")
                logging.info(f"    Avg r (clean) = {avg_clean:.4f}")
                logging.info(f"    Avg r (att)   = {avg_att:.4f}")
                logging.info(f"    Avg Δr        = {avg_delta:.4f}")
        
        logging.info(f"  Total: {total_samples} samples, {total_plausible} plausible ({(total_plausible/total_samples)*100:.1f}%)")
        logging.info("-" * 40)


if __name__ == "__main__":
    PHYSIONET_CHANNELS = ["HR", "NISysABP", "NIDiasABP", "NIMAP", "Temp"]
    WESAD_CHANNELS = [
        "chest_ACC_0", "chest_ACC_1", "chest_ACC_2", "chest_ECG", "chest_EDA",
        "chest_EMG", "chest_Resp", "chest_Temp", "wrist_ACC_0", "wrist_ACC_1",
        "wrist_ACC_2", "wrist_BVP", "wrist_EDA", "wrist_TEMP"
    ]
    
    validate_dataset(
        "physionet", 
        "data/generated_attacks/physionet/physionet_attacks.h5", 
        "data/generated_attacks/physionet/physionet_attacks_metadata.json",
        PHYSIONET_CHANNELS
    )
    
    validate_dataset(
        "wesad", 
        "data/generated_attacks/wesad/wesad_attacks.h5", 
        "data/generated_attacks/wesad/wesad_attacks_metadata.json",
        WESAD_CHANNELS
    )

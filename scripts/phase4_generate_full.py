"""
CSCM-IoMT Phase 4: Full Dataset Generation
==========================================
Generates the complete synthetic FDI attack benchmark across all splits
for both PhysioNet and WESAD datasets.

Strictly adheres to:
 - Frozen configs/attacks.yaml
 - Deterministic seeds per window
 - Train/val/test split isolation
 - NaN policies and bounds checks on TARGETED channels only
 - Comprehensive metadata extraction per sample
"""

import os
import json
import logging
from pathlib import Path

import h5py
import numpy as np
import yaml

from src.attacks.generator import AttackGenerator
from src.attacks.channel_relationships import get_physionet_relationships, get_wesad_relationships

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def generate_full_dataset(
    dataset_name: str,
    h5_in_path: str,
    norm_path: str,
    out_path: str,
):
    with open("configs/attacks.yaml", "r") as f:
        attack_cfg = yaml.safe_load(f)
        
    with open(norm_path, "r") as f:
        norm_stats = json.load(f)
        
    out_dir = Path(out_path).parent
    out_dir.mkdir(parents=True, exist_ok=True)
    
    logging.info(f"Starting FULL attack generation for {dataset_name} -> {out_path}")
    
    with h5py.File(h5_in_path, "r") as f_in, h5py.File(out_path, "w") as f_out:
        channels_str = f_in.attrs.get("channels") or f_in.attrs.get("channel_names")
        if isinstance(channels_str, bytes):
            channels_str = channels_str.decode("utf-8")
        all_channels = channels_str.split(",")
        
        # Determine relationships
        if dataset_name == "physionet":
            rel_configs = get_physionet_relationships()
        else:
            rel_configs = get_wesad_relationships()
            
        bounds = attack_cfg[dataset_name]["plausibility_bounds"]
        
        generator = AttackGenerator(attack_cfg, dataset_name, norm_stats, bounds, all_channels)
        
        splits = ["train", "val", "test"]
        meta_storage = {split: [] for split in splits}
        
        composition = attack_cfg.get("composition", {
            "clean": 0.25,
            "single_channel": 0.25,
            "coordinated_2": 0.25,
            "coordinated_3": 0.25
        })
        comp_keys = sorted(list(composition.keys())) # deterministic order
        
        single_types = ["additive", "multiplicative", "drift"]
        severities = ["low", "medium", "high"]
        
        for split in splits:
            if split not in f_in:
                continue
                
            in_grp = f_in[split]
            data_arr = in_grp["data"]
            n_windows = data_arr.shape[0]
            T = data_arr.shape[1]
            C = data_arr.shape[2]
            
            logging.info(f"  Processing {dataset_name} {split} split ({n_windows} windows)...")
            
            out_grp = f_out.create_group(split)
            out_grp.create_dataset("clean_data", shape=(n_windows, T, C), dtype=np.float32)
            out_grp.create_dataset("attacked_data", shape=(n_windows, T, C), dtype=np.float32)
            out_grp.create_dataset("clean_mask", shape=(n_windows, T, C), dtype=bool)
            out_grp.create_dataset("attack_mask", shape=(n_windows, T, C), dtype=bool)
            
            # Create a dedicated RNG for planning the attacks in this split for exact determinism
            plan_rng = np.random.default_rng(42 + splits.index(split))
            
            for i in range(n_windows):
                clean_data = data_arr[i]
                if "mask" in in_grp:
                    clean_mask = in_grp["mask"][i]
                else:
                    clean_mask = np.ones_like(clean_data, dtype=bool)
                
                # 1. Pick composition group via cycle to ensure exact proportions
                comp_group = comp_keys[i % len(comp_keys)]
                
                # 2. Assign attack family, targets, policy, etc
                policy = "opposite_direction"
                policy_params = {}
                
                if comp_group == "clean":
                    att_family = "clean"
                    target_channels = []
                elif comp_group == "single_channel":
                    att_family = plan_rng.choice(single_types)
                    target_channels = [plan_rng.choice(all_channels)]
                elif comp_group == "coordinated_2":
                    att_family = "coordinated_2"
                    # Find all 2-channel relationships
                    valid_rels = [k for k, v in rel_configs.items() if len(v["channels"]) == 2]
                    if valid_rels:
                        rel_key = plan_rng.choice(valid_rels)
                        target_channels = rel_configs[rel_key]["channels"]
                        policy = rel_configs[rel_key].get("policy", "opposite_direction")
                        policy_params = rel_configs[rel_key].get("policy_params", {})
                    else:
                        target_channels = list(plan_rng.choice(all_channels, size=2, replace=False))
                elif comp_group == "coordinated_3":
                    att_family = "coordinated_3"
                    valid_rels = [k for k, v in rel_configs.items() if len(v["channels"]) >= 3]
                    if valid_rels:
                        rel_key = plan_rng.choice(valid_rels)
                        target_channels = rel_configs[rel_key]["channels"]
                        policy = rel_configs[rel_key].get("policy", "opposite_direction")
                        policy_params = rel_configs[rel_key].get("policy_params", {})
                    else:
                        target_channels = list(plan_rng.choice(all_channels, size=3, replace=False))
                else:
                    att_family = "clean"
                    target_channels = []
                
                # Randomize severity
                sev = plan_rng.choice(severities) if att_family != "clean" else "none"
                
                # Base seed for this specific window's generation
                window_seed = 100000 + i + (splits.index(split) * 1000000)
                
                res = generator.generate_attack(
                    clean_data, clean_mask,
                    att_family, sev, target_channels,
                    window_seed,
                    policy=policy,
                    policy_params=policy_params
                )
                
                out_grp["clean_data"][i] = clean_data
                out_grp["attacked_data"][i] = res["attacked_data"]
                out_grp["clean_mask"][i] = clean_mask
                out_grp["attack_mask"][i] = res["attack_mask"]
                
                m = res["metadata"]
                m["window_index"] = i
                m["composition_group"] = comp_group
                meta_storage[split].append(m)
                
                if (i + 1) % 1000 == 0:
                    logging.info(f"    Completed {i + 1}/{n_windows} windows...")
            
            logging.info(f"  Finished {split} split. Summary:")
            rj_count = sum(1 for m in meta_storage[split] if m.get("rejection_reason") is not None)
            logging.info(f"    Total: {n_windows}, Rejected/Flagged: {rj_count}, Plausible: {n_windows - rj_count}")
                    
        # Save metadata
        meta_out = str(out_path).replace(".h5", "_metadata.json")
        with open(meta_out, "w") as jf:
            json.dump(meta_storage, jf, indent=2)
            
    logging.info(f"COMPLETED FULL GENERATION for {dataset_name}.")


if __name__ == "__main__":
    generate_full_dataset(
        "physionet", 
        "data/processed/physionet/physionet_grid30_win2h_7be100f8.h5",
        "data/processed/normalization/physionet_normalization.json",
        "data/generated_attacks/physionet/physionet_attacks.h5"
    )
    
    generate_full_dataset(
        "wesad", 
        "data/processed/wesad/wesad_rate4hz_win30s_5cbc160d.h5",
        "data/processed/normalization/wesad_normalization.json",
        "data/generated_attacks/wesad/wesad_attacks.h5"
    )

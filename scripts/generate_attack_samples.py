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

def get_config(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)

def generate_samples(dataset_name: str, h5_in_path: str, norm_path: str, out_path: str, max_samples: int = 50):
    attack_cfg = get_config("configs/attacks.yaml")
    
    with open(norm_path, "r") as f:
        norm_stats = json.load(f)
        
    out_dir = Path(out_path).parent
    out_dir.mkdir(parents=True, exist_ok=True)
    
    logging.info(f"Generating attack samples for {dataset_name} (Max {max_samples} windows)")
    
    with h5py.File(h5_in_path, "r") as f_in, h5py.File(out_path, "w") as f_out:
        channels_str = f_in.attrs.get("channels") or f_in.attrs.get("channel_names")
        if isinstance(channels_str, bytes):
            channels_str = channels_str.decode("utf-8")
        all_channels = channels_str.split(",")
        
        # Determine relationships to use
        if dataset_name == "physionet":
            rel_configs = get_physionet_relationships()
        else:
            rel_configs = get_wesad_relationships()
            
        bounds = attack_cfg[dataset_name]["plausibility_bounds"]
        
        generator = AttackGenerator(attack_cfg, dataset_name, norm_stats, bounds, all_channels)
        
        # Setup output HDF5
        grp = f_out.create_group("samples")
        
        # Get shape info from train split
        in_train = f_in["train"]
        num_windows = min(max_samples, in_train["data"].shape[0])
        win_len = in_train["data"].shape[1]
        num_chan = in_train["data"].shape[2]
        
        grp.create_dataset("clean_data", shape=(num_windows, win_len, num_chan), dtype=np.float32)
        grp.create_dataset("attacked_data", shape=(num_windows, win_len, num_chan), dtype=np.float32)
        grp.create_dataset("clean_mask", shape=(num_windows, win_len, num_chan), dtype=bool)
        grp.create_dataset("attack_mask", shape=(num_windows, win_len, num_chan), dtype=bool)
        
        # Metadata storage
        meta_storage = []
        
        # Define attack rotating pool for samples
        # Let's generate a variety:
        # single additive, single multiplicative, coordinated 2-chan, coordinated 3-chan, drift
        attack_types = ["additive", "multiplicative", "drift", "coordinated_2", "coordinated_3", "clean"]
        severities = ["low", "medium", "high"]
        
        # Single channel candidates
        single_candidates = all_channels[:3] # just take first 3 for single tests
        
        for i in range(num_windows):
            clean_data = in_train["data"][i]
            if "mask" in in_train:
                clean_mask = in_train["mask"][i]
            else:
                clean_mask = np.ones_like(clean_data, dtype=bool)
                
            # Rotate attack strategies based on index
            att_type = attack_types[i % len(attack_types)]
            sev = severities[(i // len(attack_types)) % len(severities)]
            
            # Select channels
            target_channels = []
            if att_type in ["additive", "multiplicative", "drift"]:
                target_channels = [single_candidates[i % len(single_candidates)]]
            elif att_type == "coordinated_2":
                # Find a 2 channel relation
                for k, v in rel_configs.items():
                    if len(v["channels"]) == 2:
                        target_channels = v["channels"]
                        break
            elif att_type == "coordinated_3":
                for k, v in rel_configs.items():
                    if len(v["channels"]) >= 3:
                        target_channels = v["channels"]
                        break
                # Fallback if no 3 channel relation
                if not target_channels:
                    target_channels = all_channels[:3]
            
            seed = 42 + i
            
            # Generate!
            res = generator.generate_attack(
                clean_data, clean_mask, att_type, sev, target_channels, seed
            )
            
            # Write to HDF5
            grp["clean_data"][i] = clean_data
            grp["attacked_data"][i] = res["attacked_data"]
            grp["clean_mask"][i] = clean_mask
            grp["attack_mask"][i] = res["attack_mask"]
            
            # Collect metadata to save as JSON later
            meta = res["metadata"]
            meta["window_index"] = i
            
            meta_storage.append(meta)
            
        # Save metadata as JSON for easy inspection
        with open(out_path.replace(".h5", "_metadata.json"), "w") as jf:
            json.dump(meta_storage, jf, indent=2)
            
    logging.info(f"Finished {dataset_name} sample generation.")

if __name__ == "__main__":
    generate_samples(
        "physionet", 
        "data/processed/physionet/physionet_grid30_win2h_7be100f8.h5",
        "data/processed/normalization/physionet_normalization.json",
        "data/generated_attacks/physionet/samples.h5"
    )
    generate_samples(
        "wesad", 
        "data/processed/wesad/wesad_rate4hz_win30s_5cbc160d.h5",
        "data/processed/normalization/wesad_normalization.json",
        "data/generated_attacks/wesad/samples.h5"
    )

"""
scripts/preprocess_wesad.py
===========================
Runs the WESAD preprocessing experiment.
Supports safe resume behavior for massive subject files.
"""

import argparse
import hashlib
import json
import logging
import os
from pathlib import Path

import h5py
import numpy as np
import yaml

from src.preprocessing.wesad_preprocessor import process_wesad_subject, generate_wesad_windows
from src.preprocessing.splits import generate_wesad_splits
from src.preprocessing.quality import append_experiment_record, generate_wesad_report

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def get_config_hash(config: dict) -> str:
    config_str = json.dumps(config, sort_keys=True)
    return hashlib.sha256(config_str.encode('utf-8')).hexdigest()[:8]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--subjects", nargs="+", default=None, help="Process only specific subjects (Sample Mode)")
    args = parser.parse_args()

    # Load Config
    with open("configs/preprocessing.yaml", "r") as f:
        config = yaml.safe_load(f)

    w_config = config["wesad"]
    seed = config["seed"]
    cfg_hash = get_config_hash(w_config)

    logging.info(f"Starting WESAD Preprocessing (Config Hash: {cfg_hash})")

    # Paths
    from src.utils.config import resolve_dataset_paths
    paths = resolve_dataset_paths()
    raw_dir = paths["wesad"]["root"]
    processed_dir = Path(f"data/processed/wesad")
    splits_path = Path("data/processed/splits/wesad_split.json")
    results_dir = Path("results/preprocessing")
    
    from src.data.wesad_loader import load_subject_pkl
    
    all_subjects = w_config["split"]["train_subjects"] + w_config["split"]["val_subjects"] + w_config["split"]["test_subjects"]
    
    if args.subjects:
        logging.info(f"*** SAMPLE MODE: Processing only subjects {args.subjects} ***")
        # Only process requested subjects, but they must be in the split definition
        subjects_to_process = [s for s in args.subjects if s in all_subjects]
    else:
        subjects_to_process = all_subjects

    # Generate or load splits
    splits = generate_wesad_splits(
        w_config["split"]["train_subjects"],
        w_config["split"]["val_subjects"],
        w_config["split"]["test_subjects"],
        seed,
        splits_path
    )
    
    # We will pick the first configuration parameters as the primary one for the HDF5 output
    target_rate = w_config["target_rates_hz"][0]
    window_sec = w_config["window_sizes_seconds"][0]
    purity_thresh = w_config["purity_thresholds"][0]
    
    out_file = processed_dir / f"wesad_rate{target_rate}hz_win{window_sec}s_{cfg_hash}.h5"
    processed_dir.mkdir(parents=True, exist_ok=True)
    
    # Track overall quality stats
    overall_stats = {
        "subjects_processed": 0,
        "subjects_failed": 0,
        "target_rate_hz": target_rate,
        "window_size_sec": window_sec,
        "purity_threshold": purity_thresh,
        "train_subjects": len(splits["train"]),
        "val_subjects": len(splits["val"]),
        "test_subjects": len(splits["test"]),
        "windows_generated": 0,
        "usable_windows": 0,
        "rejected_windows": 0,
        "rejection_reasons": {}
    }

    # Initialize HDF5 if not exists
    if not out_file.exists():
        with h5py.File(out_file, "w") as h5f:
            for sp in ["train", "val", "test"]:
                grp = h5f.create_group(sp)
                
                # Channels: 6 chest, 2 wrist (BVP, ACCx3, EDA, TEMP) => We'll define dynamically
                grp.create_dataset("data", shape=(0, window_sec * target_rate, 8), 
                                   maxshape=(None, window_sec * target_rate, 20), dtype=np.float32, chunks=True)
                grp.create_dataset("mask", shape=(0, window_sec * target_rate, 8), 
                                   maxshape=(None, window_sec * target_rate, 20), dtype=bool, chunks=True)
                grp.create_dataset("label", shape=(0,), maxshape=(None,), dtype=np.int32, chunks=True)
                grp.create_dataset("subject_id", shape=(0,), maxshape=(None,), dtype=h5py.string_dtype(encoding='utf-8'), chunks=True)
                
            h5f.attrs["config_hash"] = cfg_hash
            h5f.attrs["processed_subjects"] = ""

    # Subject mapping
    sub_to_split = {}
    for sp_name, ids in splits.items():
        for s_id in ids:
            sub_to_split[s_id] = sp_name
            
    chest_mods = ["ACC", "ECG", "EDA", "EMG", "Resp", "Temp"]
    wrist_mods = ["ACC", "BVP", "EDA", "TEMP"]

    # Process subjects sequentially to prevent OOM
    for sub in subjects_to_process:
        # Check if already processed (Resume Support)
        with h5py.File(out_file, "r") as h5f:
            processed_subs = h5f.attrs["processed_subjects"].split(",")
            if sub in processed_subs:
                logging.info(f"Subject {sub} already processed. Skipping.")
                continue
                
        logging.info(f"Processing WESAD subject: {sub}")
        try:
            subject_dir = raw_dir / sub
            subject_data = load_subject_pkl(subject_dir, sub)
            if not subject_data:
                overall_stats["subjects_failed"] += 1
                continue
                
            overall_stats["subjects_processed"] += 1
            
            # 1. Resample and Align
            values, masks, labels, chan_names = process_wesad_subject(
                subject_data, target_rate, chest_mods, wrist_mods
            )
            
            # 2. Windowing
            w_v, w_m, w_l, stats = generate_wesad_windows(
                values, masks, labels, window_sec, target_rate,
                w_config["window_overlap"], purity_thresh,
                w_config["valid_labels"], w_config["transient_label"],
                w_config["ignore_labels"]
            )
            
            overall_stats["windows_generated"] += stats["generated"]
            overall_stats["usable_windows"] += stats["usable"]
            overall_stats["rejected_windows"] += stats["rejected"]
            for r, c in stats["reasons"].items():
                overall_stats["rejection_reasons"][r] = overall_stats["rejection_reasons"].get(r, 0) + c
                
            if not w_v:
                continue
                
            # 3. Write to HDF5 atomically
            sp_name = sub_to_split[sub]
            
            with h5py.File(out_file, "a") as h5f:
                grp = h5f[sp_name]
                
                v_arr = np.array(w_v, dtype=np.float32)
                m_arr = np.array(w_m, dtype=bool)
                l_arr = np.array(w_l, dtype=np.int32)
                
                # Resize channels if needed (first subject determines shape)
                num_channels = v_arr.shape[2]
                if grp["data"].shape[2] != num_channels:
                    grp["data"].resize(num_channels, axis=2)
                    grp["mask"].resize(num_channels, axis=2)
                
                cur_len = grp["data"].shape[0]
                add_len = len(v_arr)
                
                grp["data"].resize(cur_len + add_len, axis=0)
                grp["data"][cur_len:] = v_arr
                
                grp["mask"].resize(cur_len + add_len, axis=0)
                grp["mask"][cur_len:] = m_arr
                
                grp["label"].resize(cur_len + add_len, axis=0)
                grp["label"][cur_len:] = l_arr
                
                grp["subject_id"].resize(cur_len + add_len, axis=0)
                grp["subject_id"][cur_len:] = np.array([sub] * add_len, dtype=object)
                
                # Update processed list for resume
                processed_list = h5f.attrs["processed_subjects"].split(",")
                if "" in processed_list: processed_list.remove("")
                processed_list.append(sub)
                h5f.attrs["processed_subjects"] = ",".join(processed_list)
                
                if "channel_names" not in h5f.attrs:
                    h5f.attrs["channel_names"] = ",".join(chan_names)

        except Exception as e:
            logging.error(f"Error processing subject {sub}: {e}")
            overall_stats["subjects_failed"] += 1
            
        finally:
            if 'subject_data' in locals():
                del subject_data
            import gc
            gc.collect()

    # Record experiment
    exp_record = {
        "dataset": "wesad",
        "hash": cfg_hash,
        "target_rate": target_rate,
        "window_sec": window_sec,
        "purity": purity_thresh,
        "usable_windows": overall_stats["usable_windows"]
    }
    append_experiment_record(exp_record, results_dir / "preprocessing_experiments.json")
    
    generate_wesad_report(overall_stats, results_dir / "wesad_preprocessing.md")
    
    logging.info("WESAD preprocessing complete.")


if __name__ == "__main__":
    main()

"""
scripts/preprocess_physionet.py
===============================
Runs the PhysioNet preprocessing experiment. 
Produces candidate HDF5 representations and quality reports.
"""

import argparse
import hashlib
import json
import logging
from pathlib import Path

import h5py
import numpy as np
import yaml

from src.preprocessing.physionet_preprocessor import process_record_to_grid, generate_physionet_windows
from src.preprocessing.splits import generate_physionet_splits
from src.preprocessing.temporal_grid import validate_grid_window_compatibility
from src.preprocessing.quality import append_experiment_record, generate_physionet_report

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def get_config_hash(config: dict) -> str:
    """Generate a deterministic hash of the configuration."""
    config_str = json.dumps(config, sort_keys=True)
    return hashlib.sha256(config_str.encode('utf-8')).hexdigest()[:8]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=None, help="Process only N records for testing")
    args = parser.parse_args()

    # Load Config
    with open("configs/preprocessing.yaml", "r") as f:
        config = yaml.safe_load(f)

    p_config = config["physionet"]
    seed = config["seed"]
    cfg_hash = get_config_hash(p_config)

    logging.info(f"Starting PhysioNet Preprocessing (Config Hash: {cfg_hash})")
    if args.sample:
        logging.info(f"*** SAMPLE MODE: Processing only {args.sample} records ***")

    # Paths
    from src.utils.config import resolve_dataset_paths
    paths = resolve_dataset_paths()
    raw_dir = paths["physionet"]["set_a"]
    processed_dir = Path(f"data/processed/physionet")
    splits_path = Path("data/processed/splits/physionet_split.json")
    results_dir = Path("results/preprocessing")
    
    from src.data.physionet_loader import parse_record
    
    all_files = list(raw_dir.glob("*.txt"))
    # Extract RecordID from filename (e.g., "132539.txt" -> "132539")
    all_records = sorted([f.stem for f in all_files])
    
    if args.sample:
        all_records = all_records[:args.sample]
        all_files = all_files[:args.sample]

    if not all_records:
        logging.error("No records found in data/raw/physionet/set-a!")
        return

    # Generate or load splits
    splits = generate_physionet_splits(
        all_records,
        p_config["split"]["train"],
        p_config["split"]["val"],
        p_config["split"]["test"],
        seed,
        splits_path
    )
    
    channels = p_config["primary_channels"] # + secondary_channels if requested
    
    # Track overall quality stats
    overall_stats = {
        "records_processed": 0,
        "records_failed": 0,
        "primary_channels": p_config["primary_channels"],
        "secondary_channels": p_config["secondary_channels"],
        "evaluated_grids": p_config["temporal_grids"],
        "train_records": len(splits["train"]),
        "val_records": len(splits["val"]),
        "test_records": len(splits["test"]),
        "rejection_reasons": {}
    }

    grid_res = p_config["temporal_grids"][0] 
    window_h = p_config["window_sizes_hours"][0]
    imputation_mode = p_config["imputation_modes"][0]
    max_gap = p_config["max_imputation_gaps"][0]
    coverage = p_config["coverage_thresholds"][0]
    
    is_valid = validate_grid_window_compatibility(grid_res, window_h * 60.0, p_config["min_temporal_points"])
    if not is_valid:
        logging.error(f"Config {grid_res}m grid + {window_h}h window is INVALID.")
        return
        
    out_file = processed_dir / f"physionet_grid{grid_res}_win{window_h}h_{cfg_hash}.h5"
    processed_dir.mkdir(parents=True, exist_ok=True)
    
    record_to_split = {}
    for sp_name, ids in splits.items():
        for r_id in ids:
            record_to_split[str(r_id)] = sp_name

    with h5py.File(out_file, "w") as h5f:
        for sp in ["train", "val", "test"]:
            grp = h5f.create_group(sp)
            grp.create_dataset("data", shape=(0, int(window_h * 60 / grid_res), len(channels)), 
                               maxshape=(None, int(window_h * 60 / grid_res), len(channels)), 
                               dtype=np.float32, chunks=True)
            grp.create_dataset("mask", shape=(0, int(window_h * 60 / grid_res), len(channels)), 
                               maxshape=(None, int(window_h * 60 / grid_res), len(channels)), 
                               dtype=bool, chunks=True)
            grp.create_dataset("record_id", shape=(0,), maxshape=(None,), dtype=h5py.string_dtype(encoding='utf-8'), chunks=True)

        h5f.attrs["config_hash"] = cfg_hash
        h5f.attrs["grid_res_min"] = grid_res
        h5f.attrs["window_h"] = window_h
        h5f.attrs["channels"] = ",".join(channels)

        for i, rec_id in enumerate(all_records):
            file_path = raw_dir / f"{rec_id}.txt"
            overall_stats["records_processed"] += 1
            if i % 100 == 0:
                logging.info(f"Processed {i}/{len(all_records)} records...")
                
            try:
                rec_data = parse_record(file_path)
                
                # Convert rec_data["parameters"] into a DataFrame compatible with process_record_to_grid
                # param_name -> list of (time_min, value, is_sentinel, error)
                rows = []
                for param, obs_list in rec_data.get("parameters", {}).items():
                    if param in channels:
                        for time_min, val, is_sent, _ in obs_list:
                            rows.append({'elapsed_min': time_min, 'Parameter': param, 'Value': val if not is_sent else -1.0})
                
                if not rows:
                    continue
                    
                import pandas as pd
                df = pd.DataFrame(rows)
                
                # 1. Grid
                grid_vals, grid_mask = process_record_to_grid(
                    df, channels, grid_res, imputation_mode, max_gap
                )
                
                if len(grid_vals) == 0:
                    continue
                    
                # 2. Windows
                w_vals, w_masks, stats = generate_physionet_windows(
                    grid_vals, grid_mask, window_h * 60.0, grid_res, 
                    p_config["window_overlap"], p_config["min_temporal_points"], coverage
                )
                
                for r, c in stats["reasons"].items():
                    overall_stats["rejection_reasons"][r] = overall_stats["rejection_reasons"].get(r, 0) + c
                    
                if not w_vals:
                    continue
                    
                # 3. Save to appropriate split
                sp_name = record_to_split[str(rec_id)]
                grp = h5f[sp_name]
                
                v_arr = np.array(w_vals, dtype=np.float32)
                m_arr = np.array(w_masks, dtype=bool)
                
                cur_len = grp["data"].shape[0]
                add_len = len(v_arr)
                
                grp["data"].resize(cur_len + add_len, axis=0)
                grp["data"][cur_len:] = v_arr
                
                grp["mask"].resize(cur_len + add_len, axis=0)
                grp["mask"][cur_len:] = m_arr
                
                grp["record_id"].resize(cur_len + add_len, axis=0)
                grp["record_id"][cur_len:] = np.array([str(rec_id)] * add_len, dtype=object)

            except Exception as e:
                logging.error(f"Error processing record {rec_id}: {e}")
                overall_stats["records_failed"] += 1

    # Record experiment details
    exp_record = {
        "dataset": "physionet",
        "hash": cfg_hash,
        "grid_min": grid_res,
        "window_h": window_h,
        "usable_windows": 0 # We could count the h5 files
    }
    append_experiment_record(exp_record, results_dir / "preprocessing_experiments.json")
    
    generate_physionet_report(overall_stats, results_dir / "physionet_preprocessing.md")
    
    logging.info("PhysioNet preprocessing complete.")


if __name__ == "__main__":
    main()

"""
scripts/validate_preprocessed.py
================================
Validates processed HDF5 datasets for leakage (Subject/Record level),
data integrity, and correctness of masks.
"""

import json
import logging
from pathlib import Path

import h5py
import numpy as np

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def check_split_crossover(train_ids: list, val_ids: list, test_ids: list) -> bool:
    """Returns True if leakage detected."""
    t = set(train_ids)
    v = set(val_ids)
    ts = set(test_ids)
    
    if not t.isdisjoint(v):
        logging.error(f"Leakage: Train and Val overlap -> {t.intersection(v)}")
        return True
    if not t.isdisjoint(ts):
        logging.error(f"Leakage: Train and Test overlap -> {t.intersection(ts)}")
        return True
    if not v.isdisjoint(ts):
        logging.error(f"Leakage: Val and Test overlap -> {v.intersection(ts)}")
        return True
    return False


def validate_physionet(h5_path: Path):
    logging.info(f"Validating PhysioNet: {h5_path}")
    
    with h5py.File(h5_path, "r") as h5f:
        # Check splits
        tr_ids = [s.decode('utf-8') for s in h5f['train']['record_id'][:]]
        va_ids = [s.decode('utf-8') for s in h5f['val']['record_id'][:]]
        te_ids = [s.decode('utf-8') for s in h5f['test']['record_id'][:]]
        
        has_leak = check_split_crossover(tr_ids, va_ids, te_ids)
        if has_leak:
            raise ValueError("PhysioNet Record Leakage Detected!")
            
        logging.info("PhysioNet Leakage Check: PASS")
        
        # Check masks
        tr_mask = h5f['train']['mask'][:]
        tr_data = h5f['train']['data'][:]
        
        # Values that are observed (mask=True) must not be NaN
        observed_data = tr_data[tr_mask]
        if np.any(np.isnan(observed_data)):
            raise ValueError("Observed data (mask=True) contains NaN!")
            
        logging.info("PhysioNet Mask Integrity: PASS")


def validate_wesad(h5_path: Path):
    logging.info(f"Validating WESAD: {h5_path}")
    
    with h5py.File(h5_path, "r") as h5f:
        # Check splits
        tr_ids = [s.decode('utf-8') for s in h5f['train']['subject_id'][:]]
        va_ids = [s.decode('utf-8') for s in h5f['val']['subject_id'][:]]
        te_ids = [s.decode('utf-8') for s in h5f['test']['subject_id'][:]]
        
        has_leak = check_split_crossover(tr_ids, va_ids, te_ids)
        if has_leak:
            raise ValueError("WESAD Subject Leakage Detected!")
            
        logging.info("WESAD Leakage Check: PASS")
        
        # Check masks
        tr_mask = h5f['train']['mask'][:]
        tr_data = h5f['train']['data'][:]
        
        observed_data = tr_data[tr_mask]
        if np.any(np.isnan(observed_data)):
            raise ValueError("WESAD Observed data (mask=True) contains NaN!")
            
        logging.info("WESAD Mask Integrity: PASS")


def main():
    processed_dir = Path("data/processed")
    p_dir = processed_dir / "physionet"
    w_dir = processed_dir / "wesad"
    
    # Validate latest PhysioNet file
    p_files = list(p_dir.glob("*.h5"))
    if p_files:
        validate_physionet(p_files[-1])
    else:
        logging.warning("No PhysioNet h5 found to validate.")
        
    # Validate latest WESAD file
    w_files = list(w_dir.glob("*.h5"))
    if w_files:
        validate_wesad(w_files[-1])
    else:
        logging.warning("No WESAD h5 found to validate.")
        
    logging.info("Validation complete.")


if __name__ == "__main__":
    main()

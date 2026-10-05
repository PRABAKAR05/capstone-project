"""
Inspect Phase 3 PhysioNet HDF5 to determine exactly how masked values
are represented in the tensor and clean_mask arrays.
"""
import h5py
import numpy as np

PHYSIONET_H5 = "data/processed/physionet/physionet_grid30_win2h_7be100f8.h5"
CHANNELS = ["HR", "NISysABP", "NIDiasABP", "NIMAP", "Temp"]

with h5py.File(PHYSIONET_H5, "r") as f:
    for split in ["train", "val", "test"]:
        data  = f[split]["data"]
        mask  = f[split]["mask"]
        print(f"\n=== {split} ===")
        print(f"  data shape: {data.shape}  dtype: {data.dtype}")
        print(f"  mask shape: {mask.shape}  dtype: {mask.dtype}")
        
        # Sample first 5 windows
        d5 = data[:5]
        m5 = mask[:5]
        
        nan_count  = int(np.isnan(d5).sum())
        inf_count  = int(np.isinf(d5).sum())
        mask_false = int((~m5).sum())
        mask_true  = int(m5.sum())
        
        print(f"  NaN in first 5 windows: {nan_count}")
        print(f"  Inf in first 5 windows: {inf_count}")
        print(f"  mask==True  count: {mask_true}")
        print(f"  mask==False count: {mask_false}")
        
        # Per-channel mask False fraction in training set
        if split == "train":
            full_data = data[:]
            full_mask = mask[:]
            print(f"\n  Per-channel mask=False fraction (training):")
            for ci, ch in enumerate(CHANNELS):
                false_frac = (~full_mask[:, :, ci]).mean() * 100
                nan_frac   = np.isnan(full_data[:, :, ci]).mean() * 100
                print(f"    {ch:<16} mask=False: {false_frac:6.2f}%   NaN: {nan_frac:6.2f}%")
            
            # Find a window with mask=False and show its value
            for wi in range(len(full_mask)):
                for ci in range(len(CHANNELS)):
                    if not full_mask[wi, :, ci].all():
                        false_t = np.where(~full_mask[wi, :, ci])[0]
                        vals = full_data[wi, false_t, ci]
                        print(f"\n  Example masked position: window={wi}, channel={CHANNELS[ci]}")
                        print(f"    mask=False at timesteps: {false_t}")
                        print(f"    stored values at those timesteps: {vals}")
                        print(f"    is NaN? {np.isnan(vals).any()}")
                        break
                else:
                    continue
                break

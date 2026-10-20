import h5py
import json

def inspect_data():
    for ds in ["physionet", "wesad"]:
        print(f"\n--- {ds.upper()} ---")
        h5_path = f"data/generated_attacks/{ds}/{ds}_attacks.h5"
        meta_path = f"data/generated_attacks/{ds}/{ds}_attacks_metadata.json"
        
        with h5py.File(h5_path, "r") as f:
            print(f"HDF5 Arrays: {list(f['test'].keys())}")
            print(f"Test Data Shape: {f['test']['attacked_data'].shape} -> [Windows, Channels, Sequence, Time]")
            
        with open(meta_path, "r") as m:
            meta = json.load(m)
            print(f"Total Test Windows: {len(meta['test'])}")

if __name__ == "__main__":
    inspect_data()

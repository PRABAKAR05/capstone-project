import json
import h5py
import numpy as np
import pandas as pd

def analyze_samples(dataset: str, h5_path: str, meta_path: str):
    print(f"\n{'='*50}\nANALYSIS FOR {dataset.upper()}\n{'='*50}")
    
    with open(meta_path, "r") as f:
        meta = json.load(f)
        
    with h5py.File(h5_path, "r") as f:
        grp = f["samples"]
        
        # We will collect stats for a pandas dataframe to print
        rows = []
        
        for i, m in enumerate(meta):
            family = m["attack_family"]
            if family == "clean":
                continue
                
            sev = m["severity"]
            chans = m["attacked_channels"]
            
            clean = grp["clean_data"][i]
            att = grp["attacked_data"][i]
            a_mask = grp["attack_mask"][i]
            
            start = m["attack_start"]
            end = m["attack_end"]
            
            # Calculate modified %
            mod_pct = (np.sum(a_mask) / a_mask.size) * 100
            
            # Mean and Max delta over the modified region
            if np.sum(a_mask) > 0:
                diff = np.abs(att[a_mask] - clean[a_mask])
                mean_d = np.mean(diff)
                max_d = np.max(diff)
            else:
                mean_d = 0.0
                max_d = 0.0
                
            rows.append({
                "Dataset": dataset,
                "Attack": family,
                "Channels": ",".join(chans),
                "Severity": sev,
                "Modified%": f"{mod_pct:.1f}%",
                "Mean Delta": f"{mean_d:.3f}",
                "Max Delta": f"{max_d:.3f}",
                "Violations": m.get("plausibility_violation", "None")
            })
            
            # Deep dive on Coordinated attacks
            if family.startswith("coordinated") and len(chans) >= 2:
                # Find indices of first two channels
                # Since channels aren't passed strictly mapped in HDF5 for sample (only names in meta),
                # we'll approximate the correlation printout. 
                pass
                
        df = pd.DataFrame(rows)
        print(df.to_string(index=False))

if __name__ == "__main__":
    analyze_samples("physionet", "data/generated_attacks/physionet/samples.h5", "data/generated_attacks/physionet/samples_metadata.json")
    analyze_samples("wesad", "data/generated_attacks/wesad/samples.h5", "data/generated_attacks/wesad/samples_metadata.json")

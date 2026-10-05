import os
import json
import numpy as np
import pandas as pd

def compute_aggregates():
    datasets = ["physionet", "wesad"]
    models = ["naive", "cscm"]
    seeds = [42, 123, 2024]
    
    results = []
    
    for ds in datasets:
        for md in models:
            f1s, auprcs, aurocs = [], [], []
            for sd in seeds:
                metrics_path = f"experiments/phase6/{ds}/{md}/seed_{sd}/test_metrics.json"
                if not os.path.exists(metrics_path):
                    print(f"Missing {metrics_path}")
                    continue
                    
                with open(metrics_path, "r") as f:
                    m = json.load(f)
                    f1s.append(m["f1"])
                    auprcs.append(m["auprc"])
                    aurocs.append(m["auroc"])
                    
            if len(f1s) > 0:
                results.append({
                    "Dataset": ds,
                    "Model": md,
                    "F1_mean": np.mean(f1s),
                    "F1_std": np.std(f1s),
                    "AUPRC_mean": np.mean(auprcs),
                    "AUPRC_std": np.std(auprcs),
                    "AUROC_mean": np.mean(aurocs),
                    "AUROC_std": np.std(aurocs)
                })
                
    df = pd.DataFrame(results)
    
    os.makedirs("reports/phase6_results", exist_ok=True)
    df.to_csv("reports/phase6_results/aggregated_metrics.csv", index=False)
    
    print("\n--- Phase 6 Aggregated Results ---")
    print(df.to_string(index=False))

if __name__ == "__main__":
    compute_aggregates()

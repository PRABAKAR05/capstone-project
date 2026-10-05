import os
import json
import numpy as np
import pandas as pd

def compute_comparisons():
    datasets = ["physionet", "wesad"]
    # Model A: naive, Model B: ablation, Model C: cscm
    models = ["naive", "ablation", "cscm"]
    model_names = {"naive": "A (Naive)", "ablation": "B (Graph-Only)", "cscm": "C (CSCM)"}
    seeds = [42, 123, 2024]
    
    results = []
    
    # Load all individual seeds
    for ds in datasets:
        for md in models:
            for sd in seeds:
                if md == "ablation":
                    metrics_path = f"experiments/phase7/{ds}/{md}/seed_{sd}/test_metrics.json"
                else:
                    metrics_path = f"experiments/phase6/{ds}/{md}/seed_{sd}/test_metrics.json"
                
                if not os.path.exists(metrics_path):
                    continue
                    
                with open(metrics_path, "r") as f:
                    m = json.load(f)
                    results.append({
                        "Dataset": ds,
                        "Model": model_names[md],
                        "Seed": sd,
                        "F1": m["f1"],
                        "AUPRC": m["auprc"],
                        "AUROC": m["auroc"]
                    })
                    
    df_all = pd.DataFrame(results)
    os.makedirs("reports/phase7_results", exist_ok=True)
    df_all.to_csv("reports/phase7_results/all_seeds.csv", index=False)
    
    print("--- Individual Seed Results ---")
    print(df_all.to_string(index=False))
    
    # Calculate means and deltas
    agg_results = []
    for ds in datasets:
        ds_data = df_all[df_all["Dataset"] == ds]
        
        means = {}
        stds = {}
        for md in ["A (Naive)", "B (Graph-Only)", "C (CSCM)"]:
            md_data = ds_data[ds_data["Model"] == md]
            if len(md_data) > 0:
                means[md] = md_data[["F1", "AUPRC", "AUROC"]].mean()
                stds[md] = md_data[["F1", "AUPRC", "AUROC"]].std()
                
        # Format aggregate rows
        for md in ["A (Naive)", "B (Graph-Only)", "C (CSCM)"]:
            if md in means:
                row = {
                    "Dataset": ds,
                    "Model": md,
                    "F1_mean": means[md]["F1"], "F1_std": stds[md]["F1"],
                    "AUPRC_mean": means[md]["AUPRC"], "AUPRC_std": stds[md]["AUPRC"],
                    "AUROC_mean": means[md]["AUROC"], "AUROC_std": stds[md]["AUROC"],
                }
                
                # Add deltas
                if md == "B (Graph-Only)" and "A (Naive)" in means:
                    row["Delta_F1"] = means["B (Graph-Only)"]["F1"] - means["A (Naive)"]["F1"]
                    row["Delta_AUPRC"] = means["B (Graph-Only)"]["AUPRC"] - means["A (Naive)"]["AUPRC"]
                    row["Delta_AUROC"] = means["B (Graph-Only)"]["AUROC"] - means["A (Naive)"]["AUROC"]
                elif md == "C (CSCM)" and "B (Graph-Only)" in means:
                    row["Delta_F1"] = means["C (CSCM)"]["F1"] - means["B (Graph-Only)"]["F1"]
                    row["Delta_AUPRC"] = means["C (CSCM)"]["AUPRC"] - means["B (Graph-Only)"]["AUPRC"]
                    row["Delta_AUROC"] = means["C (CSCM)"]["AUROC"] - means["B (Graph-Only)"]["AUROC"]
                else:
                    row["Delta_F1"] = 0.0
                    row["Delta_AUPRC"] = 0.0
                    row["Delta_AUROC"] = 0.0
                    
                agg_results.append(row)
                
    df_agg = pd.DataFrame(agg_results)
    df_agg.to_csv("reports/phase7_results/aggregated_metrics.csv", index=False)
    
    print("\n--- Aggregated Means and Deltas ---")
    print(df_agg.to_string(index=False))

if __name__ == "__main__":
    compute_comparisons()

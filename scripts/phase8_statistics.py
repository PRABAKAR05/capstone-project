import os
import json
import numpy as np
import pandas as pd
import h5py
from sklearn.metrics import roc_auc_score, average_precision_score, f1_score
import scipy.stats

def load_predictions(dataset, model, seed):
    if model == "ablation":
        path = f"models/{dataset}/{model}/seed_{seed}/test_predictions.csv"
    else:
        path = f"models/{dataset}/{model}/seed_{seed}/test_predictions.csv"
        
    df = pd.read_csv(path)
    return df

def get_group_ids(dataset):
    if dataset == "physionet":
        # Check data/processed/physionet/ for the file
        h5_path = "data/processed/physionet/physionet_grid30_win2h_7be100f8.h5"
        key = "record_id"
    else:
        h5_path = "data/processed/wesad/wesad_rate4hz_win30s_5cbc160d.h5"
        key = "subject_id"
        
    with h5py.File(h5_path, "r") as f:
        group_ids = f["test"][key][:]
        
    if isinstance(group_ids[0], bytes):
        group_ids = [gid.decode('utf-8') for gid in group_ids]
    return np.array(group_ids)

def hierarchical_bootstrap_diff(df_A, df_B, group_ids, n_resamples=1000):
    unique_groups = np.unique(group_ids)
    
    diff_f1 = []
    diff_auprc = []
    diff_auroc = []
    
    # Pre-compute indices for each group for fast lookup
    group_to_indices = {g: np.where(group_ids == g)[0] for g in unique_groups}
    
    # Extract arrays
    true_labels = df_A["true_label"].values
    prob_A = df_A["prob"].values
    pred_A = df_A["pred"].values
    prob_B = df_B["prob"].values
    pred_B = df_B["pred"].values
    
    rng = np.random.default_rng(42) # fixed seed for reproducibility of bootstrap
    
    for _ in range(n_resamples):
        sampled_groups = rng.choice(unique_groups, size=len(unique_groups), replace=True)
        
        sample_indices = []
        for g in sampled_groups:
            sample_indices.extend(group_to_indices[g])
            
        sample_indices = np.array(sample_indices)
        
        y_true = true_labels[sample_indices]
        # Fast exit if only one class is present in the sample (very rare but possible)
        if len(np.unique(y_true)) < 2:
            continue
            
        p_A = prob_A[sample_indices]
        p_B = prob_B[sample_indices]
        pr_A = pred_A[sample_indices]
        pr_B = pred_B[sample_indices]
        
        f1_A = f1_score(y_true, pr_A)
        f1_B = f1_score(y_true, pr_B)
        
        auprc_A = average_precision_score(y_true, p_A)
        auprc_B = average_precision_score(y_true, p_B)
        
        auroc_A = roc_auc_score(y_true, p_A)
        auroc_B = roc_auc_score(y_true, p_B)
        
        diff_f1.append(f1_B - f1_A)
        diff_auprc.append(auprc_B - auprc_A)
        diff_auroc.append(auroc_B - auroc_A)
        
    def get_ci(dist):
        return np.percentile(dist, 2.5), np.percentile(dist, 97.5)
        
    return {
        "F1": get_ci(diff_f1),
        "AUPRC": get_ci(diff_auprc),
        "AUROC": get_ci(diff_auroc)
    }

def mcnemar_test(df_A, df_B):
    y_true = df_A["true_label"].values
    pred_A = df_A["pred"].values
    pred_B = df_B["pred"].values
    
    # n00: both correct
    # n01: A correct, B wrong
    # n10: A wrong, B correct
    # n11: both wrong
    
    correct_A = (pred_A == y_true)
    correct_B = (pred_B == y_true)
    
    n00 = np.sum(correct_A & correct_B)
    n01 = np.sum(correct_A & ~correct_B)
    n10 = np.sum(~correct_A & correct_B)
    n11 = np.sum(~correct_A & ~correct_B)
    
    # McNemar statistic with continuity correction
    b = n01
    c = n10
    
    if b + c == 0:
        stat = 0.0
        p_value = 1.0
    else:
        stat = ((abs(b - c) - 1.0) ** 2) / (b + c)
        p_value = scipy.stats.chi2.sf(stat, 1)
        
    return stat, p_value, b, c

def run_analysis():
    datasets = ["physionet", "wesad"]
    seeds = [42, 123, 2024]
    
    results = []
    
    for ds in datasets:
        group_ids = get_group_ids(ds)
        
        for seed in seeds:
            df_A = load_predictions(ds, "naive", seed)
            df_B = load_predictions(ds, "ablation", seed)
            df_C = load_predictions(ds, "cscm", seed)
            
            # Map test predictions back to group IDs using original_index
            # The test_predictions.csv has 'original_index' which corresponds to the test split index
            g_A = group_ids[df_A["original_index"].values]
            
            # 1. Compare B vs A
            ci_B_A = hierarchical_bootstrap_diff(df_A, df_B, g_A)
            stat_BA, p_BA, b_BA, c_BA = mcnemar_test(df_A, df_B)
            
            # 2. Compare C vs B
            ci_C_B = hierarchical_bootstrap_diff(df_B, df_C, g_A)
            stat_CB, p_CB, b_CB, c_CB = mcnemar_test(df_B, df_C)
            
            results.append({
                "Dataset": ds,
                "Seed": seed,
                "Comparison": "B - A (Graph vs Naive)",
                "F1_CI": f"[{ci_B_A['F1'][0]:.4f}, {ci_B_A['F1'][1]:.4f}]",
                "AUPRC_CI": f"[{ci_B_A['AUPRC'][0]:.4f}, {ci_B_A['AUPRC'][1]:.4f}]",
                "AUROC_CI": f"[{ci_B_A['AUROC'][0]:.4f}, {ci_B_A['AUROC'][1]:.4f}]",
                "McNemar_b": b_BA,
                "McNemar_c": c_BA,
                "McNemar_stat": stat_BA,
                "McNemar_p": p_BA
            })
            
            results.append({
                "Dataset": ds,
                "Seed": seed,
                "Comparison": "C - B (CSCM vs Graph)",
                "F1_CI": f"[{ci_C_B['F1'][0]:.4f}, {ci_C_B['F1'][1]:.4f}]",
                "AUPRC_CI": f"[{ci_C_B['AUPRC'][0]:.4f}, {ci_C_B['AUPRC'][1]:.4f}]",
                "AUROC_CI": f"[{ci_C_B['AUROC'][0]:.4f}, {ci_C_B['AUROC'][1]:.4f}]",
                "McNemar_b": b_CB,
                "McNemar_c": c_CB,
                "McNemar_stat": stat_CB,
                "McNemar_p": p_CB
            })
            
    df_res = pd.DataFrame(results)
    
    os.makedirs("reports/phase8_results", exist_ok=True)
    df_res.to_csv("reports/phase8_results/statistical_tests.csv", index=False)
    
    print(df_res.to_string())

if __name__ == "__main__":
    run_analysis()

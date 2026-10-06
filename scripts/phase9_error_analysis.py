import os
import json
import pandas as pd
import numpy as np
from sklearn.metrics import recall_score, precision_score, f1_score, confusion_matrix

def load_data(dataset):
    # Load metadata
    meta_path = f"data/generated_attacks/{dataset}/{dataset}_attacks_metadata.json"
    with open(meta_path, "r") as f:
        meta = json.load(f)["test"]
        
    meta_df = pd.DataFrame(meta)
    meta_df["original_index"] = meta_df.index
    
    # We will pool predictions across all 3 seeds for robust error analysis
    seeds = [42, 123, 2024]
    
    b_preds = []
    c_preds = []
    
    for s in seeds:
        df_b = pd.read_csv(f"models/{dataset}/ablation/seed_{s}/test_predictions.csv")
        df_b["seed_run"] = s
        b_preds.append(df_b)
        
        df_c = pd.read_csv(f"models/{dataset}/cscm/seed_{s}/test_predictions.csv")
        df_c["seed_run"] = s
        c_preds.append(df_c)
        
    df_b = pd.concat(b_preds, ignore_index=True)
    df_c = pd.concat(c_preds, ignore_index=True)
    
    # Merge metadata
    df_b = df_b.merge(meta_df, on="original_index", suffixes=("", "_meta"))
    df_c = df_c.merge(meta_df, on="original_index", suffixes=("", "_meta"))
    
    return df_b, df_c

def calc_metrics(df):
    y_true = df["true_label"].values
    y_pred = df["pred"].values
    
    if len(np.unique(y_true)) < 2:
        return 0, 0, 0, 0, 0
        
    rec = recall_score(y_true, y_pred, zero_division=0)
    prec = precision_score(y_true, y_pred, zero_division=0)
    f1 = f1_score(y_true, y_pred, zero_division=0)
    
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    
    return rec, prec, f1, fp, fn

def analyze_dataset(dataset, df_b, df_c, out_f):
    out_f.write(f"## {dataset.upper()} Error Analysis\n\n")
    
    # A. Attack Characteristics
    out_f.write("### A. Attack Characteristics (Model B / Graph-Only)\n")
    out_f.write("| Subgroup | Total Windows | Attacked | Recall | Precision | F1 | FP | FN |\n")
    out_f.write("|---|---|---|---|---|---|---|---|\n")
    
    # Composition Groups (Single, Coordinated 2, Coordinated 3)
    for comp in ["clean", "single_channel", "coordinated_2", "coordinated_3"]:
        sub = df_b[df_b["composition_group"] == comp]
        n_tot = len(sub)
        n_att = sub["true_label"].sum()
        if n_tot > 0:
            rec, prec, f1, fp, fn = calc_metrics(sub)
            out_f.write(f"| {comp} | {n_tot} | {n_att} | {rec:.4f} | {prec:.4f} | {f1:.4f} | {fp} | {fn} |\n")
            
    # Attack Family
    for fam in ["additive", "multiplicative", "drift"]:
        sub = df_b[df_b["attack_family"] == fam]
        n_tot = len(sub)
        n_att = sub["true_label"].sum()
        if n_tot > 0:
            rec, prec, f1, fp, fn = calc_metrics(sub)
            out_f.write(f"| {fam} | {n_tot} | {n_att} | {rec:.4f} | {prec:.4f} | {f1:.4f} | {fp} | {fn} |\n")
            
    # Severity
    for sev in ["low", "medium", "high"]:
        sub = df_b[df_b["severity"] == sev]
        n_tot = len(sub)
        n_att = sub["true_label"].sum()
        if n_tot > 0:
            rec, prec, f1, fp, fn = calc_metrics(sub)
            out_f.write(f"| Severity: {sev} | {n_tot} | {n_att} | {rec:.4f} | {prec:.4f} | {f1:.4f} | {fp} | {fn} |\n")
            
    out_f.write("\n")
    
    # B. Dataset/Channel Characteristics
    out_f.write("### B. Channel Breakdown (Model B / Graph-Only)\n")
    out_f.write("*(Note: Evaluated on Single-Channel attacks to isolate channel discriminability)*\n\n")
    out_f.write("| Channel | Total Windows | Attacked | Recall | Precision | F1 | FP | FN |\n")
    out_f.write("|---|---|---|---|---|---|---|---|\n")
    
    single_b = df_b[df_b["composition_group"] == "single_channel"]
    # attacked_channels is a list, extract the first element
    single_b = single_b.copy()
    single_b["target_chan"] = single_b["attacked_channels"].apply(lambda x: x[0] if isinstance(x, list) and len(x)>0 else "None")
    
    channels = single_b["target_chan"].unique()
    for ch in channels:
        if ch == "None": continue
        sub = single_b[single_b["target_chan"] == ch]
        n_tot = len(sub)
        n_att = sub["true_label"].sum()
        if n_tot > 0:
            rec, prec, f1, fp, fn = calc_metrics(sub)
            out_f.write(f"| {ch} | {n_tot} | {n_att} | {rec:.4f} | {prec:.4f} | {f1:.4f} | {fp} | {fn} |\n")
            
    out_f.write("\n")
    
    # Missingness/Imputation Status
    out_f.write("### C. Impact of Missingness (Model B / Graph-Only)\n")
    out_f.write("| NaN Count in Window | Total Windows | Attacked | Recall | Precision | F1 | FP | FN |\n")
    out_f.write("|---|---|---|---|---|---|---|---|\n")
    
    df_b["has_nans"] = df_b["nan_positions"] > 0
    for has_n in [False, True]:
        sub = df_b[df_b["has_nans"] == has_n]
        n_tot = len(sub)
        n_att = sub["true_label"].sum()
        if n_tot > 0:
            rec, prec, f1, fp, fn = calc_metrics(sub)
            lbl = "Contains NaNs" if has_n else "Clean/Fully Observed"
            out_f.write(f"| {lbl} | {n_tot} | {n_att} | {rec:.4f} | {prec:.4f} | {f1:.4f} | {fp} | {fn} |\n")
            
    out_f.write("\n")
    
    # D. Model Disagreement (B vs C)
    out_f.write("### D. Model Disagreement (Graph-Only vs CSCM)\n")
    out_f.write("Breakdown of predictions where Models B and C disagree across the pooled seeds.\n\n")
    
    df_merged = df_b[["original_index", "seed_run", "true_label", "pred", "composition_group", "attack_family"]].merge(
        df_c[["original_index", "seed_run", "pred"]], 
        on=["original_index", "seed_run"], 
        suffixes=("_B", "_C")
    )
    
    b_correct = (df_merged["pred_B"] == df_merged["true_label"])
    c_correct = (df_merged["pred_C"] == df_merged["true_label"])
    
    both_correct = (b_correct & c_correct).sum()
    both_wrong = (~b_correct & ~c_correct).sum()
    b_only = (b_correct & ~c_correct).sum()
    c_only = (~b_correct & c_correct).sum()
    
    out_f.write("| Disagreement Type | Count | % of Total |\n")
    out_f.write("|---|---|---|\n")
    total = len(df_merged)
    out_f.write(f"| Both Models Correct | {both_correct} | {both_correct/total*100:.2f}% |\n")
    out_f.write(f"| Both Models Wrong | {both_wrong} | {both_wrong/total*100:.2f}% |\n")
    out_f.write(f"| **Model B Correct, C Wrong** | **{b_only}** | **{b_only/total*100:.2f}%** |\n")
    out_f.write(f"| **Model C Correct, B Wrong** | **{c_only}** | **{c_only/total*100:.2f}%** |\n")
    out_f.write("\n")
    

def main():
    os.makedirs("reports", exist_ok=True)
    with open("reports/ERROR_ANALYSIS.md", "w") as f:
        f.write("# Error and Failure Analysis\n\n")
        f.write("This document provides a deep dive into the specific detection behaviors, edge cases, and failure modes of the Graph-Only model (Model B) and compares disagreements with the Full CSCM model (Model C). Predictions are pooled across all 3 random seeds (42, 123, 2024).\n\n")
        
        df_b_phys, df_c_phys = load_data("physionet")
        analyze_dataset("physionet", df_b_phys, df_c_phys, f)
        
        df_b_wes, df_c_wes = load_data("wesad")
        analyze_dataset("wesad", df_b_wes, df_c_wes, f)

if __name__ == "__main__":
    main()

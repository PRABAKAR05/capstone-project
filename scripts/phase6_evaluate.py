import argparse
import json
import os
import yaml
import torch
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, average_precision_score, f1_score, precision_recall_curve
from torch.utils.data import DataLoader

from src.data.phase6_dataset import Phase6FDIDataset
from src.models.naive_multichannel import NaiveMultiChannelModel
from src.models.cscm import CSCM
from src.utils.reproducibility import set_all_seeds

def find_best_threshold(y_true, y_prob):
    precision, recall, thresholds = precision_recall_curve(y_true, y_prob)
    f1_scores = 2 * (precision * recall) / (precision + recall + 1e-8)
    best_idx = np.argmax(f1_scores)
    # the last threshold can sometimes be omitted in precision_recall_curve return array
    if best_idx < len(thresholds):
        return thresholds[best_idx]
    return 0.5

def evaluate(dataset_name, model_name, seed):
    set_all_seeds(seed)
    
    with open("configs/phase6.yaml", "r") as f:
        config = yaml.safe_load(f)
        
    ds_conf = config[dataset_name]
    channels = ds_conf["channels"]
    fusion_dim = ds_conf["fusion_dim"]
    
    h5_path = f"data/generated_attacks/{dataset_name}/{dataset_name}_attacks.h5"
    meta_path = f"data/generated_attacks/{dataset_name}/{dataset_name}_attacks_metadata.json"
    norm_path = f"data/processed/normalization/{dataset_name}_normalization.json"
    
    with open(norm_path, "r") as f:
        norm_stats = json.load(f)
        
    val_ds = Phase6FDIDataset(h5_path, meta_path, "val", channels, norm_stats)
    test_ds = Phase6FDIDataset(h5_path, meta_path, "test", channels, norm_stats)
    
    val_loader = DataLoader(val_ds, batch_size=config["training"]["batch_size"], shuffle=False)
    test_loader = DataLoader(test_ds, batch_size=config["training"]["batch_size"], shuffle=False)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    if model_name == "naive":
        model = NaiveMultiChannelModel(num_channels=len(channels), fusion_dim=fusion_dim)
    elif model_name == "cscm":
        model = CSCM(dataset_name=dataset_name, num_channels=len(channels), relation_dim=config["model"]["relation_dim"])
    elif model_name == "ablation":
        from src.models.cscm_ablation import GraphOnlyAblation
        model = GraphOnlyAblation(dataset_name=dataset_name, num_channels=len(channels), relation_dim=config["model"]["relation_dim"])
        out_dir = f"experiments/phase7/{dataset_name}/{model_name}/seed_{seed}"
    else:
        raise ValueError(f"Unknown model_name: {model_name}")
        
    if model_name != "ablation":
        out_dir = f"experiments/phase6/{dataset_name}/{model_name}/seed_{seed}"
    model.load_state_dict(torch.load(os.path.join(out_dir, "checkpoint.pt"), map_location=device))
    model = model.to(device)
    model.eval()
    
    def get_preds(loader):
        probs, labels, idxs = [], [], []
        with torch.no_grad():
            for x, y, idx in loader:
                x = x.to(device)
                logits = model(x)
                probs.extend(torch.sigmoid(logits).cpu().numpy().flatten())
                labels.extend(y.numpy().flatten())
                idxs.extend(idx.numpy().flatten())
        return np.array(probs), np.array(labels), np.array(idxs)
        
    val_probs, val_labels, _ = get_preds(val_loader)
    best_thresh = find_best_threshold(val_labels, val_probs)
    
    test_probs, test_labels, test_idxs = get_preds(test_loader)
    test_preds = (test_probs >= best_thresh).astype(int)
    
    # Save predictions with metadata
    with open(meta_path, "r") as f:
        full_meta = json.load(f)["test"]
        
    results = []
    for i, orig_idx in enumerate(test_idxs):
        meta = full_meta[orig_idx]
        results.append({
            "original_index": orig_idx,
            "attack_family": meta.get("attack_family", "clean"),
            "severity": meta.get("severity", 0),
            "composition_group": meta.get("composition_group", "unknown"),
            "true_label": test_labels[i],
            "prob": test_probs[i],
            "pred": test_preds[i]
        })
        
    df = pd.DataFrame(results)
    df.to_csv(os.path.join(out_dir, "test_predictions.csv"), index=False)
    
    auroc = roc_auc_score(test_labels, test_probs)
    auprc = average_precision_score(test_labels, test_probs)
    f1 = f1_score(test_labels, test_preds)
    
    metrics = {
        "auroc": float(auroc),
        "auprc": float(auprc),
        "f1": float(f1),
        "threshold": float(best_thresh)
    }
    with open(os.path.join(out_dir, "test_metrics.json"), "w") as f:
        json.dump(metrics, f, indent=4)
        
    print(f"[{dataset_name} | {model_name} | Seed {seed}] Test F1: {f1:.4f} | AUPRC: {auprc:.4f} | AUROC: {auroc:.4f}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, choices=["physionet", "wesad"])
    parser.add_argument("--model", required=True, choices=["naive", "cscm", "ablation"])
    parser.add_argument("--seed", type=int, required=True)
    args = parser.parse_args()
    evaluate(args.dataset, args.model, args.seed)

"""
CSCM-IoMT Phase 5: Evaluate Independent Baseline Models
=======================================================
Evaluates the channel-specific 1D CNN baseline models on the test split.

Outputs:
1. Channel-level metrics (AUROC, AUPRC, F1 at frozen threshold)
2. Detectability breakdown by attack family (Single vs Coordinated)
3. Aggregate single-channel ensemble analysis (max of scores across channels)
"""

import argparse
import json
import logging
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
from sklearn.metrics import roc_auc_score, auc, precision_recall_curve
from torch.utils.data import DataLoader

from src.data.baseline_dataset import SingleChannelFDIDataset
from src.models.baseline_cnn import Baseline1DCNN

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def evaluate_baselines(dataset_name: str, h5_path: str, meta_path: str, norm_path: str, channels: list[str], models_dir: Path):
    logger = logging.getLogger(f"Eval[{dataset_name}]")
    logger.info(f"Starting Baseline Evaluation for {dataset_name.upper()}")
    
    device = "cuda" if torch.cuda.is_available() else "cpu"
    
    with open(norm_path, "r") as f:
        norm_stats = json.load(f)
        
    with open(meta_path, "r") as f:
        full_meta = json.load(f)
        test_meta = full_meta.get("test", [])
        
    # We need to map which original index corresponds to which sample after filtering plausible
    # But for aggregate ensemble, we need predictions ALIGNED by window.
    # The safest way is to evaluate per channel, but keep track of window_index.
    
    channel_preds = {}
    channel_labels = {}
    
    for ch in channels:
        model_path = models_dir / f"{dataset_name}_{ch}_baseline.pt"
        if not model_path.exists():
            logger.warning(f"Model for {ch} not found. Skipping.")
            continue
            
        checkpoint = torch.load(model_path, map_location=device, weights_only=False)
        threshold = checkpoint["best_threshold"]
        
        model = Baseline1DCNN().to(device)
        model.load_state_dict(checkpoint["model_state_dict"])
        model.eval()
        
        dataset = SingleChannelFDIDataset(h5_path, meta_path, "test", ch, channels, norm_stats)
        loader = DataLoader(dataset, batch_size=128, shuffle=False)
        
        preds_dict = {}
        labels_dict = {}
        
        with torch.no_grad():
            for x, y, idxs in loader:
                x = x.to(device)
                probs = model.predict_proba(x).cpu().numpy().flatten()
                y = y.numpy().flatten()
                
                for i, prob, label in zip(idxs.numpy(), probs, y):
                    preds_dict[i] = {"prob": float(prob), "pred": int(prob >= threshold)}
                    labels_dict[i] = int(label)
                    
        channel_preds[ch] = preds_dict
        channel_labels[ch] = labels_dict
        
        # ── 1. Channel-level Metrics ──────────────────────────────────
        y_true = np.array(list(labels_dict.values()))
        y_prob = np.array([v["prob"] for v in preds_dict.values()])
        y_pred = np.array([v["pred"] for v in preds_dict.values()])
        
        if len(np.unique(y_true)) > 1:
            auroc = roc_auc_score(y_true, y_prob)
            precision, recall, _ = precision_recall_curve(y_true, y_prob)
            auprc = auc(recall, precision)
            f1 = 2 * (precision_recall_curve(y_true, y_pred)[0][1] * precision_recall_curve(y_true, y_pred)[1][1]) / (precision_recall_curve(y_true, y_pred)[0][1] + precision_recall_curve(y_true, y_pred)[1][1] + 1e-8)
            # Simpler F1:
            tp = np.sum((y_pred == 1) & (y_true == 1))
            fp = np.sum((y_pred == 1) & (y_true == 0))
            fn = np.sum((y_pred == 0) & (y_true == 1))
            prec = tp / (tp + fp + 1e-8)
            rec = tp / (tp + fn + 1e-8)
            f1_exact = 2 * (prec * rec) / (prec + rec + 1e-8)
        else:
            auroc = auprc = f1_exact = 0.0
            
        logger.info(f"[{ch}] AUROC: {auroc:.4f} | AUPRC: {auprc:.4f} | F1: {f1_exact:.4f} (Thr: {threshold:.4f})")


    # ── 2. Attack-family/severity analysis (Detectability vs Availability) ──
    logger.info("--- Attack Type Breakdown (Availability vs Detectability) ---")
    
    # We will iterate through all plausible test windows that exist across ALL evaluated channels
    # (Since we filter by is_plausible globally per channel, some channels might filter out different windows? 
    # Actually, is_plausible is a global property of the window in the metadata. So valid indices are identical across channels).
    
    # Get common valid indices
    if not channel_preds:
        return
        
    common_indices = list(list(channel_preds.values())[0].keys())
    
    # Group by attack family
    family_stats = defaultdict(lambda: {"total": 0, "detected_by_any": 0})
    
    for idx in common_indices:
        meta = test_meta[idx]
        family = meta["attack_family"]
        sev = meta["severity"]
        attacked_channels = meta["attacked_channels"]
        
        # We define "Aggregate Detected" if ANY channel's model predicts 1
        any_detected = False
        for ch in channels:
            if ch in channel_preds and channel_preds[ch][idx]["pred"] == 1:
                any_detected = True
                break
                
        group_key = f"{family}_{sev}"
        family_stats[group_key]["total"] += 1
        if any_detected:
            family_stats[group_key]["detected_by_any"] += 1
            
    for k, v in sorted(family_stats.items()):
        total = v["total"]
        if total > 0:
            det = v["detected_by_any"]
            logger.info(f"  {k:<20}: {det}/{total} detected ({det/total*100:.1f}%)")


    # ── 3. Aggregate single-channel ensemble analysis ───────────────────
    logger.info("--- Aggregate Single-Channel Ensemble Analysis ---")
    
    agg_y_true = []
    agg_y_prob = []
    agg_y_pred = []
    
    for idx in common_indices:
        meta = test_meta[idx]
        # Overall label for the window: is ANY channel attacked?
        # Alternatively, we just read meta["attack_family"] != "clean"
        is_attack = int(meta["attack_family"] != "clean")
        
        max_prob = 0.0
        any_pred = 0
        
        for ch in channels:
            if ch in channel_preds:
                prob = channel_preds[ch][idx]["prob"]
                pred = channel_preds[ch][idx]["pred"]
                if prob > max_prob: max_prob = prob
                if pred == 1: any_pred = 1
                
        agg_y_true.append(is_attack)
        agg_y_prob.append(max_prob)
        agg_y_pred.append(any_pred)
        
    agg_y_true = np.array(agg_y_true)
    agg_y_prob = np.array(agg_y_prob)
    agg_y_pred = np.array(agg_y_pred)
    
    if len(np.unique(agg_y_true)) > 1:
        agg_auroc = roc_auc_score(agg_y_true, agg_y_prob)
        precision, recall, _ = precision_recall_curve(agg_y_true, agg_y_prob)
        agg_auprc = auc(recall, precision)
        
        tp = np.sum((agg_y_pred == 1) & (agg_y_true == 1))
        fp = np.sum((agg_y_pred == 1) & (agg_y_true == 0))
        fn = np.sum((agg_y_pred == 0) & (agg_y_true == 1))
        prec = tp / (tp + fp + 1e-8)
        rec = tp / (tp + fn + 1e-8)
        agg_f1 = 2 * (prec * rec) / (prec + rec + 1e-8)
        
        logger.info(f"Aggregate Ensemble AUROC: {agg_auroc:.4f}")
        logger.info(f"Aggregate Ensemble AUPRC: {agg_auprc:.4f}")
        logger.info(f"Aggregate Ensemble F1:    {agg_f1:.4f} (Recall: {rec:.4f}, Precision: {prec:.4f})")
    else:
        logger.info("Not enough classes for aggregate ROC/PR computation.")
        
    logger.info("Phase 5 Evaluation Complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=str, required=True, choices=["physionet", "wesad"])
    args = parser.parse_args()
    
    models_dir = Path("models/baseline")
    
    if args.dataset == "physionet":
        h5_path = "data/generated_attacks/physionet/physionet_attacks.h5"
        meta_path = "data/generated_attacks/physionet/physionet_attacks_metadata.json"
        norm_path = "data/processed/normalization/physionet_normalization.json"
        channels = ["HR", "NISysABP", "NIDiasABP", "NIMAP", "Temp"]
    else:
        h5_path = "data/generated_attacks/wesad/wesad_attacks.h5"
        meta_path = "data/generated_attacks/wesad/wesad_attacks_metadata.json"
        norm_path = "data/processed/normalization/wesad_normalization.json"
        channels = [
            "chest_ACC_0", "chest_ACC_1", "chest_ACC_2", "chest_ECG", "chest_EDA",
            "chest_EMG", "chest_Resp", "chest_Temp", "wrist_ACC_0", "wrist_ACC_1",
            "wrist_ACC_2", "wrist_BVP", "wrist_EDA", "wrist_TEMP"
        ]
        
    evaluate_baselines(args.dataset, h5_path, meta_path, norm_path, channels, models_dir)

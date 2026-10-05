"""
CSCM-IoMT Phase 5: Train Independent Baseline Models
====================================================
Trains a separate 1D CNN baseline model for each physiological channel.

Features:
- Independent model per channel.
- Uses exact NaN processing and normalization from Phase 3.
- Tracks Val AUPRC to save the best model and choose the optimal F1 threshold.
- Freezes the F1 threshold based on Val set.
"""

import argparse
import json
import logging
import os
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import precision_recall_curve, roc_auc_score, auc
from torch.utils.data import DataLoader

from src.data.baseline_dataset import SingleChannelFDIDataset
from src.models.baseline_cnn import Baseline1DCNN

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def train_channel_model(
    dataset_name: str,
    channel_name: str,
    h5_path: str,
    meta_path: str,
    norm_path: str,
    all_channels: list[str],
    out_dir: Path,
    epochs: int = 20,
    batch_size: int = 128,
    lr: float = 1e-3,
    device: str = "cuda" if torch.cuda.is_available() else "cpu"
):
    logger = logging.getLogger(f"Train[{channel_name}]")
    logger.info(f"Initializing independent baseline for {dataset_name} channel: {channel_name}")
    
    with open(norm_path, "r") as f:
        norm_stats = json.load(f)
        
    train_dataset = SingleChannelFDIDataset(h5_path, meta_path, "train", channel_name, all_channels, norm_stats)
    val_dataset = SingleChannelFDIDataset(h5_path, meta_path, "val", channel_name, all_channels, norm_stats)
    
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, drop_last=True)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False)
    
    model = Baseline1DCNN().to(device)
    criterion = nn.BCEWithLogitsLoss()
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr)
    
    best_val_auprc = -1.0
    best_threshold = 0.5
    
    model_save_path = out_dir / f"{dataset_name}_{channel_name}_baseline.pt"
    
    for epoch in range(epochs):
        model.train()
        train_loss = 0.0
        for x, y, _ in train_loader:
            x, y = x.to(device), y.to(device)
            optimizer.zero_grad()
            logits = model(x)
            loss = criterion(logits, y)
            loss.backward()
            optimizer.step()
            train_loss += loss.item()
            
        train_loss /= len(train_loader)
        
        model.eval()
        val_loss = 0.0
        all_y = []
        all_probs = []
        with torch.no_grad():
            for x, y, _ in val_loader:
                x, y = x.to(device), y.to(device)
                logits = model(x)
                loss = criterion(logits, y)
                val_loss += loss.item()
                probs = torch.sigmoid(logits)
                
                all_y.extend(y.cpu().numpy())
                all_probs.extend(probs.cpu().numpy())
                
        val_loss /= len(val_loader)
        
        # Calculate metrics
        all_y = np.array(all_y).flatten()
        all_probs = np.array(all_probs).flatten()
        
        # If there are no positive samples (e.g. clean only, which shouldn't happen), AUPRC is undefined
        if len(np.unique(all_y)) > 1:
            auroc = roc_auc_score(all_y, all_probs)
            precision, recall, thresholds = precision_recall_curve(all_y, all_probs)
            auprc = auc(recall, precision)
            
            # Find best F1 threshold on val set
            f1_scores = 2 * (precision * recall) / (precision + recall + 1e-8)
            best_idx = np.argmax(f1_scores)
            best_f1 = f1_scores[best_idx]
            threshold_for_best_f1 = thresholds[best_idx] if best_idx < len(thresholds) else thresholds[-1]
        else:
            auroc = 0.0
            auprc = 0.0
            best_f1 = 0.0
            threshold_for_best_f1 = 0.5
            
        logger.info(f"Epoch {epoch+1:02d} | Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f} | Val AUROC: {auroc:.4f} | Val AUPRC: {auprc:.4f} | Val F1: {best_f1:.4f}")
        
        if auprc > best_val_auprc:
            best_val_auprc = auprc
            best_threshold = threshold_for_best_f1
            torch.save({
                "epoch": epoch,
                "model_state_dict": model.state_dict(),
                "best_val_auprc": best_val_auprc,
                "best_threshold": float(best_threshold),
                "val_auroc": auroc
            }, model_save_path)
            logger.info(f"  --> Saved new best model (AUPRC: {auprc:.4f}, Threshold: {best_threshold:.4f})")
            
    logger.info(f"Finished training {channel_name}. Best Val AUPRC: {best_val_auprc:.4f}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=str, required=True, choices=["physionet", "wesad"])
    args = parser.parse_args()
    
    out_dir = Path("models/baseline")
    out_dir.mkdir(parents=True, exist_ok=True)
    
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
        
    for ch in channels:
        train_channel_model(args.dataset, ch, h5_path, meta_path, norm_path, channels, out_dir)

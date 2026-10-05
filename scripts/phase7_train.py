import argparse
import json
import os
import yaml
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader
from sklearn.metrics import precision_recall_curve, auc
import numpy as np

from src.data.phase6_dataset import Phase6FDIDataset
from src.models.cscm_ablation import GraphOnlyAblation
from src.utils.reproducibility import set_all_seeds

def get_auprc(y_true, y_prob):
    if len(np.unique(y_true)) < 2:
        return 0.0
    precision, recall, _ = precision_recall_curve(y_true, y_prob)
    return auc(recall, precision)

def train(dataset_name, model_name, seed):
    set_all_seeds(seed)
    
    with open("configs/phase6.yaml", "r") as f:
        config = yaml.safe_load(f)
        
    ds_conf = config[dataset_name]
    channels = ds_conf["channels"]
    
    h5_path = f"data/generated_attacks/{dataset_name}/{dataset_name}_attacks.h5"
    meta_path = f"data/generated_attacks/{dataset_name}/{dataset_name}_attacks_metadata.json"
    norm_path = f"data/processed/normalization/{dataset_name}_normalization.json"
    
    with open(norm_path, "r") as f:
        norm_stats = json.load(f)
        
    train_ds = Phase6FDIDataset(h5_path, meta_path, "train", channels, norm_stats)
    val_ds = Phase6FDIDataset(h5_path, meta_path, "val", channels, norm_stats)
    
    train_loader = DataLoader(train_ds, batch_size=config["training"]["batch_size"], shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=config["training"]["batch_size"], shuffle=False)
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    if model_name == "ablation":
        model = GraphOnlyAblation(dataset_name=dataset_name, num_channels=len(channels), relation_dim=config["model"]["relation_dim"])
    else:
        raise ValueError("This script only trains the ablation model. Use phase6_train.py for Naive/CSCM.")
        
    model = model.to(device)
    
    optimizer = optim.Adam(model.parameters(), lr=config["training"]["learning_rate"], weight_decay=config["training"]["weight_decay"])
    criterion = nn.BCEWithLogitsLoss()
    
    # Store phase 7 models in experiments/phase7
    out_dir = f"experiments/phase7/{dataset_name}/{model_name}/seed_{seed}"
    os.makedirs(out_dir, exist_ok=True)
    
    best_auprc = -1
    patience_counter = 0
    best_epoch = 0
    
    log_file = open(os.path.join(out_dir, "training_log.csv"), "w")
    log_file.write("epoch,train_loss,val_loss,val_auprc\n")
    
    for epoch in range(1, config["training"]["epochs"] + 1):
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
        val_preds = []
        val_labels = []
        with torch.no_grad():
            for x, y, _ in val_loader:
                x, y = x.to(device), y.to(device)
                logits = model(x)
                loss = criterion(logits, y)
                val_loss += loss.item()
                val_preds.extend(torch.sigmoid(logits).cpu().numpy().flatten())
                val_labels.extend(y.cpu().numpy().flatten())
        val_loss /= len(val_loader)
        
        val_auprc = get_auprc(np.array(val_labels), np.array(val_preds))
        log_file.write(f"{epoch},{train_loss:.4f},{val_loss:.4f},{val_auprc:.4f}\n")
        log_file.flush()
        
        if val_auprc > best_auprc:
            best_auprc = val_auprc
            best_epoch = epoch
            patience_counter = 0
            torch.save(model.state_dict(), os.path.join(out_dir, "checkpoint.pt"))
        else:
            patience_counter += 1
            
        if patience_counter >= config["training"]["patience"]:
            print(f"[{dataset_name} | {model_name} | Seed {seed}] Early stopping at epoch {epoch}")
            break
            
    log_file.close()
    
    with open(os.path.join(out_dir, "model_summary.txt"), "w") as f:
        f.write(f"Best Epoch: {best_epoch}\n")
        f.write(f"Best Val AUPRC: {best_auprc:.4f}\n")
        
    print(f"[{dataset_name} | {model_name} | Seed {seed}] Done. Best Val AUPRC: {best_auprc:.4f}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", required=True, choices=["physionet", "wesad"])
    parser.add_argument("--model", required=True, choices=["ablation"])
    parser.add_argument("--seed", type=int, required=True)
    args = parser.parse_args()
    train(args.dataset, args.model, args.seed)

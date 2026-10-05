import json
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Subset

from src.data.phase6_dataset import Phase6FDIDataset
from src.models.naive_multichannel import NaiveMultiChannelModel
from src.models.cscm import CSCM

def run_smoke_test(dataset_name, model_class, model_name):
    print(f"\n--- Smoke Test: {model_name} on {dataset_name} ---")
    
    if dataset_name == "physionet":
        channels = ["HR", "NISysABP", "NIDiasABP", "NIMAP", "Temp"]
        h5_path = "data/generated_attacks/physionet/physionet_attacks.h5"
        meta_path = "data/generated_attacks/physionet/physionet_attacks_metadata.json"
        norm_path = "data/processed/normalization/physionet_normalization.json"
        fusion_dim = 256
    else:
        channels = [
            "chest_ACC_0", "chest_ACC_1", "chest_ACC_2", "chest_ECG", "chest_EDA",
            "chest_EMG", "chest_Resp", "chest_Temp", "wrist_ACC_0", "wrist_ACC_1",
            "wrist_ACC_2", "wrist_BVP", "wrist_EDA", "wrist_TEMP"
        ]
        h5_path = "data/generated_attacks/wesad/wesad_attacks.h5"
        meta_path = "data/generated_attacks/wesad/wesad_attacks_metadata.json"
        norm_path = "data/processed/normalization/wesad_normalization.json"
        fusion_dim = 90
        
    with open(norm_path, "r") as f:
        norm_stats = json.load(f)
        
    ds = Phase6FDIDataset(h5_path, meta_path, "val", channels, norm_stats)
    
    # Use a tiny subset for smoke testing (e.g. 64 samples)
    subset_indices = list(range(min(64, len(ds))))
    tiny_ds = Subset(ds, subset_indices)
    loader = DataLoader(tiny_ds, batch_size=16, shuffle=True)
    
    if model_name == "Model_B":
        model = model_class(num_channels=len(channels), fusion_dim=fusion_dim)
    else:
        model = model_class(dataset_name=dataset_name, num_channels=len(channels), relation_dim=64)
        
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    criterion = nn.BCEWithLogitsLoss()
    
    model.train()
    print("Epoch 1...")
    total_loss = 0
    for x, y, _ in loader:
        optimizer.zero_grad()
        logits = model(x)
        loss = criterion(logits, y)
        loss.backward()
        optimizer.step()
        total_loss += loss.item()
    print(f"Epoch 1 Loss: {total_loss:.4f}")
    
    print("Epoch 2...")
    total_loss2 = 0
    for x, y, _ in loader:
        optimizer.zero_grad()
        logits = model(x)
        loss = criterion(logits, y)
        loss.backward()
        optimizer.step()
        total_loss2 += loss.item()
    print(f"Epoch 2 Loss: {total_loss2:.4f}")
    
    assert total_loss2 < total_loss or abs(total_loss2 - total_loss) < 0.1, "Loss did not behave normally."
    print("Smoke test PASSED.")

if __name__ == "__main__":
    run_smoke_test("physionet", NaiveMultiChannelModel, "Model_B")
    run_smoke_test("physionet", CSCM, "Model_C")
    run_smoke_test("wesad", NaiveMultiChannelModel, "Model_B")
    run_smoke_test("wesad", CSCM, "Model_C")

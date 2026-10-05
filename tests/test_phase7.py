import pytest
import torch
from src.models.naive_multichannel import NaiveMultiChannelModel
from src.models.cscm import CSCM
from src.models.cscm_ablation import GraphOnlyAblation

def count_parameters(model):
    return sum(p.numel() for p in model.parameters() if p.requires_grad)

def test_phase7_models():
    print("\n--- Phase 7 Model Capacities ---")
    
    # 1. PhysioNet Setup
    B, C, in_ch, T = 4, 5, 2, 4
    x_phys = torch.randn(B, C, in_ch, T)
    
    model_a_phys = NaiveMultiChannelModel(num_channels=C, fusion_dim=256)  # Called Ablation A in Phase 7
    model_b_phys = GraphOnlyAblation(dataset_name="physionet", num_channels=C, relation_dim=64)
    model_c_phys = CSCM(dataset_name="physionet", num_channels=C, relation_dim=64)
    
    print(f"[PhysioNet] Ablation A (Naive): {count_parameters(model_a_phys):,}")
    print(f"[PhysioNet] Ablation B (Graph-Only): {count_parameters(model_b_phys):,}")
    print(f"[PhysioNet] Ablation C (CSCM): {count_parameters(model_c_phys):,}")
    
    out_b = model_b_phys(x_phys)
    assert out_b.shape == (B, 1)
    
    # 2. WESAD Setup
    B, C, in_ch, T = 4, 14, 2, 120
    x_wesad = torch.randn(B, C, in_ch, T)
    
    model_a_wesad = NaiveMultiChannelModel(num_channels=C, fusion_dim=90)
    model_b_wesad = GraphOnlyAblation(dataset_name="wesad", num_channels=C, relation_dim=64)
    model_c_wesad = CSCM(dataset_name="wesad", num_channels=C, relation_dim=64)
    
    print(f"[WESAD] Ablation A (Naive): {count_parameters(model_a_wesad):,}")
    print(f"[WESAD] Ablation B (Graph-Only): {count_parameters(model_b_wesad):,}")
    print(f"[WESAD] Ablation C (CSCM): {count_parameters(model_c_wesad):,}")
    
    out_b = model_b_wesad(x_wesad)
    assert out_b.shape == (B, 1)

if __name__ == "__main__":
    test_phase7_models()

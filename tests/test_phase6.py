import pytest
import torch
import numpy as np

from src.models.naive_multichannel import NaiveMultiChannelModel
from src.models.cscm import CSCM
from src.models.graph import PhysiologicalGraph

def count_parameters(model):
    return sum(p.numel() for p in model.parameters() if p.requires_grad)

def test_model_shapes_and_parameters():
    print("\n--- PARAMETER CAPACITIES ---")
    
    # 1. PhysioNet Setup
    B, C, in_ch, T = 4, 5, 2, 4
    x_phys = torch.randn(B, C, in_ch, T)
    
    model_b_phys = NaiveMultiChannelModel(num_channels=C, fusion_dim=256)
    model_c_phys = CSCM(dataset_name="physionet", num_channels=C, relation_dim=64)
    
    params_b = count_parameters(model_b_phys)
    params_c = count_parameters(model_c_phys)
    print(f"[PhysioNet] Model B: {params_b:,} | Model C: {params_c:,}")
    
    out_b = model_b_phys(x_phys)
    out_c = model_c_phys(x_phys)
    
    assert out_b.shape == (B, 1), f"Expected (B, 1), got {out_b.shape}"
    assert out_c.shape == (B, 1), f"Expected (B, 1), got {out_c.shape}"
    assert not torch.isnan(out_b).any()
    assert not torch.isnan(out_c).any()
    
    # 2. WESAD Setup
    B, C, in_ch, T = 4, 14, 2, 120
    x_wesad = torch.randn(B, C, in_ch, T)
    
    model_b_wesad = NaiveMultiChannelModel(num_channels=C, fusion_dim=90)
    model_c_wesad = CSCM(dataset_name="wesad", num_channels=C, relation_dim=64)
    
    params_b = count_parameters(model_b_wesad)
    params_c = count_parameters(model_c_wesad)
    print(f"[WESAD] Model B: {params_b:,} | Model C: {params_c:,}")
    
    out_b = model_b_wesad(x_wesad)
    out_c = model_c_wesad(x_wesad)
    
    assert out_b.shape == (B, 1), f"Expected (B, 1), got {out_b.shape}"
    assert out_c.shape == (B, 1), f"Expected (B, 1), got {out_c.shape}"
    assert not torch.isnan(out_b).any()
    assert not torch.isnan(out_c).any()
    
def test_graph_bidirectional():
    # Verify graph is explicitly bidirectional
    phys_edge_index = PhysiologicalGraph.build_edge_index("physionet", add_self_loops=False)
    wesad_edge_index = PhysiologicalGraph.build_edge_index("wesad", add_self_loops=False)
    
    for edge_idx in [phys_edge_index, wesad_edge_index]:
        edges_set = set(zip(edge_idx[0].tolist(), edge_idx[1].tolist()))
        for u, v in edges_set:
            assert (v, u) in edges_set, f"Edge ({u}, {v}) is missing bidirectional partner ({v}, {u})"

if __name__ == "__main__":
    test_model_shapes_and_parameters()
    test_graph_bidirectional()

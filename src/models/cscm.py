import torch
import torch.nn as nn
from .temporal_encoder import SharedTemporalEncoder
from .consistency import PairwiseConsistencyModule
from .graph import PhysiologicalGraph

class CSCM(nn.Module):
    """
    Model C: Cross-Sensor Consistency Model.
    Explicitly models the physiological relationships between sensors.
    """
    def __init__(self, dataset_name: str, num_channels: int, input_channels: int = 2, hidden_channels: int = 64, relation_dim: int = 64):
        super().__init__()
        
        self.num_channels = num_channels
        self.dataset_name = dataset_name
        
        # 1. Temporal Encoder
        self.temporal_encoder = SharedTemporalEncoder(input_channels, hidden_channels)
        temporal_out_dim = self.temporal_encoder.output_dim  # 256
        
        # 2. Channel Identity Embeddings
        self.channel_embeddings = nn.Embedding(num_channels, temporal_out_dim)
        
        # 3. Fixed Graph Definition
        # shape: (2, E)
        self.register_buffer("edge_index", PhysiologicalGraph.build_edge_index(dataset_name, add_self_loops=False))
        
        # 4. Explicit Pairwise Consistency Module
        self.consistency_module = PairwiseConsistencyModule(node_dim=temporal_out_dim, relation_dim=relation_dim)
        
        # 5. Node Update Module (integrates aggregated relation features)
        self.node_update = nn.Sequential(
            nn.Linear(temporal_out_dim + relation_dim, temporal_out_dim),
            nn.GELU(),
            nn.Linear(temporal_out_dim, temporal_out_dim)
        )
        
        # 6. Final Classifier
        self.classifier = nn.Sequential(
            nn.Linear(temporal_out_dim, 128),
            nn.ReLU(inplace=True),
            nn.Dropout(0.2),
            nn.Linear(128, 1)
        )
        
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        x: (B, C, 2, T)
        Returns: (B, 1) logits
        """
        B, C, in_ch, T = x.shape
        assert C == self.num_channels, f"Expected {self.num_channels} channels, got {C}"
        
        # 1. Temporal Encoding
        x_reshaped = x.view(B * C, in_ch, T)
        z = self.temporal_encoder(x_reshaped)  # (B*C, 256)
        z = z.view(B, C, -1)  # (B, C, 256)
        
        # 2. Add Channel Embeddings
        # (C) -> (C, 256) -> broadcast to (B, C, 256)
        channel_ids = torch.arange(C, device=x.device)
        emb = self.channel_embeddings(channel_ids)
        z = z + emb.unsqueeze(0)
        
        # 3. Cross-Sensor Consistency Graph Message Passing
        E = self.edge_index.shape[1]
        
        if E > 0:
            src_idx = self.edge_index[0]  # (E,)
            dst_idx = self.edge_index[1]  # (E,)
            
            # Extract representations for edge endpoints
            z_src = z[:, src_idx, :]  # (B, E, 256)
            z_dst = z[:, dst_idx, :]  # (B, E, 256)
            
            # Compute relation features r_ij
            r_ij = self.consistency_module(z_src, z_dst)  # (B, E, relation_dim)
            
            # Aggregate relations for each target node (mean or sum aggregation)
            # We use scatter_add to sum relations arriving at each dst_idx
            # r_ij is (B, E, D_rel). We want (B, C, D_rel)
            aggregated_relations = torch.zeros(B, C, r_ij.shape[-1], device=x.device, dtype=r_ij.dtype)
            
            # Expand dst_idx to match dimensions for scatter_add_
            # dst_idx: (E,) -> (1, E, 1) -> (B, E, D_rel)
            scatter_idx = dst_idx.unsqueeze(0).unsqueeze(-1).expand(B, E, r_ij.shape[-1])
            aggregated_relations.scatter_add_(dim=1, index=scatter_idx, src=r_ij)
            
            # 4. Node Update
            # Concat original node representation with aggregated consistency information
            z_concat = torch.cat([z, aggregated_relations], dim=-1)  # (B, C, 256 + relation_dim)
            z_updated = self.node_update(z_concat)  # (B, C, 256)
            
            # Residual connection
            z = z + z_updated
            
        # 5. Global Mean Pooling over Nodes
        z_global = z.mean(dim=1)  # (B, 256)
        
        # 6. Classification
        logits = self.classifier(z_global)  # (B, 1)
        
        return logits

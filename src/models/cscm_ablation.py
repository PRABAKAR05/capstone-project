import torch
import torch.nn as nn
from .temporal_encoder import SharedTemporalEncoder
from .graph import PhysiologicalGraph

class GraphOnlyAblation(nn.Module):
    """
    Phase 7 Ablation B: Graph Without Explicit Consistency.
    Explicitly removes the |z_i - z_j| and z_i * z_j representations from the edge features.
    Only passes the concatenated neighbor states [z_i, z_j] to test if message passing
    alone is the primary driver of performance.
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
        self.register_buffer("edge_index", PhysiologicalGraph.build_edge_index(dataset_name, add_self_loops=False))
        
        # 4. Naive Graph Message Passing Module (Ablation B specific)
        # Input is just [z_i, z_j], so 2 * 256 = 512
        input_dim = 2 * temporal_out_dim
        intermediate_dim = 128
        
        self.relation_mlp = nn.Sequential(
            nn.Linear(input_dim, intermediate_dim),
            nn.GELU(),
            nn.Linear(intermediate_dim, relation_dim)
        )
        
        # 5. Node Update Module
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
        
        # 1. Temporal Encoding
        x_reshaped = x.view(B * C, in_ch, T)
        z = self.temporal_encoder(x_reshaped)
        z = z.view(B, C, -1)
        
        # 2. Add Channel Embeddings
        channel_ids = torch.arange(C, device=x.device)
        emb = self.channel_embeddings(channel_ids)
        z = z + emb.unsqueeze(0)
        
        # 3. Graph Message Passing
        E = self.edge_index.shape[1]
        
        if E > 0:
            src_idx = self.edge_index[0]
            dst_idx = self.edge_index[1]
            
            z_src = z[:, src_idx, :]  # (B, E, 256)
            z_dst = z[:, dst_idx, :]  # (B, E, 256)
            
            # ABLATION B LOGIC: strictly concatenate [z_i, z_j]
            r_input = torch.cat([z_src, z_dst], dim=-1)  # (B, E, 512)
            r_ij = self.relation_mlp(r_input)            # (B, E, 64)
            
            # Aggregate relations
            aggregated_relations = torch.zeros(B, C, r_ij.shape[-1], device=x.device, dtype=r_ij.dtype)
            scatter_idx = dst_idx.unsqueeze(0).unsqueeze(-1).expand(B, E, r_ij.shape[-1])
            aggregated_relations.scatter_add_(dim=1, index=scatter_idx, src=r_ij)
            
            # 4. Node Update
            z_concat = torch.cat([z, aggregated_relations], dim=-1)
            z_updated = self.node_update(z_concat)
            z = z + z_updated
            
        # 5. Global Mean Pooling
        z_global = z.mean(dim=1)
        
        # 6. Classification
        logits = self.classifier(z_global)
        
        return logits

import torch
import torch.nn as nn

class PairwiseConsistencyModule(nn.Module):
    """
    Explicit Pairwise Cross-Sensor Consistency Module.
    Constructs an explicit relation embedding between two connected sensor nodes
    using their representations, their absolute difference, and their element-wise product.
    
    This provides the network with explicit features representing sensor agreement/discrepancy.
    """
    def __init__(self, node_dim: int = 256, relation_dim: int = 64):
        super().__init__()
        
        # r_ij = [z_i, z_j, |z_i - z_j|, z_i * z_j]
        # input dim = 4 * node_dim
        input_dim = 4 * node_dim
        
        # Per user requirement: 1024 -> 128 -> 64
        intermediate_dim = 128
        
        self.relation_mlp = nn.Sequential(
            nn.Linear(input_dim, intermediate_dim),
            nn.GELU(),
            nn.Linear(intermediate_dim, relation_dim)
        )
        
    def forward(self, z_i: torch.Tensor, z_j: torch.Tensor) -> torch.Tensor:
        """
        Computes the relation embedding between source nodes z_i and target nodes z_j.
        Args:
            z_i: (E, D) Tensor of source node representations.
            z_j: (E, D) Tensor of target node representations.
        Returns:
            r_ij: (E, relation_dim) Tensor of relation embeddings.
        """
        # Absolute difference (explicit learned discrepancy)
        diff = torch.abs(z_i - z_j)
        
        # Element-wise product
        prod = z_i * z_j
        
        # Concatenate: [z_i, z_j, |z_i - z_j|, z_i * z_j]
        # Shape: (E, 4 * D)
        r_input = torch.cat([z_i, z_j, diff, prod], dim=-1)
        
        # Pass through MLP to get relation embedding
        # Shape: (E, relation_dim)
        r_ij = self.relation_mlp(r_input)
        return r_ij

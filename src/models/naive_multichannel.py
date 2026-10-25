import torch
import torch.nn as nn
from .temporal_encoder import SharedTemporalEncoder

class NaiveMultiChannelModel(nn.Module):
    """
    Model B: Naive Multi-Channel Baseline.
    Processes all channels through a shared temporal encoder, flattens the representations,
    and fuses them using an MLP. It explicitly DOES NOT use a physiological graph 
    or cross-sensor consistency modeling.
    """
    def __init__(self, num_channels: int, input_channels: int = 2, hidden_channels: int = 64, fusion_dim: int = 64):
        super().__init__()
        
        self.num_channels = num_channels
        self.temporal_encoder = SharedTemporalEncoder(input_channels, hidden_channels)
        
        # Output dim from temporal encoder is 256 per channel
        temporal_out_dim = self.temporal_encoder.output_dim
        
        # Flattened representation
        flat_dim = num_channels * temporal_out_dim
        
        # MLP Fusion
        # The fusion_dim is kept intentionally compact (e.g. 64 or 128) to prevent 
        # the parameter count of Model B from exploding (e.g. 14 * 256 * 256 = ~917k)
        # and creating an unfair capacity comparison against Model C.
        self.fusion = nn.Sequential(
            nn.Linear(flat_dim, fusion_dim),
            nn.ReLU(inplace=True),
            nn.Dropout(0.2),
            nn.Linear(fusion_dim, 1)
        )
        
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        x: (B, C, 2, T)
        Returns: (B, 1) logits
        """
        B, C, in_ch, T = x.shape
        assert C == self.num_channels, f"Expected {self.num_channels} channels, got {C}"
        
        # Reshape to treat (B*C) as batch dimension for the shared encoder
        x_reshaped = x.view(B * C, in_ch, T)
        
        # (B*C, 256)
        temporal_features = self.temporal_encoder(x_reshaped)
        
        # Reshape back and flatten channels
        # (B, C * 256)
        temporal_features = temporal_features.view(B, C * self.temporal_encoder.output_dim)
        
        # MLP Fusion -> (B, 1)
        logits = self.fusion(temporal_features)
        
        return logits

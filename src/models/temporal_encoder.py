import torch
import torch.nn as nn

class Conv1DBlock(nn.Module):
    def __init__(self, in_channels: int, out_channels: int, kernel_size: int = 3, stride: int = 1):
        super().__init__()
        padding = kernel_size // 2
        self.conv = nn.Conv1d(in_channels, out_channels, kernel_size, stride, padding, bias=False)
        self.bn = nn.BatchNorm1d(out_channels)
        self.relu = nn.ReLU(inplace=True)
        
    def forward(self, x):
        return self.relu(self.bn(self.conv(x)))

class SharedTemporalEncoder(nn.Module):
    """
    Shared temporal encoder for Phase 6 Models B and C.
    This architecture and dimensionality matches the Phase 5 baseline
    to ensure Model B and C have equivalent temporal modeling capacity.
    """
    def __init__(self, input_channels: int = 2, hidden_channels: int = 64):
        super().__init__()
        
        self.features = nn.Sequential(
            Conv1DBlock(input_channels, hidden_channels, kernel_size=5, stride=2),
            Conv1DBlock(hidden_channels, hidden_channels * 2, kernel_size=3, stride=2),
            Conv1DBlock(hidden_channels * 2, hidden_channels * 4, kernel_size=3, stride=2),
        )
        self.gap = nn.AdaptiveAvgPool1d(1)
        self.output_dim = hidden_channels * 4
        
    def forward(self, x):
        """
        x: (B*C, 2, T)
        Returns: (B*C, 256)
        """
        out = self.features(x)
        out = self.gap(out).squeeze(-1)
        return out

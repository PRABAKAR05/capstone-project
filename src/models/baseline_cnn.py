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

class Baseline1DCNN(nn.Module):
    """
    Fixed compact 1D CNN/ResNet-style temporal classifier for the Phase 5 Baseline.
    Processes a single physiological channel.
    
    Input: (B, 2, 120)  [normalized_signal, missingness_indicator]
    Output: (B, 1)      [Probability of window containing an attack on this channel]
    """
    def __init__(self, input_channels: int = 2, hidden_channels: int = 64):
        super().__init__()
        
        self.features = nn.Sequential(
            Conv1DBlock(input_channels, hidden_channels, kernel_size=5, stride=2),
            Conv1DBlock(hidden_channels, hidden_channels * 2, kernel_size=3, stride=2),
            Conv1DBlock(hidden_channels * 2, hidden_channels * 4, kernel_size=3, stride=2),
        )
        
        # Global Average Pooling (B, C, T) -> (B, C)
        self.gap = nn.AdaptiveAvgPool1d(1)
        
        # Classifier
        self.classifier = nn.Sequential(
            nn.Linear(hidden_channels * 4, hidden_channels),
            nn.ReLU(inplace=True),
            nn.Dropout(0.2),
            nn.Linear(hidden_channels, 1)
            # Note: We output logits and use BCEWithLogitsLoss during training for numerical stability.
            # Sigmoid is applied during inference.
        )
        
    def forward(self, x):
        """
        x: (B, 2, T)
        Returns: (B, 1) logits
        """
        out = self.features(x)
        out = self.gap(out).squeeze(-1)
        logits = self.classifier(out)
        return logits
        
    def predict_proba(self, x):
        """
        Returns probability of attack [0, 1].
        """
        logits = self.forward(x)
        return torch.sigmoid(logits)


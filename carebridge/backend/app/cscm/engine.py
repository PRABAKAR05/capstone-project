"""CSCM Inference Engine.

Executes deterministic, read-only PyTorch inference on multi-channel IoMT telemetry windows,
extracts grounded graph relation divergence for transparent channel attribution,
and generates calibrated, safe detection reporting.
"""

import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import torch

PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models.graph import PhysiologicalGraph
from app.cscm.model_loader import load_cscm_model, load_normalization_stats
from app.schemas.cscm import ChannelAttribution, CSCMVerificationResponse


class CSCMInferenceEngine:
    """In-process inference engine for cross-sensor consistency monitoring."""

    def __init__(self, dataset_name: str = "physionet", seed: int = 42, threshold: float = 0.85):
        self.dataset_name = dataset_name.lower()
        self.seed = seed
        self.threshold = threshold
        self.model, self.cold_load_latency_ms = load_cscm_model(dataset_name=self.dataset_name, seed=self.seed)
        self.norm_stats = load_normalization_stats(dataset_name=self.dataset_name)
        self.channels = (
            PhysiologicalGraph.PHYSIONET_CHANNELS
            if self.dataset_name == "physionet"
            else PhysiologicalGraph.WESAD_CHANNELS
        )

    def prepare_input_tensor(self, window_data: np.ndarray) -> torch.Tensor:
        """Transforms a raw (T, C) or (C, T) telemetry matrix into model-ready (1, C, 2, T) tensor."""
        if not isinstance(window_data, np.ndarray):
            window_data = np.array(window_data, dtype=np.float32)

        # Ensure shape is (T, C)
        if window_data.shape[1] != len(self.channels) and window_data.shape[0] == len(self.channels):
            window_data = window_data.T

        T, C = window_data.shape
        if C != len(self.channels):
            raise ValueError(f"Expected {len(self.channels)} channels ({self.channels}), got {C}")

        x_proc = np.zeros((1, C, 2, T), dtype=np.float32)

        for c_idx, ch_name in enumerate(self.channels):
            ch_stats = self.norm_stats.get("statistics", {}).get(ch_name, {}).get("zscore", {})
            mean = ch_stats.get("mean", 0.0)
            std = ch_stats.get("std", 1.0)
            if std == 0.0:
                std = 1.0

            col = window_data[:, c_idx]
            norm = (col - mean) / std
            missing_mask = np.isnan(norm).astype(np.float32)
            norm = np.nan_to_num(norm, nan=0.0)

            x_proc[0, c_idx, 0, :] = norm
            x_proc[0, c_idx, 1, :] = missing_mask

        return torch.tensor(x_proc, dtype=torch.float32)

    def evaluate_window(self, window_data: np.ndarray) -> Dict[str, Any]:
        """Runs forward pass, computes probability, and extracts graph edge relation divergence."""
        x_tensor = self.prepare_input_tensor(window_data)

        start_time = time.perf_counter()
        with torch.no_grad():
            # 1. Forward pass for classification logit
            logit = self.model(x_tensor).item()
            probability = float(torch.sigmoid(torch.tensor(logit)).item())

            # 2. Extract grounded graph relation divergence per channel
            B, C, in_ch, T = x_tensor.shape
            x_reshaped = x_tensor.view(B * C, in_ch, T)
            z = self.model.temporal_encoder(x_reshaped).view(B, C, -1)
            channel_ids = torch.arange(C, device=x_tensor.device)
            z = z + self.model.channel_embeddings(channel_ids).unsqueeze(0)

            E = self.model.edge_index.shape[1]
            if E > 0:
                src_idx = self.model.edge_index[0]
                dst_idx = self.model.edge_index[1]
                z_src = z[:, src_idx, :]
                z_dst = z[:, dst_idx, :]

                # Relation embeddings r_ij
                r_ij = self.model.consistency_module(z_src, z_dst)

                # Aggregate relations arriving at each channel node
                aggregated_relations = torch.zeros(
                    B, C, r_ij.shape[-1], device=x_tensor.device, dtype=r_ij.dtype
                )
                scatter_idx = dst_idx.unsqueeze(0).unsqueeze(-1).expand(B, E, r_ij.shape[-1])
                aggregated_relations.scatter_add_(dim=1, index=scatter_idx, src=r_ij)

                # Channel relation divergence norm
                channel_divergences = torch.norm(aggregated_relations, dim=-1)[0].cpu().numpy()
            else:
                channel_divergences = np.zeros(C, dtype=np.float32)

        inference_latency_ms = (time.perf_counter() - start_time) * 1000.0

        # Calibrated safe status & wording
        is_anomaly = bool(probability >= self.threshold)
        if is_anomaly:
            detection_status = "inconsistency_detected"
            display_message = "Cross-sensor inconsistency detected (Suspected FDIA)"
        else:
            detection_status = "baseline_consistent"
            display_message = "No anomaly detected by current model"

        # Compute relative attribution percentages
        total_divergence = float(np.sum(channel_divergences))
        attributions: List[ChannelAttribution] = []

        mean_div = float(np.mean(channel_divergences)) if len(channel_divergences) > 0 else 0.0

        for idx, ch_name in enumerate(self.channels):
            score = float(channel_divergences[idx])
            rel_pct = (score / total_divergence * 100.0) if total_divergence > 0 else (100.0 / C)

            # Classify divergence
            if is_anomaly and score > (mean_div * 1.15):
                div_status = "elevated_graph_divergence"
                significance = (
                    "Elevated graph relation divergence (edge residual magnitude). "
                    "Represents mathematical pairwise discrepancy along physiological edges; "
                    "does not prove hardware sensor defect."
                )
            else:
                div_status = "normal_concordance"
                significance = "Consistent physiological cross-sensor relationship with connected channels."

            attributions.append(
                ChannelAttribution(
                    channel_name=ch_name,
                    divergence_score=round(score, 4),
                    relative_divergence_pct=round(rel_pct, 2),
                    divergence_status=div_status,
                    clinical_significance=significance,
                )
            )

        return {
            "detection_status": detection_status,
            "display_message": display_message,
            "anomaly_probability": round(probability, 4),
            "anomaly_logit": round(logit, 4),
            "threshold": self.threshold,
            "is_anomaly": is_anomaly,
            "channel_attributions": attributions,
            "disclaimer": (
                "Advisory integrity warning only. Does not replace clinical assessment or "
                "certified biomedical equipment inspection."
            ),
            "inference_latency_ms": round(inference_latency_ms, 2),
            "model_version": f"CSCM-v1.0 (seed={self.seed}, dataset={self.dataset_name})",
        }

    def benchmark_inference(self, num_iterations: int = 50) -> Dict[str, Any]:
        """Measures cold load vs. warm per-window inference latency."""
        sample_window = np.zeros((4, len(self.channels)), dtype=np.float32)
        # Populate with baseline mean values
        for c_idx, ch in enumerate(self.channels):
            mean = self.norm_stats.get("statistics", {}).get(ch, {}).get("zscore", {}).get("mean", 80.0)
            sample_window[:, c_idx] = mean

        latencies: List[float] = []
        for _ in range(num_iterations):
            start = time.perf_counter()
            _ = self.evaluate_window(sample_window)
            latencies.append((time.perf_counter() - start) * 1000.0)

        mean_lat = float(np.mean(latencies))
        p95_lat = float(np.percentile(latencies, 95))

        return {
            "cold_load_latency_ms": round(self.cold_load_latency_ms, 2),
            "mean_inference_latency_ms": round(mean_lat, 2),
            "p95_inference_latency_ms": round(p95_lat, 2),
            "total_benchmarked_windows": num_iterations,
            "device_type": "CPU",
            "weights_only_verified": True,
        }

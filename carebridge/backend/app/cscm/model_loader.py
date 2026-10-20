"""CSCM Model Loader Module.

Loads pre-trained CSCM research checkpoints strictly in read-only inference mode
with weights_only=True, parameter freezing, and isolated cold-load latency tracking.
Preserves existing capstone research models, datasets, and pipelines without mutation.
"""

import sys
import json
import time
import logging
import threading
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

import torch

logger = logging.getLogger("carebridge.cscm.model_loader")

# Resolve project root (capstone_PRABAKAR)
PROJECT_ROOT = Path(__file__).resolve().parents[4]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.models.cscm import CSCM
from src.models.graph import PhysiologicalGraph

_model_lock = threading.Lock()
_model_cache: Dict[str, Tuple[CSCM, float]] = {}  # key -> (model, cold_load_latency_ms)
_norm_cache: Dict[str, Dict[str, Any]] = {}


def get_default_checkpoint_path(dataset_name: str = "physionet", seed: int = 42) -> Path:
    """Returns absolute path to preserved research checkpoint."""
    checkpoint_path = PROJECT_ROOT / "models" / dataset_name.lower() / "cscm" / f"seed_{seed}" / "checkpoint.pt"
    if not checkpoint_path.exists():
        raise FileNotFoundError(f"Preserved CSCM checkpoint not found at {checkpoint_path}")
    return checkpoint_path


def load_normalization_stats(dataset_name: str = "physionet") -> Dict[str, Any]:
    """Loads preserved normalization parameters (z-score means and standard deviations)."""
    dataset_name = dataset_name.lower()
    if dataset_name in _norm_cache:
        return _norm_cache[dataset_name]

    norm_path = PROJECT_ROOT / "data" / "processed" / "normalization" / f"{dataset_name}_normalization.json"
    if not norm_path.exists():
        raise FileNotFoundError(f"Normalization statistics file not found at {norm_path}")

    with open(norm_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    _norm_cache[dataset_name] = data
    return data


def load_cscm_model(
    dataset_name: str = "physionet",
    seed: int = 42,
    force_reload: bool = False,
) -> Tuple[CSCM, float]:
    """Loads pre-trained CSCM model strictly in eval mode with weights_only=True.

    Returns:
        (model, cold_load_latency_ms)
    """
    dataset_name = dataset_name.lower()
    cache_key = f"{dataset_name}_seed_{seed}"

    with _model_lock:
        if not force_reload and cache_key in _model_cache:
            return _model_cache[cache_key]

        start_time = time.perf_counter()
        checkpoint_path = get_default_checkpoint_path(dataset_name=dataset_name, seed=seed)

        num_channels = len(PhysiologicalGraph.PHYSIONET_CHANNELS) if dataset_name == "physionet" else len(PhysiologicalGraph.WESAD_CHANNELS)

        # 1. Instantiate model architecture matching preserved weights
        model = CSCM(
            dataset_name=dataset_name,
            num_channels=num_channels,
            input_channels=2,
            hidden_channels=64,
            relation_dim=64,
        )

        # 2. Load weights strictly in read-only mode with weights_only=True
        state_dict = torch.load(
            str(checkpoint_path),
            map_location="cpu",
            weights_only=True,
        )
        model.load_state_dict(state_dict)

        # 3. Freeze all parameters and set to evaluation mode
        model.eval()
        for param in model.parameters():
            param.requires_grad = False

        cold_load_latency_ms = (time.perf_counter() - start_time) * 1000.0
        logger.info(
            "Loaded CSCM model '%s' (seed %d) in %.2f ms [eval=True, weights_only=True]",
            dataset_name, seed, cold_load_latency_ms
        )

        _model_cache[cache_key] = (model, cold_load_latency_ms)
        return model, cold_load_latency_ms

"""
CSCM-IoMT Reproducibility Utilities
======================================
Sets deterministic seeds for Python, NumPy, and PyTorch (when available).
Records the environment state for reproducibility documentation.

Usage::

    from src.utils.reproducibility import set_all_seeds, get_environment_state

    set_all_seeds(seed=42)
    state = get_environment_state()
"""

from __future__ import annotations

import os
import random
import sys
import platform
from typing import Any


def set_all_seeds(seed: int = 42) -> None:
    """
    Set random seeds for all available randomness sources.

    Sources seeded:
      - Python ``random`` module
      - Environment variable ``PYTHONHASHSEED`` (influences hash randomization)
      - NumPy random generator (if numpy is available)
      - PyTorch CPU and CUDA (if torch is available)

    Parameters
    ----------
    seed : int
        The random seed to use. Default is 42.

    Notes
    -----
    PyTorch determinism also requires setting
    ``torch.backends.cudnn.deterministic = True`` and
    ``torch.use_deterministic_algorithms(True)``.
    This function enables those settings when PyTorch is available.
    """
    # Python built-in
    random.seed(seed)

    # Hash seed (affects dict ordering in < 3.7 but we document it anyway)
    os.environ["PYTHONHASHSEED"] = str(seed)

    # NumPy
    try:
        import numpy as np
        np.random.seed(seed)
    except ImportError:
        pass

    # PyTorch
    try:
        import torch
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed(seed)
            torch.cuda.manual_seed_all(seed)
        # Deterministic algorithms (may be slower)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
        try:
            torch.use_deterministic_algorithms(True)
        except Exception:
            pass  # Older PyTorch versions may not support this
    except ImportError:
        pass


def get_environment_state() -> dict[str, Any]:
    """
    Capture the current environment for reproducibility documentation.

    Returns
    -------
    dict
        Keys: python_version, platform, numpy_version, torch_version,
              cuda_available, cuda_version, gpu_name, pythonhashseed.
    """
    state: dict[str, Any] = {
        "python_version": sys.version,
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "numpy_version": None,
        "torch_version": None,
        "cuda_available": False,
        "cuda_version": None,
        "gpu_name": None,
        "pythonhashseed": os.environ.get("PYTHONHASHSEED", "not_set"),
    }

    try:
        import numpy as np
        state["numpy_version"] = np.__version__
    except ImportError:
        pass

    try:
        import torch
        state["torch_version"] = torch.__version__
        state["cuda_available"] = torch.cuda.is_available()
        if torch.cuda.is_available():
            state["cuda_version"] = torch.version.cuda
            state["gpu_name"] = torch.cuda.get_device_name(0)
    except ImportError:
        pass

    return state
